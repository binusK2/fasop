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


# ── RC (Remote Control) — baca scd_his_rc + resolve hasil dari scd_his_message ────
#
# scd_his_rc diisi OTOMATIS oleh trigger tr1_scd_his_message di OFDB tiap ada
# perintah CB/LBS (kolom datum_1/status_1/msgoperator terisi begitu perintah
# dikirim). Tapi penyelesaiannya (datum_2/status_2/cek_remote = apakah perintah
# itu BERHASIL/GAGAL) seharusnya diisi oleh job up2bmakassar/apps/tasks/jobs/
# scd_his_rc.py -- yang sudah lama mati (apps.tasks di-comment). FASOP membaca
# scd_his_rc read-only lalu menyelesaikan sendiri yang masih kosong, TANPA
# menulis balik ke OFDB -- hasilnya disimpan di model RemoteControl (Postgres).

def get_rc_events(cursor, dt_start, dt_end):
    """
    RC yang diperintahkan (datum_1 dalam rentang) dari OFDB scd_his_rc.

    Kolom b1/b2/b3/elem di scd_his_rc TIDAK pernah diisi oleh trigger (cuma
    path1-5 kode mentah yang terisi) -- jadi label terbaca diambil lewat lookup
    ke scd_c_point berdasarkan kombinasi path1-5 (OUTER APPLY, fallback ke kode
    mentah kalau tidak ketemu match persis).
    """
    sql = """
        SELECT r.id_his_rc, r.path1, r.path2, r.path3, r.path4, r.path5,
               COALESCE(cp.path1text, r.path1) AS b1,
               COALESCE(cp.path2text, r.path2) AS b2,
               COALESCE(cp.path3text, r.path3) AS b3,
               COALESCE(cp.path4text, r.path4) AS elem,
               r.datum_1, r.status_1, r.datum_2, r.status_2, r.msgoperator, r.cek_remote
        FROM scd_his_rc r
        OUTER APPLY (
            SELECT TOP 1 path1text, path2text, path3text, path4text
            FROM scd_c_point c
            WHERE c.path1 = r.path1 AND c.path2 = r.path2 AND c.path3 = r.path3
                  AND c.path4 = r.path4 AND c.path5 = r.path5
        ) cp
        WHERE r.datum_1 >= ? AND r.datum_1 <= ?
        ORDER BY r.datum_1
    """
    cursor.execute(sql, [dt_start, dt_end])
    return cursor.fetchall()


def resolve_rc_result(cursor, path1, path2, path3, path4, path5, datum_1):
    """
    Cari hasil RC (BERHASIL/GAGAL) dari scd_his_message dalam +2 menit sejak datum_1.
    Portasi dari up2bmakassar apps/tasks/jobs/scd_his_rc.py: tag mengandung
    NE/RC/R*/MU dianggap respons; mengandung 'NE' = GAGAL, selain itu BERHASIL.
    Tidak ada respons dalam window = GAGAL (default, sama seperti aslinya).
    """
    sql = """
        SELECT TOP 1 tag, time_stamp, msec FROM scd_his_message
        WHERE path1=? AND path2=? AND path3=? AND path4=? AND path5=?
              AND time_stamp >= ? AND time_stamp <= DATEADD(MINUTE, 2, ?)
              AND (tag LIKE '%NE%' OR tag LIKE '%RC%' OR tag LIKE '%R*%' OR tag LIKE '%MU%')
        ORDER BY time_stamp
    """
    cursor.execute(sql, [path1, path2, path3, path4, path5, datum_1, datum_1])
    row = cursor.fetchone()
    if row:
        tag, time_stamp, msec = row
        status = 'GAGAL' if 'NE' in tag else 'BERHASIL'
        return time_stamp, msec or 0, status
    return datum_1, 999, 'GAGAL'
