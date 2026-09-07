"""
Cache singkat per-worker untuk endpoint OPSIS yang di-poll terus-menerus.

Tanpa cache, tiap poll dari tiap klien menembak MSSQL sendiri; satu query lambat
(koneksi pyodbc baru + query-timeout 30s di _get_area_freq) mengunci satu thread
gunicorn. Beberapa tab up2d/dashboard = 10 slot thread habis → gunicorn macet →
nginx "upstream timed out" / worker dibunuh. Cache per-worker dengan pola
stale-while-revalidate: hanya SATU thread per worker menyegarkan tiap TTL; poller
lain langsung dapat nilai terakhir dan tak ikut menembak MSSQL.

Dipisahkan dari opsis/views.py supaya modul non-view (opsis/ktt.py, dipakai juga
oleh API eksternal di api/views.py) bisa ikut memakainya tanpa mengimpor views.
"""
import threading as _threading
import time as _time

TTL_DEFAULT = 2.0                   # detik — kesegaran cukup untuk kartu live

_cache = {}                         # key -> (value, monotonic_ts)
_locks = {}                         # key -> Lock
_locks_guard = _threading.Lock()


def nilai_cached(key, producer, ttl=TTL_DEFAULT):
    """Nilai ter-cache; disegarkan lewat `producer` maksimal 1x per TTL per worker.
    Saat penyegaran sedang berjalan di thread lain, sajikan nilai lama (bila ada)
    daripada ikut menembak MSSQL — mencegah thread menumpuk saat DB lambat."""
    now = _time.monotonic()
    ent = _cache.get(key)
    if ent and (now - ent[1]) < ttl:
        return ent[0]
    with _locks_guard:
        lock = _locks.setdefault(key, _threading.Lock())
    if not lock.acquire(blocking=False):
        return ent[0] if ent else None     # ada yg menyegarkan → pakai nilai lama
    try:
        val = producer()
        _cache[key] = (val, _time.monotonic())
        return val
    finally:
        lock.release()
