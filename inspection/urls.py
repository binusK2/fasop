from django.urls import path
from . import views

urlpatterns = [
    path('',                              views.inspection_lokasi,       name='inspection_lokasi'),
    path('dashboard/',                    views.inspection_dashboard,       name='inspection_dashboard'),
    path('dashboard/ultg/<int:pk>/',      views.inspection_dashboard_ultg, name='inspection_dashboard_ultg'),
    path('lokasi/<str:lokasi>/',          views.inspection_device_list,  name='inspection_device_list'),
    path('form/<hid:device_pk>/',         views.inspection_form,         name='inspection_form'),
    path('riwayat/<hid:pk>/',             views.inspection_riwayat,      name='inspection_riwayat'),
    path('riwayat/<hid:pk>/delete/',      views.inspection_delete,       name='inspection_delete'),
    path('riwayat/<hid:pk>/flag/',        views.inspection_flag,         name='inspection_flag'),
    path('riwayat/<hid:pk>/unflag/',      views.inspection_unflag,       name='inspection_unflag'),
    path('riwayat/device/<hid:device_pk>/', views.inspection_riwayat_device, name='inspection_riwayat_device'),
    path('export/',                       views.inspection_export,       name='inspection_export'),
    path('export/ultg/',                  views.inspection_export_ultg,  name='inspection_export_ultg'),
    path('api/last/',                     views.inspection_api_last,     name='inspection_api_last'),

    # Pengujian Telekomunikasi (Dispatcher)
    path('pengujian-telecom/',                          views.pengujian_telecom_dashboard, name='pengujian_telecom_dashboard'),
    path('pengujian-telecom/baru/',                     views.pengujian_telecom_form,      name='pengujian_telecom_form'),
    path('pengujian-radio/baru/',                       views.pengujian_radio_form,         name='pengujian_radio_form'),
    path('pengujian-voip/baru/',                        views.pengujian_voip_form,          name='pengujian_voip_form'),
    path('pengujian-telecom/riwayat/',                  views.pengujian_telecom_list,       name='pengujian_telecom_list'),
    path('pengujian-telecom/riwayat/<int:pk>/',         views.pengujian_telecom_detail,     name='pengujian_telecom_detail'),
    path('pengujian-telecom/riwayat/<int:pk>/delete/',  views.pengujian_telecom_delete,     name='pengujian_telecom_delete'),

    # Kesiapan Fasilitas Operasi — harus sebelum route <hid> generik
    path('kesiapan/',                                  views.kesiapan_list,            name='kesiapan_list'),
    path('kesiapan/baru/',                             views.kesiapan_baru,            name='kesiapan_baru'),
    path('kesiapan/publik/<str:token>/',               views.kesiapan_publik,          name='kesiapan_publik'),
    path('kesiapan/api/device-search/',                views.kesiapan_device_search,   name='kesiapan_device_search'),
    path('kesiapan/<hid:pk>/',                         views.kesiapan_detail,          name='kesiapan_detail'),
    path('kesiapan/<hid:pk>/ubah/',                    views.kesiapan_ubah,            name='kesiapan_ubah'),
    path('kesiapan/<hid:pk>/selesai/',                 views.kesiapan_selesai,         name='kesiapan_selesai'),
    path('kesiapan/<hid:pk>/hapus/',                   views.kesiapan_hapus,           name='kesiapan_hapus'),
    path('kesiapan/<hid:pk>/snapshot-rtu/',            views.kesiapan_snapshot_rtu,    name='kesiapan_snapshot_rtu'),
    path('kesiapan/<hid:pk>/muat-master-station/',     views.kesiapan_muat_master_station,    name='kesiapan_muat_master_station'),
    path('kesiapan/<hid:pk>/muat-telekomunikasi/',     views.kesiapan_muat_telekomunikasi,    name='kesiapan_muat_telekomunikasi'),
    path('kesiapan/<hid:pk>/muat-catu-daya/',          views.kesiapan_muat_catu_daya,         name='kesiapan_muat_catu_daya'),
    path('kesiapan/<hid:pk>/muat-dfr/',                views.kesiapan_muat_dfr,        name='kesiapan_muat_dfr'),
    path('kesiapan/<hid:pk>/item/tambah/',             views.kesiapan_item_tambah,     name='kesiapan_item_tambah'),
    path('kesiapan/<hid:pk>/item/simpan-semua/',       views.kesiapan_item_simpan_semua, name='kesiapan_item_simpan_semua'),
    path('kesiapan/<hid:pk>/item/<hid:item_pk>/ubah/', views.kesiapan_item_ubah,       name='kesiapan_item_ubah'),
    path('kesiapan/<hid:pk>/item/<hid:item_pk>/hapus/', views.kesiapan_item_hapus,     name='kesiapan_item_hapus'),
]
