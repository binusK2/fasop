"""
Koneksi READ-ONLY ke OFDB (dbup2bmakasar) -- database offline SCADA milik
aplikasi up2bmakassar di 192.168.19.1. FASOP hanya membaca lewat user
'fasop_readonly' (db_datareader, DENY write eksplisit) -- tidak pernah menulis
ke OFDB dari modul ini.

Tabel yang dipakai (Fase 1):
  scd_c_point      -- master titik SCADA (kinerja=1, id_pointtype, point_type, path1..5)
  scd_pointtype    -- jenis titik + induknya (TELEMETERING/TELESIGNAL/RTU/MASTER/...)
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


# ── Jenis kinerja SCADATEL (scd_pointtype) ──────────────────────────────────────
#
# PENTING: jenis kinerja di app up2bmakassar ditentukan oleh INDUK point type
# (scd_c_point.id_pointtype -> scd_pointtype.id_induk_pointtype), BUKAN oleh
# kolom scd_c_point.point_type ('A'/'D') saja. UI up2bmakassar mengirim
# id_induk_pointtype=15 untuk halaman Telemetering dan 21 untuk Telesignal,
# dan dashboard-nya memfilter lewat nama induk ('TELEMETERING', 'TELESIGNAL',
# 'RTU', 'MASTER', 'TELEKOMUNIKASI').
#
# Kalau kinerja dihitung hanya dengan point_type='D', titik RTU/MASTER/
# TELEKOMUNIKASI ikut terhitung sebagai Telesignal sehingga jumlah titik dan
# angka availability-nya beda jauh dengan app lama.

JENIS_TELEMETERING   = 'TELEMETERING'
JENIS_TELESIGNAL     = 'TELESIGNAL'
JENIS_RTU            = 'RTU'
JENIS_MASTER         = 'MASTER'
JENIS_TELEKOMUNIKASI = 'TELEKOMUNIKASI'

# jenis -> (point_type di scd_c_point, tabel histori transisinya)
JENIS_SUMBER = {
    JENIS_TELEMETERING:   ('A', 'scd_his_analog'),
    JENIS_TELESIGNAL:     ('D', 'scd_his_digital'),
    JENIS_RTU:            ('D', 'scd_his_digital'),
    JENIS_MASTER:         ('D', 'scd_his_digital'),
    JENIS_TELEKOMUNIKASI: ('D', 'scd_his_digital'),
}

JENIS_ANALOG  = [JENIS_TELEMETERING]
JENIS_DIGITAL = [JENIS_TELESIGNAL, JENIS_RTU, JENIS_MASTER, JENIS_TELEKOMUNIKASI]

TABEL_HISTORI = ('scd_his_analog', 'scd_his_digital')


def _cek_tabel(table):
    """Tabel histori harus dari whitelist tetap, bukan input user."""
    if table not in TABEL_HISTORI:
        raise ValueError(f"Tabel tidak diizinkan: {table}")
    return table


def _teks(nilai):
    """
    Rapikan nilai teks OFDB: buang spasi padding di kiri/kanan.

    PENTING untuk path1..path5. Kolom-kolom itu diisi oleh beberapa program dari
    era berbeda: syncoffline/points.py memecah C_POINT.POINT_NAME dari Oracle
    (kolom CHAR, jadi tiap potongan ikut membawa spasi padding -> 'PMONA6  ')
    sementara baris yang ditulis program lama sudah ter-trim ('PMONA6'). Di SQL
    Server keduanya dianggap sama karena '=' mengabaikan spasi ekor, tapi di
    Python tidak -- tanpa strip ini pencocokan titik lewat path gagal total
    padahal nama station/bay-nya identik.
    """
    return (nilai or '').strip()


def _nomor(nilai):
    """
    Samakan tipe point_number jadi int.

    Kolom point_number tidak selalu bertipe sama di semua tabel OFDB (ada yang
    INT, ada yang NUMERIC atau bahkan VARCHAR), sehingga pyodbc bisa mengembalikan
    int / Decimal / str untuk nilai yang sebenarnya sama. Tanpa normalisasi ini,
    pencocokan master titik dengan hasil query uptime bisa meleset total.
    """
    if nilai is None:
        return None
    try:
        return int(nilai)
    except (TypeError, ValueError):
        return nilai


def get_induk_pointtype_id(cursor, jenis):
    """
    id_pointtype dari INDUK point type dengan nama tertentu (mis. 'TELESIGNAL').
    Baris induk = yang id_induk_pointtype-nya NULL / menunjuk dirinya sendiri;
    itu yang diprioritaskan kalau ada beberapa baris bernama sama.
    """
    cursor.execute("""
        SELECT TOP 1 id_pointtype FROM scd_pointtype
        WHERE UPPER(LTRIM(RTRIM(name))) = ?
        ORDER BY CASE WHEN id_induk_pointtype IS NULL
                        OR id_induk_pointtype = id_pointtype THEN 0 ELSE 1 END,
                 id_pointtype
    """, [jenis.upper()])
    row = cursor.fetchone()
    return row[0] if row else None


# Dari mana daftar titik kinerja diambil:
#   'kinerja' -- scd_c_point.kinerja = 1, sama seperti app up2bmakassar. Benar
#                secara konsep, TAPI bergantung pada flag yang di-reset 0 oleh
#                syncoffline/points.py setiap kali sebuah titik berubah.
#   'berdata' -- semua titik jenis tersebut yang punya baris di scd_*_rtl, yaitu
#                titik yang benar-benar termonitor sekarang. Dipakai kalau flag
#                kinerja sudah tidak bisa dipercaya.
SUMBER_KINERJA = 'kinerja'
SUMBER_BERDATA = 'berdata'


def get_kinerja_points(cursor, jenis, abaikan_point_type=False, sumber=SUMBER_KINERJA):
    """
    Semua titik yang perlu dihitung kinerjanya untuk satu `jenis`
    (TELEMETERING/TELESIGNAL/RTU/MASTER/TELEKOMUNIKASI).

    Return list of dict: point_number, path1..path5, b1..b3, elem (versi terbaca
    dari pathXtext, fallback ke kode mentah), jenis.

    `sumber` = SUMBER_KINERJA (flag kinerja=1) atau SUMBER_BERDATA (punya baris
    di tabel realtime). Lihat catatan di atas.

    abaikan_point_type=True melepas syarat point_type='A'/'D' -- dipakai command
    diagnosa untuk melihat apakah ada titik yang induk point type-nya benar tapi
    point_type-nya tidak sesuai (histori transisinya ada di tabel yang lain).

    Filter site aktif/tidak (SitePath1) TIDAK dilakukan di SQL -- pemanggil yang
    menyaring di Python, supaya seed SitePath1 tetap melihat semua path1 yang ada.
    """
    if jenis not in JENIS_SUMBER:
        raise ValueError(f"Jenis kinerja tidak dikenal: {jenis}")
    point_type, table = JENIS_SUMBER[jenis]

    induk_id = get_induk_pointtype_id(cursor, jenis)
    if induk_id is None:
        return []

    sql = """
        SELECT p.point_number, p.path1, p.path2, p.path3, p.path4, p.path5,
               COALESCE(NULLIF(p.path1text, ''), p.path1) AS b1,
               COALESCE(NULLIF(p.path2text, ''), p.path2) AS b2,
               COALESCE(NULLIF(p.path3text, ''), p.path3) AS b3,
               COALESCE(NULLIF(p.path4text, ''), p.path4) AS elem
        FROM scd_c_point p
        JOIN scd_pointtype pt ON pt.id_pointtype = p.id_pointtype
        WHERE p.id_pointtype > 0
              AND COALESCE(pt.id_induk_pointtype, pt.id_pointtype) = ?
    """
    params = [induk_id]

    if sumber == SUMBER_BERDATA:
        _, tabel_rtl = TABEL_STATUS[table]
        sql += f' AND EXISTS (SELECT 1 FROM {tabel_rtl} r WHERE r.point_number = p.point_number)'
    else:
        sql += ' AND p.kinerja = 1'

    if not abaikan_point_type:
        sql += ' AND p.point_type = ?'
        params.append(point_type)

    cursor.execute(sql, params)

    points = []
    for row in cursor.fetchall():
        points.append({
            'point_number': _nomor(row[0]),
            'path1': _teks(row[1]), 'path2': _teks(row[2]), 'path3': _teks(row[3]),
            'path4': _teks(row[4]), 'path5': _teks(row[5]),
            'b1': _teks(row[6]), 'b2': _teks(row[7]), 'b3': _teks(row[8]), 'elem': _teks(row[9]),
            'jenis': jenis,
        })
    return points


# ── Perhitungan uptime harian ───────────────────────────────────────────────────
#
# Formula sama dengan up2bmakassar (deprecated/task/old/scd_kin_analog_harian.py):
# uptime = total durasi transisi kesimpulan='VALID' di dalam 1 hari, transisi yang
# menyeberang batas hari dipotong pas di batas. Bedanya di sini SEMUA titik dihitung
# dalam SATU query GROUP BY, bukan 4 query per titik seperti script lamanya --
# versi per-titik butuh puluhan ribu round-trip ke 192.168.19.1 dan praktis tidak
# pernah selesai (itu sebabnya tabel kinerja di FASOP kosong / halamannya blank).

def compute_kinerja_harian(cursor, table, day_start, day_end):
    """
    Hitung uptime semua titik sekaligus untuk rentang [day_start, day_end).
    Return dict {point_number: (jumlah_transisi_valid, uptime_detik)}.

    Transisi dianggap menyentuh hari kalau datum_1 < day_end DAN datum_2 > day_start,
    lalu dipotong (clamp) ke batas hari. Satu transisi yang menyeberang batas awal
    dan satu yang menyeberang batas akhir otomatis ikut terhitung sebagian --
    persis seperti langkah (b) dan (c) di script lama, tanpa query tambahan.

    datum_2 NULL = interval masih berjalan (belum ditutup), diperlakukan sebagai
    "sampai sekarang" -> dipotong ke day_end. Script lama membuang baris seperti
    ini (semua query-nya membandingkan datum_2), makanya titik yang statusnya
    tidak pernah berubah selalu keluar 0 dan harus ditolong tabel snapshot.
    """
    _cek_tabel(table)
    cursor.execute(f"""
        SELECT point_number,
               COUNT(*) AS jlh,
               SUM(DATEDIFF(SECOND,
                   CASE WHEN datum_1 < ? THEN ? ELSE datum_1 END,
                   CASE WHEN datum_2 IS NULL OR datum_2 > ? THEN ? ELSE datum_2 END)) AS uptime
        FROM {table}
        WHERE kesimpulan = 'VALID'
              AND datum_1 IS NOT NULL
              AND datum_1 < ? AND (datum_2 IS NULL OR datum_2 > ?)
        GROUP BY point_number
    """, [day_start, day_start, day_end, day_end, day_end, day_start])
    return {_nomor(row[0]): (row[1] or 0, float(row[2] or 0)) for row in cursor.fetchall()}


# ── Status titik saat tidak ada transisi di hari itu ────────────────────────────
#
# Baris di scd_his_* hanya ditulis kalau status titik BERUBAH. Titik yang sehat
# terus-menerus bisa tidak punya baris sama sekali untuk hari tertentu -- kalau
# dianggap 0 detik uptime, availability-nya jadi 0% padahal titiknya normal.
# Script up2bmakassar menutup celah ini lewat snapshot harian scd_*_rtl_hari.
# Kita pakai tiga sumber, dari yang paling akurat untuk tanggal itu:
#   1. scd_*_rtl_hari  -- snapshot status per tanggal (kalau job-nya masih jalan)
#   2. scd_his_*       -- kesimpulan transisi terakhir sebelum hari itu
#   3. scd_*_rtl       -- status realtime sekarang (paling kasar; hanya masuk akal
#                          untuk tanggal yang belum lama lewat)

TABEL_STATUS = {
    'scd_his_analog':  ('scd_analog_rtl_hari',  'scd_analog_rtl'),
    'scd_his_digital': ('scd_digital_rtl_hari', 'scd_digital_rtl'),
}


def _status_map(cursor, sql, params, sumber):
    """Jalankan query status; kalau tabelnya tidak ada di OFDB, kembalikan dict kosong."""
    try:
        cursor.execute(sql, params)
        return {_nomor(row[0]): _teks(row[1]).upper() for row in cursor.fetchall()}
    except Exception as e:
        logger.warning('OFDB: sumber status %s tidak terbaca (%s)', sumber, e)
        return {}


def get_status_snapshot(cursor, table, tanggal):
    """Status per titik dari snapshot harian scd_*_rtl_hari untuk `tanggal`."""
    _cek_tabel(table)
    tabel_hari, _ = TABEL_STATUS[table]
    return _status_map(
        cursor,
        f'SELECT point_number, kesimpulan FROM {tabel_hari} WHERE datum = ?',
        [tanggal], tabel_hari,
    )


def get_status_realtime(cursor, table):
    """Status realtime per titik dari scd_*_rtl (satu baris per titik)."""
    _cek_tabel(table)
    _, tabel_rtl = TABEL_STATUS[table]
    return _status_map(
        cursor,
        f'SELECT point_number, kesimpulan FROM {tabel_rtl}',
        [], tabel_rtl,
    )


def get_status_sebelum(cursor, table, day_start, lookback_days=90):
    """
    Kesimpulan (VALID/INVALID) transisi TERAKHIR sebelum day_start per titik,
    dibatasi `lookback_days` hari ke belakang supaya tidak scan seluruh histori.

    Return dict {point_number: kesimpulan}.
    """
    _cek_tabel(table)
    return _status_map(
        cursor,
        f"""
        SELECT point_number, kesimpulan FROM (
            SELECT point_number, kesimpulan,
                   ROW_NUMBER() OVER (PARTITION BY point_number ORDER BY datum_1 DESC) AS rn
            FROM {table}
            WHERE datum_1 < ? AND datum_1 >= DATEADD(DAY, ?, ?)
        ) t WHERE rn = 1
        """,
        [day_start, -abs(int(lookback_days)), day_start], table,
    )


def ringkasan_cakupan(cursor, point_type):
    """
    Diagnosa: untuk semua titik `point_type` di scd_c_point, berapa yang
    point_number-nya benar-benar ada di tabel histori transisi dan di tabel
    realtime -- dipecah per induk point type dan per flag kinerja.

    Pengecekan dilakukan di sisi SQL Server (EXISTS), jadi hasilnya tidak
    terpengaruh cara Python membandingkan tipe data point_number. Kalau kolom
    "ada_histori"/"ada_rtl" nol untuk jenis yang seharusnya termonitor, berarti
    masalahnya di isi OFDB (titik kinerja=1 menunjuk point_number yang tidak
    punya data), bukan di perhitungan FASOP.

    Return list of tuple (jenis, kinerja, titik, ada_histori, ada_rtl).
    """
    table = 'scd_his_analog' if point_type == 'A' else 'scd_his_digital'
    _, tabel_rtl = TABEL_STATUS[table]
    # EXISTS-nya harus dihitung di derived table dulu -- SQL Server menolak
    # SUM(CASE WHEN EXISTS (...)) langsung di SELECT yang ber-GROUP BY.
    cursor.execute(f"""
        SELECT jenis, kinerja, COUNT(*) AS titik,
               SUM(ada_histori) AS ada_histori, SUM(ada_rtl) AS ada_rtl
        FROM (
            SELECT COALESCE(ind.name, pt.name) AS jenis,
                   p.kinerja AS kinerja,
                   CASE WHEN EXISTS (SELECT 1 FROM {table} h
                                     WHERE h.point_number = p.point_number)
                        THEN 1 ELSE 0 END AS ada_histori,
                   CASE WHEN EXISTS (SELECT 1 FROM {tabel_rtl} r
                                     WHERE r.point_number = p.point_number)
                        THEN 1 ELSE 0 END AS ada_rtl
            FROM scd_c_point p
            JOIN scd_pointtype pt ON pt.id_pointtype = p.id_pointtype
            LEFT JOIN scd_pointtype ind ON ind.id_pointtype = pt.id_induk_pointtype
            WHERE p.point_type = ?
        ) t
        GROUP BY jenis, kinerja
        ORDER BY jenis, kinerja
    """, [point_type])
    return cursor.fetchall()


# Tabel OFDB + kolom waktunya, untuk mengukur sampai kapan tiap rantai data masih
# terisi. scd_sync_* adalah watermark milik syncoffline (Oracle 15.1 -> 19.1);
# kalau yang ini tertinggal jauh, berarti sinkronisasi dari Spectrum yang berhenti,
# bukan pengolahan di 19.1.
KESEGARAN_TABEL = [
    ('scd_sync_10_anat',        'system_time_stamp', 'watermark sync analog dari Spectrum'),
    ('scd_sync_11_digitalt',    'system_time_stamp', 'watermark sync digital dari Spectrum'),
    ('scd_his_10_anat_temp',    'system_time_stamp', 'data analog mentah hasil sync'),
    ('scd_his_11_digitalt_temp', 'system_time_stamp', 'data digital mentah hasil sync'),
    ('scd_c_point',             'last_update',       'master titik'),
    ('scd_analog_rtl',          'datum_1',           'status realtime analog'),
    ('scd_digital_rtl',         'datum_1',           'status realtime digital'),
    ('scd_his_analog',          'datum_1',           'transisi status analog'),
    ('scd_his_digital',         'datum_1',           'transisi status digital'),
    ('scd_analog_rtl_hari',     'datum',             'snapshot harian analog'),
    ('scd_digital_rtl_hari',    'datum',             'snapshot harian digital'),
    ('scd_his_message',         'time_stamp',        'SOE log'),
    ('scd_his_rc',              'datum_1',           'log RC'),
]


def kesegaran_ofdb(cursor):
    """
    Timestamp terbaru di tiap tabel OFDB -- untuk melihat rantai mana yang masih
    jalan dan mana yang sudah berhenti. Tabel yang tidak ada dilewati.

    Return list of (tabel, keterangan, nilai_terbaru | None, pesan_error | None).
    """
    hasil = []
    for tabel, kolom, keterangan in KESEGARAN_TABEL:
        try:
            cursor.execute(f'SELECT MAX({kolom}) FROM {tabel}')
            row = cursor.fetchone()
            hasil.append((tabel, keterangan, row[0] if row else None, None))
        except Exception as e:
            hasil.append((tabel, keterangan, None, str(e).split(']')[-1].strip()[:60]))
    return hasil


TITIK_KINERJA_KOLOM = [
    'point_number', 'jenis', 'pointtype', 'point_type', 'active', 'kinerja',
    'point_name', 'description',
    'path1', 'path2', 'path3', 'path4', 'path5',
    'path1text', 'path2text', 'path3text', 'path4text', 'path5text',
]


def get_titik_kinerja_semua(cursor):
    """
    SEMUA titik ber-flag kinerja=1 di scd_c_point, apa pun jenis & point_type-nya,
    lengkap dengan nama induk point type dan seluruh path/pathtext.

    Dipakai untuk mengarsipkan daftar titik kinerja sebelum ada perubahan di sisi
    OFDB. Flag `kinerja` di OFDB rapuh (di-reset 0 oleh syncoffline/points.py
    setiap titik berubah, dan barisnya bisa terhapus kalau titiknya tidak ada lagi
    di Spectrum), jadi arsip ini bisa jadi satu-satunya catatan titik mana saja
    yang dulu dinilai kinerjanya.
    """
    cursor.execute("""
        SELECT p.point_number,
               COALESCE(ind.name, pt.name) AS jenis,
               pt.name AS pointtype,
               p.point_type, p.active, p.kinerja,
               p.point_name, p.description,
               p.path1, p.path2, p.path3, p.path4, p.path5,
               p.path1text, p.path2text, p.path3text, p.path4text, p.path5text
        FROM scd_c_point p
        LEFT JOIN scd_pointtype pt ON pt.id_pointtype = p.id_pointtype
        LEFT JOIN scd_pointtype ind ON ind.id_pointtype = pt.id_induk_pointtype
        WHERE p.kinerja = 1
        ORDER BY COALESCE(ind.name, pt.name), p.path1, p.path2, p.path3, p.path4
    """)
    return cursor.fetchall()


def get_point_paths(cursor, point_type):
    """
    (point_number, kinerja, path1..path5) semua titik dengan point_type tersebut.
    Tabelnya kecil (ribuan baris), jadi pemetaan/analisisnya dikerjakan di Python.
    """
    cursor.execute("""
        SELECT point_number, kinerja, path1, path2, path3, path4, path5
        FROM scd_c_point WHERE point_type = ?
    """, [point_type])
    return [
        (_nomor(r[0]), r[1],
         (_teks(r[2]), _teks(r[3]), _teks(r[4]), _teks(r[5]), _teks(r[6])))
        for r in cursor.fetchall()
    ]


def get_point_berdata(cursor, table):
    """
    Set point_number yang benar-benar termonitor -- yaitu punya baris di tabel
    realtime (scd_*_rtl). Titik yang tidak ada di sini tidak akan pernah punya
    uptime berapa pun rentang tanggalnya.
    """
    _cek_tabel(table)
    _, tabel_rtl = TABEL_STATUS[table]
    try:
        cursor.execute(f'SELECT DISTINCT point_number FROM {tabel_rtl}')
        return {_nomor(r[0]) for r in cursor.fetchall()}
    except Exception as e:
        logger.warning('OFDB: %s tidak terbaca (%s)', tabel_rtl, e)
        return set()


def _kunci_path(key):
    """Kunci identitas titik dari tuple path, sudah dinormalisasi (strip + huruf besar)."""
    return tuple(_teks(x).upper() for x in key)


def _kunci_titik(p):
    """Kunci identitas titik dari dict hasil get_kinerja_points."""
    return _kunci_path((p['path1'], p['path2'], p['path3'], p['path4'], p['path5']))


def analisa_kecocokan_path(points, semua_point, berdata):
    """
    Diagnosa: berapa titik kinerja yang path-nya cocok dengan titik ber-data,
    pada beberapa tingkat kelonggaran (path1..5 penuh sampai path1 saja).

    Kalau bahkan pada level path1 (station/B1) tidak ada yang cocok, berarti
    penamaan di master titik lama sudah sama sekali berbeda dengan yang ada di
    data hidup -- pemetaan otomatis tidak mungkin, harus ditandai ulang manual.

    Return (hasil_per_level, contoh_kinerja, contoh_berdata).
    """
    hasil = {}
    for level in (5, 4, 3, 1):
        kunci = {_kunci_path(key)[:level] for pn, _k, key in semua_point if pn in berdata}
        hasil[level] = sum(1 for p in points if _kunci_titik(p)[:level] in kunci)
    contoh_kinerja = [
        (p['point_number'], (p['path1'], p['path2'], p['path3'], p['path4'], p['path5']))
        for p in points[:3]
    ]
    contoh_berdata = [(pn, key) for pn, _k, key in semua_point if pn in berdata][:3]
    return hasil, contoh_kinerja, contoh_berdata


def cari_kembaran(points, semua_point, berdata):
    """
    Cari pengganti untuk titik kinerja yang point_number-nya tidak punya data.

    Identitas logis sebuah titik adalah kombinasi path1..path5 (B1/B2/B3/Element/
    Info), bukan point_number-nya -- point_number bisa berubah kalau database
    Spectrum di-rebuild. Kalau titik kinerja=1 menunjuk point_number mati tapi ada
    titik lain dengan path yang sama persis dan punya data, titik itulah yang
    dipakai.

    Return (jumlah_dipetakan, jumlah_tidak_ketemu). `points` diubah di tempat:
    point_number diganti, point_number_asal menyimpan nilai lamanya.
    """
    kandidat = {}
    for pn, _kinerja, key in semua_point:
        key = _kunci_path(key)
        if pn in berdata and (key not in kandidat or pn > kandidat[key]):
            kandidat[key] = pn

    dipakai = {p['point_number'] for p in points if p['point_number'] in berdata}
    dipetakan = 0
    gagal = 0
    for p in points:
        if p['point_number'] in berdata:
            continue
        pengganti = kandidat.get(_kunci_titik(p))
        if pengganti is not None and pengganti not in dipakai:
            p['point_number_asal'] = p['point_number']
            p['point_number'] = pengganti
            dipakai.add(pengganti)
            dipetakan += 1
        else:
            gagal += 1
    return dipetakan, gagal


def contoh_point_number(cursor, table, limit=5):
    """Diagnosa: beberapa point_number contoh dari sebuah tabel OFDB, apa adanya."""
    if table not in TABEL_HISTORI and table not in [t for pair in TABEL_STATUS.values() for t in pair]:
        raise ValueError(f"Tabel tidak diizinkan: {table}")
    cursor.execute(f'SELECT DISTINCT TOP {int(limit)} point_number FROM {table} ORDER BY point_number')
    return [row[0] for row in cursor.fetchall()]


def get_status_awal_hari(cursor, table, tanggal, day_start, status_realtime=None):
    """
    Gabungan tiga sumber status di atas, prioritas: snapshot harian > transisi
    terakhir > realtime. Return dict {point_number: kesimpulan}.

    `status_realtime` boleh dioper dari luar (hasil get_status_realtime) supaya
    tidak diquery ulang untuk tiap tanggal saat backfill.
    """
    gabungan = dict(status_realtime if status_realtime is not None
                    else get_status_realtime(cursor, table))
    gabungan.update(get_status_sebelum(cursor, table, day_start))
    gabungan.update(get_status_snapshot(cursor, table, tanggal))
    return gabungan


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

    # Nilai teks dirapikan di sini juga: scd_his_rc mewarisi spasi padding dari
    # POINT_NAME Oracle, dan kalau dibiarkan, satu bay yang sama bisa terpecah
    # jadi dua baris rekap ('KDNEW5' vs 'KDNEW5  ') saat di-GROUP BY di Python.
    hasil = []
    for row in cursor.fetchall():
        (id_his_rc, path1, path2, path3, path4, path5, b1, b2, b3, elem,
         datum_1, status_1, datum_2, status_2, msgoperator, cek_remote) = row
        hasil.append((
            id_his_rc,
            _teks(path1), _teks(path2), _teks(path3), _teks(path4), _teks(path5),
            _teks(b1), _teks(b2), _teks(b3), _teks(elem),
            datum_1, _teks(status_1), datum_2, _teks(status_2),
            _teks(msgoperator), cek_remote,
        ))
    return hasil


def ringkasan_rc(cursor, dt_start, dt_end):
    """
    Diagnosa RC: berapa perintah RC di OFDB pada rentang itu, berapa yang sudah
    diselesaikan sendiri oleh OFDB (cek_remote=1), dan sebaran status_2-nya.

    Kalau `total` nol padahal operator merasa ada perintah RC hari itu, berarti
    trigger tr1_scd_his_message di OFDB tidak mengisi scd_his_rc -- masalahnya di
    19.1, bukan di FASOP.
    """
    cursor.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN cek_remote = 1 THEN 1 ELSE 0 END) AS sudah_resolve,
               SUM(CASE WHEN status_2 = 'BERHASIL' THEN 1 ELSE 0 END) AS berhasil,
               SUM(CASE WHEN status_2 = 'GAGAL' THEN 1 ELSE 0 END) AS gagal
        FROM scd_his_rc
        WHERE datum_1 >= ? AND datum_1 <= ?
    """, [dt_start, dt_end])
    row = cursor.fetchone()
    return {
        'total': row[0] or 0,
        'sudah_resolve': row[1] or 0,
        'berhasil': row[2] or 0,
        'gagal': row[3] or 0,
    }


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
