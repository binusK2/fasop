from django.db import models
from django.contrib.auth.models import User
from devices.models import Device
from django.utils import timezone
import datetime


def generate_nomor_gangguan():
    """Generate nomor tiket format: GNG-YYYYMM-XXXX (rekap per bulan)"""
    bulan = timezone.now().strftime('%Y%m')
    prefix = f'GNG-{bulan}-'
    last = (
        Gangguan.objects
        .filter(nomor_gangguan__startswith=prefix)
        .order_by('-nomor_gangguan')
        .first()
    )
    if last:
        try:
            seq = int(last.nomor_gangguan.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f'{prefix}{seq:04d}'


class Gangguan(models.Model):

    KATEGORI_CHOICES = (
        ('perangkat',  'Perangkat / Hardware'),
        ('jaringan',   'Jaringan / Komunikasi'),
        ('daya',       'Daya / Power'),
        ('software',   'Software / Konfigurasi'),
        ('eksternal',  'Faktor Eksternal'),
        ('lainnya',    'Lainnya'),
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

    # ── Identitas tiket ──────────────────────────────────────────
    nomor_gangguan  = models.CharField(max_length=30, unique=True, editable=False, verbose_name='Nomor Gangguan')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', verbose_name='Status')
    kategori        = models.CharField(max_length=20, choices=KATEGORI_CHOICES, default='perangkat', verbose_name='Kategori Gangguan')
    tingkat_keparahan = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='sedang', verbose_name='Tingkat Keparahan')

    # ── Waktu gangguan ───────────────────────────────────────────
    tanggal_gangguan = models.DateTimeField(verbose_name='Tanggal & Jam Gangguan')
    tanggal_resolved = models.DateTimeField(null=True, blank=True, verbose_name='Tanggal & Jam Resolved')

    # ── Lokasi & peralatan ───────────────────────────────────────
    site            = models.CharField(max_length=150, verbose_name='Site / Lokasi', help_text='Nama site yang mengalami gangguan')
    peralatan       = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Peralatan Terdampak',
        help_text='Opsional — pilih peralatan spesifik jika gangguan terkait satu perangkat'
    )

    # ── Isi laporan gangguan ─────────────────────────────────────
    executive_summary   = models.TextField(verbose_name='Executive Summary', help_text='Ringkasan singkat kondisi gangguan')
    indikasi_gangguan   = models.TextField(verbose_name='Indikasi Gangguan', help_text='Gejala atau indikasi yang terdeteksi')
    penyebab_gangguan   = models.TextField(blank=True, verbose_name='Penyebab Gangguan', help_text='Root cause gangguan jika sudah diketahui')
    dampak_gangguan     = models.TextField(verbose_name='Dampak Gangguan', help_text='Dampak yang ditimbulkan terhadap layanan/sistem')
    tindak_lanjut       = models.TextField(blank=True, verbose_name='Tindak Lanjut', help_text='[Tidak digunakan lagi — gunakan Log Tindak Lanjut]')
    catatan_penutupan   = models.TextField(blank=True, verbose_name='Catatan Penutupan', help_text='Diisi saat gangguan dinyatakan selesai / closed')

    # ── Foto Eviden ──────────────────────────────────────────────
    foto_eviden1    = models.ImageField(upload_to='gangguan_eviden/', blank=True, null=True, verbose_name='Foto Eviden 1')
    foto_eviden2    = models.ImageField(upload_to='gangguan_eviden/', blank=True, null=True, verbose_name='Foto Eviden 2')
    foto_eviden3    = models.ImageField(upload_to='gangguan_eviden/', blank=True, null=True, verbose_name='Foto Eviden 3')

    # ── Metadata ─────────────────────────────────────────────────
    created_at      = models.DateTimeField(auto_now_add=True, verbose_name='Dibuat Pada')
    created_by      = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gangguan_dibuat',
        verbose_name='Dideklarasikan oleh'
    )
    updated_at      = models.DateTimeField(auto_now=True, verbose_name='Diupdate Pada')

    class Meta:
        verbose_name        = 'Gangguan'
        verbose_name_plural = 'Gangguan'
        ordering            = ['-tanggal_gangguan']

    def __str__(self):
        return f'{self.nomor_gangguan} — {self.site}'

    def save(self, *args, **kwargs):
        if not self.nomor_gangguan:
            self.nomor_gangguan = generate_nomor_gangguan()
        # Auto-set tanggal_resolved saat status pertama kali resolved/closed
        if self.status in ('resolved', 'closed') and not self.tanggal_resolved:
            self.tanggal_resolved = timezone.now()
        super().save(*args, **kwargs)

    @property
    def durasi(self):
        """Durasi gangguan dalam format string."""
        end = self.tanggal_resolved or timezone.now()
        delta = end - self.tanggal_gangguan
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


class GangguanLog(models.Model):
    """Catatan tindak lanjut per jam / per aksi untuk satu gangguan."""
    gangguan    = models.ForeignKey(Gangguan, on_delete=models.CASCADE, related_name='log_entries')
    waktu_aksi  = models.DateTimeField(verbose_name='Waktu Aksi')
    keterangan  = models.TextField(verbose_name='Keterangan Tindakan')
    dibuat_oleh = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='gangguan_log_entries', verbose_name='Dicatat oleh'
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['waktu_aksi']
        verbose_name = 'Log Tindak Lanjut'

    def __str__(self):
        return f'{self.gangguan.nomor_gangguan} — {self.waktu_aksi}'
