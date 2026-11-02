"""Tes filter Lokasi di daftar peralatan (/devices/).

Dulu pilihan dropdown Lokasi hanya diambil dari Device.lokasi, sehingga lokasi
yang baru didaftarkan di Manajemen Lokasi (SiteLocation) tidak pernah muncul
sampai ada peralatan yang dipasang di sana.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Device, DeviceType, SiteLocation, UserProfile


class FilterLokasiDeviceListTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='teknisi', password='rahasia')
        p, _ = UserProfile.objects.get_or_create(user=self.user)
        p.role = 'technician'
        p.force_password_change = False
        p.save()
        self.client.force_login(self.user)
        self.jenis = DeviceType.objects.create(name='ROUTER')

    def _pilihan(self):
        resp = self.client.get(reverse('device_list'))
        self.assertEqual(resp.status_code, 200)
        return list(resp.context['lokasi_list'])

    def _filter(self, lokasi):
        resp = self.client.get(reverse('device_list'),
                               {'_filter': '1', 'lokasi': lokasi})
        self.assertEqual(resp.status_code, 200)
        return [d.nama for d in resp.context['devices']]

    def test_lokasi_baru_tanpa_peralatan_muncul(self):
        SiteLocation.objects.create(nama='GI BARU')
        self.assertIn('GI BARU', self._pilihan())

    def test_lokasi_lama_yang_tidak_terdaftar_tetap_muncul(self):
        Device.objects.create(nama='R1', merk='X', lokasi='GI LAMA', jenis=self.jenis)
        self.assertIn('GI LAMA', self._pilihan())

    def test_tidak_ada_lokasi_kembar(self):
        SiteLocation.objects.create(nama='GI TELLO')
        Device.objects.create(nama='R1', merk='X', lokasi='GI TELLO', jenis=self.jenis)
        Device.objects.create(nama='R2', merk='X', lokasi='Gi Tello ', jenis=self.jenis)
        pilihan = self._pilihan()
        self.assertEqual([p for p in pilihan if p.upper() == 'GI TELLO'], ['GI TELLO'])

    def test_lokasi_kosong_dan_none_tidak_ikut(self):
        Device.objects.create(nama='R1', merk='X', lokasi='', jenis=self.jenis)
        Device.objects.create(nama='R2', merk='X', lokasi='None', jenis=self.jenis)
        self.assertEqual(self._pilihan(), [])

    def test_pilihan_urut_abjad(self):
        SiteLocation.objects.create(nama='GI ZETA')
        Device.objects.create(nama='R1', merk='X', lokasi='GI ALFA', jenis=self.jenis)
        self.assertEqual(self._pilihan(), ['GI ALFA', 'GI ZETA'])

    def test_filter_tidak_peka_huruf_dan_spasi(self):
        Device.objects.create(nama='R1', merk='X', lokasi='Gi Tello ', jenis=self.jenis)
        Device.objects.create(nama='R2', merk='X', lokasi='GI DAYA', jenis=self.jenis)
        self.assertEqual(self._filter('GI TELLO'), ['R1'])

    def test_filter_lokasi_baru_tanpa_peralatan(self):
        SiteLocation.objects.create(nama='GI BARU')
        Device.objects.create(nama='R1', merk='X', lokasi='GI DAYA', jenis=self.jenis)
        self.assertEqual(self._filter('GI BARU'), [])

    def test_halaman_per_jenis_juga_memuat_lokasi_baru(self):
        SiteLocation.objects.create(nama='GI BARU')
        resp = self.client.get(reverse('device_by_type', args=[self.jenis.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('GI BARU', list(resp.context['lokasi_list']))
