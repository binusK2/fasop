import datetime
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from .models import RTU, RTULog


def _boundaries():
    """
    Kembalikan (now, today_start, month_start) semuanya timezone-aware UTC.
    Batas dihitung dari waktu LOKAL agar benar untuk zona Asia/Makassar.
    """
    tz_local   = timezone.get_current_timezone()
    now        = timezone.now()                         # UTC-aware
    now_local  = now.astimezone(tz_local)

    today_start = now_local.replace(
        hour=0, minute=0, second=0, microsecond=0
    )                                                   # masih aware (local tz)

    month_start = now_local.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    return now, today_start, month_start


def _calc_avail(logs_down, since, now, total_menit):
    """
    Hitung menit DOWN dari kumpulan log yang sudah di-filter,
    lalu kembalikan availability %.
    logs_down: queryset atau list RTULog (state=DOWN) yang overlap dengan [since, now].
    """
    down_menit = 0
    for log in logs_down:
        start = max(log.mulai, since)
        end   = min(log.selesai, now) if log.selesai else now
        down_menit += max(0, int((end - start).total_seconds() / 60))

    up_menit = max(0, total_menit - down_menit)
    return round(up_menit / total_menit * 100, 2)


@login_required
def dashboard(request):
    return render(request, 'device_mon/dashboard.html')


@login_required
def api_status(request):
    """
    JSON: status semua RTU + statistik availability.
    Dipanggil oleh dashboard setiap 60 detik.

    Optimasi: ambil semua log DOWN dalam satu query per periode,
    kemudian group by rtu_id di Python — tidak ada N+1.
    """
    now, today_start, month_start = _boundaries()

    rtus = list(RTU.objects.filter(aktif=True))
    if not rtus:
        return JsonResponse({
            'total_up': 0, 'total_down': 0, 'total_rtu': 0,
            'avail_hari': None, 'avail_bulan': None,
            'rtus': [], 'gangguan_terkini': [],
        })

    rtu_ids = [r.pk for r in rtus]

    # ── Ambil semua log DOWN relevan dalam SATU query per periode ──────
    # Hari ini
    down_today = list(
        RTULog.objects.filter(
            rtu_id__in=rtu_ids,
            state='DOWN',
            mulai__lt=now,
        ).filter(Q(selesai__gt=today_start) | Q(selesai__isnull=True))
    )

    # Bulan ini
    down_month = list(
        RTULog.objects.filter(
            rtu_id__in=rtu_ids,
            state='DOWN',
            mulai__lt=now,
        ).filter(Q(selesai__gt=month_start) | Q(selesai__isnull=True))
    )

    # Group log by rtu_id di Python (tanpa loop N query)
    def group_by_rtu(logs):
        d = {}
        for log in logs:
            d.setdefault(log.rtu_id, []).append(log)
        return d

    today_by_rtu = group_by_rtu(down_today)
    month_by_rtu = group_by_rtu(down_month)

    total_menit_today = max(1, int((now - today_start).total_seconds() / 60))
    total_menit_month = max(1, int((now - month_start).total_seconds() / 60))

    # ── Hitung per RTU ─────────────────────────────────────────────────
    rtu_data   = []
    total_up   = 0
    total_down = 0
    avail_hari_list = []

    for rtu in rtus:
        if rtu.state == 'UP':
            total_up  += 1
        elif rtu.state == 'DOWN':
            total_down += 1

        avail_hari  = _calc_avail(
            today_by_rtu.get(rtu.pk, []), today_start, now, total_menit_today
        )
        avail_bulan = _calc_avail(
            month_by_rtu.get(rtu.pk, []), month_start, now, total_menit_month
        )
        avail_hari_list.append(avail_hari)

        # Menit DOWN hari ini (hanya yang sudah selesai + yang masih jalan)
        down_menit_hari = 0
        for log in today_by_rtu.get(rtu.pk, []):
            start = max(log.mulai, today_start)
            end   = min(log.selesai, now) if log.selesai else now
            down_menit_hari += max(0, int((end - start).total_seconds() / 60))

        rtu_data.append({
            'id':              rtu.pk,
            'nama':            rtu.nama,
            'lokasi':          rtu.lokasi,
            'state':           rtu.state,
            'state_sejak':     rtu.state_sejak.isoformat() if rtu.state_sejak else None,
            'durasi_menit':    rtu.durasi_menit,
            'avail_hari':      avail_hari,
            'avail_bulan':     avail_bulan,
            'down_menit_hari': down_menit_hari,
        })

    avg_avail_hari  = round(sum(avail_hari_list) / len(avail_hari_list), 2) if avail_hari_list else None
    avg_avail_bulan = _calc_avail(down_month, month_start, now, total_menit_month * len(rtus)) if rtus else None

    # ── 10 log gangguan terkini ────────────────────────────────────────
    gangguan = RTULog.objects.filter(state='DOWN').select_related('rtu').order_by('-mulai')[:10]
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
    """Halaman laporan availability per RTU — bulan ini."""
    now, _, month_start = _boundaries()

    rtu_ids = list(RTU.objects.filter(aktif=True).values_list('pk', flat=True))
    down_month = list(
        RTULog.objects.filter(
            rtu_id__in=rtu_ids,
            state='DOWN',
            mulai__lt=now,
        ).filter(Q(selesai__gt=month_start) | Q(selesai__isnull=True))
    )
    month_by_rtu   = {}
    for log in down_month:
        month_by_rtu.setdefault(log.rtu_id, []).append(log)

    total_menit = max(1, int((now - month_start).total_seconds() / 60))

    rtus = RTU.objects.filter(aktif=True)
    rows = []
    for rtu in rtus:
        avail = _calc_avail(month_by_rtu.get(rtu.pk, []), month_start, now, total_menit)
        rows.append({'rtu': rtu, 'avail': avail})

    tz_local   = timezone.get_current_timezone()
    month_start_local = month_start.astimezone(tz_local)

    return render(request, 'device_mon/availability.html', {
        'rows':   rows,
        'period': month_start_local.strftime('%B %Y'),
    })
