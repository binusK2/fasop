from django import forms
from .models import ScadaAvSession, MASTER_CHOICES, INPUT_TYPE_CHOICES, CALC_TYPE_CHOICES

_TXT  = 'form-control'
_SEL  = 'form-select'
_DATE = 'form-control'


class ScadaAvUploadForm(forms.Form):
    nama = forms.CharField(
        label='Nama Sesi',
        max_length=200,
        widget=forms.TextInput(attrs={'class': _TXT, 'placeholder': 'Misal: RTU Availability April 2025'}),
    )
    keterangan = forms.CharField(
        label='Keterangan',
        required=False,
        widget=forms.Textarea(attrs={'class': _TXT, 'rows': 2, 'placeholder': 'Opsional'}),
    )
    periode_awal = forms.DateField(
        label='Periode Awal',
        widget=forms.DateInput(attrs={'class': _DATE, 'type': 'date'}),
    )
    periode_akhir = forms.DateField(
        label='Periode Akhir',
        widget=forms.DateInput(attrs={'class': _DATE, 'type': 'date'}),
    )
    master = forms.ChoiceField(
        label='Sumber Data (Master)',
        choices=MASTER_CHOICES,
        initial='spectrum',
        widget=forms.Select(attrs={'class': _SEL}),
    )
    input_type = forms.ChoiceField(
        label='Tipe File Input',
        choices=INPUT_TYPE_CHOICES,
        initial='soe',
        widget=forms.Select(attrs={'class': _SEL, 'id': 'id_input_type'}),
    )
    calc_type = forms.ChoiceField(
        label='Tipe Kalkulasi',
        choices=CALC_TYPE_CHOICES,
        initial='both',
        widget=forms.Select(attrs={'class': _SEL, 'id': 'id_calc_type'}),
    )
    files = forms.FileField(
        label='File Input',
        widget=forms.FileInput(attrs={
            'class': _TXT,
            'multiple': True,
            'accept': '.xls,.xlsx,.xml',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        awal   = cleaned.get('periode_awal')
        akhir  = cleaned.get('periode_akhir')
        itype  = cleaned.get('input_type')
        ctype  = cleaned.get('calc_type')

        if awal and akhir and awal > akhir:
            raise forms.ValidationError('Periode akhir harus setelah periode awal.')

        # Konsistensi input_type ↔ calc_type
        if itype == 'avrs' and ctype not in ('rtu',):
            cleaned['calc_type'] = 'rtu'
        elif itype == 'avrcd' and ctype not in ('rcd',):
            cleaned['calc_type'] = 'rcd'

        return cleaned
