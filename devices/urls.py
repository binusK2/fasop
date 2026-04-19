from django.urls import path
from . import views
from . import views_komponen

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('devices/', views.device_list, name='device_list'),
    path('devices/<int:pk>/', views.device_detail, name='device_detail'),
    path('add/', views.device_create, name='device_add'),
    path('edit/<int:pk>/', views.device_update, name='device_edit'),
    path('delete/<int:pk>/', views.device_delete, name='device_delete'),
    path('view/<int:pk>/', views.device_detail, name='device_view'),
    path('type/<int:type_id>/', views.device_by_type, name='device_by_type'),
    path('lokasi/', views.lokasi_list, name='lokasi_list'),
    path('api/lokasi/<str:lokasi_nama>/devices/', views.api_lokasi_devices, name='api_lokasi_devices'),

    # Layanan ICON+
    path('layanan-icon/', views.layanan_icon, name='layanan_icon'),
    path('icon/', views.icon_create, name='icon_add'),
    path('icon/edit/<int:pk>/', views.icon_update, name='icon_edit'),
    path('icon/delete/<int:pk>/', views.icon_delete, name='icon_delete'),

    # Fiber Optic
    path('fiber-optic/', views.fiber_optic_list, name='fiber_optic_list'),
    path('fiber-optic/tambah/', views.fiber_optic_create, name='fiber_optic_add'),
    path('fiber-optic/edit/<int:pk>/', views.fiber_optic_update, name='fiber_optic_edit'),
    path('fiber-optic/hapus/<int:pk>/', views.fiber_optic_delete, name='fiber_optic_delete'),
    path('fiber-optic/<int:pk>/', views.fiber_optic_detail, name='fiber_optic_detail'),
    path('fiber-optic/<int:fo_pk>/core/<int:core_pk>/update/', views.fiber_optic_core_update, name='fiber_optic_core_update'),
    path('api/fiber-optic/', views.api_fiber_optic_json, name='api_fiber_optic_json'),
    path('fiber-optic/<int:pk>/qr/', views.fo_qr, name='fo_qr'),

    # QR Code & Export
    path('qr/<int:pk>/', views.device_qr, name='device_qr'),
    path('export/devices/', views.export_devices_excel, name='export_devices_excel'),
    path('export/icon/', views.export_icon_excel, name='export_icon_excel'),

    # Device Events
    path('view/<int:pk>/event/add/', views.device_event_add, name='device_event_add'),
    path('view/<int:pk>/event/<int:event_pk>/delete/', views.device_event_delete, name='device_event_delete'),

    # Eviden Tambahan
    path('view/<int:pk>/eviden/add/', views.device_eviden_add, name='device_eviden_add'),
    path('view/<int:pk>/eviden/<int:eviden_pk>/delete/', views.device_eviden_delete, name='device_eviden_delete'),

    # Komponen Perangkat
    path('view/<int:device_pk>/komponen/add/', views_komponen.komponen_add, name='komponen_add'),
    path('view/<int:device_pk>/komponen/<int:komponen_pk>/edit/', views_komponen.komponen_edit, name='komponen_edit'),
    path('view/<int:device_pk>/komponen/<int:komponen_pk>/delete/', views_komponen.komponen_delete, name='komponen_delete'),

    # Manajemen Lokasi
    path('lokasi-admin/', views.lokasi_admin, name='lokasi_admin'),
    path('api/lokasi-list/', views.api_lokasi_list, name='api_lokasi_list'),

    # Distribusi Status per Jenis
    path('distribusi-jenis/', views.distribusi_jenis, name='distribusi_jenis'),

    # Peta Jaringan
    path('peta-jaringan/', views.peta_jaringan, name='peta_jaringan'),
    path('api/peta-jaringan/', views.api_peta_jaringan, name='api_peta_jaringan'),

    # Public page (QR Code — tanpa login)
    path('public/<str:token>/', views.device_public, name='device_public'),

    # API komponen berdasarkan device
    path('api/device/<int:device_pk>/komponen/', views_komponen.api_komponen_by_device, name='api_komponen_by_device'),
]
