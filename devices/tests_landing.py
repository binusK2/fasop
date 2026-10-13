"""
Landing page "/" untuk pengunjung yang belum login (devices.views.beranda).

Yang dijaga: pengguna yang sudah login tidak boleh merasakan perubahan apa pun
(dashboard & pengalihan per peran tetap), halaman publik ini tidak menembak
database untuk tiap pengunjung, dan ia tetap lolos CSP tanpa 'unsafe-inline'.
"""
import re
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from devices.models import PengumumanPemeliharaan, UserProfile

TEMPLATE = 'devices/landing.html'


def _bersihkan_cache():
    PengumumanPemeliharaan._cache = {'obj': None, 'ts': 0.0}


def _user(username, role):
    user = User.objects.create_user(username, password='Rahasia-123')
    UserProfile.objects.update_or_create(
        user=user, defaults={'role': role, 'force_password_change': False})
    return user


class LandingAnonimTest(TestCase):
    def setUp(self):
        _bersihkan_cache()

    def tearDown(self):
        _bersihkan_cache()

    def test_anonim_mendapat_landing(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, TEMPLATE)
        self.assertContains(resp, f'href="{reverse("login")}"')

    def test_tidak_diindeks_mesin_pencari(self):
        """Sistem internal: tidak perlu ditemukan lewat Google."""
        self.assertContains(self.client.get('/'), 'name="robots" content="noindex, nofollow"')

    def test_tanpa_query_selain_pengumuman(self):
        """
        Context processor tidak boleh ikut jalan untuk tiap pengunjung anonim
        dan bot. Ini juga yang menjamin tidak ada data operasional dari database
        yang ikut tergambar di halaman publik ini.
        """
        PengumumanPemeliharaan.ambil()
        _bersihkan_cache()
        with CaptureQueriesContext(connection) as q:
            self.client.get('/')
        self.assertLessEqual(len(q), 1, [x['sql'] for x in q])

    def test_halaman_lolos_csp_tanpa_unsafe_inline(self):
        html = self.client.get('/').content.decode()
        self.assertEqual(re.findall(r'<script(?![^>]*\bsrc=)[^>]*>', html), [], 'skrip inline')
        self.assertEqual(re.findall(r'\son[a-z]+\s*=', html), [], 'handler on*=')
        self.assertEqual(re.findall(r'\sstyle\s*=', html), [], 'atribut style=')
        self.assertNotIn('javascript:', html)

    def test_sumber_luar_hanya_google_fonts(self):
        html = self.client.get('/').content.decode()
        luar = set()
        for tag in re.findall(r'<(?:script|link|img)\b[^>]*>', html):
            m = re.search(r'\b(?:src|href)="(https?://[^/"]+)', tag)
            if m:
                luar.add(m.group(1))
        self.assertLessEqual(luar, {'https://fonts.googleapis.com', 'https://fonts.gstatic.com'})

    def test_berkas_statis_yang_dirujuk_ada(self):
        """Path static yang salah ketik = halaman depan tanpa gaya, tanpa error di server."""
        isi = (Path(__file__).parent / 'templates' / TEMPLATE).read_text(encoding='utf-8')
        paths = re.findall(r"\{%\s*static\s+'([^']+)'\s*%\}", isi)
        self.assertTrue(paths)
        self.assertEqual([p for p in paths if not finders.find(p)], [])

    @override_settings(HELPDESK_WA='')
    def test_nomor_wa_kosong_menyembunyikan_tombol(self):
        resp = self.client.get('/')
        self.assertNotContains(resp, 'wa.me')
        self.assertContains(resp, 'Hubungi admin FASOP di unit Anda')

    @override_settings(HELPDESK_WA='+62 812-3456-7890')
    def test_nomor_wa_dibersihkan(self):
        self.assertContains(self.client.get('/'), 'https://wa.me/6281234567890?text=')


class LandingPengumumanTest(TestCase):
    """Banner di landing memakai aturan tampil yang sama dengan pop-up setelah login."""

    def setUp(self):
        _bersihkan_cache()
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = True
        obj.judul = 'Rencana Restart Server'
        obj.pesan = 'Server direstart Sabtu 22.00.'
        obj.tingkat = 'penting'
        obj.save()
        _bersihkan_cache()

    def tearDown(self):
        _bersihkan_cache()

    def test_aktif_tampil_sebelum_login(self):
        resp = self.client.get('/')
        self.assertContains(resp, 'Rencana Restart Server')
        self.assertContains(resp, 'Server direstart Sabtu 22.00.')
        self.assertContains(resp, 'notice t-penting')

    def test_nonaktif_tidak_tampil(self):
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = False
        obj.save()
        _bersihkan_cache()
        self.assertNotContains(self.client.get('/'), 'Rencana Restart Server')

    def test_berhenti_otomatis_setelah_jadwal_lewat(self):
        obj = PengumumanPemeliharaan.ambil()
        obj.berhenti_otomatis = True
        obj.selesai = timezone.now() - timedelta(hours=1)
        obj.save()
        _bersihkan_cache()
        self.assertNotContains(self.client.get('/'), 'Rencana Restart Server')

    def test_jadwal_ditulis_dalam_bahasa_indonesia(self):
        from datetime import datetime
        obj = PengumumanPemeliharaan.ambil()
        obj.mulai = timezone.make_aware(datetime(2026, 10, 17, 22, 0))
        obj.save()
        _bersihkan_cache()
        resp = self.client.get('/')
        self.assertContains(resp, '17 Okt 2026, 22:00')
        self.assertNotContains(resp, 'Oct')

    def test_isi_pengumuman_di_escape(self):
        """Halaman publik: teks dari admin tetap diperlakukan sebagai teks."""
        obj = PengumumanPemeliharaan.ambil()
        obj.pesan = '<script>alert(1)</script>'
        obj.save()
        _bersihkan_cache()
        resp = self.client.get('/')
        self.assertNotContains(resp, '<script>alert(1)</script>', html=False)
        self.assertContains(resp, '&lt;script&gt;alert(1)&lt;/script&gt;')


class LandingSudahLoginTest(TestCase):
    """Bagi yang sudah login, "/" harus berperilaku persis seperti sebelumnya."""

    def test_teknisi_tetap_ke_dashboard(self):
        self.client.force_login(_user('teknisi1', 'technician'))
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateNotUsed(resp, TEMPLATE)

    def test_operator_tetap_ke_dashboard_operator(self):
        """Operator boleh membuka "/" (ALLOWED_EXACT) dan dashboard() mem-fork-nya."""
        self.client.force_login(_user('operator1', 'operator'))
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'devices/dashboard_operator.html')
        self.assertTemplateNotUsed(resp, TEMPLATE)

    def test_opsis_tetap_dialihkan_middleware(self):
        self.client.force_login(_user('opsis1', 'opsis'))
        resp = self.client.get('/')
        self.assertRedirects(resp, '/opsis/', fetch_redirect_response=False)

    def test_nama_url_dashboard_tetap(self):
        self.assertEqual(reverse('dashboard'), '/')
