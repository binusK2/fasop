from django.contrib import admin

from .models import KinerjaAnalogHarian, KinerjaDigitalHarian


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
