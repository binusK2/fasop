import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from .models import SettingRele, GambarDevice
from .forms import SettingReleForm, GambarDeviceForm
from devices.models import Device
from devices.permissions import require_can_edit, is_viewer_only


def _get_device_json():
    devices = (
        Device.objects.filter(is_deleted=False)
        .select_related('jenis')
        .order_by('lokasi', 'nama')
        .values('id', 'nama', 'lokasi', 'jenis__name')
    )
    return json.dumps([
        {
            'id':       d['id'],
            'nama':     d['nama'],
            'lokasi':   d['lokasi'] or '',
            'jenis':    d['jenis__name'] or '',
        }
        for d in devices
    ])


# ── Setting Rele ─────────────────────────────────────────────────────────────

@login_required
def setting_list(request):
    qs = SettingRele.objects.select_related('device', 'device__jenis', 'checker', 'created_by')

    status_filter = request.GET.get('status', '').strip()
    search        = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if search:
        qs = qs.filter(
            Q(nomor__icontains=search) |
            Q(judul__icontains=search) |
            Q(device__nama__icontains=search) |
            Q(device__lokasi__icontains=search)
        )

    total   = SettingRele.objects.count()
    n_draft   = SettingRele.objects.filter(status='draft').count()
    n_checked = SettingRele.objects.filter(status='checked').count()

    return render(request, 'dokumentasi/setting_list.html', {
        'object_list':    qs,
        'status_filter':  status_filter,
        'search':         search,
        'stats': {'total': total, 'draft': n_draft, 'checked': n_checked},
        'STATUS_CHOICES': SettingRele.STATUS_CHOICES,
        'user_can_edit':  not is_viewer_only(request.user),
    })


@login_required
@require_can_edit
def setting_create(request):
    device_json = _get_device_json()
    if request.method == 'POST':
        form = SettingReleForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            return redirect('setting_rele_detail', pk=obj.pk)
    else:
        form = SettingReleForm(initial={'tanggal': timezone.localdate()})

    return render(request, 'dokumentasi/setting_form.html', {
        'form':        form,
        'is_edit':     False,
        'device_json': device_json,
    })


@login_required
def setting_detail(request, pk):
    obj = get_object_or_404(SettingRele, pk=pk)
    return render(request, 'dokumentasi/setting_detail.html', {
        'obj':          obj,
        'user_can_edit': not is_viewer_only(request.user),
    })


@login_required
@require_can_edit
def setting_update(request, pk):
    obj = get_object_or_404(SettingRele, pk=pk)
    device_json = _get_device_json()
    if request.method == 'POST':
        form = SettingReleForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            return redirect('setting_rele_detail', pk=obj.pk)
    else:
        form = SettingReleForm(instance=obj)

    return render(request, 'dokumentasi/setting_form.html', {
        'form':        form,
        'obj':         obj,
        'is_edit':     True,
        'device_json': device_json,
    })


# ── Gambar Device ─────────────────────────────────────────────────────────────

@login_required
def gambar_list(request):
    qs = GambarDevice.objects.select_related('device', 'device__jenis', 'checker', 'created_by')

    tipe_filter   = request.GET.get('tipe', '').strip()
    search        = request.GET.get('q', '').strip()

    if tipe_filter:
        qs = qs.filter(tipe=tipe_filter)
    if search:
        qs = qs.filter(
            Q(nomor__icontains=search) |
            Q(judul__icontains=search) |
            Q(device__nama__icontains=search) |
            Q(device__lokasi__icontains=search)
        )

    total = GambarDevice.objects.count()

    from .models import TIPE_GAMBAR_CHOICES
    return render(request, 'dokumentasi/gambar_list.html', {
        'object_list':   qs,
        'tipe_filter':   tipe_filter,
        'search':        search,
        'stats':         {'total': total},
        'TIPE_CHOICES':  TIPE_GAMBAR_CHOICES,
        'user_can_edit': not is_viewer_only(request.user),
    })


@login_required
@require_can_edit
def gambar_create(request):
    device_json = _get_device_json()
    if request.method == 'POST':
        form = GambarDeviceForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            return redirect('gambar_rele_detail', pk=obj.pk)
    else:
        form = GambarDeviceForm(initial={'tanggal': timezone.localdate()})

    return render(request, 'dokumentasi/gambar_form.html', {
        'form':        form,
        'is_edit':     False,
        'device_json': device_json,
    })


@login_required
def gambar_detail(request, pk):
    obj = get_object_or_404(GambarDevice, pk=pk)
    return render(request, 'dokumentasi/gambar_detail.html', {
        'obj':          obj,
        'user_can_edit': not is_viewer_only(request.user),
    })


@login_required
@require_can_edit
def gambar_update(request, pk):
    obj = get_object_or_404(GambarDevice, pk=pk)
    device_json = _get_device_json()
    if request.method == 'POST':
        form = GambarDeviceForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            return redirect('gambar_rele_detail', pk=obj.pk)
    else:
        form = GambarDeviceForm(instance=obj)

    return render(request, 'dokumentasi/gambar_form.html', {
        'form':        form,
        'obj':         obj,
        'is_edit':     True,
        'device_json': device_json,
    })
