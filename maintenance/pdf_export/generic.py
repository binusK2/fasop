"""
pdf_export/generic.py
Fallback PDF untuk jenis perangkat yang belum memiliki modul spesifik.
"""
from reportlab.lib.units import mm
from reportlab.platypus import Table
from ._base import _p, _val, _grid, _sec, _draw, CW, ML


def render(c, y, data):
    y -= 2*mm
    y = _draw(c, _sec('II.  CATATAN PEMELIHARAAN'), ML, y)
    y -= 0.5*mm
    cat = data.get('catatan_tambahan', '')
    ct = Table([[_p(_val(cat), 7.5)]], colWidths=[CW])
    ct.setStyle(_grid([('MINROWHEIGHT', (0,0),(-1,-1), 18*mm)]))
    y = _draw(c, ct, ML, y)
    return y
