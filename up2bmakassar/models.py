from django.db import models


class KinerjaAnalogHarian(models.Model):
    """
    Rekap harian kinerja (uptime) titik ANALOG, dihitung dari histori transisi
    status di OFDB (dbup2bmakasar.scd_his_analog, dibaca read-only).

    Formula (portasi dari up2bmakassar deprecated/task/old/scd_kin_analog_harian.py):
    performance = total durasi kesimpulan='VALID' dalam 1 hari / total detik dalam 1 hari * 100
    """
    point_number = models.IntegerField(db_index=True)
    path1 = models.CharField(max_length=100, blank=True, default='')
    path2 = models.CharField(max_length=100, blank=True, default='')
    path3 = models.CharField(max_length=100, blank=True, default='')
    tanggal = models.DateField(db_index=True)
    jumlah_up = models.IntegerField(default=0)
    uptime_detik = models.FloatField(default=0)
    alltime_detik = models.FloatField(default=0)
    performance = models.FloatField(default=0)  # persen, 0-100
    dihitung_pada = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['point_number', 'tanggal'], name='uniq_kinerja_analog_harian')
        ]
        indexes = [models.Index(fields=['tanggal', 'point_number'])]
        verbose_name = 'Kinerja Analog Harian'
        verbose_name_plural = 'Kinerja Analog Harian'

    def __str__(self):
        return f'{self.point_number} - {self.tanggal} ({self.performance:.2f}%)'


class KinerjaDigitalHarian(models.Model):
    """
    Rekap harian kinerja (uptime) titik DIGITAL, dihitung dari histori transisi
    status di OFDB (dbup2bmakasar.scd_his_digital, dibaca read-only).
    """
    point_number = models.IntegerField(db_index=True)
    path1 = models.CharField(max_length=100, blank=True, default='')
    path2 = models.CharField(max_length=100, blank=True, default='')
    path3 = models.CharField(max_length=100, blank=True, default='')
    tanggal = models.DateField(db_index=True)
    jumlah_up = models.IntegerField(default=0)
    uptime_detik = models.FloatField(default=0)
    alltime_detik = models.FloatField(default=0)
    performance = models.FloatField(default=0)
    dihitung_pada = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['point_number', 'tanggal'], name='uniq_kinerja_digital_harian')
        ]
        indexes = [models.Index(fields=['tanggal', 'point_number'])]
        verbose_name = 'Kinerja Digital Harian'
        verbose_name_plural = 'Kinerja Digital Harian'

    def __str__(self):
        return f'{self.point_number} - {self.tanggal} ({self.performance:.2f}%)'
