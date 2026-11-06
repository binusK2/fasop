"""Form Offline: upload PDF/Word → validasi "mengetahui" AM → terhitung.

Yang paling penting dijaga: selama MENUNGGU validasi, form tidak dihitung di
mana pun; setelah divalidasi, ia muncul di Laporan Pemeliharaan dan riwayat
perangkat sebagai pemeliharaan Preventive yang selesai.
"""
import io
import shutil
import tempfile
import zipfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile
from notifikasi.models import Notifikasi

from .forms import PESAN_PELAKSANA_WAJIB
from .models import FormOffline, Maintenance

PDF = b'%PDF-1.4\n% form offline uji\n'
_MEDIA = tempfile.mkdtemp(prefix='fasop-uji-form-offline-')


def _user(username, role, superuser=False):
    buat = User.objects.create_superuser if superuser else User.objects.create_user
    u = buat(username=username, password='rahasia', first_name=username.title())
    profil, _ = UserProfile.objects.get_or_create(user=u)
    profil.role = role
    profil.force_password_change = False
    profil.save()
    return u


def _docx():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('word/document.xml', '<w:document/>')
    return buf.getvalue()


@override_settings(MEDIA_ROOT=_MEDIA)
class FormOfflineTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        self.teknisi = _user('teknisi_fo', 'technician')
        self.am = _user('am_fo', 'asisten_manager')
        jenis = DeviceType.objects.create(name='RTU')
        self.device = Device.objects.create(nama='RTU-TELLO', jenis=jenis,
                                            merk='SEL', lokasi='GI TELLO')
        self.url = reverse('offline_form_upload')
        self.tanggal = timezone.localtime() - timezone.timedelta(days=2)

    # ── helper ────────────────────────────────────────────────────────
    def _isian(self, **ubah):
        from fasop.hashids_helper import encode
        data = {
            'device': encode(self.device.pk),
            'tanggal': self.tanggal.strftime('%Y-%m-%dT%H:%M'),
            'pelaksana_names': '["Budi", " Andi "]',
            'berkas': SimpleUploadedFile('Form PM RTU.pdf', PDF, content_type='application/pdf'),
        }
        data.update(ubah)
        return data

    def _upload(self, user=None, **ubah):
        self.client.force_login(user or self.teknisi)
        return self.client.post(self.url, self._isian(**ubah))

    def _validasi(self, fo, user=None):
        self.client.force_login(user or self.am)
        return self.client.post(reverse('offline_form_validasi', args=[fo.pk]))

    # ── upload ────────────────────────────────────────────────────────
    def test_halaman_terbuka_dan_form_upload_tampil(self):
        self.client.force_login(self.teknisi)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="form-offline"')
        self.assertContains(resp, 'name="berkas"')
        self.assertContains(resp, 'pelaksana-suggest')          # widget pelaksana yang sama

    def test_upload_tersimpan_menunggu_dan_memberi_notif(self):
        resp = self._upload()
        self.assertRedirects(resp, self.url + '?tab=menunggu', fetch_redirect_response=False)

        fo = FormOffline.objects.get()
        self.assertEqual(fo.status, FormOffline.STATUS_MENUNGGU)
        self.assertEqual(fo.device, self.device)
        self.assertEqual(fo.pelaksana_names, ['Budi', 'Andi'])
        self.assertEqual(fo.created_by, self.teknisi)
        self.assertEqual(fo.nama_berkas, 'Form PM RTU.pdf')

        pesan = [str(m) for m in resp.wsgi_request._messages]
        self.assertTrue(any('berhasil diunggah' in p and 'RTU-TELLO' in p for p in pesan), pesan)
        self.assertTrue(Notifikasi.objects.filter(user=self.am, tipe='form_offline_validasi').exists())

    def test_belum_divalidasi_tidak_dihitung_di_mana_pun(self):
        self._upload()
        self.assertFalse(Maintenance.objects.exists())

        self.client.force_login(self.am)
        laporan = self.client.get(reverse('maintenance_report'),
                                  {'month': self.tanggal.month, 'year': self.tanggal.year})
        self.assertEqual(laporan.context['summary']['total'], 0)
        detail = self.client.get(reverse('device_view', args=[self.device.pk]))
        self.assertEqual(detail.context['maintenance_total'], 0)

    def test_isian_wajib_dan_pesan_di_atas_kolom(self):
        kasus = {
            'pelaksana': {'pelaksana_names': '[]'},
            'device': {'device': ''},
            'tanggal': {'tanggal': ''},
            'berkas_kosong': {'berkas': ''},
        }
        for nama, ubah in kasus.items():
            with self.subTest(kasus=nama):
                resp = self._upload(**ubah)
                self.assertEqual(resp.status_code, 200)
                self.assertFalse(FormOffline.objects.exists())
        resp = self._upload(pelaksana_names='["  "]')
        self.assertContains(resp, PESAN_PELAKSANA_WAJIB)
        html = resp.content.decode()
        self.assertLess(html.index('id="pelaksana-error"'), html.index('id="pelaksana-tag-box"'))

    def test_tanggal_masa_depan_ditolak(self):
        besok = (timezone.localtime() + timezone.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        resp = self._upload(tanggal=besok)
        self.assertContains(resp, 'tidak boleh di masa depan')
        self.assertFalse(FormOffline.objects.exists())

    def test_hanya_pdf_atau_word_asli(self):
        palsu = SimpleUploadedFile('form.pdf', b'MZ\x90\x00 bukan pdf', content_type='application/pdf')
        self.assertContains(self._upload(berkas=palsu), 'Isi file tidak sesuai ekstensinya')
        exe = SimpleUploadedFile('form.exe', b'MZ\x90\x00', content_type='application/octet-stream')
        self.assertContains(self._upload(berkas=exe), 'tidak diizinkan')
        self.assertFalse(FormOffline.objects.exists())

        docx = SimpleUploadedFile('form.docx', _docx())
        self.assertEqual(self._upload(berkas=docx).status_code, 302)
        self.assertEqual(FormOffline.objects.count(), 1)

    def test_viewer_tidak_bisa_upload(self):
        viewer = _user('viewer_fo', 'viewer')
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(self.url), 'id="form-offline"')
        self._upload(user=viewer)
        self.assertFalse(FormOffline.objects.exists())

    def test_teknisi_hanya_melihat_unggahannya_sendiri(self):
        lain = _user('teknisi_lain', 'technician')
        self._upload(user=lain)
        self._upload()
        self.client.force_login(self.teknisi)
        self.assertEqual(len(self.client.get(self.url).context['daftar']), 1)
        self.client.force_login(self.am)
        self.assertEqual(len(self.client.get(self.url).context['daftar']), 2)

    # ── validasi AM ───────────────────────────────────────────────────
    def test_validasi_am_membuat_pemeliharaan_yang_terhitung(self):
        self._upload()
        fo = FormOffline.objects.get()
        self._validasi(fo)

        fo.refresh_from_db()
        self.assertEqual(fo.status, FormOffline.STATUS_DIVALIDASI)
        self.assertEqual(fo.divalidasi_oleh, self.am)
        m = fo.maintenance
        self.assertEqual((m.device, m.maintenance_type, m.status), (self.device, 'Preventive', 'Done'))
        self.assertEqual(m.pelaksana_names, ['Budi', 'Andi'])
        self.assertEqual(m.signed_by, self.am)
        self.assertEqual(timezone.localtime(m.date).strftime('%Y-%m-%d %H:%M'),
                         self.tanggal.strftime('%Y-%m-%d %H:%M'))
        self.assertTrue(Notifikasi.objects.filter(user=self.teknisi, tipe='form_offline_hasil').exists())

        # Laporan Pemeliharaan
        laporan = self.client.get(reverse('maintenance_report'),
                                  {'month': self.tanggal.month, 'year': self.tanggal.year})
        self.assertEqual(laporan.context['summary']['preventive'], 1)
        # Riwayat perangkat
        detail = self.client.get(reverse('device_view', args=[self.device.pk]))
        self.assertEqual(detail.context['maintenance_total'], 1)
        self.assertContains(detail, 'Form Offline')
        self.assertContains(detail, 'Divalidasi AM')

    def test_validasi_dua_kali_tidak_menggandakan(self):
        self._upload()
        fo = FormOffline.objects.get()
        self._validasi(fo)
        self._validasi(fo)
        self.assertEqual(Maintenance.objects.count(), 1)

    def test_selain_am_tidak_bisa_validasi(self):
        self._upload()
        fo = FormOffline.objects.get()
        for u in (self.teknisi, _user('su_fo', 'viewer', superuser=True)):
            with self.subTest(user=u.username):
                self._validasi(fo, user=u)
                fo.refresh_from_db()
                self.assertEqual(fo.status, FormOffline.STATUS_MENUNGGU)
        self.assertFalse(Maintenance.objects.exists())

    def test_tolak_wajib_alasan_dan_tidak_terhitung(self):
        self._upload()
        fo = FormOffline.objects.get()
        self.client.force_login(self.am)
        url = reverse('offline_form_tolak', args=[fo.pk])

        self.client.post(url, {'alasan': '  '})
        fo.refresh_from_db()
        self.assertEqual(fo.status, FormOffline.STATUS_MENUNGGU)

        self.client.post(url, {'alasan': 'Berkas untuk RTU lain'})
        fo.refresh_from_db()
        self.assertEqual(fo.status, FormOffline.STATUS_DITOLAK)
        self.assertEqual(fo.alasan_tolak, 'Berkas untuk RTU lain')
        self.assertFalse(Maintenance.objects.exists())
        self.assertTrue(Notifikasi.objects.filter(
            user=self.teknisi, tipe='form_offline_hasil', pesan__contains='Berkas untuk RTU lain').exists())

    # ── batalkan ──────────────────────────────────────────────────────
    def test_pengunggah_bisa_membatalkan_selama_belum_divalidasi(self):
        self._upload()
        fo = FormOffline.objects.get()
        lain = _user('teknisi_lain2', 'technician')
        self.client.force_login(lain)
        self.client.post(reverse('offline_form_hapus', args=[fo.pk]))
        self.assertTrue(FormOffline.objects.exists())

        self.client.force_login(self.teknisi)
        self.client.post(reverse('offline_form_hapus', args=[fo.pk]))
        self.assertFalse(FormOffline.objects.exists())

    def test_yang_sudah_divalidasi_tidak_bisa_dibatalkan(self):
        self._upload()
        fo = FormOffline.objects.get()
        self._validasi(fo)
        self.client.force_login(self.teknisi)
        self.client.post(reverse('offline_form_hapus', args=[fo.pk]))
        self.assertTrue(FormOffline.objects.filter(pk=fo.pk).exists())

    # ── berkas ────────────────────────────────────────────────────────
    def test_akses_berkas(self):
        self._upload()
        fo = FormOffline.objects.get()
        url = reverse('offline_form_berkas', args=[fo.pk])
        lain = _user('teknisi_lain3', 'technician')

        self.client.force_login(lain)
        self.assertEqual(self.client.get(url).status_code, 404)     # belum divalidasi
        for u in (self.teknisi, self.am):
            self.client.force_login(u)
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp['Content-Type'], 'application/pdf')
            self.assertTrue(resp['Content-Disposition'].startswith('inline'))

        self._validasi(fo)
        self.client.force_login(lain)
        self.assertEqual(self.client.get(url).status_code, 200)     # sudah jadi catatan pemeliharaan

    def test_word_selalu_diunduh(self):
        self._upload(berkas=SimpleUploadedFile('form.docx', _docx()))
        fo = FormOffline.objects.get()
        resp = self.client.get(reverse('offline_form_berkas', args=[fo.pk]))
        self.assertTrue(resp['Content-Disposition'].startswith('attachment'))

    def test_pdf_pemeliharaan_menyajikan_berkas_asli(self):
        self._upload()
        fo = FormOffline.objects.get()
        self._validasi(fo)
        fo.refresh_from_db()
        resp = self.client.get(reverse('export_maintenance_pdf', args=[fo.maintenance.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b''.join(resp.streaming_content), PDF)

        detail = self.client.get(reverse('maintenance_view', args=[fo.maintenance.pk]))
        self.assertContains(detail, 'Validasi AM (Mengetahui)')
        self.assertContains(detail, 'Form PM RTU.pdf')

    # ── pengingat AM ──────────────────────────────────────────────────
    def test_badge_dan_pengingat_untuk_am(self):
        self._upload()
        self.client.force_login(self.am)
        resp = self.client.get(reverse('maintenance_approval'))
        self.assertEqual(resp.context['form_offline_menunggu_count'], 1)
        self.assertContains(resp, '1 form offline</strong> menunggu validasi')

        self.client.force_login(self.teknisi)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context['form_offline_menunggu_count'], 0)
