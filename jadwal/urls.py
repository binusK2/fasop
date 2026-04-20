from django.urls import path
from . import views

urlpatterns = [
    path('',              views.jadwal_list,   name='jadwal_list'),
    path('buat/',         views.jadwal_create, name='jadwal_create'),
    path('<hid:pk>/',     views.jadwal_detail, name='jadwal_detail'),
    path('<hid:pk>/done/', views.jadwal_done,  name='jadwal_done'),
    path('<hid:pk>/selesai-semua/', views.jadwal_selesai_semua, name='jadwal_selesai_semua'),
    path('<hid:pk>/hapus/', views.jadwal_delete, name='jadwal_delete'),
]
