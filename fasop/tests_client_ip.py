"""
IP klien di belakang nginx/cloudflared — fasop/client_ip.py.

Di produksi REMOTE_ADDR selalu 127.0.0.1 (nginx). Sebelum ini django-axes
membaca REMOTE_ADDR (semua orang satu IP → siapa pun bisa mengunci akun orang
lain), sedangkan log login & audit log membaca elemen PERTAMA X-Forwarded-For
(bisa diisi pengirim sendiri).
"""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from fasop.client_ip import ip_klien

NGINX = '127.0.0.1'
PUBLIK = '203.0.113.7'
KARANGAN = '6.6.6.6'


def _req(remote=NGINX, xff=None):
    meta = {'REMOTE_ADDR': remote}
    if xff is not None:
        meta['HTTP_X_FORWARDED_FOR'] = xff
    return RequestFactory().get('/', **meta)


class IpKlienTest(TestCase):
    def test_lewat_cloudflare_dan_nginx(self):
        # Cloudflare menulis IP pengguna, nginx menambahkan alamat cloudflared.
        self.assertEqual(ip_klien(_req(xff=f'{PUBLIK}, 127.0.0.1')), PUBLIK)

    def test_x_forwarded_for_karangan_pengirim_diabaikan(self):
        # Penyerang mengirim X-Forwarded-For sendiri; Cloudflare MENAMBAHKAN.
        self.assertEqual(ip_klien(_req(xff=f'{KARANGAN}, {PUBLIK}, 127.0.0.1')), PUBLIK)
        self.assertEqual(ip_klien(_req(xff=f'not-an-ip, 1.1.1.1, {PUBLIK}, 127.0.0.1')), PUBLIK)

    def test_jaringan_kantor_lewat_nginx(self):
        # http://IP-internal: tidak lewat Cloudflare, nginx menambahkan IP pengguna.
        self.assertEqual(ip_klien(_req(xff=f'{KARANGAN}, 192.168.10.20')), '192.168.10.20')

    def test_tersambung_langsung_header_tidak_dipercaya(self):
        # Bukan dari proxy kita (mis. langsung ke port gunicorn): header dikarang.
        self.assertEqual(ip_klien(_req(remote='192.168.10.20', xff=KARANGAN)), '192.168.10.20')

    def test_tanpa_header_jatuh_ke_remote_addr(self):
        self.assertEqual(ip_klien(_req()), NGINX)
        self.assertEqual(ip_klien(_req(xff='')), NGINX)

    def test_isian_rusak_di_ujung_kanan_tidak_dipercaya(self):
        self.assertEqual(ip_klien(_req(xff=f'{PUBLIK}, sampah')), NGINX)

    def test_unix_socket_dianggap_proxy_lokal(self):
        self.assertEqual(ip_klien(_req(remote='', xff=f'{KARANGAN}, {PUBLIK}')), PUBLIK)

    def test_port_dan_ipv6_dinormalkan(self):
        self.assertEqual(ip_klien(_req(xff=f'{PUBLIK}:51234')), PUBLIK)
        self.assertEqual(ip_klien(_req(xff='[2001:db8::1]:443')), '2001:db8::1')
        self.assertEqual(ip_klien(_req(xff='2001:DB8:0::1')), '2001:db8::1')
        self.assertEqual(ip_klien(_req(xff=f'::ffff:{PUBLIK}')), PUBLIK)
        self.assertEqual(ip_klien(_req(remote='::1', xff=PUBLIK)), PUBLIK)

    @override_settings(PROXY_TEPERCAYA=['127.0.0.1', '172.17.0.0/16'])
    def test_proxy_tambahan_bisa_didaftarkan(self):
        # cloudflared di container Docker: nginx melihatnya sebagai 172.17.x.x.
        self.assertEqual(ip_klien(_req(xff=f'{PUBLIK}, 172.17.0.2')), PUBLIK)

    def test_proxy_yang_tidak_didaftarkan_tidak_dilompati(self):
        self.assertEqual(ip_klien(_req(xff=f'{PUBLIK}, 172.17.0.2')), '172.17.0.2')


class PemakaiIpKlienTest(TestCase):
    """Semua pencatat IP memakai ip_klien — bukan elemen pertama X-Forwarded-For."""

    HEADER = {'REMOTE_ADDR': NGINX, 'HTTP_X_FORWARDED_FOR': f'{KARANGAN}, {PUBLIK}, 127.0.0.1'}

    def setUp(self):
        self.user = User.objects.create_user('budi', password='Rahasia-123')
        self.user.profile.force_password_change = False
        self.user.profile.save(update_fields=['force_password_change'])

    def _login(self, password, **header):
        return self.client.post(reverse('login'), {'username': 'budi', 'password': password},
                                **(header or self.HEADER))

    def test_log_login_mencatat_ip_sebenarnya(self):
        from devices.models import UserLoginLog
        self.assertEqual(self._login('Rahasia-123').status_code, 302)
        self.assertEqual(UserLoginLog.objects.get(action='login').ip_address, PUBLIK)

    def test_axes_mencatat_ip_sebenarnya(self):
        from axes.models import AccessAttempt
        self._login('salah')
        self.assertEqual(AccessAttempt.objects.get().ip_address, PUBLIK)

    @override_settings(AXES_FAILURE_LIMIT=3)
    def test_penyerang_tidak_bisa_mengunci_akun_orang_lain(self):
        """
        Inti perbaikannya. Dulu semua permintaan tercatat 127.0.0.1, jadi 3x
        salah password dari internet mengunci 'budi' untuk SEMUA orang.
        """
        penyerang = {'REMOTE_ADDR': NGINX, 'HTTP_X_FORWARDED_FOR': f'{KARANGAN}, 127.0.0.1'}
        for _ in range(4):
            resp = self._login('salah', **penyerang)
        self.assertEqual(resp.status_code, 429)   # penyerangnya sendiri terkunci

        pemilik = {'REMOTE_ADDR': NGINX, 'HTTP_X_FORWARDED_FOR': f'{PUBLIK}, 127.0.0.1'}
        self.assertEqual(self._login('Rahasia-123', **pemilik).status_code, 302)

    @override_settings(AXES_FAILURE_LIMIT=3)
    def test_mengarang_x_forwarded_for_tidak_melepas_kunci(self):
        """Mengganti isi X-Forwarded-For tiap percobaan tidak memberi 'IP baru'."""
        for i in range(4):
            resp = self._login('salah', REMOTE_ADDR=NGINX,
                               HTTP_X_FORWARDED_FOR=f'10.0.0.{i}, {PUBLIK}, 127.0.0.1')
        self.assertEqual(resp.status_code, 429)

    def test_audit_log_mencatat_ip_sebenarnya(self):
        from auditlog.models import AuditLog
        from auditlog.utils import log_action
        req = RequestFactory().get('/', **self.HEADER)
        req.user = self.user
        log_action(req, 'update', 'devices', 'Device', object_id=1, object_repr='x')
        self.assertEqual(AuditLog.objects.get().ip_address, PUBLIK)


class KunciApiIpTest(TestCase):
    def test_ip_terakhir_kunci_api_ip_sebenarnya(self):
        from api.tests import _hdr, _kunci
        k = _kunci('Konsumen', 'status_monitor')
        r = self.client.get(reverse('api:fasop_status_monitor'), headers=_hdr(k),
                            REMOTE_ADDR=NGINX, HTTP_X_FORWARDED_FOR=f'{KARANGAN}, {PUBLIK}, 127.0.0.1')
        self.assertEqual(r.status_code, 200)
        k.refresh_from_db()
        self.assertEqual(k.terakhir_ip, PUBLIK)


class CekIpTest(TestCase):
    def test_superuser_melihat_rincian(self):
        admin = User.objects.create_superuser('adm-ip', 'a@b.id', 'Rahasia-123')
        admin.profile.force_password_change = False
        admin.profile.save(update_fields=['force_password_change'])
        self.client.force_login(admin)
        d = self.client.get('/cek-ip/', REMOTE_ADDR=NGINX,
                            HTTP_X_FORWARDED_FOR=f'{KARANGAN}, {PUBLIK}, 127.0.0.1').json()
        self.assertEqual(d['ip_klien'], PUBLIK)
        self.assertEqual(d['REMOTE_ADDR'], NGINX)
        self.assertIn('127.0.0.1/32', d['PROXY_TEPERCAYA'])

    def test_selain_superuser_404(self):
        self.assertEqual(self.client.get('/cek-ip/').status_code, 404)
        user = User.objects.create_user('biasa', password='Rahasia-123')
        user.profile.force_password_change = False
        user.profile.save(update_fields=['force_password_change'])
        self.client.force_login(user)
        self.assertEqual(self.client.get('/cek-ip/').status_code, 404)
