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
    asset_id = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name='Asset ID',
        help_text='Nomor identitas aset (angka).',
    )
    ASET_CHOICES = (
        ('UP2B',       'UP2B'),
        ('IPP',        'IPP'),
        ('BELUM_STAP', 'Belum STAP'),
    )
    status_aset = models.CharField(
        max_length=50,
        default='UP2B',
        db_index=True,
        verbose_name='Status Aset',
        help_text='Kepemilikan aset. Hanya UP2B yang masuk perhitungan jumlah aset.',
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
    wiring_json = models.JSONField(
        null=True, blank=True,
        verbose_name='Wiring Diagram Data',
    )
    wiring_img = models.ImageField(
        upload_to='wiring/', null=True, blank=True,
        verbose_name='Wiring Diagram Image',
    )
    host = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='vm_children',
        verbose_name='Host Server (untuk VM)',
        help_text='Isi jika perangkat ini adalah VM di dalam server fisik',
    )

    class Meta:
        indexes = [
            models.Index(fields=['is_deleted', 'jenis'], name='device_del_jenis_idx'),
            models.Index(fields=['is_deleted', 'lokasi'], name='device_del_lokasi_idx'),
            models.Index(fields=['is_deleted', 'host'], name='device_del_host_idx'),
            models.Index(fields=['is_deleted', 'status_operasi'], name='device_del_status_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['ip_address', 'lokasi'],
                condition=models.Q(ip_address__isnull=False),
                name='unique_ip_per_lokasi',
            )
        ]

    def __str__(self):
        return self.nama

    def get_status_aset_display(self):
        return dict(self.ASET_CHOICES).get(str(self.status_aset), str(self.status_aset) or '—')

    def save(self, *args, **kwargs):
        if self.asset_id is not None:
            self.asset_id = str(self.asset_id).strip()
        if self.status_aset:
            self.status_aset = self.status_aset.strip()
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


class ULTG(models.Model):
    """Unit Layanan Transmisi dan Gardu Induk — membawahi beberapa SiteLocation."""
    nama     = models.CharField(max_length=100, unique=True, verbose_name='Nama ULTG',
                                help_text='Contoh: ULTG Makassar, ULTG Pare-Pare')
    lokasi   = models.ManyToManyField(
        'SiteLocation', blank=True,
        verbose_name='Lokasi / GI yang dibawahi',
        help_text='Pilih semua Gardu Induk yang berada di bawah ULTG ini'
    )
    keterangan = models.TextField(blank=True, verbose_name='Keterangan')

    class Meta:
        verbose_name      = 'ULTG'
        verbose_name_plural = 'ULTG'
        ordering          = ['nama']

    def __str__(self):
        return self.nama

    def get_lokasi_names(self):
        return list(self.lokasi.values_list('nama', flat=True))


class Branch(models.Model):
    """Pengelompokan lokasi berdasarkan unit/wilayah (UP2B, PB Kendari, dll)."""
    nama       = models.CharField(max_length=100, unique=True, verbose_name='Nama Branch')
    kode       = models.CharField(max_length=20, blank=True, verbose_name='Kode')
    keterangan = models.TextField(blank=True, verbose_name='Keterangan')

    class Meta:
        verbose_name        = 'Branch'
        verbose_name_plural = 'Branch'
        ordering            = ['nama']

    def __str__(self):
        return self.nama


class SiteLocation(models.Model):
    """Menyimpan koordinat GPS untuk setiap site/lokasi peralatan."""
    nama = models.CharField(
        max_length=150,
        unique=True,
        verbose_name='Nama Site',
        help_text='Harus sama persis dengan nilai lokasi pada data Device'
    )
    branch     = models.ForeignKey(
        'Branch', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Branch', related_name='lokasi_set'
    )
    latitude   = models.FloatField(verbose_name='Latitude', null=True, blank=True)
    longitude  = models.FloatField(verbose_name='Longitude', null=True, blank=True)
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
        ('operator',         'Operator'),
        ('dispatcher',       'Dispatcher — Pengujian Telekomunikasi'),
        ('technician',       'Teknisi / Engineer'),
        ('asisten_manager',  'Asisten Manager Operasi'),
        ('opsis',            'Opsis — Monitoring Pembangkit (Input Data, Sesi Tunggal)'),
        ('opsis_view',       'Opsis View — Monitoring (Lihat Saja, Multi-Sesi)'),
        ('up2d',             'UP2D — Dashboard Beban Sistem'),
        ('vendor',           'Vendor — Asesmen Optik (Hanya Asesmen)'),
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
    active_session_key = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Session Key Aktif',
        help_text='Session key dari sesi login terakhir. Otomatis diperbarui saat login.'
    )
    ultg = models.ForeignKey(
        'ULTG', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='ULTG', related_name='operators',
        help_text='Untuk role Operator — ULTG yang dilayani. Inspeksi hanya menampilkan lokasi ULTG ini.'
    )
    branch = models.ForeignKey(
        'Branch', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Branch', related_name='dispatchers',
        help_text='Untuk role Dispatcher — Branch yang dilayani. Pengujian hanya menampilkan lokasi dalam branch ini.'
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

    @property
    def is_operator(self):
        return self.role == 'operator'

    @property
    def is_dispatcher(self):
        return self.role == 'dispatcher'

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
    def is_opsis_view(self):
        return self.role == 'opsis_view'

    # ── OPSIS ─────────────────────────────────────────────────────
    # Tiga tingkat akses OPSIS, didefinisikan SEKALI di sini lalu dipakai
    # ulang oleh view (lewat devices.permissions) dan template. Sebelumnya
    # tuple role-nya disalin di lima tempat lintas dua app; begitu salah satu
    # tertinggal saat diubah, gejalanya menu tampil tapi halamannya menolak.
    OPSIS_ROLE_LIHAT   = ('opsis', 'opsis_view', 'asisten_manager')
    OPSIS_ROLE_TULIS   = ('opsis', 'asisten_manager')
    OPSIS_ROLE_EWS     = ('technician', 'asisten_manager')

    # ── Asesmen Optik ─────────────────────────────────────────────
    # Pengisinya vendor di lapangan dan tim teknisi. Didefinisikan sekali di
    # sini — alasan yang sama dengan tuple OPSIS di atas: begitu disalin ke
    # view dan template, satu tempat pasti tertinggal saat diubah.
    ASESMEN_ROLE_ISI = ('vendor', 'technician', 'asisten_manager')

    @property
    def bisa_isi_asesmen(self):
        """Boleh membuat & menyunting Asesmen Optik."""
        return self.user.is_superuser or self.role in self.ASESMEN_ROLE_ISI

    @property
    def is_vendor(self):
        return self.role == 'vendor'

    @property
    def bisa_lihat_opsis(self):
        """
        Halaman OPSIS yang dibatasi role — Respons Pembangkit & Logsheet.
        Halaman OPSIS lain terbuka untuk semua user yang sudah login, jadi
        properti ini bukan gerbang masuk /opsis/ secara umum.
        """
        return self.user.is_superuser or self.role in self.OPSIS_ROLE_LIHAT

    @property
    def bisa_tulis_opsis(self):
        """
        Aksi yang mengubah data OPSIS: input HOP harian, penanda 'data tidak
        sesuai', dan mode Atur Peta. Opsis View sengaja TIDAK termasuk —
        role itu memang lihat-saja.
        """
        return self.user.is_superuser or self.role in self.OPSIS_ROLE_TULIS

    @property
    def bisa_sunting_ews(self):
        """
        Sunting ambang setting rele di EWS Defense Scheme. Teknisi karena
        merekalah yang tahu setting di lapangan berubah, plus AM. Pemetaan ke
        tabel MSSQL tetap hanya lewat site admin.
        """
        return self.user.is_superuser or self.role in self.OPSIS_ROLE_EWS

    @property
    def can_input_hop(self):
        """Boleh input data HOP harian — lihat bisa_tulis_opsis."""
        return self.bisa_tulis_opsis

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

class UserLoginLog(models.Model):
    """Mencatat riwayat login dan logout setiap pengguna."""
    ACTION_CHOICES = (
        ('login',  'Login'),
        ('logout', 'Logout'),
    )
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_logs')
    action     = models.CharField(max_length=10, choices=ACTION_CHOICES)
    timestamp  = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Log Login'
        verbose_name_plural = 'Log Login'

    def __str__(self):
        return f"{self.user.username} — {self.action} @ {self.timestamp:%Y-%m-%d %H:%M}"


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
        ('relokasi',              'Relokasi / Pindah Lokasi'),
        ('penggantian',           'Penggantian Komponen'),
        ('penggantian_perangkat', 'Penggantian Perangkat'),
        ('pembongkaran',          'Pembongkaran'),
        ('pemasangan',            'Pemasangan Kembali'),
        ('penambahan',            'Penambahan Komponen'),
        ('modifikasi',            'Modifikasi Konfigurasi'),
    )

    device          = models.ForeignKey(
        'Device', on_delete=models.CASCADE, related_name='events'
    )
    tipe            = models.CharField(max_length=25, choices=TIPE_CHOICES, verbose_name='Tipe Kejadian')
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
    merk_komponen_baru = models.CharField(
        max_length=100, blank=True,
        verbose_name='Merk Komponen Baru',
        help_text='Merk komponen pengganti (isi saat penggantian)'
    )
    tipe_komponen_baru = models.CharField(
        max_length=100, blank=True,
        verbose_name='Tipe / Model Komponen Baru',
        help_text='Tipe atau model komponen pengganti'
    )

    # ── Alasan Penggantian / Pembongkaran ─────────────────────
    ALASAN_CHOICES = (
        ('rusak',       'Rusak / Tidak Berfungsi'),
        ('kinerja',     'Kinerja Menurun'),
        ('improvement', 'Improvement / Upgrade Kehandalan'),
        ('lifetime',    'Habis Masa Pakai'),
        ('preventif',   'Pemeliharaan Preventif'),
        ('lainnya',     'Lainnya'),
    )
    alasan_penggantian = models.CharField(
        max_length=20, blank=True, choices=ALASAN_CHOICES,
        verbose_name='Alasan Penggantian / Pembongkaran')

    # ── Penambahan Komponen ───────────────────────────────────
    serial_komponen_baru = models.CharField(
        max_length=100, blank=True, verbose_name='Serial Number Komponen Baru')
    posisi_komponen_baru = models.CharField(
        max_length=50, blank=True, verbose_name='Posisi / Slot Komponen Baru')

    # ── Pembongkaran ──────────────────────────────────────────
    PEMBONGKARAN_TIPE_CHOICES = (('komponen', 'Komponen'), ('perangkat', 'Perangkat'))
    pembongkaran_tipe = models.CharField(
        max_length=10, blank=True, choices=PEMBONGKARAN_TIPE_CHOICES,
        verbose_name='Tipe Pembongkaran')

    # ── Modifikasi Konfigurasi ────────────────────────────────
    CONFIG_ASPEK_CHOICES = (
        ('ip_address',   'IP Address / Routing'),
        ('vlan',         'VLAN / Switching'),
        ('protokol',     'Protokol Komunikasi'),
        ('firmware',     'Firmware / Software'),
        ('ntp',          'NTP / Sinkronisasi Waktu'),
        ('port',         'Konfigurasi Port / Interface'),
        ('acl',          'ACL / Access Control'),
        ('credential',   'Password / Credential'),
        ('parameter',    'Parameter Operasi'),
        ('lainnya',      'Lainnya'),
    )
    config_aspek = models.CharField(
        max_length=20, blank=True, choices=CONFIG_ASPEK_CHOICES,
        verbose_name='Aspek Konfigurasi')

    # ── Pemasangan Kembali ────────────────────────────────────
    item_bongkar_ref = models.ForeignKey(
        'devices.ItemBongkar', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pemasangan_events',
        verbose_name='Item Bongkar yang Dipasang')

    # ── Penggantian Perangkat ─────────────────────────────────
    perangkat_pengganti = models.ForeignKey(
        'devices.Device', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='menggantikan_event',
        verbose_name='Perangkat Pengganti (baru)')

    # ── Relokasi — komponen ikut pindah ───────────────────────
    komponen_relokasi_ids = models.JSONField(
        default=list, blank=True,
        verbose_name='ID Komponen yang Direlokasi')

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
            'relokasi':              'bi-geo-alt',
            'penggantian':           'bi-arrow-repeat',
            'penggantian_perangkat': 'bi-hdd-stack',
            'pembongkaran':          'bi-box-arrow-down',
            'pemasangan':            'bi-box-arrow-in-up',
            'penambahan':            'bi-plus-circle',
            'modifikasi':            'bi-sliders',
        }.get(self.tipe, 'bi-circle')

    @property
    def tipe_color(self):
        return {
            'relokasi':              '#3b82f6',
            'penggantian':           '#f59e0b',
            'penggantian_perangkat': '#dc2626',
            'pembongkaran':          '#ef4444',
            'pemasangan':            '#10b981',
            'penambahan':            '#8b5cf6',
            'modifikasi':            '#06b6d4',
        }.get(self.tipe, '#94a3b8')

    @property
    def tipe_bg(self):
        return {
            'relokasi':              '#dbeafe',
            'penggantian':           '#fef3c7',
            'penggantian_perangkat': '#fee2e2',
            'pembongkaran':          '#fee2e2',
            'pemasangan':            '#dcfce7',
            'penambahan':            '#f5f3ff',
            'modifikasi':            '#cffafe',
        }.get(self.tipe, '#f1f5f9')

    @property
    def user_display(self):
        if not self.dilakukan_oleh:
            return '—'
        return self.dilakukan_oleh.get_full_name() or self.dilakukan_oleh.username


class KomponenRusak(models.Model):
    """
    Daftar komponen yang telah diganti / rusak, beserta lokasi penyimpanannya.
    Dibuat otomatis saat mencatat kejadian Penggantian Komponen.
    """
    device            = models.ForeignKey(
        'Device', on_delete=models.CASCADE, related_name='komponen_rusak',
        verbose_name='Perangkat'
    )
    nama_komponen     = models.CharField(max_length=150, verbose_name='Nama Komponen')
    merk              = models.CharField(max_length=100, blank=True, verbose_name='Merk')
    tipe              = models.CharField(max_length=100, blank=True, verbose_name='Tipe / Model')
    branch            = models.ForeignKey(
        'Branch', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Disimpan di Branch', related_name='komponen_rusak_set',
    )
    komponen_terkait  = models.ForeignKey(
        'devices.DeviceComponent',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='riwayat_rusak',
        verbose_name='Referensi Komponen'
    )
    ALASAN_CHOICES = (
        ('rusak',       'Rusak / Tidak Berfungsi'),
        ('kinerja',     'Kinerja Menurun'),
        ('improvement', 'Improvement / Upgrade Kehandalan'),
        ('lifetime',    'Habis Masa Pakai'),
        ('preventif',   'Pemeliharaan Preventif'),
        ('lainnya',     'Lainnya'),
    )
    alasan_penggantian = models.CharField(
        max_length=20, blank=True, choices=ALASAN_CHOICES,
        verbose_name='Alasan Penggantian')
    tanggal_rusak     = models.DateField(verbose_name='Tanggal Diganti / Rusak')
    disimpan_di       = models.CharField(
        max_length=200, blank=True,
        verbose_name='Disimpan Di',
        help_text='Lokasi penyimpanan komponen rusak, misal: Gudang Teknik, Loker B2'
    )
    keterangan        = models.TextField(blank=True, verbose_name='Keterangan')
    event             = models.ForeignKey(
        'DeviceEvent',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='komponen_rusak_set',
        verbose_name='Sumber Kejadian'
    )
    created_by        = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='komponen_rusak_dicatat',
        verbose_name='Dicatat oleh'
    )
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Komponen Rusak'
        verbose_name_plural = 'Daftar Komponen Rusak'
        ordering            = ['-tanggal_rusak', '-created_at']

    def __str__(self):
        return f'{self.nama_komponen} — {self.device.nama} ({self.tanggal_rusak})'


class ItemBongkar(models.Model):
    """
    Item (perangkat atau komponen) yang telah dibongkar dan disimpan di gudang/branch.
    Dibuat otomatis saat mencatat kejadian Pembongkaran.
    Diperbarui saat dilakukan Pemasangan Kembali.
    """
    TIPE_CHOICES = (
        ('perangkat', 'Perangkat'),
        ('komponen',  'Komponen'),
    )
    STATUS_CHOICES = (
        ('di_gudang',        'Di Gudang'),
        ('dipasang_kembali', 'Dipasang Kembali'),
        ('dibuang',          'Dibuang / Dihapus'),
    )

    tipe               = models.CharField(max_length=10, choices=TIPE_CHOICES, verbose_name='Tipe Item')
    nama               = models.CharField(max_length=150, verbose_name='Nama')
    merk               = models.CharField(max_length=100, blank=True, verbose_name='Merk')
    model_tipe         = models.CharField(max_length=100, blank=True, verbose_name='Model / Tipe')
    serial_number      = models.CharField(max_length=100, blank=True, verbose_name='Serial Number')

    device_asal        = models.ForeignKey(
        'Device', on_delete=models.CASCADE,
        related_name='item_bongkar', verbose_name='Perangkat Asal')
    komponen_terkait   = models.ForeignKey(
        'devices.DeviceComponent', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='item_bongkar',
        verbose_name='Referensi Komponen')

    branch             = models.ForeignKey(
        'Branch', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='item_bongkar', verbose_name='Disimpan di Branch')
    lokasi_penyimpanan = models.CharField(max_length=200, blank=True,
                                          verbose_name='Lokasi Spesifik di Gudang')

    ALASAN_CHOICES = (
        ('rusak',       'Rusak / Tidak Berfungsi'),
        ('kinerja',     'Kinerja Menurun'),
        ('improvement', 'Improvement / Upgrade Kehandalan'),
        ('lifetime',    'Habis Masa Pakai'),
        ('preventif',   'Pemeliharaan Preventif'),
        ('lainnya',     'Lainnya'),
    )
    alasan_penggantian = models.CharField(
        max_length=20, blank=True, choices=ALASAN_CHOICES,
        verbose_name='Alasan Pembongkaran / Penggantian')
    tanggal_bongkar    = models.DateField(verbose_name='Tanggal Pembongkaran')
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                          default='di_gudang', verbose_name='Status')

    event_bongkar      = models.ForeignKey(
        'DeviceEvent', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='item_bongkar_set', verbose_name='Event Pembongkaran')
    event_pasang       = models.ForeignKey(
        'DeviceEvent', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='item_pasang_set', verbose_name='Event Pemasangan Kembali')

    catatan            = models.TextField(blank=True, verbose_name='Catatan')
    created_by         = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='item_bongkar_dicatat', verbose_name='Dicatat oleh')
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Item Bongkar'
        verbose_name_plural = 'Daftar Item Bongkar'
        ordering            = ['-tanggal_bongkar', '-created_at']

    def __str__(self):
        return f'{self.get_tipe_display()}: {self.nama} dari {self.device_asal.nama}'

    @property
    def status_color(self):
        return {'di_gudang': '#f59e0b', 'dipasang_kembali': '#10b981', 'dibuang': '#94a3b8'}.get(self.status, '#94a3b8')

    @property
    def status_bg(self):
        return {'di_gudang': '#fef3c7', 'dipasang_kembali': '#dcfce7', 'dibuang': '#f1f5f9'}.get(self.status, '#f1f5f9')


class FiberOptic(models.Model):
    """Inventaris segmen kabel fiber optic."""

    TIPE_KABEL_CHOICES = (
        ('ADSS',  'ADSS (All-Dielectric Self-Supporting)'),
        ('OPGW',  'OPGW (Optical Ground Wire)'),
        ('DROP',  'Drop Cable'),
    )

    TIPE_KONEKTOR_CHOICES = (
        ('SC',     'SC (subscriber Connector)'),
        ('LC',     'LC (Lucent Connector)'),
        ('FC',     'FC (Ferrule Connector)'),
        ('lainnya','Lainnya'),
    )

    KONFIGURASI_CHOICES = (
        ('lurus',    'Lurus (Straight)'),
        ('crossing', 'Crossing'),
        ('campuran', 'Campuran'),
    )

    STATUS_CHOICES = (
        ('baik',           'Baik'),
        ('gangguan',       'Gangguan'),
        ('dalam_perbaikan','Dalam Perbaikan'),
        ('tidak_aktif',    'Tidak Aktif'),
    )

    # ── Identitas ────────────────────────────────────────────────
    nama         = models.CharField(max_length=200, verbose_name='Nama Segmen',
                                    help_text='Misal: Link FO GI Tello – GI Barru')
    lokasi_a     = models.CharField(max_length=150, verbose_name='Titik A (Asal)')
    lokasi_b     = models.CharField(max_length=150, verbose_name='Titik B (Tujuan)')

    # ── Spesifikasi kabel ────────────────────────────────────────
    tipe_kabel      = models.CharField(max_length=20, choices=TIPE_KABEL_CHOICES,
                                       blank=True, null=True, verbose_name='Tipe Kabel')
    tipe_konektor   = models.CharField(max_length=20, choices=TIPE_KONEKTOR_CHOICES,
                                       blank=True, null=True, verbose_name='Tipe Konektor')
    tipe_konektor_a = models.CharField(max_length=20, choices=TIPE_KONEKTOR_CHOICES,
                                       blank=True, null=True, verbose_name='Tipe Konektor Site A')
    tipe_konektor_b = models.CharField(max_length=20, choices=TIPE_KONEKTOR_CHOICES,
                                       blank=True, null=True, verbose_name='Tipe Konektor Site B')
    jumlah_core     = models.PositiveIntegerField(blank=True, null=True,
                                                   verbose_name='Jumlah Core')
    konfigurasi     = models.CharField(max_length=20, choices=KONFIGURASI_CHOICES,
                                       blank=True, null=True, verbose_name='Konfigurasi Core',
                                       help_text='Lurus: core A1→B1; Crossing: core A1→B lain')
    panjang_km      = models.DecimalField(max_digits=8, decimal_places=2,
                                          blank=True, null=True, verbose_name='Panjang (km)')

    # ── Info operasional ─────────────────────────────────────────
    tahun_pasang    = models.PositiveIntegerField(blank=True, null=True,
                                                   verbose_name='Tahun Pemasangan')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                       default='baik', verbose_name='Status')
    keterangan      = models.TextField(blank=True, null=True, verbose_name='Keterangan')

    # ── Foto site ────────────────────────────────────────────────
    foto_site_a  = models.ImageField(upload_to='fiber_optic/foto/', blank=True, null=True,
                                     verbose_name='Foto Site A')
    foto_site_b  = models.ImageField(upload_to='fiber_optic/foto/', blank=True, null=True,
                                     verbose_name='Foto Site B')

    # ── Metadata ─────────────────────────────────────────────────
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    created_by   = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fiber_dibuat',
        verbose_name='Dibuat Oleh',
    )
    public_token = models.CharField(
        max_length=40, blank=True, null=True, unique=True,
        verbose_name='Token Publik QR',
    )


    class Meta:
        verbose_name        = 'Fiber Optic'
        verbose_name_plural = 'Fiber Optic'
        ordering            = ['nama']

    def __str__(self):
        return f'{self.nama} ({self.lokasi_a} ↔ {self.lokasi_b})'

    def save(self, *args, **kwargs):
        if not self.public_token:
            import secrets
            self.public_token = secrets.token_urlsafe(20)
        super().save(*args, **kwargs)

    @property
    def status_color(self):
        return {
            'baik':           '#10b981',
            'gangguan':       '#ef4444',
            'dalam_perbaikan':'#f59e0b',
            'tidak_aktif':    '#94a3b8',
        }.get(self.status, '#94a3b8')

    @property
    def status_bg(self):
        return {
            'baik':           '#dcfce7',
            'gangguan':       '#fee2e2',
            'dalam_perbaikan':'#fef3c7',
            'tidak_aktif':    '#f1f5f9',
        }.get(self.status, '#f1f5f9')

class FiberOpticCore(models.Model):
    """Detail per-core dari satu segmen fiber optic."""

    STATUS_CORE_CHOICES = (
        ('aktif',     'Aktif / Digunakan'),
        ('spare',     'Spare / Cadangan'),
        ('rusak',     'Rusak / Putus'),
        ('tidak_aktif','Tidak Aktif'),
    )

    fiber_optic  = models.ForeignKey(
        FiberOptic, on_delete=models.CASCADE,
        related_name='cores', verbose_name='Segmen FO',
    )
    nomor_core   = models.PositiveIntegerField(verbose_name='Nomor Core')
    nomor_core_a = models.PositiveIntegerField(
        blank=True, null=True, verbose_name='Nomor Core Site A',
        help_text='Nomor core sebagaimana tertera di ODF/panel Site A',
    )
    nomor_core_b = models.PositiveIntegerField(
        blank=True, null=True, verbose_name='Nomor Core Site B',
        help_text='Nomor core sebagaimana tertera di ODF/panel Site B',
    )
    fungsi       = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name='Fungsi / Digunakan Untuk',
        help_text='Misal: Link SCADA GI Tello–Barru, VoIP Kantor, Spare',
    )
    status       = models.CharField(
        max_length=20, choices=STATUS_CORE_CHOICES,
        default='spare', verbose_name='Status Core (overall)',
    )
    status_a     = models.CharField(
        max_length=20, choices=STATUS_CORE_CHOICES,
        default='spare', verbose_name='Status Core Site A',
    )
    status_b     = models.CharField(
        max_length=20, choices=STATUS_CORE_CHOICES,
        default='spare', verbose_name='Status Core Site B',
    )
    koneksi_a    = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name='Koneksi Site A',
        help_text='Perangkat/port yang terhubung di Site A (misal: ODF-1 port 3)',
    )
    koneksi_b    = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name='Koneksi Site B',
        help_text='Perangkat/port yang terhubung di Site B (misal: Switch GI Barru eth1)',
    )
    fungsi_b     = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name='Fungsi / Digunakan Untuk (Site B)',
    )
    keterangan_b = models.TextField(blank=True, null=True, verbose_name='Catatan Site B')

    # ── Hasil OTDR Site A ─────────────────────────────────────
    # λ1310 nm — Site A
    otdr_jarak_km_1310 = models.DecimalField(
        max_digits=9, decimal_places=4, blank=True, null=True,
        verbose_name='OTDR A Jarak λ1310 (km)',
    )
    otdr_redaman_db_1310 = models.DecimalField(
        max_digits=6, decimal_places=3, blank=True, null=True,
        verbose_name='OTDR A Redaman λ1310 (dB)',
    )
    otdr_redaman_per_km_1310 = models.DecimalField(
        max_digits=5, decimal_places=3, blank=True, null=True,
        verbose_name='OTDR A Avg Loss λ1310 (dB/km)',
    )
    # λ1550 nm — Site A
    otdr_jarak_km_1550 = models.DecimalField(
        max_digits=9, decimal_places=4, blank=True, null=True,
        verbose_name='OTDR A Jarak λ1550 (km)',
    )
    otdr_redaman_db_1550 = models.DecimalField(
        max_digits=6, decimal_places=3, blank=True, null=True,
        verbose_name='OTDR A Redaman λ1550 (dB)',
    )
    otdr_redaman_per_km_1550 = models.DecimalField(
        max_digits=5, decimal_places=3, blank=True, null=True,
        verbose_name='OTDR A Avg Loss λ1550 (dB/km)',
    )
    otdr_tanggal = models.DateField(blank=True, null=True, verbose_name='OTDR A Tanggal Pengukuran')
    otdr_catatan = models.TextField(blank=True, null=True, verbose_name='OTDR A Catatan')

    # ── Hasil OTDR Site B ─────────────────────────────────────
    # λ1310 nm — Site B
    otdr_b_jarak_km_1310 = models.DecimalField(
        max_digits=9, decimal_places=4, blank=True, null=True,
        verbose_name='OTDR B Jarak λ1310 (km)',
    )
    otdr_b_redaman_db_1310 = models.DecimalField(
        max_digits=6, decimal_places=3, blank=True, null=True,
        verbose_name='OTDR B Redaman λ1310 (dB)',
    )
    otdr_b_redaman_per_km_1310 = models.DecimalField(
        max_digits=5, decimal_places=3, blank=True, null=True,
        verbose_name='OTDR B Avg Loss λ1310 (dB/km)',
    )
    # λ1550 nm — Site B
    otdr_b_jarak_km_1550 = models.DecimalField(
        max_digits=9, decimal_places=4, blank=True, null=True,
        verbose_name='OTDR B Jarak λ1550 (km)',
    )
    otdr_b_redaman_db_1550 = models.DecimalField(
        max_digits=6, decimal_places=3, blank=True, null=True,
        verbose_name='OTDR B Redaman λ1550 (dB)',
    )
    otdr_b_redaman_per_km_1550 = models.DecimalField(
        max_digits=5, decimal_places=3, blank=True, null=True,
        verbose_name='OTDR B Avg Loss λ1550 (dB/km)',
    )
    otdr_b_tanggal = models.DateField(blank=True, null=True, verbose_name='OTDR B Tanggal Pengukuran')
    otdr_b_catatan = models.TextField(blank=True, null=True, verbose_name='OTDR B Catatan')

    keterangan   = models.TextField(blank=True, null=True, verbose_name='Keterangan')
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Core Fiber Optic'
        verbose_name_plural = 'Core Fiber Optic'
        ordering            = ['fiber_optic', 'nomor_core']
        unique_together     = [('fiber_optic', 'nomor_core')]

    def __str__(self):
        return f'Core {self.nomor_core} — {self.fiber_optic.nama}'

    @property
    def core_num_a(self):
        return self.nomor_core_a if self.nomor_core_a is not None else self.nomor_core

    @property
    def core_num_b(self):
        return self.nomor_core_b if self.nomor_core_b is not None else self.nomor_core

    _STATUS_COLORS = {'aktif':'#10b981','spare':'#3b82f6','rusak':'#ef4444','tidak_aktif':'#94a3b8'}
    _STATUS_BGS    = {'aktif':'#dcfce7','spare':'#eff6ff','rusak':'#fee2e2','tidak_aktif':'#f1f5f9'}

    @property
    def status_color(self):
        return self._STATUS_COLORS.get(self.status, '#94a3b8')
    @property
    def status_bg(self):
        return self._STATUS_BGS.get(self.status, '#f1f5f9')

    @property
    def status_a_color(self):
        return self._STATUS_COLORS.get(self.status_a, '#94a3b8')
    @property
    def status_a_bg(self):
        return self._STATUS_BGS.get(self.status_a, '#f1f5f9')

    @property
    def status_b_color(self):
        return self._STATUS_COLORS.get(self.status_b, '#94a3b8')
    @property
    def status_b_bg(self):
        return self._STATUS_BGS.get(self.status_b, '#f1f5f9')


# ── Import model komponen agar ikut migrasi ──────────────────
from devices.models_komponen import (  # noqa: E402, F401
    GrupTipeKomponen, TipeKomponen,
    DeviceComponent,
    SpecRouterPort, SpecMuxSlot, SpecPSU,
    SpecRectifierModul, SpecBattery, SpecBatteryCell,
    SpecRadioModul, SpecPLCModul,
)


# ─────────────────────────────────────────────────────────────
# EVIDEN TAMBAHAN PERANGKAT
# ─────────────────────────────────────────────────────────────
def device_eviden_upload(instance, filename):
    ext  = os.path.splitext(filename)[1].lower() or '.jpg'
    nama = slugify_simple(instance.device.nama if instance.device else 'PERANGKAT')
    tgl  = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'device_eviden/{nama}_{tgl}{ext}'


class DeviceEviden(models.Model):
    """Foto eviden tambahan untuk suatu perangkat (bisa banyak)."""
    device      = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name='eviden_list'
    )
    foto        = models.ImageField(upload_to=device_eviden_upload)
    keterangan  = models.CharField(max_length=200, blank=True, default='')
    uploaded_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f'Eviden {self.pk} — {self.device.nama}'


# ─────────────────────────────────────────────────────────────
# GALERI FOTO LAPANGAN (staging)
# Foto diupload massal dari lapangan lalu diarahkan (assign) ke
# Device.foto/foto2 atau DeviceEviden. File di-COPY saat assign,
# foto asli tetap tersimpan di galeri sebagai riwayat.
# ─────────────────────────────────────────────────────────────
def foto_lapangan_upload(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    tgl = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S_%f')
    return f'foto_lapangan/{tgl}{ext}'


def foto_lapangan_thumb_upload(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    tgl = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S_%f')
    return f'foto_lapangan/thumb/{tgl}{ext}'


class FotoLapangan(models.Model):
    """Foto lapangan yang diupload massal, menunggu/telah diarahkan ke perangkat."""
    STATUS_CHOICES = (
        ('unassigned', 'Belum Diarahkan'),
        ('assigned',   'Sudah Diarahkan'),
    )
    ASSIGNED_AS_CHOICES = (
        ('foto',   'Foto Device 1'),
        ('foto2',  'Foto Device 2'),
        ('eviden', 'Eviden Tambahan'),
    )
    image        = models.ImageField(upload_to=foto_lapangan_upload)
    thumbnail    = models.ImageField(upload_to=foto_lapangan_thumb_upload, blank=True, null=True)
    folder       = models.CharField(
        max_length=150, blank=True, default='', db_index=True,
        verbose_name='Folder / Lokasi',
        help_text='Label pengelompokan bebas (mis. nama GI/lokasi). Kosong = Tanpa Folder.',
    )
    caption      = models.CharField(max_length=200, blank=True, default='')
    taken_at     = models.DateTimeField(null=True, blank=True, verbose_name='Waktu Ambil (EXIF)')
    original_name = models.CharField(max_length=255, blank=True, default='')
    uploaded_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    uploaded_at  = models.DateTimeField(auto_now_add=True)

    status       = models.CharField(max_length=12, choices=STATUS_CHOICES, default='unassigned')
    # Jejak assignment terakhir (foto bisa di-copy ke beberapa target)
    assigned_device = models.ForeignKey(
        'Device', on_delete=models.SET_NULL, null=True, blank=True, related_name='foto_lapangan_assigned'
    )
    assigned_as  = models.CharField(max_length=10, choices=ASSIGNED_AS_CHOICES, blank=True, default='')
    assigned_at  = models.DateTimeField(null=True, blank=True)
    assigned_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Foto Lapangan'
        verbose_name_plural = 'Foto Lapangan'

    def __str__(self):
        return f'FotoLapangan {self.pk} ({self.get_status_display()})'

    @property
    def display_time(self):
        """Waktu ambil (EXIF) bila ada, kalau tidak waktu upload."""
        return self.taken_at or self.uploaded_at


# ─────────────────────────────────────────────────────────────
# KONEKSI ANTAR PERANGKAT (untuk peta topologi)
# ─────────────────────────────────────────────────────────────

class DeviceLink(models.Model):
    TIPE_CHOICES = [
        ('fiber',      'Fiber Optik'),
        ('radio',      'Radio / MW'),
        ('opgw',       'OPGW'),
        ('pilot_wire', 'Pilot Wire'),
        ('lainnya',    'Lainnya'),
    ]

    device_a  = models.ForeignKey(Device, on_delete=models.CASCADE,
                                  related_name='link_dari', verbose_name='Perangkat A')
    device_b  = models.ForeignKey(Device, on_delete=models.CASCADE,
                                  related_name='link_ke',   verbose_name='Perangkat B')
    tipe      = models.CharField(max_length=20, choices=TIPE_CHOICES, default='fiber',
                                 verbose_name='Tipe Koneksi')
    label     = models.CharField(max_length=120, blank=True, verbose_name='Label',
                                 help_text='Kosongkan untuk otomatis "NamaA → NamaB"')
    aktif     = models.BooleanField(default=True, verbose_name='Aktif')
    keterangan = models.TextField(blank=True, verbose_name='Keterangan')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Koneksi Perangkat'
        verbose_name_plural = 'Koneksi Perangkat'
        ordering            = ['device_a__lokasi', 'device_a__nama']

    def __str__(self):
        label = self.label or f'{self.device_a.nama} → {self.device_b.nama}'
        return f'[{self.get_tipe_display()}] {label}'

    @property
    def display_label(self):
        return self.label or f'{self.device_a.nama} → {self.device_b.nama}'


# ═══════════════════════════════════════════════════════════════════════════
#  Kunci API eksternal — akses baca untuk aplikasi pihak lain (UP2D dsb.)
# ═══════════════════════════════════════════════════════════════════════════
class KunciApi(models.Model):
    """
    Kunci API per-konsumen untuk endpoint BACA `/api/v1/` (lihat api/auth.py
    `require_kunci_baca`).

    Sengaja terpisah dari `settings.API_KEY`. Kunci global itu satu untuk semua
    dan ikut membuka endpoint TULIS (`/api/v1/devices/` upsert inventaris,
    `/api/v1/hop/`, `/api/v1/prakiraan-beban/`), jadi membagikannya ke pihak
    luar sama dengan memberi akses tulis ke data aset. Baris di sini hanya bisa
    membaca, bisa dicabut satu per satu tanpa redeploy, dan pemakaiannya
    terlihat di admin — tiga hal yang tidak bisa dilakukan kunci di `.env`.

    Dimodelkan di app `devices` karena app `api` sengaja tidak punya model
    (tidak terdaftar di INSTALLED_APPS); `devices` sudah menampung infrastruktur
    lintas-app sejenis seperti UserProfile dan UserLoginLog.
    """
    # Selang minimum penulisan `terakhir_dipakai`. Tanpa ini setiap panggilan API
    # jadi satu UPDATE — penarik yang memoll tiap 5 detik menulis 17 ribu baris
    # sehari hanya untuk informasi yang dibaca manusia sekali-sekali.
    JEDA_CATAT_DETIK = 60

    nama = models.CharField(
        max_length=100, verbose_name='Nama Konsumen',
        help_text='Siapa pemakai kunci ini, mis. "UP2D Sulselrabar — dashboard beban".'
    )
    kunci = models.CharField(
        max_length=64, unique=True, db_index=True, blank=True, verbose_name='Kunci',
        help_text='Dikirim konsumen di header X-API-Key. Dibuat otomatis bila dikosongkan.'
    )
    aktif = models.BooleanField(
        default=True, verbose_name='Aktif',
        help_text='Hilangkan centang untuk mencabut akses seketika, tanpa menghapus riwayatnya.'
    )
    keterangan = models.TextField(
        blank=True, default='', verbose_name='Keterangan',
        help_text='Kontak PIC, nomor surat permintaan data, dsb.'
    )
    dibuat_oleh = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='kunci_api_dibuat', verbose_name='Dibuat Oleh'
    )
    created_at       = models.DateTimeField(auto_now_add=True, verbose_name='Dibuat')
    terakhir_dipakai = models.DateTimeField(null=True, blank=True, verbose_name='Terakhir Dipakai')
    terakhir_ip      = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP Terakhir')

    class Meta:
        verbose_name        = 'Kunci API'
        verbose_name_plural = 'Kunci API'
        ordering            = ['nama']

    def __str__(self):
        return f'{self.nama}{"" if self.aktif else " (nonaktif)"}'

    @staticmethod
    def kunci_baru():
        """String acak 43 karakter, aman untuk URL. Dipakai admin & migrasi."""
        import secrets
        return secrets.token_urlsafe(32)

    def save(self, *args, **kwargs):
        if not self.kunci:
            self.kunci = self.kunci_baru()
        super().save(*args, **kwargs)

    @property
    def kunci_tersamar(self):
        """4 karakter pertama + 4 terakhir — cukup untuk mencocokkan kunci mana
        yang dipakai konsumen tanpa memampangkan kuncinya di daftar admin."""
        if len(self.kunci) <= 12:
            return '•' * len(self.kunci)
        return f'{self.kunci[:4]}…{self.kunci[-4:]}'

    def catat_pemakaian(self, ip=None):
        """Perbarui jejak pemakaian, dibatasi JEDA_CATAT_DETIK sekali."""
        sekarang = timezone.now()
        if (self.terakhir_dipakai
                and (sekarang - self.terakhir_dipakai).total_seconds() < self.JEDA_CATAT_DETIK):
            return
        self.terakhir_dipakai = sekarang
        self.terakhir_ip = ip or self.terakhir_ip
        self.save(update_fields=['terakhir_dipakai', 'terakhir_ip'])


class AsesmenOptik(models.Model):
    """Asesmen kondisi FO & aksesoris di satu tower transmisi.

    Beda dengan FiberOptic yang mencatat SEGMEN (core, redaman, kegunaan),
    asesmen ini mencatat per TOWER: fungsi kabelnya, aksesoris yang memegangnya,
    dan kondisi keduanya di lapangan.

    Karena itu ia menempel pada ruas FO yang sudah terdaftar (`fiber_optic`) —
    GI awal/akhir dan tipe kabel diambil dari sana, tidak diketik ulang.
    Konsekuensinya ruas yang belum punya baris Fiber Optic harus didaftarkan
    dulu di menu Fiber Optic sebelum towernya bisa diasesmen.

    Satu baris = satu tower pada satu kali kunjungan. Kunjungan berikutnya
    membuat baris baru, jadi riwayat kondisi tiap tower tetap ada — pola yang
    sama dengan Maintenance, bukan menimpa data lama.
    """

    FASA_CHOICES = (
        ('atas',   'Atas (R)'),
        ('tengah', 'Tengah (S)'),
        ('bawah',  'Bawah (T)'),
    )
    TIPE_KABEL_CHOICES = (
        ('ADSS', 'ADSS'),
        ('OPGW', 'OPGW'),
    )
    KONDISI_FO_CHOICES = (
        ('baik',    'Baik'),
        ('anomali', 'Anomali'),
        ('rusak',   'Rusak'),
    )
    TIPE_ASESORIS_CHOICES = (
        ('tension',    'Tension'),
        ('suspension', 'Suspension'),
    )
    KONDISI_ASESORIS_CHOICES = (
        ('baik',         'Baik'),
        ('anomali',      'Anomali'),
        ('tanpa_fitmen', 'Tanpa Fitmen'),
    )
    JOINT_BOX_CHOICES = (
        ('ada',       'Ada'),
        ('tidak_ada', 'Tidak Ada'),
    )
    LEVEL_TEGANGAN_CHOICES = (
        ('70 kV',  '70 kV'),
        ('150 kV', '150 kV'),
        ('275 kV', '275 kV'),
    )
    UPT_CHOICES = (
        ('UPT MAKASSAR', 'UPT MAKASSAR'),
        ('UPT PALU',     'UPT PALU'),
        ('UPT MANADO',   'UPT MANADO'),
    )

    # ── Induk: ruas FO yang sudah terdaftar ──────────────────────
    fiber_optic = models.ForeignKey(
        'FiberOptic', on_delete=models.CASCADE, related_name='asesmen',
        verbose_name='Ruas Fiber Optic',
        help_text='GI awal/akhir & tipe kabel mengikuti data ruas ini.',
    )

    # ── Identitas tower ──────────────────────────────────────────
    no_tower       = models.CharField(max_length=20, verbose_name='No. Tower',
                                      help_text='Contoh: 12 atau #012')
    upt            = models.CharField(max_length=30, choices=UPT_CHOICES, blank=True,
                                      verbose_name='UPT')
    level_tegangan = models.CharField(max_length=10, choices=LEVEL_TEGANGAN_CHOICES,
                                      blank=True, verbose_name='Level Tegangan')
    tipe_tower     = models.CharField(max_length=50, blank=True, verbose_name='Tipe Tower')
    jarak_span     = models.PositiveIntegerField(null=True, blank=True,
                                                 verbose_name='Jarak Span (m)')
    # 8 desimal, bukan 6: koordinat yang disalin dari peta/GPS/berkas sumber
    # lazim punya 7-9 angka di belakang koma, dan pembulatan diam-diam bukan
    # pilihan yang baik untuk titik yang dipakai mencari tower di lapangan.
    lintang        = models.DecimalField(max_digits=12, decimal_places=8, null=True,
                                         blank=True, verbose_name='Lintang')
    bujur          = models.DecimalField(max_digits=12, decimal_places=8, null=True,
                                         blank=True, verbose_name='Bujur')

    # ── Hasil asesmen: kabel ─────────────────────────────────────
    fasa_fo    = models.CharField(max_length=10, choices=FASA_CHOICES, blank=True,
                                  verbose_name='Fasa FO')
    tipe_kabel = models.CharField(max_length=10, choices=TIPE_KABEL_CHOICES, blank=True,
                                  verbose_name='ADSS / OPGW',
                                  help_text='Kosongkan untuk mengikuti tipe kabel ruasnya.')
    kondisi_fo = models.CharField(max_length=10, choices=KONDISI_FO_CHOICES, blank=True,
                                  verbose_name='Kondisi FO')

    # ── Hasil asesmen: aksesoris ─────────────────────────────────
    tipe_asesoris    = models.CharField(max_length=15, choices=TIPE_ASESORIS_CHOICES,
                                        blank=True, verbose_name='Tipe Aksesoris')
    kondisi_asesoris = models.CharField(max_length=15, choices=KONDISI_ASESORIS_CHOICES,
                                        blank=True, verbose_name='Kondisi Aksesoris')
    ukuran_fitmen    = models.CharField(max_length=50, blank=True, verbose_name='Ukuran Fitmen')
    joint_box        = models.CharField(max_length=10, choices=JOINT_BOX_CHOICES, blank=True,
                                        verbose_name='Joint Box')

    # ── Lingkungan & kepemilikan ─────────────────────────────────
    asset           = models.CharField(max_length=50, blank=True, verbose_name='Asset',
                                       help_text='Pemilik aset, mis. UP2B')
    area_rintangan  = models.CharField(max_length=100, blank=True,
                                       verbose_name='Area Jalur Rintangan SUTT',
                                       help_text='Mis. Rumah, Sawah, Sungai, Hutan Rawa')
    keterangan      = models.TextField(blank=True, verbose_name='Keterangan')

    # ── Bukti & jejak ────────────────────────────────────────────
    foto        = models.ImageField(upload_to='asesmen_optik/', blank=True, null=True,
                                    verbose_name='Foto Tower / Aksesoris')
    foto_2      = models.ImageField(upload_to='asesmen_optik/', blank=True, null=True,
                                    verbose_name='Foto Tambahan')
    tanggal     = models.DateField(verbose_name='Tanggal Asesmen')
    petugas     = models.CharField(max_length=150, blank=True, verbose_name='Petugas / Vendor',
                                   help_text='Nama pelaksana di lapangan.')
    created_by  = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asesmen_optik_dibuat', verbose_name='Diinput oleh',
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Asesmen Optik'
        verbose_name_plural = 'Asesmen Optik'
        ordering            = ['-tanggal', 'fiber_optic', 'no_tower']
        indexes = [
            models.Index(fields=['fiber_optic', 'no_tower'], name='asesmen_ruas_tower_idx'),
            models.Index(fields=['-tanggal'], name='asesmen_tanggal_idx'),
        ]

    def __str__(self):
        return f'{self.fiber_optic.nama} — Tower {self.no_tower}'

    def save(self, *args, **kwargs):
        # '#012' dan '12' menunjuk tower yang sama; disimpan tanpa '#' supaya
        # pencarian & pengurutannya tidak bergantung cara orang mengetik.
        self.no_tower = (self.no_tower or '').strip().lstrip('#').strip()
        super().save(*args, **kwargs)

    @property
    def tipe_kabel_efektif(self):
        """Tipe kabel asesmen ini; kosong → ikut tipe kabel ruasnya."""
        return self.tipe_kabel or (self.fiber_optic.tipe_kabel or '')

    @property
    def ada_anomali(self):
        """Perlu ditindaklanjuti — dipakai penanda di daftar."""
        return (self.kondisi_fo in ('anomali', 'rusak')
                or self.kondisi_asesoris in ('anomali', 'tanpa_fitmen'))

    @property
    def koordinat(self):
        if self.lintang is None or self.bujur is None:
            return ''
        return f'{self.lintang}, {self.bujur}'
