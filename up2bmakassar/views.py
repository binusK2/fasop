from datetime import datetime, timedelta, time

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from . import ofdb
from .models import KinerjaAnalogHarian, KinerjaDigitalHarian


def _parse_tanggal(request, default_days_back=1):
    raw = request.GET.get('tanggal')
    if raw:
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError:
            pass
    return timezone.localdate() - timedelta(days=default_days_back)


def _ringkasan(qs):
    """Rata-rata performance & jumlah titik dari satu queryset kinerja harian."""
    total = qs.count()
    if total == 0:
        return {'jumlah_titik': 0, 'rata_rata': 0, 'terbaik': None, 'terburuk': None}
    rata_rata = sum(r.performance for r in qs) / total
    terbaik = max(qs, key=lambda r: r.performance)
    terburuk = min(qs, key=lambda r: r.performance)
    return {'jumlah_titik': total, 'rata_rata': rata_rata, 'terbaik': terbaik, 'terburuk': terburuk}


@login_required
def dashboard(request):
    tanggal = timezone.localdate() - timedelta(days=1)
    ringkasan_analog = _ringkasan(KinerjaAnalogHarian.objects.filter(tanggal=tanggal))
    ringkasan_digital = _ringkasan(KinerjaDigitalHarian.objects.filter(tanggal=tanggal))
    return render(request, 'up2bmakassar/dashboard.html', {
        'tanggal': tanggal,
        'ringkasan_analog': ringkasan_analog,
        'ringkasan_digital': ringkasan_digital,
    })


def _kinerja_list(request, model, template):
    tanggal = _parse_tanggal(request)
    q = request.GET.get('q', '').strip()

    qs = model.objects.filter(tanggal=tanggal).order_by('path1', 'path2', 'path3')
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(path1__icontains=q) | Q(path2__icontains=q) | Q(path3__icontains=q)
            | Q(point_number__icontains=q)
        )

    ringkasan = _ringkasan(qs)

    return render(request, template, {
        'tanggal': tanggal,
        'q': q,
        'rows': qs,
        'ringkasan': ringkasan,
    })


@login_required
def kinerja_analog(request):
    return _kinerja_list(request, KinerjaAnalogHarian, 'up2bmakassar/kinerja_analog.html')


@login_required
def kinerja_digital(request):
    return _kinerja_list(request, KinerjaDigitalHarian, 'up2bmakassar/kinerja_digital.html')


# ── SOE Log — query on-demand read-only ke OFDB, tidak disimpan di PostgreSQL ──────

def _soe_range(request):
    """Parse tanggal_dari/tanggal_sampai (default: hari ini). Return (date_dari, date_sampai)."""
    today = timezone.localdate()

    def _p(name, default):
        raw = request.GET.get(name)
        if raw:
            try:
                return datetime.strptime(raw, '%Y-%m-%d').date()
            except ValueError:
                pass
        return default

    dari = _p('tanggal_dari', today)
    sampai = _p('tanggal_sampai', today)
    if sampai < dari:
        sampai = dari
    return dari, sampai


def _soe_fetch(request):
    """Ambil SOE dari OFDB untuk rentang & keyword. Return dict siap render/export."""
    dari, sampai = _soe_range(request)
    q = request.GET.get('q', '').strip()

    dt_start = datetime.combine(dari, time.min)
    dt_end = datetime.combine(sampai, time.max)

    ctx = {
        'tanggal_dari': dari, 'tanggal_sampai': sampai, 'q': q,
        'headers': ofdb.SOE_HEADERS, 'rows': [], 'truncated': False,
        'error': None, 'max_rows': ofdb.SOE_MAX_ROWS,
    }
    try:
        conn = ofdb.get_connection()
    except Exception as e:
        ctx['error'] = f'Gagal konek OFDB: {e}'
        return ctx
    try:
        cursor = conn.cursor()
        rows, truncated = ofdb.query_soe(cursor, dt_start, dt_end, q=q or None)
        ctx['rows'] = rows
        ctx['truncated'] = truncated
    except Exception as e:
        ctx['error'] = f'Gagal query SOE: {e}'
    finally:
        conn.close()
    return ctx


@login_required
def soe_log(request):
    if request.GET.get('export') == '1':
        return _soe_export(request)
    return render(request, 'up2bmakassar/soe_log.html', _soe_fetch(request))


def _soe_export(request):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    ctx = _soe_fetch(request)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'SOE Log'

    header_fill = PatternFill('solid', fgColor='1D4ED8')
    header_font = Font(bold=True, color='FFFFFF')
    for col, h in enumerate(ctx['headers'], start=1):
        c = ws.cell(row=1, column=col, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal='center')

    for r_idx, row in enumerate(ctx['rows'], start=2):
        for c_idx, val in enumerate(row, start=1):
            # kolom pertama (time_stamp) -> string rapi
            if c_idx == 1 and val is not None:
                val = val.strftime('%Y-%m-%d %H:%M:%S')
            ws.cell(row=r_idx, column=c_idx, value=val)

    for col in range(1, len(ctx['headers']) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18

    fname = f"soe_log_{ctx['tanggal_dari']}_sd_{ctx['tanggal_sampai']}.xlsx"
    resp = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    resp['Content-Disposition'] = f'attachment; filename="{fname}"'
    wb.save(resp)
    return resp
