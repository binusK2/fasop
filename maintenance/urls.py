from django.urls import path
from . import views

urlpatterns = [
    path('', views.maintenance_list, name='maintenance_list'),
    path('maintenance/add/<hid:device_id>/', views.maintenance_create, name='maintenance_add_device'),
    path('maintenance/delete/<hid:pk>/', views.maintenance_delete, name='maintenance_delete'),
    path('update_status/<hid:pk>/', views.maintenance_update_status, name='maintenance_update_status'),
    path('view/<hid:pk>/', views.maintenance_detail, name='maintenance_view'),
    path('edit/<hid:pk>/', views.maintenance_edit, name='maintenance_edit'),

    # ✅ BARU: Laporan bulanan & Export
    path('report/', views.maintenance_report, name='maintenance_report'),
    path('export/', views.export_maintenance_excel, name='export_maintenance_excel'),
    path('berita-acara/', views.berita_acara_config, name='berita_acara_config'),
    path('berita-acara/excel/', views.berita_acara_excel, name='berita_acara_excel'),
    path('berita-acara/pdf/', views.berita_acara_pdf, name='berita_acara_pdf'),
    path('export-pdf/<hid:pk>/', views.export_maintenance_pdf, name='export_maintenance_pdf'),
    path('sign/<hid:pk>/', views.maintenance_sign, name='maintenance_sign'),
    path('catatan-am/<hid:pk>/', views.maintenance_catatan_am_edit, name='maintenance_catatan_am_edit'),
    path('profile/', views.profile_view, name='profile_view'),
    # Approval & Coverage
    path('approval/', views.maintenance_approval, name='maintenance_approval'),
    path('coverage/', views.maintenance_coverage, name='maintenance_coverage'),

    # Dashboard Catu Daya
    path('catu-daya/', views.catu_daya_dashboard, name='catu_daya_dashboard'),

    # Corrective Maintenance
    path('corrective/add/',                       views.corrective_add,                              name='corrective_add'),
    path('corrective/device/<hid:device_id>/',    lambda r, device_id: views.corrective_add(r, device_id=device_id),    name='corrective_add_device'),
    path('corrective/gangguan/<hid:gangguan_id>/', lambda r, gangguan_id: views.corrective_add(r, gangguan_id=gangguan_id), name='corrective_add_gangguan'),
    path('corrective/edit/<hid:pk>/',             views.corrective_edit, name='corrective_edit'),
    # Offline Form (download template & upload)
    path('offline/download/', views.offline_form_download, name='offline_form_download'),
    path('offline/upload/',   views.offline_form_upload,   name='offline_form_upload'),

    # Ekspor Data — Berita Acara
    path('ekspor/pemasangan/',   views.ba_pemasangan,   name='ba_pemasangan'),
    path('ekspor/pembongkaran/', views.ba_pembongkaran, name='ba_pembongkaran'),
    path('ekspor/penggantian/',  views.ba_penggantian,  name='ba_penggantian'),

    # List & aksi BA
    path('ekspor/list/',                    views.ba_list,         name='ba_list'),
    path('ekspor/<hid:pk>/export/',         views.ba_export,       name='ba_export'),
    path('ekspor/<hid:pk>/preview/',        views.ba_preview,      name='ba_preview'),
    path('ekspor/<hid:pk>/hapus/',          views.ba_delete,       name='ba_delete'),
    path('ekspor/<hid:pk>/minta-ttd/',      views.ba_request_sign, name='ba_request_sign'),
    path('ekspor/<hid:pk>/ttd-engineer/',   views.ba_sign_engineer,name='ba_sign_engineer'),
    path('ekspor/<hid:pk>/ttd-am/',         views.ba_sign_am,      name='ba_sign_am'),
]