from django.contrib import admin
from .models import CommonEnemy, CommonEnemyLog


@admin.register(CommonEnemy)
class CommonEnemyAdmin(admin.ModelAdmin):
    list_display   = ['nomor_ce', 'site', 'kategori', 'sub_kategori', 'tingkat_keparahan',
                      'sumber_laporan', 'status', 'tanggal_laporan', 'created_by']
    list_filter    = ['status', 'kategori', 'tingkat_keparahan', 'sumber_laporan']
    search_fields  = ['nomor_ce', 'site', 'deskripsi_masalah']
    readonly_fields = ['nomor_ce', 'created_at', 'updated_at']
    ordering       = ['-tanggal_laporan']


@admin.register(CommonEnemyLog)
class CommonEnemyLogAdmin(admin.ModelAdmin):
    list_display = ['common_enemy', 'waktu_aksi', 'dibuat_oleh']
    ordering     = ['-waktu_aksi']
