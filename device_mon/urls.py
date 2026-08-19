from django.urls import path
from . import views

urlpatterns = [
    path('',                    views.dashboard,           name='dm_dashboard'),
    path('api/status/',         views.api_status,          name='dm_api_status'),
    path('rtu/<int:pk>/',       views.rtu_detail,          name='dm_rtu_detail'),
    path('rtu/<int:pk>/logs/',  views.api_rtu_logs,        name='dm_api_rtu_logs'),
    path('gangguan/',           views.gangguan_list,       name='dm_gangguan'),
    path('availability/',       views.availability_report, name='dm_availability'),
    path('export/availability/', views.export_availability, name='dm_export_availability'),

    # Zabbix — status host dipantau lewat Zabbix API (pull) + webhook (push)
    path('zabbix/',                  views.zbx_dashboard,        name='dm_zbx_dashboard'),
    path('zabbix/api/summary/',      views.zbx_api_summary,      name='dm_zbx_api_summary'),
    path('zabbix/api/status/',       views.zbx_api_status,       name='dm_zbx_api_status'),
    path('zabbix/group/<str:group>/', views.zbx_group_detail,    name='dm_zbx_group_detail'),
    path('zabbix/host/<hid:pk>/',    views.zbx_host_detail,      name='dm_zbx_host_detail'),
    path('zabbix/host/<hid:pk>/logs/', views.zbx_api_host_logs,  name='dm_zbx_api_host_logs'),
    path('zabbix/gangguan/',         views.zbx_gangguan_list,    name='dm_zbx_gangguan'),
    # Webhook — dipanggil oleh Zabbix Action (media type Webhook), tanpa login,
    # diamankan dengan token (lihat views.zbx_webhook_receiver).
    path('zabbix/webhook/',          views.zbx_webhook_receiver, name='dm_zbx_webhook'),
]
