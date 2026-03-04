from django import forms
from .models import Maintenance, MaintenancePLC, MaintenanceRouter, MaintenanceRadio, MaintenanceVoIP, MaintenanceMux, MaintenanceRectifier


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
            'cpu_load':       forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': '0–100'}),
            'memory_usage':   forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': '0–100'}),

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
