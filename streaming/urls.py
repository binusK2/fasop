from django.urls import path

from . import views

app_name = 'streaming'

urlpatterns = [
    path('', views.session_list, name='list'),
    path('mulai/', views.start_session, name='start'),
    path('<hid:pk>/', views.session_detail, name='detail'),
    path('<hid:pk>/status/', views.session_status, name='status'),
    path('<hid:pk>/heartbeat/', views.session_heartbeat, name='heartbeat'),
    path('<hid:pk>/gabung-pengawas/', views.join_pengawas, name='join_pengawas'),
    path('<hid:pk>/selesai/', views.end_session, name='end'),
    path('<hid:pk>/rekaman/', views.session_recording, name='recording'),
    path('<hid:pk>/rekaman/file/', views.serve_recording, name='recording_file'),
    path('webhook/mediamtx-auth/', views.mediamtx_auth_webhook, name='mediamtx_auth_webhook'),
    path('webhook/mediamtx-record/', views.mediamtx_record_webhook, name='mediamtx_record_webhook'),
]
