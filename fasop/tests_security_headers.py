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
from django.contrib.staticfiles import finders
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from devices.models import UserProfile
from fasop.security_headers import gabung_csp, susun_permissions_policy
from fasop.settings import _CSP_KEBIJAKAN as _KEBIJAKAN
from streaming.models import KameraEzviz, LiveSession


POLA_CDN_PUBLIK = ('cdn.jsdelivr.net', 'unpkg.com', 'cdnjs.cloudflare.com')


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
        # Font disajikan sendiri (static/fonts/fasop-fonts.css), bukan dari Google.
        self.assertEqual(csp['font-src'], ["'self'", 'data:'])
        self.assertEqual(csp['style-src'], ["'self'", "'unsafe-inline'"])
        # Gambar hanya dari FASOP sendiri + tile peta, bukan https: mana saja.
        self.assertNotIn('https:', csp['img-src'])
        self.assertIn('https://*.basemaps.cartocdn.com', csp['img-src'])

    def test_tidak_ada_cdn_npm_publik(self):
        """
        jsdelivr/unpkg/cdnjs menyajikan paket npm APA SAJA. Mengizinkan host-nya
        berarti penyerang bisa memuat library lama bercelah dari host yang sama
        untuk melewati CSP. Library disimpan sendiri di static/vendor/.
        """
        header = self.client.get(reverse('login')).headers['Content-Security-Policy']
        for host in POLA_CDN_PUBLIK:
            self.assertNotIn(host, header)

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

    def test_rocket_loader_tidak_diizinkan_web_analytics_tetap(self):
        """
        Rocket Loader dimatikan di Cloudflare; host-nya tidak boleh kembali
        diam-diam. Web Analytics masih dipakai — kalau ikut terhapus, datanya
        berhenti masuk tanpa error di mana pun.
        """
        csp = _direktif(self.client.get(reverse('login')).headers['Content-Security-Policy'])
        self.assertNotIn('https://ajax.cloudflare.com', csp['script-src'])
        self.assertIn('https://static.cloudflareinsights.com', csp['script-src'])
        self.assertIn('https://cloudflareinsights.com', csp['connect-src'])

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
        self.assertIn('https:', csp['img-src'])
        # Perluasan, bukan pengganti.
        self.assertIn('https://static.cloudflareinsights.com', csp['script-src'])
        self.assertEqual(csp['object-src'], ["'none'"])

    def test_halaman_sesi_ezviz(self):
        self._cek_izin_ezviz(self._csp(reverse('streaming:detail', kwargs={'pk': self.sesi_ezviz.pk})))

    def test_multi_view(self):
        self._cek_izin_ezviz(self._csp(reverse('streaming:grid')))

    def test_sesi_kamera_perangkat_tetap_kebijakan_dasar(self):
        csp = self._csp(reverse('streaming:detail', kwargs={'pk': self.sesi_perangkat.pk}))
        self.assertNotIn('wss:', csp['connect-src'])
        self.assertNotIn("'wasm-unsafe-eval'", csp['script-src'])
        self.assertNotIn('https:', csp['img-src'])

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
    POLA_VENDOR = re.compile(r'\{%\s*static\s+["\'](vendor/[^"\']+)["\']')

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
        self.assertEqual(
            salah, [],
            'Simpan library-nya di static/vendor/ (lihat "Header Keamanan" di '
            'CLAUDE.md), jangan menambahkan CDN publik ke _CSP_KEBIJAKAN',
        )

    def test_berkas_vendor_yang_dirujuk_ada(self):
        """Salah ketik path vendor = CSS/JS hilang tanpa error di server."""
        hilang = []
        for berkas, isi in self._template():
            for path in self.POLA_VENDOR.findall(isi):
                if not finders.find(path):
                    hilang.append(f'{berkas}: {path}')
        self.assertEqual(hilang, [])

    def test_tidak_ada_google_fonts(self):
        """
        Termasuk <link rel="preconnect">, yang tidak tertangkap tes stylesheet
        di atas: koneksinya ditolak CSP tanpa pesan apa pun di layar.
        """
        pakai = [str(berkas) for berkas, isi in self._template()
                 if re.search(r'fonts\.(googleapis|gstatic)\.com', isi)]
        self.assertEqual(pakai, [], 'pakai static/fonts/fasop-fonts.css')

    def test_berkas_font_yang_dirujuk_ada(self):
        """
        url() di CSS font tidak diperiksa siapa pun: font yang salah path
        jatuh diam-diam ke font sistem, tanpa error di server maupun console.
        """
        css_path = finders.find('fonts/fasop-fonts.css')
        self.assertTrue(css_path)
        css = Path(css_path).read_text(encoding='utf-8')
        urls = re.findall(r"url\('\.\./([^']+)'\)", css)
        self.assertEqual(len(urls), 24)
        self.assertEqual([u for u in urls if not finders.find(u)], [])
        for keluarga in ('DM Sans', 'JetBrains Mono', 'Barlow', 'Barlow Condensed'):
            self.assertIn(f"font-family: '{keluarga}';", css)


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


class HeaderTambahanTest(TestCase):
    """X-Robots-Tag, Cross-Origin-Resource-Policy, X-Permitted-Cross-Domain-Policies."""

    def _cek(self, resp):
        self.assertEqual(resp.headers['X-Robots-Tag'], 'noindex, nofollow')
        self.assertEqual(resp.headers['Cross-Origin-Resource-Policy'], 'same-site')
        self.assertEqual(resp.headers['X-Permitted-Cross-Domain-Policies'], 'none')

    def test_halaman_html(self):
        self._cek(self.client.get(reverse('login')))

    def test_respons_non_html_ikut(self):
        """CORP justru paling berguna di foto/PDF/JSON, bukan di HTML."""
        resp = self.client.get(reverse('service_worker'))
        self.assertEqual(resp.status_code, 200)
        self._cek(resp)

    def test_halaman_publik_bertoken_tidak_diindeks(self):
        """Halaman peralatan lewat QR terbuka tanpa login — tautannya bisa tersebar."""
        from devices.models import Device, DeviceType
        device = Device.objects.create(
            nama='RTU-01', jenis=DeviceType.objects.create(name='RTU'),
            merk='SEL', lokasi='GI TELLO')
        resp = self.client.get(reverse('device_public', args=[device.public_token]))
        self.assertEqual(resp.status_code, 200)
        self._cek(resp)

    def test_header_dari_view_tidak_ditimpa(self):
        from django.http import HttpResponse
        from django.test import RequestFactory
        from fasop.security_headers import HeaderTambahanMiddleware

        def view(request):
            resp = HttpResponse('x')
            resp['Cross-Origin-Resource-Policy'] = 'cross-origin'
            return resp

        resp = HeaderTambahanMiddleware(view)(RequestFactory().get('/'))
        self.assertEqual(resp.headers['Cross-Origin-Resource-Policy'], 'cross-origin')
        self.assertEqual(resp.headers['X-Robots-Tag'], 'noindex, nofollow')

    def test_boleh_diindeks_hanya_melepas_x_robots_tag(self):
        from django.http import HttpResponse
        from django.test import RequestFactory
        from fasop.security_headers import HeaderTambahanMiddleware, boleh_diindeks

        resp = HeaderTambahanMiddleware(lambda r: boleh_diindeks(HttpResponse('x')))(
            RequestFactory().get('/'))
        self.assertNotIn('X-Robots-Tag', resp.headers)
        self.assertEqual(resp.headers['Cross-Origin-Resource-Policy'], 'same-site')

    def test_tanpa_coep(self):
        """require-corp memblokir tile peta Leaflet dan decoder Ezviz."""
        self.assertNotIn('Cross-Origin-Embedder-Policy', self.client.get(reverse('login')).headers)


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
