import datetime
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from .models import RTU, RTULog


def _avail_pct(rtu, since, until=None):
    """
    Hitung availability RTU dalam periode [since, until].
    Returns float 0-100 atau None jika belum ada log.
    """
    if until is None:
        until = timezone.now()
    total_menit = max(1, int((until - since).total_seconds() / 60))

    # Jumlahkan durasi DOWN dalam periode
    logs = RTULog.objects.filter(
        rtu=rtu,
        state='DOWN',
        mulai__lt=until,
    ).filter(Q(selesai__gt=since) | Q(selesai__isnull=True))

    down_menit = 0
    for log in logs:
        start = max(log.mulai, since)
        end   = min(log.selesai, until) if log.selesai else until
        down_menit += max(0, int((end - start).total_seconds() / 60))

    up_menit = max(0, total_menit - down_menit)
    return round(up_menit / total_menit * 100, 4)


@login_required
def dashboard(request):
    return render(request, 'device_mon/dashboard.html')


@login_required
def api_status(request):
    """
    JSON: status semua RTU + statistik availability.
    Dipanggil oleh dashboard setiap 60 detik.
    """
    tz_local = timezone.get_current_timezone()
    now      = timezone.now()

    # Batas waktu hari ini & bulan ini (waktu lokal)
    now_local    = now.astimezone(tz_local)
    today_start  = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start  = today_start.astimezone(timezone.utc)
    month_start  = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start  = month_start.astimezone(timezone.utc)

    rtus = RTU.objects.filter(aktif=True)

    rtu_data    = []
    total_up    = 0
    total_down  = 0
    avail_list  = []

    for rtu in rtus:
        is_up      = rtu.state == 'UP'
        if is_up:
            total_up  += 1
        elif rtu.state == 'DOWN':
            total_down += 1

        # Availability hari ini
        avail_hari = _avail_pct(rtu, today_start, now)
        avail_list.append(avail_hari)

        # Availability bulan ini
        avail_bulan = _avail_pct(rtu, month_start, now)

        # Menit DOWN hari ini
        down_hari = RTULog.objects.filter(
            rtu=rtu, state='DOWN',
            mulai__gte=today_start,
        )
        down_menit_hari = sum(
            l.durasi_menit or 0 for l in down_hari if l.durasi_menit
        )

        rtu_data.append({
            'id':             rtu.pk,
            'nama':           rtu.nama,
            'lokasi':         rtu.lokasi,
            'state':          rtu.state,
            'state_sejak':    rtu.state_sejak.isoformat() if rtu.state_sejak else None,
            'durasi_menit':   rtu.durasi_menit,
            'avail_hari':     avail_hari,
            'avail_bulan':    avail_bulan,
            'down_menit_hari': down_menit_hari,
        })

    # Availability sistem = rata-rata semua RTU
    avg_avail_hari  = round(sum(avail_list) / len(avail_list), 2) if avail_list else None
    avg_avail_bulan = None  # hitung saat diperlukan (berat jika banyak RTU)

    # 10 log gangguan terkini
    gangguan = RTULog.objects.filter(state='DOWN').select_related('rtu')[:10]
    gangguan_data = [
        {
            'rtu':          g.rtu.nama,
            'state':        g.state,
            'mulai':        g.mulai.isoformat(),
            'selesai':      g.selesai.isoformat() if g.selesai else None,
            'durasi_menit': g.durasi_menit,
        }
        for g in gangguan
    ]

    return JsonResponse({
        'total_up':         total_up,
        'total_down':       total_down,
        'total_rtu':        len(rtu_data),
        'avail_hari':       avg_avail_hari,
        'avail_bulan':      avg_avail_bulan,
        'rtus':             rtu_data,
        'gangguan_terkini': gangguan_data,
    })


@login_required
def gangguan_list(request):
    """Halaman histori gangguan."""
    logs = (RTULog.objects
            .filter(state='DOWN')
            .select_related('rtu')
            .order_by('-mulai')[:200])
    return render(request, 'device_mon/gangguan.html', {'logs': logs})


@login_required
def availability_report(request):
    """Halaman laporan availability per RTU."""
    tz_local    = timezone.get_current_timezone()
    now         = timezone.now()
    now_local   = now.astimezone(tz_local)

    # Default: bulan ini
    month_start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start_utc = month_start.astimezone(timezone.utc)

    rtus = RTU.objects.filter(aktif=True)
    rows = []
    for rtu in rtus:
        avail = _avail_pct(rtu, month_start_utc, now)
        rows.append({'rtu': rtu, 'avail': avail})

    return render(request, 'device_mon/availability.html', {
        'rows':       rows,
        'period':     month_start.strftime('%B %Y'),
    })
