from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from .models import Pembangkit
from . import mssql


def _pembangkit_aktif():
    return list(Pembangkit.objects.filter(aktif=True))


@login_required
def dashboard(request):
    pembangkit_list = _pembangkit_aktif()
    return render(request, 'opsis/dashboard.html', {
        'pembangkit_list': pembangkit_list,
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
    data = mssql.get_live_data(pembangkit_list)
    return JsonResponse({'data': data})


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
def api_diagnose(request):
    """
    Endpoint diagnostik — cek koneksi MSSQL dan query data.
    Buka: /opsis/api/diagnose/
    Hanya superuser atau staff yang bisa akses.
    """
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': 'Akses ditolak'}, status=403)

    tbl = getattr(settings, 'MSSQL_TABLE', 'dbo.HIS_MEAS_KIT')

    result = {
        'config': {
            'MSSQL_HOST':  getattr(settings, 'MSSQL_HOST',  '') or '(kosong)',
            'MSSQL_DB':    getattr(settings, 'MSSQL_DB',    '') or '(kosong)',
            'MSSQL_USER':  getattr(settings, 'MSSQL_USER',  '') or '(kosong)',
            'MSSQL_TABLE': tbl,
            'MSSQL_PASS':  '***' if getattr(settings, 'MSSQL_PASS', '') else '(kosong)',
        },
        'koneksi':    None,
        'b1_sample':  [],
        'pembangkit': [],
        'error':      None,
    }

    try:
        conn = mssql._get_connection()
        result['koneksi'] = 'BERHASIL'
        cursor = conn.cursor()

        # Cek nilai B1 yang ada di tabel (RTRIM agar bersih dari trailing spaces)
        try:
            cursor.execute(f"SELECT DISTINCT TOP 10 RTRIM(B1) FROM {tbl} ORDER BY RTRIM(B1)")
            result['b1_sample'] = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            result['b1_sample'] = f'Error: {e}'

        # Cek setiap pembangkit yang terdaftar
        for p in _pembangkit_aktif():
            info = {'kode': p.kode, 'nama': p.nama}
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {tbl} WHERE RTRIM(B1) = ?", (p.kode,))
                info['total_baris'] = cursor.fetchone()[0]

                cursor.execute(f"SELECT MAX(TIME) FROM {tbl} WHERE RTRIM(B1) = ?", (p.kode,))
                row = cursor.fetchone()
                info['max_time'] = str(row[0]) if row and row[0] else 'NULL — tidak ada data'

                cursor.execute(
                    f"SELECT TOP 3 RTRIM(B1), RTRIM(B3), P, Q, TIME FROM {tbl} WHERE RTRIM(B1) = ? ORDER BY TIME DESC",
                    (p.kode,)
                )
                info['sample'] = [
                    {'B1': r[0], 'B3': r[1], 'P': str(r[2]), 'Q': str(r[3]), 'TIME': str(r[4])}
                    for r in cursor.fetchall()
                ]
            except Exception as e:
                info['error'] = str(e)
            result['pembangkit'].append(info)

        conn.close()

    except Exception as e:
        result['koneksi'] = 'GAGAL'
        result['error']   = str(e)

    return JsonResponse(result, json_dumps_params={'indent': 2})
