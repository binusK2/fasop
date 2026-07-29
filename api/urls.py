from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Health check — tanpa auth
    path('ping/', views.ping, name='ping'),

    # Device endpoints
    path('devices/', views.devices_endpoint, name='devices'),
    path('device-types/', views.device_types_endpoint, name='device_types'),

    # Logsheet feed untuk n8n -> Google Sheets
    path('logsheet/', views.logsheet_endpoint, name='logsheet'),
    path('logsheet/export/', views.logsheet_export_endpoint, name='logsheet_export'),
    path('logsheet/ranges/', views.logsheet_ranges_endpoint, name='logsheet_ranges'),

    # HOP — terima data dari spreadsheet (n8n -> FASOP)
    path('hop/', views.hop_endpoint, name='hop'),
]
