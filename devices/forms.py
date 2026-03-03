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
        model = Icon
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control'
            })
