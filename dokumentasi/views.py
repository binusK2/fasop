import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from .models import SettingRele, GambarDevice
from .forms import SettingReleForm, GambarDeviceForm
from devices.models import Device
from devices.permissions import require_can_edit, is_viewer_only


def _get_device_json(prosis_only=False):
    qs = Device.objects.filter(is_deleted=False).select_related('jenis').order_by('lokasi', 'nama')
    if prosis_only:
        qs = qs.filter(
            jenis__name__iregex=r'^(defense scheme|rele defense scheme|master trip|ufls)$'
        )
    return json.dumps([
        {
            'id':            d.id,
            'nama':          d.nama,
            'lokasi':        d.lokasi or '',
            'jenis':         d.jenis.name if d.jenis else '',
            'merk':          d.merk or '',
            'type':          d.type or '',
            'serial_number': d.serial_number or '',
            'ip_address':    str(d.ip_address) if d.ip_address else '',
        }
        for d in qs
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
    device_json = _get_device_json(prosis_only=True)
    if request.method == 'POST':
        form = SettingReleForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.status = 'draft'
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
    user = request.user
    user_is_checker  = (obj.checker_id == user.pk) or user.is_superuser
    user_is_uploader = (obj.created_by_id == user.pk) or user.is_superuser
    return render(request, 'dokumentasi/setting_detail.html', {
        'obj':             obj,
        'user_can_edit':   not is_viewer_only(user),
        'user_is_checker': user_is_checker,
        'user_is_uploader': user_is_uploader,
    })


@login_required
@require_can_edit
def setting_submit(request, pk):
    """Uploader kirim dokumen ke checker: draft/perlu_perbaikan → on_check (AJAX POST)."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    obj = get_object_or_404(SettingRele, pk=pk)
    if obj.status not in ('draft', 'perlu_perbaikan'):
        return JsonResponse({'ok': False, 'error': 'Status tidak valid untuk dikirim'}, status=400)
    if not obj.checker_id:
        return JsonResponse({'ok': False, 'error': 'Checker belum ditentukan — edit dokumen dulu'}, status=400)
    if obj.status == 'perlu_perbaikan':
        try:
            obj.versi = f'{int(obj.versi) + 1:04d}'
        except (ValueError, TypeError):
            obj.versi = '0002'
    obj.status = 'on_check'
    obj.catatan_perbaikan = ''
    obj.save()
    return JsonResponse({'ok': True, 'status': 'on_check', 'versi': obj.versi})


@login_required
@require_can_edit
def setting_verify(request, pk):
    """Checker setujui — on_check → uptodate (AJAX POST)."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    obj = get_object_or_404(SettingRele, pk=pk)
    if request.user.pk != obj.checker_id and not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': 'Bukan checker dokumen ini'}, status=403)
    if obj.status != 'on_check':
        return JsonResponse({'ok': False, 'error': 'Dokumen belum dikirim untuk dicek'}, status=400)
    obj.status = 'uptodate'
    obj.tanggal_cek = timezone.localdate()
    obj.catatan_perbaikan = ''
    obj.save()
    return JsonResponse({'ok': True, 'status': 'uptodate',
                         'tanggal_cek': obj.tanggal_cek.strftime('%d %b %Y')})


@login_required
@require_can_edit
def setting_revisi(request, pk):
    """Checker kembalikan dengan catatan: on_check → perlu_perbaikan (AJAX POST)."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    obj = get_object_or_404(SettingRele, pk=pk)
    if request.user.pk != obj.checker_id and not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': 'Bukan checker dokumen ini'}, status=403)
    catatan = request.POST.get('catatan', '').strip()
    if not catatan:
        return JsonResponse({'ok': False, 'error': 'Catatan perbaikan wajib diisi'}, status=400)
    obj.status = 'perlu_perbaikan'
    obj.catatan_perbaikan = catatan
    obj.tanggal_cek = None
    obj.save()
    return JsonResponse({'ok': True, 'status': 'perlu_perbaikan', 'catatan': catatan})


@login_required
@require_can_edit
def setting_update(request, pk):
    obj = get_object_or_404(SettingRele, pk=pk)
    device_json = _get_device_json(prosis_only=True)
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
