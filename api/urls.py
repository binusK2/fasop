from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Health check — tanpa auth
    path('ping/', views.ping, name='ping'),

    # Device endpoints
    path('devices/', views.devices_endpoint, name='devices'),
    path('device-types/', views.device_types_endpoint, name='device_types'),
]
