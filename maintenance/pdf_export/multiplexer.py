"""
pdf_export/multiplexer.py
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
    C_BLUE_MID,
    C_GRAY_HEAD,
    C_WHITE,
    C_GRAY_TXT,
    TA_CENTER,
    CW,
    H,
    ML
)


def render(c, y, data):
    m = data.get('mux', {})
    y -= 2*mm

    # Info umum
    y = _draw(c, _sec('II.  INFORMASI MULTIPLEXER'), ML, y)
    y -= 0.5*mm
    LW = 30*mm; VW = CW/2 - LW
    irows = [
        [_p('Brand',7.5,True),      _p(_val(m.get('brand')),7.5),
         _p('Firmware',7.5,True),   _p(_val(m.get('firmware')),7.5)],
        [_p('Sync Source 1',7.5,True), _p(_val(m.get('sync_source_1')),7.5),
         _p('Sync Source 2',7.5,True), _p(_val(m.get('sync_source_2')),7.5)],
        [_p('Suhu Ruangan',7.5,True),  _p(f"{m.get('suhu_ruangan','')} °C" if m.get('suhu_ruangan') else '-',7.5),
         _p('Kebersihan',7.5,True),    _p(_val(m.get('kebersihan')),7.5)],
    ]
    it = Table(irows, colWidths=[LW,VW,LW,VW])
    it.setStyle(_grid([
        ('BACKGROUND',(0,0),(0,-1),C_GRAY_HEAD),('BACKGROUND',(2,0),(2,-1),C_GRAY_HEAD),
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
    ]))
    y = _draw(c, it, ML, y)

    # HS 1 & HS 2
    y -= 2*mm
    y = _draw(c, _sec('III.  DATA HS OPTIKAL'), ML, y)
    y -= 0.5*mm
    HS_C = [13*mm, 20*mm, 18*mm, 20*mm, 18*mm, CW-13*mm-20*mm-18*mm-20*mm-18*mm-18*mm, 18*mm]
    hs_h = [_p('Port',7.5,True,align=TA_CENTER),
            _p('TX Bias (mA)',7.5,True,align=TA_CENTER),
            _p('Jarak (km)',7.5,True,align=TA_CENTER),
            _p('TX (dBm)',7.5,True,align=TA_CENTER),
            _p('Lambda (nm)',7.5,True,align=TA_CENTER),
            _p('Merk',7.5,True),
            _p('BW',7.5,True,align=TA_CENTER)]
    hs_rows = [hs_h]
    for n,pfx in [('1','hs1'),('2','hs2')]:
        hs_rows.append([
            _p(f'HS {n}',7.5,True,C_BLUE_MID,TA_CENTER),
            _p(_val(m.get(f'{pfx}_tx_bias')),7.5,align=TA_CENTER),
            _p(_val(m.get(f'{pfx}_jarak')),7.5,align=TA_CENTER),
            _p(_val(m.get(f'{pfx}_tx')),7.5,align=TA_CENTER),
            _p(_val(m.get(f'{pfx}_lambda')),7.5,align=TA_CENTER),
            _p(_val(m.get(f'{pfx}_merk')),7.5),
            _p(_val(m.get(f'{pfx}_bandwidth')),7.5,align=TA_CENTER),
        ])
    hs_t = Table(hs_rows, colWidths=HS_C)
    hs_t.setStyle(_grid([
        ('BACKGROUND',(0,0),(-1,0),C_GRAY_HEAD),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('BACKGROUND',(0,1),(-1,1),C_WHITE),
        ('BACKGROUND',(0,2),(-1,2),C_GRAY_HEAD),
    ]))
    y = _draw(c, hs_t, ML, y)

    # PSU & FAN
    y -= 2*mm
    y = _draw(c, _sec('IV.  STATUS PSU & FAN'), ML, y)
    y -= 0.5*mm
    PSC = [CW//3]*3
    psu_h = [_p('Unit',7.5,True,align=TA_CENTER),
             _p('Status',7.5,True,align=TA_CENTER),
             _p('Temp Sensor (°C)',7.5,True,align=TA_CENTER)]
    psu_rows = [psu_h]
    for lbl, sk, t1k, t2k, t3k in [
        ('PSU 1','psu1_status','psu1_temp1','psu1_temp2','psu1_temp3'),
        ('PSU 2','psu2_status','psu2_temp1','psu2_temp2','psu2_temp3'),
        ('FAN',  'fan_status', None, None, None),
    ]:
        sv = m.get(sk,'')
        t_str = ' / '.join(str(m.get(k)) for k in [t1k,t2k,t3k] if k and m.get(k) is not None) or '-'
        psu_rows.append([
            _p(lbl,7.5,True,C_BLUE_MID,TA_CENTER),
            _sc(sv),
            _p(t_str,7.5,align=TA_CENTER),
        ])
    psu_t = Table(psu_rows, colWidths=PSC)
    ps_ex = [('BACKGROUND',(0,0),(-1,0),C_GRAY_HEAD),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')]
    for i in range(1,4):
        sv = psu_rows[i][1]
        # sv is already a Paragraph; get original text from _sc result
        pass
    # set status cell BG via per-row
    for ri in range(1,4):
        raw_sv = ['psu1_status','psu2_status','fan_status'][ri-1]
        ps_ex.append(('BACKGROUND',(1,ri),(1,ri),_sbg(m.get(raw_sv,''))))
        ps_ex.append(('BACKGROUND',(0,ri),(0,ri),C_GRAY_HEAD if ri%2==0 else C_WHITE))
    psu_t.setStyle(_grid(ps_ex))
    y = _draw(c, psu_t, ML, y)

    # Slot A-H (hanya yang diisi)
    slots = [(l, m.get(f'slot_{l.lower()}_modul',''), m.get(f'slot_{l.lower()}_isian',''))
             for l in 'ABCDEFGH' if m.get(f'slot_{l.lower()}_modul','').strip()]
    if slots:
        y -= 2*mm
        y = _draw(c, _sec(f'V.  MODUL SLOT ({len(slots)} slot terisi)'), ML, y)
        y -= 0.5*mm
        SC2 = [12*mm, 28*mm, CW-12*mm-28*mm]
        sl_h = [_p('Slot',7.5,True,align=TA_CENTER), _p('Modul',7.5,True), _p('Isian / Keterangan',7.5,True)]
        sl_rows = [sl_h]
        for i,(sl,mod,isi) in enumerate(slots):
            sl_rows.append([
                _p(sl,7.5,True,C_BLUE_MID,TA_CENTER),
                _p(_val(mod),7.5),
                _p(_val(isi),7,False,C_GRAY_TXT),
            ])
        sl_t = Table(sl_rows, colWidths=SC2)
        sl_ex = [('BACKGROUND',(0,0),(-1,0),C_GRAY_HEAD),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')]
        for i in range(1,len(sl_rows)):
            sl_ex.append(('BACKGROUND',(0,i),(-1,i),C_GRAY_HEAD if i%2==0 else C_WHITE))
        sl_t.setStyle(_grid(sl_ex))
        y = _draw(c, sl_t, ML, y)

    cat = m.get('catatan','')
    if cat:
        y -= 2*mm
        y = _draw(c, _sec('VI.  CATATAN'), ML, y)
        y -= 0.5*mm
        ct = Table([[_p(_val(cat),7.5)]], colWidths=[CW])
        ct.setStyle(_grid([('MINROWHEIGHT',(0,0),(-1,-1),8*mm)]))
        y = _draw(c, ct, ML, y)
    return y
