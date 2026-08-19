from django.contrib import admin
from .models import (Pembangkit, SnapLive, SnapUnit, SnapFreq, SnapFreqRT, SnapFreqArea,
                     Trafo, SnapTrafo, HopPembangkit, HopSnapshot,
                     PrakiraanBeban)


@admin.register(Pembangkit)
class PembangkitAdmin(admin.ModelAdmin):
    list_display  = ('urutan', 'nama', 'kode', 'jenis', 'supply', 'warna', 'aktif',
                     'data_tidak_sesuai', 'pakai_dmp')
    list_editable = ('urutan', 'jenis', 'supply', 'aktif')
    list_filter   = ('jenis', 'supply', 'aktif', 'data_tidak_sesuai')
    search_fields = ('nama', 'kode')
    list_display_links = ('nama',)
    readonly_fields = ('ditandai_oleh', 'ditandai_pada')
    fieldsets = (
        (None, {'fields': ('nama', 'kode', 'jenis', 'supply', 'warna', 'urutan', 'aktif')}),
        ('Posisi di Peta Pembangkit', {
            'classes': ('collapse',),
            'description': 'Posisi pin pada /opsis/peta/ dalam persen viewBox peta Sulawesi '
                           '(X: 0 = barat, 100 = timur; Y: 0 = utara, 100 = selatan). Kosongkan '
                           'keduanya untuk memakai posisi bawaan yang dicocokkan dari nama '
                           'pembangkit (opsis/hop_map.py). Isi hanya bila pembangkit belum '
                           'terdaftar di sana atau pinnya perlu digeser.',
            'fields': ('peta_x', 'peta_y'),
        }),
        ('Penanda Data Tidak Sesuai', {
            'description': 'Diisi manual (juga bisa dari dashboard OPSIS oleh superuser/Opsis). '
                            'Bila dicentang, kartu pembangkit di dashboard diberi label ketidaksesuaian.',
            'fields': ('data_tidak_sesuai', 'data_keterangan', 'ditandai_oleh', 'ditandai_pada'),
        }),
        ('Sumber Data KIT_REALTIME', {
            'description': 'Kosongkan Kode KIT dan Unit yang Dipakai untuk perilaku default '
                            '(baca semua unit dari baris KIT_REALTIME dengan KIT = Kode). Isi '
                            'keduanya jika satu baris KIT_REALTIME berisi unit milik lebih dari '
                            'satu pembangkit — mis. Pembangkit A pakai UNIT1-6, Pembangkit B pakai '
                            'UNIT7 dari baris KIT yang sama.',
            'fields': ('kode_kit', 'unit_list'),
        }),
        ('Daya Mampu — dbo.KIT_DMP', {
            'description': 'Isi nama kolom yang menyimpan DMN dan DMP pada dbo.KIT_DMP. '
                           'Kolom Kunci global diatur lewat MSSQL_DMP_KEYCOL (default: KIT). '
                           'Nilai Kunci dikosongkan untuk memakai Kode KIT/Kode pembangkit. Pisahkan '
                           'beberapa nilai dengan koma untuk menjumlahkan DMN/DMP, mis. POSO2A_U1,POSO2A_U2. '
                           'Gunakan python manage.py probe_dmp untuk melihat struktur tabel.',
            'fields': ('dmp_key', 'dmp_kolom_dmn', 'dmp_kolom_dmp'),
        }),
        ('Tag MSSQL', {
            'description': 'Isi tag/kolom sesuai struktur tabel historian di MSSQL.',
            'fields': ('tag_frekuensi', 'tag_mw', 'tag_mvar'),
        }),
    )

    @admin.display(boolean=True, description='DMN/DMP')
    def pakai_dmp(self, obj):
        return obj.pakai_dmp()


@admin.register(Trafo)
class TrafoAdmin(admin.ModelAdmin):
    list_display   = ('urutan', 'site', 'bay', 'aktif', 'pakai_override')
    list_editable  = ('urutan', 'aktif')
    list_filter    = ('site', 'aktif')
    list_display_links = ('bay',)
    search_fields  = ('site', 'bay')
    fieldsets = (
        (None, {'fields': ('site', 'bay', 'urutan', 'aktif')}),
        ('Sumber Data Pengganti', {
            'description': 'Isi hanya jika titik trafo ini berhenti terupdate di ALL_TRANS_DATA '
                            'dan datanya harus dibaca dari tabel MSSQL lain (mis. IBT GITET Wotu). '
                            'Kosongkan Tabel Sumber Pengganti untuk kembali memakai ALL_TRANS_DATA. '
                            'Mode Baris: satu titik per baris, kolom kunci dicocokkan dengan Tag P/Q/V/I '
                            'lalu nilainya diambil dari Kolom Nilai. Mode Kolom: satu baris tabel '
                            'berisi kolom P/Q/V/I langsung, dipilih lewat Kolom Kunci = Nilai Kunci.',
            'fields': ('sumber_tabel', 'sumber_mode',
                       'sumber_filter_kolom', 'sumber_filter_nilai', 'sumber_kolom_nilai',
                       'sumber_p', 'sumber_q', 'sumber_v', 'sumber_i'),
        }),
    )

    @admin.display(boolean=True, description='Override')
    def pakai_override(self, obj):
        return obj.pakai_override


@admin.register(SnapFreq)
class SnapFreqAdmin(admin.ModelAdmin):
    list_display   = ('waktu', 'hz')
    date_hierarchy = 'waktu'
    readonly_fields = ('waktu', 'hz')
    ordering       = ('-waktu',)


@admin.register(SnapFreqRT)
class SnapFreqRTAdmin(admin.ModelAdmin):
    list_display   = ('waktu', 'hz')
    date_hierarchy = 'waktu'
    readonly_fields = ('waktu', 'hz')
    ordering       = ('-waktu',)


@admin.register(SnapFreqArea)
class SnapFreqAreaAdmin(admin.ModelAdmin):
    list_display   = ('waktu', 'area', 'hz')
    list_filter    = ('area',)
    date_hierarchy = 'waktu'
    readonly_fields = ('area', 'waktu', 'hz')
    ordering       = ('-waktu',)


@admin.register(SnapTrafo)
class SnapTrafoAdmin(admin.ModelAdmin):
    list_display   = ('trafo', 'waktu', 'p', 'dicatat_pada')
    list_filter    = ('trafo__site',)
    date_hierarchy = 'waktu'
    readonly_fields = ('trafo', 'waktu', 'p', 'dicatat_pada')
    ordering       = ('-waktu',)


class SnapUnitInline(admin.TabularInline):
    model = SnapUnit
    extra = 0
    readonly_fields = ('nama', 'mw', 'mvar')
    can_delete = False


@admin.register(SnapLive)
class SnapLiveAdmin(admin.ModelAdmin):
    list_display   = ('pembangkit', 'waktu', 'mw', 'mvar', 'frekuensi', 'dicatat_pada')
    list_filter    = ('pembangkit',)
    date_hierarchy = 'waktu'
    readonly_fields = ('pembangkit', 'waktu', 'mw', 'mvar', 'frekuensi', 'dicatat_pada')
    inlines        = [SnapUnitInline]
    ordering       = ('-waktu',)


class HopSnapshotInline(admin.TabularInline):
    model = HopSnapshot
    extra = 0
    fields = ('tanggal', 'hop')
    ordering = ('-tanggal',)


@admin.register(HopPembangkit)
class HopPembangkitAdmin(admin.ModelAdmin):
    list_display  = ('urutan', 'nama', 'kategori', 'sistem', 'aset', 'dmn_mw',
                     'hop_terakhir', 'aktif')
    list_editable = ('urutan', 'aktif')
    list_filter   = ('kategori', 'sistem', 'aset', 'aktif')
    search_fields = ('nama',)
    list_display_links = ('nama',)
    inlines = (HopSnapshotInline,)


@admin.register(HopSnapshot)
class HopSnapshotAdmin(admin.ModelAdmin):
    list_display   = ('pembangkit', 'tanggal', 'hop')
    list_filter    = ('pembangkit__kategori', 'pembangkit__sistem')
    date_hierarchy = 'tanggal'
    search_fields  = ('pembangkit__nama',)
    ordering       = ('-tanggal',)


@admin.register(PrakiraanBeban)
class PrakiraanBebanAdmin(admin.ModelAdmin):
    """
    Kurva prakiraan beban dari spreadsheet. Normalnya diisi n8n lewat
    POST /api/v1/prakiraan-beban/ — admin ini untuk memeriksa/menambal satu
    titik kalau ada slot yang salah, bukan jalur input utama.
    """
    list_display   = ('tanggal', 'jam', 'mw', 'sumber', 'diperbarui')
    list_filter    = ('sumber',)
    date_hierarchy = 'tanggal'
    ordering       = ('-tanggal', 'menit')
