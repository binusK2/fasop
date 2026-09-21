from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Health check — tanpa auth
    path('ping/', views.ping, name='ping'),

    # Device endpoints
    path('devices/', views.devices_endpoint, name='devices'),
    path('device-types/', views.device_types_endpoint, name='device_types'),

    # Logsheet feed untuk n8n -> Google Sheets
    path('logsheet/', views.logsheet_endpoint, name='logsheet'),
    path('logsheet/export/', views.logsheet_export_endpoint, name='logsheet_export'),
    path('logsheet/ranges/', views.logsheet_ranges_endpoint, name='logsheet_ranges'),

    # HOP — terima data dari spreadsheet (n8n -> FASOP)
    path('hop/', views.hop_endpoint, name='hop'),

    # Prakiraan beban OPSIS — kurva 30 menit dari spreadsheet (n8n -> FASOP)
    path('prakiraan-beban/', views.prakiraan_beban_endpoint, name='prakiraan_beban'),

    # ── Endpoint BACA untuk konsumen luar ────────────────────────────────
    # Dikunci devices.KunciApi (siapa) + devices.DatasetApi (data apa), lihat
    # api/registry.py. Rute riwayat didaftarkan SEBELUM rute terkininya bukan
    # karena harus, melainkan supaya keduanya terbaca berpasangan.
    path('opsis/beban-ktt/', views.opsis_beban_ktt_endpoint,
         name='opsis_beban_ktt'),
    path('opsis/beban-pembangkit/', views.opsis_beban_pembangkit_endpoint,
         name='opsis_beban_pembangkit'),
    path('opsis/beban-pembangkit/riwayat/', views.opsis_beban_pembangkit_riwayat_endpoint,
         name='opsis_beban_pembangkit_riwayat'),
    path('opsis/frekuensi/', views.opsis_frekuensi_endpoint,
         name='opsis_frekuensi'),
    path('logsheet/pembebanan/', views.logsheet_pembebanan_endpoint,
         name='logsheet_pembebanan'),
]
