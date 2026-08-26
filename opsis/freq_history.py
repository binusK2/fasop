"""
Riwayat frekuensi sistem per detik — dari TIGA sumber sekaligus.

Latar: `SYS_FREQ_HIS` di historian MSSQL adalah sumber aslinya (1 baris/detik),
tapi job penulisnya di sisi SCADA pernah berhenti berhari-hari tanpa ketahuan —
seluruh Respons Pembangkit ikut mati karenanya, padahal `SYS_FREQ_RT` (nilai
realtime) di server yang sama tetap hidup. Karena itu FASOP juga merekam
frekuensi sendiri ke PostgreSQL lewat `collect_freq_rt` (`opsis.SnapFreqRT`).

Modul ini menggabungkan TIGA sumber, berurut prioritas. Detik yang sudah
terisi sumber di atasnya tidak pernah ditimpa sumber di bawahnya:

  1. `SYS_FREQ_HIS` (MSSQL) — sumber asli, acuan. Resolusi 1 baris/detik.
  2. `opsis.SnapFreq` (PostgreSQL) — cermin no.1, diisi cron `collect_freq`.
     Isinya identik, tapi tetap terbaca saat MSSQL-nya sendiri tak terjangkau
     (koneksi putus / circuit breaker terbuka — lihat mssql._conn_circuit).
     Ia TIDAK menolong saat job penulis SYS_FREQ_HIS yang berhenti, karena
     cermin ikut berhenti bersama sumbernya.
  3. `opsis.SnapFreqRT` (PostgreSQL) — rekaman FASOP sendiri dari
     `SYS_FREQ_RT` lewat cron `collect_freq_rt`. Ini satu-satunya sumber yang
     tetap terisi saat SYS_FREQ_HIS berhenti, karena sumbernya berbeda.

Dua mode kegagalan itu berbeda dan butuh penambal berbeda — no.2 untuk MSSQL
tak terjangkau, no.3 untuk historian berhenti diisi. Jangan hapus salah satu
dengan alasan "sudah ada yang lain".

Ini satu-satunya tempat yang boleh dipanggil pemakai riwayat frekuensi
(views, management command). Jangan memanggil `mssql.get_freq_range()` langsung
lagi — kalau begitu, salah satu jalur akan kehilangan tambalannya.

Bentuk kembalian sengaja identik dengan `mssql.get_freq_range()`:
list `[(datetime naive waktu lokal, hz)]` terurut waktu.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

# Resolusi penggabungan. Ketiga sumber sama-sama 1 baris/detik, jadi detik
# dipakai sebagai kunci — cukup untuk menyatakan "detik ini sudah terisi".
def _kunci(waktu):
    return waktu.replace(microsecond=0)


def _ke_naive_lokal(waktu):
    """
    Samakan ke datetime naive waktu lokal.

    MSSQL mengembalikan naive (sudah waktu lokal server historian), sedangkan
    PostgreSQL menyimpan aware (UTC) karena USE_TZ=True. Tanpa penyamaan ini
    deretnya akan meleset 8 jam saat digabung.
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


def _dari_snapfreq(t0, t1):
    """Deret dari opsis.SnapFreq — cermin SYS_FREQ_HIS di PostgreSQL."""
    from opsis.models import SnapFreq
    try:
        a, b = t0, t1
        if timezone.is_naive(a):
            a = timezone.make_aware(a)
        if timezone.is_naive(b):
            b = timezone.make_aware(b)
        return [(_ke_naive_lokal(w), float(hz)) for w, hz in
                SnapFreq.objects.filter(waktu__gte=a, waktu__lte=b)
                                .order_by('waktu').values_list('waktu', 'hz')]
    except Exception as e:
        logger.error('freq_history: snapfreq gagal: %s', e)
        return []


def ambil_range_detail(t0, t1):
    """
    Deret frekuensi gabungan + keterangan asal datanya.

    Return (deret, info) dengan info =
        {'historian': n, 'snapfreq': n, 'postgres': n,
         'sumber': 'historian'|'snapfreq'|'postgres'|'gabungan'|'kosong'}

    Tiap n adalah jumlah detik yang benar-benar DIPAKAI dari sumber itu, bukan
    jumlah baris yang terbaca — supaya angkanya bisa dipercaya sebagai "berapa
    banyak yang ditambal", bukan sekadar "berapa yang tersedia".
    """
    gabung = {}
    dipakai = {}

    # Urutan panggilan = urutan prioritas; yang lebih dulu tidak pernah ditimpa.
    for nama, ambil in (('historian', _dari_historian),
                        ('snapfreq',  _dari_snapfreq),
                        ('postgres',  _dari_postgres)):
        n = 0
        for t, h in ambil(t0, t1):
            if t is None:
                continue
            k = _kunci(t)
            if k not in gabung:
                gabung[k] = h
                n += 1
        dipakai[nama] = n

    berkontribusi = [nama for nama, n in dipakai.items() if n]
    if len(berkontribusi) > 1:
        sumber = 'gabungan'
    elif berkontribusi:
        sumber = berkontribusi[0]
    else:
        sumber = 'kosong'

    info = dict(dipakai, sumber=sumber)
    return sorted(gabung.items()), info


def ambil_range(t0, t1):
    """
    Deret frekuensi gabungan, bentuknya sama persis dengan
    `mssql.get_freq_range()` sehingga bisa dipakai sebagai getter pengganti.
    """
    deret, _ = ambil_range_detail(t0, t1)
    return deret


KETERANGAN_SUMBER = {
    'historian': 'Historian SCADA (SYS_FREQ_HIS)',
    'snapfreq':  'Cermin historian di PostgreSQL (SnapFreq)',
    'postgres':  'Rekaman FASOP (SnapFreqRT, dari SYS_FREQ_RT)',
    'kosong':    'Tidak ada data frekuensi pada rentang ini',
}


def keterangan(info):
    """Teks asal data untuk ditampilkan di halaman/PDF."""
    if info.get('sumber') != 'gabungan':
        return KETERANGAN_SUMBER.get(info.get('sumber'), '')
    bagian = [f'{KETERANGAN_SUMBER[n]}: {info[n]} detik'
              for n in ('historian', 'snapfreq', 'postgres') if info.get(n)]
    return ' + '.join(bagian)
