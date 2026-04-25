import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from .models import CommonEnemy, CommonEnemyLog
from .forms import CommonEnemyForm, CommonEnemyLogForm
from devices.models import Device, DeviceType
from devices.permissions import require_can_delete, require_can_edit, is_viewer_only


def _get_device_json():
    """Semua device aktif sebagai JSON untuk JS filter."""
    devices = (
        Device.objects.filter(is_deleted=False)
        .select_related('jenis')
        .order_by('jenis__name', 'lokasi', 'nama')
        .values('id', 'nama', 'lokasi', 'jenis__id', 'jenis__name')
    )
    device_list = [
        {
            'id':        d['id'],
            'nama':      d['nama'],
            'lokasi':    d['lokasi'] or '',
            'jenis_id':  d['jenis__id'] or 0,
            'jenis_nama': d['jenis__name'] or 'Lainnya',
        }
        for d in devices
    ]
    types = DeviceType.objects.all().order_by('name').values('id', 'name')
    type_list = [{'id': t['id'], 'name': t['name']} for t in types]
    return json.dumps(device_list), json.dumps(type_list)


@login_required
def ce_list(request):
    qs = CommonEnemy.objects.select_related('created_by', 'peralatan', 'sub_kategori')

    status_filter   = request.GET.get('status', '').strip()
    kategori_filter = request.GET.get('kategori', '').strip()
    severity_filter = request.GET.get('severity', '').strip()
    sumber_filter   = request.GET.get('sumber', '').strip()
    site_filter     = request.GET.get('site', '').strip()
    search          = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if kategori_filter:
        qs = qs.filter(kategori=kategori_filter)
    if severity_filter:
        qs = qs.filter(tingkat_keparahan=severity_filter)
    if sumber_filter:
        qs = qs.filter(sumber_laporan=sumber_filter)
    if site_filter:
        qs = qs.filter(site__icontains=site_filter)
    if search:
        qs = qs.filter(
            Q(nomor_ce__icontains=search) |
            Q(site__icontains=search) |
            Q(deskripsi_masalah__icontains=search)
        )

    stats = {
        'total':       CommonEnemy.objects.count(),
        'open':        CommonEnemy.objects.filter(status='open').count(),
        'in_progress': CommonEnemy.objects.filter(status='in_progress').count(),
        'resolved':    CommonEnemy.objects.filter(status='resolved').count(),
        'closed':      CommonEnemy.objects.filter(status='closed').count(),
    }

    site_list = (
        CommonEnemy.objects.values_list('site', flat=True)
        .distinct().order_by('site')
    )

    return render(request, 'common_enemy/ce_list.html', {
        'ce_list':        qs,
        'stats':           stats,
        'site_list':       site_list,
        'status_filter':   status_filter,
        'kategori_filter': kategori_filter,
        'severity_filter': severity_filter,
        'sumber_filter':   sumber_filter,
        'site_filter':     site_filter,
        'search':          search,
        'STATUS_CHOICES':   CommonEnemy.STATUS_CHOICES,
        'KATEGORI_CHOICES': CommonEnemy.KATEGORI_CHOICES,
        'SEVERITY_CHOICES': CommonEnemy.SEVERITY_CHOICES,
        'SUMBER_CHOICES':   CommonEnemy.SUMBER_CHOICES,
    })


@login_required
@require_can_edit
def ce_create(request):
    device_json, type_json = _get_device_json()
    site_list = (
        CommonEnemy.objects.values_list('site', flat=True)
        .distinct().order_by('site')
    )

    if request.method == 'POST':
        form = CommonEnemyForm(request.POST, request.FILES)
        if form.is_valid():
            ce = form.save(commit=False)
            ce.created_by = request.user
            raw = request.POST.get('pelaksana_names_input', '[]')
            try:
                ce.pelaksana_names = json.loads(raw)
            except (ValueError, TypeError):
                ce.pelaksana_names = []
            ce.save()
            return redirect('ce_detail', pk=ce.pk)
    else:
        form = CommonEnemyForm(initial={'tanggal_laporan': timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')})

    return render(request, 'common_enemy/ce_form.html', {
        'form':        form,
        'is_edit':     False,
        'site_list':   site_list,
        'device_json': device_json,
        'type_json':   type_json,
    })


@login_required
def ce_detail(request, pk):
    ce = get_object_or_404(CommonEnemy, pk=pk)
    log_entries = ce.log_entries.select_related('dibuat_oleh').order_by('waktu_aksi')
    log_form = CommonEnemyLogForm(initial={
        'waktu_aksi': timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
    })
    return render(request, 'common_enemy/ce_detail.html', {
        'ce':            ce,
        'log_entries':   log_entries,
        'log_form':      log_form,
        'user_can_edit': not is_viewer_only(request.user),
    })


@login_required
@require_can_edit
def ce_update(request, pk):
    ce = get_object_or_404(CommonEnemy, pk=pk)
    if ce.status == 'closed':
        return redirect('ce_detail', pk=pk)

    device_json, type_json = _get_device_json()
    site_list = (
        CommonEnemy.objects.values_list('site', flat=True)
        .distinct().order_by('site')
    )

    if request.method == 'POST':
        form = CommonEnemyForm(request.POST, request.FILES, instance=ce)
        if form.is_valid():
            ce = form.save(commit=False)
            raw = request.POST.get('pelaksana_names_input', '[]')
            try:
                ce.pelaksana_names = json.loads(raw)
            except (ValueError, TypeError):
                pass
            ce.save()
            return redirect('ce_detail', pk=ce.pk)
    else:
        form = CommonEnemyForm(instance=ce)

    return render(request, 'common_enemy/ce_form.html', {
        'form':        form,
        'ce':          ce,
        'is_edit':     True,
        'site_list':   site_list,
        'device_json': device_json,
        'type_json':   type_json,
    })


@login_required
@require_can_edit
def ce_update_status(request, pk):
    if request.method != 'POST':
        return redirect('ce_detail', pk=pk)

    ce = get_object_or_404(CommonEnemy, pk=pk)
    new_status = request.POST.get('status', '').strip()
    valid_statuses = [s[0] for s in CommonEnemy.STATUS_CHOICES]

    if new_status in valid_statuses:
        ce.status = new_status
        catatan = request.POST.get('catatan_penutupan', '').strip()
        if catatan:
            ce.catatan_penutupan = catatan
        resolved_str = request.POST.get('tanggal_resolved', '').strip()
        if resolved_str and new_status in ('resolved', 'closed'):
            try:
                from django.utils.dateparse import parse_datetime
                import pytz
                dt = parse_datetime(resolved_str)
                if dt and timezone.is_naive(dt):
                    tz = timezone.get_current_timezone()
                    dt = timezone.make_aware(dt, tz)
                if dt:
                    ce.tanggal_resolved = dt
            except Exception:
                pass
        ce.save()

    return redirect('ce_detail', pk=pk)


@login_required
@require_can_edit
def ce_add_log(request, pk):
    ce = get_object_or_404(CommonEnemy, pk=pk)
    if request.method == 'POST':
        form = CommonEnemyLogForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.common_enemy = ce
            log.dibuat_oleh  = request.user
            log.save()
    return redirect('ce_detail', pk=pk)


@login_required
@require_can_delete
def ce_delete_log(request, pk, log_pk):
    if request.method == 'POST':
        log = get_object_or_404(CommonEnemyLog, pk=log_pk, common_enemy__pk=pk)
        log.delete()
    return redirect('ce_detail', pk=pk)
