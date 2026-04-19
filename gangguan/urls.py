from django.urls import path, register_converter
from fasop.converters import HashIdConverter
register_converter(HashIdConverter, 'hid')
from . import views

urlpatterns = [
    path('',            views.gangguan_list,          name='gangguan_list'),
    path('deklarasi/',  views.gangguan_create,         name='gangguan_create'),
    path('<hid:pk>/',   views.gangguan_detail,         name='gangguan_detail'),
    path('<hid:pk>/edit/',          views.gangguan_update,        name='gangguan_edit'),
    path('<hid:pk>/update-status/', views.gangguan_update_status,  name='gangguan_update_status'),
    path('<hid:pk>/log/tambah/',     views.gangguan_add_log,        name='gangguan_add_log'),
    path('<hid:pk>/log/<hid:log_pk>/hapus/', views.gangguan_delete_log, name='gangguan_delete_log'),
    path('<hid:pk>/perubahan/tambah/', views.gangguan_catat_perubahan, name='gangguan_catat_perubahan'),
    path('<hid:pk>/perubahan/<hid:event_pk>/hapus/', views.gangguan_hapus_perubahan, name='gangguan_hapus_perubahan'),
    # Public status page
    path('status/<str:nomor>/<str:token>/', views.gangguan_public_status, name='gangguan_public'),
]
