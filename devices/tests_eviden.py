"""Tes hapus Eviden Tambahan di Device Detail.

Dulu tombol hapus eviden hanya untuk superuser dan langsung menghapus baris
beserta berkas fotonya (tanpa jalan pulih). Sekarang Teknisi juga boleh
menghapus, sehingga hapusnya dijadikan SOFT-DELETE seperti Peralatan &
Pemeliharaan: baris ditandai is_deleted, berkas tetap ada, dan bisa dipulihkan
dari site admin. Berkas baru dibuang saat baris dihapus permanen dari admin.
"""
import io
import os
import shutil
import tempfile

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Device, DeviceEviden, DeviceType, UserProfile

MEDIA_TES = tempfile.mkdtemp(prefix='fasop_tes_eviden_')


def _png():
    buf = io.BytesIO()
    Image.new('RGB', (4, 4), (200, 30, 30)).save(buf, format='PNG')
    return SimpleUploadedFile('eviden.png', buf.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=MEDIA_TES)
class HapusEvidenTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TES, ignore_errors=True)

    def _user(self, username, role=None, superuser=False):
        if superuser:
            u = User.objects.create_superuser(username=username, password='rahasia')
        else:
            u = User.objects.create_user(username=username, password='rahasia')
        p, _ = UserProfile.objects.get_or_create(user=u)
        if role:
            p.role = role
        p.force_password_change = False
        p.save()
        return u

    def setUp(self):
        self.teknisi = self._user('teknisi', 'technician')
        self.viewer = self._user('viewer', 'viewer')
        self.device = Device.objects.create(
            nama='ROUTER GI TELLO', merk='X', lokasi='GI TELLO',
            jenis=DeviceType.objects.create(name='ROUTER'))
        self.ev = DeviceEviden.objects.create(
            device=self.device, foto=_png(), keterangan='Panel depan',
            uploaded_by=self.teknisi)
        self.path_foto = self.ev.foto.path

    def _url_hapus(self, ev=None):
        return reverse('device_eviden_delete',
                       kwargs={'pk': self.device.pk, 'eviden_pk': (ev or self.ev).pk})

    def _detail(self):
        resp = self.client.get(reverse('device_view', kwargs={'pk': self.device.pk}))
        self.assertEqual(resp.status_code, 200)
        return resp

    # ── Teknisi boleh menghapus, dan hapusnya soft-delete ──────────────
    def test_teknisi_bisa_hapus_eviden(self):
        self.client.force_login(self.teknisi)
        resp = self.client.post(self._url_hapus())
        self.assertEqual(resp.status_code, 302)
        self.ev.refresh_from_db()
        self.assertTrue(self.ev.is_deleted)
        self.assertEqual(self.ev.deleted_by, self.teknisi)
        self.assertIsNotNone(self.ev.deleted_at)

    def test_soft_delete_tidak_membuang_berkas(self):
        """Berkas wajib tetap ada — tanpanya aksi Pulihkan di admin tidak berarti apa-apa."""
        self.client.force_login(self.teknisi)
        self.client.post(self._url_hapus())
        self.assertTrue(DeviceEviden.objects.filter(pk=self.ev.pk).exists())
        self.assertTrue(os.path.isfile(self.path_foto))

    def test_eviden_terhapus_hilang_dari_device_detail(self):
        lain = DeviceEviden.objects.create(device=self.device, foto=_png())
        self.client.force_login(self.teknisi)
        self.client.post(self._url_hapus())
        self.assertEqual(list(self._detail().context['eviden_list']), [lain])

    def test_superuser_juga_soft_delete(self):
        self.client.force_login(self._user('admin', superuser=True))
        self.client.post(self._url_hapus())
        self.ev.refresh_from_db()
        self.assertTrue(self.ev.is_deleted)
        self.assertTrue(os.path.isfile(self.path_foto))

    def test_hapus_dicatat_di_audit_log(self):
        from auditlog.models import AuditLog
        self.client.force_login(self.teknisi)
        self.client.post(self._url_hapus())
        log = AuditLog.objects.get(model_name='Eviden Tambahan')
        self.assertEqual(log.user, self.teknisi)
        self.assertEqual(log.action, 'delete')
        self.assertEqual(log.object_id, self.ev.pk)

    # ── Yang tidak boleh ───────────────────────────────────────────────
    def test_viewer_ditolak(self):
        self.client.force_login(self.viewer)
        resp = self.client.post(self._url_hapus())
        self.assertEqual(resp.status_code, 403)
        self.ev.refresh_from_db()
        self.assertFalse(self.ev.is_deleted)

    def test_get_tidak_menghapus(self):
        self.client.force_login(self.teknisi)
        self.client.get(self._url_hapus())
        self.ev.refresh_from_db()
        self.assertFalse(self.ev.is_deleted)

    def test_eviden_perangkat_lain_404(self):
        lain = Device.objects.create(nama='MUX GI BONTOALA', merk='Y',
                                     lokasi='GI BONTOALA', jenis=self.device.jenis)
        url = reverse('device_eviden_delete',
                      kwargs={'pk': lain.pk, 'eviden_pk': self.ev.pk})
        self.client.force_login(self.teknisi)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.ev.refresh_from_db()
        self.assertFalse(self.ev.is_deleted)

    # ── Tombol di Device Detail ────────────────────────────────────────
    def test_tombol_hapus_tampil_untuk_teknisi(self):
        self.client.force_login(self.teknisi)
        self.assertContains(self._detail(), self._url_hapus())

    def test_tombol_hapus_tidak_tampil_untuk_viewer(self):
        self.client.force_login(self.viewer)
        self.assertNotContains(self._detail(), self._url_hapus())

    # ── Pemulihan & hapus permanen dari site admin ─────────────────────
    def test_admin_pulihkan(self):
        self.client.force_login(self.teknisi)
        self.client.post(self._url_hapus())
        model_admin = admin_site._registry[DeviceEviden]
        request = RequestFactory().post('/')
        request.user = self._user('admin', superuser=True)
        model_admin.message_user = lambda *a, **k: None
        model_admin.pulihkan_data(request, DeviceEviden.objects.all())
        self.ev.refresh_from_db()
        self.assertFalse(self.ev.is_deleted)
        self.assertIsNone(self.ev.deleted_by)
        self.assertIsNone(self.ev.deleted_at)
        self.assertIn(self.ev, self._detail().context['eviden_list'])

    def test_hapus_permanen_membuang_berkas(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.ev.delete()
        self.assertFalse(os.path.isfile(self.path_foto))
