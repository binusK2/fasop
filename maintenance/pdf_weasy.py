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
    'REPEATER':            'maintenance/pdf/repeater.html',
    'REPEATER & TOWER':    'maintenance/pdf/repeater.html',
    'VOIP':                'maintenance/pdf/voip.html',
    'MULTIPLEXER':         'maintenance/pdf/multiplexer.html',
    'RECTIFIER':           'maintenance/pdf/rectifier.html',
    'CATU DAYA':           'maintenance/pdf/rectifier.html',
    'CATUDAYA':            'maintenance/pdf/rectifier.html',
    'RECTIFIER & BATTERY': 'maintenance/pdf/rectifier.html',
    'TELEPROTEKSI':        'maintenance/pdf/teleproteksi.html',
    'GENSET':              'maintenance/pdf/genset.html',
    'RTU':                 'maintenance/pdf/rtu.html',
    'RTU_GENERIC':         'maintenance/pdf/sas.html',
    'IED BCU':             'maintenance/pdf/bcu.html',
    'BCU':                 'maintenance/pdf/bcu.html',
    'SAS':                 'maintenance/pdf/sas.html',
    'SERVER SCADA':        'maintenance/pdf/sas.html',
    'GATEWAY SAS':         'maintenance/pdf/sas.html',
    'MASTER STATION':      'maintenance/pdf/master_station.html',
    'WORKSTATION SCADA':   'maintenance/pdf/master_station.html',
    'SERVER TELKOM':       'maintenance/pdf/master_station.html',
    'SERVER PROSIS':       'maintenance/pdf/master_station.html',
    'WORKSTATION PC':      'maintenance/pdf/master_station.html',
    'ROIP':                'maintenance/pdf/roip.html',
    'UPS':                 'maintenance/pdf/ups.html',
    'UFLS':            'maintenance/pdf/ufls.html',
    'UFR ISLAND':      'maintenance/pdf/ufls.html',
    'OFGS':            'maintenance/pdf/ufls.html',
    'CDSAS':           'maintenance/pdf/ufls.html',
    'FREQUENCY RELAY': 'maintenance/pdf/ufls.html',
    'MASTER TRIP':          'maintenance/pdf/master_trip.html',
    'RELE DEFENSE SCHEME':  'maintenance/pdf/master_trip.html',
    'DEFENSE SCHEME':       'maintenance/pdf/master_trip.html',
    'DFR':                  'maintenance/pdf/dfr.html',
    'PMU':                  'maintenance/pdf/dfr.html',
}

_CORRECTIVE_TEMPLATE = 'maintenance/pdf/corrective.html'

_TITLES = {
    'ROUTER':       'Formulir Pemeliharaan Peralatan Router',
    'SWITCH':       'Formulir Pemeliharaan Peralatan Switch',
    'PLC':          'Formulir Pemeliharaan Peralatan PLC',
    'RADIO':        'Formulir Pemeliharaan Peralatan Radio Komunikasi',
    'REPEATER':     'Formulir Pemeliharaan Peralatan Repeater',
    'REPEATER & TOWER': 'Formulir Pemeliharaan Peralatan Repeater',
    'VOIP':         'Formulir Pemeliharaan Peralatan VoIP',
    'MULTIPLEXER':  'Formulir Pemeliharaan Peralatan Multiplexer',
    'GENSET':       'Formulir Pemeliharaan Peralatan Genset',
    'TELEPROTEKSI': 'Formulir Pemeliharaan Peralatan Teleproteksi',
    'RECTIFIER':    'Formulir Pemeliharaan Peralatan Rectifier dan Battery',
    'CATU DAYA':    'Formulir Pemeliharaan Peralatan Rectifier dan Battery',
    'RTU':          'Formulir Pemeliharaan Peralatan RTU AK3',
    'RTU_GENERIC':  'Formulir Pemeliharaan Peralatan RTU',
    'IED BCU':      'Formulir Pemeliharaan Peralatan BCU',
    'BCU':          'Formulir Pemeliharaan Peralatan BCU',
    'SAS':               'Formulir Pemeliharaan Peralatan SAS / Server SCADA',
    'SERVER SCADA':      'Formulir Pemeliharaan Peralatan Server SCADA',
    'GATEWAY SAS':       'Formulir Pemeliharaan Peralatan Gateway SAS',
    'MASTER STATION':    'Formulir Pemeliharaan Server / Workstation Master Station',
    'WORKSTATION SCADA': 'Formulir Pemeliharaan Server / Workstation SCADA',
    'SERVER TELKOM':     'Formulir Pemeliharaan Server Telkom',
    'SERVER PROSIS':     'Formulir Pemeliharaan Server Prosis',
    'WORKSTATION PC':    'Formulir Pemeliharaan Workstation PC',
    'ROIP':         'Formulir Pemeliharaan Peralatan RoIP',
    'UPS':          'Formulir Pemeliharaan Peralatan UPS',
    'UFLS':            'Form Checklist Frequency Relay — UFLS',
    'UFR ISLAND':      'Form Checklist Frequency Relay — UFR Island',
    'OFGS':            'Form Checklist Frequency Relay — OFGS',
    'CDSAS':           'Form Checklist Frequency Relay — CDSAS',
    'FREQUENCY RELAY': 'Form Checklist Frequency Relay',
    'MASTER TRIP':         'Form Checklist Master Trip',
    'RELE DEFENSE SCHEME': 'Form Checklist Rele Defense Scheme',
    'DEFENSE SCHEME':      'Form Checklist Rele Defense Scheme',
    'DFR':                 'Form Checklist DFR / PMU',
    'PMU':                 'Form Checklist DFR / PMU',
}

_CORRECTIVE_TITLE = 'Laporan Corrective Maintenance'

_v = lambda x: x if x not in (None, '') else '-'


_DOC_CODES = {
    'RECTIFIER':           'UP2B_FML_04_2012',
    'CATU DAYA':           'UP2B_FML_04_2012',
    'CATUDAYA':            'UP2B_FML_04_2012',
    'RECTIFIER & BATTERY': 'UP2B_FML_04_2012',
    'MULTIPLEXER':         'UP2B_FML_04_2007',
    'PLC':                 '',
    'RADIO':               'UP2B_FML_04_2001',
    'ROUTER':              'UP2B_FML_04',
    'SWITCH':              'UP2B_FML_04',
    'TELEPROTEKSI':        'UP2B_FML_04_2008',
    'VOIP':                '',
    'GENSET':              '',
    'RTU':                 '',
    'RTU_GENERIC':         '',
    'IED BCU':             '',
    'BCU':                 '',
    'SAS':                 '',
    'SERVER SCADA':        '',
    'GATEWAY SAS':         '',
    'MASTER STATION':      'UP2B_FML_04_1002',
    'WORKSTATION SCADA':   'UP2B_FML_04_1002',
    'SERVER TELKOM':       'UP2B_FML_04_1002',
    'SERVER PROSIS':       'UP2B_FML_04_1002',
    'WORKSTATION PC':      'UP2B_FML_04_1002',
    'ROIP':                '',
    'UPS':                 '',
    'UFLS':            '',
    'UFR ISLAND':      '',
    'OFGS':            '',
    'CDSAS':           '',
    'FREQUENCY RELAY': '',
    'MASTER TRIP':         '',
    'RELE DEFENSE SCHEME': '',
    'DEFENSE SCHEME':      '',
    'DFR':                 '',
    'PMU':                 '',
}


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
        'header_pln':       _img_uri(os.path.join(static_root, 'img', 'header_pln.png')),
        'doc_code':         _DOC_CODES.get(kind, ''),
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
        'modul_terpasang': p.get('modul_terpasang') or [],
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


def _ctx_repeater(data, ctx):
    r = data.get('repeater', {})
    ctx.update({
        'env_items': [
            {'label': 'Suhu Ruangan',     'value': f"{r['suhu_ruangan']} °C" if r.get('suhu_ruangan') else '-'},
            {'label': 'Kebersihan',        'value': _v(r.get('kebersihan'))},
            {'label': 'Lampu Penerangan',  'value': _v(r.get('lampu_penerangan'))},
            {'label': 'Jenis Antena',      'value': _v(r.get('jenis_antena'))},
        ],
        'equip_items': [
            {'label': 'Radio TX',     'value': r.get('ada_radio_tx', '')},
            {'label': 'Radio RX',     'value': r.get('ada_radio_rx', '')},
            {'label': 'Battery',      'value': r.get('ada_battery', '')},
            {'label': 'Power Supply', 'value': r.get('ada_power_supply', '')},
        ],
        'merk_items': [
            {'label': 'Merk Battery',      'value': _v(r.get('merk_battery'))},
            {'label': 'Merk Power Supply', 'value': _v(r.get('merk_power_supply'))},
        ],
        'tx_items': [
            {'label': 'Merk Radio TX',        'value': _v(r.get('merk_radio_tx'))},
            {'label': 'Tipe/Model Radio TX',  'value': _v(r.get('tipe_radio_tx'))},
            {'label': 'SWR TX',                'value': _v(r.get('swr_tx')),     'standar': '-'},
            {'label': 'Power TX',              'value': _v(r.get('power_tx')),   'standar': 'W'},
            {'label': 'Frekuensi TX / Tone',   'value': _v(r.get('frekuensi_tx')), 'standar': 'MHz'},
        ],
        'rx_items': [
            {'label': 'Merk Radio RX',        'value': _v(r.get('merk_radio_rx'))},
            {'label': 'Tipe/Model Radio RX',  'value': _v(r.get('tipe_radio_rx'))},
            {'label': 'SWR RX',                'value': _v(r.get('swr_rx')),     'standar': '-'},
            {'label': 'Frekuensi RX / Tone',   'value': _v(r.get('frekuensi_rx')), 'standar': 'MHz'},
        ],
        'pengukuran_items': [
            {'label': 'Tegangan Battery',      'value': _v(r.get('tegangan_battery')), 'standar': '>= 11 V'},
            {'label': 'Tegangan Power Supply', 'value': _v(r.get('tegangan_psu')),     'standar': '13.5-14 V'},
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
        ('Pengujian Perangkat',     v.get('pengujian_perangkat', '')),
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
        ('V Load',      r.get('rect1_v_load'),       'V'),
        ('Teg(+) GND',  r.get('rect1_teg_pos_ground'), 'V'),
        ('Teg(-) GND',  r.get('rect1_teg_neg_ground'), 'V'),
        ('V Dropper',   r.get('rect1_v_dropper'),   'V'),
        ('A Rectifier', r.get('rect1_a_rectifier'), 'A'),
        ('A Battery',   r.get('rect1_a_battery'),   'A'),
        ('A Load',      r.get('rect1_a_load'),       'A'),
    ]
    rect_rows = []
    for i in range(0, len(RMES), 3):
        row = []
        for lbl, val, unit in RMES[i:i+3]:
            row.append({'text': lbl, 'is_label': True})
            row.append({'text': f"{val} {unit}" if val else '-', 'is_value': True})
        rect_rows.append(row)

    # Battery measurements — group by 4 agar setiap baris punya 8 sel, sejajar colgroup
    BMES = [
        ('Jumlah Cell',   _v(r.get('bat1_jumlah')),              False),
        ('Kondisi Kabel', r.get('bat1_kondisi_kabel', ''),        True),
        ('Mur & Baut',    r.get('bat1_kondisi_mur_baut', ''),     True),
        ('Sel & Rak',     r.get('bat1_kondisi_sel_rak', ''),      True),
        ('Air Battery',   _v(r.get('bat1_air_battery')),          False),
    ]
    # Pad ke kelipatan 4 agar setiap baris tepat 8 sel
    while len(BMES) % 4 != 0:
        BMES.append(('', '', False))
    bat_rows = []
    for i in range(0, len(BMES), 4):
        row = []
        for lbl, val, is_status in BMES[i:i+4]:
            row.append({'text': lbl, 'is_label': bool(lbl)})
            row.append({'text': str(val) if val else '', 'is_value': bool(lbl) and not is_status, 'is_status': bool(lbl) and is_status})
        bat_rows.append(row)

    # Per-cell data — format di Python agar template tinggal tampilkan
    CELL_KEYS = ['v_float', 'vd_0', 'vd_half', 'vd_1', 'vd_2', 'v_boost']
    COL_HEADS = ['V Float', 'VD 0 Jam', 'VD ½ Jam', 'VD 1 Jam', 'VD 2 Jam', 'V Boost']

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


_TEG_LABEL  = {'48': '48 V', '110': '110 V', '220': '220 V'}
_POL_LABEL  = {'negatif': 'Negatif', 'positif': 'Positif'}


def _ctx_teleproteksi(data, ctx):
    tp = data.get('tp', {})
    jumlah = tp.get('jumlah_skema') or 4
    try:
        jumlah = min(int(jumlah), 4)
    except (TypeError, ValueError):
        jumlah = 4
    skema_list = []
    for n in range(1, jumlah + 1):
        send_teg  = tp.get(f'skema_{n}_send_teg', '')
        send_pol  = tp.get(f'skema_{n}_send_pol', '')
        recv_teg  = tp.get(f'skema_{n}_receive_teg', '')
        recv_pol  = tp.get(f'skema_{n}_receive_pol', '')
        send_minus = tp.get(f'skema_{n}_send_minus')
        send_plus  = tp.get(f'skema_{n}_send_plus')
        recv_minus = tp.get(f'skema_{n}_receive_minus')
        recv_plus  = tp.get(f'skema_{n}_receive_plus')
        skema_list.append({
            'n': n,
            'command':           tp.get(f'skema_{n}_command', ''),
            'send_teg':          send_teg,
            'send_pol':          send_pol,
            'receive_teg':       recv_teg,
            'receive_pol':       recv_pol,
            # pre-formatted display labels for template
            'send_teg_label':    _TEG_LABEL.get(send_teg, ''),
            'send_pol_label':    _POL_LABEL.get(send_pol, ''),
            'receive_teg_label': _TEG_LABEL.get(recv_teg, ''),
            'receive_pol_label': _POL_LABEL.get(recv_pol, ''),
            # field lama — backward compat
            'send_minus':    send_minus,
            'send_plus':     send_plus,
            'receive_minus': recv_minus,
            'receive_plus':  recv_plus,
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
    'REPEATER': _ctx_repeater, 'REPEATER & TOWER': _ctx_repeater,
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


def _ctx_rtu(data, ctx):
    r = data.get('rtu', {})

    CP_INDS    = ['RY','ER','W','BBD','INT','EXT','ACT','HLT',
                  'LK X0','ACT 0','ERR 0','LK X1','ACT 1','ERR 1',
                  'OH X2','ACT 2','ERR 2','OH X3','ACT 3','ERR 3']
    DI_DO_INDS = ['RY','ER']
    AI_INDS    = ['RY','ER']
    IED_ITEMS  = ['BUSBAR','OHL','TRAFO','GEN.','CAP/REAC','TRF. GEN']

    def _ind_rows(data_dict, inds):
        rows = []
        for ind in inds:
            val = data_dict.get(ind, {})
            if isinstance(val, dict):
                rows.append({'name': ind, 'sb': val.get('sb', False), 'sd': val.get('sd', False)})
            else:
                rows.append({'name': ind, 'sb': False, 'sd': False})
        return rows

    def _ied_rows(data_dict):
        rows = []
        for item in IED_ITEMS:
            val = data_dict.get(item, 0)
            rows.append({'name': item, 'jumlah': val if not isinstance(val, dict) else 0})
        return rows

    ctx.update({
        'rtu': r,
        'cp2016_rows': _ind_rows(r.get('cp2016_data') or {}, CP_INDS),
        'cp2019_rows': _ind_rows(r.get('cp2019_data') or {}, CP_INDS),
        'di2112_rows': _ind_rows(r.get('di2112_data') or {}, DI_DO_INDS),
        'do2210_rows': _ind_rows(r.get('do2210_data') or {}, DI_DO_INDS),
        'ai2300_rows': _ind_rows(r.get('ai2300_data') or {}, AI_INDS),
        'ied_rows':    _ied_rows(r.get('ied_data') or {}),
        'ps48': [
            ('Teg. Beban',  r.get('ps48_teg_beban'),  'V'),
            ('Arus Beban',  r.get('ps48_arus_beban'),  'A'),
            ('Teg. Supply', r.get('ps48_teg_supply'),  'V'),
            ('Arus Supply', r.get('ps48_arus_supply'), 'A'),
        ],
        'ps110': [
            ('Teg. Beban',  r.get('ps110_teg_beban'),   'V'),
            ('Arus Beban',  r.get('ps110_arus_beban'),   'A'),
            ('Teg. Supply', r.get('ps110_teg_supply'),   'V'),
            ('Arus Supply', r.get('ps110_arus_supply'),  'A'),
        ],
    })


_CTX_BUILDERS['RTU'] = _ctx_rtu


def _ctx_sas(data, ctx):
    ctx.update({'sas': data.get('sas', {})})


_CTX_BUILDERS['SAS'] = _ctx_sas
_CTX_BUILDERS['SERVER SCADA'] = _ctx_sas
_CTX_BUILDERS['GATEWAY SAS'] = _ctx_sas
_CTX_BUILDERS['RTU_GENERIC'] = _ctx_sas


def _ctx_bcu(data, ctx):
    ctx.update({'bcu': data.get('bcu', {})})


_CTX_BUILDERS['IED BCU'] = _ctx_bcu
_CTX_BUILDERS['BCU']     = _ctx_bcu


def _ctx_roip(data, ctx):
    ctx.update({'roip': data.get('roip', {})})


def _ctx_master_station(data, ctx):
    ctx.update({'ms': data.get('ms', {})})

_CTX_BUILDERS['MASTER STATION']    = _ctx_master_station
_CTX_BUILDERS['WORKSTATION SCADA'] = _ctx_master_station
_CTX_BUILDERS['SERVER TELKOM']     = _ctx_master_station
_CTX_BUILDERS['SERVER PROSIS']     = _ctx_master_station
_CTX_BUILDERS['WORKSTATION PC']    = _ctx_master_station

_CTX_BUILDERS['ROIP'] = _ctx_roip


def _ctx_ups(data, ctx):
    u = data.get('ups', {})

    CELL_KEYS = ['v_float', 'vd_0', 'vd_1', 'vd_2', 'vd_3']

    def _cv(v):
        if v is None or v == '': return '-'
        try:    return f'{float(v):.3f}'
        except: return str(v)

    all_cells  = u.get('bat_cells') or []
    raw_cells  = [c for c in all_cells if isinstance(c.get('cell'), int)]
    vtotal_raw = next((c for c in all_cells if c.get('cell') == 'vtotal'), {})

    fmt_cells = [
        {'num': str(c.get('cell', '')).zfill(2), 'vals': [_cv(c.get(k)) for k in CELL_KEYS]}
        for c in raw_cells
    ]
    half = (len(fmt_cells) + 1) // 2
    fmt_cells_left  = fmt_cells[:half]
    fmt_cells_right = fmt_cells[half:]
    fmt_vtotal_vals = [_cv(vtotal_raw.get(k)) for k in CELL_KEYS]

    ctx.update({
        'ups': u,
        'fmt_cells':       fmt_cells,
        'fmt_cells_left':  fmt_cells_left,
        'fmt_cells_right': fmt_cells_right,
        'fmt_vtotal_vals': fmt_vtotal_vals,
        'catatan': u.get('catatan', ''),
    })


_CTX_BUILDERS['UPS'] = _ctx_ups


def _ctx_freq_relay(data, ctx):
    fr = data.get('freq_relay', {})
    settings = []
    for n in range(1, 8):
        settings.append({
            'tahap':   f'F{n}',
            'frek_hz': fr.get(f'f{n}_hz'),
            'waktu_s': fr.get(f'f{n}_s'),
            'rl_no':   fr.get(f'f{n}_rl', ''),
            'pos_vdc': fr.get(f'f{n}_pos_vdc', ''),
            'pos_pin': fr.get(f'f{n}_pos_pin', ''),
            'neg_vdc': fr.get(f'f{n}_neg_vdc', ''),
            'neg_pin': fr.get(f'f{n}_neg_pin', ''),
        })
    aux_rl = []
    for n in range(1, 8):
        aux_rl.append({
            'rl':  fr.get(f'aux{n}_rl', ''),
            'tf':  fr.get(f'aux{n}_tf', ''),
            'led': fr.get(f'aux{n}_led', ''),
        })
    ctx.update({
        'ufls': {
            'healthy':  fr.get('healthy', ''),
            'frek_oor': fr.get('frek_oor', ''),
            'alarm':    fr.get('alarm', ''),
            'fungsi':          fr.get('fungsi', ''),
            'target_proteksi': fr.get('target_proteksi', ''),
            'rasio_vt':        fr.get('rasio_vt', ''),
            'rasio_vt_sekunder': fr.get('rasio_vt_sek', ''),
            'vblock':          fr.get('vblock', ''),
            'measurement': {
                'v_an':  fr.get('v_an', ''), 'v_bn':  fr.get('v_bn', ''),
                'v_cn':  fr.get('v_cn', ''), 'v_ab':  fr.get('v_ab', ''),
                'v_bc':  fr.get('v_bc', ''), 'v_ac':  fr.get('v_ac', ''),
                'frekuensi': fr.get('frekuensi', ''),
                'v_an_target':  fr.get('target_v_an', ''),
                'v_bn_target':  fr.get('target_v_bn', ''),
                'v_cn_target':  fr.get('target_v_cn', ''),
                'v_ab_target':  fr.get('target_v_ab', ''),
                'v_bc_target':  fr.get('target_v_bc', ''),
                'v_ac_target':  fr.get('target_v_ac', ''),
                'frekuensi_target': fr.get('target_frekuensi', ''),
            },
            'settings': settings,
            'aux_rl':   aux_rl,
            'supply_dc': fr.get('supply_dc', ''),
            'selektor':  fr.get('selektor', ''),
            'catatan':   fr.get('catatan', ''),
        }
    })


_CTX_BUILDERS['UFLS']            = _ctx_freq_relay
_CTX_BUILDERS['UFR ISLAND']      = _ctx_freq_relay
_CTX_BUILDERS['OFGS']            = _ctx_freq_relay
_CTX_BUILDERS['CDSAS']           = _ctx_freq_relay
_CTX_BUILDERS['FREQUENCY RELAY'] = _ctx_freq_relay


def _ctx_master_trip(data, ctx):
    """Master Trip / Rele Defense Scheme.

    Barisnya selalu dibangun 6 baris walau `master_trip` kosong, supaya
    `blank_maintenance_pdf` (Cetak Formulir) menghasilkan formulir kosong
    dengan kotak isian yang sama persis dengan laporan berisi data.
    """
    raw = data.get('master_trip') or {}
    # Semua kunci skalar selalu ada (string kosong bila tak terisi) supaya
    # formulir kosong tidak menyisakan variabel template yang tak terdefinisi.
    mt = {k: '' for k in (
        'healthy', 'trip_led', 'alarm', 'merek', 'no_seri', 'target', 'fungsi',
        'rasio_ct', 'supply_dc', 'selektor', 'catatan',
    )}
    mt.update(raw)

    def _rows(prefix):
        return [{
            'rl':        mt.get(f'{prefix}{n}_rl', ''),
            'vdc':       mt.get(f'{prefix}{n}_vdc', ''),
            'pin':       mt.get(f'{prefix}{n}_pin', ''),
            'tahap_vdc': mt.get(f'{prefix}{n}_tahap_vdc', ''),
            'tahap_pin': mt.get(f'{prefix}{n}_tahap_pin', ''),
        } for n in range(1, 7)]

    aux_rows = [{
        'rl':  mt.get(f'aux{n}_rl', ''),
        'tf':  mt.get(f'aux{n}_tf', ''),
        'led': mt.get(f'aux{n}_led', ''),
    } for n in range(1, 7)]

    dev_rows = [{
        'nama':  mt.get(f'dev{n}_nama', ''),
        'gi':    mt.get(f'dev{n}_gi', ''),
        'ready': mt.get(f'dev{n}_ready', ''),
        'comm':  mt.get(f'dev{n}_comm', ''),
    } for n in range(1, 7)]

    arus_items = [
        {'label': 'I A', 'value': mt.get('i_a', ''), 'unit': 'A'},
        {'label': 'I B', 'value': mt.get('i_b', ''), 'unit': 'A'},
        {'label': 'I C', 'value': mt.get('i_c', ''), 'unit': 'A'},
    ]
    tegangan_items = [
        {'label': 'V A',       'value': mt.get('v_a', ''),       'unit': 'kV'},
        {'label': 'V B',       'value': mt.get('v_b', ''),       'unit': 'kV'},
        {'label': 'V C',       'value': mt.get('v_c', ''),       'unit': 'kV'},
        {'label': 'Frekuensi', 'value': mt.get('frekuensi', ''), 'unit': 'Hz'},
    ]
    setting_items = [
        {'label': 'I >',         'setting': mt.get('setting_i', ''),   'waktu': mt.get('waktu_i', ''),     'unit': 'A'},
        {'label': 'I >>',        'setting': mt.get('setting_ii', ''),  'waktu': mt.get('waktu_ii', ''),    'unit': 'A'},
        {'label': 'Under Power', 'setting': mt.get('under_power', ''), 'waktu': mt.get('waktu_under', ''), 'unit': 'kV'},
        {'label': 'Over Power',  'setting': mt.get('over_power', ''),  'waktu': mt.get('waktu_over', ''),  'unit': 'kV'},
    ]

    kind = data.get('device_kind', '').strip().upper()

    ctx.update({
        'mt':              mt,
        'mt_is_defense':   'DEFENSE' in kind,
        'pos_rows':        _rows('p'),
        'neg_rows':        _rows('n'),
        'aux_rows':        aux_rows,
        'dev_rows':        dev_rows,
        'arus_items':      arus_items,
        'tegangan_items':  tegangan_items,
        'setting_items':   setting_items,
        'catatan':         mt.get('catatan', ''),
    })


_CTX_BUILDERS['MASTER TRIP']         = _ctx_master_trip
_CTX_BUILDERS['RELE DEFENSE SCHEME'] = _ctx_master_trip
_CTX_BUILDERS['DEFENSE SCHEME']      = _ctx_master_trip


def _ctx_dfr(data, ctx):
    """DFR / PMU (Digital Fault Recorder).

    Tabel BAY selalu dibangun walau `dfr` kosong, dengan alasan yang sama
    seperti Master Trip: `blank_maintenance_pdf` harus menghasilkan formulir
    kosong yang bentuknya sama persis dengan laporan berisi data.
    """
    raw = data.get('dfr') or {}
    d = {k: '' for k in (
        'bay_feeder_1', 'bay_feeder_2', 'rasio_ct_1', 'rasio_ct_2',
        'rasio_pt_1', 'rasio_pt_2', 'suhu_ruangan', 'kelembaban',
        'kartu_kontrol', 'outdoor_panel', 'indoor_panel', 'tergrounding',
        'type_dfr', 'merk_dfr', 'sn_dfr',
        'kondisi_gps', 'kondisi_lcd', 'waktu_dfr',
        'dfr_aktif', 'fisik_alarm', 'fungsi_rekaman',
        'visual_5r', 'front_port_ip', 'rear_port_ip',
        'software_config', 'rekaman_gangguan', 'v_input_power', 'v_backup',
        'kapasitas_memory', 'pmu_id', 'catatan_khusus',
    )}
    d.update(raw)

    panel_items = [
        {'label': 'Isi Kartu Kontrol', 'value': d.get('kartu_kontrol', '')},
        {'label': 'Outdoor Panel',     'value': d.get('outdoor_panel', '')},
        {'label': 'Indoor Panel',      'value': d.get('indoor_panel', '')},
        {'label': 'Tergrounding',      'value': d.get('tergrounding', '')},
    ]
    gps_items = [
        {'label': 'Kondisi Koneksi GPS', 'value': d.get('kondisi_gps', '')},
        {'label': 'LCD & Keypad',        'value': d.get('kondisi_lcd', '')},
        {'label': 'Pengecekan Waktu DFR','value': d.get('waktu_dfr', '')},
    ]
    dfr_items = [
        {'label': 'DFR Aktif',            'value': d.get('dfr_aktif', '')},
        {'label': 'Pemeriksaan Fisik & Alarm', 'value': d.get('fisik_alarm', '')},
        {'label': 'Pemeriksaan Fungsi Rekaman', 'value': d.get('fungsi_rekaman', '')},
    ]
    media_rows = [
        {'media': 'Fiber Optic (FO)',  'tx': d.get('fo_tx', ''),   'rx': d.get('fo_rx', '')},
        {'media': 'Converter FO → ETH','tx': d.get('conv_tx', ''), 'rx': d.get('conv_rx', '')},
        {'media': 'LAN Cable ETH',     'tx': d.get('lan_tx', ''),  'rx': d.get('lan_rx', '')},
    ]
    ping_rows = [
        {'target': 'To Server',     'ms1': d.get('ping_server_1', ''),
         'ms2': d.get('ping_server_2', ''), 'status': d.get('ping_server_status', '')},
        {'target': 'To Device DFR', 'ms1': d.get('ping_dfr_1', ''),
         'ms2': d.get('ping_dfr_2', ''), 'status': d.get('ping_dfr_status', '')},
    ]
    software_items = [
        {'label': 'Software / Config',      'value': d.get('software_config', '')},
        {'label': 'Rekaman Gangguan',       'value': d.get('rekaman_gangguan', '')},
        {'label': 'Tegangan Input Power',   'value': d.get('v_input_power', ''),  'unit': 'VDC'},
        {'label': 'Tegangan Backup',        'value': d.get('v_backup', ''),       'unit': 'VDC'},
        {'label': 'Kapasitas Memory DFR',   'value': d.get('kapasitas_memory', '')},
        {'label': 'PMU ID',                 'value': d.get('pmu_id', '')},
    ]

    def _bay(n):
        """Empat baris pembacaan satu BAY: DFR & IED, tegangan & arus."""
        def _row(sumber, besaran, pfx, satuan, hz):
            return {
                'sumber':  sumber,
                'besaran': besaran,
                'satuan':  satuan,
                'r': d.get(f'{pfx}_r', ''), 's': d.get(f'{pfx}_s', ''),
                't': d.get(f'{pfx}_t', ''), 'n': d.get(f'{pfx}_n', ''),
                'hz': d.get(hz, '') if hz else None,
            }
        return {
            'nomor': n,
            'feeder': d.get(f'bay_feeder_{n}', ''),
            'rasio_ct': d.get(f'rasio_ct_{n}', ''),
            'rasio_pt': d.get(f'rasio_pt_{n}', ''),
            'rows': [
                _row('Analog Input DFR', 'Tegangan', f'bay{n}_dfr_v', 'kV', f'bay{n}_dfr_hz'),
                _row('Analog Input DFR', 'Beban',    f'bay{n}_dfr_i', 'A',  None),
                _row('IED Meter Pembanding', 'Tegangan', f'bay{n}_ied_v', 'kV', f'bay{n}_ied_hz'),
                _row('IED Meter Pembanding', 'Beban',    f'bay{n}_ied_i', 'A',  None),
            ],
        }

    ctx.update({
        'dfr':             d,
        'dfr_is_pmu':      data.get('device_kind', '').strip().upper() == 'PMU',
        'panel_items':     panel_items,
        'gps_items':       gps_items,
        'dfr_items':       dfr_items,
        'media_rows':      media_rows,
        'ping_rows':       ping_rows,
        'software_items':  software_items,
        'bays':            [_bay(1), _bay(2)],
        'catatan':         d.get('catatan_khusus', ''),
    })


_CTX_BUILDERS['DFR'] = _ctx_dfr
_CTX_BUILDERS['PMU'] = _ctx_dfr


def _ctx_corrective(data, ctx):
    c = data.get('corrective', {})
    ctx.update({
        'title':       _CORRECTIVE_TITLE,
        'corrective':  c,
        'foto_sebelum': _img_uri(c.get('foto_sebelum_path', '')),
        'foto_sesudah': _img_uri(c.get('foto_sesudah_path', '')),
    })


def build_pdf_weasy(data: dict, output):
    """Generate PDF menggunakan WeasyPrint."""
    import weasyprint

    is_corrective = data.get('maintenance_type') == 'Corrective'
    kind = data.get('device_kind', 'GENERIC').strip().upper()

    if is_corrective:
        template_name = _CORRECTIVE_TEMPLATE
        ctx = _base_context(data)
        ctx['title'] = _CORRECTIVE_TITLE
        _ctx_corrective(data, ctx)
    else:
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
