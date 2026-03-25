from .models import DeviceType, Device
from django.db.models.functions import Trim

# Urutan custom sidebar peralatan
DEVICE_TYPE_ORDER = [
    "Router",
    "Switch",
    "Radio",
    "VoIP",
    "Multiplexer",
    "PLC",
    "Teleproteksi",
    "RoIP",
    "Catu Daya",
    "RTU",
    "SAS",
    "SERVER",
    "UPS",
    "Workstation PC",
    "GPS",
    "GENSET",
    "DFR",
    "RELE DEFENSE SCHEME",
]

def device_types(request):
    all_types = list(DeviceType.objects.all())

    def sort_key(dt):
        name_lower = dt.name.strip().lower()
        for i, ordered_name in enumerate(DEVICE_TYPE_ORDER):
            if ordered_name.lower() == name_lower:
                return i
        return len(DEVICE_TYPE_ORDER)

    all_types.sort(key=sort_key)

    return {
        'navbar_device_types': all_types
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

    from devices.permissions import can_edit, can_delete, can_manage_lokasi, is_viewer_only
    return {
        'user_can_edit':          can_edit(request.user),
        'user_can_delete':        can_delete(request.user),
        'user_can_manage_lokasi': can_manage_lokasi(request.user),
        'user_is_viewer':         is_viewer_only(request.user),
    }
