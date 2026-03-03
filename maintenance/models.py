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
    technician      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
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
