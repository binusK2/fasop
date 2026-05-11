from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from devices.permissions import require_can_edit, require_can_delete
from django.http import JsonResponse
from django.db.models import Q, Avg, Count, Max
from django.db.models.functions import Upper, ExtractYear, ExtractMonth
from django.utils import timezone
from datetime import date as date_type
import calendar

from .models import JadwalKunjungan, JADWAL_EXCLUDED_JENIS
from devices.models import Device
from maintenance.models import Maintenance


# ── Helper: ambil semua lokasi unik dari device ───────────────────────────────
def _get_lokasi_list():
    from django.db.models.functions import Trim
    return (
        Device.objects.filter(is_deleted=False)
        .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
        .annotate(lc=Trim('lokasi'))
        .values_list('lc', flat=True)
        .distinct().order_by('lc')
    )


# ── Helper: hitung skor prioritas lokasi ─────────────────────────────────────
def _hitung_prioritas(lokasi):
    """
    Skor prioritas 0–100 berdasarkan:
    - Berapa bulan sejak maintenance preventive terakhir di lokasi (40%)
    - Rata-rata HI device di lokasi (35%, diinvers: HI rendah → prioritas tinggi)
    - Jumlah device di lokasi (25%)
    """
    today = date_type.today()

    devices = Device.objects.filter(
        lokasi__iexact=lokasi, is_deleted=False, host__isnull=True,
    ).exclude(jenis__name__in=JADWAL_EXCLUDED_JENIS)
    total_device = devices.count()
    if total_device == 0:
        return 0

    # 1. Bulan sejak preventive terakhir di lokasi ini
    last_pm = (
        Maintenance.objects
        .filter(device__lokasi__iexact=lokasi, maintenance_type='Preventive', status='Done')
        .order_by('-date').first()
    )
    if last_pm is None:
        bulan_lalu = 24   # belum pernah → anggap 24 bulan
    else:
        from dateutil.relativedelta import relativedelta
        rd = relativedelta(today, last_pm.date.date() if hasattr(last_pm.date, 'date') else last_pm.date)
        bulan_lalu = rd.years * 12 + rd.months

    skor_umur = min(bulan_lalu / 24 * 100, 100)  # maks 24 bulan → 100%

    # 2. Rata-rata HI (tanpa simpan snapshot untuk hemat resource)
    try:
        from health_index.calculator import calculate_hi
        hi_scores = [calculate_hi(d, save_snapshot=False)['score'] for d in devices[:10]]
        avg_hi = sum(hi_scores) / len(hi_scores) if hi_scores else 75
    except Exception:
        avg_hi = 75
    skor_hi = 100 - avg_hi   # HI rendah → prioritas tinggi

    # 3. Jumlah device (lebih banyak device → lebih prioritas, maks 30)
    skor_device = min(total_device / 30 * 100, 100)

    total = round(skor_umur * 0.40 + skor_hi * 0.35 + skor_device * 0.25)
    return min(total, 100)


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
def jadwal_list(request):
    """Halaman utama — daftar jadwal + ranking prioritas lokasi."""
    filter_status = request.GET.get('status', '')
    filter_tahun  = request.GET.get('tahun', str(date_type.today().year))
    search        = request.GET.get('q', '').strip()

    jadwals_qs = JadwalKunjungan.objects.select_related('created_by').all()
    if filter_status:
        jadwals_qs = jadwals_qs.filter(status=filter_status)
    if filter_tahun:
        jadwals_qs = jadwals_qs.filter(tahun_rencana=int(filter_tahun))
    if search:
        jadwals_qs = jadwals_qs.filter(lokasi__icontains=search)

    today = date_type.today()
    current_month_start = date_type(today.year, today.month, 1)
    filter_tahun_int = int(filter_tahun) if filter_tahun else today.year

    jadwals = list(jadwals_qs)  # evaluate queryset once

    # Batch 1: device count per lokasi (upper-cased for case-insensitive match)
    _dev_count_map = {
        row['lu']: row['cnt']
        for row in Device.objects.filter(is_deleted=False, host__isnull=True)
            .exclude(jenis__name__in=JADWAL_EXCLUDED_JENIS)
            .annotate(lu=Upper('lokasi'))
            .values('lu').annotate(cnt=Count('id'))
    }

    # Batch 2: distinct devices with Preventive maintenance per (lokasi_upper, year, month)
    _selesai_map = {
        (row['lu'], row['yr'], row['mo']): row['selesai']
        for row in Maintenance.objects.filter(
                maintenance_type='Preventive',
                device__is_deleted=False,
                device__host__isnull=True,
            )
            .exclude(device__jenis__name__in=JADWAL_EXCLUDED_JENIS)
            .annotate(
                lu=Upper('device__lokasi'),
                yr=ExtractYear('date'),
                mo=ExtractMonth('date'),
            )
            .values('lu', 'yr', 'mo')
            .annotate(selesai=Count('device_id', distinct=True))
    }

    # Compute progress + sync status in Python — no per-jadwal DB queries
    jadwal_data = []
    to_update = []
    for j in jadwals:
        lokasi_up = j.lokasi.upper()
        total = _dev_count_map.get(lokasi_up, 0)
        if total == 0:
            prog = {'total': 0, 'selesai': 0, 'belum': 0, 'pct': 0, 'status_auto': 'planned'}
        else:
            selesai = _selesai_map.get((lokasi_up, j.tahun_rencana, j.bulan_rencana), 0)
            pct = round(selesai / total * 100)
            if selesai == 0:       status_auto = 'planned'
            elif selesai >= total: status_auto = 'done'
            else:                  status_auto = 'in_progress'
            prog = {
                'total': total, 'selesai': selesai,
                'belum': total - selesai, 'pct': pct, 'status_auto': status_auto,
            }

        if prog['status_auto'] != j.status and j.status != 'done':
            j.status = prog['status_auto']
            to_update.append(j)

        period_start = date_type(j.tahun_rencana, j.bulan_rencana, 1)
        is_overdue = (j.status != 'done') and (period_start < current_month_start)
        jadwal_data.append({'jadwal': j, 'progress': prog, 'is_overdue': is_overdue})

    if to_update:
        JadwalKunjungan.objects.bulk_update(to_update, ['status', 'updated_at'])

    # Urutkan: overdue & aktif di atas, selesai (done) di bawah
    jadwal_data.sort(key=lambda x: (
        1 if x['jadwal'].status == 'done' else 0,
        x['jadwal'].tahun_rencana,
        x['jadwal'].bulan_rencana,
        x['jadwal'].minggu_rencana,
        x['jadwal'].lokasi,
    ))

    # Summary — single aggregated query
    semua = JadwalKunjungan.objects.filter(tahun_rencana=filter_tahun_int)
    _scounts = dict(semua.values('status').annotate(cnt=Count('id')).values_list('status', 'cnt'))
    summary = {
        'total':       sum(_scounts.values()),
        'planned':     _scounts.get('planned', 0),
        'in_progress': _scounts.get('in_progress', 0),
        'done':        _scounts.get('done', 0),
    }

    # Data kalender — 12 bulan
    _BULAN_ID = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
    kalender_data = []
    for bulan in range(1, 13):
        entries = [item for item in jadwal_data if item['jadwal'].bulan_rencana == bulan]
        period_start = date_type(filter_tahun_int, bulan, 1)
        kalender_data.append({
            'bulan': bulan,
            'nama': _BULAN_ID[bulan],
            'entries': entries,
            'is_current': bulan == today.month and filter_tahun_int == today.year,
            'is_past': period_start < current_month_start,
        })

    # Ranking prioritas lokasi yang belum punya jadwal tahun ini — batch queries
    lokasi_sudah_dijadwal = set(
        JadwalKunjungan.objects.filter(tahun_rencana=today.year).values_list('lokasi', flat=True)
    )
    lokasi_belum = [l for l in _get_lokasi_list() if l not in lokasi_sudah_dijadwal]

    ranking = []
    if lokasi_belum:
        from dateutil.relativedelta import relativedelta as _rd
        from health_index.models import HISnapshot

        # Batch: device count per lokasi
        _rank_dev_map = {
            row['lu']: row['cnt']
            for row in Device.objects.filter(is_deleted=False)
                .annotate(lu=Upper('lokasi')).values('lu').annotate(cnt=Count('id'))
        }
        # Batch: last preventive PM per lokasi
        _rank_pm_map = {
            row['lu']: row['last_date']
            for row in Maintenance.objects.filter(maintenance_type='Preventive', status='Done')
                .annotate(lu=Upper('device__lokasi')).values('lu').annotate(last_date=Max('date'))
        }
        # Batch: avg HI score from this month's snapshots per lokasi
        _rank_hi_map = {
            row['lu']: row['avg_s']
            for row in HISnapshot.objects.filter(bulan=today.month, tahun=today.year)
                .annotate(lu=Upper('device__lokasi')).values('lu').annotate(avg_s=Avg('score'))
        }

        for lok in lokasi_belum:
            lok_up = lok.upper()
            dev_count = _rank_dev_map.get(lok_up, 0)
            if dev_count == 0:
                continue
            last_pm_date = _rank_pm_map.get(lok_up)
            if last_pm_date is None:
                bulan_lalu = 24
            else:
                if hasattr(last_pm_date, 'date'):
                    last_pm_date = last_pm_date.date()
                rd = _rd(today, last_pm_date)
                bulan_lalu = rd.years * 12 + rd.months
            skor_umur   = min(bulan_lalu / 24 * 100, 100)
            avg_hi      = _rank_hi_map.get(lok_up) or 75
            skor_hi     = 100 - avg_hi
            skor_device = min(dev_count / 30 * 100, 100)
            prioritas   = min(round(skor_umur * 0.40 + skor_hi * 0.35 + skor_device * 0.25), 100)
            ranking.append({'lokasi': lok, 'prioritas': prioritas, 'device_count': dev_count})

        ranking.sort(key=lambda x: x['prioritas'], reverse=True)
        ranking = ranking[:8]

    # Daftar tahun untuk filter
    tahun_list = list(range(date_type.today().year - 2, date_type.today().year + 3))
    bulan_list  = [(i, calendar.month_name[i]) for i in range(1, 13)]
    minggu_list = [(0, 'Semua Minggu'), (1, 'Minggu 1'), (2, 'Minggu 2'), (3, 'Minggu 3'), (4, 'Minggu 4')]

    return render(request, 'jadwal/jadwal_list.html', {
        'jadwal_data':    jadwal_data,
        'kalender_data':  kalender_data,
        'summary':        summary,
        'ranking':        ranking,
        'filter_status':  filter_status,
        'filter_tahun':   filter_tahun,
        'search':         search,
        'tahun_list':     tahun_list,
        'lokasi_list':    _get_lokasi_list(),
        'bulan_list':     bulan_list,
        'minggu_list':    minggu_list,
        'today_year':     date_type.today().year,
        'today_month':    date_type.today().month,
    })


@login_required
@require_can_edit
def jadwal_create(request):
    """Buat jadwal kunjungan baru — tidak bisa backdate."""
    from django.contrib import messages
    if request.method == 'POST':
        lokasi  = request.POST.get('lokasi', '').strip()
        bulan   = int(request.POST.get('bulan_rencana', 0))
        tahun   = int(request.POST.get('tahun_rencana', 0))
        minggu  = int(request.POST.get('minggu_rencana', 0))
        catatan = request.POST.get('catatan', '').strip()

        if lokasi and bulan and tahun:
            today = date_type.today()

            # Validasi backdate: tidak boleh bulan/tahun yang sudah lewat
            if (tahun < today.year) or (tahun == today.year and bulan < today.month):
                messages.error(request, 'Tidak dapat membuat jadwal untuk bulan yang sudah lewat.')
                return redirect('jadwal_list')

            jadwal, created = JadwalKunjungan.objects.get_or_create(
                lokasi=lokasi.upper(),
                bulan_rencana=bulan,
                tahun_rencana=tahun,
                minggu_rencana=minggu,
                defaults={'catatan': catatan, 'created_by': request.user}
            )
            return redirect('jadwal_detail', pk=jadwal.pk)

    return redirect('jadwal_list')


@login_required
def jadwal_detail(request, pk):
    """Detail satu jadwal kunjungan — progress per device."""
    jadwal = get_object_or_404(JadwalKunjungan, pk=pk)
    jadwal.sync_status()

    devices = Device.objects.filter(
        lokasi__iexact=jadwal.lokasi, is_deleted=False, host__isnull=True,
    ).exclude(jenis__name__in=JADWAL_EXCLUDED_JENIS).select_related('jenis').order_by('jenis__name', 'nama')

    # Cek tiap device: sudah ada maintenance Preventive di periode ini?
    device_data = []
    for d in devices:
        maintenance_periode = Maintenance.objects.filter(
            device=d,
            maintenance_type='Preventive',
            date__year=jadwal.tahun_rencana,
            date__month=jadwal.bulan_rencana,
        ).order_by('-date').first()

        # HI device
        try:
            from health_index.calculator import calculate_hi
            hi = calculate_hi(d, save_snapshot=False)
            hi_score    = hi['score']
            hi_kategori = hi['kategori']
        except Exception:
            hi_score    = None
            hi_kategori = None

        device_data.append({
            'device':             d,
            'maintenance_periode': maintenance_periode,
            'selesai':            maintenance_periode is not None,
            'hi_score':           hi_score,
            'hi_kategori':        hi_kategori,
        })

    progress = jadwal.get_progress()

    return render(request, 'jadwal/jadwal_detail.html', {
        'jadwal':      jadwal,
        'device_data': device_data,
        'progress':    progress,
    })


@login_required
def jadwal_done(request, pk):
    """Manual tandai jadwal sebagai Done."""
    if request.method == 'POST':
        jadwal = get_object_or_404(JadwalKunjungan, pk=pk)
        jadwal.status = 'done'
        jadwal.save(update_fields=['status', 'updated_at'])
    return redirect('jadwal_detail', pk=pk)


@login_required
@require_can_edit
def jadwal_selesai_semua(request, pk):
    """Bulk tandai semua pemeliharaan device di jadwal ini sebagai Done."""
    from datetime import datetime
    if request.method == 'POST':
        jadwal = get_object_or_404(JadwalKunjungan, pk=pk)
        devices = Device.objects.filter(
            lokasi__iexact=jadwal.lokasi, is_deleted=False, host__isnull=True,
        ).exclude(jenis__name__in=JADWAL_EXCLUDED_JENIS)

        tgl = timezone.make_aware(datetime(jadwal.tahun_rencana, jadwal.bulan_rencana, 1))

        for d in devices:
            exists = Maintenance.objects.filter(
                device=d,
                maintenance_type='Preventive',
                date__year=jadwal.tahun_rencana,
                date__month=jadwal.bulan_rencana,
            ).exists()
            if not exists:
                Maintenance.objects.create(
                    device=d,
                    maintenance_type='Preventive',
                    date=tgl,
                    status='Done',
                    description='Ditandai selesai via Jadwal Kunjungan (bulk)',
                )
    return redirect('jadwal_detail', pk=pk)


@login_required
@require_can_delete
def jadwal_delete(request, pk):
    """Hapus jadwal."""
    if request.method == 'POST':
        jadwal = get_object_or_404(JadwalKunjungan, pk=pk)
        jadwal.delete()
    return redirect('jadwal_list')
