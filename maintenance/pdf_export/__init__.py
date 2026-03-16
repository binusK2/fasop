"""
pdf_export/__init__.py  —  Entry point.
Dipanggil dari views.py: from maintenance.pdf_export import build_pdf
"""
from reportlab.pdfgen import canvas as rl_canvas
from ._base import (W, H, ML, MT, draw_header, draw_info, draw_pengesahan, draw_footer)
from . import router, plc, radio, voip, multiplexer, rectifier, generic

_MAP = {
    'ROUTER': router, 'SWITCH': router,
    'PLC': plc, 'RADIO': radio, 'VOIP': voip,
    'MULTIPLEXER': multiplexer,
    'RECTIFIER': rectifier,
    'CATU DAYA': rectifier, 'CATUDAYA': rectifier,
    'RECTIFIER & BATTERY': rectifier,
}

def build_pdf(data: dict, output_path):
    c = rl_canvas.Canvas(output_path, pagesize=(W, H))
    c.setTitle('Laporan Pemeliharaan FASOP')
    c.setAuthor('UP2B Sistem Makassar')
    info = data.get('info', {})
    kind = data.get('device_kind', 'GENERIC').strip().upper()
    y = draw_header(c, kind)
    y = draw_info(c, y, info)
    y = _MAP.get(kind, generic).render(c, y, data)
    y = draw_pengesahan(c, y, info, signatures=data.get('signatures'))
    draw_footer(c,
                print_by=data.get('print_by', ''),
                print_date=data.get('print_date', ''))
    c.save()