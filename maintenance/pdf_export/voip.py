"""
pdf_export/voip.py
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
    ML,
    W,
    H,
)


def render(c, y, data):
    v = data.get('voip', {})
    y -= 2*mm

    y = _draw(c, _sec('II.  INFORMASI PERANGKAT VoIP'), ML, y)
    y -= 0.5*mm
    LW = 32*mm; VW = CW/2 - LW
    info_rows = [
        [_p('IP Address',7.5,True),     _p(_val(v.get('ip_address')),7.5),
         _p('Extension Number',7.5,True),_p(_val(v.get('extension_number')),7.5)],
        [_p('SIP Server 1',7.5,True),   _p(_val(v.get('sip_server_1')),7.5),
         _p('SIP Server 2',7.5,True),   _p(_val(v.get('sip_server_2')),7.5)],
        [_p('Suhu Ruangan',7.5,True),   _p(f"{v.get('suhu_ruangan','')} °C" if v.get('suhu_ruangan') else '-',7.5),
         _p('Merk PSU',7.5,True),       _p(_val(v.get('ps_merk')),7.5)],
    ]
    it = Table(info_rows, colWidths=[LW,VW,LW,VW])
    it.setStyle(_grid([
        ('BACKGROUND',(0,0),(0,-1),C_GRAY_HEAD),
        ('BACKGROUND',(2,0),(2,-1),C_GRAY_HEAD),
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
        ('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
    ]))
    y = _draw(c, it, ML, y)

    y -= 2*mm
    y = _draw(c, _sec('III.  CHECKLIST STATUS'), ML, y)
    y -= 0.5*mm
    checks = [
        ('Kondisi Fisik Perangkat', v.get('kondisi_fisik','')),
        ('NTP Server',              v.get('ntp_server','')),
        ('Web Config',              v.get('webconfig','')),
        ('Status Power Supply',     v.get('ps_status','')),
    ]
    mid = 2
    LWc = (CW-2*mm)/2; LBL = LWc-16*mm
    def mkcol2(rows):
        t = Table([[_p(l,7.5), _sc(val)] for l,val in rows], colWidths=[LBL,16*mm])
        ex = []
        for i,(_,val) in enumerate(rows):
            ex.append(('BACKGROUND',(1,i),(1,i),_sbg(val)))
            ex.append(('BACKGROUND',(0,i),(0,i),C_GRAY_HEAD if i%2==0 else C_WHITE))
        t.setStyle(_grid(ex)); return t
    cl = mkcol2(checks[:mid]); cr = mkcol2(checks[mid:])
    for t in (cl,cr): t.wrapOn(c,CW,H)
    ty=y
    cl.drawOn(c, ML,            ty-cl._height)
    cr.drawOn(c, ML+LWc+2*mm,   ty-cr._height)
    y = ty - max(cl._height, cr._height)

    y -= 2*mm
    y = _draw(c, _sec('IV.  TEGANGAN INPUT PSU'), ML, y)
    y -= 0.5*mm
    pv = _val(v.get('ps_tegangan_input'))
    psu_t = Table([[_p('Tegangan Input PSU',7.5),
                    _p(pv,8,True,C_BLUE_MID,TA_CENTER),
                    _p('V\n210-240 V',6.5,False,C_GRAY_TXT,TA_CENTER)]],
                  colWidths=[CW-28*mm-14*mm, 28*mm, 14*mm])
    psu_t.setStyle(_grid([('BACKGROUND',(0,0),(-1,-1),C_GRAY_HEAD)]))
    y = _draw(c, psu_t, ML, y)

    cat = v.get('catatan','')
    if cat:
        y -= 2*mm
        y = _draw(c, _sec('V.  CATATAN'), ML, y)
        y -= 0.5*mm
        ct = Table([[_p(_val(cat),7.5)]], colWidths=[CW])
        ct.setStyle(_grid([('MINROWHEIGHT',(0,0),(-1,-1),8*mm)]))
        y = _draw(c, ct, ML, y)
    return y