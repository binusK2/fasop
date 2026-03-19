"""
health_index/calculator.py

Modul perhitungan Health Index (HI) peralatan.

Rumus:
    HI = 100 − (pengurangan dari 5 faktor)

Faktor & bobot maksimal pengurangan:
    1. Umur Peralatan            : maks −35
    2. Status Operasi            : maks −15
    3. Maintenance Terakhir      : maks −25
    4. Corrective Maintenance    : maks −15
    5. Gangguan Aktif            : maks −15
    ─────────────────────────────────────────
    Total maks pengurangan       : −105  → skor minimum = 0
    (skor diklem antara 0–100)

Kategori:
    85–100 : Sangat Baik   🟢
    70–84  : Baik          🔵
    50–69  : Cukup         🟡
    25–49  : Buruk         🟠
     0–24  : Kritis        🔴
"""

from datetime import date as date_type
from django.utils import timezone
from dateutil.relativedelta import relativedelta


# ─── Kategori ────────────────────────────────────────────────────────────────

def get_kategori(score):
    if score >= 85:
        return {
            'label':  'Sangat Baik',
            'color':  '#065f46',
            'bg':     '#dcfce7',
            'border': '#a7f3d0',
            'accent': '#10b981',
            'icon':   'bi-shield-check',
        }
    elif score >= 70:
        return {
            'label':  'Baik',
            'color':  '#1d4ed8',
            'bg':     '#dbeafe',
            'border': '#bfdbfe',
            'accent': '#3b82f6',
            'icon':   'bi-shield',
        }
    elif score >= 50:
        return {
            'label':  'Cukup',
            'color':  '#854d0e',
            'bg':     '#fef3c7',
            'border': '#fde68a',
            'accent': '#f59e0b',
            'icon':   'bi-shield-exclamation',
        }
    elif score >= 25:
        return {
            'label':  'Buruk',
            'color':  '#9a3412',
            'bg':     '#fff7ed',
            'border': '#fed7aa',
            'accent': '#f97316',
            'icon':   'bi-shield-slash',
        }
    else:
        return {
            'label':  'Kritis',
            'color':  '#991b1b',
            'bg':     '#fee2e2',
            'border': '#fca5a5',
            'accent': '#ef4444',
            'icon':   'bi-exclamation-triangle-fill',
        }


# ─── Kalkulasi Utama ─────────────────────────────────────────────────────────

def calculate_hi(device):
    """
    Hitung Health Index untuk satu Device.
    Mengembalikan dict berisi skor, kategori, dan breakdown faktor.
    """
    from maintenance.models import Maintenance
    from gangguan.models import Gangguan

    score = 100
    breakdown = []
    today = date_type.today()
    now = timezone.now()

    # ── 1. Umur Peralatan ─────────────────────────────────────────
    if device.tahun_operasi:
        umur = today.year - device.tahun_operasi
        if umur >= 20:
            deduksi = -35
            status = 'danger'
            keterangan = f'{umur} tahun — sudah melewati usia ekonomis'
        elif umur >= 15:
            deduksi = -30
            status = 'danger'
            keterangan = f'{umur} tahun — mendekati akhir usia pakai'
        elif umur >= 10:
            deduksi = -20
            status = 'warning'
            keterangan = f'{umur} tahun — perlu perhatian lebih'
        elif umur >= 5:
            deduksi = -10
            status = 'info'
            keterangan = f'{umur} tahun — masih dalam batas normal'
        else:
            deduksi = 0
            status = 'good'
            keterangan = f'{umur} tahun — kondisi baru'
        nilai = f'{umur} tahun (sejak {device.tahun_operasi})'
    else:
        umur = None
        deduksi = -10
        status = 'unknown'
        keterangan = 'Tahun operasi belum diisi'
        nilai = 'Tidak diketahui'

    score += deduksi
    breakdown.append({
        'faktor':     'Umur Peralatan',
        'icon':       'bi-calendar3',
        'nilai':      nilai,
        'keterangan': keterangan,
        'deduksi':    deduksi,
        'maks':       -35,
        'status':     status,
    })

    # ── 2. Status Operasi ─────────────────────────────────────────
    if device.status_operasi == 'tidak_operasi':
        deduksi = -15
        status  = 'danger'
        keterangan = 'Peralatan sedang tidak beroperasi'
    else:
        deduksi = 0
        status  = 'good'
        keterangan = 'Peralatan beroperasi normal'

    score += deduksi
    breakdown.append({
        'faktor':     'Status Operasi',
        'icon':       'bi-activity',
        'nilai':      device.get_status_operasi_display(),
        'keterangan': keterangan,
        'deduksi':    deduksi,
        'maks':       -15,
        'status':     status,
    })

    # ── 3. Maintenance Terakhir ───────────────────────────────────
    last_m = (
        Maintenance.objects
        .filter(device=device, status='Done')
        .order_by('-date')
        .first()
    )
    if last_m is None:
        deduksi    = -25
        status_m   = 'danger'
        keterangan = 'Belum pernah dilakukan maintenance'
        nilai      = 'Belum pernah'
    else:
        rd = relativedelta(now, last_m.date)
        bulan_lalu = rd.years * 12 + rd.months
        tgl_str = last_m.date.strftime('%d %b %Y')
        if bulan_lalu > 12:
            deduksi    = -20
            status_m   = 'danger'
            keterangan = f'Sudah {bulan_lalu} bulan sejak maintenance terakhir'
        elif bulan_lalu > 6:
            deduksi    = -10
            status_m   = 'warning'
            keterangan = f'Sudah {bulan_lalu} bulan sejak maintenance terakhir'
        else:
            deduksi    = 0
            status_m   = 'good'
            keterangan = f'Maintenance rutin terpenuhi ({bulan_lalu} bulan lalu)'
        nilai = f'{tgl_str} ({bulan_lalu} bulan lalu)'

    score += deduksi
    breakdown.append({
        'faktor':     'Maintenance Terakhir',
        'icon':       'bi-tools',
        'nilai':      nilai,
        'keterangan': keterangan,
        'deduksi':    deduksi,
        'maks':       -25,
        'status':     status_m,
    })

    # ── 4. Corrective Maintenance (1 tahun terakhir) ──────────────
    satu_tahun_lalu = now - relativedelta(years=1)
    corrective_count = (
        Maintenance.objects
        .filter(device=device, maintenance_type='Corrective', date__gte=satu_tahun_lalu)
        .count()
    )
    if corrective_count >= 3:
        deduksi    = -15
        status_c   = 'danger'
        keterangan = f'{corrective_count}× corrective — indikasi masalah berulang'
    elif corrective_count == 2:
        deduksi    = -10
        status_c   = 'warning'
        keterangan = f'{corrective_count}× corrective — perlu investigasi'
    elif corrective_count == 1:
        deduksi    = -5
        status_c   = 'info'
        keterangan = f'{corrective_count}× corrective dalam setahun'
    else:
        deduksi    = 0
        status_c   = 'good'
        keterangan = 'Tidak ada corrective maintenance dalam 1 tahun'

    score += deduksi
    breakdown.append({
        'faktor':     'Corrective Maintenance (1 Tahun)',
        'icon':       'bi-wrench-adjustable',
        'nilai':      f'{corrective_count} kali',
        'keterangan': keterangan,
        'deduksi':    deduksi,
        'maks':       -15,
        'status':     status_c,
    })

    # ── 5. Gangguan Aktif ─────────────────────────────────────────
    gangguan_open = (
        Gangguan.objects
        .filter(peralatan=device, status__in=['open', 'in_progress'])
    )
    gangguan_deduksi = 0
    for g in gangguan_open:
        if g.tingkat_keparahan == 'kritis':
            gangguan_deduksi -= 10
        elif g.tingkat_keparahan == 'tinggi':
            gangguan_deduksi -= 7
        elif g.tingkat_keparahan == 'sedang':
            gangguan_deduksi -= 4
        else:
            gangguan_deduksi -= 2
    gangguan_deduksi = max(gangguan_deduksi, -15)

    open_count = gangguan_open.count()
    if open_count == 0:
        status_g   = 'good'
        keterangan = 'Tidak ada gangguan aktif'
    elif open_count == 1:
        status_g   = 'warning'
        keterangan = f'1 gangguan aktif sedang ditangani'
    else:
        status_g   = 'danger'
        keterangan = f'{open_count} gangguan aktif belum terselesaikan'

    score += gangguan_deduksi
    breakdown.append({
        'faktor':     'Gangguan Aktif',
        'icon':       'bi-lightning-charge',
        'nilai':      f'{open_count} gangguan',
        'keterangan': keterangan,
        'deduksi':    gangguan_deduksi,
        'maks':       -15,
        'status':     status_g,
    })

    # ── Final ─────────────────────────────────────────────────────
    score = max(0, min(100, score))
    kategori = get_kategori(score)

    # Info tambahan untuk summary
    total_maintenance = Maintenance.objects.filter(device=device).count()
    total_gangguan    = Gangguan.objects.filter(peralatan=device).count()

    return {
        'score':             score,
        'kategori':          kategori,
        'breakdown':         breakdown,
        'total_maintenance': total_maintenance,
        'total_gangguan':    total_gangguan,
        'umur':              umur,
    }
