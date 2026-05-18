from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ['created_at', 'user', 'action', 'app_label', 'model_name', 'object_repr', 'ip_address']
    list_filter   = ['action', 'app_label', 'created_at']
    search_fields = ['user__username', 'object_repr', 'detail', 'model_name']
    readonly_fields = ['user', 'action', 'app_label', 'model_name', 'object_id',
                       'object_repr', 'detail', 'ip_address', 'created_at']
    ordering      = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
