from django.db import models
from devices.models import Device
from django.contrib.auth.models import User
from django.utils import timezone
import os
import re


def slugify_simple(text):
    text = str(text).strip().upper()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s]+', '_', text)
    return text[:40]


def maintenance_photo_upload(instance, filename):
    ext   = os.path.splitext(filename)[1].lower() or '.jpg'
    nama  = slugify_simple(instance.device.nama if instance.device else 'PERANGKAT')
    lokasi = slugify_simple(instance.device.lokasi if instance.device and instance.device.lokasi else 'LOKASI')
    tgl   = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'maintenance_photos/{nama}_{lokasi}_{tgl}{ext}'


# ─────────────────────────────────────────────────────────────
# MODEL UTAMA MAINTENANCE
# ─────────────────────────────────────────────────────────────
class Maintenance(models.Model):

    MAINTENANCE_TYPE = (
        ('Preventive', 'Preventive'),
        ('Corrective', 'Corrective'),
    )

    STATUS_CHOICES = (
        ('Open', 'Open'),
        ('Done', 'Done'),
    )

    device          = models.ForeignKey(Device, on_delete=models.CASCADE)
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPE)
    date            = models.DateTimeField()
    description     = models.TextField(blank=True)
    technicians     = models.ManyToManyField(User, blank=True, related_name='maintenance_technician_set', verbose_name='Pelaksana')
    pelaksana_names = models.JSONField(default=list, blank=True, verbose_name='Nama Pelaksana')
    signed_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='signed_maintenances', verbose_name='Ditandatangani oleh')
    signed_at       = models.DateTimeField(null=True, blank=True, verbose_name='Waktu TTD')
    catatan_am      = models.TextField(blank=True, default='', verbose_name='Catatan Asisten Manager')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    photo           = models.ImageField(upload_to=maintenance_photo_upload, blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.device} — {self.maintenance_type} ({self.date})"


# ─────────────────────────────────────────────────────────────
# DETAIL PLC
# ─────────────────────────────────────────────────────────────
class MaintenancePLC(models.Model):

    STATUS_CHECK = (
        ('OK', 'OK'),
        ('NOK', 'NOK'),
    )

    maintenance         = models.OneToOneField(Maintenance, on_delete=models.CASCADE)
    akses_plc           = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    remote_akses_plc    = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    transmission_line   = models.FloatField(null=True, blank=True)
    rx_pilot_level      = models.FloatField(null=True, blank=True)
    freq_tx             = models.FloatField(null=True, blank=True, verbose_name='Frequency TX (MHz)')
    bandwidth_tx        = models.FloatField(null=True, blank=True, verbose_name='Bandwidth TX (MHz)')
    freq_rx             = models.FloatField(null=True, blank=True, verbose_name='Frequency RX (MHz)')
    bandwidth_rx        = models.FloatField(null=True, blank=True, verbose_name='Bandwidth RX (MHz)')
    time_sync           = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    wave_trap           = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    imu                 = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    kabel_coaxial       = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    modul_terpasang     = models.JSONField(default=list, blank=True, verbose_name='Modul Terpasang')

    class Meta:
        verbose_name = 'Maintenance PLC'


# ─────────────────────────────────────────────────────────────
# DETAIL ROUTER / SWITCH
# ─────────────────────────────────────────────────────────────
class MaintenanceRouter(models.Model):

    STATUS_CHECK = (
        ('OK', 'OK'),
        ('NOK', 'NOK'),
    )

    maintenance = models.OneToOneField(Maintenance, on_delete=models.CASCADE)

    # Checklist fisik
    kondisi_fisik   = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True,
                                       verbose_name='Kondisi Fisik Unit')
    led_link        = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True,
                                       verbose_name='Indikator LED Link/Port')
    kondisi_kabel   = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True,
                                       verbose_name='Kondisi Kabel & Konektor')

    # Nilai pengukuran
    tegangan_input  = models.FloatField(null=True, blank=True, verbose_name='Tegangan Input (V)')
    suhu_perangkat  = models.FloatField(null=True, blank=True, verbose_name='Suhu Perangkat (°C)')
    cpu_load        = models.FloatField(null=True, blank=True, verbose_name='CPU Load (%)')
    memory_usage    = models.FloatField(null=True, blank=True, verbose_name='Memory Usage (%)')

    # Kondisi interface / port
    jumlah_port_aktif   = models.PositiveSmallIntegerField(null=True, blank=True,
                                                           verbose_name='Port Aktif')
    jumlah_port_total   = models.PositiveSmallIntegerField(null=True, blank=True,
                                                           verbose_name='Port Total')
    status_routing      = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True,
                                           verbose_name='IP / Routing Status')
    detail_port         = models.TextField(blank=True,
                                           verbose_name='Detail Status Port')

    # SFP Port (jumlah + detail per port disimpan sebagai JSON)
    jumlah_sfp_port  = models.PositiveSmallIntegerField(null=True, blank=True,
                                                        verbose_name='Jumlah SFP Port')
    sfp_port_data    = models.TextField(blank=True,
                                        verbose_name='Data SFP Port (JSON)')

    # Catatan bebas
    catatan_tambahan = models.TextField(blank=True, verbose_name='Catatan Tambahan')

    class Meta:
        verbose_name = 'Maintenance Router/Switch'


# ─────────────────────────────────────────────────────────────
# DETAIL RADIO KOMUNIKASI
# ─────────────────────────────────────────────────────────────
class MaintenanceRadio(models.Model):

    STATUS_CHECK = (
        ('OK', 'OK'),
        ('NOK', 'NOK'),
    )

    KEBERSIHAN_CHOICES = (
        ('Bersih', 'Bersih'),
        ('Kotor', 'Kotor'),
    )

    LAMPU_CHOICES = (
        ('Menyala', 'Menyala'),
        ('Tidak Menyala', 'Tidak Menyala'),
        ('Redup', 'Redup'),
        ('Tidak Ada', 'Tidak Ada'),
    )

    ANTENA_CHOICES = (
        ('Directional', 'Directional'),
        ('Bidirectional', 'Bidirectional'),
    )

    maintenance = models.OneToOneField(Maintenance, on_delete=models.CASCADE)

    # Kondisi ruangan
    suhu_ruangan        = models.FloatField(null=True, blank=True, verbose_name='Suhu Ruangan (°C)')
    kebersihan          = models.CharField(max_length=10, choices=KEBERSIHAN_CHOICES, blank=True)
    lampu_penerangan    = models.CharField(max_length=15, choices=LAMPU_CHOICES, blank=True)

    # Peralatan terpasang (checklist keberadaan)
    ada_radio           = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Radio')
    ada_battery         = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Battery')
    merk_battery        = models.CharField(max_length=100, blank=True, verbose_name='Merk Battery')
    ada_power_supply    = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Power Supply')
    merk_power_supply   = models.CharField(max_length=100, blank=True, verbose_name='Merk Power Supply')
    jenis_antena        = models.CharField(max_length=15, choices=ANTENA_CHOICES, blank=True, verbose_name='Jenis Antena')

    # Pengukuran
    swr                 = models.FloatField(null=True, blank=True, verbose_name='SWR')
    power_tx            = models.FloatField(null=True, blank=True, verbose_name='Power TX (W)')
    tegangan_battery    = models.FloatField(null=True, blank=True, verbose_name='Tegangan Battery (V)')
    tegangan_psu        = models.FloatField(null=True, blank=True, verbose_name='Tegangan Power Supply (V)')
    frekuensi_tx        = models.FloatField(null=True, blank=True, verbose_name='Frekuensi TX / Tone (MHz)')
    frekuensi_rx        = models.FloatField(null=True, blank=True, verbose_name='Frekuensi RX / Tone (MHz)')

    # Catatan
    catatan             = models.TextField(blank=True, verbose_name='Catatan')

    class Meta:
        verbose_name = 'Maintenance Radio'


# ─────────────────────────────────────────────────────────────────────
# DETAIL VOIP
# ─────────────────────────────────────────────────────────────────────
class MaintenanceVoIP(models.Model):

    STATUS_CHECK = (
        ('OK', 'OK'),
        ('NOK', 'NOK'),
    )

    maintenance = models.OneToOneField(Maintenance, on_delete=models.CASCADE)

    # Informasi perangkat
    ip_address       = models.CharField(max_length=50, blank=True, verbose_name='IP Address')
    extension_number = models.CharField(max_length=50, blank=True, verbose_name='Extension Number')
    sip_server_1     = models.CharField(max_length=100, blank=True, verbose_name='SIP Server 1')
    sip_server_2     = models.CharField(max_length=100, blank=True, verbose_name='SIP Server 2')

    # Kondisi lingkungan
    suhu_ruangan    = models.FloatField(null=True, blank=True, verbose_name='Suhu Ruangan (°C)')

    # Checklist OK/NOK
    kondisi_fisik   = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True,
                                        verbose_name='Kondisi Fisik Perangkat')
    ntp_server      = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True,
                                        verbose_name='NTP Server')
    webconfig       = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True,
                                        verbose_name='Web Config')

    # Power Supply
    ps_merk         = models.CharField(max_length=100, blank=True, verbose_name='Merk Power Supply')
    ps_tegangan_input = models.FloatField(null=True, blank=True, verbose_name='Tegangan Input PSU (V)')
    ps_status       = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True,
                                        verbose_name='Status Power Supply')

    # Catatan
    catatan         = models.TextField(blank=True, verbose_name='Catatan')

    class Meta:
        verbose_name = 'Maintenance VoIP'


# ─────────────────────────────────────────────────────────────────────
# DETAIL MULTIPLEXER
# ─────────────────────────────────────────────────────────────────────
class MaintenanceMux(models.Model):

    STATUS_CHECK = (('OK', 'OK'), ('NOK', 'NOK'),)
    KEBERSIHAN_CHOICES = (('Bersih', 'Bersih'), ('Kotor', 'Kotor'),)
    LAMPU_CHOICES = (
        ('Menyala', 'Menyala'),
        ('Tidak Menyala', 'Tidak Menyala'),
        ('Redup', 'Redup'),
    )

    maintenance = models.OneToOneField(Maintenance, on_delete=models.CASCADE)

    # Kondisi Lingkungan
    suhu_ruangan      = models.FloatField(null=True, blank=True, verbose_name='Suhu Ruangan (°C)')
    kebersihan        = models.CharField(max_length=10, choices=KEBERSIHAN_CHOICES, blank=True)
    lampu_penerangan  = models.CharField(max_length=15, choices=LAMPU_CHOICES, blank=True)

    # Peralatan Terpasang
    brand             = models.CharField(max_length=100, blank=True, verbose_name='Brand')
    firmware          = models.CharField(max_length=100, blank=True, verbose_name='Firmware')
    sync_source_1     = models.CharField(max_length=100, blank=True, verbose_name='Sync Source 1')
    sync_source_2     = models.CharField(max_length=100, blank=True, verbose_name='Sync Source 2')

    # CPU
    cpu_1             = models.TextField(blank=True, verbose_name='CPU 1')
    cpu_2             = models.TextField(blank=True, verbose_name='CPU 2')

    # HS 1
    hs1_merk          = models.CharField(max_length=100, blank=True)
    hs1_tx_bias       = models.FloatField(null=True, blank=True, verbose_name='HS1 TX Bias (mA)')
    hs1_jarak         = models.FloatField(null=True, blank=True, verbose_name='HS1 Jarak (km)')
    hs1_tx            = models.FloatField(null=True, blank=True, verbose_name='HS1 Nilai TX (dBm)')
    hs1_lambda        = models.FloatField(null=True, blank=True, verbose_name='HS1 Lambda (nm)')
    hs1_suhu          = models.FloatField(null=True, blank=True, verbose_name='HS1 Suhu (°C)')
    hs1_rx            = models.FloatField(null=True, blank=True, verbose_name='HS1 Nilai RX (dBm)')
    hs1_bandwidth     = models.CharField(max_length=50, blank=True, verbose_name='HS1 Bandwidth')

    # HS 2
    hs2_merk          = models.CharField(max_length=100, blank=True)
    hs2_tx_bias       = models.FloatField(null=True, blank=True, verbose_name='HS2 TX Bias (mA)')
    hs2_jarak         = models.FloatField(null=True, blank=True, verbose_name='HS2 Jarak (km)')
    hs2_tx            = models.FloatField(null=True, blank=True, verbose_name='HS2 Nilai TX (dBm)')
    hs2_lambda        = models.FloatField(null=True, blank=True, verbose_name='HS2 Lambda (nm)')
    hs2_suhu          = models.FloatField(null=True, blank=True, verbose_name='HS2 Suhu (°C)')
    hs2_rx            = models.FloatField(null=True, blank=True, verbose_name='HS2 Nilai RX (dBm)')
    hs2_bandwidth     = models.CharField(max_length=50, blank=True, verbose_name='HS2 Bandwidth')

    # Slot A–H (nama modul + keterangan isian)
    slot_a_modul      = models.CharField(max_length=100, blank=True, verbose_name='Slot A Modul')
    slot_a_isian      = models.TextField(blank=True, verbose_name='Slot A Isian')
    slot_b_modul      = models.CharField(max_length=100, blank=True, verbose_name='Slot B Modul')
    slot_b_isian      = models.TextField(blank=True, verbose_name='Slot B Isian')
    slot_c_modul      = models.CharField(max_length=100, blank=True, verbose_name='Slot C Modul')
    slot_c_isian      = models.TextField(blank=True, verbose_name='Slot C Isian')
    slot_d_modul      = models.CharField(max_length=100, blank=True, verbose_name='Slot D Modul')
    slot_d_isian      = models.TextField(blank=True, verbose_name='Slot D Isian')
    slot_e_modul      = models.CharField(max_length=100, blank=True, verbose_name='Slot E Modul')
    slot_e_isian      = models.TextField(blank=True, verbose_name='Slot E Isian')
    slot_f_modul      = models.CharField(max_length=100, blank=True, verbose_name='Slot F Modul')
    slot_f_isian      = models.TextField(blank=True, verbose_name='Slot F Isian')
    slot_g_modul      = models.CharField(max_length=100, blank=True, verbose_name='Slot G Modul')
    slot_g_isian      = models.TextField(blank=True, verbose_name='Slot G Isian')
    slot_h_modul      = models.CharField(max_length=100, blank=True, verbose_name='Slot H Modul')
    slot_h_isian      = models.TextField(blank=True, verbose_name='Slot H Isian')

    # PSU 1
    psu1_status       = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    psu1_temp1        = models.FloatField(null=True, blank=True, verbose_name='PSU1 Temp Sensor 1 (°C)')
    psu1_temp2        = models.FloatField(null=True, blank=True, verbose_name='PSU1 Temp Sensor 2 (°C)')
    psu1_temp3        = models.FloatField(null=True, blank=True, verbose_name='PSU1 Temp Sensor 3 (°C)')

    # PSU 2
    psu2_status       = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    psu2_temp1        = models.FloatField(null=True, blank=True, verbose_name='PSU2 Temp Sensor 1 (°C)')
    psu2_temp2        = models.FloatField(null=True, blank=True, verbose_name='PSU2 Temp Sensor 2 (°C)')
    psu2_temp3        = models.FloatField(null=True, blank=True, verbose_name='PSU2 Temp Sensor 3 (°C)')

    # FAN
    fan_status        = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)

    # Catatan
    catatan           = models.TextField(blank=True, verbose_name='Catatan')

    class Meta:
        verbose_name = 'Maintenance Multiplexer'


# ─────────────────────────────────────────────────────────────────────
# DETAIL RECTIFIER & BATTERY
# ─────────────────────────────────────────────────────────────────────
class MaintenanceRectifier(models.Model):

    STATUS_CHECK  = (('OK','OK'),('NOK','NOK'),)
    EXHAUST_CHOICES = (
        ('Terpasang','Terpasang'),
        ('Tidak Terpasang','Tidak Terpasang'),
        ('Rusak','Rusak'),
    )
    KEBERSIHAN_CHOICES = (('Bersih','Bersih'),('Kotor','Kotor'),)
    LAMPU_CHOICES = (
        ('Menyala','Menyala'),
        ('Tidak Menyala','Tidak Menyala'),
        ('Redup','Redup'),
    )

    maintenance = models.OneToOneField(Maintenance, on_delete=models.CASCADE)

    # ── Kondisi Lingkungan ───────────────────────────────────────────
    suhu_ruangan      = models.FloatField(null=True, blank=True, verbose_name='Suhu Ruangan (°C)')
    exhaust_fan       = models.CharField(max_length=20, choices=EXHAUST_CHOICES, blank=True)
    kebersihan        = models.CharField(max_length=10, choices=KEBERSIHAN_CHOICES, blank=True)
    lampu_penerangan  = models.CharField(max_length=15, choices=LAMPU_CHOICES, blank=True)

    # ── Rectifier 1 ─────────────────────────────────────────────────
    rect1_merk           = models.CharField(max_length=100, blank=True)
    rect1_tipe           = models.CharField(max_length=100, blank=True)
    rect1_kondisi        = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    rect1_kapasitas      = models.CharField(max_length=50, blank=True)
    rect1_v_rectifier    = models.FloatField(null=True, blank=True, verbose_name='Rect1 V Rectifier (V)')
    rect1_v_battery      = models.FloatField(null=True, blank=True, verbose_name='Rect1 V Battery (V)')
    rect1_teg_pos_ground = models.FloatField(null=True, blank=True, verbose_name='Rect1 Teg(+) Ground (V)')
    rect1_teg_neg_ground = models.FloatField(null=True, blank=True, verbose_name='Rect1 Teg(-) Ground (V)')
    rect1_v_dropper      = models.FloatField(null=True, blank=True, verbose_name='Rect1 Dropper (V)')
    rect1_v_load         = models.FloatField(null=True, blank=True, verbose_name='Rect1 V Load (V)')
    rect1_a_rectifier    = models.FloatField(null=True, blank=True, verbose_name='Rect1 Arus Rectifier (A)')
    rect1_a_battery      = models.FloatField(null=True, blank=True, verbose_name='Rect1 Arus Battery (A)')
    rect1_a_load         = models.FloatField(null=True, blank=True, verbose_name='Rect1 Arus Load (A)')


    # ── Battery Bank 1 ──────────────────────────────────────────────
    bat1_merk              = models.CharField(max_length=100, blank=True)
    bat1_tipe              = models.CharField(max_length=100, blank=True)
    bat1_kondisi           = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    bat1_kapasitas         = models.CharField(max_length=50, blank=True)
    bat1_jumlah            = models.IntegerField(null=True, blank=True, verbose_name='Jumlah Cell Bank 1')
    bat1_kondisi_kabel     = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    bat1_kondisi_mur_baut  = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    bat1_kondisi_sel_rak   = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True)
    bat1_air_battery       = models.FloatField(null=True, blank=True, verbose_name='Air Battery Bank 1 (V)')
    bat1_v_total           = models.FloatField(null=True, blank=True, verbose_name='V Total Bank 1 (V)')
    bat1_v_load            = models.FloatField(null=True, blank=True, verbose_name='V Load Bank 1 (V)')
    # JSON: [{"cell":1,"v_float":2.13,"vd_0":null,"vd_half":null,"vd_1":null,"vd_2":null,"v_boost":null}, ...]
    bat1_cells             = models.JSONField(default=list, blank=True, verbose_name='Data Cell Bank 1')

    # ── Catatan ─────────────────────────────────────────────────────
    catatan = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Maintenance Rectifier & Battery'

# ─────────────────────────────────────────────────────────────
# CORRECTIVE MAINTENANCE (ringkas, terrelasi)
# ─────────────────────────────────────────────────────────────

def corrective_foto_upload(instance, filename):
    import os, re
    from django.utils import timezone
    ext  = os.path.splitext(filename)[1].lower() or '.jpg'
    nama = re.sub(r'[^\w]', '_', str(instance.maintenance.device.nama if instance.maintenance else 'DEV'))[:30]
    tgl  = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    return f'corrective_photos/{nama}_{tgl}{ext}'


class MaintenanceCorrective(models.Model):
    """
    Detail Corrective Maintenance — ringkas & terrelasi.
    FK ke Maintenance (type=Corrective) dan opsional ke Gangguan.
    """
    JENIS_KERUSAKAN = (
        ('hardware',   'Hardware / Fisik'),
        ('software',   'Software / Konfigurasi'),
        ('power',      'Power / Catu Daya'),
        ('komunikasi', 'Komunikasi / Jaringan'),
        ('mekanik',    'Mekanik / Konektor'),
        ('lainnya',    'Lainnya'),
    )

    STATUS_CHOICES = (
        ('selesai',          'Selesai'),
        ('perlu_tindaklanjut', 'Perlu Tindak Lanjut'),
    )

    maintenance         = models.OneToOneField(
        Maintenance, on_delete=models.CASCADE,
        related_name='corrective_detail'
    )
    gangguan            = models.ForeignKey(
        'gangguan.Gangguan',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='corrective_maintenances',
        verbose_name='Terkait Gangguan',
    )
    jenis_kerusakan     = models.CharField(
        max_length=20, choices=JENIS_KERUSAKAN,
        blank=True, verbose_name='Jenis Kerusakan'
    )
    deskripsi_masalah   = models.TextField(verbose_name='Deskripsi Masalah / Kerusakan')
    tindakan            = models.TextField(verbose_name='Tindakan yang Dilakukan')
    komponen_diganti    = models.BooleanField(default=False, verbose_name='Ada Komponen Diganti?')
    nama_komponen       = models.CharField(max_length=150, blank=True, verbose_name='Nama Komponen')
    komponen_terkait    = models.ForeignKey(
        'devices.DeviceComponent',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='corrective_maintenances',
        verbose_name='Komponen Terkait',
        help_text='Pilih komponen spesifik yang diperbaiki/diganti',
    )
    kondisi_sebelum     = models.CharField(max_length=200, blank=True, verbose_name='Kondisi Sebelum')
    kondisi_sesudah     = models.CharField(max_length=200, blank=True, verbose_name='Kondisi Sesudah')
    durasi_jam          = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Durasi (jam)')
    durasi_menit        = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Durasi (menit)')
    status_perbaikan    = models.CharField(
        max_length=25, choices=STATUS_CHOICES,
        default='selesai', verbose_name='Status Perbaikan'
    )
    foto_sebelum        = models.ImageField(
        upload_to=corrective_foto_upload, blank=True, null=True,
        verbose_name='Foto Sebelum'
    )
    foto_sesudah        = models.ImageField(
        upload_to=corrective_foto_upload, blank=True, null=True,
        verbose_name='Foto Sesudah'
    )

    class Meta:
        verbose_name        = 'Detail Corrective Maintenance'
        verbose_name_plural = 'Detail Corrective Maintenance'

    def __str__(self):
        return f'Corrective — {self.maintenance.device.nama}'

    @property
    def durasi_display(self):
        parts = []
        if self.durasi_jam:   parts.append(f'{self.durasi_jam}j')
        if self.durasi_menit: parts.append(f'{self.durasi_menit}m')
        return ' '.join(parts) if parts else '—'


# ─────────────────────────────────────────────────────────────────────
# DETAIL TELEPROTEKSI
# ─────────────────────────────────────────────────────────────────────
class MaintenanceTeleproteksi(models.Model):

    STATUS_CHECK = (('OK', 'OK'), ('NOK', 'NOK'),)

    TIPE_TP = (
        ('Digital', 'Digital'),
        ('Analog',  'Analog'),
    )

    PORT_COMM = (
        ('E1',  'E1'),
        ('G64', 'G64'),
        ('E&M', 'E&M'),
        ('PLC', 'PLC'),
    )

    SKEMA_COMMAND = (
        ('',               '— Pilih —'),
        ('Distance',       'Distance'),
        ('DEF',            'DEF'),
        ('DTT',            'DTT'),
        ('Tidak Terpakai', 'Tidak Terpakai'),
    )

    KEBERSIHAN = (
        ('Bersih', 'Bersih'),
        ('Kotor',  'Kotor'),
    )

    maintenance = models.OneToOneField(Maintenance, on_delete=models.CASCADE)

    # ── Informasi Umum ───────────────────────────────────────────────
    suhu_ruangan        = models.FloatField(null=True, blank=True, verbose_name='Suhu Ruangan (°C)')
    kebersihan_perangkat = models.CharField(max_length=10, choices=KEBERSIHAN, blank=True, verbose_name='Kebersihan Perangkat')
    kebersihan_panel    = models.CharField(max_length=10, choices=KEBERSIHAN, blank=True, verbose_name='Kebersihan Panel')
    lampu               = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Lampu')

    # ── Informasi Perangkat ──────────────────────────────────────────
    link            = models.CharField(max_length=200, blank=True, verbose_name='Link (terhubung ke)')
    tipe_tp         = models.CharField(max_length=10, choices=TIPE_TP, blank=True, verbose_name='Tipe Teleproteksi')
    versi_program   = models.CharField(max_length=100, blank=True, verbose_name='Versi Program')
    address_tp      = models.CharField(max_length=100, blank=True, verbose_name='Address TP (Digital)')
    port_comm       = models.CharField(max_length=10, choices=PORT_COMM, blank=True, verbose_name='Port Comm TP')
    akses_tp        = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Akses TP')
    remote_akses_tp = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Remote Akses TP')

    # ── Kondisi Peralatan ────────────────────────────────────────────
    jumlah_skema = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Jumlah Skema')

    # Skema 1
    skema_1_command          = models.CharField(max_length=20, choices=SKEMA_COMMAND, blank=True, verbose_name='Skema 1 Command')
    skema_1_send_minus       = models.FloatField(null=True, blank=True, verbose_name='Skema 1 Teg Standby Send (-) V')
    skema_1_send_plus        = models.FloatField(null=True, blank=True, verbose_name='Skema 1 Teg Standby Send (+) V')
    skema_1_receive_minus    = models.FloatField(null=True, blank=True, verbose_name='Skema 1 Teg Standby Receive (-) V')
    skema_1_receive_plus     = models.FloatField(null=True, blank=True, verbose_name='Skema 1 Teg Standby Receive (+) V')

    # Skema 2
    skema_2_command          = models.CharField(max_length=20, choices=SKEMA_COMMAND, blank=True, verbose_name='Skema 2 Command')
    skema_2_send_minus       = models.FloatField(null=True, blank=True, verbose_name='Skema 2 Teg Standby Send (-) V')
    skema_2_send_plus        = models.FloatField(null=True, blank=True, verbose_name='Skema 2 Teg Standby Send (+) V')
    skema_2_receive_minus    = models.FloatField(null=True, blank=True, verbose_name='Skema 2 Teg Standby Receive (-) V')
    skema_2_receive_plus     = models.FloatField(null=True, blank=True, verbose_name='Skema 2 Teg Standby Receive (+) V')

    # Skema 3
    skema_3_command          = models.CharField(max_length=20, choices=SKEMA_COMMAND, blank=True, verbose_name='Skema 3 Command')
    skema_3_send_minus       = models.FloatField(null=True, blank=True, verbose_name='Skema 3 Teg Standby Send (-) V')
    skema_3_send_plus        = models.FloatField(null=True, blank=True, verbose_name='Skema 3 Teg Standby Send (+) V')
    skema_3_receive_minus    = models.FloatField(null=True, blank=True, verbose_name='Skema 3 Teg Standby Receive (-) V')
    skema_3_receive_plus     = models.FloatField(null=True, blank=True, verbose_name='Skema 3 Teg Standby Receive (+) V')

    # Skema 4
    skema_4_command          = models.CharField(max_length=20, choices=SKEMA_COMMAND, blank=True, verbose_name='Skema 4 Command')
    skema_4_send_minus       = models.FloatField(null=True, blank=True, verbose_name='Skema 4 Teg Standby Send (-) V')
    skema_4_send_plus        = models.FloatField(null=True, blank=True, verbose_name='Skema 4 Teg Standby Send (+) V')
    skema_4_receive_minus    = models.FloatField(null=True, blank=True, verbose_name='Skema 4 Teg Standby Receive (-) V')
    skema_4_receive_plus     = models.FloatField(null=True, blank=True, verbose_name='Skema 4 Teg Standby Receive (+) V')

    # ── Pengujian per Skema ──────────────────────────────────────────
    skema_1_send_result     = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Pengujian Send Command 1')
    skema_1_receive_result  = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Pengujian Receive Command 1')
    skema_2_send_result     = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Pengujian Send Command 2')
    skema_2_receive_result  = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Pengujian Receive Command 2')
    skema_3_send_result     = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Pengujian Send Command 3')
    skema_3_receive_result  = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Pengujian Receive Command 3')
    skema_4_send_result     = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Pengujian Send Command 4')
    skema_4_receive_result  = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Pengujian Receive Command 4')

    # ── Pengujian Umum ───────────────────────────────────────────────
    time_sync   = models.CharField(max_length=3, choices=STATUS_CHECK, blank=True, verbose_name='Time Sync')
    loop_test   = models.FloatField(null=True, blank=True, verbose_name='Loop Test (ms)')

    # ── Catatan ──────────────────────────────────────────────────────
    catatan     = models.TextField(blank=True, verbose_name='Catatan')

    class Meta:
        verbose_name = 'Maintenance Teleproteksi'


# ─────────────────────────────────────────────────────────────────────
# DETAIL GENSET
# ─────────────────────────────────────────────────────────────────────
class MaintenanceGenset(models.Model):

    MCB_CHOICES = (('ON', 'ON'), ('OFF', 'OFF'),)

    maintenance = models.OneToOneField(Maintenance, on_delete=models.CASCADE)

    # ── Perangkat Pendukung: Batere ──────────────────────────────────
    air_accu            = models.FloatField(null=True, blank=True, verbose_name='Air Accu (mm)')
    tegangan_batere     = models.FloatField(null=True, blank=True, verbose_name='Tegangan Batere (VDC)')
    arus_pengisian      = models.FloatField(null=True, blank=True, verbose_name='Arus Pengisian (A)')

    # ── Perangkat Pendukung: Charger ─────────────────────────────────
    tegangan_charger    = models.FloatField(null=True, blank=True, verbose_name='Tegangan Charger (VDC)')
    arus_beban_charger  = models.FloatField(null=True, blank=True, verbose_name='Arus Beban Charger (A)')

    # ── Perangkat Utama Genset ───────────────────────────────────────
    radiator            = models.FloatField(null=True, blank=True, verbose_name='Radiator (°C)')
    kapasitas_tangki    = models.FloatField(null=True, blank=True, verbose_name='Kapasitas Tangki (liter)')
    tangki_bbm_sebelum  = models.FloatField(null=True, blank=True, verbose_name='Tangki BBM Sebelum (%)')
    tangki_bbm_sesudah  = models.FloatField(null=True, blank=True, verbose_name='Tangki BBM Sesudah (%)')
    mcb                 = models.CharField(max_length=3, choices=MCB_CHOICES, blank=True, verbose_name='MCB')
    pelumas             = models.CharField(max_length=100, blank=True, verbose_name='Pelumas')

    # ── Waktu Transisi ───────────────────────────────────────────────
    waktu_transisi      = models.FloatField(null=True, blank=True, verbose_name='Waktu Transisi (detik)')

    # ── Pengukuran Supply PLN ────────────────────────────────────────
    pln_f_r             = models.FloatField(null=True, blank=True, verbose_name='PLN Frekuensi R-N (Hz)')
    pln_f_s             = models.FloatField(null=True, blank=True, verbose_name='PLN Frekuensi S-N (Hz)')
    pln_f_t             = models.FloatField(null=True, blank=True, verbose_name='PLN Frekuensi T-N (Hz)')
    pln_v_rn            = models.FloatField(null=True, blank=True, verbose_name='PLN Teg 1Ph R-N (V)')
    pln_v_sn            = models.FloatField(null=True, blank=True, verbose_name='PLN Teg 1Ph S-N (V)')
    pln_v_tn            = models.FloatField(null=True, blank=True, verbose_name='PLN Teg 1Ph T-N (V)')
    pln_v_rs            = models.FloatField(null=True, blank=True, verbose_name='PLN Teg 3Ph R-S (V)')
    pln_v_st            = models.FloatField(null=True, blank=True, verbose_name='PLN Teg 3Ph S-T (V)')
    pln_v_tr            = models.FloatField(null=True, blank=True, verbose_name='PLN Teg 3Ph T-R (V)')
    pln_i_r             = models.FloatField(null=True, blank=True, verbose_name='PLN Arus R (A)')
    pln_i_s             = models.FloatField(null=True, blank=True, verbose_name='PLN Arus S (A)')
    pln_i_t             = models.FloatField(null=True, blank=True, verbose_name='PLN Arus T (A)')

    # ── Pengukuran Supply Genset ─────────────────────────────────────
    gen_f_r             = models.FloatField(null=True, blank=True, verbose_name='Genset Frekuensi R-N (Hz)')
    gen_f_s             = models.FloatField(null=True, blank=True, verbose_name='Genset Frekuensi S-N (Hz)')
    gen_f_t             = models.FloatField(null=True, blank=True, verbose_name='Genset Frekuensi T-N (Hz)')
    gen_v_rn            = models.FloatField(null=True, blank=True, verbose_name='Genset Teg 1Ph R-N (V)')
    gen_v_sn            = models.FloatField(null=True, blank=True, verbose_name='Genset Teg 1Ph S-N (V)')
    gen_v_tn            = models.FloatField(null=True, blank=True, verbose_name='Genset Teg 1Ph T-N (V)')
    gen_v_rs            = models.FloatField(null=True, blank=True, verbose_name='Genset Teg 3Ph R-S (V)')
    gen_v_st            = models.FloatField(null=True, blank=True, verbose_name='Genset Teg 3Ph S-T (V)')
    gen_v_tr            = models.FloatField(null=True, blank=True, verbose_name='Genset Teg 3Ph T-R (V)')
    gen_i_r             = models.FloatField(null=True, blank=True, verbose_name='Genset Arus R (A)')
    gen_i_s             = models.FloatField(null=True, blank=True, verbose_name='Genset Arus S (A)')
    gen_i_t             = models.FloatField(null=True, blank=True, verbose_name='Genset Arus T (A)')

    # ── MDF Cubicle ──────────────────────────────────────────────────
    oil_pressure        = models.FloatField(null=True, blank=True, verbose_name='Oil Pressure (Kpa)')
    engine_temperature  = models.FloatField(null=True, blank=True, verbose_name='Engine Temperature (°C)')
    batere_condition    = models.FloatField(null=True, blank=True, verbose_name='Batere Condition (VDC)')
    rpm                 = models.FloatField(null=True, blank=True, verbose_name='RPM')

    # ── Counter Analog ───────────────────────────────────────────────
    counter_sebelum     = models.FloatField(null=True, blank=True, verbose_name='Counter Sebelum (jam)')
    counter_sesudah     = models.FloatField(null=True, blank=True, verbose_name='Counter Sesudah (jam)')

    # ── Jam Operasi ──────────────────────────────────────────────────
    waktu_start         = models.TimeField(null=True, blank=True, verbose_name='Waktu Start')
    waktu_stop          = models.TimeField(null=True, blank=True, verbose_name='Waktu Stop')

    # ── Catatan ──────────────────────────────────────────────────────
    catatan             = models.TextField(blank=True, verbose_name='Catatan')

    class Meta:
        verbose_name = 'Maintenance Genset'

    @property
    def durasi_menit(self):
        if self.waktu_start and self.waktu_stop:
            from datetime import datetime, date, timedelta
            start = datetime.combine(date.today(), self.waktu_start)
            stop  = datetime.combine(date.today(), self.waktu_stop)
            if stop < start:
                stop += timedelta(days=1)
            return int((stop - start).total_seconds() / 60)
        return None

    @property
    def bbm_terpakai(self):
        """Selisih % BBM (sebelum - sesudah)."""
        if self.tangki_bbm_sebelum is not None and self.tangki_bbm_sesudah is not None:
            return round(self.tangki_bbm_sebelum - self.tangki_bbm_sesudah, 1)
        return None

    @property
    def persen_bbm_sesudah(self):
        """Nilai % BBM sesudah (langsung dari field)."""
        return self.tangki_bbm_sesudah

    @property
    def selisih_counter(self):
        if self.counter_sebelum is not None and self.counter_sesudah is not None:
            return round(self.counter_sesudah - self.counter_sebelum, 2)
        return None


# ─────────────────────────────────────────────────────────────
# DETAIL RTU (model AK3)
# ─────────────────────────────────────────────────────────────
class MaintenanceRTU(models.Model):
    """
    Detail pemeliharaan RTU AK3.
    Indikasi per modul disimpan sebagai JSONField:
      { "RY": {"sb": true, "sd": true}, "ER": {"sb": false, "sd": true}, ... }
    sb = sebelum, sd = sesudah
    """

    maintenance = models.OneToOneField(
        Maintenance, on_delete=models.CASCADE,
        related_name='maintenancertu'
    )

    # ── RTU: CP-2016 ─────────────────────────────────────────────────
    cp2016_jumlah = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Jumlah CP-2016')
    cp2016_data   = models.JSONField(default=dict, blank=True, verbose_name='Indikasi CP-2016')

    # ── RTU: CP-2019 ─────────────────────────────────────────────────
    cp2019_jumlah = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Jumlah CP-2019')
    cp2019_data   = models.JSONField(default=dict, blank=True, verbose_name='Indikasi CP-2019')

    # ── RTU: DI-2112/2113 ────────────────────────────────────────────
    di2112_jumlah = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Jumlah DI-2112/2113')
    di2112_data   = models.JSONField(default=dict, blank=True, verbose_name='Indikasi DI-2112/2113')

    # ── RTU: DO-2210/2211 ────────────────────────────────────────────
    do2210_jumlah = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Jumlah DO-2210/2211')
    do2210_data   = models.JSONField(default=dict, blank=True, verbose_name='Indikasi DO-2210/2211')

    # ── RTU: AI-2300 ─────────────────────────────────────────────────
    ai2300_data   = models.JSONField(default=dict, blank=True, verbose_name='Indikasi AI-2300')

    # ── IED ──────────────────────────────────────────────────────────
    ied_data      = models.JSONField(default=dict, blank=True, verbose_name='Indikasi IED')

    # ── Power Supply 48 VDC ──────────────────────────────────────────
    ps48_teg_beban   = models.FloatField(null=True, blank=True, verbose_name='48V Tegangan Beban (V)')
    ps48_arus_beban  = models.FloatField(null=True, blank=True, verbose_name='48V Arus Beban (A)')
    ps48_teg_supply  = models.FloatField(null=True, blank=True, verbose_name='48V Tegangan Supply (V)')
    ps48_arus_supply = models.FloatField(null=True, blank=True, verbose_name='48V Arus Supply (A)')

    # ── Power Supply 110 VDC ─────────────────────────────────────────
    ps110_teg_beban   = models.FloatField(null=True, blank=True, verbose_name='110V Tegangan Beban (V)')
    ps110_arus_beban  = models.FloatField(null=True, blank=True, verbose_name='110V Arus Beban (A)')
    ps110_teg_supply  = models.FloatField(null=True, blank=True, verbose_name='110V Tegangan Supply (V)')
    ps110_arus_supply = models.FloatField(null=True, blank=True, verbose_name='110V Arus Supply (A)')

    class Meta:
        verbose_name = 'Maintenance RTU'


# ─────────────────────────────────────────────────────────────
# DETAIL SAS (SERVER / GATEWAY SAS)
# ─────────────────────────────────────────────────────────────
class MaintenanceSAS(models.Model):

    BERSIH_CHOICES = (('BERSIH', 'Bersih'), ('TIDAK BERSIH', 'Tidak Bersih'),)
    OK_ALARM       = (('OK', 'OK'), ('ALARM', 'Alarm'),)
    ADA_CHOICES    = (('ADA', 'Ada'), ('TIDAK ADA', 'Tidak Ada'),)
    OK_NOK         = (('OK', 'OK'), ('NOK', 'NOK'),)
    FAN_CHOICES    = (
        ('ADA, BERFUNGSI',     'Ada, Berfungsi'),
        ('ADA, TIDAK BERFUNGSI', 'Ada, Tidak Berfungsi'),
        ('TIDAK ADA',          'Tidak Ada'),
    )

    maintenance = models.OneToOneField(
        Maintenance, on_delete=models.CASCADE,
        related_name='maintenancesas'
    )

    # ── Spesifikasi ──────────────────────────────────────────
    spek_merk           = models.CharField(max_length=100, blank=True, default='', verbose_name='Merk')
    spek_type           = models.CharField(max_length=100, blank=True, default='', verbose_name='Type')
    spek_cpu            = models.CharField(max_length=100, blank=True, default='', verbose_name='CPU')
    spek_ram            = models.CharField(max_length=100, blank=True, default='', verbose_name='RAM')
    spek_gpu            = models.CharField(max_length=100, blank=True, default='', verbose_name='GPU')
    spek_storage        = models.CharField(max_length=100, blank=True, default='', verbose_name='Storage Memory')
    spek_firmware       = models.CharField(max_length=100, blank=True, default='', verbose_name='Firmware Version')
    spek_config_ver     = models.CharField(max_length=100, blank=True, default='', verbose_name='Configuration Version')
    spek_ip             = models.CharField(max_length=50,  blank=True, default='', verbose_name='Maintenance IP')
    modul_io            = models.TextField(blank=True, default='', verbose_name='Modul I/O / Card / Terminal Terpasang')

    # ── Kondisi Peralatan ────────────────────────────────────
    kondisi_server      = models.CharField(max_length=20, blank=True, default='', choices=BERSIH_CHOICES, verbose_name='Kondisi Server/Gateway')
    kondisi_panel       = models.CharField(max_length=20, blank=True, default='', choices=BERSIH_CHOICES, verbose_name='Kondisi Panel')
    temp_ruangan        = models.FloatField(null=True, blank=True, verbose_name='Temperatur Ruangan (°C)')
    temp_peralatan      = models.FloatField(null=True, blank=True, verbose_name='Temperatur Peralatan (°C)')
    exhaust_fan         = models.CharField(max_length=30, blank=True, default='', choices=FAN_CHOICES, verbose_name='Exhaust Fan')

    # ── Peripheral Pendukung ─────────────────────────────────
    peri_eth_switch     = models.CharField(max_length=10, blank=True, default='', choices=OK_ALARM, verbose_name='Ethernet Switch')
    peri_gps            = models.CharField(max_length=10, blank=True, default='', choices=OK_ALARM, verbose_name='GPS')
    peri_eth_serial     = models.CharField(max_length=10, blank=True, default='', choices=OK_ALARM, verbose_name='Ethernet to Serial')
    peri_router         = models.CharField(max_length=10, blank=True, default='', choices=OK_ALARM, verbose_name='Router')
    jumlah_bay          = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Jumlah Bay')
    peri_keterangan     = models.TextField(blank=True, default='', verbose_name='Keterangan Peripheral')

    # ── Performa Peralatan ───────────────────────────────────
    perf_cpu            = models.CharField(max_length=20, blank=True, default='', verbose_name='CPU Terpakai')
    perf_ram            = models.CharField(max_length=20, blank=True, default='', verbose_name='RAM Terpakai')
    perf_storage        = models.CharField(max_length=20, blank=True, default='', verbose_name='Storage Terpakai')
    indikasi_alarm      = models.CharField(max_length=15, blank=True, default='', choices=ADA_CHOICES, verbose_name='Indikasi Alarm/Error')
    komm_master         = models.CharField(max_length=10, blank=True, default='', choices=OK_ALARM, verbose_name='Komunikasi ke Master Station')
    komm_ied            = models.CharField(max_length=10, blank=True, default='', choices=OK_ALARM, verbose_name='Komunikasi ke IED')
    time_sync           = models.CharField(max_length=10, blank=True, default='', choices=OK_NOK,   verbose_name='Time Synchronization')

    # ── Power Supply — Inverter ──────────────────────────────
    inv_kondisi         = models.CharField(max_length=10, blank=True, default='', choices=OK_ALARM, verbose_name='Inverter Kondisi')
    inv_teg_input       = models.FloatField(null=True, blank=True, verbose_name='Inverter Tegangan Input (V)')
    inv_arus_input      = models.FloatField(null=True, blank=True, verbose_name='Inverter Arus Input (A)')
    inv_teg_output      = models.FloatField(null=True, blank=True, verbose_name='Inverter Tegangan Output (V)')
    inv_arus_output     = models.FloatField(null=True, blank=True, verbose_name='Inverter Arus Output (A)')

    # ── Power Supply — 110 VDC / 48 VDC ─────────────────────
    ps_teg_input        = models.FloatField(null=True, blank=True, verbose_name='PS Tegangan Input (V)')
    ps_arus_input       = models.FloatField(null=True, blank=True, verbose_name='PS Arus Input (A)')
    ps_teg_output       = models.FloatField(null=True, blank=True, verbose_name='PS Tegangan Output (V)')
    ps_arus_output      = models.FloatField(null=True, blank=True, verbose_name='PS Arus Output (A)')

    class Meta:
        verbose_name = 'Maintenance SAS'


# ─────────────────────────────────────────────────────────────
# DETAIL RoIP (Radio over IP)
# ─────────────────────────────────────────────────────────────
class MaintenanceRoIP(models.Model):

    STATUS_CHECK = (('OK', 'OK'), ('NOK', 'NOK'),)

    maintenance = models.OneToOneField(
        Maintenance, on_delete=models.CASCADE,
        related_name='maintenanceroip'
    )

    # ── Kondisi Peralatan ────────────────────────────────────
    kondisi_fisik   = models.CharField(max_length=3, blank=True, choices=STATUS_CHECK, verbose_name='Kondisi Fisik Perangkat')
    ntp_server      = models.CharField(max_length=3, blank=True, choices=STATUS_CHECK, verbose_name='NTP Server')
    power_supply    = models.CharField(max_length=3, blank=True, choices=STATUS_CHECK, verbose_name='Power Supply')
    memory_usage    = models.FloatField(null=True, blank=True, verbose_name='Memory Usage (%)')

    # ── Konfig Peralatan ─────────────────────────────────────
    tx_volume_offset          = models.FloatField(null=True, blank=True, verbose_name='TX Volume Offset to Transceiver (dB)')
    rx_volume_offset          = models.FloatField(null=True, blank=True, verbose_name='RX Volume Offset from Transceiver (dB)')
    bridge_conn_source        = models.CharField(max_length=100, blank=True, verbose_name='Bridge Connection Source')
    bridge_conn_destination   = models.CharField(max_length=100, blank=True, verbose_name='Bridge Connection Destination')
    dest_port_number          = models.CharField(max_length=20, blank=True, verbose_name='Destination Port Number')
    source_port_number        = models.CharField(max_length=20, blank=True, verbose_name='Source Port Number')

    # ── PTT Control Setting ───────────────────────────────────
    ptt_attack_time   = models.FloatField(null=True, blank=True, verbose_name='PTT Attack Time (ms)')
    ptt_release_time  = models.FloatField(null=True, blank=True, verbose_name='PTT Release Time (ms)')
    ptt_voice_delay   = models.FloatField(null=True, blank=True, verbose_name='PTT Voice Delay (ms)')
    ptt_vox_threshold = models.FloatField(null=True, blank=True, verbose_name='PTT VOX Threshold (%)')

    # ── Receive Detection Setting ─────────────────────────────
    rx_attack_time   = models.FloatField(null=True, blank=True, verbose_name='RX Attack Time (ms)')
    rx_release_time  = models.FloatField(null=True, blank=True, verbose_name='RX Release Time (ms)')
    rx_voice_delay   = models.FloatField(null=True, blank=True, verbose_name='RX Voice Delay (ms)')
    rx_vox_threshold = models.FloatField(null=True, blank=True, verbose_name='RX VOX Threshold (%)')

    # ── Pengujian ─────────────────────────────────────────────
    test_radio_master = models.CharField(max_length=3, blank=True, choices=STATUS_CHECK, verbose_name='Test Fungsi Radio ke RoIP Master')
    test_ping_master  = models.FloatField(null=True, blank=True, verbose_name='Test Ping ke RoIP Master (ms)')

    catatan = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Maintenance RoIP'
