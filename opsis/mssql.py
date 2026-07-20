"""
Koneksi dan query ke MSSQL untuk data pembangkit.

Tabel yang digunakan:
  HIS_MEAS_KIT  — historis per-unit (B1, B3, P, Q, TIME) → untuk trend chart
  KIT_REALTIME  — live per-KIT (KIT, UNIT1_P..UNIT8_P, TOTAL, DATE) → untuk live dashboard
  SYS_FREQ_HIS  — frekuensi sistem (ID, TIME, F) → untuk Frekuensi Sistem dashboard

Env vars di .env server:
  MSSQL_HOST     = host,port
  MSSQL_DB       = nama_database
  MSSQL_USER     = username
  MSSQL_PASS     = password
  MSSQL_TABLE    = dbo.HIS_MEAS_KIT
  MSSQL_RT_TABLE = dbo.KIT_REALTIME
  MSSQL_FREQ_TABLE = dbo.SYS_FREQ_HIS
  MSSQL_DRIVER   = ODBC Driver 17 for SQL Server
"""
from django.conf import settings
import datetime
import logging

logger = logging.getLogger(__name__)


def _tbl():
    """Tabel historis HIS_MEAS_KIT — untuk trend chart."""
    return getattr(settings, 'MSSQL_TABLE', 'dbo.HIS_MEAS_KIT')

def _rt_tbl():
    """Tabel realtime KIT_REALTIME — untuk live dashboard."""
    return getattr(settings, 'MSSQL_RT_TABLE', 'dbo.KIT_REALTIME')

def _freq_tbl():
    """Tabel frekuensi SYS_FREQ_HIS — untuk Frekuensi Sistem."""
    return getattr(settings, 'MSSQL_FREQ_TABLE', 'dbo.SYS_FREQ_HIS')

def _trafo_tbl():
    """Tabel beban trafo ALL_TRANS_DATA."""
    return getattr(settings, 'MSSQL_TRAFO_TABLE', 'dbo.ALL_TRANS_DATA')

def _ktt_tbl():
    """Tabel beban KTT (konsumen tegangan tinggi) IND_LOAD."""
    return getattr(settings, 'MSSQL_KTT_TABLE', 'dbo.IND_LOAD')


def _parse_host_port(host_setting, default_port=1433):
    """Parse 'host,port' atau 'host' dari setting MSSQL_HOST."""
    if ',' in host_setting:
        h, p = host_setting.rsplit(',', 1)
        return h.strip(), int(p.strip())
    return host_setting.strip(), default_port


def _tcp_ping(host_setting, timeout=2):
    """Cek apakah host reachable via TCP. Parse port dari 'host,port' jika ada."""
    import socket
    host, port = _parse_host_port(host_setting)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, host, port
    except OSError:
        return False, host, port


_reachable_cache = {'ok': False, 'ts': 0.0}
_REACHABLE_CACHE_TTL = 3  # detik — beberapa endpoint (api_hz, api_live) di-poll browser tiap 1-5 detik


def is_reachable(timeout=1.5):
    """
    Cek cepat apakah MSSQL_HOST terkonfigurasi & reachable (TCP ping saja,
    tanpa buka koneksi ODBC penuh). Hasil di-cache singkat (_REACHABLE_CACHE_TTL)
    supaya polling frekuensi tinggi dari browser tidak membuka TCP probe baru
    tiap request. Dipakai view untuk menandai 'terputus' di response JSON.
    """
    import time
    now = time.monotonic()
    if now - _reachable_cache['ts'] < _REACHABLE_CACHE_TTL:
        return _reachable_cache['ok']
    host = getattr(settings, 'MSSQL_HOST', '')
    ok = False
    if host:
        ok, _, _ = _tcp_ping(host, timeout=timeout)
    _reachable_cache['ok'] = ok
    _reachable_cache['ts'] = now
    return ok


def _get_connection():
    import pyodbc
    host = getattr(settings, 'MSSQL_HOST', 'localhost')
    ok, h, port = _tcp_ping(host)
    if not ok:
        raise ConnectionError(f"Host {h}:{port} tidak reachable (TCP timeout)")
    user = getattr(settings, 'MSSQL_USER', '')
    pwd  = getattr(settings, 'MSSQL_PASS', '')
    auth = f"UID={user};PWD={pwd};" if user else "Trusted_Connection=yes;"
    conn_str = (
        f"DRIVER={getattr(settings, 'MSSQL_DRIVER', 'ODBC Driver 17 for SQL Server')};"
        f"SERVER={host};"
        f"DATABASE={getattr(settings, 'MSSQL_DB', '')};"
        + auth +
        "Encrypt=no;TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, timeout=5)
    conn.timeout = 30  # query timeout 30 detik
    return conn


def _make_conn_str():
    """Build connection string dari settings (tanpa TCP ping)."""
    import pyodbc
    host = getattr(settings, 'MSSQL_HOST', '')
    if not host:
        return None, None
    h, port = _parse_host_port(host)
    user = getattr(settings, 'MSSQL_USER', '')
    pwd  = getattr(settings, 'MSSQL_PASS', '')
    auth = f"UID={user};PWD={pwd};" if user else "Trusted_Connection=yes;"
    conn_str = (
        f"DRIVER={getattr(settings, 'MSSQL_DRIVER', 'ODBC Driver 17 for SQL Server')};"
        f"SERVER={h},{port};"
        f"DATABASE={getattr(settings, 'MSSQL_DB', '')};"
        + auth +
        "Encrypt=no;TrustServerCertificate=yes;"
    )
    return conn_str, pyodbc


# Persistent connection untuk Hz polling 1 detik — di-share dalam satu proses
_hz_conn = None

def get_current_hz():
    """
    Ambil nilai Hz terkini dari SYS_FREQ_HIS.
    Menggunakan persistent connection (tidak buat koneksi baru tiap detik).
    Reconnect otomatis jika koneksi putus.
    """
    global _hz_conn
    if not getattr(settings, 'MSSQL_HOST', ''):
        return None

    freq = _freq_tbl()
    # WHERE TIME >= ... agar pakai index TIME, hindari full scan tabel besar
    sql  = f"SELECT TOP 1 F FROM {freq} WITH (NOLOCK) WHERE TIME >= DATEADD(minute, -5, GETDATE()) ORDER BY TIME DESC"

    # TCP ping sekali sebelum masuk loop — fail fast tanpa menunggu ODBC timeout
    host = getattr(settings, 'MSSQL_HOST', '')
    if not host:
        return None
    ok, _, _ = _tcp_ping(host, timeout=2)
    if not ok:
        return None

    for attempt in range(2):  # 1 retry jika koneksi mati
        try:
            if _hz_conn is None:
                conn_str, pyodbc = _make_conn_str()
                if conn_str is None:
                    return None
                _hz_conn = pyodbc.connect(conn_str, timeout=3)
                _hz_conn.timeout = 5
            cursor = _hz_conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            return float(row[0]) if row and row[0] is not None else None
        except Exception as e:
            logger.debug('get_current_hz attempt %d: %s', attempt + 1, e)
            try:
                _hz_conn.close()
            except Exception:
                pass
            _hz_conn = None  # force reconnect on next attempt
    return None


# ── Live data ─────────────────────────────────────────────────────────

def _kosong_live(pembangkit_list):
    """Struktur live 'terputus' (MSSQL belum dikonfigurasi / tidak reachable) — semua nilai None."""
    return {
        p.kode: {
            'mw': None, 'mvar': None, 'frekuensi': None,
            'units': [], 'timestamp': None,
        }
        for p in pembangkit_list
    }

def get_live_data(pembangkit_list):
    """
    Return {'data': {kode: {...}}, 'frekuensi_sistem': float|None}.

    Live MW/unit → KIT_REALTIME (satu baris per KIT, kolom UNIT1_P..UNIT8_P, TOTAL).
    Frekuensi sistem → SYS_FREQ_HIS (TOP 1 ORDER BY ID DESC).
    Trend tetap pakai HIS_MEAS_KIT via get_trend_data().
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return {'data': _kosong_live(pembangkit_list), 'frekuensi_sistem': None}

    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        rt     = _rt_tbl()
        freq   = _freq_tbl()

        # ── Query 1: live MW per KIT dari KIT_REALTIME ──────────────────
        cursor.execute(
            f"""
            SELECT KIT, DATE,
                   UNIT1_P, UNIT1_Q, UNIT2_P, UNIT2_Q,
                   UNIT3_P, UNIT3_Q, UNIT4_P, UNIT4_Q,
                   UNIT5_P, UNIT5_Q, UNIT6_P, UNIT6_Q,
                   UNIT7_P, UNIT7_Q, UNIT8_P, UNIT8_Q
            FROM {rt} WITH (NOLOCK)
            """
        )
        rt_rows = cursor.fetchall()

        # Proses per KIT: kumpulkan unit mentah (belum di-filter/sum) per baris KIT.
        # Filtering per unit dan penjumlahan dilakukan belakangan per Pembangkit,
        # karena satu baris KIT_REALTIME bisa dipecah antar beberapa Pembangkit
        # (lihat Pembangkit.kode_kit / unit_list).
        raw_rows = {}
        unit_cols = [  # (P_idx, Q_idx, nama)
            (2,  3,  'UNIT1'), (4,  5,  'UNIT2'),
            (6,  7,  'UNIT3'), (8,  9,  'UNIT4'),
            (10, 11, 'UNIT5'), (12, 13, 'UNIT6'),
            (14, 15, 'UNIT7'), (16, 17, 'UNIT8'),
        ]
        for row in rt_rows:
            kit = row[0].strip().upper() if row[0] else ''
            ts  = row[1].isoformat() if row[1] else None

            units_raw = {}
            for p_idx, q_idx, nama in unit_cols:
                # abs() P — sebagian unit terbaca minus akibat polaritas
                # wiring CT/PT terbalik, bukan berarti unit itu benar-benar
                # menyerap daya. Tanpa abs() ini, unit tsb ke-exclude dari
                # total (filter '> 0' di bawah) dan bikin total beban
                # pembangkit lebih rendah dari realisasi sebenarnya.
                p_ = abs(float(row[p_idx])) if row[p_idx] is not None else None
                q_ = float(row[q_idx]) if row[q_idx] is not None else None
                if p_ is not None:  # skip unit yang NULL (tidak aktif)
                    units_raw[nama] = {'mw': p_, 'mvar': q_}

            raw_rows[kit] = {'timestamp': ts, 'units_raw': units_raw}

        # ── Query 2: frekuensi sistem dari SYS_FREQ_HIS ─────────────────
        frekuensi_sistem = None
        try:
            cursor.execute(f"SELECT TOP 1 F FROM {freq} WITH (NOLOCK) WHERE TIME >= DATEADD(minute, -5, GETDATE()) ORDER BY TIME DESC")
            row = cursor.fetchone()
            if row and row[0] is not None:
                frekuensi_sistem = float(row[0])
        except Exception as e:
            logger.warning('Frekuensi sistem gagal diambil: %s', e)

        conn.close()

        # Cocokkan dengan kode pembangkit Django (case-insensitive), lalu filter unit
        # sesuai unit_list bila baris KIT dipakai bersama oleh >1 Pembangkit.
        data = {}
        for p in pembangkit_list:
            if not p.aktif:
                continue
            row = raw_rows.get(p.kit_source())
            if row is None:
                data[p.kode] = {
                    'mw': None, 'mvar': None, 'frekuensi': None,
                    'units': [], 'timestamp': None,
                }
                continue

            whitelist = p.unit_whitelist()
            units = []
            mw_total = mvar_total = 0.0
            has_mw = has_mvar = False
            for nama, vals in row['units_raw'].items():
                if whitelist is not None and nama not in whitelist:
                    continue
                units.append({'nama': nama, 'mw': vals['mw'], 'mvar': vals['mvar']})
                if vals['mw'] is not None and vals['mw'] > 0:
                    mw_total += vals['mw']
                    has_mw = True
                if vals['mvar'] is not None and vals['mvar'] > 0:
                    mvar_total += vals['mvar']
                    has_mvar = True
            units.sort(key=lambda u: u['nama'])

            data[p.kode] = {
                'mw':        round(mw_total, 3)   if has_mw   else None,
                'mvar':      round(mvar_total, 3) if has_mvar else None,
                'frekuensi': None,
                'units':     units,
                'timestamp': row['timestamp'],
            }

        return {'data': data, 'frekuensi_sistem': frekuensi_sistem}

    except Exception as e:
        logger.error('get_live_data error: %s', e, exc_info=True)
        return {'data': _kosong_live(pembangkit_list), 'frekuensi_sistem': None}


# ── Trend data (untuk chart) ──────────────────────────────────────────

def get_trend_data(pembangkit, jam=1):
    """
    Return list [{timestamp, mw, mvar, frekuensi}] untuk Chart.js.

    Grouping per menit (DATEPART) agar tidak terlalu banyak titik.
    `kode` di model Pembangkit harus sama dengan B1 di tabel.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return []

    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        tbl    = _tbl()

        # Interval titik: 1j→1 mnt, 6j→5 mnt, 24j→15 mnt
        interval_menit = {1: 1, 6: 5, 24: 15}.get(jam, 1)

        # Ambil nilai terbaru per B3 per menit → baru SUM antar unit
        # Tanpa ini, SUM menjumlahkan semua baris dalam satu menit (bisa puluhan)
        cursor.execute(
            f"""
            WITH per_unit AS (
                SELECT
                    CONVERT(VARCHAR(16), TIME, 120) AS menit,
                    RTRIM(B3) AS B3,
                    P, Q,
                    ROW_NUMBER() OVER (
                        PARTITION BY CONVERT(VARCHAR(16), TIME, 120), RTRIM(B3)
                        ORDER BY TIME DESC
                    ) AS rn
                FROM {tbl} WITH (NOLOCK)
                WHERE B1 LIKE ?
                  AND TIME >= DATEADD(hour, ?, GETDATE())
                  AND DATEPART(minute, TIME) % ? = 0
            )
            SELECT menit,
                   SUM(CASE WHEN P > 0 THEN P ELSE 0 END) AS total_mw,
                   SUM(CASE WHEN Q > 0 THEN Q ELSE 0 END) AS total_mvar
            FROM per_unit
            WHERE rn = 1
            GROUP BY menit
            ORDER BY menit
            """,
            (pembangkit.kode + '%', -jam, interval_menit)
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'timestamp': row[0],
                'mw':        float(row[1]) if row[1] is not None else None,
                'mvar':      float(row[2]) if row[2] is not None else None,
                'frekuensi': None,
            }
            for row in rows
        ]

    except Exception as e:
        logger.error('get_trend_data error: %s', e, exc_info=True)
        return []


# ── Frekuensi trend ───────────────────────────────────────────────────

def get_freq_trend(menit=10):
    """
    Return list [{timestamp, hz}] dari SYS_FREQ_HIS, N menit terakhir.
    Data per detik → menit×60 titik, diurutkan ascending untuk chart.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return []
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        freq   = _freq_tbl()
        titik  = int(menit) * 60  # int, aman di-embed langsung (TOP tidak terima parameter)
        # WHERE TIME >= ... agar pakai index TIME (hindari full scan tabel besar)
        # buffer +5 menit supaya hasil tidak kurang saat ada gap data
        buf = int(menit) + 5
        cursor.execute(
            f"""
            SELECT TOP ({titik}) TIME, F
            FROM {freq} WITH (NOLOCK)
            WHERE TIME >= DATEADD(minute, -{buf}, GETDATE())
            ORDER BY TIME DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {'timestamp': row[0].strftime('%H:%M:%S') if row[0] else '',
             'hz': float(row[1]) if row[1] is not None else None}
            for row in reversed(rows)
        ]
    except Exception as e:
        logger.error('get_freq_trend error: %s', e)
        return []


def get_freq_hari_ini():
    """
    Return list [{timestamp 'HH:MM', hz}] rata-rata per menit hari ini
    dari SYS_FREQ_HIS. Dipakai untuk chart Frekuensi Hari Ini di dashboard.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return []
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        freq   = _freq_tbl()
        # GROUP BY per menit (CONVERT varchar 5 → 'HH:MM'), AVG Hz per menit
        cursor.execute(
            f"""
            SELECT CONVERT(VARCHAR(5), TIME, 108) AS menit, AVG(F) AS avg_hz
            FROM {freq} WITH (NOLOCK)
            WHERE TIME >= CAST(CAST(GETDATE() AS DATE) AS DATETIME)
            GROUP BY CONVERT(VARCHAR(5), TIME, 108)
            ORDER BY menit
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {'timestamp': row[0], 'hz': float(row[1]) if row[1] is not None else None}
            for row in rows
        ]
    except Exception as e:
        logger.error('get_freq_hari_ini error: %s', e)
        return []


def get_freq_seconds(detik=70):
    """
    Ambil data frekuensi per detik dari SYS_FREQ_HIS untuk N detik terakhir.
    Return list of (datetime_naive, float_hz) — dipakai oleh collect_freq command.
    Menggunakan _get_connection() biasa (dengan TCP ping).
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return []
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        freq   = _freq_tbl()
        titik  = int(detik)
        buf    = titik + 10
        cursor.execute(
            f"""
            SELECT TOP ({titik}) TIME, F
            FROM {freq} WITH (NOLOCK)
            WHERE TIME >= DATEADD(second, -{buf}, GETDATE())
            ORDER BY TIME DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            (row[0], float(row[1]))          # (datetime_naive, hz)
            for row in rows
            if row[0] is not None and row[1] is not None
        ]
    except Exception as e:
        logger.error('get_freq_seconds error: %s', e)
        return []


# ── Beban total hari ini ──────────────────────────────────────────────

def get_beban_trend():
    """
    Return list [{timestamp 'HH:MM', mw}] SUM semua pembangkit hari ini,
    per 15 menit, dari HIS_MEAS_KIT.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return []
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        tbl    = _tbl()
        cursor.execute(
            f"""
            WITH per_unit AS (
                SELECT CONVERT(VARCHAR(16), TIME, 120) AS menit,
                       RTRIM(B1) AS B1, RTRIM(B3) AS B3, P,
                       ROW_NUMBER() OVER (
                           PARTITION BY CONVERT(VARCHAR(16), TIME, 120),
                                        RTRIM(B1), RTRIM(B3)
                           ORDER BY TIME DESC
                       ) AS rn
                FROM {tbl} WITH (NOLOCK)
                WHERE TIME >= CAST(CAST(GETDATE() AS DATE) AS DATETIME)
                  AND DATEPART(minute, TIME) % 15 = 0
            )
            SELECT menit,
                   SUM(CASE WHEN P > 0 THEN P ELSE 0 END) AS total_mw
            FROM per_unit
            WHERE rn = 1
            GROUP BY menit
            ORDER BY menit
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {'timestamp': row[0][11:16] if row[0] else '',   # 'YYYY-MM-DD HH:MM' → 'HH:MM'
             'mw': float(row[1]) if row[1] is not None else None}
            for row in rows
        ]
    except Exception as e:
        logger.error('get_beban_trend error: %s', e)
        return []



# ── Beban Trafo ──────────────────────────────────────────────────────

def get_beban_trafo():
    """
    Ambil data beban trafo DISTRIBUSI dari ALL_TRANS_DATA
    (BAY LIKE 'TRF52%' atau 'TRF42%'). Trafo IBT (transmisi) belum termasuk —
    akan jadi fitur terpisah nantinya.

    Returns:
        list of dict:
            site  : str  — nama GI
            bay   : str  — nama bay trafo (TRF52-1 dll)
            p     : float|None — beban aktif (MW)
            q     : float|None — beban reaktif (MVAR)
            v     : float|None — tegangan (kV)
            i     : float|None — arus (A)

    Dikelompokkan di view berdasarkan site.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return []

    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        tbl    = _trafo_tbl()
        cursor.execute(
            f"""
            SELECT RTRIM(SITE), RTRIM(BAY), P, Q, V, I
            FROM {tbl} WITH (NOLOCK)
            WHERE BAY LIKE 'TRF52%' OR BAY LIKE 'TRF42%'
            ORDER BY SITE, BAY
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'site': (row[0] or '').strip(),
                'bay':  (row[1] or '').strip(),
                'p':    float(row[2]) if row[2] is not None else None,
                'q':    float(row[3]) if row[3] is not None else None,
                'v':    float(row[4]) if row[4] is not None else None,
                'i':    float(row[5]) if row[5] is not None else None,
            }
            for row in rows
        ]
    except Exception as e:
        logger.error('get_beban_trafo error: %s', e)
        return []


def get_beban_trafo_ibt():
    """
    Ambil data beban trafo IBT (Inter Bus Transformer) dari ALL_TRANS_DATA
    (BAY LIKE 'TRF65%' atau 'TRF54%'). Tabel sama dengan Beban Trafo
    Distribusi, cuma titik BAY yang diambil beda.

    Returns: sama seperti get_beban_trafo() — list of dict site/bay/p/q/v/i.
    Dikelompokkan di view berdasarkan site.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return []

    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        tbl    = _trafo_tbl()
        cursor.execute(
            f"""
            SELECT RTRIM(SITE), RTRIM(BAY), P, Q, V, I
            FROM {tbl} WITH (NOLOCK)
            WHERE BAY LIKE 'TRF65%' OR BAY LIKE 'TRF54%'
            ORDER BY SITE, BAY
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'site': (row[0] or '').strip(),
                'bay':  (row[1] or '').strip(),
                'p':    float(row[2]) if row[2] is not None else None,
                'q':    float(row[3]) if row[3] is not None else None,
                'v':    float(row[4]) if row[4] is not None else None,
                'i':    float(row[5]) if row[5] is not None else None,
            }
            for row in rows
        ]
    except Exception as e:
        logger.error('get_beban_trafo_ibt error: %s', e)
        return []


# ── Beban KTT (Konsumen Tegangan Tinggi) ─────────────────────────────────────

def get_beban_ktt():
    """
    Ambil data beban semua konsumen tegangan tinggi dari IND_LOAD.

    Returns:
        list of dict:
            id     : int   — ID baris
            analog : str   — nama/kode konsumen (kolom ANALOG)
            value  : float|None — nilai beban (kolom VALUE)
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return []

    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        tbl    = _ktt_tbl()
        cursor.execute(
            f"""
            SELECT ID, RTRIM(ANALOG), VALUE
            FROM {tbl} WITH (NOLOCK)
            ORDER BY ANALOG
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'id':     row[0],
                'analog': (row[1] or '').strip(),
                'value':  float(row[2]) if row[2] is not None else None,
            }
            for row in rows
        ]
    except Exception as e:
        logger.error('get_beban_ktt error: %s', e)
        return []


# ── Frekuensi Area (Sultra / Baubau) ─────────────────────────────────────────

def _get_area_freq(table, site, bay):
    """
    Ambil nilai F terbaru dari tabel TRANS_xxx_RT untuk SITE dan BAY tertentu.
    Tabel RT biasanya menyimpan satu baris per titik ukur (realtime snapshot).
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return None
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT TOP 1 F FROM {table} WITH (NOLOCK) "
            "WHERE RTRIM(SITE) = ? AND RTRIM(BAY) = ?",
            (site, bay)
        )
        row = cursor.fetchone()
        conn.close()
        return float(row[0]) if row and row[0] is not None else None
    except Exception as e:
        logger.error('_get_area_freq %s error: %s', table, e)
        return None


def get_freq_sultra():
    """Frekuensi sistem Sultra dari TRANS_KDNEW5_RT (GI KENDARI NEW / COMMON)."""
    tbl = getattr(settings, 'MSSQL_FREQ_SULTRA_TABLE', 'dbo.TRANS_KDNEW5_RT')
    return _get_area_freq(tbl, 'GI KENDARI NEW', 'COMMON')


def get_freq_baubau():
    """Frekuensi sistem Baubau dari TRANS_BAUBAU5_RT (GI BAUBAU / COMMON)."""
    tbl = getattr(settings, 'MSSQL_FREQ_BAUBAU_TABLE', 'dbo.TRANS_BABAU5_RT')
    return _get_area_freq(tbl, 'GI BAUBAU', 'COMMON')


def get_freq_sulteng():
    """Frekuensi sistem Sulteng dari TRANS_TLISE5_RT (GI TALISE 150 / COMMON)."""
    tbl = getattr(settings, 'MSSQL_FREQ_SULTENG_TABLE', 'dbo.TRANS_TLISE5_RT')
    return _get_area_freq(tbl, 'GI TALISE 150', 'COMMON')


def get_freq_luwuk():
    """Frekuensi sistem Luwuk dari TRANS_LUWUK5_RT (GI LUWUK / COMMON)."""
    tbl = getattr(settings, 'MSSQL_FREQ_LUWUK_TABLE', 'dbo.TRANS_LUWUK5_RT')
    return _get_area_freq(tbl, 'GI LUWUK', 'COMMON')


# ─────────────────────────────────────────────────────────────────────────────
# RTU State — untuk device_mon app
# ─────────────────────────────────────────────────────────────────────────────

def get_rtu_state():
    """
    Ambil semua baris dari dbo.RTU_ALL_STATE.
    Returns list of (nama:str, state:str, state_sejak:datetime|None).
    state = 'UP' atau 'DOWN'.
    """
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT RTRIM(RTU), RTRIM(STATE), TIME "
            "FROM dbo.RTU_ALL_STATE WITH (NOLOCK) "
            "ORDER BY RTU"
        )
        rows = cursor.fetchall()
        conn.close()
        result = []
        for row in rows:
            nama        = (row[0] or '').strip()
            state       = (row[1] or '').strip().upper()
            state_sejak = row[2]   # datetime atau None
            if not nama:
                continue
            result.append((nama, state, state_sejak))
        return result
    except Exception as e:
        logger.error('get_rtu_state error: %s', e)
        return []
