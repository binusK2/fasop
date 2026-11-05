"""TTD massal di halaman Approval — hanya role Asisten Manager.

Daftar di layar bisa basi (AM lain sudah menandatangani, pemeliharaan dibuka
kembali), jadi syarat "Done & belum TTD" diperiksa ulang di server; id dari
browser hanya memilih baris.
"""
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditlog.models import AuditLog
from devices.models import Device, DeviceType, UserProfile
from fasop.hashids_helper import encode

from .models import Maintenance


def _user(username, role, superuser=False):
    if superuser:
        u = User.objects.create_superuser(username=username, password='rahasia')
    else:
        u = User.objects.create_user(username=username, password='rahasia')
    profil, _ = UserProfile.objects.get_or_create(user=u)
    profil.role = role
    profil.force_password_change = False
    profil.save()
    return u


class TtdMassalTests(TestCase):

    def setUp(self):
        self.am = _user('am_massal', 'asisten_manager')
        self.client.force_login(self.am)

        jenis = DeviceType.objects.create(name='RTU')
        self.device = Device.objects.create(nama='RTU-01', jenis=jenis,
                                            merk='SEL', lokasi='GI TELLO')
        self.url = reverse('maintenance_bulk_sign')
        self.url_approval = reverse('maintenance_approval')

    def _m(self, status='Done', **kw):
        return Maintenance.objects.create(
            device=self.device, maintenance_type='Preventive',
            date=timezone.now(), description='uji', status=status, **kw)

    def _kirim(self, *maintenances, ids=None):
        if ids is None:
            ids = [encode(m.pk) for m in maintenances]
        return self.client.post(self.url, {'ids': ids})

    def _pesan(self, resp):
        return [str(m) for m in get_messages(resp.wsgi_request)]

    def test_menandatangani_semua_yang_dipilih(self):
        a, b = self._m(), self._m()
        resp = self._kirim(a, b)

        self.assertRedirects(resp, self.url_approval + '?tab=pending',
                             fetch_redirect_response=False)
        for m in (a, b):
            m.refresh_from_db()
            self.assertEqual(m.signed_by, self.am)
            self.assertIsNotNone(m.signed_at)
        self.assertIn('2 laporan pemeliharaan berhasil ditandatangani.', self._pesan(resp))
        self.assertEqual(
            AuditLog.objects.filter(action='sign', object_id__in=[a.pk, b.pk]).count(), 2)

    def test_yang_tidak_dipilih_tidak_ikut(self):
        dipilih, tidak = self._m(), self._m()
        self._kirim(dipilih)
        tidak.refresh_from_db()
        self.assertIsNone(tidak.signed_by)

    def test_syarat_diperiksa_ulang_di_server(self):
        """Belum Done, sudah di-TTD AM lain, atau sudah dihapus → dilewati."""
        am_lain = _user('am_lain', 'asisten_manager')
        waktu_lama = timezone.now() - timezone.timedelta(days=3)
        open_ = self._m(status='Open')
        sudah = self._m(signed_by=am_lain, signed_at=waktu_lama)
        terhapus = self._m(is_deleted=True)
        sah = self._m()

        resp = self._kirim(open_, sudah, terhapus, sah)

        sah.refresh_from_db()
        self.assertEqual(sah.signed_by, self.am)
        open_.refresh_from_db()
        self.assertIsNone(open_.signed_by)
        sudah.refresh_from_db()
        self.assertEqual((sudah.signed_by, sudah.signed_at), (am_lain, waktu_lama))
        self.assertIsNone(Maintenance.semua_objects.get(pk=terhapus.pk).signed_by)

        pesan = self._pesan(resp)
        self.assertIn('1 laporan pemeliharaan berhasil ditandatangani.', pesan)
        self.assertTrue(any(p.startswith('3 laporan dilewati') for p in pesan), pesan)

    def test_selain_am_ditolak(self):
        m = self._m()
        for u in (_user('teknisi_massal', 'technician'),
                  _user('su_massal', 'viewer', superuser=True)):
            with self.subTest(user=u.username):
                self.client.force_login(u)
                self._kirim(m)
                m.refresh_from_db()
                self.assertIsNone(m.signed_by)

    def test_tanpa_pilihan_atau_id_rusak(self):
        m = self._m()
        for ids in ([], ['bukan-hashid', str(m.pk)]):
            with self.subTest(ids=ids):
                resp = self._kirim(ids=ids)
                self.assertIn('Pilih minimal satu pemeliharaan yang akan ditandatangani.',
                              self._pesan(resp))
        m.refresh_from_db()
        self.assertIsNone(m.signed_by)

    def test_get_ditolak(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_halaman_approval_menampilkan_pilihan_untuk_am(self):
        m = self._m()
        resp = self.client.get(self.url_approval, {'tab': 'pending'})
        self.assertContains(resp, 'id="form-ttd-massal"')
        # Nilai checkbox memakai hashid, bukan PK mentah (konvensi FASOP)
        self.assertContains(resp, f'value="{encode(m.pk)}" aria-label="Pilih {self.device.nama}"')
        self.assertContains(resp, 'TTD Terpilih')

    def test_halaman_approval_tanpa_pilihan_untuk_superuser_bukan_am(self):
        """Superuser boleh membuka Approval, tapi TTD (tunggal maupun massal)
        tetap hanya untuk AM — tombolnya tidak ditawarkan."""
        self._m()
        self.client.force_login(_user('su_lihat', 'viewer', superuser=True))
        resp = self.client.get(self.url_approval, {'tab': 'pending'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'form-ttd-massal')
        self.assertNotContains(resp, 'TTD Terpilih')

    def test_peringatan_bila_belum_ada_gambar_ttd(self):
        self._m()
        resp = self.client.get(self.url_approval, {'tab': 'pending'})
        self.assertContains(resp, 'Gambar tanda tangan Anda belum diunggah')
