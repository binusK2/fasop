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

from .models import (Maintenance, MaintenanceFrequencyRelay,
                     MaintenanceMasterStation)


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

class DetailInstanceLookupTests(TestCase):
    """Form edit harus memuat kembali baris detail yang sudah tersimpan.

    Kalau tidak, dua hal terjadi sekaligus: form edit terbuka kosong (data
    terlihat hilang), dan simpan berikutnya membuat baris detail kedua untuk
    pemeliharaan yang sama sehingga menabrak unique constraint OneToOne —
    Internal Server Error. Itu yang terjadi pada UFLS.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(username='admin2', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

    def _maintenance(self, nama_jenis):
        jenis, _ = DeviceType.objects.get_or_create(name=nama_jenis)
        device = Device.objects.create(nama=f'{nama_jenis}-01', jenis=jenis,
                                       merk='SEL', lokasi='GI TELLO')
        return Maintenance.objects.create(device=device, maintenance_type='Preventive',
                                          date=timezone.now(), description='uji')

    def test_semua_form_detail_terjangkau_lewat_relasi(self):
        """Model tiap form detail harus punya relasi OneToOne ke Maintenance.

        Itu satu-satunya syarat supaya _detail_instance() bisa menemukannya —
        jadi jenis perangkat baru tidak bisa lagi diam-diam terlewat seperti
        UFLS dulu.
        """
        from maintenance.forms import MaintenanceRTUGenericForm
        from maintenance.views import DEVICE_FORM_MAP, _detail_instance

        form_classes = {f for f, _t in DEVICE_FORM_MAP.values() if f is not None}
        form_classes.add(MaintenanceRTUGenericForm)   # dipakai RTU non-AK3

        m = self._maintenance('UFLS')
        for form_class in sorted(form_classes, key=lambda f: f.__name__):
            with self.subTest(form=form_class.__name__):
                model = form_class._meta.model
                relasi = [f for f in Maintenance._meta.get_fields()
                          if f.one_to_one and f.auto_created and f.related_model is model]
                self.assertEqual(len(relasi), 1,
                                 f'{model.__name__} tidak punya OneToOne ke Maintenance')
                # belum ada barisnya → None, bukan exception
                self.assertIsNone(_detail_instance(m, form_class))

    def test_form_edit_ufls_memuat_nilai_lama(self):
        m = self._maintenance('UFLS')
        MaintenanceFrequencyRelay.objects.create(
            maintenance=m, fungsi='UFLS', target_proteksi='TRAFO',
            rasio_vt='150/100', v_an='58.1', frekuensi='50.01', healthy='Normal')

        resp = self.client.get(reverse('maintenance_edit', args=[m.pk]))
        self.assertEqual(resp.status_code, 200)
        dform = resp.context['detail_form']
        self.assertIsNotNone(dform.instance.pk)
        self.assertEqual(dform.initial.get('rasio_vt'), '150/100')
        self.assertContains(resp, '150/100')

    def test_simpan_ulang_ufls_memperbarui_bukan_menduplikasi(self):
        m = self._maintenance('UFLS')
        MaintenanceFrequencyRelay.objects.create(
            maintenance=m, fungsi='UFLS', rasio_vt='150/100', v_an='58.1')

        data = {
            'maintenance_type': 'Preventive',
            'date': timezone.localtime(m.date).strftime('%Y-%m-%dT%H:%M'),
            'description': 'Diedit',
            'status': 'Open',
            'pelaksana_names': '["Budi"]',
            'fungsi': 'UFLS', 'target_proteksi': 'TRAFO',
            'rasio_vt': '150/100', 'v_an': '59.9', 'healthy': 'Normal',
        }
        resp = self.client.post(reverse('maintenance_edit', args=[m.pk]), data)
        self.assertEqual(resp.status_code, 302)   # sebelum diperbaiki: IntegrityError

        self.assertEqual(MaintenanceFrequencyRelay.objects.filter(maintenance=m).count(), 1)
        detail = MaintenanceFrequencyRelay.objects.get(maintenance=m)
        self.assertEqual(detail.v_an, '59.9')     # diperbarui, bukan baris baru
        m.refresh_from_db()
        self.assertEqual(m.description, 'Diedit')

