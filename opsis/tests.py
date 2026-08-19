"""
Tes prediksi beban berbasis spreadsheet (opsis/prakiraan.py) dan endpoint
penerima kurvanya (api/views.py::prakiraan_beban_endpoint).

Jalankan: python manage.py test opsis
"""
import datetime
import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Pembangkit, PrakiraanBeban, SnapLive
from . import prakiraan, prediksi

API_KEY = 'kunci-tes-prakiraan'


def _waktu_lokal(tanggal, menit):
    """datetime tz-aware pada `menit` sejak 00:00 waktu lokal."""
    tz = timezone.get_current_timezone()
    return timezone.make_aware(
        datetime.datetime.combine(tanggal, datetime.time.min), tz
    ) + datetime.timedelta(minutes=menit)


class PrakiraanBebanTest(TestCase):
    """Kurva spreadsheet dibaca benar dan dibandingkan ke realisasi SnapLive."""

    @classmethod
    def setUpTestData(cls):
        cls.hari_ini = timezone.localdate()
        cls.besok = cls.hari_ini + datetime.timedelta(days=1)
        cls.kit_a = Pembangkit.objects.create(kode='KITA', nama='PLTU A', kode_kit='KITA')
        cls.kit_b = Pembangkit.objects.create(kode='KITB', nama='PLTU B', kode_kit='KITB')

    def _isi_kurva(self, tanggal, nilai_per_menit):
        for menit, mw in nilai_per_menit.items():
            PrakiraanBeban.objects.create(tanggal=tanggal, menit=menit, mw=mw)

    def _isi_realisasi(self, tanggal, nilai_per_menit):
        """Realisasi dibagi dua pembangkit — total sistem = jumlah keduanya."""
        for menit, mw in nilai_per_menit.items():
            waktu = _waktu_lokal(tanggal, menit)
            SnapLive.objects.create(pembangkit=self.kit_a, waktu=waktu, mw=mw * 0.6)
            SnapLive.objects.create(pembangkit=self.kit_b, waktu=waktu, mw=mw * 0.4)

    def test_kurva_hari_ini_dan_puncak(self):
        self._isi_kurva(self.hari_ini, {0: 800.0, 720: 900.0, 1110: 1000.0})
        self._isi_realisasi(self.hari_ini, {720: 890.0, 1110: 1010.0})

        hasil = prakiraan.predict_beban_hari_ini()

        self.assertEqual(hasil['source'], 'sheet')
        self.assertEqual([p['minute'] for p in hasil['forecast']], [0, 720, 1110])
        self.assertEqual(hasil['prediksi_puncak_siang'], 900.0)
        self.assertEqual(hasil['prediksi_puncak_malam'], 1000.0)
        self.assertEqual(hasil['realisasi_puncak_siang'], 890.0)
        self.assertEqual(hasil['realisasi_puncak_malam'], 1010.0)
        # 'actual' menjumlahkan semua pembangkit per menit, bukan satu baris per KIT
        self.assertEqual(len(hasil['actual']), 2)

    def test_realisasi_none_bila_titik_belum_terlewati(self):
        self._isi_kurva(self.hari_ini, {720: 900.0})
        hasil = prakiraan.predict_beban_hari_ini()
        self.assertEqual(hasil['prediksi_puncak_siang'], 900.0)
        self.assertIsNone(hasil['realisasi_puncak_siang'])

    def test_realisasi_toleransi_2_menit_hanya_ke_belakang(self):
        self._isi_kurva(self.hari_ini, {720: 900.0})
        # SnapLive telat 2 menit (12:02) tidak boleh dipakai untuk titik 12:00;
        # yang 11:58 boleh (toleransi ke belakang).
        self._isi_realisasi(self.hari_ini, {718: 880.0, 722: 999.0})
        hasil = prakiraan.predict_beban_hari_ini()
        self.assertEqual(hasil['realisasi_puncak_siang'], 880.0)

    def test_hari_lain_tidak_ikut_terbawa(self):
        self._isi_kurva(self.hari_ini, {720: 900.0})
        self._isi_kurva(self.besok, {720: 950.0, 1110: 1100.0})

        hasil = prakiraan.predict_beban_hari_ini()
        self.assertEqual(len(hasil['forecast']), 1)

        besok = prakiraan.predict_besok_puncak()
        self.assertEqual(besok['source'], 'sheet')
        self.assertEqual(besok['prediksi_puncak_siang_besok'], 950.0)
        self.assertEqual(besok['prediksi_puncak_malam_besok'], 1100.0)

    def test_besok_belum_diunggah(self):
        besok = prakiraan.predict_besok_puncak()
        self.assertEqual(besok['source'], 'no_sheet')
        self.assertIsNone(besok['prediksi_puncak_siang_besok'])

    def test_akurasi_dihitung_dari_pasangan_yang_punya_realisasi(self):
        # Dua titik punya realisasi (selisih 10 MW dari 1000 -> MAPE 1%),
        # satu titik belum ada realisasinya -> harus dilewati, bukan dianggap 0.
        self._isi_kurva(self.hari_ini, {600: 1010.0, 660: 990.0, 1110: 1200.0})
        self._isi_realisasi(self.hari_ini, {600: 1000.0, 660: 1000.0})

        a = prakiraan.evaluate_accuracy(days=7)
        self.assertEqual(a['n'], 2)
        self.assertAlmostEqual(a['mae'], 10.0, places=2)
        self.assertAlmostEqual(a['rmse'], 10.0, places=2)
        self.assertAlmostEqual(a['mape_percent'], 1.0, places=2)
        self.assertAlmostEqual(a['akurasi_percent'], 99.0, places=2)

    def test_akurasi_kosong_bila_belum_ada_prakiraan(self):
        a = prakiraan.evaluate_accuracy(days=7)
        self.assertEqual(a['n'], 0)
        self.assertIsNone(a['akurasi_percent'])
        self.assertEqual(a['period_days'], 7)

    def test_akurasi_abaikan_hari_di_luar_rentang(self):
        lama = self.hari_ini - datetime.timedelta(days=30)
        self._isi_kurva(lama, {600: 1010.0})
        self._isi_realisasi(lama, {600: 1000.0})
        self.assertEqual(prakiraan.evaluate_accuracy(days=7)['n'], 0)


class SumberPrediksiTest(TestCase):
    """Switch OPSIS_FORECAST_SOURCE memilih implementasi yang benar."""

    @override_settings(OPSIS_FORECAST_SOURCE='sheet')
    def test_default_sheet(self):
        self.assertEqual(prediksi.sumber_aktif(), 'sheet')
        self.assertEqual(prediksi.predict_besok_puncak()['source'], 'no_sheet')

    @override_settings(OPSIS_FORECAST_SOURCE='ML')
    def test_ml_case_insensitive(self):
        self.assertEqual(prediksi.sumber_aktif(), 'ml')

    @override_settings(OPSIS_FORECAST_SOURCE='entah-apa')
    def test_nilai_tak_dikenal_jatuh_ke_sheet(self):
        self.assertEqual(prediksi.sumber_aktif(), 'sheet')


@override_settings(API_KEY=API_KEY)
class PrakiraanBebanEndpointTest(TestCase):
    """POST /api/v1/prakiraan-beban/ — jalur n8n dari Google Sheets."""

    def setUp(self):
        self.url = reverse('api:prakiraan_beban')
        self.hari_ini = timezone.localdate()

    def _post(self, payload, key=API_KEY):
        headers = {'X-API-Key': key} if key else {}
        return self.client.post(self.url, data=json.dumps(payload),
                                content_type='application/json', headers=headers)

    def test_tolak_tanpa_api_key(self):
        self.assertEqual(self._post({'data': []}, key=None).status_code, 401)

    def test_tolak_api_key_salah(self):
        self.assertEqual(self._post({'data': []}, key='salah').status_code, 403)

    def test_terima_jam_hh_mm_dan_menit(self):
        r = self._post({
            'tanggal': self.hari_ini.isoformat(),
            'data': [
                {'jam': '00:00', 'mw': 800},
                {'jam': '18:30:00', 'mw': '1.010,5'.replace('.', '')},  # koma desimal
                {'menit': 720, 'mw': 900.25},
            ],
        })
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['titik_ditulis'], 3)
        self.assertEqual(body['dilewati'], 0)
        self.assertEqual(
            list(PrakiraanBeban.objects.filter(tanggal=self.hari_ini)
                 .order_by('menit').values_list('menit', flat=True)),
            [0, 720, 1110])
        self.assertEqual(
            PrakiraanBeban.objects.get(tanggal=self.hari_ini, menit=1110).mw, 1010.5)

    def test_idempoten_dan_memperbarui_nilai(self):
        payload = {'tanggal': self.hari_ini.isoformat(),
                   'data': [{'menit': 720, 'mw': 900}]}
        self._post(payload)
        payload['data'][0]['mw'] = 950
        self._post(payload)
        self.assertEqual(PrakiraanBeban.objects.count(), 1)
        self.assertEqual(PrakiraanBeban.objects.get().mw, 950.0)

    def test_baris_boleh_bawa_tanggal_sendiri(self):
        besok = self.hari_ini + datetime.timedelta(days=1)
        r = self._post({
            'tanggal': self.hari_ini.isoformat(),
            'data': [
                {'menit': 720, 'mw': 900},
                {'tanggal': besok.isoformat(), 'menit': 720, 'mw': 950},
            ],
        })
        self.assertEqual(r.json()['titik_ditulis'], 2)
        self.assertEqual(sorted(r.json()['tanggal_tertulis']),
                         sorted([self.hari_ini.isoformat(), besok.isoformat()]))

    def test_sel_kosong_dilewati_tanpa_error(self):
        r = self._post({'data': [{'menit': 0, 'mw': ''}, {'menit': 30, 'mw': None},
                                 {'menit': 60, 'mw': 810}]})
        body = r.json()
        self.assertEqual(body['titik_ditulis'], 1)
        self.assertEqual(body['dilewati'], 2)
        self.assertEqual(body['errors'], [])

    def test_nilai_tidak_valid_dilaporkan(self):
        r = self._post({'data': [{'menit': 1500, 'mw': 800},
                                 {'jam': 'pagi', 'mw': 800},
                                 {'menit': 0, 'mw': 'abc'}]})
        body = r.json()
        self.assertEqual(body['titik_ditulis'], 0)
        self.assertEqual(len(body['errors']), 3)
        self.assertEqual(PrakiraanBeban.objects.count(), 0)

    def test_replace_menghapus_titik_yang_tidak_dikirim(self):
        self._post({'tanggal': self.hari_ini.isoformat(),
                    'data': [{'menit': 0, 'mw': 800}, {'menit': 30, 'mw': 810}]})
        # Tanpa replace: titik lama tetap ada.
        self._post({'tanggal': self.hari_ini.isoformat(),
                    'data': [{'menit': 0, 'mw': 805}]})
        self.assertEqual(PrakiraanBeban.objects.count(), 2)
        # Dengan replace: titik 30 ikut terhapus.
        self._post({'tanggal': self.hari_ini.isoformat(), 'replace': True,
                    'data': [{'menit': 0, 'mw': 806}]})
        self.assertEqual(
            list(PrakiraanBeban.objects.values_list('menit', flat=True)), [0])

    def test_replace_tidak_menyentuh_tanggal_lain(self):
        besok = self.hari_ini + datetime.timedelta(days=1)
        PrakiraanBeban.objects.create(tanggal=besok, menit=720, mw=950)
        self._post({'tanggal': self.hari_ini.isoformat(), 'replace': True,
                    'data': [{'menit': 0, 'mw': 800}]})
        self.assertTrue(PrakiraanBeban.objects.filter(tanggal=besok, menit=720).exists())

    def test_tolak_data_bukan_array(self):
        self.assertEqual(self._post({'data': {'menit': 0}}).status_code, 400)

    def test_tolak_payload_kelewat_besar(self):
        r = self._post({'data': [{'menit': 0, 'mw': 1}] * 2001})
        self.assertEqual(r.status_code, 400)

    def test_payload_apa_adanya_dari_node_code_n8n(self):
        """
        Bentuk payload persis seperti yang dihasilkan node Code di
        docs/n8n_prakiraan_beban*.workflow.json: `menit` dan `mw` sudah
        dinormalkan di sisi n8n (sel Jam/MW di .xlsx bisa berupa angka, Date,
        atau teks dengan pemisah ribuan), jadi yang masuk ke sini angka murni.
        """
        besok = self.hari_ini + datetime.timedelta(days=1)
        r = self._post({
            'sumber': 'roh-sulbagsel',
            'data': [
                {'menit': 0, 'mw': 812.5, 'tanggal': self.hari_ini.isoformat()},
                {'menit': 720, 'mw': 1024, 'tanggal': self.hari_ini.isoformat()},
                {'menit': 1110, 'mw': 1187.3, 'tanggal': self.hari_ini.isoformat()},
                {'menit': 720, 'mw': 950, 'tanggal': besok.isoformat()},
                {'menit': 1410, 'mw': 890, 'tanggal': self.hari_ini.isoformat()},
            ],
        })
        body = r.json()
        self.assertEqual(body['titik_ditulis'], 5)
        self.assertEqual(body['errors'], [])
        self.assertEqual(
            PrakiraanBeban.objects.get(tanggal=self.hari_ini, menit=0).mw, 812.5)
        self.assertEqual(
            PrakiraanBeban.objects.get(tanggal=self.hari_ini, menit=1110).mw, 1187.3)
        self.assertEqual(
            PrakiraanBeban.objects.get(tanggal=besok, menit=720).mw, 950.0)
        self.assertEqual(
            PrakiraanBeban.objects.get(tanggal=self.hari_ini, menit=0).sumber,
            'roh-sulbagsel')

    def test_get_baca_balik_kurva(self):
        PrakiraanBeban.objects.create(tanggal=self.hari_ini, menit=1110, mw=1000)
        r = self.client.get(self.url, {'tanggal': self.hari_ini.isoformat()},
                            headers={'X-API-Key': API_KEY})
        body = r.json()
        self.assertEqual(body['jumlah'], 1)
        self.assertEqual(body['data'][0]['jam'], '18:30')


class KeteranganSumberDashboardTest(TestCase):
    """Dashboard OPSIS menyebutkan asal angka prediksi, bukan cuma "Prediksi"."""

    def setUp(self):
        # force_login, bukan login() — AxesBackend menolak authenticate()
        # tanpa objek request.
        user = User.objects.create_superuser('adm-tes', 'adm@contoh.id', 'rahasia-tes-123')
        # ForcePasswordChangeMiddleware mengalihkan user baru ke /ganti-password/
        # sebelum sempat sampai ke dashboard.
        profile = getattr(user, 'profile', None)
        if profile is not None:
            profile.force_password_change = False
            profile.save(update_fields=['force_password_change'])
        self.client.force_login(user)

    def test_dashboard_menyebut_dashboard_roh_sulbagsel(self):
        r = self.client.get('/opsis/')
        self.assertEqual(r.status_code, 200)
        isi = r.content.decode()
        self.assertIn('Dashboard ROH Sulbagsel', isi)
        self.assertIn('beban-sumber-prediksi', isi)

    def test_halaman_analitik_menyebut_sumbernya(self):
        r = self.client.get('/opsis/prediksi-beban/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Dashboard ROH Sulbagsel', r.content.decode())
