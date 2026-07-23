"""
Koneksi READ-ONLY ke OFDB (dbup2bmakasar) -- database offline SCADA milik
aplikasi up2bmakassar di 192.168.19.1. FASOP hanya membaca lewat user
'fasop_readonly' (db_datareader, DENY write eksplisit) -- tidak pernah menulis
ke OFDB dari modul ini.

Tabel yang dipakai (Fase 1):
  scd_c_point      -- master titik SCADA (kinerja=1, id_pointtype, point_type, path1..5)
  scd_his_analog   -- histori transisi status titik ANALOG (datum_1/2, kesimpulan)
  scd_his_digital  -- histori transisi status titik DIGITAL (datum_1/2, kesimpulan)

Env vars di .env server:
  OFDB_HOST   = host,port   (mis. 192.168.19.1,1433)
  OFDB_DB     = dbup2bmakasar
  OFDB_USER   = fasop_readonly
  OFDB_PASS   = ...
  OFDB_DRIVER = ODBC Driver 17 for SQL Server
"""
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def _parse_host_port(host_setting, default_port=1433):
    """Parse 'host,port' atau 'host' dari setting OFDB_HOST."""
    if ',' in host_setting:
        h, p = host_setting.rsplit(',', 1)
        return h.strip(), int(p.strip())
    return host_setting.strip(), default_port


def _tcp_ping(host_setting, timeout=2):
    """Cek apakah host reachable via TCP sebelum coba connect beneran."""
    import socket
    host, port = _parse_host_port(host_setting)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, host, port
    except OSError:
        return False, host, port


def get_connection():
    """Buka koneksi read-only ke OFDB. Raise ConnectionError kalau host tidak reachable."""
    import pyodbc
    host = getattr(settings, 'OFDB_HOST', '')
    if not host:
        raise ConnectionError("OFDB_HOST belum di-set di .env")
    ok, h, port = _tcp_ping(host)
    if not ok:
        raise ConnectionError(f"OFDB {h}:{port} tidak reachable (TCP timeout)")

    user = getattr(settings, 'OFDB_USER', '')
    pwd = getattr(settings, 'OFDB_PASS', '')
    conn_str = (
        f"DRIVER={getattr(settings, 'OFDB_DRIVER', 'ODBC Driver 17 for SQL Server')};"
        f"SERVER={h},{port};"
        f"DATABASE={getattr(settings, 'OFDB_DB', '')};"
        f"UID={user};PWD={pwd};"
        "Encrypt=no;TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, timeout=5)
    conn.timeout = 60  # agregasi harian bisa agak berat, kasih lebih longgar dari default opsis
    return conn


def get_all_kinerja_path1(cursor, point_type):
    """Semua PATH1 unik yang muncul di titik kinerja=1 untuk point_type tertentu (untuk seed SitePath1)."""
    sql = """
        SELECT DISTINCT path1 FROM scd_c_point
        WHERE kinerja=1 AND id_pointtype>0 AND point_type=? AND path1 IS NOT NULL AND path1 <> ''
    """
    cursor.execute(sql, [point_type])
    return [row[0] for row in cursor.fetchall()]


def get_kinerja_points(cursor, point_type, active_path1=None):
    """
    Daftar point_number yang perlu dihitung kinerjanya, beserta path1-3 untuk label.
    point_type: 'A' (analog) atau 'D' (digital) -- kolom scd_c_point.point_type.
    active_path1: kalau diisi (list), cuma titik dengan path1 di dalamnya yang diambil
    (dipakai untuk menyaring site lama/tidak relevan lewat admin SitePath1 di FASOP).
    None berarti tidak ada filter (ambil semua).
    """
    sql = """
        SELECT point_number, path1, path2, path3
        FROM scd_c_point
        WHERE kinerja=1 AND id_pointtype>0 AND point_type=?
    """
    params = [point_type]
    if active_path1 is not None:
        if not active_path1:
            return []
        placeholders = ','.join('?' for _ in active_path1)
        sql += f" AND path1 IN ({placeholders})"
        params.extend(active_path1)
    cursor.execute(sql, params)
    return cursor.fetchall()


def compute_point_kinerja(cursor, table, point_number, day_start, day_end):
    """
    Hitung (jumlah_transisi_valid, uptime_detik, performance_persen) untuk satu
    titik dalam rentang [day_start, day_end), dari tabel 'scd_his_analog' atau
    'scd_his_digital'. table harus berasal dari whitelist tetap, bukan input user.

    Portasi formula dari up2bmakassar deprecated/task/old/scd_kin_analog_harian.py:
    - Transisi VALID yang seluruhnya di dalam hari: dihitung penuh.
    - Transisi VALID yang menyeberang batas awal/akhir hari: dipotong pas di batas.
    - Titik tanpa transisi sama sekali di hari itu: fallback ke status VALID/INVALID
      terakhir sebelum hari itu (pengganti tabel snapshot terpisah di script lama --
      kita sudah punya seluruh histori transisi, jadi tidak perlu tabel snapshot baru).
    """
    if table not in ('scd_his_analog', 'scd_his_digital'):
        raise ValueError(f"Tabel tidak diizinkan: {table}")

    total_seconds = (day_end - day_start).total_seconds()

    # a) transisi VALID yang seluruhnya di dalam hari
    cursor.execute(f"""
        SELECT COUNT(*), SUM(DATEDIFF(SECOND, datum_1, datum_2))
        FROM {table}
        WHERE point_number=? AND kesimpulan='VALID' AND datum_1>=? AND datum_2<?
    """, [point_number, day_start, day_end])
    row = cursor.fetchone()
    jlh = row[0] or 0
    uptime = float(row[1] or 0)

    # b) transisi mulai sebelum hari, berakhir di dalam hari -> potong ke day_start
    cursor.execute(f"""
        SELECT TOP 1 datum_1, datum_2 FROM {table}
        WHERE point_number=? AND kesimpulan='VALID' AND datum_2>=? AND datum_2<?
        ORDER BY datum_2
    """, [point_number, day_start, day_end])
    row = cursor.fetchone()
    if row and row[0] < day_start:
        uptime += (row[1] - day_start).total_seconds()
        jlh += 1

    # c) transisi mulai di dalam hari, berakhir setelah hari -> potong ke day_end
    cursor.execute(f"""
        SELECT TOP 1 datum_1, datum_2 FROM {table}
        WHERE point_number=? AND kesimpulan='VALID' AND datum_1>=? AND datum_1<?
        ORDER BY datum_1 DESC
    """, [point_number, day_start, day_end])
    row = cursor.fetchone()
    if row and row[1] > day_end:
        uptime += (day_end - row[0]).total_seconds()
        jlh += 1

    # d) fallback: tidak ada transisi sama sekali menyentuh hari ini
    if uptime == 0:
        cursor.execute(f"""
            SELECT TOP 1 kesimpulan FROM {table}
            WHERE point_number=? AND datum_1 < ?
            ORDER BY datum_1 DESC
        """, [point_number, day_start])
        row = cursor.fetchone()
        if row and row[0] == 'VALID':
            uptime = total_seconds
            jlh = 1

    performance = (uptime / total_seconds * 100) if total_seconds else 0
    return jlh, uptime, performance


# ── SOE Log (query on-demand, TIDAK disimpan di PostgreSQL) ──────────────────────

# Kolom SOE yang ditampilkan/di-export. path1text..path5text = versi terbaca
# (B1/B2/B3/Element/Info) yang diisi trigger dari Oracle B1,B2,B3,ELEM,INFO.
SOE_COLUMNS = [
    'time_stamp', 'path1text', 'path2text', 'path3text', 'path4text', 'path5text',
    'msgstatus', 'value', 'tag', 'msgoperator', 'priority',
]

SOE_HEADERS = [
    'Tanggal', 'B1 (Stasiun)', 'B2 (Tegangan)', 'B3 (Bay)', 'Element', 'Info',
    'Status', 'Value', 'Tag', 'Operator', 'Prioritas',
]

# Batas keras jumlah baris per query supaya web tidak menarik jutaan baris sekaligus.
SOE_MAX_ROWS = 5000

# Filter per header -> kolom OFDB. Whitelist tetap, bukan input user langsung ke SQL.
SOE_FILTER_COLUMNS = {
    'b1': 'path1text',
    'b2': 'path2text',
    'b3': 'path3text',
    'element': 'path4text',
}


def query_soe(cursor, dt_start, dt_end, filters=None, limit=SOE_MAX_ROWS):
    """
    Ambil SOE log dari OFDB scd_his_message untuk rentang [dt_start, dt_end], read-only
    dan on-demand (tidak disimpan di PostgreSQL). Rentang tanggal WAJIB -- tanpa itu
    query bisa mengembalikan ratusan juta baris.

    filters: opsional dict {b1|b2|b3|element: nilai} -> LIKE %nilai% per kolom.
    Return (rows, truncated) -- truncated=True kalau hasil kena batas `limit`.
    """
    cols = ', '.join(SOE_COLUMNS)
    sql = f"""
        SELECT TOP {int(limit) + 1} {cols}
        FROM scd_his_message
        WHERE time_stamp >= ? AND time_stamp <= ?
    """
    params = [dt_start, dt_end]

    for key, val in (filters or {}).items():
        col = SOE_FILTER_COLUMNS.get(key)
        if col and val:
            sql += f" AND {col} LIKE ?"
            params.append(f'%{val}%')

    sql += " ORDER BY time_stamp DESC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    truncated = len(rows) > limit
    if truncated:
        rows = rows[:limit]
    return rows, truncated
