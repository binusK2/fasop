from django.contrib import admin
from .models import ZabbixHost, ZabbixEventLog, ZabbixWebhookLog


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
    list_editable = ('lokasi', 'urutan', 'aktif')
    list_display_links = ('nama',)
    list_filter = ('state', 'aktif')
    search_fields = ('nama', 'zabbix_host', 'zabbix_hostid', 'lokasi')
    autocomplete_fields = ('device',)
    readonly_fields = ('state', 'severity', 'problem_name', 'state_sejak', 'last_synced_at')
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
