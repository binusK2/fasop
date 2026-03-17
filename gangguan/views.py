from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from .models import Gangguan, GangguanLog
from .forms import GangguanForm, GangguanLogForm
from devices.models import Device


@login_required
def gangguan_list(request):
    """History gangguan — tampilan ticketing."""
    qs = Gangguan.objects.select_related('created_by', 'peralatan')

    # Filter
    status_filter   = request.GET.get('status', '').strip()
    kategori_filter = request.GET.get('kategori', '').strip()
    severity_filter = request.GET.get('severity', '').strip()
    site_filter     = request.GET.get('site', '').strip()
    search          = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if kategori_filter:
        qs = qs.filter(kategori=kategori_filter)
    if severity_filter:
        qs = qs.filter(tingkat_keparahan=severity_filter)
    if site_filter:
        qs = qs.filter(site__icontains=site_filter)
    if search:
        qs = qs.filter(
            Q(nomor_gangguan__icontains=search) |
            Q(site__icontains=search) |
            Q(executive_summary__icontains=search) |
            Q(indikasi_gangguan__icontains=search)
        )

    # Statistik ringkas
    stats = {
        'total':       Gangguan.objects.count(),
        'open':        Gangguan.objects.filter(status='open').count(),
        'in_progress': Gangguan.objects.filter(status='in_progress').count(),
        'resolved':    Gangguan.objects.filter(status='resolved').count(),
        'closed':      Gangguan.objects.filter(status='closed').count(),
    }

    # Unique site list untuk filter dropdown
    site_list = (
        Gangguan.objects.values_list('site', flat=True)
        .distinct().order_by('site')
    )

    return render(request, 'gangguan/gangguan_list.html', {
        'gangguan_list': qs,
        'stats':          stats,
        'site_list':      site_list,
        'status_filter':  status_filter,
        'kategori_filter':kategori_filter,
        'severity_filter':severity_filter,
        'site_filter':    site_filter,
        'search':         search,
        'STATUS_CHOICES':  Gangguan.STATUS_CHOICES,
        'KATEGORI_CHOICES':Gangguan.KATEGORI_CHOICES,
        'SEVERITY_CHOICES':Gangguan.SEVERITY_CHOICES,
    })


def _get_device_json():
    """Kembalikan semua device aktif sebagai list dict untuk JS filter."""
    import json
    from devices.models import DeviceType
    devices = (
        Device.objects.filter(is_deleted=False)
        .select_related('jenis')
        .order_by('jenis__name', 'lokasi', 'nama')
        .values('id', 'nama', 'lokasi', 'jenis__id', 'jenis__name')
    )
    device_list = [
        {
            'id':    d['id'],
            'nama':  d['nama'],
            'lokasi': d['lokasi'] or '',
            'jenis_id':   d['jenis__id'] or 0,
            'jenis_nama': d['jenis__name'] or 'Lainnya',
        }
        for d in devices
    ]
    types = (
        DeviceType.objects.all().order_by('name').values('id', 'name')
    )
    type_list = [{'id': t['id'], 'name': t['name']} for t in types]
    return json.dumps(device_list), json.dumps(type_list)


@login_required
def gangguan_create(request):
    """Deklarasi gangguan baru."""
    if request.method == 'POST':
        form = GangguanForm(request.POST, request.FILES)
        if form.is_valid():
            gangguan = form.save(commit=False)
            gangguan.created_by = request.user
            gangguan.save()
            return redirect('gangguan_detail', pk=gangguan.pk)
    else:
        form = GangguanForm(initial={'tanggal_gangguan': timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')})

    site_list = list(
        Device.objects.filter(is_deleted=False)
        .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
        .values_list('lokasi', flat=True)
        .distinct().order_by('lokasi')
    )
    device_json, type_json = _get_device_json()

    return render(request, 'gangguan/gangguan_form.html', {
        'form':        form,
        'is_edit':     False,
        'site_list':   site_list,
        'device_json': device_json,
        'type_json':   type_json,
        'selected_peralatan_id': None,
    })


@login_required
def gangguan_detail(request, pk):
    """Detail laporan gangguan."""
    gangguan = get_object_or_404(Gangguan, pk=pk)
    log_entries = gangguan.log_entries.select_related('dibuat_oleh').order_by('waktu_aksi')
    log_form = GangguanLogForm(initial={
        'waktu_aksi': timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
    })
    return render(request, 'gangguan/gangguan_detail.html', {
        'gangguan':    gangguan,
        'log_entries': log_entries,
        'log_form':    log_form,
    })


@login_required
def gangguan_update(request, pk):
    """Edit / update laporan gangguan."""
    gangguan = get_object_or_404(Gangguan, pk=pk)
    # Tiket closed tidak bisa diedit
    if gangguan.status == 'closed':
        return redirect('gangguan_detail', pk=pk)
    if request.method == 'POST':
        form = GangguanForm(request.POST, request.FILES, instance=gangguan)
        if form.is_valid():
            form.save()
            return redirect('gangguan_detail', pk=gangguan.pk)
    else:
        form = GangguanForm(instance=gangguan)

    site_list = list(
        Device.objects.filter(is_deleted=False)
        .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
        .values_list('lokasi', flat=True)
        .distinct().order_by('lokasi')
    )
    device_json, type_json = _get_device_json()

    return render(request, 'gangguan/gangguan_form.html', {
        'form':        form,
        'gangguan':    gangguan,
        'is_edit':     True,
        'site_list':   site_list,
        'device_json': device_json,
        'type_json':   type_json,
        'selected_peralatan_id': gangguan.peralatan_id or '',
    })


@login_required
def gangguan_update_status(request, pk):
    """Quick update status via POST."""
    gangguan = get_object_or_404(Gangguan, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Gangguan.STATUS_CHOICES):
            gangguan.status = new_status
            catatan = request.POST.get('catatan_penutupan', '').strip()
            if catatan:
                gangguan.catatan_penutupan = catatan
            gangguan.save()
    return redirect('gangguan_detail', pk=pk)


@login_required
def gangguan_add_log(request, pk):
    """Tambah entri log tindak lanjut."""
    gangguan = get_object_or_404(Gangguan, pk=pk)
    if request.method == 'POST':
        form = GangguanLogForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.gangguan    = gangguan
            log.dibuat_oleh = request.user
            log.save()
    return redirect('gangguan_detail', pk=pk)


@login_required
def gangguan_delete_log(request, pk, log_pk):
    """Hapus entri log tindak lanjut."""
    log = get_object_or_404(GangguanLog, pk=log_pk, gangguan__pk=pk)
    if request.method == 'POST':
        log.delete()
    return redirect('gangguan_detail', pk=pk)
