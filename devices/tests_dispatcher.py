"""
Tes akses role Dispatcher: Pengujian Telekomunikasi + OPSIS + Device Monitoring.

Yang dijaga di sini adalah kesepakatan antara menu dan
DispatcherAccessMiddleware. Begitu keduanya berbeda pendapat, gejalanya diam:
menu tampil, diklik, lalu memantul balik ke Pengujian Telekomunikasi tanpa
pesan apa pun — persis yang dulu dialami role UP2D (lihat SidebarUp2dTest di
opsis/tests.py).
"""

import re

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from devices.middleware import DispatcherAccessMiddleware


class DispatcherAksesTest(TestCase):

    def _user(self, role='dispatcher'):
        nama = f'tes-{role}'
        u = User.objects.create_user(nama, f'{nama}@contoh.id', 'rahasia-tes-123')
        profil = u.profile
        profil.role = role
        profil.force_password_change = False
        profil.save()
        self.client.force_login(u)
        return u

    def _isi(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, f'{url} -> {r.status_code}')
        return r.content.decode()

    def _lolos_middleware(self, user, path):
        """True kalau DispatcherAccessMiddleware meneruskan path ke view-nya."""
        req = RequestFactory().get(path)
        req.user = user
        resp = DispatcherAccessMiddleware(lambda r: HttpResponse('ok'))(req)
        return resp.status_code == 200

    # ── Menu FASOP ────────────────────────────────────────────────────
    def test_menu_opsis_dan_device_mon_di_bawah_pengujian_telekomunikasi(self):
        self._user()
        isi = self._isi(reverse('pengujian_telecom_dashboard'))
        pos_uji = isi.find(f'href="{reverse("pengujian_telecom_dashboard")}"')
        pos_opsis = isi.find(f'href="{reverse("opsis_dashboard")}"')
        pos_dm = isi.find(f'href="{reverse("dm_dashboard")}"')
        self.assertNotEqual(pos_uji, -1, 'menu Pengujian Telekomunikasi hilang')
        self.assertNotEqual(pos_opsis, -1, 'menu OPSIS hilang')
        self.assertNotEqual(pos_dm, -1, 'menu Device Monitoring hilang')
        self.assertLess(pos_uji, pos_opsis)
        self.assertLess(pos_opsis, pos_dm)

    def test_menu_monitoring_lain_tidak_bocor_ke_dispatcher(self):
        """Kinerja Scadatel & Live Streaming tidak diizinkan middleware."""
        self._user()
        isi = self._isi(reverse('pengujian_telecom_dashboard'))
        self.assertNotIn(f'href="{reverse("up2b_dashboard")}"', isi)
        self.assertNotIn(f'href="{reverse("streaming:list")}"', isi)
        self.assertNotIn('data-target="submenu-status-peralatan"', isi)

    # ── Halaman yang dibuka dari menu itu harus benar-benar terbuka ────
    def test_halaman_opsis_dan_device_mon_terbuka(self):
        self._user()
        for url in (reverse('opsis_dashboard'), reverse('dm_dashboard')):
            self._isi(url)

    def test_api_yang_dipoll_halamannya_ikut_terbuka(self):
        u = self._user()
        for path in ('/opsis/api/live/', '/opsis/api/hz/', '/opsis/api/ews/',
                     '/device-mon/api/status/', '/device-mon/zabbix/telkom/api/summary/'):
            self.assertTrue(self._lolos_middleware(u, path), f'{path} dipantulkan')

    def test_semua_tautan_di_opsis_dan_device_mon_lolos_middleware(self):
        """
        Sidebar OPSIS & Device Monitoring punya menunya sendiri. Setiap tautan
        di sana harus lolos middleware, kecuali "Beranda" ('/') yang memang
        mengantar Dispatcher pulang ke Pengujian Telekomunikasi.
        """
        u = self._user()
        for halaman in (reverse('opsis_dashboard'), reverse('dm_dashboard')):
            isi = self._isi(halaman)
            tautan = set(re.findall(r'href="(/[^"]*)"', isi)) - {'/'}
            tautan = {t for t in tautan if not t.startswith('/static/')}
            self.assertTrue(tautan, f'tidak ada tautan terbaca di {halaman}')
            for t in sorted(tautan):
                self.assertTrue(self._lolos_middleware(u, t),
                                f'{t} (dari {halaman}) dipantulkan middleware')

    # ── OPSIS tetap lihat-saja ────────────────────────────────────────
    def test_menu_opsis_terbatas_tidak_tampil(self):
        """Logsheet/Respons/Input HOP/Config Inersia dijaga properti UserProfile."""
        self._user()
        isi = self._isi(reverse('opsis_dashboard'))
        for jalur in ('/opsis/logsheet/', '/opsis/respon/',
                      '/opsis/hop/input/', '/opsis/inersia/config/'):
            self.assertNotIn(f'href="{jalur}"', isi, f'{jalur} bocor ke menu Dispatcher')

    def test_tidak_bisa_menulis_di_opsis(self):
        self._user()
        r = self.client.get('/opsis/inersia/config/')
        self.assertRedirects(r, reverse('opsis_dashboard'), fetch_redirect_response=False)
        r = self.client.post('/opsis/ews/simpan/', '{}', content_type='application/json')
        self.assertEqual(r.status_code, 403)

    # ── Halaman lain tetap tertutup ───────────────────────────────────
    def test_halaman_lain_tetap_memantul(self):
        self._user()
        tujuan = reverse('pengujian_telecom_dashboard')
        for jalur in ('/', '/maintenance/', '/kinerja-scadatel/', '/streaming/',
                      '/inspection/dashboard/'):
            r = self.client.get(jalur)
            self.assertEqual(r.status_code, 302, jalur)
            self.assertEqual(r['Location'], tujuan, jalur)

    def test_role_operator_tidak_ikut_terbuka(self):
        self._user('operator')
        r = self.client.get(reverse('opsis_dashboard'))
        self.assertRedirects(r, reverse('inspection_lokasi'), fetch_redirect_response=False)
