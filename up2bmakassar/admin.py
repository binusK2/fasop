from django.contrib import admin

from .models import KinerjaAnalogHarian, KinerjaDigitalHarian, SitePath1


@admin.register(SitePath1)
class SitePath1Admin(admin.ModelAdmin):
    list_display = ('path1', 'aktif', 'keterangan', 'dibuat_pada')
    list_editable = ('aktif',)
    list_filter = ('aktif',)
    search_fields = ('path1', 'keterangan')
    ordering = ('path1',)


@admin.register(KinerjaAnalogHarian)
class KinerjaAnalogHarianAdmin(admin.ModelAdmin):
    list_display = ('point_number', 'path1', 'path2', 'path3', 'tanggal', 'performance', 'jumlah_up')
    list_filter = ('tanggal',)
    search_fields = ('point_number', 'path1', 'path2', 'path3')


@admin.register(KinerjaDigitalHarian)
class KinerjaDigitalHarianAdmin(admin.ModelAdmin):
    list_display = ('point_number', 'path1', 'path2', 'path3', 'tanggal', 'performance', 'jumlah_up')
    list_filter = ('tanggal',)
    search_fields = ('point_number', 'path1', 'path2', 'path3')
