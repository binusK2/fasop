"""
pdf_export/_base.py  —  Konstanta, helper, header/footer, pengesahan.
Digunakan bersama oleh semua modul device.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import Table, TableStyle, Paragraph
import os

W, H = A4

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

_HERE        = os.path.dirname(os.path.abspath(__file__))
LOGO_PETIR   = os.path.join(_HERE, '..', '..', 'static', 'img', 'pln_logo_conv.png')
LOGO_DANAT   = os.path.join(_HERE, '..', '..', 'static', 'img', 'danantara_logo.png')

ML = 15*mm; MR = 15*mm; MT = 14*mm; MB = 12*mm
CW = W - ML - MR

# ── Helpers ──────────────────────────────────────────────────────────
def _p(text, size=8, bold=False, color=None, align=TA_LEFT, leading=None):
    if color is None: color = C_BLACK
    return Paragraph(str(text) if text is not None else '-', ParagraphStyle(
        'x', fontSize=size,
        fontName='Helvetica-Bold' if bold else 'Helvetica',
        textColor=color, alignment=align,
        leading=leading or size*1.35, spaceAfter=0, spaceBefore=0,
    ))

def _val(v):
    if v is None or str(v).strip() == '': return '-'
    return str(v)

def _sc(val):
    v = (val or '').strip().upper()
    if v in ('OK','UP','BAIK','NORMAL'):       return _p(v, 7.5, True, C_GREEN_TXT, TA_CENTER)
    if v in ('NOK','DOWN','RUSAK','ABNORMAL'): return _p(v, 7.5, True, C_RED_TXT,   TA_CENTER)
    if v == 'N/A':                              return _p('N/A', 7.5, False, C_GRAY_TXT, TA_CENTER)
    return _p(_val(v), 7.5, False, C_GRAY_TXT, TA_CENTER)

def _sbg(val):
    v = (val or '').strip().upper()
    if v in ('OK','UP','BAIK','NORMAL'):       return C_GREEN_BG
    if v in ('NOK','DOWN','RUSAK','ABNORMAL'): return C_RED_BG
    if v == 'N/A':                              return C_ORANGE_BG
    return C_WHITE

_BS = [
    ('BOX',          (0,0),(-1,-1), 0.4, C_GRAY_LINE),
    ('INNERGRID',    (0,0),(-1,-1), 0.3, C_GRAY_LINE),
    ('TOPPADDING',   (0,0),(-1,-1), 2),
    ('BOTTOMPADDING',(0,0),(-1,-1), 2),
    ('LEFTPADDING',  (0,0),(-1,-1), 4),
    ('RIGHTPADDING', (0,0),(-1,-1), 3),
    ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
    ('FONTSIZE',     (0,0),(-1,-1), 7.5),
    ('FONTNAME',     (0,0),(-1,-1), 'Helvetica'),
]

def _grid(extra=None):
    s = list(_BS)
    if extra: s += extra
    return TableStyle(s)

def _sec(title, w=None):
    t = Table([[_p(title, 7.5, True, C_WHITE)]], colWidths=[w or CW])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), C_BLUE_DARK),
        ('TOPPADDING',    (0,0),(-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3.5),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
    ]))
    return t

def _draw(c, tbl, x, y):
    w, h = tbl.wrapOn(c, CW, H)
    tbl.drawOn(c, x, y - h)
    return y - h

# ── Header ───────────────────────────────────────────────────────────
_TITLES = {
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

def draw_header(c, kind):
    HDR_H = 16*mm
    logo_y = H - MT - HDR_H

    # ── Logo Danantara (kiri) ─────────────────────────────────────
    danat = os.path.normpath(LOGO_DANAT)
    if os.path.exists(danat):
        lh = (HDR_H - 3*mm) * 0.55        # 55% dari tinggi header — lebih kecil
        lw = lh * (1945/512)              # aspect ratio PNG 1945×512
        logo_center_y = logo_y + (HDR_H - lh) / 2   # vertikal tengah
        c.drawImage(danat, ML, logo_center_y, width=lw, height=lh,
                    preserveAspectRatio=True, mask='auto')
        txt_lx = ML + lw + 2*mm
    else:
        txt_lx = ML

    # ── Logo PLN petir (kanan) ─────────────────────────────────────
    petir = os.path.normpath(LOGO_PETIR)
    if os.path.exists(petir):
        lh2 = HDR_H - 3*mm
        lw2 = lh2 * (474/714)
        c.drawImage(petir, W - MR - lw2, logo_y + 1.5*mm, width=lw2, height=lh2,
                    preserveAspectRatio=True, mask='auto')
        txt_rx = W - MR - lw2 - 2*mm
    else:
        txt_rx = W - MR

    # ── Teks unit (kanan, di atas logo PLN) ───────────────────────
    c.setFont('Helvetica-Bold', 7); c.setFillColor(C_BLUE_DARK)
    c.drawRightString(txt_rx, logo_y + HDR_H - 5*mm,  'UIP3B SULAWESI')
    c.drawRightString(txt_rx, logo_y + HDR_H - 10*mm, 'UP2B SISTEM MAKASSAR')

    # ── Garis atas & bawah header ─────────────────────────────────
    c.setStrokeColor(C_BLACK); c.setLineWidth(0.6)
    c.line(ML, logo_y + HDR_H, W - MR, logo_y + HDR_H)
    c.line(ML, logo_y,         W - MR, logo_y)

    # ── Judul tengah ──────────────────────────────────────────────
    c.setFont('Helvetica-Bold', 9); c.setFillColor(C_BLACK)
    c.drawCentredString(W/2, logo_y + HDR_H/2 - 3,
                        _TITLES.get(kind, 'Formulir Pemeliharaan Peralatan FASOP'))

    # ── Garis merah bawah ─────────────────────────────────────────
    c.setStrokeColor(C_RED); c.setLineWidth(1.0)
    c.line(ML, logo_y, W - MR, logo_y)

    return logo_y - 2*mm

# ── Info ─────────────────────────────────────────────────────────────
def draw_info(c, y, info):
    y = _draw(c, _sec('I.  INFORMASI PEMELIHARAAN'), ML, y)
    y -= 0.5*mm
    LW = 32*mm; VW = CW/2 - LW
    def ir(l1,v1,l2,v2):
        return [_p(l1,7.5,True),_p(_val(v1),7.5),_p(l2,7.5,True),_p(_val(v2),7.5)]
    jenis_merk = ' / '.join(filter(None,[str(info.get('device_type') or '').strip(),
                                         str(info.get('merk') or '').strip()])) or '-'
    rows = [
        ir('Nama Perangkat',info.get('device_name'),'Jenis / Merk',jenis_merk),
        ir('Lokasi',info.get('lokasi'),'Type',info.get('type')),
        ir('No. Seri',info.get('serial_number'), 'IP Address',info.get('ip_address')),
        ir('Jenis Kegiatan',info.get('maintenance_type'), 'Tgl. Pemeliharaan',info.get('date')),
        ir('Status Perangkat',info.get('status'),'Pelaksana',info.get('technician')),
    ]
    itbl = Table(rows, colWidths=[LW,VW,LW,VW])
    itbl.setStyle(_grid([
        ('BACKGROUND',(0,0),(0,-1),C_GRAY_HEAD),('BACKGROUND',(2,0),(2,-1),C_GRAY_HEAD),
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
    ]))
    y = _draw(c, itbl, ML, y)
    desc = (info.get('description') or '').strip()
    if desc:
        dt = Table([[_p('Deskripsi / Keluhan:',7.5,True),_p(desc,7.5)]],colWidths=[LW,CW-LW])
        dt.setStyle(_grid([('BACKGROUND',(0,0),(0,0),C_GRAY_HEAD)]))
        y = _draw(c, dt, ML, y)
    catatan_am = (info.get('catatan_am') or '').strip()
    if catatan_am:
        ca = Table([[_p('Catatan Asisten Manager:',7.5,True),_p(catatan_am,7.5)]],colWidths=[LW,CW-LW])
        ca.setStyle(_grid([('BACKGROUND',(0,0),(0,0),colors.HexColor('#E0F2FE'))]))
        y = _draw(c, ca, ML, y)
    return y

# ── Footer ───────────────────────────────────────────────────────────
def draw_footer(c, print_by='', print_date=''):
    fy = MB + 3*mm
    c.setStrokeColor(colors.HexColor('#94A3B8')); c.setLineWidth(0.5)
    c.line(ML, fy + 4*mm, W - MR, fy + 4*mm)
    c.setFont('Helvetica', 6); c.setFillColor(C_GRAY_TXT)
    c.drawString(ML, fy + 1.5*mm,
        'Jl. Letjen Hertasning Blok B, Pandang, Panakkukang, Makassar 90222'
        '    |    www.pln.co.id    |    T 0411 440066')
    if print_by or print_date:
        label = f'Dicetak oleh: {print_by}   pada: {print_date}'
    else:
        label = ''
    if label:
        c.drawRightString(W - MR, fy + 1.5*mm, label)

# ── Pengesahan ───────────────────────────────────────────────────────
_TTD_ZONE_H = 32*mm          # zona TTD sedikit lebih tinggi

def draw_pengesahan(c, y, info, signatures=None):
    sigs = signatures or {}
    technicians = (info.get('technician') or '').strip()

    # ── Spasi sebelum pengesahan ──────────────────────────────────
    y -= 8*mm

    AM_W = CW * 0.45; TEK_W = CW - AM_W

    # ── Header baris "Mengetahui / Pelaksana" ─────────────────────
    hdr = Table([
        [_p('Mengetahui,', 7, True, C_WHITE, TA_CENTER),
         _p('Pelaksana Pemeliharaan', 7, True, C_WHITE, TA_CENTER)]
    ], colWidths=[AM_W, TEK_W])
    hdr.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), C_BLUE_DARK),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
        ('RIGHTPADDING',  (0,0),(-1,-1), 6),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
    ]))
    y = _draw(c, hdr, ML, y)

    # ── Sub-header "Asisten Manager Operasi" ──────────────────────
    ttl = Table([
        [_p('Asisten Manager Operasi', 7, True, C_GRAY_TXT, TA_CENTER),
         _p('', 7)]
    ], colWidths=[AM_W, TEK_W])
    ttl.setStyle(TableStyle([
        ('BOX',           (0,0),(-1,-1), 0.4, C_GRAY_LINE),
        ('INNERGRID',     (0,0),(-1,-1), 0.3, C_GRAY_LINE),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
    ]))
    y = _draw(c, ttl, ML, y)

    # ── Zona TTD ──────────────────────────────────────────────────
    zt = y; zh = _TTD_ZONE_H; zb = zt - zh
    c.setStrokeColor(C_GRAY_LINE); c.setLineWidth(0.4)
    c.rect(ML,        zb, AM_W,  zh, fill=0, stroke=1)
    c.rect(ML + AM_W, zb, TEK_W, zh, fill=0, stroke=1)

    # Gambar tanda tangan AM (tengah kolom kiri)
    spx = 6*mm; spy = 4*mm
    sw = AM_W - 2*spx; sh = zh - 2*spy
    sx = ML + spx; syb = zb + spy
    sig_path = sigs.get('asisten_manager', '')
    if sig_path and os.path.exists(sig_path):
        pad = 3*mm
        c.drawImage(sig_path, sx + pad, syb + pad,
                    width=sw - 2*pad, height=sh - 2*pad,
                    preserveAspectRatio=True, anchor='c', mask='auto')
    else:
        c.saveState()
        c.setFont('Helvetica', 6.5); c.setFillColor(colors.HexColor('#CBD5E1'))
        lbl = 'Tanda Tangan'
        lw = c.stringWidth(lbl, 'Helvetica', 6.5)
        c.drawString(sx + (sw - lw)/2, syb + sh/2 - 3, lbl)
        c.restoreState()

    # Daftar nama pelaksana di kolom kanan
    if technicians:
        names = [n.strip() for n in technicians.split(',') if n.strip()]
        c.setFont('Helvetica-Bold', 7); c.setFillColor(colors.HexColor('#475569'))
        c.drawString(ML + AM_W + 6*mm, zt - 7*mm, 'Nama Pelaksana:')
        c.setFont('Helvetica', 8); c.setFillColor(colors.HexColor('#0F172A'))
        for i, name in enumerate(names):
            c.drawString(ML + AM_W + 6*mm, zt - (13 + i*8)*mm, f'{i+1}.  {name}')

    y = zb

    # ── Baris nama AM (tengah) ────────────────────────────────────
    signed_name = (info.get('signed_by') or '').strip()
    name_display = f'( {signed_name} )' if signed_name else '( ................................................ )'
    bot = Table([
        [_p(name_display, 7.5, False, C_BLACK, TA_CENTER), _p('', 7.5)]
    ], colWidths=[AM_W, TEK_W])
    bot.setStyle(TableStyle([
        ('BOX',           (0,0),(-1,-1), 0.4, C_GRAY_LINE),
        ('INNERGRID',     (0,0),(-1,-1), 0.3, C_GRAY_LINE),
        ('TOPPADDING',    (0,0),(-1,-1), 5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('BACKGROUND',    (0,0),(-1,-1), C_GRAY_HEAD),
    ]))
    return _draw(c, bot, ML, y)