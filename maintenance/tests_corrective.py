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

from .models import (BeritaAcaraRecord, Maintenance,
                     MaintenanceCorrective)


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

    def test_hanya_simpan_dan_batal_di_tombol_aksinya(self):
        """Cetak Formulir & Simpan + Cetak PDF sudah ditiadakan dari form ini."""
        for url in (reverse('corrective_add'),
                    reverse('corrective_add_device', args=[self.device.pk])):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertNotContains(resp, 'Cetak Formulir')
                self.assertNotContains(resp, 'Cetak PDF')
                self.assertNotContains(
                    resp, reverse('blank_maintenance_pdf', args=[self.device.pk]))
                self.assertContains(resp, 'Simpan Corrective')
                self.assertContains(resp, 'Batal')

    def test_perangkat_bisa_dicari(self):
        """Daftarnya memuat semua perangkat — menggulirnya tidak praktis."""
        resp = self.client.get(reverse('corrective_add'))
        self.assertContains(resp, 'select-cari')
        # lokasi ikut tercari walau letaknya di judul optgroup, bukan teks opsi
        self.assertContains(resp, 'data-cari="%s' % self.device.lokasi)

    def test_pelaksana_memakai_widget_yang_sama_dengan_preventive(self):
        """Satu widget dipakai berdua — bukan dua salinan yang lama-lama beda.

        Yang membedakan dulu: corrective tidak punya autocomplete sama sekali,
        jadi nama pelaksananya diketik bebas dan tidak pernah cocok dengan nama
        yang dipakai form preventive.
        """
        korektif   = self.client.get(reverse('corrective_add'))
        preventive = self.client.get(
            reverse('maintenance_add_device', args=[self.device.pk]))

        for resp in (korektif, preventive):
            self.assertContains(resp, 'pelaksana-suggest')      # dropdown saran
            self.assertContains(resp, reverse('pelaksana_search'))
            self.assertContains(resp, 'pelaksana-add-btn')

    def test_saran_pelaksana_hanya_teknisi_dan_nama_lengkapnya(self):
        from django.contrib.auth.models import User as _User

        teknisi = _User.objects.create_user(username='budi', password='x',
                                            first_name='Budi', last_name='Santoso')
        prof, _ = UserProfile.objects.get_or_create(user=teknisi)
        prof.role = 'technician'
        prof.save()

        bukan = _User.objects.create_user(username='vera', password='x',
                                          first_name='Vera', last_name='Viewer')
        prof2, _ = UserProfile.objects.get_or_create(user=bukan)
        prof2.role = 'viewer'
        prof2.save()

        hasil = self.client.get(reverse('pelaksana_search'), {'q': 'a'}).json()['results']
        self.assertIn('Budi Santoso', hasil)      # nama lengkap, bukan username
        self.assertNotIn('Vera Viewer', hasil)    # bukan teknisi


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

class TerbitBADariCorrectiveTests(TestCase):
    """Simpan corrective -> popup -> BA terbit otomatis TANPA nomor.

    Nomor BA mengikuti agenda kantor, bukan sistem; itu sebabnya BA-nya terbit
    sebagai draft dan orangnya harus diingatkan untuk melengkapinya.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_ba', password='rahasia')
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
        self.gangguan = Gangguan.objects.create(
            peralatan=self.device, site='GI TELLO',
            tanggal_gangguan=timezone.make_aware(timezone.datetime(2026, 3, 9, 7, 0)))

    def _isian(self, **ubah):
        data = {
            'device_id': self.device.pk,
            'tanggal': '2026-03-10T08:00',
            'pelaksana_names_input': '["Budi", "Andi"]',
            'jenis_kerusakan': 'hardware',
            'deskripsi_masalah': 'Power supply mati total',
            'tindakan': 'Ganti power supply 48V',
            'komponen_diganti': 'on',
            'nama_komponen': 'PSU 48V',
            'komponen_terkait': self.komponen.pk,
            'kondisi_sebelum': 'Mati',
            'kondisi_sesudah': 'Normal',
            'durasi_jam': '2',
            'durasi_menit': '30',
            'status_perbaikan': 'selesai',
        }
        data.update(ubah)
        return data

    def test_tanpa_jawab_ya_tidak_ada_ba(self):
        """Simpan saja = tidak menerbitkan apa pun."""
        self.client.post(reverse('corrective_add'), self._isian(terbitkan_ba='0'))
        self.assertFalse(BeritaAcaraRecord.objects.exists())

    def test_jawab_ya_menerbitkan_ba_tanpa_nomor(self):
        self.client.post(reverse('corrective_add'), self._isian(terbitkan_ba='1'))

        ba = BeritaAcaraRecord.objects.get()
        self.assertEqual(ba.nomor_ba, '')            # diisi manual
        self.assertEqual(ba.ttd_status, 'draft')
        self.assertEqual(ba.jenis, 'gangguan')
        self.assertEqual(ba.created_by, self.user)
        self.assertEqual(ba.sumber_maintenance, Maintenance.objects.get())

    def test_bentuk_ba_tetap_format_bawaan_gangguan(self):
        """Kolomnya kolom BA 'gangguan' yang sudah ada, bukan bentuk baru."""
        from maintenance.views import _BA_DEFAULT_COLUMNS

        self.client.post(reverse('corrective_add'), self._isian(terbitkan_ba='1'))
        ba = BeritaAcaraRecord.objects.get()
        self.assertEqual(ba.columns_data, _BA_DEFAULT_COLUMNS['gangguan'])

    def test_isian_corrective_dipetakan_ke_kolomnya(self):
        self.client.post(reverse('corrective_add'), self._isian(terbitkan_ba='1'))
        ba = BeritaAcaraRecord.objects.get()

        sel = dict(zip(ba.columns_data, ba.rows_data[0]['cells']))
        self.assertEqual(sel['Lokasi'], 'GI TELLO')
        self.assertEqual(sel['Peralatan'], 'RTU-01')
        self.assertEqual(sel['Komponen'], str(self.komponen))
        self.assertEqual(sel['Indikasi Gangguan'], 'Power supply mati total')
        self.assertIn('Ganti power supply 48V', sel['Keterangan'])
        self.assertIn('Normal', sel['Keterangan'])
        self.assertIn('2 jam 30 menit', sel['Keterangan'])
        self.assertEqual(sel['Tanggal Perbaikan'], '10/03/2026 08:00')
        self.assertEqual(ba.pelaksana, 'Budi, Andi')

    def test_tanggal_gangguan_terisi_bila_tiketnya_ditaut(self):
        self.client.post(reverse('corrective_add'),
                         self._isian(terbitkan_ba='1', gangguan_id=self.gangguan.pk))
        ba = BeritaAcaraRecord.objects.get()
        sel = dict(zip(ba.columns_data, ba.rows_data[0]['cells']))
        self.assertEqual(sel['Tanggal Gangguan'], '09/03/2026 07:00')
        self.assertEqual(ba.catatan, self.gangguan.nomor_gangguan)

    def test_notifikasi_perlu_dilengkapi_dibuat(self):
        from notifikasi.models import Notifikasi

        self.client.post(reverse('corrective_add'), self._isian(terbitkan_ba='1'))
        ba = BeritaAcaraRecord.objects.get()

        notif = Notifikasi.objects.get(tipe='ba_perlu_dilengkapi')
        self.assertEqual(notif.user, self.user)
        self.assertEqual(notif.url, reverse('ba_edit', args=[ba.pk]))
        self.assertEqual(notif.level, 'warning')

    def test_pesan_di_layar_menyebut_perlu_diselesaikan(self):
        resp = self.client.post(reverse('corrective_add'),
                                self._isian(terbitkan_ba='1'), follow=True)
        isi = resp.content.decode()
        self.assertIn('PERLU DISELESAIKAN', isi)
        # tautan ke editor BA harus benar-benar jadi tautan, bukan teks mentah
        ba = BeritaAcaraRecord.objects.get()
        self.assertIn('href="%s"' % reverse('ba_edit', args=[ba.pk]), isi)

    def test_simpan_ulang_tidak_menerbitkan_ba_kedua(self):
        """Form corrective bisa disimpan berkali-kali; BA-nya tetap satu."""
        self.client.post(reverse('corrective_add'), self._isian(terbitkan_ba='1'))
        m = Maintenance.objects.get()

        self.client.post(reverse('corrective_edit', args=[m.pk]),
                         self._isian(terbitkan_ba='1', tindakan='Diperbaiki lagi'))
        self.assertEqual(BeritaAcaraRecord.objects.count(), 1)

    def test_form_edit_menunjukkan_ba_yang_sudah_terbit(self):
        """Kalau BA-nya sudah ada, popup tidak muncul lagi - diganti tautan."""
        self.client.post(reverse('corrective_add'), self._isian(terbitkan_ba='1'))
        m = Maintenance.objects.get()
        ba = BeritaAcaraRecord.objects.get()

        resp = self.client.get(reverse('corrective_edit', args=[m.pk]))
        self.assertEqual(resp.context['ba_terkait'], ba)
        self.assertContains(resp, 'belum bernomor')
        self.assertNotContains(resp, 'modalTerbitBA')

    def test_ba_membeku_saat_corrective_diedit_kemudian(self):
        """BA bertanda tangan tidak boleh ikut berubah isinya.

        rows_data adalah salinan, bukan bacaan langsung ke corrective.
        """
        self.client.post(reverse('corrective_add'), self._isian(terbitkan_ba='1'))
        m = Maintenance.objects.get()
        sebelum = BeritaAcaraRecord.objects.get().rows_data

        self.client.post(reverse('corrective_edit', args=[m.pk]),
                         self._isian(tindakan='TINDAKAN DIUBAH'))

        self.assertEqual(BeritaAcaraRecord.objects.get().rows_data, sebelum)

class BADaftarBelumBernomorTests(TestCase):
    """BA tanpa nomor harus terlihat di daftar BA, bukan terkubur.

    Urutan daftar BA memakai nomor urut pada nomor_ba dan disortir MENURUN.
    BA tanpa nomor jatuh ke -1, jadi dulu ia mendarat di dasar daftar — di
    bawah seluruh BA lama — dan terbaca seperti tidak masuk daftar sama
    sekali. Padahal justru inilah yang paling perlu ditindak.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_daftar', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

        jenis = DeviceType.objects.create(name='RTU')
        self.device = Device.objects.create(nama='RTU-01', jenis=jenis,
                                            merk='SEL', lokasi='GI TELLO')

        # BA lama yang sudah bernomor, seperti di produksi
        for i in range(1, 6):
            BeritaAcaraRecord.objects.create(
                jenis='gangguan',
                nomor_ba='%03d.BA/FASOP/UP2BS-MKS/2026' % i,
                tanggal=timezone.datetime(2026, 1, i).date(),
                pelaksana='Budi', ttd_status='draft')

    def _terbitkan(self):
        self.client.post(reverse('corrective_add'), {
            'device_id': self.device.pk,
            'tanggal': '2026-03-10T08:00',
            'pelaksana_names_input': '["Budi"]',
            'jenis_kerusakan': 'hardware',
            'deskripsi_masalah': 'PSU mati',
            'tindakan': 'Ganti PSU',
            'status_perbaikan': 'selesai',
            'terbitkan_ba': '1',
        })
        return BeritaAcaraRecord.objects.get(sumber_maintenance__isnull=False)

    def test_ba_terbit_masuk_daftar(self):
        ba = self._terbitkan()
        resp = self.client.get(reverse('ba_list'))
        self.assertIn(ba, list(resp.context['records']))

    def test_ba_belum_bernomor_di_paling_atas(self):
        """Bukan sekadar ada — harus terlihat tanpa menggulir daftar panjang."""
        ba = self._terbitkan()
        resp = self.client.get(reverse('ba_list'))
        self.assertEqual(resp.context['records'][0], ba)

    def test_statusnya_draft(self):
        ba = self._terbitkan()
        self.assertEqual(ba.ttd_status, 'draft')
        self.assertEqual(ba.nomor_ba, '')

    def test_ditandai_belum_bernomor_di_layar(self):
        self._terbitkan()
        resp = self.client.get(reverse('ba_list'))
        self.assertContains(resp, 'Belum bernomor')
        self.assertContains(resp, '1 Berita Acara belum bernomor')

    def test_tanpa_ba_tanpa_nomor_bannernya_tidak_muncul(self):
        resp = self.client.get(reverse('ba_list'))
        self.assertEqual(resp.context['belum_bernomor'], 0)
        self.assertNotContains(resp, 'belum bernomor')

    def test_ba_bernomor_tetap_urut_seperti_semula(self):
        """Perubahan urutan hanya menyangkut yang belum bernomor."""
        self._terbitkan()
        resp = self.client.get(reverse('ba_list'))
        bernomor = [r.nomor_ba for r in resp.context['records'] if r.nomor_ba]
        self.assertEqual(bernomor, sorted(bernomor, reverse=True))

