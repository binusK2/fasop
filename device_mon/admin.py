from django.contrib import admin
from .models import (RTU, RTULog, RTUAlertLog, ZabbixHost, ZabbixEventLog,
                     ZabbixWebhookLog, ZabbixGroup)


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


class ZabbixEventLogInline(admin.TabularInline):
    model = ZabbixEventLog
    extra = 0
    readonly_fields = ('state', 'severity', 'problem_name', 'source', 'mulai', 'selesai', 'durasi_menit')
    can_delete = False
    max_num = 20
    ordering = ('-mulai',)


@admin.register(ZabbixHost)
class ZabbixHostAdmin(admin.ModelAdmin):
    list_display = ('nama', 'zabbix_hostid', 'device', 'lokasi', 'state', 'severity',
                    'state_sejak', 'urutan', 'aktif')
    list_editable = ('urutan', 'aktif')
    list_display_links = ('nama',)
    list_filter = ('state', 'aktif', 'lokasi')
    search_fields = ('nama', 'zabbix_host', 'zabbix_hostid', 'lokasi__nama')
    # autocomplete: dropdown search-as-you-type, bukan pilihan bebas — 'lokasi'
    # butuh SiteLocationAdmin.search_fields (sudah ada, lihat devices/admin.py).
    autocomplete_fields = ('device', 'lokasi')
    # 'groups' readonly: SELALU ditimpa ulang oleh sync_zabbix dari Host Group
    # di Zabbix, jadi edit manual di sini pasti hilang. Untuk mengelompokkan
    # tampilan dashboard, pakai Grup Host Zabbix (ZabbixGroup) yang manual.
    readonly_fields = ('groups', 'state', 'severity', 'problem_name',
                       'state_sejak', 'last_synced_at')
    inlines = [ZabbixEventLogInline]


@admin.register(ZabbixEventLog)
class ZabbixEventLogAdmin(admin.ModelAdmin):
    list_display = ('host', 'state', 'severity', 'source', 'mulai', 'selesai', 'durasi_menit')
    list_filter = ('state', 'source', 'severity')
    date_hierarchy = 'mulai'
    search_fields = ('host__nama', 'problem_name', 'zabbix_eventid')
    readonly_fields = ('host', 'state', 'severity', 'problem_name', 'zabbix_eventid',
                       'source', 'mulai', 'selesai', 'durasi_menit')
    ordering = ('-mulai',)


@admin.register(ZabbixWebhookLog)
class ZabbixWebhookLogAdmin(admin.ModelAdmin):
    list_display = ('received_at', 'ok', 'host', 'keterangan')
    list_filter = ('ok',)
    date_hierarchy = 'received_at'
    search_fields = ('keterangan', 'payload', 'host__nama')
    readonly_fields = ('received_at', 'ok', 'host', 'keterangan', 'payload')
    ordering = ('-received_at',)


@admin.register(ZabbixGroup)
class ZabbixGroupAdmin(admin.ModelAdmin):
    list_display = ('nama', 'jumlah_host', 'urutan', 'aktif')
    list_editable = ('urutan', 'aktif')
    list_display_links = ('nama',)
    list_filter = ('aktif',)
    search_fields = ('nama', 'keterangan')
    # Widget dua-kolom "available / chosen" dengan kotak pencarian — pola yang
    # sama dengan ULTGAdmin.lokasi di devices/admin.py.
    filter_horizontal = ('hosts',)

    def jumlah_host(self, obj):
        return obj.hosts.count()
    jumlah_host.short_description = 'Jumlah Host'
