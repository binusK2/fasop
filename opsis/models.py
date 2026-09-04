import re
import time

from django.db import models
from django.contrib.auth.models import User


JENIS_CHOICES = [
    ('PLTA',  'PLTA — Tenaga Air'),
    ('PLTB',  'PLTB — Tenaga Bayu'),
    ('PLTD',  'PLTD — Tenaga Diesel'),
    ('PLTU',  'PLTU — Tenaga Uap'),
    ('PLTG',  'PLTG — Tenaga Gas'),
    ('PLTGU', 'PLTGU — Gas & Uap'),
    ('PLTS',  'PLTS — Tenaga Surya'),
    ('LAIN',  'Lainnya'),
]


# Warna per jenis pembangkit — dipakai kartu/chart komposisi dashboard dan ikon
# Peta Pembangkit. Ini satu-satunya definisi: view yang butuh warna mengirimnya
# ke template, jangan menyalin dict ini ke dalam <script>.
JENIS_WARNA = {
    'PLTA':  '#3b82f6',
    'PLTB':  '#22c55e',
    'PLTD':  '#ef4444',
    'PLTU':  '#f59e0b',
    'PLTG':  '#a855f7',
    'PLTGU': '#06b6d4',
    'PLTS':  '#eab308',
    'LAIN':  '#64748b',
}


class Pembangkit(models.Model):
    nama          = models.CharField(max_length=100, verbose_name='Nama Pembangkit')
    kode          = models.CharField(max_length=20, unique=True, verbose_name='Kode')
    jenis         = models.CharField(max_length=10, choices=JENIS_CHOICES, default='PLTD', verbose_name='Jenis')
    warna         = models.CharField(max_length=7, default='#3b82f6', verbose_name='Warna Chart')
    supply        = models.CharField(max_length=5, blank=True, default='',
                                     choices=[('netto', 'Netto'), ('gross', 'Gross')],
                                     verbose_name='Tipe Supply',
                                     help_text='Netto / Gross. Tampil sebagai label kecil di kartu dashboard. '
                                               'Kosongkan bila tidak ingin menampilkan label.')
    urutan        = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif         = models.BooleanField(default=True, verbose_name='Aktif')
    # Tag MSSQL — diisi sesuai struktur tabel historian/SCADA
    tag_frekuensi = models.CharField(max_length=200, blank=True, verbose_name='Tag Frekuensi (MSSQL)')
    tag_mw        = models.CharField(max_length=200, blank=True, verbose_name='Tag Daya MW (MSSQL)')
    tag_mvar      = models.CharField(max_length=200, blank=True, verbose_name='Tag Daya MVAR (MSSQL)')
    # Sumber baris KIT_REALTIME + filter unit — untuk kasus satu baris KIT_REALTIME
    # berisi unit milik lebih dari satu pembangkit (mis. UNIT7_P pada baris KIT
    # 'SUPPA5' sebenarnya milik pembangkit lain).
    kode_kit      = models.CharField(max_length=20, blank=True, verbose_name='Kode KIT (MSSQL)',
                                      help_text='Kode KIT_REALTIME yang dibaca. Kosongkan jika sama dengan Kode.')
    unit_list     = models.CharField(max_length=100, blank=True, verbose_name='Unit yang Dipakai',
                                      help_text='Daftar unit dipisah koma, mis. UNIT1,UNIT2,UNIT3. '
                                                 'Kosongkan untuk memakai semua unit (UNIT1-UNIT8).')
    # ── Daya Mampu (DMN/DMP) dari tabel MSSQL KIT_DMP ─────────────────
    # Nama kolom sengaja dibuat konfigurabel dari admin karena struktur
    # KIT_DMP belum tentu sama di tiap deployment. Kosongkan dmp_key untuk
    # menonaktifkan pembacaan DMN/DMP pembangkit ini.
    dmp_key       = models.CharField(max_length=200, blank=True, verbose_name='Nilai Kunci KIT_DMP',
                                      help_text='Nilai pada Kolom Kunci KIT_DMP yang menandai pembangkit ini '
                                                '(mis. isi KIT). Pisahkan dengan koma untuk menggabungkan beberapa '
                                                'baris, contoh: POSO2A_U1,POSO2A_U2. Kosongkan untuk memakai Kode KIT / Kode.')
    dmp_kolom_dmn = models.CharField(max_length=50, blank=True, default='', verbose_name='Kolom DMN',
                                      help_text='Nama kolom KIT_DMP berisi Daya Mampu Netto (MW). '
                                                'Kosongkan bila DMN tidak tersedia.')
    dmp_kolom_dmp = models.CharField(max_length=50, blank=True, default='', verbose_name='Kolom DMP',
                                      help_text='Nama kolom KIT_DMP berisi Daya Mampu Pasok (MW). '
                                                'Kosongkan bila DMP tidak tersedia.')
    # ── Inersia (kartu Inersia Sistem di dashboard) ────────────────────
    # Energi kinetik tersimpan sebuah mesin = MVA x H. Keduanya sifat mesin,
    # bukan hasil ukur, jadi diisi manual di admin. Dikosongkan = pembangkit
    # ini tidak ikut perhitungan inersia sama sekali (bukan dianggap nol).
    mva       = models.FloatField(null=True, blank=True, verbose_name='Kapasitas S (MVA)',
                                  help_text='Daya semu terpasang dalam MVA. Kosongkan bila '
                                            'pembangkit ini tidak diikutkan hitungan inersia.')
    inersia_h = models.FloatField(null=True, blank=True, verbose_name='Konstanta Inersia H (detik)',
                                  help_text='Konstanta inersia mesin dalam detik, umumnya 2-9 s. '
                                            'Energi kinetiknya = MVA x H (MWs).')
    # ── Posisi pin pada Peta Pembangkit (/opsis/peta/) ─────────────────
    # Persen terhadap viewBox peta Sulawesi: peta_x 0=barat, 100=timur;
    # peta_y 0=utara, 100=selatan. Kosongkan untuk memakai posisi bawaan
    # opsis.hop_map.posisi_pembangkit() yang dicocokkan dari nama pembangkit;
    # isi hanya bila pembangkit belum terdaftar di sana atau pinnya perlu digeser.
    peta_x        = models.FloatField(null=True, blank=True, verbose_name='Posisi Peta X (%)',
                                      help_text='0–100, persen dari kiri peta. Kosongkan untuk posisi bawaan.')
    peta_y        = models.FloatField(null=True, blank=True, verbose_name='Posisi Peta Y (%)',
                                      help_text='0–100, persen dari atas peta. Kosongkan untuk posisi bawaan.')
    # Sakelar tampil/sembunyi ikon. Dipisah dari peta_x/peta_y karena mengosongkan
    # koordinat TIDAK menghilangkan ikon — pembangkit yang namanya terdaftar di
    # opsis.hop_map akan kembali muncul di posisi bawaannya.
    tampil_di_peta = models.BooleanField(
        default=True, verbose_name='Tampilkan Ikon di Peta',
        help_text='Hilangkan centang untuk menyembunyikan ikon pembangkit ini dari '
                  'Peta Pembangkit (mis. hanya menampilkan pembangkit berbeban besar). '
                  'Pembangkitnya tetap masuk tabel daya di sebelah peta.')
    # Penanda data tidak valid / tidak sesuai kondisi real (diisi manual oleh
    # superuser / role Opsis dari dashboard). Bila False, tampilan dashboard
    # tidak berubah; bila True, kartu diberi label ketidaksesuaian.
    data_tidak_sesuai = models.BooleanField(default=False, verbose_name='Data Tidak Sesuai')
    data_keterangan   = models.CharField(max_length=255, blank=True, default='',
                                         verbose_name='Keterangan Ketidaksesuaian')
    ditandai_oleh     = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name='+', verbose_name='Ditandai Oleh')
    ditandai_pada     = models.DateTimeField(null=True, blank=True, verbose_name='Ditandai Pada')

    class Meta:
        ordering = ['urutan', 'nama']
        verbose_name = 'Pembangkit'
        verbose_name_plural = 'Pembangkit'

    def __str__(self):
        return self.nama

    @property
    def energi_kinetik_mws(self):
        """
        Energi kinetik tersimpan (MWs) = MVA x H. None bila salah satunya
        belum diisi — sengaja None, bukan 0, supaya pembangkit yang datanya
        belum lengkap terlihat sebagai 'belum diisi' di admin dan tidak
        diam-diam menyusutkan total inersia sistem.
        """
        if self.mva is None or self.inersia_h is None:
            return None
        return self.mva * self.inersia_h

    def kit_source(self):
        """Kode KIT_REALTIME yang dibaca — kode_kit jika diisi, else kode."""
        return (self.kode_kit or self.kode).strip().upper()

    def unit_whitelist(self):
        """Set nama unit ('UNIT1'..'UNIT8') yang termasuk pembangkit ini, atau None untuk semua unit."""
        if not self.unit_list.strip():
            return None
        return {u.strip().upper() for u in self.unit_list.split(',') if u.strip()}

    def dmp_sources(self):
        """Daftar nilai kunci KIT_DMP; beberapa nilai dipisahkan dengan koma."""
        raw = self.dmp_key or self.kit_source()
        return [key.strip().upper() for key in raw.split(',') if key.strip()]

    def pakai_dmp(self):
        """True bila minimal satu kolom DMN/DMP dikonfigurasi."""
        return bool(self.dmp_kolom_dmn.strip() or self.dmp_kolom_dmp.strip())

    def posisi_peta(self):
        """
        (x%, y%) pin pada Peta Pembangkit, atau None bila pembangkit ini belum
        punya posisi. peta_x/peta_y dari admin menang atas tabel bawaan
        opsis.hop_map (dicocokkan dari nama).
        """
        from opsis.hop_map import posisi_pembangkit
        if self.peta_x is not None and self.peta_y is not None:
            return (self.peta_x, self.peta_y)
        return posisi_pembangkit(self.nama)


HOP_KATEGORI_CHOICES = [
    ('batubara', 'Batu Bara'),
    ('bbm',      'BBM'),
]

HOP_SISTEM_CHOICES = [
    ('Sulbagsel', 'Sulbagsel'),
    ('Sulutgo',   'Sulutgo'),
    ('Baubau',    'Baubau'),
]

# Band status HOP (Hari Operasi) per kategori bahan bakar — jumlah hari operasi
# yang masih dapat dicover oleh stok. Batu bara & BBM punya norma operasi
# berbeda, jadi bandnya dipisah. Ini adalah SATU-SATUNYA sumber definisi
# status: fungsi hop_status(), KPI dashboard, legenda, dan garis ambang pada
# chart semuanya diturunkan dari sini. Ubah angka/warna di sini bila kebijakan
# perusahaan berbeda.
#
# Tiap band: (kode, label, warna, batas, op) dievaluasi dari atas ke bawah;
# band dengan batas=None adalah penampung sisa (paling bawah). 'op' menentukan
# perbandingan terhadap batas: '>' (di atas) atau '>=' (mulai dari).
#   Batu bara: HOP > 15 Normal (hijau) | 10–15 Siaga (kuning) |
#              5–10 Waspada (merah) | < 5 Kritis (hitam)
#   BBM:       HOP >= 7 Normal (hijau) | 3–7 Siaga (kuning) | < 3 Kritis (merah)
HOP_BANDS = {
    'batubara': [
        ('normal',  'Normal',  '#10b981', 15,   '>'),   # HOP > 15
        ('siaga',   'Siaga',   '#f59e0b', 10,   '>'),   # 10 < HOP <= 15
        ('waspada', 'Waspada', '#ef4444', 5,    '>='),  # 5 <= HOP <= 10
        ('kritis',  'Kritis',  '#0a0a0a', None, None),  # HOP < 5 (hitam)
    ],
    'bbm': [
        ('normal',  'Normal',  '#10b981', 7,    '>='),  # HOP >= 7
        ('siaga',   'Siaga',   '#f59e0b', 3,    '>='),  # 3 <= HOP < 7
        ('kritis',  'Kritis',  '#ef4444', None, None),  # HOP < 3
    ],
}

STATUS_KOSONG = ('kosong', 'Belum ada data', '#64748b')


def _bands(kategori):
    return HOP_BANDS.get(kategori, HOP_BANDS['bbm'])


def hop_status(kategori, hop):
    """
    Kembalikan (kode, label, warna_hex) status HOP untuk sebuah nilai.
    hop None -> status 'kosong' (belum ada data).
    """
    if hop is None:
        return STATUS_KOSONG
    for kode, label, warna, batas, op in _bands(kategori):
        if batas is None:
            return (kode, label, warna)
        if op == '>' and hop > batas:
            return (kode, label, warna)
        if op == '>=' and hop >= batas:
            return (kode, label, warna)
    return STATUS_KOSONG


def hop_deskripsi_band(kategori):
    """
    Ringkasan tiap band untuk KPI/legenda: list of
    (kode, label, warna, deskripsi_rentang). Urut dari paling aman ke bahaya.
    """
    bands = _bands(kategori)
    hasil = []
    for i, (kode, label, warna, batas, op) in enumerate(bands):
        if batas is None:
            # band terbawah: di bawah batas band sebelumnya
            prev_batas = bands[i - 1][3] if i > 0 else None
            desc = f'HOP < {prev_batas:g} hari' if prev_batas is not None else '—'
        elif i == 0:
            desc = f'HOP {op} {batas:g} hari'
        else:
            prev_batas = bands[i - 1][3]
            desc = f'{batas:g} – {prev_batas:g} hari' if prev_batas is not None else f'HOP {op} {batas:g}'
        hasil.append((kode, label, warna, desc))
    return hasil


def hop_garis_ambang(kategori):
    """Nilai batas tiap band (untuk garis referensi pada chart tren)."""
    return [{'value': batas, 'warna': warna, 'label': label}
            for (kode, label, warna, batas, op) in _bands(kategori)
            if batas is not None]


class HopPembangkit(models.Model):
    """
    Master pembangkit untuk monitoring HOP (Hari Operasi) — jumlah hari
    operasi yang masih dapat dicover oleh stok bahan bakar. Berbeda dari
    model Pembangkit (OPSIS realtime MW/MVAR): daftar ini bersumber dari
    laporan konfirmasi stok batu bara / BBM (spreadsheet), bukan SCADA.
    Nilai HOP harian disimpan di HopSnapshot; kolom di sini adalah metadata
    yang diperbarui saat impor.
    """
    nama     = models.CharField(max_length=120, verbose_name='Nama Pembangkit')
    kategori = models.CharField(max_length=10, choices=HOP_KATEGORI_CHOICES, db_index=True,
                                verbose_name='Kategori Bahan Bakar')
    sistem   = models.CharField(max_length=20, choices=HOP_SISTEM_CHOICES, blank=True,
                                verbose_name='Sistem')
    aset     = models.CharField(max_length=40, blank=True, verbose_name='Aset / Pengelola')
    dmn_mw   = models.FloatField(null=True, blank=True, verbose_name='DMN (MW)')
    urutan   = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif    = models.BooleanField(default=True, verbose_name='Aktif')

    class Meta:
        unique_together = ('nama', 'kategori')
        ordering = ['kategori', 'urutan', 'nama']
        verbose_name = 'HOP — Pembangkit'
        verbose_name_plural = 'HOP — Pembangkit'

    def __str__(self):
        return f'{self.nama} ({self.get_kategori_display()})'

    def snapshot_terakhir(self):
        return self.hop_snaps.order_by('-tanggal').first()

    def hop_terakhir(self):
        snap = self.snapshot_terakhir()
        return snap.hop if snap else None

    def status_terakhir(self):
        return hop_status(self.kategori, self.hop_terakhir())


class HopSnapshot(models.Model):
    """Nilai HOP harian per pembangkit (time-series untuk tren)."""
    pembangkit = models.ForeignKey(HopPembangkit, on_delete=models.CASCADE,
                                   related_name='hop_snaps', db_index=True)
    tanggal    = models.DateField(db_index=True)
    hop        = models.FloatField(null=True, verbose_name='HOP (hari)')

    class Meta:
        unique_together = ('pembangkit', 'tanggal')
        indexes = [models.Index(fields=['pembangkit', '-tanggal'])]
        ordering = ['-tanggal']
        verbose_name = 'HOP — Snapshot Harian'
        verbose_name_plural = 'HOP — Snapshot Harian'

    def __str__(self):
        return f'{self.pembangkit.nama} @ {self.tanggal:%Y-%m-%d} — {self.hop} hari'


SUMBER_MODE_CHOICES = [
    ('baris', 'Baris — satu titik per baris (kolom kunci + kolom nilai)'),
    ('kolom', 'Kolom — satu baris berisi kolom P/Q/V/I'),
]


class Trafo(models.Model):
    """
    Registry trafo (GI + bay) yang diikutkan dalam perhitungan Beban Trafo.
    Auto-terdaftar (aktif=True) saat pertama kali muncul di ALL_TRANS_DATA
    (lihat opsis.views._trafo_aktif_saja); nonaktifkan dari admin untuk
    mengeluarkan trafo tertentu dari tampilan/perhitungan tanpa hapus data.

    Sumber Data Pengganti (field 'sumber_*'): dipakai saat titik sebuah trafo
    berhenti terupdate di ALL_TRANS_DATA (mis. IBT GITET Wotu) sementara
    nilainya masih hidup di tabel MSSQL lain. Kalau 'sumber_tabel' diisi,
    nilai trafo ini dibaca dari tabel tersebut dan MENGGANTIKAN baris
    ALL_TRANS_DATA — termasuk saat barisnya sudah hilang sama sekali dari
    ALL_TRANS_DATA (baris tetap dimunculkan). Lihat
    opsis.mssql.get_nilai_override() dan opsis.views._trafo_aktif_saja().
    """
    site   = models.CharField(max_length=100, verbose_name='Site (GI)')
    bay    = models.CharField(max_length=50, verbose_name='Bay (Tag MSSQL)')
    urutan = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif  = models.BooleanField(default=True, verbose_name='Aktif')

    sumber_tabel = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Tabel Sumber Pengganti',
        help_text="Kosongkan untuk memakai ALL_TRANS_DATA (default). Contoh: dbo.ANALOG_RT")
    sumber_mode = models.CharField(
        max_length=10, choices=SUMBER_MODE_CHOICES, default='baris', verbose_name='Bentuk Tabel Sumber')
    sumber_filter_kolom = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Kolom Kunci',
        help_text="Kolom penanda titik. Mode Baris: kolom yang dicocokkan dengan Tag P/Q/V/I "
                  "(mis. ANALOG). Mode Kolom: kolom untuk memilih baris (mis. BAY).")
    sumber_filter_nilai = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Nilai Kunci (mode Kolom)',
        help_text="Hanya untuk mode Kolom — nilai yang dicari pada Kolom Kunci.")
    sumber_kolom_nilai = models.CharField(
        max_length=50, blank=True, default='VALUE', verbose_name='Kolom Nilai (mode Baris)',
        help_text="Hanya untuk mode Baris — kolom berisi angkanya. Umumnya VALUE.")
    sumber_p = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Tag/Kolom P',
        help_text="Mode Baris: nilai kunci titik P. Mode Kolom: nama kolom P. "
                  "Kosongkan bila metrik ini tidak ada di tabel sumber.")
    sumber_q = models.CharField(max_length=100, blank=True, default='', verbose_name='Tag/Kolom Q')
    sumber_v = models.CharField(max_length=100, blank=True, default='', verbose_name='Tag/Kolom V')
    sumber_i = models.CharField(max_length=100, blank=True, default='', verbose_name='Tag/Kolom I')

    class Meta:
        unique_together = ('site', 'bay')
        ordering = ['urutan', 'site', 'bay']
        verbose_name = 'Trafo'
        verbose_name_plural = 'Trafo'

    def __str__(self):
        return f'{self.site} — {self.bay}'

    @property
    def pakai_override(self):
        """True bila trafo ini dibaca dari tabel sumber pengganti, bukan ALL_TRANS_DATA."""
        return bool(self.sumber_tabel.strip())

    def spesifikasi_override(self):
        """
        Spesifikasi sumber pengganti untuk opsis.mssql.get_nilai_override().
        Return None bila trafo ini memakai ALL_TRANS_DATA seperti biasa.
        """
        if not self.pakai_override:
            return None
        return {
            'key':          (self.site, self.bay),
            'tabel':        self.sumber_tabel.strip(),
            'mode':         self.sumber_mode,
            'filter_kolom': self.sumber_filter_kolom.strip(),
            'filter_nilai': self.sumber_filter_nilai.strip(),
            'kolom_nilai':  (self.sumber_kolom_nilai or 'VALUE').strip(),
            'p':            self.sumber_p.strip(),
            'q':            self.sumber_q.strip(),
            'v':            self.sumber_v.strip(),
            'i':            self.sumber_i.strip(),
        }


class SnapFreq(models.Model):
    """
    Snapshot frekuensi sistem per detik dari SYS_FREQ_HIS.
    Disimpan via management command 'collect_freq' (jalan tiap menit).
    Auto-purge: data > 30 hari dihapus otomatis saat collect berjalan.
    Estimasi: 86.400 baris/hari × 30 hari = ~2.6 juta baris max.
    """
    waktu = models.DateTimeField(unique=True, db_index=True)  # timezone-aware, per detik
    hz    = models.FloatField()

    class Meta:
        ordering = ['-waktu']
        verbose_name = 'Snapshot Frekuensi'
        verbose_name_plural = 'Snapshots Frekuensi'

    def __str__(self):
        return f"{self.waktu:%Y-%m-%d %H:%M:%S} — {self.hz} Hz"


class SnapFreqRT(models.Model):
    """
    Snapshot frekuensi sistem dari SYS_FREQ_RT (tabel REALTIME, nilai terkini).
    Karena sumbernya tanpa history, nilai disimpan tiap kali command
    'collect_freq_rt' berjalan (mis. tiap menit) untuk membentuk time-series
    chart dashboard. Auto-purge > 30 hari.
    """
    waktu = models.DateTimeField(unique=True, db_index=True)  # floor ke detik
    hz    = models.FloatField()

    class Meta:
        ordering = ['-waktu']
        verbose_name = 'Snapshot Frekuensi RT'
        verbose_name_plural = 'Snapshot Frekuensi RT'

    def __str__(self):
        return f"{self.waktu:%Y-%m-%d %H:%M:%S} — {self.hz} Hz (RT)"


AREA_FREQ_CHOICES = [
    ('sultra',  'Sultra — GI Kendari New'),
    ('sulteng', 'Sulteng — GI Talise 150'),
    ('baubau',  'Baubau — GI Baubau'),
    ('luwuk',   'Luwuk — GI Luwuk'),
]


class SnapFreqArea(models.Model):
    """
    Snapshot frekuensi per area (Sultra/Sulteng/Baubau/Luwuk) dari tabel
    realtime TRANS_xxx_RT (snapshot nilai terkini, bukan historian per detik
    seperti SYS_FREQ_HIS). Disimpan via 'collect_freq' — satu baris per area
    setiap kali command jalan (tiap menit sesuai jadwal cron).
    Auto-purge: data > 30 hari dihapus otomatis saat collect berjalan.
    """
    area  = models.CharField(max_length=10, choices=AREA_FREQ_CHOICES, db_index=True)
    waktu = models.DateTimeField(db_index=True)  # timezone-aware
    hz    = models.FloatField()

    class Meta:
        unique_together = ('area', 'waktu')
        ordering = ['-waktu']
        verbose_name = 'Snapshot Frekuensi Area'
        verbose_name_plural = 'Snapshots Frekuensi Area'

    def __str__(self):
        return f"{self.area} @ {self.waktu:%Y-%m-%d %H:%M:%S} — {self.hz} Hz"


class SnapLive(models.Model):
    """
    Snapshot data realtime KIT_REALTIME yang disimpan ke PostgreSQL tiap N menit
    via management command 'collect_live'.
    Satu baris per pembangkit per menit — ML-ready, tidak ada duplikat.
    """
    pembangkit   = models.ForeignKey(Pembangkit, on_delete=models.PROTECT,
                                     related_name='snaps', db_index=True)
    waktu        = models.DateTimeField()        # floor ke menit (timezone-aware)
    mw           = models.FloatField(null=True)  # total MW semua unit positif
    mvar         = models.FloatField(null=True)  # total MVAR semua unit positif
    frekuensi    = models.FloatField(null=True)  # Hz sistem saat snapshot
    dicatat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('pembangkit', 'waktu')
        indexes = [models.Index(fields=['pembangkit', '-waktu'])]
        ordering = ['-waktu']
        verbose_name = 'Snapshot Live'
        verbose_name_plural = 'Snapshots Live'

    def __str__(self):
        return f"{self.pembangkit.kode} @ {self.waktu:%Y-%m-%d %H:%M}"


class SnapUnit(models.Model):
    """Detail per unit (UNIT1..UNIT8) dari satu SnapLive."""
    snap = models.ForeignKey(SnapLive, on_delete=models.CASCADE, related_name='units')
    nama = models.CharField(max_length=10)   # 'UNIT1'..'UNIT8'
    mw   = models.FloatField(null=True)
    mvar = models.FloatField(null=True)

    class Meta:
        unique_together = ('snap', 'nama')
        verbose_name = 'Unit Snapshot'
        verbose_name_plural = 'Unit Snapshots'

    def __str__(self):
        return f"{self.snap} — {self.nama}"


class SnapTrafo(models.Model):
    """
    Snapshot data trafo dari ALL_TRANS_DATA — trafo distribusi (BAY
    TRF52%/TRF42%) MAUPUN trafo IBT (BAY TRF65%/TRF54%), dibedakan lewat
    trafo.bay, bukan field terpisah — disimpan ke PostgreSQL tiap menit via
    management command 'collect_trafo'. Satu baris per trafo per menit —
    dipakai untuk chart 24 jam daya aktif (P) per trafo (baik "Chart Trafo
    Distribusi" maupun "Chart Trafo IBT"), sama seperti SnapLive dipakai
    untuk chart Beban Kit. Hanya P yang disimpan (Q tidak dipakai di chart
    ini), dan disimpan APA ADANYA (bisa negatif — arah aliran daya, terutama
    relevan untuk IBT — tidak di-abs()-kan). ALL_TRANS_DATA sendiri hanya
    menyimpan nilai realtime (tanpa histori), jadi PostgreSQL adalah
    satu-satunya sumber untuk data historis trafo.
    """
    trafo        = models.ForeignKey(Trafo, on_delete=models.PROTECT,
                                     related_name='snaps', db_index=True)
    waktu        = models.DateTimeField()        # floor ke menit (timezone-aware)
    p            = models.FloatField(null=True)  # daya aktif (MW)
    dicatat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('trafo', 'waktu')
        indexes = [models.Index(fields=['trafo', '-waktu'])]
        ordering = ['-waktu']
        verbose_name = 'Snapshot Trafo'
        verbose_name_plural = 'Snapshots Trafo'

    def __str__(self):
        return f"{self.trafo} @ {self.waktu:%Y-%m-%d %H:%M}"


class PrakiraanBeban(models.Model):
    """
    Prakiraan beban sistem (total MW) yang berasal dari SPREADSHEET dispatcher,
    bukan dari model machine learning.

    Grid 30 menit, 48 titik per hari — bentuk yang sama persis dengan seri
    'forecast' yang sudah dikonsumsi chart "Beban Kit — Hari Ini"
    (`{minute, mw}`), jadi tidak ada perubahan di sisi UI saat sumbernya
    berpindah dari model ML ke spreadsheet (lihat opsis/prakiraan.py dan
    switch OPSIS_FORECAST_SOURCE di settings).

    Diisi lewat POST /api/v1/prakiraan-beban/ — n8n membaca Google Sheets lalu
    mengirim seluruh kurva satu hari sekali kirim. Baris hari-hari lampau
    TIDAK dihapus: histori prakiraan itulah yang dipakai menghitung akurasi
    terhadap realisasi SnapLive di halaman Analitik Prediksi Beban.
    """
    tanggal    = models.DateField(db_index=True)
    menit      = models.PositiveSmallIntegerField(
        help_text='Menit sejak 00:00 waktu lokal (0–1439). Grid 30 menit: 0, 30, 60, …')
    mw         = models.FloatField()
    sumber     = models.CharField(max_length=50, default='spreadsheet',
                                  help_text='Asal data, mis. nama sheet / "spreadsheet" / "upload".')
    diperbarui = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tanggal', 'menit')
        indexes = [models.Index(fields=['tanggal', 'menit'])]
        ordering = ['-tanggal', 'menit']
        verbose_name = 'Prakiraan Beban'
        verbose_name_plural = 'Prakiraan Beban'

    @property
    def jam(self):
        """Label jam dinding lokal, mis. 1110 -> '18:30'."""
        return f'{self.menit // 60:02d}:{self.menit % 60:02d}'

    def __str__(self):
        return f"{self.tanggal:%Y-%m-%d} {self.jam} — {self.mw} MW"


class KelompokPeta(models.Model):
    """
    Satu ikon di Peta Pembangkit yang mewakili BEBERAPA pembangkit sekaligus —
    mis. rumpun Tello atau gugusan Punagaya. Dipakai supaya peta hanya
    menampilkan titik-titik besar, bukan puluhan ikon yang saling berdesakan.

    Pembangkit yang menjadi anggota sebuah kelompok yang tampil TIDAK lagi
    digambar sebagai ikon sendiri (lihat opsis.views.peta_pembangkit) — kalau
    tidak, dayanya akan terlihat dua kali di peta. Semuanya tetap muncul di
    tabel daya di sebelah peta.

    Daya kelompok tidak disimpan: dihitung di browser dari /opsis/api/live/
    dengan menjumlahkan anggotanya, sumber angka yang sama dengan ikon biasa.
    """

    nama       = models.CharField(max_length=80, verbose_name='Nama Kelompok',
                                  help_text='Tampil sebagai keterangan di bawah ikon, mis. "Kompleks Tello".')
    keterangan = models.CharField(max_length=200, blank=True, default='', verbose_name='Keterangan',
                                  help_text='Opsional. Tampil saat kursor diarahkan ke ikon.')
    jenis      = models.CharField(max_length=10, choices=JENIS_CHOICES, default='LAIN',
                                  verbose_name='Ikon Jenis',
                                  help_text='Menentukan gambar dan warna ikon kelompok.')
    anggota    = models.ManyToManyField('Pembangkit', blank=True, related_name='kelompok_peta',
                                        verbose_name='Pembangkit Anggota')
    peta_x     = models.FloatField(default=50, verbose_name='Posisi Peta X (%)',
                                   help_text='0–100, persen dari kiri peta.')
    peta_y     = models.FloatField(default=50, verbose_name='Posisi Peta Y (%)',
                                   help_text='0–100, persen dari atas peta.')
    tampil_di_peta = models.BooleanField(default=True, verbose_name='Tampilkan di Peta')
    dibuat_pada    = models.DateTimeField(auto_now_add=True)
    diubah_pada    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Kelompok Peta'
        verbose_name_plural = 'Kelompok Peta'

    def __str__(self):
        return self.nama


class PantauanKit(models.Model):
    """
    Sekelompok pembangkit yang dipantau terpisah di dashboard OPSIS: satu kartu
    kecil berisi total MW-nya, dan satu chart 24 jam di sebelahnya. Anggotanya
    dipilih dari site admin — menambah/mengurangi pembangkit yang dipantau
    tidak butuh perubahan kode maupun migrasi, sama seperti KelompokPeta.

    Baris tunggal (pk=1): dashboard hanya punya satu pasang kartu ini.

    Angka di kartu kecil TIDAK disimpan dan tidak punya endpoint sendiri —
    dijumlahkan di browser dari /opsis/api/live/, sumber yang sama dengan
    kartu pembangkit di bawahnya. Ini disengaja: kalau dihitung terpisah di
    server, total kartu ini bisa berbeda dari jumlah kartu-kartu yang terlihat
    di layar yang sama, dan tidak ada yang bisa menjelaskan selisihnya.
    Konsekuensinya, mengubah keanggotaan dari admin baru terlihat setelah
    halaman dimuat ulang.

    Chart 24 jam-nya sumbernya SnapLive (PostgreSQL), sama dengan chart
    "Beban Kit — Hari Ini", jadi kedua chart selalu bercerita hal yang sama.
    """

    nama    = models.CharField(
        max_length=80, default='KIT Terpilih', verbose_name='Judul Kartu',
        help_text='Tampil sebagai judul kartu kecil dan chart-nya di dashboard.')
    anggota = models.ManyToManyField(
        'Pembangkit', blank=True, related_name='pantauan_kit',
        verbose_name='Pembangkit yang Dipantau',
        help_text='Pilih satu atau beberapa. Totalnya yang tampil di kartu dan chart. '
                  'Pembangkit yang tidak aktif tidak ikut terhitung.')
    warna   = models.CharField(
        max_length=7, default='#38bdf8', verbose_name='Warna',
        help_text='Warna angka kartu dan garis chart, mis. #38bdf8.')
    aktif   = models.BooleanField(
        default=False, verbose_name='Tampilkan di Dashboard',
        help_text='Hilangkan centang untuk menyembunyikan kartu dan chart-nya '
                  'tanpa menghapus daftar anggotanya.')
    diubah_pada = models.DateTimeField(auto_now=True, verbose_name='Diubah Pada')

    class Meta:
        verbose_name = 'Pantauan KIT Terpilih'
        verbose_name_plural = 'Pantauan KIT Terpilih'

    def __str__(self):
        return f'{self.nama} — {self.anggota.count()} pembangkit'

    def save(self, *args, **kwargs):
        self.pk = 1                       # selalu satu baris, apa pun jalur simpannya
        super().save(*args, **kwargs)

    @classmethod
    def ambil(cls):
        """Baris pengaturan, dibuat dengan nilai bawaan bila belum ada."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def anggota_aktif(self):
        """Anggota yang pembangkitnya masih aktif, urut seperti dashboard."""
        return list(self.anggota.filter(aktif=True).order_by('urutan', 'nama'))

    def tampil(self):
        """Kartu digambar hanya bila dinyalakan DAN ada anggotanya."""
        return self.aktif and bool(self.anggota_aktif())


class PengaturanInersia(models.Model):
    """
    Kartu "Inersia Sistem" di dashboard OPSIS: energi kinetik tersimpan seluruh
    pembangkit yang sedang beroperasi, dan berapa MW yang boleh lepas pada
    batas ROCOF tertentu.

        E    = SUM(MVA x H) pembangkit yang ikut dihitung        [MWs]
        dP   = 2 x E x ROCOF_batas / f0                          [MW]

    Contoh dari lapangan: E = 11890 MWs, ROCOF 1 Hz/s, f0 50 Hz
                          -> dP = 2 x 11890 x 1 / 50 = 475,6 MW

    ROCOF dan f0 di sini adalah PARAMETER RENCANA, bukan hasil ukur — dP yang
    dihasilkan berarti "batas aman lepas pembangkit", bukan "besar gangguan
    yang barusan terjadi". Kalau suatu saat yang dibutuhkan adalah yang kedua,
    ROCOF-nya harus datang dari SnapFreqRT dan itu perhitungan yang berbeda.

    MVA & H per pembangkit ada di Pembangkit.mva / .inersia_h. Baris tunggal
    (pk=1) seperti PantauanKit dan ModePemeliharaan.
    """

    aktif = models.BooleanField(
        default=False, verbose_name='Tampilkan di Dashboard',
        help_text='Hilangkan centang untuk menyembunyikan kartu dan chart-nya tanpa '
                  'menghapus pengaturannya.')
    nama  = models.CharField(
        max_length=80, default='Inersia Sistem', verbose_name='Judul Kartu',
        help_text='Tampil sebagai judul kartu kecil dan chart-nya di dashboard.')

    rocof_batas = models.FloatField(
        default=1.0, verbose_name='Batas ROCOF (Hz/s)',
        help_text='Laju perubahan frekuensi yang masih dianggap aman, mis. 1 Hz/s. '
                  'Dipakai menghitung dP = 2 x E x ROCOF / f0.')
    frekuensi_nominal = models.FloatField(
        default=50.0, verbose_name='Frekuensi Nominal f0 (Hz)',
        help_text='Umumnya 50 Hz.')

    hanya_beroperasi = models.BooleanField(
        default=True, verbose_name='Hitung Hanya Pembangkit yang Beroperasi',
        help_text='Hanya mesin yang tersinkron menyimpan energi kinetik, jadi bawaannya '
                  'dicentang — pembangkit dengan MW di bawah ambang di bawah ini tidak '
                  'ikut dihitung. Hilangkan centang untuk memakai seluruh pembangkit '
                  'yang punya MVA & H (angkanya jadi kapasitas inersia terpasang, dan '
                  'grafiknya praktis datar).')
    ambang_mw = models.FloatField(
        default=1.0, verbose_name='Ambang MW Dianggap Beroperasi',
        help_text='Pembangkit dengan MW lebih besar dari angka ini dianggap tersinkron. '
                  'Bukan nol supaya derau pengukuran kecil tidak terbaca sebagai '
                  'mesin yang berputar.')

    warna       = models.CharField(
        max_length=7, default='#22d3ee', verbose_name='Warna Energi Kinetik',
        help_text='Warna angka E dan garis chart-nya, mis. #22d3ee.')
    warna_delta = models.CharField(
        max_length=7, default='#fb923c', verbose_name='Warna dP',
        help_text='Warna angka dP dan garis chart-nya.')
    diubah_pada = models.DateTimeField(auto_now=True, verbose_name='Diubah Pada')

    class Meta:
        verbose_name = 'Pengaturan Inersia Sistem'
        verbose_name_plural = 'Pengaturan Inersia Sistem'

    def __str__(self):
        return f'{self.nama} — ROCOF {self.rocof_batas} Hz/s @ {self.frekuensi_nominal} Hz'

    def save(self, *args, **kwargs):
        self.pk = 1                       # selalu satu baris, apa pun jalur simpannya
        super().save(*args, **kwargs)

    @classmethod
    def ambil(cls):
        """Baris pengaturan, dibuat dengan nilai bawaan bila belum ada."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def pembangkit_terhitung(self):
        """
        Pembangkit aktif yang MVA dan H-nya sudah diisi — kandidat penyumbang
        inersia. Apakah masing-masing benar-benar ikut pada suatu waktu masih
        bergantung `hanya_beroperasi`.
        """
        return list(Pembangkit.objects
                    .filter(aktif=True, mva__isnull=False, inersia_h__isnull=False)
                    .order_by('urutan', 'nama'))

    def delta_p(self, energi_mws):
        """
        dP = 2 x E x ROCOF_batas / f0. None bila E tidak diketahui atau f0
        nol (pembagian nol hanya bisa terjadi kalau seseorang mengisi 0 di
        admin — dijawab dengan None, bukan exception di tengah render).
        """
        if energi_mws is None or not self.frekuensi_nominal:
            return None
        return 2.0 * energi_mws * self.rocof_batas / self.frekuensi_nominal

    def tampil(self):
        """Kartu digambar hanya bila dinyalakan DAN ada pembangkit yang terisi."""
        return self.aktif and bool(self.pembangkit_terhitung())


class ModePemeliharaan(models.Model):
    """
    Sakelar "OPSIS sedang dalam pemeliharaan" — baris tunggal (pk=1) yang diubah
    dari site admin. Selama `aktif` dicentang, semua permintaan ke /opsis/*
    dijawab halaman pemeliharaan oleh devices.middleware.OpsisMaintenanceMiddleware
    (HTTP 503), bukan oleh tiap view satu per satu.

    Dipakai mis. saat FASOP belum tersambung ke historian MSSQL: halaman OPSIS
    akan penuh angka kosong dan menembak MSSQL terus-menerus, jadi lebih baik
    ditutup dulu sampai koneksinya siap.

    Cron pengumpul data (collect_live, collect_freq, dsb.) TIDAK terpengaruh —
    sakelar ini hanya menutup akses web.
    """

    # Sakelar ini dibaca tiap request /opsis/*, jadi hasilnya di-cache sebentar
    # per proses. Konsekuensinya perubahan dari admin berlaku paling lambat
    # TTL_CACHE detik di worker lain (worker yang menyimpan langsung tahu).
    TTL_CACHE = 5.0
    _cache = {'obj': None, 'ts': 0.0}

    aktif = models.BooleanField(
        default=False, verbose_name='Aktifkan Mode Pemeliharaan',
        help_text='Bila dicentang, semua halaman /opsis/ diganti halaman pemeliharaan.')
    judul = models.CharField(
        max_length=120, default='OPSIS Sedang Dalam Pemeliharaan', verbose_name='Judul',
        help_text='Judul besar yang tampil di halaman pemeliharaan.')
    pesan = models.TextField(
        default='Dashboard OPSIS untuk sementara tidak dapat diakses karena koneksi ke '
                'server data SCADA (MSSQL) belum tersedia. Halaman akan dibuka kembali '
                'setelah koneksi siap.',
        verbose_name='Pesan', help_text='Penjelasan singkat untuk pengguna.')
    perkiraan_selesai = models.DateTimeField(
        null=True, blank=True, verbose_name='Perkiraan Selesai',
        help_text='Opsional. Kosongkan bila belum ada perkiraan waktu.')
    boleh_superuser = models.BooleanField(
        default=True, verbose_name='Superuser Tetap Bisa Masuk',
        help_text='Bila dicentang, superuser tetap dapat membuka /opsis/ untuk pengujian '
                  '(dengan pita penanda di atas halaman). Hilangkan centang untuk menutup '
                  'OPSIS bagi semua orang tanpa kecuali.')
    diubah_oleh = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+', verbose_name='Diubah Oleh')
    diubah_pada = models.DateTimeField(auto_now=True, verbose_name='Diubah Pada')

    class Meta:
        verbose_name = 'Mode Pemeliharaan OPSIS'
        verbose_name_plural = 'Mode Pemeliharaan OPSIS'

    def __str__(self):
        return 'Aktif — OPSIS ditutup' if self.aktif else 'Nonaktif — OPSIS terbuka'

    def save(self, *args, **kwargs):
        self.pk = 1                       # selalu satu baris, apa pun jalur simpannya
        super().save(*args, **kwargs)
        type(self)._cache = {'obj': self, 'ts': time.monotonic()}

    @classmethod
    def ambil(cls):
        """Baris pengaturan, dibuat dengan nilai bawaan bila belum ada."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def status(cls):
        """
        Seperti ambil(), tapi memakai cache pendek karena dipanggil tiap request
        /opsis/*. Mengembalikan None bila tabelnya belum ada (mis. sebelum
        migrate dijalankan) supaya kegagalan di sini tidak menjatuhkan seluruh
        aplikasi — pemanggil memperlakukan None sebagai "tidak sedang dipelihara".
        """
        now = time.monotonic()
        cache = cls._cache
        if cache['obj'] is not None and (now - cache['ts']) < cls.TTL_CACHE:
            return cache['obj']
        try:
            obj = cls.ambil()
        except Exception:
            return cache['obj']
        cls._cache = {'obj': obj, 'ts': now}
        return obj


# ── Kartu Total Padam ────────────────────────────────────────────────────────

PADAM_AGREGASI_CHOICES = [
    ('jumlah', 'Jumlah — SUM kolom nilai dari semua baris yang cocok'),
    ('hitung', 'Hitung — COUNT baris yang cocok (kolom nilai tidak dipakai)'),
    ('nilai',  'Nilai tunggal — TOP 1 kolom nilai dari baris yang cocok'),
]


class KartuPadam(models.Model):
    """
    Pengaturan kartu "Total Padam" di dashboard OPSIS — baris tunggal (pk=1)
    yang diubah dari site admin.

    Dua hal yang memang harus bisa diatur tanpa deploy:

    * `aktif` menyalakan/mematikan kartunya. Kartu ini dipasang di layar yang
      menyala berjam-jam, jadi status on/off ikut dikirim setiap poll — bukan
      hanya saat halaman dirender — supaya mematikannya dari admin langsung
      terlihat tanpa ada yang perlu me-refresh layar ruang operasi.
    * `sumber_*` menunjuk tabel/kolom MSSQL tempat angkanya dibaca. Bentuknya
      sengaja sama dengan opsis.TitikEWS.sumber_* (tabel + kolom nilai + kolom
      kunci + nilai kunci + faktor skala): nama tabel/kolom datang dari input
      admin sehingga divalidasi regex di opsis.mssql.get_total_padam() sebelum
      masuk SQL, sedangkan NILAI kunci tetap lewat bind parameter.

    Selama `sumber_tabel` kosong kartu tampil "sumber belum diatur", bukan
    error — sama seperti titik EWS yang belum termonitor.
    """

    # Kartu ini dibaca saat render dashboard DAN tiap poll endpointnya. Cache
    # pendek per proses seperti ModePemeliharaan: perubahan dari admin berlaku
    # instan di worker yang menyimpan, paling lambat TTL_CACHE detik di worker
    # lain.
    TTL_CACHE = 5.0
    _cache = {'obj': None, 'ts': 0.0}

    aktif = models.BooleanField(
        default=False, verbose_name='Tampilkan Kartu Total Padam',
        help_text='Bila dicentang, kartu Total Padam muncul di dashboard OPSIS. '
                  'Menghilangkan centang menyembunyikannya dari semua layar dalam '
                  'beberapa detik, tanpa perlu reload.')
    judul = models.CharField(
        max_length=60, default='Total Padam', verbose_name='Judul Kartu',
        help_text='Teks kecil di atas angka, mis. "Total Padam".')
    satuan = models.CharField(
        max_length=10, blank=True, default='MW', verbose_name='Satuan',
        help_text='Ditampilkan di belakang angka. Kosongkan bila angkanya tanpa satuan '
                  '(mis. jumlah penyulang).')
    desimal = models.PositiveSmallIntegerField(
        default=2, verbose_name='Jumlah Desimal',
        help_text='Banyak angka di belakang koma. Isi 0 untuk bilangan bulat '
                  '(cocok untuk mode Hitung).')
    warna = models.CharField(
        max_length=20, default='#f87171', verbose_name='Warna Aksen',
        help_text='Warna angka dan garis tepi kartu, mis. #f87171.')
    keterangan = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Keterangan',
        help_text='Teks kecil di bawah angka. Kosongkan untuk memakai keterangan '
                  'bawaan (jumlah baris sumber yang terbaca).')

    agregasi = models.CharField(
        max_length=10, choices=PADAM_AGREGASI_CHOICES, default='jumlah',
        verbose_name='Cara Menghitung')
    sumber_tabel = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Tabel Sumber (MSSQL)',
        help_text='Kosongkan bila sumbernya belum ditentukan — kartu tampil '
                  '"sumber belum diatur". Contoh: dbo.PADAM_RT')
    sumber_kolom_nilai = models.CharField(
        max_length=50, blank=True, default='VALUE', verbose_name='Kolom Nilai',
        help_text='Kolom berisi angka yang dijumlahkan/dibaca. Tidak dipakai pada '
                  'mode Hitung.')
    sumber_kolom_kunci = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Kolom Kunci',
        help_text='Kolom penyaring baris, mis. ANALOG atau STATUS. Kosongkan untuk '
                  'memakai SELURUH isi tabel.')
    sumber_nilai_kunci = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Nilai Kunci',
        help_text='Nilai yang dicari pada Kolom Kunci. Pisahkan dengan koma untuk '
                  'beberapa titik sekaligus, mis. PADAM_MKS,PADAM_KDI. Dikosongkan '
                  'berarti tanpa penyaring.')
    faktor_skala = models.FloatField(
        default=1.0, verbose_name='Faktor Skala',
        help_text='Hasil dikalikan angka ini. Mis. 0.001 bila historian menyimpan kW '
                  'sementara kartu menampilkan MW.')

    diubah_oleh = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+', verbose_name='Diubah Oleh')
    diubah_pada = models.DateTimeField(auto_now=True, verbose_name='Diubah Pada')

    class Meta:
        verbose_name = 'Kartu Total Padam'
        verbose_name_plural = 'Kartu Total Padam'

    def __str__(self):
        if not self.aktif:
            return 'Nonaktif — kartu tidak tampil'
        return f'Aktif — {self.sumber_tabel or "sumber belum diatur"}'

    def save(self, *args, **kwargs):
        self.pk = 1                       # selalu satu baris, apa pun jalur simpannya
        super().save(*args, **kwargs)
        type(self)._cache = {'obj': self, 'ts': time.monotonic()}

    @classmethod
    def ambil(cls):
        """Baris pengaturan, dibuat dengan nilai bawaan bila belum ada."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def setelan(cls):
        """
        Seperti ambil(), tapi memakai cache pendek dan tidak pernah melempar
        exception: mengembalikan None bila tabelnya belum ada (mis. sebelum
        migrate dijalankan). Pemanggil memperlakukan None sebagai "kartu mati",
        supaya dashboard tidak ikut jatuh hanya karena kartu tambahan.
        """
        now = time.monotonic()
        cache = cls._cache
        if cache['obj'] is not None and (now - cache['ts']) < cls.TTL_CACHE:
            return cache['obj']
        try:
            obj = cls.ambil()
        except Exception:
            return cache['obj']
        cls._cache = {'obj': obj, 'ts': now}
        return obj

    @property
    def pakai_sumber(self):
        """True bila kartu ini sudah diarahkan ke sebuah tabel MSSQL."""
        return bool(self.sumber_tabel.strip())

    @property
    def warna_lembut(self):
        """
        Warna aksen untuk garis tepi kartu — versi transparan dari `warna`.

        Warna heksa ditambahi alfa (#f87171 → #f871714d) mengikuti kartu lain di
        dashboard. Nilai yang bukan heksa 6 digit dikembalikan apa adanya:
        menempelkan '4d' ke situ menghasilkan warna tidak sah dan browser
        membuang SELURUH deklarasi border, jadi kartunya kehilangan tepi hanya
        karena salah ketik di admin.
        """
        warna = (self.warna or '').strip() or '#f87171'
        if re.fullmatch(r'#[0-9A-Fa-f]{6}', warna):
            return warna + '4d'
        return warna

    def nilai_kunci_list(self):
        """Nilai kunci sebagai daftar (dipisah koma, yang kosong dibuang)."""
        return [b.strip() for b in self.sumber_nilai_kunci.split(',') if b.strip()]

    def spesifikasi_sumber(self):
        """
        Spesifikasi untuk opsis.mssql.get_total_padam(). None bila kartu ini
        belum diarahkan ke tabel mana pun.
        """
        if not self.pakai_sumber:
            return None
        return {
            'tabel':       self.sumber_tabel.strip(),
            'kolom_nilai': (self.sumber_kolom_nilai or 'VALUE').strip(),
            'kolom_kunci': self.sumber_kolom_kunci.strip(),
            'nilai_kunci': self.nilai_kunci_list(),
            'agregasi':    self.agregasi,
            'faktor':      self.faktor_skala if self.faktor_skala is not None else 1.0,
        }


# ── EWS Defense Scheme ───────────────────────────────────────────────────────
#
# Halaman /opsis/ews/ membandingkan nilai ukur realtime dengan ambang setting
# rele defense scheme. Seluruh isinya berasal dari database — kolom parameter
# (KolomEWS) maupun titiknya (TitikEWS) didaftarkan lewat site admin, termasuk
# tabel/kolom MSSQL tempat nilai ukurnya dibaca. Tidak ada nama tabel/kolom
# yang di-hardcode di kode, jadi menambah skema baru tidak butuh migrasi.

SKEMA_CHOICES = [
    ('UVLS',   'UVLS — Under Voltage Load Shedding'),
    ('OVTS',   'OVTS — Over Voltage Transmission Shedding'),
    ('OVCS',   'OVCS — Over Voltage Capacitor Switching'),
    ('UVRS',   'UVRS — Under Voltage Reactor Switching'),
    ('OFGS',   'OFGS — Over Frequency Generator Shedding'),
    ('UFLS',   'UFLS — Under Frequency Load Shedding'),
    ('OLS',    'OLS — Over Load Shedding'),
    ('OGS',    'OGS — Over Generation Shedding'),
    ('ADS',    'ADS — Anti Discharge Scheme'),
    ('UPLS',   'UPLS — Under Power Load Shedding'),
    ('ISLAND', 'ISLAND — Islanding Scheme'),
]

# Warna tag per jenis skema. Sama seperti JENIS_WARNA: ini satu-satunya
# definisi, view mengirimnya ke template lewat json_script.
SKEMA_WARNA = {
    'UVLS':   '#3987e5',
    'OVTS':   '#d95926',
    'OVCS':   '#199e70',
    'UVRS':   '#9085e9',
    'OFGS':   '#d95926',
    'UFLS':   '#3987e5',
    'OLS':    '#199e70',
    'OGS':    '#c98500',
    'ADS':    '#c98500',
    'UPLS':   '#d55181',
    'ISLAND': '#9085e9',
}

BESARAN_CHOICES = [
    ('v', 'Tegangan (kV)'),
    ('f', 'Frekuensi (Hz)'),
    ('i', 'Arus (A)'),
    ('p', 'Daya (MW)'),
]

SATUAN_DEFAULT = {'v': 'kV', 'f': 'Hz', 'i': 'A', 'p': 'MW'}

# Ambang "waspada" bawaan per besaran — seberapa dekat ke setting sebelum
# kartu berubah kuning. Tegangan/arus/daya dalam pecahan (3% = 0.03), frekuensi
# dalam Hz absolut. Bisa ditimpa per titik lewat TitikEWS.ambang_waspada.
AMBANG_WASPADA_DEFAULT = {'v': 0.03, 'f': 0.15, 'i': 0.05, 'p': 0.10}

ARAH_CHOICES = [
    ('bawah', 'Ambang bawah — skema bekerja saat nilai turun melewati setting'),
    ('atas',  'Ambang atas — skema bekerja saat nilai naik melewati setting'),
]

STATUS_SKEMA_CHOICES = [
    ('aktif',    'Terpasang & Aktif'),
    ('nonaktif', 'Terpasang, Tidak Aktif'),
    ('rencana',  'Rencana'),
]


class KolomEWS(models.Model):
    """
    Satu kolom parameter di halaman EWS (mis. Tegangan / Frekuensi / Sensing
    Lainnya). Jumlah dan judul kolom ditentukan dari admin, bukan dari kode —
    itulah yang membuat halamannya bisa dipakai ulang untuk pengelompokan lain.
    """
    nama       = models.CharField(max_length=100, verbose_name='Nama Kolom')
    keterangan = models.TextField(
        blank=True, default='', verbose_name='Keterangan',
        help_text='Teks kecil di bawah judul kolom — menjelaskan skema apa saja '
                  'yang masuk kolom ini.')
    warna      = models.CharField(
        max_length=20, default='#3987e5', verbose_name='Warna Aksen',
        help_text='Kode warna garis di kiri judul kolom, mis. #3987e5.')
    urutan     = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif      = models.BooleanField(default=True, verbose_name='Aktif')

    class Meta:
        ordering = ['urutan', 'nama']
        verbose_name = 'Kolom EWS'
        verbose_name_plural = 'Kolom EWS'

    def __str__(self):
        return self.nama


class TitikEWS(models.Model):
    """
    Satu skema defense scheme yang dipantau: identitas dari berkas Defense
    Scheme, ambang setting relenya, dan penunjuk ke nilai ukur realtime di
    MSSQL.

    Sumber data (field 'sumber_*') mengikuti bentuk yang sama dengan
    opsis.Trafo.sumber_* — nama tabel dan kolom diisi dari admin, lalu
    divalidasi regex di opsis.mssql.get_nilai_ews() sebelum masuk ke SQL.
    Selama 'sumber_tabel' kosong, titik ini tampil sebagai "belum termonitor".
    """
    kolom        = models.ForeignKey(
        KolomEWS, on_delete=models.PROTECT, related_name='titik',
        verbose_name='Kolom Parameter')
    nama         = models.CharField(max_length=150, verbose_name='Nama Titik / Lokasi Rele')
    skema        = models.CharField(max_length=10, choices=SKEMA_CHOICES, verbose_name='Jenis Skema')
    sistem       = models.CharField(
        max_length=50, default='Sulbagsel', verbose_name='Sistem',
        help_text='Mis. Sulbagsel / BauBau / Luwuk. Dipakai sebagai filter di halaman EWS.')
    subsistem    = models.CharField(max_length=50, blank=True, default='', verbose_name='Subsistem')
    nomor        = models.CharField(max_length=10, blank=True, default='', verbose_name='No. Berkas')
    kode         = models.CharField(max_length=20, blank=True, default='', verbose_name='Kode Skema')
    target       = models.TextField(
        blank=True, default='', verbose_name='Target Kerja',
        help_text='Beban/pembangkit yang dilepas saat skema bekerja.')
    time_delay   = models.CharField(max_length=30, blank=True, default='', verbose_name='Time Delay')
    status_skema = models.CharField(
        max_length=10, choices=STATUS_SKEMA_CHOICES, default='aktif', verbose_name='Status Skema')
    catatan      = models.TextField(
        blank=True, default='', verbose_name='Catatan / Ketidaksesuaian',
        help_text='Satu catatan per baris. Ditampilkan bertanda bendera di panel detail.')
    urutan       = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif        = models.BooleanField(default=True, verbose_name='Aktif')

    besaran        = models.CharField(
        max_length=2, choices=BESARAN_CHOICES, default='v', verbose_name='Besaran Ukur')
    satuan         = models.CharField(
        max_length=10, blank=True, default='', verbose_name='Satuan',
        help_text='Kosongkan untuk memakai satuan bawaan besaran (kV/Hz/A/MW).')
    nominal        = models.FloatField(
        null=True, blank=True, verbose_name='Nilai Nominal',
        help_text='Mis. 150 untuk bus 150 kV, 50 untuk frekuensi. Kosongkan untuk arus.')
    setting        = models.FloatField(
        null=True, blank=True, verbose_name='Setting Rele',
        help_text='Vset/Fset/Iset. Kosongkan bila belum tercantum — kartu ditandai '
                  '"setting belum diisi" dan margin tidak dihitung.')
    arah           = models.CharField(
        max_length=5, choices=ARAH_CHOICES, default='bawah', verbose_name='Arah Kerja')
    ambang_waspada = models.FloatField(
        null=True, blank=True, verbose_name='Ambang Waspada',
        help_text='Kosongkan untuk memakai bawaan: 3% Vn (tegangan), 0,15 Hz (frekuensi), '
                  '5% I Set (arus), 10% ambang (daya). Tegangan/arus/daya diisi dalam '
                  'pecahan (0.03 = 3%), frekuensi dalam Hz.')

    sumber_tabel       = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Tabel Sumber (MSSQL)',
        help_text='Kosongkan bila titik ini belum termonitor. Contoh: dbo.KIT_REALTIME')
    sumber_kolom_nilai = models.CharField(
        max_length=50, blank=True, default='VALUE', verbose_name='Kolom Nilai',
        help_text='Kolom berisi angka yang dibaca. Umumnya VALUE.')
    sumber_kolom_kunci = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Kolom Kunci',
        help_text='Kolom penanda titik, mis. ANALOG atau KIT. Kosongkan bila tabelnya '
                  'hanya berisi satu baris (nilai diambil dari baris pertama).')
    sumber_nilai_kunci = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Nilai Kunci',
        help_text='Nilai yang dicari pada Kolom Kunci, mis. FREQ_MKS.')
    faktor_skala       = models.FloatField(
        default=1.0, verbose_name='Faktor Skala',
        help_text='Nilai MSSQL dikalikan angka ini. Mis. 0.001 bila historian menyimpan '
                  'Volt sementara halaman menampilkan kV.')

    class Meta:
        ordering = ['kolom__urutan', 'urutan', 'nama']
        verbose_name = 'Titik EWS'
        verbose_name_plural = 'Titik EWS'

    def __str__(self):
        return f'{self.skema} — {self.nama}'

    @property
    def satuan_tampil(self):
        return self.satuan.strip() or SATUAN_DEFAULT.get(self.besaran, '')

    @property
    def pakai_sumber(self):
        """True bila titik ini sudah diarahkan ke sebuah tabel MSSQL."""
        return bool(self.sumber_tabel.strip())

    def spesifikasi_sumber(self):
        """
        Spesifikasi untuk opsis.mssql.get_nilai_ews(). None bila titik ini
        belum diarahkan ke tabel mana pun.
        """
        if not self.pakai_sumber:
            return None
        return {
            'pk':          self.pk,
            'tabel':       self.sumber_tabel.strip(),
            'kolom_nilai': (self.sumber_kolom_nilai or 'VALUE').strip(),
            'kolom_kunci': self.sumber_kolom_kunci.strip(),
            'nilai_kunci': self.sumber_nilai_kunci.strip(),
            'faktor':      self.faktor_skala if self.faktor_skala is not None else 1.0,
        }

    def ambang(self):
        """Ambang waspada efektif titik ini."""
        if self.ambang_waspada is not None:
            return self.ambang_waspada
        return AMBANG_WASPADA_DEFAULT.get(self.besaran, 0.05)

    def margin(self, nilai):
        """
        Jarak nilai ukur ke setting, dinormalkan supaya bisa dibandingkan antar
        titik: pecahan terhadap nominal (tegangan) atau terhadap setting
        (arus/daya), dan Hz absolut untuk frekuensi. Negatif berarti sudah
        melewati setting. None bila nilai atau settingnya belum ada.
        """
        if nilai is None or self.setting is None:
            return None
        if self.besaran == 'v':
            ref = self.nominal or self.setting
        elif self.besaran == 'f':
            ref = 1
        else:
            ref = self.setting
        if not ref:
            return None
        if self.arah == 'bawah':
            return (nilai - self.setting) / ref
        return (self.setting - nilai) / ref

    def status(self, nilai):
        """
        Status kartu, dihitung di sini (bukan di JavaScript) supaya API dan
        pemakai lain — termasuk alerting nanti — memakai aturan yang sama.

        plan     rencana, belum diarahkan ke MSSQL, atau nilainya belum terbaca
        unknown  setting rele belum diisi, margin tidak bisa dihitung
        critical nilai sudah melewati setting
        warning  margin lebih kecil dari ambang waspada
        good     aman
        """
        if self.status_skema == 'rencana' or not self.pakai_sumber or nilai is None:
            return 'plan'
        if self.setting is None:
            return 'unknown'
        m = self.margin(nilai)
        if m is None:
            return 'unknown'
        if m <= 0:
            return 'critical'
        if m < self.ambang():
            return 'warning'
        return 'good'
