# devices/models_komponen.py
# ============================================================
# Model Komponen Perangkat & Spesifikasi per Tipe
# ============================================================

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class GrupTipeKomponen(models.Model):
    """Grup/kategori untuk mengelompokkan tipe komponen di dropdown."""
    nama = models.CharField(max_length=50, unique=True, verbose_name='Nama Grup')
    urutan = models.PositiveSmallIntegerField(default=0, verbose_name='Urutan Tampil')

    class Meta:
        verbose_name = 'Grup Tipe Komponen'
        verbose_name_plural = 'Grup Tipe Komponen'
        ordering = ['urutan', 'nama']

    def __str__(self):
        return self.nama


class TipeKomponen(models.Model):
    """
    Tipe komponen yang bisa dikelola via Admin.
    Contoh: PSU, SFP, Modul CPU, Battery Bank, dll.
    """
    kode = models.CharField(
        max_length=30, unique=True, verbose_name='Kode',
        help_text='Kode pendek unik, e.g. psu, sfp, modul_cpu',
    )
    nama = models.CharField(max_length=100, verbose_name='Nama Tipe')
    grup = models.ForeignKey(
        GrupTipeKomponen, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tipe_komponen',
        verbose_name='Grup',
    )
    urutan = models.PositiveSmallIntegerField(default=0, verbose_name='Urutan Tampil')

    class Meta:
        verbose_name = 'Tipe Komponen'
        verbose_name_plural = 'Tipe Komponen'
        ordering = ['grup__urutan', 'urutan', 'nama']

    def __str__(self):
        return self.nama


class DeviceComponent(models.Model):
    """
    Komponen fisik yang terpasang di sebuah Device.
    """

    STATUS_CHOICES = (
        ('terpasang',    'Terpasang & Normal'),
        ('rusak',        'Rusak'),
        ('diganti',      'Sudah Diganti'),
        ('tidak_ada',    'Tidak Terpasang'),
    )

    device = models.ForeignKey(
        'Device', on_delete=models.CASCADE,
        related_name='komponen', verbose_name='Perangkat Induk',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='sub_komponen',
        verbose_name='Komponen Induk',
        help_text='Kosongkan jika ini komponen level atas',
    )

    nama = models.CharField(max_length=150, verbose_name='Nama Komponen',
                            help_text='Contoh: CPU 1, Slot A, PSU 1')
    tipe_komponen = models.ForeignKey(
        TipeKomponen, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='komponen',
        verbose_name='Tipe Komponen',
    )
    posisi = models.CharField(max_length=50, blank=True, verbose_name='Posisi / Slot',
                              help_text='Contoh: Slot A, Bay 1, Port 3')
    merk = models.CharField(max_length=100, blank=True, verbose_name='Merk')
    model = models.CharField(max_length=100, blank=True, verbose_name='Model / Tipe')
    serial_number = models.CharField(max_length=100, blank=True, verbose_name='Serial Number')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='terpasang', verbose_name='Status')
    keterangan = models.TextField(blank=True, verbose_name='Keterangan')

    tanggal_pasang = models.DateField(null=True, blank=True, verbose_name='Tanggal Pemasangan')
    tanggal_ganti = models.DateField(null=True, blank=True, verbose_name='Tanggal Penggantian Terakhir')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, blank=True, verbose_name='Ditambahkan oleh')

    class Meta:
        verbose_name = 'Komponen Perangkat'
        verbose_name_plural = 'Komponen Perangkat'
        ordering = ['device', 'posisi', 'nama']

    def __str__(self):
        pos = f" [{self.posisi}]" if self.posisi else ""
        return f"{self.nama}{pos} — {self.device.nama}"

    @property
    def status_color(self):
        return {
            'terpasang': '#10b981', 'rusak': '#ef4444',
            'diganti': '#f59e0b', 'tidak_ada': '#94a3b8',
        }.get(self.status, '#94a3b8')

    @property
    def tipe_display(self):
        """Nama tipe komponen untuk tampilan."""
        return self.tipe_komponen.nama if self.tipe_komponen else '—'

    @property
    def spec(self):
        """Ambil spesifikasi detail (Spec model) yang terhubung."""
        for attr in [
            'spec_sfp', 'spec_mux_slot', 'spec_rectifier_modul',
            'spec_battery', 'spec_battery_cell',
            'spec_psu', 'spec_radio_modul', 'spec_plc_modul',
        ]:
            try:
                return getattr(self, attr)
            except Exception:
                continue
        return None


# ============================================================
# HELPER display_fields
# ============================================================
def _build_display(instance, field_map):
    """
    field_map = [ ('field_name', 'Label', 'suffix'), ... ]
    Return [{'label': ..., 'value': ...}, ...]
    """
    fields = []
    for field_name, label, suffix in field_map:
        val = getattr(instance, field_name, None)
        if val is None or val == '':
            continue
        # Choice fields → gunakan get_FOO_display()
        display_fn = getattr(instance, f'get_{field_name}_display', None)
        if display_fn:
            try:
                model_field = instance.__class__._meta.get_field(field_name)
                if model_field.choices:
                    val = display_fn()
            except Exception:
                pass
        if isinstance(val, float):
            val = f"{val:g}"
        if suffix:
            val = f"{val} {suffix}"
        fields.append({'label': label, 'value': str(val)})
    return fields


# ============================================================
# SPESIFIKASI PER TIPE KOMPONEN
# ============================================================

class SpecRouterPort(models.Model):
    """Spesifikasi SFP/Port pada Router/Switch."""
    komponen = models.OneToOneField(DeviceComponent, on_delete=models.CASCADE,
                                    related_name='spec_sfp')

    SPEED_CHOICES = (
        ('100M', '100 Mbps'), ('1G', '1 Gbps'), ('10G', '10 Gbps'),
        ('25G', '25 Gbps'), ('40G', '40 Gbps'),
    )
    kecepatan = models.CharField(max_length=10, choices=SPEED_CHOICES, blank=True,
                                 verbose_name='Kecepatan')
    wavelength = models.CharField(max_length=30, blank=True, verbose_name='Wavelength (nm)')
    tx_power = models.FloatField(null=True, blank=True, verbose_name='TX Power (dBm)')
    rx_power = models.FloatField(null=True, blank=True, verbose_name='RX Power (dBm)')
    jarak_max = models.CharField(max_length=30, blank=True, verbose_name='Jarak Max')
    tipe_konektor = models.CharField(max_length=30, blank=True, verbose_name='Tipe Konektor')

    class Meta:
        verbose_name = 'Spec SFP / Port'

    def __str__(self):
        return f"Spec SFP: {self.komponen.nama}"

    @property
    def display_fields(self):
        return _build_display(self, [
            ('kecepatan', 'Kecepatan', ''), ('wavelength', 'Wavelength', 'nm'),
            ('tx_power', 'TX Power', 'dBm'), ('rx_power', 'RX Power', 'dBm'),
            ('jarak_max', 'Jarak Max', ''), ('tipe_konektor', 'Konektor', ''),
        ])


class SpecMuxSlot(models.Model):
    """Spesifikasi modul slot pada Multiplexer."""
    komponen = models.OneToOneField(DeviceComponent, on_delete=models.CASCADE,
                                    related_name='spec_mux_slot')

    TIPE_MODUL_CHOICES = (
        ('-', 'Kosong'), ('E1Q', 'E1Q'), ('16E1Q', '16E1Q'),
        ('V.35', 'V.35'), ('6V.35', '6V.35'), ('SWITCH', 'SWITCH'),
        ('G.64', 'G.64'), ('E&M', 'E&M'), ('HDSL', 'HDSL'),
    )
    tipe_modul = models.CharField(max_length=20, choices=TIPE_MODUL_CHOICES,
                                  default='-', verbose_name='Tipe Modul')
    firmware = models.CharField(max_length=50, blank=True, verbose_name='Firmware Version')
    isian = models.TextField(blank=True, verbose_name='Isian / Konfigurasi')

    class Meta:
        verbose_name = 'Spec Slot Multiplexer'

    def __str__(self):
        return f"Spec Slot: {self.komponen.nama} ({self.tipe_modul})"

    @property
    def display_fields(self):
        return _build_display(self, [
            ('tipe_modul', 'Tipe Modul', ''), ('firmware', 'Firmware', ''),
            ('isian', 'Isian', ''),
        ])


class SpecPSU(models.Model):
    """Spesifikasi Power Supply Unit."""
    komponen = models.OneToOneField(DeviceComponent, on_delete=models.CASCADE,
                                    related_name='spec_psu')

    tegangan_input = models.CharField(max_length=30, blank=True, verbose_name='Tegangan Input')
    tegangan_output = models.CharField(max_length=30, blank=True, verbose_name='Tegangan Output')
    kapasitas_watt = models.FloatField(null=True, blank=True, verbose_name='Kapasitas (Watt)')
    redundan = models.BooleanField(default=False, verbose_name='Redundan?')

    class Meta:
        verbose_name = 'Spec PSU'

    def __str__(self):
        return f"Spec PSU: {self.komponen.nama}"

    @property
    def display_fields(self):
        fields = _build_display(self, [
            ('tegangan_input', 'Teg. Input', ''), ('tegangan_output', 'Teg. Output', ''),
            ('kapasitas_watt', 'Kapasitas', 'W'),
        ])
        if self.redundan:
            fields.append({'label': 'Redundan', 'value': 'Ya'})
        return fields


class SpecRectifierModul(models.Model):
    """Spesifikasi Modul Rectifier."""
    komponen = models.OneToOneField(DeviceComponent, on_delete=models.CASCADE,
                                    related_name='spec_rectifier_modul')

    kapasitas_ampere = models.FloatField(null=True, blank=True, verbose_name='Kapasitas (A)')
    tegangan_output = models.CharField(max_length=30, blank=True, verbose_name='Tegangan Output')
    efisiensi = models.FloatField(null=True, blank=True, verbose_name='Efisiensi (%)')

    class Meta:
        verbose_name = 'Spec Modul Rectifier'

    def __str__(self):
        return f"Spec Rect: {self.komponen.nama}"

    @property
    def display_fields(self):
        return _build_display(self, [
            ('kapasitas_ampere', 'Kapasitas', 'A'),
            ('tegangan_output', 'Teg. Output', ''),
            ('efisiensi', 'Efisiensi', '%'),
        ])


class SpecBattery(models.Model):
    """Spesifikasi Battery Bank."""
    komponen = models.OneToOneField(DeviceComponent, on_delete=models.CASCADE,
                                    related_name='spec_battery')

    TIPE_CHOICES = (
        ('vrla', 'VRLA / AGM'), ('gel', 'Gel'),
        ('lithium', 'Lithium-Ion'), ('wet', 'Wet Cell'),
    )
    tipe_baterai = models.CharField(max_length=20, choices=TIPE_CHOICES, blank=True)
    kapasitas_ah = models.FloatField(null=True, blank=True, verbose_name='Kapasitas (Ah)')
    tegangan_nominal = models.FloatField(null=True, blank=True, verbose_name='Tegangan Nominal (V)')
    jumlah_cell = models.IntegerField(null=True, blank=True, verbose_name='Jumlah Cell')
    tanggal_pasang_baterai = models.DateField(null=True, blank=True, verbose_name='Tgl Pasang Baterai')
    umur_desain_tahun = models.IntegerField(null=True, blank=True, verbose_name='Umur Desain (tahun)')

    class Meta:
        verbose_name = 'Spec Battery'

    def __str__(self):
        return f"Spec Bat: {self.komponen.nama}"

    @property
    def display_fields(self):
        fields = _build_display(self, [
            ('tipe_baterai', 'Tipe', ''), ('kapasitas_ah', 'Kapasitas', 'Ah'),
            ('tegangan_nominal', 'Teg. Nominal', 'V'), ('jumlah_cell', 'Jumlah Cell', ''),
            ('umur_desain_tahun', 'Umur Desain', 'tahun'),
        ])
        if self.tanggal_pasang_baterai:
            fields.append({'label': 'Tgl Pasang', 'value': self.tanggal_pasang_baterai.strftime('%d %b %Y')})
        return fields


class SpecBatteryCell(models.Model):
    """Spesifikasi individual Battery Cell."""
    komponen = models.OneToOneField(DeviceComponent, on_delete=models.CASCADE,
                                    related_name='spec_battery_cell')

    nomor_cell = models.IntegerField(verbose_name='Nomor Cell')
    tegangan_float = models.FloatField(null=True, blank=True, verbose_name='V Float')
    tegangan_boost = models.FloatField(null=True, blank=True, verbose_name='V Boost')
    internal_resistance = models.FloatField(null=True, blank=True, verbose_name='Internal Resistance (mOhm)')

    class Meta:
        verbose_name = 'Spec Battery Cell'
        ordering = ['nomor_cell']

    def __str__(self):
        return f"Cell #{self.nomor_cell} — {self.komponen.nama}"

    @property
    def display_fields(self):
        return _build_display(self, [
            ('nomor_cell', 'Cell #', ''), ('tegangan_float', 'V Float', 'V'),
            ('tegangan_boost', 'V Boost', 'V'), ('internal_resistance', 'Int. Res.', 'mOhm'),
        ])


class SpecRadioModul(models.Model):
    """Spesifikasi Modul Radio TX/RX."""
    komponen = models.OneToOneField(DeviceComponent, on_delete=models.CASCADE,
                                    related_name='spec_radio_modul')

    frekuensi_tx = models.CharField(max_length=30, blank=True, verbose_name='Frekuensi TX')
    frekuensi_rx = models.CharField(max_length=30, blank=True, verbose_name='Frekuensi RX')
    tx_power_watt = models.FloatField(null=True, blank=True, verbose_name='TX Power (W)')
    tipe_modulasi = models.CharField(max_length=30, blank=True, verbose_name='Tipe Modulasi')

    class Meta:
        verbose_name = 'Spec Radio Modul'

    def __str__(self):
        return f"Spec Radio: {self.komponen.nama}"

    @property
    def display_fields(self):
        return _build_display(self, [
            ('frekuensi_tx', 'Freq TX', ''), ('frekuensi_rx', 'Freq RX', ''),
            ('tx_power_watt', 'TX Power', 'W'), ('tipe_modulasi', 'Modulasi', ''),
        ])


class SpecPLCModul(models.Model):
    """Spesifikasi Modul PLC (Power Line Carrier)."""
    komponen = models.OneToOneField(DeviceComponent, on_delete=models.CASCADE,
                                    related_name='spec_plc_modul')

    freq_tx = models.FloatField(null=True, blank=True, verbose_name='Frekuensi TX (kHz)')
    bandwidth_tx = models.FloatField(null=True, blank=True, verbose_name='Bandwidth TX (kHz)')
    freq_rx = models.FloatField(null=True, blank=True, verbose_name='Frekuensi RX (kHz)')
    bandwidth_rx = models.FloatField(null=True, blank=True, verbose_name='Bandwidth RX (kHz)')
    tx_level = models.FloatField(null=True, blank=True, verbose_name='TX Level (dBm)')

    class Meta:
        verbose_name = 'Spec PLC Modul'

    def __str__(self):
        return f"Spec PLC: {self.komponen.nama}"

    @property
    def display_fields(self):
        return _build_display(self, [
            ('freq_tx', 'Freq TX', 'kHz'), ('bandwidth_tx', 'BW TX', 'kHz'),
            ('freq_rx', 'Freq RX', 'kHz'), ('bandwidth_rx', 'BW RX', 'kHz'),
            ('tx_level', 'TX Level', 'dBm'),
        ])
