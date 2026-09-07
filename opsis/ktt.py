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
