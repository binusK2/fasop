from django.db import models


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


class Pembangkit(models.Model):
    nama          = models.CharField(max_length=100, verbose_name='Nama Pembangkit')
    kode          = models.CharField(max_length=20, unique=True, verbose_name='Kode')
    jenis         = models.CharField(max_length=10, choices=JENIS_CHOICES, default='PLTD', verbose_name='Jenis')
    warna         = models.CharField(max_length=7, default='#3b82f6', verbose_name='Warna Chart')
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


class Trafo(models.Model):
    """
    Registry trafo (GI + bay) yang diikutkan dalam perhitungan Beban Trafo.
    Auto-terdaftar (aktif=True) saat pertama kali muncul di ALL_TRANS_DATA
    (lihat opsis.views._trafo_aktif_saja); nonaktifkan dari admin untuk
    mengeluarkan trafo tertentu dari tampilan/perhitungan tanpa hapus data.
    """
    site   = models.CharField(max_length=100, verbose_name='Site (GI)')
    bay    = models.CharField(max_length=50, verbose_name='Bay (Tag MSSQL)')
    urutan = models.PositiveIntegerField(default=0, verbose_name='Urutan Tampil')
    aktif  = models.BooleanField(default=True, verbose_name='Aktif')

    class Meta:
        unique_together = ('site', 'bay')
        ordering = ['urutan', 'site', 'bay']
        verbose_name = 'Trafo'
        verbose_name_plural = 'Trafo'

    def __str__(self):
        return f'{self.site} — {self.bay}'


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
