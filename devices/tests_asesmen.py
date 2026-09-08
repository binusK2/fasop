"""Tes Asesmen Optik — pendataan FO & aksesoris per tower.

Diisi vendor (pihak luar) dan tim teknisi, jadi yang dijaga di sini bukan cuma
"formnya jalan" tapi juga sejauh mana akun vendor bisa bergerak.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import AsesmenOptik, FiberOptic, UserProfile


def _profil(user, role):
    p, _ = UserProfile.objects.get_or_create(user=user)
    p.role = role
    p.force_password_change = False
    p.save()
    return p


class AsesmenOptikFormTests(TestCase):
    """Form asesmen — menempel ke ruas FO yang sudah ada, bukan diketik ulang."""

    def setUp(self):
        self.teknisi = User.objects.create_user(username='teknisi', password='rahasia')
        _profil(self.teknisi, 'technician')
        self.client.force_login(self.teknisi)

        self.fo = FiberOptic.objects.create(
            nama='LINK FO GI TELLO - GI DAYA', lokasi_a='GI TELLO',
            lokasi_b='GI DAYA', tipe_kabel='ADSS')

    def _isian(self, **ubah):
        data = {
            'fiber_optic': self.fo.pk,
            'no_tower': '12',
            'tanggal': '2026-03-10',
            'upt': 'UPT MAKASSAR',
            'level_tegangan': '150 kV',
            'fasa_fo': 'tengah',
            'kondisi_fo': 'baik',
            'tipe_asesoris': 'tension',
            'kondisi_asesoris': 'anomali',
            'joint_box': 'tidak_ada',
            'asset': 'UP2B',
            'area_rintangan': 'Sawah',
            'keterangan': 'Fitmen berkarat',
            'petugas': 'CV Optik Jaya',
        }
        data.update(ubah)
        return data

    def test_form_terbuka(self):
        resp = self.client.get(reverse('asesmen_optik_add'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Ruas Fiber Optic')
        self.assertContains(resp, self.fo.nama)

    def test_simpan_menyimpan_seluruh_isian(self):
        resp = self.client.post(reverse('asesmen_optik_add'), self._isian())
        self.assertEqual(resp.status_code, 302)

        a = AsesmenOptik.objects.get()
        self.assertEqual(a.fiber_optic, self.fo)
        self.assertEqual(a.no_tower, '12')
        self.assertEqual(a.kondisi_fo, 'baik')
        self.assertEqual(a.kondisi_asesoris, 'anomali')
        self.assertEqual(a.joint_box, 'tidak_ada')
        self.assertEqual(a.area_rintangan, 'Sawah')
        self.assertEqual(a.petugas, 'CV Optik Jaya')
        self.assertEqual(a.created_by, self.teknisi)

    def test_nomor_tower_dinormalkan(self):
        """'#012' dan '12' menunjuk tower yang sama."""
        self.client.post(reverse('asesmen_optik_add'), self._isian(no_tower='#012'))
        self.assertEqual(AsesmenOptik.objects.get().no_tower, '012')

    def test_tipe_kabel_ikut_ruas_bila_dikosongkan(self):
        """Tidak diketik ulang per tower — itu inti 'arahkan ke data FO'."""
        self.client.post(reverse('asesmen_optik_add'), self._isian())
        self.assertEqual(AsesmenOptik.objects.get().tipe_kabel_efektif, 'ADSS')

    def test_tipe_kabel_boleh_beda_dari_ruasnya(self):
        self.client.post(reverse('asesmen_optik_add'), self._isian(tipe_kabel='OPGW'))
        self.assertEqual(AsesmenOptik.objects.get().tipe_kabel_efektif, 'OPGW')

    def test_ruas_wajib_dipilih(self):
        resp = self.client.post(reverse('asesmen_optik_add'), self._isian(fiber_optic=''))
        self.assertEqual(resp.status_code, 200)      # form kembali dengan error
        self.assertFalse(AsesmenOptik.objects.exists())

    def test_lanjut_ke_tower_berikutnya_mempertahankan_konteks(self):
        """Vendor mengisi puluhan tower berurutan di ruas yang sama."""
        resp = self.client.post(reverse('asesmen_optik_add'),
                                dict(self._isian(), lanjut='1'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('ruas=', resp['Location'])
        self.assertIn('tanggal=2026-03-10', resp['Location'])

        lanjutan = self.client.get(resp['Location'])
        self.assertEqual(lanjutan.context['form'].initial['fiber_optic'], self.fo.pk)
        self.assertEqual(lanjutan.context['form'].initial['petugas'], 'CV Optik Jaya')

    def test_riwayat_tersimpan_bukan_ditimpa(self):
        """Tower yang sama diasesmen lagi → baris baru, bukan menimpa."""
        self.client.post(reverse('asesmen_optik_add'), self._isian())
        self.client.post(reverse('asesmen_optik_add'),
                         self._isian(tanggal='2026-09-10', kondisi_asesoris='baik'))
        self.assertEqual(AsesmenOptik.objects.filter(no_tower='12').count(), 2)

    def test_penanda_anomali(self):
        self.client.post(reverse('asesmen_optik_add'), self._isian())
        self.assertTrue(AsesmenOptik.objects.get().ada_anomali)

        AsesmenOptik.objects.update(kondisi_asesoris='baik')
        self.assertFalse(AsesmenOptik.objects.get().ada_anomali)


class AsesmenOptikDaftarTests(TestCase):
    """Daftar & penyaringnya."""

    def setUp(self):
        self.user = User.objects.create_superuser(username='admin_ao', password='rahasia')
        _profil(self.user, 'asisten_manager')
        self.client.force_login(self.user)

        self.fo1 = FiberOptic.objects.create(nama='RUAS A', lokasi_a='A', lokasi_b='B')
        self.fo2 = FiberOptic.objects.create(nama='RUAS B', lokasi_a='C', lokasi_b='D')

        AsesmenOptik.objects.create(fiber_optic=self.fo1, no_tower='1',
                                    tanggal='2026-03-01', kondisi_fo='baik',
                                    kondisi_asesoris='baik', petugas='Budi')
        AsesmenOptik.objects.create(fiber_optic=self.fo1, no_tower='2',
                                    tanggal='2026-03-02', kondisi_fo='baik',
                                    kondisi_asesoris='anomali', petugas='Budi')
        AsesmenOptik.objects.create(fiber_optic=self.fo2, no_tower='1',
                                    tanggal='2026-03-03', kondisi_fo='rusak',
                                    kondisi_asesoris='baik', petugas='Andi')

    def test_daftar_menampilkan_semua(self):
        resp = self.client.get(reverse('asesmen_optik_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['paginator'].count, 3)

    def test_saring_per_ruas(self):
        from fasop.hashids_helper import encode
        resp = self.client.get(reverse('asesmen_optik_list'),
                               {'ruas': encode(self.fo1.pk)})
        self.assertEqual(resp.context['paginator'].count, 2)

    def test_saring_perlu_tindak_lanjut(self):
        """Kondisi FO rusak/anomali ATAU aksesoris anomali/tanpa fitmen."""
        resp = self.client.get(reverse('asesmen_optik_list'), {'kondisi': 'anomali'})
        self.assertEqual(resp.context['paginator'].count, 2)

    def test_saring_baik_semua(self):
        resp = self.client.get(reverse('asesmen_optik_list'), {'kondisi': 'baik'})
        self.assertEqual(resp.context['paginator'].count, 1)

    def test_cari_petugas(self):
        resp = self.client.get(reverse('asesmen_optik_list'), {'q': 'Andi'})
        self.assertEqual(resp.context['paginator'].count, 1)


class AsesmenOptikAksesTests(TestCase):
    """Siapa boleh apa — vendor adalah pihak LUAR."""

    def setUp(self):
        self.fo = FiberOptic.objects.create(nama='RUAS A', lokasi_a='A', lokasi_b='B')

        self.vendor = User.objects.create_user(username='vendor1', password='rahasia')
        _profil(self.vendor, 'vendor')
        self.vendor_lain = User.objects.create_user(username='vendor2', password='rahasia')
        _profil(self.vendor_lain, 'vendor')
        self.viewer = User.objects.create_user(username='viewer1', password='rahasia')
        _profil(self.viewer, 'viewer')

    def _asesmen(self, oleh):
        return AsesmenOptik.objects.create(
            fiber_optic=self.fo, no_tower='1', tanggal='2026-03-01', created_by=oleh)

    def test_vendor_bisa_mengisi(self):
        self.client.force_login(self.vendor)
        self.assertEqual(self.client.get(reverse('asesmen_optik_add')).status_code, 200)

    def test_viewer_tidak_bisa_mengisi(self):
        self.client.force_login(self.viewer)
        resp = self.client.get(reverse('asesmen_optik_add'))
        self.assertNotEqual(resp.status_code, 200)

    def test_viewer_tetap_bisa_melihat_daftar(self):
        self.client.force_login(self.viewer)
        resp = self.client.get(reverse('asesmen_optik_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['bisa_isi'])

    def test_vendor_hanya_menyunting_isiannya_sendiri(self):
        milik_orang_lain = self._asesmen(self.vendor_lain)
        self.client.force_login(self.vendor)
        resp = self.client.get(reverse('asesmen_optik_edit', args=[milik_orang_lain.pk]))
        self.assertRedirects(resp, reverse('asesmen_optik_list'))

    def test_vendor_bisa_menyunting_miliknya(self):
        milik_sendiri = self._asesmen(self.vendor)
        self.client.force_login(self.vendor)
        resp = self.client.get(reverse('asesmen_optik_edit', args=[milik_sendiri.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_teknisi_bisa_menyunting_isian_vendor(self):
        milik_vendor = self._asesmen(self.vendor)
        teknisi = User.objects.create_user(username='tek2', password='rahasia')
        _profil(teknisi, 'technician')
        self.client.force_login(teknisi)
        resp = self.client.get(reverse('asesmen_optik_edit', args=[milik_vendor.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_vendor_terkunci_di_luar_asesmen(self):
        """Akun pihak luar tidak boleh menelusuri sisa FASOP."""
        self.client.force_login(self.vendor)
        for nama in ('device_list', 'fiber_optic_list', 'maintenance_list'):
            with self.subTest(halaman=nama):
                resp = self.client.get(reverse(nama))
                self.assertRedirects(resp, reverse('asesmen_optik_list'))

    def test_vendor_tetap_bisa_membuka_halaman_asesmen(self):
        self.client.force_login(self.vendor)
        self.assertEqual(
            self.client.get(reverse('asesmen_optik_list')).status_code, 200)

class AsesmenOptikKoordinatTests(TestCase):
    """Koordinat harus menerima bentuk yang benar-benar disalin orang.

    Isian lintang/bujur dulu <input type="number" step="0.000001">: koma
    desimal dan sepasang koordinat yang ditempel sekaligus ditolak browser
    tanpa pesan, sementara error dari server tidak pernah dirender sama
    sekali — form kembali kosong tanpa keterangan apa pun.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='tek_koord', password='rahasia')
        _profil(self.user, 'technician')
        self.client.force_login(self.user)
        self.fo = FiberOptic.objects.create(nama='RUAS A', lokasi_a='A', lokasi_b='B')

    def _simpan(self, lintang='', bujur=''):
        return self.client.post(reverse('asesmen_optik_add'), {
            'fiber_optic': self.fo.pk, 'no_tower': '12', 'tanggal': '2026-03-10',
            'lintang': lintang, 'bujur': bujur,
        })

    def test_desimal_biasa(self):
        self.assertEqual(self._simpan('-5.147889', '119.470535').status_code, 302)
        a = AsesmenOptik.objects.get()
        self.assertEqual(str(a.lintang), '-5.14788900')

    def test_koma_desimal_diterima(self):
        """Begitulah cara mengetik angka desimal di sini."""
        self.assertEqual(self._simpan('-5,147889', '119,470535').status_code, 302)
        a = AsesmenOptik.objects.get()
        self.assertEqual(str(a.lintang), '-5.14788900')
        self.assertEqual(str(a.bujur), '119.47053500')

    def test_desimal_berlebih_dibulatkan_bukan_ditolak(self):
        """Selisihnya di bawah satu milimeter — tidak layak jadi penghalang."""
        self.assertEqual(self._simpan('-5.147888577', '119.4705353').status_code, 302)
        a = AsesmenOptik.objects.get()
        self.assertEqual(str(a.lintang), '-5.14788858')

    def test_sepasang_koordinat_ditempel_sekaligus(self):
        """Bentuk salinan dari peta dan dari berkas sumbernya."""
        self.assertEqual(self._simpan('-5.147888577, 119.4705353').status_code, 302)
        a = AsesmenOptik.objects.get()
        self.assertEqual(str(a.lintang), '-5.14788858')
        self.assertEqual(str(a.bujur), '119.47053530')

    def test_tempelan_tidak_menimpa_bujur_yang_sudah_diisi(self):
        """Angka yang sudah diketik orang menang atas setengah tempelan."""
        self.assertEqual(
            self._simpan('-5.147889, 119.470535', '120.000000').status_code, 302)
        a = AsesmenOptik.objects.get()
        self.assertEqual(str(a.lintang), '-5.14788900')
        self.assertEqual(str(a.bujur), '120.00000000')

    def test_koordinat_boleh_kosong(self):
        self.assertEqual(self._simpan().status_code, 302)
        a = AsesmenOptik.objects.get()
        self.assertIsNone(a.lintang)
        self.assertIsNone(a.bujur)

    def test_isian_ngawur_ditolak_dengan_pesan_yang_terlihat(self):
        """Ini inti keluhannya: dulu ditolak tanpa keterangan apa pun."""
        resp = self._simpan('bukan angka', '')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AsesmenOptik.objects.exists())

        pesan = resp.context['form'].errors['lintang'][0]
        isi = resp.content.decode()
        self.assertIn(pesan, isi)                       # pesannya benar-benar dirender
        self.assertIn('Asesmen belum tersimpan', isi)   # ringkasan di atas form
        self.assertIn('Lintang', isi)                   # menyebut isian mana
        self.assertIn('harus berupa angka', pesan)      # dan berbahasa Indonesia

    def test_semua_isian_menampilkan_errornya(self):
        """Bukan cuma lintang — dulu hanya 3 dari 22 isian punya blok error."""
        resp = self.client.post(reverse('asesmen_optik_add'), {
            'fiber_optic': '', 'no_tower': '', 'tanggal': 'bukan tanggal',
            'jarak_span': 'abc',
        })
        self.assertEqual(resp.status_code, 200)
        isi = resp.content.decode()
        for field, pesan in resp.context['form'].errors.items():
            with self.subTest(field=field):
                self.assertIn(pesan[0], isi)

class AsesmenOptikExportTests(TestCase):
    """Export Excel — isinya harus sama dengan yang terlihat di layar."""

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_exp', password='rahasia')
        _profil(self.user, 'asisten_manager')
        self.client.force_login(self.user)

        self.fo1 = FiberOptic.objects.create(nama='RUAS A', lokasi_a='GI TELLO',
                                             lokasi_b='GI DAYA', tipe_kabel='ADSS')
        self.fo2 = FiberOptic.objects.create(nama='RUAS B', lokasi_a='GI BARRU',
                                             lokasi_b='GI PARE', tipe_kabel='OPGW')

        AsesmenOptik.objects.create(
            fiber_optic=self.fo1, no_tower='10', tanggal='2026-03-01',
            upt='UPT MAKASSAR', level_tegangan='150 kV', fasa_fo='tengah',
            kondisi_fo='baik', kondisi_asesoris='anomali', joint_box='ada',
            area_rintangan='Sawah', keterangan='Fitmen berkarat',
            petugas='CV Optik Jaya', lintang='-5.147889', bujur='119.470535',
            created_by=self.user)
        AsesmenOptik.objects.create(
            fiber_optic=self.fo2, no_tower='5', tanggal='2026-03-02',
            kondisi_fo='baik', kondisi_asesoris='baik', petugas='Tim Teknisi')

    def _unduh(self, **params):
        resp = self.client.get(reverse('asesmen_optik_export'), params)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])
        self.assertIn('attachment;', resp['Content-Disposition'])
        return resp

    def _baca(self, resp):
        import io as _io
        import openpyxl
        wb = openpyxl.load_workbook(_io.BytesIO(resp.content))
        return wb

    def test_berkas_terunduh(self):
        wb = self._baca(self._unduh())
        self.assertIn('Asesmen Optik', wb.sheetnames)
        self.assertIn('Keterangan', wb.sheetnames)

    def test_susunan_kolom_mengikuti_berkas_kerja(self):
        """Supaya bisa langsung dibandingkan dengan berkas yang dipakai tim."""
        ws = self._baca(self._unduh())['Asesmen Optik']
        judul = [sel.value for sel in next(ws.iter_rows(max_row=1))]
        for wajib in ('UPT', 'GI Awal', 'GI Akhir', 'Level Tegangan', 'No Tower',
                      'Fasa FO', 'ADSS/ OPGW', 'Kondisi FO', 'Tipe Asesoris',
                      'Kondisi Asesoris', 'Joint Box', 'Ukuran Fitmen',
                      'Area Jalur Rintangan SUTT', 'Keterangan'):
            self.assertIn(wajib, judul)

    def test_isi_baris_lengkap(self):
        ws = self._baca(self._unduh())['Asesmen Optik']
        judul = [sel.value for sel in next(ws.iter_rows(max_row=1))]
        baris = [sel.value for sel in list(ws.iter_rows(min_row=2, max_row=2))[0]]
        isi = dict(zip(judul, baris))

        self.assertEqual(isi['GI Awal'], 'GI TELLO')
        self.assertEqual(isi['GI Akhir'], 'GI DAYA')
        self.assertEqual(isi['No Tower'], '10')
        self.assertEqual(isi['Fasa FO'], 'Tengah (S)')
        self.assertEqual(isi['ADSS/ OPGW'], 'ADSS')      # ikut ruasnya
        self.assertEqual(isi['Kondisi Asesoris'], 'Anomali')
        self.assertEqual(isi['Area Jalur Rintangan SUTT'], 'Sawah')

    def test_export_menghormati_penyaring_ruas(self):
        from fasop.hashids_helper import encode
        ws = self._baca(self._unduh(ruas=encode(self.fo1.pk)))['Asesmen Optik']
        self.assertEqual(ws.max_row, 2)                  # 1 judul + 1 data

    def test_export_menghormati_penyaring_kondisi(self):
        ws = self._baca(self._unduh(kondisi='anomali'))['Asesmen Optik']
        self.assertEqual(ws.max_row, 2)

    def test_lembar_keterangan_menyebut_penyaringnya(self):
        """Berkas hasil unduhan sebagian harus bisa dibedakan dari yang lengkap."""
        wb = self._baca(self._unduh(kondisi='anomali'))
        teks = '\n'.join(
            str(sel.value) for row in wb['Keterangan'].iter_rows() for sel in row)
        self.assertIn('perlu tindak lanjut', teks)

    def test_tombol_export_membawa_penyaring(self):
        from fasop.hashids_helper import encode
        resp = self.client.get(reverse('asesmen_optik_list'),
                               {'kondisi': 'anomali', 'ruas': encode(self.fo1.pk)})
        self.assertContains(resp, reverse('asesmen_optik_export') + '?')
        self.assertIn('kondisi=anomali', resp.context['querystring'])

