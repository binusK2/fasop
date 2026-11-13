"""Catu Daya / Rectifier — satu sumber angka untuk dashboard & ekspor Excel.

Dashboard Catu Daya (`views.catu_daya_dashboard`, tab "Catu Daya / Rectifier")
dan ekspor Excel-nya (`views.catu_daya_export_excel`) memanggil fungsi yang
SAMA di modul ini. Status Aman/Perhatian/Bahaya dan estimasi waktu baterai
mencapai 38 VDC adalah angka yang dipakai menilai kesiapan catu daya; berkas
yang dilampirkan ke laporan tidak boleh bisa menyebut hal lain dari layar.
Dijaga `tests_catu_daya_export.py`, yang membandingkan isi Excel dengan
context dashboard.

Satu pengecualian yang disengaja: HAR tanpa data discharge sama sekali
(`ada_data` False). Dashboard menampilkannya "Bahaya" karena tegangan kosong
terhitung 0 V; ekspor menulis "Tanpa data discharge" — lihat `label_status()`.
"""
from collections import defaultdict
from datetime import date

from django.db.models import Q
from django.utils import timezone

from devices.models import Device

from .models import MaintenanceRectifier

THRESHOLD_VDC = 38.0

# Titik waktu discharge (jam) ↔ kunci di bat1_cells.
TITIK_DISCHARGE = ((0, 'vd_0'), (0.5, 'vd_half'), (1, 'vd_1'), (2, 'vd_2'))

STATUS_LABEL = {'ok': 'Aman', 'warning': 'Perhatian', 'danger': 'Bahaya'}


# ─────────────────────────────────────────────────────────────────────
# Data
# ─────────────────────────────────────────────────────────────────────
def perangkat_catu_daya():
    """Semua perangkat berjenis Catu Daya / Rectifier yang belum dihapus."""
    return (
        Device.objects
        .filter(is_deleted=False, jenis__isnull=False)
        .filter(Q(jenis__name__icontains='catu') | Q(jenis__name__icontains='rectifier'))
        .select_related('jenis')
        .order_by('lokasi', 'nama')
    )


def rekaman_har(devices, dengan_pelaksana=False):
    """{device_id: [MaintenanceRectifier, ...]} urut HAR terlama → terbaru.

    Satu query untuk semua perangkat (dulu satu query per perangkat).
    `maintenance__is_deleted=False` WAJIB: lookup lintas relasi melewati
    `MaintenanceManager`, jadi tanpa penyaring ini pemeliharaan yang sudah
    di-soft-delete Teknisi diam-diam ikut terbaca lagi.
    """
    qs = (
        MaintenanceRectifier.objects
        .filter(maintenance__device__in=devices, maintenance__is_deleted=False)
        .select_related('maintenance')
        .order_by('maintenance__date', 'pk')
    )
    if dengan_pelaksana:
        qs = qs.prefetch_related('maintenance__technicians')
    peta = defaultdict(list)
    for rec in qs:
        peta[rec.maintenance.device_id].append(rec)
    return peta


# ─────────────────────────────────────────────────────────────────────
# Perhitungan discharge
# ─────────────────────────────────────────────────────────────────────
def _nilai_baris_vtotal(cells, field):
    """Nilai dari baris ringkasan "vtotal" di bat1_cells (diisi saat input form)."""
    row = next((c for c in cells if str(c.get('cell', '')) == 'vtotal'), None)
    if row:
        v = row.get(field)
        return round(float(v), 3) if v not in (None, '', 0) else None
    return None


def _jumlah_sel(cells, field):
    """Jumlah tegangan sel individual — hanya sel bernomor, bukan baris ringkasan."""
    vals = [float(c[field]) for c in cells
            if isinstance(c.get('cell'), int) and c.get(field) not in (None, '', 0)]
    return round(sum(vals), 3) if vals else None


def nilai_bank(cells, field):
    """Tegangan total bank: baris "vtotal" dulu, jumlah sel bila kosong."""
    v = _nilai_baris_vtotal(cells, field)
    return v if v is not None else _jumlah_sel(cells, field)


def v_float(rec):
    """V Float total bank sebelum discharge; jatuh ke V Total Bank bila kosong."""
    return nilai_bank(rec.bat1_cells or [], 'v_float') or rec.bat1_v_total


def titik_discharge(rec):
    """Titik kurva: V Float di t = -0.5 (referensi), lalu VD 0 / 0.5 / 1 / 2 jam."""
    cells = rec.bat1_cells or []
    titik = []
    vf = v_float(rec)
    if vf:
        titik.append({'t': -0.5, 'v': round(float(vf), 3), 'label': 'V Float'})
    for t, field in TITIK_DISCHARGE:
        v = nilai_bank(cells, field)
        if v is not None:
            titik.append({'t': t, 'v': v})
    return titik


def linreg(xs, ys):
    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2 = sum(x * x for x in xs)
    d = n * sx2 - sx * sx
    if d == 0:
        return None, None
    slope = (n * sxy - sx * sy) / d
    intercept = (sy - slope * sx) / n
    return slope, intercept


def analisa_discharge(rec):
    """Kurva, prediksi linear, estimasi capai 38 VDC, dan status satu HAR."""
    actual = titik_discharge(rec)
    # Regresi hanya dari titik VD (t >= 0), bukan V Float.
    pts = [p for p in actual if p['t'] >= 0]

    prediction = []
    threshold_time = None
    slope = None
    if len(pts) >= 2:
        sl, intercept = linreg([p['t'] for p in pts], [p['v'] for p in pts])
        if sl is not None:
            slope = sl
            for t in [x / 2 for x in range(5, 21)]:
                prediction.append({'t': t, 'v': round(sl * t + intercept, 3)})
            if sl < 0:
                t_thr = (THRESHOLD_VDC - intercept) / sl
                if t_thr > 0:
                    threshold_time = round(t_thr, 2)

    latest_v = pts[-1]['v'] if pts else (rec.bat1_v_total or 0)
    if latest_v <= THRESHOLD_VDC:
        status = 'danger'
    elif threshold_time is not None and threshold_time <= 10:
        status = 'warning'
    else:
        status = 'ok'

    return {
        'actual':         actual,
        'prediction':     prediction,
        'threshold_time': threshold_time,
        'slope':          slope,
        'status':         status,
        'cukup_titik':    len(pts) >= 2,
        # Tanpa titik VD dan tanpa V Total Bank, `latest_v` di atas jatuh ke 0
        # sehingga `status` menjadi 'danger' — padahal tidak ada yang diukur.
        # Dashboard (masih) menampilkannya sebagai Bahaya; ekspor tidak.
        'ada_data':       bool(pts) or rec.bat1_v_total is not None,
    }


def label_status(analisa):
    """Teks kolom "Status" di ekspor.

    Tidak tahu ≠ tegangan 0 V: perangkat tanpa data discharge sama sekali
    tidak ditulis "Bahaya" di berkas yang dilampirkan ke laporan.
    """
    if not analisa['ada_data']:
        return 'Tanpa data discharge'
    return STATUS_LABEL[analisa['status']]


def label_estimasi(analisa):
    """Isi kolom "Est. Capai 38 V": angka jam, atau teks bila tidak ada.

    Sama dengan teks di dashboard, kecuali saat data discharge tidak cukup:
    di layar itu tampil "> 10 jam" atau "Sudah ≤ 38V", padahal yang
    sebenarnya terjadi adalah tidak ada data untuk menghitungnya — di berkas
    yang dilampirkan ke laporan klaim itu tidak boleh ikut tercetak.
    """
    if not analisa['ada_data']:
        return 'Tanpa data discharge'
    if analisa['threshold_time'] is not None:
        return analisa['threshold_time']
    if analisa['status'] == 'danger':
        return 'Sudah ≤ 38 V'
    if not analisa['cukup_titik']:
        return 'Data discharge kurang'
    return '> 10 jam'


# ─────────────────────────────────────────────────────────────────────
# Ekspor Excel
# ─────────────────────────────────────────────────────────────────────
CAKUPAN = {
    'semua': 'Semua perangkat catu daya (yang belum HAR dibiarkan kosong)',
    'har':   'Hanya perangkat catu daya yang sudah di-HAR',
}


def tanggal_lokal(dt):
    """Tanggal WITA dari DateTimeField. `dt.date()` langsung memberi tanggal
    UTC — HAR/inspeksi pagi hari (sebelum 08.00 WITA) jatuh ke hari kemarin."""
    if dt is None:
        return None
    return timezone.localtime(dt).date() if timezone.is_aware(dt) else dt.date()


def _tgl(m):
    return tanggal_lokal(m.date)


def _pelaksana(m):
    nama = [t.get_full_name() or t.username for t in m.technicians.all()]
    if not nama:
        nama = [str(n) for n in (m.pelaksana_names or []) if n]
    return ', '.join(nama)


def _kolom(cakupan_ringkasan):
    """(grup, judul, lebar, ambil(dev, rec, analisa, jumlah_har)).

    `rec`/`analisa` None = perangkat belum pernah di-HAR → sel kosong.
    `cakupan_ringkasan` True untuk sheet utama (satu baris per perangkat);
    sheet riwayat tidak memuat kolom "Jumlah HAR".
    """
    def r(attr):
        return lambda d, rec, a, n: getattr(rec, attr) if rec else None

    def m(fn):
        return lambda d, rec, a, n: fn(rec.maintenance) if rec else None

    def bank(field):
        return lambda d, rec, a, n: nilai_bank(rec.bat1_cells or [], field) if rec else None

    kolom = [
        ('Perangkat', 'No', 5, None),
        ('Perangkat', 'Nama Perangkat', 28, lambda d, rec, a, n: d.nama),
        ('Perangkat', 'Lokasi', 24, lambda d, rec, a, n: d.lokasi),
        ('Perangkat', 'Jenis', 16, lambda d, rec, a, n: d.jenis.name if d.jenis else ''),
        ('Perangkat', 'Merk', 14, lambda d, rec, a, n: d.merk),
        ('Perangkat', 'Tipe', 16, lambda d, rec, a, n: d.type),
        ('Perangkat', 'Serial Number', 16, lambda d, rec, a, n: d.serial_number),
        ('Perangkat', 'Status Operasi', 13, lambda d, rec, a, n: d.get_status_operasi_display()),

        ('HAR', 'Tgl HAR', 12, m(_tgl)),
    ]
    if cakupan_ringkasan:
        kolom.append(('HAR', 'Jumlah HAR', 9, lambda d, rec, a, n: n))
    kolom += [
        ('HAR', 'Status HAR', 10, m(lambda mt: mt.status)),
        ('HAR', 'Pelaksana', 26, m(_pelaksana)),

        ('Rectifier', 'Merk', 14, r('rect1_merk')),
        ('Rectifier', 'Tipe', 14, r('rect1_tipe')),
        ('Rectifier', 'Kapasitas', 11, r('rect1_kapasitas')),
        ('Rectifier', 'Kondisi', 9, r('rect1_kondisi')),
        ('Rectifier', 'V Rectifier (V)', 11, r('rect1_v_rectifier')),
        ('Rectifier', 'V Battery (V)', 11, r('rect1_v_battery')),
        ('Rectifier', 'V Load (V)', 11, r('rect1_v_load')),
        ('Rectifier', 'Teg (+) Ground (V)', 11, r('rect1_teg_pos_ground')),
        ('Rectifier', 'Teg (−) Ground (V)', 11, r('rect1_teg_neg_ground')),
        ('Rectifier', 'V Dropper (V)', 11, r('rect1_v_dropper')),
        ('Rectifier', 'A Rectifier (A)', 11, r('rect1_a_rectifier')),
        ('Rectifier', 'A Battery (A)', 11, r('rect1_a_battery')),
        ('Rectifier', 'A Load (A)', 11, r('rect1_a_load')),

        ('Battery Bank', 'Merk', 14, r('bat1_merk')),
        ('Battery Bank', 'Tipe', 14, r('bat1_tipe')),
        ('Battery Bank', 'Kapasitas', 11, r('bat1_kapasitas')),
        ('Battery Bank', 'Jumlah Cell', 9, r('bat1_jumlah')),
        ('Battery Bank', 'Kondisi', 9, r('bat1_kondisi')),
        ('Battery Bank', 'Kabel', 8, r('bat1_kondisi_kabel')),
        ('Battery Bank', 'Mur & Baut', 8, r('bat1_kondisi_mur_baut')),
        ('Battery Bank', 'Sel & Rak', 8, r('bat1_kondisi_sel_rak')),
        ('Battery Bank', 'Air Battery', 9, r('bat1_air_battery')),
        ('Battery Bank', 'V Total Bank (V)', 11, r('bat1_v_total')),
        ('Battery Bank', 'V Load Bank (V)', 11, r('bat1_v_load')),

        ('Discharge & Prediksi', 'V Float (V)', 11,
         lambda d, rec, a, n: v_float(rec) if rec else None),
        ('Discharge & Prediksi', 'VD 0 Jam (V)', 11, bank('vd_0')),
        ('Discharge & Prediksi', 'VD 0.5 Jam (V)', 11, bank('vd_half')),
        ('Discharge & Prediksi', 'VD 1 Jam (V)', 11, bank('vd_1')),
        ('Discharge & Prediksi', 'VD 2 Jam (V)', 11, bank('vd_2')),
        ('Discharge & Prediksi', 'Laju Penurunan (V/jam)', 12,
         lambda d, rec, a, n: round(a['slope'], 4) if a and a['slope'] else None),
        ('Discharge & Prediksi', 'Est. Capai 38 V (jam)', 13,
         lambda d, rec, a, n: label_estimasi(a) if a else None),
        ('Discharge & Prediksi', 'Status', 13,
         lambda d, rec, a, n: label_status(a) if a else None),

        ('Lingkungan', 'Suhu Ruangan (°C)', 10, r('suhu_ruangan')),
        ('Lingkungan', 'Exhaust Fan', 13, r('exhaust_fan')),
        ('Lingkungan', 'Kebersihan', 10, r('kebersihan')),
        ('Lingkungan', 'Lampu', 12, r('lampu_penerangan')),

        ('Catatan', 'Catatan', 36, r('catatan')),
    ]
    return kolom


def buat_workbook(cakupan):
    """Workbook ekspor + nama berkasnya. `cakupan` salah satu kunci CAKUPAN."""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    devices = list(perangkat_catu_daya())
    har = rekaman_har(devices, dengan_pelaksana=True)
    sudah_har = [d for d in devices if har.get(d.id)]
    baris_perangkat = devices if cakupan == 'semua' else sudah_har

    sekarang = timezone.localtime(timezone.now())
    thin = Side(style='thin', color='CBD5E1')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    f_hdr = Font(bold=True, color='FFFFFF', size=10)
    f_grup = Font(bold=True, color='0F172A', size=10)
    a_hdr = Alignment(horizontal='center', vertical='center', wrap_text=True)
    a_tengah = Alignment(horizontal='center', vertical='center')
    a_kiri = Alignment(vertical='center', wrap_text=True)
    warna_grup = {
        'Perangkat': 'E2E8F0', 'HAR': 'DBEAFE', 'Rectifier': 'D1FAE5',
        'Battery Bank': 'FEF3C7', 'Discharge & Prediksi': 'EDE9FE',
        'Lingkungan': 'E0F2FE', 'Catatan': 'F1F5F9',
    }
    gaya_status = {
        'Aman':      ('D1FAE5', '065F46'),
        'Perhatian': ('FEF3C7', '92400E'),
        'Bahaya':    ('FEE2E2', '991B1B'),
        'Tanpa data discharge': ('F1F5F9', '64748B'),
    }
    f_nok = Font(bold=True, color='991B1B')
    f_kosong = Font(italic=True, color='94A3B8')

    def tulis_sheet(ws, judul, kolom, baris):
        n = len(kolom)
        # Judul tidak digabung sel: sel gabungan yang melintasi batas freeze
        # pane ikut tergulung dan terpotong; teks biasa cukup meluber.
        ws['A1'] = judul
        ws['A1'].font = Font(bold=True, size=12)
        ws.row_dimensions[1].height = 24
        ws['A2'] = (f'{CAKUPAN[cakupan]} · {len(devices)} perangkat, '
                    f'{len(sudah_har)} sudah HAR · Dicetak {sekarang:%d/%m/%Y %H:%M}')
        ws['A2'].font = Font(italic=True, size=9, color='64748B')

        # Baris 4: grup kolom (digabung), baris 5: judul kolom.
        mulai = 1
        for ci in range(2, n + 2):
            if ci <= n and kolom[ci - 1][0] == kolom[mulai - 1][0]:
                continue
            grup = kolom[mulai - 1][0]
            sel = ws.cell(row=4, column=mulai, value=grup)
            sel.font = f_grup
            sel.alignment = a_hdr
            sel.fill = PatternFill('solid', fgColor=warna_grup[grup])
            sel.border = border
            if ci - 1 > mulai:
                ws.merge_cells(start_row=4, start_column=mulai, end_row=4, end_column=ci - 1)
            mulai = ci
        for ci, (_, judul_kolom, lebar, _) in enumerate(kolom, 1):
            sel = ws.cell(row=5, column=ci, value=judul_kolom)
            sel.font = f_hdr
            sel.fill = PatternFill('solid', fgColor='0F172A')
            sel.alignment = a_hdr
            sel.border = border
            ws.column_dimensions[get_column_letter(ci)].width = lebar
        ws.row_dimensions[5].height = 32
        ws.freeze_panes = 'C6'

        if not baris:
            ws.cell(row=6, column=1, value='Tidak ada data.').font = f_kosong
            return

        for no, (dev, rec, analisa, jumlah) in enumerate(baris, 1):
            wr = no + 5
            for ci, (_, judul_kolom, _, ambil) in enumerate(kolom, 1):
                nilai = no if ambil is None else ambil(dev, rec, analisa, jumlah)
                if nilai == '':
                    nilai = None
                sel = ws.cell(row=wr, column=ci, value=nilai)
                sel.border = border
                if isinstance(nilai, date):
                    sel.number_format = 'DD/MM/YYYY'
                    sel.alignment = a_tengah
                elif isinstance(nilai, (int, float)):
                    sel.alignment = a_tengah
                else:
                    sel.alignment = a_kiri
                if nilai in gaya_status and judul_kolom == 'Status':
                    isi, teks = gaya_status[nilai]
                    sel.fill = PatternFill('solid', fgColor=isi)
                    sel.font = Font(bold=True, color=teks)
                elif nilai == 'NOK':
                    sel.font = f_nok

    wb = openpyxl.Workbook()

    # ── Sheet 1: satu baris per perangkat, HAR terakhir ──────────────
    ws = wb.active
    ws.title = 'Catu Daya'
    ws.sheet_properties.tabColor = '3B82F6'
    baris = []
    for dev in baris_perangkat:
        recs = har.get(dev.id) or []
        terakhir = recs[-1] if recs else None
        baris.append((dev, terakhir,
                      analisa_discharge(terakhir) if terakhir else None, len(recs)))
    tulis_sheet(ws, 'DATA HAR CATU DAYA / RECTIFIER — HAR TERAKHIR TIAP PERANGKAT',
                _kolom(True), baris)

    # ── Sheet 2: seluruh HAR, satu baris per pemeliharaan ────────────
    ws = wb.create_sheet('Riwayat HAR')
    ws.sheet_properties.tabColor = '7C3AED'
    baris = []
    for dev in sudah_har:
        for rec in har[dev.id]:
            baris.append((dev, rec, analisa_discharge(rec), None))
    tulis_sheet(ws, 'RIWAYAT HAR CATU DAYA / RECTIFIER — SELURUH PEMELIHARAAN',
                _kolom(False), baris)

    # ── Sheet 3: keterangan ──────────────────────────────────────────
    ws = wb.create_sheet('Keterangan')
    ws.sheet_properties.tabColor = '64748B'
    ws.column_dimensions['A'].width = 26
    ws.column_dimensions['B'].width = 90
    catatan = [
        ('Cakupan', CAKUPAN[cakupan]),
        ('Jumlah perangkat', f'{len(devices)} perangkat catu daya / rectifier, '
                             f'{len(sudah_har)} sudah HAR'),
        ('Dicetak', f'{sekarang:%d/%m/%Y %H:%M}'),
        ('Sheet "Catu Daya"', 'Satu baris per perangkat, berisi HAR terakhirnya. '
                              'Perangkat yang belum pernah di-HAR hanya berisi data perangkat.'),
        ('Sheet "Riwayat HAR"', 'Satu baris per pemeliharaan, urut perangkat lalu tanggal. '
                                'Status & estimasi dihitung dari data HAR baris itu sendiri.'),
        ('Tegangan bank', 'V Float & VD diambil dari baris total (vtotal) di tabel sel; '
                          'bila kosong, dijumlahkan dari tegangan tiap sel.'),
        ('Laju Penurunan', 'Kemiringan regresi linear titik VD 0 / 0.5 / 1 / 2 jam (V per jam).'),
        ('Est. Capai 38 V', 'Perpanjangan garis regresi itu sampai 38 VDC. '
                            '"Data discharge kurang" = titik VD kurang dari dua.'),
        ('Status', f'Bahaya = tegangan VD terakhir ≤ {THRESHOLD_VDC:g} V (atau V Total Bank '
                   'bila tidak ada data VD); Perhatian = estimasi capai 38 V ≤ 10 jam; '
                   'selain itu Aman. Aturan yang sama dengan Dashboard Catu Daya.'),
        ('Tanpa data discharge', 'HAR yang tidak memuat satu pun titik VD maupun V Total Bank. '
                                 'Dashboard Catu Daya saat ini menampilkan perangkat seperti ini '
                                 'sebagai "Bahaya" (tegangan kosong terhitung 0 V); di berkas ini '
                                 'ditulis apa adanya: belum ada data.'),
        ('HAR terhapus', 'Pemeliharaan yang sudah dihapus (soft-delete) tidak ikut.'),
    ]
    ws['A1'] = 'KETERANGAN EKSPOR CATU DAYA / RECTIFIER'
    ws['A1'].font = Font(bold=True, size=12)
    for i, (k, v) in enumerate(catatan, 3):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        sel = ws.cell(row=i, column=2, value=v)
        sel.alignment = Alignment(wrap_text=True, vertical='top')

    nama_file = f'catu_daya_{cakupan}_{sekarang:%Y%m%d_%H%M}.xlsx'
    return wb, nama_file
