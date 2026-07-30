from django.contrib import admin
from .models import RTU, RTULog, RTUAlertLog


class RTULogInline(admin.TabularInline):
    model       = RTULog
    extra       = 0
    readonly_fields = ('state', 'mulai', 'selesai', 'durasi_menit')
    can_delete  = False
    max_num     = 20
    ordering    = ('-mulai',)


@admin.register(RTU)
class RTUAdmin(admin.ModelAdmin):
    list_display  = ('nama', 'lokasi', 'state', 'state_sejak', 'urutan', 'aktif')
    list_editable = ('lokasi', 'urutan', 'aktif')
    list_display_links = ('nama',)
    list_filter   = ('state', 'aktif')
    search_fields = ('nama', 'lokasi')
    readonly_fields = ('state', 'state_sejak')
    inlines       = [RTULogInline]


@admin.register(RTULog)
class RTULogAdmin(admin.ModelAdmin):
    list_display  = ('rtu', 'state', 'mulai', 'selesai', 'durasi_menit')
    list_filter   = ('state', 'rtu')
    date_hierarchy = 'mulai'
    readonly_fields = ('rtu', 'state', 'mulai', 'selesai', 'durasi_menit')
    ordering      = ('-mulai',)


@admin.register(RTUAlertLog)
class RTUAlertLogAdmin(admin.ModelAdmin):
    list_display  = ('rtu', 'jenis', 'terkirim', 'keterangan', 'created_at')
    list_filter   = ('jenis', 'terkirim', 'rtu')
    date_hierarchy = 'created_at'
    search_fields = ('rtu__nama', 'keterangan', 'pesan')
    readonly_fields = ('rtu', 'jenis', 'pesan', 'terkirim', 'keterangan', 'created_at')
    ordering      = ('-created_at',)
