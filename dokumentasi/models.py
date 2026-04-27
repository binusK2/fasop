from django.db import models
from django.contrib.auth.models import User
from devices.models import Device
from django.utils import timezone
import os
import re


def slugify_simple(text):
    text = str(text).strip().upper()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s]+', '_', text)
    return text[:40]


# ── Setting Rele ────────────────────────────────────────────────────────────

def setting_file_upload(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.pdf'
    nama = slugify_simple(instance.device.nama if instance.device_id else 'DEVICE')
    tgl = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'dokumentasi/setting/{nama}_{tgl}{ext}'


def _generate_nomor_sr():
    prefix = timezone.now().strftime('SR-%Y%m-')
    last = SettingRele.objects.filter(nomor__startswith=prefix).order_by('-nomor').first()
    if last:
        try:
            seq = int(last.nomor.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f'{prefix}{seq:04d}'


class SettingRele(models.Model):
    STATUS_CHOICES = (
        ('draft',   'Draft'),
        ('checked', 'Sudah Dicek'),
    )

    nomor        = models.CharField(max_length=25, unique=True, editable=False, verbose_name='Nomor')
    device       = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='setting_rele', verbose_name='Perangkat Rele')
    judul        = models.CharField(max_length=200, verbose_name='Judul')
    tanggal      = models.DateField(verbose_name='Tanggal')
    versi        = models.CharField(max_length=50, blank=True, verbose_name='Versi')
    file_setting = models.FileField(upload_to=setting_file_upload, null=True, blank=True, verbose_name='File Setting')
    keterangan   = models.TextField(blank=True, verbose_name='Keterangan')
    checker      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='setting_rele_checked', verbose_name='Checker')
    tanggal_cek  = models.DateField(null=True, blank=True, verbose_name='Tanggal Cek')
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft', verbose_name='Status')
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='setting_rele_dibuat', verbose_name='Dibuat Oleh')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tanggal', '-created_at']
        verbose_name = 'Setting Rele'
        verbose_name_plural = 'Setting Rele'

    def __str__(self):
        return f'{self.nomor} — {self.device.nama}'

    def save(self, *args, **kwargs):
        if not self.nomor:
            self.nomor = _generate_nomor_sr()
        super().save(*args, **kwargs)

    @property
    def file_ext(self):
        if self.file_setting:
            return os.path.splitext(self.file_setting.name)[1].lower().lstrip('.')
        return ''


# ── Gambar Device ────────────────────────────────────────────────────────────

TIPE_GAMBAR_CHOICES = (
    ('wiring',      'Wiring Diagram'),
    ('single_line', 'Single Line Diagram'),
    ('skema',       'Skema Proteksi'),
    ('panel',       'Layout Panel'),
    ('lainnya',     'Lainnya'),
)


def gambar_upload(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.pdf'
    nama = slugify_simple(instance.device.nama if instance.device_id else 'DEVICE')
    tgl = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'dokumentasi/gambar/{nama}_{tgl}{ext}'


def _generate_nomor_gr():
    prefix = timezone.now().strftime('GR-%Y%m-')
    last = GambarDevice.objects.filter(nomor__startswith=prefix).order_by('-nomor').first()
    if last:
        try:
            seq = int(last.nomor.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f'{prefix}{seq:04d}'


class GambarDevice(models.Model):
    nomor       = models.CharField(max_length=25, unique=True, editable=False, verbose_name='Nomor')
    device      = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='gambar_device', verbose_name='Perangkat')
    judul       = models.CharField(max_length=200, verbose_name='Judul')
    tipe        = models.CharField(max_length=20, choices=TIPE_GAMBAR_CHOICES, default='wiring', verbose_name='Tipe Gambar')
    tanggal     = models.DateField(verbose_name='Tanggal')
    versi       = models.CharField(max_length=50, blank=True, verbose_name='Versi')
    file_gambar = models.FileField(upload_to=gambar_upload, null=True, blank=True, verbose_name='File Gambar')
    keterangan  = models.TextField(blank=True, verbose_name='Keterangan')
    checker     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='gambar_device_checked', verbose_name='Checker')
    tanggal_cek = models.DateField(null=True, blank=True, verbose_name='Tanggal Cek')
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='gambar_device_dibuat', verbose_name='Dibuat Oleh')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tanggal', '-created_at']
        verbose_name = 'Gambar / Wiring Diagram'
        verbose_name_plural = 'Gambar / Wiring Diagram'

    def __str__(self):
        return f'{self.nomor} — {self.device.nama}'

    def save(self, *args, **kwargs):
        if not self.nomor:
            self.nomor = _generate_nomor_gr()
        super().save(*args, **kwargs)

    @property
    def file_ext(self):
        if self.file_gambar:
            return os.path.splitext(self.file_gambar.name)[1].lower().lstrip('.')
        return ''

    @property
    def is_image(self):
        return self.file_ext in ('jpg', 'jpeg', 'png', 'svg')
