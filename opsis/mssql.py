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


_DUMMY_MODE = False  # set True untuk paksa data dummy


def _tbl():
    """Tabel historis HIS_MEAS_KIT — untuk trend chart."""
    return getattr(settings, 'MSSQL_TABLE', 'dbo.HIS_MEAS_KIT')

def _rt_tbl():
    """Tabel realtime KIT_REALTIME — untuk live dashboard."""
    return getattr(settings, 'MSSQL_RT_TABLE', 'dbo.KIT_REALTIME')

def _freq_tbl():
    """Tabel frekuensi SYS_FREQ_HIS — untuk Frekuensi Sistem."""
    return getattr(settings, 'MSSQL_FREQ_TABLE', 'dbo.SYS_FREQ_HIS')


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
    if _DUMMY_MODE or not getattr(settings, 'MSSQL_HOST', ''):
        import random
        return round(50 + random.uniform(-0.1, 0.1), 3)

    freq = _freq_tbl()
    # WHERE TIME >= ... agar pakai index TIME, hindari full scan tabel besar
    sql  = f"SELECT TOP 1 F FROM {freq} WITH (NOLOCK) WHERE TIME >= DATEADD(minute, -5, GETDATE()) ORDER BY TIME DESC"

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


# ── Dummy data (saat MSSQL belum tersambung) ─────────────────────────

def _dummy_live(pembangkit_list):
    import random
    now = datetime.datetime.now().isoformat()
    result = {}
    for p in pembangkit_list:
        result[p.kode] = {
            'mw':       round(random.uniform(80, 250), 2),
            'mvar':     round(random.uniform(20, 80), 2),
            'frekuensi': None,
            'units':    [],
            'timestamp': now,
            'is_dummy':  True,
        }
    return result


def _dummy_trend(pembangkit, jam=1):
    import random
    now = datetime.datetime.now()
    points = min(jam * 60, 1440)  # maks 1 titik/menit
    result = []
    base_mw = random.uniform(100, 200)
    for i in range(points, 0, -1):
        t = now - datetime.timedelta(minutes=i)
        result.append({
            'timestamp': t.strftime('%H:%M'),
            'mw':    round(base_mw + random.uniform(-20, 20), 2),
            'mvar':  round(40 + random.uniform(-10, 10), 2),
            'frekuensi': None,
        })
    return result


# ── Live data ─────────────────────────────────────────────────────────

def get_live_data(pembangkit_list):
    """
    Return {'data': {kode: {...}}, 'frekuensi_sistem': float|None}.

    Live MW/unit → KIT_REALTIME (satu baris per KIT, kolom UNIT1_P..UNIT8_P, TOTAL).
    Frekuensi sistem → SYS_FREQ_HIS (TOP 1 ORDER BY ID DESC).
    Trend tetap pakai HIS_MEAS_KIT via get_trend_data().
    """
    if _DUMMY_MODE or not getattr(settings, 'MSSQL_HOST', ''):
        return {'data': _dummy_live(pembangkit_list), 'frekuensi_sistem': None}

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

        # Proses per KIT: bangun units list dari UNIT1..UNIT8
        db_map = {}
        unit_cols = [  # (P_idx, Q_idx, nama)
            (2,  3,  'UNIT1'), (4,  5,  'UNIT2'),
            (6,  7,  'UNIT3'), (8,  9,  'UNIT4'),
            (10, 11, 'UNIT5'), (12, 13, 'UNIT6'),
            (14, 15, 'UNIT7'), (16, 17, 'UNIT8'),
        ]
        for row in rt_rows:
            kit = row[0].strip().upper() if row[0] else ''
            ts  = row[1].isoformat() if row[1] else None

            units = []
            mw_total   = 0.0
            mvar_total = 0.0
            has_mw = has_mvar = False
            for p_idx, q_idx, nama in unit_cols:
                p_ = float(row[p_idx]) if row[p_idx] is not None else None
                q_ = float(row[q_idx]) if row[q_idx] is not None else None
                if p_ is not None:  # skip unit yang NULL (tidak aktif)
                    units.append({'nama': nama, 'mw': p_, 'mvar': q_})
                    if p_ > 0:      # total hanya dari unit yang menghasilkan (positif)
                        mw_total += p_
                        has_mw = True
                    if q_ is not None and q_ > 0:
                        mvar_total += q_
                        has_mvar = True

            db_map[kit] = {
                'mw':        round(mw_total, 3)   if has_mw   else None,
                'mvar':      round(mvar_total, 3) if has_mvar else None,
                'frekuensi': None,
                'units':     units,
                'timestamp': ts,
                'is_dummy':  False,
            }

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

        # Cocokkan dengan kode pembangkit Django (case-insensitive)
        data = {}
        for p in pembangkit_list:
            if not p.aktif:
                continue
            data[p.kode] = db_map.get(p.kode.strip().upper(), {
                'mw': None, 'mvar': None, 'frekuensi': None,
                'units': [], 'timestamp': None, 'is_dummy': False,
            })

        return {'data': data, 'frekuensi_sistem': frekuensi_sistem}

    except Exception as e:
        logger.error('get_live_data error: %s', e, exc_info=True)
        return {'data': _dummy_live(pembangkit_list), 'frekuensi_sistem': None}


# ── Trend data (untuk chart) ──────────────────────────────────────────

def get_trend_data(pembangkit, jam=1):
    """
    Return list [{timestamp, mw, mvar, frekuensi}] untuk Chart.js.

    Grouping per menit (DATEPART) agar tidak terlalu banyak titik.
    `kode` di model Pembangkit harus sama dengan B1 di tabel.
    """
    if _DUMMY_MODE or not getattr(settings, 'MSSQL_HOST', ''):
        return _dummy_trend(pembangkit, jam)

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

    except Exception:
        return _dummy_trend(pembangkit, jam)


# ── Frekuensi trend ───────────────────────────────────────────────────

def get_freq_trend(menit=10):
    """
    Return list [{timestamp, hz}] dari SYS_FREQ_HIS, N menit terakhir.
    Data per detik → menit×60 titik, diurutkan ascending untuk chart.
    """
    if _DUMMY_MODE or not getattr(settings, 'MSSQL_HOST', ''):
        import random
        now = datetime.datetime.now()
        return [
            {'timestamp': (now - datetime.timedelta(seconds=i)).strftime('%H:%M:%S'),
             'hz': round(50 + random.uniform(-0.1, 0.1), 3)}
            for i in range(menit * 60, 0, -1)
        ]
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
    if _DUMMY_MODE or not getattr(settings, 'MSSQL_HOST', ''):
        import random
        now = datetime.datetime.now()
        result = []
        t = now.replace(hour=0, minute=0, second=0, microsecond=0)
        while t <= now:
            result.append({'timestamp': t.strftime('%H:%M'),
                           'hz': round(50 + random.uniform(-0.15, 0.15), 3)})
            t += datetime.timedelta(minutes=1)
        return result
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
    if _DUMMY_MODE or not getattr(settings, 'MSSQL_HOST', ''):
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
    if _DUMMY_MODE or not getattr(settings, 'MSSQL_HOST', ''):
        import random
        now = datetime.datetime.now()
        result = []
        t = now.replace(hour=0, minute=0, second=0, microsecond=0)
        while t <= now:
            result.append({'timestamp': t.strftime('%H:%M'),
                           'mw': round(random.uniform(300, 600), 2)})
            t += datetime.timedelta(minutes=15)
        return result
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
