"""
pdf_export.py  –  Laporan Pemeliharaan FASOP
Mendukung: Router / Switch / PLC / Generic
Format   : A4 portrait, 1 halaman
Logo PLN : pojok kanan atas (header bar biru)
Tgl Cetak: footer kanan bawah
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.pdfgen import canvas as rl_canvas
import os, json

W, H = A4   # 595.28 × 841.89 pt

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

_HERE     = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(_HERE, '..', 'static', 'img', 'pln_logo.png')

ML = 15*mm; MR = 15*mm; MT = 14*mm; MB = 12*mm
CW = W - ML - MR


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
    v = (val or '').strip().upper()
    if v in ('OK','UP','BAIK','NORMAL'):         return _p(v,7.5,True,C_GREEN_TXT,TA_CENTER)
    elif v in ('NOK','DOWN','RUSAK','ABNORMAL'):  return _p(v,7.5,True,C_RED_TXT,TA_CENTER)
    elif v == 'N/A':                              return _p('N/A',7.5,False,C_GRAY_TXT,TA_CENTER)
    return _p(_val(v),7.5,False,C_GRAY_TXT,TA_CENTER)

def _sbg(val):
    v = (val or '').strip().upper()
    if v in ('OK','UP','BAIK','NORMAL'):          return C_GREEN_BG
    if v in ('NOK','DOWN','RUSAK','ABNORMAL'):    return C_RED_BG
    if v == 'N/A':                                return C_ORANGE_BG
    return C_WHITE

_BS = [
    ('BOX',           (0,0),(-1,-1), 0.4, C_GRAY_LINE),
    ('INNERGRID',     (0,0),(-1,-1), 0.3, C_GRAY_LINE),
    ('TOPPADDING',    (0,0),(-1,-1), 3),
    ('BOTTOMPADDING', (0,0),(-1,-1), 3),
    ('LEFTPADDING',   (0,0),(-1,-1), 5),
    ('RIGHTPADDING',  (0,0),(-1,-1), 4),
    ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ('FONTSIZE',      (0,0),(-1,-1), 7.5),
    ('FONTNAME',      (0,0),(-1,-1), 'Helvetica'),
]

def _grid(extra=None):
    s = list(_BS)
    if extra: s += extra
    return TableStyle(s)

def _sec(title, w=None):
    t = Table([[_p(title,7.5,True,C_WHITE)]], colWidths=[w or CW])
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,-1),C_BLUE_DARK),
        ('TOPPADDING',   (0,0),(-1,-1),3.5),
        ('BOTTOMPADDING',(0,0),(-1,-1),3.5),
        ('LEFTPADDING',  (0,0),(-1,-1),6),
    ]))
    return t

def _draw(c, tbl, x, y):
    w,h = tbl.wrapOn(c, CW, H)
    tbl.drawOn(c, x, y-h)
    return y-h


# ── Router / Switch ──────────────────────────────────────────────────
def _router(c, y, data):
    fisik = data.get('fisik',{})
    ukur  = data.get('pengukuran',{})
    port  = data.get('port',{})
    sfp   = data.get('sfp_ports',[])

    y -= 2*mm
    LW2 = 82*mm; RW2 = CW - LW2 - 2*mm; GAP = 2*mm

    fh = _sec('II.  PEMERIKSAAN FISIK', LW2)
    fi = [
        ('Kondisi Fisik Unit',       fisik.get('kondisi_fisik','')),
        ('Indikator LED Link / Port', fisik.get('led_link','')),
        ('Kondisi Kabel & Konektor', fisik.get('kondisi_kabel','')),
    ]
    fb_rows = [[_p(l,7.5), _sc(v)] for l,v in fi]
    fb = Table(fb_rows, colWidths=[LW2-16*mm, 16*mm])
    fe = []
    for i,(l,v) in enumerate(fi):
        fe.append(('BACKGROUND',(1,i),(1,i),_sbg(v)))
        fe.append(('BACKGROUND',(0,i),(0,i),C_GRAY_HEAD if i%2==0 else C_WHITE))
    fb.setStyle(_grid(fe))

    uh = _sec('III.  NILAI PENGUKURAN', RW2)
    ui = [
        ('Tegangan Input', _val(ukur.get('tegangan_input')),'V',  '210-240 V'),
        ('Suhu Perangkat', _val(ukur.get('suhu_perangkat')),'C',  '< 50 C'),
        ('CPU Load',       _val(ukur.get('cpu_load')),      '%',  '< 80 %'),
        ('Memory Usage',   _val(ukur.get('memory_usage')),  '%',  '< 80 %'),
    ]
    UC = [RW2-28*mm-12*mm, 28*mm, 12*mm]
    ub_rows = [[_p(p2,7.5), _p(v,8,True,C_BLUE_MID,TA_CENTER), _p(f'{s}\n{n}',6.5,False,C_GRAY_TXT,TA_CENTER)]
               for p2,v,s,n in ui]
    ub = Table(ub_rows, colWidths=UC)
    ue = [('BACKGROUND',(0,i),(-1,i),C_GRAY_HEAD if i%2==0 else C_WHITE) for i in range(len(ui))]
    ub.setStyle(_grid(ue))

    for t in (fh,fb,uh,ub): t.wrapOn(c,CW,H)
    ty = y
    fh.drawOn(c, ML,           ty - fh._height)
    fb.drawOn(c, ML,           ty - fh._height - fb._height)
    uh.drawOn(c, ML+LW2+GAP,   ty - uh._height)
    ub.drawOn(c, ML+LW2+GAP,   ty - uh._height - ub._height)
    y = ty - max(fh._height+fb._height, uh._height+ub._height)

    y -= 2*mm
    y = _draw(c, _sec('IV.  STATUS PORT & INTERFACE'), ML, y)
    y -= 0.5*mm
    P1,P2,P3 = 25*mm, 20*mm, 55*mm; P4 = CW-P1-P2-P3
    ph = [_p('Port Aktif/Total',7.5,True), _p('Routing',7.5,True),
          _p('Detail Port',7.5,True), _p('Catatan Tambahan',7.5,True)]
    pr = [
        _p(f'{_val(port.get("jumlah_port_aktif"))} / {_val(port.get("jumlah_port_total"))}',8,True,C_BLUE_MID,TA_CENTER),
        _sc(port.get('status_routing','')),
        _p(_val(port.get('detail_port')),7.5),
        _p(_val(data.get('catatan_tambahan')),7.5,False,C_GRAY_TXT),
    ]
    pt = Table([ph,pr], colWidths=[P1,P2,P3,P4])
    pt.setStyle(_grid([
        ('BACKGROUND',(0,0),(-1,0),C_GRAY_HEAD),
        ('FONTNAME',  (0,0),(-1,0),'Helvetica-Bold'),
        ('BACKGROUND',(1,1),(1,1),_sbg(port.get('status_routing',''))),
    ]))
    y = _draw(c, pt, ML, y)

    if sfp:
        y -= 2*mm
        y = _draw(c, _sec(f'V.  DATA SFP PORT  ({len(sfp)} port)'), ML, y)
        y -= 0.5*mm
        SC = [13*mm,20*mm,20*mm,18*mm,20*mm, CW-13*mm-20*mm-20*mm-18*mm-20*mm-14*mm, 14*mm]
        sh = [_p('Port',7.5,True,align=TA_CENTER), _p('Tx (dBm)',7.5,True,align=TA_CENTER),
              _p('Rx (dBm)',7.5,True,align=TA_CENTER), _p('Lamda(nm)',7.5,True,align=TA_CENTER),
              _p('Bandwidth',7.5,True,align=TA_CENTER), _p('Merk / Tipe',7.5,True),
              _p('Status',7.5,True,align=TA_CENTER)]
        sr = [sh]
        for i,sp in enumerate(sfp):
            sv = (sp.get('status','') or '').strip().upper()
            sr.append([
                _p(f'SFP {i+1}',7.5,True,C_BLUE_MID,TA_CENTER),
                _p(_val(sp.get('tx')),7.5,align=TA_CENTER),
                _p(_val(sp.get('rx')),7.5,align=TA_CENTER),
                _p(_val(sp.get('lambda')),7.5,align=TA_CENTER),
                _p(_val(sp.get('bandwidth')),7.5,align=TA_CENTER),
                _p(_val(sp.get('merk')),7.5),
                _sc(sv),
            ])
        sfp_tbl = Table(sr, colWidths=SC)
        se = [('BACKGROUND',(0,0),(-1,0),C_GRAY_HEAD),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')]
        for i,sp in enumerate(sfp):
            row=i+1; sv=(sp.get('status','') or '').strip().upper()
            se.append(('BACKGROUND',(0,row),(-2,row),C_GRAY_HEAD if i%2==0 else C_WHITE))
            se.append(('BACKGROUND',(-1,row),(-1,row),_sbg(sv)))
        sfp_tbl.setStyle(_grid(se))
        y = _draw(c, sfp_tbl, ML, y)
    return y


# ── PLC ──────────────────────────────────────────────────────────────
def _plc(c, y, data):
    plc = data.get('plc',{})
    y -= 2*mm
    y = _draw(c, _sec('II.  CHECKLIST PEMELIHARAAN PLC'), ML, y)
    y -= 0.5*mm
    items = [
        ('Akses PLC Lokal',    plc.get('akses_plc','')),
        ('Remote Akses PLC',   plc.get('remote_akses_plc','')),
        ('Sinkronisasi Waktu', plc.get('time_sync','')),
        ('Wave Trap',          plc.get('wave_trap','')),
        ('IMU',                plc.get('imu','')),
        ('Kabel Coaxial',      plc.get('kabel_coaxial','')),
    ]
    mid = (len(items)+1)//2
    LWc = (CW-2*mm)/2; LBL = LWc-16*mm; VAL = 16*mm
    def mkcol(rows):
        t = Table([[_p(l,7.5), _sc(v)] for l,v in rows], colWidths=[LBL,VAL])
        ex = []
        for i,(_,v) in enumerate(rows):
            ex.append(('BACKGROUND',(1,i),(1,i),_sbg(v)))
            ex.append(('BACKGROUND',(0,i),(0,i),C_GRAY_HEAD if i%2==0 else C_WHITE))
        t.setStyle(_grid(ex)); return t
    tl = mkcol(items[:mid]); tr = mkcol(items[mid:])
    for t in (tl,tr): t.wrapOn(c,CW,H)
    ty=y
    tl.drawOn(c, ML,            ty-tl._height)
    tr.drawOn(c, ML+LWc+2*mm,   ty-tr._height)
    y = ty - max(tl._height, tr._height)

    y -= 2*mm
    y = _draw(c, _sec('III.  NILAI PENGUKURAN PLC'), ML, y)
    y -= 0.5*mm
    ui2 = [
        ('Transmission Line Level', _val(plc.get('transmission_line')), 'dBm', '-'),
        ('Rx Pilot Level',          _val(plc.get('rx_pilot_level')),    'dBm', '-'),
        ('Frequency TX',            _val(plc.get('freq_tx')),           'MHz', '-'),
        ('Bandwidth TX',            _val(plc.get('bandwidth_tx')),      'MHz', '-'),
        ('Frequency RX',            _val(plc.get('freq_rx')),           'MHz', '-'),
        ('Bandwidth RX',            _val(plc.get('bandwidth_rx')),      'MHz', '-'),
    ]
    UC2 = [CW-28*mm-14*mm, 28*mm, 14*mm]
    ub2 = Table([[_p(p2,7.5), _p(v,8,True,C_BLUE_MID,TA_CENTER), _p(f'{s}\n{n}',6.5,False,C_GRAY_TXT,TA_CENTER)]
                 for p2,v,s,n in ui2], colWidths=UC2)
    ub2.setStyle(_grid([('BACKGROUND',(0,i),(-1,i),C_GRAY_HEAD if i%2==0 else C_WHITE) for i in range(len(ui2))]))
    y = _draw(c, ub2, ML, y)

    y -= 2*mm
    y = _draw(c, _sec('IV.  CATATAN TAMBAHAN'), ML, y)
    y -= 0.5*mm
    cat = data.get('catatan_tambahan','')
    ct = Table([[_p(_val(cat),7.5,False,C_GRAY_TXT if not cat else C_BLACK)]], colWidths=[CW])
    ct.setStyle(_grid([('MINROWHEIGHT',(0,0),(-1,-1),10*mm)]))
    y = _draw(c, ct, ML, y)
    return y


# ── Generic ──────────────────────────────────────────────────────────
def _generic(c, y, data):
    y -= 2*mm
    y = _draw(c, _sec('II.  CATATAN PEMELIHARAAN'), ML, y)
    y -= 0.5*mm
    cat = data.get('catatan_tambahan','')
    ct = Table([[_p(_val(cat),7.5)]], colWidths=[CW])
    ct.setStyle(_grid([('MINROWHEIGHT',(0,0),(-1,-1),18*mm)]))
    y = _draw(c, ct, ML, y)
    return y


# ════════════════════════════════════════════════════════════════════
def build_pdf(data: dict, output_path):
    c = rl_canvas.Canvas(output_path, pagesize=A4)
    c.setTitle('Laporan Pemeliharaan FASOP')
    c.setAuthor('UP2B Sistem Makassar')

    info = data.get('info',{})
    kind = data.get('device_kind','GENERIC').strip().upper()

    # HEADER
    HDR_H = 17*mm
    c.setFillColor(C_BLUE_DARK)
    c.rect(0, H-HDR_H, W, HDR_H, fill=1, stroke=0)
    c.setFillColor(C_RED)
    c.rect(0, H-HDR_H-1.5, W, 1.5, fill=1, stroke=0)
    c.setFillColor(C_WHITE)
    c.setFont('Helvetica-Bold', 10.5)
    c.drawString(ML, H-8*mm, 'LAPORAN PEMELIHARAAN PERALATAN FASOP')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML, H-13*mm, 'UIP3B Sulawesi  -  UP2B Sistem Makassar')
    logo = os.path.normpath(LOGO_PATH)
    if os.path.exists(logo):
        lw,lh = 36*mm,4.8*mm
        c.drawImage(logo, W-MR-lw, H-HDR_H+(HDR_H-lh)/2,
                    width=lw, height=lh, preserveAspectRatio=True, mask='auto')

    y = H - HDR_H - 1.5 - 2.5*mm

    # I. INFO
    y = _draw(c, _sec('I.  INFORMASI PEMELIHARAAN'), ML, y)
    y -= 0.5*mm
    LW = 32*mm; VW = CW/2 - LW
    def ir(l1,v1,l2,v2):
        return [_p(l1,7.5,True), _p(_val(v1),7.5), _p(l2,7.5,True), _p(_val(v2),7.5)]
    rows = [
        ir('Nama Perangkat',  info.get('device_name'),
           'Jenis / Merk',    (str(info.get('device_type') or '') + ' / ' + str(info.get('brand') or '')).strip(' /')),
        ir('Lokasi',          info.get('lokasi'),
           'IP Address',      info.get('ip_address')),
        ir('No. Seri',        info.get('serial_number'),
           'Tgl. Pemeliharaan', info.get('date')),
        ir('Jenis Kegiatan',  info.get('maintenance_type'),
           'Pelaksana',       info.get('technician')),
        ir('Status',          info.get('status'), '', ''),
    ]
    itbl = Table(rows, colWidths=[LW,VW,LW,VW])
    itbl.setStyle(_grid([
        ('BACKGROUND',(0,0),(0,-1),C_GRAY_HEAD),
        ('BACKGROUND',(2,0),(2,-1),C_GRAY_HEAD),
        ('FONTNAME',  (0,0),(0,-1),'Helvetica-Bold'),
        ('FONTNAME',  (2,0),(2,-1),'Helvetica-Bold'),
    ]))
    y = _draw(c, itbl, ML, y)
    desc = (info.get('description') or '').strip()
    if desc:
        dt = Table([[_p('Deskripsi / Keluhan:',7.5,True), _p(desc,7.5)]], colWidths=[LW,CW-LW])
        dt.setStyle(_grid([('BACKGROUND',(0,0),(0,0),C_GRAY_HEAD)]))
        y = _draw(c, dt, ML, y)

    # Konten detail
    if kind in ('ROUTER','SWITCH'):
        y = _router(c, y, data)
    elif kind == 'PLC':
        y = _plc(c, y, data)
    else:
        y = _generic(c, y, data)

    # PENGESAHAN
    y -= 3*mm
    y = _draw(c, _sec('PENGESAHAN'), ML, y)
    y -= 0.5*mm
    tcw = CW/3
    ttd = [
        [_p('Pelaksana Pemeliharaan',7.5,True,align=TA_CENTER),
         _p('Koordinator Pemeliharaan',7.5,True,align=TA_CENTER),
         _p('Asisten Manager Operasi',7.5,True,align=TA_CENTER)],
        [_p('\n\n\n\n',7), _p('\n\n\n\n',7), _p('\n\n\n\n',7)],
        [_p(f'( {info.get("technician") or "................................"} )',7.5,align=TA_CENTER),
         _p('( ................................ )',7.5,align=TA_CENTER),
         _p('( ................................ )',7.5,align=TA_CENTER)],
        [_p('NIP. ............................',7,False,C_GRAY_TXT,TA_CENTER),
         _p('NIP. ............................',7,False,C_GRAY_TXT,TA_CENTER),
         _p('NIP. ............................',7,False,C_GRAY_TXT,TA_CENTER)],
    ]
    ttd_tbl = Table(ttd, colWidths=[tcw,tcw,tcw])
    ttd_tbl.setStyle(_grid([
        ('BACKGROUND',(0,0),(-1,0),C_GRAY_HEAD),
        ('FONTNAME',  (0,0),(-1,0),'Helvetica-Bold'),
        ('ALIGN',     (0,0),(-1,-1),'CENTER'),
    ]))
    y = _draw(c, ttd_tbl, ML, y)

    # FOOTER
    fy = MB + 5*mm
    c.setStrokeColor(C_RED); c.setLineWidth(1)
    c.line(ML, fy+4*mm, W-MR, fy+4*mm)
    c.setFont('Helvetica', 6.5); c.setFillColor(C_GRAY_TXT)
    c.drawString(ML, fy+1.5*mm,
        'UP2B Sistem Makassar  |  Jl. Letjen Hertasning Blok B, Pandang, Panakkukang, Makassar 90222  |  www.pln.co.id')
    c.drawRightString(W-MR, fy+1.5*mm, f'Tanggal Cetak: {data.get("print_date","")}')

    c.save()
