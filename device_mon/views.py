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
def rtu_detail(request, pk):
    """Halaman detail satu RTU — info state, availability, histori log."""
    rtu = get_object_or_404(RTU, pk=pk)
    return render(request, 'device_mon/rtu_detail.html', {'rtu': rtu})


@login_required
def api_rtu_logs(request, pk):
    """
    JSON: log state RTU untuk chart timeline + tabel.
    ?hari=N  (default 7, max 30)
    """
    rtu = get_object_or_404(RTU, pk=pk)
    try:
        hari = min(max(int(request.GET.get('hari', 7)), 1), 30)
    except (ValueError, TypeError):
        hari = 7

    now, today_start, month_start = _boundaries()
    tz_local = timezone.get_current_timezone()
    since    = now - datetime.timedelta(days=hari)

    logs = (RTULog.objects
            .filter(rtu=rtu, mulai__gte=since)
            .order_by('mulai'))

    total_menit = max(1, int((now - since).total_seconds() / 60))
    down_logs   = [l for l in logs if l.state == 'DOWN']
    avail       = _calc_avail(down_logs, since, now, total_menit)

    # Availability hari ini & bulan ini
    down_today = [l for l in RTULog.objects.filter(
        rtu=rtu, state='DOWN', mulai__lt=now
    ).filter(Q(selesai__gt=today_start) | Q(selesai__isnull=True))]
    down_month = [l for l in RTULog.objects.filter(
        rtu=rtu, state='DOWN', mulai__lt=now
    ).filter(Q(selesai__gt=month_start) | Q(selesai__isnull=True))]

    avail_hari  = _calc_avail(down_today, today_start, now,
                              max(1, int((now - today_start).total_seconds() / 60)))
    avail_bulan = _calc_avail(down_month, month_start, now,
                              max(1, int((now - month_start).total_seconds() / 60)))

    # Total menit DOWN dalam periode
    down_menit_total = sum(
        max(0, int((
            (min(l.selesai, now) if l.selesai else now) -
            max(l.mulai, since)
        ).total_seconds() / 60))
        for l in down_logs
    )

    # Format log untuk tabel & chart
    log_data = []
    for l in logs:
        mulai_local   = l.mulai.astimezone(tz_local)
        selesai_local = l.selesai.astimezone(tz_local) if l.selesai else None
        # Durasi aktual (mungkin masih berjalan)
        dur = l.durasi_menit
        if dur is None and not l.selesai:
            dur = max(0, int((now - l.mulai).total_seconds() / 60))
        log_data.append({
            'state':        l.state,
            'mulai':        mulai_local.strftime('%d/%m %H:%M'),
            'selesai':      selesai_local.strftime('%d/%m %H:%M') if selesai_local else None,
            'durasi_menit': dur,
        })

    return JsonResponse({
        'nama':             rtu.nama,
        'lokasi':           rtu.lokasi,
        'state':            rtu.state,
        'state_sejak':      rtu.state_sejak.astimezone(tz_local).strftime('%d/%m/%Y %H:%M') if rtu.state_sejak else None,
        'durasi_menit':     rtu.durasi_menit,
        'avail_hari':       avail_hari,
        'avail_bulan':      avail_bulan,
        'avail_periode':    avail,
        'down_menit_total': down_menit_total,
        'hari':             hari,
        'logs':             log_data,
    })


@login_required
def gangguan_list(request):
    """Halaman histori gangguan."""
    logs = (RTULog.objects
            .filter(state='DOWN')
            .select_related('rtu')
            .order_by('-mulai')[:200])
    return render(request, 'device_mon/gangguan.html', {'logs': logs})


def _bulan_boundaries(tahun, bulan):
    """Batas awal & akhir (eksklusif) sebuah bulan, timezone-aware (local tz)."""
    tz_local = timezone.get_current_timezone()
    month_start = timezone.make_aware(datetime.datetime(tahun, bulan, 1), tz_local)
    if bulan == 12:
        next_tahun, next_bulan = tahun + 1, 1
    else:
        next_tahun, next_bulan = tahun, bulan + 1
    month_end = timezone.make_aware(datetime.datetime(next_tahun, next_bulan, 1), tz_local)
    return month_start, month_end


NAMA_BULAN = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
              'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']


@login_required
def export_availability(request):
    """
    Download rekap availability RTU per bulan ke Excel.
    ?bulan=YYYY-MM  (default: bulan berjalan)

    Sheet "Detail Gangguan": tiap log DOWN RTU dalam bulan tsb, dengan kolom
    Eliminasi (dropdown Ya/Tidak) dan Durasi Efektif (formula Excel).
    Sheet "Rekap Availability": AV% per RTU dihitung via formula SUMIFS yang
    merujuk ke sheet Detail — jadi saat kolom Eliminasi diubah di Excel,
    nilai Av langsung ter-update otomatis tanpa perlu download ulang.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    tz_local = timezone.get_current_timezone()
    now = timezone.now()

    bulan_str = request.GET.get('bulan', '')
    try:
        tahun_str, bulan_num_str = bulan_str.split('-')
        tahun, bulan = int(tahun_str), int(bulan_num_str)
        if not (1 <= bulan <= 12):
            raise ValueError
    except (ValueError, TypeError):
        now_local = now.astimezone(tz_local)
        tahun, bulan = now_local.year, now_local.month

    month_start, month_end = _bulan_boundaries(tahun, bulan)
    effective_end = min(now, month_end)
    total_menit_bulan = max(1, int((effective_end - month_start).total_seconds() / 60))

    rtus = list(RTU.objects.filter(aktif=True))
    rtu_ids = [r.pk for r in rtus]

    down_logs = list(
        RTULog.objects.filter(
            rtu_id__in=rtu_ids,
            state='DOWN',
            mulai__lt=effective_end,
        ).filter(Q(selesai__gt=month_start) | Q(selesai__isnull=True))
        .select_related('rtu')
        .order_by('rtu__urutan', 'rtu__nama', 'mulai')
    )

    # ── Workbook & style ────────────────────────────────────────────
    wb = openpyxl.Workbook()

    hdr_fill = PatternFill('solid', fgColor='0F172A')
    hdr_font = Font(bold=True, color='60A5FA', size=10)
    thin     = Side(style='thin', color='1E293B')
    border   = Border(left=thin, right=thin, top=thin, bottom=thin)
    center   = Alignment(horizontal='center', vertical='center')

    label_periode = f'{NAMA_BULAN[bulan]} {tahun}'

    # ── Sheet 1: Detail Gangguan ────────────────────────────────────
    ws1 = wb.active
    ws1.title = 'Detail Gangguan'

    headers1 = ['No', 'RTU', 'Lokasi', 'Turun (Down)', 'Naik (Up) Kembali',
                'Durasi Down (menit)', 'Eliminasi', 'Durasi Efektif (menit)']
    ws1.append(headers1)
    for col in range(1, len(headers1) + 1):
        cell = ws1.cell(1, col)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.border = border
        cell.alignment = center

    for i, w in enumerate([6, 16, 18, 18, 18, 16, 12, 18], 1):
        ws1.column_dimensions[get_column_letter(i)].width = w

    row_idx = 1
    for log in down_logs:
        row_idx += 1
        mulai_clip   = max(log.mulai, month_start).astimezone(tz_local)
        selesai_clip = (min(log.selesai, effective_end) if log.selesai else effective_end).astimezone(tz_local)
        durasi = max(0, int((selesai_clip - mulai_clip).total_seconds() / 60))

        ws1.append([
            row_idx - 1,
            log.rtu.nama,
            log.rtu.lokasi,
            mulai_clip.strftime('%d/%m/%Y %H:%M'),
            selesai_clip.strftime('%d/%m/%Y %H:%M') if log.selesai else 'Masih Down',
            durasi,
            'Tidak',
            f'=IF(G{row_idx}="Ya",0,F{row_idx})',
        ])
        for col in range(1, len(headers1) + 1):
            ws1.cell(row_idx, col).border = border
            ws1.cell(row_idx, col).alignment = center

    if row_idx == 1:
        # Tidak ada gangguan sama sekali pada bulan ini
        row_idx = 2
        ws1.append(['-', '-', '-', '-', '-', 0, 'Tidak', 0])
        for col in range(1, len(headers1) + 1):
            ws1.cell(row_idx, col).border = border
            ws1.cell(row_idx, col).alignment = center

    last_detail_row = row_idx

    dv = DataValidation(type='list', formula1='"Tidak,Ya"', allow_blank=False)
    dv.add(f'G2:G{last_detail_row}')
    ws1.add_data_validation(dv)

    ws1.freeze_panes = 'A2'

    # ── Sheet 2: Rekap Availability ─────────────────────────────────
    ws2 = wb.create_sheet('Rekap Availability')
    ws2.append([f'Periode: {label_periode}'])
    ws2.cell(1, 1).font = Font(bold=True, color='CCE0FF', size=11)
    ws2.append([])

    headers2 = ['No', 'RTU', 'Lokasi', 'Total Menit Bulan',
                'Total Down Efektif (menit)', 'Availability (%)']
    header_row2 = 3
    ws2.append(headers2)
    for col in range(1, len(headers2) + 1):
        cell = ws2.cell(header_row2, col)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.border = border
        cell.alignment = center

    for i, w in enumerate([6, 16, 18, 18, 22, 16], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    row_idx2 = header_row2
    for rtu in rtus:
        row_idx2 += 1
        ws2.append([
            row_idx2 - header_row2,
            rtu.nama,
            rtu.lokasi,
            total_menit_bulan,
            f"=SUMIFS('Detail Gangguan'!$H$2:$H${last_detail_row},"
            f"'Detail Gangguan'!$B$2:$B${last_detail_row},B{row_idx2})",
            f'=ROUND((D{row_idx2}-E{row_idx2})/D{row_idx2}*100,2)',
        ])
        for col in range(1, len(headers2) + 1):
            ws2.cell(row_idx2, col).border = border
            ws2.cell(row_idx2, col).alignment = center

    first_data_row2 = header_row2 + 1
    last_rekap_row  = row_idx2
    ws2.append([])
    ws2.append(['', '', '', '', 'Rata-rata Availability',
                f'=ROUND(AVERAGE(F{first_data_row2}:F{last_rekap_row}),2)'])
    summary_row2 = last_rekap_row + 2
    ws2.cell(summary_row2, 5).font = Font(bold=True, color='34D399', size=10)
    ws2.cell(summary_row2, 6).font = Font(bold=True, color='34D399', size=10)

    ws2.freeze_panes = f'A{first_data_row2}'

    # ── Response ──────────────────────────────────────────────────
    filename = f'Availability_RTU_{tahun}-{bulan:02d}.xlsx'
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


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
