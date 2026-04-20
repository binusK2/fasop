"""
health_index/calculator.py

Kalkulasi Health Index menggunakan Factor Registry System.
Faktor dan bobotnya diambil dari KonfigurasiHI (database),
sehingga bisa dikonfigurasi tanpa edit kode.
"""

from datetime import date as date_type
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from fasop.hashids_helper import encode as _hid


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

        if score < 50:
            level = 'danger' if score < 25 else 'warning'
            Notifikasi.objects.get_or_create(
                device=device, tipe='hi_rendah', is_read=False,
                defaults={
                    'judul': f'Health Index Rendah — {device.nama}',
                    'pesan': f'Skor HI {device.nama} ({device.lokasi}) adalah {score} ({kategori_label}).',
                    'level': level,
                    'url':   f'/health-index/{_hid(device.pk)}/',
                }
            )
        else:
            Notifikasi.objects.filter(device=device, tipe='hi_rendah', is_read=False).delete()

        if score_sebelumnya is not None and (score_sebelumnya - score) >= 15:
            penurunan = score_sebelumnya - score
            Notifikasi.objects.get_or_create(
                device=device, tipe='hi_turun', is_read=False,
                defaults={
                    'judul': f'HI Turun Drastis — {device.nama}',
                    'pesan': f'Skor HI {device.nama} turun {penurunan} poin bulan ini ({score_sebelumnya} → {score}).',
                    'level': 'danger',
                    'url':   f'/health-index/{_hid(device.pk)}/',
                }
            )

        last_m = Maintenance.objects.filter(device=device, status='Done').order_by('-date').first()
        if last_m:
            rd = relativedelta(timezone.now(), last_m.date)
            bulan_lalu = rd.years * 12 + rd.months
            if bulan_lalu > 6:
                Notifikasi.objects.get_or_create(
                    device=device, tipe='maintenance_overdue', is_read=False,
                    defaults={
                        'judul': f'Maintenance Overdue — {device.nama}',
                        'pesan': f'Maintenance terakhir {device.nama} sudah {bulan_lalu} bulan lalu.',
                        'level': 'warning',
                        'url':   f'/view/{_hid(device.pk)}/',
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
                    'url':   f'/view/{_hid(device.pk)}/',
                }
            )
    except Exception:
        pass


def calculate_hi(device, save_snapshot=True):
    """
    Hitung Health Index untuk satu Device menggunakan Factor Registry.
    Bobot tiap faktor diambil dari KonfigurasiHI (DB).
    """
    from health_index.models import KonfigurasiHI
    from health_index.registry import get_factor
    from maintenance.models import Maintenance
    from gangguan.models import Gangguan

    # Ambil / inisialisasi konfigurasi dari DB
    configs = KonfigurasiHI.get_or_init()

    score     = 100
    breakdown = []
    today     = date_type.today()

    for cfg in configs:
        if not cfg.aktif:
            continue

        factor = get_factor(cfg.faktor_key)
        if factor is None:
            continue

        # Cek apakah faktor berlaku untuk jenis device ini
        if not factor.is_applicable(device):
            continue

        result = factor.calculate(device, cfg.bobot_maks)
        score += result['deduksi']
        breakdown.append(result)

    score = max(0, min(100, score))
    kategori          = get_kategori(score)
    total_maintenance = Maintenance.objects.filter(device=device).count()
    total_gangguan    = Gangguan.objects.filter(peralatan=device).count()

    # Umur untuk konteks
    umur = (today.year - device.tahun_operasi) if device.tahun_operasi else None

    if save_snapshot:
        save_snapshot_if_needed(device, score, kategori['label'], breakdown)
        try:
            from health_index.models import HISnapshot
            prev_month = date_type(today.year, today.month, 1) - relativedelta(months=1)
            prev_snap  = HISnapshot.objects.filter(
                device=device, bulan=prev_month.month, tahun=prev_month.year
            ).first()
            score_sebelumnya = prev_snap.score if prev_snap else None
        except Exception:
            score_sebelumnya = None
        trigger_notifikasi(device, score, score_sebelumnya, kategori['label'])

    return {
        'score':             score,
        'kategori':          kategori,
        'breakdown':         breakdown,
        'total_maintenance': total_maintenance,
        'total_gangguan':    total_gangguan,
        'umur':              umur,
    }
