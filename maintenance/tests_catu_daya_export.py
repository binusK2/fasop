"""Ekspor Excel tab Catu Daya / Rectifier di Dashboard Catu Daya.

Yang dijaga: cakupan "semua" memuat perangkat yang belum di-HAR dengan kolom
HAR kosong, cakupan "har" sama persis dengan daftar di dashboard, status &
estimasi di berkas sama dengan layar (keduanya lewat maintenance/catu_daya.py),
dan HAR yang sudah di-soft-delete tidak ikut — baik di berkas maupun di layar.
"""
from io import BytesIO

import openpyxl
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile

from .models import Maintenance, MaintenanceRectifier

BARIS_DATA = 6   # baris 4 = grup kolom, baris 5 = judul kolom


def _sel(**nilai):
    """Tabel sel bat1_cells berisi baris ringkasan vtotal saja."""
    return [{'cell': 'vtotal', **nilai}]


class CatuDayaExportTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_catu', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        catu = DeviceType.objects.create(name='CATU DAYA 48V')
        rect = DeviceType.objects.create(name='RECTIFIER')
        rtu = DeviceType.objects.create(name='RTU')

        self.aman = Device.objects.create(nama='CD-TELLO', jenis=catu, merk='Benning',
                                          lokasi='GI TELLO')
        self.bahaya = Device.objects.create(nama='RECT-BTL', jenis=rect, merk='Eltek',
                                            lokasi='GI BONTOALA')
        self.belum = Device.objects.create(nama='CD-PARE', jenis=catu, merk='Benning',
                                           lokasi='GI PAREPARE')
        Device.objects.create(nama='RTU-TELLO', jenis=rtu, merk='SEL', lokasi='GI TELLO')
        Device.objects.create(nama='CD-HAPUS', jenis=catu, merk='X', lokasi='GI A',
                              is_deleted=True)

        # CD-TELLO: dua HAR, yang terbaru turun pelan (Aman)
        self._har(self.aman, 2026, 3, rect1_v_battery=110.0,
                  cells=_sel(v_float=54.0, vd_0=52.0, vd_2=50.0))
        self.har_terbaru = self._har(
            self.aman, 2026, 9, rect1_v_battery=111.5, rect1_kondisi='OK',
            cells=_sel(v_float=54.6, vd_0=53.0, vd_half=52.8, vd_1=52.5, vd_2=52.0))
        # RECT-BTL: tegangan sudah di bawah 38 V sejak awal discharge (Bahaya)
        self._har(self.bahaya, 2026, 8, rect1_kondisi='NOK',
                  cells=_sel(v_float=50.0, vd_0=37.0, vd_2=35.0))

        self.url = reverse('catu_daya_export_excel')

    def _har(self, device, tahun, bulan, cells, hapus=False, **kolom):
        m = Maintenance.semua_objects.create(
            device=device, maintenance_type='Preventive',
            date=timezone.make_aware(timezone.datetime(tahun, bulan, 10, 9, 0)),
            status='Done', pelaksana_names=['Budi', 'Andi'], is_deleted=hapus)
        return MaintenanceRectifier.objects.create(maintenance=m, bat1_cells=cells, **kolom)

    def _unduh(self, cakupan):
        resp = self.client.get(self.url, {'cakupan': cakupan})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        return openpyxl.load_workbook(BytesIO(resp.content))

    def _tabel(self, ws):
        """[{judul kolom: nilai}] per baris data; judul ganda diberi awalan grup."""
        judul = []
        for ci in range(1, ws.max_column + 1):
            grup = None
            for rng in ws.merged_cells.ranges:
                if rng.min_row == 4 and rng.min_col <= ci <= rng.max_col:
                    grup = ws.cell(row=4, column=rng.min_col).value
            grup = grup or ws.cell(row=4, column=ci).value
            judul.append(f'{grup}/{ws.cell(row=5, column=ci).value}')
        baris = []
        for r in range(BARIS_DATA, ws.max_row + 1):
            baris.append({j: ws.cell(row=r, column=ci).value
                          for ci, j in enumerate(judul, 1)})
        return baris

    def _per_nama(self, ws):
        return {b['Perangkat/Nama Perangkat']: b for b in self._tabel(ws)}

    # ── Cakupan ──────────────────────────────────────────────────────
    def test_semua_memuat_perangkat_belum_har_dengan_kolom_kosong(self):
        wb = self._unduh('semua')
        data = self._per_nama(wb['Catu Daya'])

        self.assertEqual(set(data), {'CD-TELLO', 'RECT-BTL', 'CD-PARE'})
        belum = data['CD-PARE']
        self.assertEqual(belum['Perangkat/Lokasi'], 'GI PAREPARE')
        self.assertEqual(belum['HAR/Jumlah HAR'], 0)
        self.assertIsNone(belum['HAR/Tgl HAR'])
        self.assertIsNone(belum['Rectifier/V Battery (V)'])
        self.assertIsNone(belum['Discharge & Prediksi/Status'])

    def test_bawaan_tanpa_parameter_adalah_semua(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        wb = openpyxl.load_workbook(BytesIO(resp.content))
        self.assertIn('CD-PARE', self._per_nama(wb['Catu Daya']))

    def test_har_hanya_perangkat_yang_sudah_har(self):
        wb = self._unduh('har')
        self.assertEqual(set(self._per_nama(wb['Catu Daya'])), {'CD-TELLO', 'RECT-BTL'})

    def test_har_sama_dengan_daftar_dashboard(self):
        resp = self.client.get(reverse('catu_daya_dashboard'))
        di_layar = {d['device_name'] for d in resp.context['devices_data']}
        wb = self._unduh('har')
        self.assertEqual(set(self._per_nama(wb['Catu Daya'])), di_layar)

    def test_cakupan_tak_dikenal_ditolak(self):
        resp = self.client.get(self.url, {'cakupan': 'semuanya'})
        self.assertEqual(resp.status_code, 400)

    def test_perlu_login(self):
        self.client.logout()
        resp = self.client.get(self.url, {'cakupan': 'semua'})
        self.assertEqual(resp.status_code, 302)

    # ── Isi ──────────────────────────────────────────────────────────
    def test_baris_utama_memakai_har_terakhir(self):
        data = self._per_nama(self._unduh('semua')['Catu Daya'])
        tello = data['CD-TELLO']
        self.assertEqual(tello['HAR/Jumlah HAR'], 2)
        self.assertEqual(tello['Rectifier/V Battery (V)'], 111.5)
        self.assertEqual(tello['Discharge & Prediksi/VD 2 Jam (V)'], 52.0)
        self.assertEqual(tello['Discharge & Prediksi/V Float (V)'], 54.6)
        self.assertEqual(tello['HAR/Pelaksana'], 'Budi, Andi')
        self.assertEqual(tello['HAR/Tgl HAR'].date().isoformat(), '2026-09-10')

    def test_status_dan_estimasi_sama_dengan_dashboard(self):
        resp = self.client.get(reverse('catu_daya_dashboard'))
        layar = {d['device_name']: d for d in resp.context['devices_data']}
        data = self._per_nama(self._unduh('har')['Catu Daya'])
        label = {'ok': 'Aman', 'warning': 'Perhatian', 'danger': 'Bahaya'}

        for nama, d in layar.items():
            baris = data[nama]
            self.assertEqual(baris['Discharge & Prediksi/Status'], label[d['status']], nama)
            self.assertEqual(baris['Discharge & Prediksi/Laju Penurunan (V/jam)'], d['slope'], nama)
            if d['threshold_time'] is not None:
                self.assertEqual(baris['Discharge & Prediksi/Est. Capai 38 V (jam)'],
                                 d['threshold_time'], nama)

        self.assertEqual(data['RECT-BTL']['Discharge & Prediksi/Status'], 'Bahaya')
        self.assertEqual(data['RECT-BTL']['Discharge & Prediksi/Est. Capai 38 V (jam)'],
                         'Sudah ≤ 38 V')

    def test_har_tanpa_data_discharge_tidak_ditulis_bahaya(self):
        # Tanpa titik VD dan tanpa V Total Bank, rumus dashboard menghitung
        # tegangannya 0 V → "Bahaya". Berkas laporan tidak boleh ikut begitu.
        kosong = Device.objects.create(nama='CD-KOSONG', jenis=self.aman.jenis,
                                       merk='X', lokasi='GI MAROS')
        self._har(kosong, 2026, 7, rect1_v_battery=54.0,
                  cells=[{'cell': 1, 'v_float': None}, {'cell': 'vtotal', 'vd_0': None}])

        baris = self._per_nama(self._unduh('har')['Catu Daya'])['CD-KOSONG']
        self.assertEqual(baris['Discharge & Prediksi/Status'], 'Tanpa data discharge')
        self.assertEqual(baris['Discharge & Prediksi/Est. Capai 38 V (jam)'],
                         'Tanpa data discharge')
        self.assertEqual(baris['Rectifier/V Battery (V)'], 54.0)   # isi HAR lain tetap ada

    def test_v_total_bank_saja_tetap_dinilai(self):
        cukup = Device.objects.create(nama='CD-VTOTAL', jenis=self.aman.jenis,
                                      merk='X', lokasi='GI MAROS')
        self._har(cukup, 2026, 7, bat1_v_total=36.5, cells=[])

        baris = self._per_nama(self._unduh('har')['Catu Daya'])['CD-VTOTAL']
        self.assertEqual(baris['Discharge & Prediksi/Status'], 'Bahaya')

    def test_riwayat_satu_baris_per_har(self):
        riwayat = self._tabel(self._unduh('semua')['Riwayat HAR'])
        nama_tgl = [(b['Perangkat/Nama Perangkat'], b['HAR/Tgl HAR'].date().isoformat())
                    for b in riwayat]
        # urut lokasi perangkat (GI BONTOALA < GI TELLO), lalu tanggal
        self.assertEqual(nama_tgl, [('RECT-BTL', '2026-08-10'),
                                    ('CD-TELLO', '2026-03-10'),
                                    ('CD-TELLO', '2026-09-10')])
        self.assertNotIn('HAR/Jumlah HAR', riwayat[0])

    def test_har_soft_delete_tidak_ikut_di_berkas_maupun_layar(self):
        # HAR terbaru (Desember) dihapus Teknisi → yang dipakai tetap September
        self._har(self.aman, 2026, 12, rect1_v_battery=99.0, hapus=True,
                  cells=_sel(vd_0=30.0, vd_2=20.0))
        # Satu-satunya HAR CD-PARE dihapus → tetap tercatat belum HAR
        self._har(self.belum, 2026, 5, rect1_v_battery=80.0, hapus=True, cells=[])

        data = self._per_nama(self._unduh('semua')['Catu Daya'])
        self.assertEqual(data['CD-TELLO']['HAR/Jumlah HAR'], 2)
        self.assertEqual(data['CD-TELLO']['Rectifier/V Battery (V)'], 111.5)
        self.assertEqual(data['CD-PARE']['HAR/Jumlah HAR'], 0)

        resp = self.client.get(reverse('catu_daya_dashboard'))
        layar = {d['device_name']: d for d in resp.context['devices_data']}
        self.assertNotIn('CD-PARE', layar)
        self.assertEqual(layar['CD-TELLO']['v_battery'], 111.5)

    def test_sheet_keterangan_ada(self):
        wb = self._unduh('semua')
        self.assertEqual(wb.sheetnames, ['Catu Daya', 'Riwayat HAR', 'Keterangan'])

    def test_kosong_tetap_menghasilkan_berkas(self):
        MaintenanceRectifier.objects.all().delete()
        wb = self._unduh('har')
        self.assertEqual(wb['Catu Daya'].cell(row=BARIS_DATA, column=1).value, 'Tidak ada data.')

    # ── Tombol ───────────────────────────────────────────────────────
    def test_dashboard_menampilkan_tombol_export(self):
        resp = self.client.get(reverse('catu_daya_dashboard'))
        self.assertContains(resp, f'{self.url}?cakupan=har')
        self.assertContains(resp, f'{self.url}?cakupan=semua')
        self.assertEqual(resp.context['jumlah_perangkat_catu_daya'], 3)

    def test_tombol_tetap_ada_saat_belum_ada_har_sama_sekali(self):
        MaintenanceRectifier.objects.all().delete()
        resp = self.client.get(reverse('catu_daya_dashboard'))
        self.assertContains(resp, 'Belum ada data Catu Daya')
        self.assertContains(resp, f'{self.url}?cakupan=semua')
