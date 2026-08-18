from django.urls import path
from . import views

urlpatterns = [
    path('',                    views.dashboard,       name='zbx_dashboard'),
    path('api/status/',         views.api_status,      name='zbx_api_status'),
    path('host/<hid:pk>/',      views.host_detail,     name='zbx_host_detail'),
    path('host/<hid:pk>/logs/', views.api_host_logs,   name='zbx_api_host_logs'),
    path('gangguan/',           views.gangguan_list,   name='zbx_gangguan'),

    # Webhook — dipanggil oleh Zabbix Action (media type Webhook), tanpa login,
    # diamankan dengan token (lihat views.webhook_receiver).
    path('webhook/',            views.webhook_receiver, name='zbx_webhook'),
]
