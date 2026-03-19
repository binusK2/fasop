from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class JadwalKunjungan(models.Model):

    STATUS_CHOICES = (
        ('planned',     'Terjadwal'),
        ('in_progress', 'Sedang Berjalan'),
        ('done',        'Selesai'),
    )

    lokasi          = models.CharField(max_length=150, verbose_name='Lokasi / Site')
    bulan_rencana   = models.PositiveSmallIntegerField(verbose_name='Bulan Rencana')   # 1–12
    tahun_rencana   = models.PositiveSmallIntegerField(verbose_name='Tahun Rencana')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    catatan         = models.TextField(blank=True, verbose_name='Catatan')
    created_by      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jadwal_dibuat', verbose_name='Dibuat oleh'
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Jadwal Kunjungan'
        verbose_name_plural = 'Jadwal Kunjungan'
        ordering            = ['tahun_rencana', 'bulan_rencana', 'lokasi']
        unique_together     = ('lokasi', 'bulan_rencana', 'tahun_rencana')

    def __str__(self):
        import calendar
        bln = calendar.month_abbr[self.bulan_rencana]
        return f'{self.lokasi} — {bln} {self.tahun_rencana}'

    @property
    def label_periode(self):
        import calendar
        return f"{calendar.month_name[self.bulan_rencana]} {self.tahun_rencana}"

    @property
    def periode_str(self):
        """Format YYYY-MM untuk filter maintenance."""
        return f"{self.tahun_rencana}-{self.bulan_rencana:02d}"

    def get_progress(self):
        """
        Hitung progres: berapa device di lokasi ini yang sudah punya
        maintenance (type=Preventive) di bulan & tahun rencana ini.
        Kembalikan dict: {total, selesai, pct, status_auto}
        """
        from devices.models import Device
        from maintenance.models import Maintenance

        devices = Device.objects.filter(
            lokasi__iexact=self.lokasi, is_deleted=False
        )
        total = devices.count()
        if total == 0:
            return {'total': 0, 'selesai': 0, 'pct': 0, 'status_auto': 'planned'}

        # Device yang sudah ada maintenance Preventive di periode ini
        selesai = devices.filter(
            maintenance__maintenance_type='Preventive',
            maintenance__date__year=self.tahun_rencana,
            maintenance__date__month=self.bulan_rencana,
        ).distinct().count()

        pct = round(selesai / total * 100)

        if selesai == 0:
            status_auto = 'planned'
        elif selesai == total:
            status_auto = 'done'
        else:
            status_auto = 'in_progress'

        return {
            'total':       total,
            'selesai':     selesai,
            'belum':       total - selesai,
            'pct':         pct,
            'status_auto': status_auto,
        }

    def sync_status(self):
        """Sinkronkan status dengan progres aktual, lalu save."""
        progress = self.get_progress()
        new_status = progress['status_auto']
        if new_status != self.status and self.status != 'done':
            # Jangan downgrade kalau sudah manual Done
            self.status = new_status
            self.save(update_fields=['status', 'updated_at'])
