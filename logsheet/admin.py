from django.contrib import admin
from .models import LogsheetTitik, LogsheetNilai


@admin.register(LogsheetTitik)
class LogsheetTitikAdmin(admin.ModelAdmin):
    list_display  = ('key', 'kategori', 'besaran', 'sheet', 'baris',
                     'mssql_tabel', 'mssql_kolom', 'mssql_key', 'aktif')
    list_editable = ('aktif',)
    list_filter   = ('kategori', 'besaran', 'sheet', 'aktif')
    search_fields = ('key', 'nama', 'mssql_key')
    ordering      = ('kategori', 'sheet', 'baris')


@admin.register(LogsheetNilai)
class LogsheetNilaiAdmin(admin.ModelAdmin):
    list_display   = ('titik', 'tanggal', 'slot', 'waktu', 'nilai')
    list_filter    = ('tanggal', 'titik__kategori')
    date_hierarchy = 'tanggal'
    search_fields  = ('titik__key',)
    ordering       = ('-tanggal', 'titik', 'slot')
