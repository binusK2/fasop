from django.contrib import admin
from .models import Pembangkit, SnapLive, SnapUnit


@admin.register(Pembangkit)
class PembangkitAdmin(admin.ModelAdmin):
    list_display  = ('urutan', 'nama', 'kode', 'jenis', 'warna', 'aktif')
    list_editable = ('urutan', 'jenis', 'aktif')
    list_display_links = ('nama',)
    fieldsets = (
        (None, {'fields': ('nama', 'kode', 'jenis', 'warna', 'urutan', 'aktif')}),
        ('Tag MSSQL', {
            'description': 'Isi tag/kolom sesuai struktur tabel historian di MSSQL.',
            'fields': ('tag_frekuensi', 'tag_mw', 'tag_mvar'),
        }),
    )


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
