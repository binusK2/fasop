"""Tes form Tambah/Edit Peralatan.

Yang dijaga di sini: mengedit peralatan tidak boleh menghapus data yang TIDAK
ada di form. Dulu `DeviceForm` memakai `fields = '__all__'`, sehingga kolom
yang tidak pernah dirender template â€” `created_by`, `public_token`,
`wiring_json` â€” tetap menjadi field form. Field ForeignKey/CharField/JSONField
tanpa nilai bawaan yang tidak ikut terkirim dianggap "dikosongkan" oleh
ModelForm, jadi setiap kali peralatan diedit:

- "Ditambahkan oleh" di halaman detail jadi kosong (â€”),
- token QR publik diganti baru (stiker QR yang sudah tertempel mati),
- data wiring diagram hilang.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import DeviceForm
from .models import Device, DeviceLog, DeviceType, UserProfile


def _profil(user, role):
    p, _ = UserProfile.objects.get_or_create(user=user)
    p.role = role
    p.force_password_change = False
    p.save()
    return p


class DeviceEditTidakMenghapusDataTests(TestCase):

    def setUp(self):
        self.jenis = DeviceType.objects.create(name='ROUTER')
        self.pembuat = User.objects.create_user(
            username='pembuat', password='rahasia', first_name='Andi')
        _profil(self.pembuat, 'technician')
        self.penyunting = User.objects.create_user(
            username='penyunting', password='rahasia', first_name='Budi')
        _profil(self.penyunting, 'technician')

    def _isian(self, **ubah):
        data = {
            'nama': 'ROUTER GI TELLO',
            'jenis': self.jenis.pk,
            'merk': 'Mikrotik',
            'lokasi': 'GI TELLO',
            'status_operasi': 'operasi',
            'status_aset': 'UP2B',
            'spesifikasi_json': '{}',
            'komponen_json': '[]',
        }
        data.update(ubah)
        return data

    def _tambah(self):
        self.client.force_login(self.pembuat)
        resp = self.client.post(reverse('device_add'), self._isian())
        self.assertEqual(resp.status_code, 302)
        return Device.objects.get()

    def test_tambah_mencatat_pembuat(self):
        device = self._tambah()
        self.assertEqual(device.created_by, self.pembuat)

    def test_edit_tidak_menghapus_pembuat(self):
        device = self._tambah()

        self.client.force_login(self.penyunting)
        resp = self.client.post(reverse('device_edit', args=[device.pk]),
                                self._isian(merk='Cisco'))
        self.assertEqual(resp.status_code, 302)

        device.refresh_from_db()
        self.assertEqual(device.merk, 'Cisco')
        self.assertEqual(device.created_by, self.pembuat)

    def test_detail_menampilkan_pembuat_setelah_diedit(self):
        device = self._tambah()
        self.client.force_login(self.penyunting)
        self.client.post(reverse('device_edit', args=[device.pk]),
                         self._isian(merk='Cisco'))

        resp = self.client.get(reverse('device_detail', args=[device.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Ditambahkan oleh')
        self.assertContains(resp, 'Andi')       # pembuat
        self.assertContains(resp, 'Budi')       # terakhir diupdate

    def test_edit_tidak_mengganti_token_qr(self):
        device = self._tambah()
        token_lama = device.public_token
        self.assertTrue(token_lama)

        self.client.force_login(self.penyunting)
        self.client.post(reverse('device_edit', args=[device.pk]),
                         self._isian(merk='Cisco'))

        device.refresh_from_db()
        self.assertEqual(device.public_token, token_lama)

    def test_edit_tidak_menghapus_wiring(self):
        device = self._tambah()
        wiring = {'nodes': [{'id': 1}], 'links': []}
        Device.objects.filter(pk=device.pk).update(wiring_json=wiring)

        self.client.force_login(self.penyunting)
        self.client.post(reverse('device_edit', args=[device.pk]),
                         self._isian(merk='Cisco'))

        device.refresh_from_db()
        self.assertEqual(device.wiring_json, wiring)

    def test_form_hanya_memuat_kolom_yang_dirender(self):
        # Kolom internal tidak boleh menjadi field form. Kalau suatu saat ada
        # kolom baru di Device yang memang perlu diedit, tambahkan ke
        # DeviceForm.Meta.fields DAN render di device_form.html.
        fields = set(DeviceForm().fields)
        for internal in ('created_by', 'deleted_by', 'is_deleted',
                         'public_token', 'wiring_json', 'wiring_img'):
            self.assertNotIn(internal, fields)


class IsiUlangPembuatDariLogTests(TestCase):
    """Migrasi 0072 memulihkan created_by yang terhapus dari DeviceLog 'create'."""

    def test_isi_ulang_dari_log_create(self):
        from importlib import import_module
        from django.apps import apps

        mig = import_module('devices.migrations.0072_isi_ulang_device_created_by')

        pembuat = User.objects.create_user(username='pembuat')
        lain = User.objects.create_user(username='lain')
        kosong = Device.objects.create(nama='A', merk='X', lokasi='GI A')
        terisi = Device.objects.create(nama='B', merk='X', lokasi='GI B',
                                       created_by=lain)
        tanpa_log = Device.objects.create(nama='C', merk='X', lokasi='GI C')
        api = Device.objects.create(nama='D', merk='X', lokasi='GI D')

        DeviceLog.objects.create(device=kosong, user=pembuat, aksi='create')
        DeviceLog.objects.create(device=kosong, user=lain, aksi='edit')
        DeviceLog.objects.create(device=terisi, user=pembuat, aksi='create')
        DeviceLog.objects.create(device=api, user=None, aksi='create')

        mig.isi_ulang(apps, None)

        kosong.refresh_from_db()
        terisi.refresh_from_db()
        tanpa_log.refresh_from_db()
        api.refresh_from_db()
        self.assertEqual(kosong.created_by, pembuat)
        self.assertEqual(terisi.created_by, lain)   # tidak ditimpa
        self.assertIsNone(tanpa_log.created_by)
        self.assertIsNone(api.created_by)            # dibuat lewat API, memang tanpa user
