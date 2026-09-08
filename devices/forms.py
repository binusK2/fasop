from django import forms
from django.db.models import Q
from .models import AsesmenOptik, Device, FiberOptic, Icon

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


class AsesmenOptikForm(forms.ModelForm):
    """Form asesmen FO & aksesoris per tower.

    Ruas FO dipilih dari data Fiber Optic yang sudah ada — GI awal/akhir dan
    tipe kabelnya ikut dari sana, jadi tidak diketik ulang tiap tower.
    """

    class Meta:
        model = AsesmenOptik
        fields = [
            'fiber_optic', 'no_tower', 'upt', 'level_tegangan', 'tipe_tower',
            'jarak_span', 'lintang', 'bujur',
            'fasa_fo', 'tipe_kabel', 'kondisi_fo',
            'tipe_asesoris', 'kondisi_asesoris', 'ukuran_fitmen', 'joint_box',
            'asset', 'area_rintangan', 'keterangan',
            'foto', 'foto_2', 'tanggal', 'petugas',
        ]
        # LANGUAGE_CODE aplikasi ini 'en-us', jadi pesan bawaan Django keluar
        # dalam bahasa Inggris. Menggantinya app-wide menyentuh seluruh FASOP
        # (admin, auth, semua form lain), jadi pesannya di-Indonesia-kan di
        # sini saja — form ini diisi tim lapangan dan vendor.
        error_messages = {
            'fiber_optic':    {'required': 'Pilih ruas FO-nya dulu.'},
            'no_tower':       {'required': 'Nomor tower wajib diisi.'},
            'tanggal':        {'required': 'Tanggal asesmen wajib diisi.',
                               'invalid':  'Tanggal tidak terbaca — pakai pemilih tanggalnya.'},
            'jarak_span':     {'invalid':  'Jarak span harus berupa angka (meter).'},
            'lintang':        {'invalid':  'Lintang harus berupa angka, mis. -5.147889.'},
            'bujur':          {'invalid':  'Bujur harus berupa angka, mis. 119.470535.'},
        }
        widgets = {
            'fiber_optic':      forms.Select(attrs={'class': 'form-select select-cari',
                                                    'data-placeholder': 'Cari ruas FO...'}),
            'no_tower':         forms.TextInput(attrs={'class': 'form-control',
                                                       'placeholder': 'mis. 12'}),
            'upt':              forms.Select(attrs={'class': 'form-select'}),
            'level_tegangan':   forms.Select(attrs={'class': 'form-select'}),
            'tipe_tower':       forms.TextInput(attrs={'class': 'form-control',
                                                       'placeholder': 'mis. AA, BB, Tension'}),
            'jarak_span':       forms.NumberInput(attrs={'class': 'form-control',
                                                         'placeholder': 'meter', 'min': 0}),
            # TextInput, BUKAN NumberInput: <input type="number"> menolak koma
            # desimal dan sepasang koordinat yang ditempel sekaligus — browser
            # malah mengosongkan isiannya tanpa pesan apa pun, sehingga
            # orangnya tidak pernah tahu apa yang salah. Normalisasinya
            # dikerjakan di __init__ lalu divalidasi server.
            'lintang':          forms.TextInput(attrs={'class': 'form-control',
                                                       'inputmode': 'decimal',
                                                       'placeholder': '-5.147889'}),
            'bujur':            forms.TextInput(attrs={'class': 'form-control',
                                                       'inputmode': 'decimal',
                                                       'placeholder': '119.470535'}),
            'fasa_fo':          forms.Select(attrs={'class': 'form-select'}),
            'tipe_kabel':       forms.Select(attrs={'class': 'form-select'}),
            'kondisi_fo':       forms.Select(attrs={'class': 'form-select'}),
            'tipe_asesoris':    forms.Select(attrs={'class': 'form-select'}),
            'kondisi_asesoris': forms.Select(attrs={'class': 'form-select'}),
            'ukuran_fitmen':    forms.TextInput(attrs={'class': 'form-control',
                                                       'placeholder': 'mis. 12 mm'}),
            'joint_box':        forms.Select(attrs={'class': 'form-select'}),
            'asset':            forms.TextInput(attrs={'class': 'form-control',
                                                       'placeholder': 'mis. UP2B'}),
            'area_rintangan':   forms.TextInput(attrs={'class': 'form-control',
                                                       'list': 'daftar-rintangan',
                                                       'placeholder': 'mis. Rumah, Sawah, Sungai'}),
            'keterangan':       forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                                      'placeholder': 'mis. Fitmen berkarat, '
                                                                     'terdapat spare kabel...'}),
            'foto':             forms.ClearableFileInput(attrs={'class': 'form-control',
                                                                'accept': 'image/*'}),
            'foto_2':           forms.ClearableFileInput(attrs={'class': 'form-control',
                                                                'accept': 'image/*'}),
            'tanggal':          forms.DateInput(attrs={'class': 'form-control', 'type': 'date'},
                                                format='%Y-%m-%d'),
            'petugas':          forms.TextInput(attrs={'class': 'form-control',
                                                       'placeholder': 'Nama pelaksana / vendor'}),
        }

    # Presisi kolom lintang/bujur di model. 8 desimal ~ 1 mm di permukaan bumi.
    DESIMAL_KOORDINAT = 8

    @classmethod
    def _bulatkan_koordinat(cls, teks):
        """Potong kelebihan desimal, bukan menolaknya.

        Koordinat salinan dari peta/GPS sering punya 9-10 angka di belakang
        koma. Menolaknya berarti menyuruh orang mengetik ulang angka panjang
        demi selisih di bawah satu milimeter. Yang tidak terbaca sebagai angka
        dibiarkan apa adanya supaya pesan error normalnya tetap muncul.
        """
        from decimal import Decimal, InvalidOperation

        if not teks:
            return teks
        try:
            angka = Decimal(teks)
        except InvalidOperation:
            return teks
        if -angka.as_tuple().exponent <= cls.DESIMAL_KOORDINAT:
            return teks
        return str(angka.quantize(Decimal(1).scaleb(-cls.DESIMAL_KOORDINAT)))

    @staticmethod
    def _pisah_koordinat(teks):
        """('-5.14, 119.47') → ('-5.14', '119.47'); selain itu (teks, None).

        Koordinat lazim disalin sebagai sepasang angka sekaligus — begitu pula
        bentuknya di berkas sumber. Aturannya: dianggap SEPASANG hanya bila ada
        titik desimal di dalamnya. Tanpa syarat itu, '-5,147889' (koma desimal,
        cara mengetik yang wajar di sini) akan salah dibaca sebagai dua angka.
        """
        if ',' not in teks or '.' not in teks:
            return teks, None
        bagian = [b.strip() for b in teks.split(',')]
        if len(bagian) == 2 and all(bagian):
            return bagian[0], bagian[1]
        return teks, None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Rapikan koordinat SEBELUM validasi: di sini nilainya masih string
        # mentah. Sesudah validasi sudah terlambat — isian yang gagal to_python
        # tidak pernah sampai ke cleaned_data.
        if self.is_bound:
            data = self.data.copy()
            lintang = (data.get(self.add_prefix('lintang')) or '').strip()
            bujur   = (data.get(self.add_prefix('bujur')) or '').strip()

            # Tempelan sepasang koordinat selalu dipecah; bagian bujurnya
            # dipakai HANYA bila isian bujur masih kosong. Menimpa angka yang
            # sudah diketik orang lebih buruk daripada mengabaikan setengah
            # tempelan — dan membiarkannya utuh membuat simpannya gagal dengan
            # pesan 'Enter a number' yang tidak menjelaskan apa-apa.
            kiri, kanan = self._pisah_koordinat(lintang)
            if kanan:
                lintang = kiri
                if not bujur:
                    bujur = kanan

            data[self.add_prefix('lintang')] = self._bulatkan_koordinat(
                lintang.replace(',', '.'))
            data[self.add_prefix('bujur')] = self._bulatkan_koordinat(
                bujur.replace(',', '.'))
            self.data = data

        # Label ruas cukup namanya; __str__ FiberOptic mengulang lokasi A/B
        # sehingga di dropdown jadi terlalu panjang untuk dibaca sekilas.
        self.fields['fiber_optic'].queryset = FiberOptic.objects.order_by('nama')
        self.fields['fiber_optic'].label_from_instance = lambda fo: fo.nama
        self.fields['fiber_optic'].empty_label = '— Pilih Ruas FO —'
