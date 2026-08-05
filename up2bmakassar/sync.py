"""
Inti perhitungan kinerja harian SCADATEL (dipakai management command
sync_kinerja_analog / sync_kinerja_digital).

Alur per hari, per jenis (TELEMETERING/TELESIGNAL/RTU/MASTER/TELEKOMUNIKASI):
  1. Ambil master titik dari OFDB scd_c_point + scd_pointtype (kinerja=1, induk
     point type sesuai jenis) -- satu query.
  2. Hitung uptime SEMUA titik untuk hari itu -- satu query GROUP BY ke
     scd_his_analog / scd_his_digital.
  3. Titik yang tidak punya transisi sama sekali di hari itu: ambil status
     terakhir sebelum hari itu -- satu query.
  4. Simpan/replace ke KinerjaAnalogHarian / KinerjaDigitalHarian (PostgreSQL)
     dengan bulk_create, bukan update_or_create per titik.

Jadi 3 query ke OFDB per hari (bukan 4 query per titik per hari seperti script
lama up2bmakassar) -- inilah yang bikin sinkronisasi bisa selesai dalam hitungan
detik dan tabel kinerja di FASOP tidak lagi kosong.
"""
import logging
from datetime import datetime, timedelta

from django.db import transaction

from . import ofdb
from .models import KinerjaAnalogHarian, KinerjaDigitalHarian, SitePath1

logger = logging.getLogger(__name__)

# jenis -> model penyimpan hasilnya
JENIS_MODEL = {
    ofdb.JENIS_TELEMETERING:   KinerjaAnalogHarian,
    ofdb.JENIS_TELESIGNAL:     KinerjaDigitalHarian,
    ofdb.JENIS_RTU:            KinerjaDigitalHarian,
    ofdb.JENIS_MASTER:         KinerjaDigitalHarian,
    ofdb.JENIS_TELEKOMUNIKASI: KinerjaDigitalHarian,
}


def ambil_titik(cursor, jenis, seed_site=True, sumber=ofdb.SUMBER_KINERJA):
    """
    Master titik untuk satu jenis.

    SEMUA titik kinerja=1 dihitung -- sama seperti app up2bmakassar, yang tidak
    punya konsep site aktif/tidak sama sekali. SitePath1 tetap di-seed di sini
    tapi hanya dipakai sebagai filter TAMPILAN di halaman kinerja: menyembunyikan
    site dari halaman tidak boleh sampai membuat datanya tidak ikut dihitung
    (dulu begitu, akibatnya sebagian besar titik hilang dari rekap).
    """
    points = ofdb.get_kinerja_points(cursor, jenis, sumber=sumber)
    if not points:
        return []

    if seed_site:
        for path1 in sorted({p['path1'] for p in points if p['path1']}):
            SitePath1.objects.get_or_create(path1=path1)

    return points


def hitung_hari(cursor, jenis, points, tanggal, status_realtime=None, sertakan_tanpa_data=False):
    """
    Hitung kinerja semua `points` untuk satu tanggal.
    Return (list dict siap jadi baris model, jumlah titik yang dilewati).

    Titik yang tidak punya jejak sama sekali di OFDB -- tidak ada di hasil uptime
    maupun di ketiga sumber status -- DILEWATI, bukan dicatat 0%. Titik seperti itu
    bukan "tidak tersedia 100%", melainkan tidak diketahui: point_number-nya sudah
    tidak dipakai lagi. Mencatatnya 0% membuat rata-rata availability jadi ngawur
    (mis. 394 titik mati menarik angka Telemetering ke 4%).

    sertakan_tanpa_data=True mengembalikan perilaku lama (dicatat 0%), berguna
    kalau memang ingin melihat titik mana saja yang tidak punya data.
    """
    _, table = ofdb.JENIS_SUMBER[jenis]
    day_start = datetime.combine(tanggal, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    alltime = (day_end - day_start).total_seconds()

    uptime_map = ofdb.compute_kinerja_harian(cursor, table, day_start, day_end)

    # Titik tanpa transisi sama sekali di hari itu -> pakai status awal harinya
    # (snapshot harian / transisi terakhir / realtime). VALID = normal seharian.
    butuh_fallback = any(p['point_number'] not in uptime_map for p in points)
    status = (ofdb.get_status_awal_hari(cursor, table, tanggal, day_start, status_realtime)
              if butuh_fallback else {})

    hasil = []
    dilewati = 0
    for p in points:
        pn = p['point_number']
        if not sertakan_tanpa_data and pn not in uptime_map and pn not in status:
            dilewati += 1
            continue
        jlh, uptime = uptime_map.get(pn, (0, 0.0))
        if uptime == 0 and status.get(pn) == 'VALID':
            uptime = alltime
            jlh = 1
        uptime = min(uptime, alltime)
        hasil.append(dict(
            point_number=p['point_number'],
            jenis=p['jenis'],
            path1=p['path1'], path2=p['path2'], path3=p['path3'],
            path4=p['path4'], path5=p['path5'],
            b1=p['b1'], b2=p['b2'], b3=p['b3'], elem=p['elem'],
            tanggal=tanggal,
            jumlah_up=jlh,
            uptime_detik=uptime,
            alltime_detik=alltime,
            performance=(uptime / alltime * 100) if alltime else 0,
        ))
    return hasil, dilewati


def simpan_hari(model, jenis, tanggal, rows):
    """
    Replace hasil satu hari untuk satu jenis (delete + bulk_create), meniru
    'delete from scd_kin_..._harian where datum=...' di script up2bmakassar.
    """
    with transaction.atomic():
        model.objects.filter(tanggal=tanggal, jenis=jenis).delete()
        # Baris versi lama (tanpa `jenis`, dihitung dari point_type='A'/'D' saja)
        # untuk tanggal ini sudah pasti basi -- sync sekarang menulis ulang semua
        # titik untuk tanggal tersebut, jadi hapus supaya tidak dobel.
        model.objects.filter(tanggal=tanggal, jenis='').delete()
        model.objects.bulk_create([model(**r) for r in rows], batch_size=1000)


def sync_jenis(cursor, jenis, tanggal_list, dry_run=False, log=None, petakan_path=False,
               sumber=ofdb.SUMBER_KINERJA, sertakan_tanpa_data=False):
    """
    Jalankan sinkronisasi untuk satu jenis dan beberapa tanggal.
    `log` = callable(str) untuk output progres (mis. self.stdout.write).
    `petakan_path` = pakai pemetaan lewat path1..path5 untuk titik kinerja yang
    point_number-nya sudah mati (lihat ofdb.cari_kembaran).
    Return jumlah baris yang ditulis.
    """
    def _log(msg):
        if log:
            log(msg)

    model = JENIS_MODEL[jenis]
    points = ambil_titik(cursor, jenis, sumber=sumber)
    if not points:
        _log(f'[{jenis}] Tidak ada titik (sumber={sumber}) di scd_c_point '
             f'(cek nama induk point type di scd_pointtype).')
        return 0
    _log(f'[{jenis}] {len(points)} titik, sumber daftar titik: {sumber}.')

    point_type, table = ofdb.JENIS_SUMBER[jenis]

    berdata = ofdb.get_point_berdata(cursor, table)
    tanpa_data = sum(1 for p in points if p['point_number'] not in berdata)
    if tanpa_data:
        _log(f'[{jenis}] {tanpa_data} dari {len(points)} titik menunjuk point_number '
             f'yang tidak ada di tabel realtime OFDB.')
        if petakan_path:
            dipetakan, gagal = ofdb.cari_kembaran(
                points, ofdb.get_point_paths(cursor, point_type), berdata)
            _log(f'[{jenis}] Dipetakan lewat path: {dipetakan}, tetap tidak ketemu: {gagal}.')
        else:
            _log(f'[{jenis}] Coba --petakan-path kalau point_number-nya berubah '
                 f'(identitas titik dicocokkan lewat path).')

    status_realtime = ofdb.get_status_realtime(cursor, table)

    total = 0
    for tanggal in sorted(tanggal_list):
        rows, dilewati = hitung_hari(cursor, jenis, points, tanggal, status_realtime,
                                     sertakan_tanpa_data=sertakan_tanpa_data)
        uptime_total = sum(r['uptime_detik'] for r in rows)
        alltime_total = sum(r['alltime_detik'] for r in rows)
        avail = (uptime_total / alltime_total * 100) if alltime_total else 0
        nol = sum(1 for r in rows if r['uptime_detik'] == 0)

        keterangan = (f'{tanggal} titik={len(rows)} avail={avail:.2f}% '
                      f'0%={nol} dilewati={dilewati}')
        if dry_run:
            _log(f'[DRY][{jenis}] {keterangan}')
        else:
            simpan_hari(model, jenis, tanggal, rows)
            total += len(rows)
            _log(f'[{jenis}] {keterangan}')
    return total
