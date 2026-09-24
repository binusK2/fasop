"""Temuan pemindaian Wapiti (24 Sep 2026) terhadap halaman login.

1. POST /login/ dengan username ribuan karakter → HTTP 500. django-axes
   mencatat percobaan gagal ke ``AccessAttempt.username`` (varchar 255) tanpa
   memotongnya, dan PostgreSQL menolak nilai yang terlalu panjang
   (SQLite tidak, jadi tes ini baru bermakna dijalankan di PostgreSQL).
2. Halaman lockout axes tidak membawa X-Frame-Options: AxesMiddleware
   mengganti response SETELAH XFrameOptionsMiddleware memasang header-nya.
"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


class LoginUsernamePanjangTest(TestCase):
    def _post(self, username):
        return self.client.post(reverse('login'), {'username': username, 'password': 'salah'})

    def test_username_sangat_panjang_tidak_500(self):
        resp = self._post('x' * 4400)
        self.assertEqual(resp.status_code, 200)

    def test_username_panjang_tetap_tercatat_dan_bisa_dikunci(self):
        from axes.models import AccessAttempt
        for _ in range(5):
            self._post('y' * 1000)
        attempt = AccessAttempt.objects.get()
        self.assertEqual(len(attempt.username), 255)
        self.assertEqual(attempt.failures_since_start, 5)

    def test_username_normal_tidak_berubah(self):
        from axes.models import AccessAttempt
        self._post('alice')
        self.assertEqual(AccessAttempt.objects.get().username, 'alice')

    def test_login_berhasil_tetap_jalan(self):
        User.objects.create_user('budi', password='Rahasia-123')
        resp = self.client.post(reverse('login'), {'username': 'budi', 'password': 'Rahasia-123'})
        self.assertEqual(resp.status_code, 302)


class LockoutXFrameOptionsTest(TestCase):
    @override_settings(AXES_FAILURE_LIMIT=2)
    def test_halaman_lockout_membawa_x_frame_options(self):
        for _ in range(3):
            resp = self.client.post(reverse('login'), {'username': 'alice', 'password': 'salah'})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.headers.get('X-Frame-Options'), 'DENY')

    def test_halaman_login_membawa_x_frame_options(self):
        resp = self.client.get(reverse('login'))
        self.assertEqual(resp.headers.get('X-Frame-Options'), 'DENY')
