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
    ip_address = models.GenericIPAddressField(blank=True, null=True, unique=True)
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
    spesifikasi = models.JSONField(blank=True, null=True, default=dict)
    tahun_operasi = models.IntegerField(
        blank=True, null=True,
        verbose_name='Tahun Operasi',
        help_text='Tahun peralatan mulai beroperasi (contoh: 2019)'
    )
    public_token = models.CharField(
        max_length=40, blank=True, null=True, unique=True,
        verbose_name='Token Publik QR',
        help_text='Token unik untuk halaman publik QR Code'
    )

    def __str__(self):
        return self.nama

    def save(self, *args, **kwargs):
        if not self.public_token:
            import secrets
            self.public_token = secrets.token_urlsafe(20)
        super().save(*args, **kwargs)


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
        ('viewer',           'Viewer (Hanya Lihat)'),
        ('technician',       'Teknisi / Engineer'),
        ('asisten_manager',  'Asisten Manager Operasi'),
    )
    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role         = models.CharField(max_length=30, choices=ROLE_CHOICES, default='technician', verbose_name='Peran')
    display_name = models.CharField(max_length=150, blank=True, default='', verbose_name='Nama Tampilan / Alias',
                                    help_text='Nama lengkap yang akan muncul di PDF (opsional). Jika kosong, pakai nama akun.')
    signature    = models.ImageField(upload_to='signatures/', blank=True, null=True, verbose_name='Tanda Tangan')
    force_password_change = models.BooleanField(
        default=True, verbose_name='Wajib Ganti Password',
        help_text='Jika aktif, user akan diarahkan ke halaman ganti password saat login berikutnya.'
    )

    class Meta:
        verbose_name = 'Profil Pengguna'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    # ── Role checks ───────────────────────────────────────────────
    @property
    def is_asisten_manager(self):
        return self.role == 'asisten_manager'

    @property
    def is_technician(self):
        return self.role == 'technician'

    @property
    def is_viewer(self):
        return self.role == 'viewer'

    # ── Permission shortcuts ──────────────────────────────────────
    @property
    def can_delete(self):
        """Hanya superuser yang bisa hapus."""
        return self.user.is_superuser

    @property
    def can_edit(self):
        """Technician dan AM bisa edit, viewer tidak."""
        return self.role in ('technician', 'asisten_manager') or self.user.is_superuser

    @property
    def can_manage_lokasi(self):
        """Kelola master lokasi & konfigurasi HI: AM ke atas."""
        return self.role == 'asisten_manager' or self.user.is_superuser

    @property
    def can_view_admin_log(self):
        """Log perubahan device: AM ke atas."""
        return self.role == 'asisten_manager' or self.user.is_superuser

    def get_display_name(self):
        """Nama yang ditampilkan di PDF: alias > full_name > username."""
        return self.display_name.strip() or self.user.get_full_name() or self.user.username

class DeviceLog(models.Model):
    """
    Audit trail perubahan data Device.
    Setiap kali device diedit, dibuat, atau dihapus,
    satu record log dibuat dengan detail field yang berubah.
    """
    AKSI_CHOICES = (
        ('create', 'Dibuat'),
        ('edit',   'Diedit'),
        ('delete', 'Dihapus'),
    )

    device     = models.ForeignKey(
        'Device', on_delete=models.CASCADE, related_name='logs',
    )
    user       = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_logs',
    )
    aksi       = models.CharField(max_length=10, choices=AKSI_CHOICES)
    perubahan  = models.JSONField(default=list)  # [{field, label, dari, ke}]
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Log Perubahan Device'
        verbose_name_plural = 'Log Perubahan Device'
        ordering            = ['-created_at']

    def __str__(self):
        u = self.user.username if self.user else 'System'
        return f'{self.device.nama} — {self.get_aksi_display()} oleh {u}'

    @property
    def user_display(self):
        if not self.user:
            return 'System'
        return self.user.get_full_name() or self.user.username


def device_event_foto_upload(instance, filename):
    ext  = os.path.splitext(filename)[1].lower() or '.jpg'
    nama = slugify_simple(instance.device.nama if instance.device else 'PERANGKAT')
    tgl  = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'device_events/{nama}_{tgl}{ext}'


class DeviceEvent(models.Model):
    """
    Riwayat kejadian fisik peralatan:
    relokasi, penggantian komponen, pembongkaran, pemasangan, penambahan, modifikasi.
    """
    TIPE_CHOICES = (
        ('relokasi',     'Relokasi / Pindah Lokasi'),
        ('penggantian',  'Penggantian Komponen'),
        ('pembongkaran', 'Pembongkaran'),
        ('pemasangan',   'Pemasangan Kembali'),
        ('penambahan',   'Penambahan Komponen'),
        ('modifikasi',   'Modifikasi Konfigurasi'),
    )

    device          = models.ForeignKey(
        'Device', on_delete=models.CASCADE, related_name='events'
    )
    tipe            = models.CharField(max_length=20, choices=TIPE_CHOICES, verbose_name='Tipe Kejadian')
    tanggal         = models.DateField(verbose_name='Tanggal Kejadian')
    komponen        = models.CharField(max_length=150, blank=True, verbose_name='Komponen',
                                       help_text='Contoh: PSU, Modul CPU, Battery Bank')
    nilai_lama      = models.TextField(blank=True, verbose_name='Kondisi / Nilai Sebelumnya')
    nilai_baru      = models.TextField(blank=True, verbose_name='Kondisi / Nilai Sesudahnya')
    lokasi_asal     = models.CharField(max_length=150, blank=True, verbose_name='Lokasi Asal')
    lokasi_tujuan   = models.CharField(max_length=150, blank=True, verbose_name='Lokasi Tujuan')
    catatan         = models.TextField(blank=True, verbose_name='Catatan Tambahan')
    foto            = models.ImageField(
        upload_to=device_event_foto_upload, blank=True, null=True, verbose_name='Foto Bukti'
    )
    dilakukan_oleh  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='device_events', verbose_name='Dicatat oleh'
    )
    gangguan        = models.ForeignKey(
        'gangguan.Gangguan',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='perubahan_fisik',
        verbose_name='Terkait Gangguan',
        help_text='Opsional — hubungkan ke tiket gangguan terkait'
    )
    komponen_terkait = models.ForeignKey(
        'devices.DeviceComponent',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='device_events',
        verbose_name='Komponen Terkait',
        help_text='Opsional — pilih komponen spesifik dari database'
    )
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Riwayat Kejadian Peralatan'
        verbose_name_plural = 'Riwayat Kejadian Peralatan'
        ordering            = ['-tanggal', '-created_at']

    def __str__(self):
        return f'{self.device.nama} — {self.get_tipe_display()} ({self.tanggal})'

    @property
    def tipe_icon(self):
        return {
            'relokasi':     'bi-geo-alt',
            'penggantian':  'bi-arrow-repeat',
            'pembongkaran': 'bi-box-arrow-down',
            'pemasangan':   'bi-box-arrow-in-up',
            'penambahan':   'bi-plus-circle',
            'modifikasi':   'bi-sliders',
        }.get(self.tipe, 'bi-circle')

    @property
    def tipe_color(self):
        return {
            'relokasi':     '#3b82f6',
            'penggantian':  '#f59e0b',
            'pembongkaran': '#ef4444',
            'pemasangan':   '#10b981',
            'penambahan':   '#8b5cf6',
            'modifikasi':   '#06b6d4',
        }.get(self.tipe, '#94a3b8')

    @property
    def tipe_bg(self):
        return {
            'relokasi':     '#dbeafe',
            'penggantian':  '#fef3c7',
            'pembongkaran': '#fee2e2',
            'pemasangan':   '#dcfce7',
            'penambahan':   '#f5f3ff',
            'modifikasi':   '#cffafe',
        }.get(self.tipe, '#f1f5f9')

    @property
    def user_display(self):
        if not self.dilakukan_oleh:
            return '—'
        return self.dilakukan_oleh.get_full_name() or self.dilakukan_oleh.username


# ── Import model komponen agar ikut migrasi ──────────────────
from devices.models_komponen import (  # noqa: E402, F401
    GrupTipeKomponen, TipeKomponen,
    DeviceComponent,
    SpecRouterPort, SpecMuxSlot, SpecPSU,
    SpecRectifierModul, SpecBattery, SpecBatteryCell,
    SpecRadioModul, SpecPLCModul,
)
