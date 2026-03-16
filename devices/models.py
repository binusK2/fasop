from django.db import models
from django.contrib.auth.models import User

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
    keterangan = models.TextField(blank=True, null=True)
    foto = models.ImageField(upload_to='device_photos/', blank=True, null=True)
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