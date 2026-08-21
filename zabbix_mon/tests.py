"""
Tes gating blast WhatsApp untuk host Zabbix (zabbix_mon.notifications).

Fokusnya keputusan "kirim / tidak kirim" — gateway OpenWA-nya sendiri
di-mock, karena yang gampang salah di sini adalah ambang severity dan
aturan pesan pulih, bukan HTTP-nya.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from zabbix_mon.models import ZabbixAlertLog, ZabbixHost
from zabbix_mon.notifications import alert_wa, targets_default, _targets


def _host(**kwargs):
    data = dict(
        zabbix_hostid='10084', zabbix_host='voip-mks', nama='VoIP Makassar',
        lokasi='Kantor UP2B', wa_alert=True, wa_min_severity='3',
        state='PROBLEM', severity='High', problem_name='Interface down',
    )
    data.update(kwargs)
    return ZabbixHost.objects.create(**data)


@override_settings(WA_CHAT_IDS_ZABBIX='123@g.us', WA_CHAT_IDS='rtu@g.us')
class AlertWaTest(TestCase):

    def test_host_tanpa_wa_alert_tidak_dikirim_dan_tidak_dicatat(self):
        host = _host(wa_alert=False)
        with patch('device_mon.notifications.kirim_wa') as mock_kirim:
            self.assertFalse(alert_wa(host, 'PROBLEM'))
        mock_kirim.assert_not_called()
        self.assertEqual(ZabbixAlertLog.objects.count(), 0)

    def test_severity_di_bawah_ambang_dilewati_tapi_dicatat(self):
        host = _host(wa_min_severity='4', severity='Warning')   # 2 < 4
        with patch('device_mon.notifications.kirim_wa') as mock_kirim:
            self.assertFalse(alert_wa(host, 'PROBLEM'))
        mock_kirim.assert_not_called()
        log = ZabbixAlertLog.objects.get()
        self.assertFalse(log.terkirim)
        self.assertIn('di bawah ambang', log.keterangan)

    def test_severity_memenuhi_ambang_dikirim(self):
        host = _host(wa_min_severity='3', severity='High')      # 4 >= 3
        with patch('device_mon.notifications.kirim_wa', return_value=(1, 1, 'OK')) as mock_kirim:
            self.assertTrue(alert_wa(host, 'PROBLEM'))
        pesan = mock_kirim.call_args.args[0]
        self.assertIn('VoIP Makassar', pesan)
        self.assertIn('Interface down', pesan)
        self.assertEqual(mock_kirim.call_args.kwargs['chat_ids'], ['123@g.us'])
        self.assertTrue(ZabbixAlertLog.objects.get().terkirim)

    def test_pulih_dikirim_hanya_kalau_problemnya_tadi_terkirim(self):
        host = _host()
        with patch('device_mon.notifications.kirim_wa', return_value=(1, 1, 'OK')):
            alert_wa(host, 'PROBLEM')
        with patch('device_mon.notifications.kirim_wa', return_value=(1, 1, 'OK')) as mock_kirim:
            self.assertTrue(alert_wa(host, 'OK', dur_tutup_menit=90))
        self.assertIn('1 jam 30 menit', mock_kirim.call_args.args[0])

    def test_pulih_dilewati_kalau_problemnya_tidak_pernah_masuk(self):
        host = _host(wa_min_severity='5', severity='Warning')
        with patch('device_mon.notifications.kirim_wa') as mock_kirim:
            alert_wa(host, 'PROBLEM')          # dilewati, terkirim=False
            self.assertFalse(alert_wa(host, 'OK', dur_tutup_menit=10))
        mock_kirim.assert_not_called()

    def test_gagal_kirim_dicatat_dengan_keterangan_gateway(self):
        host = _host()
        with patch('device_mon.notifications.kirim_wa',
                   return_value=(0, 1, '123@g.us: HTTP 500 session not connected')):
            self.assertFalse(alert_wa(host, 'PROBLEM'))
        log = ZabbixAlertLog.objects.get()
        self.assertFalse(log.terkirim)
        self.assertIn('session not connected', log.keterangan)

    def test_tujuan_kosong_dicatat_sebagai_salah_konfigurasi(self):
        host = _host()
        with override_settings(WA_CHAT_IDS_ZABBIX='', WA_CHAT_IDS=''):
            with patch('device_mon.notifications.kirim_wa') as mock_kirim:
                self.assertFalse(alert_wa(host, 'PROBLEM'))
        mock_kirim.assert_not_called()
        self.assertIn('Tujuan WA kosong', ZabbixAlertLog.objects.get().keterangan)


@override_settings(WA_CHAT_IDS_ZABBIX='zbx@g.us', WA_CHAT_IDS='rtu@g.us')
class TargetResolutionTest(TestCase):

    def test_default_pakai_wa_chat_ids_zabbix(self):
        self.assertEqual(targets_default(), ['zbx@g.us'])

    def test_default_jatuh_ke_wa_chat_ids_kalau_zabbix_kosong(self):
        with override_settings(WA_CHAT_IDS_ZABBIX=''):
            self.assertEqual(targets_default(), ['rtu@g.us'])

    def test_kolom_host_menimpa_default(self):
        host = _host(wa_chat_ids=' a@g.us , b@g.us ')
        self.assertEqual(_targets(host), ['a@g.us', 'b@g.us'])

    def test_kolom_host_kosong_pakai_default(self):
        self.assertEqual(_targets(_host(wa_chat_ids='')), ['zbx@g.us'])


class SeverityIndexTest(TestCase):

    def test_label_angka_dan_nilai_aneh(self):
        from zabbix_mon.zabbix_api import severity_index
        self.assertEqual(severity_index('Disaster'), 5)
        self.assertEqual(severity_index('high'), 4)
        self.assertEqual(severity_index('4'), 4)
        self.assertEqual(severity_index(''), 0)
        self.assertEqual(severity_index(None), 0)
        self.assertEqual(severity_index('Entah apa'), 0)
