"""
pdf_export/radio.py
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
    r = data.get('radio', {})
    y -= 2*mm

    # Kondisi lingkungan + peralatan
    y = _draw(c, _sec('II.  KONDISI LINGKUNGAN & PERALATAN'), ML, y)
    y -= 0.5*mm
    LW2 = (CW-2*mm)/2

    env_items = [
        ('Suhu Ruangan',     f"{r.get('suhu_ruangan','')} °C" if r.get('suhu_ruangan') else '-'),
        ('Kebersihan',       _val(r.get('kebersihan'))),
        ('Lampu Penerangan', _val(r.get('lampu_penerangan'))),
        ('Jenis Antena',     _val(r.get('jenis_antena'))),
    ]
    equip_items = [
        ('Radio',        r.get('ada_radio','')),
        ('Battery',      r.get('ada_battery','')),
        ('Power Supply', r.get('ada_power_supply','')),
    ]

    # Kiri: lingkungan (teks biasa)
    tl_rows = [[_p(l,7.5), _p(v,7.5,True,C_BLUE_MID,TA_CENTER)] for l,v in env_items]
    tl = Table(tl_rows, colWidths=[LW2-18*mm, 18*mm])
    tl_ex = [('BACKGROUND',(0,i),(0,i),C_GRAY_HEAD if i%2==0 else C_WHITE) for i in range(len(env_items))]
    tl.setStyle(_grid(tl_ex))

    # Kanan: peralatan (OK/NOK badge)
    merk_items = [
        ('Merk Battery',       _val(r.get('merk_battery'))),
        ('Merk Power Supply',  _val(r.get('merk_power_supply'))),
    ]
    tr_rows = [[_p(l,7.5), _sc(v)] for l,v in equip_items] +               [[_p(l,7.5), _p(v,7.5,False,C_GRAY_TXT,TA_CENTER)] for l,v in merk_items]
    tr = Table(tr_rows, colWidths=[LW2-16*mm, 16*mm])
    tr_ex = []
    for i,(l,v) in enumerate(equip_items):
        tr_ex.append(('BACKGROUND',(1,i),(1,i),_sbg(v)))
        tr_ex.append(('BACKGROUND',(0,i),(0,i),C_GRAY_HEAD if i%2==0 else C_WHITE))
    for i,_ in enumerate(merk_items):
        ri = i + len(equip_items)
        tr_ex.append(('BACKGROUND',(0,ri),(-1,ri),C_GRAY_HEAD if ri%2==0 else C_WHITE))
    tr.setStyle(_grid(tr_ex))

    for t in (tl,tr): t.wrapOn(c,CW,H)
    ty = y
    tl.drawOn(c, ML,              ty - tl._height)
    tr.drawOn(c, ML+LW2+2*mm,     ty - tr._height)
    y = ty - max(tl._height, tr._height)

    y -= 2*mm
    y = _draw(c, _sec('III.  NILAI PENGUKURAN'), ML, y)
    y -= 0.5*mm
    meas = [
        ('SWR',                 _val(r.get('swr')),            '',    '-'),
        ('Power TX',            _val(r.get('power_tx')),       'W',   '-'),
        ('Tegangan Battery',    _val(r.get('tegangan_battery')),'V',  '≥ 11 V'),
        ('Tegangan Power Supply',_val(r.get('tegangan_psu')),  'V',   '13.5-14 V'),
        ('Frekuensi TX / Tone', _val(r.get('frekuensi_tx')),  'MHz', '-'),
        ('Frekuensi RX / Tone', _val(r.get('frekuensi_rx')),  'MHz', '-'),
    ]
    UC = [CW-28*mm-14*mm, 28*mm, 14*mm]
    mb = Table([[_p(l,7.5), _p(v,8,True,C_BLUE_MID,TA_CENTER), _p(f'{s}\n{n}',6.5,False,C_GRAY_TXT,TA_CENTER)]
                for l,v,s,n in meas], colWidths=UC)
    mb.setStyle(_grid([('BACKGROUND',(0,i),(-1,i),C_GRAY_HEAD if i%2==0 else C_WHITE) for i in range(len(meas))]))
    y = _draw(c, mb, ML, y)

    cat = r.get('catatan','')
    if cat:
        y -= 2*mm
        y = _draw(c, _sec('IV.  CATATAN'), ML, y)
        y -= 0.5*mm
        ct = Table([[_p(_val(cat),7.5)]], colWidths=[CW])
        ct.setStyle(_grid([('MINROWHEIGHT',(0,0),(-1,-1),8*mm)]))
        y = _draw(c, ct, ML, y)
    return y
