from .models import DeviceType, Device
from django.db.models.functions import Trim
from .constants import DEVICE_GROUP_CONFIG, get_group_key, type_sort_key


def device_types(request):
    all_types = list(DeviceType.objects.all())
    all_types.sort(key=type_sort_key)

    # Build grouped structure
    groups = {}
    ungrouped = []

    for dt in all_types:
        group_key = get_group_key(dt.name)
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


def pending_approval_count(request):
    """Inject jumlah maintenance Done belum TTD — untuk badge sidebar Approval."""
    if not request.user.is_authenticated:
        return {'pending_approval_count': 0}
    try:
        is_am = request.user.profile.is_asisten_manager
    except Exception:
        is_am = False
    if not (request.user.is_superuser or is_am):
        return {'pending_approval_count': 0}
    try:
        from maintenance.models import Maintenance
        count = Maintenance.objects.filter(status='Done', signed_by__isnull=True).count()
    except Exception:
        count = 0
    return {'pending_approval_count': count}


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
            'user_is_opsis':          False,
        }

    from devices.permissions import can_edit, can_delete, can_manage_lokasi, is_viewer_only, is_operator, is_dispatcher
    try:
        _is_opsis = request.user.profile.role == 'opsis'
    except Exception:
        _is_opsis = False
    return {
        'user_can_edit':          can_edit(request.user),
        'user_can_delete':        can_delete(request.user),
        'user_can_manage_lokasi': can_manage_lokasi(request.user),
        'user_is_viewer':         is_viewer_only(request.user),
        'user_is_operator':       is_operator(request.user),
        'user_is_dispatcher':     is_dispatcher(request.user),
        'user_is_opsis':          _is_opsis,
    }
