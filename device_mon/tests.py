"""
Tes gating blast WhatsApp (device_mon.notifications).

Fokusnya keputusan "kirim / tidak kirim" — gateway WAHA-nya sendiri
di-mock, karena yang gampang salah di sini adalah ambang severity, aturan
pesan pulih, dan resolusi tujuan. Bentuk HTTP-nya sendiri dijaga terpisah
oleh GatewayWahaTest di bawah.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from devices.models import SiteLocation
from device_mon.models import RTU, ZabbixAlertLog, ZabbixHost, ZabbixInstance
from device_mon.notifications import (alert_rtu, alert_zabbix, zbx_targets,
                                      zbx_targets_default)


def _host(**kwargs):
    data = dict(
        zabbix_hostid='10084', zabbix_host='voip-mks', nama='VoIP Makassar',
        wa_alert=True, wa_min_severity='3',
        state='PROBLEM', severity='High', problem_name='Interface down',
    )
    data.update(kwargs)
    return ZabbixHost.objects.create(**data)


def _instansi(kode, nama, **kolom):
    """
    Instansi Zabbix untuk tes — update_or_create, BUKAN create.

    Migrasi 0009 menambah FK `instance` ke ZabbixHost/ZabbixGroup dengan nilai
    bawaan ZabbixInstance.ambil_default(); saat kolom itu dibuat, Django
    memanggil fungsi tersebut dan baris 'telkom' ikut lahir di database tes.
    create(kode='telkom') lalu bentrok dengan unique constraint `kode` —
    penyebab 14 tes device_mon merah sejak multi-instansi dirilis.
    """
    obj, _ = ZabbixInstance.objects.update_or_create(
        kode=kode, defaults={'nama': nama, **kolom})
    return obj


@override_settings(WA_CHAT_IDS_ZABBIX='123@g.us', WA_CHAT_IDS='rtu@g.us')
class AlertZabbixTest(TestCase):

    def test_host_tanpa_wa_alert_tidak_dikirim_dan_tidak_dicatat(self):
        host = _host(wa_alert=False)
        with patch('device_mon.notifications.kirim_wa') as mock_kirim:
            self.assertFalse(alert_zabbix(host, 'PROBLEM'))
        mock_kirim.assert_not_called()
        self.assertEqual(ZabbixAlertLog.objects.count(), 0)

    def test_severity_di_bawah_ambang_dilewati_tapi_dicatat(self):
        host = _host(wa_min_severity='4', severity='Warning')   # 2 < 4
        with patch('device_mon.notifications.kirim_wa') as mock_kirim:
            self.assertFalse(alert_zabbix(host, 'PROBLEM'))
        mock_kirim.assert_not_called()
        log = ZabbixAlertLog.objects.get()
        self.assertFalse(log.terkirim)
        self.assertIn('di bawah ambang', log.keterangan)

    def test_severity_memenuhi_ambang_dikirim(self):
        host = _host(wa_min_severity='3', severity='High')      # 4 >= 3
        with patch('device_mon.notifications.kirim_wa', return_value=(1, 1, 'OK')) as mock_kirim:
            self.assertTrue(alert_zabbix(host, 'PROBLEM'))
        pesan = mock_kirim.call_args.args[0]
        self.assertIn('VoIP Makassar', pesan)
        self.assertIn('Interface down', pesan)
        self.assertEqual(mock_kirim.call_args.kwargs['chat_ids'], ['123@g.us'])
        self.assertTrue(ZabbixAlertLog.objects.get().terkirim)

    def test_lokasi_diambil_dari_site_location(self):
        lok = SiteLocation.objects.create(nama='GI Tello')
        host = _host(lokasi=lok)
        with patch('device_mon.notifications.kirim_wa', return_value=(1, 1, 'OK')) as mock_kirim:
            alert_zabbix(host, 'PROBLEM')
        self.assertIn('GI Tello', mock_kirim.call_args.args[0])

    def test_lokasi_kosong_tidak_bikin_error(self):
        host = _host(lokasi=None)
        with patch('device_mon.notifications.kirim_wa', return_value=(1, 1, 'OK')) as mock_kirim:
            self.assertTrue(alert_zabbix(host, 'PROBLEM'))
        self.assertIn('Lokasi    : -', mock_kirim.call_args.args[0])

    def test_pulih_dikirim_hanya_kalau_problemnya_tadi_terkirim(self):
        host = _host()
        with patch('device_mon.notifications.kirim_wa', return_value=(1, 1, 'OK')):
            alert_zabbix(host, 'PROBLEM')
        with patch('device_mon.notifications.kirim_wa', return_value=(1, 1, 'OK')) as mock_kirim:
            self.assertTrue(alert_zabbix(host, 'OK', dur_tutup_menit=90))
        self.assertIn('1 jam 30 menit', mock_kirim.call_args.args[0])

    def test_pulih_dilewati_kalau_problemnya_tidak_pernah_masuk(self):
        host = _host(wa_min_severity='5', severity='Warning')
        with patch('device_mon.notifications.kirim_wa') as mock_kirim:
            alert_zabbix(host, 'PROBLEM')          # dilewati, terkirim=False
            self.assertFalse(alert_zabbix(host, 'OK', dur_tutup_menit=10))
        mock_kirim.assert_not_called()

    def test_gagal_kirim_dicatat_dengan_keterangan_gateway(self):
        host = _host()
        with patch('device_mon.notifications.kirim_wa',
                   return_value=(0, 1, '123@g.us: HTTP 500 session not connected')):
            self.assertFalse(alert_zabbix(host, 'PROBLEM'))
        log = ZabbixAlertLog.objects.get()
        self.assertFalse(log.terkirim)
        self.assertIn('session not connected', log.keterangan)

    def test_tujuan_kosong_dicatat_sebagai_salah_konfigurasi(self):
        host = _host()
        with override_settings(WA_CHAT_IDS_ZABBIX='', WA_CHAT_IDS=''):
            with patch('device_mon.notifications.kirim_wa') as mock_kirim:
                self.assertFalse(alert_zabbix(host, 'PROBLEM'))
        mock_kirim.assert_not_called()
        self.assertIn('Tujuan WA kosong', ZabbixAlertLog.objects.get().keterangan)


@override_settings(WA_CHAT_IDS_ZABBIX='zbx@g.us', WA_CHAT_IDS='rtu@g.us')
class TargetResolutionTest(TestCase):

    def test_default_pakai_wa_chat_ids_zabbix(self):
        self.assertEqual(zbx_targets_default(), ['zbx@g.us'])

    def test_default_jatuh_ke_wa_chat_ids_kalau_zabbix_kosong(self):
        with override_settings(WA_CHAT_IDS_ZABBIX=''):
            self.assertEqual(zbx_targets_default(), ['rtu@g.us'])

    def test_kolom_host_menimpa_default(self):
        self.assertEqual(zbx_targets(_host(wa_chat_ids=' a@g.us , b@g.us ')),
                         ['a@g.us', 'b@g.us'])

    def test_kolom_host_kosong_pakai_default(self):
        self.assertEqual(zbx_targets(_host(wa_chat_ids='')), ['zbx@g.us'])


class SeverityIndexTest(TestCase):

    def test_label_angka_dan_nilai_aneh(self):
        from device_mon.zabbix_api import severity_index
        self.assertEqual(severity_index('Disaster'), 5)
        self.assertEqual(severity_index('high'), 4)
        self.assertEqual(severity_index('4'), 4)
        self.assertEqual(severity_index(''), 0)
        self.assertEqual(severity_index(None), 0)
        self.assertEqual(severity_index('Entah apa'), 0)


class AlertRtuWaFlagTest(TestCase):
    """RTU.wa_alert default True — perilaku lama tidak boleh berubah."""

    def test_default_true_tetap_mengirim(self):
        rtu = RTU.objects.create(nama='RTU-01', state='DOWN')
        self.assertTrue(rtu.wa_alert)
        with patch('device_mon.notifications.kirim_wa', return_value=(1, 1, 'OK')) as mock_kirim:
            self.assertTrue(alert_rtu(rtu, 'DOWN'))
        mock_kirim.assert_called_once()

    def test_wa_alert_mati_membisukan_satu_rtu(self):
        rtu = RTU.objects.create(nama='RTU-02', state='DOWN', wa_alert=False)
        with patch('device_mon.notifications.kirim_wa') as mock_kirim:
            self.assertFalse(alert_rtu(rtu, 'DOWN'))
        mock_kirim.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
#  Multi-instansi Zabbix (ZabbixInstance) — "Zabbix Telkom" + "Zabbix Prosis".
# ═══════════════════════════════════════════════════════════════════════════
class ZabbixInstanceModelTest(TestCase):
    """ZabbixInstance.ambil_default() dan fallback *_efektif() ke .env."""

    def test_ambil_default_membuat_telkom_bila_belum_ada(self):
        # Baris 'telkom' bawaan migrasi dibuang dulu: yang diuji justru
        # pemasangan yang belum punya satu instansi pun.
        ZabbixInstance.objects.all().delete()
        self.assertEqual(ZabbixInstance.objects.count(), 0)
        obj = ZabbixInstance.ambil_default()
        self.assertEqual(obj.kode, 'telkom')
        self.assertEqual(obj.nama, 'Zabbix Telkom')
        self.assertEqual(ZabbixInstance.objects.count(), 1)

    def test_ambil_default_idempoten(self):
        pertama = ZabbixInstance.ambil_default()
        kedua = ZabbixInstance.ambil_default()
        self.assertEqual(pertama.pk, kedua.pk)
        self.assertEqual(ZabbixInstance.objects.count(), 1)

    def test_host_tanpa_instance_eksplisit_ikut_default_telkom(self):
        host = _host()
        self.assertEqual(host.instance.kode, 'telkom')

    @override_settings(ZABBIX_API_URL='http://zabbix-env.local/api_jsonrpc.php',
                       ZABBIX_API_TOKEN='token-env', ZABBIX_WEBHOOK_TOKEN='webhook-env')
    def test_field_kosong_jatuh_ke_env(self):
        obj = _instansi('telkom', 'Zabbix Telkom')
        self.assertEqual(obj.api_url_efektif(), 'http://zabbix-env.local/api_jsonrpc.php')
        self.assertEqual(obj.api_token_efektif(), 'token-env')
        self.assertEqual(obj.webhook_token_efektif(), 'webhook-env')

    @override_settings(ZABBIX_API_URL='http://zabbix-env.local/api_jsonrpc.php',
                       ZABBIX_WEBHOOK_TOKEN='webhook-env')
    def test_field_terisi_menimpa_env(self):
        obj = _instansi(
            'prosis', 'Zabbix Prosis',
            api_url='http://zabbix-prosis.local/api_jsonrpc.php',
            webhook_token='webhook-prosis',
        )
        self.assertEqual(obj.api_url_efektif(), 'http://zabbix-prosis.local/api_jsonrpc.php')
        self.assertEqual(obj.webhook_token_efektif(), 'webhook-prosis')

    def test_kode_terpakai_ditolak(self):
        from django.core.exceptions import ValidationError
        obj = ZabbixInstance(kode='webhook', nama='Salah')
        with self.assertRaises(ValidationError):
            obj.clean()

    @override_settings(WA_CHAT_IDS_ZABBIX='zbx@g.us', WA_CHAT_IDS='rtu@g.us')
    def test_wa_chat_ids_efektif_fallback_chain(self):
        kosong = _instansi('telkom', 'Zabbix Telkom')
        self.assertEqual(kosong.wa_chat_ids_efektif(), ['zbx@g.us'])

        sendiri = _instansi('prosis', 'Zabbix Prosis', wa_chat_ids='prosis@g.us')
        self.assertEqual(sendiri.wa_chat_ids_efektif(), ['prosis@g.us'])

    @override_settings(WA_CHAT_IDS_ZABBIX='', WA_CHAT_IDS='rtu@g.us')
    def test_zbx_targets_host_jatuh_ke_instance_dulu_baru_global(self):
        prosis = _instansi('prosis', 'Zabbix Prosis', wa_chat_ids='prosis@g.us')
        host = _host(instance=prosis, wa_chat_ids='')
        self.assertEqual(zbx_targets(host), ['prosis@g.us'])


class ZabbixHostUniquePerInstanceTest(TestCase):
    """hostid unik PER INSTANSI, bukan global — dua server Zabbix berbeda
    boleh kebetulan memakai hostid yang sama untuk host yang berbeda."""

    def test_hostid_sama_di_instansi_berbeda_tidak_bentrok(self):
        telkom = _instansi('telkom', 'Zabbix Telkom')
        prosis = _instansi('prosis', 'Zabbix Prosis')
        ZabbixHost.objects.create(instance=telkom, zabbix_hostid='10084', nama='Host Telkom')
        # Tidak boleh IntegrityError meski hostid-nya sama persis.
        h2 = ZabbixHost.objects.create(instance=prosis, zabbix_hostid='10084', nama='Host Prosis')
        self.assertEqual(h2.zabbix_hostid, '10084')

    def test_hostid_sama_di_instansi_sama_bentrok(self):
        from django.db import IntegrityError, transaction
        telkom = _instansi('telkom', 'Zabbix Telkom')
        ZabbixHost.objects.create(instance=telkom, zabbix_hostid='10084', nama='A')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ZabbixHost.objects.create(instance=telkom, zabbix_hostid='10084', nama='B')


class ZabbixWebhookInstanceTest(TestCase):
    """Endpoint webhook per-instansi — token dan host tidak boleh bocor antar instansi."""

    def setUp(self):
        self.telkom = _instansi('telkom', 'Zabbix Telkom', webhook_token='token-telkom')
        self.prosis = _instansi('prosis', 'Zabbix Prosis', webhook_token='token-prosis')

    def _post(self, url, token, **payload):
        import json
        return self.client.post(
            url, data=json.dumps(payload), content_type='application/json',
            HTTP_X_ZABBIX_WEBHOOK_TOKEN=token,
        )

    def test_token_instansi_sendiri_diterima(self):
        resp = self._post('/device-mon/zabbix/telkom/webhook/', 'token-telkom',
                          event_status='PROBLEM', eventid='1', hostid='500',
                          host='rtr-1', host_visible_name='Router 1', severity='High')
        self.assertEqual(resp.status_code, 200)
        host = ZabbixHost.objects.get(instance=self.telkom, zabbix_hostid='500')
        self.assertEqual(host.state, 'PROBLEM')

    def test_token_instansi_lain_ditolak(self):
        resp = self._post('/device-mon/zabbix/prosis/webhook/', 'token-telkom',
                          event_status='PROBLEM', eventid='1', hostid='500', host='rtr-1')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(ZabbixHost.objects.filter(instance=self.prosis).exists())

    def test_kode_tidak_dikenal_404(self):
        resp = self._post('/device-mon/zabbix/tidak-ada/webhook/', 'apa-saja',
                          event_status='PROBLEM', eventid='1', hostid='500')
        self.assertEqual(resp.status_code, 404)

    def test_path_lama_tanpa_kode_alias_ke_telkom(self):
        resp = self._post('/device-mon/zabbix/webhook/', 'token-telkom',
                          event_status='PROBLEM', eventid='1', hostid='999', host='rtr-2')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ZabbixHost.objects.filter(instance=self.telkom, zabbix_hostid='999').exists())


class ZabbixUrlRedirectTest(TestCase):
    """Path lama (sebelum multi-instansi) tetap hidup lewat redirect 302 ke 'telkom'."""

    def test_dashboard_lama_redirect_ke_telkom(self):
        resp = self.client.get('/device-mon/zabbix/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/device-mon/zabbix/telkom/')

    def test_gangguan_lama_redirect_ke_telkom(self):
        resp = self.client.get('/device-mon/zabbix/gangguan/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/device-mon/zabbix/telkom/gangguan/')

    def test_group_lama_redirect_ke_telkom(self):
        resp = self.client.get('/device-mon/zabbix/group/VoIP%20Mks/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/device-mon/zabbix/telkom/group/VoIP%20Mks/')


class ZabbixDashboardScopingTest(TestCase):
    """Dashboard/API satu instansi tidak boleh menghitung host instansi lain."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.telkom = _instansi('telkom', 'Zabbix Telkom')
        self.prosis = _instansi('prosis', 'Zabbix Prosis')
        ZabbixHost.objects.create(instance=self.telkom, zabbix_hostid='1', nama='Telkom A')
        ZabbixHost.objects.create(instance=self.telkom, zabbix_hostid='2', nama='Telkom B')
        ZabbixHost.objects.create(instance=self.prosis, zabbix_hostid='1', nama='Prosis A')
        user = User.objects.create_superuser('adm-zbx-scope', 'a@b.id', 'rahasia-tes-123')
        # create_profile signal (devices/admin.py) membuat UserProfile dengan
        # force_password_change=True bawaan — matikan supaya ForcePasswordChangeMiddleware
        # tidak mengalihkan request tes ke /ganti-password/.
        user.profile.force_password_change = False
        user.profile.save(update_fields=['force_password_change'])
        self.client.force_login(user)

    def test_summary_telkom_hanya_hitung_host_telkom(self):
        resp = self.client.get('/device-mon/zabbix/telkom/api/summary/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total_host'], 2)

    def test_summary_prosis_hanya_hitung_host_prosis(self):
        resp = self.client.get('/device-mon/zabbix/prosis/api/summary/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total_host'], 1)

    def test_kode_tidak_dikenal_404(self):
        resp = self.client.get('/device-mon/zabbix/entah-apa/')
        self.assertEqual(resp.status_code, 404)


class SyncZabbixMultiInstanceTest(TestCase):
    """Satu instansi gagal tidak boleh menghentikan sinkronisasi instansi lain."""

    def setUp(self):
        self.telkom = _instansi('telkom', 'Zabbix Telkom', api_url='http://telkom.local/api_jsonrpc.php')
        self.prosis = _instansi('prosis', 'Zabbix Prosis', api_url='http://prosis.local/api_jsonrpc.php')

    def test_instansi_gagal_tidak_menghentikan_instansi_lain(self):
        from device_mon.zabbix_api import ZabbixAPIError
        from io import StringIO
        from django.core.management import call_command

        def fake_status(group_names=None, client=None):
            if client.url == 'http://telkom.local/api_jsonrpc.php':
                raise ZabbixAPIError('koneksi telkom gagal')
            return {
                '900': {'host': 'prosis-1', 'name': 'Prosis 1', 'groups': '',
                        'state': 'OK', 'severity': '', 'problem_name': '', 'eventid': '', 'clock': None},
            }

        with patch('device_mon.management.commands.sync_zabbix.get_current_status',
                  side_effect=fake_status):
            out, err = StringIO(), StringIO()
            call_command('sync_zabbix', stdout=out, stderr=err)

        self.assertIn('telkom', err.getvalue().lower())
        self.assertTrue(ZabbixHost.objects.filter(instance=self.prosis, zabbix_hostid='900').exists())
        self.assertFalse(ZabbixHost.objects.filter(instance=self.telkom).exists())

    def test_filter_instansi_tunggal(self):
        from io import StringIO
        from django.core.management import call_command

        def fake_status(group_names=None, client=None):
            return {
                '1': {'host': 'h1', 'name': 'H1', 'groups': '', 'state': 'OK',
                      'severity': '', 'problem_name': '', 'eventid': '', 'clock': None},
            }

        with patch('device_mon.management.commands.sync_zabbix.get_current_status',
                  side_effect=fake_status) as mock_status:
            call_command('sync_zabbix', instansi='prosis', stdout=StringIO())

        mock_status.assert_called_once()
        self.assertTrue(ZabbixHost.objects.filter(instance=self.prosis).exists())
        self.assertFalse(ZabbixHost.objects.filter(instance=self.telkom).exists())


# ===========================================================================
#  Bentuk HTTP ke gateway WAHA.
#
#  Sengaja TIDAK memakai mock kirim_wa seperti tes di atas: yang dijaga di
#  sini justru lapisan yang tes-tes itu lewati. Saat gateway ditukar dari
#  OpenWA ke WAHA, tidak ada satu tes pun yang gagal walaupun path, header,
#  dan body-nya berubah semua — persis bagian yang kalau salah membuat blast
#  diam tanpa gejala sampai ada gangguan sungguhan.
# ===========================================================================
@override_settings(WA_ALERT_ENABLED=True,
                   WA_API_BASE='http://wa.example:3000',
                   WA_API_KEY='rahasia',
                   WA_SESSION_ID='',
                   WA_TIMEOUT=7)
class GatewayWahaTest(TestCase):

    def test_url_endpoint_tunggal_tanpa_sesi_di_path(self):
        """WAHA: satu endpoint /api/sendText, sesi pindah ke body."""
        from device_mon.notifications import _build_url

        self.assertEqual(_build_url(), 'http://wa.example:3000/api/sendText')

    def test_url_toleran_trailing_slash(self):
        from device_mon.notifications import _build_url

        with override_settings(WA_API_BASE='http://wa.example:3000/'):
            self.assertEqual(_build_url(), 'http://wa.example:3000/api/sendText')

    def test_header_api_key(self):
        from device_mon.notifications import _build_headers

        self.assertEqual(_build_headers()['X-Api-Key'], 'rahasia')

    def test_header_tanpa_api_key_saat_kosong(self):
        """Gateway yang tidak dikunci: jangan kirim header kosong."""
        from device_mon.notifications import _build_headers

        with override_settings(WA_API_KEY=''):
            self.assertNotIn('X-Api-Key', _build_headers())

    def test_payload_memuat_sesi(self):
        from device_mon.notifications import _build_payload

        self.assertEqual(
            _build_payload('123@g.us', 'halo'),
            {'session': 'default', 'chatId': '123@g.us', 'text': 'halo'},
        )

    def test_sesi_kosong_jadi_default(self):
        """WA_SESSION_ID kosong = sesi bawaan WAHA, bukan konfigurasi cacat."""
        from device_mon.notifications import sesi_wa

        self.assertEqual(sesi_wa(), 'default')

    def test_sesi_dari_env_dipakai(self):
        from device_mon.notifications import sesi_wa, _build_payload

        with override_settings(WA_SESSION_ID='fasop'):
            self.assertEqual(sesi_wa(), 'fasop')
            self.assertEqual(_build_payload('1@g.us', 'x')['session'], 'fasop')

    def test_kirim_wa_tidak_butuh_wa_session_id(self):
        """Regresi migrasi OpenWA -> WAHA.

        Guard lama menolak kirim saat WA_SESSION_ID kosong (di OpenWA id sesi
        memang wajib, ia ada di path URL). Di WAHA itu konfigurasi yang sah,
        jadi guard yang sama akan membisukan blast pada pemasangan yang
        sebenarnya sudah benar.
        """
        from device_mon.notifications import kirim_wa

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            terkirim, total, ket = kirim_wa('halo', chat_ids=['123@g.us'])

        self.assertEqual((terkirim, total, ket), (1, 1, 'OK'))
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'http://wa.example:3000/api/sendText')
        self.assertEqual(kwargs['json'],
                         {'session': 'default', 'chatId': '123@g.us', 'text': 'halo'})
        self.assertEqual(kwargs['headers']['X-Api-Key'], 'rahasia')
        self.assertEqual(kwargs['timeout'], 7)

    def test_kirim_wa_butuh_api_base(self):
        from device_mon.notifications import kirim_wa

        with override_settings(WA_API_BASE=''):
            self.assertEqual(kirim_wa('halo', chat_ids=['1@g.us'])[0], 0)

    def test_kirim_wa_http_error_tidak_raise(self):
        """Gateway menjawab error: dicatat, bukan melempar ke collect_rtu."""
        from device_mon.notifications import kirim_wa

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 422
            mock_post.return_value.text = 'session not found'
            terkirim, total, ket = kirim_wa('halo', chat_ids=['1@g.us'])

        self.assertEqual((terkirim, total), (0, 1))
        self.assertIn('422', ket)


# ═══════════════════════════════════════════════════════════════════════════
#  Rekap semua sumber (/device-mon/) — RTU + setiap Instansi Zabbix aktif.
# ═══════════════════════════════════════════════════════════════════════════
class RekapDeviceMonTest(TestCase):
    """
    /device-mon/ adalah rekap; dashboard RTU pindah ke /device-mon/rtu/.
    Angka rekap wajib sama dengan dashboard tiap sumber — dua layar yang
    menyebut jumlah gangguan berbeda untuk data yang sama tidak bisa dipercaya
    salah satunya.
    """

    def setUp(self):
        from datetime import timedelta
        from django.contrib.auth.models import User
        from django.utils import timezone

        kini = timezone.now()
        RTU.objects.create(nama='RTU-UP', state='UP', state_sejak=kini - timedelta(hours=3))
        RTU.objects.create(nama='RTU-DOWN', state='DOWN', lokasi='GI Tello',
                           state_sejak=kini - timedelta(minutes=30))
        RTU.objects.create(nama='RTU-NONAKTIF', state='DOWN', aktif=False)

        self.telkom = _instansi('telkom', 'Zabbix Telkom', urutan=1)
        self.prosis = _instansi('prosis', 'Zabbix Prosis', urutan=2)
        lama = _instansi('lama', 'Zabbix Lama', aktif=False)

        ZabbixHost.objects.create(instance=self.telkom, zabbix_hostid='1', nama='Telkom OK', state='OK')
        ZabbixHost.objects.create(instance=self.telkom, zabbix_hostid='2', nama='Telkom High',
                                  state='PROBLEM', severity='High', problem_name='Link down',
                                  state_sejak=kini - timedelta(minutes=5))
        ZabbixHost.objects.create(instance=self.telkom, zabbix_hostid='3', nama='Telkom Warning',
                                  state='PROBLEM', severity='Warning',
                                  state_sejak=kini - timedelta(minutes=600))
        ZabbixHost.objects.create(instance=self.prosis, zabbix_hostid='1', nama='Prosis Disaster',
                                  state='PROBLEM', severity='Disaster',
                                  state_sejak=kini - timedelta(minutes=60))
        ZabbixHost.objects.create(instance=self.prosis, zabbix_hostid='2', nama='Prosis Nonaktif',
                                  state='PROBLEM', severity='High', aktif=False)
        ZabbixHost.objects.create(instance=lama, zabbix_hostid='1', nama='Host Instansi Mati',
                                  state='PROBLEM', severity='High')

        user = User.objects.create_superuser('adm-rekap', 'r@b.id', 'rahasia-tes-123')
        user.profile.force_password_change = False
        user.profile.save(update_fields=['force_password_change'])
        self.client.force_login(user)

    def _rekap(self):
        resp = self.client.get('/device-mon/api/rekap/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_pintu_masuk_device_mon_adalah_rekap(self):
        resp = self.client.get('/device-mon/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'device_mon/rekap.html')

    def test_dashboard_rtu_pindah_ke_halaman_sendiri(self):
        resp = self.client.get('/device-mon/rtu/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'device_mon/rtu_dashboard.html')

    def test_sidebar_punya_rekap_dan_bagian_rtu_sendiri(self):
        isi = self.client.get('/device-mon/').content.decode()
        self.assertIn('href="/device-mon/"', isi)
        self.assertIn('href="/device-mon/rtu/"', isi)
        self.assertIn('Rekap Semua', isi)
        # Bagian per instansi Zabbix tetap ada, termasuk yang baru ditambah.
        self.assertIn('href="/device-mon/zabbix/prosis/"', isi)
        self.assertNotIn('href="/device-mon/zabbix/lama/"', isi)

    def test_satu_baris_per_sumber_aktif_berurutan(self):
        sumber = self._rekap()['sumber']
        self.assertEqual([s['kode'] for s in sumber], ['rtu', 'telkom', 'prosis'])
        rtu, telkom, prosis = sumber
        self.assertEqual((rtu['total'], rtu['normal'], rtu['gangguan']), (2, 1, 1))
        self.assertEqual((telkom['total'], telkom['normal'], telkom['gangguan'], telkom['warning']),
                         (3, 1, 1, 1))
        self.assertEqual((prosis['total'], prosis['gangguan']), (1, 1))
        self.assertEqual(rtu['url'], '/device-mon/rtu/')
        self.assertEqual(prosis['url'], '/device-mon/zabbix/prosis/')

    def test_total_menjumlahkan_semua_sumber(self):
        total = self._rekap()['total']
        self.assertEqual(total, {'total': 6, 'normal': 2, 'gangguan': 3, 'warning': 1, 'unknown': 0})

    def test_angka_sama_dengan_dashboard_sumbernya(self):
        sumber = {s['kode']: s for s in self._rekap()['sumber']}
        rtu = self.client.get('/device-mon/api/status/').json()
        self.assertEqual(sumber['rtu']['normal'], rtu['total_up'])
        self.assertEqual(sumber['rtu']['gangguan'], rtu['total_down'])
        self.assertEqual(sumber['rtu']['avail_hari'], rtu['avail_hari'])
        for kode in ('telkom', 'prosis'):
            z = self.client.get(f'/device-mon/zabbix/{kode}/api/summary/').json()
            s = sumber[kode]
            self.assertEqual((s['total'], s['normal'], s['gangguan'], s['warning'], s['unknown']),
                             (z['total_host'], z['total_ok'], z['total_problem'],
                              z['total_warning'], z['total_unknown']), kode)
            self.assertEqual((s['avail_hari'], s['avail_bulan']),
                             (z['avail_hari'], z['avail_bulan']), kode)

    def test_gangguan_aktif_lintas_sumber_kritis_dulu_lalu_terlama(self):
        aktif = self._rekap()['aktif']
        self.assertEqual([a['nama'] for a in aktif],
                         ['Prosis Disaster', 'RTU-DOWN', 'Telkom High', 'Telkom Warning'])
        self.assertEqual([a['kelas'] for a in aktif], ['problem', 'problem', 'problem', 'warning'])
        rtu = aktif[1]
        self.assertEqual((rtu['sumber'], rtu['status'], rtu['lokasi']), ('RTU (SCADA)', 'DOWN', 'GI Tello'))
        telkom = aktif[2]
        self.assertEqual((telkom['status'], telkom['keterangan']), ('High', 'Link down'))
        self.assertTrue(telkom['url'].startswith('/device-mon/zabbix/host/'))

    def test_tanpa_data_sama_sekali_tetap_200(self):
        RTU.objects.all().delete()
        ZabbixHost.objects.all().delete()
        d = self._rekap()
        self.assertEqual(d['total']['total'], 0)
        self.assertEqual(d['aktif'], [])
        self.assertEqual(d['sumber'][0]['avail_hari'], None)

    def test_wajib_login(self):
        self.client.logout()
        for url in ('/device-mon/', '/device-mon/api/rekap/', '/device-mon/rtu/'):
            self.assertEqual(self.client.get(url).status_code, 302, url)
