from django.urls import path
from . import views

urlpatterns = [
    path('setting/',                    views.setting_list,   name='setting_rele_list'),
    path('setting/tambah/',             views.setting_create, name='setting_rele_create'),
    path('setting/<hid:pk>/',           views.setting_detail, name='setting_rele_detail'),
    path('setting/<hid:pk>/edit/',      views.setting_update, name='setting_rele_update'),
    path('gambar/',                     views.gambar_list,    name='gambar_rele_list'),
    path('gambar/tambah/',              views.gambar_create,  name='gambar_rele_create'),
    path('gambar/<hid:pk>/',            views.gambar_detail,  name='gambar_rele_detail'),
    path('gambar/<hid:pk>/edit/',       views.gambar_update,  name='gambar_rele_update'),
]
