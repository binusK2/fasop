from django.urls import path
from . import views

urlpatterns = [
    path('',                              views.inspection_lokasi,       name='inspection_lokasi'),
    path('dashboard/',                    views.inspection_dashboard,    name='inspection_dashboard'),
    path('lokasi/<str:lokasi>/',          views.inspection_device_list,  name='inspection_device_list'),
    path('form/<int:device_pk>/',         views.inspection_form,         name='inspection_form'),
    path('riwayat/<int:pk>/',             views.inspection_riwayat,      name='inspection_riwayat'),
    path('riwayat/device/<int:device_pk>/', views.inspection_riwayat_device, name='inspection_riwayat_device'),
    path('export/',                       views.inspection_export,       name='inspection_export'),
]
