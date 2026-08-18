"""
Pemilih sumber prediksi beban — satu-satunya pintu yang dipakai views.

Ada dua implementasi dengan API identik:

    opsis/prakiraan.py  -> kurva dari spreadsheet dispatcher (n8n -> Google Sheets)
    opsis/forecast.py   -> model machine learning (HistGradientBoostingRegressor)

Yang aktif ditentukan setting OPSIS_FORECAST_SOURCE ('sheet' | 'ml'), default
'sheet'. Modul ML sengaja TIDAK dihapus dan TIDAK di-import kalau tidak dipakai
(import-nya menarik pandas/numpy/joblib) — untuk menghidupkannya lagi cukup
ubah satu baris di .env, tanpa revert kode.

Semua fungsi di sini mengembalikan dict dengan kunci yang sama persis apa pun
sumbernya, jadi opsis/views.py, chart dashboard, dan halaman Analitik Prediksi
Beban tidak perlu tahu bedanya. Satu-satunya yang membedakan di respons API
adalah field 'source' ('sheet'/'no_sheet' vs 'model'/'no_model').
"""
from django.conf import settings


def sumber_aktif():
    """'sheet' (default) atau 'ml' — dinormalisasi, tidak pernah melempar."""
    nilai = str(getattr(settings, 'OPSIS_FORECAST_SOURCE', 'sheet') or 'sheet').strip().lower()
    return 'ml' if nilai == 'ml' else 'sheet'


def _impl():
    if sumber_aktif() == 'ml':
        from . import forecast
        return forecast
    from . import prakiraan
    return prakiraan


def predict_beban_hari_ini(step_minutes=30):
    return _impl().predict_beban_hari_ini(step_minutes=step_minutes)


def predict_besok_puncak():
    return _impl().predict_besok_puncak()


def evaluate_accuracy(days=7):
    return _impl().evaluate_accuracy(days=days)
