"""
Riwayat frekuensi sistem per detik — dari DUA sumber sekaligus.

Latar: `SYS_FREQ_HIS` di historian MSSQL adalah sumber aslinya (1 baris/detik),
tapi job penulisnya di sisi SCADA pernah berhenti berhari-hari tanpa ketahuan —
seluruh Respons Pembangkit ikut mati karenanya, padahal `SYS_FREQ_RT` (nilai
realtime) di server yang sama tetap hidup. Karena itu FASOP juga merekam
frekuensi sendiri ke PostgreSQL lewat `collect_freq_rt` (`opsis.SnapFreqRT`).

Modul ini menggabungkan keduanya. Aturannya:

  * Historian MSSQL adalah acuan — di detik mana pun ia punya data, itu yang
    dipakai. Ia sumber asli dan resolusinya penuh.
  * PostgreSQL menambal detik yang TIDAK dipunyai historian. Jadi lubang
    seperti 24 Agustus 2026 15:17 dan seterusnya tetap ada isinya, dan begitu
    historian pulih ia otomatis kembali jadi acuan tanpa perlu ganti setelan.

Ini satu-satunya tempat yang boleh dipanggil pemakai riwayat frekuensi
(views, management command). Jangan memanggil `mssql.get_freq_range()` langsung
lagi — kalau begitu, salah satu jalur akan kehilangan tambalannya.

Bentuk kembalian sengaja identik dengan `mssql.get_freq_range()`:
list `[(datetime naive waktu lokal, hz)]` terurut waktu.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

# Resolusi penggabungan. Kedua sumber sama-sama 1 baris/detik, jadi detik
# dipakai sebagai kunci — cukup untuk menyatakan "detik ini sudah terisi".
def _kunci(waktu):
    return waktu.replace(microsecond=0)


def _ke_naive_lokal(waktu):
    """
    Samakan ke datetime naive waktu lokal.

    MSSQL mengembalikan naive (sudah waktu lokal server historian), sedangkan
    PostgreSQL menyimpan aware (UTC) karena USE_TZ=True. Tanpa penyamaan ini
    kedua deret akan meleset 8 jam saat digabung.
    """
    if waktu is None:
        return None
    if timezone.is_aware(waktu):
        waktu = timezone.localtime(waktu).replace(tzinfo=None)
    return waktu.replace(microsecond=0)


def _dari_historian(t0, t1):
    """Deret dari SYS_FREQ_HIS. List kosong bila MSSQL mati/tak terkonfigurasi."""
    from opsis import mssql
    try:
        return [(_ke_naive_lokal(t), float(h))
                for t, h in mssql.get_freq_range(t0, t1)
                if t is not None and h is not None]
    except Exception as e:                      # pragma: no cover — mssql sudah menelan errornya
        logger.error('freq_history: historian gagal: %s', e)
        return []


def _dari_postgres(t0, t1):
    """Deret dari opsis.SnapFreqRT (rekaman FASOP sendiri dari SYS_FREQ_RT)."""
    from opsis.models import SnapFreqRT
    try:
        a, b = t0, t1
        if timezone.is_naive(a):
            a = timezone.make_aware(a)
        if timezone.is_naive(b):
            b = timezone.make_aware(b)
        return [(_ke_naive_lokal(w), float(hz)) for w, hz in
                SnapFreqRT.objects.filter(waktu__gte=a, waktu__lte=b)
                                  .order_by('waktu').values_list('waktu', 'hz')]
    except Exception as e:
        logger.error('freq_history: postgres gagal: %s', e)
        return []


def ambil_range_detail(t0, t1):
    """
    Deret frekuensi gabungan + keterangan asal datanya.

    Return (deret, info) dengan info =
        {'historian': n, 'postgres': n, 'sumber': 'historian'|'postgres'|'gabungan'|'kosong'}
    di mana n adalah jumlah detik yang benar-benar DIPAKAI dari sumber itu —
    bukan jumlah baris yang terbaca, supaya angkanya bisa dipercaya sebagai
    "berapa banyak yang ditambal PostgreSQL".
    """
    his = _dari_historian(t0, t1)
    gabung = {}
    for t, h in his:
        if t is not None:
            gabung[_kunci(t)] = h
    n_his = len(gabung)

    n_pg = 0
    for t, h in _dari_postgres(t0, t1):
        if t is None:
            continue
        k = _kunci(t)
        if k not in gabung:                     # historian selalu menang
            gabung[k] = h
            n_pg += 1

    deret = sorted(gabung.items())
    if n_his and n_pg:
        sumber = 'gabungan'
    elif n_his:
        sumber = 'historian'
    elif n_pg:
        sumber = 'postgres'
    else:
        sumber = 'kosong'
    return deret, {'historian': n_his, 'postgres': n_pg, 'sumber': sumber}


def ambil_range(t0, t1):
    """
    Deret frekuensi gabungan, bentuknya sama persis dengan
    `mssql.get_freq_range()` sehingga bisa dipakai sebagai getter pengganti.
    """
    deret, _ = ambil_range_detail(t0, t1)
    return deret


KETERANGAN_SUMBER = {
    'historian': 'Historian SCADA (SYS_FREQ_HIS)',
    'postgres':  'Rekaman FASOP (SnapFreqRT, dari SYS_FREQ_RT)',
    'gabungan':  'Historian SCADA + rekaman FASOP',
    'kosong':    'Tidak ada data frekuensi pada rentang ini',
}


def keterangan(info):
    """Teks asal data untuk ditampilkan di halaman/PDF."""
    dasar = KETERANGAN_SUMBER.get(info.get('sumber'), '')
    if info.get('sumber') == 'gabungan':
        return f"{dasar} — {info['postgres']} detik ditambal dari rekaman FASOP"
    return dasar
