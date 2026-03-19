"""
health_index/pdf_export/laporan_jadwal.py

Laporan Rekap Jadwal Pemeliharaan per Lokasi
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from io import BytesIO
import calendar, os
from datetime import date as date_type

W, H = A4
ML = 15*mm; MR = 15*mm; MT = 14*mm; MB = 16*mm
CW = W - ML - MR

C_DARK   = colors.HexColor('#0F172A')
C_BLUE   = colors.HexColor('#2563EB')
C_NAVY   = colors.HexColor('#1A3A5C')
C_GRAY   = colors.HexColor('#64748B')
C_LGRAY  = colors.HexColor('#F1F5F9')
C_BORDER = colors.HexColor('#E2E8F0')
C_GREEN  = colors.HexColor('#10B981')
C_GREEN_B= colors.HexColor('#DCFCE7')
C_YELLOW = colors.HexColor('#F59E0B')
C_YELLOW_B=colors.HexColor('#FEF3C7')
C_RED    = colors.HexColor('#EF4444')
C_RED_B  = colors.HexColor('#FEE2E2')
C_BLUE_B = colors.HexColor('#DBEAFE')
C_WHITE  = colors.white

_HERE      = os.path.dirname(os.path.abspath(__file__))
LOGO_PETIR = os.path.join(_HERE, '..', '..', 'static', 'img', 'pln_logo_conv.png')
LOGO_DANAT = os.path.join(_HERE, '..', '..', 'static', 'img', 'danantara_logo.png')


def _p(text, size=8, bold=False, color=None, align=TA_LEFT):
    if color is None: color = C_DARK
    return Paragraph(str(text) if text is not None else '-', ParagraphStyle(
        'x', fontSize=size,
        fontName='Helvetica-Bold' if bold else 'Helvetica',
        textColor=color, alignment=align,
        leading=size * 1.4, spaceAfter=0, spaceBefore=0,
    ))


def _on_page(canvas, doc, tahun, print_date):
    canvas.saveState()
    y_top = H - MT
    HDR_H = 16 * mm
    logo_y = y_top - HDR_H

    # ── Logo Danantara (kiri) ─────────────────────────────────────
    if os.path.exists(LOGO_DANAT):
        lh = (HDR_H - 3*mm) * 0.55
        lw = lh * (1945/512)
        logo_cy = logo_y + (HDR_H - lh) / 2
        canvas.drawImage(LOGO_DANAT, ML, logo_cy, width=lw, height=lh,
                         preserveAspectRatio=True, mask='auto')

    # ── Logo PLN (kanan) ──────────────────────────────────────────
    if os.path.exists(LOGO_PETIR):
        lh2 = HDR_H - 3*mm
        lw2 = lh2 * (474/714)
        canvas.drawImage(LOGO_PETIR, W - MR - lw2, logo_y + 1.5*mm,
                         width=lw2, height=lh2, preserveAspectRatio=True, mask='auto')
        txt_rx = W - MR - lw2 - 2*mm
    else:
        txt_rx = W - MR

    # ── Teks unit kanan ───────────────────────────────────────────
    canvas.setFont('Helvetica-Bold', 7)
    canvas.setFillColor(colors.HexColor('#1A3A5C'))
    canvas.drawRightString(txt_rx, logo_y + HDR_H - 5*mm,  'UIP3B SULAWESI')
    canvas.drawRightString(txt_rx, logo_y + HDR_H - 10*mm, 'UP2B SISTEM MAKASSAR')

    # ── Garis atas & bawah header (hitam) ────────────────────────
    canvas.setStrokeColor(colors.HexColor('#0F172A'))
    canvas.setLineWidth(0.6)
    canvas.line(ML, logo_y + HDR_H, W - MR, logo_y + HDR_H)
    canvas.line(ML, logo_y,         W - MR, logo_y)

    # ── Judul tengah ──────────────────────────────────────────────
    canvas.setFont('Helvetica-Bold', 9)
    canvas.setFillColor(colors.HexColor('#0F172A'))
    canvas.drawCentredString(W/2, logo_y + HDR_H/2 + 1,
                             'REKAP JADWAL PEMELIHARAAN PERALATAN')
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(colors.HexColor('#64748B'))
    canvas.drawCentredString(W/2, logo_y + HDR_H/2 - 6, f'Tahun {tahun}')

    # ── Garis merah bawah header ──────────────────────────────────
    canvas.setStrokeColor(colors.HexColor('#DC2626'))
    canvas.setLineWidth(1.0)
    canvas.line(ML, logo_y, W - MR, logo_y)

    # ── Footer ────────────────────────────────────────────────────
    canvas.setFillColor(colors.HexColor('#64748B'))
    canvas.setFont('Helvetica', 6.5)
    canvas.drawString(ML, MB - 4*mm,
                      f'Dicetak: {print_date}  |  FASOP UP2B Sistem Makassar')
    canvas.drawRightString(W - MR, MB - 4*mm, f'Hal. {doc.page}')
    canvas.setStrokeColor(colors.HexColor('#E2E8F0'))
    canvas.setLineWidth(0.5)
    canvas.line(ML, MB, W - MR, MB)
    canvas.restoreState()


def generate_laporan_jadwal(jadwal_list, tahun=None):
    """
    Generate PDF laporan jadwal pemeliharaan.

    Args:
        jadwal_list: list of JadwalKunjungan objects (sudah di-annotate progress)
        tahun: int

    Returns:
        BytesIO buffer PDF
    """
    today = date_type.today()
    tahun = tahun or today.year
    print_date = today.strftime('%d %B %Y')

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT + 22*mm, bottomMargin=MB + 4*mm,
        title=f'Rekap Jadwal Pemeliharaan {tahun}',
    )

    story = []
    story.append(Spacer(1, 3*mm))

    # ── Ringkasan ─────────────────────────────────────────────────────────────
    story.append(_p('RINGKASAN JADWAL', 9, True, C_BLUE))
    story.append(HRFlowable(width=CW, thickness=1, color=C_BORDER, spaceAfter=4))

    total     = len(jadwal_list)
    planned   = sum(1 for j in jadwal_list if j.status == 'planned')
    in_prog   = sum(1 for j in jadwal_list if j.status == 'in_progress')
    done      = sum(1 for j in jadwal_list if j.status == 'done')

    sum_data = [
        [_p('Total Jadwal', 7, False, C_GRAY, TA_CENTER),
         _p('Terjadwal',    7, False, C_GRAY, TA_CENTER),
         _p('Berjalan',     7, False, C_GRAY, TA_CENTER),
         _p('Selesai',      7, False, C_GRAY, TA_CENTER)],
        [_p(str(total),   16, True, C_DARK,   TA_CENTER),
         _p(str(planned), 16, True, C_BLUE,   TA_CENTER),
         _p(str(in_prog), 16, True, C_YELLOW, TA_CENTER),
         _p(str(done),    16, True, C_GREEN,  TA_CENTER)],
    ]
    cw4 = CW / 4
    sum_tbl = Table(sum_data, colWidths=[cw4]*4, rowHeights=[8*mm, 11*mm])
    sum_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_LGRAY),
        ('BACKGROUND', (1,1), (1,1), C_BLUE_B),
        ('BACKGROUND', (2,1), (2,1), C_YELLOW_B),
        ('BACKGROUND', (3,1), (3,1), C_GREEN_B),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(sum_tbl)
    story.append(Spacer(1, 6*mm))

    # ── Tabel Detail Jadwal ───────────────────────────────────────────────────
    story.append(_p('DETAIL JADWAL PER LOKASI', 9, True, C_BLUE))
    story.append(HRFlowable(width=CW, thickness=1, color=C_BORDER, spaceAfter=4))

    col_w = [CW*0.28, CW*0.13, CW*0.10, CW*0.10, CW*0.10, CW*0.14, CW*0.15]
    header = [
        _p('Lokasi / Site',   7.5, True, C_WHITE),
        _p('Periode',         7.5, True, C_WHITE, TA_CENTER),
        _p('Total Dev.',      7.5, True, C_WHITE, TA_CENTER),
        _p('Selesai',         7.5, True, C_WHITE, TA_CENTER),
        _p('Progres',         7.5, True, C_WHITE, TA_CENTER),
        _p('Status',          7.5, True, C_WHITE, TA_CENTER),
        _p('Catatan',         7.5, True, C_WHITE, TA_LEFT),
    ]

    rows = [header]
    row_styles = []

    for i, j in enumerate(jadwal_list):
        prog = j.get_progress()
        pct  = prog.get('pct', 0)
        selesai = prog.get('selesai', 0)
        total_d = prog.get('total', 0)

        # Status badge warna
        if j.status == 'done':
            s_color, s_bg, s_label = C_GREEN,  C_GREEN_B,  'Selesai'
        elif j.status == 'in_progress':
            s_color, s_bg, s_label = C_YELLOW, C_YELLOW_B, 'Berjalan'
        else:
            s_color, s_bg, s_label = C_BLUE,   C_BLUE_B,   'Terjadwal'

        row = [
            _p(j.lokasi, 8),
            _p(j.label_periode, 7.5, False, C_GRAY, TA_CENTER),
            _p(str(total_d), 8, False, C_DARK, TA_CENTER),
            _p(str(selesai), 8, True,  C_GREEN if selesai == total_d else C_DARK, TA_CENTER),
            _p(f'{pct}%', 8, True, s_color, TA_CENTER),
            _p(s_label, 7.5, True, s_color, TA_CENTER),
            _p(j.catatan[:40] if j.catatan else '-', 7, False, C_GRAY),
        ]
        rows.append(row)

        bg = colors.HexColor('#F8FAFC') if i % 2 == 0 else C_WHITE
        row_styles.append(('BACKGROUND', (0, i+1), (-1, i+1), bg))
        # Warna kolom status
        row_styles.append(('BACKGROUND', (5, i+1), (5, i+1), s_bg))

    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl_style = [
        ('BACKGROUND', (0,0), (-1,0), C_NAVY),
        ('GRID', (0,0), (-1,-1), 0.4, C_BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (0,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
    ] + row_styles
    tbl.setStyle(TableStyle(tbl_style))
    story.append(tbl)
    story.append(Spacer(1, 6*mm))

    # ── Belum Selesai ─────────────────────────────────────────────────────────
    belum = [j for j in jadwal_list if j.status != 'done']
    if belum:
        story.append(_p('JADWAL BELUM SELESAI — PERLU TINDAK LANJUT', 9, True, C_YELLOW))
        story.append(HRFlowable(width=CW, thickness=1, color=C_BORDER, spaceAfter=4))

        for j in belum:
            prog    = j.get_progress()
            belum_d = prog.get('belum', 0)
            selesai = prog.get('selesai', 0)
            total_d = prog.get('total', 0)

            info = [[
                _p(f'{j.lokasi}  —  {j.label_periode}', 8, True, C_DARK),
                _p(f'{selesai}/{total_d} device selesai  ({prog.get("pct",0)}%)',
                   8, False, C_GRAY, TA_RIGHT),
            ]]
            t = Table(info, colWidths=[CW*0.65, CW*0.35])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), C_YELLOW_B),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('LEFTPADDING', (0,0), (0,-1), 8),
                ('RIGHTPADDING', (-1,0), (-1,-1), 8),
            ]))
            story.append(t)

            if belum_d > 0:
                # Cari device yang belum
                from devices.models import Device
                from maintenance.models import Maintenance
                devs = Device.objects.filter(
                    lokasi__iexact=j.lokasi, is_deleted=False
                ).order_by('nama')
                belum_rows = []
                for d in devs:
                    m = Maintenance.objects.filter(
                        device=d,
                        maintenance_type='Preventive',
                        date__year=j.tahun_rencana,
                        date__month=j.bulan_rencana,
                    ).first()
                    if not m:
                        belum_rows.append([
                            _p(d.nama, 7),
                            _p(d.jenis.name if d.jenis else '-', 7, False, C_GRAY, TA_CENTER),
                            _p('Belum ada maintenance periode ini', 7, False, C_RED),
                        ])
                if belum_rows:
                    bw = [CW*0.40, CW*0.20, CW*0.40]
                    bt = Table(belum_rows, colWidths=bw)
                    bt.setStyle(TableStyle([
                        ('GRID', (0,0), (-1,-1), 0.3, C_BORDER),
                        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FFFBF0')),
                        ('TOPPADDING', (0,0), (-1,-1), 4),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                        ('LEFTPADDING', (0,0), (-1,-1), 5),
                    ]))
                    story.append(bt)
            story.append(Spacer(1, 3*mm))

    doc.build(
        story,
        onFirstPage=lambda c, d: _on_page(c, d, tahun, print_date),
        onLaterPages=lambda c, d: _on_page(c, d, tahun, print_date),
    )
    buf.seek(0)
    return buf
