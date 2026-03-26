from django import forms
from .models import Gangguan, GangguanLog
from devices.models import Device
from django.utils import timezone


class GangguanForm(forms.ModelForm):

    class Meta:
        model  = Gangguan
        fields = [
            'tanggal_gangguan', 'site', 'peralatan', 'komponen_rusak',
            'kategori', 'tingkat_keparahan', 'status',
            'executive_summary', 'indikasi_gangguan',
            'penyebab_gangguan', 'dampak_gangguan',
            'catatan_penutupan',
            'foto_eviden1', 'foto_eviden2', 'foto_eviden3',
        ]
        widgets = {
            'tanggal_gangguan': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'},
                format='%Y-%m-%dT%H:%M'
            ),
            'site':               forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. GI Tello, PLTU Barru'}),
            'peralatan':          forms.Select(attrs={'class': 'form-select', 'id': 'id_peralatan'}),
            'komponen_rusak':     forms.Select(attrs={'class': 'form-select', 'id': 'id_komponen_rusak'}),
            'kategori':           forms.Select(attrs={'class': 'form-select'}),
            'tingkat_keparahan':  forms.Select(attrs={'class': 'form-select'}),
            'status':             forms.Select(attrs={'class': 'form-select'}),
            'executive_summary':  forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ringkasan singkat kondisi gangguan…'}),
            'indikasi_gangguan':  forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Gejala atau indikasi yang terdeteksi…'}),
            'penyebab_gangguan':  forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Root cause (isi jika sudah diketahui)…'}),
            'dampak_gangguan':    forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Dampak terhadap layanan / sistem…'}),
            'catatan_penutupan':  forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Diisi saat gangguan dinyatakan selesai…'}),
            'foto_eviden1':       forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'foto_eviden2':       forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'foto_eviden3':       forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tanggal_gangguan'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M']
        self.fields['peralatan'].queryset = Device.objects.filter(is_deleted=False).order_by('lokasi', 'nama')
        self.fields['peralatan'].empty_label = '— Pilih peralatan (opsional) —'
        # Komponen rusak — mulai kosong, diisi via AJAX saat peralatan dipilih
        from devices.models_komponen import DeviceComponent
        if self.instance and self.instance.pk and self.instance.peralatan_id:
            self.fields['komponen_rusak'].queryset = DeviceComponent.objects.filter(
                device_id=self.instance.peralatan_id
            ).order_by('posisi', 'nama')
        else:
            self.fields['komponen_rusak'].queryset = DeviceComponent.objects.none()
        self.fields['komponen_rusak'].empty_label = '— Pilih komponen (opsional) —'
        # Gunakan localtime saat edit agar tidak offset
        if self.instance and self.instance.pk and self.instance.tanggal_gangguan:
            local_dt = timezone.localtime(self.instance.tanggal_gangguan)
            self.initial['tanggal_gangguan'] = local_dt.strftime('%Y-%m-%dT%H:%M')


class GangguanLogForm(forms.ModelForm):
    class Meta:
        model  = GangguanLog
        fields = ['waktu_aksi', 'keterangan']
        widgets = {
            'waktu_aksi':  forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'},
                format='%Y-%m-%dT%H:%M'
            ),
            'keterangan':  forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 2,
                'placeholder': 'Uraikan tindakan yang dilakukan pada jam ini…'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['waktu_aksi'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M']
