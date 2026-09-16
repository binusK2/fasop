from django.contrib import admin
from .models import (
    Maintenance, MaintenancePLC, MaintenanceRouter, MaintenanceSAS, MaintenanceBCU, MaintenanceRoIP, MaintenanceUPS,
    BeritaAcaraRecord, BeritaAcaraEviden,
)


class MaintenancePLCInline(admin.StackedInline):
    model = MaintenancePLC
    extra = 0


class MaintenanceRouterInline(admin.StackedInline):
    model = MaintenanceRouter
    extra = 0


@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display  = ['device', 'maintenance_type', 'date', 'status', 'get_technicians', 'signed_by',
                      'is_deleted', 'deleted_by']
    list_filter   = ['status', 'maintenance_type', 'device__jenis', 'is_deleted']
    search_fields = ['device__nama', 'description']
    inlines       = [MaintenancePLCInline, MaintenanceRouterInline]
    filter_horizontal = ['technicians']
    actions       = ['pulihkan_data']

    def get_queryset(self, request):
        # Maintenance.objects (default manager) menyaring is_deleted=True --
        # admin butuh melihat SEMUA data (termasuk yang di-soft-delete Teknisi)
        # supaya bisa dipulihkan, jadi pakai semua_objects (unfiltered) di sini.
        qs = self.model.semua_objects.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    @admin.display(description='Pelaksana')
    def get_technicians(self, obj):
        return ', '.join(
            t.get_full_name() or t.username
            for t in obj.technicians.all()
        ) or '—'

    @admin.action(description='Pulihkan data yang terhapus (batalkan soft-delete)')
    def pulihkan_data(self, request, queryset):
        n = queryset.filter(is_deleted=True).update(is_deleted=False, deleted_by=None)
        self.message_user(request, f'{n} data maintenance dipulihkan.')


@admin.register(MaintenancePLC)
class MaintenancePLCAdmin(admin.ModelAdmin):
    pass


@admin.register(MaintenanceRouter)
class MaintenanceRouterAdmin(admin.ModelAdmin):
    list_display = ['maintenance', 'kondisi_fisik', 'cpu_load', 'memory_usage', 'status_routing']


@admin.register(MaintenanceSAS)
class MaintenanceSASAdmin(admin.ModelAdmin):
    list_display = ['maintenance', 'spek_merk', 'spek_type', 'kondisi_server', 'inv_kondisi']


@admin.register(MaintenanceBCU)
class MaintenanceBCUAdmin(admin.ModelAdmin):
    list_display = ['maintenance', 'spek_cpu', 'kondisi_cpu', 'komunikasi_master', 'ps_jenis']


@admin.register(MaintenanceRoIP)
class MaintenanceRoIPAdmin(admin.ModelAdmin):
    pass


@admin.register(MaintenanceUPS)
class MaintenanceUPSAdmin(admin.ModelAdmin):
    list_display = ['maintenance', 'ups_merk', 'ups_model', 'ups_kondisi', 'bat_jumlah_cell']


class BeritaAcaraEvidenInline(admin.TabularInline):
    model = BeritaAcaraEviden
    extra = 0
    fields = ['gambar', 'catatan', 'urutan']


@admin.register(BeritaAcaraRecord)
class BeritaAcaraRecordAdmin(admin.ModelAdmin):
    list_display  = ['nomor_ba', 'jenis', 'tanggal', 'pelaksana', 'ttd_status', 'created_by', 'created_at']
    list_filter   = ['jenis', 'ttd_status', 'tanggal']
    search_fields = ['nomor_ba', 'pelaksana', 'nip', 'catatan']
    date_hierarchy = 'tanggal'
    inlines       = [BeritaAcaraEvidenInline]
    readonly_fields = ['created_at']
    autocomplete_fields = ['created_by', 'ttd_req_to', 'ttd_engineer', 'ttd_am']
