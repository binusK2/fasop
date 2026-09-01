from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'streaming'

urlpatterns = [
    path('', views.session_list, name='list'),
    path('mulai/', views.start_session, name='start'),
    path('multi-view/', views.session_grid, name='grid'),
    # Path lama sebelum halamannya diberi label "Multi View". Dipertahankan
    # sebagai pengalihan supaya tautan yang sudah terlanjur dibagikan (atau
    # di-bookmark di layar ruang operasi) tidak mati. Pengalihan SEMENTARA,
    # bukan 301: 301 disimpan permanen di cache browser, jadi kalau path ini
    # nanti dipakai untuk hal lain, browser yang pernah membukanya tidak akan
    # pernah menanyakannya lagi ke server.
    path('dinding/', RedirectView.as_view(pattern_name='streaming:grid', permanent=False)),
    path('api/sesi-live/', views.api_live_sessions, name='api_live_sessions'),
    path('api/ezviz-token/', views.ezviz_token, name='ezviz_token'),
    path('ezviz/sinkron/', views.ezviz_sync, name='ezviz_sync'),
    path('<hid:pk>/', views.session_detail, name='detail'),
    path('<hid:pk>/status/', views.session_status, name='status'),
    path('<hid:pk>/heartbeat/', views.session_heartbeat, name='heartbeat'),
    path('<hid:pk>/siaran-heartbeat/', views.publisher_heartbeat, name='publisher_heartbeat'),
    path('<hid:pk>/gabung-pengawas/', views.join_pengawas, name='join_pengawas'),
    path('<hid:pk>/selesai/', views.end_session, name='end'),
    path('<hid:pk>/rekaman/', views.session_recording, name='recording'),
    path('<hid:pk>/rekaman/file/', views.serve_recording, name='recording_file'),
    path('<hid:pk>/rekaman/pengawas/', views.serve_talkback_recording, name='talkback_recording_file'),
    path('webhook/mediamtx-auth/', views.mediamtx_auth_webhook, name='mediamtx_auth_webhook'),
    path('webhook/mediamtx-record/', views.mediamtx_record_webhook, name='mediamtx_record_webhook'),
]
