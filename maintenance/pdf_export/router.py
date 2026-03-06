"""
pdf_export/router.py
Konten PDF untuk perangkat Router dan Switch.
"""
from reportlab.lib.units import mm
from reportlab.platypus import Table
from ._base import (
    _p, _val, _sc, _sbg, _grid, _sec, _draw,
    C_BLUE_MID, C_GRAY_HEAD, C_WHITE, C_GRAY_TXT,
    TA_CENTER, CW, H, ML
)


def render(c, y, data):
    fisik = data.get('fisik', {})
    ukur  = data.get('pengukuran', {})
    port  = data.get('port', {})
    sfp   = data.get('sfp_ports', [])

    y -= 2*mm
    LW2 = 82*mm; RW2 = CW - LW2 - 2*mm; GAP = 2*mm

    fh = _sec('II.  PEMERIKSAAN FISIK', LW2)
    fi = [
        ('Kondisi Fisik Unit',       fisik.get('kondisi_fisik', '')),
        ('Indikator LED Link / Port', fisik.get('led_link', '')),
        ('Kondisi Kabel & Konektor', fisik.get('kondisi_kabel', '')),
    ]
    fb_rows = [[_p(l, 7.5), _sc(v)] for l, v in fi]
    fb = Table(fb_rows, colWidths=[LW2-16*mm, 16*mm])
    fe = []
    for i, (l, v) in enumerate(fi):
        fe.append(('BACKGROUND', (1,i),(1,i), _sbg(v)))
        fe.append(('BACKGROUND', (0,i),(0,i), C_GRAY_HEAD if i%2==0 else C_WHITE))
    fb.setStyle(_grid(fe))

    uh = _sec('III.  NILAI PENGUKURAN', RW2)
    ui = [
        ('Tegangan Input', _val(ukur.get('tegangan_input')), '', '24/48/220 V'),
        ('Suhu Perangkat', _val(ukur.get('suhu_perangkat')), '', '< 60 C'),
        ('CPU Load',       _val(ukur.get('cpu_load')),       '', '< 80 %'),
        ('Memory Usage',   _val(ukur.get('memory_usage')),   '', '< 80 %'),
    ]
    UC = [RW2-28*mm-12*mm, 28*mm, 12*mm]
    ub_rows = [
        [_p(p2, 7.5), _p(v, 8, True, C_BLUE_MID, TA_CENTER),
         _p(f'{s}\n{n}', 6.5, False, C_GRAY_TXT, TA_CENTER)]
        for p2, v, s, n in ui
    ]
    ub = Table(ub_rows, colWidths=UC)
    ue = [('BACKGROUND',(0,i),(-1,i), C_GRAY_HEAD if i%2==0 else C_WHITE)
          for i in range(len(ui))]
    ub.setStyle(_grid(ue))

    for t in (fh, fb, uh, ub): t.wrapOn(c, CW, H)
    ty = y
    fh.drawOn(c, ML,         ty - fh._height)
    fb.drawOn(c, ML,         ty - fh._height - fb._height)
    uh.drawOn(c, ML+LW2+GAP, ty - uh._height)
    ub.drawOn(c, ML+LW2+GAP, ty - uh._height - ub._height)
    y = ty - max(fh._height+fb._height, uh._height+ub._height)

    y -= 2*mm
    y = _draw(c, _sec('IV.  STATUS PORT & INTERFACE'), ML, y)
    y -= 0.5*mm
    P1, P2, P3 = 25*mm, 20*mm, 55*mm; P4 = CW-P1-P2-P3
    ph = [_p('Port Aktif/Total',7.5,True), _p('Routing',7.5,True),
          _p('Detail Port',7.5,True),      _p('Catatan Tambahan',7.5,True)]
    pr = [
        _p(f'{_val(port.get("jumlah_port_aktif"))} / {_val(port.get("jumlah_port_total"))}',
           8, True, C_BLUE_MID, TA_CENTER),
        _sc(port.get('status_routing', '')),
        _p(_val(port.get('detail_port')), 7.5),
        _p(_val(data.get('catatan_tambahan')), 7.5, False, C_GRAY_TXT),
    ]
    pt = Table([ph, pr], colWidths=[P1, P2, P3, P4])
    pt.setStyle(_grid([
        ('BACKGROUND', (0,0),(-1,0), C_GRAY_HEAD),
        ('FONTNAME',   (0,0),(-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (1,1),(1,1),  _sbg(port.get('status_routing', ''))),
    ]))
    y = _draw(c, pt, ML, y)

    if sfp:
        y -= 2*mm
        y = _draw(c, _sec(f'V.  DATA SFP PORT  ({len(sfp)} port)'), ML, y)
        y -= 0.5*mm
        SC = [13*mm, 20*mm, 20*mm, 18*mm, 20*mm,
              CW-13*mm-20*mm-20*mm-18*mm-20*mm-14*mm, 14*mm]
        sh = [_p('Port',7.5,True,align=TA_CENTER),
              _p('Tx (dBm)',7.5,True,align=TA_CENTER),
              _p('Rx (dBm)',7.5,True,align=TA_CENTER),
              _p('Lamda(nm)',7.5,True,align=TA_CENTER),
              _p('Bandwidth',7.5,True,align=TA_CENTER),
              _p('Merk / Tipe',7.5,True),
              _p('Status',7.5,True,align=TA_CENTER)]
        sr = [sh]
        for i, sp in enumerate(sfp):
            sv = (sp.get('status', '') or '').strip().upper()
            sr.append([
                _p(f'SFP {i+1}', 7.5, True, C_BLUE_MID, TA_CENTER),
                _p(_val(sp.get('tx')),        7.5, align=TA_CENTER),
                _p(_val(sp.get('rx')),        7.5, align=TA_CENTER),
                _p(_val(sp.get('lambda')),    7.5, align=TA_CENTER),
                _p(_val(sp.get('bandwidth')), 7.5, align=TA_CENTER),
                _p(_val(sp.get('merk')),      7.5),
                _sc(sv),
            ])
        sfp_tbl = Table(sr, colWidths=SC)
        se = [('BACKGROUND',(0,0),(-1,0),C_GRAY_HEAD),
              ('FONTNAME',  (0,0),(-1,0),'Helvetica-Bold')]
        for i, sp in enumerate(sfp):
            row = i+1
            sv  = (sp.get('status', '') or '').strip().upper()
            se.append(('BACKGROUND',(0,row),(-2,row),
                        C_GRAY_HEAD if i%2==0 else C_WHITE))
            se.append(('BACKGROUND',(-1,row),(-1,row), _sbg(sv)))
        sfp_tbl.setStyle(_grid(se))
        y = _draw(c, sfp_tbl, ML, y)
    return y
