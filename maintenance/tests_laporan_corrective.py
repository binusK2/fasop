"""Data corrective di Laporan Pemeliharaan (halaman + Excel)."""
from io import BytesIO

import openpyxl
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile
from gangguan.models import Gangguan

from .models import Maintenance, MaintenanceCorrective


def _waktu(bulan, hari, jam=8):
    return timezone.make_aware(timezone.datetime(2026, bulan, hari, jam, 0))


class LaporanCorrectiveTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_lap', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        self.rtu = DeviceType.objects.create(name='RTU')
        self.device = Device.objects.create(nama='RTU-01', jenis=self.rtu,
                                            merk='SEL', lokasi='GI TELLO')
        self.gangguan = Gangguan.objects.create(
            peralatan=self.device, site='GI TELLO', tanggal_gangguan=_waktu(3, 4))

        for hari in (2, 3):
            Maintenance.objects.create(device=self.device, maintenance_type='Preventive',
                                       date=_waktu(3, hari), status='Done',
                                       description='Pemeliharaan rutin')

        self._corrective(5, 'hardware', 'Ganti modul CPU', jam=2, komponen='Modul CPU')
        self._corrective(6, 'power', 'Reset MCB catu daya', menit=30,
                         status='perlu_tindaklanjut', gangguan=self.gangguan)
        self._corrective(7, '', 'Cek kabel')                    # tanpa durasi
        self._corrective(5, 'software', 'DI LUAR PERIODE', bulan=4, jam=1)

    def _corrective(self, hari, kerusakan, tindakan, jam=None, menit=None,
                    status='selesai', gangguan=None, komponen='', bulan=3):
        m = Maintenance.objects.create(device=self.device, maintenance_type='Corrective',
                                       date=_waktu(bulan, hari), status='Done',
                                       description='masalah')
        MaintenanceCorrective.objects.create(
            maintenance=m, jenis_kerusakan=kerusakan, deskripsi_masalah='masalah',
            tindakan=tindakan, durasi_jam=jam, durasi_menit=menit,
            status_perbaikan=status, gangguan=gangguan,
            komponen_diganti=bool(komponen), nama_komponen=komponen)
        return m

    def _laporan(self, **params):
        return self.client.get(reverse('maintenance_report'),
                               {'month': 3, 'year': 2026, **params})

    def test_ringkasan_memisahkan_preventive_dan_corrective(self):
        resp = self._laporan()
        s = resp.context['summary']
        self.assertEqual((s['total'], s['preventive'], s['corrective']), (5, 2, 3))
        self.assertContains(resp, 'Corrective</div>')

        rtu = resp.context['by_type'][0]
        self.assertEqual((rtu['preventive'], rtu['corrective']), (2, 3))

    def test_rincian_corrective(self):
        c = self._laporan().context['corrective']
        self.assertEqual(c['selesai'], 2)
        self.assertEqual(c['tindak_lanjut'], 1)
        self.assertEqual(c['terkait_gangguan'], 1)
        self.assertEqual(c['komponen_diganti'], 1)
        self.assertEqual(c['total_menit'], 150)
        # Rata-rata dari 2 perbaikan yang berdurasi — bukan dibagi 3
        self.assertEqual(c['rata_menit'], 75)
        self.assertEqual(c['total_durasi'], '2 jam 30 menit')
        self.assertEqual(c['rata_durasi'], '1 jam 15 menit')
        self.assertEqual(
            {(r['label'], r['jumlah'], r['menit']) for r in c['per_kerusakan']},
            {('Hardware / Fisik', 1, 120), ('Power / Catu Daya', 1, 30), ('Belum diisi', 1, 0)})
        self.assertEqual(c['per_kerusakan'][-1]['label'], 'Belum diisi')   # selalu paling bawah

    def test_tabel_detail_memuat_keterangan_corrective(self):
        resp = self._laporan()
        self.assertContains(resp, 'id="ringkasan-corrective"')
        self.assertContains(resp, 'Ganti modul CPU')
        self.assertContains(resp, 'Hardware / Fisik')
        self.assertContains(resp, self.gangguan.nomor_gangguan)
        self.assertContains(resp, 'Perlu tindak lanjut')
        self.assertContains(resp, 'Pemeliharaan rutin')       # keterangan preventive
        self.assertNotContains(resp, 'DI LUAR PERIODE')

    def test_tabel_detail_tanpa_query_per_baris(self):
        """Keterangan corrective (detail + tiket) diambil lewat select_related —
        10 baris corrective tambahan tidak boleh menambah satu query pun."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._laporan()                                   # pemanasan cache per proses
        with CaptureQueriesContext(connection) as awal:
            self._laporan()
        for hari in range(10, 20):
            self._corrective(hari, 'hardware', f'Perbaikan {hari}', gangguan=self.gangguan)
        with CaptureQueriesContext(connection) as sesudah:
            resp = self._laporan()
        self.assertContains(resp, 'Perbaikan 19')
        self.assertEqual(len(sesudah.captured_queries), len(awal.captured_queries))

    def test_periode_tanpa_corrective_tidak_menggambar_bagiannya(self):
        resp = self._laporan(month=2)
        self.assertIsNone(resp.context['corrective'])
        self.assertNotContains(resp, 'id="ringkasan-corrective"')

    def test_ytd_per_bulan_memisahkan_corrective(self):
        resp = self.client.get(reverse('maintenance_report'), {'mode': 'ytd', 'year': 2026})
        per_bulan = {r['month_name']: r for r in resp.context['monthly_summary']}
        self.assertEqual((per_bulan['Maret']['preventive'], per_bulan['Maret']['corrective']), (2, 3))
        self.assertEqual(per_bulan['April']['corrective'], 1)

    def _sheet(self, **params):
        resp = self.client.get(reverse('export_maintenance_excel'), params)
        self.assertEqual(resp.status_code, 200)
        return openpyxl.load_workbook(BytesIO(resp.content))

    def test_excel_bulanan_punya_sheet_corrective(self):
        wb = self._sheet(year=2026, month=3, mode='monthly')
        self.assertIn('Corrective', wb.sheetnames)
        baris = [r for r in wb['Corrective'].iter_rows(min_row=5, values_only=True) if r[0]]
        self.assertEqual(len(baris), 3)
        hardware = next(r for r in baris if r[6] == 'Ganti modul CPU')
        self.assertEqual(hardware[4], 'Hardware / Fisik')
        self.assertEqual(hardware[7], 'Modul CPU')
        self.assertEqual(hardware[8], '2 jam')
        power = next(r for r in baris if r[6] == 'Reset MCB catu daya')
        self.assertEqual(power[9], 'Perlu Tindak Lanjut')
        self.assertEqual(power[10], self.gangguan.nomor_gangguan)

    def test_excel_ytd_punya_sheet_corrective(self):
        wb = self._sheet(year=2026, mode='ytd')
        self.assertIn('Corrective', wb.sheetnames)

    def test_excel_tanpa_corrective_tidak_membuat_sheetnya(self):
        wb = self._sheet(year=2026, month=2, mode='monthly')
        self.assertNotIn('Corrective', wb.sheetnames)
