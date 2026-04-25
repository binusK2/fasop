import datetime
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from .models import Pembangkit, SnapLive, SnapFreq
from . import mssql


def _pembangkit_aktif():
    return list(Pembangkit.objects.filter(aktif=True))


@login_required
def dashboard(request):
    pembangkit_list = _pembangkit_aktif()
    # Kelompokkan per jenis untuk tampilan grid
    grouped = {}
    for p in pembangkit_list:
        grouped.setdefault(p.jenis, []).append(p)
    return render(request, 'opsis/dashboard.html', {
        'pembangkit_list': pembangkit_list,
        'grouped':         grouped,
    })


@login_required
def pembangkit_detail(request, pk):
    p = get_object_or_404(Pembangkit, pk=pk, aktif=True)
    pembangkit_list = _pembangkit_aktif()
    return render(request, 'opsis/pembangkit.html', {
        'p':               p,
        'pembangkit_list': pembangkit_list,
    })


@login_required
def api_live(request):
    """JSON: nilai live semua pembangkit aktif. Dipanggil setiap 5 detik."""
    pembangkit_list = _pembangkit_aktif()
    result = mssql.get_live_data(pembangkit_list)
    data   = result['data']
    response = {
        'data':              data,
        'frekuensi_sistem':  result.get('frekuensi_sistem'),
    }
    if request.GET.get('debug') and (request.user.is_superuser or request.user.is_staff):
        response['dummy_count'] = sum(1 for v in data.values() if v.get('is_dummy'))
    return JsonResponse(response)


@login_required
def api_trend(request, pk):
    """JSON: data trend satu pembangkit untuk chart. ?jam=1|6|24"""
    p = get_object_or_404(Pembangkit, pk=pk)
    try:
        jam = int(request.GET.get('jam', 1))
        if jam not in (1, 6, 24):
            jam = 1
    except (ValueError, TypeError):
        jam = 1

    rows = mssql.get_trend_data(p, jam)

    labels    = [r['timestamp'] for r in rows]
    frekuensi = [r['frekuensi'] for r in rows]
    mw        = [r['mw']        for r in rows]
    mvar      = [r['mvar']      for r in rows]

    return JsonResponse({
        'labels':    labels,
        'frekuensi': frekuensi,
        'mw':        mw,
        'mvar':      mvar,
        'jam':       jam,
        'nama':      p.nama,
        'warna':     p.warna,
    })


@login_required
def export_frekuensi(request):
    """
    Download rekap frekuensi sistem harian dari PostgreSQL (SnapLive).
    ?tanggal=YYYY-MM-DD  (default: hari ini)
    Format: Excel (.xlsx)
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from django.db.models import Avg
    from django.http import HttpResponse

    # Parse tanggal
    tanggal_str = request.GET.get('tanggal', '')
    try:
        tanggal = datetime.date.fromisoformat(tanggal_str)
    except ValueError:
        tanggal = timezone.now().astimezone(timezone.get_current_timezone()).date()

    tz_local = timezone.get_current_timezone()

    # Ambil dari SnapFreq (per detik, retensi 30 hari)
    rows = SnapFreq.objects.filter(waktu__date=tanggal).order_by('waktu')

    # Buat workbook Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'Frekuensi {tanggal}'

    # Style
    hdr_fill = PatternFill('solid', fgColor='0F172A')
    hdr_font = Font(bold=True, color='60A5FA', size=10)
    thin     = Side(style='thin', color='1E293B')
    border   = Border(left=thin, right=thin, top=thin, bottom=thin)
    center   = Alignment(horizontal='center', vertical='center')

    # Header
    headers = ['No', 'Tanggal', 'Waktu', 'Frekuensi (Hz)', 'Status']
    ws.append(headers)
    for col, _ in enumerate(headers, 1):
        cell = ws.cell(1, col)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.border = border
        cell.alignment = center

    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 18
    ws.column_dimensions['E'].width = 18

    # Batas frekuensi normal PLN: 49.5 – 50.5 Hz
    batas_bawah, batas_atas = 49.5, 50.5

    for i, row in enumerate(rows, 1):
        waktu_lokal = row.waktu.astimezone(tz_local)
        hz = round(row.hz, 4) if row.hz is not None else None
        if hz is None:
            status = '—'
        elif hz < batas_bawah:
            status = '⚠ Rendah'
        elif hz > batas_atas:
            status = '⚠ Tinggi'
        else:
            status = '✓ Normal'

        ws.append([
            i,
            waktu_lokal.strftime('%Y-%m-%d'),
            waktu_lokal.strftime('%H:%M'),
            hz,
            status,
        ])

        # Warna baris abnormal
        if hz is not None and (hz < batas_bawah or hz > batas_atas):
            for col in range(1, 6):
                ws.cell(i + 1, col).fill = PatternFill('solid', fgColor='2D1A1A')

        for col in range(1, 6):
            ws.cell(i + 1, col).border = border
            ws.cell(i + 1, col).alignment = center

    # Summary baris terakhir
    if rows.exists():
        hz_vals = [r.hz for r in rows if r.hz is not None]
        if hz_vals:
            ws.append([])
            ws.append(['', '', 'Rata-rata', round(sum(hz_vals)/len(hz_vals), 4), ''])
            ws.append(['', '', 'Minimum',   round(min(hz_vals), 4), ''])
            ws.append(['', '', 'Maksimum',  round(max(hz_vals), 4), ''])
            abnormal = sum(1 for h in hz_vals if h < batas_bawah or h > batas_atas)
            ws.append(['', '', 'Abnormal',  abnormal, f'dari {len(hz_vals)} data'])

    # Response
    filename = f'Frekuensi_{tanggal}.xlsx'
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def export_beban(request):
    """
    Download rekap beban kit harian dari PostgreSQL (SnapLive).
    ?tanggal=YYYY-MM-DD  (default: hari ini)
    Format: Excel (.xlsx)
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from django.db.models import Sum
    from django.http import HttpResponse

    tanggal_str = request.GET.get('tanggal', '')
    try:
        tanggal = datetime.date.fromisoformat(tanggal_str)
    except ValueError:
        tanggal = timezone.now().astimezone(timezone.get_current_timezone()).date()

    tz_local = timezone.get_current_timezone()

    # Beban total per menit (sum semua pembangkit)
    rows = (SnapLive.objects
            .filter(waktu__date=tanggal)
            .values('waktu')
            .annotate(total_mw=Sum('mw'))
            .order_by('waktu'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'Beban {tanggal}'

    hdr_fill = PatternFill('solid', fgColor='0F172A')
    hdr_font = Font(bold=True, color='34D399', size=10)
    thin     = Side(style='thin', color='1E293B')
    border   = Border(left=thin, right=thin, top=thin, bottom=thin)
    center   = Alignment(horizontal='center', vertical='center')

    headers = ['No', 'Tanggal', 'Waktu', 'Total Beban (MW)']
    ws.append(headers)
    for col, _ in enumerate(headers, 1):
        cell = ws.cell(1, col)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.border = border
        cell.alignment = center

    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 18

    for i, row in enumerate(rows, 1):
        waktu_lokal = row['waktu'].astimezone(tz_local)
        mw = round(row['total_mw'], 2) if row['total_mw'] is not None else None
        ws.append([i, waktu_lokal.strftime('%Y-%m-%d'), waktu_lokal.strftime('%H:%M'), mw])
        for col in range(1, 5):
            ws.cell(i + 1, col).border = border
            ws.cell(i + 1, col).alignment = center

    if rows:
        mw_vals = [r['total_mw'] for r in rows if r['total_mw'] is not None]
        if mw_vals:
            ws.append([])
            ws.append(['', '', 'Rata-rata', round(sum(mw_vals)/len(mw_vals), 2)])
            ws.append(['', '', 'Minimum',   round(min(mw_vals), 2)])
            ws.append(['', '', 'Maksimum',  round(max(mw_vals), 2)])

    filename = f'BebanKit_{tanggal}.xlsx'
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def api_hz(request):
    """Hz terkini — ringan, dipanggil tiap 1 detik dari dashboard."""
    hz = mssql.get_current_hz()
    return JsonResponse({'hz': hz})


@login_required
def api_freq(request):
    """
    Chart frekuensi sistem.
    ?mode=hari_ini  → rata-rata per menit sejak 00:00 (untuk chart Frekuensi Hari Ini)
    ?menit=N        → last N menit data per detik (default 10, maks 60)
    """
    if request.GET.get('mode') == 'hari_ini':
        rows = mssql.get_freq_hari_ini()
    else:
        try:
            menit = min(max(int(request.GET.get('menit', 10)), 1), 120)
        except (ValueError, TypeError):
            menit = 10
        rows = mssql.get_freq_trend(menit)
    return JsonResponse({'rows': rows})


@login_required
def api_beban(request):
    """
    Chart beban kit — seluruh hari ini (00:00 sampai sekarang, per menit).
    Sumber: PostgreSQL (SnapLive). Termasuk nilai beban puncak siang (12:00)
    dan malam (18:30) untuk ditampilkan di bawah chart.
    """
    from django.db.models import Sum

    tz_local = timezone.get_current_timezone()
    today    = timezone.now().astimezone(tz_local).date()

    snaps = (SnapLive.objects
             .filter(waktu__date=today)
             .values('waktu')
             .annotate(total_mw=Sum('mw'))
             .order_by('waktu'))
    if snaps.exists():
        rows = []
        puncak_siang = None  # MW pada 12:00
        puncak_malam = None  # MW pada 18:30
        for s in snaps:
            waktu_lokal = s['waktu'].astimezone(tz_local)
            ts = waktu_lokal.strftime('%H:%M')
            mw = round(s['total_mw'], 2) if s['total_mw'] is not None else None
            rows.append({'timestamp': ts, 'mw': mw})
            if ts == '12:00':
                puncak_siang = mw
            elif ts == '18:30':
                puncak_malam = mw
        return JsonResponse({
            'rows':          rows,
            'source':        'postgresql',
            'count':         len(rows),
            'puncak_siang':  puncak_siang,
            'puncak_malam':  puncak_malam,
        })

    # Fallback: MSSQL HIS_MEAS_KIT per 15 menit
    rows = mssql.get_beban_trend()
    return JsonResponse({'rows': rows, 'source': 'mssql', 'puncak_siang': None, 'puncak_malam': None})


@login_required
def api_ping(request):
    """Cek cepat TCP ke MSSQL host:1433. Selesai dalam maks ~2 detik."""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': 'Akses ditolak'}, status=403)

    host = getattr(settings, 'MSSQL_HOST', '') or '(kosong)'
    if host == '(kosong)':
        return JsonResponse({'tcp': 'SKIP', 'info': 'MSSQL_HOST belum diset di .env'})

    reachable, h, port = mssql._tcp_ping(host)
    return JsonResponse({
        'host': h,
        'port': port,
        'tcp':  'BERHASIL' if reachable else 'GAGAL',
        'info': 'Host reachable, lanjut cek /opsis/api/diagnose/' if reachable
                else 'Host tidak reachable — cek IP/hostname, firewall, atau pastikan SQL Server berjalan',
    })


@login_required
def api_history(request, pk):
    """
    JSON: historis MW/MVAR dari PostgreSQL (SnapLive) untuk chart trend.
    ?jam=1|6|24|168  (default 24; 168 = 7 hari)
    Data berasal dari collect_live management command, bukan MSSQL langsung.
    """
    p = get_object_or_404(Pembangkit, pk=pk)
    try:
        jam = int(request.GET.get('jam', 24))
        if jam not in (1, 6, 24, 168):
            jam = 24
    except (ValueError, TypeError):
        jam = 24

    since = timezone.now() - datetime.timedelta(hours=jam)
    snaps = (SnapLive.objects
             .filter(pembangkit=p, waktu__gte=since)
             .order_by('waktu')
             .values('waktu', 'mw', 'mvar', 'frekuensi'))

    return JsonResponse({
        'nama':  p.nama,
        'warna': p.warna,
        'jam':   jam,
        'count': snaps.count(),
        'rows': [
            {
                'timestamp': s['waktu'].astimezone(timezone.get_current_timezone()).strftime('%H:%M'),
                'mw':        s['mw'],
                'mvar':      s['mvar'],
                'frekuensi': s['frekuensi'],
            }
            for s in snaps
        ]
    })


@login_required
def api_diagnose(request):
    """
    Endpoint diagnostik — cek koneksi MSSQL dan query data.
    Buka: /opsis/api/diagnose/
    Hanya superuser atau staff yang bisa akses.
    """
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': 'Akses ditolak'}, status=403)

    tbl = getattr(settings, 'MSSQL_TABLE', 'dbo.HIS_MEAS_KIT')

    import time as _time

    result = {
        'config': {
            'MSSQL_HOST':  getattr(settings, 'MSSQL_HOST',  '') or '(kosong)',
            'MSSQL_DB':    getattr(settings, 'MSSQL_DB',    '') or '(kosong)',
            'MSSQL_USER':  getattr(settings, 'MSSQL_USER',  '') or '(kosong)',
            'MSSQL_TABLE': tbl,
            'MSSQL_PASS':  '***' if getattr(settings, 'MSSQL_PASS', '') else '(kosong)',
        },
        'timing':     {},
        'koneksi':    None,
        'b1_sample':  [],
        'pembangkit': [],
        'error':      None,
    }

    try:
        t0 = _time.monotonic()
        conn = mssql._get_connection()
        result['timing']['koneksi_ms'] = round((_time.monotonic() - t0) * 1000)
        result['koneksi'] = 'BERHASIL'
        cursor = conn.cursor()

        t0 = _time.monotonic()
        try:
            cursor.execute(
                f"SELECT TOP 20 B1, TIME FROM {tbl} WITH (NOLOCK) ORDER BY TIME DESC"
            )
            rows = cursor.fetchall()
            seen = {}
            for r in rows:
                k = r[0].strip() if r[0] else ''
                if k and k not in seen:
                    seen[k] = str(r[1])
            result['b1_sample'] = [{'B1': k, 'TIME': t} for k, t in seen.items()]
        except Exception as e:
            result['b1_sample'] = f'Error: {e}'
        result['timing']['b1_sample_ms'] = round((_time.monotonic() - t0) * 1000)

        pembangkit_list = _pembangkit_aktif()
        info_map = {p.kode: {'kode': p.kode, 'nama': p.nama} for p in pembangkit_list}

        t0 = _time.monotonic()
        for p in pembangkit_list:
            try:
                cursor.execute(
                    f"""
                    SELECT TOP 1 RTRIM(B1), RTRIM(B3), P, Q, TIME
                    FROM {tbl} WITH (NOLOCK)
                    WHERE B1 LIKE ?
                    ORDER BY TIME DESC
                    """,
                    (p.kode + '%',)
                )
                row = cursor.fetchone()
                if row:
                    info_map[p.kode]['max_time'] = str(row[4])
                    info_map[p.kode]['sample'] = {
                        'B1': row[0], 'B3': row[1], 'P': str(row[2]), 'Q': str(row[3]), 'TIME': str(row[4])
                    }
                else:
                    info_map[p.kode]['max_time'] = 'NULL — tidak ada data (cek apakah kode cocok dengan B1)'
            except Exception as e:
                info_map[p.kode]['error'] = str(e)
        result['timing']['pembangkit_ms'] = round((_time.monotonic() - t0) * 1000)

        result['pembangkit'] = list(info_map.values())
        conn.close()

    except Exception as e:
        result['koneksi'] = 'GAGAL'
        result['error']   = str(e)

    return JsonResponse(result, json_dumps_params={'indent': 2})


@login_required
def rangkuman(request):
    """
    Rangkuman harian sistem: beban puncak, frekuensi, durasi abnormal.
    ?periode=kemarin|minggu|bulan
    """
    from django.db.models import Sum, Avg, Max, Min, Count, Case, When, IntegerField
    from django.db.models.functions import TruncDate
    from collections import defaultdict

    tz_local   = timezone.get_current_timezone()
    today      = timezone.now().astimezone(tz_local).date()
    periode    = request.GET.get('periode', 'kemarin')

    if periode == 'minggu':
        start_date = today - datetime.timedelta(days=7)
        end_date   = today - datetime.timedelta(days=1)
    elif periode == 'bulan':
        start_date = today - datetime.timedelta(days=30)
        end_date   = today - datetime.timedelta(days=1)
    else:
        periode    = 'kemarin'
        start_date = today - datetime.timedelta(days=1)
        end_date   = today - datetime.timedelta(days=1)

    # ── Beban: totalisasi per menit, lalu agregat per hari di Python ─
    per_minute = list(
        SnapLive.objects
        .filter(waktu__date__range=(start_date, end_date))
        .values('waktu')
        .annotate(total_mw=Sum('mw'))
        .order_by('waktu')
    )
    daily_mw = defaultdict(list)
    for r in per_minute:
        if r['total_mw'] is None:
            continue
        day = r['waktu'].astimezone(tz_local).date()
        daily_mw[day].append((r['total_mw'], r['waktu'].astimezone(tz_local)))

    # ── Frekuensi: agregat per hari via ORM (efisien) ────────────────
    freq_daily = (
        SnapFreq.objects
        .filter(waktu__date__range=(start_date, end_date), hz__isnull=False)
        .annotate(tanggal=TruncDate('waktu', tzinfo=tz_local))
        .values('tanggal')
        .annotate(
            avg_hz=Avg('hz'),
            min_hz=Min('hz'),
            max_hz=Max('hz'),
            total_detik=Count('id'),
            abnormal=Count(Case(
                When(hz__lt=49.5, then=1),
                When(hz__gt=50.5, then=1),
                output_field=IntegerField(),
            )),
        )
        .order_by('tanggal')
    )
    freq_map = {r['tanggal']: r for r in freq_daily}

    # ── Gabungkan per hari ────────────────────────────────────────────
    all_dates = sorted(set(list(daily_mw.keys()) + list(freq_map.keys())))
    ringkasan = []
    for day in all_dates:
        entry = {'tanggal': day}

        records = daily_mw.get(day, [])
        if records:
            mw_vals       = [r[0] for r in records]
            pk_idx        = mw_vals.index(max(mw_vals))
            entry.update({
                'puncak_mw':    round(max(mw_vals), 2),
                'puncak_waktu': records[pk_idx][1].strftime('%H:%M'),
                'avg_mw':       round(sum(mw_vals) / len(mw_vals), 2),
                'min_mw':       round(min(mw_vals), 2),
                'data_menit':   len(records),
            })
        else:
            entry.update({'puncak_mw': None, 'puncak_waktu': None,
                          'avg_mw': None, 'min_mw': None, 'data_menit': 0})

        freq = freq_map.get(day, {})
        total_detik = freq.get('total_detik', 0)
        abnormal    = freq.get('abnormal', 0)
        entry.update({
            'avg_hz':         round(freq['avg_hz'], 3) if freq.get('avg_hz') else None,
            'min_hz':         round(freq['min_hz'], 3) if freq.get('min_hz') else None,
            'max_hz':         round(freq['max_hz'], 3) if freq.get('max_hz') else None,
            'abnormal_detik': abnormal,
            'abnormal_menit': round(abnormal / 60, 1) if abnormal else 0,
            'abnormal_pct':   round(abnormal / total_detik * 100, 2) if total_detik else 0,
        })
        ringkasan.append(entry)

    # ── Ringkasan keseluruhan periode ─────────────────────────────────
    puncak_list  = [r['puncak_mw']  for r in ringkasan if r.get('puncak_mw')]
    avg_mw_list  = [r['avg_mw']     for r in ringkasan if r.get('avg_mw')]
    avg_hz_list  = [r['avg_hz']     for r in ringkasan if r.get('avg_hz')]
    min_hz_list  = [r['min_hz']     for r in ringkasan if r.get('min_hz')]
    total_abnormal = sum(r.get('abnormal_detik', 0) for r in ringkasan)
    summary = {
        'puncak_mw':      max(puncak_list)                              if puncak_list else None,
        'avg_beban':      round(sum(avg_mw_list)/len(avg_mw_list), 2)  if avg_mw_list else None,
        'avg_hz':         round(sum(avg_hz_list)/len(avg_hz_list), 3)  if avg_hz_list else None,
        'min_hz':         min(min_hz_list)                              if min_hz_list else None,
        'total_abnormal': total_abnormal,
        'abnormal_menit': round(total_abnormal / 60, 1),
        'total_hari':     len(ringkasan),
    }

    pembangkit_list = _pembangkit_aktif()
    return render(request, 'opsis/rangkuman.html', {
        'pembangkit_list': pembangkit_list,
        'ringkasan':       ringkasan,
        'summary':         summary,
        'periode':         periode,
        'start_date':      start_date,
        'end_date':        end_date,
    })
