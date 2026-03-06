"""
pdf_export/__init__.py
Entry point utama — dipanggil dari views.py:
    from maintenance.pdf_export import build_pdf

Dispatcher: memilih modul per jenis perangkat, lalu memanggil render().
"""

from reportlab.pdfgen import canvas as rl_canvas

from ._base import (
    W, H, ML, MT,
    draw_header, draw_info, draw_pengesahan, draw_footer,
)

# Import semua modul device
from . import router
from . import plc
from . import radio
from . import voip
from . import multiplexer
from . import rectifier
from . import generic


# Mapping jenis perangkat → modul
_DEVICE_MAP = {
    'ROUTER':      router,
    'SWITCH':      router,       # Router dan Switch pakai modul yang sama
    'PLC':         plc,
    'RADIO':       radio,
    'VOIP':        voip,
    'MULTIPLEXER': multiplexer,
    'RECTIFIER':   rectifier,
    'CATU DAYA':   rectifier,
    'CATUDAYA':    rectifier,
    'RECTIFIER & BATTERY': rectifier,
}


def build_pdf(data: dict, output_path):
    """
    Generate PDF laporan pemeliharaan.

    Args:
        data        : dict berisi 'info', 'device_kind', dan data detail perangkat
        output_path : string path file atau BytesIO object
    """
    c = rl_canvas.Canvas(output_path, pagesize=(W, H))
    c.setTitle('Laporan Pemeliharaan FASOP')
    c.setAuthor('UP2B Sistem Makassar')

    info = data.get('info', {})
    kind = data.get('device_kind', 'GENERIC').strip().upper()

    # ── Header ──────────────────────────────────────────────────────
    y = draw_header(c, kind)

    # ── I. Informasi Pemeliharaan ────────────────────────────────────
    y = draw_info(c, y, info)

    # ── Konten detail sesuai jenis perangkat ─────────────────────────
    module = _DEVICE_MAP.get(kind, generic)
    y = module.render(c, y, data)

    # ── Pengesahan TTD ───────────────────────────────────────────────
    y = draw_pengesahan(c, y, info, signatures=data.get('signatures'))

    # ── Footer ──────────────────────────────────────────────────────
    draw_footer(c)

    c.save()
