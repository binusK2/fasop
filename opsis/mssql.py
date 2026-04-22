"""
Koneksi dan query ke MSSQL untuk data real-time pembangkit.

Env vars yang dibutuhkan (di .env server):
  MSSQL_HOST   = localhost
  MSSQL_DB     = nama_database
  MSSQL_USER   = username
  MSSQL_PASS   = password
  MSSQL_DRIVER = ODBC Driver 17 for SQL Server

Fungsi get_live_data() dan get_trend_data() berisi placeholder query.
Sesuaikan dengan struktur tabel MSSQL aktual.
"""
from django.conf import settings
import datetime

_DUMMY_MODE = False  # set True jika ingin paksa data dummy tanpa koneksi


def _get_connection():
    import pyodbc
    conn_str = (
        f"DRIVER={getattr(settings, 'MSSQL_DRIVER', 'ODBC Driver 17 for SQL Server')};"
        f"SERVER={getattr(settings, 'MSSQL_HOST', 'localhost')};"
        f"DATABASE={getattr(settings, 'MSSQL_DB', '')};"
        f"UID={getattr(settings, 'MSSQL_USER', '')};"
        f"PWD={getattr(settings, 'MSSQL_PASS', '')};"
        "Encrypt=no;TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=5)


def _dummy_live(pembangkit_list):
    """Data dummy saat MSSQL belum terhubung."""
    import random, math
    now = datetime.datetime.now().isoformat()
    result = {}
    for p in pembangkit_list:
        result[p.kode] = {
            'frekuensi': round(50.0 + random.uniform(-0.05, 0.05), 3),
            'mw':        round(random.uniform(80, 200), 2),
            'mvar':      round(random.uniform(20, 80), 2),
            'timestamp': now,
            'is_dummy':  True,
        }
    return result


def _dummy_trend(pembangkit, jam=1):
    """Data trend dummy untuk chart."""
    import random
    now = datetime.datetime.now()
    points = jam * 60  # 1 titik per menit
    result = []
    for i in range(points, 0, -1):
        t = now - datetime.timedelta(minutes=i)
        result.append({
            'timestamp': t.strftime('%H:%M'),
            'frekuensi': round(50.0 + random.uniform(-0.08, 0.08), 3),
            'mw':        round(140 + random.uniform(-30, 30), 2),
            'mvar':      round(50  + random.uniform(-15, 15), 2),
        })
    return result


def get_live_data(pembangkit_list):
    """
    Return dict {kode: {frekuensi, mw, mvar, timestamp}}.

    TODO: sesuaikan query di bawah dengan struktur tabel MSSQL aktual.
    Contoh jika tabel bernama 'RealTimeData' dengan kolom TagName, Value, Timestamp:

        tags = {p.kode: (p.tag_frekuensi, p.tag_mw, p.tag_mvar) for p in pembangkit_list if p.aktif}
        placeholders = ','.join('?' * (len(tags) * 3))
        all_tags = [t for trio in tags.values() for t in trio]
        cursor.execute(f"SELECT TagName, Value, Timestamp FROM RealTimeData WHERE TagName IN ({placeholders})", all_tags)
        rows = cursor.fetchall()
        ...
    """
    if _DUMMY_MODE or not getattr(settings, 'MSSQL_HOST', ''):
        return _dummy_live(pembangkit_list)
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        result = {}
        now = datetime.datetime.now().isoformat()
        for p in pembangkit_list:
            if not p.aktif:
                continue
            # ── PLACEHOLDER QUERY ── ganti sesuai struktur MSSQL ──
            # Contoh: SELECT TOP 1 Value FROM HistorianTable WHERE TagName=? ORDER BY Timestamp DESC
            frekuensi = mw = mvar = None
            if p.tag_frekuensi:
                pass  # cursor.execute("SELECT ...", [p.tag_frekuensi])
            if p.tag_mw:
                pass  # cursor.execute("SELECT ...", [p.tag_mw])
            if p.tag_mvar:
                pass  # cursor.execute("SELECT ...", [p.tag_mvar])
            result[p.kode] = {
                'frekuensi': frekuensi,
                'mw':        mw,
                'mvar':      mvar,
                'timestamp': now,
                'is_dummy':  False,
            }
        conn.close()
        return result
    except Exception:
        return _dummy_live(pembangkit_list)


def get_trend_data(pembangkit, jam=1):
    """
    Return list [{timestamp, frekuensi, mw, mvar}] untuk chart.

    TODO: sesuaikan query dengan struktur tabel historian MSSQL.
    Contoh jika ada tabel HistorianData dengan kolom TagName, Value, Timestamp:

        since = datetime.datetime.now() - datetime.timedelta(hours=jam)
        cursor.execute(
            "SELECT Timestamp, Value FROM HistorianData WHERE TagName=? AND Timestamp >= ? ORDER BY Timestamp",
            [tag, since]
        )
    """
    if _DUMMY_MODE or not getattr(settings, 'MSSQL_HOST', ''):
        return _dummy_trend(pembangkit, jam)
    try:
        conn = _get_connection()
        # ── PLACEHOLDER — ganti sesuai struktur MSSQL ──
        conn.close()
        return _dummy_trend(pembangkit, jam)
    except Exception:
        return _dummy_trend(pembangkit, jam)
