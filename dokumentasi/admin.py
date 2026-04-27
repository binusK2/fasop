from django.contrib import admin
from .models import SettingRele, GambarDevice


@admin.register(SettingRele)
class SettingReleAdmin(admin.ModelAdmin):
    list_display  = ('nomor', 'device', 'judul', 'tanggal', 'versi', 'status', 'checker', 'created_by')
    list_filter   = ('status',)
    search_fields = ('nomor', 'judul', 'device__nama')
    readonly_fields = ('nomor', 'created_at', 'updated_at')


@admin.register(GambarDevice)
class GambarDeviceAdmin(admin.ModelAdmin):
    list_display  = ('nomor', 'device', 'judul', 'tipe', 'tanggal', 'versi', 'checker', 'created_by')
    list_filter   = ('tipe',)
    search_fields = ('nomor', 'judul', 'device__nama')
    readonly_fields = ('nomor', 'created_at', 'updated_at')
