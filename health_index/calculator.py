"""
health_index/calculator.py — dengan auto-snapshot & trigger notifikasi
"""

from datetime import date as date_type
from django.utils import timezone
from dateutil.relativedelta import relativedelta


def get_kategori(score):
    if score >= 85:
        return {'label':'Sangat Baik','color':'#065f46','bg':'#dcfce7','border':'#a7f3d0','accent':'#10b981','icon':'bi-shield-check'}
    elif score >= 70:
        return {'label':'Baik','color':'#1d4ed8','bg':'#dbeafe','border':'#bfdbfe','accent':'#3b82f6','icon':'bi-shield'}
    elif score >= 50:
        return {'label':'Cukup','color':'#854d0e','bg':'#fef3c7','border':'#fde68a','accent':'#f59e0b','icon':'bi-shield-exclamation'}
    elif score >= 25:
        return {'label':'Buruk','color':'#9a3412','bg':'#fff7ed','border':'#fed7aa','accent':'#f97316','icon':'bi-shield-slash'}
    else:
        return {'label':'Kritis','color':'#991b1b','bg':'#fee2e2','border':'#fca5a5','accent':'#ef4444','icon':'bi-exclamation-triangle-fill'}


def save_snapshot_if_needed(device, score, kategori_label, breakdown):
    try:
        from health_index.models import HISnapshot
        today = date_type.today()
        HISnapshot.objects.get_or_create(
            device=device, bulan=today.month, tahun=today.year,
            defaults={'score': score, 'kategori': kategori_label, 'breakdown': breakdown}
        )
    except Exception:
        pass


def trigger_notifikasi(device, score, score_sebelumnya, kategori_label):
    try:
        from notifikasi.models import Notifikasi
        from maintenance.models import Maintenance

        # 1. Skor rendah (< 50)
        if score < 50:
            level = 'danger' if score < 25 else 'warning'
            Notifikasi.objects.get_or_create(
                device=device, tipe='hi_rendah', is_read=False,
                defaults={
                    'judul': f'Health Index Rendah — {device.nama}',
                    'pesan': f'Skor HI {device.nama} ({device.lokasi}) adalah {score} ({kategori_label}). Segera lakukan pemeriksaan.',
                    'level': level,
                    'url':   f'/health-index/{device.pk}/',
                }
            )
        else:
            # Kalau sudah membaik, hapus notif hi_rendah yang belum dibaca
            Notifikasi.objects.filter(device=device, tipe='hi_rendah', is_read=False).delete()

        # 2. Penurunan drastis ≥ 15 poin dari bulan lalu
        if score_sebelumnya is not None and (score_sebelumnya - score) >= 15:
            penurunan = score_sebelumnya - score
            Notifikasi.objects.get_or_create(
                device=device, tipe='hi_turun', is_read=False,
                defaults={
                    'judul': f'HI Turun Drastis — {device.nama}',
                    'pesan': f'Skor HI {device.nama} turun {penurunan} poin bulan ini ({score_sebelumnya} → {score}).',
                    'level': 'danger',
                    'url':   f'/health-index/{device.pk}/',
                }
            )

        # 3. Maintenance overdue
        last_m = Maintenance.objects.filter(device=device, status='Done').order_by('-date').first()
        if last_m:
            rd = relativedelta(timezone.now(), last_m.date)
            bulan_lalu = rd.years * 12 + rd.months
            if bulan_lalu > 6:
                Notifikasi.objects.get_or_create(
                    device=device, tipe='maintenance_overdue', is_read=False,
                    defaults={
                        'judul': f'Maintenance Overdue — {device.nama}',
                        'pesan': f'Maintenance terakhir {device.nama} sudah {bulan_lalu} bulan lalu ({last_m.date.strftime("%d %b %Y")}).',
                        'level': 'warning',
                        'url':   f'/view/{device.pk}/',
                    }
                )
            else:
                Notifikasi.objects.filter(device=device, tipe='maintenance_overdue', is_read=False).delete()
        else:
            Notifikasi.objects.get_or_create(
                device=device, tipe='maintenance_overdue', is_read=False,
                defaults={
                    'judul': f'Belum Ada Maintenance — {device.nama}',
                    'pesan': f'{device.nama} ({device.lokasi}) belum pernah tercatat maintenance.',
                    'level': 'warning',
                    'url':   f'/view/{device.pk}/',
                }
            )
    except Exception:
        pass


def calculate_hi(device, save_snapshot=True):
    from maintenance.models import Maintenance
    from gangguan.models import Gangguan

    score = 100
    breakdown = []
    today = date_type.today()
    now = timezone.now()

    # ── 1. Umur Peralatan
    if device.tahun_operasi:
        umur = today.year - device.tahun_operasi
        if umur >= 20:   deduksi, status, keterangan = -35, 'danger',  f'{umur} tahun — sudah melewati usia ekonomis'
        elif umur >= 15: deduksi, status, keterangan = -30, 'danger',  f'{umur} tahun — mendekati akhir usia pakai'
        elif umur >= 10: deduksi, status, keterangan = -20, 'warning', f'{umur} tahun — perlu perhatian lebih'
        elif umur >= 5:  deduksi, status, keterangan = -10, 'info',    f'{umur} tahun — masih dalam batas normal'
        else:            deduksi, status, keterangan =   0, 'good',    f'{umur} tahun — kondisi baru'
        nilai = f'{umur} tahun (sejak {device.tahun_operasi})'
    else:
        umur = None
        deduksi, status, keterangan = -10, 'unknown', 'Tahun operasi belum diisi'
        nilai = 'Tidak diketahui'
    score += deduksi
    breakdown.append({'faktor':'Umur Peralatan','icon':'bi-calendar3','nilai':nilai,'keterangan':keterangan,'deduksi':deduksi,'maks':-35,'status':status})

    # ── 2. Status Operasi
    if device.status_operasi == 'tidak_operasi':
        deduksi, status, keterangan = -15, 'danger', 'Peralatan sedang tidak beroperasi'
    else:
        deduksi, status, keterangan = 0, 'good', 'Peralatan beroperasi normal'
    score += deduksi
    breakdown.append({'faktor':'Status Operasi','icon':'bi-activity','nilai':device.get_status_operasi_display(),'keterangan':keterangan,'deduksi':deduksi,'maks':-15,'status':status})

    # ── 3. Maintenance Terakhir
    last_m = Maintenance.objects.filter(device=device, status='Done').order_by('-date').first()
    if last_m is None:
        deduksi, status_m, keterangan, nilai = -25, 'danger', 'Belum pernah dilakukan maintenance', 'Belum pernah'
    else:
        rd = relativedelta(now, last_m.date)
        bulan_lalu = rd.years * 12 + rd.months
        tgl_str = last_m.date.strftime('%d %b %Y')
        if bulan_lalu > 12:   deduksi, status_m, keterangan = -20, 'danger',  f'Sudah {bulan_lalu} bulan sejak maintenance terakhir'
        elif bulan_lalu > 6:  deduksi, status_m, keterangan = -10, 'warning', f'Sudah {bulan_lalu} bulan sejak maintenance terakhir'
        else:                 deduksi, status_m, keterangan =   0, 'good',    f'Maintenance rutin terpenuhi ({bulan_lalu} bulan lalu)'
        nilai = f'{tgl_str} ({bulan_lalu} bulan lalu)'
    score += deduksi
    breakdown.append({'faktor':'Maintenance Terakhir','icon':'bi-tools','nilai':nilai,'keterangan':keterangan,'deduksi':deduksi,'maks':-25,'status':status_m})

    # ── 4. Corrective Maintenance (1 tahun)
    satu_tahun_lalu = now - relativedelta(years=1)
    corrective_count = Maintenance.objects.filter(device=device, maintenance_type='Corrective', date__gte=satu_tahun_lalu).count()
    if corrective_count >= 3:   deduksi, status_c, keterangan = -15, 'danger',  f'{corrective_count}× corrective — indikasi masalah berulang'
    elif corrective_count == 2: deduksi, status_c, keterangan = -10, 'warning', f'{corrective_count}× corrective — perlu investigasi'
    elif corrective_count == 1: deduksi, status_c, keterangan =  -5, 'info',    f'{corrective_count}× corrective dalam setahun'
    else:                       deduksi, status_c, keterangan =   0, 'good',    'Tidak ada corrective maintenance dalam 1 tahun'
    score += deduksi
    breakdown.append({'faktor':'Corrective Maintenance (1 Tahun)','icon':'bi-wrench-adjustable','nilai':f'{corrective_count} kali','keterangan':keterangan,'deduksi':deduksi,'maks':-15,'status':status_c})

    # ── 5. Gangguan Aktif
    gangguan_open = Gangguan.objects.filter(peralatan=device, status__in=['open','in_progress'])
    gangguan_deduksi = 0
    for g in gangguan_open:
        gangguan_deduksi -= {'kritis':10,'tinggi':7,'sedang':4}.get(g.tingkat_keparahan, 2)
    gangguan_deduksi = max(gangguan_deduksi, -15)
    open_count = gangguan_open.count()
    if open_count == 0:   status_g, keterangan = 'good',    'Tidak ada gangguan aktif'
    elif open_count == 1: status_g, keterangan = 'warning', '1 gangguan aktif sedang ditangani'
    else:                 status_g, keterangan = 'danger',  f'{open_count} gangguan aktif belum terselesaikan'
    score += gangguan_deduksi
    breakdown.append({'faktor':'Gangguan Aktif','icon':'bi-lightning-charge','nilai':f'{open_count} gangguan','keterangan':keterangan,'deduksi':gangguan_deduksi,'maks':-15,'status':status_g})

    # ── Final
    score = max(0, min(100, score))
    kategori = get_kategori(score)
    total_maintenance = Maintenance.objects.filter(device=device).count()
    total_gangguan    = Gangguan.objects.filter(peralatan=device).count()

    if save_snapshot:
        save_snapshot_if_needed(device, score, kategori['label'], breakdown)
        try:
            from health_index.models import HISnapshot
            prev_month = date_type(today.year, today.month, 1) - relativedelta(months=1)
            prev_snap = HISnapshot.objects.filter(device=device, bulan=prev_month.month, tahun=prev_month.year).first()
            score_sebelumnya = prev_snap.score if prev_snap else None
        except Exception:
            score_sebelumnya = None
        trigger_notifikasi(device, score, score_sebelumnya, kategori['label'])

    return {
        'score': score, 'kategori': kategori, 'breakdown': breakdown,
        'total_maintenance': total_maintenance, 'total_gangguan': total_gangguan, 'umur': umur,
    }
