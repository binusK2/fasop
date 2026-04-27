from django import forms
from django.contrib.auth.models import User
from devices.models import Device
from .models import SettingRele, GambarDevice


class SettingReleForm(forms.ModelForm):
    class Meta:
        model = SettingRele
        fields = ['device', 'judul', 'tanggal', 'versi',
                  'file_setting', 'keterangan', 'checker', 'tanggal_cek', 'status']
        widgets = {
            'device':      forms.Select(attrs={'class': 'form-select', 'id': 'id_device'}),
            'judul':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misal: Setting Rele OC/EF DS Tello Rev.2'}),
            'tanggal':     forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'versi':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rev.1 / v2.0 (opsional)'}),
            'file_setting': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.xlsx,.xls,.ols,.rdb,.csv,.doc,.docx,.zip',
            }),
            'keterangan':  forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Catatan tambahan…'}),
            'checker':     forms.Select(attrs={'class': 'form-select'}),
            'tanggal_cek': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status':      forms.Select(attrs={'class': 'form-select'}),
        }

    # Nama jenis device yang diizinkan untuk setting rele
    PROSIS_TYPES = [
        'defense scheme', 'rele defense scheme', 'master trip', 'ufls',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['device'].queryset = (
            Device.objects.filter(
                is_deleted=False,
                jenis__name__iregex=r'^(defense scheme|rele defense scheme|master trip|ufls)$',
            )
            .select_related('jenis')
            .order_by('lokasi', 'nama')
        )
        self.fields['device'].empty_label = '— Pilih Perangkat Rele —'
        self.fields['checker'].queryset = (
            User.objects.select_related('profile')
            .order_by('first_name', 'last_name')
        )
        self.fields['checker'].empty_label = '— Pilih Checker —'
        self.fields['checker'].required = False
        self.fields['versi'].required = False
        self.fields['keterangan'].required = False
        self.fields['tanggal_cek'].required = False
        self.fields['file_setting'].required = False


class GambarDeviceForm(forms.ModelForm):
    class Meta:
        model = GambarDevice
        fields = ['device', 'judul', 'tipe', 'tanggal', 'versi',
                  'file_gambar', 'keterangan', 'checker', 'tanggal_cek']
        widgets = {
            'device':     forms.Select(attrs={'class': 'form-select', 'id': 'id_device'}),
            'judul':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misal: Wiring Diagram Panel C DS Tello'}),
            'tipe':       forms.Select(attrs={'class': 'form-select'}),
            'tanggal':    forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'versi':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rev.1 / v2.0 (opsional)'}),
            'file_gambar': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.dwg,.dxf,.svg,.zip',
            }),
            'keterangan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Catatan tambahan…'}),
            'checker':    forms.Select(attrs={'class': 'form-select'}),
            'tanggal_cek': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['device'].queryset = (
            Device.objects.filter(is_deleted=False)
            .select_related('jenis')
            .order_by('lokasi', 'nama')
        )
        self.fields['device'].empty_label = '— Pilih Perangkat —'
        self.fields['checker'].queryset = (
            User.objects.select_related('profile')
            .order_by('first_name', 'last_name')
        )
        self.fields['checker'].empty_label = '— Pilih Checker —'
        self.fields['checker'].required = False
        self.fields['versi'].required = False
        self.fields['keterangan'].required = False
        self.fields['tanggal_cek'].required = False
        self.fields['file_gambar'].required = False
