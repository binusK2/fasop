from django.urls import path
from . import views
from . import views_komponen

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
    # Device Events
    path('view/<int:pk>/event/add/', views.device_event_add, name='device_event_add'),
    path('view/<int:pk>/event/<int:event_pk>/delete/', views.device_event_delete, name='device_event_delete'),

    # ✅ BARU: Komponen Perangkat
    path('view/<int:device_pk>/komponen/add/', views_komponen.komponen_add, name='komponen_add'),
    path('view/<int:device_pk>/komponen/<int:komponen_pk>/edit/', views_komponen.komponen_edit, name='komponen_edit'),
    path('view/<int:device_pk>/komponen/<int:komponen_pk>/delete/', views_komponen.komponen_delete, name='komponen_delete'),

    # Manajemen Lokasi
    path('lokasi-admin/', views.lokasi_admin, name='lokasi_admin'),
    path('api/lokasi-list/', views.api_lokasi_list, name='api_lokasi_list'),
    # Public page (QR Code — tanpa login)
    path('public/<str:token>/', views.device_public, name='device_public'),

    # ✅ BARU: API untuk komponen berdasarkan device (digunakan di form gangguan)
    path('api/device/<int:device_pk>/komponen/', views_komponen.api_komponen_by_device, name='api_komponen_by_device'),
]
