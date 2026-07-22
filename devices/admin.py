from django.contrib import admin
from .models import Device, DeviceType, SiteLocation, ULTG, KomponenRusak, Branch
from .models_komponen import (
    GrupTipeKomponen, TipeKomponen,
    DeviceComponent,
    SpecRouterPort, SpecMuxSlot, SpecPSU,
    SpecRectifierModul, SpecBattery, SpecBatteryCell,
    SpecRadioModul, SpecPLCModul,
)

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['nama', 'jenis', 'merk', 'lokasi', 'status_operasi']
    search_fields = ['nama', 'merk', 'serial_number', 'lokasi']
    list_filter = ['jenis', 'status_operasi']

admin.site.register(DeviceType)


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
