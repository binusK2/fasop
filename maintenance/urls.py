from django.urls import path
from . import views

urlpatterns = [
    path('', views.maintenance_list, name='maintenance_list'),
    path('maintenance/add/<int:device_id>/', views.maintenance_create, name='maintenance_add_device'),
    path('maintenance/delete/<int:pk>/', views.maintenance_delete, name='maintenance_delete'),
    path('update_status/<int:pk>/', views.maintenance_update_status, name='maintenance_update_status'),
    path('view/<int:pk>/', views.maintenance_detail, name='maintenance_view'),
    path('edit/<int:pk>/', views.maintenance_edit, name='maintenance_edit'),

    # ✅ BARU: Laporan bulanan & Export
    path('report/', views.maintenance_report, name='maintenance_report'),
    path('export/', views.export_maintenance_excel, name='export_maintenance_excel'),
    path('berita-acara/', views.berita_acara_excel, name='berita_acara_excel'),
    path('berita-acara/pdf/', views.berita_acara_pdf, name='berita_acara_pdf'),
    path('export-pdf/<int:pk>/', views.export_maintenance_pdf, name='export_maintenance_pdf'),
    path('sign/<int:pk>/', views.maintenance_sign, name='maintenance_sign'),
    path('catatan-am/<int:pk>/', views.maintenance_catatan_am_edit, name='maintenance_catatan_am_edit'),
    path('profile/', views.profile_view, name='profile_view'),
    # Corrective Maintenance
    path('corrective/add/',                       views.corrective_add,                              name='corrective_add'),
    path('corrective/device/<int:device_id>/',    lambda r, device_id: views.corrective_add(r, device_id=device_id),    name='corrective_add_device'),
    path('corrective/gangguan/<int:gangguan_id>/', lambda r, gangguan_id: views.corrective_add(r, gangguan_id=gangguan_id), name='corrective_add_gangguan'),
    path('corrective/edit/<int:pk>/',             views.corrective_edit, name='corrective_edit'),
    # Offline Form (download template & upload)
    path('offline/download/', views.offline_form_download, name='offline_form_download'),
    path('offline/upload/',   views.offline_form_upload,   name='offline_form_upload'),
]