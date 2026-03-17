from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('devices/', views.device_list, name='device_list'),
    path('add/', views.device_create, name='device_add'),
    path('edit/<int:pk>/', views.device_update, name='device_edit'),
    path('delete/<int:pk>/', views.device_delete, name='device_delete'),
    path('view/<int:pk>/', views.device_detail, name='device_view'),
    path('type/<int:type_id>/', views.device_by_type, name='device_by_type'),
    path('lokasi/', views.lokasi_list, name='lokasi_list'),
    path('api/lokasi/<str:lokasi_nama>/devices/', views.api_lokasi_devices, name='api_lokasi_devices'),
    path('layanan-icon/', views.layanan_icon, name='layanan_icon'),
    path('icon/', views.icon_create, name='icon_add'),
    path('icon/edit/<int:pk>/', views.icon_update, name='icon_edit'),
    path('icon/delete/<int:pk>/', views.icon_delete, name='icon_delete'),

    # ✅ BARU: QR Code & Export
    path('qr/<int:pk>/', views.device_qr, name='device_qr'),
    path('export/devices/', views.export_devices_excel, name='export_devices_excel'),
    path('export/icon/', views.export_icon_excel, name='export_icon_excel'),
]
