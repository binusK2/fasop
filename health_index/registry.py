"""
health_index/registry.py

Factor Registry — daftar semua faktor HI yang tersedia.
Untuk menambah faktor baru:
    1. Buat class baru di health_index/factors/
    2. Daftarkan di FACTOR_CLASSES di bawah
    3. Tambahkan default KonfigurasiHI via migration atau admin
"""

from health_index.factors.umur       import UmurPeralatanFactor
from health_index.factors.operasi    import StatusOperasiFactor
from health_index.factors.maintenance import MaintenanceGapFactor, CorrectiveCountFactor
from health_index.factors.gangguan   import GangguanAktifFactor
from health_index.factors.kualitas   import KualitasHasilFactor
from health_index.factors.suhu       import (
    KondisiSuhuFactor,
    PerformaJaringanFactor,
    KondisiPowerFactor,
)

# ── Daftar semua faktor ──────────────────────────────────────────────────────
# Urutan di sini menentukan urutan tampil di UI
FACTOR_CLASSES = [
    UmurPeralatanFactor,
    StatusOperasiFactor,
    MaintenanceGapFactor,
    CorrectiveCountFactor,
    GangguanAktifFactor,
    KualitasHasilFactor,
    KondisiSuhuFactor,
    PerformaJaringanFactor,
    KondisiPowerFactor,
]

# Mapping key → instance (singleton per factor)
_registry = {cls.key: cls() for cls in FACTOR_CLASSES}


def get_all_factors():
    """Kembalikan semua instance faktor yang terdaftar."""
    return list(_registry.values())


def get_factor(key):
    """Ambil faktor berdasarkan key."""
    return _registry.get(key)


def get_factor_keys():
    """Kembalikan semua key faktor yang terdaftar."""
    return list(_registry.keys())


# ── Default konfigurasi (bobot_maks) ─────────────────────────────────────────
DEFAULT_BOBOT = {
    'umur_peralatan':    -35,
    'status_operasi':    -15,
    'maintenance_gap':   -25,
    'corrective_count':  -15,
    'gangguan_aktif':    -15,
    'kualitas_hasil':    -20,
    'kondisi_suhu':      -10,
    'performa_jaringan': -10,
    'kondisi_power':     -15,
}

DEFAULT_NAMA = {cls.key: cls.nama for cls in FACTOR_CLASSES}
DEFAULT_ICON = {cls.key: cls.icon for cls in FACTOR_CLASSES}
