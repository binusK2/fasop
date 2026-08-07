from django import forms
from django.db.models import Q
from .models import Device, Icon

class DeviceForm(forms.ModelForm):
    ip_address = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kosongkan jika tidak ada'}),
        label='IP Address',
    )

    tahun_operasi = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'contoh: 2019',
            'min': '1990',
            'max': '2100',
        }),
        label='Tahun Operasi',
    )

    asset_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kosongkan jika tidak ada',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
        }),
        label='Asset ID',
        help_text='Nomor identitas aset (angka).',
    )

    class Meta:
        model = Device
        fields = '__all__'
        exclude = ['is_deleted', 'deleted_by']
        widgets = {
            'status_aset': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_asset_id(self):
        val = (self.cleaned_data.get('asset_id') or '').strip()
        if val and not val.isdigit():
            raise forms.ValidationError('Asset ID hanya boleh berisi angka.')
        return val or None

    def clean_status_aset(self):
        val = (self.cleaned_data.get('status_aset') or '').strip()
        if not val:
            raise forms.ValidationError('Pilih status aset atau isi manual.')
        return val

    def clean_ip_address(self):
        ip = self.cleaned_data.get('ip_address', '').strip()
        if not ip or ip == '-':
            return None
        from django.core.validators import validate_ipv46_address
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_ipv46_address(ip)
        except DjangoValidationError:
            raise forms.ValidationError('Masukkan alamat IP yang valid (contoh: 192.168.1.1)')
        return ip

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('status_aset') == 'LAINNYA':
            manual = (cleaned.get('status_aset_lainnya') or '').strip()
            if not manual:
                self.add_error('status_aset_lainnya', 'Isi status aset manual atau pilih dari daftar.')
            else:
                cleaned['status_aset'] = manual

        ip     = cleaned.get('ip_address')
        lokasi = cleaned.get('lokasi')
        if ip and lokasi:
            qs = Device.objects.filter(ip_address=ip, lokasi__iexact=lokasi)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    'ip_address',
                    f'IP {ip} sudah digunakan perangkat lain di lokasi {lokasi.upper()}.'
                )
        return cleaned

    def clean_lokasi(self):
        lokasi = self.cleaned_data.get('lokasi')
        if lokasi:
            return lokasi.strip().upper()
        return lokasi
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control'
            })

        self.fields['foto'].widget.attrs.update({'class': 'form-control'})
        self.fields['foto2'].widget.attrs.update({'class': 'form-control'})

        aset_choices = list(Device.ASET_CHOICES) + [('LAINNYA', 'Lainnya (isi manual)')]
        status_initial = 'UP2B'
        lain_initial = ''
        if self.instance and self.instance.pk:
            cur = self.instance.status_aset
            valid_vals = [c[0] for c in aset_choices]
            if cur and cur not in valid_vals:
                status_initial = 'LAINNYA'
                lain_initial = cur
            else:
                status_initial = cur

        self.fields['status_aset'] = forms.ChoiceField(
            choices=aset_choices,
            initial=status_initial,
            widget=forms.Select(attrs={'class': 'form-select'}),
            label='Status Aset',
        )
        self.fields['status_aset_lainnya'] = forms.CharField(
            required=False,
            initial=lain_initial,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tulis status aset manual',
            }),
            label='',
        )

        self.fields['asset_id'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Kosongkan jika tidak ada',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
        })

        # host: tampilkan server fisik yang bisa menjadi host VM (bukan VM itu sendiri)
        self.fields['host'].required = False
        self.fields['host'].queryset = Device.objects.filter(
            Q(jenis__name__icontains='master station') |
            Q(jenis__name__icontains='server scada'),   # backward compat nama lama
            is_deleted=False,
            host__isnull=True,
        )
        self.fields['host'].widget.attrs.update({'class': 'form-select'})
        self.fields['host'].empty_label = '— Bukan VM (perangkat fisik) —'

    

class IconForm(forms.ModelForm):

    class Meta:
        model  = Icon
        fields = '__all__'
        widgets = {
            'name':                forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. UP2B Metronet SCADA'}),
            'nama_layanan':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Metronet SCADA'}),
            'lokasi_layanan':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. GI Tello, PLTU Barru'}),
            'bandwidth':           forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2 Mbps, 10 Mbps, 1 Gbps'}),
            'SID1':                forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 410120200083'}),
            'SID2':                forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 01000037504'}),
            'kontrak':             forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. UP2B, UP3, PLN'}),
            'kondisi_operasional': forms.Select(
                choices=[
                    ('', '— Pilih Kondisi —'),
                    ('Operasi Baik', 'Operasi Baik'),
                    ('Gangguan', 'Gangguan'),
                    ('Tidak Operasi', 'Tidak Operasi'),
                    ('Dalam Pemeliharaan', 'Dalam Pemeliharaan'),
                ],
                attrs={'class': 'form-select'}
            ),
            'keterangan': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Deskripsi layanan, rute, atau catatan lainnya...'}),
        }