from django.db import models
from django.contrib.auth.models import User
from devices.models import Device, DeviceType
from django.utils import timezone
import os
import re


def slugify_simple(text):
    text = str(text).strip().upper()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s]+', '_', text)
    return text[:40]


def ce_eviden_upload(nomor, site, n, filename):
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    site_slug = slugify_simple(site or 'SITE')
    nomor_slug = str(nomor).replace('-', '')
    tgl = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'ce_eviden/{nomor_slug}_{site_slug}_{tgl}_{n}{ext}'


def ce_eviden1_upload(instance, filename):
    return ce_eviden_upload(instance.nomor_ce or 'CE', instance.site, 1, filename)

def ce_eviden2_upload(instance, filename):
    return ce_eviden_upload(instance.nomor_ce or 'CE', instance.site, 2, filename)

def ce_eviden3_upload(instance, filename):
    return ce_eviden_upload(instance.nomor_ce or 'CE', instance.site, 3, filename)


def generate_nomor_ce():
    """Generate nomor tiket format: CE-YYYYMM-XXXX (rekap per bulan)"""
    bulan = timezone.now().strftime('%Y%m')
    prefix = f'CE-{bulan}-'
    last = (
        CommonEnemy.objects
        .filter(nomor_ce__startswith=prefix)
        .order_by('-nomor_ce')
        .first()
    )
    if last:
        try:
            seq = int(last.nomor_ce.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f'{prefix}{seq:04d}'


class CommonEnemy(models.Model):

    KATEGORI_CHOICES = (
        ('scada',   'SCADA'),
        ('telkom',  'Telekomunikasi'),
        ('prosis',  'Proteksi & Sistem'),
        ('lainnya', 'Lainnya'),
    )

    SEVERITY_CHOICES = (
        ('kritis', 'Kritis'),
        ('tinggi', 'Tinggi'),
        ('sedang', 'Sedang'),
        ('rendah', 'Rendah'),
    )

    STATUS_CHOICES = (
        ('open',        'Open'),
        ('in_progress', 'In Progress'),
        ('resolved',    'Resolved'),
        ('closed',      'Closed'),
    )

    SUMBER_CHOICES = (
        ('operator',   'Laporan Operator'),
        ('dispatcher', 'Dispatcher'),
        ('surat',      'Surat / Disposisi'),
        ('inspeksi',   'Temuan Inspeksi'),
        ('lainnya',    'Lainnya'),
    )

    # ── Identitas tiket ──────────────────────────────────────────
    nomor_ce          = models.CharField(max_length=30, unique=True, editable=False, verbose_name='Nomor CE')
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', verbose_name='Status')
    tingkat_keparahan = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='sedang', verbose_name='Tingkat Keparahan')
    sumber_laporan    = models.CharField(max_length=20, choices=SUMBER_CHOICES, default='operator', verbose_name='Sumber Laporan')

    # ── Kategorisasi berbasis bidang ─────────────────────────────
    kategori     = models.CharField(max_length=20, choices=KATEGORI_CHOICES, default='telkom', verbose_name='Kategori / Bidang')
    sub_kategori = models.ForeignKey(
        DeviceType,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='common_enemy_terkait',
        verbose_name='Sub Kategori (Jenis Peralatan)',
        help_text='Opsional — pilih jenis peralatan sesuai bidang',
    )

    # ── Lokasi & Peralatan ───────────────────────────────────────
    site      = models.CharField(max_length=150, verbose_name='Site / Lokasi')
    peralatan = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='common_enemy_terkait',
        verbose_name='Peralatan Terdampak',
        help_text='Opsional — pilih peralatan spesifik',
    )

    # ── Waktu ────────────────────────────────────────────────────
    tanggal_laporan  = models.DateTimeField(verbose_name='Tanggal & Jam Laporan')
    tanggal_resolved = models.DateTimeField(null=True, blank=True, verbose_name='Tanggal & Jam Resolved')

    # ── Isi laporan ──────────────────────────────────────────────
    deskripsi_masalah = models.TextField(verbose_name='Deskripsi Masalah', help_text='Uraian lengkap masalah yang dilaporkan')
    tindak_lanjut     = models.TextField(blank=True, verbose_name='Tindak Lanjut', help_text='Tindakan yang sudah / sedang dilakukan')
    catatan_penutupan = models.TextField(blank=True, verbose_name='Catatan Penutupan', help_text='Diisi saat issue dinyatakan selesai / closed')

    # ── Pelaksana / PIC ──────────────────────────────────────────
    pelaksana_names = models.JSONField(default=list, blank=True, verbose_name='Nama Pelaksana / PIC')

    # ── Foto Eviden ──────────────────────────────────────────────
    foto_eviden1 = models.ImageField(upload_to=ce_eviden1_upload, blank=True, null=True, verbose_name='Foto Eviden 1')
    foto_eviden2 = models.ImageField(upload_to=ce_eviden2_upload, blank=True, null=True, verbose_name='Foto Eviden 2')
    foto_eviden3 = models.ImageField(upload_to=ce_eviden3_upload, blank=True, null=True, verbose_name='Foto Eviden 3')

    # ── Metadata ─────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Dibuat Pada')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ce_dibuat',
        verbose_name='Dilaporkan oleh'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Diupdate Pada')

    class Meta:
        verbose_name        = 'Common Enemy'
        verbose_name_plural = 'Common Enemy'
        ordering            = ['-tanggal_laporan']

    def __str__(self):
        return f'{self.nomor_ce} — {self.site}'

    def save(self, *args, **kwargs):
        if not self.nomor_ce:
            self.nomor_ce = generate_nomor_ce()
        if self.status in ('resolved', 'closed') and not self.tanggal_resolved:
            self.tanggal_resolved = timezone.now()
        super().save(*args, **kwargs)

    @property
    def durasi(self):
        end = self.tanggal_resolved or timezone.now()
        delta = end - self.tanggal_laporan
        total_minutes = int(delta.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        days, hours = divmod(hours, 24)
        if days:
            return f'{days}h {hours}j {minutes}m'
        elif hours:
            return f'{hours}j {minutes}m'
        else:
            return f'{minutes}m'

    @property
    def is_open(self):
        return self.status in ('open', 'in_progress')

    @property
    def severity_color(self):
        return {
            'kritis': '#ef4444',
            'tinggi': '#f97316',
            'sedang': '#f59e0b',
            'rendah': '#10b981',
        }.get(self.tingkat_keparahan, '#94a3b8')

    @property
    def status_color(self):
        return {
            'open':        '#ef4444',
            'in_progress': '#f59e0b',
            'resolved':    '#10b981',
            'closed':      '#64748b',
        }.get(self.status, '#94a3b8')

    @property
    def kategori_color(self):
        return {
            'scada':   '#6366f1',
            'telkom':  '#0ea5e9',
            'prosis':  '#8b5cf6',
            'lainnya': '#94a3b8',
        }.get(self.kategori, '#94a3b8')


class CommonEnemyLog(models.Model):
    """Catatan tindak lanjut per aksi untuk satu Common Enemy."""
    common_enemy = models.ForeignKey(CommonEnemy, on_delete=models.CASCADE, related_name='log_entries')
    waktu_aksi   = models.DateTimeField(verbose_name='Waktu Aksi')
    keterangan   = models.TextField(verbose_name='Keterangan Tindakan')
    dibuat_oleh  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ce_log_entries', verbose_name='Dicatat oleh'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ['waktu_aksi']
        verbose_name = 'Log Tindak Lanjut CE'

    def __str__(self):
        return f'{self.common_enemy.nomor_ce} — {self.waktu_aksi}'
