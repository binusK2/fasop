from django.urls import path
from . import views

urlpatterns = [
    path('',              views.notifikasi_list,  name='notifikasi_list'),
    path('<int:pk>/read/', views.notifikasi_read,  name='notifikasi_read'),
    path('read-all/',     views.notifikasi_read_all, name='notifikasi_read_all'),
    path('count/',        views.notifikasi_count,  name='notifikasi_count'),
    path('<int:pk>/delete/', views.notifikasi_delete, name='notifikasi_delete'),
    path('delete-read/', views.notifikasi_delete_read, name='notifikasi_delete_read'),
]
