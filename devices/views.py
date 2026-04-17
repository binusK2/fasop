from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from devices.permissions import (
    require_can_delete, require_can_edit, require_can_manage_lokasi,
    can_delete, can_edit, can_manage_lokasi, is_viewer_only
)
from .models import Device, DeviceType, Icon, SiteLocation, DeviceLog, DeviceEvent
from .forms import DeviceForm, IconForm
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth, Lower, Trim
from maintenance.models import Maintenance
from django.utils.timezone import now
from django.http import HttpResponse, JsonResponse
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import date as date_type
from dateutil.relativedelta import relativedelta
import json
from .device_schema import DEVICE_SCHEMA


@login_required
def device_list(request):
    jenis_id       = request.GET.get('jenis')
    search         = request.GET.get('q') or ''
    lokasi         = request.GET.get('lokasi')
    status_operasi = request.GET.get('status_operasi')
    sort           = request.GET.get('sort', 'nama')
    direction      = request.GET.get('dir', 'asc')

    # Cek apakah filter jenis yang dipilih adalah VM SCADA
    _is_vm_jenis = (
        jenis_id and
        DeviceType.objects.filter(pk=jenis_id, name__iexact='VM SCADA').exists()
    )
    if _is_vm_jenis:
        # Untuk VM SCADA: tampilkan VM (host terisi), bukan aset fisik
        devices = Device.objects.filter(is_deleted=False, host__isnull=False)
    else:
        # Semua jenis lain: hanya aset fisik (bukan VM)
        devices = Device.objects.filter(is_deleted=False, host__isnull=True)

    if jenis_id:
        devices = devices.filter(jenis_id=jenis_id)

    if search:
        devices = devices.filter(
            Q(nama__icontains=search) |
            Q(ip_address__icontains=search)
        )

    if lokasi:
        devices = devices.filter(lokasi=lokasi)

    if status_operasi:
        devices = devices.filter(status_operasi=status_operasi)

    # Sorting
    SORT_FIELDS = {
        'nama': 'nama',
        'jenis': 'jenis__name',
        'merk': 'merk',
        'ip': 'ip_address',
        'lokasi': 'lokasi',
        'serial': 'serial_number',
    }
    order_field = SORT_FIELDS.get(sort, 'nama')
    if direction == 'desc':
        order_field = '-' + order_field
    devices = devices.order_by(order_field)

    lokasi_list = (
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

    return render(request, 'devices/device_list.html', {
        'devices':          devices,
        'search':           search,
        'selected_jenis':   jenis_id,
        'lokasi_list':      lokasi_list,
        'selected_lokasi':  lokasi,
        'selected_status':  status_operasi,
        'current_sort':     sort,
        'current_dir':      direction,
    })


@login_required
@require_can_edit
def device_create(request):
    host_pk = request.GET.get('host') or request.POST.get('host_prefill')
    if request.method == 'POST':
        form = DeviceForm(request.POST, request.FILES)
        if form.is_valid():
            device = form.save(commit=False)
            spesifikasi_raw = request.POST.get('spesifikasi_json', '{}')
            try:
                device.spesifikasi = json.loads(spesifikasi_raw)
            except (json.JSONDecodeError, ValueError):
                device.spesifikasi = {}
            device.created_by = request.user
            device.save()

            # ── Simpan komponen dari form ──────────────────────────
            komponen_json = request.POST.get('komponen_json', '[]')
            try:
                komponen_list = json.loads(komponen_json)
            except (json.JSONDecodeError, ValueError):
                komponen_list = []

            from devices.models_komponen import DeviceComponent
            from devices.views_komponen import _resolve_tipe
            for k in komponen_list:
                if not k.get('nama'):
                    continue
                DeviceComponent.objects.create(
                    device=device,
                    nama=k.get('nama', '').strip(),
                    tipe_komponen=_resolve_tipe(k.get('tipe_komponen')),
                    posisi=k.get('posisi', '').strip(),
                    merk=k.get('merk', '').strip(),
                    serial_number=k.get('serial_number', '').strip(),
                    status=k.get('status', 'terpasang'),
                    keterangan=k.get('keterangan', '').strip(),
                    created_by=request.user,
                )

            # Audit log
            from devices.device_audit import log_create
            log_create(device, request.user)
            return redirect('device_view', pk=device.pk)
    else:
        initial = {}
        if host_pk:
            try:
                host_device = Device.objects.get(pk=host_pk, is_deleted=False)
                initial['host'] = host_device
            except Device.DoesNotExist:
                pass
        form = DeviceForm(initial=initial)
    from devices.views_komponen import get_tipe_grouped_json
    # Tentukan jenis DeviceType untuk "VM SCADA" agar JS bisa pre-pilih
    try:
        vm_jenis = DeviceType.objects.get(name__iexact='VM SCADA')
        vm_jenis_id = vm_jenis.pk
    except DeviceType.DoesNotExist:
        vm_jenis_id = None
    return render(request, 'devices/device_form.html', {
        'form': form,
        'is_edit': False,
        'device_schema_json': json.dumps(DEVICE_SCHEMA),
        'tipe_komponen_json': get_tipe_grouped_json(),
        'prefill_host_pk': host_pk,
        'vm_jenis_id': vm_jenis_id,
    })


@login_required
@require_can_edit
def device_update(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == 'POST':
        # Snapshot sebelum perubahan
        from devices.device_audit import log_edit, TRACKED_FIELDS
        import copy
        device_before = copy.copy(device)

        form = DeviceForm(request.POST, request.FILES, instance=device)
        if form.is_valid():
            dev = form.save(commit=False)
            spesifikasi_raw = request.POST.get('spesifikasi_json', '{}')
            try:
                dev.spesifikasi = json.loads(spesifikasi_raw)
            except (json.JSONDecodeError, ValueError):
                dev.spesifikasi = {}
            dev.save()

            # ── Simpan komponen baru dari form ────────────────────
            komponen_json = request.POST.get('komponen_json', '[]')
            try:
                komponen_list = json.loads(komponen_json)
            except (json.JSONDecodeError, ValueError):
                komponen_list = []

            from devices.models_komponen import DeviceComponent
            from devices.views_komponen import _resolve_tipe
            for k in komponen_list:
                if not k.get('nama'):
                    continue
                DeviceComponent.objects.create(
                    device=device,
                    nama=k.get('nama', '').strip(),
                    tipe_komponen=_resolve_tipe(k.get('tipe_komponen')),
                    posisi=k.get('posisi', '').strip(),
                    merk=k.get('merk', '').strip(),
                    serial_number=k.get('serial_number', '').strip(),
                    status=k.get('status', 'terpasang'),
                    keterangan=k.get('keterangan', '').strip(),
                    created_by=request.user,
                )

            # Audit log — bandingkan sebelum vs sesudah
            log_edit(device_before, dev, request.user)
            return redirect('device_view', pk=device.pk)
    else:
        form = DeviceForm(instance=device)
    from devices.views_komponen import get_tipe_grouped_json
    return render(request, 'devices/device_form.html', {
        'form': form,
        'is_edit': True,
        'device': device,
        'device_schema_json': json.dumps(DEVICE_SCHEMA),
        'existing_spesifikasi': json.dumps(device.spesifikasi or {}),
        'tipe_komponen_json': get_tipe_grouped_json(),
    })


@login_required
@require_can_delete
def device_delete(request, pk):
    device = get_object_or_404(Device, pk=pk)
    from devices.device_audit import log_delete
    log_delete(device, request.user)
    device.is_deleted = True
    device.deleted_by = request.user
    device.save()
    return redirect('device_list')


@login_required
def dashboard(request):
    # ── Fork ke dashboard operator ───────────────────────────────
    if not request.user.is_superuser:
        try:
            role = request.user.profile.role
        except Exception:
            role = ''
        if role == 'operator':
            return _dashboard_operator(request)

    # ── Dashboard normal (teknisi / AM / superuser) ──────────────
    # VM (host__isnull=False) tidak dihitung sebagai aset fisik
    _asset_qs = Device.objects.filter(is_deleted=False, host__isnull=True)
    total_devices  = _asset_qs.count()
    dev_operasi    = _asset_qs.filter(status_operasi='operasi').count()
    dev_tdk_operasi= _asset_qs.filter(status_operasi='tidak_operasi').count()

    # Hitung per jenis + persen untuk progress bar
    device_by_type_qs = (
        _asset_qs
        .values('jenis__name', 'jenis__id')
        .annotate(total=Count('id'))
        .order_by('jenis__name')
    )

    # tambah pct untuk progress bar
    device_by_type = []
    for d in device_by_type_qs:
        pct = round((d['total'] / total_devices * 100)) if total_devices else 0
        device_by_type.append({**d, 'pct': pct})

    # Status operasi per jenis → untuk pie chart di dashboard
    import json as _json
    _status_qs = (
        _asset_qs
        .values('jenis__name', 'status_operasi')
        .annotate(total=Count('id'))
        .order_by('jenis__name')
    )
    _status_map = {}
    for row in _status_qs:
        jenis = row['jenis__name'] or 'Lainnya'
        if jenis not in _status_map:
            _status_map[jenis] = {'operasi': 0, 'tidak_operasi': 0}
        _status_map[jenis][row['status_operasi']] = row['total']
    device_status_by_type_json = _json.dumps(_status_map)

    # ── Distribusi peralatan per kelompok (Telkom / SCADA / Prosis) ─
    _KELOMPOK_CFG = [
        {
            'key': 'telkom', 'label': 'Telekomunikasi',
            'icon': 'bi-broadcast-pin', 'color': '#3b82f6', 'bg': '#eff6ff',
            'types': {
                'router', 'switch', 'teleproteksi', 'roip', 'voip',
                'multiplexer', 'plc', 'radio', 'server telkom',
                'master clock', 'ht', 'pheriperal telkom', 'peripheral telkom',
            },
        },
        {
            'key': 'scada', 'label': 'SCADA',
            'icon': 'bi-diagram-3', 'color': '#10b981', 'bg': '#f0fdf4',
            'types': {
                'rtu', 'sas', 'ups', 'server scada', 'vm scada', 'ied bcu',
                'clock server', 'serial server', 'router sas', 'switch sas',
                'inverter sas', 'pheriperal scada', 'peripheral scada',
            },
        },
        {
            'key': 'prosis', 'label': 'Proteksi Sistem',
            'icon': 'bi-shield-check', 'color': '#f59e0b', 'bg': '#fffbeb',
            'types': {
                'defense scheme', 'rele defense scheme', 'dfr',
                'master trip', 'ufls', 'server prosis',
            },
        },
    ]
    _maintained_ids = set(
        Maintenance.objects.filter(status='Done').values_list('device_id', flat=True)
    )
    _type_agg = {}
    for _dev in _asset_qs.select_related('jenis'):
        _jname = (_dev.jenis.name if _dev.jenis else 'Lainnya').strip()
        if _jname not in _type_agg:
            _type_agg[_jname] = {'total': 0, 'maintained': 0}
        _type_agg[_jname]['total'] += 1
        if _dev.id in _maintained_ids:
            _type_agg[_jname]['maintained'] += 1

    kelompok_data = []
    for _kg in _KELOMPOK_CFG:
        _entries = []
        for _jname, _st in _type_agg.items():
            if _jname.lower().strip() in _kg['types']:
                _entries.append({
                    'name': _jname,
                    'total': _st['total'],
                    'maintained': _st['maintained'],
                })
        _entries.sort(key=lambda x: -x['total'])
        kelompok_data.append({
            'key':        _kg['key'],
            'label':      _kg['label'],
            'icon':       _kg['icon'],
            'color':      _kg['color'],
            'bg':         _kg['bg'],
            'total':      sum(e['total'] for e in _entries),
            'maintained': sum(e['maintained'] for e in _entries),
            'types':      _entries,
        })
    kelompok_json = _json.dumps(kelompok_data)

    total_maintenance = Maintenance.objects.count()
    maintenance_open = Maintenance.objects.filter(status='Open').count()
    maintenance_done = Maintenance.objects.filter(status='Done').count()
    belum_ttd = Maintenance.objects.filter(status='Done', signed_by__isnull=True).count()

    # Selalu tampilkan 6 bulan terakhir, isi 0 jika tidak ada data
    today = date_type.today()
    months_6 = [today.replace(day=1) - relativedelta(months=i) for i in range(5, -1, -1)]
    counts_qs = (
        Maintenance.objects
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Count('id'))
    )
    counts_map = {m['month'].date().replace(day=1): m['total'] for m in counts_qs}
    maintenance_by_month = [
        {'month_label': m.strftime('%b %Y'), 'total': counts_map.get(m, 0)}
        for m in months_6
    ]

    # Maintenance open terbaru (5 record) — tangkap status 'Open' maupun blank/null
    recent_open_maintenance = (
        Maintenance.objects
        .exclude(status='Done')
        .select_related('device', 'device__jenis')
        .order_by('-date')[:5]
    )

    # Maintenance per lokasi (top 8)
    maintenance_by_lokasi = (
        Maintenance.objects
        .exclude(device__lokasi__isnull=True)
        .exclude(device__lokasi__exact='')
        .values('device__lokasi')
        .annotate(total=Count('id'), open=Count('id', filter=Q(status='Open')), done=Count('id', filter=Q(status='Done')))
        .order_by('-total')[:8]
    )
    max_lokasi = maintenance_by_lokasi[0]['total'] if maintenance_by_lokasi else 1

    # ── Gangguan stats ───────────────────────────────────────────
    from gangguan.models import Gangguan
    gangguan_total      = Gangguan.objects.count()
    gangguan_open       = Gangguan.objects.filter(status='open').count()
    gangguan_progress   = Gangguan.objects.filter(status='in_progress').count()
    gangguan_resolved   = Gangguan.objects.filter(status='resolved').count()
    gangguan_closed     = Gangguan.objects.filter(status='closed').count()

    # Trend gangguan 6 bulan (berdasarkan tanggal_gangguan)
    gangguan_counts_qs = (
        Gangguan.objects
        .annotate(month=TruncMonth('tanggal_gangguan'))
        .values('month')
        .annotate(total=Count('id'))
    )
    gangguan_counts_map = {g['month'].date().replace(day=1): g['total'] for g in gangguan_counts_qs}
    gangguan_by_month = [
        {'month_label': m.strftime('%b %Y'), 'total': gangguan_counts_map.get(m, 0)}
        for m in months_6
    ]

    # Gangguan terbaru open/in_progress
    recent_gangguan = (
        Gangguan.objects
        .filter(status__in=['open', 'in_progress'])
        .select_related('peralatan', 'created_by')
        .order_by('-tanggal_gangguan')[:5]
    )

    # ── Health Index summary ─────────────────────────────────────
    from health_index.calculator import calculate_hi
    hi_summary = {'sangat_baik': 0, 'baik': 0, 'cukup': 0, 'buruk': 0, 'kritis': 0}
    hi_kritis_list = []
    for dev in Device.objects.filter(is_deleted=False).select_related('jenis'):
        hi = calculate_hi(dev, save_snapshot=False)
        s = hi['score']
        if s >= 85:
            hi_summary['sangat_baik'] += 1
        elif s >= 70:
            hi_summary['baik'] += 1
        elif s >= 50:
            hi_summary['cukup'] += 1
        elif s >= 25:
            hi_summary['buruk'] += 1
        else:
            hi_summary['kritis'] += 1
            hi_kritis_list.append({'device': dev, 'hi': hi})
    hi_kritis_list = hi_kritis_list[:5]  # tampilkan max 5
    hi_summary_json = _json.dumps(hi_summary)

    # ── Gangguan breakdown by kategori & severity ─────────────────
    gangguan_by_kategori_qs = (
        Gangguan.objects
        .values('kategori')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    _kat_labels = {
        'perangkat': 'Perangkat/HW', 'jaringan': 'Jaringan',
        'daya': 'Daya/Power', 'software': 'Software',
        'eksternal': 'Eksternal', 'lainnya': 'Lainnya',
    }
    gangguan_kategori_json = _json.dumps([
        {'label': _kat_labels.get(g['kategori'], g['kategori']), 'total': g['total']}
        for g in gangguan_by_kategori_qs
    ])

    gangguan_by_severity_qs = (
        Gangguan.objects
        .values('tingkat_keparahan')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    _sev_order = ['kritis', 'tinggi', 'sedang', 'rendah']
    _sev_labels = {'kritis': 'Kritis', 'tinggi': 'Tinggi', 'sedang': 'Sedang', 'rendah': 'Rendah'}
    _sev_map = {g['tingkat_keparahan']: g['total'] for g in gangguan_by_severity_qs}
    gangguan_severity_json = _json.dumps([
        {'label': _sev_labels[s], 'total': _sev_map.get(s, 0)}
        for s in _sev_order
    ])

    # Gangguan open per severity (untuk card badges)
    gangguan_open_kritis = Gangguan.objects.filter(status__in=['open', 'in_progress'], tingkat_keparahan='kritis').count()

    # ── Maintenance stacked (preventive vs corrective per bulan) ──
    _maint_type_qs = (
        Maintenance.objects
        .annotate(month=TruncMonth('date'))
        .values('month', 'maintenance_type')
        .annotate(total=Count('id'))
    )
    _maint_type_map = {}
    for _m in _maint_type_qs:
        _mo = _m['month'].date().replace(day=1)
        _t = _m['maintenance_type'] or 'Lainnya'
        if _mo not in _maint_type_map:
            _maint_type_map[_mo] = {}
        _maint_type_map[_mo][_t] = _m['total']
    maintenance_stacked_json = _json.dumps({
        'labels': [m.strftime('%b %Y') for m in months_6],
        'preventive': [_maint_type_map.get(m, {}).get('Preventive', 0) for m in months_6],
        'corrective':  [_maint_type_map.get(m, {}).get('Corrective', 0) for m in months_6],
    })

    # ── Device per lokasi top 10 ──────────────────────────────────
    _dev_lokasi_qs = (
        Device.objects
        .filter(is_deleted=False)
        .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
        .values('lokasi')
        .annotate(
            total=Count('id'),
            operasi=Count('id', filter=Q(status_operasi='operasi')),
            tidak_operasi=Count('id', filter=Q(status_operasi='tidak_operasi')),
        )
        .order_by('-total')[:10]
    )
    device_by_lokasi_json = _json.dumps([
        {
            'lokasi': r['lokasi'], 'total': r['total'],
            'operasi': r['operasi'], 'tidak_operasi': r['tidak_operasi'],
        }
        for r in _dev_lokasi_qs
    ])

    # ── Jadwal kunjungan terdekat ─────────────────────────────────
    try:
        from jadwal.models import JadwalKunjungan
        from datetime import date as _date
        today_d = _date.today()
        jadwal_terdekat = (
            JadwalKunjungan.objects
            .exclude(status='done')
            .filter(
                tahun_rencana=today_d.year,
                bulan_rencana__gte=today_d.month
            )
            .order_by('bulan_rencana', 'lokasi')[:5]
        )
        jadwal_terdekat = [
            {'jadwal': j, 'progress': j.get_progress()}
            for j in jadwal_terdekat
        ]
    except Exception:
        jadwal_terdekat = []

    # ── Notifikasi terbaru belum dibaca ───────────────────────────
    try:
        from notifikasi.models import Notifikasi
        notif_terbaru = (
            Notifikasi.objects
            .filter(is_read=False)
            .select_related('device')
            .order_by('-created_at')[:5]
        )
        notif_unread_total = Notifikasi.objects.filter(is_read=False).count()
    except Exception:
        notif_terbaru      = []
        notif_unread_total = 0

    return render(request, 'devices/dashboard.html', {
        'total_devices':    total_devices,
        'dev_operasi':      dev_operasi,
        'dev_tdk_operasi':  dev_tdk_operasi,
        'device_by_type':              device_by_type,
        'device_status_by_type_json':  device_status_by_type_json,
        'kelompok_data':    kelompok_data,
        'kelompok_json':    kelompok_json,
        'total_maintenance':    total_maintenance,
        'maintenance_open':     maintenance_open,
        'maintenance_done':     maintenance_done,
        'belum_ttd':            belum_ttd,
        'maintenance_by_month': maintenance_by_month,
        'recent_open_maintenance': recent_open_maintenance,
        'maintenance_by_lokasi':   maintenance_by_lokasi,
        'max_lokasi':              max_lokasi,
        # gangguan
        'gangguan_total':    gangguan_total,
        'gangguan_open':     gangguan_open,
        'gangguan_progress': gangguan_progress,
        'gangguan_resolved': gangguan_resolved,
        'gangguan_closed':   gangguan_closed,
        'gangguan_by_month': gangguan_by_month,
        'recent_gangguan':   recent_gangguan,
        # health index
        'hi_summary':        hi_summary,
        'hi_kritis_list':    hi_kritis_list,
        # jadwal & notifikasi
        'jadwal_terdekat':   jadwal_terdekat,
        'notif_terbaru':     notif_terbaru,
        'notif_unread_total': notif_unread_total,
        # analytics extras
        'hi_summary_json':          hi_summary_json,
        'gangguan_kategori_json':   gangguan_kategori_json,
        'gangguan_severity_json':   gangguan_severity_json,
        'gangguan_open_kritis':     gangguan_open_kritis,
        'maintenance_stacked_json': maintenance_stacked_json,
        'device_by_lokasi_json':    device_by_lokasi_json,
    })


@login_required
def distribusi_jenis(request):
    """Halaman distribusi status operasi per jenis perangkat — semua jenis tampil dengan chart masing-masing."""
    PALETTE = [
        '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
        '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#64748b',
    ]

    jenis_qs = (
        Device.objects
        .filter(is_deleted=False)
        .values('jenis__id', 'jenis__name', 'status_operasi')
        .annotate(jumlah=Count('id'))
        .order_by('jenis__name')
    )

    # Kumpulkan per jenis
    jenis_map = {}
    for row in jenis_qs:
        jid   = row['jenis__id']
        jname = row['jenis__name'] or 'Lainnya'
        if jid not in jenis_map:
            jenis_map[jid] = {'id': jid, 'name': jname, 'operasi': 0, 'tidak_operasi': 0}
        jenis_map[jid][row['status_operasi']] = row['jumlah']

    jenis_data = []
    for i, (jid, d) in enumerate(sorted(jenis_map.items(), key=lambda x: x[1]['name'])):
        total = d['operasi'] + d['tidak_operasi']
        jenis_data.append({
            'id':            d['id'],
            'name':          d['name'],
            'operasi':       d['operasi'],
            'tidak_operasi': d['tidak_operasi'],
            'total':         total,
            'pct_operasi':   round(d['operasi'] / total * 100) if total else 0,
            'color':         PALETTE[i % len(PALETTE)],
        })

    jenis_json = json.dumps([
        {'name': d['name'], 'operasi': d['operasi'], 'tidak_operasi': d['tidak_operasi']}
        for d in jenis_data
    ])

    return render(request, 'devices/distribusi_jenis.html', {
        'jenis_data': jenis_data,
        'jenis_json': jenis_json,
    })


def _dashboard_operator(request):
    """Dashboard khusus role Operator — fokus Inservice Inspection."""
    from inspection.models import Inspection, InspectionCatuDaya, InspectionDefenseScheme
    from inspection.models import InspectionMasterTrip, InspectionUFLS
    from datetime import date as date_type, timedelta
    from django.db.models import Count
    from django.db.models.functions import TruncDate, TruncMonth

    today   = date_type.today()
    user    = request.user

    INSPECTABLE = ['Catu Daya', 'RELE DEFENSE SCHEME', 'MASTER TRIP', 'UFLS']

    # ── Filter berdasarkan ULTG user ──────────────────────────────
    ultg         = None
    ultg_lokasi  = None  # None = semua lokasi
    try:
        profile = request.user.profile
        if profile.role == 'operator' and profile.ultg:
            ultg       = profile.ultg
            ultg_lokasi = ultg.get_lokasi_names()
    except Exception:
        pass

    def filter_by_ultg(qs):
        if ultg_lokasi is not None:
            return qs.filter(device__lokasi__in=ultg_lokasi)
        return qs

    def filter_device_by_ultg(qs):
        if ultg_lokasi is not None:
            return qs.filter(lokasi__in=ultg_lokasi)
        return qs

    # ── Statistik harian ─────────────────────────────────────────
    insp_base       = filter_by_ultg(Inspection.objects.all())
    insp_hari_ini   = insp_base.filter(tanggal__date=today).count()
    insp_hari_ini_u = insp_base.filter(tanggal__date=today, operator=user).count()
    insp_bulan_ini  = insp_base.filter(tanggal__year=today.year, tanggal__month=today.month).count()
    insp_total      = insp_base.count()

    # ── Alarm hari ini ────────────────────────────────────────────
    alarm_count = 0
    for insp in insp_base.filter(tanggal__date=today).select_related('device'):
        try:
            if insp.jenis == 'catu_daya':
                d = insp.detail_catu_daya
                if d.kondisi_rectifier == 'alarm': alarm_count += 1
            elif insp.jenis == 'defense_scheme':
                d = insp.detail_defense_scheme
                if d.kondisi_relay == 'faulty' or d.indikator_led == 'faulty': alarm_count += 1
            elif insp.jenis == 'master_trip':
                d = insp.detail_master_trip
                if d.kondisi_relay == 'faulty' or d.indikator_led == 'faulty': alarm_count += 1
            elif insp.jenis == 'ufls':
                d = insp.detail_ufls
                if d.kondisi_relay == 'faulty' or d.indikator_led == 'faulty': alarm_count += 1
        except Exception:
            pass

    # ── Total device per jenis inspectable ───────────────────────
    device_stats = []
    for jenis_name in INSPECTABLE:
        devs = filter_device_by_ultg(
            Device.objects.filter(is_deleted=False, jenis__name=jenis_name)
        )
        total = devs.count()
        if total == 0:
            continue
        inspected_ids = filter_by_ultg(Inspection.objects.filter(
            device__in=devs,
            tanggal__year=today.year, tanggal__month=today.month
        )).values_list('device_id', flat=True).distinct()
        sudah = len(set(inspected_ids))
        belum = total - sudah
        pct   = round(sudah / total * 100) if total else 0
        device_stats.append({
            'jenis': jenis_name, 'total': total,
            'sudah': sudah, 'belum': belum, 'pct': pct,
        })

    # ── Trend inspeksi 7 hari terakhir ───────────────────────────
    trend_7 = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = insp_base.filter(tanggal__date=d).count()
        trend_7.append({'label': d.strftime('%d %b'), 'count': count, 'is_today': d == today})

    # ── Trend inspeksi per jenis 30 hari ─────────────────────────
    insp_by_jenis = (
        insp_base
        .filter(tanggal__date__gte=today - timedelta(days=30))
        .values('jenis')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    # ── Inspeksi terbaru ──────────────────────────────────────────
    recent_inspections = (
        insp_base
        .select_related('device', 'device__jenis', 'operator')
        .order_by('-tanggal')[:10]
    )
    # Tambah status kondisi
    recent_list = []
    for insp in recent_inspections:
        status = 'normal'
        try:
            if insp.jenis == 'catu_daya':
                d = insp.detail_catu_daya
                if d.kondisi_rectifier == 'alarm': status = 'alarm'
            elif insp.jenis in ('defense_scheme', 'master_trip', 'ufls'):
                if insp.jenis == 'defense_scheme': d = insp.detail_defense_scheme
                elif insp.jenis == 'master_trip':  d = insp.detail_master_trip
                else:                              d = insp.detail_ufls
                if d.kondisi_relay == 'faulty' or d.indikator_led == 'faulty':
                    status = 'alarm'
        except Exception:
            pass
        insp.status_kondisi = status
        recent_list.append(insp)

    # ── Device belum diinspeksi bulan ini ─────────────────────────
    all_inspectable = filter_device_by_ultg(
        Device.objects.filter(is_deleted=False, jenis__name__in=INSPECTABLE)
    ).select_related('jenis')
    insp_ids_bulan = insp_base.filter(
        tanggal__year=today.year, tanggal__month=today.month
    ).values_list('device_id', flat=True).distinct()
    belum_insp = all_inspectable.exclude(pk__in=insp_ids_bulan).order_by('jenis__name','lokasi','nama')[:15]

    return render(request, 'devices/dashboard_operator.html', {
        'today':              today,
        'insp_hari_ini':      insp_hari_ini,
        'insp_hari_ini_u':    insp_hari_ini_u,
        'insp_bulan_ini':     insp_bulan_ini,
        'insp_total':         insp_total,
        'alarm_count':        alarm_count,
        'device_stats':       device_stats,
        'trend_7':            trend_7,
        'insp_by_jenis':      list(insp_by_jenis),
        'recent_list':        recent_list,
        'belum_insp':         belum_insp,
        'ultg':               ultg,
    })


@login_required
def device_detail(request, pk):
    device = get_object_or_404(Device, pk=pk)
    maintenance_history = Maintenance.objects.filter(device=device).order_by('-date')
    maintenance_total = maintenance_history.count()
    maintenance_done = maintenance_history.filter(status='Done').count()
    maintenance_open = maintenance_history.filter(status='Open').count()

    # Bangun spesifikasi_display: [{label, value, is_sfp}] berdasarkan schema
    spesifikasi_display = []
    if device.spesifikasi and device.jenis:
        jenis_name = device.jenis.name
        schema_fields = DEVICE_SCHEMA.get(jenis_name, [])
        # Buat mapping key -> label dari schema
        label_map = {f["key"]: f["label"] for f in schema_fields}
        for key, value in device.spesifikasi.items():
            if not value and value != 0:
                continue
            label = label_map.get(key, key.replace("_", " ").title())
            if key == "sfp_speeds" and isinstance(value, list):
                # Tampilkan per port
                for i, speed in enumerate(value, 1):
                    if speed:
                        spesifikasi_display.append({
                            "label": f"SFP Port {i}",
                            "value": speed,
                            "is_sfp": True,
                        })
            else:
                spesifikasi_display.append({
                    "label": label,
                    "value": value if not isinstance(value, list) else ", ".join(str(v) for v in value if v),
                    "is_sfp": False,
                })

    # Hitung umur peralatan (dalam tahun) dari tahun_operasi
    umur_peralatan = None
    if device.tahun_operasi:
        umur_peralatan = date_type.today().year - device.tahun_operasi

    # Hitung Health Index
    from health_index.calculator import calculate_hi
    health_index = calculate_hi(device)

    # Audit log
    from devices.models import DeviceLog, DeviceEvent
    device_logs     = DeviceLog.objects.filter(device=device).order_by('-created_at')
    last_update_log = device_logs.first()
    device_events   = DeviceEvent.objects.filter(device=device).order_by('-tanggal', '-created_at')

    # Komponen perangkat
    from devices.views_komponen import get_komponen_for_device, _get_tipe_grouped
    komponen_list = get_komponen_for_device(device)
    tipe_grouped = _get_tipe_grouped()

    # Eviden tambahan
    from devices.models import DeviceEviden
    eviden_list = DeviceEviden.objects.filter(device=device).order_by('uploaded_at')

    # VM children (untuk SERVER SCADA)
    vm_children = device.vm_children.filter(is_deleted=False).order_by('nama')

    # Kandidat host server untuk form tambah VM (SERVER SCADA yg bukan VM)
    host_candidates = Device.objects.filter(
        is_deleted=False,
        host__isnull=True,
        jenis__name__icontains='server scada',
    ).exclude(pk=device.pk)

    return render(request, 'devices/device_detail.html', {
        'device':             device,
        'maintenance_history': maintenance_history,
        'maintenance_total':  maintenance_total,
        'maintenance_done':   maintenance_done,
        'maintenance_open':   maintenance_open,
        'spesifikasi_display': spesifikasi_display,
        'umur_peralatan':     umur_peralatan,
        'health_index':       health_index,
        'device_logs':        device_logs,
        'last_update_log':    last_update_log,
        'device_events':      device_events,
        'komponen_list':      komponen_list,
        'tipe_grouped':       tipe_grouped,
        'eviden_list':        eviden_list,
        'today_date':         date_type.today().strftime('%Y-%m-%d'),
        'vm_children':        vm_children,
        'host_candidates':    host_candidates,
    })


@login_required
def device_by_type(request, type_id):
    device_type = get_object_or_404(DeviceType, id=type_id)
    if device_type.name.strip().upper() == 'VM SCADA':
        devices = Device.objects.filter(jenis_id=type_id, is_deleted=False, host__isnull=False)
    else:
        devices = Device.objects.filter(jenis_id=type_id, is_deleted=False, host__isnull=True)
    lokasi_list = (
        Device.objects.filter(is_deleted=False)
        .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
        .annotate(lokasi_clean=Trim('lokasi'))
        .values_list('lokasi_clean', flat=True)
        .distinct().order_by('lokasi_clean')
    )
    return render(request, 'devices/device_list.html', {
        'devices': devices,
        'filter_type': device_type,
        'lokasi_list': lokasi_list,
        'selected_jenis': type_id,
    })


@login_required
def lokasi_list(request):
    lokasi_data = (
        Device.objects
        .filter(is_deleted=False)
        .exclude(lokasi__isnull=True)
        .exclude(lokasi__exact='')
        .exclude(lokasi__iexact='none')
        .annotate(lokasi_clean=Trim('lokasi'))
        .values('lokasi_clean')
        .annotate(total_device=Count('id'))
        .order_by('lokasi_clean')
    )
    # Tambahkan info maintenance open per lokasi
    from maintenance.models import Maintenance
    open_by_lokasi = {}
    for m in Maintenance.objects.filter(status='Open').select_related('device'):
        loc = (m.device.lokasi or '').strip()
        open_by_lokasi[loc] = open_by_lokasi.get(loc, 0) + 1

    # Ambil koordinat dari SiteLocation
    site_coords = {sl.nama: sl for sl in SiteLocation.objects.all()}

    lokasi_list_final = []
    for row in lokasi_data:
        row = dict(row)
        row['maintenance_open'] = open_by_lokasi.get(row['lokasi_clean'], 0)
        sl = site_coords.get(row['lokasi_clean'])
        row['latitude']  = sl.latitude  if sl and sl.has_coords else None
        row['longitude'] = sl.longitude if sl and sl.has_coords else None
        row['has_coords'] = bool(row['latitude'] and row['longitude'])
        lokasi_list_final.append(row)

    return render(request, 'devices/lokasi_list.html', {'lokasi_data': lokasi_list_final})


def api_lokasi_devices(request, lokasi_nama):
    """API endpoint: kembalikan daftar device di suatu lokasi sebagai JSON."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthenticated'}, status=401)
    devices = (
        Device.objects
        .filter(is_deleted=False, lokasi__iexact=lokasi_nama)
        .select_related('jenis')
        .values('id', 'nama', 'jenis__name', 'merk', 'type', 'ip_address', 'serial_number')
        .order_by('jenis__name', 'nama')
    )
    data = [
        {
            'id':     d['id'],
            'nama':   d['nama'],
            'jenis':  d['jenis__name'] or '-',
            'merk':   d['merk'],
            'type':   d['type'] or '-',
            'ip':     d['ip_address'] or '-',
            'sn':     d['serial_number'] or '-',
        }
        for d in devices
    ]
    return JsonResponse({'lokasi': lokasi_nama, 'devices': data})


@login_required
@login_required
def layanan_icon(request):
    icons = Icon.objects.all()

    # Filter
    search = request.GET.get('q', '').strip()
    selected_kondisi = request.GET.get('kondisi', '').strip()
    sort_by  = request.GET.get('sort', 'name')
    sort_dir = request.GET.get('dir', 'asc')

    if search:
        icons = icons.filter(
            Q(name__icontains=search) |
            Q(lokasi_layanan__icontains=search) |
            Q(SID1__icontains=search) |
            Q(SID2__icontains=search) |
            Q(keterangan__icontains=search)
        )
    if selected_kondisi:
        icons = icons.filter(kondisi_operasional__icontains=selected_kondisi)

    # Sort
    SORT_FIELDS = {
        'name':     'name',
        'lokasi':   'lokasi_layanan',
        'bandwidth':'bandwidth',
        'sid1':     'SID1',
        'kontrak':  'kontrak',
        'kondisi':  'kondisi_operasional',
    }
    order_field = SORT_FIELDS.get(sort_by, 'name')
    if sort_dir == 'desc':
        order_field = '-' + order_field
    icons = icons.order_by(order_field)

    icons = list(icons)

    # Hitung jumlah gangguan per icon (berdasarkan FK layanan_icon di model Gangguan)
    from gangguan.models import Gangguan
    gangguan_counts = dict(
        Gangguan.objects.filter(layanan_icon__isnull=False)
        .values('layanan_icon_id')
        .annotate(total=Count('id'))
        .values_list('layanan_icon_id', 'total')
    )
    for icon in icons:
        icon.jumlah_gangguan = gangguan_counts.get(icon.id, 0)

    # Summary counters
    operasi_baik = sum(
        1 for i in icons
        if i.kondisi_operasional and 'Baik' in i.kondisi_operasional
    )
    operasi_gangguan = sum(
        1 for i in icons
        if i.kondisi_operasional and (
            'Gangguan' in i.kondisi_operasional or
            'NOK' in i.kondisi_operasional
        )
    )
    operasi_lain = sum(
        1 for i in icons
        if i.kondisi_operasional and
        'Baik' not in i.kondisi_operasional and
        'Gangguan' not in i.kondisi_operasional and
        'NOK' not in i.kondisi_operasional and
        'Tidak Operasi' in i.kondisi_operasional
    )

    # Total tiket gangguan aktif yang terkait layanan ICON+
    total_gangguan_aktif = Gangguan.objects.filter(
        layanan_icon__isnull=False,
        status__in=('open', 'in_progress')
    ).count()

    # Distinct kondisi values for filter dropdown
    kondisi_list = sorted(set(
        i.kondisi_operasional for i in Icon.objects.all()
        if i.kondisi_operasional
    ))

    return render(request, 'devices/layanan_icon.html', {
        'icons':                icons,
        'search':               search,
        'selected_kondisi':     selected_kondisi,
        'kondisi_list':         kondisi_list,
        'operasi_baik':         operasi_baik,
        'gangguan':             operasi_gangguan,
        'lainnya':              operasi_lain,
        'sort_by':              sort_by,
        'sort_dir':             sort_dir,
        'total_gangguan_aktif': total_gangguan_aktif,
    })


# ══════════════════════════════════════════════════════════════
# FIBER OPTIC VIEWS
# ══════════════════════════════════════════════════════════════

@login_required
def fiber_optic_list(request):
    from .models import FiberOptic
    from gangguan.models import Gangguan

    qs = FiberOptic.objects.all()

    search       = request.GET.get('q', '').strip()
    status_f     = request.GET.get('status', '').strip()
    sort_by      = request.GET.get('sort', 'nama')
    sort_dir     = request.GET.get('dir', 'asc')

    if search:
        qs = qs.filter(
            Q(nama__icontains=search) |
            Q(lokasi_a__icontains=search) |
            Q(lokasi_b__icontains=search) |
            Q(keterangan__icontains=search)
        )
    if status_f:
        qs = qs.filter(status=status_f)

    SORT_MAP = {
        'nama': 'nama', 'lokasi_a': 'lokasi_a', 'lokasi_b': 'lokasi_b',
        'panjang': 'panjang_km', 'status': 'status',
    }
    order_field = SORT_MAP.get(sort_by, 'nama')
    if sort_dir == 'desc':
        order_field = '-' + order_field
    qs = qs.order_by(order_field)

    fo_list = list(qs)

    # Hitung jumlah gangguan per segmen FO
    gangguan_counts = dict(
        Gangguan.objects.filter(fiber_optic__isnull=False)
        .values('fiber_optic_id')
        .annotate(total=Count('id'))
        .values_list('fiber_optic_id', 'total')
    )
    for fo in fo_list:
        fo.jumlah_gangguan = gangguan_counts.get(fo.id, 0)

    # Summary
    total_fo        = len(fo_list)
    total_baik      = sum(1 for f in fo_list if f.status == 'baik')
    total_gangguan  = sum(1 for f in fo_list if f.status == 'gangguan')
    total_perbaikan = sum(1 for f in fo_list if f.status == 'dalam_perbaikan')

    total_aktif = Gangguan.objects.filter(
        fiber_optic__isnull=False,
        status__in=('open', 'in_progress')
    ).count()

    return render(request, 'devices/fiber_optic_list.html', {
        'fo_list':           fo_list,
        'search':            search,
        'status_filter':     status_f,
        'sort_by':           sort_by,
        'sort_dir':          sort_dir,
        'total_fo':          total_fo,
        'total_baik':        total_baik,
        'total_gangguan':    total_gangguan,
        'total_perbaikan':   total_perbaikan,
        'total_aktif':       total_aktif,
        'STATUS_CHOICES':    FiberOptic.STATUS_CHOICES,
    })


@login_required
@require_can_edit
def fiber_optic_create(request):
    from .models import FiberOptic, FiberOpticCore, SiteLocation
    lokasi_list = list(SiteLocation.objects.values_list('nama', flat=True).order_by('nama'))
    if request.method == 'POST':
        jumlah_core = int(request.POST['jumlah_core']) if request.POST.get('jumlah_core') else None
        fo = FiberOptic(
            nama            = request.POST.get('nama', '').strip(),
            lokasi_a        = request.POST.get('lokasi_a', '').strip(),
            lokasi_b        = request.POST.get('lokasi_b', '').strip(),
            tipe_kabel      = request.POST.get('tipe_kabel') or None,
            tipe_konektor   = request.POST.get('tipe_konektor') or None,
            tipe_konektor_a = request.POST.get('tipe_konektor_a') or None,
            tipe_konektor_b = request.POST.get('tipe_konektor_b') or None,
            jumlah_core     = jumlah_core,
            konfigurasi     = request.POST.get('konfigurasi') or None,
            panjang_km      = request.POST.get('panjang_km') or None,
            tahun_pasang    = int(request.POST['tahun_pasang']) if request.POST.get('tahun_pasang') else None,
            status          = request.POST.get('status', 'baik'),
            keterangan      = request.POST.get('keterangan', '').strip() or None,
            created_by      = request.user,
        )
        if request.FILES.get('foto_site_a'):
            fo.foto_site_a = request.FILES['foto_site_a']
        if request.FILES.get('foto_site_b'):
            fo.foto_site_b = request.FILES['foto_site_b']
        fo.save()
        if jumlah_core:
            for n in range(1, jumlah_core + 1):
                FiberOpticCore.objects.get_or_create(fiber_optic=fo, nomor_core=n)
        return redirect('fiber_optic_detail', pk=fo.pk)
    return render(request, 'devices/fiber_optic_form.html', {
        'is_edit':           False,
        'TIPE_KABEL':        FiberOptic.TIPE_KABEL_CHOICES,
        'TIPE_KONEKTOR':     FiberOptic.TIPE_KONEKTOR_CHOICES,
        'KONFIGURASI':       FiberOptic.KONFIGURASI_CHOICES,
        'STATUS_CHOICES':    FiberOptic.STATUS_CHOICES,
        'lokasi_list':       lokasi_list,
    })


@login_required
@require_can_edit
def fiber_optic_update(request, pk):
    from .models import FiberOptic, FiberOpticCore, SiteLocation
    fo = get_object_or_404(FiberOptic, pk=pk)
    lokasi_list = list(SiteLocation.objects.values_list('nama', flat=True).order_by('nama'))
    if request.method == 'POST':
        jumlah_core_baru = int(request.POST['jumlah_core']) if request.POST.get('jumlah_core') else None
        fo.nama            = request.POST.get('nama', '').strip()
        fo.lokasi_a        = request.POST.get('lokasi_a', '').strip()
        fo.lokasi_b        = request.POST.get('lokasi_b', '').strip()
        fo.tipe_kabel      = request.POST.get('tipe_kabel') or None
        fo.tipe_konektor   = request.POST.get('tipe_konektor') or None
        fo.tipe_konektor_a = request.POST.get('tipe_konektor_a') or None
        fo.tipe_konektor_b = request.POST.get('tipe_konektor_b') or None
        fo.jumlah_core     = jumlah_core_baru
        fo.konfigurasi     = request.POST.get('konfigurasi') or None
        fo.panjang_km      = request.POST.get('panjang_km') or None
        fo.tahun_pasang    = int(request.POST['tahun_pasang']) if request.POST.get('tahun_pasang') else None
        fo.status          = request.POST.get('status', 'baik')
        fo.keterangan      = request.POST.get('keterangan', '').strip() or None
        if request.FILES.get('foto_site_a'):
            fo.foto_site_a = request.FILES['foto_site_a']
        if request.FILES.get('foto_site_b'):
            fo.foto_site_b = request.FILES['foto_site_b']
        fo.save()
        # Tambah core baru jika jumlah_core bertambah
        if jumlah_core_baru:
            existing = set(fo.cores.values_list('nomor_core', flat=True))
            for n in range(1, jumlah_core_baru + 1):
                if n not in existing:
                    FiberOpticCore.objects.create(fiber_optic=fo, nomor_core=n)
        return redirect('fiber_optic_detail', pk=fo.pk)
    return render(request, 'devices/fiber_optic_form.html', {
        'is_edit':        True,
        'fo':             fo,
        'TIPE_KABEL':     FiberOptic.TIPE_KABEL_CHOICES,
        'TIPE_KONEKTOR':  FiberOptic.TIPE_KONEKTOR_CHOICES,
        'KONFIGURASI':    FiberOptic.KONFIGURASI_CHOICES,
        'STATUS_CHOICES': FiberOptic.STATUS_CHOICES,
        'lokasi_list':    lokasi_list,
    })


@login_required
def fiber_optic_detail(request, pk):
    import json as _json
    from .models import FiberOptic, FiberOpticCore
    fo = get_object_or_404(FiberOptic, pk=pk)
    cores = fo.cores.order_by('nomor_core')
    from gangguan.models import Gangguan
    gangguan_list = Gangguan.objects.filter(fiber_optic=fo).order_by('-tanggal_gangguan')

    # Build JSON for OTDR dashboard
    def _f(v):
        return float(v) if v is not None else None

    cores_json = _json.dumps([{
        'pk':              c.pk,
        'nomor_core':      c.nomor_core,
        'fungsi':          c.fungsi or '',
        'status':          c.status,
        'status_a':        c.status_a,
        'status_b':        c.status_b,
        'koneksi_a':       c.koneksi_a or '',
        'koneksi_b':       c.koneksi_b or '',
        # OTDR Site A (existing fields)
        'a_jarak':         _f(c.otdr_jarak_km),
        'a_redaman':       _f(c.otdr_redaman_db),
        'a_dbkm':          _f(c.otdr_redaman_per_km),
        'a_tanggal':       str(c.otdr_tanggal) if c.otdr_tanggal else '',
        'a_catatan':       c.otdr_catatan or '',
        # OTDR Site B (new fields)
        'b_jarak':         _f(c.otdr_b_jarak_km),
        'b_redaman':       _f(c.otdr_b_redaman_db),
        'b_dbkm':          _f(c.otdr_b_redaman_per_km),
        'b_tanggal':       str(c.otdr_b_tanggal) if c.otdr_b_tanggal else '',
        'b_catatan':       c.otdr_b_catatan or '',
    } for c in cores])

    return render(request, 'devices/fiber_optic_detail.html', {
        'fo':            fo,
        'cores':         cores,
        'gangguan_list': gangguan_list,
        'STATUS_CORE':   FiberOpticCore.STATUS_CORE_CHOICES,
        'cores_json':    cores_json,
    })


@login_required
@require_can_edit
def fiber_optic_core_update(request, fo_pk, core_pk):
    """Update satu baris core via POST (AJAX-friendly)."""
    from .models import FiberOpticCore
    core = get_object_or_404(FiberOpticCore, pk=core_pk, fiber_optic_id=fo_pk)
    if request.method == 'POST':
        # shared fields
        core.fungsi     = request.POST.get('fungsi', '').strip() or None
        core.keterangan = request.POST.get('keterangan', '').strip() or None

        site = request.POST.get('site', 'a')
        if site == 'a':
            core.status_a               = request.POST.get('status_a', 'spare')
            core.koneksi_a              = request.POST.get('koneksi_a', '').strip() or None
            core.otdr_jarak_km          = request.POST.get('otdr_jarak_km') or None
            core.otdr_redaman_db        = request.POST.get('otdr_redaman_db') or None
            core.otdr_redaman_per_km    = request.POST.get('otdr_redaman_per_km') or None
            core.otdr_tanggal           = request.POST.get('otdr_tanggal') or None
            core.otdr_catatan           = request.POST.get('otdr_catatan', '').strip() or None
        else:  # site == 'b'
            core.status_b               = request.POST.get('status_b', 'spare')
            core.koneksi_b              = request.POST.get('koneksi_b', '').strip() or None
            core.otdr_b_jarak_km        = request.POST.get('otdr_b_jarak_km') or None
            core.otdr_b_redaman_db      = request.POST.get('otdr_b_redaman_db') or None
            core.otdr_b_redaman_per_km  = request.POST.get('otdr_b_redaman_per_km') or None
            core.otdr_b_tanggal         = request.POST.get('otdr_b_tanggal') or None
            core.otdr_b_catatan         = request.POST.get('otdr_b_catatan', '').strip() or None

        # keep legacy status in sync with the site being updated
        core.status = core.status_a if site == 'a' else core.status_b
        core.save()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': True})
    return redirect('fiber_optic_detail', pk=fo_pk)


@login_required
@require_can_delete
def fiber_optic_delete(request, pk):
    from .models import FiberOptic
    fo = get_object_or_404(FiberOptic, pk=pk)
    if request.method == 'POST':
        fo.delete()
    return redirect('fiber_optic_list')


def api_fiber_optic_json(request):
    """API: semua segmen FO sebagai JSON untuk JS autocomplete di form gangguan."""
    from .models import FiberOptic
    data = list(
        FiberOptic.objects.all().order_by('nama').values(
            'id', 'nama', 'lokasi_a', 'lokasi_b',
            'tipe_kabel', 'tipe_konektor', 'jumlah_core',
            'panjang_km', 'status',
        )
    )
    for d in data:
        if d['panjang_km']:
            d['panjang_km'] = str(d['panjang_km'])
    return JsonResponse({'fiber_optic': data})

@login_required
@require_can_edit
def icon_create(request):
    if request.method == 'POST':
        form = IconForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('layanan_icon')
    else:
        form = IconForm()
    return render(request, 'devices/icon_form.html', {
        'form': form,
        'is_edit': False,
        'kondisi_choices': [('Operasi Baik','Operasi Baik'),('Gangguan','Gangguan'),('Tidak Operasi','Tidak Operasi'),('Dalam Pemeliharaan','Dalam Pemeliharaan')],
    })


@login_required
@require_can_edit
def icon_update(request, pk):
    icon = get_object_or_404(Icon, pk=pk)
    if request.method == 'POST':
        form = IconForm(request.POST, request.FILES, instance=icon)
        if form.is_valid():
            form.save()
            return redirect('layanan_icon')
    else:
        form = IconForm(instance=icon)
    return render(request, 'devices/icon_form.html', {
        'form': form,
        'is_edit': True,
        'icon': icon,
        'kondisi_choices': [('Operasi Baik','Operasi Baik'),('Gangguan','Gangguan'),('Tidak Operasi','Tidak Operasi'),('Dalam Pemeliharaan','Dalam Pemeliharaan')],
    })


@login_required
@require_can_delete
def icon_delete(request, pk):
    icon = get_object_or_404(Icon, pk=pk)
    if request.method == 'POST':
        icon.delete()
    return redirect('layanan_icon')


# =====================================================
# QR CODE VIEW — buka halaman print QR
# =====================================================
@login_required
def device_qr(request, pk):
    device = get_object_or_404(Device, pk=pk)
    from django.urls import reverse
    if device.public_token:
        public_url = request.build_absolute_uri(
            reverse('device_public', args=[device.public_token])
        )
    else:
        import secrets
        device.public_token = secrets.token_urlsafe(20)
        device.save(update_fields=['public_token'])
        public_url = request.build_absolute_uri(
            reverse('device_public', args=[device.public_token])
        )
    return render(request, 'devices/device_qr.html', {
        'device':     device,
        'detail_url': public_url,
        'public_url': public_url,
    })


# =====================================================
# EXPORT DEVICES KE EXCEL
# =====================================================
@login_required
def export_devices_excel(request):
    jenis_id = request.GET.get('jenis')
    search = request.GET.get('q') or ''
    lokasi = request.GET.get('lokasi')

    devices = Device.objects.filter(is_deleted=False).select_related('jenis')

    if jenis_id:
        devices = devices.filter(jenis_id=jenis_id)
    if search:
        devices = devices.filter(Q(nama__icontains=search) | Q(ip_address__icontains=search))
    if lokasi:
        devices = devices.filter(lokasi=lokasi)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventory Peralatan"

    # Styles
    header_fill = PatternFill("solid", fgColor="0F172A")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # Judul
    ws.merge_cells('A1:I1')
    title_cell = ws['A1']
    title_cell.value = "INVENTORY PERALATAN FASOP UP2B"
    title_cell.font = Font(bold=True, size=13)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    title_cell.fill = PatternFill("solid", fgColor="EFF6FF")
    ws.row_dimensions[1].height = 28

    ws.merge_cells('A2:I2')
    from datetime import date
    ws['A2'].value = f"Dicetak: {date.today().strftime('%d %B %Y')}"
    ws['A2'].alignment = Alignment(horizontal="center")
    ws['A2'].font = Font(size=10, italic=True, color="64748B")
    ws.row_dimensions[2].height = 18

    ws.row_dimensions[3].height = 6  # spacer

    # Header
    headers = ['No', 'Nama', 'Jenis', 'Merk', 'Type/Model', 'Serial Number', 'IP Address', 'Lokasi', 'Firmware']
    col_widths = [5, 25, 15, 15, 18, 20, 16, 20, 15]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=4, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[4].height = 22

    # Data
    alt_fill = PatternFill("solid", fgColor="F8FAFC")
    for row_idx, d in enumerate(devices, 1):
        ws_row = row_idx + 4
        row_data = [
            row_idx,
            d.nama,
            d.jenis.name if d.jenis else '-',
            d.merk,
            d.type or '-',
            d.serial_number or '-',
            str(d.ip_address),
            d.lokasi,
            d.firmware_version or '-',
        ]
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=ws_row, column=col_idx, value=value)
            cell.border = thin_border
            cell.alignment = center_align if col_idx == 1 else Alignment(vertical="center")
            if row_idx % 2 == 0:
                cell.fill = alt_fill
        ws.row_dimensions[ws_row].height = 18

    # Freeze panes
    ws.freeze_panes = 'A5'

    # Response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="inventory_peralatan_fasop.xlsx"'
    wb.save(response)
    return response


@login_required
def export_icon_excel(request):
    from datetime import date

    icons = Icon.objects.all()

    # Apply same filters as list view
    search = request.GET.get('q', '').strip()
    selected_kondisi = request.GET.get('kondisi', '').strip()
    if search:
        icons = icons.filter(
            Q(name__icontains=search) |
            Q(lokasi_layanan__icontains=search) |
            Q(SID1__icontains=search) |
            Q(SID2__icontains=search) |
            Q(keterangan__icontains=search)
        )
    if selected_kondisi:
        icons = icons.filter(kondisi_operasional__icontains=selected_kondisi)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Layanan ICON+"

    # Styles
    header_fill  = PatternFill("solid", fgColor="0F172A")
    header_font  = Font(bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align   = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin_border  = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'),  bottom=Side(style='thin')
    )
    alt_fill = PatternFill("solid", fgColor="F8FAFC")

    COLS = 9

    # Judul
    ws.merge_cells(f'A1:{get_column_letter(COLS)}1')
    ws['A1'].value     = "DATA LAYANAN ICON+ — FASOP UP2B"
    ws['A1'].font      = Font(bold=True, size=13)
    ws['A1'].alignment = Alignment(horizontal="center", vertical="center")
    ws['A1'].fill      = PatternFill("solid", fgColor="EFF6FF")
    ws.row_dimensions[1].height = 28

    ws.merge_cells(f'A2:{get_column_letter(COLS)}2')
    ws['A2'].value     = f"Dicetak: {date.today().strftime('%d %B %Y')}"
    ws['A2'].alignment = Alignment(horizontal="center")
    ws['A2'].font      = Font(size=10, italic=True, color="64748B")
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 6  # spacer

    # Header row
    headers    = ['No', 'Nama Layanan', 'Lokasi Layanan', 'Bandwidth', 'SID 1', 'SID 2', 'Kontrak', 'Kondisi Operasional', 'Keterangan']
    col_widths = [5,    28,             25,                14,          22,      22,      18,        22,                   35]

    for col_idx, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=4, column=col_idx, value=h)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = header_align
        cell.border    = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = w
    ws.row_dimensions[4].height = 22

    # Conditional fill colours for kondisi
    green_fill  = PatternFill("solid", fgColor="DCFCE7")
    red_fill    = PatternFill("solid", fgColor="FEE2E2")
    yellow_fill = PatternFill("solid", fgColor="FEF3C7")

    # Data rows
    for row_idx, d in enumerate(icons, 1):
        ws_row = row_idx + 4
        row_data = [
            row_idx,
            d.name or '-',
            d.lokasi_layanan or '-',
            d.bandwidth or '-',
            d.SID1 or '-',
            d.SID2 or '-',
            d.kontrak or '-',
            d.kondisi_operasional or '-',
            d.keterangan or '-',
        ]
        for col_idx, value in enumerate(row_data, 1):
            cell            = ws.cell(row=ws_row, column=col_idx, value=value)
            cell.border     = thin_border
            cell.alignment  = center_align if col_idx == 1 else left_align
            if row_idx % 2 == 0:
                cell.fill = alt_fill

        # Colour-code kondisi cell (col 8)
        kondisi_val = d.kondisi_operasional or ''
        kondisi_cell = ws.cell(row=ws_row, column=8)
        if 'Baik' in kondisi_val:
            kondisi_cell.fill = green_fill
            kondisi_cell.font = Font(bold=True, color="065F46")
        elif 'Gangguan' in kondisi_val or 'NOK' in kondisi_val:
            kondisi_cell.fill = red_fill
            kondisi_cell.font = Font(bold=True, color="991B1B")
        elif kondisi_val != '-':
            kondisi_cell.fill = yellow_fill
            kondisi_cell.font = Font(bold=True, color="92400E")

        ws.row_dimensions[ws_row].height = 18

    # Freeze header
    ws.freeze_panes = 'A5'

    # Auto-filter
    ws.auto_filter.ref = f'A4:{get_column_letter(COLS)}{4 + icons.count() if hasattr(icons, "count") else 4 + len(list(icons))}'

    # Response
    from django.http import HttpResponse
    import io
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"layanan_icon_{date.today().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# ── Device Event Views ──────────────────────────────────────────────────────

@login_required
@require_can_edit
def device_event_add(request, pk):
    """Tambah event kejadian fisik peralatan."""
    device = get_object_or_404(Device, pk=pk)

    if request.method == 'POST':
        from devices.models import DeviceEvent
        from devices.models_komponen import DeviceComponent
        tipe          = request.POST.get('tipe', '').strip()
        tanggal       = request.POST.get('tanggal', '')
        komponen      = request.POST.get('komponen', '').strip()
        komponen_terkait_pk = request.POST.get('komponen_terkait_id', '') or None
        nilai_lama    = request.POST.get('nilai_lama', '').strip()
        nilai_baru    = request.POST.get('nilai_baru', '').strip()
        lokasi_asal   = request.POST.get('lokasi_asal', '').strip()
        lokasi_tujuan = request.POST.get('lokasi_tujuan', '').strip()
        catatan       = request.POST.get('catatan', '').strip()
        foto          = request.FILES.get('foto')

        komponen_terkait_obj = None
        if komponen_terkait_pk:
            komponen_terkait_obj = DeviceComponent.objects.filter(pk=komponen_terkait_pk).first()

        if tipe and tanggal:
            event = DeviceEvent(
                device        = device,
                tipe          = tipe,
                tanggal       = tanggal,
                komponen      = komponen,
                komponen_terkait = komponen_terkait_obj,
                nilai_lama    = nilai_lama,
                nilai_baru    = nilai_baru,
                lokasi_asal   = lokasi_asal,
                lokasi_tujuan = lokasi_tujuan,
                catatan       = catatan,
                dilakukan_oleh = request.user,
            )
            if foto:
                event.foto = foto
            event.save()

            # Auto-update lokasi device jika relokasi
            if tipe == 'relokasi' and lokasi_tujuan:
                old_lokasi = device.lokasi
                device.lokasi = lokasi_tujuan.upper()
                device.save(update_fields=['lokasi'])
                # Catat di audit log
                from devices.device_audit import log_edit
                import copy
                d_before = copy.copy(device)
                d_before.lokasi = old_lokasi
                device_copy = copy.copy(device)
                log_edit(d_before, device_copy, request.user)

            # Auto-update status DeviceComponent
            if komponen_terkait_obj:
                from django.utils import timezone as _tz
                if tipe == 'penggantian':
                    komponen_terkait_obj.status = 'diganti'
                    komponen_terkait_obj.tanggal_ganti = _tz.localdate()
                    komponen_terkait_obj.save(update_fields=['status', 'tanggal_ganti', 'updated_at'])
                elif tipe == 'pembongkaran':
                    komponen_terkait_obj.status = 'tidak_ada'
                    komponen_terkait_obj.save(update_fields=['status', 'updated_at'])
                elif tipe in ('pemasangan', 'penambahan'):
                    komponen_terkait_obj.status = 'terpasang'
                    komponen_terkait_obj.tanggal_pasang = _tz.localdate()
                    komponen_terkait_obj.save(update_fields=['status', 'tanggal_pasang', 'updated_at'])

    return redirect('device_view', pk=pk)


@login_required
@require_can_delete
def device_event_delete(request, pk, event_pk):
    """Hapus event kejadian fisik."""
    if request.method == 'POST':
        from devices.models import DeviceEvent
        event = get_object_or_404(DeviceEvent, pk=event_pk, device_id=pk)
        event.delete()
    return redirect('device_view', pk=pk)


# ── Manajemen Lokasi (Admin only) ─────────────────────────────────────────────

@login_required
@require_can_manage_lokasi
def lokasi_admin(request):

    if request.method == 'POST':
        action = request.POST.get('action')
        pk     = request.POST.get('pk')

        if action == 'add':
            nama = request.POST.get('nama', '').strip().upper()
            lat  = request.POST.get('latitude', '').strip()
            lng  = request.POST.get('longitude', '').strip()
            ket  = request.POST.get('keterangan', '').strip()
            if nama:
                SiteLocation.objects.get_or_create(
                    nama=nama,
                    defaults={
                        'latitude':    float(lat) if lat else None,
                        'longitude':   float(lng) if lng else None,
                        'keterangan':  ket,
                    }
                )

        elif action == 'edit' and pk:
            site = get_object_or_404(SiteLocation, pk=pk)
            nama = request.POST.get('nama', '').strip().upper()
            lat  = request.POST.get('latitude', '').strip()
            lng  = request.POST.get('longitude', '').strip()
            ket  = request.POST.get('keterangan', '').strip()
            if nama:
                site.nama       = nama
                site.latitude   = float(lat) if lat else None
                site.longitude  = float(lng) if lng else None
                site.keterangan = ket
                site.save()

        elif action == 'delete' and pk:
            SiteLocation.objects.filter(pk=pk).delete()

        return redirect('lokasi_admin')

    sites = SiteLocation.objects.all()
    # Hitung berapa device per lokasi
    device_count = {}
    for d in Device.objects.filter(is_deleted=False).values('lokasi'):
        loc = (d['lokasi'] or '').strip().upper()
        device_count[loc] = device_count.get(loc, 0) + 1

    sites_data = []
    for s in sites:
        sites_data.append({
            'site':         s,
            'device_count': device_count.get(s.nama.upper(), 0),
        })

    return render(request, 'devices/lokasi_admin.html', {
        'sites_data': sites_data,
    })


def api_lokasi_list(request):
    """API: kembalikan daftar lokasi sebagai JSON untuk validasi form."""
    from devices.models import SiteLocation
    locs = list(SiteLocation.objects.values_list('nama', flat=True).order_by('nama'))
    return JsonResponse({'lokasi': locs})


# ── Public Device Page (QR Code) ─────────────────────────────────────────────

def device_public(request, token):
    """Halaman publik perangkat via QR Code — tidak perlu login."""
    device = get_object_or_404(Device, public_token=token, is_deleted=False)

    # Maintenance history ringkas (10 terakhir)
    from maintenance.models import Maintenance
    maintenance_history = (
        Maintenance.objects
        .filter(device=device)
        .order_by('-date')[:10]
    )

    # Gangguan — aktif + 5 terakhir selesai
    from gangguan.models import Gangguan
    gangguan_aktif = Gangguan.objects.filter(
        peralatan=device, status__in=['open', 'in_progress']
    ).order_by('-tanggal_gangguan')
    gangguan_selesai = Gangguan.objects.filter(
        peralatan=device, status__in=['resolved', 'closed']
    ).order_by('-tanggal_gangguan')[:5]

    # Health Index
    try:
        from health_index.calculator import calculate_hi
        health_index = calculate_hi(device, save_snapshot=False)
    except Exception:
        health_index = None

    # Umur peralatan
    from datetime import date as date_type
    umur = None
    if device.tahun_operasi:
        umur = date_type.today().year - device.tahun_operasi

    # ── Inspeksi terakhir ─────────────────────────────────────────
    last_inspection  = None
    can_inspect      = False
    inspection_url   = None
    INSPECTABLE = ['Catu Daya', 'RELE DEFENSE SCHEME', 'MASTER TRIP', 'UFLS']

    jenis_name = device.jenis.name if device.jenis else ''
    if jenis_name in INSPECTABLE:
        can_inspect = True
        inspection_url = f'/inspection/form/{device.pk}/'
        try:
            from inspection.models import Inspection
            last_inspection = (
                Inspection.objects
                .filter(device=device)
                .select_related('operator')
                .order_by('-tanggal')
                .first()
            )
        except Exception:
            pass

    return render(request, 'devices/device_public.html', {
        'device':             device,
        'maintenance_history': maintenance_history,
        'gangguan_aktif':     gangguan_aktif,
        'gangguan_selesai':   gangguan_selesai,
        'health_index':       health_index,
        'umur':               umur,
        'now':                now(),
        'last_inspection':    last_inspection,
        'can_inspect':        can_inspect,
        'inspection_url':     inspection_url,
    })


# ── Peta Jaringan ─────────────────────────────────────────────────────────────

@login_required
def peta_jaringan(request):
    """Halaman peta jaringan — marker per site diwarnai berdasarkan HI rata-rata."""
    site_locations = SiteLocation.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).order_by('nama')

    all_lokasi = (
        Device.objects
        .filter(is_deleted=False)
        .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
        .values_list('lokasi', flat=True)
        .distinct()
    )
    total_lokasi    = all_lokasi.count()
    total_berkoord  = site_locations.count()
    total_tanpa     = total_lokasi - total_berkoord

    return render(request, 'devices/peta_jaringan.html', {
        'total_lokasi':   total_lokasi,
        'total_berkoord': total_berkoord,
        'total_tanpa':    total_tanpa,
    })


@login_required
def api_peta_jaringan(request):
    """
    API JSON untuk peta jaringan.
    Kembalikan semua site yang punya koordinat beserta:
    - Daftar device + skor HI masing-masing
    - Skor HI rata-rata site (untuk warna marker)
    - Jumlah gangguan aktif dan maintenance open
    """
    from health_index.calculator import calculate_hi, get_kategori
    from gangguan.models import Gangguan
    from maintenance.models import Maintenance

    site_locations = SiteLocation.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).order_by('nama')

    gangguan_per_lokasi = {}
    for g in Gangguan.objects.filter(status__in=['open', 'in_progress']).select_related('peralatan'):
        if g.peralatan:
            lok = (g.peralatan.lokasi or '').strip()
            gangguan_per_lokasi[lok] = gangguan_per_lokasi.get(lok, 0) + 1

    maint_per_lokasi = {}
    for m in Maintenance.objects.filter(status='Open').select_related('device'):
        lok = (m.device.lokasi or '').strip()
        maint_per_lokasi[lok] = maint_per_lokasi.get(lok, 0) + 1

    result = []
    for sl in site_locations:
        devices = Device.objects.filter(
            is_deleted=False, lokasi__iexact=sl.nama
        ).select_related('jenis').order_by('jenis__name', 'nama')

        device_list = []
        scores = []
        for dev in devices:
            try:
                hi = calculate_hi(dev, save_snapshot=False)
                score = hi['score']
                kat   = hi['kategori']
            except Exception:
                score = None
                kat   = None

            scores.append(score)
            device_list.append({
                'id':        dev.pk,
                'nama':      dev.nama,
                'jenis':     dev.jenis.name if dev.jenis else '\u2014',
                'merk':      dev.merk or '',
                'type':      dev.type or '',
                'ip':        str(dev.ip_address) if dev.ip_address else '',
                'status':    dev.status_operasi,
                'hi_score':  score,
                'hi_label':  kat['label']  if kat else '\u2014',
                'hi_accent': kat['accent'] if kat else '#94a3b8',
                'hi_icon':   kat['icon']   if kat else 'bi-circle',
                'url':       f'/view/{dev.pk}/',
                'hi_url':    f'/health-index/{dev.pk}/',
            })

        valid_scores = [s for s in scores if s is not None]
        avg_score = round(sum(valid_scores) / len(valid_scores)) if valid_scores else None
        site_kat  = get_kategori(avg_score) if avg_score is not None else None

        result.append({
            'nama':           sl.nama,
            'lat':            sl.latitude,
            'lng':            sl.longitude,
            'keterangan':     sl.keterangan or '',
            'total_device':   len(device_list),
            'hi_avg':         avg_score,
            'hi_label':       site_kat['label']  if site_kat else '\u2014',
            'hi_accent':      site_kat['accent'] if site_kat else '#94a3b8',
            'hi_bg':          site_kat['bg']     if site_kat else '#f1f5f9',
            'gangguan_aktif': gangguan_per_lokasi.get(sl.nama, 0),
            'maint_open':     maint_per_lokasi.get(sl.nama, 0),
            'devices':        device_list,
        })

    return JsonResponse({'sites': result})


# ─────────────────────────────────────────────────────────────────────
# EVIDEN TAMBAHAN PERANGKAT
# ─────────────────────────────────────────────────────────────────────
@login_required
@require_can_edit
def device_eviden_add(request, pk):
    """Upload satu atau lebih foto eviden untuk perangkat."""
    device = get_object_or_404(Device, pk=pk)
    if request.method == 'POST':
        from devices.models import DeviceEviden
        fotos = request.FILES.getlist('eviden_foto')
        keterangans = request.POST.getlist('eviden_keterangan')
        for i, foto in enumerate(fotos):
            if not foto:
                continue
            ket = keterangans[i] if i < len(keterangans) else ''
            DeviceEviden.objects.create(
                device      = device,
                foto        = foto,
                keterangan  = ket.strip(),
                uploaded_by = request.user,
            )
    return redirect('device_view', pk=pk)


@login_required
@require_can_delete
def device_eviden_delete(request, pk, eviden_pk):
    """Hapus satu eviden."""
    device = get_object_or_404(Device, pk=pk)
    from devices.models import DeviceEviden
    eviden = get_object_or_404(DeviceEviden, pk=eviden_pk, device=device)
    # Hapus file fisik
    if eviden.foto:
        try:
            import os
            if os.path.isfile(eviden.foto.path):
                os.remove(eviden.foto.path)
        except Exception:
            pass
    eviden.delete()
    return redirect('device_view', pk=pk)
