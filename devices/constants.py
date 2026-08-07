DEVICE_GROUP_CONFIG = {
    'telkom': {
        'label': 'Telekomunikasi',
        'icon': 'bi-broadcast-pin',
        'color': '#3b82f6',
        'bg': '#eff6ff',
        'types': [
            'router', 'switch', 'teleproteksi', 'roip',
            'voip', 'multiplexer', 'plc', 'radio', 'microwave',
            'server telkom', 'master clock', 'ht',
            'pheriperal telkom', 'peripheral telkom',
            'pabx', 'repeater', 'tower', 'repeater & tower',
        ],
    },
    'scada': {
        'label': 'SCADA',
        'icon': 'bi-diagram-3',
        'color': '#10b981',
        'bg': '#f0fdf4',
        'types': [
            'rtu', 'sas', 'ups', 'master station',
            'vm scada', 'workstation scada', 'ied bcu',
            'clock server', 'serial server', 'router sas',
            'switch sas', 'inverter sas',
            'pheriperal scada', 'peripheral scada', 'gps',
            'server scada', 'dc-mon', 'dc mon',
        ],
    },
    'prosis': {
        'label': 'Proteksi Sistem',
        'icon': 'bi-shield-check',
        'color': '#f59e0b',
        'bg': '#fffbeb',
        'types': [
            'defense scheme', 'rele defense scheme', 'dfr',
            'master trip', 'ufls', 'server prosis',
        ],
    },
}

DEVICE_TYPE_ORDER_IN_GROUP = [
    "ROUTER", "SWITCH", "RADIO", "MICROWAVE", "VOIP", "MULTIPLEXER",
    "PLC", "TELEPROTEKSI", "ROIP", "SERVER TELKOM", "MASTER CLOCK",
    "HT", "PABX", "PHERIPERAL TELKOM", "PERIPHERAL TELKOM",
    "REPEATER", "TOWER", "REPEATER & TOWER",
    "RTU", "SAS", "Master Station", "VM SCADA", "Workstation SCADA",
    "UPS", "GPS", "SERVER SCADA",
    "IED BCU", "CLOCK SERVER", "SERIAL SERVER", "ROUTER SAS",
    "SWITCH SAS", "INVERTER SAS", "DC-MON",
    "PHERIPERAL SCADA", "PERIPHERAL SCADA",
    "RELE DEFENSE SCHEME", "MASTER TRIP", "UFLS", "DFR", "SERVER PROSIS",
    "Catu Daya", "Workstation PC", "GENSET",
]


def get_group_key(name):
    name_lower = name.strip().lower()
    for key, cfg in DEVICE_GROUP_CONFIG.items():
        for t in cfg['types']:
            if t == name_lower:
                return key
    return None


def type_sort_key(dt):
    name = dt.name.strip().lower() if hasattr(dt, 'name') else str(dt).strip().lower()
    for i, ordered_name in enumerate(DEVICE_TYPE_ORDER_IN_GROUP):
        if ordered_name.lower() == name:
            return i
    return len(DEVICE_TYPE_ORDER_IN_GROUP)
