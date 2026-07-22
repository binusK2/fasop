from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='up2b_dashboard'),
    path('analog/', views.kinerja_analog, name='up2b_kinerja_analog'),
    path('digital/', views.kinerja_digital, name='up2b_kinerja_digital'),
]
