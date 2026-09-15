"""
Tes gating blast WhatsApp (device_mon.notifications).

Fokusnya keputusan "kirim / tidak kirim" — gateway OpenWA-nya sendiri
di-mock, karena yang gampang salah di sini adalah ambang severity, aturan
pesan pulih, dan resolusi tujuan; bukan HTTP-nya.
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
        obj = ZabbixInstance.objects.create(kode='telkom', nama='Zabbix Telkom')
        self.assertEqual(obj.api_url_efektif(), 'http://zabbix-env.local/api_jsonrpc.php')
        self.assertEqual(obj.api_token_efektif(), 'token-env')
        self.assertEqual(obj.webhook_token_efektif(), 'webhook-env')

    @override_settings(ZABBIX_API_URL='http://zabbix-env.local/api_jsonrpc.php',
                       ZABBIX_WEBHOOK_TOKEN='webhook-env')
    def test_field_terisi_menimpa_env(self):
        obj = ZabbixInstance.objects.create(
            kode='prosis', nama='Zabbix Prosis',
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
        kosong = ZabbixInstance.objects.create(kode='telkom', nama='Zabbix Telkom')
        self.assertEqual(kosong.wa_chat_ids_efektif(), ['zbx@g.us'])

        sendiri = ZabbixInstance.objects.create(
            kode='prosis', nama='Zabbix Prosis', wa_chat_ids='prosis@g.us')
        self.assertEqual(sendiri.wa_chat_ids_efektif(), ['prosis@g.us'])

    @override_settings(WA_CHAT_IDS_ZABBIX='', WA_CHAT_IDS='rtu@g.us')
    def test_zbx_targets_host_jatuh_ke_instance_dulu_baru_global(self):
        prosis = ZabbixInstance.objects.create(
            kode='prosis', nama='Zabbix Prosis', wa_chat_ids='prosis@g.us')
        host = _host(instance=prosis, wa_chat_ids='')
        self.assertEqual(zbx_targets(host), ['prosis@g.us'])


class ZabbixHostUniquePerInstanceTest(TestCase):
    """hostid unik PER INSTANSI, bukan global — dua server Zabbix berbeda
    boleh kebetulan memakai hostid yang sama untuk host yang berbeda."""

    def test_hostid_sama_di_instansi_berbeda_tidak_bentrok(self):
        telkom = ZabbixInstance.objects.create(kode='telkom', nama='Zabbix Telkom')
        prosis = ZabbixInstance.objects.create(kode='prosis', nama='Zabbix Prosis')
        ZabbixHost.objects.create(instance=telkom, zabbix_hostid='10084', nama='Host Telkom')
        # Tidak boleh IntegrityError meski hostid-nya sama persis.
        h2 = ZabbixHost.objects.create(instance=prosis, zabbix_hostid='10084', nama='Host Prosis')
        self.assertEqual(h2.zabbix_hostid, '10084')

    def test_hostid_sama_di_instansi_sama_bentrok(self):
        from django.db import IntegrityError, transaction
        telkom = ZabbixInstance.objects.create(kode='telkom', nama='Zabbix Telkom')
        ZabbixHost.objects.create(instance=telkom, zabbix_hostid='10084', nama='A')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ZabbixHost.objects.create(instance=telkom, zabbix_hostid='10084', nama='B')


class ZabbixWebhookInstanceTest(TestCase):
    """Endpoint webhook per-instansi — token dan host tidak boleh bocor antar instansi."""

    def setUp(self):
        self.telkom = ZabbixInstance.objects.create(
            kode='telkom', nama='Zabbix Telkom', webhook_token='token-telkom')
        self.prosis = ZabbixInstance.objects.create(
            kode='prosis', nama='Zabbix Prosis', webhook_token='token-prosis')

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
        self.telkom = ZabbixInstance.objects.create(kode='telkom', nama='Zabbix Telkom')
        self.prosis = ZabbixInstance.objects.create(kode='prosis', nama='Zabbix Prosis')
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
        self.telkom = ZabbixInstance.objects.create(
            kode='telkom', nama='Zabbix Telkom', api_url='http://telkom.local/api_jsonrpc.php')
        self.prosis = ZabbixInstance.objects.create(
            kode='prosis', nama='Zabbix Prosis', api_url='http://prosis.local/api_jsonrpc.php')

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
