"""Tes halaman detail pemeliharaan.

Keluarga Master Station (Master Station, Workstation SCADA, Server Telkom,
Server Prosis, Workstation PC) memakai satu partial bersama; kalau partial itu
me-`include` berkas yang tidak ada, halaman detailnya balas HTTP 500 begitu
detail pemeliharaannya sudah terisi — dan itu baru ketahuan di produksi.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile

from .models import Maintenance, MaintenanceMasterStation


class MasterStationDetailTests(TestCase):
    """Halaman detail untuk perangkat keluarga Master Station harus terbuka."""

    JENIS = ('MASTER STATION', 'WORKSTATION SCADA', 'SERVER TELKOM',
             'SERVER PROSIS', 'WORKSTATION PC')

    def setUp(self):
        self.user = User.objects.create_superuser(username='admin', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()

    def _buat(self, nama_jenis, dengan_detail=True):
        jenis = DeviceType.objects.create(name=nama_jenis)
        device = Device.objects.create(nama=f'{nama_jenis}-01', jenis=jenis,
                                       merk='HP', lokasi='UP2B MAKASSAR')
        m = Maintenance.objects.create(device=device, maintenance_type='Preventive',
                                       date=timezone.now(), description='uji')
        if dengan_detail:
            MaintenanceMasterStation.objects.create(
                maintenance=m, spek_merk='HP', spek_type='DL380', spek_ip='10.10.10.5',
                kondisi_server='BERSIH', kondisi_panel='BERSIH',
                temp_ruangan=22.5, temp_peralatan=35.0,
                power_supply='ADA, BERFUNGSI', fan_processor='ADA, BERFUNGSI',
                indikasi_alarm='TIDAK ADA', time_sync='OK',
                copper_jumlah=2, copper_kondisi='OK', fo_jumlah=2, fo_kondisi='OK')
        return m

    def test_detail_terbuka_untuk_semua_jenis(self):
        self.client.force_login(self.user)
        for nama_jenis in self.JENIS:
            with self.subTest(jenis=nama_jenis):
                m = self._buat(nama_jenis)
                resp = self.client.get(reverse('maintenance_view', args=[m.pk]))
                self.assertEqual(resp.status_code, 200)

    def test_seksi_master_station_ikut_dirender(self):
        self.client.force_login(self.user)
        m = self._buat('SERVER TELKOM')
        resp = self.client.get(reverse('maintenance_view', args=[m.pk]))
        self.assertContains(resp, 'Spesifikasi')
        self.assertContains(resp, 'Kondisi Peralatan')
        self.assertContains(resp, 'Performa Peralatan')
        self.assertContains(resp, 'Komunikasi')
        self.assertContains(resp, '10.10.10.5')

    def test_detail_terbuka_meski_belum_ada_detail_pemeliharaan(self):
        self.client.force_login(self.user)
        m = self._buat('SERVER TELKOM', dengan_detail=False)
        resp = self.client.get(reverse('maintenance_view', args=[m.pk]))
        self.assertEqual(resp.status_code, 200)
