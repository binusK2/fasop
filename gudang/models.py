from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os


def alat_foto_upload(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    nama = str(instance.nama or 'alat').strip().replace(' ', '_')[:30].upper()
    tgl = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'gudang/alat/{nama}_{tgl}{ext}'


def sparepart_foto_upload(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    nama = str(instance.nama or 'part').strip().replace(' ', '_')[:30].upper()
    tgl = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'gudang/sparepart/{nama}_{tgl}{ext}'


class AlatUji(models.Model):
    """
    Tools & alat uji yang dimiliki PLN UP2B.
    Tracking kondisi dan lokasi penyimpanan.
    """
    KONDISI_CHOICES = (
        ('baik',          'Baik'),
        ('kalibrasi',     'Perlu Kalibrasi'),
        ('rusak',         'Rusak'),
        ('perbaikan',     'Dalam Perbaikan'),
    )

    nama                    = models.CharField(max_length=150, verbose_name='Nama Alat')
    kategori                = models.CharField(max_length=100, verbose_name='Kategori',
                                               help_text='Contoh: OTDR, Power Meter, Multimeter, Laptop Lapangan')
    merk                    = models.CharField(max_length=100, blank=True, verbose_name='Merk / Brand')
    model                   = models.CharField(max_length=100, blank=True, verbose_name='Model / Type')
    nomor_seri              = models.CharField(max_length=100, blank=True, verbose_name='Nomor Seri')
    kondisi                 = models.CharField(max_length=20, choices=KONDISI_CHOICES,
                                               default='baik', verbose_name='Kondisi')
    lokasi_penyimpanan      = models.CharField(max_length=150, verbose_name='Lokasi Penyimpanan',
                                               help_text='Contoh: Lemari A Ruang Teknik, Gudang Lt.1')
    tanggal_kalibrasi       = models.DateField(blank=True, null=True, verbose_name='Tanggal Kalibrasi Terakhir')
    jadwal_kalibrasi_berikut= models.DateField(blank=True, null=True, verbose_name='Jadwal Kalibrasi Berikutnya')
    keterangan              = models.TextField(blank=True, verbose_name='Keterangan')
    foto                    = models.ImageField(upload_to=alat_foto_upload, blank=True, null=True,
                                                verbose_name='Foto Alat')
    created_by              = models.ForeignKey(User, on_delete=models.SET_NULL,
                                                null=True, blank=True,
                                                related_name='alat_dibuat',
                                                verbose_name='Ditambahkan oleh')
    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)
    is_deleted              = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Alat Uji'
        verbose_name_plural = 'Alat Uji'
        ordering            = ['kategori', 'nama']

    def __str__(self):
        return f'{self.nama} ({self.kategori})'

    @property
    def kondisi_label(self):
        return dict(self.KONDISI_CHOICES).get(self.kondisi, self.kondisi)

    @property
    def kondisi_color(self):
        return {
            'baik':      'success',
            'kalibrasi': 'warning',
            'rusak':     'danger',
            'perbaikan': 'secondary',
        }.get(self.kondisi, 'secondary')

    @property
    def kalibrasi_overdue(self):
        """True jika jadwal kalibrasi sudah lewat."""
        if self.jadwal_kalibrasi_berikut:
            from datetime import date
            return self.jadwal_kalibrasi_berikut < date.today()
        return False


class Sparepart(models.Model):
    """
    Spare part dan komponen yang tersimpan di gudang.
    Stok dihitung otomatis dari mutasi masuk - keluar.
    """
    SATUAN_CHOICES = (
        ('pcs',   'pcs'),
        ('unit',  'unit'),
        ('meter', 'meter'),
        ('roll',  'roll'),
        ('set',   'set'),
        ('box',   'box'),
    )

    nama                = models.CharField(max_length=150, verbose_name='Nama Spare Part')
    kategori            = models.CharField(max_length=100, verbose_name='Kategori',
                                           help_text='Contoh: SFP, Kabel, Baterai, Power Supply')
    merk                = models.CharField(max_length=100, blank=True, verbose_name='Merk / Brand')
    part_number         = models.CharField(max_length=100, blank=True, verbose_name='Part Number')
    satuan              = models.CharField(max_length=10, choices=SATUAN_CHOICES,
                                           default='pcs', verbose_name='Satuan')
    lokasi_penyimpanan  = models.CharField(max_length=150, verbose_name='Lokasi di Gudang',
                                           help_text='Contoh: Rak B3, Laci 2 Lemari Komponen')
    stok_minimum        = models.PositiveIntegerField(default=0,
                                                      verbose_name='Stok Minimum',
                                                      help_text='Alert jika stok di bawah nilai ini')
    keterangan          = models.TextField(blank=True, verbose_name='Keterangan')
    foto                = models.ImageField(upload_to=sparepart_foto_upload, blank=True, null=True,
                                            verbose_name='Foto')
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL,
                                            null=True, blank=True,
                                            related_name='sparepart_dibuat',
                                            verbose_name='Ditambahkan oleh')
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)
    is_deleted          = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Spare Part'
        verbose_name_plural = 'Spare Part'
        ordering            = ['kategori', 'nama']

    def __str__(self):
        return f'{self.nama} ({self.kategori})'

    @property
    def stok_sekarang(self):
        """Hitung stok real-time dari mutasi."""
        masuk  = self.mutasi.filter(tipe='masuk').aggregate(
            total=models.Sum('jumlah'))['total'] or 0
        keluar = self.mutasi.filter(tipe='keluar').aggregate(
            total=models.Sum('jumlah'))['total'] or 0
        return masuk - keluar

    @property
    def stok_kritis(self):
        return self.stok_sekarang <= self.stok_minimum

    @property
    def stok_color(self):
        stok = self.stok_sekarang
        if stok <= 0:
            return 'danger'
        if stok <= self.stok_minimum:
            return 'warning'
        return 'success'


class MutasiSparepart(models.Model):
    """
    Histori keluar-masuk spare part dari gudang.
    Teknisi mencatat setiap transaksi.
    """
    TIPE_CHOICES = (
        ('masuk',  'Masuk'),
        ('keluar', 'Keluar'),
    )

    sparepart           = models.ForeignKey(Sparepart, on_delete=models.CASCADE,
                                            related_name='mutasi',
                                            verbose_name='Spare Part')
    tipe                = models.CharField(max_length=10, choices=TIPE_CHOICES,
                                           verbose_name='Tipe Mutasi')
    jumlah              = models.PositiveIntegerField(verbose_name='Jumlah')
    keperluan           = models.CharField(max_length=255, verbose_name='Keperluan / Keterangan')
    terkait_gangguan    = models.ForeignKey(
        'gangguan.Gangguan',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='mutasi_sparepart',
        verbose_name='Terkait Gangguan',
        help_text='Opsional — hubungkan ke tiket gangguan'
    )
    terkait_maintenance = models.ForeignKey(
        'maintenance.Maintenance',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='mutasi_sparepart',
        verbose_name='Terkait Maintenance',
        help_text='Opsional — hubungkan ke jadwal maintenance'
    )
    dilakukan_oleh      = models.ForeignKey(User, on_delete=models.SET_NULL,
                                            null=True, blank=True,
                                            related_name='mutasi_sparepart',
                                            verbose_name='Dicatat oleh')
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Mutasi Spare Part'
        verbose_name_plural = 'Mutasi Spare Part'
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.get_tipe_display()} {self.jumlah} {self.sparepart.satuan} — {self.sparepart.nama}'
