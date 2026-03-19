from django.db import models
from devices.models import Device


class Notifikasi(models.Model):

    TIPE_CHOICES = (
        ('hi_rendah',           'Health Index Rendah'),
        ('hi_turun',            'HI Turun Drastis'),
        ('maintenance_overdue', 'Maintenance Overdue'),
        ('gangguan_lama',       'Gangguan Terlalu Lama'),
    )

    LEVEL_CHOICES = (
        ('danger',  'Danger'),
        ('warning', 'Warning'),
        ('info',    'Info'),
    )

    device      = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='notifikasi', null=True, blank=True)
    tipe        = models.CharField(max_length=30, choices=TIPE_CHOICES)
    judul       = models.CharField(max_length=200)
    pesan       = models.TextField()
    level       = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='warning')
    url         = models.CharField(max_length=200, blank=True)
    is_read     = models.BooleanField(default=False, verbose_name='Sudah Dibaca')
    created_at  = models.DateTimeField(auto_now_add=True)
    read_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Notifikasi'
        verbose_name_plural = 'Notifikasi'
        ordering            = ['-created_at']

    def __str__(self):
        return f'[{self.level.upper()}] {self.judul}'

    @property
    def level_color(self):
        return {'danger': '#ef4444', 'warning': '#f59e0b', 'info': '#3b82f6'}.get(self.level, '#94a3b8')

    @property
    def level_bg(self):
        return {'danger': '#fee2e2', 'warning': '#fef3c7', 'info': '#dbeafe'}.get(self.level, '#f1f5f9')

    @property
    def level_icon(self):
        return {'danger': 'bi-exclamation-triangle-fill', 'warning': 'bi-exclamation-circle-fill', 'info': 'bi-info-circle-fill'}.get(self.level, 'bi-bell')
