from django.urls import path, register_converter
from fasop.converters import HashIdConverter
register_converter(HashIdConverter, 'hid')
from . import views

urlpatterns = [
    path('',                              views.inspection_lokasi,       name='inspection_lokasi'),
    path('dashboard/',                    views.inspection_dashboard,    name='inspection_dashboard'),
    path('lokasi/<str:lokasi>/',          views.inspection_device_list,  name='inspection_device_list'),
    path('form/<hid:device_pk>/',         views.inspection_form,         name='inspection_form'),
    path('riwayat/<hid:pk>/',             views.inspection_riwayat,      name='inspection_riwayat'),
    path('riwayat/<hid:pk>/delete/',      views.inspection_delete,       name='inspection_delete'),
    path('riwayat/<hid:pk>/flag/',        views.inspection_flag,         name='inspection_flag'),
    path('riwayat/<hid:pk>/unflag/',      views.inspection_unflag,       name='inspection_unflag'),
    path('riwayat/device/<hid:device_pk>/', views.inspection_riwayat_device, name='inspection_riwayat_device'),
    path('export/',                       views.inspection_export,       name='inspection_export'),
    path('export/ultg/',                  views.inspection_export_ultg,  name='inspection_export_ultg'),
    path('api/last/',                     views.inspection_api_last,     name='inspection_api_last'),
]
