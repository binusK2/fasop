"""Tombol aksi form pemeliharaan: hanya Batal + Simpan.

"Cetak Formulir" dan "Simpan & Cetak PDF" dihapus karena tidak terpakai.
Ke-20 template per jenis perangkat kini memakai satu partial
(_tombol_aksi_form.html); tes ini membuka form create & edit tiap template
supaya tidak ada yang tertinggal memakai tombol lama.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, DeviceType, UserProfile

from .models import Maintenance
from .views import DEVICE_FORM_MAP


class TombolAksiFormTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(username='am_tombol', password='rahasia')
        profil, _ = UserProfile.objects.get_or_create(user=self.user)
        profil.role = 'asisten_manager'
        profil.force_password_change = False
        profil.save()
        self.client.force_login(self.user)

    def _jenis_per_template(self):
        jenis = ['JENIS TIDAK DIKENAL']                   # → maintenance_form.html generik
        terlihat = set()
        for nama, (_form, template) in DEVICE_FORM_MAP.items():
            if template not in terlihat:
                terlihat.add(template)
                jenis.append(nama)
        return jenis

    def _device(self, nama_jenis):
        jenis, _ = DeviceType.objects.get_or_create(name=nama_jenis)
        return Device.objects.create(nama=f'{nama_jenis}-01', jenis=jenis,
                                     merk='SEL', lokasi='GI TELLO')

    def _cek_tombol(self, resp, label_simpan, url_batal):
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'maintenance/_tombol_aksi_form.html')
        self.assertNotContains(resp, 'Cetak Formulir')
        self.assertNotContains(resp, 'Simpan &amp; Cetak')
        self.assertNotContains(resp, 'name="next"')
        self.assertNotContains(resp, 'blank-pdf/')
        self.assertContains(resp, label_simpan)
        self.assertContains(resp, f'<a href="{url_batal}" class="btn btn-outline-secondary btn-print-hide">')

    def test_form_baru_hanya_batal_dan_simpan(self):
        for nama_jenis in self._jenis_per_template():
            with self.subTest(jenis=nama_jenis):
                device = self._device(nama_jenis)
                resp = self.client.get(reverse('maintenance_add_device', args=[device.pk]))
                self._cek_tombol(resp, 'Simpan Maintenance', reverse('device_view', args=[device.pk]))

    def test_form_edit_hanya_batal_dan_simpan(self):
        for nama_jenis in self._jenis_per_template():
            with self.subTest(jenis=nama_jenis):
                device = self._device(nama_jenis)
                m = Maintenance.objects.create(device=device, maintenance_type='Preventive',
                                               date=timezone.now(), description='uji', status='Open')
                resp = self.client.get(reverse('maintenance_edit', args=[m.pk]))
                self._cek_tombol(resp, 'Simpan Perubahan', reverse('maintenance_view', args=[m.pk]))

    def test_batal_kembali_ke_halaman_asal(self):
        """Dibuka dari Jadwal Pemeliharaan → Batal kembali ke Jadwal, bukan
        ke detail perangkat (dulu tujuan Batal ditulis mati di tiap template)."""
        device = self._device('RTU')
        resp = self.client.get(reverse('maintenance_add_device', args=[device.pk]),
                               {'dari': '/jadwal/'})
        self.assertContains(resp, '<a href="/jadwal/" class="btn btn-outline-secondary btn-print-hide">')

    def test_simpan_tetap_kembali_ke_asal(self):
        """Cabang 'next=pdf' dihapus dari view — simpan selalu ke halaman asal."""
        device = self._device('JENIS TIDAK DIKENAL')
        resp = self.client.post(reverse('maintenance_add_device', args=[device.pk]), {
            'maintenance_type': 'Preventive',
            'date': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'description': 'uji',
            'status': 'Open',
            'pelaksana_names': '["Budi"]',
            'next': 'pdf',                               # sisa form lama di cache browser
        })
        self.assertRedirects(resp, reverse('maintenance_list'), fetch_redirect_response=False)
