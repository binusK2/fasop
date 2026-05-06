from django import forms
from django.contrib.auth.models import User
from devices.models import Device
from .models import SettingRele, GambarDevice


class SettingReleForm(forms.ModelForm):
    class Meta:
        model = SettingRele
        fields = ['device', 'judul', 'tipe_setting', 'penyulang_bay',
                  'tanggal', 'versi', 'file_setting', 'keterangan',
                  'checker', 'tanggal_cek', 'status']
        widgets = {
            'device':        forms.Select(attrs={'class': 'form-select', 'id': 'id_device'}),
            'judul':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misal: Setting Rele OC/EF DS Tello Rev.2'}),
            'tipe_setting':  forms.Select(attrs={'class': 'form-select'}),
            'penyulang_bay': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misal: Penyulang Tello / Bay 1'}),
            'tanggal':       forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'versi':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rev.1 / v2.0'}),
            'file_setting':  forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.xlsx,.xls,.ols,.rdb,.csv,.doc,.docx,.zip',
                'id': 'id_file_setting',
            }),
            'keterangan':    forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Catatan tambahan, acuan, referensi dokumen…'}),
            'checker':       forms.Select(attrs={'class': 'form-select'}),
            'tanggal_cek':   forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status':        forms.Select(attrs={'class': 'form-select'}),
        }

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
        self.fields['tipe_setting'].empty_label = '— Pilih Tipe Setting —'
        self.fields['checker'].queryset = (
            User.objects.select_related('profile')
            .order_by('first_name', 'last_name')
        )
        self.fields['checker'].empty_label = '— Pilih Checker —'
        for f in ('checker', 'versi', 'keterangan', 'tanggal_cek',
                  'file_setting', 'tipe_setting', 'penyulang_bay'):
            self.fields[f].required = False


class GambarDeviceForm(forms.ModelForm):
    class Meta:
        model = GambarDevice
        fields = ['device', 'judul', 'tipe', 'nomor_gambar', 'skala',
                  'tanggal', 'versi', 'file_gambar', 'keterangan',
                  'checker', 'tanggal_cek']
        widgets = {
            'device':       forms.Select(attrs={'class': 'form-select', 'id': 'id_device'}),
            'judul':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misal: Wiring Diagram Panel C DS Tello'}),
            'tipe':         forms.Select(attrs={'class': 'form-select'}),
            'nomor_gambar': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misal: DS-TELLO-WD-001'}),
            'skala':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misal: 1:100 / NTS / A3'}),
            'tanggal':      forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'versi':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rev.1 / v2.0'}),
            'file_gambar':  forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.dwg,.dxf,.svg,.zip',
                'id': 'id_file_gambar',
            }),
            'keterangan':   forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Catatan tambahan, sumber gambar, referensi…'}),
            'checker':      forms.Select(attrs={'class': 'form-select'}),
            'tanggal_cek':  forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
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
        for f in ('checker', 'versi', 'keterangan', 'tanggal_cek',
                  'file_gambar', 'nomor_gambar', 'skala'):
            self.fields[f].required = False
