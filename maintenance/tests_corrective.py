"""Tes form Corrective Maintenance.

Form ini dibuka dari empat tempat berbeda dan memakai template yang sama
dengan view-nya sendiri (bukan `maintenance_create`/`maintenance_edit`), jadi
konteksnya beda — itu yang dulu membuat seluruh halamannya balas HTTP 500
tanpa ada satu tes pun yang menangkapnya.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile
from devices.models_komponen import DeviceComponent
from gangguan.models import Gangguan

from .models import Maintenance, MaintenanceCorrective


class FormCorrectiveTerbukaTests(TestCase):
    """Setiap jalan masuk form Corrective harus terbuka, bukan HTTP 500."""

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_corr', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        jenis = DeviceType.objects.create(name='RTU')
        self.device = Device.objects.create(nama='RTU-01', jenis=jenis,
                                            merk='SEL', lokasi='GI TELLO')
        self.gangguan = Gangguan.objects.create(
            peralatan=self.device, site='GI TELLO',
            tanggal_gangguan=timezone.make_aware(timezone.datetime(2026, 3, 9, 7, 0)))

    def test_dari_menu_umum(self):
        """Belum ada perangkat terpilih — dulu inilah yang paling gampang 500."""
        resp = self.client.get(reverse('corrective_add'))
        self.assertEqual(resp.status_code, 200)

    def test_dari_detail_perangkat(self):
        resp = self.client.get(reverse('corrective_add_device', args=[self.device.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.device.nama)

    def test_dari_tiket_gangguan(self):
        resp = self.client.get(reverse('corrective_add_gangguan', args=[self.gangguan.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.gangguan.nomor_gangguan)

    def test_tombol_cetak_formulir_menunggu_perangkat_dipilih(self):
        """Tanpa perangkat, tidak ada formulir kosong yang bisa dicetak."""
        resp = self.client.get(reverse('corrective_add'))
        self.assertContains(resp, 'Pilih perangkat dulu')
        # ...tapi tiap opsi membawa alamatnya sendiri untuk dipakai JS
        self.assertContains(
            resp, reverse('blank_maintenance_pdf', args=[self.device.pk]))

    def test_tombol_cetak_formulir_langsung_aktif_bila_perangkat_diketahui(self):
        resp = self.client.get(reverse('corrective_add_device', args=[self.device.pk]))
        self.assertContains(
            resp, reverse('blank_maintenance_pdf', args=[self.device.pk]))
        self.assertNotContains(resp, 'Pilih perangkat dulu')


class SimpanCorrectiveTests(TestCase):
    """Isi form harus benar-benar tersimpan — termasuk Komponen Terkait."""

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_corr2', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        jenis = DeviceType.objects.create(name='RTU')
        self.device = Device.objects.create(nama='RTU-01', jenis=jenis,
                                            merk='SEL', lokasi='GI TELLO')
        self.komponen = DeviceComponent.objects.create(
            device=self.device, nama='Power Supply A')
        self.komponen_lain = DeviceComponent.objects.create(
            device=self.device, nama='Modul I/O B')

    def _isian(self, **ubah):
        data = {
            'device_id': self.device.pk,
            'tanggal': '2026-03-10T08:00',
            'pelaksana_names_input': '["Budi"]',
            'jenis_kerusakan': 'hardware',
            'deskripsi_masalah': 'Power supply mati',
            'tindakan': 'Ganti power supply',
            'komponen_diganti': 'on',
            'nama_komponen': 'PSU 48V',
            'komponen_terkait': self.komponen.pk,
            'kondisi_sebelum': 'Mati total',
            'kondisi_sesudah': 'Normal',
            'durasi_jam': '2',
            'durasi_menit': '30',
            'status_perbaikan': 'selesai',
        }
        data.update(ubah)
        return data

    def test_simpan_baru_menyimpan_seluruh_isian(self):
        resp = self.client.post(reverse('corrective_add'), self._isian())
        self.assertEqual(resp.status_code, 302)

        corr = MaintenanceCorrective.objects.get()
        self.assertEqual(corr.jenis_kerusakan, 'hardware')
        self.assertEqual(corr.deskripsi_masalah, 'Power supply mati')
        self.assertEqual(corr.tindakan, 'Ganti power supply')
        self.assertTrue(corr.komponen_diganti)
        self.assertEqual(corr.nama_komponen, 'PSU 48V')
        self.assertEqual(corr.komponen_terkait, self.komponen)
        self.assertEqual(corr.kondisi_sebelum, 'Mati total')
        self.assertEqual(corr.kondisi_sesudah, 'Normal')
        self.assertEqual((corr.durasi_jam, corr.durasi_menit), (2, 30))
        self.assertEqual(corr.status_perbaikan, 'selesai')

        m = corr.maintenance
        self.assertEqual(m.maintenance_type, 'Corrective')
        self.assertEqual(m.status, 'Done')           # 'selesai' → Done
        self.assertEqual(m.pelaksana_names, ['Budi'])

        # Jam yang diketik operator harus tersimpan apa adanya (waktu lokal),
        # bukan bergeser 8 jam karena diperlakukan sebagai UTC
        lokal = timezone.localtime(m.date)
        self.assertEqual((lokal.hour, lokal.minute), (8, 0))
        self.assertEqual((lokal.year, lokal.month, lokal.day), (2026, 3, 10))

    def test_edit_menyimpan_perubahan_komponen_terkait(self):
        """Dropdown-nya tampil di form edit tapi dulu tidak pernah disimpan."""
        self.client.post(reverse('corrective_add'), self._isian())
        corr = MaintenanceCorrective.objects.get()

        self.client.post(
            reverse('corrective_edit', args=[corr.maintenance.pk]),
            self._isian(komponen_terkait=self.komponen_lain.pk,
                        tindakan='Ganti modul I/O'))

        corr.refresh_from_db()
        self.assertEqual(corr.komponen_terkait, self.komponen_lain)
        self.assertEqual(corr.tindakan, 'Ganti modul I/O')

    def test_edit_bisa_mengosongkan_komponen_terkait(self):
        self.client.post(reverse('corrective_add'), self._isian())
        corr = MaintenanceCorrective.objects.get()

        self.client.post(
            reverse('corrective_edit', args=[corr.maintenance.pk]),
            self._isian(komponen_terkait=''))

        corr.refresh_from_db()
        self.assertIsNone(corr.komponen_terkait)

    def test_corrective_tidak_ikut_terkunci_saat_done(self):
        """Aturan kunci "sudah selesai" hanya untuk preventive.

        Corrective dibuka-tutup lewat field Status Perbaikan-nya sendiri;
        mengunci form ini berarti tidak ada lagi cara mengubahnya kembali
        jadi 'belum selesai'.
        """
        self.client.post(reverse('corrective_add'), self._isian())
        corr = MaintenanceCorrective.objects.get()
        self.assertEqual(corr.maintenance.status, 'Done')

        # maintenance_edit mengalihkan Corrective ke form-nya sendiri, bukan
        # memantulkannya balik ke halaman detail
        resp = self.client.get(reverse('maintenance_edit', args=[corr.maintenance.pk]))
        self.assertRedirects(
            resp, reverse('corrective_edit', args=[corr.maintenance.pk]))

        self.client.post(
            reverse('corrective_edit', args=[corr.maintenance.pk]),
            self._isian(status_perbaikan='pending'))
        corr.refresh_from_db()
        self.assertEqual(corr.status_perbaikan, 'pending')
        self.assertEqual(corr.maintenance.status, 'Open')
