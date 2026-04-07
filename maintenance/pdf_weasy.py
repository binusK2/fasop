# maintenance/pdf_weasy.py
# ============================================================
# PDF Export menggunakan WeasyPrint (HTML -> PDF)
# Install: pip install weasyprint
# ============================================================

import os, base64
from io import BytesIO
from django.template.loader import render_to_string
from django.conf import settings


def _img_uri(path):
    if not path or not os.path.exists(path):
        return ''
    ext = os.path.splitext(path)[1].lower()
    mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}.get(ext, 'image/png')
    with open(path, 'rb') as f:
        return f'data:{mime};base64,{base64.b64encode(f.read()).decode()}'


_TEMPLATE_MAP = {
    'ROUTER':              'maintenance/pdf/router.html',
    'SWITCH':              'maintenance/pdf/router.html',
    'PLC':                 'maintenance/pdf/plc.html',
    'RADIO':               'maintenance/pdf/radio.html',
    'VOIP':                'maintenance/pdf/voip.html',
    'MULTIPLEXER':         'maintenance/pdf/multiplexer.html',
    'RECTIFIER':           'maintenance/pdf/rectifier.html',
    'CATU DAYA':           'maintenance/pdf/rectifier.html',
    'CATUDAYA':            'maintenance/pdf/rectifier.html',
    'RECTIFIER & BATTERY': 'maintenance/pdf/rectifier.html',
    'TELEPROTEKSI':        'maintenance/pdf/teleproteksi.html',
    'GENSET':              'maintenance/pdf/genset.html',
}

_TITLES = {
    'ROUTER':      'Formulir Pemeliharaan Peralatan Router',
    'SWITCH':      'Formulir Pemeliharaan Peralatan Switch',
    'PLC':         'Formulir Pemeliharaan Peralatan PLC',
    'RADIO':       'Formulir Pemeliharaan Peralatan Radio Komunikasi',
    'VOIP':        'Formulir Pemeliharaan Peralatan VoIP',
    'MULTIPLEXER': 'Formulir Pemeliharaan Peralatan Multiplexer',
    'RECTIFIER':   'Formulir Pemeliharaan Peralatan Rectifier dan Battery',
    'CATU DAYA':   'Formulir Pemeliharaan Peralatan Rectifier dan Battery',
}

_v = lambda x: x if x not in (None, '') else '-'


def _base_context(data):
    """Context dasar yang dipakai semua template."""
    info = data.get('info', {})
    sigs = data.get('signatures', {})
    static_root = os.path.join(settings.BASE_DIR, 'static')
    kind = data.get('device_kind', 'GENERIC').strip().upper()

    techs = info.get('technician', '')
    techs_list = [n.strip() for n in techs.split(',') if n.strip()]

    return {
        'title':            _TITLES.get(kind, 'Formulir Pemeliharaan Peralatan'),
        'info':             info,
        'logo_pln':         _img_uri(os.path.join(static_root, 'img', 'pln_logo_conv.png')),
        'logo_danantara':   _img_uri(os.path.join(static_root, 'img', 'danantara_logo.png')),
        'sig_am':           _img_uri(sigs.get('asisten_manager', '')),
        'technicians_list': techs_list,
        'signed_by':        info.get('signed_by', ''),
        'print_by':         data.get('print_by', ''),
        'print_date':       data.get('print_date', ''),
    }


def _ctx_router(data, ctx):
    f = data.get('fisik', {})
    u = data.get('pengukuran', {})
    ctx.update({
        'fisik_items': [
            {'label': 'Kondisi Fisik Unit',       'value': f.get('kondisi_fisik', '')},
            {'label': 'Indikator LED Link / Port', 'value': f.get('led_link', '')},
            {'label': 'Kondisi Kabel & Konektor',  'value': f.get('kondisi_kabel', '')},
        ],
        'pengukuran_items': [
            {'label': 'Tegangan Input', 'value': _v(u.get('tegangan_input')), 'standar': '24/48/220 V'},
            {'label': 'Suhu Perangkat', 'value': _v(u.get('suhu_perangkat')), 'standar': '< 60 °C'},
            {'label': 'CPU Load',       'value': _v(u.get('cpu_load')),       'standar': '< 80 %'},
            {'label': 'Memory Usage',   'value': _v(u.get('memory_usage')),   'standar': '< 80 %'},
        ],
        'port':              data.get('port', {}),
        'sfp_ports':         data.get('sfp_ports', []),
        'catatan_tambahan':  data.get('catatan_tambahan', ''),
    })


def _ctx_plc(data, ctx):
    p = data.get('plc', {})
    items = [
        ('Akses PLC Lokal',    p.get('akses_plc', '')),
        ('Remote Akses PLC',   p.get('remote_akses_plc', '')),
        ('Sinkronisasi Waktu', p.get('time_sync', '')),
        ('Wave Trap',          p.get('wave_trap', '')),
        ('IMU',                p.get('imu', '')),
        ('Kabel Coaxial',      p.get('kabel_coaxial', '')),
    ]
    mid = (len(items) + 1) // 2
    ctx.update({
        'checklist_left':  [{'label': l, 'value': v} for l, v in items[:mid]],
        'checklist_right': [{'label': l, 'value': v} for l, v in items[mid:]],
        'pengukuran_items': [
            {'label': 'Transmission Line Level', 'value': _v(p.get('transmission_line')), 'unit': 'dBm'},
            {'label': 'Rx Pilot Level',          'value': _v(p.get('rx_pilot_level')),    'unit': 'dBm'},
            {'label': 'Frequency TX',            'value': _v(p.get('freq_tx')),           'unit': 'MHz'},
            {'label': 'Bandwidth TX',            'value': _v(p.get('bandwidth_tx')),      'unit': 'MHz'},
            {'label': 'Frequency RX',            'value': _v(p.get('freq_rx')),           'unit': 'MHz'},
            {'label': 'Bandwidth RX',            'value': _v(p.get('bandwidth_rx')),      'unit': 'MHz'},
        ],
        'catatan': data.get('catatan_tambahan', ''),
    })


def _ctx_radio(data, ctx):
    r = data.get('radio', {})
    ctx.update({
        'env_items': [
            {'label': 'Suhu Ruangan',     'value': f"{r['suhu_ruangan']} °C" if r.get('suhu_ruangan') else '-'},
            {'label': 'Kebersihan',        'value': _v(r.get('kebersihan'))},
            {'label': 'Lampu Penerangan',  'value': _v(r.get('lampu_penerangan'))},
            {'label': 'Jenis Antena',      'value': _v(r.get('jenis_antena'))},
        ],
        'equip_items': [
            {'label': 'Radio',        'value': r.get('ada_radio', '')},
            {'label': 'Battery',      'value': r.get('ada_battery', '')},
            {'label': 'Power Supply', 'value': r.get('ada_power_supply', '')},
        ],
        'merk_items': [
            {'label': 'Merk Battery',      'value': _v(r.get('merk_battery'))},
            {'label': 'Merk Power Supply', 'value': _v(r.get('merk_power_supply'))},
        ],
        'pengukuran_items': [
            {'label': 'SWR',                  'value': _v(r.get('swr')),              'standar': '-'},
            {'label': 'Power TX',             'value': _v(r.get('power_tx')),         'standar': 'W'},
            {'label': 'Tegangan Battery',     'value': _v(r.get('tegangan_battery')), 'standar': '>= 11 V'},
            {'label': 'Tegangan Power Supply','value': _v(r.get('tegangan_psu')),     'standar': '13.5-14 V'},
            {'label': 'Frekuensi TX / Tone',  'value': _v(r.get('frekuensi_tx')),    'standar': 'MHz'},
            {'label': 'Frekuensi RX / Tone',  'value': _v(r.get('frekuensi_rx')),    'standar': 'MHz'},
        ],
        'catatan': r.get('catatan', ''),
    })


def _ctx_voip(data, ctx):
    v = data.get('voip', {})
    checks = [
        ('Kondisi Fisik Perangkat', v.get('kondisi_fisik', '')),
        ('NTP Server',              v.get('ntp_server', '')),
        ('Web Config',              v.get('webconfig', '')),
        ('Status Power Supply',     v.get('ps_status', '')),
    ]
    ctx.update({
        'voip': v,
        'checks_left':  [{'label': l, 'value': val} for l, val in checks[:2]],
        'checks_right': [{'label': l, 'value': val} for l, val in checks[2:]],
        'catatan': v.get('catatan', ''),
    })


def _ctx_multiplexer(data, ctx):
    m = data.get('mux', {})
    hs_data = []
    for pfx in ['hs1', 'hs2']:
        hs_data.append({
            'tx_bias':   _v(m.get(f'{pfx}_tx_bias')),
            'jarak':     _v(m.get(f'{pfx}_jarak')),
            'tx':        _v(m.get(f'{pfx}_tx')),
            'lamda':     _v(m.get(f'{pfx}_lambda')),
            'merk':      _v(m.get(f'{pfx}_merk')),
            'bandwidth': _v(m.get(f'{pfx}_bandwidth')),
        })
    psu_data = []
    for lbl, sk, t1, t2, t3 in [
        ('PSU 1', 'psu1_status', 'psu1_temp1', 'psu1_temp2', 'psu1_temp3'),
        ('PSU 2', 'psu2_status', 'psu2_temp1', 'psu2_temp2', 'psu2_temp3'),
        ('FAN',   'fan_status',  None, None, None),
    ]:
        temps = ' / '.join(str(m[k]) for k in [t1, t2, t3] if k and m.get(k) is not None) or '-'
        psu_data.append({'label': lbl, 'status': m.get(sk, ''), 'temps': temps})

    slots = []
    for l in 'ABCDEFGH':
        modul = m.get(f'slot_{l.lower()}_modul', '').strip()
        if modul:
            slots.append({'letter': l, 'modul': modul, 'isian': m.get(f'slot_{l.lower()}_isian', '')})

    ctx.update({
        'mux': m, 'hs_data': hs_data, 'psu_data': psu_data, 'slots': slots,
        'catatan': m.get('catatan', ''),
    })


def _ctx_rectifier(data, ctx):
    r = data.get('rectifier', {})

    # Rect measurements in rows of 4
    RMES = [
        ('V Rectifier', r.get('rect1_v_rectifier'), 'V'),
        ('V Battery',   r.get('rect1_v_battery'),   'V'),
        ('Teg(+) GND',  r.get('rect1_teg_pos_ground'), 'V'),
        ('Teg(-) GND',  r.get('rect1_teg_neg_ground'), 'V'),
        ('V Dropper',   r.get('rect1_v_dropper'),   'V'),
        ('A Rectifier', r.get('rect1_a_rectifier'), 'A'),
        ('A Battery',   r.get('rect1_a_battery'),   'A'),
        ('A Load',      r.get('rect1_a_load'),       'A'),
    ]
    rect_rows = []
    for i in range(0, len(RMES), 4):
        row = []
        for lbl, val, unit in RMES[i:i+4]:
            row.append({'text': lbl, 'is_label': True})
            row.append({'text': f"{val} {unit}" if val else '-', 'is_value': True})
        rect_rows.append(row)

    # Battery measurements
    BMES = [
        ('Jumlah Cell',  _v(r.get('bat1_jumlah')),           False),
        ('Kondisi Kabel', r.get('bat1_kondisi_kabel', ''),   True),
        ('Mur & Baut',    r.get('bat1_kondisi_mur_baut', ''),True),
        ('Sel & Rak',     r.get('bat1_kondisi_sel_rak', ''), True),
        ('Air Battery',   _v(r.get('bat1_air_battery')),     False),
    ]
    bat_rows = []
    for i in range(0, len(BMES), 3):
        row = []
        for lbl, val, is_status in BMES[i:i+3]:
            row.append({'text': lbl, 'is_label': True})
            row.append({'text': str(val), 'is_value': not is_status, 'is_status': is_status})
        bat_rows.append(row)

    # Per-cell data — format di Python agar template tinggal tampilkan
    CELL_KEYS = ['v_float', 'vd_0', 'vd_half', 'vd_1', 'vd_2', 'vf_after', 'v_boost']
    COL_HEADS = ['V Float', 'VD 0 Jam', 'VD ½ Jam', 'VD 1 Jam', 'VD 2 Jam', 'V Float ↓', 'V Boost']

    def _cv(v):
        if v is None or v == '': return '-'
        try:    return f'{float(v):.3f}'
        except: return str(v)

    all_cells  = r.get('bat1_cells') or []
    raw_cells  = [c for c in all_cells if isinstance(c.get('cell'), int)]
    vtotal_raw = next((c for c in all_cells if c.get('cell') == 'vtotal'), {})
    vload_raw  = next((c for c in all_cells if c.get('cell') == 'vload'),  {})

    fmt_cells = [
        {'num': str(c.get('cell', '')).zfill(2), 'vals': [_cv(c.get(k)) for k in CELL_KEYS]}
        for c in raw_cells
    ]
    # Bagi dua kolom agar muat 1 halaman
    half = (len(fmt_cells) + 1) // 2
    fmt_cells_left  = fmt_cells[:half]
    fmt_cells_right = fmt_cells[half:]

    fmt_vtotal_vals = [_cv(vtotal_raw.get(k)) for k in CELL_KEYS]
    fmt_vload_vals  = [_cv(vload_raw.get(k))  for k in CELL_KEYS]

    ctx.update({
        'rect': r, 'rect_measurements': rect_rows, 'bat_measurements': bat_rows,
        'catatan':          r.get('catatan', ''),
        'fmt_cells':        fmt_cells,
        'fmt_cells_left':   fmt_cells_left,
        'fmt_cells_right':  fmt_cells_right,
        'fmt_vtotal_vals':  fmt_vtotal_vals,
        'fmt_vload_vals':   fmt_vload_vals,
        'col_heads':        COL_HEADS,
    })


def _ctx_teleproteksi(data, ctx):
    tp = data.get('tp', {})
    skema_list = []
    for n in range(1, 5):
        skema_list.append({
            'n': n,
            'command':       tp.get(f'skema_{n}_command', ''),
            'send_minus':    tp.get(f'skema_{n}_send_minus'),
            'send_plus':     tp.get(f'skema_{n}_send_plus'),
            'receive_minus': tp.get(f'skema_{n}_receive_minus'),
            'receive_plus':  tp.get(f'skema_{n}_receive_plus'),
            'send_result':   tp.get(f'skema_{n}_send_result', ''),
            'receive_result':tp.get(f'skema_{n}_receive_result', ''),
        })
    ctx.update({
        'tp':         tp,
        'tp_skema':   skema_list,
        'catatan':    tp.get('catatan', ''),
    })


_CTX_BUILDERS = {
    'ROUTER': _ctx_router, 'SWITCH': _ctx_router,
    'PLC': _ctx_plc, 'RADIO': _ctx_radio, 'VOIP': _ctx_voip,
    'MULTIPLEXER': _ctx_multiplexer,
    'RECTIFIER': _ctx_rectifier, 'CATU DAYA': _ctx_rectifier,
    'CATUDAYA': _ctx_rectifier, 'RECTIFIER & BATTERY': _ctx_rectifier,
    'TELEPROTEKSI': _ctx_teleproteksi,
}


def _ctx_genset(data, ctx):
    g = data.get('genset', {})

    def row(item, sub, pln_key, gen_key, ref, rowspan=None):
        return {
            'item': item, 'sub': sub, 'ref': ref,
            'pln': g.get(pln_key), 'gen': g.get(gen_key),
            'rowspan': rowspan,
        }

    genset_rows = [
        row('Frekuensi', 'R-N', 'pln_f_r', 'gen_f_r', 'Hz', rowspan=3),
        row(None,        'S-N', 'pln_f_s', 'gen_f_s', 'Hz'),
        row(None,        'T-N', 'pln_f_t', 'gen_f_t', 'Hz'),
        row('Teg. 1Ph',  'R-N', 'pln_v_rn','gen_v_rn','220 VAC', rowspan=3),
        row(None,        'S-N', 'pln_v_sn','gen_v_sn','220 VAC'),
        row(None,        'T-N', 'pln_v_tn','gen_v_tn','220 VAC'),
        row('Teg. 3Ph',  'R-S', 'pln_v_rs','gen_v_rs','380 VAC', rowspan=3),
        row(None,        'S-T', 'pln_v_st','gen_v_st','380 VAC'),
        row(None,        'T-R', 'pln_v_tr','gen_v_tr','380 VAC'),
        row('Arus Beban','R',   'pln_i_r', 'gen_i_r', 'Ampere', rowspan=3),
        row(None,        'S',   'pln_i_s', 'gen_i_s', 'Ampere'),
        row(None,        'T',   'pln_i_t', 'gen_i_t', 'Ampere'),
    ]

    ctx.update({
        'genset':      g,
        'genset_rows': genset_rows,
        'catatan':     g.get('catatan', ''),
    })


_CTX_BUILDERS['GENSET'] = _ctx_genset


def build_pdf_weasy(data: dict, output):
    """Generate PDF menggunakan WeasyPrint."""
    import weasyprint

    kind = data.get('device_kind', 'GENERIC').strip().upper()
    template_name = _TEMPLATE_MAP.get(kind, 'maintenance/pdf/generic.html')

    ctx = _base_context(data)
    builder = _CTX_BUILDERS.get(kind)
    if builder:
        builder(data, ctx)

    html_string = render_to_string(template_name, ctx)
    html = weasyprint.HTML(string=html_string)

    if isinstance(output, BytesIO):
        output.write(html.write_pdf())
    else:
        html.write_pdf(output)
