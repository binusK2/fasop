from django.urls import path
from . import views

urlpatterns = [
    path('',                views.hi_list,          name='hi_list'),
    path('settings/',       views.hi_settings,      name='hi_settings'),
    path('export/pdf/',     views.export_hi_pdf,    name='export_hi_pdf'),
    path('export/jadwal/',  views.export_jadwal_pdf, name='export_jadwal_pdf'),
    path('<int:pk>/',       views.hi_detail,        name='hi_detail'),
]
