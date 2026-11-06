"""Kunci filter di halaman Semua Pemeliharaan.

Filter disimpan di session supaya daftar tidak kembali ke semua data setiap
kali pengguna membuka detail lalu kembali lewat menu. Yang dijaga di sini:
kuncinya bertahan, bisa dilepas, tautan dashboard tetap jujur, dan nilai
rusak tidak bisa "terkunci" sampai membuat halaman error terus-menerus.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile

from .models import Maintenance
from .views import SESI_FILTER_DAFTAR


class KunciFilterDaftarTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_filter', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        self.rtu = DeviceType.objects.create(name='RTU')
        tello = Device.objects.create(nama='RTU-TELLO', jenis=self.rtu,
                                      merk='SEL', lokasi='GI TELLO')
        bontoala = Device.objects.create(nama='RTU-BTL', jenis=self.rtu,
                                         merk='SEL', lokasi='GI BONTOALA')
        tgl = timezone.make_aware(timezone.datetime(2026, 3, 10, 8, 0))
        for device, status in ((tello, 'Open'), (tello, 'Done'),
                               (bontoala, 'Open'), (bontoala, 'Done')):
            Maintenance.objects.create(device=device, maintenance_type='Preventive',
                                       date=tgl, description='uji', status=status)
        self.url = reverse('maintenance_list')

    def _jumlah(self, resp):
        return resp.context['paginator'].count

    def test_filter_tetap_berlaku_saat_kembali_tanpa_parameter(self):
        self.client.get(self.url, {'status': 'Open', 'lokasi': 'GI TELLO', 'jenis': '',
                                   'date_from': '', 'date_to': ''})

        resp = self.client.get(self.url)          # mis. klik menu di sidebar
        self.assertEqual(self._jumlah(resp), 1)
        self.assertEqual(resp.context['selected_status'], 'Open')
        self.assertEqual(resp.context['selected_lokasi'], 'GI TELLO')
        self.assertTrue(resp.context['filter_terkunci'])
        self.assertContains(resp, 'Filter Terkunci')

    def test_reset_melepas_kunci(self):
        self.client.get(self.url, {'lokasi': 'GI TELLO'})

        resp = self.client.get(self.url, {'reset_filter': '1'})
        self.assertRedirects(resp, self.url)
        self.assertNotIn(SESI_FILTER_DAFTAR, self.client.session)

        resp = self.client.get(self.url)
        self.assertEqual(self._jumlah(resp), 4)
        self.assertFalse(resp.context['filter_terkunci'])
        self.assertNotContains(resp, 'Filter Terkunci')

    def test_tombol_reset_melepas_kunci_bukan_tautan_polos(self):
        """Tautan polos ke daftar justru memulihkan kunci."""
        resp = self.client.get(self.url, {'lokasi': 'GI TELLO'})
        self.assertContains(resp, f'href="{self.url}?reset_filter=1"')

    def test_filter_dikosongkan_lewat_form_juga_melepas_kunci(self):
        self.client.get(self.url, {'lokasi': 'GI TELLO'})
        self.client.get(self.url, {'status': '', 'lokasi': '', 'jenis': '',
                                   'date_from': '', 'date_to': ''})
        self.assertNotIn(SESI_FILTER_DAFTAR, self.client.session)
        self.assertEqual(self._jumlah(self.client.get(self.url)), 4)

    def test_tautan_dashboard_mengganti_kunci_bukan_digabung(self):
        """'?status=Open' dari dashboard harus menampilkan SEMUA yang Open —
        bukan hanya yang kebetulan cocok dengan lokasi yang terkunci."""
        self.client.get(self.url, {'lokasi': 'GI TELLO'})

        resp = self.client.get(self.url, {'status': 'Open'})
        self.assertEqual(self._jumlah(resp), 2)
        self.assertEqual(resp.context['selected_lokasi'], '')
        self.assertEqual(self.client.session[SESI_FILTER_DAFTAR], {'status': 'Open'})

    def test_halaman_berikutnya_tetap_tersaring(self):
        self.client.get(self.url, {'lokasi': 'GI TELLO'})
        resp = self.client.get(self.url, {'page': '1'})
        self.assertEqual(self._jumlah(resp), 2)
        self.assertEqual(resp.context['querystring'], 'lokasi=GI+TELLO')

    def test_export_mengikuti_filter_terkunci(self):
        """Kalau tautan Export membaca request.GET, daftar yang terkunci
        mengekspor seluruh data."""
        self.client.get(self.url, {'lokasi': 'GI TELLO', 'jenis': str(self.rtu.pk)})
        resp = self.client.get(self.url)
        export = reverse('export_maintenance_excel')
        self.assertContains(resp, f'href="{export}?lokasi=GI+TELLO&amp;jenis={self.rtu.pk}"')
        self.assertContains(resp, 'Jenis: RTU')

    def test_nilai_rusak_tidak_ikut_terkunci(self):
        resp = self.client.get(self.url, {'status': 'Selesai', 'jenis': 'abc',
                                          'date_from': '2026-13-45', 'lokasi': 'GI TELLO'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.session[SESI_FILTER_DAFTAR], {'lokasi': 'GI TELLO'})

    def test_session_rusak_tidak_membuat_halaman_error(self):
        sesi = self.client.session
        sesi[SESI_FILTER_DAFTAR] = {'jenis': 'abc', 'date_to': 'kemarin', 'status': 'Open'}
        sesi.save()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._jumlah(resp), 2)       # hanya status=Open yang sah

        sesi = self.client.session
        sesi[SESI_FILTER_DAFTAR] = 'bukan-dict'
        sesi.save()
        self.assertEqual(self.client.get(self.url).status_code, 200)


class RentangTanggalInklusifTests(TestCase):
    """"Sampai Tanggal" dulu dibandingkan dengan pukul 00.00, jadi pemeliharaan
    di tanggal itu sendiri tidak pernah ikut tampil — di daftar maupun Export."""

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_tgl', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        jenis = DeviceType.objects.create(name='RTU')

        def buat(nama, *waktu):
            d = Device.objects.create(nama=nama, jenis=jenis, merk='SEL', lokasi='GI TELLO')
            Maintenance.objects.create(
                device=d, maintenance_type='Preventive', status='Open', description='uji',
                date=timezone.make_aware(timezone.datetime(*waktu)))   # waktu lokal

        buat('SEBELUM', 2026, 3, 9, 23, 30)
        buat('PAGI', 2026, 3, 10, 0, 0)
        buat('SIANG', 2026, 3, 10, 8, 0)
        buat('MALAM', 2026, 3, 10, 23, 59)
        buat('SESUDAH', 2026, 3, 11, 0, 0)
        self.rentang = {'date_from': '2026-03-10', 'date_to': '2026-03-10'}

    def test_daftar_memuat_seluruh_hari_terakhir(self):
        resp = self.client.get(reverse('maintenance_list'), self.rentang)
        nama = sorted(m.device.nama for m in resp.context['maintenances'])
        self.assertEqual(nama, ['MALAM', 'PAGI', 'SIANG'])

    def test_export_sama_dengan_daftar(self):
        from io import BytesIO
        import openpyxl

        resp = self.client.get(reverse('export_maintenance_excel'), self.rentang)
        self.assertEqual(resp.status_code, 200)
        wb = openpyxl.load_workbook(BytesIO(resp.content))
        isi = {str(c) for ws in wb.worksheets
               for row in ws.iter_rows(values_only=True) for c in row if c}
        for nama in ('PAGI', 'SIANG', 'MALAM'):
            self.assertTrue(any(nama in s for s in isi), nama)
        for nama in ('SEBELUM', 'SESUDAH'):
            self.assertFalse(any(nama in s for s in isi), nama)

    def test_tanggal_rusak_di_export_bukan_error(self):
        resp = self.client.get(reverse('export_maintenance_excel'),
                               {'date_from': 'kemarin', 'date_to': '2026-02-30'})
        self.assertEqual(resp.status_code, 200)
