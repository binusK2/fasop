from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from .models import Gangguan, GangguanLog
from .forms import GangguanForm, GangguanLogForm
from devices.models import Device
from devices.permissions import require_can_delete, require_can_edit, is_viewer_only


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


def _get_icon_json():
    """Semua layanan ICON+ sebagai JSON untuk JS autocomplete di form gangguan."""
    import json
    from devices.models import Icon
    icons = Icon.objects.all().order_by('name').values(
        'id', 'name', 'nama_layanan', 'lokasi_layanan',
        'bandwidth', 'SID1', 'SID2', 'kontrak', 'kondisi_operasional',
    )
    return json.dumps([
        {
            'id':          ic['id'],
            'name':        ic['name'],
            'nama_layanan':ic['nama_layanan'] or '',
            'lokasi':      ic['lokasi_layanan'] or '',
            'bandwidth':   ic['bandwidth'] or '',
            'SID1':        ic['SID1'] or '',
            'SID2':        ic['SID2'] or '',
            'kontrak':     ic['kontrak'] or '',
            'kondisi':     ic['kondisi_operasional'] or '',
        }
        for ic in icons
    ])


@login_required
@require_can_edit
def gangguan_create(request):
    """Deklarasi gangguan baru."""
    if request.method == 'POST':
        form = GangguanForm(request.POST, request.FILES)
        if form.is_valid():
            gangguan = form.save(commit=False)
            gangguan.created_by = request.user
            # Simpan pelaksana dari tag-input JS
            import json as _json
            names_raw = request.POST.get('pelaksana_names_input', '[]')
            try:
                gangguan.pelaksana_names = _json.loads(names_raw)
            except Exception:
                gangguan.pelaksana_names = []
            gangguan.save()
            # Notif ke AM — gangguan baru
            try:
                from notifikasi.views import notif_ke_am
                notif_ke_am(
                    tipe   = 'gangguan_baru',
                    judul  = f'Gangguan baru — {gangguan.site}',
                    pesan  = (
                        f'Tiket {gangguan.nomor_gangguan} dibuat oleh '
                        f'{request.user.get_full_name() or request.user.username}. '
                        f'Severity: {gangguan.get_tingkat_keparahan_display()}. '
                        f'{gangguan.executive_summary[:100]}'
                    ),
                    level  = 'danger' if gangguan.tingkat_keparahan == 'kritis' else 'warning',
                    url    = f'/gangguan/{gangguan.pk}/',
                    device = gangguan.peralatan,
                )
            except Exception:
                pass
            return redirect('gangguan_detail', pk=gangguan.pk)
    else:
        # Nilai default
        initial = {
            'tanggal_gangguan': timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M'),
        }

        # Prefill dari layanan ICON+ jika datang dari tombol "Laporkan Gangguan"
        prefill_icon = None
        icon_id_param = request.GET.get('icon_id', '').strip()
        if icon_id_param:
            try:
                from devices.models import Icon
                prefill_icon = Icon.objects.get(pk=int(icon_id_param))
                if prefill_icon.lokasi_layanan:
                    initial['site'] = prefill_icon.lokasi_layanan
                initial['layanan_icon'] = prefill_icon.pk
            except (Icon.DoesNotExist, ValueError):
                prefill_icon = None

        form = GangguanForm(initial=initial)

    site_list = list(
        Device.objects.filter(is_deleted=False)
        .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
        .values_list('lokasi', flat=True)
        .distinct().order_by('lokasi')
    )
    device_json, type_json = _get_device_json()

    # master_lokasi_list — gabungan lokasi device + lokasi_layanan icon
    # agar lokasi layanan ICON+ juga muncul di autocomplete site
    from devices.models import Icon as _Icon
    icon_lokasi = list(
        _Icon.objects.exclude(lokasi_layanan__isnull=True)
        .exclude(lokasi_layanan__exact='')
        .values_list('lokasi_layanan', flat=True)
        .distinct()
    )
    master_lokasi_list = sorted(set(site_list) | set(icon_lokasi))

    return render(request, 'gangguan/gangguan_form.html', {
        'form':                  form,
        'is_edit':               False,
        'site_list':             site_list,
        'master_lokasi_list':    master_lokasi_list,
        'device_json':           device_json,
        'type_json':             type_json,
        'icon_json':             _get_icon_json(),
        'prefill_icon':          prefill_icon if 'prefill_icon' in dir() else None,
        'prefill_icon_id':       prefill_icon.pk if 'prefill_icon' in dir() and prefill_icon else '',
        'selected_peralatan_id': '',
    })


@login_required
def gangguan_detail(request, pk):
    """Detail laporan gangguan."""
    gangguan    = get_object_or_404(Gangguan, pk=pk)
    log_entries = gangguan.log_entries.select_related('dibuat_oleh').order_by('waktu_aksi')
    log_form    = GangguanLogForm(initial={
        'waktu_aksi': timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
    })

    # Perubahan fisik terhubung
    from devices.models import DeviceEvent, Device
    perubahan_fisik = gangguan.perubahan_fisik.select_related(
        'device', 'device__jenis', 'dilakukan_oleh'
    ).order_by('-tanggal', '-created_at')

    # Daftar device untuk dropdown (prioritaskan device di tiket)
    devices_list = Device.objects.filter(is_deleted=False).select_related('jenis').order_by('lokasi', 'nama')

    from datetime import date as date_type
    return render(request, 'gangguan/gangguan_detail.html', {
        'gangguan':       gangguan,
        'log_entries':    log_entries,
        'log_form':       log_form,
        'perubahan_fisik': perubahan_fisik,
        'devices_list':   devices_list,
        'today_date':     date_type.today().strftime('%Y-%m-%d'),
    })


@login_required
@require_can_edit
def gangguan_update(request, pk):
    """Edit / update laporan gangguan."""
    gangguan = get_object_or_404(Gangguan, pk=pk)
    # Tiket closed tidak bisa diedit
    if gangguan.status == 'closed':
        return redirect('gangguan_detail', pk=pk)
    if request.method == 'POST':
        form = GangguanForm(request.POST, request.FILES, instance=gangguan)
        if form.is_valid():
            import json as _json
            updated = form.save(commit=False)
            names_raw = request.POST.get('pelaksana_names_input', '[]')
            try:
                updated.pelaksana_names = _json.loads(names_raw)
            except Exception:
                updated.pelaksana_names = []
            updated.save()
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

    from devices.models import Icon as _Icon
    icon_lokasi = list(
        _Icon.objects.exclude(lokasi_layanan__isnull=True)
        .exclude(lokasi_layanan__exact='')
        .values_list('lokasi_layanan', flat=True)
        .distinct()
    )
    master_lokasi_list = sorted(set(site_list) | set(icon_lokasi))

    return render(request, 'gangguan/gangguan_form.html', {
        'form':                  form,
        'gangguan':              gangguan,
        'is_edit':               True,
        'site_list':             site_list,
        'master_lokasi_list':    master_lokasi_list,
        'device_json':           device_json,
        'type_json':             type_json,
        'icon_json':             _get_icon_json(),
        'prefill_icon':          None,
        'prefill_icon_id':       '',
        'selected_peralatan_id': gangguan.peralatan_id or '',
    })


@login_required
@require_can_edit
def gangguan_update_status(request, pk):
    """Quick update status via POST."""
    gangguan = get_object_or_404(Gangguan, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Gangguan.STATUS_CHOICES):
            old_status = gangguan.status
            gangguan.status = new_status
            catatan = request.POST.get('catatan_penutupan', '').strip()
            if catatan:
                gangguan.catatan_penutupan = catatan
            gangguan.save()

            # Notif ke AM kalau gangguan resolved/closed
            if old_status not in ('resolved', 'closed') and new_status in ('resolved', 'closed'):
                try:
                    from notifikasi.views import notif_ke_am
                    notif_ke_am(
                        tipe   = 'gangguan_selesai',
                        judul  = f'Gangguan selesai — {gangguan.nomor_gangguan}',
                        pesan  = (
                            f'Tiket {gangguan.nomor_gangguan} ({gangguan.site}) '
                            f'telah di-update ke status {gangguan.get_status_display()} '
                            f'oleh {request.user.get_full_name() or request.user.username}.'
                        ),
                        level  = 'success',
                        url    = f'/gangguan/{gangguan.pk}/',
                        device = gangguan.peralatan,
                    )
                except Exception:
                    pass
    return redirect('gangguan_detail', pk=pk)


@login_required
@require_can_edit
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
@require_can_delete
def gangguan_delete_log(request, pk, log_pk):
    log = get_object_or_404(GangguanLog, pk=log_pk, gangguan__pk=pk)
    if request.method == 'POST':
        log.delete()
    return redirect('gangguan_detail', pk=pk)


@login_required
@require_can_edit
def gangguan_catat_perubahan(request, pk):
    gangguan = get_object_or_404(Gangguan, pk=pk)

    if request.method == 'POST':
        from devices.models import Device, DeviceEvent
        from devices.models_komponen import DeviceComponent

        device_id     = request.POST.get('device_id')
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

        # Device: dari form atau dari gangguan.peralatan
        device = None
        if device_id:
            device = Device.objects.filter(pk=device_id, is_deleted=False).first()
        if not device and gangguan.peralatan:
            device = gangguan.peralatan

        # Resolve komponen_terkait
        komponen_terkait_obj = None
        if komponen_terkait_pk:
            komponen_terkait_obj = DeviceComponent.objects.filter(pk=komponen_terkait_pk).first()

        if device and tipe and tanggal:
            event = DeviceEvent(
                device         = device,
                tipe           = tipe,
                tanggal        = tanggal,
                komponen       = komponen,
                komponen_terkait = komponen_terkait_obj,
                nilai_lama     = nilai_lama,
                nilai_baru     = nilai_baru,
                lokasi_asal    = lokasi_asal,
                lokasi_tujuan  = lokasi_tujuan,
                catatan        = catatan,
                dilakukan_oleh = request.user,
                gangguan       = gangguan,
            )
            if foto:
                event.foto = foto
            event.save()

            # Auto-update lokasi jika relokasi
            if tipe == 'relokasi' and lokasi_tujuan:
                device.lokasi = lokasi_tujuan.upper()
                device.save(update_fields=['lokasi'])

            # Auto-update status DeviceComponent berdasarkan tipe perubahan
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

    return redirect('gangguan_detail', pk=pk)


@login_required
@require_can_delete
def gangguan_hapus_perubahan(request, pk, event_pk):
    """Hapus perubahan fisik dari halaman gangguan."""
    if request.method == 'POST':
        from devices.models import DeviceEvent
        event = get_object_or_404(DeviceEvent, pk=event_pk, gangguan_id=pk)
        event.delete()
    return redirect('gangguan_detail', pk=pk)


def gangguan_public_status(request, nomor, token):
    """Halaman publik status gangguan — TIDAK perlu login."""
    gangguan = get_object_or_404(Gangguan, nomor_gangguan=nomor, public_token=token)
    log_entries = gangguan.log_entries.order_by('waktu_aksi')
    return render(request, 'gangguan/gangguan_public.html', {
        'gangguan':    gangguan,
        'log_entries': log_entries,
    })
