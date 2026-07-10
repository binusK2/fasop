from django.urls import path

from . import views

app_name = 'streaming'

urlpatterns = [
    path('', views.session_list, name='list'),
    path('mulai/', views.start_session, name='start'),
    path('<hid:pk>/', views.session_detail, name='detail'),
    path('<hid:pk>/gabung-pengawas/', views.join_pengawas, name='join_pengawas'),
    path('<hid:pk>/selesai/', views.end_session, name='end'),
    path('webhook/mediamtx-auth/', views.mediamtx_auth_webhook, name='mediamtx_auth_webhook'),
]
