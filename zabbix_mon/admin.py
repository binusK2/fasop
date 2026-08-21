from django.contrib import admin, messages

from .models import ZabbixHost, ZabbixEventLog, ZabbixWebhookLog, ZabbixAlertLog


class ZabbixEventLogInline(admin.TabularInline):
    model = ZabbixEventLog
    extra = 0
    readonly_fields = ('state', 'severity', 'problem_name', 'source', 'mulai', 'selesai', 'durasi_menit')
    can_delete = False
    max_num = 20
    ordering = ('-mulai',)


class ZabbixAlertLogInline(admin.TabularInline):
    model = ZabbixAlertLog
    extra = 0
    readonly_fields = ('jenis', 'terkirim', 'keterangan', 'created_at')
    fields = ('created_at', 'jenis', 'terkirim', 'keterangan')
    can_delete = False
    max_num = 10
    ordering = ('-created_at',)
    verbose_name_plural = 'Blast WA terakhir'


@admin.register(ZabbixHost)
class ZabbixHostAdmin(admin.ModelAdmin):
    list_display = ('nama', 'zabbix_hostid', 'device', 'lokasi', 'state', 'severity',
                    'state_sejak', 'urutan', 'aktif', 'wa_alert', 'wa_min_severity')
    list_editable = ('lokasi', 'urutan', 'aktif', 'wa_alert', 'wa_min_severity')
    list_display_links = ('nama',)
    list_filter = ('state', 'aktif', 'wa_alert', 'wa_min_severity')
    search_fields = ('nama', 'zabbix_host', 'zabbix_hostid', 'lokasi')
    autocomplete_fields = ('device',)
    readonly_fields = ('state', 'severity', 'problem_name', 'state_sejak', 'last_synced_at')
    inlines = [ZabbixAlertLogInline, ZabbixEventLogInline]
    actions = ('aktifkan_blast', 'matikan_blast', 'kirim_uji_wa')

    fieldsets = (
        (None, {
            'fields': ('zabbix_hostid', 'zabbix_host', 'nama', 'device', 'lokasi',
                       'urutan', 'aktif'),
        }),
        ('Blast WhatsApp', {
            'fields': ('wa_alert', 'wa_min_severity', 'wa_chat_ids'),
            'description': (
                'Pilih host mana yang transisinya dikirim ke grup WhatsApp lewat OpenWA. '
                'Butuh <code>WA_ALERT_ENABLED=True</code> di <code>.env</code>. '
                'Tujuan default diambil dari <code>WA_CHAT_IDS_ZABBIX</code>; isi '
                '"Grup WA Khusus" hanya kalau host ini perlu grup yang berbeda. '
                'Pakai action "Kirim pesan uji" di daftar host untuk mengetes tujuan '
                'tanpa menunggu problem betulan.'
            ),
        }),
        ('State terkini (otomatis)', {
            'fields': ('state', 'severity', 'problem_name', 'state_sejak', 'last_synced_at'),
        }),
    )

    @admin.action(description='Aktifkan blast WhatsApp')
    def aktifkan_blast(self, request, queryset):
        n = queryset.update(wa_alert=True)
        self.message_user(request, f'{n} host diaktifkan untuk blast WhatsApp.',
                          messages.SUCCESS)

    @admin.action(description='Matikan blast WhatsApp')
    def matikan_blast(self, request, queryset):
        n = queryset.update(wa_alert=False)
        self.message_user(request, f'{n} host dimatikan dari blast WhatsApp.',
                          messages.SUCCESS)

    @admin.action(description='Kirim pesan uji WA ke tujuan host terpilih')
    def kirim_uji_wa(self, request, queryset):
        from django.utils import timezone
        from device_mon.notifications import kirim_wa
        from .notifications import _targets

        for host in queryset:
            chat_ids = _targets(host)
            if not chat_ids:
                self.message_user(
                    request,
                    f'{host.nama}: tujuan WA kosong — isi WA_CHAT_IDS_ZABBIX di .env '
                    f'atau kolom "Grup WA Khusus".',
                    messages.WARNING,
                )
                continue

            now = timezone.localtime(timezone.now())
            pesan = (
                '🔔 *Tes Blast Zabbix FASOP*\n'
                f'Perangkat : {host.nama}\n'
                f'Lokasi    : {host.lokasi or "-"}\n'
                f'Waktu     : {now:%d-%m-%Y %H:%M:%S}\n'
                '\n_Pesan uji — bukan gangguan._'
            )
            terkirim, total, ket = kirim_wa(pesan, chat_ids=chat_ids)
            if terkirim:
                self.message_user(request, f'{host.nama}: terkirim ke {terkirim}/{total} grup.',
                                  messages.SUCCESS)
            else:
                self.message_user(request, f'{host.nama}: gagal kirim (0/{total}). {ket}',
                                  messages.ERROR)


@admin.register(ZabbixAlertLog)
class ZabbixAlertLogAdmin(admin.ModelAdmin):
    list_display = ('host', 'jenis', 'terkirim', 'keterangan', 'created_at')
    list_filter = ('jenis', 'terkirim', 'host')
    date_hierarchy = 'created_at'
    search_fields = ('host__nama', 'keterangan', 'pesan')
    readonly_fields = ('host', 'jenis', 'pesan', 'terkirim', 'keterangan', 'created_at')
    ordering = ('-created_at',)


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
