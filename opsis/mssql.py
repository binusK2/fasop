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
import re

logger = logging.getLogger(__name__)


def _tbl():
    """Tabel historis HIS_MEAS_KIT — untuk trend chart."""
    return getattr(settings, 'MSSQL_TABLE', 'dbo.HIS_MEAS_KIT')

def _rt_tbl():
    """Tabel realtime KIT_REALTIME — untuk live dashboard."""
    return getattr(settings, 'MSSQL_RT_TABLE', 'dbo.KIT_REALTIME')

def _freq_tbl():
    """Tabel frekuensi SYS_FREQ_HIS — historian per detik (rekap/respon)."""
    return getattr(settings, 'MSSQL_FREQ_TABLE', 'dbo.SYS_FREQ_HIS')

def _freq_rt_tbl():
    """Tabel frekuensi REALTIME SYS_FREQ_RT — nilai terkini (dashboard)."""
    return getattr(settings, 'MSSQL_FREQ_RT_TABLE', 'dbo.SYS_FREQ_RT')

def _freq_rt_col():
    """Kolom nilai Hz pada tabel realtime (SYS_FREQ_RT.VALUE)."""
    return getattr(settings, 'MSSQL_FREQ_RT_COL', 'VALUE')

def _freq_rt_sql():
    """SELECT nilai Hz realtime terkini, terfilter tag (ANALOG='FREQ_MKS')."""
    col    = _freq_rt_col()
    keycol = getattr(settings, 'MSSQL_FREQ_RT_KEYCOL', 'ANALOG')
    key    = getattr(settings, 'MSSQL_FREQ_RT_KEY', 'FREQ_MKS')
    where  = f" WHERE RTRIM({keycol}) = '{key}'" if keycol and key else ''
    return f"SELECT TOP 1 {col} FROM {_freq_rt_tbl()} WITH (NOLOCK){where}"

def _trafo_tbl():
    """Tabel beban trafo ALL_TRANS_DATA."""
    return getattr(settings, 'MSSQL_TRAFO_TABLE', 'dbo.ALL_TRANS_DATA')

def _ktt_tbl():
    """Tabel beban KTT (konsumen tegangan tinggi) IND_LOAD."""
    return getattr(settings, 'MSSQL_KTT_TABLE', 'dbo.IND_LOAD')

def _dmp_tbl():
    """Tabel Daya Mampu KIT_DMP — sumber DMN (netto) & DMP (pasok)."""
    return getattr(settings, 'MSSQL_DMP_TABLE', 'dbo.KIT_DMP')

def _dmp_keycol():
    """Kolom kunci KIT_DMP yang dicocokkan dengan Pembangkit.dmp_source()."""
    return getattr(settings, 'MSSQL_DMP_KEYCOL', 'KIT')


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
    Ambil nilai Hz terkini dari SYS_FREQ_RT (tabel REALTIME, nilai terkini).
    Menggunakan persistent connection (tidak buat koneksi baru tiap detik).
    Reconnect otomatis jika koneksi putus.
    """
    global _hz_conn
    if not getattr(settings, 'MSSQL_HOST', ''):
        return None

    # tabel realtime = satu nilai terkini (tanpa history), terfilter tag
    sql = _freq_rt_sql()

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

        # ── Query 2: frekuensi sistem dari SYS_FREQ_RT (realtime) ───────
        frekuensi_sistem = None
        try:
            cursor.execute(_freq_rt_sql())
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
            -- ABS(P): sama seperti KIT_REALTIME (lihat get_live_data), sebagian unit
            -- terbaca minus akibat polaritas wiring CT/PT terbalik — bukan berarti
            -- unit itu menyerap daya. Q dibiarkan (arah reaktif masih relevan).
            SELECT menit,
                   SUM(ABS(P)) AS total_mw,
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
            -- ABS(P): sama seperti KIT_REALTIME (lihat get_live_data) — wiring
            -- CT/PT terbalik bikin sebagian unit terbaca minus.
            SELECT menit,
                   SUM(ABS(P)) AS total_mw
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

_COLUMN_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_TABLE_RE  = re.compile(r'^[A-Za-z_][A-Za-z0-9_\[\].]*$')


def _trafo_override_specs():
    """
    Daftar spesifikasi sumber data pengganti dari opsis.Trafo (field sumber_*).
    Hanya trafo aktif yang memakai override ikut dibaca. Return [] bila tidak ada.
    """
    from opsis.models import Trafo
    out = []
    for t in Trafo.objects.filter(aktif=True).exclude(sumber_tabel=''):
        spec = t.spesifikasi_override()
        if spec:
            out.append(spec)
    return out


def get_nilai_override(spec):
    """
    Ambil nilai p/q/v/i sebuah trafo dari TABEL SUMBER PENGGANTI
    (opsis.Trafo.sumber_*), dipakai saat titik berhenti update di ALL_TRANS_DATA
    (mis. IBT GITET Wotu) sementara nilainya masih hidup di tabel MSSQL lain.

    spec = dict dari Trafo.spesifikasi_override():
        mode         'baris' — satu titik per baris; filter_kolom dicocokkan dengan
                               Tag P/Q/V/I, nilai diambil dari kolom_nilai.
                     'kolom' — satu baris berisi kolom P/Q/V/I; filter_kolom dipilih
                               dengan filter_nilai.
        tabel        nama tabel MSSQL.
        filter_kolom kolom penanda titik (mode baris: kolom tag; mode kolom: kolom pemilih).
        filter_nilai hanya mode kolom — nilai yang dicari pada filter_kolom.
        kolom_nilai  hanya mode baris — kolom berisi angkanya (umumnya VALUE).
        p/q/v/i      mode baris: tag kunci titik; mode kolom: nama kolom. Kosong = None.

    Return dict site/bay/p/q/v/i, atau None bila tabel/kolom invalid atau query gagal.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return None

    tabel = (spec.get('tabel') or '').strip()
    if not _TABLE_RE.match(tabel):
        logger.error('get_nilai_override: nama tabel invalid %r', tabel)
        return None
    key_col = (spec.get('filter_kolom') or '').strip()
    if not _COLUMN_RE.match(key_col):
        logger.error('get_nilai_override: kolom kunci invalid %r', key_col)
        return None

    row = {
        'site': spec['key'][0],
        'bay':  spec['key'][1],
        'p': None, 'q': None, 'v': None, 'i': None,
    }

    conn = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        if spec.get('mode') == 'kolom':
            nilai = (spec.get('filter_nilai') or '').strip()
            if not nilai:
                conn.close()
                return None
            cols = []
            for met in ('p', 'q', 'v', 'i'):
                c = (spec.get(met) or '').strip()
                cols.append(c if _COLUMN_RE.match(c) else 'NULL')
            select = ', '.join(cols) or 'NULL'
            cursor.execute(
                f'SELECT TOP 1 {select} FROM {tabel} WITH (NOLOCK) WHERE RTRIM({key_col}) = ?',
                (nilai,),
            )
            vals = cursor.fetchone()
            if vals:
                for met, val in zip(('p', 'q', 'v', 'i'), vals):
                    row[met] = float(val) if val is not None else None
        else:  # mode baris — satu query per metrik yang tag-nya diisi
            kolom_nilai = (spec.get('kolom_nilai') or 'VALUE').strip()
            if not _COLUMN_RE.match(kolom_nilai):
                conn.close()
                return None
            for met, tag in (('p', spec['p']), ('q', spec['q']),
                             ('v', spec['v']), ('i', spec['i'])):
                if not tag:
                    continue
                cursor.execute(
                    f'SELECT TOP 1 {kolom_nilai} FROM {tabel} WITH (NOLOCK) '
                    f'WHERE RTRIM({key_col}) = ?',
                    (tag,),
                )
                val = cursor.fetchone()
                row[met] = float(val[0]) if val and val[0] is not None else None
        return row
    except Exception as e:
        logger.error('get_nilai_override(%s) error: %s', tabel, e, exc_info=True)
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _apply_override(rows):
    """
    Sisipkan hasil tabel sumber pengganti ke daftar baris ALL_TRANS_DATA.
    Baris (site, bay) yang punya override dihapus dan diganti nilai dari
    get_nilai_override(); trafo override yang sudah hilang dari ALL_TRANS_DATA
    tetap dimunculkan. Return rows apa adanya bila tidak ada override.
    """
    specs = _trafo_override_specs()
    if not specs:
        return rows

    keys = {(s['key'][0], s['key'][1]) for s in specs}
    merged = [r for r in rows if (r['site'], r['bay']) not in keys]
    for s in specs:
        row = get_nilai_override(s)
        if row is not None:
            merged.append(row)
    merged.sort(key=lambda r: (r['site'], r['bay']))
    return merged


def get_beban_trafo():
    """
    Ambil data beban trafo DISTRIBUSI dari ALL_TRANS_DATA
    (BAY LIKE 'TRF52%' atau 'TRF42%'). Trafo IBT (transmisi) belum termasuk —
    akan jadi fitur terpisah nantinya.

    Trafo yang dikonfigurasi sumber pengganti (opsis.Trafo.sumber_tabel) dibaca
    dari tabel tersebut dan menggantikan baris ALL_TRANS_DATA-nya (lihat
    _apply_override/get_nilai_override).

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
        base = [
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
        return _apply_override(base)
    except Exception as e:
        logger.error('get_beban_trafo error: %s', e)
        return _apply_override([])  # override saja bila ALL_TRANS_DATA gagal


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
        base = [
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
        return _apply_override(base)
    except Exception as e:
        logger.error('get_beban_trafo_ibt error: %s', e)
        return _apply_override([])  # override saja bila ALL_TRANS_DATA gagal


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


# ── Daya Mampu (DMN / DMP) dari KIT_DMP ──────────────────────────────────────

def get_daya_mampu(pembangkit_list):
    """
    Ambil Daya Mampu Netto (DMN) dan Daya Mampu Pasok (DMP) tiap pembangkit
    dari tabel KIT_DMP.

    Nama kolom DMN/DMP tidak di-hardcode: tiap Pembangkit menentukan sendiri
    lewat field dmp_kolom_dmn / dmp_kolom_dmp (diisi dari site admin), sedang
    baris yang dibaca dipilih lewat dmp_source() vs kolom kunci KIT_DMP
    (MSSQL_DMP_KEYCOL, default KIT). Pembangkit yang belum dikonfigurasi
    (pakai_dmp() False) tidak ikut diquery.

    Return {kode: {'dmn': float|None, 'dmp': float|None}} — dict kosong bila
    MSSQL belum dikonfigurasi/tidak reachable atau tak ada yang dikonfigurasi.
    """
    targets = [p for p in pembangkit_list if p.aktif and p.pakai_dmp()]
    if not targets or not getattr(settings, 'MSSQL_HOST', ''):
        return {}

    tbl = _dmp_tbl()
    key_col = _dmp_keycol()
    if not _TABLE_RE.match(tbl) or not _COLUMN_RE.match(key_col):
        logger.error('get_daya_mampu: tabel/kolom kunci invalid (%r, %r)', tbl, key_col)
        return {}

    # Kumpulkan semua kolom valid yang dipakai — satu query untuk semua baris.
    kolom = set()
    for p in targets:
        for c in (p.dmp_kolom_dmn.strip(), p.dmp_kolom_dmp.strip()):
            if c and _COLUMN_RE.match(c):
                kolom.add(c)
    if not kolom:
        return {}

    kolom = sorted(kolom)
    conn = None
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT RTRIM({key_col}), {', '.join(kolom)} FROM {tbl} WITH (NOLOCK)"
        )
        rows = {}
        for row in cursor.fetchall():
            kunci = (row[0] or '').strip().upper()
            if not kunci:
                continue
            rows[kunci] = dict(zip(kolom, row[1:]))
        conn.close()
        conn = None
    except Exception as e:
        logger.error('get_daya_mampu error: %s', e, exc_info=True)
        return {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def _nilai(src, nama_kolom):
        nama_kolom = (nama_kolom or '').strip()
        if not nama_kolom or nama_kolom not in src:
            return None
        val = src[nama_kolom]
        try:
            return round(float(val), 3) if val is not None else None
        except (TypeError, ValueError):
            return None

    hasil = {}
    for p in targets:
        sumber = [rows[key] for key in p.dmp_sources() if key in rows]
        if not sumber:
            hasil[p.kode] = {'dmn': None, 'dmp': None}
            continue

        def _jumlah(kolom):
            nilai = [_nilai(src, kolom) for src in sumber]
            nilai = [val for val in nilai if val is not None]
            return round(sum(nilai), 3) if nilai else None

        hasil[p.kode] = {
            'dmn': _jumlah(p.dmp_kolom_dmn),
            'dmp': _jumlah(p.dmp_kolom_dmp),
        }
    return hasil


def probe_dmp(limit=20):
    """
    Diagnosa: daftar kolom + beberapa baris pertama KIT_DMP, untuk menentukan
    kolom mana yang harus diisi ke Pembangkit.dmp_kolom_dmn / dmp_kolom_dmp.

    Return {'tabel', 'kolom': [...], 'rows': [ {kolom: nilai} ], 'error': str|None}.
    """
    tbl = _dmp_tbl()
    if not getattr(settings, 'MSSQL_HOST', ''):
        return {'tabel': tbl, 'kolom': [], 'rows': [], 'error': 'MSSQL_HOST belum dikonfigurasi'}
    if not _TABLE_RE.match(tbl):
        return {'tabel': tbl, 'kolom': [], 'rows': [], 'error': 'Nama tabel invalid'}
    conn = None
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        cursor.execute(f'SELECT TOP {int(limit)} * FROM {tbl} WITH (NOLOCK)')
        kolom = [c[0] for c in cursor.description]
        rows  = [dict(zip(kolom, r)) for r in cursor.fetchall()]
        return {'tabel': tbl, 'kolom': kolom, 'rows': rows, 'error': None}
    except Exception as e:
        logger.error('probe_dmp error: %s', e)
        return {'tabel': tbl, 'kolom': [], 'rows': [], 'error': str(e)}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


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


# ── Respons Pembangkit (lookback historian) ───────────────────────────
def get_freq_range(t0, t1):
    """
    Frekuensi sistem per detik dari SYS_FREQ_HIS untuk rentang [t0, t1].
    Return list [(datetime_naive, hz)] terurut. Dipakai analisis Respons Kit.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return []
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        freq   = _freq_tbl()
        cursor.execute(
            f"SELECT TIME, F FROM {freq} WITH (NOLOCK) "
            f"WHERE TIME BETWEEN ? AND ? ORDER BY TIME",
            (t0, t1))
        rows = cursor.fetchall()
        conn.close()
        return [(r[0], float(r[1])) for r in rows if r[0] is not None and r[1] is not None]
    except Exception as e:
        logger.error('get_freq_range error: %s', e)
        return []


def get_kit_mw_range(pembangkit_list, t0, t1):
    """
    MW total per pembangkit per detik dari HIS_MEAS_KIT untuk rentang [t0, t1].

    pembangkit_list : iterable (nama, kode) — kode dicocokkan ke kolom B1
                      (pola LIKE, sama seperti get_trend_data).
    Return dict {nama: [(datetime, mw)]} per detik (dedup unit terbaru per B3
    lalu SUM(ABS(P)) antar unit; ABS mengikuti get_live_data/get_trend_data).
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return {}
    hasil = {}
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        tbl    = _tbl()
        for nama, kode in pembangkit_list:
            if not kode:
                continue
            cursor.execute(
                f"""
                WITH per_unit AS (
                    SELECT CONVERT(VARCHAR(19), TIME, 120) AS dtk,
                           RTRIM(B3) AS B3, P,
                           ROW_NUMBER() OVER (
                               PARTITION BY CONVERT(VARCHAR(19), TIME, 120), RTRIM(B3)
                               ORDER BY TIME DESC) AS rn
                    FROM {tbl} WITH (NOLOCK)
                    WHERE B1 LIKE ? AND TIME BETWEEN ? AND ?
                )
                SELECT dtk, SUM(ABS(P)) AS mw
                FROM per_unit WHERE rn = 1
                GROUP BY dtk ORDER BY dtk
                """,
                (kode + '%', t0, t1))
            seri = []
            for r in cursor.fetchall():
                if r[0] is None or r[1] is None:
                    continue
                try:
                    waktu = datetime.datetime.strptime(r[0], '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    continue
                seri.append((waktu, float(r[1])))
            if seri:
                hasil[nama] = seri
        conn.close()
    except Exception as e:
        logger.error('get_kit_mw_range error: %s', e)
    return hasil


def get_kit_unit_mw_range(pembangkit_list, t0, t1):
    """
    MW PER UNIT (bukan dijumlah) per detik dari HIS_MEAS_KIT untuk [t0, t1] —
    meniru Excel Respons Kit yang berbasis unit (UNIT1_P, UNIT2_P, …).

    pembangkit_list : iterable (nama, kode) — kode dicocokkan ke B1 (LIKE).
    Return dict {"<nama> · <B3>": [(datetime, mw)]} per detik.
    Tiap unit = satu nilai B3 (RTRIM), dedup baris terbaru per detik per B3.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return {}
    hasil = {}
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        tbl    = _tbl()
        for nama, kode in pembangkit_list:
            if not kode:
                continue
            cursor.execute(
                f"""
                WITH per_unit AS (
                    SELECT CONVERT(VARCHAR(19), TIME, 120) AS dtk,
                           RTRIM(B3) AS B3, P,
                           ROW_NUMBER() OVER (
                               PARTITION BY CONVERT(VARCHAR(19), TIME, 120), RTRIM(B3)
                               ORDER BY TIME DESC) AS rn
                    FROM {tbl} WITH (NOLOCK)
                    WHERE B1 LIKE ? AND TIME BETWEEN ? AND ?
                )
                SELECT dtk, B3, ABS(P) AS mw
                FROM per_unit WHERE rn = 1
                ORDER BY B3, dtk
                """,
                (kode + '%', t0, t1))
            for r in cursor.fetchall():
                if r[0] is None or r[2] is None:
                    continue
                b3 = (r[1] or '').strip()
                try:
                    waktu = datetime.datetime.strptime(r[0], '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    continue
                label = f'{nama} · {b3}' if b3 else nama
                hasil.setdefault(label, []).append((waktu, float(r[2])))
        conn.close()
    except Exception as e:
        logger.error('get_kit_unit_mw_range error: %s', e)
    return hasil


def probe_kit(kode, t0, t1, limit=40):
    """
    Diagnostik "bedah data": kembalikan info mentah HIS_MEAS_KIT untuk satu KIT.
    Return dict {units:[B3…], jumlah_baris, contoh:[(TIME,B3,P)…], resolusi_detik}.
    Dipakai command deteksi_respon --probe.
    """
    out = {'units': [], 'jumlah_baris': 0, 'contoh': [], 'resolusi_detik': None}
    if not getattr(settings, 'MSSQL_HOST', ''):
        return out
    try:
        conn = _get_connection(); cur = conn.cursor(); tbl = _tbl()
        cur.execute(
            f"SELECT DISTINCT RTRIM(B3) FROM {tbl} WITH (NOLOCK) "
            f"WHERE B1 LIKE ? AND TIME BETWEEN ? AND ? ORDER BY 1",
            (kode + '%', t0, t1))
        out['units'] = [(r[0] or '').strip() for r in cur.fetchall()]
        cur.execute(
            f"SELECT COUNT(*) FROM {tbl} WITH (NOLOCK) "
            f"WHERE B1 LIKE ? AND TIME BETWEEN ? AND ?",
            (kode + '%', t0, t1))
        out['jumlah_baris'] = cur.fetchone()[0]
        cur.execute(
            f"SELECT TOP ({int(limit)}) TIME, RTRIM(B3), P FROM {tbl} WITH (NOLOCK) "
            f"WHERE B1 LIKE ? AND TIME BETWEEN ? AND ? ORDER BY TIME DESC",
            (kode + '%', t0, t1))
        rows = cur.fetchall()
        out['contoh'] = [(str(r[0]), (r[1] or '').strip(), float(r[2]) if r[2] is not None else None)
                         for r in rows]
        # resolusi: beda waktu antar sampel 1 unit
        if out['units']:
            u0 = out['units'][0]
            cur.execute(
                f"SELECT TOP 30 TIME FROM {tbl} WITH (NOLOCK) "
                f"WHERE B1 LIKE ? AND RTRIM(B3)=? AND TIME BETWEEN ? AND ? ORDER BY TIME DESC",
                (kode + '%', u0, t0, t1))
            ts = [r[0] for r in cur.fetchall() if r[0] is not None]
            if len(ts) >= 2:
                gaps = [abs((ts[i] - ts[i+1]).total_seconds()) for i in range(len(ts)-1)]
                gaps = [g for g in gaps if g > 0]
                if gaps:
                    out['resolusi_detik'] = round(sum(gaps) / len(gaps), 1)
        conn.close()
    except Exception as e:
        logger.error('probe_kit error: %s', e)
    return out


def list_kit_codes(menit=10):
    """
    Bedah data: daftar kode B1 (KIT) yang benar-benar ada di HIS_MEAS_KIT pada
    N menit terakhir, beserta jumlah baris & contoh unit (B3). Juga waktu data
    terbaru (untuk cek kesegaran/zona waktu). Return dict.
    """
    out = {'max_time': None, 'kits': []}
    if not getattr(settings, 'MSSQL_HOST', ''):
        return out
    try:
        conn = _get_connection(); cur = conn.cursor(); tbl = _tbl()
        cur.execute(f"SELECT MAX(TIME) FROM {tbl} WITH (NOLOCK)")
        row = cur.fetchone()
        out['max_time'] = str(row[0]) if row and row[0] is not None else None
        cur.execute(
            f"""
            SELECT RTRIM(B1) AS b1, COUNT(*) AS c,
                   COUNT(DISTINCT RTRIM(B3)) AS n_unit, MAX(RTRIM(B3)) AS contoh_b3
            FROM {tbl} WITH (NOLOCK)
            WHERE TIME >= DATEADD(minute, -{int(menit)}, GETDATE())
            GROUP BY RTRIM(B1) ORDER BY b1
            """)
        out['kits'] = [((r[0] or '').strip(), r[1], r[2], (r[3] or '').strip())
                       for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        logger.error('list_kit_codes error: %s', e)
    return out


def get_all_kit_unit_mw_range(t0, t1, kits=None):
    """
    MW per UNIT untuk SEMUA KIT (atau subset `kits`) dari HIS_MEAS_KIT [t0,t1] —
    satu query, cakupan seperti Excel Respons Kit (semua pembangkit, per unit).

    Return dict {"<B1> · <B3>": [(datetime, mw)]} per detik (dedup terbaru per
    detik per (B1,B3); SUM tidak dilakukan — tiap unit terpisah).
    `kits` opsional: iterable kode B1 untuk membatasi.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return {}
    hasil = {}
    try:
        conn = _get_connection(); cur = conn.cursor(); tbl = _tbl()
        filt = ''
        params = [t0, t1]
        if kits:
            ph = ','.join('?' for _ in kits)
            filt = f' AND RTRIM(B1) IN ({ph})'
            params += list(kits)
        cur.execute(
            f"""
            WITH pu AS (
                SELECT CONVERT(VARCHAR(19), TIME, 120) AS dtk,
                       RTRIM(B1) AS b1, RTRIM(B3) AS b3, P,
                       ROW_NUMBER() OVER (
                           PARTITION BY CONVERT(VARCHAR(19), TIME, 120),
                                        RTRIM(B1), RTRIM(B3)
                           ORDER BY TIME DESC) AS rn
                FROM {tbl} WITH (NOLOCK)
                WHERE TIME BETWEEN ? AND ?{filt}
            )
            SELECT dtk, b1, b3, ABS(P) AS mw
            FROM pu WHERE rn = 1
            ORDER BY b1, b3, dtk
            """, params)
        for r in cur.fetchall():
            if r[0] is None or r[3] is None:
                continue
            try:
                waktu = datetime.datetime.strptime(r[0], '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                continue
            label = f"{(r[1] or '').strip()} · {(r[2] or '').strip()}"
            hasil.setdefault(label, []).append((waktu, float(r[3])))
        conn.close()
    except Exception as e:
        logger.error('get_all_kit_unit_mw_range error: %s', e)
    return hasil


def get_monitor_1h(kits=None):
    """
    Monitor Respons: frekuensi + total MW pembangkit selama 1 JAM terakhir
    (rata/agregat per menit) untuk chart di halaman /opsis/respon.

    Return dict:
      freq:  [(menit 'HH:MM', hz), …]
      mw:    [(menit 'HH:MM', total_mw), …]
      freq_now, mw_now, waktu (str)
    `kits` opsional: batasi total MW ke daftar kode B1 (mis. RESPON_PLANTS).
    """
    out = {'freq': [], 'mw': [], 'freq_now': None, 'mw_now': None, 'waktu': None}
    if not getattr(settings, 'MSSQL_HOST', ''):
        return out
    try:
        conn = _get_connection(); cur = conn.cursor()
        freq = _freq_tbl(); tbl = _tbl()

        # Frekuensi rata per menit, 1 jam terakhir
        cur.execute(
            f"""SELECT CONVERT(VARCHAR(16), TIME, 120) AS menit, AVG(F) AS hz
                FROM {freq} WITH (NOLOCK)
                WHERE TIME >= DATEADD(hour, -1, GETDATE())
                GROUP BY CONVERT(VARCHAR(16), TIME, 120) ORDER BY menit""")
        out['freq'] = [(r[0][11:16], round(float(r[1]), 3))
                       for r in cur.fetchall() if r[0] and r[1] is not None]

        # Total MW per menit (ambil sampel terbaru per unit per menit, lalu SUM)
        filt, params = '', []
        if kits:
            ph = ','.join('?' for _ in kits)
            filt = f' AND RTRIM(B1) IN ({ph})'
            params = list(kits)
        cur.execute(
            f"""WITH pu AS (
                    SELECT CONVERT(VARCHAR(16), TIME, 120) AS menit,
                           RTRIM(B1) AS b1, RTRIM(B3) AS b3, ABS(P) AS p,
                           ROW_NUMBER() OVER (
                               PARTITION BY CONVERT(VARCHAR(16), TIME, 120),
                                            RTRIM(B1), RTRIM(B3)
                               ORDER BY TIME DESC) AS rn
                    FROM {tbl} WITH (NOLOCK)
                    WHERE TIME >= DATEADD(hour, -1, GETDATE()){filt}
                )
                SELECT menit, SUM(p) FROM pu WHERE rn = 1
                GROUP BY menit ORDER BY menit""", params)
        out['mw'] = [(r[0][11:16], round(float(r[1]), 1))
                     for r in cur.fetchall() if r[0] and r[1] is not None]
        conn.close()

        if out['freq']:
            out['freq_now'] = out['freq'][-1][1]
        if out['mw']:
            out['mw_now'] = out['mw'][-1][1]
            out['waktu']  = out['mw'][-1][0]
    except Exception as e:
        logger.error('get_monitor_1h error: %s', e)
    return out


def get_freq_events_day(tanggal, ambang=0.2):
    """
    Deteksi menit-menit EKSURSI frekuensi pada satu hari — RINGAN: agregasi di
    SQL (MIN/MAX F per menit), hanya kembalikan menit yang melewati ambang.

    tanggal : datetime.date
    ambang  : deviasi (Hz) dari 50 agar dianggap eksursi.
    Return list [(menit 'YYYY-MM-DD HH:MM', fmin, fmax)] terurut.
    """
    if not getattr(settings, 'MSSQL_HOST', ''):
        return []
    try:
        conn = _get_connection(); cur = conn.cursor(); freq = _freq_tbl()
        lo = 50.0 - float(ambang); hi = 50.0 + float(ambang)
        cur.execute(
            f"""SELECT CONVERT(VARCHAR(16), TIME, 120) AS menit,
                       MIN(F) AS fmin, MAX(F) AS fmax
                FROM {freq} WITH (NOLOCK)
                WHERE TIME >= ? AND TIME < DATEADD(day, 1, ?)
                GROUP BY CONVERT(VARCHAR(16), TIME, 120)
                HAVING MIN(F) <= ? OR MAX(F) >= ?
                ORDER BY menit""",
            (tanggal, tanggal, lo, hi))
        return [(r[0], float(r[1]), float(r[2])) for r in cur.fetchall()
                if r[0] and r[1] is not None and r[2] is not None]
    except Exception as e:
        logger.error('get_freq_events_day error: %s', e)
        return []
    finally:
        try: conn.close()
        except Exception: pass


# ── Frekuensi REALTIME (SYS_FREQ_RT) — sumber baru dashboard ───────────
def get_current_hz_rt():
    """Nilai Hz terkini dari SYS_FREQ_RT (koneksi biasa; untuk collector)."""
    if not getattr(settings, 'MSSQL_HOST', ''):
        return None
    try:
        conn = _get_connection(); cur = conn.cursor()
        cur.execute(_freq_rt_sql())
        row = cur.fetchone(); conn.close()
        return float(row[0]) if row and row[0] is not None else None
    except Exception as e:
        logger.error('get_current_hz_rt error: %s', e)
        return None


def probe_freq_rt(limit=10):
    """Bedah data SYS_FREQ_RT: nama kolom + beberapa baris (verifikasi kolom Hz)."""
    out = {'tabel': _freq_rt_tbl(), 'kolom_dipakai': _freq_rt_col(),
           'kolom': [], 'contoh': []}
    if not getattr(settings, 'MSSQL_HOST', ''):
        return out
    try:
        conn = _get_connection(); cur = conn.cursor()
        cur.execute(f"SELECT TOP ({int(limit)}) * FROM {_freq_rt_tbl()} WITH (NOLOCK)")
        out['kolom'] = [d[0] for d in cur.description]
        out['contoh'] = [tuple(str(v) for v in row) for row in cur.fetchall()]
        conn.close()
    except Exception as e:
        logger.error('probe_freq_rt error: %s', e)
        out['error'] = str(e)
    return out
