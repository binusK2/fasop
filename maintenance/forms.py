from django import forms
from .models import Maintenance, MaintenancePLC, MaintenanceRouter, MaintenanceRadio, MaintenanceVoIP, MaintenanceMux, MaintenanceRectifier, MaintenanceTeleproteksi, MaintenanceGenset, MaintenanceRTU, MaintenanceSAS, MaintenanceRTUGeneric, MaintenanceRoIP, MaintenanceUPS, MaintenanceMasterTrip, MaintenanceDFR


# ─── Widget helpers ───────────────────────────────────────────────────
OK_NOK_WIDGET = forms.RadioSelect(attrs={'class': 'd-flex gap-3'})
NUM_WIDGET    = lambda: forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'})
INT_WIDGET    = lambda: forms.NumberInput(attrs={'class': 'form-control'})
TEXT_WIDGET   = lambda rows=3: forms.Textarea(attrs={'class': 'form-control', 'rows': rows})


# ─────────────────────────────────────────────────────────────────────
# FORM MAINTENANCE UTAMA (sama untuk semua jenis)
# ─────────────────────────────────────────────────────────────────────
class MaintenanceForm(forms.ModelForm):

    date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        input_formats=['%Y-%m-%dT%H:%M']
    )

    # Field khusus untuk menerima input pelaksana dari tag-input JS
    pelaksana_input = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_pelaksana_input'})
    )

    # Lock maintenance_type ke Preventive
    # PENTING: Jangan pakai disabled, karena browser tidak kirim field disabled.
    # Pakai HiddenInput agar value selalu terkirim di POST.
    maintenance_type = forms.CharField(
        initial='Preventive',
        widget=forms.HiddenInput(),
    )

    class Meta:
        model  = Maintenance
        fields = '__all__'
        exclude = ['device', 'created_at', 'technicians']
        widgets = {
            'description':     forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status':          forms.Select(attrs={'class': 'form-select'}),
            'photo':           forms.FileInput(attrs={'class': 'form-control'}),
            'pelaksana_names': forms.HiddenInput(attrs={'id': 'id_pelaksana_names'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pastikan selalu Preventive
        self.fields['maintenance_type'].initial = 'Preventive'
        if 'maintenance_type' not in (self.data or {}):
            self.initial['maintenance_type'] = 'Preventive'
        for name, field in self.fields.items():
            if not isinstance(field.widget, (forms.RadioSelect, forms.DateTimeInput, forms.HiddenInput)):
                if not field.widget.attrs.get('class'):
                    field.widget.attrs['class'] = 'form-control'
                    field.widget.attrs['class'] = 'form-control'


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL PLC (sudah ada sebelumnya)
# ─────────────────────────────────────────────────────────────────────
_PLC_SEL = forms.Select(choices=[('','—'),('OK','OK'),('NOK','NOK')], attrs={'class':'form-select form-select-sm'})


class MaintenancePLCForm(forms.ModelForm):
    import json as _json

    # HiddenInput carries the JSON array of module rows submitted by JS
    modul_terpasang = forms.CharField(required=False, widget=forms.HiddenInput(), initial='[]')

    def clean_modul_terpasang(self):
        import json
        raw = self.cleaned_data.get('modul_terpasang') or '[]'
        try:
            result = json.loads(raw)
            return result if isinstance(result, list) else []
        except (ValueError, TypeError):
            return []

    class Meta:
        model   = MaintenancePLC
        exclude = ['maintenance']
        widgets = {
            'akses_plc':        _PLC_SEL,
            'remote_akses_plc': _PLC_SEL,
            'time_sync':        _PLC_SEL,
            'wave_trap':        _PLC_SEL,
            'imu':              _PLC_SEL,
            'kabel_coaxial':    _PLC_SEL,
            'transmission_line': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -32.5'}),
            'rx_pilot_level':    forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -28.0'}),
            'freq_tx':           forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 72.5'}),
            'bandwidth_tx':      forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 4.0'}),
            'freq_rx':           forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 80.0'}),
            'bandwidth_rx':      forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 4.0'}),
        }


SELECT_OK_NOK = forms.Select(
    choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')],
    attrs={'class': 'form-select'}
)

# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL ROUTER / SWITCH  ← BARU
# ─────────────────────────────────────────────────────────────────────
class MaintenanceRouterForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceRouter
        exclude = ['maintenance']
        widgets = {
            # Fisik — pakai Select (bukan RadioSelect) agar JS querySelector('select') bisa baca nilainya
            'kondisi_fisik':  forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'led_link':       forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'kondisi_kabel':  forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),

            # Pengukuran
            'tegangan_input': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 220.5'}),
            'suhu_perangkat': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 45.0'}),
            # Port — status_routing juga pakai Select
            'jumlah_port_aktif':  forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'jumlah_port_total':  forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'status_routing':     forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
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
            'swr': forms.NumberInput(attrs={
                'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 1.2', 'id': 'id_swr'
            }),
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


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL VOIP
# ─────────────────────────────────────────────────────────────────────
class MaintenanceVoIPForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceVoIP
        exclude = ['maintenance']
        widgets = {
            # Informasi perangkat
            'ip_address':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 192.168.1.100'}),
            'extension_number':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 1001'}),
            'sip_server_1':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 192.168.1.10'}),
            'sip_server_2':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 192.168.1.11'}),
            # Suhu
            'suhu_ruangan':      forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 28.5'}),
            # Checklist — Select agar JS bisa baca dengan querySelector('select')
            'kondisi_fisik':     forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'ntp_server':        forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'webconfig':         forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            # Power Supply
            'ps_merk':           forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Huawei, Delta, APC'}),
            'ps_tegangan_input': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 220.5'}),
            'ps_status':         forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            # Catatan
            'catatan':           forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL MULTIPLEXER
# ─────────────────────────────────────────────────────────────────────
class MaintenanceMuxForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceMux
        exclude = ['maintenance']

        def _txt(ph=''):  return forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph})
        def _num(ph='', step='any'): return forms.NumberInput(attrs={'class': 'form-control', 'step': step, 'placeholder': ph})
        def _sel(choices): return forms.Select(choices=[('','—')]+list(choices), attrs={'class': 'form-select'})
        def _ta(rows=2): return forms.Textarea(attrs={'class': 'form-control', 'rows': rows})

        STATUS   = [('OK','OK'),('NOK','NOK')]
        KEBERSIHAN = [('Bersih','Bersih'),('Kotor','Kotor')]
        LAMPU    = [('Menyala','Menyala'),('Tidak Menyala','Tidak Menyala'),('Redup','Redup')]

        widgets = {
            # Lingkungan
            'suhu_ruangan':     forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'e.g. 25.0'}),
            'kebersihan':       forms.Select(choices=[('','—'),('Bersih','Bersih'),('Kotor','Kotor')], attrs={'class':'form-select'}),
            'lampu_penerangan': forms.Select(choices=[('','—'),('Menyala','Menyala'),('Tidak Menyala','Tidak Menyala'),('Redup','Redup')], attrs={'class':'form-select'}),
            # Peralatan
            'brand':         forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. Huawei, ZTE, Ciena'}),
            'firmware':      forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. V200R002C50SPC800'}),
            'sync_source_1': forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. 192.168.1.1'}),
            'sync_source_2': forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. 192.168.1.2'}),
            # CPU
            'cpu_1': forms.Textarea(attrs={'class':'form-control','rows':2,'placeholder':'Kondisi / versi CPU 1'}),
            'cpu_2': forms.Textarea(attrs={'class':'form-control','rows':2,'placeholder':'Kondisi / versi CPU 2'}),
            # HS 1
            'hs1_merk':      forms.TextInput(attrs={'class':'form-control','placeholder':'Merk HS 1'}),
            'hs1_tx_bias':   forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'mA'}),
            'hs1_jarak':     forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'km'}),
            'hs1_tx':        forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'dBm'}),
            'hs1_lambda':    forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'nm'}),
            'hs1_suhu':      forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'°C'}),
            'hs1_rx':        forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'dBm'}),
            'hs1_bandwidth': forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. 10G'}),
            # HS 2
            'hs2_merk':      forms.TextInput(attrs={'class':'form-control','placeholder':'Merk HS 2'}),
            'hs2_tx_bias':   forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'mA'}),
            'hs2_jarak':     forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'km'}),
            'hs2_tx':        forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'dBm'}),
            'hs2_lambda':    forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'nm'}),
            'hs2_suhu':      forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'°C'}),
            'hs2_rx':        forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'dBm'}),
            'hs2_bandwidth': forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. 10G'}),
            # Slot A-H
            'slot_a_modul': forms.Select(choices=[('', '— Pilih Modul —'), ('V35D', 'V35D'), ('6V35D', '6V35D'), ('SWITCH', 'SWITCH'), ('E1Q', 'E1Q'), ('16E1Q', '16E1Q'), ('G64', 'G64'), ('FOHW', 'FOHW'), ('DSL', 'DSL'), ('E1 G703', 'E1 G703'), ('E&M', 'E&M'), ('FXO', 'FXO'), ('FXO10', 'FXO10'), ('FXS4', 'FXS4'), ('FXS10', 'FXS10')], attrs={'class':'form-select'}),
            'slot_a_isian': forms.Textarea(attrs={'class':'form-control','rows':2,'placeholder':'e.g. Port 1 kosong, Port 2 active'}),
            'slot_b_modul': forms.Select(choices=[('', '— Pilih Modul —'), ('V35D', 'V35D'), ('6V35D', '6V35D'), ('SWITCH', 'SWITCH'), ('E1Q', 'E1Q'), ('16E1Q', '16E1Q'), ('G64', 'G64'), ('FOHW', 'FOHW'), ('DSL', 'DSL'), ('E1 G703', 'E1 G703'), ('E&M', 'E&M'), ('FXO', 'FXO'), ('FXO10', 'FXO10'), ('FXS4', 'FXS4'), ('FXS10', 'FXS10')], attrs={'class':'form-select'}),
            'slot_b_isian': forms.Textarea(attrs={'class':'form-control','rows':2,'placeholder':'e.g. Port 1 kosong, Port 2 active'}),
            'slot_c_modul': forms.Select(choices=[('', '— Pilih Modul —'), ('V35D', 'V35D'), ('6V35D', '6V35D'), ('SWITCH', 'SWITCH'), ('E1Q', 'E1Q'), ('16E1Q', '16E1Q'), ('G64', 'G64'), ('FOHW', 'FOHW'), ('DSL', 'DSL'), ('E1 G703', 'E1 G703'), ('E&M', 'E&M'), ('FXO', 'FXO'), ('FXO10', 'FXO10'), ('FXS4', 'FXS4'), ('FXS10', 'FXS10')], attrs={'class':'form-select'}),
            'slot_c_isian': forms.Textarea(attrs={'class':'form-control','rows':2,'placeholder':'e.g. Port 1 kosong, Port 2 active'}),
            'slot_d_modul': forms.Select(choices=[('', '— Pilih Modul —'), ('V35D', 'V35D'), ('6V35D', '6V35D'), ('SWITCH', 'SWITCH'), ('E1Q', 'E1Q'), ('16E1Q', '16E1Q'), ('G64', 'G64'), ('FOHW', 'FOHW'), ('DSL', 'DSL'), ('E1 G703', 'E1 G703'), ('E&M', 'E&M'), ('FXO', 'FXO'), ('FXO10', 'FXO10'), ('FXS4', 'FXS4'), ('FXS10', 'FXS10')], attrs={'class':'form-select'}),
            'slot_d_isian': forms.Textarea(attrs={'class':'form-control','rows':2,'placeholder':'e.g. Port 1 kosong, Port 2 active'}),
            'slot_e_modul': forms.Select(choices=[('', '— Pilih Modul —'), ('V35D', 'V35D'), ('6V35D', '6V35D'), ('SWITCH', 'SWITCH'), ('E1Q', 'E1Q'), ('16E1Q', '16E1Q'), ('G64', 'G64'), ('FOHW', 'FOHW'), ('DSL', 'DSL'), ('E1 G703', 'E1 G703'), ('E&M', 'E&M'), ('FXO', 'FXO'), ('FXO10', 'FXO10'), ('FXS4', 'FXS4'), ('FXS10', 'FXS10')], attrs={'class':'form-select'}),
            'slot_e_isian': forms.Textarea(attrs={'class':'form-control','rows':2,'placeholder':'e.g. Port 1 kosong, Port 2 active'}),
            'slot_f_modul': forms.Select(choices=[('', '— Pilih Modul —'), ('V35D', 'V35D'), ('6V35D', '6V35D'), ('SWITCH', 'SWITCH'), ('E1Q', 'E1Q'), ('16E1Q', '16E1Q'), ('G64', 'G64'), ('FOHW', 'FOHW'), ('DSL', 'DSL'), ('E1 G703', 'E1 G703'), ('E&M', 'E&M'), ('FXO', 'FXO'), ('FXO10', 'FXO10'), ('FXS4', 'FXS4'), ('FXS10', 'FXS10')], attrs={'class':'form-select'}),
            'slot_f_isian': forms.Textarea(attrs={'class':'form-control','rows':2,'placeholder':'e.g. Port 1 kosong, Port 2 active'}),
            'slot_g_modul': forms.Select(choices=[('', '— Pilih Modul —'), ('V35D', 'V35D'), ('6V35D', '6V35D'), ('SWITCH', 'SWITCH'), ('E1Q', 'E1Q'), ('16E1Q', '16E1Q'), ('G64', 'G64'), ('FOHW', 'FOHW'), ('DSL', 'DSL'), ('E1 G703', 'E1 G703'), ('E&M', 'E&M'), ('FXO', 'FXO'), ('FXO10', 'FXO10'), ('FXS4', 'FXS4'), ('FXS10', 'FXS10')], attrs={'class':'form-select'}),
            'slot_g_isian': forms.Textarea(attrs={'class':'form-control','rows':2,'placeholder':'e.g. Port 1 kosong, Port 2 active'}),
            'slot_h_modul': forms.Select(choices=[('', '— Pilih Modul —'), ('V35D', 'V35D'), ('6V35D', '6V35D'), ('SWITCH', 'SWITCH'), ('E1Q', 'E1Q'), ('16E1Q', '16E1Q'), ('G64', 'G64'), ('FOHW', 'FOHW'), ('DSL', 'DSL'), ('E1 G703', 'E1 G703'), ('E&M', 'E&M'), ('FXO', 'FXO'), ('FXO10', 'FXO10'), ('FXS4', 'FXS4'), ('FXS10', 'FXS10')], attrs={'class':'form-select'}),
            'slot_h_isian': forms.Textarea(attrs={'class':'form-control','rows':2,'placeholder':'e.g. Port 1 kosong, Port 2 active'}),
            # PSU
            'psu1_status': forms.Select(choices=[('','—'),('OK','OK'),('NOK','NOK')], attrs={'class':'form-select'}),
            'psu1_temp1':  forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'°C'}),
            'psu1_temp2':  forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'°C'}),
            'psu1_temp3':  forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'°C'}),
            'psu2_status': forms.Select(choices=[('','—'),('OK','OK'),('NOK','NOK')], attrs={'class':'form-select'}),
            'psu2_temp1':  forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'°C'}),
            'psu2_temp2':  forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'°C'}),
            'psu2_temp3':  forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'°C'}),
            # FAN + catatan
            'fan_status': forms.Select(choices=[('','—'),('OK','OK'),('NOK','NOK')], attrs={'class':'form-select'}),
            'catatan':    forms.Textarea(attrs={'class':'form-control','rows':3}),
        }


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL RECTIFIER & BATTERY
# ─────────────────────────────────────────────────────────────────────
class MaintenanceRectifierForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceRectifier
        exclude = ['maintenance']

        STATUS   = [('','—'),('OK','OK'),('NOK','NOK')]
        EXHAUST  = [('','—'),('Terpasang','Terpasang'),('Tidak Terpasang','Tidak Terpasang'),('Rusak','Rusak')]
        KEBERSIHAN = [('','—'),('Bersih','Bersih'),('Kotor','Kotor')]
        LAMPU    = [('','—'),('Menyala','Menyala'),('Tidak Menyala','Tidak Menyala'),('Redup','Redup')]

        def _num(ph=''):
            return forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':ph})
        def _txt(ph=''):
            return forms.TextInput(attrs={'class':'form-control','placeholder':ph})
        def _sel(ch):
            return forms.Select(choices=ch, attrs={'class':'form-select'})

        widgets = {
            # Lingkungan
            'suhu_ruangan':     forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'°C'}),
            'exhaust_fan':      forms.Select(choices=EXHAUST,    attrs={'class':'form-select'}),
            'kebersihan':       forms.Select(choices=KEBERSIHAN, attrs={'class':'form-select'}),
            'lampu_penerangan': forms.Select(choices=LAMPU,      attrs={'class':'form-select'}),
            # Rectifier 1
            'rect1_merk':           forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. Eltek, Huawei'}),
            'rect1_tipe':           forms.TextInput(attrs={'class':'form-control','placeholder':'Tipe/model'}),
            'rect1_kondisi':        forms.Select(choices=STATUS, attrs={'class':'form-select'}),
            'rect1_kapasitas':      forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. 48V/100A'}),
            'rect1_v_rectifier':    forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'V'}),
            'rect1_v_battery':      forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'V'}),
            'rect1_teg_pos_ground': forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'V'}),
            'rect1_teg_neg_ground': forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'V'}),
            'rect1_v_dropper':      forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'V'}),
            'rect1_v_load':         forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'V'}),
            'rect1_a_rectifier':    forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'A'}),
            'rect1_a_battery':      forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'A'}),
            'rect1_a_load':         forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'A'}),
            # Battery Bank 1
            'bat1_merk':             forms.TextInput(attrs={'class':'form-control','placeholder':'Merk battery'}),
            'bat1_tipe':             forms.TextInput(attrs={'class':'form-control','placeholder':'Tipe/model'}),
            'bat1_kondisi':          forms.Select(choices=STATUS, attrs={'class':'form-select'}),
            'bat1_kapasitas':        forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. 100 Ah'}),
            'bat1_jumlah':           forms.NumberInput(attrs={'class':'form-control','placeholder':'Jumlah cell','min':1,'max':40,'id':'bat1_jumlah'}),
            'bat1_kondisi_kabel':    forms.Select(choices=STATUS, attrs={'class':'form-select'}),
            'bat1_kondisi_mur_baut': forms.Select(choices=STATUS, attrs={'class':'form-select'}),
            'bat1_kondisi_sel_rak':  forms.Select(choices=STATUS, attrs={'class':'form-select'}),
            'bat1_air_battery':      forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'V'}),
            'bat1_v_total':          forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'V'}),
            'bat1_v_load':           forms.NumberInput(attrs={'class':'form-control','step':'any','placeholder':'V'}),
            'bat1_cells':            forms.HiddenInput(),
            # Catatan
            'catatan': forms.Textarea(attrs={'class':'form-control','rows':3}),
        }


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL TELEPROTEKSI
# ─────────────────────────────────────────────────────────────────────
class MaintenanceTeleproteksiForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceTeleproteksi
        exclude = ['maintenance']
        widgets = {
            # Informasi Umum
            'suhu_ruangan':         forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 28.5'}),
            'kebersihan_perangkat': forms.Select(choices=[('', '—'), ('Bersih', 'Bersih'), ('Kotor', 'Kotor')], attrs={'class': 'form-select'}),
            'kebersihan_panel':     forms.Select(choices=[('', '—'), ('Bersih', 'Bersih'), ('Kotor', 'Kotor')], attrs={'class': 'form-select'}),
            'lampu':                forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            # Informasi Perangkat
            'link':             forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. GI Tello 150 — GI Soppeng'}),
            'tipe_tp':          forms.Select(attrs={'class': 'form-select', 'id': 'id_tipe_tp'}),
            'versi_program':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. v3.2.1'}),
            'address_tp':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 01'}),
            'port_comm':        forms.Select(attrs={'class': 'form-select'}),
            'akses_tp':         forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'remote_akses_tp':  forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            # Kondisi
            'jumlah_skema': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '4'}),
            # Skema 1
            'skema_1_command':       forms.Select(attrs={'class': 'form-select'}),
            'skema_1_send_minus':    forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -48.5'}),
            'skema_1_send_plus':     forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 48.5'}),
            'skema_1_receive_minus': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -48.5'}),
            'skema_1_receive_plus':  forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 48.5'}),
            # Skema 2
            'skema_2_command':       forms.Select(attrs={'class': 'form-select'}),
            'skema_2_send_minus':    forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -48.5'}),
            'skema_2_send_plus':     forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 48.5'}),
            'skema_2_receive_minus': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -48.5'}),
            'skema_2_receive_plus':  forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 48.5'}),
            # Skema 3
            'skema_3_command':       forms.Select(attrs={'class': 'form-select'}),
            'skema_3_send_minus':    forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -48.5'}),
            'skema_3_send_plus':     forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 48.5'}),
            'skema_3_receive_minus': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -48.5'}),
            'skema_3_receive_plus':  forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 48.5'}),
            # Skema 4
            'skema_4_command':       forms.Select(attrs={'class': 'form-select'}),
            'skema_4_send_minus':    forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -48.5'}),
            'skema_4_send_plus':     forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 48.5'}),
            'skema_4_receive_minus': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. -48.5'}),
            'skema_4_receive_plus':  forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 48.5'}),
            # Teg Standby & Polaritas (field baru)
            'skema_1_send_teg':      forms.Select(attrs={'class': 'form-select'}),
            'skema_1_send_pol':      forms.Select(attrs={'class': 'form-select'}),
            'skema_1_receive_teg':   forms.Select(attrs={'class': 'form-select'}),
            'skema_1_receive_pol':   forms.Select(attrs={'class': 'form-select'}),
            'skema_2_send_teg':      forms.Select(attrs={'class': 'form-select'}),
            'skema_2_send_pol':      forms.Select(attrs={'class': 'form-select'}),
            'skema_2_receive_teg':   forms.Select(attrs={'class': 'form-select'}),
            'skema_2_receive_pol':   forms.Select(attrs={'class': 'form-select'}),
            'skema_3_send_teg':      forms.Select(attrs={'class': 'form-select'}),
            'skema_3_send_pol':      forms.Select(attrs={'class': 'form-select'}),
            'skema_3_receive_teg':   forms.Select(attrs={'class': 'form-select'}),
            'skema_3_receive_pol':   forms.Select(attrs={'class': 'form-select'}),
            'skema_4_send_teg':      forms.Select(attrs={'class': 'form-select'}),
            'skema_4_send_pol':      forms.Select(attrs={'class': 'form-select'}),
            'skema_4_receive_teg':   forms.Select(attrs={'class': 'form-select'}),
            'skema_4_receive_pol':   forms.Select(attrs={'class': 'form-select'}),
            # Hasil pengujian
            'skema_1_send_result':    forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'skema_1_receive_result': forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'skema_2_send_result':    forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'skema_2_receive_result': forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'skema_3_send_result':    forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'skema_3_receive_result': forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'skema_4_send_result':    forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'skema_4_receive_result': forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            # Pengujian umum
            'time_sync': forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select'}),
            'loop_test': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g. 12.5'}),
            # Catatan
            'catatan':   forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL GENSET
# ─────────────────────────────────────────────────────────────────────
class MaintenanceGensetForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceGenset
        exclude = ['maintenance']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fc   = 'form-control'
        fcsm = 'form-control form-control-sm'
        fs   = 'form-select'
        num  = {'step': 'any'}

        # Batere & Charger
        for f, ph in [
            ('air_accu','e.g. 90'), ('tegangan_batere','e.g. 24.0'),
            ('arus_pengisian','e.g. 5.5'), ('tegangan_charger','e.g. 27.6'),
            ('arus_beban_charger','e.g. 2.0'),
        ]:
            self.fields[f].widget = forms.NumberInput(attrs={'class': fc, **num, 'placeholder': ph})

        # Genset utama
        for f, ph in [
            ('radiator','e.g. 85'), ('kapasitas_tangki','e.g. 500'),
            ('tangki_bbm_sebelum','e.g. 70'), ('tangki_bbm_sesudah','e.g. 60'),
            ('waktu_transisi','e.g. 5'),
        ]:
            self.fields[f].widget = forms.NumberInput(attrs={'class': fc, **num, 'placeholder': ph})

        self.fields['mcb'].widget    = forms.Select(choices=[('','—'),('ON','ON'),('OFF','OFF')], attrs={'class': fs})
        self.fields['pelumas'].widget = forms.TextInput(attrs={'class': fc, 'placeholder': 'e.g. Strip On Stick'})

        # Pengukuran PLN & Genset — input kecil
        meas_fields = [
            'pln_f_r','pln_f_s','pln_f_t',
            'pln_v_rn','pln_v_sn','pln_v_tn',
            'pln_v_rs','pln_v_st','pln_v_tr',
            'pln_i_r','pln_i_s','pln_i_t',
            'gen_f_r','gen_f_s','gen_f_t',
            'gen_v_rn','gen_v_sn','gen_v_tn',
            'gen_v_rs','gen_v_st','gen_v_tr',
            'gen_i_r','gen_i_s','gen_i_t',
        ]
        for f in meas_fields:
            self.fields[f].widget = forms.NumberInput(attrs={'class': fcsm, **num})

        # MDF Cubicle
        for f, ph in [
            ('oil_pressure','e.g. 270'), ('engine_temperature','e.g. 71'),
            ('batere_condition','e.g. 27.0'), ('rpm','e.g. 1500'),
        ]:
            self.fields[f].widget = forms.NumberInput(attrs={'class': fc, **num, 'placeholder': ph})

        # Counter
        for f in ['counter_sebelum','counter_sesudah']:
            self.fields[f].widget = forms.NumberInput(attrs={'class': fc, **num, 'placeholder': 'e.g. 575.57'})

        # Jam Operasi
        self.fields['waktu_start'].widget = forms.TimeInput(attrs={'class': fc, 'type': 'time'})
        self.fields['waktu_stop'].widget  = forms.TimeInput(attrs={'class': fc, 'type': 'time'})

        # Catatan
        self.fields['catatan'].widget = forms.Textarea(attrs={'class': fc, 'rows': 3})


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL RTU
# ─────────────────────────────────────────────────────────────────────
class MaintenanceRTUForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceRTU
        exclude = ['maintenance']
        widgets = {
            # Jumlah modul — NumberInput
            'cp2016_jumlah': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Jumlah'}),
            'cp2019_jumlah': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Jumlah'}),
            'di2112_jumlah': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Jumlah'}),
            'do2210_jumlah': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Jumlah'}),
            # JSON data — HiddenInput, diisi oleh JavaScript
            'cp2016_data': forms.HiddenInput(attrs={'id': 'id_cp2016_data'}),
            'cp2019_data': forms.HiddenInput(attrs={'id': 'id_cp2019_data'}),
            'di2112_data': forms.HiddenInput(attrs={'id': 'id_di2112_data'}),
            'do2210_data': forms.HiddenInput(attrs={'id': 'id_do2210_data'}),
            'ai2300_data': forms.HiddenInput(attrs={'id': 'id_ai2300_data'}),
            'ied_data':    forms.HiddenInput(attrs={'id': 'id_ied_data'}),
            # Power Supply 48V
            'ps48_teg_beban':   forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'ps48_arus_beban':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
            'ps48_teg_supply':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'ps48_arus_supply': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
            # Power Supply 110V
            'ps110_teg_beban':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'ps110_arus_beban': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
            'ps110_teg_supply': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'ps110_arus_supply':forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
        }

# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL SAS (SERVER / GATEWAY SAS)
# ─────────────────────────────────────────────────────────────────────
_SAS_SEL = {'class': 'form-select form-select-sm'}

class MaintenanceSASForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceSAS
        exclude = ['maintenance']
        widgets = {
            # Spesifikasi
            'spek_merk':       forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_type':       forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_cpu':        forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_ram':        forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_gpu':        forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_storage':    forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_firmware':   forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_config_ver': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_ip':         forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '192.168.x.x/24'}),
            'modul_io':        forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 8, 'placeholder': 'Daftar modul/card/terminal yang terpasang...'}),
            # Kondisi (Select — hidden, dikendalikan toggle button di template)
            'kondisi_server':  forms.Select(attrs=_SAS_SEL),
            'kondisi_panel':   forms.Select(attrs=_SAS_SEL),
            'exhaust_fan':     forms.Select(attrs=_SAS_SEL),
            'temp_ruangan':    forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': '°C'}),
            'temp_peralatan':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': '°C'}),
            # Peripheral
            'peri_eth_switch': forms.Select(attrs=_SAS_SEL),
            'peri_gps':        forms.Select(attrs=_SAS_SEL),
            'peri_eth_serial': forms.Select(attrs=_SAS_SEL),
            'peri_router':     forms.Select(attrs=_SAS_SEL),
            'jumlah_bay':      forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0', 'placeholder': 'Bay'}),
            'peri_keterangan': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            # Performa
            'perf_cpu':        forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'misal 45%'}),
            'perf_ram':        forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'misal 60%'}),
            'perf_storage':    forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'misal 30%'}),
            'indikasi_alarm':  forms.Select(attrs=_SAS_SEL),
            'komm_master':     forms.Select(attrs=_SAS_SEL),
            'komm_ied':        forms.Select(attrs=_SAS_SEL),
            'time_sync':       forms.Select(attrs=_SAS_SEL),
            # Power Supply — Inverter
            'inv_kondisi':     forms.Select(attrs=_SAS_SEL),
            'inv_teg_input':   forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'inv_arus_input':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
            'inv_teg_output':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'inv_arus_output': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
            # Power Supply — 110VDC/48VDC
            'ps_teg_input':    forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'ps_arus_input':   forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
            'ps_teg_output':   forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'ps_arus_output':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
        }


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL RTU GENERIC (selain Siemens AK3) — field identik SASForm
# ─────────────────────────────────────────────────────────────────────
class MaintenanceRTUGenericForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceRTUGeneric
        exclude = ['maintenance']
        widgets = {
            'spek_merk':       forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_type':       forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_cpu':        forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_ram':        forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_gpu':        forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_storage':    forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_firmware':   forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_config_ver': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'spek_ip':         forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '192.168.x.x/24'}),
            'modul_io':        forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 8, 'placeholder': 'Daftar modul/card/terminal yang terpasang...'}),
            'kondisi_server':  forms.Select(attrs=_SAS_SEL),
            'kondisi_panel':   forms.Select(attrs=_SAS_SEL),
            'exhaust_fan':     forms.Select(attrs=_SAS_SEL),
            'temp_ruangan':    forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': '°C'}),
            'temp_peralatan':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': '°C'}),
            'peri_eth_switch': forms.Select(attrs=_SAS_SEL),
            'peri_gps':        forms.Select(attrs=_SAS_SEL),
            'peri_eth_serial': forms.Select(attrs=_SAS_SEL),
            'peri_router':     forms.Select(attrs=_SAS_SEL),
            'jumlah_bay':      forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0', 'placeholder': 'Bay'}),
            'peri_keterangan': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'perf_cpu':        forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'misal 45%'}),
            'perf_ram':        forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'misal 60%'}),
            'perf_storage':    forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'misal 30%'}),
            'indikasi_alarm':  forms.Select(attrs=_SAS_SEL),
            'komm_master':     forms.Select(attrs=_SAS_SEL),
            'komm_ied':        forms.Select(attrs=_SAS_SEL),
            'time_sync':       forms.Select(attrs=_SAS_SEL),
            'inv_kondisi':     forms.Select(attrs=_SAS_SEL),
            'inv_teg_input':   forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'inv_arus_input':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
            'inv_teg_output':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'inv_arus_output': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
            'ps_teg_input':    forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'ps_arus_input':   forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
            'ps_teg_output':   forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'V'}),
            'ps_arus_output':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any', 'placeholder': 'A'}),
        }


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL RoIP
# ─────────────────────────────────────────────────────────────────────
_ROIP_SEL = [('', '—'), ('OK', 'OK'), ('NOK', 'NOK')]


class MaintenanceRoIPForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceRoIP
        exclude = ['maintenance']
        widgets = {
            'kondisi_fisik':    forms.Select(choices=_ROIP_SEL, attrs={'class': 'form-select'}),
            'ntp_server':       forms.Select(choices=_ROIP_SEL, attrs={'class': 'form-select'}),
            'power_supply':     forms.Select(choices=_ROIP_SEL, attrs={'class': 'form-select'}),
            'memory_usage':     forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': '%'}),
            'tx_volume_offset':        forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'dB'}),
            'rx_volume_offset':        forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'dB'}),
            'bridge_conn_source':      forms.TextInput(attrs={'class': 'form-control'}),
            'bridge_conn_destination': forms.TextInput(attrs={'class': 'form-control'}),
            'dest_port_number':        forms.TextInput(attrs={'class': 'form-control'}),
            'source_port_number':      forms.TextInput(attrs={'class': 'form-control'}),
            'ptt_attack_time':         forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ms'}),
            'ptt_release_time':  forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ms'}),
            'ptt_voice_delay':   forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ms'}),
            'ptt_vox_threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': '%'}),
            'rx_attack_time':   forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ms'}),
            'rx_release_time':  forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ms'}),
            'rx_voice_delay':   forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ms'}),
            'rx_vox_threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': '%'}),
            'test_radio_master': forms.Select(choices=_ROIP_SEL, attrs={'class': 'form-select'}),
            'test_ping_master':  forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ms'}),
            'catatan':           forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# ─────────────────────────────────────────────────────────────────────
# FORM DETAIL UPS
# ─────────────────────────────────────────────────────────────────────
_UPS_SEL = forms.Select(choices=[('', '—'), ('OK', 'OK'), ('NOK', 'NOK')], attrs={'class': 'form-select form-select-sm'})


class MaintenanceUPSForm(forms.ModelForm):

    class Meta:
        model   = MaintenanceUPS
        exclude = ['maintenance']

        def _num(ph='', step='any'):
            return forms.NumberInput(attrs={'class': 'form-control', 'step': step, 'placeholder': ph})
        def _txt(ph=''):
            return forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph})

        widgets = {
            # UPS info
            'ups_merk':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. APC, Emerson, Socomec'}),
            'ups_model':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Smart-UPS 3000'}),
            'ups_kapasitas': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 3000 VA / 2.7 kVA'}),
            'ups_kondisi':   _UPS_SEL,
            # Input AC
            'v_input_r': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'V'}),
            'v_input_s': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'V'}),
            'v_input_t': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'V'}),
            'f_input':   forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Hz'}),
            # Output AC
            'v_output_r':   forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'V'}),
            'v_output_s':   forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'V'}),
            'v_output_t':   forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'V'}),
            'f_output':     forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Hz'}),
            'a_load':       forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'A'}),
            'percent_load': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': '%'}),
            # Battery
            'bat_merk':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Yuasa, GS Astra'}),
            'bat_tipe':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. NPL38-12'}),
            'bat_kapasitas':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 38 Ah / 12V'}),
            'bat_jumlah_cell':  forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 200, 'id': 'bat_jumlah_cell'}),
            'bat_kondisi':      _UPS_SEL,
            'bat_kondisi_kabel':_UPS_SEL,
            'bat_v_total':      forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'V'}),
            'bat_cells':        forms.HiddenInput(),
            # Catatan
            'catatan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# ─────────────────────────────────────────────────────────────
# FORM FREQUENCY RELAY (UFLS / UFR ISLAND / OFGS / CDSAS)
# ─────────────────────────────────────────────────────────────
_VI_SEL = forms.Select(attrs={'class': 'form-select form-select-sm'})
_FR_TXT = forms.TextInput(attrs={'class': 'form-control form-control-sm'})
_FR_NUM = forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': 'any'})
_FR_SEL = forms.Select(attrs={'class': 'form-select form-select-sm'})


class MaintenanceFrequencyRelayForm(forms.ModelForm):
    class Meta:
        from .models import MaintenanceFrequencyRelay
        model = MaintenanceFrequencyRelay
        exclude = ['maintenance']
        widgets = {
            # Visual Inspection
            'healthy':  _VI_SEL,
            'frek_oor': _VI_SEL,
            'alarm':    _VI_SEL,
            # Info Relay
            'fungsi':          _FR_SEL,
            'target_proteksi': _FR_SEL,
            'rasio_vt':        _FR_TXT,
            'rasio_vt_sek':    _FR_TXT,
            'vblock':          _FR_TXT,
            # Measurement
            'v_an': _FR_TXT, 'v_bn': _FR_TXT, 'v_cn': _FR_TXT,
            'v_ab': _FR_TXT, 'v_bc': _FR_TXT, 'v_ac': _FR_TXT,
            'frekuensi': _FR_TXT,
            'target_v_an': _FR_TXT, 'target_v_bn': _FR_TXT, 'target_v_cn': _FR_TXT,
            'target_v_ab': _FR_TXT, 'target_v_bc': _FR_TXT, 'target_v_ac': _FR_TXT,
            'target_frekuensi': _FR_TXT,
            # Setting Relay F1-F7
            'f1_hz': _FR_NUM, 'f1_s': _FR_NUM, 'f1_rl': _FR_TXT,
            'f1_pos_vdc': _FR_TXT, 'f1_pos_pin': _FR_TXT,
            'f1_neg_vdc': _FR_TXT, 'f1_neg_pin': _FR_TXT,
            'f2_hz': _FR_NUM, 'f2_s': _FR_NUM, 'f2_rl': _FR_TXT,
            'f2_pos_vdc': _FR_TXT, 'f2_pos_pin': _FR_TXT,
            'f2_neg_vdc': _FR_TXT, 'f2_neg_pin': _FR_TXT,
            'f3_hz': _FR_NUM, 'f3_s': _FR_NUM, 'f3_rl': _FR_TXT,
            'f3_pos_vdc': _FR_TXT, 'f3_pos_pin': _FR_TXT,
            'f3_neg_vdc': _FR_TXT, 'f3_neg_pin': _FR_TXT,
            'f4_hz': _FR_NUM, 'f4_s': _FR_NUM, 'f4_rl': _FR_TXT,
            'f4_pos_vdc': _FR_TXT, 'f4_pos_pin': _FR_TXT,
            'f4_neg_vdc': _FR_TXT, 'f4_neg_pin': _FR_TXT,
            'f5_hz': _FR_NUM, 'f5_s': _FR_NUM, 'f5_rl': _FR_TXT,
            'f5_pos_vdc': _FR_TXT, 'f5_pos_pin': _FR_TXT,
            'f5_neg_vdc': _FR_TXT, 'f5_neg_pin': _FR_TXT,
            'f6_hz': _FR_NUM, 'f6_s': _FR_NUM, 'f6_rl': _FR_TXT,
            'f6_pos_vdc': _FR_TXT, 'f6_pos_pin': _FR_TXT,
            'f6_neg_vdc': _FR_TXT, 'f6_neg_pin': _FR_TXT,
            'f7_hz': _FR_NUM, 'f7_s': _FR_NUM, 'f7_rl': _FR_TXT,
            'f7_pos_vdc': _FR_TXT, 'f7_pos_pin': _FR_TXT,
            'f7_neg_vdc': _FR_TXT, 'f7_neg_pin': _FR_TXT,
            # AUX RL
            'aux1_rl': _FR_TXT, 'aux1_tf': _FR_TXT, 'aux1_led': _FR_TXT,
            'aux2_rl': _FR_TXT, 'aux2_tf': _FR_TXT, 'aux2_led': _FR_TXT,
            'aux3_rl': _FR_TXT, 'aux3_tf': _FR_TXT, 'aux3_led': _FR_TXT,
            'aux4_rl': _FR_TXT, 'aux4_tf': _FR_TXT, 'aux4_led': _FR_TXT,
            'aux5_rl': _FR_TXT, 'aux5_tf': _FR_TXT, 'aux5_led': _FR_TXT,
            'aux6_rl': _FR_TXT, 'aux6_tf': _FR_TXT, 'aux6_led': _FR_TXT,
            'aux7_rl': _FR_TXT, 'aux7_tf': _FR_TXT, 'aux7_led': _FR_TXT,
            # Catatan
            'supply_dc': _FR_TXT,
            'selektor':  _FR_TXT,
            'catatan':   forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


_MT_TXT = forms.TextInput(attrs={'class': 'form-control form-control-sm'})
_MT_SEL = forms.Select(attrs={'class': 'form-select form-select-sm'})
_MT_TA  = forms.Textarea(attrs={'class': 'form-control', 'rows': 3})


class MaintenanceMasterTripForm(forms.ModelForm):
    class Meta:
        model   = MaintenanceMasterTrip
        exclude = ['maintenance']
        widgets = {
            # Visual Inspection
            'healthy': _MT_SEL, 'trip_led': _MT_SEL, 'alarm': _MT_SEL,
            # Info
            'merek': _MT_TXT, 'no_seri': _MT_TXT, 'target': _MT_TXT, 'fungsi': _MT_TXT, 'rasio_ct': _MT_TXT,
            # Measurement
            'i_a': _MT_TXT, 'i_b': _MT_TXT, 'i_c': _MT_TXT,
            'v_a': _MT_TXT, 'v_b': _MT_TXT, 'v_c': _MT_TXT, 'frekuensi': _MT_TXT,
            # Setting relay
            'setting_i': _MT_TXT, 'waktu_i': _MT_TXT, 'setting_ii': _MT_TXT, 'waktu_ii': _MT_TXT,
            'under_power': _MT_TXT, 'waktu_under': _MT_TXT, 'over_power': _MT_TXT, 'waktu_over': _MT_TXT,
            # Common Positif RL
            'p1_rl': _MT_TXT, 'p1_vdc': _MT_TXT, 'p1_pin': _MT_TXT, 'p1_tahap_vdc': _MT_TXT, 'p1_tahap_pin': _MT_TXT,
            'p2_rl': _MT_TXT, 'p2_vdc': _MT_TXT, 'p2_pin': _MT_TXT, 'p2_tahap_vdc': _MT_TXT, 'p2_tahap_pin': _MT_TXT,
            'p3_rl': _MT_TXT, 'p3_vdc': _MT_TXT, 'p3_pin': _MT_TXT, 'p3_tahap_vdc': _MT_TXT, 'p3_tahap_pin': _MT_TXT,
            'p4_rl': _MT_TXT, 'p4_vdc': _MT_TXT, 'p4_pin': _MT_TXT, 'p4_tahap_vdc': _MT_TXT, 'p4_tahap_pin': _MT_TXT,
            'p5_rl': _MT_TXT, 'p5_vdc': _MT_TXT, 'p5_pin': _MT_TXT, 'p5_tahap_vdc': _MT_TXT, 'p5_tahap_pin': _MT_TXT,
            'p6_rl': _MT_TXT, 'p6_vdc': _MT_TXT, 'p6_pin': _MT_TXT, 'p6_tahap_vdc': _MT_TXT, 'p6_tahap_pin': _MT_TXT,
            # Common Negatif RL
            'n1_rl': _MT_TXT, 'n1_vdc': _MT_TXT, 'n1_pin': _MT_TXT, 'n1_tahap_vdc': _MT_TXT, 'n1_tahap_pin': _MT_TXT,
            'n2_rl': _MT_TXT, 'n2_vdc': _MT_TXT, 'n2_pin': _MT_TXT, 'n2_tahap_vdc': _MT_TXT, 'n2_tahap_pin': _MT_TXT,
            'n3_rl': _MT_TXT, 'n3_vdc': _MT_TXT, 'n3_pin': _MT_TXT, 'n3_tahap_vdc': _MT_TXT, 'n3_tahap_pin': _MT_TXT,
            'n4_rl': _MT_TXT, 'n4_vdc': _MT_TXT, 'n4_pin': _MT_TXT, 'n4_tahap_vdc': _MT_TXT, 'n4_tahap_pin': _MT_TXT,
            'n5_rl': _MT_TXT, 'n5_vdc': _MT_TXT, 'n5_pin': _MT_TXT, 'n5_tahap_vdc': _MT_TXT, 'n5_tahap_pin': _MT_TXT,
            'n6_rl': _MT_TXT, 'n6_vdc': _MT_TXT, 'n6_pin': _MT_TXT, 'n6_tahap_vdc': _MT_TXT, 'n6_tahap_pin': _MT_TXT,
            # AUX RL/BO
            'aux1_rl': _MT_TXT, 'aux1_tf': _MT_TXT, 'aux1_led': _MT_TXT,
            'aux2_rl': _MT_TXT, 'aux2_tf': _MT_TXT, 'aux2_led': _MT_TXT,
            'aux3_rl': _MT_TXT, 'aux3_tf': _MT_TXT, 'aux3_led': _MT_TXT,
            'aux4_rl': _MT_TXT, 'aux4_tf': _MT_TXT, 'aux4_led': _MT_TXT,
            'aux5_rl': _MT_TXT, 'aux5_tf': _MT_TXT, 'aux5_led': _MT_TXT,
            'aux6_rl': _MT_TXT, 'aux6_tf': _MT_TXT, 'aux6_led': _MT_TXT,
            # Status Kesiapan + Test COMM
            'dev1_nama': _MT_TXT, 'dev1_gi': _MT_TXT, 'dev1_ready': _MT_SEL, 'dev1_comm': _MT_SEL,
            'dev2_nama': _MT_TXT, 'dev2_gi': _MT_TXT, 'dev2_ready': _MT_SEL, 'dev2_comm': _MT_SEL,
            'dev3_nama': _MT_TXT, 'dev3_gi': _MT_TXT, 'dev3_ready': _MT_SEL, 'dev3_comm': _MT_SEL,
            'dev4_nama': _MT_TXT, 'dev4_gi': _MT_TXT, 'dev4_ready': _MT_SEL, 'dev4_comm': _MT_SEL,
            'dev5_nama': _MT_TXT, 'dev5_gi': _MT_TXT, 'dev5_ready': _MT_SEL, 'dev5_comm': _MT_SEL,
            'dev6_nama': _MT_TXT, 'dev6_gi': _MT_TXT, 'dev6_ready': _MT_SEL, 'dev6_comm': _MT_SEL,
            # Catatan
            'supply_dc': _MT_TXT, 'selektor': _MT_TXT, 'catatan': _MT_TA,
        }


_DFR_TXT = forms.TextInput(attrs={'class': 'form-control form-control-sm'})
_DFR_SEL = forms.Select(attrs={'class': 'form-select form-select-sm'})
_DFR_TA  = forms.Textarea(attrs={'class': 'form-control', 'rows': 3})


class MaintenanceDFRForm(forms.ModelForm):
    class Meta:
        model   = MaintenanceDFR
        exclude = ['maintenance']
        widgets = {
            # Header
            'bay_feeder_1': _DFR_TXT, 'bay_feeder_2': _DFR_TXT,
            'rasio_ct_1':   _DFR_TXT, 'rasio_ct_2':   _DFR_TXT,
            'rasio_pt_1':   _DFR_TXT, 'rasio_pt_2':   _DFR_TXT,
            'suhu_ruangan': _DFR_TXT, 'kelembaban':   _DFR_TXT,
            # Section I
            'kartu_kontrol': _DFR_SEL, 'outdoor_panel': _DFR_SEL,
            'indoor_panel':  _DFR_SEL, 'tergrounding':  _DFR_SEL,
            'type_dfr': _DFR_TXT, 'sn_dfr': _DFR_TXT, 'merk_dfr': _DFR_TXT,
            # Section II
            'kondisi_gps': _DFR_SEL, 'kondisi_lcd': _DFR_SEL, 'waktu_dfr': _DFR_SEL,
            # Section III
            'dfr_aktif': _DFR_SEL, 'fisik_alarm': _DFR_SEL, 'fungsi_rekaman': _DFR_SEL,
            # Section IV
            'visual_5r': _DFR_SEL,
            'front_port_ip': _DFR_TXT, 'rear_port_ip': _DFR_TXT,
            'fo_tx': _DFR_SEL, 'fo_rx': _DFR_SEL,
            'conv_tx': _DFR_SEL, 'conv_rx': _DFR_SEL,
            'lan_tx': _DFR_SEL, 'lan_rx': _DFR_SEL,
            'ping_server_1': _DFR_TXT, 'ping_server_2': _DFR_TXT, 'ping_server_status': _DFR_SEL,
            'ping_dfr_1':    _DFR_TXT, 'ping_dfr_2':    _DFR_TXT, 'ping_dfr_status':    _DFR_SEL,
            # Section V
            'software_config': _DFR_SEL, 'rekaman_gangguan': _DFR_SEL,
            'v_input_power': _DFR_TXT, 'v_backup': _DFR_TXT,
            'kapasitas_memory': _DFR_TXT, 'pmu_id': _DFR_TXT,
            'catatan_khusus': _DFR_TA,
            # Bay 1 DFR
            'bay1_dfr_v_r': _DFR_TXT, 'bay1_dfr_v_s': _DFR_TXT, 'bay1_dfr_v_t': _DFR_TXT, 'bay1_dfr_v_n': _DFR_TXT,
            'bay1_dfr_i_r': _DFR_TXT, 'bay1_dfr_i_s': _DFR_TXT, 'bay1_dfr_i_t': _DFR_TXT, 'bay1_dfr_i_n': _DFR_TXT,
            'bay1_dfr_hz':  _DFR_TXT,
            # Bay 1 IED
            'bay1_ied_v_r': _DFR_TXT, 'bay1_ied_v_s': _DFR_TXT, 'bay1_ied_v_t': _DFR_TXT, 'bay1_ied_v_n': _DFR_TXT,
            'bay1_ied_i_r': _DFR_TXT, 'bay1_ied_i_s': _DFR_TXT, 'bay1_ied_i_t': _DFR_TXT, 'bay1_ied_i_n': _DFR_TXT,
            'bay1_ied_hz':  _DFR_TXT,
            # Bay 2 DFR
            'bay2_dfr_v_r': _DFR_TXT, 'bay2_dfr_v_s': _DFR_TXT, 'bay2_dfr_v_t': _DFR_TXT, 'bay2_dfr_v_n': _DFR_TXT,
            'bay2_dfr_i_r': _DFR_TXT, 'bay2_dfr_i_s': _DFR_TXT, 'bay2_dfr_i_t': _DFR_TXT, 'bay2_dfr_i_n': _DFR_TXT,
            'bay2_dfr_hz':  _DFR_TXT,
            # Bay 2 IED
            'bay2_ied_v_r': _DFR_TXT, 'bay2_ied_v_s': _DFR_TXT, 'bay2_ied_v_t': _DFR_TXT, 'bay2_ied_v_n': _DFR_TXT,
            'bay2_ied_i_r': _DFR_TXT, 'bay2_ied_i_s': _DFR_TXT, 'bay2_ied_i_t': _DFR_TXT, 'bay2_ied_i_n': _DFR_TXT,
            'bay2_ied_hz':  _DFR_TXT,
        }
