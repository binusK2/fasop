from django.contrib import admin

from .models import LiveSession


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ('judul', 'teknisi', 'pengawas', 'status', 'started_at', 'ended_at')
    list_filter = ('status',)
    search_fields = ('judul', 'teknisi__username', 'pengawas__username')
    readonly_fields = ('stream_key', 'pengawas_key', 'view_token', 'started_at', 'ended_at')
    date_hierarchy = 'started_at'
