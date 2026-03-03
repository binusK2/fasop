from django import forms
from .models import Maintenance, MaintenancePLC, MaintenanceRouter, MaintenanceRadio


# ─── Widget helpers ───────────────────────────────────────────────────
OK_NOK_WIDGET = forms.RadioSelect(attrs={'class': 'd-flex gap-3'})
NUM_WIDGET    = lambda: forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'})
INT_WIDGET    = lambda: forms.NumberInput(attrs={'class': 'form-control'})
TEXT_WIDGET   = lambda rows=3: forms.Textarea(attrs={'class': 'form-control', 'rows': rows})


# ─────────────────────────────────────────────────────────────────────
# FORM MAINTENANCE UTAMA (sama untuk semua jenis)
# ─────────────────────────────────────────────────────────────────────
class MaintenanceForm(forms.ModelForm):

    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        input_formats=['%Y-%m-%d']
    )

    class Meta:
        model  = Maintenance
        fields = '__all__'
        exclude = ['device', 'created_at']
        widgets = {
            'maintenance_type': forms.Select(attrs={'class': 'form-select'}),
            'description':      forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'technician':       forms.Select(attrs={'class': 'form-select'}),
            'status':           forms.Select(attrs={'class': 'form-select'}),
            'photo':            forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, (forms.RadioSelect, forms.DateInput)):
                if not field.widget.attrs.get('class'):
                    field.widget.attrs['class'] = 'form-control'


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL PLC (sudah ada sebelumnya)
# ─────────────────────────────────────────────────────────────────────
class MaintenancePLCForm(forms.ModelForm):

    class Meta:
        model   = MaintenancePLC
        exclude = ['maintenance']
        widgets = {
            'akses_plc':        OK_NOK_WIDGET,
            'remote_akses_plc': OK_NOK_WIDGET,
            'time_sync':        OK_NOK_WIDGET,
            'wave_trap':        OK_NOK_WIDGET,
            'imu':              OK_NOK_WIDGET,
            'kabel_coaxial':    OK_NOK_WIDGET,
            'transmission_line': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -32.5'}),
            'rx_pilot_level':    forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -28.0'}),
            'freq_tx':           forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 72.5'}),
            'bandwidth_tx':      forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 4.0'}),
            'freq_rx':           forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 80.0'}),
            'bandwidth_rx':      forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 4.0'}),
        }


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL ROUTER / SWITCH  ← BARU
# ─────────────────────────────────────────────────────────────────────
class MaintenanceRouterForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceRouter
        exclude = ['maintenance']
        widgets = {
            # Fisik
            'kondisi_fisik':  OK_NOK_WIDGET,
            'led_link':       OK_NOK_WIDGET,
            'kondisi_kabel':  OK_NOK_WIDGET,

            # Pengukuran
            'tegangan_input': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 220.5'}),
            'suhu_perangkat': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 45.0'}),
            'cpu_load':       forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': '0–100'}),
            'memory_usage':   forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': '0–100'}),

            # Port
            'jumlah_port_aktif':  forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'jumlah_port_total':  forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'status_routing':     OK_NOK_WIDGET,
            'detail_port':        forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                                        'placeholder': 'Contoh: ether1 UP, ether2 DOWN, sfp1 UP ...'}),

            # SFP Port
            'jumlah_sfp_port': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '48', 'id': 'id_jumlah_sfp_port'}),
            'sfp_port_data':   forms.HiddenInput(attrs={'id': 'id_sfp_port_data'}),

            # Catatan
            'catatan_tambahan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# ─────────────────────────────────────────────────────────────
# FORM DETAIL RADIO KOMUNIKASI
# ─────────────────────────────────────────────────────────────
class MaintenanceRadioForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceRadio
        exclude = ['maintenance']
        widgets = {
            # Kondisi ruangan
            'suhu_ruangan': forms.NumberInput(attrs={
                'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 28.5'
            }),
            'kebersihan': forms.Select(attrs={'class': 'form-select'}),
            'lampu_penerangan': forms.Select(attrs={'class': 'form-select'}),

            # Peralatan terpasang
            'ada_radio':        OK_NOK_WIDGET,
            'ada_battery':      OK_NOK_WIDGET,
            'merk_battery': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. Yuasa, GS, Panasonic'
            }),
            'ada_power_supply': OK_NOK_WIDGET,
            'merk_power_supply': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. Huawei, Eltek, Delta'
            }),
            'jenis_antena': forms.Select(attrs={'class': 'form-select'}),

            # Pengukuran
            'swr': forms.Select(attrs={'class': 'form-select'}),
            'power_tx': forms.NumberInput(attrs={
                'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 5.0'
            }),
            'tegangan_battery': forms.NumberInput(attrs={
                'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 12.5'
            }),
            'tegangan_psu': forms.NumberInput(attrs={
                'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 13.8'
            }),
            'frekuensi_tx': forms.NumberInput(attrs={
                'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 156.800'
            }),
            'frekuensi_rx': forms.NumberInput(attrs={
                'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 156.800'
            }),
            'catatan': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3, 'placeholder': 'Catatan tambahan...'
            }),
        }
