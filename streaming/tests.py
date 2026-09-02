import json
import os
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from devices.models import UserProfile
from fasop.hashids_helper import encode

from . import ezviz
from .models import (
    NEVER_STARTED_ABANDON_SECONDS,
    PUBLISHER_ABANDON_SECONDS,
    PUBLISHER_STALE_SECONDS,
    EzvizToken,
    KameraEzviz,
    LiveSession,
    LiveViewerHeartbeat,
)
from .views import mediamtx_record_webhook


class MediaMtxRecordWebhookTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='teknisi')
        self.session = LiveSession.objects.create(teknisi=self.user, stream_key='abc123')

    def _post(self, segment_path, root):
        payload = {'path': 'live-abc123-rec', 'segment_path': segment_path}
        request = self.factory.post(
            '/streaming/webhook/mediamtx-record/?key=secret',
            data=json.dumps(payload),
            content_type='application/json',
        )
        with override_settings(MEDIAMTX_AUTH_SECRET='secret', STREAMING_RECORDINGS_ROOT=root):
            return mediamtx_record_webhook(request)

    def test_rejects_segment_path_outside_recordings_root(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            response = self._post(os.path.join(other, 'evil.mp4'), root)
            self.session.refresh_from_db()
            self.assertEqual(response.status_code, 403)
            self.assertEqual(self.session.recording_path, '')

    def test_accepts_segment_path_inside_recordings_root(self):
        with tempfile.TemporaryDirectory() as root:
            segment = os.path.join(root, 'live-abc123-rec.mp4')
            response = self._post(segment, root)
            self.session.refresh_from_db()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.session.recording_path, segment)


def _buat_user(username, role='technician'):
    user = User.objects.create_user(username=username, password='rahasia123')
    UserProfile.objects.update_or_create(
        user=user, defaults={'role': role, 'force_password_change': False},
    )
    return user


class MulaiSesiEzvizTests(TestCase):
    """
    Sesi Ezviz berdiri di atas satu baris KameraEzviz — tanpa kamera, sesi itu
    tidak punya apa pun untuk diputar. Tes di sini menjaga supaya kegagalan itu
    ditangkap saat pembuatan sesi, bukan baru terlihat sebagai kotak hitam di
    layar penonton.
    """

    def setUp(self):
        self.user = _buat_user('teknisi1')
        self.client.force_login(self.user)
        self.kamera = KameraEzviz.objects.create(nama='CCTV Gardu A', serial='BD3957004', channel=1)

    @override_settings(EZVIZ_APP_KEY='key', EZVIZ_APP_SECRET='secret')
    def test_sesi_ezviz_menyimpan_kamera_terpilih(self):
        resp = self.client.post(reverse('streaming:start'), {
            'sumber': 'ezviz', 'kamera': self.kamera.pk, 'judul': '',
        })
        sesi = LiveSession.objects.get()
        self.assertEqual(sesi.sumber, 'ezviz')
        self.assertEqual(sesi.kamera, self.kamera)
        # Judul kosong ikut nama kamera, bukan nama teknisi.
        self.assertIn('CCTV Gardu A', sesi.judul)
        self.assertRedirects(resp, reverse('streaming:detail', kwargs={'pk': sesi.pk}))

    @override_settings(EZVIZ_APP_KEY='key', EZVIZ_APP_SECRET='secret')
    def test_sesi_ezviz_tanpa_kamera_ditolak(self):
        resp = self.client.post(reverse('streaming:start'), {'sumber': 'ezviz', 'kamera': ''})
        self.assertRedirects(resp, reverse('streaming:list'))
        self.assertFalse(LiveSession.objects.exists())

    @override_settings(EZVIZ_APP_KEY='', EZVIZ_APP_SECRET='')
    def test_sesi_ezviz_ditolak_kalau_kredensial_kosong(self):
        self.client.post(reverse('streaming:start'), {'sumber': 'ezviz', 'kamera': self.kamera.pk})
        self.assertFalse(LiveSession.objects.exists())

    def test_sumber_tak_dikenal_jatuh_ke_kamera_perangkat(self):
        self.client.post(reverse('streaming:start'), {'sumber': 'entah-apa'})
        self.assertEqual(LiveSession.objects.get().sumber, 'perangkat')


class ApiSesiLiveTests(TestCase):
    def setUp(self):
        self.user = _buat_user('teknisi2')
        self.client.force_login(self.user)
        self.kamera = KameraEzviz.objects.create(nama='CCTV Gardu B', serial='BC7900686', channel=2, hd=False)
        self.sesi_perangkat = LiveSession.objects.create(teknisi=self.user, judul='Perangkat')
        self.sesi_ezviz = LiveSession.objects.create(
            teknisi=self.user, judul='CCTV', sumber='ezviz', kamera=self.kamera,
        )

    def test_tiap_sumber_membawa_data_pemutarnya_sendiri(self):
        data = self.client.get(reverse('streaming:api_live_sessions')).json()
        per_id = {x['id']: x for x in data['sessions']}

        perangkat = per_id[encode(self.sesi_perangkat.pk)]
        self.assertIn('view_token', perangkat)
        self.assertNotIn('ezopen_url', perangkat)

        sesi_ezviz = per_id[encode(self.sesi_ezviz.pk)]
        self.assertEqual(sesi_ezviz['ezopen_url'], 'ezopen://open.ys7.com/BC7900686/2.live')
        # Token baca MediaMTX tidak ada gunanya untuk sesi Ezviz — jangan
        # dikirim ke browser sama sekali.
        self.assertNotIn('view_token', sesi_ezviz)

    def test_pk_tidak_pernah_bocor_sebagai_angka(self):
        data = self.client.get(reverse('streaming:api_live_sessions')).json()
        for sesi in data['sessions']:
            self.assertNotEqual(sesi['id'], str(self.sesi_perangkat.pk))

    def test_parameter_nonton_mencatat_heartbeat_penonton(self):
        self.client.get(reverse('streaming:api_live_sessions'), {
            'nonton': encode(self.sesi_ezviz.pk),
        })
        self.assertTrue(
            LiveViewerHeartbeat.objects.filter(session=self.sesi_ezviz, user=self.user).exists()
        )
        self.assertFalse(
            LiveViewerHeartbeat.objects.filter(session=self.sesi_perangkat, user=self.user).exists()
        )

    def test_id_ngawur_di_nonton_tidak_membuat_heartbeat(self):
        self.client.get(reverse('streaming:api_live_sessions'), {'nonton': 'bukan-id,zzzz'})
        self.assertFalse(LiveViewerHeartbeat.objects.exists())


class SinkronKameraEzvizTests(TestCase):
    """
    Sinkronisasi menyentuh master data, jadi yang dijaga di sini justru apa
    yang TIDAK boleh dilakukannya: menimpa nama versi PLN dengan nama pabrik,
    dan menghapus baris yang masih ditunjuk sesi live lama.
    """

    def _mock_cloud(self, kamera):
        return mock.patch.object(ezviz, 'daftar_kamera_cloud', return_value=kamera)

    def test_kamera_baru_dibuat_aktif(self):
        with self._mock_cloud([{'serial': 'AA1', 'channel': 1, 'nama': 'C6N', 'status': 'online'}]):
            hasil = ezviz.sinkron_kamera()
        kamera = KameraEzviz.objects.get(serial='AA1')
        self.assertTrue(kamera.aktif)
        self.assertEqual(kamera.status_cloud, 'online')
        self.assertEqual(hasil['dibuat'], 1)

    def test_nama_yang_sudah_diedit_tidak_ditimpa(self):
        KameraEzviz.objects.create(nama='CCTV Bay Trafo 1', serial='AA1', channel=1, lokasi='GI Sungguminasa')
        with self._mock_cloud([{'serial': 'AA1', 'channel': 1, 'nama': 'C6N', 'status': 'offline'}]):
            ezviz.sinkron_kamera()
        kamera = KameraEzviz.objects.get(serial='AA1')
        self.assertEqual(kamera.nama, 'CCTV Bay Trafo 1')
        self.assertEqual(kamera.lokasi, 'GI Sungguminasa')
        self.assertEqual(kamera.status_cloud, 'offline')

    def test_kamera_hilang_ditandai_bukan_dihapus(self):
        KameraEzviz.objects.create(nama='Kamera Lama', serial='ZZ9', channel=1)
        with self._mock_cloud([]):
            hasil = ezviz.sinkron_kamera()
        kamera = KameraEzviz.objects.get(serial='ZZ9')
        self.assertEqual(kamera.status_cloud, 'hilang')
        self.assertEqual(hasil['hilang'], 1)

    def test_channel_berbeda_adalah_kamera_berbeda(self):
        """NVR: satu serial, banyak channel — masing-masing punya barisnya sendiri."""
        with self._mock_cloud([
            {'serial': 'NVR1', 'channel': 1, 'nama': 'Ch1', 'status': 'online'},
            {'serial': 'NVR1', 'channel': 2, 'nama': 'Ch2', 'status': 'online'},
        ]):
            ezviz.sinkron_kamera()
        self.assertEqual(KameraEzviz.objects.filter(serial='NVR1').count(), 2)


class AksesEzvizTests(TestCase):
    def test_viewer_tidak_bisa_ambil_token_ezviz(self):
        """
        accessToken berlaku untuk SELURUH akun Ezviz, jadi endpointnya harus
        tunduk pada pembatasan menu Live Streaming (Teknisi & AM saja) — bukan
        sekadar @login_required.
        """
        # force_login: proyek ini memakai django-axes, yang menolak
        # authenticate() tanpa request (lihat AxesBackend).
        self.client.force_login(_buat_user('penonton', role='viewer'))
        resp = self.client.get(reverse('streaming:ezviz_token'))
        self.assertEqual(resp.status_code, 403)

    @override_settings(EZVIZ_APP_KEY='', EZVIZ_APP_SECRET='')
    def test_token_menjelaskan_kalau_kredensial_kosong(self):
        self.client.force_login(_buat_user('teknisi3'))
        resp = self.client.get(reverse('streaming:ezviz_token'))
        self.assertEqual(resp.status_code, 503)
        self.assertIn('belum dikonfigurasi', resp.json()['error'])

    def test_teknisi_tidak_bisa_menyinkronkan_daftar_kamera(self):
        """Sinkronisasi menyentuh master data seluruh akun — dibatasi ke AM/superuser."""
        self.client.force_login(_buat_user('teknisi4'))
        resp = self.client.post(reverse('streaming:ezviz_sync'))
        self.assertEqual(resp.status_code, 403)


class TokenEzvizTests(TestCase):
    @override_settings(EZVIZ_APP_KEY='key', EZVIZ_APP_SECRET='secret')
    def test_token_yang_masih_berlaku_tidak_meminta_ulang_ke_ezviz(self):
        EzvizToken.objects.create(
            pk=1, token='at.lama', expire_at=timezone.now() + timezone.timedelta(days=3),
        )
        with mock.patch.object(ezviz, '_minta_token_baru') as minta:
            self.assertEqual(ezviz.ambil_access_token(), 'at.lama')
        minta.assert_not_called()

    @override_settings(EZVIZ_APP_KEY='key', EZVIZ_APP_SECRET='secret')
    def test_token_yang_hampir_kedaluwarsa_diperbarui(self):
        """
        Margin 1 jam: token yang tinggal beberapa menit tidak boleh dipakai —
        sesi yang sedang diputar akan mati di tengah jalan saat token habis.
        """
        EzvizToken.objects.create(
            pk=1, token='at.hampir-habis', expire_at=timezone.now() + timezone.timedelta(minutes=10),
        )
        with mock.patch.object(ezviz, '_minta_token_baru', return_value='at.baru') as minta:
            self.assertEqual(ezviz.ambil_access_token(), 'at.baru')
        minta.assert_called_once()


class PesanErrorEzvizTests(TestCase):
    """
    Pesan Ezviz sendiri tidak cukup untuk menjelaskan kegagalan yang paling
    sering terjadi. Kejadian nyata: appKey dari platform Singapura dikirim ke
    host bawaan open.ys7.com, dan yang muncul di layar hanya "appKey不存在" —
    dalam bahasa Mandarin, tanpa menyebut host mana pun.
    """

    def _tolak(self, kode, pesan):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {'code': kode, 'msg': pesan}
        return mock.patch.object(ezviz.requests, 'post', return_value=resp)

    @override_settings(EZVIZ_API_BASE='https://open.ys7.com')
    def test_error_menyebut_host_yang_dihubungi(self):
        with self._tolak('10005', 'appKey异常'):
            with self.assertRaises(ezviz.EzvizError) as ctx:
                ezviz._panggil('/api/lapp/token/get', {})
        self.assertIn('https://open.ys7.com', str(ctx.exception))

    @override_settings(EZVIZ_API_BASE='https://open.ys7.com')
    def test_appkey_tidak_dikenal_menyebut_kemungkinan_salah_region(self):
        with self._tolak('10017', 'appKey不存在'):
            with self.assertRaises(ezviz.EzvizError) as ctx:
                ezviz._panggil('/api/lapp/token/get', {})
        keterangan = str(ctx.exception)
        self.assertIn('EZVIZ_API_BASE', keterangan)
        self.assertIn('isgpopen.ezvizlife.com', keterangan)


class RegionTokenEzvizTests(TestCase):
    """
    /api/lapp/token/get mengembalikan `areaDomain`: host region tempat
    accessToken itu satu-satunya berlaku. Memakainya berarti operator cukup
    mengarahkan EZVIZ_API_BASE ke platform yang benar (Tiongkok vs
    internasional) — region persisnya ditentukan Ezviz sendiri.
    """

    def _balasan(self, payload):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = payload
        return resp

    @override_settings(EZVIZ_APP_KEY='k', EZVIZ_APP_SECRET='s',
                       EZVIZ_API_BASE='https://open.ezvizlife.com')
    def test_area_domain_disimpan_dan_dipakai_panggilan_berikutnya(self):
        token_resp = self._balasan({
            'code': '200',
            'data': {
                'accessToken': 'at.abc',
                'expireTime': 4102444800000,
                'areaDomain': 'https://isgpopen.ezvizlife.com',
            },
        })
        list_resp = self._balasan({'code': '200', 'data': []})

        with mock.patch.object(ezviz.requests, 'post', side_effect=[token_resp, list_resp]) as post:
            ezviz._dengan_token('/api/lapp/camera/list', {'pageStart': 0, 'pageSize': 50})

        self.assertEqual(EzvizToken.objects.get(pk=1).area_domain, 'https://isgpopen.ezvizlife.com')
        # Token diminta ke host entry, tapi panggilan berikutnya ke host region.
        self.assertEqual(post.call_args_list[0].args[0],
                         'https://open.ezvizlife.com/api/lapp/token/get')
        self.assertEqual(post.call_args_list[1].args[0],
                         'https://isgpopen.ezvizlife.com/api/lapp/camera/list')

    @override_settings(EZVIZ_API_BASE='https://open.ys7.com')
    def test_tanpa_area_domain_jatuh_ke_setting(self):
        self.assertEqual(ezviz.domain_aktif(), 'https://open.ys7.com')

    @override_settings(EZVIZ_APP_KEY='k', EZVIZ_APP_SECRET='s',
                       EZVIZ_API_BASE='https://open.ys7.com')
    def test_area_domain_lama_tidak_dihapus_balasan_tanpa_area_domain(self):
        """
        Sebagian region tidak mengirim areaDomain. Menimpanya dengan string
        kosong akan membuang informasi yang sudah benar dan memindahkan
        panggilan berikutnya ke host yang salah.
        """
        EzvizToken.objects.create(pk=1, token='lama', area_domain='https://isgpopen.ezvizlife.com')
        resp = self._balasan({'code': '200', 'data': {'accessToken': 'at.baru', 'expireTime': 4102444800000}})
        with mock.patch.object(ezviz.requests, 'post', return_value=resp):
            ezviz._minta_token_baru()
        self.assertEqual(EzvizToken.objects.get(pk=1).area_domain, 'https://isgpopen.ezvizlife.com')

    def test_kode_parameter_salah_tidak_memicu_permintaan_token_ulang(self):
        """10001 = parameter salah menurut dokumentasi Ezviz, bukan token basi."""
        self.assertNotIn('10001', ezviz.KODE_TOKEN_BASI)
        self.assertIn('10002', ezviz.KODE_TOKEN_BASI)


class AlamatEzopenTests(TestCase):
    def test_serial_dinormalkan_jadi_kapital_tanpa_spasi(self):
        """
        Dokumentasi Ezviz mensyaratkan huruf pada serial ditulis KAPITAL.
        Serial yang tidak memenuhi itu ditolak server dengan "illegal parameter
        ezopen" (10001) — pesan yang tidak menyebut serialnya sama sekali, jadi
        satu-satunya cara aman adalah menormalkannya sebelum disimpan.
        """
        k = KameraEzviz.objects.create(nama='A', serial='  bd3957004 ', channel=1)
        k.refresh_from_db()
        self.assertEqual(k.serial, 'BD3957004')
        self.assertEqual(k.ezopen_url, 'ezopen://open.ys7.com/BD3957004/1.hd.live')

    def test_channel_kosong_jatuh_ke_satu(self):
        k = KameraEzviz.objects.create(nama='A', serial='BD3957004', channel=0)
        k.refresh_from_db()
        self.assertEqual(k.channel, 1)

    def test_sinkron_menormalkan_serial_dari_cloud(self):
        with mock.patch.object(ezviz, 'daftar_kamera_cloud', return_value=[
            {'serial': 'bd3957004', 'channel': 1, 'nama': 'C6N', 'status': 'online'},
        ]):
            ezviz.sinkron_kamera()
        self.assertTrue(KameraEzviz.objects.filter(serial='BD3957004').exists())

    @override_settings(EZVIZ_EZOPEN_HOST='isgpopen.ezvizlife.com')
    def test_host_ezopen_bisa_diganti_per_region(self):
        """
        Host di dalam alamat ezopen bukan host API, dan yang tidak diterima
        ditolak server sebagai "illegal parameter ezopen" tanpa keterangan —
        jadi harus bisa diganti tanpa mengubah kode.
        """
        k = KameraEzviz(nama='A', serial='BF5628809', channel=1, hd=False)
        self.assertEqual(k.ezopen_url, 'ezopen://isgpopen.ezvizlife.com/BF5628809/1.live')

    def test_hd_menyisipkan_penanda_kualitas(self):
        hd = KameraEzviz(nama='A', serial='BD3957004', channel=1, hd=True)
        sd = KameraEzviz(nama='B', serial='BD3957004', channel=3, hd=False)
        self.assertEqual(hd.ezopen_url, 'ezopen://open.ys7.com/BD3957004/1.hd.live')
        self.assertEqual(sd.ezopen_url, 'ezopen://open.ys7.com/BD3957004/3.live')


class SiaranTerputusTests(TestCase):
    """
    `status='live'` saja tidak pernah cukup untuk tahu sebuah sesi benar-benar
    mengirim video: status hanya berubah kalau ada yang menekan "Akhiri Live".
    Begitu halaman teknisi ter-refresh atau tertutup, sesinya menggantung
    "Sedang Live" padahal kosong. Tes di sini menjaga pembedaan itu.
    """

    def setUp(self):
        self.user = _buat_user('teknisi5')
        self.client.force_login(self.user)
        self.sesi = LiveSession.objects.create(teknisi=self.user, judul='Uji')

    def _geser_publisher(self, detik):
        LiveSession.objects.filter(pk=self.sesi.pk).update(
            publisher_last_seen=timezone.now() - timezone.timedelta(seconds=detik),
        )
        self.sesi.refresh_from_db()

    def test_sesi_baru_belum_dianggap_tersiar(self):
        self.assertTrue(self.sesi.is_live)
        self.assertFalse(self.sesi.siaran_aktif)
        self.assertFalse(self.sesi.pernah_tersiar)

    def test_heartbeat_penyiar_membuat_sesi_dianggap_tersiar(self):
        self.client.post(reverse('streaming:publisher_heartbeat', kwargs={'pk': self.sesi.pk}))
        self.sesi.refresh_from_db()
        self.assertTrue(self.sesi.siaran_aktif)
        self.assertTrue(self.sesi.pernah_tersiar)

    def test_kabar_penyiar_yang_basi_berarti_terputus(self):
        self._geser_publisher(PUBLISHER_STALE_SECONDS + 5)
        self.assertFalse(self.sesi.siaran_aktif)
        # Tetap 'pernah tersiar' — inilah yang membuat halaman siaran
        # menyambung ulang otomatis alih-alih menunggu klik.
        self.assertTrue(self.sesi.pernah_tersiar)

    def test_berhenti_mengosongkan_penanda_seketika(self):
        """Menutup halaman tidak boleh menyisakan 30 detik status 'live' palsu."""
        self.client.post(reverse('streaming:publisher_heartbeat', kwargs={'pk': self.sesi.pk}))
        self.client.post(reverse('streaming:publisher_heartbeat', kwargs={'pk': self.sesi.pk}), {'berhenti': '1'})
        self.sesi.refresh_from_db()
        self.assertIsNone(self.sesi.publisher_last_seen)
        self.assertFalse(self.sesi.siaran_aktif)

    def test_hanya_pemilik_sesi_yang_boleh_mengabarkan_siaran(self):
        self.client.force_login(_buat_user('teknisi6'))
        resp = self.client.post(reverse('streaming:publisher_heartbeat', kwargs={'pk': self.sesi.pk}))
        self.assertEqual(resp.status_code, 403)
        self.sesi.refresh_from_db()
        self.assertIsNone(self.sesi.publisher_last_seen)

    def test_status_json_membedakan_live_dari_tersiar(self):
        data = self.client.get(reverse('streaming:status', kwargs={'pk': self.sesi.pk})).json()
        self.assertTrue(data['is_live'])
        self.assertFalse(data['siaran_aktif'])

    def test_sesi_ezviz_selalu_dianggap_tersiar(self):
        """Tidak ada browser yang mem-publish sesi Ezviz — tidak ada yang bisa putus."""
        kamera = KameraEzviz.objects.create(nama='CCTV', serial='EZ1', channel=1)
        sesi = LiveSession.objects.create(teknisi=self.user, sumber='ezviz', kamera=kamera)
        self.assertTrue(sesi.siaran_aktif)


class UrlMultiViewTests(TestCase):
    def test_path_lama_dialihkan_ke_multi_view(self):
        """
        `/streaming/dinding/` adalah nama halaman ini sebelum labelnya jadi
        "Multi View". Dipertahankan sebagai pengalihan karena layar ruang
        operasi kemungkinan sudah menyimpannya sebagai bookmark — dan 302,
        bukan 301, supaya path itu tidak terkunci selamanya di cache browser.
        """
        self.client.force_login(_buat_user('teknisi8'))
        resp = self.client.get('/streaming/dinding/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('streaming:grid'))

    def test_url_baru_dipakai_saat_membangun_tautan(self):
        self.assertEqual(reverse('streaming:grid'), '/streaming/multi-view/')


class SesiTerbengkalaiTests(TestCase):
    def setUp(self):
        self.user = _buat_user('teknisi7')
        self.client.force_login(self.user)

    def _tuakan(self, sesi, detik):
        LiveSession.objects.filter(pk=sesi.pk).update(
            started_at=timezone.now() - timezone.timedelta(seconds=detik),
        )

    def test_sesi_yang_penyiarnya_lama_hilang_diakhiri(self):
        sesi = LiveSession.objects.create(teknisi=self.user)
        LiveSession.objects.filter(pk=sesi.pk).update(
            publisher_last_seen=timezone.now() - timezone.timedelta(seconds=PUBLISHER_ABANDON_SECONDS + 60),
        )
        LiveSession.akhiri_yang_terbengkalai()
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'ended')
        self.assertIsNotNone(sesi.ended_at)

    def test_sesi_yang_tidak_pernah_menyiar_diakhiri_setelah_ambang_yang_longgar(self):
        """Teknisi menekan "Mulai Live" lalu menutup tab tanpa pernah mengirim video."""
        sesi = LiveSession.objects.create(teknisi=self.user)
        self._tuakan(sesi, NEVER_STARTED_ABANDON_SECONDS + 60)
        LiveSession.akhiri_yang_terbengkalai()
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'ended')

    def test_sesi_yang_belum_menyiar_tidak_ditutup_secepat_yang_terputus(self):
        """
        Teknisi lazim menekan "Mulai Live" dari kantor lalu berjalan ke
        peralatannya. Kalau sesinya sudah ditutup saat ia akhirnya menekan
        "Mulai Kirim", MediaMTX akan menolak publish-nya (webhook auth
        mensyaratkan sesi masih live) — persis di saat ia siap bekerja.
        """
        sesi = LiveSession.objects.create(teknisi=self.user)
        self._tuakan(sesi, PUBLISHER_ABANDON_SECONDS + 60)
        LiveSession.akhiri_yang_terbengkalai()
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'live')

    def test_sesi_yang_baru_dibuat_tidak_ikut_diakhiri(self):
        """Teknisi masih memilih kamera — jangan tutup sesinya di bawah kakinya."""
        sesi = LiveSession.objects.create(teknisi=self.user)
        LiveSession.akhiri_yang_terbengkalai()
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'live')

    def test_sesi_yang_sedang_menyiar_tidak_diakhiri(self):
        sesi = LiveSession.objects.create(teknisi=self.user)
        self._tuakan(sesi, NEVER_STARTED_ABANDON_SECONDS + 60)
        LiveSession.objects.filter(pk=sesi.pk).update(publisher_last_seen=timezone.now())
        LiveSession.akhiri_yang_terbengkalai()
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'live')

    def test_sesi_ezviz_tidak_pernah_diakhiri_otomatis(self):
        """Tidak ada penyiar yang bisa menghilang; kameranya memang masih mengalir."""
        kamera = KameraEzviz.objects.create(nama='CCTV', serial='EZ2', channel=1)
        sesi = LiveSession.objects.create(teknisi=self.user, sumber='ezviz', kamera=kamera)
        self._tuakan(sesi, NEVER_STARTED_ABANDON_SECONDS * 10)
        LiveSession.akhiri_yang_terbengkalai()
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'live')

    def test_halaman_daftar_membereskan_sesi_hantu(self):
        sesi = LiveSession.objects.create(teknisi=self.user)
        self._tuakan(sesi, NEVER_STARTED_ABANDON_SECONDS + 60)
        self.client.get(reverse('streaming:list'))
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'ended')

    def test_api_multi_view_membereskan_sesi_hantu(self):
        sesi = LiveSession.objects.create(teknisi=self.user)
        self._tuakan(sesi, NEVER_STARTED_ABANDON_SECONDS + 60)
        data = self.client.get(reverse('streaming:api_live_sessions')).json()
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'ended')
        self.assertEqual(data['sessions'], [])
