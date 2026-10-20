"""
Tes favicon per bagian aplikasi.

OPSIS punya favicon sendiri (static/favicon/opsis/) supaya tab-nya bisa
dibedakan dari FASOP di layar ruang kontrol yang membuka banyak tab sekaligus.
Device Monitor dan Kinerja SCADATEL tetap memakai favicon FASOP. Ketiganya
punya template dasar sendiri yang tidak meng-extend devices/base.html, jadi
favicon yang lupa dipasang tidak memunculkan error apa pun — tab-nya cuma
kosong.
"""

import pathlib
import re

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

AKAR = pathlib.Path(__file__).resolve().parent.parent

BASE_OPSIS = (
    'opsis/templates/opsis/opsis_base.html',
    'opsis/templates/opsis/pemeliharaan.html',
)
BASE_FASOP = (
    'devices/templates/base.html',
    'device_mon/templates/device_mon/base.html',
    'up2bmakassar/templates/up2bmakassar/base.html',
)

RE_FAVICON = re.compile(r"""\{% static '(favicon/[^']+)' %\}""")


def _favicon(path):
    return RE_FAVICON.findall((AKAR / path).read_text(encoding='utf-8'))


class FaviconTest(SimpleTestCase):
    def test_opsis_memakai_favicon_opsis(self):
        for f in BASE_OPSIS:
            with self.subTest(base=f):
                ikon = _favicon(f)
                self.assertIn('favicon/opsis/favicon-32x32.png', ikon)
                self.assertTrue(all(i.startswith('favicon/opsis/') for i in ikon), ikon)

    def test_device_mon_dan_kinerja_memakai_favicon_fasop(self):
        for f in BASE_FASOP:
            with self.subTest(base=f):
                ikon = _favicon(f)
                self.assertIn('favicon/favicon-32x32.png', ikon)
                self.assertFalse(any(i.startswith('favicon/opsis/') for i in ikon), ikon)

    def test_berkas_favicon_yang_dirujuk_ada(self):
        for f in BASE_OPSIS + BASE_FASOP:
            for ikon in _favicon(f):
                with self.subTest(base=f, ikon=ikon):
                    self.assertTrue(finders.find(ikon), f'{ikon} tidak ditemukan di static')
