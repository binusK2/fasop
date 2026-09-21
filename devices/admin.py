from django.contrib import admin
from .models import (AsesmenOptik, Device, DeviceType, SiteLocation, ULTG,
                     KomponenRusak, Branch, FotoLapangan)
from .models_komponen import (
    GrupTipeKomponen, TipeKomponen,
    DeviceComponent,
    SpecRouterPort, SpecMuxSlot, SpecPSU,
    SpecRectifierModul, SpecBattery, SpecBatteryCell,
    SpecRadioModul, SpecPLCModul,
)

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['nama', 'jenis', 'merk', 'lokasi', 'status_operasi', 'is_deleted', 'deleted_by']
    search_fields = ['nama', 'merk', 'serial_number', 'lokasi']
    list_filter = ['jenis', 'status_operasi', 'is_deleted']
    actions = ['pulihkan_data']

    @admin.action(description='Pulihkan data yang terhapus (batalkan soft-delete)')
    def pulihkan_data(self, request, queryset):
        n = queryset.filter(is_deleted=True).update(is_deleted=False, deleted_by=None)
        self.message_user(request, f'{n} perangkat dipulihkan.')

admin.site.register(DeviceType)


@admin.register(FotoLapangan)
class FotoLapanganAdmin(admin.ModelAdmin):
    list_display = ['id', 'folder', 'status', 'assigned_device', 'assigned_as', 'taken_at', 'uploaded_by', 'uploaded_at']
    list_filter = ['status', 'folder', 'assigned_as', 'uploaded_at']
    search_fields = ['folder', 'caption', 'original_name', 'assigned_device__nama']
    readonly_fields = ['uploaded_at', 'assigned_at']


# ── Tipe Komponen (dikelola via Admin) ───────────────────────
class TipeKomponenInline(admin.TabularInline):
    model = TipeKomponen
    extra = 1
    fields = ['kode', 'nama', 'urutan']

@admin.register(GrupTipeKomponen)
class GrupTipeKomponenAdmin(admin.ModelAdmin):
    list_display = ['nama', 'urutan', 'jumlah_tipe']
    list_editable = ['urutan']
    inlines = [TipeKomponenInline]

    def jumlah_tipe(self, obj):
        return obj.tipe_komponen.count()
    jumlah_tipe.short_description = 'Jumlah Tipe'

@admin.register(TipeKomponen)
class TipeKomponenAdmin(admin.ModelAdmin):
    list_display = ['kode', 'nama', 'grup', 'urutan']
    list_filter = ['grup']
    list_editable = ['nama', 'grup', 'urutan']
    search_fields = ['kode', 'nama']


# ── Inline Spec Models ──────────────────────────────────────
class SpecRouterPortInline(admin.StackedInline):
    model = SpecRouterPort
    extra = 0
    max_num = 1

class SpecMuxSlotInline(admin.StackedInline):
    model = SpecMuxSlot
    extra = 0
    max_num = 1

class SpecPSUInline(admin.StackedInline):
    model = SpecPSU
    extra = 0
    max_num = 1

class SpecRectifierModulInline(admin.StackedInline):
    model = SpecRectifierModul
    extra = 0
    max_num = 1

class SpecBatteryInline(admin.StackedInline):
    model = SpecBattery
    extra = 0
    max_num = 1

class SpecBatteryCellInline(admin.StackedInline):
    model = SpecBatteryCell
    extra = 0
    max_num = 1

class SpecRadioModulInline(admin.StackedInline):
    model = SpecRadioModul
    extra = 0
    max_num = 1

class SpecPLCModulInline(admin.StackedInline):
    model = SpecPLCModul
    extra = 0
    max_num = 1


class SubKomponenInline(admin.TabularInline):
    """Inline untuk sub-komponen (child components)."""
    model = DeviceComponent
    fk_name = 'parent'
    extra = 0
    fields = ['nama', 'tipe_komponen', 'posisi', 'status', 'serial_number']
    verbose_name = 'Sub-Komponen'
    verbose_name_plural = 'Sub-Komponen'


@admin.register(DeviceComponent)
class DeviceComponentAdmin(admin.ModelAdmin):
    list_display = [
        'nama', 'device', 'tipe_komponen', 'posisi',
        'status', 'merk', 'serial_number',
    ]
    list_filter = ['tipe_komponen', 'status', 'device__jenis']
    search_fields = ['nama', 'serial_number', 'device__nama', 'merk']
    autocomplete_fields = ['device', 'parent']
    list_editable = ['status']

    inlines = [
        SubKomponenInline,
        SpecRouterPortInline,
        SpecMuxSlotInline,
        SpecPSUInline,
        SpecRectifierModulInline,
        SpecBatteryInline,
        SpecBatteryCellInline,
        SpecRadioModulInline,
        SpecPLCModulInline,
    ]

    fieldsets = (
        ('Relasi', {
            'fields': ('device', 'parent'),
        }),
        ('Identitas Komponen', {
            'fields': ('nama', 'tipe_komponen', 'posisi', 'merk', 'model', 'serial_number'),
        }),
        ('Status & Riwayat', {
            'fields': ('status', 'keterangan', 'tanggal_pasang', 'tanggal_ganti'),
        }),
    )

@admin.register(ULTG)
class ULTGAdmin(admin.ModelAdmin):
    list_display   = ('nama', 'jumlah_lokasi', 'jumlah_operator')
    search_fields  = ('nama',)
    filter_horizontal = ('lokasi',)

    def jumlah_lokasi(self, obj):
        return obj.lokasi.count()
    jumlah_lokasi.short_description = 'Jumlah Lokasi/GI'

    def jumlah_operator(self, obj):
        return obj.operators.count()
    jumlah_operator.short_description = 'Jumlah Operator'

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'lokasi':
            obj_id = request.resolver_match.kwargs.get('object_id')
            # Sembunyikan lokasi yang sudah di-assign ke ULTG lain
            assigned_to_other = SiteLocation.objects.filter(ultg__isnull=False)
            if obj_id:
                assigned_to_other = assigned_to_other.exclude(ultg__id=obj_id)
            kwargs['queryset'] = SiteLocation.objects.exclude(
                pk__in=assigned_to_other.values('pk')
            ).order_by('nama')
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display   = ['nama', 'kode', 'jumlah_lokasi', 'keterangan']
    search_fields  = ['nama', 'kode']
    list_display_links = ['nama']

    def jumlah_lokasi(self, obj):
        return obj.lokasi_set.count()
    jumlah_lokasi.short_description = 'Jumlah Lokasi'


@admin.register(SiteLocation)
class SiteLocationAdmin(admin.ModelAdmin):
    list_display       = ['nama', 'branch', 'latitude', 'longitude', 'has_coords', 'keterangan']
    list_filter        = ['branch']
    search_fields      = ['nama']
    list_display_links = ['nama']
    list_editable      = ['branch']
    autocomplete_fields = []

    def has_coords(self, obj):
        return obj.has_coords
    has_coords.boolean = True
    has_coords.short_description = 'Ada Koordinat'


from .models import UserProfile
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'role', 'ultg', 'force_password_change', 'has_signature']
    list_editable = ['role', 'force_password_change']
    list_filter   = ['role', 'ultg']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    autocomplete_fields = []

    def has_signature(self, obj): return bool(obj.signature)
    has_signature.boolean = True

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@admin.register(KomponenRusak)
class KomponenRusakAdmin(admin.ModelAdmin):
    list_display  = ['tanggal_rusak', 'device', 'nama_komponen', 'merk', 'tipe', 'disimpan_di', 'created_by']
    list_filter   = ['tanggal_rusak', 'device__lokasi']
    search_fields = ['nama_komponen', 'merk', 'tipe', 'disimpan_di', 'device__nama']
    date_hierarchy = 'tanggal_rusak'


from .models import DeviceLink, ItemBongkar

@admin.register(ItemBongkar)
class ItemBongkarAdmin(admin.ModelAdmin):
    list_display   = ['device_asal', 'tipe', 'nama', 'branch', 'tanggal_bongkar', 'status', 'created_by']
    list_filter    = ['tipe', 'status', 'branch', 'tanggal_bongkar']
    search_fields  = ['device_asal__nama', 'nama', 'merk', 'serial_number', 'alasan_penggantian']
    readonly_fields = ['created_at', 'event_bongkar', 'event_pasang']
    date_hierarchy = 'tanggal_bongkar'
    fieldsets = [
        ('Identitas', {'fields': [
            'device_asal', 'tipe', 'komponen_terkait',
            'nama', 'merk', 'model_tipe', 'serial_number',
        ]}),
        ('Pembongkaran', {'fields': [
            'tanggal_bongkar', 'alasan_penggantian', 'branch', 'status',
            'event_bongkar',
        ]}),
        ('Pemasangan Kembali', {'fields': [
            'event_pasang',
        ], 'classes': ['collapse']}),
        ('Audit', {'fields': [
            'created_by', 'created_at',
        ], 'classes': ['collapse']}),
    ]

@admin.register(DeviceLink)
class DeviceLinkAdmin(admin.ModelAdmin):
    list_display        = ['display_label', 'tipe_badge', 'lokasi_a', 'lokasi_b', 'aktif', 'created_at']
    list_filter         = ['tipe', 'aktif', 'device_a__lokasi']
    search_fields       = ['label', 'device_a__nama', 'device_b__nama',
                           'device_a__lokasi', 'device_b__lokasi']
    autocomplete_fields = ['device_a', 'device_b']
    list_editable       = ['aktif']
    readonly_fields     = ['created_at']
    fieldsets = [
        (None,      {'fields': ['device_a', 'device_b', 'tipe', 'label', 'aktif']}),
        ('Catatan', {'fields': ['keterangan', 'created_at'], 'classes': ['collapse']}),
    ]

    @admin.display(description='Koneksi')
    def display_label(self, obj):
        return obj.display_label

    @admin.display(description='Tipe')
    def tipe_badge(self, obj):
        from django.utils.html import format_html
        colors = {'fiber':'#3b82f6','radio':'#f59e0b','opgw':'#10b981',
                  'pilot_wire':'#8b5cf6','lainnya':'#94a3b8'}
        c = colors.get(obj.tipe, '#94a3b8')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:20px;'
            'font-size:11px;font-weight:600;">{}</span>', c, obj.get_tipe_display()
        )

    @admin.display(description='Lokasi A')
    def lokasi_a(self, obj):
        return obj.device_a.lokasi or '—'

    @admin.display(description='Lokasi B')
    def lokasi_b(self, obj):
        return obj.device_b.lokasi or '—'


# ═══════════════════════════════════════════════════════════════════════════
#  Kunci API eksternal
# ═══════════════════════════════════════════════════════════════════════════
from django.utils.html import format_html, format_html_join  # noqa: E402
from django.utils.safestring import mark_safe  # noqa: E402

from .models import DatasetApi, KunciApi


@admin.register(DatasetApi)
class DatasetApiAdmin(admin.ModelAdmin):
    """
    "Data apa yang boleh keluar dari FASOP" — satu baris per jenis data.

    Barisnya tidak bisa ditambah/dihapus dari sini: yang menyajikan angkanya
    adalah sebuah view, jadi kode yang diketik manual hanya melahirkan izin
    yang tidak menjaga apa pun. Daftarnya disamakan dengan api/registry.py tiap
    kali halaman ini dibuka, sehingga data yang baru ditambahkan di kode
    langsung terlihat — dalam keadaan TERTUTUP, menunggu diputuskan.
    """
    list_display    = ['nama_data', 'kode', 'aktif', 'jumlah_kunci', 'diubah_pada']
    list_filter     = ['aktif']
    search_fields   = ['kode', 'keterangan']
    list_editable   = ['aktif']
    readonly_fields = ['kode', 'rincian', 'daftar_kunci', 'diubah_pada']
    actions         = ['buka', 'tutup']
    fieldsets = [
        (None, {
            'fields': ['kode', 'rincian', 'aktif', 'keterangan'],
            'description': (
                'Sakelar ini berlaku untuk <b>semua</b> konsumen sekaligus. '
                'Siapa yang boleh membaca ditentukan terpisah di '
                '<b>Kunci API</b> → kolom "Data yang Boleh Dibaca" — sebuah data '
                'baru benar-benar keluar bila dibuka di sini <b>dan</b> '
                'dicentang pada kunci yang bersangkutan.'
            ),
        }),
        ('Dipakai kunci', {'fields': ['daftar_kunci', 'diubah_pada']}),
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Sinkronisasi di sini, bukan di get_queryset(): get_queryset() dipanggil
        # juga oleh widget M2M di halaman Kunci API dan oleh aksi massal, jadi
        # menaruhnya di sana berarti menulis ke DB pada jalur yang tidak
        # mengharapkannya.
        baru = DatasetApi.sinkron()
        if baru:
            self.message_user(
                request,
                f'{baru} jenis data baru terdaftar dari kode dan ditambahkan di sini '
                f'dalam keadaan TERTUTUP. Buka hanya yang memang disetujui keluar.'
            )
        return super().changelist_view(request, extra_context)

    @admin.display(description='Data', ordering='kode')
    def nama_data(self, obj):
        return obj.nama

    @admin.display(description='Dipakai kunci')
    def jumlah_kunci(self, obj):
        return obj.kunci.count()

    @admin.display(description='Rincian')
    def rincian(self, obj):
        if not obj.terdaftar:
            return format_html(
                '<b style="color:#b91c1c">Kode ini sudah tidak ada di api/registry.py.</b><br>'
                'Tidak ada endpoint yang memakainya — izin yang tertinggal di sini '
                'tidak membuka apa pun, dan barisnya boleh diabaikan.'
            )
        daftar = format_html_join('', '<li><code>{}</code></li>',
                                  ((e,) for e in obj.endpoint))
        return format_html(
            '{}<br><br><b>Sumber angka:</b> {}<br><b>Endpoint:</b><ul>{}</ul>',
            obj.penjelasan, obj.sumber, daftar
        )

    @admin.display(description='Kunci yang diberi izin')
    def daftar_kunci(self, obj):
        nama = list(obj.kunci.values_list('nama', flat=True))
        return ', '.join(nama) if nama else '— belum ada —'

    @admin.action(description='Buka (boleh dikeluarkan)')
    def buka(self, request, queryset):
        n = queryset.update(aktif=True)
        self.message_user(
            request,
            f'{n} jenis data dibuka. Konsumen tetap harus dicentang satu per satu '
            f'di Kunci API — membuka di sini saja belum mengirimkan apa pun.'
        )

    @admin.action(description='Tutup (hentikan untuk semua konsumen)')
    def tutup(self, request, queryset):
        n = queryset.update(aktif=False)
        self.message_user(request, f'{n} jenis data ditutup untuk semua konsumen, seketika.')


@admin.register(KunciApi)
class KunciApiAdmin(admin.ModelAdmin):
    list_display  = ['nama', 'kunci_tersamar', 'aktif', 'izin_data', 'terakhir_dipakai',
                     'terakhir_ip', 'created_at']
    list_filter   = ['aktif', 'dataset']
    search_fields = ['nama', 'keterangan']
    filter_horizontal = ['dataset']
    readonly_fields = ['created_at', 'terakhir_dipakai', 'terakhir_ip', 'dibuat_oleh']
    actions = ['buat_ulang_kunci', 'nonaktifkan', 'cabut_semua_izin']
    fieldsets = [
        (None, {
            'fields': ['nama', 'kunci', 'aktif', 'keterangan'],
            'description': (
                'Kunci ini hanya membuka endpoint BACA <code>/api/v1/</code> yang '
                'dicentang di bawah. Ia BUKAN <code>API_KEY</code> di .env — kunci itu '
                'ikut membuka endpoint tulis dan tidak boleh dibagikan ke pihak luar. '
                'Kosongkan kolom Kunci saat menambah untuk membuat kunci acak.'
            ),
        }),
        ('Data yang boleh dibaca', {
            'fields': ['dataset'],
            'description': (
                'Centang hanya yang memang diminta konsumen ini. Data yang tidak '
                'dicentang dibalas <code>403</code> dengan pesan yang menyebut '
                'izinnya kurang. Data juga harus dalam keadaan dibuka di '
                '<b>Data API Eksternal</b>; menutupnya di sana menghentikan semua '
                'konsumen sekaligus tanpa mengubah centang di sini.'
            ),
        }),
        ('Jejak', {'fields': ['dibuat_oleh', 'created_at', 'terakhir_dipakai', 'terakhir_ip']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('dataset')

    @admin.display(description='Kunci')
    def kunci_tersamar(self, obj):
        return obj.kunci_tersamar

    @admin.display(description='Data yang boleh dibaca')
    def izin_data(self, obj):
        daftar = obj.dataset.all()
        if not daftar:
            # Kunci tanpa izin bukan kesalahan — begitulah kunci baru lahir —
            # tapi ia juga tidak bisa membaca apa pun, dan itu harus terbaca
            # dari daftar supaya tidak dikira integrasinya yang rusak.
            return format_html('<span style="color:{}">{}</span>',
                               '#b45309', '— belum diberi izin —')
        return format_html_join(
            mark_safe('<br>'), '{}{}',
            ((d.nama, '' if d.aktif else ' (ditutup)') for d in daftar)
        )

    def save_model(self, request, obj, form, change):
        # Kolom Kunci boleh dikosongkan (model.save() mengisinya sendiri). Catat
        # dulu apakah tadi kosong: setelah super().save_model() sudah terisi.
        dibuatkan = not obj.kunci
        if not change and obj.dibuat_oleh_id is None:
            obj.dibuat_oleh = request.user
        super().save_model(request, obj, form, change)
        if dibuatkan:
            # Ditampilkan sekali di sini supaya kuncinya bisa langsung disalin —
            # daftar admin hanya menampilkan versi tersamar.
            self.message_user(
                request,
                f'Kunci untuk "{obj.nama}" dibuat: {obj.kunci} — salin dan kirimkan '
                f'ke konsumennya lewat jalur yang aman.'
            )

    @admin.action(description='Buat ulang kunci (kunci lama langsung tidak berlaku)')
    def buat_ulang_kunci(self, request, queryset):
        for obj in queryset:
            obj.kunci = KunciApi.kunci_baru()
            obj.save(update_fields=['kunci'])
        self.message_user(
            request,
            f'{queryset.count()} kunci dibuat ulang. Kunci lama sudah tidak berlaku — '
            f'kirimkan kunci baru ke konsumennya, kalau tidak integrasinya akan berhenti.'
        )

    @admin.action(description='Nonaktifkan (cabut akses tanpa menghapus)')
    def nonaktifkan(self, request, queryset):
        n = queryset.update(aktif=False)
        self.message_user(request, f'{n} kunci dinonaktifkan.')

    @admin.action(description='Cabut semua izin data (kunci tetap aktif)')
    def cabut_semua_izin(self, request, queryset):
        for obj in queryset:
            obj.dataset.clear()
        self.message_user(
            request,
            f'Izin data pada {queryset.count()} kunci dikosongkan. Kuncinya masih '
            f'berlaku tapi sekarang tidak bisa membaca apa pun — pakai ini bila '
            f'aksesnya perlu disusun ulang dari awal.'
        )


@admin.register(AsesmenOptik)
class AsesmenOptikAdmin(admin.ModelAdmin):
    list_display  = ('fiber_optic', 'no_tower', 'tanggal', 'kondisi_fo',
                     'kondisi_asesoris', 'joint_box', 'petugas')
    list_filter   = ('kondisi_fo', 'kondisi_asesoris', 'joint_box', 'upt',
                     'level_tegangan', 'tanggal', 'fiber_optic')
    search_fields = ('no_tower', 'fiber_optic__nama', 'petugas', 'keterangan')
    date_hierarchy = 'tanggal'
    autocomplete_fields = ()
    readonly_fields = ('created_at', 'updated_at')



# ── Pengumuman Pemeliharaan ──────────────────────────────────────────────────

from .models import PengumumanPemeliharaan  # noqa: E402


@admin.register(PengumumanPemeliharaan)
class PengumumanPemeliharaanAdmin(admin.ModelAdmin):
    """
    Pop-up pengumuman (mis. rencana restart server) yang muncul sekali per sesi
    login. Baris tunggal, jadi tombol Tambah/Hapus dimatikan dan daftar langsung
    membuka baris itu — sama seperti Mode Pemeliharaan OPSIS.
    """
    list_display    = ('status_ringkas', 'judul', 'tingkat', 'mulai', 'selesai',
                       'diubah_oleh', 'diubah_pada')
    readonly_fields = ('diubah_oleh', 'diubah_pada')
    fieldsets = (
        (None, {
            'description': 'Pop-up ini muncul sekali untuk setiap pengguna yang login, '
                           'di seluruh halaman FASOP. Menyimpan perubahan apa pun di sini '
                           'membuat pop-up muncul lagi ke semua orang — termasuk yang sudah '
                           'menutupnya — supaya jadwal yang digeser tidak luput terbaca.',
            'fields': ('aktif',),
        }),
        ('Isi Pengumuman', {'fields': ('judul', 'pesan', 'tingkat')}),
        ('Jadwal', {
            'description': 'Opsional, hanya ditampilkan di pop-up. Ini BUKAN penjadwal — '
                           'tidak ada yang dimatikan otomatis pada jam tersebut.',
            'fields': ('mulai', 'selesai', 'berhenti_otomatis'),
        }),
        ('Riwayat', {'fields': ('diubah_oleh', 'diubah_pada')}),
    )

    @admin.display(description='Tampil', boolean=True)
    def status_ringkas(self, obj):
        return obj.sedang_tampil()

    def has_add_permission(self, request):
        # Baris tunggal: dibuat otomatis oleh changelist_view di bawah.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        PengumumanPemeliharaan.ambil()   # pastikan barisnya ada sebelum daftar dirender
        return super().changelist_view(request, extra_context)

    def save_model(self, request, obj, form, change):
        obj.diubah_oleh = request.user
        super().save_model(request, obj, form, change)
