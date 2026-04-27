"""
URL configuration for fasop project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include, register_converter
from django.contrib.auth import views as auth_views
from django.conf.urls.static import static
from django.views.defaults import page_not_found
from devices.views import fo_public
from fasop.converters import HashIdConverter

register_converter(HashIdConverter, 'hid')

handler404 = 'django.views.defaults.page_not_found'

urlpatterns = [
    path('secure-panel/', admin.site.urls),
    path('', include('devices.urls')),
    path('maintenance/', include('maintenance.urls')),
    path('gangguan/', include('gangguan.urls')),
    path('health-index/', include('health_index.urls')),
    path('notifikasi/', include('notifikasi.urls')),
    path('jadwal/', include('jadwal.urls')),

    # REST API — untuk integrasi n8n / Google Sheets
    path('api/v1/', include('api.urls')),

    # Gudang — alat uji & spare part
    path('gudang/', include('gudang.urls')),

    # Inservice Inspection — role Operator
    path('inspection/', include('inspection.urls')),

    # Opsis — Monitoring Pembangkit (role Opsis)
    path('opsis/', include('opsis.urls')),

    # Device Monitor — Status RTU Realtime + Availability
    path('device-mon/', include('device_mon.urls')),

    # Common Enemy — Masalah kronik / berulang pada peralatan
    path('common-enemy/', include('common_enemy.urls')),

    # Dokumentasi — Setting Rele & Gambar/Wiring Diagram
    path('dokumentasi/', include('dokumentasi.urls')),

    # Public FO page — tanpa login (QR scan)
    path('fo/public/<str:token>/', fo_public, name='fo_public'),

    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('ganti-password/', include('devices.urls_auth')),

    

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)