"""
health_index/pdf_export/laporan_hi.py
Laporan Bulanan Health Index — Ringkas (1-2 halaman)
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from io import BytesIO
import calendar, os
from datetime import date as date_type

W, H = A4
ML = 15*mm; MR = 15*mm; MT = 14*mm; MB = 16*mm
CW = W - ML - MR

C_DARK    = colors.HexColor('#0F172A')
C_BLUE    = colors.HexColor('#2563EB')
C_NAVY    = colors.HexColor('#1A3A5C')
C_GRAY    = colors.HexColor('#64748B')
C_LGRAY   = colors.HexColor('#F1F5F9')
C_BORDER  = colors.HexColor('#E2E8F0')
C_GREEN   = colors.HexColor('#10B981')
C_GREEN_B = colors.HexColor('#DCFCE7')
C_BLUE_B  = colors.HexColor('#DBEAFE')
C_YELLOW  = colors.HexColor('#F59E0B')
C_YELLOW_B= colors.HexColor('#FEF3C7')
C_ORANGE  = colors.HexColor('#F97316')
C_ORANGE_B= colors.HexColor('#FFF7ED')
C_RED     = colors.HexColor('#EF4444')
C_RED_B   = colors.HexColor('#FEE2E2')
C_WHITE   = colors.white

_HERE      = os.path.dirname(os.path.abspath(__file__))
LOGO_PETIR = os.path.join(_HERE, '..', '..', 'static', 'img', 'pln_logo_conv.png')
LOGO_DANAT = os.path.join(_HERE, '..', '..', 'static', 'img', 'danantara_logo.png')


def _p(text, size=8, bold=False, color=None, align=TA_LEFT):
    if color is None: color = C_DARK
    return Paragraph(str(text) if text is not None else '-', ParagraphStyle(
        'x', fontSize=size,
        fontName='Helvetica-Bold' if bold else 'Helvetica',
        textColor=color, alignment=align,
        leading=size*1.4, spaceAfter=0, spaceBefore=0,
    ))


def _hi_color(score):
    if score >= 85:   return C_GREEN,  C_GREEN_B,  'Sangat Baik'
    elif score >= 70: return C_BLUE,   C_BLUE_B,   'Baik'
    elif score >= 50: return C_YELLOW, C_YELLOW_B, 'Cukup'
    elif score >= 25: return C_ORANGE, C_ORANGE_B, 'Buruk'
    else:             return C_RED,    C_RED_B,    'Kritis'


def _on_page(canvas, doc, bulan, tahun, print_date, judul, subjudul):
    canvas.saveState()
    y_top  = H - MT
    HDR_H  = 16*mm
    logo_y = y_top - HDR_H

    danat = os.path.normpath(LOGO_DANAT)
    if os.path.exists(danat):
        lh = (HDR_H - 3*mm) * 0.55
        lw = lh * (1945/512)
        canvas.drawImage(danat, ML, logo_y + (HDR_H-lh)/2,
                         width=lw, height=lh, preserveAspectRatio=True, mask='auto')

    petir  = os.path.normpath(LOGO_PETIR)
    txt_rx = W - MR
    if os.path.exists(petir):
        lh2 = HDR_H - 3*mm
        lw2 = lh2 * (474/714)
        canvas.drawImage(petir, W-MR-lw2, logo_y+1.5*mm,
                         width=lw2, height=lh2, preserveAspectRatio=True, mask='auto')
        txt_rx = W - MR - lw2 - 2*mm

    canvas.setFont('Helvetica-Bold', 7)
    canvas.setFillColor(C_NAVY)
    canvas.drawRightString(txt_rx, logo_y+HDR_H-5*mm,  'UIP3B SULAWESI')
    canvas.drawRightString(txt_rx, logo_y+HDR_H-10*mm, 'UP2B SISTEM MAKASSAR')

    canvas.setStrokeColor(C_DARK); canvas.setLineWidth(0.6)
    canvas.line(ML, logo_y+HDR_H, W-MR, logo_y+HDR_H)
    canvas.line(ML, logo_y,       W-MR, logo_y)

    canvas.setFont('Helvetica-Bold', 9); canvas.setFillColor(C_DARK)
    canvas.drawCentredString(W/2, logo_y+HDR_H/2+1, judul)
    canvas.setFont('Helvetica', 7.5); canvas.setFillColor(C_GRAY)
    canvas.drawCentredString(W/2, logo_y+HDR_H/2-6, subjudul)

    canvas.setStrokeColor(colors.HexColor('#DC2626')); canvas.setLineWidth(1.0)
    canvas.line(ML, logo_y, W-MR, logo_y)

    canvas.setFillColor(C_GRAY); canvas.setFont('Helvetica', 6.5)
    canvas.drawString(ML, MB-4*mm, f'Dicetak: {print_date}  |  FASOP UP2B Sistem Makassar')
    canvas.drawRightString(W-MR, MB-4*mm, f'Hal. {doc.page}')
    canvas.setStrokeColor(C_BORDER); canvas.setLineWidth(0.5)
    canvas.line(ML, MB, W-MR, MB)
    canvas.restoreState()


def generate_laporan_hi(devices_hi, bulan=None, tahun=None, lokasi=None):
    today      = date_type.today()
    bulan      = bulan or today.month
    tahun      = tahun or today.year
    print_date = today.strftime('%d %B %Y')
    bln_str    = calendar.month_name[bulan]
    judul      = 'LAPORAN HEALTH INDEX PERALATAN'
    subjudul   = f'Periode: {bln_str} {tahun}'
    if lokasi:
        subjudul += f'  |  Lokasi: {lokasi}'

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT+20*mm, bottomMargin=MB+4*mm,
    )
    cb = lambda c, d: _on_page(c, d, bulan, tahun, print_date, judul, subjudul)
    story = [Spacer(1, 2*mm)]

    if not devices_hi:
        story.append(Spacer(1, 20*mm))
        story.append(_p('Tidak ada peralatan yang sesuai filter.', 10, False, C_GRAY, TA_CENTER))
        doc.build(story, onFirstPage=cb, onLaterPages=cb)
        buf.seek(0)
        return buf

    # ── Ringkasan ──────────────────────────────────────────────────
    story.append(_p('RINGKASAN EKSEKUTIF', 9, True, C_BLUE))
    story.append(HRFlowable(width=CW, thickness=1, color=C_BORDER, spaceAfter=3))

    total = len(devices_hi)
    counts = {'Sangat Baik':0,'Baik':0,'Cukup':0,'Buruk':0,'Kritis':0}
    avg_score = 0
    for item in devices_hi:
        s = item['hi']['score']; avg_score += s
        kat = item['hi']['kategori']['label']
        if kat in counts: counts[kat] += 1
    avg_score = round(avg_score/total) if total else 0

    cw5 = CW/5
    sum_tbl = Table([
        [_p('Total',7,False,C_GRAY,TA_CENTER), _p('Rata-rata HI',7,False,C_GRAY,TA_CENTER),
         _p('Sangat Baik',7,False,C_GRAY,TA_CENTER), _p('Perlu Perhatian',7,False,C_GRAY,TA_CENTER),
         _p('Kritis',7,False,C_GRAY,TA_CENTER)],
        [_p(str(total),16,True,C_DARK,TA_CENTER), _p(str(avg_score),16,True,C_BLUE,TA_CENTER),
         _p(str(counts['Sangat Baik']+counts['Baik']),16,True,C_GREEN,TA_CENTER),
         _p(str(counts['Cukup']+counts['Buruk']),16,True,C_YELLOW,TA_CENTER),
         _p(str(counts['Kritis']),16,True,C_RED,TA_CENTER)],
    ], colWidths=[cw5]*5, rowHeights=[7*mm,11*mm])
    sum_tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),C_LGRAY),
        ('BACKGROUND',(1,1),(1,1),C_BLUE_B),('BACKGROUND',(2,1),(2,1),C_GREEN_B),
        ('BACKGROUND',(3,1),(3,1),C_YELLOW_B),('BACKGROUND',(4,1),(4,1),C_RED_B),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('GRID',(0,0),(-1,-1),0.5,C_BORDER),
    ]))
    story.append(sum_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Distribusi ─────────────────────────────────────────────────
    dist_row = []
    dist_bg  = []
    for i,(label,fc,bg) in enumerate([
        ('Sangat Baik',C_GREEN,C_GREEN_B),('Baik',C_BLUE,C_BLUE_B),
        ('Cukup',C_YELLOW,C_YELLOW_B),('Buruk',C_ORANGE,C_ORANGE_B),('Kritis',C_RED,C_RED_B),
    ]):
        cnt = counts.get(label,0)
        pct = round(cnt/total*100) if total else 0
        dist_row.append(_p(f'{label}\n{cnt} device ({pct}%)', 7.5, True, fc, TA_CENTER))
        dist_bg.append(('BACKGROUND',(i,0),(i,0),bg))

    dist_tbl = Table([dist_row], colWidths=[cw5]*5, rowHeights=[10*mm])
    dist_tbl.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),0.4,C_BORDER),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER'),
    ]+dist_bg))
    story.append(dist_tbl)
    story.append(Spacer(1, 5*mm))

    # ── Tabel Detail ───────────────────────────────────────────────
    story.append(_p('DAFTAR HEALTH INDEX PERALATAN', 9, True, C_BLUE))
    story.append(HRFlowable(width=CW, thickness=1, color=C_BORDER, spaceAfter=3))

    rek = {'Sangat Baik':'Maintenance rutin','Baik':'Monitor berkala',
           'Cukup':'Perlu perhatian','Buruk':'Jadwalkan perbaikan','Kritis':'Tindakan segera!'}
    col_w = [CW*0.28,CW*0.18,CW*0.13,CW*0.10,CW*0.13,CW*0.18]
    rows = [[
        _p('Nama Peralatan',7.5,True,C_WHITE), _p('Lokasi',7.5,True,C_WHITE),
        _p('Jenis',7.5,True,C_WHITE,TA_CENTER), _p('Skor',7.5,True,C_WHITE,TA_CENTER),
        _p('Kategori',7.5,True,C_WHITE,TA_CENTER), _p('Rekomendasi',7.5,True,C_WHITE),
    ]]
    rstyles = []
    for i,item in enumerate(sorted(devices_hi, key=lambda x: x['hi']['score'])):
        d = item['device']; hi = item['hi']; s = hi['score']
        kat_label = hi['kategori']['label']
        fc, bg, _ = _hi_color(s)
        bg_row = C_LGRAY if i%2==0 else C_WHITE
        rows.append([
            _p(d.nama,7.5), _p(d.lokasi or '-',7,False,C_GRAY),
            _p(d.jenis.name if d.jenis else '-',7,False,C_GRAY,TA_CENTER),
            _p(str(s),9,True,fc,TA_CENTER), _p(kat_label,7,True,fc,TA_CENTER),
            _p(rek.get(kat_label,'-'),7,False,C_GRAY),
        ])
        rstyles += [('BACKGROUND',(0,i+1),(-1,i+1),bg_row),
                    ('BACKGROUND',(3,i+1),(4,i+1),bg)]

    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),C_NAVY),
        ('GRID',(0,0),(-1,-1),0.4,C_BORDER),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(0,0),(-1,-1),5),
    ]+rstyles))
    story.append(tbl)

    doc.build(story, onFirstPage=cb, onLaterPages=cb)
    buf.seek(0)
    return buf
