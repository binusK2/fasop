"""
Tes popup konfirmasi bersama (devices/templates/_popup_js.html).

Puluhan tombol hapus/akhiri/selesai memanggil fasopConfirm()/confirmSubmit().
Kalau fungsi itu tidak terdefinisi di sebuah halaman, tombolnya diam total —
ReferenceError-nya hanya tercetak di console. Itu pernah terjadi ketika
popup-nya masih berkas statis (static/js/popup.js) yang tidak ikut terserve.
"""

import pathlib
import re

from django.template.loader import render_to_string
from django.test import SimpleTestCase

AKAR = pathlib.Path(__file__).resolve().parent.parent

BASE_POPUP = (
    'devices/templates/base.html',
    'opsis/templates/opsis/opsis_base.html',
)

FUNGSI = ('fasopConfirm', 'fasopAlert', 'fasopPrompt', 'confirmSubmit', 'confirmNav')


def _template_proyek():
    for p in AKAR.rglob('templates/**/*.html'):
        bagian = p.relative_to(AKAR).parts
        if bagian[0] in ('venv', '.venv', 'staticfiles', 'node_modules'):
            continue
        yield p


class PopupBersamaTest(SimpleTestCase):
    def test_base_meng_include_popup_inline(self):
        for f in BASE_POPUP:
            with self.subTest(base=f):
                isi = (AKAR / f).read_text(encoding='utf-8')
                self.assertIn('{% include "_popup_js.html" %}', isi)
                # Popup tidak boleh kembali bergantung pada berkas statis
                # yang bisa tidak terserve (collectstatic terlewat, cache CDN).
                self.assertNotIn('js/popup.js', isi)

    def test_partial_mendefinisikan_semua_fungsi(self):
        html = render_to_string('_popup_js.html')
        for nama in FUNGSI:
            with self.subTest(fungsi=nama):
                self.assertIn(f'global.{nama} = {nama};', html)
        # Komentar multi-baris harus {% comment %}, bukan {# #}, supaya tidak
        # bocor jadi teks di setiap halaman.
        self.assertNotIn('{#', html)
        self.assertNotIn('comment %}', html)

    def test_jalur_cadangan_tanpa_bootstrap(self):
        """Bootstrap dari CDN gagal dimuat → dialog bawaan browser, bukan tombol mati."""
        html = render_to_string('_popup_js.html')
        self.assertIn('global.confirm(message)', html)
        self.assertIn('global.alert(message)', html)
        self.assertIn('global.prompt(message', html)

    def test_pemakai_popup_meng_extend_base_yang_memuatnya(self):
        """Template yang memanggil popup harus berada di bawah base yang memuatnya."""
        pola_fungsi = re.compile(r'\b(' + '|'.join(FUNGSI) + r')\(')
        pola_extends = re.compile(r'{%\s*extends\s+["\']([^"\']+)["\']')
        base_ok = {'base.html', 'opsis/opsis_base.html'}
        for p in _template_proyek():
            if p.name == '_popup_js.html':
                continue
            isi = p.read_text(encoding='utf-8', errors='ignore')
            if not pola_fungsi.search(isi):
                continue
            m = pola_extends.search(isi)
            if not m:
                # Partial yang di-include halaman lain (mis. komponen_section).
                continue
            with self.subTest(template=str(p.relative_to(AKAR))):
                self.assertIn(m.group(1), base_ok)
