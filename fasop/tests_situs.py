"""
Berkas verifikasi Google Search Console (fasop/situs_views.py).

Yang paling penting dijaga di sini bukan bahwa berkas kita terjawab, tapi bahwa
berkas ORANG LAIN tidak: menjawab sembarang googleXXXX.html sama dengan
mengizinkan siapa saja mendaftar sebagai pemilik fasopup2bmks.id di Google.
"""
from django.test import TestCase, override_settings

NAMA = 'google1a2b3c4d5e6f7a8b.html'


@override_settings(GOOGLE_SITE_VERIFICATION=[NAMA])
class GoogleVerifikasiTest(TestCase):
    def test_berkas_terdaftar_dijawab_persis(self):
        resp = self.client.get('/' + NAMA)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode(), f'google-site-verification: {NAMA}')

    def test_berkas_lain_ditolak(self):
        self.assertEqual(self.client.get('/google9999999999999999.html').status_code, 404)

    def test_tanpa_login(self):
        """Googlebot tidak login — berkasnya tidak boleh dipantulkan ke /login/."""
        resp = self.client.get('/' + NAMA)
        self.assertNotIn('Location', resp.headers)

    @override_settings(GOOGLE_SITE_VERIFICATION=[])
    def test_kosong_semua_ditolak(self):
        self.assertEqual(self.client.get('/' + NAMA).status_code, 404)

    @override_settings(GOOGLE_SITE_VERIFICATION=[NAMA, 'googleffff0000ffff0000.html'])
    def test_lebih_dari_satu_pemilik(self):
        self.assertEqual(self.client.get('/googleffff0000ffff0000.html').status_code, 200)
