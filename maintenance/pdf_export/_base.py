"""
pdf_export/_base.py
Konstanta, helper functions, header/footer, dan pengesahan TTD.
Digunakan oleh semua modul device-specific.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import Table, TableStyle, Paragraph
import os

W, H = A4   # 595.28 × 841.89 pt

# ── Warna ────────────────────────────────────────────────────────────
C_BLUE_DARK  = colors.HexColor('#1A3A5C')
C_BLUE_MID   = colors.HexColor('#2563EB')
C_RED        = colors.HexColor('#DC2626')
C_GRAY_HEAD  = colors.HexColor('#F1F5F9')
C_GRAY_LINE  = colors.HexColor('#CBD5E1')
C_GRAY_TXT   = colors.HexColor('#64748B')
C_BLACK      = colors.HexColor('#0F172A')
C_GREEN_BG   = colors.HexColor('#DCFCE7')
C_GREEN_TXT  = colors.HexColor('#166534')
C_RED_BG     = colors.HexColor('#FEE2E2')
C_RED_TXT    = colors.HexColor('#991B1B')
C_ORANGE_BG  = colors.HexColor('#FEF9C3')
C_ORANGE_TXT = colors.HexColor('#854D0E')
C_WHITE      = colors.white

# ── Path logo ────────────────────────────────────────────────────────
_HERE      = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH  = os.path.join(_HERE, '..', '..', 'static', 'img', 'pln_logo.png')
LOGO_PETIR = os.path.join(_HERE, '..', '..', 'static', 'img', 'pln_logo_conv.png')

# ── Margin ───────────────────────────────────────────────────────────
ML = 15*mm; MR = 15*mm; MT = 14*mm; MB = 12*mm
CW = W - ML - MR


# ── Helper: Paragraph ────────────────────────────────────────────────
def _p(text, size=8, bold=False, color=C_BLACK, align=TA_LEFT, leading=None):
    return Paragraph(str(text) if text is not None else '-', ParagraphStyle(
        'x', fontSize=size,
        fontName='Helvetica-Bold' if bold else 'Helvetica',
        textColor=color, alignment=align,
        leading=leading or size * 1.35,
        spaceAfter=0, spaceBefore=0,
    ))

def _val(v):
    if v is None or str(v).strip() == '': return '-'
    return str(v)

def _sc(val):
    """Status cell — OK hijau, NOK merah, lainnya abu."""
    v = (val or '').strip().upper()
    if v in ('OK', 'UP', 'BAIK', 'NORMAL'):
        return _p(v, 7.5, True, C_GREEN_TXT, TA_CENTER)
    elif v in ('NOK', 'DOWN', 'RUSAK', 'ABNORMAL'):
        return _p(v, 7.5, True, C_RED_TXT, TA_CENTER)
    elif v == 'N/A':
        return _p('N/A', 7.5, False, C_GRAY_TXT, TA_CENTER)
    return _p(_val(v), 7.5, False, C_GRAY_TXT, TA_CENTER)

def _sbg(val):
    """Background warna sesuai status."""
    v = (val or '').strip().upper()
    if v in ('OK', 'UP', 'BAIK', 'NORMAL'):   return C_GREEN_BG
    if v in ('NOK', 'DOWN', 'RUSAK', 'ABNORMAL'): return C_RED_BG
    if v == 'N/A':                              return C_ORANGE_BG
    return C_WHITE


# ── Table style default ──────────────────────────────────────────────
_BS = [
    ('BOX',           (0,0),(-1,-1), 0.4, C_GRAY_LINE),
    ('INNERGRID',     (0,0),(-1,-1), 0.3, C_GRAY_LINE),
    ('TOPPADDING',    (0,0),(-1,-1), 2),
    ('BOTTOMPADDING', (0,0),(-1,-1), 2),
    ('LEFTPADDING',   (0,0),(-1,-1), 4),
    ('RIGHTPADDING',  (0,0),(-1,-1), 3),
    ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ('FONTSIZE',      (0,0),(-1,-1), 7.5),
    ('FONTNAME',      (0,0),(-1,-1), 'Helvetica'),
]

def _grid(extra=None):
    s = list(_BS)
    if extra: s += extra
    return TableStyle(s)

def _sec(title, w=None):
    """Section header bar biru gelap."""
    t = Table([[_p(title, 7.5, True, C_WHITE)]], colWidths=[w or CW])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), C_BLUE_DARK),
        ('TOPPADDING',    (0,0),(-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3.5),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
    ]))
    return t

def _draw(c, tbl, x, y):
    """Draw table di canvas, return y baru."""
    w, h = tbl.wrapOn(c, CW, H)
    tbl.drawOn(c, x, y - h)
    return y - h


# ── Header halaman (gaya form resmi PLN) ─────────────────────────────
def draw_header(c, kind):
    """
    Gambar header di atas halaman.
    Returns: y (posisi awal konten di bawah header)
    """
    HDR_H  = 14*mm
    logo_y = H - MT - HDR_H

    # Logo petir PLN (kanan)
    petir = os.path.normpath(LOGO_PETIR)
    if os.path.exists(petir):
        lh2 = HDR_H - 2*mm
        lw2 = lh2 * (474/714)
        c.drawImage(petir, W-MR-lw2, logo_y+1*mm,
                    width=lw2, height=lh2,
                    preserveAspectRatio=True, mask='auto')
        txt_rx = W - MR - lw2 - 2*mm
    else:
        txt_rx = W - MR

    c.setFont('Helvetica-Bold', 7)
    c.setFillColor(C_BLUE_DARK)
    c.drawRightString(txt_rx, logo_y+HDR_H-5*mm,  'UIP3B SULAWESI')
    c.drawRightString(txt_rx, logo_y+HDR_H-10*mm, 'UP2B SISTEM MAKASSAR')

    # Garis atas & bawah header
    c.setStrokeColor(C_BLACK); c.setLineWidth(0.6)
    c.line(ML, logo_y+HDR_H, W-MR, logo_y+HDR_H)
    c.line(ML, logo_y,       W-MR, logo_y)

    # Judul formulir sesuai jenis perangkat
    _titles = {
        'ROUTER':      'Formulir Pemeliharaan Peralatan Router',
        'SWITCH':      'Formulir Pemeliharaan Peralatan Switch',
        'PLC':         'Formulir Pemeliharaan Peralatan PLC',
        'RADIO':       'Formulir Pemeliharaan Peralatan Radio Komunikasi',
        'VOIP':        'Formulir Pemeliharaan Peralatan VoIP',
        'MULTIPLEXER': 'Formulir Pemeliharaan Peralatan Multiplexer',
        'RECTIFIER':   'Formulir Pemeliharaan Peralatan Rectifier dan Battery',
        'CATU DAYA':   'Formulir Pemeliharaan Peralatan Rectifier dan Battery',
        'CATUDAYA':    'Formulir Pemeliharaan Peralatan Rectifier dan Battery',
    }
    c.setFont('Helvetica-Bold', 9)
    c.setFillColor(C_BLACK)
    c.drawCentredString(W/2, logo_y+HDR_H/2-3,
                        _titles.get(kind, 'Formulir Pemeliharaan Peralatan FASOP'))

    # Garis merah bawah (seperti form asli)
    c.setStrokeColor(C_RED); c.setLineWidth(1.0)
    c.line(ML, logo_y, W-MR, logo_y)

    return logo_y - 2*mm


# ── Tabel informasi pemeliharaan ─────────────────────────────────────
def draw_info(c, y, info):
    """Gambar section I: Informasi Pemeliharaan."""
    y = _draw(c, _sec('I.  INFORMASI PEMELIHARAAN'), ML, y)
    y -= 0.5*mm

    LW = 32*mm
    VW = CW/2 - LW

    def ir(l1, v1, l2, v2):
        return [_p(l1,7.5,True), _p(_val(v1),7.5),
                _p(l2,7.5,True), _p(_val(v2),7.5)]

    jenis_merk = ' / '.join(filter(None, [
        str(info.get('device_type') or '').strip(),
        str(info.get('brand') or '').strip()
    ])) or '-'

    rows = [
        ir('Nama Perangkat', info.get('device_name'),
           'Jenis / Merk',   jenis_merk),
        ir('Lokasi',         info.get('lokasi'),
           'IP Address',     info.get('ip_address')),
        ir('No. Seri',       info.get('serial_number'),
           'Tgl. Pemeliharaan', info.get('date')),
        ir('Jenis Kegiatan', info.get('maintenance_type'),
           'Pelaksana',      info.get('technician')),
        ir('Status Perangkat', info.get('status'), '', ''),
    ]

    itbl = Table(rows, colWidths=[LW, VW, LW, VW])
    itbl.setStyle(_grid([
        ('BACKGROUND', (0,0),(0,-1), C_GRAY_HEAD),
        ('BACKGROUND', (2,0),(2,-1), C_GRAY_HEAD),
        ('FONTNAME',   (0,0),(0,-1), 'Helvetica-Bold'),
        ('FONTNAME',   (2,0),(2,-1), 'Helvetica-Bold'),
        ('SPAN',       (2,4),(3,4)),
        ('BACKGROUND', (2,4),(3,4), C_WHITE),
    ]))
    y = _draw(c, itbl, ML, y)

    # Deskripsi/keluhan (jika ada)
    desc = (info.get('description') or '').strip()
    if desc:
        dt = Table(
            [[_p('Deskripsi / Keluhan:', 7.5, True), _p(desc, 7.5)]],
            colWidths=[LW, CW-LW]
        )
        dt.setStyle(_grid([('BACKGROUND',(0,0),(0,0), C_GRAY_HEAD)]))
        y = _draw(c, dt, ML, y)

    return y


# ── Footer halaman ───────────────────────────────────────────────────
def draw_footer(c):
    fy = MB + 3*mm
    c.setStrokeColor(colors.HexColor('#94A3B8')); c.setLineWidth(0.5)
    c.line(ML, fy+4*mm, W-MR, fy+4*mm)
    c.setFont('Helvetica', 6); c.setFillColor(C_GRAY_TXT)
    c.drawString(ML, fy+1.5*mm,
        'Jl. Letjen Hertasning Blok B, Pandang, Panakkukang, Makassar 90222'
        '    |    www.pln.co.id    |    T 0411 440066')
    c.drawRightString(W-MR, fy+1.5*mm, 'Paraf ___________________')


# ── Pengesahan TTD ───────────────────────────────────────────────────
_TTD_ZONE_H = 28 * mm

def draw_pengesahan(c, y, info, signatures=None):
    """
    Pengesahan: kolom kiri = TTD Asisten Manager, kolom kanan = daftar pelaksana.
    """
    sigs        = signatures or {}
    technicians = (info.get('technician') or '').strip()

    AM_W  = CW * 0.45
    TEK_W = CW - AM_W

    # Header baris label
    hdr_tbl = Table([[
        _p('Mengetahui,', 7, True, C_WHITE),
        _p('Pelaksana Pemeliharaan', 7, True, C_WHITE),
    ]], colWidths=[AM_W, TEK_W])
    hdr_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), C_BLUE_DARK),
        ('TOPPADDING',    (0,0),(-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3.5),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
        ('RIGHTPADDING',  (0,0),(-1,-1), 6),
    ]))
    y = _draw(c, hdr_tbl, ML, y)

    # Label jabatan
    title_tbl = Table([[
        _p('Asisten Manager Operasi', 7, True, C_GRAY_TXT),
        _p('', 7),
    ]], colWidths=[AM_W, TEK_W])
    title_tbl.setStyle(TableStyle([
        ('BOX',           (0,0),(-1,-1), 0.4, C_GRAY_LINE),
        ('INNERGRID',     (0,0),(-1,-1), 0.3, C_GRAY_LINE),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
    ]))
    y = _draw(c, title_tbl, ML, y)

    zone_y_top = y
    zone_h     = _TTD_ZONE_H
    zone_y_bot = zone_y_top - zone_h

    # Border zona TTD + border kanan (pelaksana)
    c.setStrokeColor(C_GRAY_LINE); c.setLineWidth(0.4)
    c.rect(ML,          zone_y_bot, AM_W,  zone_h, fill=0, stroke=1)
    c.rect(ML + AM_W,   zone_y_bot, TEK_W, zone_h, fill=0, stroke=1)

    # Slot TTD (dashed)
    SLOT_PAD_X = 6*mm; SLOT_PAD_Y = 4*mm
    SLOT_W = AM_W - 2*SLOT_PAD_X
    SLOT_H = zone_h - 2*SLOT_PAD_Y
    slot_x = ML + SLOT_PAD_X
    slot_y_bot = zone_y_bot + SLOT_PAD_Y

    c.saveState()
    c.setStrokeColor(colors.HexColor('#94A3B8'))
    c.setLineWidth(0.5); c.setDash([2, 3])
    c.rect(slot_x, slot_y_bot, SLOT_W, SLOT_H, fill=0, stroke=1)
    c.restoreState()

    # Gambar tanda tangan jika ada
    sig_path = sigs.get('asisten_manager', '')
    if sig_path and os.path.exists(sig_path):
        IMG_PAD = 3*mm
        c.drawImage(sig_path,
                    slot_x + IMG_PAD, slot_y_bot + IMG_PAD,
                    width=SLOT_W - 2*IMG_PAD, height=SLOT_H - 2*IMG_PAD,
                    preserveAspectRatio=True, anchor='c', mask='auto')
    else:
        c.saveState()
        c.setFont('Helvetica', 6.5)
        c.setFillColor(colors.HexColor('#CBD5E1'))
        lbl = 'Tanda Tangan'
        lbl_w = c.stringWidth(lbl, 'Helvetica', 6.5)
        c.drawString(slot_x + (SLOT_W - lbl_w)/2,
                     slot_y_bot + SLOT_H/2 - 3, lbl)
        c.restoreState()

    # Daftar pelaksana (kanan)
    tek_x = ML + AM_W
    if technicians:
        names = [n.strip() for n in technicians.split(',') if n.strip()]
        c.saveState()
        c.setFont('Helvetica-Bold', 7)
        c.setFillColor(colors.HexColor('#475569'))
        c.drawString(tek_x + 6*mm, zone_y_top - 7*mm, 'Nama Pelaksana:')
        c.setFont('Helvetica', 8)
        c.setFillColor(colors.HexColor('#0F172A'))
        for i, name in enumerate(names):
            c.drawString(tek_x + 6*mm, zone_y_top - (12 + i*7)*mm, f'{i+1}.  {name}')
        c.restoreState()
    else:
        c.saveState()
        c.setFont('Helvetica', 7)
        c.setFillColor(colors.HexColor('#CBD5E1'))
        c.drawString(tek_x + 6*mm, zone_y_bot + zone_h/2 - 3, '— Belum ada pelaksana —')
        c.restoreState()

    y = zone_y_bot

    # Baris nama Asisten Manager
    am_name = (info.get('signed_by') or '').strip()
    bot_tbl = Table([[
        _p(f'( {am_name if am_name else "................................................"} )',
           7.5, False, C_BLACK, TA_CENTER),
        _p('', 7.5),
    ]], colWidths=[AM_W, TEK_W])
    bot_tbl.setStyle(TableStyle([
        ('BOX',           (0,0),(-1,-1), 0.4, C_GRAY_LINE),
        ('INNERGRID',     (0,0),(-1,-1), 0.3, C_GRAY_LINE),
        ('TOPPADDING',    (0,0),(-1,-1), 5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING',   (0,0),(-1,-1), 5),
        ('RIGHTPADDING',  (0,0),(-1,-1), 5),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('BACKGROUND',    (0,0),(-1,-1), C_GRAY_HEAD),
    ]))
    y = _draw(c, bot_tbl, ML, y)
    return y
