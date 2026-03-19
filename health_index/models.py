from django.db import models
from devices.models import Device


class HISnapshot(models.Model):
    """
    Snapshot Health Index per peralatan, disimpan otomatis sekali per bulan.
    Data historis ini dipakai untuk grafik tren kondisi peralatan.
    """
    device      = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='hi_snapshots')
    score       = models.IntegerField(verbose_name='Skor HI')
    kategori    = models.CharField(max_length=20, verbose_name='Kategori')   # label string
    breakdown   = models.JSONField(default=list, verbose_name='Breakdown Faktor')
    bulan       = models.PositiveSmallIntegerField(verbose_name='Bulan')      # 1–12
    tahun       = models.PositiveSmallIntegerField(verbose_name='Tahun')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Snapshot Health Index'
        verbose_name_plural = 'Snapshot Health Index'
        unique_together     = ('device', 'bulan', 'tahun')   # satu snapshot per device per bulan
        ordering            = ['-tahun', '-bulan']

    def __str__(self):
        return f'{self.device.nama} — {self.bulan:02d}/{self.tahun} — {self.score}'

    @property
    def label_bulan(self):
        import calendar
        return f"{calendar.month_abbr[self.bulan]} {self.tahun}"
