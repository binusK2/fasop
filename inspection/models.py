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
        ('master_trip',    'Master Trip'),
        ('ufls',           'UFLS'),
        ('dfr',            'DFR'),
        ('server_ads',     'Server ADS'),
        ('telecom',        'Pengujian Telekomunikasi'),
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

    # ── Flag oleh Engineer / AM ───────────────────────────────────
    is_flagged   = models.BooleanField(default=False, verbose_name='Diflag')
    flag_catatan = models.TextField(blank=True, verbose_name='Catatan Flag')
    flagged_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='flagged_inspections',
                                     verbose_name='Diflag oleh')
    flagged_at   = models.DateTimeField(null=True, blank=True,
                                        verbose_name='Waktu Flag')

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

    KONDISI_RELAY_CHOICES = (
        ('normal', 'Normal'),
        ('faulty', 'Faulty'),
    )
    LED_CHOICES = (
        ('normal', 'Normal'),
        ('faulty', 'Faulty'),
    )
    KEBERSIHAN_CHOICES = (
        ('bersih', 'Bersih'),
        ('kotor',  'Kotor'),
    )
    LAMPU_CHOICES = (
        ('nyala', 'Nyala'),
        ('mati',  'Mati'),
    )
    STATUS_IND_CHOICES = (
        ('normal',       'Normal'),
        ('tidak_normal', 'Tidak Normal'),
    )
    BLOK_SKEMA_CHOICES = (
        ('on',  'ON'),
        ('off', 'OFF'),
    )
    SELEKTOR_CHOICES = (
        ('blok', 'Blok'),
        ('on',   'ON'),
    )
    KABEL_LAN_CHOICES = (
        ('normal',   'Normal'),
        ('terlepas', 'Terlepas'),
    )

    inspection = models.OneToOneField(
        Inspection, on_delete=models.CASCADE,
        related_name='detail_defense_scheme'
    )

    # Panel / Kondisi Lingkungan
    suhu_ruangan      = models.FloatField(null=True, blank=True, verbose_name='Suhu Ruangan (°C)')
    kelembapan        = models.FloatField(null=True, blank=True, verbose_name='Kelembapan (%)')
    kebersihan_panel  = models.CharField(max_length=10, blank=True, choices=KEBERSIHAN_CHOICES, verbose_name='Kebersihan Panel')
    lampu_panel       = models.CharField(max_length=10, blank=True, choices=LAMPU_CHOICES, verbose_name='Lampu Panel')
    # Kondisi Rele
    kondisi_relay     = models.CharField(max_length=15, blank=True, choices=KONDISI_RELAY_CHOICES, verbose_name='Kondisi Rele')
    relay_healthy     = models.CharField(max_length=15, blank=True, choices=KONDISI_RELAY_CHOICES, verbose_name='Relay Healthy')
    indikator_led     = models.CharField(max_length=15, blank=True, choices=LED_CHOICES, verbose_name='Indikasi LED')
    catatan_relay     = models.CharField(max_length=300, blank=True, verbose_name='Catatan Relay')
    # Indikator LED / Alarm
    status_indikator      = models.CharField(max_length=15, blank=True, choices=STATUS_IND_CHOICES, verbose_name='Status Indikator')
    selektor_blok_skema   = models.CharField(max_length=5, blank=True, choices=BLOK_SKEMA_CHOICES, verbose_name='Selektor Blok Skema')
    # Selektor & Kabel
    posisi_selektor   = models.CharField(max_length=15, blank=True, choices=SELEKTOR_CHOICES, verbose_name='Posisi Selektor Target')
    kondisi_kabel_lan = models.CharField(max_length=20, blank=True, choices=KABEL_LAN_CHOICES, verbose_name='Kondisi Kabel LAN')
    # Pengukuran
    sumber_dc         = models.FloatField(null=True, blank=True, verbose_name='Sumber DC (V)')

    class Meta:
        verbose_name = 'Detail Inspeksi Defense Scheme'

    def __str__(self):
        return f'Defense Scheme — {self.inspection}'
    

# ─────────────────────────────────────────────────────────────────────
# DETAIL MASTER TRIP
# ─────────────────────────────────────────────────────────────────────
class InspectionMasterTrip(models.Model):

    KONDISI_RELAY_CHOICES = (
        ('normal', 'Normal'),
        ('faulty', 'Faulty'),
    )
    LED_CHOICES = (
        ('normal', 'Normal'),
        ('faulty', 'Faulty'),
    )
    KEBERSIHAN_CHOICES = (
        ('bersih', 'Bersih'),
        ('kotor',  'Kotor'),
    )
    LAMPU_CHOICES = (
        ('nyala', 'Nyala'),
        ('mati',  'Mati'),
    )
    SELEKTOR_CHOICES = (
        ('blok', 'Blok'),
        ('on',   'ON'),
    )
    KABEL_LAN_CHOICES = (
        ('normal',   'Normal'),
        ('terlepas', 'Terlepas'),
    )

    inspection = models.OneToOneField(
        Inspection, on_delete=models.CASCADE,
        related_name='detail_master_trip'
    )

    # Panel / Kondisi Lingkungan
    suhu_ruangan      = models.FloatField(null=True, blank=True, verbose_name='Suhu Ruangan (°C)')
    kelembapan        = models.FloatField(null=True, blank=True, verbose_name='Kelembapan (%)')
    kebersihan_panel  = models.CharField(max_length=10, blank=True, choices=KEBERSIHAN_CHOICES, verbose_name='Kebersihan Panel')
    lampu_panel       = models.CharField(max_length=10, blank=True, choices=LAMPU_CHOICES, verbose_name='Lampu Panel')
    # Kondisi Rele
    kondisi_relay     = models.CharField(max_length=15, blank=True, choices=KONDISI_RELAY_CHOICES, verbose_name='Kondisi Rele')
    relay_healthy     = models.CharField(max_length=15, blank=True, choices=KONDISI_RELAY_CHOICES, verbose_name='Relay Healthy')
    indikator_led     = models.CharField(max_length=15, blank=True, choices=LED_CHOICES, verbose_name='Indikasi LED')
    catatan_relay     = models.CharField(max_length=300, blank=True, verbose_name='Catatan Relay')
    # Selektor & Kabel
    posisi_selektor   = models.CharField(max_length=15, blank=True, choices=SELEKTOR_CHOICES, verbose_name='Posisi Selektor Target')
    kondisi_kabel_lan = models.CharField(max_length=20, blank=True, choices=KABEL_LAN_CHOICES, verbose_name='Kondisi Kabel LAN')
    # Pengukuran
    sumber_dc         = models.FloatField(null=True, blank=True, verbose_name='Sumber DC (V)')

    class Meta:
        verbose_name = 'Detail Inspeksi Master Trip'

    def __str__(self):
        return f'Master Trip — {self.inspection}'

# ─────────────────────────────────────────────────────────────────────
# DETAIL UFLS
# ─────────────────────────────────────────────────────────────────────
class InspectionUFLS(models.Model):

    KONDISI_RELAY_CHOICES = (
        ('normal', 'Normal'),
        ('faulty', 'Faulty'),
    )
    LED_CHOICES = (
        ('normal', 'Normal'),
        ('faulty', 'Faulty'),
    )
    KEBERSIHAN_CHOICES = (
        ('bersih', 'Bersih'),
        ('kotor',  'Kotor'),
    )
    LAMPU_CHOICES = (
        ('nyala', 'Nyala'),
        ('mati',  'Mati'),
    )
    SELEKTOR_CHOICES = (
        ('on_aktif',    'ON / Aktif'),
        ('off_nonaktif','OFF / Nonaktif'),
    )
    KABEL_LAN_CHOICES = (
        ('terpasang',      'Terpasang'),
        ('terlepas',       'Terlepas'),
        ('tidak_tersedia', 'Tidak Tersedia'),
    )

    inspection = models.OneToOneField(
        Inspection, on_delete=models.CASCADE,
        related_name='detail_ufls'
    )

    # Panel / Kondisi Lingkungan
    suhu_ruangan      = models.FloatField(null=True, blank=True, verbose_name='Suhu Ruangan (°C)')
    kelembapan        = models.FloatField(null=True, blank=True, verbose_name='Kelembapan (%)')
    kebersihan_panel  = models.CharField(max_length=10, blank=True, choices=KEBERSIHAN_CHOICES, verbose_name='Kebersihan Panel')
    lampu_panel       = models.CharField(max_length=10, blank=True, choices=LAMPU_CHOICES, verbose_name='Lampu Panel')
    # Kondisi Rele
    kondisi_relay     = models.CharField(max_length=15, blank=True, choices=KONDISI_RELAY_CHOICES, verbose_name='Kondisi Rele')
    relay_healthy     = models.CharField(max_length=15, blank=True, choices=KONDISI_RELAY_CHOICES, verbose_name='Relay Healthy')
    indikator_led     = models.CharField(max_length=15, blank=True, choices=LED_CHOICES, verbose_name='Indikasi LED')
    catatan_relay     = models.CharField(max_length=300, blank=True, verbose_name='Catatan Relay')
    # Selektor & Kabel
    posisi_selektor   = models.CharField(max_length=15, blank=True, choices=SELEKTOR_CHOICES, verbose_name='Posisi Selektor Target')
    kondisi_kabel_lan = models.CharField(max_length=20, blank=True, choices=KABEL_LAN_CHOICES, verbose_name='Kondisi Kabel LAN')
    # Pengukuran
    sumber_dc         = models.FloatField(null=True, blank=True, verbose_name='Sumber DC (V)')

    class Meta:
        verbose_name = 'Detail Inspeksi UFLS'

    def __str__(self):
        return f'UFLS — {self.inspection}'

# ─────────────────────────────────────────────────────────────────────
# DETAIL DFR
# ─────────────────────────────────────────────────────────────────────
class InspectionDFR(models.Model):

    KONDISI_CHOICES = (
        ('normal', 'Normal'),
        ('faulty', 'Faulty'),
    )
    HEALTHY_CHOICES = (
        ('healthy', 'Healthy'),
        ('faulty',  'Faulty'),
        ('alarm',   'Alarm'),
    )
    LED_ALARM_CHOICES = (
        ('ada',      'Ada'),
        ('tidak_ada','Tidak Ada'),
    )
    STATUS_IND_CHOICES = (
        ('normal',       'Normal'),
        ('tidak_normal', 'Tidak Normal'),
    )
    KABEL_LAN_CHOICES = (
        ('normal',   'Normal'),
        ('terlepas', 'Terlepas'),
    )
    KEBERSIHAN_CHOICES = (
        ('bersih', 'Bersih'),
        ('kotor',  'Kotor'),
    )
    LAMPU_CHOICES = (
        ('baik',           'Baik'),
        ('tidak_berfungsi','Tidak Berfungsi'),
        ('redup',          'Redup'),
    )

    inspection = models.OneToOneField(
        Inspection, on_delete=models.CASCADE,
        related_name='detail_dfr'
    )

    # Kondisi Lingkungan
    suhu_ruangan      = models.FloatField(null=True, blank=True, verbose_name='Suhu Ruangan (°C)')
    kelembapan        = models.FloatField(null=True, blank=True, verbose_name='Kelembapan (%)')
    kebersihan_ruangan= models.CharField(max_length=10, blank=True, choices=KEBERSIHAN_CHOICES, verbose_name='Kebersihan')
    lampu_penerangan  = models.CharField(max_length=20, blank=True, choices=LAMPU_CHOICES, verbose_name='Lampu Penerangan')

    # Kondisi DFR
    kondisi_dfr       = models.CharField(max_length=15, blank=True, choices=KONDISI_CHOICES, verbose_name='Kondisi DFR')
    healthy_status    = models.CharField(max_length=10, blank=True, choices=HEALTHY_CHOICES, verbose_name='Healthy Status')
    indikasi_led_alarm= models.CharField(max_length=10, blank=True, choices=LED_ALARM_CHOICES, verbose_name='Indikasi LED Alarm')
    status_indikator  = models.CharField(max_length=15, blank=True, choices=STATUS_IND_CHOICES, verbose_name='Status Indikator')
    kondisi_kabel_lan = models.CharField(max_length=10, blank=True, choices=KABEL_LAN_CHOICES, verbose_name='Kondisi Kabel LAN')

    class Meta:
        verbose_name = 'Detail Inspeksi DFR'

    def __str__(self):
        return f'DFR — {self.inspection}'


# ─────────────────────────────────────────────────────────────────────
# DETAIL SERVER ADS
# ─────────────────────────────────────────────────────────────────────
class InspectionServerADS(models.Model):

    NORMAL_CHOICES = (
        ('normal',       'Normal'),
        ('tidak_normal', 'Tidak Normal'),
    )
    HMI_CHOICES = (
        ('normal',         'Normal'),
        ('tidak_normal',   'Tidak Normal'),
        ('tidak_tersedia', 'Tidak Tersedia'),
    )
    SWITCH_CHOICES = (
        ('normal', 'Normal'),
        ('mati',   'Mati'),
    )
    FAN_CHOICES = (
        ('nyala', 'Nyala'),
        ('mati',  'Mati'),
    )
    KEBERSIHAN_CHOICES = (
        ('bersih', 'Bersih'),
        ('kotor',  'Kotor'),
    )
    LAMPU_CHOICES = (
        ('baik',           'Baik'),
        ('tidak_berfungsi','Tidak Berfungsi'),
        ('redup',          'Redup'),
    )

    inspection = models.OneToOneField(
        Inspection, on_delete=models.CASCADE,
        related_name='detail_server_ads'
    )

    # Kondisi Lingkungan
    suhu_ruangan        = models.FloatField(null=True, blank=True, verbose_name='Suhu Ruangan (°C)')
    kelembapan          = models.FloatField(null=True, blank=True, verbose_name='Kelembapan (%)')
    kebersihan_ruangan  = models.CharField(max_length=10, blank=True, choices=KEBERSIHAN_CHOICES, verbose_name='Kebersihan')
    lampu_penerangan    = models.CharField(max_length=20, blank=True, choices=LAMPU_CHOICES, verbose_name='Lampu Penerangan')

    # Peralatan
    peralatan_server_ads  = models.CharField(max_length=15, blank=True, choices=NORMAL_CHOICES, verbose_name='Peralatan Server ADS')
    tampilan_hmi          = models.CharField(max_length=20, blank=True, choices=HMI_CHOICES, verbose_name='Tampilan HMI')
    peralatan_gateway_ic3 = models.CharField(max_length=15, blank=True, choices=NORMAL_CHOICES, verbose_name='Peralatan Gateway IC3 ADS')
    kondisi_switch_lan    = models.CharField(max_length=10, blank=True, choices=SWITCH_CHOICES, verbose_name='Kondisi Switch Kabel LAN')
    peralatan_power_supply= models.CharField(max_length=15, blank=True, choices=NORMAL_CHOICES, verbose_name='Peralatan Power Supply')
    fan_panel             = models.CharField(max_length=10, blank=True, choices=FAN_CHOICES, verbose_name='Fan Panel')

    class Meta:
        verbose_name = 'Detail Inspeksi Server ADS'

    def __str__(self):
        return f'Server ADS — {self.inspection}'


# ─────────────────────────────────────────────────────────────────────
# DETAIL PENGUJIAN TELEKOMUNIKASI (Radio & VoIP — Dispatcher)
# ─────────────────────────────────────────────────────────────────────
class InspectionTelecom(models.Model):

    HASIL_CHOICES = (
        ('normal',       'Normal'),
        ('tidak_normal', 'Tidak Normal'),
    )
    KUALITAS_CHOICES = (
        ('baik',  'Baik'),
        ('cukup', 'Cukup'),
        ('buruk', 'Buruk'),
    )

    inspection = models.OneToOneField(
        Inspection, on_delete=models.CASCADE,
        related_name='detail_telecom'
    )

    # Hasil pengujian utama
    hasil_komunikasi = models.CharField(
        max_length=15, blank=True, choices=HASIL_CHOICES,
        verbose_name='Hasil Pengujian Komunikasi',
    )
    kualitas_suara = models.CharField(
        max_length=10, blank=True, choices=KUALITAS_CHOICES,
        verbose_name='Kualitas Suara',
    )
    catatan_pengujian = models.TextField(
        blank=True, verbose_name='Catatan Pengujian',
    )

    class Meta:
        verbose_name = 'Detail Pengujian Telekomunikasi'

    def __str__(self):
        return f'Telecom — {self.inspection}'


# ─────────────────────────────────────────────────────────────────────
# PENGUJIAN TELEKOMUNIKASI — Batch form (Dispatcher)
# ─────────────────────────────────────────────────────────────────────
class PengujianTelecom(models.Model):
    """Header satu sesi pengujian telekomunikasi per lokasi."""

    JENIS_FORM_CHOICES = (
        ('radio', 'Radio'),
        ('voip',  'VoIP'),
        ('all',   'Radio & VoIP'),
    )
    jenis       = models.CharField(max_length=10, choices=JENIS_FORM_CHOICES, default='all',
                                   verbose_name='Jenis Pengujian')
    tanggal     = models.DateField(default=timezone.now, verbose_name='Tanggal Pengujian')
    lokasi      = models.CharField(max_length=100, blank=True, verbose_name='Lokasi / GI')
    dibuat_oleh = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='pengujian_telecom',
                                    verbose_name='Dibuat Oleh')
    catatan     = models.TextField(blank=True, verbose_name='Catatan Umum')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-tanggal', '-created_at']
        verbose_name = 'Pengujian Telekomunikasi'
        verbose_name_plural = 'Pengujian Telekomunikasi'

    def __str__(self):
        return f'{self.lokasi} — {self.tanggal}'


class PengujianTelecomItem(models.Model):
    """Satu baris hasil pengujian per perangkat Radio / VoIP."""

    HASIL_CHOICES = (
        ('normal',       'Normal'),
        ('tidak_normal', 'Tidak Normal'),
    )

    pengujian = models.ForeignKey(PengujianTelecom, on_delete=models.CASCADE,
                                  related_name='items')
    device    = models.ForeignKey(Device, on_delete=models.CASCADE,
                                  related_name='pengujian_telecom_items')
    hasil     = models.CharField(max_length=15, choices=HASIL_CHOICES,
                                 default='normal', verbose_name='Hasil')
    catatan   = models.TextField(blank=True, verbose_name='Catatan')

    class Meta:
        ordering = ['device__jenis__name', 'device__nama']
        verbose_name = 'Item Pengujian Telekomunikasi'

    def __str__(self):
        return f'{self.device.nama} — {self.get_hasil_display()}'
