"""Tes upload file Berita Acara.

`ba_upload` menyimpan lewat `objects.create()`, yang TIDAK menjalankan
validator field. Validator ekstensi sudah lama ada di model, tapi tidak pernah
dipanggil — file .exe pernah berhasil diunggah sebagai BA.
"""
import io
import shutil
import tempfile
import zipfile
from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from devices.models import UserProfile

from .models import BeritaAcaraRecord, validate_ba_file_ekstensi, validate_ba_file_isi

PDF = b'%PDF-1.4\n%dummy\n'
EXE = b'MZ\x90\x00\x03\x00\x00\x00' + b'\x00' * 64


def _docx():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<Types/>')
        zf.writestr('word/document.xml', '<w:document/>')
    return buf.getvalue()


MEDIA_UJI = tempfile.mkdtemp(prefix='fasop_ba_upload_')


@override_settings(MEDIA_ROOT=MEDIA_UJI)
class BaUploadEkstensiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_UJI, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_superuser(username='admin', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)
        self._nomor = 0

    def _upload(self, nama, isi):
        self._nomor += 1
        return self.client.post(reverse('ba_upload'), {
            'jenis': 'lainnya',
            'nomor_ba': str(self._nomor),
            'tanggal': date.today().isoformat(),
            'pelaksana': 'Uji',
            'file_upload': SimpleUploadedFile(nama, isi),
        })

    def test_exe_ditolak(self):
        resp = self._upload('virus.exe', EXE)
        self.assertEqual(resp.status_code, 200)  # form dirender ulang dengan error
        self.assertEqual(BeritaAcaraRecord.objects.count(), 0)
        self.assertContains(resp, 'tidak diizinkan')

    def test_exe_disamarkan_jadi_pdf_ditolak(self):
        self._upload('ba.pdf', EXE)
        self.assertEqual(BeritaAcaraRecord.objects.count(), 0)

    def test_gambar_dan_excel_ditolak(self):
        for nama in ('scan.jpg', 'scan.png', 'data.xlsx', 'halaman.html'):
            with self.subTest(nama=nama):
                self._upload(nama, b'apa saja')
        self.assertEqual(BeritaAcaraRecord.objects.count(), 0)

    def test_pdf_diterima(self):
        resp = self._upload('ba.pdf', PDF)
        self.assertRedirects(resp, reverse('ba_list'), fetch_redirect_response=False)
        self.assertEqual(BeritaAcaraRecord.objects.count(), 1)

    def test_docx_diterima(self):
        self._upload('ba.docx', _docx())
        self.assertEqual(BeritaAcaraRecord.objects.count(), 1)

    def test_doc_diterima(self):
        self._upload('ba.doc', b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 64)
        self.assertEqual(BeritaAcaraRecord.objects.count(), 1)

    def test_zip_biasa_berekstensi_docx_ditolak(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('payload.exe', EXE)
        self._upload('ba.docx', buf.getvalue())
        self.assertEqual(BeritaAcaraRecord.objects.count(), 0)

    def test_preview_non_pdf_dipaksa_unduhan(self):
        """BA lama berformat lain tidak boleh dirender inline dari origin FASOP."""
        rec = BeritaAcaraRecord.objects.create(
            jenis='lainnya', nomor_ba='X', tanggal=date.today(), pelaksana='Uji',
            rows_data=[], file_upload=SimpleUploadedFile('lama.html', b'<script>1</script>'),
        )
        resp = self.client.get(reverse('ba_preview', kwargs={'pk': rec.pk}))
        self.assertIn('attachment', resp.get('Content-Disposition', ''))

    def test_preview_pdf_tetap_inline(self):
        rec = BeritaAcaraRecord.objects.create(
            jenis='lainnya', nomor_ba='Y', tanggal=date.today(), pelaksana='Uji',
            rows_data=[], file_upload=SimpleUploadedFile('ba.pdf', PDF),
        )
        resp = self.client.get(reverse('ba_preview', kwargs={'pk': rec.pk}))
        self.assertNotIn('attachment', resp.get('Content-Disposition', ''))
        self.assertEqual(resp['Content-Type'], 'application/pdf')


class BaValidatorFileLamaTests(TestCase):
    """BA lama (JPG/XLSX, diizinkan dulu) harus tetap bisa disunting dari Admin."""

    def test_file_tersimpan_dilewati(self):
        class FileLama:
            name = 'ba_upload/lama.jpg'
            _committed = True
        validate_ba_file_ekstensi(FileLama())
        validate_ba_file_isi(FileLama())

    def test_unggahan_baru_tetap_diperiksa(self):
        with self.assertRaises(ValidationError):
            validate_ba_file_ekstensi(SimpleUploadedFile('lama.jpg', b'x'))
