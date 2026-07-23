from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='up2b_dashboard'),
    path('analog/', views.kinerja_analog, name='up2b_kinerja_analog'),
    path('digital/', views.kinerja_digital, name='up2b_kinerja_digital'),
    path('rc/', views.kinerja_rc, name='up2b_kinerja_rc'),
    path('soe-log/', views.soe_log, name='up2b_soe_log'),
]
