from django import forms
from .models import Device, Icon

class DeviceForm(forms.ModelForm):

    class Meta:
        model = Device
        fields = '__all__'
        exclude = ['is_deleted', 'deleted_by']

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
