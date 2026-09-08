"""
Beban KTT (konsumen tegangan tinggi) — satu-satunya tempat yang memetakan kode
IND_* dari tabel MSSQL `IND_LOAD` ke nama konsumen dan memisahkan baris total.

Dipakai oleh TIGA konsumen yang harus selalu sepakat:

| Konsumen | Kode |
|---|---|
| Halaman Beban KTT (`/opsis/beban-ktt/`) | `opsis.views.beban_ktt` |
| API halaman itu (refresh 5 detik)       | `opsis.views.api_beban_ktt` |
| API eksternal (kunci API, UP2D dsb.)    | `api.views.opsis_beban_ktt_endpoint` |

Kalau peta nama disalin ke pemanggil, cepat atau lambat halaman FASOP dan angka
yang ditarik pihak luar akan menyebut konsumen yang sama dengan nama berbeda —
dan tidak ada yang tahu mana yang benar.
"""
from . import mssql
from .cache import nilai_cached

# Kode ANALOG di IND_LOAD → nama konsumen yang dikenal orang.
# Kode yang belum terdaftar di sini tetap ikut, memakai kodenya sendiri sebagai
# nama — konsumen baru muncul apa adanya, bukan hilang diam-diam.
KTT_NAME_MAP = {
    'IND_ANTAM':  'ANTAM',
    'IND_CERIA':  'CERIA',
    'IND_TNASA':  'TONASA SEMEN',
    'IND_BSOWA':  'BOSOWA SEMEN',
    'IND_SMLTR4': 'HUADI 4',
    'IND_INDOF':  'INDOFOOD',
    'IND_HUADI':  'HUADI 1',
    'IND_HUADI2': 'HUADI 2',
    'IND_HUADI3': 'HUADI 3',
    'IND_SMLTR5': 'HUADI 5',
}

# ── Warna per konsumen ───────────────────────────────────────────────────────
# Satu konsumen harus selalu berwarna sama di mana pun ia digambar — bar chart
# dashboard, chart 24 jam, dan legenda pemilih seri. Warna eksplisit untuk
# konsumen yang sudah dikenal; sisanya jatuh ke palet lewat CRC32 kodenya.
#
# CRC32, BUKAN hash(): hash() untuk str diacak per proses (PYTHONHASHSEED), jadi
# konsumen yang sama akan berganti warna tiap worker gunicorn dan tiap restart.
KTT_WARNA = {
    'IND_ANTAM':  '#34d399',
    'IND_CERIA':  '#60a5fa',
    'IND_TNASA':  '#f59e0b',
    'IND_BSOWA':  '#f472b6',
    'IND_SMLTR4': '#a78bfa',
    'IND_INDOF':  '#22d3ee',
    'IND_HUADI':  '#fb923c',
    'IND_HUADI2': '#facc15',
    'IND_HUADI3': '#4ade80',
    'IND_SMLTR5': '#c084fc',
    'IND_TOTAL':  '#e2e8f0',
}

# Palet cadangan untuk konsumen yang belum punya warna tetap. Sengaja dipilih
# yang JAUH dari warna di KTT_WARNA: palet pertama berisi #fcd34d, dan di layar
# ia tidak bisa dibedakan dari #facc15 milik HUADI 2 — dua garis kuning yang
# tampak sama persis di chart yang justru gunanya membedakan konsumen.
PALET_KTT = (
    '#94a3b8', '#a3e635', '#818cf8', '#f87171', '#0ea5e9',
    '#d946ef', '#65a30d', '#f43f5e', '#0d9488', '#b45309',
)


def warna_ktt(kode):
    """Warna tetap untuk sebuah kode konsumen KTT."""
    kode = (kode or '').upper()
    if kode in KTT_WARNA:
        return KTT_WARNA[kode]
    import zlib
    return PALET_KTT[zlib.crc32(kode.encode('utf-8')) % len(PALET_KTT)]


# Kunci cache dipakai bersama halaman dan API eksternal: penarik dari luar tidak
# menambah satu pun query ke MSSQL selama halamannya juga sedang dibuka.
CACHE_KEY = 'beban_ktt'


def split_ktt(rows):
    """Pisahkan IND_TOTAL dari baris konsumen. Return (consumers, total_mw)."""
    consumers = []
    total_mw  = None
    for r in rows:
        if r['analog'].upper() == 'IND_TOTAL':
            total_mw = r['value']
        else:
            r['nama'] = KTT_NAME_MAP.get(r['analog'].upper(), r['analog'])
            consumers.append(r)
    # Fallback: hitung manual jika IND_TOTAL tidak ada di data
    if total_mw is None:
        total_mw = sum(r['value'] for r in consumers if r['value'] is not None)
    return consumers, round(total_mw, 2) if total_mw is not None else 0


def _baca():
    rows, total_mw = split_ktt(mssql.get_beban_ktt())
    return {
        'rows':     rows,
        'total_mw': total_mw,
        'jumlah':   len(rows),
        'terputus': not mssql.is_reachable(),
    }


def baca_beban_ktt():
    """
    Beban KTT terkini, ter-cache singkat per worker (lihat opsis/cache.py).

    Bentuk `rows` sengaja dipertahankan apa adanya (`analog`/`value`/`nama`) —
    itu kontrak dengan template `beban_ktt.html` dan JS-nya. API eksternal
    memetakannya ke nama field publik sendiri supaya konsumen luar tidak
    terikat pada nama kolom MSSQL.
    """
    # nilai_cached() mengembalikan None hanya bila belum ada nilai sama sekali
    # DAN thread lain sedang menyegarkan. Jangan panggil _baca() sebagai
    # cadangan di sini: justru saat itulah MSSQL sedang lambat, dan setiap
    # thread yang ikut menembaknya menghabiskan slot gunicorn. Lebih baik satu
    # poll menjawab "belum ada data" — pemanggil sudah menanganinya.
    return nilai_cached(CACHE_KEY, _baca) or {
        'rows': [], 'total_mw': 0, 'jumlah': 0, 'terputus': True,
    }
