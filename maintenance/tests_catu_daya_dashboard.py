"""Kartu "nilai terbaru" di tab Catu Daya / Rectifier Dashboard Catu Daya.

Dua kartu berbentuk sama — Hasil Pemeliharaan (HAR, biru) dan Hasil Inspeksi
(Inservice, ungu) — supaya angka dari dua sumber berbeda tidak tertukar saat
dibaca. Yang dijaga: kartu HAR punya data kondisi seperti kartu inspeksi, dan
tanggal di kedua kartu adalah tanggal WITA, bukan tanggal UTC.
"""
from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile
from inspection.models import Inspection, InspectionCatuDaya

from .models import Maintenance, MaintenanceRectifier


def _wita(*args):
    return timezone.make_aware(datetime(*args))   # TIME_ZONE = Asia/Makassar


class KartuNilaiTerbaruTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_kartu', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        self.dev = Device.objects.create(nama='CD-TELLO', jenis=DeviceType.objects.create(name='CATU DAYA'),
                                         merk='Benning', lokasi='GI TELLO')
        # 07.00 WITA = 23.00 UTC hari sebelumnya
        m = Maintenance.objects.create(device=self.dev, maintenance_type='Preventive',
                                       date=_wita(2026, 9, 8, 7, 0), status='Done')
        MaintenanceRectifier.objects.create(
            maintenance=m, rect1_v_battery=53.2, rect1_kondisi='OK', bat1_kondisi='NOK',
            bat1_kondisi_kabel='OK', exhaust_fan='Rusak', kebersihan='Bersih',
            lampu_penerangan='Redup', suhu_ruangan=27.5)
        insp = Inspection.objects.create(device=self.dev, jenis='catu_daya',
                                         tanggal=_wita(2026, 10, 2, 6, 30))
        InspectionCatuDaya.objects.create(inspection=insp, kondisi_rectifier='normal')

    def _dev(self):
        resp = self.client.get(reverse('catu_daya_dashboard'))
        self.assertEqual(resp.status_code, 200)
        return resp, resp.context['devices_data'][0]

    def test_kartu_har_membawa_data_kondisi(self):
        _, d = self._dev()
        self.assertEqual(d['har_rect_kondisi'], 'OK')
        self.assertEqual(d['har_bat_kondisi'], 'NOK')
        self.assertEqual(d['har_kabel'], 'OK')
        self.assertEqual(d['har_mur_baut'], '')        # tidak diisi → string kosong
        self.assertEqual(d['har_exhaust_fan'], 'Rusak')
        self.assertEqual(d['har_kebersihan'], 'Bersih')
        self.assertEqual(d['har_lampu'], 'Redup')
        self.assertEqual(d['har_suhu'], 27.5)

    def test_tanggal_kedua_kartu_memakai_tanggal_wita(self):
        _, d = self._dev()
        self.assertEqual(d['tanggal_har'], '2026-09-08')
        self.assertEqual(d['insp_tanggal'], '2026-10-02')

    def test_dua_kartu_berlabel_sumbernya(self):
        resp, _ = self._dev()
        html = resp.content.decode()
        self.assertIn('Hasil Pemeliharaan (HAR)', html)
        self.assertIn('Hasil Inspeksi (Inservice)', html)
        self.assertIn('class="cd-card cd-src cd-src-har" id="metric-grid"', html)
        self.assertIn('class="cd-card cd-src cd-src-insp" id="insp-card"', html)
        for id_ in ('har-badges', 'har-tanggal-label', 'insp-badges', 'insp-tanggal-label'):
            self.assertIn(f'id="{id_}"', html)
