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
    # ── Posisi pin pada Peta Pembangkit (/opsis/peta/) ─────────────────
    # Persen terhadap viewBox peta Sulawesi: peta_x 0=barat, 100=timur;
    # peta_y 0=utara, 100=selatan. Kosongkan untuk memakai posisi bawaan
    # opsis.hop_map.posisi_pembangkit() yang dicocokkan dari nama pembangkit;
    # isi hanya bila pembangkit belum terdaftar di sana atau pinnya perlu digeser.
    peta_x        = models.FloatField(null=True, blank=True, verbose_name='Posisi Peta X (%)',
                                      help_text='0–100, persen dari kiri peta. Kosongkan untuk posisi bawaan.')
    peta_y        = models.FloatField(null=True, blank=True, verbose_name='Posisi Peta Y (%)',
                                      help_text='0–100, persen dari atas peta. Kosongkan untuk posisi bawaan.')
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
