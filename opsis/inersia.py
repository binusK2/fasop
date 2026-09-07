"""
Perhitungan Inersia Sistem — satu-satunya tempat deret E dan ΔP dirakit.

    E  = Σ (MVA × H) pembangkit yang ikut dihitung pada menit itu   [MWs]
    ΔP = 2 × E × ROCOF_batas ÷ f0                                   [MW]

Dipakai bersama oleh dua konsumen yang harus selalu sepakat:

| Konsumen | Kode |
|---|---|
| Chart 24 jam di dashboard | `opsis.views.api_inersia` |
| Ekspor Excel              | `opsis.views.export_inersia` |

Kalau rumusnya disalin ke salah satunya, angka di layar dan angka di berkas
yang dilampirkan ke laporan bisa berbeda tanpa ada yang tahu mana yang benar —
dan ΔP adalah angka yang dipakai menimbang berapa MW boleh lepas.

Aturan yang menempel pada perhitungan ini, jangan diubah tanpa sengaja:

- **Hanya mesin yang beroperasi menyumbang E** (`hanya_beroperasi`, ambangnya
  `ambang_mw`). Itu yang benar secara fisika — hanya mesin tersinkron yang
  menyimpan energi kinetik — dan itu pula yang membuat deretnya bergerak.
- **MVA atau H yang kosong berarti pembangkitnya DILEWATI, bukan dihitung nol.**
  Kalau dianggap nol, data yang belum lengkap diam-diam menyusutkan inersia
  sistem tanpa ada yang sadar. Penyaringnya ada di
  `PengaturanInersia.pembangkit_terhitung()`.
- **Pengelompokan per MENIT, bukan per timestamp persis.** `collect_live`
  menulis tiap pembangkit dengan detik yang bisa berbeda tipis; kalau
  dikelompokkan per timestamp, satu menit pecah jadi beberapa titik yang
  masing-masing hanya berisi sebagian armada, dan E-nya terlihat naik-turun
  liar padahal tidak terjadi apa-apa.
- **Dijumlahkan di Python, bukan SUM di SQL.** Bobot tiap baris (MVA × H)
  konstanta per pembangkit, bukan kolom di `SnapLive`; yang ditarik cuma
  `(waktu, pembangkit_id)`.
- **Rentang memakai `waktu__gte`/`waktu__lt`, bukan lookup `__date`.** Lookup
  `__date` membungkus kolom dalam cast sehingga indeks `(pembangkit, -waktu)`
  tidak terpakai — alasan yang sama dengan ekspor beban pembangkit.
"""
from django.utils import timezone

from .models import SnapLive


def hitung_deret(pengaturan, awal, akhir, pembangkit=None):
    """
    Rakit deret inersia pada rentang [awal, akhir).

    Args:
        pengaturan: `PengaturanInersia`
        awal, akhir: datetime tz-aware; `akhir` eksklusif
        pembangkit: daftar `Pembangkit` yang dihitung; bila None diambil dari
            `pengaturan.pembangkit_terhitung()`

    Returns:
        (baris, kontribusi, faktor)

        baris       list of dict {'waktu': datetime lokal (dipotong ke menit),
                                  'mws': float, 'dp': float|None, 'unit': int}
                    terurut menurut waktu
        kontribusi  {pembangkit_pk: berapa menit ia ikut dihitung}
        faktor      2 × ROCOF ÷ f0, atau None bila f0 nol/kosong
    """
    if pembangkit is None:
        pembangkit = pengaturan.pembangkit_terhitung()

    faktor = (2.0 * pengaturan.rocof_batas / pengaturan.frekuensi_nominal
              if pengaturan.frekuensi_nominal else None)

    if not pembangkit:
        return [], {}, faktor

    mws_per_kit = {p.pk: p.energi_kinetik_mws for p in pembangkit}

    qs = (SnapLive.objects
          .filter(pembangkit__in=pembangkit, waktu__gte=awal, waktu__lt=akhir)
          .order_by('waktu'))
    if pengaturan.hanya_beroperasi:
        qs = qs.filter(mw__gt=pengaturan.ambang_mw)
    else:
        qs = qs.filter(mw__isnull=False)

    per_menit = {}          # menit lokal -> {'mws': float, 'unit': int}
    kontribusi = {}         # pembangkit_pk -> jumlah menit
    for waktu, pk in qs.values_list('waktu', 'pembangkit_id').iterator(chunk_size=5000):
        menit = timezone.localtime(waktu).replace(second=0, microsecond=0)
        ent = per_menit.get(menit)
        if ent is None:
            ent = per_menit[menit] = {'mws': 0.0, 'unit': 0}
        ent['mws'] += mws_per_kit.get(pk, 0.0)
        ent['unit'] += 1
        kontribusi[pk] = kontribusi.get(pk, 0) + 1

    baris = [
        {
            'waktu': menit,
            'mws':   round(ent['mws'], 2),
            'dp':    None if faktor is None else round(ent['mws'] * faktor, 2),
            'unit':  ent['unit'],
        }
        for menit, ent in sorted(per_menit.items())
    ]
    return baris, kontribusi, faktor


def ringkas(baris, kunci):
    """(minimum, rata-rata, maksimum) sebuah kolom, melewati nilai None.
    Return (None, None, None) bila tidak ada satu pun angka."""
    nilai = [b[kunci] for b in baris if b.get(kunci) is not None]
    if not nilai:
        return None, None, None
    return min(nilai), sum(nilai) / len(nilai), max(nilai)
