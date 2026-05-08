from django.contrib import admin
from .models import ScadaAvSession, ScadaAvFile, RtuAvResult, RcdSummary, RcdBayResult


class ScadaAvFileInline(admin.TabularInline):
    model   = ScadaAvFile
    extra   = 0
    readonly_fields = ('filename', 'ukuran', 'diunggah_pada')


@admin.register(ScadaAvSession)
class ScadaAvSessionAdmin(admin.ModelAdmin):
    list_display  = ('nama', 'periode_awal', 'periode_akhir', 'master', 'calc_type', 'status', 'dibuat_oleh', 'dibuat_pada')
    list_filter   = ('status', 'master', 'calc_type')
    search_fields = ('nama',)
    readonly_fields = ('dibuat_pada', 'durasi_hitung', 'error_message')
    inlines       = [ScadaAvFileInline]


@admin.register(RtuAvResult)
class RtuAvResultAdmin(admin.ModelAdmin):
    list_display  = ('session', 'rtu', 'long_name', 'rtu_availability', 'link_availability', 'overall')
    list_filter   = ('session',)
    search_fields = ('rtu', 'long_name')


@admin.register(RcdSummary)
class RcdSummaryAdmin(admin.ModelAdmin):
    list_display = ('session', 'total_valid', 'total_success', 'total_failed', 'success_ratio')


@admin.register(RcdBayResult)
class RcdBayResultAdmin(admin.ModelAdmin):
    list_display  = ('session', 'station', 'bay_b3', 'occurences', 'success', 'failed', 'success_rate')
    list_filter   = ('session',)
    search_fields = ('station', 'bay_b3')
