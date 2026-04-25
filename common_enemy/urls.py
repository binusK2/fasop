from django.urls import path
from . import views

urlpatterns = [
    path('',                                        views.ce_list,          name='ce_list'),
    path('tambah/',                                 views.ce_create,        name='ce_create'),
    path('<hid:pk>/',                               views.ce_detail,        name='ce_detail'),
    path('<hid:pk>/edit/',                          views.ce_update,        name='ce_update'),
    path('<hid:pk>/update-status/',                 views.ce_update_status, name='ce_update_status'),
    path('<hid:pk>/log/tambah/',                    views.ce_add_log,       name='ce_add_log'),
    path('<hid:pk>/log/<hid:log_pk>/hapus/',        views.ce_delete_log,    name='ce_delete_log'),
]
