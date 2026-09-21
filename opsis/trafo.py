"""
Beban trafo — modul bersama untuk daftar trafo aktif, nilai live-nya, riwayat
per menit dari PostgreSQL, dan payload chart 24 jam.

Alasannya sama dengan `opsis/ktt.py` dan `opsis/beban_kit.py`: kalau cara
menyaring trafo atau menjumlahkan MW-nya disalin ke pemanggil, cepat atau
lambat layar ruang kontrol dan spreadsheet pihak luar akan menyebut angka
berbeda untuk trafo yang sama — dan tidak ada yang tahu mana yang benar.

Dipakai oleh:

| Konsumen | Kode |
|---|---|
| Halaman Beban Trafo (distribusi & IBT) | `opsis.views` |
| Chart 24 jam keduanya                  | `opsis.views` |
| Cron pengisi snapshot                  | `collect_trafo` |
| API eksternal (kunci API, UP2D dsb.)   | `api.views.opsis_beban_trafo_endpoint` |

DISTRIBUSI dan IBT adalah dua JENIS dari satu sumber yang sama: tabel MSSQL
`ALL_TRANS_DATA`, dibedakan hanya oleh awalan BAY, dan snapshot historisnya
sama-sama di `opsis.SnapTrafo` (dibedakan lewat `trafo.bay`, bukan kolom
sendiri). Karena itu semua fungsi di sini menerima `jenis` sebagai parameter,
bukan digandakan jadi sepasang fungsi — bentuk lama itulah yang membuat dua
fungsi chart nyaris identik hidup berdampingan dan harus dijaga tetap sama
secara manual.
"""
from django.db.models import Q
from django.utils import timezone

from . import mssql
from .cache import nilai_cached

# Rentang riwayat terpanjang yang boleh diminta sekali jalan. SnapTrafo
# bertambah satu baris per trafo per menit; 3 hari x puluhan trafo sudah ratusan
# ribu baris. Alasan dan angkanya sengaja disamakan dengan
# beban_kit.MAKS_HARI_RIWAYAT.
MAKS_HARI_RIWAYAT = 3

# Awalan BAY di ALL_TRANS_DATA yang menentukan sebuah trafo masuk jenis mana.
# Registry `opsis.Trafo` dipakai BERSAMA kedua jenis, jadi tanpa penyaring ini
# trafo IBT ikut muncul di halaman distribusi walau tidak pernah kebagian
# datanya.
JENIS = {
    'distribusi': {
        'label': 'Trafo distribusi',
        'bay':   ('TRF52', 'TRF42'),
        'baca':  'get_beban_trafo',
        'cache': 'beban_trafo_distribusi',
    },
    'ibt': {
        'label': 'Trafo IBT (Inter Bus Transformer)',
        'bay':   ('TRF65', 'TRF54'),
        'baca':  'get_beban_trafo_ibt',
        'cache': 'beban_trafo_ibt',
    },
}

JENIS_BAWAAN = 'distribusi'
SEMUA_JENIS = list(JENIS)


def normalkan_jenis(mentah):
    """
    ('distribusi'|'ibt', None) atau (None, pesan galat) untuk nilai dari luar.

    Kosong = jenis bawaan. Jenis yang tidak dikenal DITOLAK, bukan diam-diam
    jatuh ke bawaan: konsumen yang salah ketik `?jenis=IBT2` akan menerima
    angka distribusi dan menyalinnya sebagai angka IBT tanpa pernah tahu.
    """
    j = (mentah or '').strip().lower()
    if not j:
        return JENIS_BAWAAN, None
    if j not in JENIS:
        return None, (f'Jenis trafo "{mentah}" tidak dikenal. '
                      f'Pilihannya: {", ".join(SEMUA_JENIS)}.')
    return j, None


def _q_bay(jenis):
    q = Q()
    for awalan in JENIS[jenis]['bay']:
        q |= Q(bay__istartswith=awalan)
    return q


def trafo_aktif(jenis):
    """Baris `opsis.Trafo` yang aktif dan termasuk `jenis`, terurut tampilan."""
    from .models import Trafo
    return list(Trafo.objects.filter(aktif=True)
                .filter(_q_bay(jenis))
                .order_by('urutan', 'site', 'bay'))


def aktif_saja(rows):
    """
    Saring hasil `mssql.get_beban_trafo*()` agar hanya trafo yang aktif di
    admin (`opsis.Trafo`) yang ikut. Trafo baru yang belum terdaftar otomatis
    didaftarkan sebagai aktif=True supaya tidak hilang dari tampilan sebelum
    sempat dikonfigurasi.

    MSSQL tak terjangkau → pembacanya sudah mengembalikan [] (lihat mssql.py),
    jadi tidak ada risiko baris palsu ikut auto-registrasi di sini.

    Dulu tinggal di `opsis.views._trafo_aktif_saja`, dan cron `collect_trafo`
    mengimpornya DARI VIEWS — sebuah command yang menarik seluruh modul views
    beserta dependensinya hanya untuk satu fungsi filter.
    """
    from .models import Trafo
    existing = {(t.site, t.bay): t.aktif for t in Trafo.objects.all()}
    hasil = []
    for r in rows:
        kunci = (r['site'], r['bay'])
        if kunci not in existing:
            Trafo.objects.get_or_create(site=r['site'], bay=r['bay'])
            existing[kunci] = True
        if existing[kunci]:
            hasil.append(r)
    return hasil


def _kelompokkan(rows):
    """
    (grouped, site_totals, total_mw) dari baris live.

    site_totals memakai abs(p) karena itu total MAGNITUDE beban sebuah GI —
    beda dengan nilai per trafo yang sengaja dibiarkan apa adanya. Tanda minus
    pada P bermakna (arah aliran daya lewat IBT dua arah), jadi menjumlahkannya
    bertanda akan membuat dua trafo berlawanan arah saling meniadakan dan GI
    yang sibuk terlihat nyaris tanpa beban.
    """
    grouped = {}
    for r in rows:
        grouped.setdefault(r['site'] or 'Unknown', []).append(r)
    site_totals = {
        site: round(sum(abs(r['p']) for r in lst if r['p'] is not None), 2)
        for site, lst in grouped.items()
    }
    return grouped, site_totals, round(sum(site_totals.values()), 2)


def _baca_live(jenis):
    rows = aktif_saja(getattr(mssql, JENIS[jenis]['baca'])())
    grouped, site_totals, total_mw = _kelompokkan(rows)
    return {
        'rows':        rows,
        'grouped':     grouped,
        'site_totals': site_totals,
        'total_mw':    total_mw,
        'jumlah':      len(rows),
        'terputus':    not mssql.is_reachable(),
    }


def baca_live(jenis=JENIS_BAWAAN):
    """Nilai live semua trafo aktif sebuah jenis, ter-cache singkat per worker."""
    return nilai_cached(JENIS[jenis]['cache'], lambda: _baca_live(jenis)) or {
        'rows': [], 'grouped': {}, 'site_totals': {}, 'total_mw': 0,
        'jumlah': 0, 'terputus': True,
    }


def riwayat(t0, t1, jenis=JENIS_BAWAAN, site=None):
    """
    Deret P per menit dari `opsis.SnapTrafo`, dikelompokkan per trafo.

    `t0`/`t1` datetime aware; `site` daftar nama GI (None = semua).
    Return list [{site, bay, jumlah, deret:[{waktu, p}]}].

    Nilai P dikembalikan APA ADANYA, bisa negatif — arah aliran daya lewat IBT
    dua arah, jadi tandanya bermakna dan tidak boleh di-abs()-kan di sini.

    Batas rentang memakai `waktu__gte`/`waktu__lt`, BUKAN lookup `__date`:
    `__date` membungkus kolom dalam cast sehingga indeks (trafo, -waktu) tidak
    terpakai dan query jatuh ke sequential scan — alasan yang sama dengan
    beban_kit.riwayat() dan ekspor Excel beban pembangkit.
    """
    from .models import SnapTrafo

    daftar = trafo_aktif(jenis)
    if site:
        pilih = {s.strip().lower() for s in site if s.strip()}
        daftar = [t for t in daftar if (t.site or '').lower() in pilih]
    if not daftar:
        return []

    peta = {t.id: t for t in daftar}
    per = {pk: [] for pk in peta}
    baris = (SnapTrafo.objects
             .filter(trafo_id__in=peta.keys(), waktu__gte=t0, waktu__lt=t1)
             .order_by('trafo_id', 'waktu')
             .values_list('trafo_id', 'waktu', 'p'))
    for tid, waktu, p in baris:
        per[tid].append({'waktu': timezone.localtime(waktu).isoformat(), 'p': p})

    return [
        {
            'site':   t.site,
            'bay':    t.bay,
            'jumlah': len(per[pk]),
            'deret':  per[pk],
        }
        for pk, t in peta.items()
    ]


def chart_harian(jenis=JENIS_BAWAAN):
    """
    Payload chart 24 jam daya aktif (P) — satu chart per GI berisi satu garis
    per trafo, semua trafo di GI yang sama berbagi sumbu waktu.

    Sumber: PostgreSQL (`SnapTrafo`), diisi tiap menit oleh cron
    `collect_trafo`. TIDAK ada jalur cadangan ke MSSQL: `ALL_TRANS_DATA` cuma
    snapshot realtime yang ditimpa di tempat, bukan tabel historian seperti
    `HIS_MEAS_KIT` — PostgreSQL satu-satunya sumber histori trafo.
    """
    from .models import SnapTrafo

    tz_local = timezone.get_current_timezone()
    hari_ini = timezone.now().astimezone(tz_local).date()

    daftar = trafo_aktif(jenis)
    snaps = (SnapTrafo.objects
             .filter(trafo__in=daftar, waktu__date=hari_ini)
             .order_by('waktu')
             .values('trafo_id', 'waktu', 'p'))

    per_trafo = {}
    count = 0
    for s in snaps:
        per_trafo.setdefault(s['trafo_id'], {})[s['waktu']] = s['p']
        count += 1

    by_site = {}
    for t in daftar:
        by_site.setdefault(t.site or 'Unknown', []).append(t)

    sites = []
    for site, trafos in sorted(by_site.items()):
        waktu_set = sorted({w for t in trafos for w in per_trafo.get(t.id, {})})
        labels = [w.astimezone(tz_local).strftime('%H:%M') for w in waktu_set]
        series = []
        for t in trafos:
            vals = per_trafo.get(t.id, {})
            series.append({
                'id':  t.id,
                'bay': t.bay,
                'p': [round(vals[w], 2) if vals.get(w) is not None else None
                      for w in waktu_set],
            })
        sites.append({'site': site, 'labels': labels, 'trafos': series})

    return {'sites': sites, 'count': count}
