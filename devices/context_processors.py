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
    lokasi = (
        Device.objects
        .filter(is_deleted=False)
        .exclude(lokasi__isnull=True)
        .exclude(lokasi__exact='')
        .exclude(lokasi__iexact='none')
        .annotate(lokasi_clean=Trim('lokasi'))
        .values_list('lokasi_clean', flat=True)
        .distinct()
        .order_by('lokasi_clean')
    )

    return {
        'navbar_lokasi_list': lokasi
    }

def notifikasi_count(request):
    """Inject jumlah notifikasi belum dibaca ke semua template."""
    if not request.user.is_authenticated:
        return {'notif_unread_count': 0}
    try:
        from notifikasi.models import Notifikasi
        count = Notifikasi.objects.filter(is_read=False).count()
    except Exception:
        count = 0
    return {'notif_unread_count': count}