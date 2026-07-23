from django.contrib import admin

from .models import KinerjaAnalogHarian, KinerjaDigitalHarian, RemoteControl, SitePath1


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


@admin.register(RemoteControl)
class RemoteControlAdmin(admin.ModelAdmin):
    list_display = ('b1', 'b3', 'elem', 'tanggal', 'datum_eksekusi', 'status_respon', 'operator')
    list_filter = ('tanggal', 'status_respon')
    search_fields = ('b1', 'b2', 'b3', 'elem', 'operator')
