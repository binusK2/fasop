from django.urls import path
from . import views

urlpatterns = [
    path('',              views.jadwal_list,   name='jadwal_list'),
    path('buat/',         views.jadwal_create, name='jadwal_create'),
    path('<int:pk>/',     views.jadwal_detail, name='jadwal_detail'),
    path('<int:pk>/done/', views.jadwal_done,  name='jadwal_done'),
    path('<int:pk>/hapus/', views.jadwal_delete, name='jadwal_delete'),
]
