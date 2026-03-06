"""
pdf_export/rectifier.py
Konten PDF untuk perangkat Rectifier dan Battery (Catu Daya).
Mengikuti layout form resmi PLN UP2B_FML_04_2012.
"""
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from ._base import (
    _p, _val, _sc, _sbg, _grid, _sec, _draw,
    C_BLUE_DARK, C_BLUE_MID, C_GRAY_HEAD, C_GRAY_LINE, C_GRAY_TXT,
    C_BLACK, C_WHITE, C_GREEN_BG, C_RED_BG,
    TA_CENTER, CW, ML
)


def render(c, y, data):
    """Layout mengikuti form resmi PLN UP2B_FML_04_2012."""
    r   = data.get('rectifier', {})
    GAP = 1*mm

    # ── II. KONDISI LINGKUNGAN ─────────────────────────────────────
    y = _draw(c, _sec('II.  KONDISI LINGKUNGAN'), ML, y)
    QW = CW / 4
    env = Table([[
        _p('Suhu Ruangan', 7, True),
        _p(f"{r.get('suhu_ruangan','')} °C" if r.get('suhu_ruangan') else '—', 7),
        _p('Exhaust Fan', 7, True), _sc(r.get('exhaust_fan', '')),
    ],[
        _p('Kebersihan', 7, True), _sc(r.get('kebersihan', '')),
        _p('Lampu Penerangan', 7, True), _sc(r.get('lampu_penerangan', '')),
    ]], colWidths=[QW]*4)
    env.setStyle(_grid([
        ('BACKGROUND', (0,0),(0,-1), C_GRAY_HEAD),
        ('BACKGROUND', (2,0),(2,-1), C_GRAY_HEAD),
        ('FONTNAME',   (0,0),(0,-1), 'Helvetica-Bold'),
        ('FONTNAME',   (2,0),(2,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (1,0),(1,0),  _sbg(r.get('exhaust_fan',''))),
        ('BACKGROUND', (1,1),(1,1),  _sbg(r.get('kebersihan',''))),
        ('BACKGROUND', (3,1),(3,1),  _sbg(r.get('lampu_penerangan',''))),
    ]))
    y = _draw(c, env, ML, y); y -= GAP

    # ── III. PERALATAN TERPASANG ──────────────────────────────────
    y = _draw(c, _sec('III.  PERALATAN TERPASANG & PENGUKURAN'), ML, y)

    # Baris identitas Rectifier + Battery (5 kolom)
    rc  = [r.get('rect1_merk',''), r.get('rect1_tipe',''),
           r.get('rect1_kondisi',''), r.get('rect1_kapasitas','')]
    bc  = [r.get('bat1_merk',''),  r.get('bat1_tipe',''),
           r.get('bat1_kondisi',''), r.get('bat1_kapasitas','')]

    ID_W = [18*mm, CW*0.22, CW*0.22, 16*mm, CW*0.14]
    id_tbl = Table([
        [_p('Rectifier',7,True,C_WHITE,TA_CENTER),
         _p(_val(rc[0]),7), _p(_val(rc[1]),7),
         _sc(rc[2]),
         _p(_val(rc[3]),7,True,C_BLUE_MID,TA_CENTER)],
        [_p('Battery',7,True,C_WHITE,TA_CENTER),
         _p(_val(bc[0]),7), _p(_val(bc[1]),7),
         _sc(bc[2]),
         _p(_val(bc[3]),7,True,C_BLUE_MID,TA_CENTER)],
    ], colWidths=ID_W)
    id_tbl.setStyle(_grid([
        ('BACKGROUND', (0,0),(0,-1), C_BLUE_DARK),
        ('ALIGN',      (3,0),(4,-1), 'CENTER'),
        ('BACKGROUND', (3,0),(3,0),  _sbg(rc[2])),
        ('BACKGROUND', (3,1),(3,1),  _sbg(bc[2])),
    ]))
    y = _draw(c, id_tbl, ML, y)

    # Pengukuran — 8 item dalam 2 baris (label atas, nilai bawah)
    MES = [
        ('V Rectifier',  r.get('rect1_v_rectifier'),  'V'),
        ('V Battery',    r.get('rect1_v_battery'),    'V'),
        ('Teg(+) GND',   r.get('rect1_teg_pos_ground'),'V'),
        ('Teg(-) GND',   r.get('rect1_teg_neg_ground'),'V'),
        ('V Dropper',    r.get('rect1_v_dropper'),    'V'),
        ('A Rectifier',  r.get('rect1_a_rectifier'),  'A'),
        ('A Battery',    r.get('rect1_a_battery'),    'A'),
        ('A Load',       r.get('rect1_a_load'),       'A'),
    ]
    MW = CW / 8
    lbl_row = [_p(l, 6.5, True, C_GRAY_TXT, TA_CENTER) for l,_,_ in MES]
    val_row = [_p(f"{v} {u}" if v else '—', 7.5, True, C_BLUE_MID, TA_CENTER)
               for _,v,u in MES]
    mes_tbl = Table([lbl_row, val_row], colWidths=[MW]*8)
    mes_tbl.setStyle(_grid([
        ('BACKGROUND', (0,0),(-1,0), C_GRAY_HEAD),
        ('ALIGN',      (0,0),(-1,-1), 'CENTER'),
        ('LINEAFTER',  (4,0),(4,-1),  0.8, C_GRAY_LINE),
        ('TOPPADDING', (0,1),(- 1,1), 3.5),
        ('BOTTOMPADDING',(0,1),(-1,1),3.5),
    ]))
    y = _draw(c, mes_tbl, ML, y); y -= GAP

    # ── IV. BATTERY BANK ──────────────────────────────────────────
    y = _draw(c, _sec('IV.  BATTERY BANK'), ML, y)

    # Kondisi fisik — 4 item 1 baris
    fis_items = [
        ('Kabel Battery', r.get('bat1_kondisi_kabel',''),    'status'),
        ('Mur & Baut',    r.get('bat1_kondisi_mur_baut',''), 'status'),
        ('Sel & Rak',     r.get('bat1_kondisi_sel_rak',''),  'status'),
        ('Jumlah Cell',   _val(r.get('bat1_jumlah','')),     'val'),
    ]
    QW4 = CW / 4
    fis_tbl = Table([
        [_p(l,6.5,True,C_GRAY_TXT,TA_CENTER) for l,_,_ in fis_items],
        [_sc(v) if k=='status' else _p(v,7.5,True,C_BLUE_MID,TA_CENTER)
         for _,v,k in fis_items],
    ], colWidths=[QW4]*4)
    fis_style = TableStyle([
        ('BACKGROUND',    (0,0),(-1,0), C_GRAY_HEAD),
        ('ALIGN',         (0,0),(-1,-1),'CENTER'),
        ('BOX',           (0,0),(-1,-1), 0.4, C_GRAY_LINE),
        ('INNERGRID',     (0,0),(-1,-1), 0.3, C_GRAY_LINE),
        ('TOPPADDING',    (0,0),(-1,-1), 2),
        ('BOTTOMPADDING', (0,0),(-1,-1), 2),
        ('LEFTPADDING',   (0,0),(-1,-1), 3),
        ('RIGHTPADDING',  (0,0),(-1,-1), 3),
    ])
    for i,(l,v,k) in enumerate(fis_items):
        if k == 'status':
            fis_style.add('BACKGROUND', (i,1),(i,1), _sbg(v))
    fis_tbl.setStyle(fis_style)
    y = _draw(c, fis_tbl, ML, y)

    # ── V. PENGUKURAN TEGANGAN PER CELL BATTERY ───────────────────
    cells = r.get('bat1_cells') or []
    if cells:
        y -= GAP
        y = _draw(c, _sec('V.  PENGUKURAN TEGANGAN PER CELL BATTERY'), ML, y)

        COL_LBL = ['Cell', 'V Float', 'VD 0J', 'VD ½J', 'VD 1J', 'VD 2J', 'V Boost']
        N = len(COL_LBL)
        cells_s = sorted(cells, key=lambda x: int(x.get('cell',0)))
        left  = [x for x in cells_s if int(x.get('cell',0)) <= 20]
        right = [x for x in cells_s if int(x.get('cell',0)) > 20]
        n_rows = max(len(left), len(right))

        # Kolom: nomor cell sempit (5.5mm), kolom nilai mengisi sisa
        CN = 5.5*mm
        CV = (CW/2 - CN) / (N - 1)
        col_w = ([CN] + [CV]*(N-1)) * 2

        hdr = [_p(l, 5.5, True, C_WHITE, TA_CENTER) for l in COL_LBL] * 2
        cell_rows = [hdr]
        for i in range(n_rows):
            row = []
            for side in [left, right]:
                if i < len(side):
                    cd = side[i]
                    def cv(k, _cd=cd):
                        return _p(_val(_cd.get(k)), 6, False, C_BLACK, TA_CENTER)
                    row += [
                        _p(str(cd.get('cell','')), 6.5, True, C_BLUE_MID, TA_CENTER),
                        cv('v_float'), cv('vd_0'), cv('vd_half'),
                        cv('vd_1'), cv('vd_2'), cv('v_boost'),
                    ]
                else:
                    row += [_p('', 6)] * N
            cell_rows.append(row)

        ct = Table(cell_rows, colWidths=col_w)
        ct.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(N*2-1,0), C_BLUE_DARK),
            ('BOX',           (0,0),(-1,-1),    0.4, C_GRAY_LINE),
            ('INNERGRID',     (0,0),(-1,-1),    0.3, C_GRAY_LINE),
            ('LINEAFTER',     (N-1,0),(N-1,-1), 1.2, colors.HexColor('#334155')),
            ('TOPPADDING',    (0,0),(-1,-1),    1),
            ('BOTTOMPADDING', (0,0),(-1,-1),    1),
            ('LEFTPADDING',   (0,0),(-1,-1),    1.5),
            ('RIGHTPADDING',  (0,0),(-1,-1),    1.5),
            ('VALIGN',        (0,0),(-1,-1),    'MIDDLE'),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),    [C_WHITE, C_GRAY_HEAD]),
        ]))
        y = _draw(c, ct, ML, y)

    # Ringkasan: Air Battery = ... / V Total = ... / V Load = ...
    # Persis seperti form asli — di bawah tabel cell
    air = _val(r.get('bat1_air_battery'))
    vt  = _val(r.get('bat1_v_total'))
    vl  = _val(r.get('bat1_v_load'))
    W3  = CW / 3
    sum_tbl = Table([[
        _p(f'Air Battery  =  {air} V', 7.5, True, C_BLACK,    TA_CENTER),
        _p(f'V Total  =  {vt} V',      7.5, True, C_BLUE_MID, TA_CENTER),
        _p(f'V Load  =  {vl} V',       7.5, True, C_BLUE_MID, TA_CENTER),
    ]], colWidths=[W3]*3)
    sum_tbl.setStyle(_grid([
        ('BACKGROUND', (0,0),(0,0), C_GRAY_HEAD),
        ('BACKGROUND', (1,0),(2,0), colors.HexColor('#EFF6FF')),
        ('ALIGN',      (0,0),(-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0),(-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1),4),
    ]))
    y = _draw(c, sum_tbl, ML, y)

    # Catatan
    cat = (r.get('catatan') or '').strip()
    if cat:
        y -= GAP
        y = _draw(c, _sec('VI.  CATATAN'), ML, y)
        ct2 = Table([[_p(cat, 7)]], colWidths=[CW])
        ct2.setStyle(_grid([('MINROWHEIGHT',(0,0),(-1,-1), 7*mm)]))
        y = _draw(c, ct2, ML, y)
    return y
