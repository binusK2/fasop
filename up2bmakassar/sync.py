"""
Inti perhitungan kinerja harian SCADATEL (dipakai management command
sync_kinerja_analog / sync_kinerja_digital).

Alur per hari, per jenis (TELEMETERING/TELESIGNAL/RTU/MASTER/TELEKOMUNIKASI):
  1. Ambil master titik dari OFDB scd_c_point + scd_pointtype (kinerja=1, induk
     point type sesuai jenis) -- satu query.
  2. Hitung uptime SEMUA titik untuk hari itu -- satu query GROUP BY ke
     scd_his_analog / scd_his_digital.
  3. Titik yang tidak punya transisi sama sekali di hari itu: ambil status
     terakhir sebelum hari itu -- satu query.
  4. Simpan/replace ke KinerjaAnalogHarian / KinerjaDigitalHarian (PostgreSQL)
     dengan bulk_create, bukan update_or_create per titik.

Jadi 3 query ke OFDB per hari (bukan 4 query per titik per hari seperti script
lama up2bmakassar) -- inilah yang bikin sinkronisasi bisa selesai dalam hitungan
detik dan tabel kinerja di FASOP tidak lagi kosong.
"""
import logging
from datetime import datetime, timedelta

from django.db import transaction

from . import ofdb
from .models import KinerjaAnalogHarian, KinerjaDigitalHarian, SitePath1

logger = logging.getLogger(__name__)

# jenis -> model penyimpan hasilnya
JENIS_MODEL = {
    ofdb.JENIS_TELEMETERING:   KinerjaAnalogHarian,
    ofdb.JENIS_TELESIGNAL:     KinerjaDigitalHarian,
    ofdb.JENIS_RTU:            KinerjaDigitalHarian,
    ofdb.JENIS_MASTER:         KinerjaDigitalHarian,
    ofdb.JENIS_TELEKOMUNIKASI: KinerjaDigitalHarian,
}


def ambil_titik(cursor, jenis, seed_site=True):
    """
    Master titik untuk satu jenis, sudah disaring site yang aktif (SitePath1).
    Path1 baru otomatis di-seed ke SitePath1 dengan aktif=True.
    """
    points = ofdb.get_kinerja_points(cursor, jenis)
    if not points:
        return []

    if seed_site:
        for path1 in sorted({p['path1'] for p in points if p['path1']}):
            SitePath1.objects.get_or_create(path1=path1)

    nonaktif = set(SitePath1.objects.filter(aktif=False).values_list('path1', flat=True))
    return [p for p in points if p['path1'] not in nonaktif]


def hitung_hari(cursor, jenis, points, tanggal):
    """
    Hitung kinerja semua `points` untuk satu tanggal.
    Return list dict siap dipakai untuk membuat baris model.
    """
    _, table = ofdb.JENIS_SUMBER[jenis]
    day_start = datetime.combine(tanggal, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    alltime = (day_end - day_start).total_seconds()

    uptime_map = ofdb.compute_kinerja_harian(cursor, table, day_start, day_end)

    # Titik tanpa transisi sama sekali di hari itu -> pakai status terakhir
    # sebelumnya (VALID = normal seharian penuh).
    butuh_fallback = any(p['point_number'] not in uptime_map for p in points)
    status_sebelum = ofdb.get_status_sebelum(cursor, table, day_start) if butuh_fallback else {}

    hasil = []
    for p in points:
        jlh, uptime = uptime_map.get(p['point_number'], (0, 0.0))
        if uptime == 0 and status_sebelum.get(p['point_number']) == 'VALID':
            uptime = alltime
            jlh = 1
        uptime = min(uptime, alltime)
        hasil.append(dict(
            point_number=p['point_number'],
            jenis=p['jenis'],
            path1=p['path1'], path2=p['path2'], path3=p['path3'],
            path4=p['path4'], path5=p['path5'],
            b1=p['b1'], b2=p['b2'], b3=p['b3'], elem=p['elem'],
            tanggal=tanggal,
            jumlah_up=jlh,
            uptime_detik=uptime,
            alltime_detik=alltime,
            performance=(uptime / alltime * 100) if alltime else 0,
        ))
    return hasil


def simpan_hari(model, jenis, tanggal, rows):
    """
    Replace hasil satu hari untuk satu jenis (delete + bulk_create), meniru
    'delete from scd_kin_..._harian where datum=...' di script up2bmakassar.
    """
    with transaction.atomic():
        model.objects.filter(tanggal=tanggal, jenis=jenis).delete()
        # Titik lama yang dulu tersimpan tanpa jenis (hasil versi sebelumnya)
        # ikut dibersihkan supaya tidak dobel.
        model.objects.filter(
            tanggal=tanggal, jenis='',
            point_number__in=[r['point_number'] for r in rows],
        ).delete()
        model.objects.bulk_create([model(**r) for r in rows], batch_size=1000)


def sync_jenis(cursor, jenis, tanggal_list, dry_run=False, log=None):
    """
    Jalankan sinkronisasi untuk satu jenis dan beberapa tanggal.
    `log` = callable(str) untuk output progres (mis. self.stdout.write).
    Return jumlah baris yang ditulis.
    """
    def _log(msg):
        if log:
            log(msg)

    model = JENIS_MODEL[jenis]
    points = ambil_titik(cursor, jenis)
    if not points:
        _log(f'[{jenis}] Tidak ada titik kinerja=1 di scd_c_point '
             f'(cek nama induk point type di scd_pointtype & flag aktif di SitePath1).')
        return 0

    total = 0
    for tanggal in sorted(tanggal_list):
        rows = hitung_hari(cursor, jenis, points, tanggal)
        rata2 = sum(r['performance'] for r in rows) / len(rows) if rows else 0

        if dry_run:
            _log(f'[DRY][{jenis}] {tanggal} titik={len(rows)} rata2={rata2:.2f}%')
        else:
            simpan_hari(model, jenis, tanggal, rows)
            total += len(rows)
            _log(f'[{jenis}] {tanggal} titik={len(rows)} rata2={rata2:.2f}%')
    return total
