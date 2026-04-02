from .models import DeviceType, Device
from django.db.models.functions import Trim

# ── Grouping jenis peralatan untuk sidebar ──────────────────
DEVICE_GROUP_CONFIG = {
    'telkom': {
        'label': 'Telekomunikasi',
        'icon': 'bi-broadcast-pin',
        'color': '#3b82f6',
        'types': [
            'router', 'switch', 'teleproteksi', 'roip',
            'voip', 'multiplexer', 'plc', 'radio', 'server telkom',
        ],
    },
    'scada': {
        'label': 'SCADA',
        'icon': 'bi-diagram-3',
        'color': '#10b981',
        'types': [
            'rtu', 'sas', 'ups', 'server scada', 'ied bcu', 'clock server', 'serial server','router sas', 'switch sas', 'inverter sas',
        ],
    },
    'prosis': {
        'label': 'Proteksi Sistem',
        'icon': 'bi-shield-check',
        'color': '#f59e0b',
        'types': [
            'defense scheme', 'rele defense scheme', 'dfr', 'server prosis',
        ],
    },
}

# Urutan dalam group
DEVICE_TYPE_ORDER_IN_GROUP = [
    "ROUTER", "SWITCH", "RADIO", "VOIP", "MULTIPLEXER", 
    "PLC", "TELEPROTEKSI", "ROIP", "SERVER TELKOM",
    "RTU", "SAS", "SERVER SCADA", "UPS",
    "IED BCU", "CLOCK SERVER", "SERIAL SERVER", "ROUTER SAS", "SWITCH SAS", "INVERTER SAS",

    "RELE DEFENSE SCHEME", "DFR", "SERVER PROSIS", 
    "Catu Daya", "Workstation PC", "GPS", "GENSET",
]


def _get_group_key(name):
    """Return group key (telkom/scada/prosis) or None for ungrouped."""
    name_lower = name.strip().lower()
    for key, cfg in DEVICE_GROUP_CONFIG.items():
        for t in cfg['types']:
            if t == name_lower:
                return key
    return None


def _sort_key(dt):
    name_lower = dt.name.strip().lower()
    for i, ordered_name in enumerate(DEVICE_TYPE_ORDER_IN_GROUP):
        if ordered_name.lower() == name_lower:
            return i
    return len(DEVICE_TYPE_ORDER_IN_GROUP)


def device_types(request):
    all_types = list(DeviceType.objects.all())
    all_types.sort(key=_sort_key)

    # Build grouped structure
    groups = {}
    ungrouped = []

    for dt in all_types:
        group_key = _get_group_key(dt.name)
        if group_key:
            if group_key not in groups:
                cfg = DEVICE_GROUP_CONFIG[group_key]
                groups[group_key] = {
                    'key': group_key,
                    'label': cfg['label'],
                    'icon': cfg['icon'],
                    'color': cfg['color'],
                    'types': [],
                }
            groups[group_key]['types'].append(dt)
        else:
            ungrouped.append(dt)

    # Preserve order: telkom, scada, prosis
    ordered_groups = []
    for key in ['telkom', 'scada', 'prosis']:
        if key in groups:
            ordered_groups.append(groups[key])

    # Detect active device jenis for sidebar highlighting on device_view
    active_device_jenis_id = None
    try:
        resolver = request.resolver_match
        if resolver and resolver.url_name == 'device_view':
            pk = resolver.kwargs.get('pk')
            if pk:
                d = Device.objects.filter(pk=pk, is_deleted=False).select_related('jenis').first()
                if d and d.jenis_id:
                    active_device_jenis_id = d.jenis_id
    except Exception:
        pass

    return {
        'navbar_device_types': all_types,  # backward compat
        'device_groups': ordered_groups,
        'device_ungrouped': ungrouped,
        'active_device_jenis_id': active_device_jenis_id,
    }

def lokasi_list(request):
    """
    Inject daftar lokasi ke semua template.
    Master data dari SiteLocation. Kalau kosong, fallback dari Device.lokasi.
    """
    from .models import SiteLocation
    from django.db.models.functions import Trim

    site_locs = list(SiteLocation.objects.values_list('nama', flat=True).order_by('nama'))

    if not site_locs:
        # Fallback: ambil dari Device yang sudah ada
        site_locs = list(
            Device.objects.filter(is_deleted=False)
            .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
            .annotate(lc=Trim('lokasi'))
            .values_list('lc', flat=True)
            .distinct().order_by('lc')
        )

    return {
        'navbar_lokasi_list': site_locs,
        'master_lokasi_list': site_locs,   # alias untuk dipakai di form
    }

def notifikasi_count(request):
    """Inject jumlah notifikasi belum dibaca — per user + global."""
    if not request.user.is_authenticated:
        return {'notif_unread_count': 0}
    try:
        from notifikasi.models import Notifikasi
        from django.db.models import Q
        count = Notifikasi.objects.filter(
            Q(user=request.user) | Q(user__isnull=True),
            is_read=False
        ).count()
    except Exception:
        count = 0
    return {'notif_unread_count': count}

def user_display_name(request):
    """
    Inject nama tampilan user ke semua template.
    Prioritas: display_name (UserProfile) > first_name+last_name > username
    """
    if not request.user.is_authenticated:
        return {'user_display_name': ''}
    try:
        name = request.user.profile.get_display_name()
    except Exception:
        name = request.user.get_full_name() or request.user.username
    return {'user_display_name': name}


def user_permissions(request):
    """
    Inject permission flags ke semua template.
    Pakai: {{ user_can_edit }}, {{ user_can_delete }}, {{ user_is_viewer }}
    """
    if not request.user.is_authenticated:
        return {
            'user_can_edit':          False,
            'user_can_delete':        False,
            'user_can_manage_lokasi': False,
            'user_is_viewer':         False,
        }

    from devices.permissions import can_edit, can_delete, can_manage_lokasi, is_viewer_only, is_operator
    return {
        'user_can_edit':          can_edit(request.user),
        'user_can_delete':        can_delete(request.user),
        'user_can_manage_lokasi': can_manage_lokasi(request.user),
        'user_is_viewer':         is_viewer_only(request.user),
        'user_is_operator':       is_operator(request.user),
    }
