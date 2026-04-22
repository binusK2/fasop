from django.urls import path
from . import views

urlpatterns = [
    path('',              views.dashboard,         name='opsis_dashboard'),
    path('<int:pk>/',     views.pembangkit_detail, name='opsis_pembangkit'),
    path('api/live/',     views.api_live,          name='opsis_api_live'),
    path('api/trend/<int:pk>/', views.api_trend,   name='opsis_api_trend'),
]
