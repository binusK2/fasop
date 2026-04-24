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
