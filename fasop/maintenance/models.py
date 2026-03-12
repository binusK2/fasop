from django.db import models
from devices.models import Device
from django.contrib.auth.models import User


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
    date            = models.DateField()
    description     = models.TextField(blank=True)
    technicians     = models.ManyToManyField(User, blank=True, related_name='maintenance_technician_set', verbose_name='Pelaksana')
    signed_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='signed_maintenances', verbose_name='Ditandatangani oleh')
    signed_at       = models.DateTimeField(null=True, blank=True, verbose_name='Waktu TTD')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    photo           = models.ImageField(upload_to='maintenance_photos/', blank=True, null=True)
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

    SWR_CHOICES = (
        ('<1.5', '< 1,5 (Baik)'),
        ('>1.5', '> 1,5 (Buruk)'),
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
    swr                 = models.CharField(max_length=5, choices=SWR_CHOICES, blank=True, verbose_name='SWR')
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
