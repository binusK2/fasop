from django.contrib import admin
from .models import Maintenance, MaintenancePLC, MaintenanceRouter, MaintenanceSAS


class MaintenancePLCInline(admin.StackedInline):
    model = MaintenancePLC
    extra = 0


class MaintenanceRouterInline(admin.StackedInline):
    model = MaintenanceRouter
    extra = 0


@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display  = ['device', 'maintenance_type', 'date', 'status', 'get_technicians', 'signed_by']
    list_filter   = ['status', 'maintenance_type', 'device__jenis']
    search_fields = ['device__nama', 'description']
    inlines       = [MaintenancePLCInline, MaintenanceRouterInline]
    filter_horizontal = ['technicians']

    @admin.display(description='Pelaksana')
    def get_technicians(self, obj):
        return ', '.join(
            t.get_full_name() or t.username
            for t in obj.technicians.all()
        ) or '—'


@admin.register(MaintenancePLC)
class MaintenancePLCAdmin(admin.ModelAdmin):
    pass


@admin.register(MaintenanceRouter)
class MaintenanceRouterAdmin(admin.ModelAdmin):
    list_display = ['maintenance', 'kondisi_fisik', 'cpu_load', 'memory_usage', 'status_routing']


@admin.register(MaintenanceSAS)
class MaintenanceSASAdmin(admin.ModelAdmin):
    list_display = ['maintenance', 'spek_merk', 'spek_type', 'kondisi_server', 'inv_kondisi']
