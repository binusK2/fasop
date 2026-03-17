from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os
import re


def slugify_simple(text):
    """Bersihkan teks jadi aman untuk nama file."""
    text = str(text).strip().upper()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s]+', '_', text)
    return text[:40]  # batasi panjang


def device_foto_upload(instance, filename):
    ext   = os.path.splitext(filename)[1].lower() or '.jpg'
    nama  = slugify_simple(instance.nama  or 'PERANGKAT')
    jenis = slugify_simple(instance.jenis.name if instance.jenis else 'LAINNYA')
    tgl   = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'device_photos/{nama}_{jenis}_{tgl}{ext}'


def device_foto2_upload(instance, filename):
    ext   = os.path.splitext(filename)[1].lower() or '.jpg'
    nama  = slugify_simple(instance.nama  or 'PERANGKAT')
    jenis = slugify_simple(instance.jenis.name if instance.jenis else 'LAINNYA')
    tgl   = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'device_photos/{nama}_{jenis}_{tgl}_2{ext}'

# Create your models here.
class DeviceType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Device(models.Model):

    nama = models.CharField(max_length=100)
    jenis = models.ForeignKey(
        DeviceType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    merk = models.CharField(max_length=100)
    type = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    firmware_version = models.CharField(max_length=100, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    lokasi = models.CharField(max_length=150)
    STATUS_CHOICES = (
        ('operasi', 'Operasi'),
        ('tidak_operasi', 'Tidak Operasi'),
    )
    status_operasi = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='operasi',
        verbose_name='Status Operasi'
    )
    keterangan = models.TextField(blank=True, null=True)
    foto = models.ImageField(upload_to=device_foto_upload, blank=True, null=True)
    foto2 = models.ImageField(upload_to=device_foto2_upload, blank=True, null=True, verbose_name='Foto 2')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_devices',
        verbose_name='Ditambahkan oleh'
    )
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_devices'
    )
    is_deleted = models.BooleanField(default=False)
    spesifikasi = models.JSONField(blank=True, null=True, default=dict)  # ← tambahan

    def __str__(self):
        return self.nama


class Icon(models.Model):
    name = models.CharField(max_length=100)
    lokasi_layanan = models.CharField(max_length=150, null=True, blank=True)
    nama_layanan = models.CharField(max_length=150, null=True, blank=True)
    bandwidth = models.CharField(max_length=50, null=True, blank=True)
    SID1 = models.CharField(max_length=100, blank=True, null=True)
    SID2 = models.CharField(max_length=100, blank=True, null=True)
    kontrak = models.CharField(max_length=100, blank=True, null=True)  
    kondisi_operasional = models.CharField(max_length=100, blank=True, null=True)
    keterangan = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class SiteLocation(models.Model):
    """Menyimpan koordinat GPS untuk setiap site/lokasi peralatan."""
    nama = models.CharField(
        max_length=150,
        unique=True,
        verbose_name='Nama Site',
        help_text='Harus sama persis dengan nilai lokasi pada data Device'
    )
    latitude = models.FloatField(verbose_name='Latitude', null=True, blank=True)
    longitude = models.FloatField(verbose_name='Longitude', null=True, blank=True)
    keterangan = models.TextField(blank=True, null=True, verbose_name='Keterangan')

    class Meta:
        verbose_name = 'Lokasi Site'
        verbose_name_plural = 'Lokasi Site'
        ordering = ['nama']

    def __str__(self):
        return self.nama

    @property
    def has_coords(self):
        return self.latitude is not None and self.longitude is not None


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('technician',       'Teknisi / Pelaksana'),
        ('asisten_manager',  'Asisten Manager Operasi'),
    )
    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role         = models.CharField(max_length=30, choices=ROLE_CHOICES, default='technician', verbose_name='Peran')
    display_name = models.CharField(max_length=150, blank=True, default='', verbose_name='Nama Tampilan / Alias',
                                    help_text='Nama lengkap yang akan muncul di PDF (opsional). Jika kosong, pakai nama akun.')
    signature    = models.ImageField(upload_to='signatures/', blank=True, null=True, verbose_name='Tanda Tangan')

    class Meta:
        verbose_name = 'Profil Pengguna'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    @property
    def is_asisten_manager(self):
        return self.role == 'asisten_manager'

    def get_display_name(self):
        """Nama yang ditampilkan di PDF: alias > full_name > username."""
        return self.display_name.strip() or self.user.get_full_name() or self.user.username