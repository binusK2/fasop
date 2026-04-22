"""
Koneksi dan query ke MSSQL untuk data real-time pembangkit.

Struktur tabel:
  ID   — auto increment
  TIME — datetime timestamp
  B1   — nama pembangkit  (contoh: SUPPA5, BKARU5, TELLO_SW)
  B3   — nama unit/kit    (contoh: UNIT1_P, UNIT2_P)
  P    — daya aktif MW    (float, bisa NULL)
  Q    — daya reaktif MVAR (float, bisa NULL — untuk pengembangan selanjutnya)
  V, I — kolom lain (belum dipakai)

Satu pembangkit (B1) bisa punya banyak baris unit (B3) per timestamp.
Query menggunakan SUM(P)/SUM(Q) GROUP BY B1 agar total daya per pembangkit.

Env vars di .env server:
  MSSQL_HOST   = localhost
  MSSQL_DB     = nama_database
  MSSQL_USER   = username
  MSSQL_PASS   = password
  MSSQL_TABLE  = nama_tabel        ← SESUAIKAN dengan nama tabel aktual
  MSSQL_DRIVER = ODBC Driver 17 for SQL Server
"""
from django.conf import settings
import datetime


_DUMMY_MODE = False  # set True untuk paksa data dummy


def _tbl():
    """Nama tabel MSSQL — baca dari settings."""
    return getattr(settings, 'MSSQL_TABLE', 'dbo.HIS_MEAS_KIT')


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
    conn.timeout = 10  # query timeout 10 detik — gagal cepat jika query lambat
    return conn


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
    Return dict {kode: {mw, mvar, frekuensi, units, timestamp, is_dummy}}.

    Strategi: ambil timestamp terbaru per B1, lalu SUM(P)/SUM(Q) untuk
    semua unit (B3) pada timestamp tersebut.

    `kode` di model Pembangkit harus sama persis dengan nilai B1 di tabel.
    Contoh: Pembangkit.kode = 'SUPPA5'  ←→  B1 = 'SUPPA5'
    """
    if _DUMMY_MODE or not getattr(settings, 'MSSQL_HOST', ''):
        return _dummy_live(pembangkit_list)

    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        tbl    = _tbl()
        result = {}

        for p in pembangkit_list:
            if not p.aktif:
                continue

            # 1. Ambil timestamp terbaru untuk pembangkit ini
            cursor.execute(
                f"SELECT MAX(TIME) FROM {tbl} WHERE B1 LIKE ?",
                (p.kode + '%',)
            )
            row = cursor.fetchone()
            if not row or row[0] is None:
                result[p.kode] = {
                    'mw': None, 'mvar': None, 'frekuensi': None,
                    'units': [], 'timestamp': None, 'is_dummy': False,
                }
                continue

            latest_time = row[0]

            # 2. Ambil semua unit pada timestamp tersebut, hitung total P dan Q
            cursor.execute(
                f"""
                SELECT
                    SUM(P)    AS total_mw,
                    SUM(Q)    AS total_mvar,
                    MAX(TIME) AS ts,
                    STRING_AGG(B3 + '=' + CAST(ISNULL(P,0) AS VARCHAR), ', ')
                              AS unit_detail
                FROM {tbl}
                WHERE B1 LIKE ? AND TIME = ?
                """,
                (p.kode + '%', latest_time)
            )
            row = cursor.fetchone()

            mw   = float(row[0]) if row and row[0] is not None else None
            mvar = float(row[1]) if row and row[1] is not None else None
            ts   = row[2].isoformat() if row and row[2] else latest_time.isoformat()
            unit_detail = row[3] if row else ''

            result[p.kode] = {
                'mw':        mw,
                'mvar':      mvar,
                'frekuensi': None,   # kolom frekuensi belum tersedia
                'units':     unit_detail or '',
                'timestamp': ts,
                'is_dummy':  False,
            }

        conn.close()
        return result

    except Exception:
        return _dummy_live(pembangkit_list)


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

        cursor.execute(
            f"""
            SELECT
                CONVERT(VARCHAR(16), TIME, 120)  AS menit,
                SUM(P)                           AS total_mw,
                SUM(Q)                           AS total_mvar
            FROM {tbl}
            WHERE B1 LIKE ?
              AND TIME >= DATEADD(hour, ?, GETDATE())
              AND DATEPART(minute, TIME) % ? = 0
            GROUP BY CONVERT(VARCHAR(16), TIME, 120)
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
