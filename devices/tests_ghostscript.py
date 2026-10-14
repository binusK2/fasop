"""
Ghostscript dimatikan untuk Pillow (devices.apps.matikan_ghostscript).

Yang dijaga: EPS yang menyamar sebagai foto tidak pernah sampai ke interpreter
`gs`, di jalur mana pun FASOP membuka gambar unggahan. Semua tes memalsukan
`gs` seolah TERPASANG — di mesin tanpa Ghostscript tes ini akan lolos walau
penjaganya dicabut, padahal server produksi belum tentu sama.
"""
import base64
from io import BytesIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import EpsImagePlugin, Image

from devices.photo_utils import make_thumbnail

EPS = (
    b'%!PS-Adobe-3.0 EPSF-3.0\n'
    b'%%BoundingBox: 0 0 10 10\n'
    b'%%EndComments\n'
    b'newpath 0 0 moveto 10 10 lineto stroke\n'
    b'showpage\n'
    b'%%EOF\n'
)


class GhostscriptMatiTest(SimpleTestCase):
    def setUp(self):
        # check_call dipalsukan berhasil: tanpa penjaga, Pillow menyimpulkan
        # `gs --version` jalan lalu memanggil gs untuk merender EPS-nya.
        patcher = mock.patch.object(EpsImagePlugin.subprocess, 'check_call')
        self.gs = patcher.start()
        self.addCleanup(patcher.stop)

    def test_ghostscript_dimatikan_saat_startup(self):
        self.assertIs(EpsImagePlugin.gs_binary, False)
        self.assertFalse(EpsImagePlugin.has_ghostscript())

    def test_eps_ditolak_tanpa_memanggil_gs(self):
        im = Image.open(BytesIO(EPS))
        self.assertEqual(im.format, 'EPS')  # dikenali dari isinya...
        with self.assertRaises(OSError):
            im.load()                        # ...tapi tidak dirender
        self.gs.assert_not_called()

    def test_thumbnail_foto_eps_dilewati(self):
        """Foto lapangan: EPS bernama .jpg → tanpa thumbnail, bukan gs."""
        foto = SimpleUploadedFile('foto.jpg', EPS, content_type='image/jpeg')
        self.assertIsNone(make_thumbnail(foto))
        self.gs.assert_not_called()

    def test_pdf_dengan_eps_tidak_memanggil_gs(self):
        """Eviden BA di-embed sebagai data URI dengan mime dari nama berkas."""
        import weasyprint
        uri = 'data:image/jpeg;base64,' + base64.b64encode(EPS).decode()
        pdf = weasyprint.HTML(string=f'<p>BA</p><img src="{uri}">').write_pdf()
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.gs.assert_not_called()
