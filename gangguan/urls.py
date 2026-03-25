from django.urls import path
from . import views

urlpatterns = [
    path('',            views.gangguan_list,          name='gangguan_list'),
    path('deklarasi/',  views.gangguan_create,         name='gangguan_create'),
    path('<int:pk>/',   views.gangguan_detail,         name='gangguan_detail'),
    path('<int:pk>/edit/',          views.gangguan_update,        name='gangguan_edit'),
    path('<int:pk>/update-status/', views.gangguan_update_status,  name='gangguan_update_status'),
    path('<int:pk>/log/tambah/',     views.gangguan_add_log,        name='gangguan_add_log'),
    path('<int:pk>/log/<int:log_pk>/hapus/', views.gangguan_delete_log, name='gangguan_delete_log'),
    path('<int:pk>/perubahan/tambah/', views.gangguan_catat_perubahan, name='gangguan_catat_perubahan'),
    path('<int:pk>/perubahan/<int:event_pk>/hapus/', views.gangguan_hapus_perubahan, name='gangguan_hapus_perubahan'),
    # Public status page
    path('status/<str:nomor>/<str:token>/', views.gangguan_public_status, name='gangguan_public'),
]
