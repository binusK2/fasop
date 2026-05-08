from django.urls import path
from . import views

urlpatterns = [
    path('',               views.scada_av_list,     name='scada_av_list'),
    path('upload/',        views.scada_av_upload,   name='scada_av_upload'),
    path('<int:pk>/',      views.scada_av_detail,   name='scada_av_detail'),
    path('<int:pk>/download/', views.scada_av_download, name='scada_av_download'),
]
