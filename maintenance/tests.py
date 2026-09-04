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

from .models import (Maintenance, MaintenanceDFR, MaintenanceFrequencyRelay,
                     MaintenanceMasterStation, MaintenanceMasterTrip)


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



class PdfReleDefenseSchemeTests(TestCase):
    """Ekspor & preview PDF untuk Rele Defense Scheme / Master Trip.

    Jenis perangkat ini punya form sendiri (`MaintenanceMasterTripForm`) tapi
    pernah tidak punya template PDF-nya, sehingga `_TEMPLATE_MAP` jatuh ke
    `generic.html`: PDF-nya keluar berisi kop + informasi pemeliharaan saja,
    seluruh hasil pemeliharaan hilang tanpa satu pun pesan error.
    """

    JENIS = ('MASTER TRIP', 'RELE DEFENSE SCHEME')

    def setUp(self):
        self.user = User.objects.create_superuser(username='admin3', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

    def _maintenance(self, nama_jenis, dengan_detail=True):
        jenis, _ = DeviceType.objects.get_or_create(name=nama_jenis)
        device = Device.objects.create(nama=f'{nama_jenis}-01', jenis=jenis,
                                       merk='SEL', lokasi='GI TELLO')
        m = Maintenance.objects.create(device=device, maintenance_type='Preventive',
                                       date=timezone.now(), description='uji')
        if dengan_detail:
            MaintenanceMasterTrip.objects.create(
                maintenance=m, healthy='normal', trip_led='abnormal', alarm='normal',
                merek='SEL', no_seri='SN-99', target='TRAFO #1', fungsi='OLS',
                rasio_ct='400/5', i_a='120.5', v_a='150.2', frekuensi='50.01',
                setting_i='1.2', waktu_i='0.5',
                p1_rl='RL1', p1_vdc='101', p1_pin='A1',
                n1_rl='RL1', n1_vdc='102', n1_pin='B1',
                aux1_rl='RL1', aux1_tf='TF1', aux1_led='LED1',
                dev1_nama='MT-BUSBAR', dev1_gi='GI TELLO', dev1_ready='READY', dev1_comm='OK',
                supply_dc='110 VDC', selektor='ON', catatan='Terminal RL3 longgar.')
        return m

    def _data_ekspor(self, maintenance):
        """Jalankan view ekspor dengan generator PDF diganti perekam data."""
        from unittest.mock import patch

        rekam = {}

        def _rekam(data, output):
            rekam.update(data)
            output.write(b'%PDF-1.4 dummy')

        with patch('maintenance.pdf_weasy.build_pdf_weasy', _rekam):
            resp = self.client.get(reverse('export_maintenance_pdf', args=[maintenance.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        return rekam, resp

    def test_template_pdf_bukan_generic(self):
        from maintenance.pdf_weasy import _CTX_BUILDERS, _TEMPLATE_MAP

        for kind in self.JENIS:
            with self.subTest(jenis=kind):
                self.assertEqual(_TEMPLATE_MAP.get(kind), 'maintenance/pdf/master_trip.html')
                self.assertIn(kind, _CTX_BUILDERS)

    def test_data_master_trip_ikut_dikirim_ke_pdf(self):
        for kind in self.JENIS:
            with self.subTest(jenis=kind):
                m = self._maintenance(kind)
                data, _resp = self._data_ekspor(m)
                mt = data.get('master_trip') or {}
                self.assertEqual(data['device_kind'], kind)
                self.assertEqual(mt.get('no_seri'), 'SN-99')
                self.assertEqual(mt.get('i_a'), '120.5')
                self.assertEqual(mt.get('p1_vdc'), '101')
                self.assertEqual(mt.get('n1_vdc'), '102')
                self.assertEqual(mt.get('aux1_led'), 'LED1')
                self.assertEqual(mt.get('dev1_nama'), 'MT-BUSBAR')
                self.assertEqual(mt.get('catatan'), 'Terminal RL3 longgar.')
                # nilai pilihan dikirim sebagai label, bukan nilai mentah —
                # template mencocokkannya dengan 'Normal' / 'Abnormal'
                self.assertEqual(mt.get('healthy'), 'Normal')
                self.assertEqual(mt.get('trip_led'), 'Abnormal')
                self.assertEqual(mt.get('dev1_ready'), 'READY')

    def test_ekspor_tetap_jalan_tanpa_detail(self):
        m = self._maintenance('RELE DEFENSE SCHEME', dengan_detail=False)
        data, _resp = self._data_ekspor(m)
        self.assertEqual(data.get('master_trip'), {})

    def test_html_pdf_memuat_nilai_hasil_pemeliharaan(self):
        """Nilai yang tersimpan harus benar-benar tercetak di halaman PDF."""
        from django.template.loader import render_to_string

        from maintenance.pdf_weasy import (_CTX_BUILDERS, _TEMPLATE_MAP,
                                           _base_context)

        m = self._maintenance('RELE DEFENSE SCHEME')
        data, _resp = self._data_ekspor(m)
        ctx = _base_context(data)
        _CTX_BUILDERS['RELE DEFENSE SCHEME'](data, ctx)
        html = render_to_string(_TEMPLATE_MAP['RELE DEFENSE SCHEME'], ctx)

        for nilai in ('SN-99', 'TRAFO #1', '400/5', '120.5', '150.2', '50.01',
                      'LED1', 'MT-BUSBAR', 'GI TELLO', '110 VDC',
                      'Terminal RL3 longgar.'):
            self.assertIn(nilai, html)

    def test_formulir_kosong_tetap_bisa_dicetak(self):
        from unittest.mock import patch

        m = self._maintenance('RELE DEFENSE SCHEME', dengan_detail=False)
        with patch('maintenance.pdf_weasy.build_pdf_weasy',
                   lambda data, output: output.write(b'%PDF-1.4 dummy')):
            resp = self.client.get(reverse('blank_maintenance_pdf', args=[m.device.pk]))
        self.assertEqual(resp.status_code, 200)


class PdfDfrTests(TestCase):
    """Ekspor & preview PDF untuk DFR / PMU.

    Persoalannya sama persis dengan Rele Defense Scheme: jenis ini punya
    `MaintenanceDFRForm` sendiri tapi tidak punya template PDF, jadi hasil
    pemeliharaannya tidak pernah ikut tercetak.
    """

    JENIS = ('DFR', 'PMU')

    def setUp(self):
        self.user = User.objects.create_superuser(username='admin4', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

    def _maintenance(self, nama_jenis, dengan_detail=True):
        jenis, _ = DeviceType.objects.get_or_create(name=nama_jenis)
        device = Device.objects.create(nama=f'{nama_jenis}-01', jenis=jenis,
                                       merk='Qualitrol', lokasi='GI TELLO')
        m = Maintenance.objects.create(device=device, maintenance_type='Preventive',
                                       date=timezone.now(), description='uji')
        if dengan_detail:
            MaintenanceDFR.objects.create(
                maintenance=m,
                bay_feeder_1='PENYULANG TELLO 1', bay_feeder_2='PENYULANG TELLO 2',
                rasio_ct_1='400/5', rasio_pt_1='150000/100',
                suhu_ruangan='24.5', kelembaban='55',
                kartu_kontrol='Terisi', outdoor_panel='Bersih', indoor_panel='Kotor',
                tergrounding='Ya', type_dfr='SIM-Q', merk_dfr='Qualitrol', sn_dfr='QT-2024-771',
                kondisi_gps='Terhubung', kondisi_lcd='Normal', waktu_dfr='Sesuai',
                dfr_aktif='Ya', fisik_alarm='Ada Alarm', fungsi_rekaman='Normal',
                visual_5r='Sangat Baik', front_port_ip='10.10.20.5', rear_port_ip='10.10.20.6',
                conv_rx='Abnormal', ping_server_1='4', ping_dfr_1='2',
                software_config='Terdownload', v_input_power='110.4', v_backup='48.2',
                kapasitas_memory='512 GB', pmu_id='PMU-TELLO-01',
                catatan_khusus='Converter Rx abnormal.',
                bay1_dfr_v_r='150.0', bay1_dfr_i_r='121.0', bay1_dfr_hz='50.01',
                bay1_ied_v_r='149.0', bay2_dfr_v_r='150.5')
        return m

    def _data_ekspor(self, maintenance):
        from unittest.mock import patch

        rekam = {}

        def _rekam(data, output):
            rekam.update(data)
            output.write(b'%PDF-1.4 dummy')

        with patch('maintenance.pdf_weasy.build_pdf_weasy', _rekam):
            resp = self.client.get(reverse('export_maintenance_pdf', args=[maintenance.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        return rekam, resp

    def test_template_pdf_bukan_generic(self):
        from maintenance.pdf_weasy import _CTX_BUILDERS, _TEMPLATE_MAP

        for kind in self.JENIS:
            with self.subTest(jenis=kind):
                self.assertEqual(_TEMPLATE_MAP.get(kind), 'maintenance/pdf/dfr.html')
                self.assertIn(kind, _CTX_BUILDERS)

    def test_data_dfr_ikut_dikirim_ke_pdf(self):
        for kind in self.JENIS:
            with self.subTest(jenis=kind):
                m = self._maintenance(kind)
                data, _resp = self._data_ekspor(m)
                d = data.get('dfr') or {}
                self.assertEqual(data['device_kind'], kind)
                self.assertEqual(d.get('bay_feeder_1'), 'PENYULANG TELLO 1')
                self.assertEqual(d.get('sn_dfr'), 'QT-2024-771')
                self.assertEqual(d.get('pmu_id'), 'PMU-TELLO-01')
                self.assertEqual(d.get('bay1_dfr_v_r'), '150.0')
                self.assertEqual(d.get('bay1_dfr_hz'), '50.01')
                self.assertEqual(d.get('bay2_dfr_v_r'), '150.5')
                self.assertEqual(d.get('catatan_khusus'), 'Converter Rx abnormal.')
                self.assertEqual(d.get('fisik_alarm'), 'Ada Alarm')
                self.assertEqual(d.get('conv_rx'), 'Abnormal')

    def test_ekspor_tetap_jalan_tanpa_detail(self):
        m = self._maintenance('DFR', dengan_detail=False)
        data, _resp = self._data_ekspor(m)
        self.assertEqual(data.get('dfr'), {})

    def test_html_pdf_memuat_nilai_hasil_pemeliharaan(self):
        from django.template.loader import render_to_string

        from maintenance.pdf_weasy import (_CTX_BUILDERS, _TEMPLATE_MAP,
                                           _base_context)

        m = self._maintenance('DFR')
        data, _resp = self._data_ekspor(m)
        ctx = _base_context(data)
        _CTX_BUILDERS['DFR'](data, ctx)
        html = render_to_string(_TEMPLATE_MAP['DFR'], ctx)

        for nilai in ('PENYULANG TELLO 1', 'QT-2024-771', '10.10.20.5', 'PMU-TELLO-01',
                      '512 GB', '150.0', '50.01', 'Ada Alarm', 'Converter Rx abnormal.'):
            self.assertIn(nilai, html)

    def test_formulir_kosong_tetap_bisa_dicetak(self):
        from unittest.mock import patch

        m = self._maintenance('DFR', dengan_detail=False)
        with patch('maintenance.pdf_weasy.build_pdf_weasy',
                   lambda data, output: output.write(b'%PDF-1.4 dummy')):
            resp = self.client.get(reverse('blank_maintenance_pdf', args=[m.device.pk]))
        self.assertEqual(resp.status_code, 200)


class PdfTemplateCoverageTests(TestCase):
    """Setiap jenis perangkat yang punya form isian sendiri harus punya
    template PDF sendiri juga.

    Kalau tidak, `_TEMPLATE_MAP` diam-diam jatuh ke `generic.html` dan PDF-nya
    keluar berisi kop + Informasi Pemeliharaan saja — persis yang terjadi pada
    Rele Defense Scheme dan DFR. Tidak ada error, tidak ada log; satu-satunya
    yang menyadari adalah orang yang membuka hasil cetaknya.
    """

    def test_semua_jenis_berform_punya_template_pdf(self):
        from maintenance.pdf_weasy import _TEMPLATE_MAP
        from maintenance.views import DEVICE_FORM_MAP

        # kunci dicari dengan nama jenis yang sudah di-uppercase
        # (lihat _get_detail_form_config / export_maintenance_pdf)
        tanpa_template = sorted(
            jenis for jenis, (form, _tpl) in DEVICE_FORM_MAP.items()
            if form is not None and jenis.upper() not in _TEMPLATE_MAP
        )
        self.assertEqual(tanpa_template, [],
                         'jenis ini akan tercetak memakai generic.html: '
                         f'{tanpa_template}')

    def test_setiap_template_khusus_punya_pembangun_konteks(self):
        """Template khusus tanpa builder = tabelnya dirender kosong."""
        from maintenance.pdf_weasy import _CTX_BUILDERS, _TEMPLATE_MAP

        tanpa_builder = sorted(
            jenis for jenis, tpl in _TEMPLATE_MAP.items()
            if tpl != 'maintenance/pdf/generic.html' and jenis not in _CTX_BUILDERS
        )
        self.assertEqual(tanpa_builder, [])
