"""
Content-Security-Policy & Permissions-Policy (fasop/security_headers.py).

Muncul dari pemindaian securityheaders.com (9 Okt 2026): dua header itu satu-
satunya yang belum ada. Tes ini menjaga supaya header-nya ada di halaman, TIDAK
ada di tempat yang justru merusak (service worker), dan halaman Ezviz tetap
mendapat izin yang dibutuhkan pemutarnya.
"""
import re
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from devices.models import UserProfile
from fasop.security_headers import gabung_csp, susun_permissions_policy
from fasop.settings import _CSP_KEBIJAKAN as _KEBIJAKAN
from streaming.models import KameraEzviz, LiveSession


def _direktif(header):
    """'a x y; b z' → {'a': ['x', 'y'], 'b': ['z']}."""
    hasil = {}
    for bagian in header.split(';'):
        kata = bagian.split()
        if kata:
            hasil[kata[0]] = kata[1:]
    return hasil


class CspHalamanTest(TestCase):
    def test_halaman_login_membawa_csp(self):
        resp = self.client.get(reverse('login'))
        csp = _direktif(resp.headers['Content-Security-Policy'])
        self.assertEqual(csp['object-src'], ["'none'"])
        self.assertEqual(csp['base-uri'], ["'self'"])
        self.assertEqual(csp['form-action'], ["'self'"])
        # Bootstrap/Chart.js dari CDN harus tetap termuat.
        self.assertIn('https://cdn.jsdelivr.net', csp['script-src'])
        self.assertIn('https://fonts.gstatic.com', csp['font-src'])

    def test_frame_ancestors_tidak_mengambil_alih_x_frame_options(self):
        """
        Begitu frame-ancestors ada, browser mengabaikan X-Frame-Options — dan
        pratinjau BA yang sengaja SAMEORIGIN ikut berubah aturannya.
        """
        resp = self.client.get(reverse('login'))
        self.assertNotIn('frame-ancestors', resp.headers['Content-Security-Policy'])
        self.assertEqual(resp.headers['X-Frame-Options'], 'DENY')

    @override_settings(AXES_FAILURE_LIMIT=2)
    def test_halaman_lockout_membawa_csp(self):
        for _ in range(3):
            resp = self.client.post(reverse('login'), {'username': 'alice', 'password': 'salah'})
        self.assertEqual(resp.status_code, 429)
        self.assertIn('Content-Security-Policy', resp.headers)

    def test_service_worker_tidak_membawa_csp(self):
        """
        Service worker tunduk pada CSP respons skripnya sendiri. Service worker
        FASOP mengambil ulang aset CDN lewat fetch(); dengan connect-src
        halaman, semua fetch itu ditolak dan tiap halaman kehilangan CSS/JS.
        """
        resp = self.client.get(reverse('service_worker'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Content-Security-Policy', resp.headers)
        self.assertNotIn('Content-Security-Policy-Report-Only', resp.headers)

    @override_settings(SECURE_CSP={}, SECURE_CSP_REPORT_ONLY=settings.SECURE_CSP)
    def test_mode_report_only(self):
        resp = self.client.get(reverse('login'))
        self.assertNotIn('Content-Security-Policy', resp.headers)
        self.assertIn("object-src 'none'", resp.headers['Content-Security-Policy-Report-Only'])

    @override_settings(SECURE_CSP={}, SECURE_CSP_REPORT_ONLY={})
    def test_mode_off(self):
        resp = self.client.get(reverse('login'))
        self.assertNotIn('Content-Security-Policy', resp.headers)
        self.assertNotIn('Content-Security-Policy-Report-Only', resp.headers)

    def test_connect_src_memuat_mediamtx(self):
        """WHIP/WHEP adalah fetch() langsung dari browser ke MediaMTX."""
        csp = _direktif(self.client.get(reverse('login')).headers['Content-Security-Policy'])
        self.assertIn("'self'", csp['connect-src'])
        for url in (settings.MEDIAMTX_WHIP_URL, settings.MEDIAMTX_WHEP_URL):
            origin = '/'.join(url.split('/')[:3])
            self.assertIn(origin, csp['connect-src'])


def _buat_teknisi(username):
    user = User.objects.create_user(username=username, password='rahasia123')
    UserProfile.objects.update_or_create(
        user=user, defaults={'role': 'technician', 'force_password_change': False},
    )
    return user


class CspEzvizTest(TestCase):
    """
    EZUIKit memuat decoder wasm dari openstatic.ys7.com ke worker blob: dan
    membuka websocket ke server stream yang ditunjuk cloud Ezviz — semuanya
    ditolak kebijakan dasar. Izin itu hanya boleh ada di halaman pemutarnya.
    """

    def setUp(self):
        self.user = _buat_teknisi('teknisi_csp')
        self.client.force_login(self.user)
        kamera = KameraEzviz.objects.create(nama='CCTV', serial='EZ1', channel=1)
        self.sesi_ezviz = LiveSession.objects.create(
            teknisi=self.user, sumber='ezviz', kamera=kamera,
        )
        self.sesi_perangkat = LiveSession.objects.create(teknisi=self.user)

    def _csp(self, url, header='Content-Security-Policy'):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return _direktif(resp.headers[header])

    def _cek_izin_ezviz(self, csp):
        self.assertIn("'wasm-unsafe-eval'", csp['script-src'])
        self.assertIn('https://*.ys7.com', csp['script-src'])
        self.assertIn('wss:', csp['connect-src'])
        self.assertEqual(csp['worker-src'], ["'self'", 'blob:'])
        # Perluasan, bukan pengganti.
        self.assertIn('https://cdn.jsdelivr.net', csp['script-src'])
        self.assertEqual(csp['object-src'], ["'none'"])

    def test_halaman_sesi_ezviz(self):
        self._cek_izin_ezviz(self._csp(reverse('streaming:detail', kwargs={'pk': self.sesi_ezviz.pk})))

    def test_multi_view(self):
        self._cek_izin_ezviz(self._csp(reverse('streaming:grid')))

    def test_sesi_kamera_perangkat_tetap_kebijakan_dasar(self):
        csp = self._csp(reverse('streaming:detail', kwargs={'pk': self.sesi_perangkat.pk}))
        self.assertNotIn('wss:', csp['connect-src'])
        self.assertNotIn("'wasm-unsafe-eval'", csp['script-src'])

    def test_halaman_lain_tetap_kebijakan_dasar(self):
        csp = self._csp(reverse('streaming:list'))
        self.assertNotIn('wss:', csp['connect-src'])

    @override_settings(SECURE_CSP={}, SECURE_CSP_REPORT_ONLY=settings.SECURE_CSP)
    def test_izin_ezviz_ikut_di_mode_report_only(self):
        url = reverse('streaming:grid')
        self._cek_izin_ezviz(self._csp(url, 'Content-Security-Policy-Report-Only'))
        self.assertNotIn('Content-Security-Policy', self.client.get(url).headers)


class CspTemplateTest(SimpleTestCase):
    """
    CDN baru di template tanpa entri di SECURE_CSP tidak memunculkan error di
    server — hanya CSS/JS yang tidak termuat, dan alasannya cuma terlihat di
    console browser. Tes ini menangkapnya lebih dulu.
    """

    POLA_SCRIPT = re.compile(r'<script\b[^>]*\bsrc=["\'](https?://[^/"\']+)', re.I)
    POLA_LINK = re.compile(r'<link\b[^>]*>', re.I)
    POLA_HREF = re.compile(r'\bhref=["\'](https?://[^/"\']+)', re.I)

    def _template(self):
        for app in apps.get_app_configs():
            for berkas in (Path(app.path) / 'templates').rglob('*.html'):
                yield berkas, berkas.read_text(encoding='utf-8', errors='ignore')

    def test_semua_cdn_di_template_diizinkan_csp(self):
        script_src = _KEBIJAKAN['script-src']
        style_src = _KEBIJAKAN['style-src']
        salah = []
        for berkas, isi in self._template():
            for host in self.POLA_SCRIPT.findall(isi):
                if host not in script_src:
                    salah.append(f'{berkas}: <script src> {host} (script-src)')
            for tag in self.POLA_LINK.findall(isi):
                href = self.POLA_HREF.search(tag)
                if href and 'stylesheet' in tag.lower() and href.group(1) not in style_src:
                    salah.append(f'{berkas}: <link stylesheet> {href.group(1)} (style-src)')
        self.assertEqual(salah, [], 'Tambahkan host-nya ke _CSP_KEBIJAKAN di settings.py')


class GabungCspTest(TestCase):
    def test_direktif_baru_mewarisi_default_src(self):
        hasil = gabung_csp({'default-src': ["'self'"]}, {'worker-src': ['blob:']})
        self.assertEqual(hasil['worker-src'], ["'self'", 'blob:'])

    def test_tidak_menggandakan_dan_tidak_mengubah_dasar(self):
        dasar = {'default-src': ["'self'"], 'connect-src': ["'self'"]}
        hasil = gabung_csp(dasar, {'connect-src': ["'self'", 'wss:']})
        self.assertEqual(hasil['connect-src'], ["'self'", 'wss:'])
        self.assertEqual(dasar['connect-src'], ["'self'"])

    def test_direktif_tanpa_sumber_tidak_merusak(self):
        """Django menerima True untuk direktif seperti upgrade-insecure-requests."""
        hasil = gabung_csp(
            {'default-src': "'self'", 'upgrade-insecure-requests': True},
            {'connect-src': ['wss:']},
        )
        self.assertIs(hasil['upgrade-insecure-requests'], True)
        self.assertEqual(hasil['connect-src'], ["'self'", 'wss:'])


class PermissionsPolicyTest(TestCase):
    def test_halaman_login_membawa_permissions_policy(self):
        header = self.client.get(reverse('login')).headers['Permissions-Policy']
        fitur = dict(bagian.split('=', 1) for bagian in header.split(', '))
        # Live Streaming butuh kamera & mikrofon — jangan sampai ikut dimatikan.
        self.assertEqual(fitur['camera'], '(self)')
        self.assertEqual(fitur['microphone'], '(self)')
        self.assertEqual(fitur['geolocation'], '()')

    def test_susun(self):
        self.assertEqual(
            susun_permissions_policy({'camera': ['self'], 'usb': [], 'x': ['https://a.id']}),
            'camera=(self), usb=(), x=("https://a.id")',
        )
