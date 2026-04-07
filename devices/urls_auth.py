from django.urls import path
from . import views_auth

urlpatterns = [
    path('', views_auth.force_change_password, name='force_change_password'),
]
