"""Pelaksana wajib diisi di form pemeliharaan (preventive & corrective).

Kolom Pelaksana adalah kotak tag yang mengirim namanya lewat input
tersembunyi, jadi atribut `required` HTML tidak bisa dipakai. Penjaganya ada
dua: JS di `_pelaksana_tag_widget.html` (menahan form di browser + pesan di
atas kolom), dan validasi server di sini — yang menangkap form yang lolos
tanpa JS, dan yang tes-tes di bawah jaga.
"""
import re

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile

from .forms import PESAN_PELAKSANA_WAJIB, bersihkan_pelaksana
from .models import Maintenance, MaintenanceCorrective


def _pesan_tampil(resp):
    """Pesan error pelaksana benar-benar terlihat (bukan div tersembunyi)."""
    html = resp.content.decode()
    m = re.search(r'<div id="pelaksana-error"[^>]*style="display:(\w+)', html)
    return bool(m) and m.group(1) == 'flex'


class BersihkanPelaksanaTests(SimpleTestCase):

    def test_json_array(self):
        self.assertEqual(bersihkan_pelaksana('["Budi", "Andi"]'), ['Budi', 'Andi'])

    def test_dipisah_koma_bentuk_lama_corrective(self):
        self.assertEqual(bersihkan_pelaksana('Budi, Andi'), ['Budi', 'Andi'])

    def test_kosong_spasi_dan_kembar_dibuang(self):
        self.assertEqual(bersihkan_pelaksana(['  Budi ', '', '   ', 'Budi']), ['Budi'])

    def test_yang_bukan_daftar_nama_jadi_kosong(self):
        for nilai in (None, '', '[]', '[  ', {'a': 1}, [1, None], '["  "]'):
            with self.subTest(nilai=nilai):
                self.assertEqual(bersihkan_pelaksana(nilai), [])


class _Dasar(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_pel', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        # Jenis tanpa form detail — yang diuji hanya bagian umum form-nya
        jenis = DeviceType.objects.create(name='PERANGKAT UJI')
        self.device = Device.objects.create(nama='UJI-01', jenis=jenis,
                                            merk='SEL', lokasi='GI TELLO')


class PreventivePelaksanaWajibTests(_Dasar):

    def _isian(self, **ubah):
        data = {
            'maintenance_type': 'Preventive',
            'date': '2026-11-05T08:00',
            'description': 'Pemeliharaan rutin',
            'status': 'Open',
            'pelaksana_names': '["Budi"]',
        }
        data.update(ubah)
        return data

    def url_tambah(self):
        return reverse('maintenance_add_device', args=[self.device.pk])

    def test_ditolak_tanpa_pelaksana(self):
        for kosong in ('[]', '["", "  "]', ''):
            with self.subTest(pelaksana_names=kosong):
                resp = self.client.post(self.url_tambah(),
                                        self._isian(pelaksana_names=kosong))
                self.assertEqual(resp.status_code, 200)
                self.assertFalse(Maintenance.objects.exists())
                self.assertEqual(
                    resp.context['maintenance_form'].errors['pelaksana_names'],
                    [PESAN_PELAKSANA_WAJIB])
                self.assertTrue(_pesan_tampil(resp))

    def test_pesan_di_atas_kolom(self):
        resp = self.client.post(self.url_tambah(), self._isian(pelaksana_names='[]'))
        html = resp.content.decode()
        self.assertLess(html.index('id="pelaksana-error"'),
                        html.index('id="pelaksana-tag-box"'))

    def test_tersimpan_dengan_nama_yang_dirapikan(self):
        resp = self.client.post(self.url_tambah(),
                                self._isian(pelaksana_names='[" Budi ", "Andi", "Budi"]'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Maintenance.objects.get().pelaksana_names, ['Budi', 'Andi'])

    def test_nama_tidak_hilang_saat_kolom_lain_salah(self):
        """Widget membaca daftar awal dari input tersembunyi — isinya harus
        nama yang dikirim, bukan kosong, kalau form ditolak karena hal lain."""
        resp = self.client.post(self.url_tambah(), self._isian(date='bukan-tanggal'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('pelaksana_names', resp.context['maintenance_form'].errors)
        self.assertContains(resp, 'value="[&quot;Budi&quot;]"')
        self.assertFalse(_pesan_tampil(resp))

    def test_edit_ditolak_tanpa_pelaksana(self):
        m = Maintenance.objects.create(
            device=self.device, maintenance_type='Preventive', date=timezone.now(),
            description='asli', status='Open', pelaksana_names=['Budi'])
        resp = self.client.post(reverse('maintenance_edit', args=[m.pk]),
                                self._isian(pelaksana_names='[]', description='DIUBAH'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(_pesan_tampil(resp))
        m.refresh_from_db()
        self.assertEqual((m.description, m.pelaksana_names), ('asli', ['Budi']))

    def test_form_kosong_menandai_kolom_wajib_tanpa_pesan_error(self):
        resp = self.client.get(self.url_tambah())
        self.assertContains(resp, 'Pelaksana <span class="text-danger">*</span>', html=False)
        self.assertFalse(_pesan_tampil(resp))
        # Teks untuk JS sama dengan pesan server — satu kalimat untuk satu kesalahan
        self.assertContains(resp, f'data-pesan-wajib="{PESAN_PELAKSANA_WAJIB}"')


class CorrectivePelaksanaWajibTests(_Dasar):

    def _isian(self, **ubah):
        data = {
            'device_id': self.device.pk,
            'tanggal': '2026-11-05T08:00',
            'pelaksana_names_input': '["Budi"]',
            'deskripsi_masalah': 'PSU mati',
            'tindakan': 'Ganti PSU',
            'status_perbaikan': 'selesai',
        }
        data.update(ubah)
        return data

    def test_tambah_ditolak_tanpa_pelaksana(self):
        resp = self.client.post(reverse('corrective_add'),
                                self._isian(pelaksana_names_input='[]'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Maintenance.objects.exists())
        self.assertEqual(resp.context['pelaksana_error'], PESAN_PELAKSANA_WAJIB)
        self.assertTrue(_pesan_tampil(resp))

    def test_tambah_tersimpan_dengan_pelaksana(self):
        resp = self.client.post(reverse('corrective_add'), self._isian())
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Maintenance.objects.get().pelaksana_names, ['Budi'])

    def test_edit_ditolak_tanpa_pelaksana(self):
        self.client.post(reverse('corrective_add'), self._isian())
        m = Maintenance.objects.get()

        resp = self.client.post(reverse('corrective_edit', args=[m.pk]),
                                self._isian(pelaksana_names_input='["  "]',
                                            tindakan='DIUBAH'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(_pesan_tampil(resp))
        m.refresh_from_db()
        self.assertEqual(m.pelaksana_names, ['Budi'])
        self.assertEqual(MaintenanceCorrective.objects.get().tindakan, 'Ganti PSU')

    def test_form_menandai_kolom_wajib(self):
        resp = self.client.get(reverse('corrective_add'))
        self.assertContains(resp, 'Pelaksana / PIC <span class="req">*</span>')
        self.assertFalse(_pesan_tampil(resp))
