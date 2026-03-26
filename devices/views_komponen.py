# devices/views_komponen.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from devices.permissions import require_can_edit, require_can_delete
from devices.models import Device
from devices.models_komponen import DeviceComponent, TipeKomponen, GrupTipeKomponen


def _get_tipe_grouped():
    """Ambil tipe komponen grouped untuk template dropdown."""
    grups = GrupTipeKomponen.objects.prefetch_related('tipe_komponen').order_by('urutan', 'nama')
    result = []
    for g in grups:
        tipes = g.tipe_komponen.order_by('urutan', 'nama')
        if tipes.exists():
            result.append({'grup': g.nama, 'tipes': list(tipes)})
    tanpa_grup = TipeKomponen.objects.filter(grup__isnull=True).order_by('urutan', 'nama')
    if tanpa_grup.exists():
        result.append({'grup': 'Lainnya', 'tipes': list(tanpa_grup)})
    return result


def _resolve_tipe(value):
    """Resolve tipe_komponen dari POST — bisa id atau kode."""
    if not value:
        return None
    try:
        return TipeKomponen.objects.get(pk=int(value))
    except (ValueError, TipeKomponen.DoesNotExist):
        pass
    try:
        return TipeKomponen.objects.get(kode=value)
    except TipeKomponen.DoesNotExist:
        return None


@login_required
@require_can_edit
def komponen_add(request, device_pk):
    device = get_object_or_404(Device, pk=device_pk)
    if request.method == 'POST':
        parent_id = request.POST.get('parent') or None
        tipe = _resolve_tipe(request.POST.get('tipe_komponen'))
        komponen = DeviceComponent(
            device=device, parent_id=parent_id,
            nama=request.POST.get('nama', '').strip(),
            tipe_komponen=tipe,
            posisi=request.POST.get('posisi', '').strip(),
            merk=request.POST.get('merk', '').strip(),
            model=request.POST.get('model', '').strip(),
            serial_number=request.POST.get('serial_number', '').strip(),
            status=request.POST.get('status', 'terpasang'),
            keterangan=request.POST.get('keterangan', '').strip(),
            created_by=request.user,
        )
        tp = request.POST.get('tanggal_pasang')
        tg = request.POST.get('tanggal_ganti')
        if tp: komponen.tanggal_pasang = tp
        if tg: komponen.tanggal_ganti = tg
        komponen.save()
    return redirect('device_view', pk=device_pk)


@login_required
@require_can_edit
def komponen_edit(request, device_pk, komponen_pk):
    device = get_object_or_404(Device, pk=device_pk)
    komponen = get_object_or_404(DeviceComponent, pk=komponen_pk, device=device)
    if request.method == 'POST':
        komponen.nama = request.POST.get('nama', '').strip()
        komponen.tipe_komponen = _resolve_tipe(request.POST.get('tipe_komponen'))
        komponen.posisi = request.POST.get('posisi', '').strip()
        komponen.merk = request.POST.get('merk', '').strip()
        komponen.model = request.POST.get('model', '').strip()
        komponen.serial_number = request.POST.get('serial_number', '').strip()
        komponen.status = request.POST.get('status', 'terpasang')
        komponen.keterangan = request.POST.get('keterangan', '').strip()
        komponen.parent_id = request.POST.get('parent') or None
        tp = request.POST.get('tanggal_pasang')
        tg = request.POST.get('tanggal_ganti')
        komponen.tanggal_pasang = tp if tp else None
        komponen.tanggal_ganti = tg if tg else None
        komponen.save()
        return redirect('device_view', pk=device_pk)

    komponen_siblings = DeviceComponent.objects.filter(device=device).exclude(pk=komponen.pk).order_by('posisi', 'nama')
    return render(request, 'devices/komponen_edit.html', {
        'device': device, 'komponen': komponen,
        'komponen_siblings': komponen_siblings,
        'tipe_grouped': _get_tipe_grouped(),
    })


@login_required
@require_can_delete
def komponen_delete(request, device_pk, komponen_pk):
    device = get_object_or_404(Device, pk=device_pk)
    komponen = get_object_or_404(DeviceComponent, pk=komponen_pk, device=device)
    if request.method == 'POST':
        komponen.delete()
    return redirect('device_view', pk=device_pk)


def get_komponen_for_device(device):
    return (
        DeviceComponent.objects
        .filter(device=device, parent__isnull=True)
        .select_related('parent', 'tipe_komponen')
        .prefetch_related('sub_komponen', 'sub_komponen__tipe_komponen')
        .order_by('posisi', 'nama')
    )


@login_required
def api_komponen_by_device(request, device_pk):
    from django.http import JsonResponse
    komponen = DeviceComponent.objects.filter(device_id=device_pk).select_related('tipe_komponen').order_by('posisi', 'nama')
    data = []
    for k in komponen:
        label = k.nama
        if k.posisi: label += f" [{k.posisi}]"
        data.append({'id': k.id, 'label': label, 'tipe': k.tipe_display, 'status': k.status})
    return JsonResponse(data, safe=False)


def get_tipe_grouped_json():
    """Tipe komponen sebagai JSON untuk JS dropdown."""
    import json
    return json.dumps([
        {'group': g['grup'], 'items': [{'id': t.pk, 'kode': t.kode, 'nama': t.nama} for t in g['tipes']]}
        for g in _get_tipe_grouped()
    ])
