from django.urls import path
from . import views

urlpatterns = [
    path('',        views.index,        name='logsheet_index'),
    path('export/', views.export_excel,  name='logsheet_export'),
]
