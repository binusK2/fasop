from datetime import datetime, timedelta, time

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from . import ofdb
from .models import KinerjaAnalogHarian, KinerjaDigitalHarian, RemoteControl


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


# ── Kinerja RC — agregat dari RemoteControl (sudah di-resolve oleh sync_rc) ────────

@login_required
def kinerja_rc(request):
    today = timezone.localdate()

    def _p(name, default):
        raw = request.GET.get(name)
        if raw:
            try:
                return datetime.strptime(raw, '%Y-%m-%d').date()
            except ValueError:
                pass
        return default

    tanggal_dari = _p('tanggal_dari', today - timedelta(days=7))
    tanggal_sampai = _p('tanggal_sampai', today)
    if tanggal_sampai < tanggal_dari:
        tanggal_sampai = tanggal_dari
    q = request.GET.get('q', '').strip()

    from django.db.models import Count, Sum, Case, When, Value, IntegerField, Q
    from django.db.models.functions import Coalesce

    qs = RemoteControl.objects.filter(tanggal__gte=tanggal_dari, tanggal__lte=tanggal_sampai)
    if q:
        qs = qs.filter(Q(b1__icontains=q) | Q(b2__icontains=q) | Q(b3__icontains=q) | Q(elem__icontains=q))

    rows = (
        qs.values('b1', 'b2', 'b3', 'elem')
        .annotate(
            jumlah=Count('id'),
            sukses=Coalesce(Sum(Case(When(status_respon='BERHASIL', then=1), output_field=IntegerField())), 0),
            gagal=Coalesce(Sum(Case(When(status_respon='GAGAL', then=1), output_field=IntegerField())), 0),
        )
        .order_by('b1', 'b3', 'elem')
    )
    rows = list(rows)
    for r in rows:
        r['performance'] = round(r['sukses'] / r['jumlah'] * 100, 2) if r['jumlah'] else 0

    total_jumlah = sum(r['jumlah'] for r in rows)
    total_sukses = sum(r['sukses'] for r in rows)
    ringkasan = {
        'jumlah_bay': len(rows),
        'total_rc': total_jumlah,
        'total_sukses': total_sukses,
        'rata_rata': round(total_sukses / total_jumlah * 100, 2) if total_jumlah else 0,
    }

    return render(request, 'up2bmakassar/kinerja_rc.html', {
        'tanggal_dari': tanggal_dari, 'tanggal_sampai': tanggal_sampai, 'q': q,
        'rows': rows, 'ringkasan': ringkasan,
    })


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
    """
    Ambil SOE dari OFDB untuk rentang & filter. Return dict siap render/export.
    Query HANYA dijalankan kalau form sudah disubmit (ada param `cari`) -- saat
    pertama buka halaman (belum submit) tabel dibiarkan kosong supaya tidak
    langsung menarik ribuan baris.
    """
    dari, sampai = _soe_range(request)
    filters = {k: request.GET.get(k, '').strip() for k in ofdb.SOE_FILTER_COLUMNS}
    submitted = 'cari' in request.GET

    ctx = {
        'tanggal_dari': dari, 'tanggal_sampai': sampai,
        'filters': filters, 'submitted': submitted,
        'headers': ofdb.SOE_HEADERS, 'rows': [], 'truncated': False,
        'error': None, 'max_rows': ofdb.SOE_MAX_ROWS,
    }

    if not submitted:
        return ctx

    dt_start = datetime.combine(dari, time.min)
    dt_end = datetime.combine(sampai, time.max)

    try:
        conn = ofdb.get_connection()
    except Exception as e:
        ctx['error'] = f'Gagal konek OFDB: {e}'
        return ctx
    try:
        cursor = conn.cursor()
        rows, truncated = ofdb.query_soe(cursor, dt_start, dt_end, filters=filters)
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
