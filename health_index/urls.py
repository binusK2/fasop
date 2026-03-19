from django.urls import path
from . import views

urlpatterns = [
    path('', views.hi_list, name='hi_list'),
    path('<int:pk>/', views.hi_detail, name='hi_detail'),
]
