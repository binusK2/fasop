from django.db import models
from django.contrib.auth.models import User
from devices.models import Device
import os
from django.utils import timezone


def inspection_photo_upload(instance, filename):
    import re
    ext  = os.path.splitext(filename)[1].lower() or '.jpg'
    nama = re.sub(r'[^\w]', '_', str(instance.device.nama if instance.device else 'DEV'))[:30]
    tgl  = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'inspection_photos/{nama}_{tgl}{ext}'


# ─────────────────────────────────────────────────────────────────────
# MODEL INDUK INSPECTION
# ─────────────────────────────────────────────────────────────────────
class Inspection(models.Model):
    """Header inspeksi inservice — satu record per sesi inspeksi per device."""

    JENIS_CHOICES = (
        ('catu_daya',      'Catu Daya'),
        ('defense_scheme', 'Rele Defense Scheme'),
    )

    device      = models.ForeignKey(Device, on_delete=models.CASCADE,
                                    related_name='inspections')
    jenis       = models.CharField(max_length=30, choices=JENIS_CHOICES,
                                   verbose_name='Jenis Inspeksi')
    tanggal     = models.DateTimeField(default=timezone.now,
                                       verbose_name='Tanggal Inspeksi')
    operator    = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='inspections',
                                    verbose_name='Operator')
    foto        = models.ImageField(upload_to=inspection_photo_upload,
                                    blank=True, null=True,
                                    verbose_name='Foto Dokumentasi')
    catatan     = models.TextField(blank=True, verbose_name='Catatan Umum')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-tanggal']
        verbose_name = 'Inspeksi Inservice'

    def __str__(self):
        return f'{self.device.nama} — {self.get_jenis_display()} ({self.tanggal.strftime("%d/%m/%Y")})'


# ─────────────────────────────────────────────────────────────────────
# DETAIL CATU DAYA
# ─────────────────────────────────────────────────────────────────────
class InspectionCatuDaya(models.Model):

    KONDISI_CHOICES = (
        ('normal', 'Normal'),
        ('alarm',  'Alarm'),
    )
    KEBERSIHAN_CHOICES = (
        ('bersih', 'Bersih'),
        ('kotor',  'Kotor'),
    )
    ADA_CHOICES = (
        ('ada',      'Ada'),
        ('tidak_ada','Tidak Ada'),
    )
    MODE_CHOICES = (
        ('float',      'Float'),
        ('boost',      'Boost'),
        ('equalizing', 'Equalizing'),
    )
    LEVEL_CHOICES = (
        ('normal',       'Normal'),
        ('bawah_level',  'Di Bawah Level'),
        ('atas_level',   'Di Atas Level'),
    )
    NYALA_CHOICES = (
        ('nyala', 'Nyala'),
        ('mati',  'Mati'),
    )

    inspection = models.OneToOneField(
        Inspection, on_delete=models.CASCADE,
        related_name='detail_catu_daya'
    )

    # ── Rectifier ────────────────────────────────────────────────────
    kondisi_rectifier        = models.CharField(max_length=10, choices=KONDISI_CHOICES,
                                                blank=True, verbose_name='Kondisi Rectifier')
    catatan_rectifier        = models.CharField(max_length=300, blank=True,
                                                verbose_name='Catatan Rectifier')
    mode_recti               = models.CharField(max_length=15, choices=MODE_CHOICES,
                                                blank=True, verbose_name='Mode Rectifier')

    # ── Alarm ─────────────────────────────────────────────────────────
    alarm_ground_fault       = models.CharField(max_length=10, choices=ADA_CHOICES,
                                                blank=True, verbose_name='Alarm Ground Fault')
    alarm_min_ac_fault       = models.CharField(max_length=10, choices=ADA_CHOICES,
                                                blank=True, verbose_name='Alarm Min AC Fault')
    alarm_recti_fault        = models.CharField(max_length=10, choices=ADA_CHOICES,
                                                blank=True, verbose_name='Alarm Recti Fault')

    # ── Ruangan ──────────────────────────────────────────────────────
    kebersihan_ruangan       = models.CharField(max_length=10, choices=KEBERSIHAN_CHOICES,
                                                blank=True, verbose_name='Kebersihan Ruangan')

    # ── Baterai / Bank ───────────────────────────────────────────────
    kondisi_baterai          = models.CharField(max_length=10, choices=KEBERSIHAN_CHOICES,
                                                blank=True, verbose_name='Kondisi Baterai')
    catatan_baterai          = models.CharField(max_length=300, blank=True,
                                                verbose_name='Catatan Baterai')

    # ── Bank ─────────────────────────────────────────────────────────
    level_air_bank           = models.CharField(max_length=15, choices=LEVEL_CHOICES,
                                                blank=True, verbose_name='Level Air Bank')
    kebersihan_ruangan_bank  = models.CharField(max_length=10, choices=KEBERSIHAN_CHOICES,
                                                blank=True, verbose_name='Kebersihan Ruangan Bank')
    kebersihan_bank          = models.CharField(max_length=10, choices=KEBERSIHAN_CHOICES,
                                                blank=True, verbose_name='Kebersihan Bank')
    exhaust_fan              = models.CharField(max_length=10, choices=NYALA_CHOICES,
                                                blank=True, verbose_name='Exhaust Fan')

    # ── Pengukuran ───────────────────────────────────────────────────
    tegangan_input_ac        = models.FloatField(null=True, blank=True,
                                                 verbose_name='Tegangan Input AC (V)')
    arus_input_ac            = models.FloatField(null=True, blank=True,
                                                 verbose_name='Arus Input AC (A)')
    tegangan_load_dc         = models.FloatField(null=True, blank=True,
                                                 verbose_name='Tegangan Load DC (V)')
    arus_load_dc             = models.FloatField(null=True, blank=True,
                                                 verbose_name='Arus Load DC (A)')
    tegangan_baterai_dc      = models.FloatField(null=True, blank=True,
                                                 verbose_name='Tegangan Baterai DC (V)')
    arus_baterai_dc          = models.FloatField(null=True, blank=True,
                                                 verbose_name='Arus Baterai DC (A)')

    # ── Kondisi Keseluruhan ──────────────────────────────────────────
    kondisi_keseluruhan      = models.CharField(max_length=10, choices=KEBERSIHAN_CHOICES,
                                                blank=True, verbose_name='Kondisi Keseluruhan')

    class Meta:
        verbose_name = 'Detail Inspeksi Catu Daya'

    def __str__(self):
        return f'Catu Daya — {self.inspection}'


# ─────────────────────────────────────────────────────────────────────
# DETAIL RELE DEFENSE SCHEME
# ─────────────────────────────────────────────────────────────────────
class InspectionDefenseScheme(models.Model):

    KONDISI_CHOICES = (
        ('normal',      'Normal'),
        ('alarm',       'Alarm'),
    )
    INDIKATOR_CHOICES = (
        ('normal',      'Normal'),
        ('tidak_normal','Tidak Normal'),
    )

    inspection = models.OneToOneField(
        Inspection, on_delete=models.CASCADE,
        related_name='detail_defense_scheme'
    )

    # Kondisi Relay
    kondisi_relay            = models.CharField(max_length=15, choices=KONDISI_CHOICES,
                                                blank=True, verbose_name='Kondisi Relay')
    catatan_relay            = models.CharField(max_length=300, blank=True,
                                                verbose_name='Catatan Relay')

    # Indikator LED/Alarm
    indikator_led            = models.CharField(max_length=15, choices=INDIKATOR_CHOICES,
                                                blank=True, verbose_name='Indikator LED/Alarm')
    catatan_led              = models.CharField(max_length=300, blank=True,
                                                verbose_name='Catatan LED/Alarm')

    # Sumber DC
    sumber_dc                = models.FloatField(null=True, blank=True,
                                                 verbose_name='Sumber DC (V)')

    class Meta:
        verbose_name = 'Detail Inspeksi Defense Scheme'

    def __str__(self):
        return f'Defense Scheme — {self.inspection}'
