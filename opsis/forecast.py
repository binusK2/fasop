"""
Prediksi beban kit (total sistem, agregat semua pembangkit) menggunakan
gradient boosting (scikit-learn HistGradientBoostingRegressor).

Satu model, dengan `horizon_minutes` sebagai fitur input (direct forecasting) —
bukan satu model per horizon, bukan recursive step-by-step. Anchor (titik
"sekarang") selalu data SnapLive terbaru yang benar-benar ada, jadi prediksi
otomatis rolling forward setiap kali predict_beban() dipanggil ulang.

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
HORIZON_MAX_MINUTES   = 2160  # 36 jam — cukup untuk "hari ini + besok"
HORIZON_STEP_MINUTES  = 30
LAG_TOLERANCE_MINUTES  = 2   # toleransi pencocokan lag/fitur ke titik data asli
LABEL_TOLERANCE_MINUTES = 2  # toleransi pencocokan label ke titik data asli
HOLDOUT_DAYS = 12           # anchor N hari terakhir dipakai sbg holdout evaluasi

FEATURE_COLUMNS = [
    'horizon_minutes', 'lag_0', 'lag_15', 'lag_30', 'lag_60',
    'roll_mean_60', 'roll_std_60',
    'same_hour_yesterday', 'same_hour_lastweek',
    'target_hour', 'target_dow', 'target_is_weekend',
]


def _model_path():
    return Path(settings.ML_MODEL_ROOT) / 'beban_forecast.joblib'


def _load_series():
    """
    Total MW sistem per menit (SUM semua pembangkit), seluruh histori SnapLive.
    Return pandas Series ber-index DatetimeIndex (UTC, sesuai penyimpanan DB),
    urut ascending. Index kosong jika belum ada data sama sekali.
    """
    qs = (SnapLive.objects
          .values('waktu')
          .annotate(total_mw=Sum('mw'))
          .order_by('waktu'))
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
    Fungsi murni — dipakai baik oleh predict_beban() maupun sebagai referensi
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


def predict_beban(hours_ahead=36, step_minutes=30):
    """
    Prediksi total MW sistem dari sekarang sampai `hours_ahead` jam ke depan,
    tiap `step_minutes` menit. Anchor = titik SnapLive TERBARU yang benar-benar
    ada (bukan wall-clock now()), supaya fitur lag valid walau collect_live
    sedang telat beberapa menit.

    Return {'rows': [{'timestamp': iso8601 lokal, 'mw': float}], 'source': 'model'}
    — atau {'rows': [], 'source': 'no_model'} jika model belum pernah dilatih
    atau data SnapLive kosong (pola graceful-degradation yang sama seperti
    opsis/mssql.py).
    """
    model = _load_model()
    if model is None:
        return {'rows': [], 'source': 'no_model'}

    series = _load_series()
    if series.empty:
        return {'rows': [], 'source': 'no_model'}

    anchor = series.index[-1]
    horizons = list(range(step_minutes, hours_ahead * 60 + 1, step_minutes))
    feature_rows = [build_feature_row(anchor, h, series) for h in horizons]
    X = pd.DataFrame(feature_rows)[FEATURE_COLUMNS]
    preds = model.predict(X)

    rows = []
    for h, p in zip(horizons, preds):
        t_local = (anchor + pd.Timedelta(minutes=h)).tz_convert(settings.TIME_ZONE)
        rows.append({'timestamp': t_local.isoformat(), 'mw': round(float(p), 2)})

    return {'rows': rows, 'source': 'model'}
