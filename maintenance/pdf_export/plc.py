"""
pdf_export/plc.py
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
    C_BLACK,
    TA_CENTER,
    CW,
    H,
    ML
)


def render(c, y, data):
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
