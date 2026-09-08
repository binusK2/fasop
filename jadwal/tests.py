"""Tes daftar peralatan di Jadwal Pemeliharaan.

Halaman ini adalah titik masuk pemeliharaan bagi teknisi yang sedang
mengerjakan satu lokasi. Dua hal yang gampang rusak diam-diam: tombol aksi
per peralatan, dan ke mana pengguna dikembalikan setelah membuka form
pemeliharaan dari sini.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile
from maintenance.models import Maintenance

from .models import JadwalKunjungan


class JadwalAksiPeralatanTests(TestCase):
    """Tombol Catat / Edit / Tandai Selesai per peralatan."""

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_jadwal', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        self.jenis = DeviceType.objects.create(name='RTU')
        self.device = Device.objects.create(nama='RTU-01', jenis=self.jenis,
                                            merk='SEL', lokasi='GI TELLO')
        self.jadwal = JadwalKunjungan.objects.create(
            lokasi='GI TELLO', bulan_rencana=9, tahun_rencana=2026)
        self.url_detail = reverse('jadwal_detail', args=[self.jadwal.pk])

    def _maintenance(self, status='Open'):
        return Maintenance.objects.create(
            device=self.device, maintenance_type='Preventive',
            date=timezone.make_aware(timezone.datetime(2026, 9, 5, 8, 0)),
            status=status, description='uji')

    def test_tiga_tombol_tampil(self):
        resp = self.client.get(self.url_detail)
        self.assertEqual(resp.status_code, 200)
        isi = resp.content.decode()
        self.assertIn('Catat', isi)
        self.assertIn('Edit', isi)
        self.assertIn('Tandai Selesai', isi)

    def test_halaman_memakai_nama_jadwal_pemeliharaan(self):
        """Judul & label kartu, bukan 'Jadwal Kunjungan' seperti dulu."""
        resp = self.client.get(self.url_detail)
        self.assertContains(resp, 'Jadwal Pemeliharaan')
        self.assertNotContains(resp, 'Jadwal Kunjungan')

    def test_tombol_catat_membawa_alamat_kembali(self):
        """Tanpa ?dari=, tombol Kembali di form pulang ke detail perangkat."""
        resp = self.client.get(self.url_detail)
        self.assertContains(
            resp, reverse('maintenance_add_device', args=[self.device.pk]) + '?dari=')

    def test_tombol_edit_menunjuk_pemeliharaan_periode_ini(self):
        m = self._maintenance(status='Open')
        resp = self.client.get(self.url_detail)
        self.assertContains(resp, reverse('maintenance_edit', args=[m.pk]))

    def test_edit_terkunci_setelah_selesai(self):
        """Done = terkunci, aturan yang sama dengan halaman detail pemeliharaan.

        Kalau tautannya tetap dipasang, penggunanya cuma dipantulkan balik
        oleh view-nya.
        """
        m = self._maintenance(status='Done')
        resp = self.client.get(self.url_detail)
        self.assertNotContains(resp, reverse('maintenance_edit', args=[m.pk]))

    def test_edit_terkunci_setelah_ditandatangani(self):
        m = self._maintenance(status='Open')
        m.signed_by = self.user
        m.save(update_fields=['signed_by'])
        resp = self.client.get(self.url_detail)
        self.assertNotContains(resp, reverse('maintenance_edit', args=[m.pk]))

    def test_tandai_selesai_membuat_pemeliharaan_bila_belum_ada(self):
        resp = self.client.post(
            reverse('jadwal_device_done', args=[self.jadwal.pk, self.device.pk]))
        self.assertRedirects(resp, self.url_detail)

        m = Maintenance.objects.get(device=self.device)
        self.assertEqual(m.status, 'Done')
        self.assertEqual(m.maintenance_type, 'Preventive')

        # Jatuh di periode jadwal, bukan tanggal hari ini. Dibandingkan dalam
        # waktu LOKAL: tersimpan UTC, dan 1 September 00:00 WITA = 31 Agustus
        # 16:00 UTC — sedangkan lookup __month milik Django juga memakai waktu
        # lokal, jadi waktu lokal itulah yang menentukan periodenya.
        lokal = timezone.localtime(m.date)
        self.assertEqual((lokal.year, lokal.month), (2026, 9))

        # Yang sebenarnya penting: jadwalnya menghitungnya sebagai selesai
        self.assertEqual(self.jadwal.get_progress()['selesai'], 1)

    def test_tandai_selesai_menutup_pemeliharaan_yang_masih_open(self):
        m = self._maintenance(status='Open')
        self.client.post(
            reverse('jadwal_device_done', args=[self.jadwal.pk, self.device.pk]))
        m.refresh_from_db()
        self.assertEqual(m.status, 'Done')
        self.assertEqual(Maintenance.objects.count(), 1)   # bukan baris kedua

    def test_tandai_selesai_menolak_peralatan_luar_jadwal(self):
        """device_id apa pun tidak boleh bisa dititipkan ke endpoint ini."""
        lain = Device.objects.create(nama='RTU-99', jenis=self.jenis,
                                     merk='SEL', lokasi='GI LAIN')
        resp = self.client.post(
            reverse('jadwal_device_done', args=[self.jadwal.pk, lain.pk]))
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(Maintenance.objects.filter(device=lain).exists())

    def test_tandai_selesai_hanya_lewat_post(self):
        self.client.get(reverse('jadwal_device_done', args=[self.jadwal.pk, self.device.pk]))
        self.assertFalse(Maintenance.objects.exists())


class TombolKembaliFormPemeliharaanTests(TestCase):
    """Form pemeliharaan harus pulang ke tempat penggunanya datang.

    Dibuka dari Jadwal Pemeliharaan -> kembali ke daftar peralatan jadwal itu;
    dibuka dari detail perangkat (tanpa ?dari=) -> tetap ke detail perangkat.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(username='tek_jadwal', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'technician'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        jenis = DeviceType.objects.create(name='RTU')
        self.device = Device.objects.create(nama='RTU-01', jenis=jenis,
                                            merk='SEL', lokasi='GI TELLO')
        self.jadwal = JadwalKunjungan.objects.create(
            lokasi='GI TELLO', bulan_rencana=9, tahun_rencana=2026)
        self.url_jadwal = reverse('jadwal_detail', args=[self.jadwal.pk])
        self.url_form = reverse('maintenance_add_device', args=[self.device.pk])

    def test_kembali_ke_jadwal_saat_dibuka_dari_jadwal(self):
        resp = self.client.get(self.url_form, {'dari': self.url_jadwal})
        self.assertEqual(resp.context['kembali_url'], self.url_jadwal)
        self.assertEqual(resp.context['kembali_label'], 'Kembali ke Jadwal')
        self.assertContains(resp, self.url_jadwal)

    def test_kembali_ke_perangkat_saat_dibuka_langsung(self):
        resp = self.client.get(self.url_form)
        self.assertEqual(resp.context['kembali_url'],
                         reverse('device_view', args=[self.device.pk]))
        self.assertEqual(resp.context['kembali_label'], 'Kembali ke Perangkat')

    def test_alamat_luar_diabaikan(self):
        """?dari= datang dari URL - kalau tidak divalidasi, jadi open redirect."""
        resp = self.client.get(self.url_form, {'dari': 'https://situs-lain.example/x'})
        self.assertEqual(resp.context['kembali_url'],
                         reverse('device_view', args=[self.device.pk]))

    def test_asal_ikut_terkirim_di_form(self):
        """Hidden field-nya wajib ada: action= form edit membuang querystring."""
        resp = self.client.get(self.url_form, {'dari': self.url_jadwal})
        self.assertContains(resp, 'name="dari" value="%s"' % self.url_jadwal)

    def test_setelah_simpan_kembali_ke_jadwal(self):
        data = {
            'maintenance_type': 'Preventive',
            'date': '2026-09-05T08:00',
            'description': 'uji dari jadwal',
            'status': 'Open',
            'pelaksana_names': '["Budi"]',
            'dari': self.url_jadwal,
        }
        resp = self.client.post(self.url_form, data)
        self.assertRedirects(resp, self.url_jadwal)
        self.assertTrue(Maintenance.objects.filter(device=self.device).exists())

    def test_setelah_simpan_tanpa_asal_tetap_ke_daftar(self):
        data = {
            'maintenance_type': 'Preventive',
            'date': '2026-09-05T08:00',
            'description': 'uji tanpa asal',
            'status': 'Open',
            'pelaksana_names': '["Budi"]',
        }
        resp = self.client.post(self.url_form, data)
        self.assertRedirects(resp, reverse('maintenance_list'))

class EditTerkunciSetelahSelesaiTests(TestCase):
    """View edit menolak pemeliharaan yang sudah selesai / ditandatangani.

    Aturannya dulu hanya berupa tombol yang disembunyikan di template detail,
    jadi setiap tautan baru ke halaman edit — seperti tombol Edit di Jadwal
    Pemeliharaan — otomatis melewatinya, termasuk POST-nya.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_kunci', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        jenis = DeviceType.objects.create(name='RTU')
        self.device = Device.objects.create(nama='RTU-01', jenis=jenis,
                                            merk='SEL', lokasi='GI TELLO')
        self.m = Maintenance.objects.create(
            device=self.device, maintenance_type='Preventive',
            date=timezone.make_aware(timezone.datetime(2026, 9, 5, 8, 0)),
            status='Open', description='asli')
        self.url_edit = reverse('maintenance_edit', args=[self.m.pk])
        self.url_view = reverse('maintenance_view', args=[self.m.pk])

    def test_masih_bisa_diedit_selama_open(self):
        self.assertEqual(self.client.get(self.url_edit).status_code, 200)

    def test_ditolak_setelah_selesai(self):
        self.m.status = 'Done'
        self.m.save(update_fields=['status'])
        self.assertRedirects(self.client.get(self.url_edit), self.url_view)

    def test_post_ikut_ditolak_setelah_selesai(self):
        """Penjagaan hanya di GET tidak ada gunanya — POST yang mengubah data."""
        self.m.status = 'Done'
        self.m.save(update_fields=['status'])
        resp = self.client.post(self.url_edit, {
            'maintenance_type': 'Preventive',
            'date': '2026-09-05T08:00',
            'description': 'DIUBAH DIAM-DIAM',
            'status': 'Done',
            'pelaksana_names': '[]',
        })
        self.assertRedirects(resp, self.url_view)
        self.m.refresh_from_db()
        self.assertEqual(self.m.description, 'asli')

    def test_ditolak_setelah_ditandatangani(self):
        self.m.signed_by = self.user
        self.m.save(update_fields=['signed_by'])
        self.assertRedirects(self.client.get(self.url_edit), self.url_view)

