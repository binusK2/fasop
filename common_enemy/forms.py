from django import forms
from django.utils import timezone
from .models import CommonEnemy, CommonEnemyLog


class CommonEnemyForm(forms.ModelForm):

    class Meta:
        model  = CommonEnemy
        fields = [
            'kategori', 'sub_kategori', 'tingkat_keparahan', 'sumber_laporan',
            'tanggal_laporan', 'site', 'peralatan',
            'deskripsi_masalah', 'tindak_lanjut', 'catatan_penutupan',
            'foto_eviden1', 'foto_eviden2', 'foto_eviden3',
        ]
        widgets = {
            'kategori':          forms.Select(attrs={'class': 'form-select'}),
            'sub_kategori':      forms.Select(attrs={'class': 'form-select', 'id': 'id_sub_kategori'}),
            'tingkat_keparahan': forms.Select(attrs={'class': 'form-select'}),
            'sumber_laporan':    forms.Select(attrs={'class': 'form-select'}),
            'tanggal_laporan':   forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'},
                format='%Y-%m-%dT%H:%M',
            ),
            'site':               forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misal: GI Tello, GI Maros', 'list': 'site-datalist'}),
            'peralatan':          forms.Select(attrs={'class': 'form-select', 'id': 'id_peralatan'}),
            'deskripsi_masalah':  forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'tindak_lanjut':      forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'catatan_penutupan':  forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'foto_eviden1':       forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'foto_eviden2':       forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'foto_eviden3':       forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tanggal_laporan'].input_formats = ['%Y-%m-%dT%H:%M']
        # Pre-fill datetime-local on edit
        if self.instance and self.instance.pk and self.instance.tanggal_laporan:
            self.initial['tanggal_laporan'] = timezone.localtime(
                self.instance.tanggal_laporan
            ).strftime('%Y-%m-%dT%H:%M')


class CommonEnemyLogForm(forms.ModelForm):

    class Meta:
        model  = CommonEnemyLog
        fields = ['waktu_aksi', 'keterangan']
        widgets = {
            'waktu_aksi':  forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'},
                format='%Y-%m-%dT%H:%M',
            ),
            'keterangan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Keterangan tindakan yang dilakukan...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['waktu_aksi'].input_formats = ['%Y-%m-%dT%H:%M']
