from django.contrib import admin, messages
from . import mssql
from .models import (Pembangkit, SnapLive, SnapUnit, SnapFreq, SnapFreqRT, SnapFreqArea,
                     Trafo, SnapTrafo, HopPembangkit, HopSnapshot,
                     PrakiraanBeban, ModePemeliharaan, KelompokPeta,
                     KolomEWS, TitikEWS, KartuPadam)


@admin.register(KelompokPeta)
class KelompokPetaAdmin(admin.ModelAdmin):
    """Ikon gabungan di Peta Pembangkit — biasanya diatur lewat mode Atur Peta
    di halaman /opsis/peta/, tapi bisa juga dari sini."""
    list_display  = ('nama', 'jenis', 'jumlah_anggota', 'tampil_di_peta', 'peta_x', 'peta_y')
    list_editable = ('jenis', 'tampil_di_peta')
    list_filter   = ('jenis', 'tampil_di_peta')
    search_fields = ('nama', 'keterangan')
    filter_horizontal = ('anggota',)
    fieldsets = (
        (None, {
            'description': 'Pembangkit yang menjadi anggota kelompok yang tampil tidak lagi '
                           'digambar sebagai ikon sendiri di peta — dayanya sudah terhitung '
                           'di ikon kelompok. Semuanya tetap ada di tabel daya.',
            'fields': ('nama', 'keterangan', 'jenis', 'anggota'),
        }),
        ('Posisi di Peta', {'fields': ('tampil_di_peta', 'peta_x', 'peta_y')}),
    )

    @admin.display(description='Anggota')
    def jumlah_anggota(self, obj):
        return obj.anggota.count()


@admin.register(ModePemeliharaan)
class ModePemeliharaanAdmin(admin.ModelAdmin):
    """
    Sakelar tunggal "OPSIS sedang dipelihara" — hanya ada satu baris, jadi
    tombol Tambah/Hapus dimatikan dan daftar langsung membuka baris itu.
    """
    list_display    = ('status_ringkas', 'judul', 'perkiraan_selesai', 'diubah_oleh', 'diubah_pada')
    readonly_fields = ('diubah_oleh', 'diubah_pada')
    fieldsets = (
        (None, {
            'description': 'Bila diaktifkan, SEMUA halaman /opsis/ (dashboard, peta, UP2D, '
                           'HOP, dsb.) diganti halaman pemeliharaan sampai sakelar ini '
                           'dimatikan lagi. Cron pengumpul data OPSIS tidak terpengaruh. '
                           'Perubahan berlaku paling lambat beberapa detik di semua worker.',
            'fields': ('aktif', 'boleh_superuser'),
        }),
        ('Isi Halaman Pemeliharaan', {'fields': ('judul', 'pesan', 'perkiraan_selesai')}),
        ('Riwayat', {'fields': ('diubah_oleh', 'diubah_pada')}),
    )

    @admin.display(description='Status', boolean=True)
    def status_ringkas(self, obj):
        return obj.aktif

    def has_add_permission(self, request):
        # Baris tunggal: dibuat otomatis oleh changelist_view di bawah.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        ModePemeliharaan.ambil()      # pastikan barisnya ada sebelum daftar dirender
        return super().changelist_view(request, extra_context)

    def save_model(self, request, obj, form, change):
        obj.diubah_oleh = request.user
        super().save_model(request, obj, form, change)


@admin.register(KartuPadam)
class KartuPadamAdmin(admin.ModelAdmin):
    """
    Pengaturan kartu Total Padam di dashboard OPSIS — hanya ada satu baris,
    jadi tombol Tambah/Hapus dimatikan dan daftar langsung membuka baris itu.

    Dua aksi di bawah menjawab "kenapa kartu saya kosong" tanpa membuka log
    server: satu memperlihatkan kolom tabel sumbernya, satu lagi membaca
    angkanya sekarang juga.
    """
    list_display    = ('status_ringkas', 'judul', 'agregasi', 'sumber_tabel',
                       'diubah_oleh', 'diubah_pada')
    readonly_fields = ('diubah_oleh', 'diubah_pada')
    actions         = ('uji_baca_mssql', 'lihat_kolom_tabel')
    fieldsets = (
        (None, {
            'description': 'Kartu Total Padam muncul di baris kartu beban dashboard OPSIS. '
                           'Mematikan sakelar ini menyembunyikan kartunya dari semua layar '
                           'dalam beberapa detik — layar monitoring tidak perlu di-refresh.',
            'fields': ('aktif',),
        }),
        ('Tampilan Kartu', {'fields': ('judul', 'satuan', 'desimal', 'warna', 'keterangan')}),
        ('Sumber Data (MSSQL)', {
            'description': 'Arahkan kartu ini ke angkanya di historian. Contoh: Tabel Sumber '
                           '<code>dbo.PADAM_RT</code>, Kolom Nilai <code>VALUE</code>, Kolom '
                           'Kunci <code>ANALOG</code>, Nilai Kunci '
                           '<code>PADAM_MKS,PADAM_KDI</code>. Kolom Kunci yang dikosongkan '
                           'berarti seluruh isi tabel dipakai. Belum tahu nama kolomnya? '
                           'Pakai aksi "Lihat kolom tabel sumber" di daftar, atau jalankan '
                           '<code>python manage.py probe_tabel_ews &lt;tabel&gt;</code>.',
            'fields': ('agregasi', 'sumber_tabel', 'sumber_kolom_nilai',
                       'sumber_kolom_kunci', 'sumber_nilai_kunci', 'faktor_skala'),
        }),
        ('Riwayat', {'fields': ('diubah_oleh', 'diubah_pada')}),
    )

    @admin.display(description='Tampil', boolean=True)
    def status_ringkas(self, obj):
        return obj.aktif

    def has_add_permission(self, request):
        # Baris tunggal: dibuat otomatis oleh changelist_view di bawah.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        KartuPadam.ambil()            # pastikan barisnya ada sebelum daftar dirender
        return super().changelist_view(request, extra_context)

    def save_model(self, request, obj, form, change):
        obj.diubah_oleh = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Uji baca nilai dari MSSQL')
    def uji_baca_mssql(self, request, queryset):
        """Baca angka kartu sekarang juga, dengan pengaturan yang tersimpan."""
        obj = queryset.first() or KartuPadam.ambil()
        if not obj.pakai_sumber:
            self.message_user(request, 'Tabel Sumber belum diisi.', level=messages.WARNING)
            return
        hasil = mssql.get_total_padam(obj.spesifikasi_sumber())
        if hasil['error']:
            self.message_user(request, f"{obj.sumber_tabel}: {hasil['error']}",
                              level=messages.ERROR)
        elif hasil['nilai'] is None:
            self.message_user(
                request,
                f'{obj.sumber_tabel}: tidak ada baris yang cocok — cek Kolom Kunci / '
                f'Nilai Kunci.', level=messages.WARNING)
        else:
            self.message_user(
                request,
                f"{obj.judul}: {hasil['nilai']:g} {obj.satuan} "
                f"(dari {hasil['baris']} baris {obj.sumber_tabel}).",
                level=messages.SUCCESS)

    @admin.action(description='Lihat kolom tabel sumber')
    def lihat_kolom_tabel(self, request, queryset):
        """Daftar kolom tabel sumber, untuk mengisi Kolom Nilai/Kolom Kunci."""
        obj = queryset.first() or KartuPadam.ambil()
        if not obj.pakai_sumber:
            self.message_user(request, 'Tabel Sumber belum diisi.', level=messages.WARNING)
            return
        hasil = mssql.probe_tabel(obj.sumber_tabel)
        if hasil.get('error'):
            self.message_user(request, f"{hasil['tabel']}: {hasil['error']}",
                              level=messages.ERROR)
            return
        self.message_user(
            request,
            f"{hasil['tabel']} — kolom: {', '.join(hasil['kolom']) or '(kosong)'}",
            level=messages.INFO)


@admin.register(Pembangkit)
class PembangkitAdmin(admin.ModelAdmin):
    list_display  = ('urutan', 'nama', 'kode', 'jenis', 'supply', 'warna', 'aktif',
                     'tampil_di_peta', 'data_tidak_sesuai', 'pakai_dmp')
    list_editable = ('urutan', 'jenis', 'supply', 'aktif', 'tampil_di_peta')
    list_filter   = ('jenis', 'supply', 'aktif', 'tampil_di_peta', 'data_tidak_sesuai')
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
                           'terdaftar di sana atau pinnya perlu digeser. Mengosongkan '
                           'koordinat TIDAK menyembunyikan ikon — untuk itu hilangkan '
                           'centang "Tampilkan Ikon di Peta".',
            'fields': ('tampil_di_peta', 'peta_x', 'peta_y'),
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


# ── EWS Defense Scheme ───────────────────────────────────────────────────────

@admin.register(KolomEWS)
class KolomEWSAdmin(admin.ModelAdmin):
    """Kolom parameter di halaman /opsis/ews/ — judul dan jumlahnya diatur di sini."""
    list_display  = ('urutan', 'nama', 'warna', 'jumlah_titik', 'aktif')
    list_editable = ('urutan', 'aktif')
    list_display_links = ('nama',)
    search_fields = ('nama',)

    @admin.display(description='Jumlah Titik')
    def jumlah_titik(self, obj):
        return obj.titik.count()


@admin.register(TitikEWS)
class TitikEWSAdmin(admin.ModelAdmin):
    """
    Pendaftaran peralatan EWS: identitas skema, ambang setting relenya, dan
    tabel/kolom MSSQL tempat nilai ukurnya dibaca. Tidak butuh migrasi —
    menambah baris di sini langsung muncul di /opsis/ews/.
    """
    list_display  = ('nama', 'skema', 'sistem', 'kolom', 'setting_tampil',
                     'status_skema', 'sumber_siap', 'urutan', 'aktif')
    list_editable = ('urutan', 'aktif')
    list_display_links = ('nama',)
    list_filter   = ('kolom', 'besaran', 'skema', 'status_skema', 'sistem', 'aktif')
    search_fields = ('nama', 'kode', 'nomor', 'target')
    actions       = ('uji_baca_mssql', 'lihat_kolom_tabel')

    fieldsets = (
        ('Identitas Skema', {
            'fields': ('kolom', 'nama', 'skema', ('sistem', 'subsistem'),
                       ('nomor', 'kode'), 'target', 'time_delay',
                       'status_skema', 'catatan', ('urutan', 'aktif')),
        }),
        ('Ambang Setting Rele', {
            'description': 'Angka dari berkas Defense Scheme. Setting yang dikosongkan '
                           'membuat kartu ditandai "setting belum diisi" — margin tidak '
                           'dihitung, tapi titiknya tetap tampil.',
            'fields': ('besaran', 'satuan', 'nominal', 'setting', 'arah', 'ambang_waspada'),
        }),
        ('Sumber Data Realtime (MSSQL)', {
            'classes': ('collapse',),
            'description': 'Arahkan titik ini ke nilai ukurnya di historian. Contoh: '
                           'Tabel Sumber <code>dbo.KIT_REALTIME</code>, Kolom Nilai '
                           '<code>VALUE</code>, Kolom Kunci <code>ANALOG</code>, Nilai Kunci '
                           '<code>FREQ_MKS</code>. Belum tahu nama kolomnya? Pakai aksi '
                           '"Lihat kolom tabel sumber" di daftar, atau jalankan '
                           '<code>python manage.py probe_tabel_ews &lt;tabel&gt;</code>. '
                           'Kosongkan Tabel Sumber bila titik ini memang belum termonitor.',
            'fields': ('sumber_tabel', 'sumber_kolom_nilai',
                       'sumber_kolom_kunci', 'sumber_nilai_kunci', 'faktor_skala'),
        }),
    )

    @admin.display(description='Setting')
    def setting_tampil(self, obj):
        if obj.setting is None:
            return '—'
        return f'{obj.setting:g} {obj.satuan_tampil}'

    @admin.display(boolean=True, description='Sumber MSSQL')
    def sumber_siap(self, obj):
        return obj.pakai_sumber

    @admin.action(description='Uji baca nilai dari MSSQL')
    def uji_baca_mssql(self, request, queryset):
        """
        Baca nilai titik terpilih sekarang juga. Ini yang menjawab "kenapa kartu
        saya kosong" tanpa harus membuka log server.
        """
        titik = list(queryset)
        specs = [s for s in (t.spesifikasi_sumber() for t in titik) if s]
        if not specs:
            self.message_user(request, 'Tidak ada titik terpilih yang sudah diisi '
                                       'Tabel Sumber.', level=messages.WARNING)
            return
        nilai = mssql.get_nilai_ews(specs)
        for t in titik:
            if not t.pakai_sumber:
                self.message_user(request, f'{t.nama}: belum diarahkan ke tabel MSSQL.',
                                  level=messages.WARNING)
                continue
            v = nilai.get(t.pk)
            if v is None:
                self.message_user(
                    request,
                    f'{t.nama}: nilai tidak terbaca dari {t.sumber_tabel} '
                    f'(cek nama kolom/nilai kunci, atau koneksi MSSQL).',
                    level=messages.ERROR)
            else:
                self.message_user(
                    request,
                    f'{t.nama}: {v:g} {t.satuan_tampil} — status {t.status(v)}.',
                    level=messages.SUCCESS)

    @admin.action(description='Lihat kolom tabel sumber')
    def lihat_kolom_tabel(self, request, queryset):
        """Daftar kolom tabel sumber dari baris terpilih pertama yang sudah diisi."""
        titik = next((t for t in queryset if t.pakai_sumber), None)
        if titik is None:
            self.message_user(request, 'Pilih minimal satu titik yang sudah diisi '
                                       'Tabel Sumber.', level=messages.WARNING)
            return
        hasil = mssql.probe_tabel(titik.sumber_tabel)
        if hasil.get('error'):
            self.message_user(request, f"{hasil['tabel']}: {hasil['error']}",
                              level=messages.ERROR)
            return
        self.message_user(
            request,
            f"{hasil['tabel']} — kolom: {', '.join(hasil['kolom']) or '(kosong)'}",
            level=messages.INFO)
