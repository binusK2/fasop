from django.urls import path
from . import views

urlpatterns = [
    path('',                    views.dashboard,           name='dm_dashboard'),
    path('api/status/',         views.api_status,          name='dm_api_status'),
    path('rtu/<int:pk>/',       views.rtu_detail,          name='dm_rtu_detail'),
    path('rtu/<int:pk>/logs/',  views.api_rtu_logs,        name='dm_api_rtu_logs'),
    path('gangguan/',           views.gangguan_list,       name='dm_gangguan'),
    path('availability/',       views.availability_report, name='dm_availability'),
]
