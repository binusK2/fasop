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

    class Meta:
        ordering = ['urutan', 'nama']
        verbose_name = 'Pembangkit'
        verbose_name_plural = 'Pembangkit'

    def __str__(self):
        return self.nama


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
