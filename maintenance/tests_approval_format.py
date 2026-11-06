"""Halaman Approval memakai format yang sama dengan Semua Pemeliharaan."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile

from .models import Maintenance
from .views import BARIS_PER_HALAMAN


class FormatApprovalTests(TestCase):

    def setUp(self):
        self.am = User.objects.create_user(username='am_format', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.am)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.am)

        self.rtu = DeviceType.objects.create(name='RTU')
        self.device = Device.objects.create(nama='RTU-01', jenis=self.rtu,
                                            merk='SEL', lokasi='GI TELLO')
        self.url = reverse('maintenance_approval')

    def _buat(self, jumlah, signed=False, tipe='Preventive'):
        for i in range(jumlah):
            Maintenance.objects.create(
                device=self.device, maintenance_type=tipe, status='Done',
                date=timezone.now() - timezone.timedelta(hours=i), description='uji',
                signed_by=self.am if signed else None,
                signed_at=timezone.now() if signed else None)

    def test_tab_disetujui_dipaginasi(self):
        self._buat(BARIS_PER_HALAMAN + 5, signed=True)
        resp = self.client.get(self.url, {'tab': 'approved'})
        self.assertEqual(len(resp.context['approved_list']), BARIS_PER_HALAMAN)
        self.assertEqual(resp.context['jumlah_approved'], BARIS_PER_HALAMAN + 5)
        self.assertContains(resp, f'{BARIS_PER_HALAMAN + 5} Sudah Disetujui')
        self.assertContains(resp, 'href="?tab=approved&page=2"')

        resp = self.client.get(self.url, {'tab': 'approved', 'page': 2})
        self.assertEqual(len(resp.context['approved_list']), 5)

    def test_tab_menunggu_tidak_dipaginasi(self):
        """"Pilih semua" TTD massal harus mencakup SEMUA yang menunggu."""
        self._buat(BARIS_PER_HALAMAN + 5)
        resp = self.client.get(self.url, {'tab': 'pending'})
        self.assertEqual(resp.content.decode().count('class="form-check-input cek-ttd"'),
                         BARIS_PER_HALAMAN + 5)
        self.assertContains(resp, f'{BARIS_PER_HALAMAN + 5} Menunggu Tanda Tangan')

    def test_kolom_sama_dengan_semua_pemeliharaan(self):
        self._buat(1, tipe='Corrective')
        approval = self.client.get(self.url, {'tab': 'pending'})
        daftar = self.client.get(reverse('maintenance_list'))
        for resp in (approval, daftar):
            with self.subTest(halaman=resp.wsgi_request.path):
                self.assertTemplateUsed(resp, 'maintenance/_kolom_daftar_pemeliharaan.html')
                for kolom in ('TANGGAL', 'PERANGKAT', 'LOKASI', 'TIPE', 'PELAKSANA', 'STATUS', 'AKSI'):
                    self.assertContains(resp, f'>{kolom}</th>')
                self.assertContains(resp, 'bi-tools')         # badge Corrective

    def test_filter_memakai_tombol_dan_reset_melepas_kunci(self):
        self.client.get(self.url, {'tab': 'pending', 'lokasi': 'GI TELLO'})
        resp = self.client.get(self.url)
        self.assertContains(resp, 'Filter Terkunci')
        self.assertContains(resp, 'Lokasi: GI TELLO')
        self.assertContains(resp, 'href="?tab=pending&reset_filter=1"')
        self.assertNotContains(resp, 'onchange="this.form.submit()"')

    def test_jenis_rusak_di_session_tidak_membuat_error(self):
        sesi = self.client.session
        sesi['approval_jenis_id'] = 'abc'
        sesi.save()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('approval_jenis_id', self.client.session)

    def test_tab_karangan_jatuh_ke_menunggu(self):
        resp = self.client.get(self.url, {'tab': 'apa-saja'})
        self.assertEqual(resp.context['tab'], 'pending')
