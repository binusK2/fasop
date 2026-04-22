from django.urls import path
from . import views

urlpatterns = [
    path('',              views.dashboard,         name='opsis_dashboard'),
    path('<int:pk>/',     views.pembangkit_detail, name='opsis_pembangkit'),
    path('api/live/',     views.api_live,          name='opsis_api_live'),
    path('api/trend/<int:pk>/', views.api_trend,   name='opsis_api_trend'),
    path('api/ping/',            views.api_ping,     name='opsis_api_ping'),
    path('api/diagnose/',       views.api_diagnose, name='opsis_api_diagnose'),
]
