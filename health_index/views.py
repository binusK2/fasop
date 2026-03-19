from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from devices.models import Device
from .calculator import calculate_hi, get_kategori


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
