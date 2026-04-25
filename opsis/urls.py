from django.urls import path
from . import views

urlpatterns = [
    path('',              views.dashboard,         name='opsis_dashboard'),
    path('<int:pk>/',     views.pembangkit_detail, name='opsis_pembangkit'),
    path('api/live/',     views.api_live,          name='opsis_api_live'),
    path('api/trend/<int:pk>/', views.api_trend,   name='opsis_api_trend'),
    path('api/freq/',            views.api_freq,     name='opsis_api_freq'),
    path('api/beban/',           views.api_beban,    name='opsis_api_beban'),
    path('api/hz/',              views.api_hz,       name='opsis_api_hz'),
    path('api/ping/',            views.api_ping,     name='opsis_api_ping'),
    path('api/diagnose/',       views.api_diagnose, name='opsis_api_diagnose'),
    path('api/history/<int:pk>/', views.api_history,        name='opsis_api_history'),
    path('export/frekuensi/',     views.export_frekuensi,   name='opsis_export_frekuensi'),
    path('export/beban/',         views.export_beban,        name='opsis_export_beban'),
    path('rangkuman/',            views.rangkuman,           name='opsis_rangkuman'),
]
