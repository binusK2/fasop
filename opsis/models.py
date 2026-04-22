from django.db import models


class Pembangkit(models.Model):
    nama          = models.CharField(max_length=100, verbose_name='Nama Pembangkit')
    kode          = models.CharField(max_length=20, unique=True, verbose_name='Kode')
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
