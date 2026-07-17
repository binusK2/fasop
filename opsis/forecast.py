"""
Prediksi beban kit (total sistem, agregat semua pembangkit) menggunakan
gradient boosting (scikit-learn HistGradientBoostingRegressor).

Satu model, dengan `horizon_minutes` sebagai fitur input (direct forecasting) —
bukan satu model per horizon, bukan recursive step-by-step. Anchor (titik
"sekarang") selalu data SnapLive terbaru yang benar-benar ada, jadi prediksi
otomatis rolling forward setiap kali predict_beban_hari_ini() dipanggil ulang.

Sumber data: SnapLive (snapshot per menit per pembangkit, tanpa auto-purge,
lihat opsis/models.py). Training & prediksi bekerja di atas agregat total MW
per menit (SUM semua pembangkit) — series yang sama seperti dipakai chart
"Beban Kit — Hari Ini" (lihat views.api_beban).

Invarian anti-leakage: SETIAP fitur untuk anchor_time tertentu hanya boleh
memakai data dengan waktu <= anchor_time. Ini ditegakkan terpusat lewat
_asof_scalar() (dan versi vektor _asof_lookup_batch()) — jangan tambah lookup
baru tanpa lewat salah satu dari keduanya.
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Sum

from .models import SnapLive

logger = logging.getLogger(__name__)

# ── Konstanta training ────────────────────────────────────────────────
ANCHOR_STRIDE_MINUTES = 30   # jarak antar anchor yang di-sample dari histori
HORIZON_MIN_MINUTES   = 30
# 48 jam — "puncak malam besok" bisa berjarak sampai ~42.5 jam dari anchor
# kalau halaman dibuka tepat lewat tengah malam (anchor = data SnapLive
# TERBARU, praktiknya selalu ~"sekarang"); 48 jam beri margin penuh 1 hari
# kalender ke depan supaya horizon itu tidak pernah mengekstrapolasi model
# di luar rentang yang dilatih. Model HARUS di-retrain (train_beban_forecast)
# setelah mengubah konstanta ini.
HORIZON_MAX_MINUTES   = 2880
HORIZON_STEP_MINUTES  = 30
LAG_TOLERANCE_MINUTES  = 2   # toleransi pencocokan lag/fitur ke titik data asli
LABEL_TOLERANCE_MINUTES = 2  # toleransi pencocokan label ke titik data asli
HOLDOUT_DAYS = 12           # anchor N hari terakhir dipakai sbg holdout evaluasi

# ── Konstanta evaluasi akurasi & prediksi puncak besok ──────────────────
ACCURACY_STRIDE_MINUTES  = 30  # jarak antar titik evaluasi (selaras ANCHOR_STRIDE_MINUTES)
ACCURACY_HORIZON_MINUTES = 30  # horizon 1-step-ahead yg dievaluasi (selaras nowcast di chart harian)

FEATURE_COLUMNS = [
    'horizon_minutes', 'lag_0', 'lag_15', 'lag_30', 'lag_60',
    'roll_mean_60', 'roll_std_60',
    'same_hour_yesterday', 'same_hour_lastweek',
    'target_hour', 'target_dow', 'target_is_weekend',
]


def _model_path():
    return Path(settings.ML_MODEL_ROOT) / 'beban_forecast.joblib'


def _load_series(since=None):
    """
    Total MW sistem per menit (SUM semua pembangkit) dari SnapLive. Return
    pandas Series ber-index DatetimeIndex (UTC, sesuai penyimpanan DB), urut
    ascending. Index kosong jika belum ada data sama sekali.

    `since` (tz-aware, opsional): batasi hanya waktu >= since. Dipakai oleh
    predict_beban_hari_ini() supaya tiap request tidak perlu load SELURUH
    histori (~3 bulan) — cukup ~8 hari terakhir untuk fitur lag terjauh
    (same_hour_lastweek, -7 hari). build_training_dataset() tetap panggil
    tanpa batas karena training butuh seluruh histori.
    """
    qs = (SnapLive.objects
          .values('waktu')
          .annotate(total_mw=Sum('mw'))
          .order_by('waktu'))
    if since is not None:
        qs = qs.filter(waktu__gte=since)
    rows = list(qs)
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame.from_records(rows)
    df = df.dropna(subset=['total_mw'])
    df['waktu'] = pd.to_datetime(df['waktu'], utc=True)
    return df.set_index('waktu')['total_mw'].astype(float).sort_index()


def _asof_scalar(series, t, cutoff, tolerance_minutes=LAG_TOLERANCE_MINUTES):
    """
    Nilai series terakhir pada atau sebelum waktu `t`, HANYA jika `t <= cutoff`
    (jaga invarian anti-leakage — cutoff biasanya anchor_time untuk fitur,
    atau `t` itu sendiri untuk label yang memang boleh di masa depan anchor).
    Ditolak (NaN) jika titik yang ditemukan lebih jauh dari `tolerance_minutes`
    dari `t` (hindari carry-forward basi lintas gap data panjang).
    """
    if series.empty or t > cutoff:
        return float('nan')
    pos = series.index.searchsorted(t, side='right') - 1
    if pos < 0:
        return float('nan')
    found_t = series.index[pos]
    if (t - found_t) > pd.Timedelta(minutes=tolerance_minutes):
        return float('nan')
    return float(series.iloc[pos])


def _target_calendar(target_time_utc):
    """Fitur kalender dari target_time, dalam TIME_ZONE lokal (bukan UTC) —
    pola beban mengikuti jam dinding lokal, bukan UTC."""
    local = target_time_utc.tz_convert(settings.TIME_ZONE)
    return {
        'target_hour': local.hour,
        'target_dow': local.weekday(),
        'target_is_weekend': int(local.weekday() >= 5),
    }


def build_feature_row(anchor_time, horizon_minutes, series):
    """
    Bangun satu baris fitur untuk prediksi total MW di anchor_time+horizon_minutes.
    Fungsi murni — dipakai baik oleh predict_beban_hari_ini() maupun sebagai referensi
    semantik yang disalin (dioptimasi jadi loop per-anchor, bukan dipanggil
    ulang) oleh build_training_dataset() untuk performa pada skala ratusan
    ribu baris. Lihat modul docstring untuk invarian anti-leakage.
    """
    target_time = anchor_time + pd.Timedelta(minutes=horizon_minutes)

    lag_0  = _asof_scalar(series, anchor_time, anchor_time)
    lag_15 = _asof_scalar(series, anchor_time - pd.Timedelta(minutes=15), anchor_time)
    lag_30 = _asof_scalar(series, anchor_time - pd.Timedelta(minutes=30), anchor_time)
    lag_60 = _asof_scalar(series, anchor_time - pd.Timedelta(minutes=60), anchor_time)

    window = series[(series.index > anchor_time - pd.Timedelta(minutes=60)) &
                     (series.index <= anchor_time)]
    roll_mean_60 = float(window.mean()) if len(window) else float('nan')
    roll_std_60  = float(window.std()) if len(window) > 1 else float('nan')

    same_hour_yesterday = _asof_scalar(series, target_time - pd.Timedelta(minutes=1440), anchor_time)
    same_hour_lastweek  = _asof_scalar(series, target_time - pd.Timedelta(minutes=10080), anchor_time)

    row = {
        'horizon_minutes': horizon_minutes,
        'lag_0': lag_0, 'lag_15': lag_15, 'lag_30': lag_30, 'lag_60': lag_60,
        'roll_mean_60': roll_mean_60, 'roll_std_60': roll_std_60,
        'same_hour_yesterday': same_hour_yesterday,
        'same_hour_lastweek': same_hour_lastweek,
    }
    row.update(_target_calendar(target_time))
    return row


def build_training_dataset():
    """
    Return (X, y, anchor_times):
      X : DataFrame fitur (kolom = FEATURE_COLUMNS)
      y : Series label (total MW aktual di target_time)
      anchor_times : DatetimeIndex anchor tiap baris X/y — dipakai untuk split
                     time-respecting (bukan random shuffle) di train().

    Anchor di-sample tiap ANCHOR_STRIDE_MINUTES sepanjang histori; untuk tiap
    anchor, horizon HORIZON_MIN_MINUTES..HORIZON_MAX_MINUTES step
    HORIZON_STEP_MINUTES. Fitur yang cuma bergantung ke anchor (lag/rolling)
    dihitung sekali per anchor lalu dipakai ulang untuk semua horizon anchor
    itu — bukan dihitung ulang per (anchor,horizon), supaya training tetap
    cepat pada ~300rb baris.
    """
    series = _load_series()
    if len(series) < 200:
        raise ValueError('Data SnapLive terlalu sedikit untuk training (< 200 titik).')

    start, end = series.index[0], series.index[-1]
    anchors = pd.date_range(start, end, freq=f'{ANCHOR_STRIDE_MINUTES}min')
    horizons = range(HORIZON_MIN_MINUTES, HORIZON_MAX_MINUTES + 1, HORIZON_STEP_MINUTES)

    rows = []
    labels = []
    anchor_times = []

    for anchor in anchors:
        lag_0  = _asof_scalar(series, anchor, anchor)
        lag_15 = _asof_scalar(series, anchor - pd.Timedelta(minutes=15), anchor)
        lag_30 = _asof_scalar(series, anchor - pd.Timedelta(minutes=30), anchor)
        lag_60 = _asof_scalar(series, anchor - pd.Timedelta(minutes=60), anchor)
        window = series[(series.index > anchor - pd.Timedelta(minutes=60)) &
                         (series.index <= anchor)]
        roll_mean_60 = float(window.mean()) if len(window) else float('nan')
        roll_std_60  = float(window.std()) if len(window) > 1 else float('nan')

        for h in horizons:
            target_time = anchor + pd.Timedelta(minutes=h)
            if target_time > end:
                break  # horizon makin besar -> target makin jauh, sisanya pasti > end juga
            label = _asof_scalar(series, target_time, target_time,
                                  tolerance_minutes=LABEL_TOLERANCE_MINUTES)
            if pd.isna(label):
                continue

            same_hour_yesterday = _asof_scalar(series, target_time - pd.Timedelta(minutes=1440), anchor)
            same_hour_lastweek  = _asof_scalar(series, target_time - pd.Timedelta(minutes=10080), anchor)

            row = {
                'horizon_minutes': h,
                'lag_0': lag_0, 'lag_15': lag_15, 'lag_30': lag_30, 'lag_60': lag_60,
                'roll_mean_60': roll_mean_60, 'roll_std_60': roll_std_60,
                'same_hour_yesterday': same_hour_yesterday,
                'same_hour_lastweek': same_hour_lastweek,
            }
            row.update(_target_calendar(target_time))
            rows.append(row)
            labels.append(label)
            anchor_times.append(anchor)

    if not rows:
        raise ValueError('Tidak ada baris training yang valid (label tidak ditemukan).')

    X = pd.DataFrame(rows)[FEATURE_COLUMNS]
    y = pd.Series(labels, name='total_mw')
    return X, y, pd.DatetimeIndex(anchor_times)


def train(dry_run=False):
    """
    Latih model dari seluruh histori SnapLive. Evaluasi MAE/RMSE di holdout
    (anchor HOLDOUT_DAYS hari terakhir, split berbasis waktu — bukan random
    shuffle, supaya window lag/rolling tidak bocor antar train/holdout).

    Jika dry_run=False, model FINAL dilatih ulang di atas seluruh data
    (train+holdout) dan disimpan ke ML_MODEL_ROOT — metrik holdout tetap
    dilaporkan dari model yang HANYA dilatih di bagian train (evaluasi jujur).

    Return dict metrik: rows, train_rows, holdout_rows, mae, rmse, saved.
    """
    from sklearn.ensemble import HistGradientBoostingRegressor

    X, y, anchor_times = build_training_dataset()

    cutoff = anchor_times.max() - pd.Timedelta(days=HOLDOUT_DAYS)
    train_mask = anchor_times <= cutoff
    X_train, y_train = X[train_mask], y[train_mask]
    X_holdout, y_holdout = X[~train_mask], y[~train_mask]

    eval_model = HistGradientBoostingRegressor(random_state=42)
    eval_model.fit(X_train, y_train)

    if len(X_holdout):
        pred = eval_model.predict(X_holdout)
        mae  = float(np.mean(np.abs(pred - y_holdout.values)))
        rmse = float(np.sqrt(np.mean((pred - y_holdout.values) ** 2)))
    else:
        mae = rmse = float('nan')

    saved = False
    if not dry_run:
        final_model = HistGradientBoostingRegressor(random_state=42)
        final_model.fit(X, y)
        path = _model_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        import joblib
        joblib.dump(final_model, path)
        saved = True

    return {
        'rows': len(X),
        'train_rows': int(train_mask.sum()),
        'holdout_rows': int((~train_mask).sum()),
        'mae': mae,
        'rmse': rmse,
        'saved': saved,
    }


_model_cache = {'model': None, 'mtime': None}


def _load_model():
    path = _model_path()
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    if _model_cache['model'] is None or _model_cache['mtime'] != mtime:
        import joblib
        try:
            _model_cache['model'] = joblib.load(path)
            _model_cache['mtime'] = mtime
        except Exception as e:
            logger.error('Gagal load model beban_forecast: %s', e, exc_info=True)
            return None
    return _model_cache['model']


PUNCAK_SIANG_MINUTE = 12 * 60        # 12:00
PUNCAK_MALAM_MINUTE = 18 * 60 + 30   # 18:30


def predict_beban_hari_ini(step_minutes=30):
    """
    Beban 'hari ini' — dua seri terpisah, keduanya membentang PENUH 24 jam
    (00:00-23:30) supaya prediksi & realisasi bisa dibandingkan visual sepanjang
    hari, bukan cuma prediksi mengisi sisa waktu ke depan:

    - 'actual'   : resolusi ASLI per menit dari SnapLive, HANYA sampai titik
                   data terbaru (anchor) — tidak di-downsample (kalau
                   di-downsample ke grid 30 menit, kurva naik-turun tiap menit
                   jadi kelihatan hampir lurus).
    - 'forecast' : grid step_minutes menit (default 30), PENUH sehari.
                   * Untuk slot > anchor (belum terjadi): direct forecast dari
                     model, anchor asli, horizon = jarak slot ke anchor
                     (sesuai desain training: horizon sbg fitur input).
                   * Untuk slot <= anchor (sudah lewat): "nowcast" 30-menit-ke-
                     depan memakai pseudo-anchor = slot - step_minutes, supaya
                     bisa dibandingkan dengan realisasi tanpa melanggar invarian
                     anti-leakage (pseudo-anchor selalu < slot, fitur lag tetap
                     hanya memakai data s.d. pseudo-anchor) dan tanpa
                     mengekstrapolasi model di luar rentang horizon latihan
                     (horizon tetap step_minutes, bukan negatif/nol).

    Tanggal "hari ini" dari wall-clock now() (bukan dari anchor) supaya
    cakupan selalu hari kalender berjalan meski data sempat telat/kosong.

    Return {
        'actual':   [{'minute': int, 'mw': float}, ...],
        'forecast': [{'minute': int, 'mw': float}, ...],
        'source': 'model'|'no_model',
        'prediksi_puncak_siang': float|None,   # prediksi model @ 12:00 (selalu ada jika model ada)
        'prediksi_puncak_malam': float|None,   # prediksi model @ 18:30
        'realisasi_puncak_siang': float|None,  # nilai SnapLive aktual @ 12:00 (None jika belum lewat)
        'realisasi_puncak_malam': float|None,  # nilai SnapLive aktual @ 18:30 (None jika belum lewat)
    }
    """
    tz = settings.TIME_ZONE
    now_local = pd.Timestamp.now(tz=tz)
    today_local = now_local.normalize()

    # Load histori secukupnya saja (~9 hari) — cukup untuk fitur lag terjauh
    # (same_hour_lastweek, -7 hari) + buffer, jauh lebih ringan daripada load
    # seluruh ~3 bulan histori tiap request (endpoint ini di-poll tiap 5 detik).
    series = _load_series(since=today_local - pd.Timedelta(days=9))
    anchor = series.index[-1] if not series.empty else None
    model = _load_model()

    # ── Aktual: SEMUA titik per menit hari ini s.d. anchor, resolusi asli ──
    actual = []
    if anchor is not None:
        todays = series[series.index >= today_local.tz_convert('UTC')]
        for t_utc, mw in todays.items():
            t_local = t_utc.tz_convert(tz)
            minute = t_local.hour * 60 + t_local.minute
            actual.append({'minute': minute, 'mw': round(float(mw), 2)})

    # ── Prediksi: grid step_minutes PENUH 00:00-23:30 ──
    forecast_by_minute = {}
    if model is not None and anchor is not None:
        minutes_list = list(range(0, 24 * 60, step_minutes))
        feats = []
        for minute in minutes_list:
            t_local = today_local + pd.Timedelta(minutes=minute)
            t_utc = t_local.tz_convert('UTC')
            if t_utc > anchor:
                pseudo_anchor = anchor
                horizon = (t_utc - anchor).total_seconds() / 60
            else:
                pseudo_anchor = t_utc - pd.Timedelta(minutes=step_minutes)
                horizon = step_minutes
            feats.append(build_feature_row(pseudo_anchor, horizon, series))
        X = pd.DataFrame(feats)[FEATURE_COLUMNS]
        preds = model.predict(X)
        forecast_by_minute = {m: round(float(p), 2) for m, p in zip(minutes_list, preds)}

    forecast = [{'minute': m, 'mw': mw} for m, mw in sorted(forecast_by_minute.items())]

    # ── Realisasi puncak: nilai aktual di 12:00/18:30, None jika belum lewat ──
    realisasi_siang = realisasi_malam = None
    if anchor is not None:
        t_siang_utc = (today_local + pd.Timedelta(minutes=PUNCAK_SIANG_MINUTE)).tz_convert('UTC')
        t_malam_utc = (today_local + pd.Timedelta(minutes=PUNCAK_MALAM_MINUTE)).tz_convert('UTC')
        v = _asof_scalar(series, t_siang_utc, anchor, tolerance_minutes=LABEL_TOLERANCE_MINUTES)
        realisasi_siang = round(float(v), 2) if not pd.isna(v) else None
        v = _asof_scalar(series, t_malam_utc, anchor, tolerance_minutes=LABEL_TOLERANCE_MINUTES)
        realisasi_malam = round(float(v), 2) if not pd.isna(v) else None

    return {
        'actual': actual,
        'forecast': forecast,
        'source': 'model' if model is not None else 'no_model',
        'prediksi_puncak_siang': forecast_by_minute.get(PUNCAK_SIANG_MINUTE),
        'prediksi_puncak_malam': forecast_by_minute.get(PUNCAK_MALAM_MINUTE),
        'realisasi_puncak_siang': realisasi_siang,
        'realisasi_puncak_malam': realisasi_malam,
    }


def predict_besok_puncak():
    """
    Prediksi puncak siang (12:00) & malam (18:30) BESOK (hari kalender
    berikutnya dari wall-clock now()). Direct forecast dari anchor asli
    (data SnapLive terbaru) + horizon langsung ke target time — sama seperti
    cabang "future" di predict_beban_hari_ini(), BUKAN pseudo-anchor, karena
    target sepenuhnya di masa depan (tidak ada realisasi utk di-nowcast-kan).

    Horizon ke puncak malam besok bisa sampai ~42-48 jam tergantung jam
    berapa fungsi ini dipanggil — makanya HORIZON_MAX_MINUTES = 2880 (48 jam).

    Return {
        'prediksi_puncak_siang_besok': float|None,
        'prediksi_puncak_malam_besok': float|None,
        'source': 'model'|'no_model',
    }
    """
    tz = settings.TIME_ZONE
    now_local = pd.Timestamp.now(tz=tz)
    besok_local = now_local.normalize() + pd.Timedelta(days=1)

    series = _load_series(since=now_local.normalize() - pd.Timedelta(days=9))
    anchor = series.index[-1] if not series.empty else None
    model = _load_model()

    if model is None or anchor is None:
        return {
            'prediksi_puncak_siang_besok': None,
            'prediksi_puncak_malam_besok': None,
            'source': 'no_model' if model is None else 'model',
        }

    targets = {
        'siang': besok_local + pd.Timedelta(minutes=PUNCAK_SIANG_MINUTE),
        'malam': besok_local + pd.Timedelta(minutes=PUNCAK_MALAM_MINUTE),
    }
    keys, feats = zip(*(
        (key, build_feature_row(anchor, (t_local.tz_convert('UTC') - anchor).total_seconds() / 60, series))
        for key, t_local in targets.items()
    ))
    X = pd.DataFrame(feats)[FEATURE_COLUMNS]
    preds = model.predict(X)

    result = {f'prediksi_puncak_{k}_besok': round(float(p), 2) for k, p in zip(keys, preds)}
    result['source'] = 'model'
    return result


def evaluate_accuracy(days=7):
    """
    Evaluasi akurasi model: walk-forward one-step-ahead (horizon
    ACCURACY_HORIZON_MINUTES/30 menit) di grid ACCURACY_STRIDE_MINUTES
    sepanjang `days` hari terakhir. Untuk tiap titik grid t, prediksi
    dibangun dari pseudo-anchor (t - horizon) — persis pola nowcast yang
    dipakai predict_beban_hari_ini() utk bagian yang sudah lewat — lalu
    dibandingkan dengan realisasi SnapLive di t (toleransi
    LABEL_TOLERANCE_MINUTES; titik tanpa realisasi dilewati). Dihitung LIVE
    tiap dipanggil (bukan disimpan dari training) supaya mencerminkan
    akurasi model saat ini terhadap data terbaru.

    Return {
        'n': int,                    # jumlah titik yang berhasil dievaluasi
        'mae': float|None,
        'rmse': float|None,
        'mape_percent': float|None,
        'akurasi_percent': float|None,  # 100 - MAPE, clip ke 0
        'period_days': int,
    }
    """
    empty = {'n': 0, 'mae': None, 'rmse': None, 'mape_percent': None,
              'akurasi_percent': None, 'period_days': days}

    model = _load_model()
    if model is None:
        return empty

    tz = settings.TIME_ZONE
    now_local = pd.Timestamp.now(tz=tz)
    # +9 hari extra: 7 hari utk fitur same_hour_lastweek pd titik grid paling
    # awal + buffer, sama seperti predict_beban_hari_ini().
    series = _load_series(since=now_local.normalize() - pd.Timedelta(days=days + 9))
    if series.empty:
        return empty

    grid = pd.date_range(now_local - pd.Timedelta(days=days), now_local,
                          freq=f'{ACCURACY_STRIDE_MINUTES}min', tz=tz).tz_convert('UTC')

    feats, actuals = [], []
    for t in grid:
        actual_mw = _asof_scalar(series, t, t, tolerance_minutes=LABEL_TOLERANCE_MINUTES)
        if pd.isna(actual_mw):
            continue
        pseudo_anchor = t - pd.Timedelta(minutes=ACCURACY_HORIZON_MINUTES)
        feats.append(build_feature_row(pseudo_anchor, ACCURACY_HORIZON_MINUTES, series))
        actuals.append(actual_mw)

    if not feats:
        return empty

    X = pd.DataFrame(feats)[FEATURE_COLUMNS]
    preds = model.predict(X)
    actuals = np.array(actuals)
    errors = preds - actuals
    abs_errors = np.abs(errors)

    mae = float(abs_errors.mean())
    rmse = float(np.sqrt((errors ** 2).mean()))
    nonzero = actuals != 0
    mape = float((abs_errors[nonzero] / np.abs(actuals[nonzero])).mean() * 100) if nonzero.any() else None
    akurasi = round(max(0.0, 100 - mape), 2) if mape is not None else None

    return {
        'n': len(actuals),
        'mae': round(mae, 2),
        'rmse': round(rmse, 2),
        'mape_percent': round(mape, 2) if mape is not None else None,
        'akurasi_percent': akurasi,
        'period_days': days,
    }
