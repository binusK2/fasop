from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from devices.models import Device
from .calculator import calculate_hi, get_kategori
from datetime import date as date_type


@login_required
def hi_list(request):
    """Halaman daftar Health Index semua peralatan."""
    devices = Device.objects.filter(is_deleted=False).select_related('jenis').order_by('nama')

    # Filter opsional
    filter_kategori = request.GET.get('kategori', '')
    filter_lokasi   = request.GET.get('lokasi', '')
    search          = request.GET.get('q', '').strip()

    # Hitung HI untuk setiap device
    results = []
    for device in devices:
        hi = calculate_hi(device, save_snapshot=False)
        results.append({
            'device': device,
            'hi':     hi,
        })

    # Terapkan filter setelah kalkulasi
    if filter_kategori:
        results = [r for r in results if r['hi']['kategori']['label'] == filter_kategori]
    if filter_lokasi:
        results = [r for r in results if r['device'].lokasi == filter_lokasi]
    if search:
        results = [
            r for r in results
            if search.lower() in r['device'].nama.lower()
            or (r['device'].lokasi and search.lower() in r['device'].lokasi.lower())
        ]

    # Urut by score ascending (paling buruk duluan) agar mudah di-triage
    sort = request.GET.get('sort', 'score_asc')
    if sort == 'score_asc':
        results.sort(key=lambda r: r['hi']['score'])
    elif sort == 'score_desc':
        results.sort(key=lambda r: r['hi']['score'], reverse=True)
    elif sort == 'nama':
        results.sort(key=lambda r: r['device'].nama)

    # Summary counters
    all_results_for_summary = []
    for device in Device.objects.filter(is_deleted=False).select_related('jenis'):
        hi = calculate_hi(device, save_snapshot=False)
        all_results_for_summary.append(hi)

    summary = {
        'sangat_baik': sum(1 for r in all_results_for_summary if r['score'] >= 85),
        'baik':        sum(1 for r in all_results_for_summary if 70 <= r['score'] < 85),
        'cukup':       sum(1 for r in all_results_for_summary if 50 <= r['score'] < 70),
        'buruk':       sum(1 for r in all_results_for_summary if 25 <= r['score'] < 50),
        'kritis':      sum(1 for r in all_results_for_summary if r['score'] < 25),
        'total':       len(all_results_for_summary),
    }

    # Daftar lokasi untuk filter dropdown
    lokasi_list = (
        Device.objects.filter(is_deleted=False)
        .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
        .values_list('lokasi', flat=True)
        .distinct().order_by('lokasi')
    )

    return render(request, 'health_index/hi_list.html', {
        'results':          results,
        'summary':          summary,
        'lokasi_list':      lokasi_list,
        'filter_kategori':  filter_kategori,
        'filter_lokasi':    filter_lokasi,
        'search':           search,
        'sort':             sort,
        'kategori_choices': ['Sangat Baik', 'Baik', 'Cukup', 'Buruk', 'Kritis'],
        'today_bulan':      date_type.today().month,
        'today_tahun':      date_type.today().year,
    })


@login_required
def hi_settings(request):
    """Halaman konfigurasi bobot faktor Health Index."""
    from health_index.models import KonfigurasiHI
    from health_index.registry import DEFAULT_BOBOT

    configs = KonfigurasiHI.get_or_init()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'reset':
            for cfg in configs:
                cfg.bobot_maks = DEFAULT_BOBOT.get(cfg.faktor_key, cfg.bobot_maks)
                cfg.aktif = True
                cfg.save()

        elif action == 'save':
            for cfg in configs:
                bobot_raw = request.POST.get(f'bobot_{cfg.faktor_key}', '')
                aktif     = request.POST.get(f'aktif_{cfg.faktor_key}') == 'on'
                try:
                    bobot = int(bobot_raw)
                    if bobot > 0:
                        bobot = -bobot   # pastikan negatif
                    cfg.bobot_maks = bobot
                except (ValueError, TypeError):
                    pass
                cfg.aktif = aktif
                cfg.save()

        return redirect('hi_settings')

    total_bobot = sum(abs(c.bobot_maks) for c in configs if c.aktif)

    kategori_guide = [
        ('Sangat Baik', '#065f46', '#dcfce7', '#a7f3d0', '85–100'),
        ('Baik',        '#1d4ed8', '#dbeafe', '#bfdbfe', '70–84'),
        ('Cukup',       '#854d0e', '#fef3c7', '#fde68a', '50–69'),
        ('Buruk',       '#9a3412', '#fff7ed', '#fed7aa', '25–49'),
        ('Kritis',      '#991b1b', '#fee2e2', '#fca5a5', '0–24'),
    ]

    return render(request, 'health_index/hi_settings.html', {
        'configs':        configs,
        'total_bobot':    total_bobot,
        'default_bobot':  DEFAULT_BOBOT,
        'kategori_guide': kategori_guide,
    })
    """Halaman detail Health Index satu peralatan."""
    device = get_object_or_404(Device, pk=pk, is_deleted=False)
    hi = calculate_hi(device)

    # Ambil 12 snapshot terakhir untuk grafik tren
    from health_index.models import HISnapshot
    snapshots = (
        HISnapshot.objects
        .filter(device=device)
        .order_by('tahun', 'bulan')[:12]
    )
    tren_labels  = [s.label_bulan for s in snapshots]
    tren_scores  = [s.score for s in snapshots]
    tren_colors  = []
    for s in snapshots:
        if s.score >= 85:   tren_colors.append('#10b981')
        elif s.score >= 70: tren_colors.append('#3b82f6')
        elif s.score >= 50: tren_colors.append('#f59e0b')
        elif s.score >= 25: tren_colors.append('#f97316')
        else:               tren_colors.append('#ef4444')

    return render(request, 'health_index/hi_detail.html', {
        'device':       device,
        'hi':           hi,
        'tren_labels':  tren_labels,
        'tren_scores':  tren_scores,
        'tren_colors':  tren_colors,
        'has_tren':     len(tren_scores) > 1,
    })


@login_required
def hi_detail(request, pk):
    """Halaman detail Health Index satu peralatan."""
    device = get_object_or_404(Device, pk=pk, is_deleted=False)
    hi = calculate_hi(device)

    # Ambil 12 snapshot terakhir untuk grafik tren
    from health_index.models import HISnapshot
    snapshots = (
        HISnapshot.objects
        .filter(device=device)
        .order_by('tahun', 'bulan')[:12]
    )
    tren_labels = [s.label_bulan for s in snapshots]
    tren_scores = [s.score for s in snapshots]
    tren_colors = []
    for s in snapshots:
        if s.score >= 85:        tren_colors.append('#10b981')
        elif s.score >= 70:      tren_colors.append('#3b82f6')
        elif s.score >= 50:      tren_colors.append('#f59e0b')
        elif s.score >= 25:      tren_colors.append('#f97316')
        else:                    tren_colors.append('#ef4444')

    return render(request, 'health_index/hi_detail.html', {
        'device':      device,
        'hi':          hi,
        'tren_labels': tren_labels,
        'tren_scores': tren_scores,
        'tren_colors': tren_colors,
        'has_tren':    len(tren_scores) > 1,
    })


@login_required
def export_hi_pdf(request):
    """Export laporan Health Index ke PDF dengan filter bulan, tahun, lokasi."""
    from django.http import HttpResponse
    from health_index.pdf_export.laporan_hi import generate_laporan_hi
    from devices.models import Device

    bulan  = int(request.GET.get('bulan', date_type.today().month))
    tahun  = int(request.GET.get('tahun', date_type.today().year))
    lokasi = request.GET.get('lokasi', '').strip() or None

    devices = Device.objects.filter(is_deleted=False).select_related('jenis').order_by('lokasi', 'nama')
    if lokasi:
        devices = devices.filter(lokasi__icontains=lokasi)

    devices_hi = []
    for d in devices:
        hi = calculate_hi(d, save_snapshot=False)
        devices_hi.append({'device': d, 'hi': hi})

    buf = generate_laporan_hi(devices_hi, bulan=bulan, tahun=tahun, lokasi=lokasi)

    import calendar
    bln      = calendar.month_abbr[bulan]
    lok_str  = f'_{lokasi.replace(" ", "_")}' if lokasi else ''
    filename = f'laporan_hi_{bln}_{tahun}{lok_str}.pdf'
    response = HttpResponse(buf.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_jadwal_pdf(request):
    """Export rekap jadwal pemeliharaan ke PDF."""
    from django.http import HttpResponse
    from health_index.pdf_export.laporan_jadwal import generate_laporan_jadwal
    from jadwal.models import JadwalKunjungan

    tahun = int(request.GET.get('tahun', date_type.today().year))

    jadwals = JadwalKunjungan.objects.filter(tahun_rencana=tahun).order_by('bulan_rencana', 'lokasi')
    for j in jadwals:
        j.sync_status()

    buf = generate_laporan_jadwal(list(jadwals), tahun=tahun)

    filename = f'rekap_jadwal_pemeliharaan_{tahun}.pdf'
    response = HttpResponse(buf.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
