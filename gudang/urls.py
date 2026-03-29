from django.urls import path
from . import views

app_name = 'gudang'

urlpatterns = [
    # Alat Uji
    path('alat/',              views.alat_list,   name='alat_list'),
    path('alat/tambah/',       views.alat_create, name='alat_create'),
    path('alat/<int:pk>/',     views.alat_detail, name='alat_detail'),
    path('alat/<int:pk>/edit/',   views.alat_edit,   name='alat_edit'),
    path('alat/<int:pk>/hapus/',  views.alat_delete, name='alat_delete'),

    # Spare Part
    path('sparepart/',                      views.sparepart_list,   name='sparepart_list'),
    path('sparepart/tambah/',               views.sparepart_create, name='sparepart_create'),
    path('sparepart/<int:pk>/',             views.sparepart_detail, name='sparepart_detail'),
    path('sparepart/<int:pk>/edit/',        views.sparepart_edit,   name='sparepart_edit'),
    path('sparepart/<int:pk>/hapus/',       views.sparepart_delete, name='sparepart_delete'),
    path('sparepart/<int:pk>/mutasi/',      views.mutasi_create,    name='mutasi_create'),
]
