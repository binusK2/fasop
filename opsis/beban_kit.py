"""
Beban pembangkit — modul bersama untuk daftar pembangkit aktif, nilai live-nya,
dan riwayat per menit dari PostgreSQL.

Dipakai oleh halaman OPSIS (lewat `opsis.views`) dan oleh API eksternal
(`api.views`). Alasannya sama dengan `opsis/ktt.py`: kalau cara menyusun
daftar pembangkit atau menjumlahkan MW-nya disalin ke pemanggil, cepat atau
lambat layar ruang kontrol dan spreadsheet pihak luar akan menyebut angka
berbeda untuk pembangkit yang sama — dan tidak ada yang tahu mana yang benar.
"""
from django.utils import timezone

from . import mssql
from .cache import nilai_cached

# Rentang riwayat terpanjang yang boleh diminta sekali jalan. SnapLive bertambah
# satu baris per pembangkit per menit; 3 hari x ~25 pembangkit sudah ~108 ribu
# baris. Lebih dari itu satu worker gunicorn tertahan sampai timeout, persis
# alasan EXPORT_KIT_MAKS_HARI pada ekspor Excel.
MAKS_HARI_RIWAYAT = 3

# Kunci cache nilai live. TTL bawaan opsis/cache.py (2 detik) sudah cukup:
# penarik luar yang memoll tiap menit tidak pernah menyentuh cache ini dua kali,
# sedangkan penarik yang terlalu rajin tetap tidak bisa membanjiri historian.
CACHE_KEY = 'beban_kit_live'


def pembangkit_aktif():
    """
    Daftar pembangkit aktif, siap dipakai `mssql.get_live_data()`.

    select_related('sumber'): tiap pembangkit boleh menunjuk tabel sumbernya
    sendiri. prefetch tag_unit: dipakai get_live_data() saat sumbernya memakai
    mode 'baris'. Tanpa keduanya setiap pembangkit memicu query sendiri di jalur
    yang dipoll browser tiap detik.
    """
    from .models import Pembangkit
    return list(Pembangkit.objects.filter(aktif=True)
                .select_related('sumber').prefetch_related('tag_unit'))


def _baca_live():
    daftar = pembangkit_aktif()
    hasil  = mssql.get_live_data(daftar)
    data   = hasil['data']

    rows = []
    for p in daftar:
        nilai = data.get(p.kode) or {}
        rows.append({
            'kode':      p.kode,
            'nama':      p.nama,
            'jenis':     p.jenis,
            'mw':        nilai.get('mw'),
            'mvar':      nilai.get('mvar'),
            'units':     nilai.get('units') or [],
            # Penanda "data tidak sesuai" dari operator OPSIS sengaja ikut
            # keluar. Kalau ruang kontrol sendiri sudah meragukan angka sebuah
            # pembangkit, konsumen luar yang menyalinnya ke laporan berhak tahu
            # — menyembunyikannya membuat angka ragu terlihat sama meyakinkan
            # dengan angka yang benar.
            'diragukan':  p.data_tidak_sesuai,
            'keterangan': p.data_keterangan or '',
        })

    mw = [r['mw'] for r in rows if r['mw'] is not None]
    return {
        'rows':             rows,
        'total_mw':         round(sum(mw), 2) if mw else None,
        'jumlah':           len(rows),
        'frekuensi_sistem': hasil.get('frekuensi_sistem'),
        'terputus':         not mssql.is_reachable(),
    }


def baca_live():
    """Nilai live semua pembangkit aktif, ter-cache singkat per worker."""
    return nilai_cached(CACHE_KEY, _baca_live) or {
        'rows': [], 'total_mw': None, 'jumlah': 0,
        'frekuensi_sistem': None, 'terputus': True,
    }


def riwayat(t0, t1, kode=None):
    """
    Deret MW/MVAR per menit dari `opsis.SnapLive`, dikelompokkan per pembangkit.

    `t0`/`t1` datetime aware; `kode` daftar kode pembangkit (None = semua yang
    aktif). Return list [{kode, nama, jenis, deret:[{waktu, mw, mvar, hz}]}].

    Batas rentang memakai `waktu__gte`/`waktu__lt`, BUKAN lookup `__date`:
    `__date` membungkus kolom dalam cast sehingga indeks (pembangkit, -waktu)
    tidak terpakai dan query jatuh ke sequential scan atas jutaan baris — sama
    seperti yang pernah membuat ekspor Excel 18 detik.
    """
    from .models import Pembangkit, SnapLive

    qs_p = Pembangkit.objects.filter(aktif=True)
    if kode:
        qs_p = qs_p.filter(kode__in=kode)
    daftar = {p.id: p for p in qs_p.order_by('urutan', 'nama')}
    if not daftar:
        return []

    per = {pk: [] for pk in daftar}
    baris = (SnapLive.objects
             .filter(pembangkit_id__in=daftar.keys(), waktu__gte=t0, waktu__lt=t1)
             .order_by('pembangkit_id', 'waktu')
             .values_list('pembangkit_id', 'waktu', 'mw', 'mvar', 'frekuensi'))
    for pid, waktu, mw, mvar, hz in baris:
        per[pid].append({
            'waktu': timezone.localtime(waktu).isoformat(),
            'mw':    mw,
            'mvar':  mvar,
            'hz':    hz,
        })

    return [
        {
            'kode':   p.kode,
            'nama':   p.nama,
            'jenis':  p.jenis,
            'jumlah': len(per[pk]),
            'deret':  per[pk],
        }
        for pk, p in daftar.items()
    ]



def deret_harian(anggota, t0, t1):
    """
    Deret MW per menit tiap pembangkit `anggota` pada rentang [t0, t1) — isi
    chart halaman rincian KIT Terpilih (/opsis/kit-terpilih/).

    Return list, urutannya mengikuti `anggota`:
        [{'kode', 'nama', 'jenis', 'mw': [[menit, mw], ...]}]

    `menit` = menit sejak 00:00 waktu lokal, konvensi semua chart 24 jam OPSIS.
    Pasangan [menit, mw] (bukan dict) karena satu hari penuh untuk belasan
    pembangkit sudah belasan ribu titik; kunci yang diulang di tiap titik
    melipatgandakan ukuran balasan tanpa menambah informasi.

    Sumbernya SnapLive — angka yang sama dengan chart KIT Terpilih di
    dashboard, jadi garis Total di halaman rincian (jumlah semua deret ini per
    menit) tidak bisa bercerita berbeda dengan chart yang baru saja diklik.

    Menit yang MW-nya kosong tidak dikirim (sama dengan api_beban_kit_terpilih);
    celahnya digambar putus oleh browser, bukan dikarang jadi nol.

    Rentang memakai `waktu__gte`/`waktu__lt`, bukan lookup `__date` — alasan
    indeks yang sama dengan `riwayat()` di atas.
    """
    from .models import SnapLive

    anggota = list(anggota)
    if not anggota:
        return []
    per_pk = {p.pk: [] for p in anggota}

    baris = (SnapLive.objects
             .filter(pembangkit_id__in=per_pk.keys(), waktu__gte=t0, waktu__lt=t1,
                     mw__isnull=False)
             .order_by('waktu')
             .values_list('pembangkit_id', 'waktu', 'mw'))
    for pid, waktu, mw in baris:
        lokal = timezone.localtime(waktu)
        per_pk[pid].append([lokal.hour * 60 + lokal.minute, round(mw, 2)])

    return [{'kode': p.kode, 'nama': p.nama, 'jenis': p.jenis, 'mw': per_pk[p.pk]}
            for p in anggota]
