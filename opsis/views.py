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
def api_ping(request):
    """Cek cepat TCP ke MSSQL host:1433. Selesai dalam maks ~2 detik."""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': 'Akses ditolak'}, status=403)

    host = getattr(settings, 'MSSQL_HOST', '') or '(kosong)'
    if host == '(kosong)':
        return JsonResponse({'tcp': 'SKIP', 'info': 'MSSQL_HOST belum diset di .env'})

    reachable = mssql._tcp_ping(host)
    return JsonResponse({
        'host': host,
        'port': 1433,
        'tcp':  'BERHASIL' if reachable else 'GAGAL',
        'info': 'Host reachable, lanjut cek /opsis/api/diagnose/' if reachable
                else 'Host tidak reachable — cek IP/hostname, firewall, atau pastikan SQL Server berjalan',
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

        # Cek semua pembangkit dalam 2 query bulk (bukan N×3 query per-pembangkit)
        pembangkit_list = _pembangkit_aktif()
        kode_list = [p.kode for p in pembangkit_list]
        info_map = {p.kode: {'kode': p.kode, 'nama': p.nama} for p in pembangkit_list}

        if kode_list:
            placeholders = ','.join('?' * len(kode_list))
            # Query 1: COUNT dan MAX(TIME) semua pembangkit sekaligus
            try:
                cursor.execute(
                    f"""
                    SELECT RTRIM(B1), COUNT(*) AS jml, MAX(TIME) AS max_time
                    FROM {tbl}
                    WHERE RTRIM(B1) IN ({placeholders})
                    GROUP BY RTRIM(B1)
                    """,
                    kode_list,
                )
                for row in cursor.fetchall():
                    kode = row[0]
                    if kode in info_map:
                        info_map[kode]['total_baris'] = row[1]
                        info_map[kode]['max_time'] = str(row[2]) if row[2] else 'NULL — tidak ada data'
            except Exception as e:
                for info in info_map.values():
                    info.setdefault('error', str(e))

            # Query 2: TOP 3 per pembangkit menggunakan ROW_NUMBER
            try:
                cursor.execute(
                    f"""
                    SELECT RTRIM(B1), RTRIM(B3), P, Q, TIME
                    FROM (
                        SELECT RTRIM(B1) AS B1, RTRIM(B3) AS B3, P, Q, TIME,
                               ROW_NUMBER() OVER (PARTITION BY RTRIM(B1) ORDER BY TIME DESC) AS rn
                        FROM {tbl}
                        WHERE RTRIM(B1) IN ({placeholders})
                    ) t
                    WHERE rn <= 3
                    ORDER BY B1, TIME DESC
                    """,
                    kode_list,
                )
                for row in cursor.fetchall():
                    kode = row[0]
                    if kode in info_map:
                        info_map[kode].setdefault('sample', []).append(
                            {'B1': row[0], 'B3': row[1], 'P': str(row[2]), 'Q': str(row[3]), 'TIME': str(row[4])}
                        )
            except Exception as e:
                for info in info_map.values():
                    info.setdefault('sample_error', str(e))

        result['pembangkit'] = list(info_map.values())

        conn.close()

    except Exception as e:
        result['koneksi'] = 'GAGAL'
        result['error']   = str(e)

    return JsonResponse(result, json_dumps_params={'indent': 2})
