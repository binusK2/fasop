from django.contrib import admin
from .models import Device, DeviceType, SiteLocation, ULTG
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


@admin.register(SiteLocation)
class SiteLocationAdmin(admin.ModelAdmin):
    list_display  = ['nama', 'latitude', 'longitude', 'has_coords', 'keterangan']
    search_fields = ['nama']
    list_display_links = ['nama']

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
