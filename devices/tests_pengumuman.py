"""
Tes pop-up Pengumuman Pemeliharaan (rencana restart server).

Yang dijaga di sini adalah hal-hal yang gejalanya diam: pop-up yang tidak bisa
ditutup oleh role terbatas, pengumuman yang diubah tapi tidak muncul lagi, dan
partial yang lupa di-include di salah satu dari empat template dasar FASOP.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import PengumumanPemeliharaan, UserProfile


def _bersihkan_cache():
    PengumumanPemeliharaan._cache = {'obj': None, 'ts': 0.0}


class PengumumanModelTest(TestCase):
    def setUp(self):
        _bersihkan_cache()

    def test_baris_selalu_tunggal(self):
        a = PengumumanPemeliharaan.ambil()
        b = PengumumanPemeliharaan.ambil()
        self.assertEqual(a.pk, 1)
        self.assertEqual(b.pk, 1)
        self.assertEqual(PengumumanPemeliharaan.objects.count(), 1)

    def test_nonaktif_tidak_tampil(self):
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = False
        obj.save()
        self.assertFalse(obj.sedang_tampil())

    def test_aktif_tampil(self):
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = True
        obj.save()
        self.assertTrue(obj.sedang_tampil())

    def test_berhenti_otomatis_setelah_selesai_lewat(self):
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = True
        obj.berhenti_otomatis = True
        obj.selesai = timezone.now() - timedelta(hours=1)
        obj.save()
        self.assertFalse(obj.sedang_tampil())

    def test_tanpa_berhenti_otomatis_tetap_tampil(self):
        """Pengumuman yang harus tampil sampai dimatikan manual."""
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = True
        obj.berhenti_otomatis = False
        obj.selesai = timezone.now() - timedelta(hours=1)
        obj.save()
        self.assertTrue(obj.sedang_tampil())

    def test_selesai_kosong_tidak_pernah_berhenti_sendiri(self):
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = True
        obj.berhenti_otomatis = True
        obj.selesai = None
        obj.save()
        self.assertTrue(obj.sedang_tampil())

    def test_versi_berubah_setiap_disimpan(self):
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = True
        obj.save()
        v1 = obj.versi
        obj.diubah_pada = timezone.now() + timedelta(seconds=5)
        PengumumanPemeliharaan.objects.filter(pk=1).update(diubah_pada=obj.diubah_pada)
        _bersihkan_cache()
        self.assertNotEqual(PengumumanPemeliharaan.ambil().versi, v1)

    def test_save_menyegarkan_cache_worker_ini(self):
        """Perubahan dari admin harus langsung terlihat di worker yang menyimpan."""
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = False
        obj.save()
        self.assertFalse(PengumumanPemeliharaan.status().aktif)
        obj.aktif = True
        obj.save()
        self.assertTrue(PengumumanPemeliharaan.status().aktif)


class PengumumanTampilTest(TestCase):
    def setUp(self):
        _bersihkan_cache()
        self.user = User.objects.create_user('teknisi1', password='rahasia123')
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={'role': 'technician', 'force_password_change': False})
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = True
        obj.judul = 'Rencana Restart Server'
        obj.pesan = 'Server direstart Sabtu 22.00.'
        obj.save()

    def test_muncul_setelah_login(self):
        self.client.force_login(self.user)
        resp = self.client.get('/')
        self.assertContains(resp, 'Rencana Restart Server')
        self.assertContains(resp, 'Server direstart Sabtu 22.00.')

    def test_tidak_muncul_untuk_anonim(self):
        """Pop-up di halaman login hanya menghalangi orang masuk."""
        resp = self.client.get('/login/')
        self.assertNotContains(resp, 'Rencana Restart Server')

    def test_tidak_muncul_lagi_setelah_ditutup(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/'), 'Rencana Restart Server')
        self.client.post(reverse('pengumuman_tutup'))
        self.assertNotContains(self.client.get('/'), 'Rencana Restart Server')

    def test_muncul_lagi_setelah_pengumuman_diubah(self):
        """Jadwal yang digeser harus terbaca ulang, juga di sesi yang sama."""
        self.client.force_login(self.user)
        self.client.post(reverse('pengumuman_tutup'))
        self.assertNotContains(self.client.get('/'), 'Rencana Restart Server')

        obj = PengumumanPemeliharaan.ambil()
        obj.pesan = 'Jadwal digeser ke Minggu 22.00.'
        obj.save()
        _bersihkan_cache()
        self.assertContains(self.client.get('/'), 'Jadwal digeser ke Minggu 22.00.')

    def test_login_baru_melihatnya_lagi(self):
        """Sesi baru = sesi bersih; pengumuman muncul lagi seperti saat login."""
        self.client.force_login(self.user)
        self.client.post(reverse('pengumuman_tutup'))
        self.client.logout()
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/'), 'Rencana Restart Server')

    def test_nonaktif_tidak_digambar(self):
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = False
        obj.save()
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get('/'), 'Rencana Restart Server')

    def test_tutup_menolak_get(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('pengumuman_tutup')).status_code, 405)

    def test_tutup_butuh_login(self):
        resp = self.client.post(reverse('pengumuman_tutup'))
        self.assertEqual(resp.status_code, 302)


class PengumumanRoleTerbatasTest(TestCase):
    """
    Role yang dibatasi middleware harus tetap bisa MENUTUP pop-up-nya.

    Kalau endpoint penutup ikut dipantulkan ke dashboard masing-masing, pop-up
    muncul lagi di setiap halaman — dan karena fetch() mengikuti redirect, JS
    di halaman menyangka penutupan itu berhasil.
    """

    def setUp(self):
        _bersihkan_cache()
        obj = PengumumanPemeliharaan.ambil()
        obj.aktif = True
        obj.save()

    def _user(self, nama, role):
        u = User.objects.create_user(nama, password='rahasia123')
        UserProfile.objects.update_or_create(
            user=u, defaults={'role': role, 'force_password_change': False})
        return u

    def test_semua_role_terbatas_bisa_menutup(self):
        for role in ('opsis', 'opsis_view', 'operator', 'up2d', 'dispatcher', 'vendor'):
            with self.subTest(role=role):
                _bersihkan_cache()
                u = self._user(f'u_{role}', role)
                self.client.force_login(u)
                resp = self.client.post(reverse('pengumuman_tutup'))
                self.assertEqual(resp.status_code, 200, f'role {role} dipantulkan')
                self.assertTrue(resp.json()['ok'])
                self.assertEqual(
                    self.client.session[PengumumanPemeliharaan.SESSION_KEY],
                    PengumumanPemeliharaan.ambil().versi)
                self.client.logout()


class PengumumanPartialTerpasangTest(TestCase):
    """
    Keempat template dasar FASOP harus meng-include partial-nya.

    Yang lupa di-include tidak menghasilkan error apa pun — pengumumannya cuma
    tidak pernah sampai ke pengguna yang halaman pertamanya kebetulan di sana.
    """

    BASE = (
        'devices/templates/base.html',
        'opsis/templates/opsis/opsis_base.html',
        'device_mon/templates/device_mon/base.html',
        'up2bmakassar/templates/up2bmakassar/base.html',
    )

    def test_semua_base_meng_include_partial(self):
        import pathlib
        akar = pathlib.Path(__file__).resolve().parent.parent
        for f in self.BASE:
            with self.subTest(base=f):
                isi = (akar / f).read_text(encoding='utf-8')
                self.assertIn('devices/_pengumuman_modal.html', isi)


class PengumumanContextProcessorTest(TestCase):
    def setUp(self):
        _bersihkan_cache()

    def test_tabel_bermasalah_tidak_menjatuhkan_halaman(self):
        from unittest.mock import patch
        from devices.context_processors import pengumuman_pemeliharaan

        with patch.object(PengumumanPemeliharaan, 'untuk',
                          side_effect=Exception('DB mati')):
            self.assertEqual(pengumuman_pemeliharaan(None), {'pengumuman': None})
