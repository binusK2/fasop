"""
pdf_export/rectifier.py
"""
from reportlab.lib.units import mm
from reportlab.platypus import Table
from ._base import (
    _p,
    _val,
    _sc,
    _sbg,
    _grid,
    _sec,
    _draw,
    C_BLUE_DARK,
    C_BLUE_MID,
    C_GRAY_HEAD,
    C_GRAY_LINE,
    C_GRAY_TXT,
    C_BLACK,
    C_WHITE,
    C_GREEN_BG,
    C_RED_BG,
    TA_CENTER,
    CW,
    ML
)


def render(c, y, data):
    r = data.get('rectifier', {})
    y -= 2*mm

    # Lingkungan
    y = _draw(c, _sec('II.  KONDISI LINGKUNGAN'), ML, y)
    y -= 0.5*mm
    LW = 38*mm; VW = CW - LW*2 - 4*mm
    env_rows = [[
        _p('Suhu Ruangan',7.5,True),
        _p(f"{r.get('suhu_ruangan','')} °C" if r.get('suhu_ruangan') else '-',7.5),
        _p('Exhaust Fan',7.5,True),  _p(_val(r.get('exhaust_fan')),7.5),
    ],[
        _p('Kebersihan',7.5,True),   _p(_val(r.get('kebersihan')),7.5),
        _p('Lampu Penerangan',7.5,True), _p(_val(r.get('lampu_penerangan')),7.5),
    ]]
    et = Table(env_rows, colWidths=[LW,VW,LW,VW])
    et.setStyle(_grid([
        ('BACKGROUND',(0,0),(0,-1),C_GRAY_HEAD),('BACKGROUND',(2,0),(2,-1),C_GRAY_HEAD),
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
    ]))
    y = _draw(c, et, ML, y)

    # Rectifier 1
    y -= 2*mm
    y = _draw(c, _sec('III.  RECTIFIER'), ML, y)
    y -= 0.5*mm
    # Header identitas rectifier
    rc1 = [r.get('rect1_merk',''), r.get('rect1_tipe',''), r.get('rect1_kondisi',''), r.get('rect1_kapasitas','')]
    ri_t = Table([[_p('Merk',7.5,True), _p(_val(rc1[0]),7.5),
                   _p('Tipe',7.5,True), _p(_val(rc1[1]),7.5),
                   _p('Kondisi',7.5,True), _sc(rc1[2]),
                   _p('Kapasitas',7.5,True), _p(_val(rc1[3]),7.5)]],
                 colWidths=[18*mm]*8)
    ri_t.setStyle(_grid([
        ('BACKGROUND',(0,0),(0,0),C_GRAY_HEAD),('BACKGROUND',(2,0),(2,0),C_GRAY_HEAD),
        ('BACKGROUND',(4,0),(4,0),C_GRAY_HEAD),('BACKGROUND',(6,0),(6,0),C_GRAY_HEAD),
        ('BACKGROUND',(5,0),(5,0),_sbg(rc1[2])),
    ]))
    y = _draw(c, ri_t, ML, y)
    y -= 0.5*mm
    # Pengukuran rectifier
    RMES = [
        ('V Rectifier', r.get('rect1_v_rectifier'), 'V'),
        ('V Battery',   r.get('rect1_v_battery'),   'V'),
        ('Teg(+) GND',  r.get('rect1_teg_pos_ground'),'V'),
        ('Teg(-) GND',  r.get('rect1_teg_neg_ground'),'V'),
        ('V Dropper',   r.get('rect1_v_dropper'),   'V'),
        ('A Rectifier', r.get('rect1_a_rectifier'), 'A'),
        ('A Battery',   r.get('rect1_a_battery'),   'A'),
        ('A Load',      r.get('rect1_a_load'),       'A'),
    ]
    ncol=4; RCW = CW/ncol
    rmes_rows=[]
    for i in range(0,len(RMES),ncol):
        chunk=RMES[i:i+ncol]
        row=[]
        for lbl,val,unit in chunk:
            row+=[_p(lbl,7,True,C_GRAY_TXT), _p(f"{val} {unit}" if val else '-',7.5,True,C_BLUE_MID,TA_CENTER)]
        while len(row)<ncol*2: row+=[_p(''),_p('')]
        rmes_rows.append(row)
    rt = Table(rmes_rows, colWidths=[RCW/2,RCW/2]*ncol)
    rt_ex = []
    for i in range(len(rmes_rows)):
        for j in range(0,ncol*2,2):
            rt_ex.append(('BACKGROUND',(j,i),(j,i),C_GRAY_HEAD))
    rt.setStyle(_grid(rt_ex))
    y = _draw(c, rt, ML, y)

    # Battery Bank 1
    y -= 2*mm
    y = _draw(c, _sec('IV.  BATTERY BANK 1'), ML, y)
    y -= 0.5*mm
    bc1 = [r.get('bat1_merk',''), r.get('bat1_tipe',''), r.get('bat1_kondisi',''), r.get('bat1_kapasitas',''), r.get('bat1_jumlah','')]
    bi_t = Table([[_p('Merk',7.5,True), _p(_val(bc1[0]),7.5),
                   _p('Tipe',7.5,True), _p(_val(bc1[1]),7.5),
                   _p('Kondisi',7.5,True), _sc(bc1[2]),
                   _p('Kapasitas',7.5,True), _p(_val(bc1[3]),7.5)]],
                 colWidths=[18*mm]*8)
    bi_t.setStyle(_grid([
        ('BACKGROUND',(0,0),(0,0),C_GRAY_HEAD),('BACKGROUND',(2,0),(2,0),C_GRAY_HEAD),
        ('BACKGROUND',(4,0),(4,0),C_GRAY_HEAD),('BACKGROUND',(6,0),(6,0),C_GRAY_HEAD),
        ('BACKGROUND',(5,0),(5,0),_sbg(bc1[2])),
    ]))
    y = _draw(c, bi_t, ML, y)
    y -= 0.5*mm
    bat_checks = [
        ('Jumlah Cell',    _val(bc1[4]),                    ''),
        ('Kondisi Kabel',  r.get('bat1_kondisi_kabel',''),   'status'),
        ('Mur & Baut',     r.get('bat1_kondisi_mur_baut',''),'status'),
        ('Sel & Rak',      r.get('bat1_kondisi_sel_rak',''), 'status'),
        ('Air Battery',    _val(r.get('bat1_air_battery')),  'V'),
        ('V Total Bank',   _val(r.get('bat1_v_total')),      'V'),
        ('V Load',         _val(r.get('bat1_v_load')),       'V'),
    ]
    BC_COLS = int(CW/(CW/3)); bc_rows=[]
    ncol2=3; BCW=CW/ncol2
    for i in range(0,len(bat_checks),ncol2):
        chunk=bat_checks[i:i+ncol2]
        row=[]
        for lbl,val,kind in chunk:
            if kind=='status': row+=[_p(lbl,7,True,C_GRAY_TXT), _sc(val)]
            else:              row+=[_p(lbl,7,True,C_GRAY_TXT), _p(str(val),7.5,True,C_BLUE_MID,TA_CENTER)]
        while len(row)<ncol2*2: row+=[_p(''),_p('')]
        bc_rows.append(row)
    bct = Table(bc_rows, colWidths=[BCW/2,BCW/2]*ncol2)
    bct_ex = []
    for i in range(len(bc_rows)):
        for j in range(0,ncol2*2,2):
            bct_ex.append(('BACKGROUND',(j,i),(j,i),C_GRAY_HEAD))
        # Color status cells
        for j2,(lbl,val,kind) in enumerate(bat_checks[i*ncol2:(i+1)*ncol2]):
            if kind=='status':
                bct_ex.append(('BACKGROUND',(j2*2+1,i),(j2*2+1,i),_sbg(val)))
    bct.setStyle(_grid(bct_ex))
    y = _draw(c, bct, ML, y)

    cat = r.get('catatan','')
    if cat:
        y -= 2*mm
        y = _draw(c, _sec('V.  CATATAN'), ML, y)
        y -= 0.5*mm
        ct = Table([[_p(_val(cat),7.5)]], colWidths=[CW])
        ct.setStyle(_grid([('MINROWHEIGHT',(0,0),(-1,-1),8*mm)]))
        y = _draw(c, ct, ML, y)
    return y
