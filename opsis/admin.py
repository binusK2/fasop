from django.contrib import admin
from .models import Pembangkit


@admin.register(Pembangkit)
class PembangkitAdmin(admin.ModelAdmin):
    list_display  = ('urutan', 'nama', 'kode', 'jenis', 'warna', 'aktif')
    list_editable = ('urutan', 'jenis', 'aktif')
    list_display_links = ('nama',)
    fieldsets = (
        (None, {'fields': ('nama', 'kode', 'jenis', 'warna', 'urutan', 'aktif')}),
        ('Tag MSSQL', {
            'description': 'Isi tag/kolom sesuai struktur tabel historian di MSSQL.',
            'fields': ('tag_frekuensi', 'tag_mw', 'tag_mvar'),
        }),
    )
