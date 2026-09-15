from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('',                    views.dashboard,           name='dm_dashboard'),
    path('api/status/',         views.api_status,          name='dm_api_status'),
    path('rtu/<int:pk>/',       views.rtu_detail,          name='dm_rtu_detail'),
    path('rtu/<int:pk>/logs/',  views.api_rtu_logs,        name='dm_api_rtu_logs'),
    path('gangguan/',           views.gangguan_list,       name='dm_gangguan'),
    path('availability/',       views.availability_report, name='dm_availability'),
    path('export/availability/', views.export_availability, name='dm_export_availability'),

    # ── Zabbix — status host dipantau lewat Zabbix API (pull) + webhook (push) ──
    # BISA LEBIH DARI SATU instansi (device_mon.ZabbixInstance, mis. 'telkom' /
    # 'prosis') — <slug:kode> memilih instansinya, jadi menambah instansi baru
    # tidak perlu path baru di sini, cukup baris admin baru.
    #
    # Path lama (sebelum multi-instansi) HARUS didaftarkan sebelum
    # 'zabbix/<slug:kode>/...' di bawah: 'webhook' dan 'gangguan' adalah slug
    # yang sah juga, jadi kalau pola <slug:kode> dicek lebih dulu ia akan
    # "mencuri" kedua path literal ini (mis. POST /zabbix/webhook/ akan
    # nyasar ke zbx_dashboard(kode='webhook') alih-alih webhook receiver).
    # Webhook lama sengaja alias LANGSUNG (bukan redirect 302) ke instansi
    # 'telkom' — redirect tidak bisa diandalkan untuk POST dari skrip webhook
    # Zabbix. Path halaman lama (dashboard/group/gangguan) memakai redirect
    # 302, pola yang sama dengan /streaming/dinding/ -> /streaming/multi-view/.
    path('zabbix/webhook/', views.zbx_webhook_receiver, {'kode': 'telkom'}, name='dm_zbx_webhook'),
    path('zabbix/gangguan/', RedirectView.as_view(pattern_name='dm_zbx_gangguan', permanent=False),
         kwargs={'kode': 'telkom'}),
    path('zabbix/group/<str:group>/',
         RedirectView.as_view(pattern_name='dm_zbx_group_detail', permanent=False),
         kwargs={'kode': 'telkom'}),
    path('zabbix/', RedirectView.as_view(pattern_name='dm_zbx_dashboard', permanent=False),
         kwargs={'kode': 'telkom'}),

    # Host detail dari hashid pk saja sudah unik lintas instansi — tidak perlu <kode>.
    path('zabbix/host/<hid:pk>/',      views.zbx_host_detail,      name='dm_zbx_host_detail'),
    path('zabbix/host/<hid:pk>/logs/', views.zbx_api_host_logs,    name='dm_zbx_api_host_logs'),

    # Rute per-instansi.
    path('zabbix/<slug:kode>/',                   views.zbx_dashboard,        name='dm_zbx_dashboard'),
    path('zabbix/<slug:kode>/api/summary/',       views.zbx_api_summary,      name='dm_zbx_api_summary'),
    path('zabbix/<slug:kode>/api/status/',        views.zbx_api_status,       name='dm_zbx_api_status'),
    path('zabbix/<slug:kode>/group/<str:group>/', views.zbx_group_detail,     name='dm_zbx_group_detail'),
    path('zabbix/<slug:kode>/gangguan/',          views.zbx_gangguan_list,    name='dm_zbx_gangguan'),
    path('zabbix/<slug:kode>/webhook/',           views.zbx_webhook_receiver, name='dm_zbx_webhook_instansi'),
]
