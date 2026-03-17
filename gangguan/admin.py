from django.contrib import admin
from .models import Gangguan


@admin.register(Gangguan)
class GangguanAdmin(admin.ModelAdmin):
    list_display  = ['nomor_gangguan', 'site', 'kategori', 'tingkat_keparahan', 'status', 'tanggal_gangguan', 'created_by']
    list_filter   = ['status', 'kategori', 'tingkat_keparahan']
    search_fields = ['nomor_gangguan', 'site', 'executive_summary']
    readonly_fields = ['nomor_gangguan', 'created_at', 'updated_at']
    ordering      = ['-tanggal_gangguan']
