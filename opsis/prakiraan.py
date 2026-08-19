"""
Prediksi beban sistem berbasis SPREADSHEET (bukan machine learning).

Sumber angkanya adalah tabel `PrakiraanBeban` — kurva 48 titik (grid 30 menit)
per hari yang dikirim n8n dari Google Sheets lewat POST /api/v1/prakiraan-beban/
(lihat api/views.py::prakiraan_beban_endpoint).

Modul ini adalah padanan 1:1 dari opsis/forecast.py (versi ML): tiga fungsi
publiknya bernama sama dan mengembalikan dict dengan kunci yang sama persis,
supaya dashboard & halaman analitik tidak perlu tahu sumbernya yang mana.
Pemilihan sumber ada di opsis/prediksi.py (setting OPSIS_FORECAST_SOURCE).

Sengaja tidak memakai pandas/numpy — semua perhitungan di sini ringan (48 titik
per hari) dan cukup dengan ORM + datetime, jadi jalur spreadsheet tidak ikut
menanggung ongkos import stack ML.

Konvensi waktu: `menit` selalu menit sejak 00:00 WAKTU LOKAL (settings.TIME_ZONE),
sama seperti sumbu-x chart beban. SnapLive disimpan UTC, jadi setiap
pembandingan dengan realisasi lewat timezone.localtime() dulu.
"""
import datetime
import logging
import math

from django.db.models import Sum
from django.utils import timezone

from .models import PrakiraanBeban, SnapLive

logger = logging.getLogger(__name__)

PUNCAK_SIANG_MINUTE = 12 * 60        # 12:00
PUNCAK_MALAM_MINUTE = 18 * 60 + 30   # 18:30

# Toleransi pencocokan realisasi SnapLive ke sebuah titik grid prakiraan.
# 2 menit — sama dengan LABEL_TOLERANCE_MINUTES di forecast.py, supaya angka
# "realisasi" di dashboard identik siapa pun sumber prediksinya.
REALISASI_TOLERANCE_MINUTES = 2


def _rentang_hari(tanggal):
    """(awal, akhir) tz-aware untuk satu tanggal lokal — akhir eksklusif."""
    tz = timezone.get_current_timezone()
    awal = timezone.make_aware(
        datetime.datetime.combine(tanggal, datetime.time.min), tz)
    return awal, awal + datetime.timedelta(days=1)


def _actual_per_menit(tanggal):
    """
    Realisasi total MW sistem (SUM semua pembangkit) per menit untuk satu
    tanggal lokal, dari SnapLive. Return dict {menit: mw} pada resolusi ASLI
    per menit — tidak di-downsample, karena kurva menit-ke-menit itulah yang
    membuat chart tidak terlihat rata.
    """
    awal, akhir = _rentang_hari(tanggal)
    rows = (SnapLive.objects
            .filter(waktu__gte=awal, waktu__lt=akhir, mw__isnull=False)
            .values('waktu')
            .annotate(total_mw=Sum('mw'))
            .order_by('waktu'))
    hasil = {}
    for r in rows:
        if r['total_mw'] is None:
            continue
        lokal = timezone.localtime(r['waktu'])
        hasil[lokal.hour * 60 + lokal.minute] = round(float(r['total_mw']), 2)
    return hasil


def _realisasi_pada(actual_by_minute, menit):
    """
    Nilai realisasi di titik grid `menit`, toleransi REALISASI_TOLERANCE_MINUTES
    ke BELAKANG saja (tidak pernah memakai data setelah titik itu). None kalau
    titiknya belum terlewati atau datanya bolong.
    """
    for offset in range(REALISASI_TOLERANCE_MINUTES + 1):
        nilai = actual_by_minute.get(menit - offset)
        if nilai is not None:
            return nilai
    return None


def _prakiraan_per_menit(tanggal):
    """Kurva prakiraan satu hari sebagai dict {menit: mw}."""
    return {p.menit: round(float(p.mw), 2)
            for p in PrakiraanBeban.objects.filter(tanggal=tanggal)}


def predict_beban_hari_ini(step_minutes=30):
    """
    Padanan forecast.predict_beban_hari_ini() untuk sumber spreadsheet.

    - 'actual'   : SnapLive resolusi per menit, hanya s.d. data terbaru.
    - 'forecast' : kurva dari spreadsheet apa adanya (biasanya grid 30 menit,
                   00:00-23:30). Tidak ada nowcast/pseudo-anchor seperti di
                   versi ML — prakiraan dispatcher memang sudah dibuat untuk
                   sehari penuh sebelum harinya berjalan, jadi bagian yang
                   sudah lewat pun tetap angka prakiraan aslinya. Justru itu
                   yang membuat perbandingan prakiraan vs realisasi jujur.

    `step_minutes` diterima demi kesamaan signature dengan versi ML, tapi tidak
    dipakai: resolusi ditentukan oleh isi spreadsheet, bukan oleh pemanggil.

    'source' bernilai 'sheet' bila kurva hari ini ada, 'no_sheet' bila belum
    ada baris prakiraan sama sekali untuk hari ini (mis. n8n belum jalan).
    """
    hari_ini = timezone.localdate()
    actual_by_minute = _actual_per_menit(hari_ini)
    forecast_by_minute = _prakiraan_per_menit(hari_ini)

    actual = [{'minute': m, 'mw': mw} for m, mw in sorted(actual_by_minute.items())]
    forecast = [{'minute': m, 'mw': mw} for m, mw in sorted(forecast_by_minute.items())]

    return {
        'actual': actual,
        'forecast': forecast,
        'source': 'sheet' if forecast else 'no_sheet',
        'prediksi_puncak_siang': forecast_by_minute.get(PUNCAK_SIANG_MINUTE),
        'prediksi_puncak_malam': forecast_by_minute.get(PUNCAK_MALAM_MINUTE),
        'realisasi_puncak_siang': _realisasi_pada(actual_by_minute, PUNCAK_SIANG_MINUTE),
        'realisasi_puncak_malam': _realisasi_pada(actual_by_minute, PUNCAK_MALAM_MINUTE),
    }


def predict_besok_puncak():
    """
    Puncak siang (12:00) & malam (18:30) BESOK, dibaca langsung dari kurva
    prakiraan besok. None kalau spreadsheet besok belum terisi — itu kondisi
    normal di pagi hari sebelum dispatcher mengunggah prakiraan H+1.
    """
    besok = timezone.localdate() + datetime.timedelta(days=1)
    kurva = _prakiraan_per_menit(besok)
    return {
        'prediksi_puncak_siang_besok': kurva.get(PUNCAK_SIANG_MINUTE),
        'prediksi_puncak_malam_besok': kurva.get(PUNCAK_MALAM_MINUTE),
        'source': 'sheet' if kurva else 'no_sheet',
    }


def evaluate_accuracy(days=7):
    """
    Akurasi prakiraan spreadsheet vs realisasi SnapLive selama `days` hari
    terakhir (termasuk hari berjalan, sebatas yang sudah terlewati).

    Tiap titik grid prakiraan dipasangkan dengan realisasi pada jam yang sama
    (toleransi REALISASI_TOLERANCE_MINUTES); titik yang belum punya realisasi
    dilewati. Dihitung ulang tiap dipanggil, bukan angka statis.

    Return dict dengan kunci yang sama seperti forecast.evaluate_accuracy().
    """
    kosong = {'n': 0, 'mae': None, 'rmse': None, 'mape_percent': None,
              'akurasi_percent': None, 'period_days': days}

    hari_ini = timezone.localdate()
    mulai = hari_ini - datetime.timedelta(days=days - 1)

    prakiraan = list(PrakiraanBeban.objects
                     .filter(tanggal__gte=mulai, tanggal__lte=hari_ini)
                     .order_by('tanggal', 'menit'))
    if not prakiraan:
        return kosong

    # Realisasi di-cache per tanggal — maksimal `days` query, bukan per titik.
    cache_actual = {}
    errors, aktual_terpakai = [], []
    for p in prakiraan:
        if p.tanggal not in cache_actual:
            cache_actual[p.tanggal] = _actual_per_menit(p.tanggal)
        realisasi = _realisasi_pada(cache_actual[p.tanggal], p.menit)
        if realisasi is None:
            continue
        errors.append(float(p.mw) - realisasi)
        aktual_terpakai.append(realisasi)

    n = len(errors)
    if not n:
        return kosong

    abs_errors = [abs(e) for e in errors]
    mae = sum(abs_errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    pasangan = [(ae, a) for ae, a in zip(abs_errors, aktual_terpakai) if a != 0]
    mape = (sum(ae / abs(a) for ae, a in pasangan) / len(pasangan) * 100) if pasangan else None

    return {
        'n': n,
        'mae': round(mae, 2),
        'rmse': round(rmse, 2),
        'mape_percent': round(mape, 2) if mape is not None else None,
        'akurasi_percent': round(max(0.0, 100 - mape), 2) if mape is not None else None,
        'period_days': days,
    }
