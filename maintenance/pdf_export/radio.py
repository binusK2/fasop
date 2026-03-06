"""
pdf_export/radio.py
Konten PDF untuk perangkat Radio Komunikasi.
"""
from reportlab.lib.units import mm
from reportlab.platypus import Table
from ._base import (
    _p, _val, _sc, _sbg, _grid, _sec, _draw,
    C_BLUE_MID, C_GRAY_HEAD, C_WHITE, C_GRAY_TXT,
    TA_CENTER, CW, H, ML
)


def render(c, y, data):
    rad = data.get('radio', {})
    y  -= 2*mm

    y = _draw(c, _sec('II.  KONDISI LINGKUNGAN & PERALATAN'), ML, y)
    y -= 0.5*mm
    env_items = [
        ('Suhu Ruangan',     f"{rad.get('suhu_ruangan','')} °C" if rad.get('suhu_ruangan') else '-'),
        ('Exhaust Fan',      rad.get('exhaust_fan', '')),
        ('Kebersihan',       rad.get('kebersihan', '')),
        ('Lampu Penerangan', rad.get('lampu_penerangan', '')),
    ]
    QW = CW / 4
    env = Table([[_p(l,7.5,True), _p(v,7.5)] for l, v in env_items],
                colWidths=[QW*0.6, QW*1.4]*2)
    env_ex = []
    for i, (l, v) in enumerate(env_items):
        col = (i % 2) * 2
        env_ex.append(('BACKGROUND',(col,i//2),(col,i//2), C_GRAY_HEAD))
    env.setStyle(_grid(env_ex))
    y = _draw(c, env, ML, y)

    y -= 2*mm
    y = _draw(c, _sec('III.  NILAI PENGUKURAN'), ML, y)
    y -= 0.5*mm
    mes = [
        ('Tegangan Input',  _val(rad.get('tegangan_input')),  'V'),
        ('Daya Pancar TX',  _val(rad.get('daya_pancar_tx')),  'dBm'),
        ('Level RX',        _val(rad.get('level_rx')),        'dBm'),
        ('Frek. TX',        _val(rad.get('frek_tx')),         'MHz'),
        ('Frek. RX',        _val(rad.get('frek_rx')),         'MHz'),
        ('VSWR',            _val(rad.get('vswr')),            ''),
        ('BER',             _val(rad.get('ber')),             ''),
        ('Suhu Perangkat',  _val(rad.get('suhu_perangkat')),  '°C'),
    ]
    ncol = 4; MW = CW / ncol
    mes_rows = []
    for i in range(0, len(mes), ncol):
        chunk = mes[i:i+ncol]
        row = []
        for lbl, val, unit in chunk:
            row += [_p(lbl, 7, True, C_GRAY_TXT),
                    _p(f"{val} {unit}".strip() if val != '-' else '-',
                       7.5, True, C_BLUE_MID, TA_CENTER)]
        while len(row) < ncol*2:
            row += [_p(''), _p('')]
        mes_rows.append(row)
    mt = Table(mes_rows, colWidths=[MW/2, MW/2]*ncol)
    mt_ex = []
    for i in range(len(mes_rows)):
        for j in range(0, ncol*2, 2):
            mt_ex.append(('BACKGROUND',(j,i),(j,i), C_GRAY_HEAD))
    mt.setStyle(_grid(mt_ex))
    y = _draw(c, mt, ML, y)

    # Checklist fisik
    checks = [
        ('Kondisi Antena',    rad.get('kondisi_antena', '')),
        ('Kondisi Kabel RF',  rad.get('kondisi_kabel_rf', '')),
        ('Grounding',         rad.get('grounding', '')),
        ('Konektor',          rad.get('kondisi_konektor', '')),
    ]
    if any(v for _, v in checks):
        y -= 2*mm
        y = _draw(c, _sec('IV.  KONDISI FISIK'), ML, y)
        y -= 0.5*mm
        QW4 = CW / 4
        ck_tbl = Table([
            [_p(l, 7, True, C_GRAY_TXT, TA_CENTER) for l, _ in checks],
            [_sc(v) for _, v in checks],
        ], colWidths=[QW4]*4)
        ck_style = [
            ('BACKGROUND',(0,0),(-1,0), C_GRAY_HEAD),
            ('ALIGN',     (0,0),(-1,-1),'CENTER'),
            ('BOX',       (0,0),(-1,-1), 0.4, C_GRAY_TXT.__class__.__module__ and __import__('reportlab.lib.colors',fromlist=['HexColor']).HexColor('#CBD5E1')),
            ('INNERGRID', (0,0),(-1,-1), 0.3, __import__('reportlab.lib.colors',fromlist=['HexColor']).HexColor('#CBD5E1')),
        ]
        for i, (_, v) in enumerate(checks):
            ck_style.append(('BACKGROUND',(i,1),(i,1), _sbg(v)))
        from reportlab.platypus import TableStyle
        ck_tbl.setStyle(TableStyle(ck_style))
        y = _draw(c, ck_tbl, ML, y)

    cat = (rad.get('catatan') or '').strip()
    if cat:
        y -= 2*mm
        y = _draw(c, _sec('V.  CATATAN'), ML, y)
        y -= 0.5*mm
        ct = Table([[_p(cat, 7.5)]], colWidths=[CW])
        ct.setStyle(_grid([('MINROWHEIGHT',(0,0),(-1,-1),8*mm)]))
        y = _draw(c, ct, ML, y)
    return y
