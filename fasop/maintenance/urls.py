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
    path('export-pdf/<int:pk>/', views.export_maintenance_pdf, name='export_maintenance_pdf'),
    path('sign/<int:pk>/', views.maintenance_sign, name='maintenance_sign'),
    path('profile/', views.profile_view, name='profile_view'),
]
