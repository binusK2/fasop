from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from devices.permissions import require_can_edit, require_can_delete
from django.http import JsonResponse
from django.db.models import Q, Avg
from django.utils import timezone
from datetime import date as date_type
import calendar

from .models import JadwalKunjungan
from devices.models import Device
from maintenance.models import Maintenance


# ── Helper: ambil semua lokasi unik dari device ───────────────────────────────
def _get_lokasi_list():
    from django.db.models.functions import Trim
    return (
        Device.objects.filter(is_deleted=False)
        .exclude(lokasi__isnull=True).exclude(lokasi__exact='')
        .annotate(lc=Trim('lokasi'))
        .values_list('lc', flat=True)
        .distinct().order_by('lc')
    )


# ── Helper: hitung skor prioritas lokasi ─────────────────────────────────────
def _hitung_prioritas(lokasi):
    """
    Skor prioritas 0–100 berdasarkan:
    - Berapa bulan sejak maintenance preventive terakhir di lokasi (40%)
    - Rata-rata HI device di lokasi (35%, diinvers: HI rendah → prioritas tinggi)
    - Jumlah device di lokasi (25%)
    """
    today = date_type.today()

    devices = Device.objects.filter(lokasi__iexact=lokasi, is_deleted=False)
    total_device = devices.count()
    if total_device == 0:
        return 0

    # 1. Bulan sejak preventive terakhir di lokasi ini
    last_pm = (
        Maintenance.objects
        .filter(device__lokasi__iexact=lokasi, maintenance_type='Preventive', status='Done')
        .order_by('-date').first()
    )
    if last_pm is None:
        bulan_lalu = 24   # belum pernah → anggap 24 bulan
    else:
        from dateutil.relativedelta import relativedelta
        rd = relativedelta(today, last_pm.date.date() if hasattr(last_pm.date, 'date') else last_pm.date)
        bulan_lalu = rd.years * 12 + rd.months

    skor_umur = min(bulan_lalu / 24 * 100, 100)  # maks 24 bulan → 100%

    # 2. Rata-rata HI (tanpa simpan snapshot untuk hemat resource)
    try:
        from health_index.calculator import calculate_hi
        hi_scores = [calculate_hi(d, save_snapshot=False)['score'] for d in devices[:10]]
        avg_hi = sum(hi_scores) / len(hi_scores) if hi_scores else 75
    except Exception:
        avg_hi = 75
    skor_hi = 100 - avg_hi   # HI rendah → prioritas tinggi

    # 3. Jumlah device (lebih banyak device → lebih prioritas, maks 30)
    skor_device = min(total_device / 30 * 100, 100)

    total = round(skor_umur * 0.40 + skor_hi * 0.35 + skor_device * 0.25)
    return min(total, 100)


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
def jadwal_list(request):
    """Halaman utama — daftar jadwal + ranking prioritas lokasi."""
    filter_status = request.GET.get('status', '')
    filter_tahun  = request.GET.get('tahun', str(date_type.today().year))
    search        = request.GET.get('q', '').strip()

    jadwals = JadwalKunjungan.objects.select_related('created_by').all()
    if filter_status:
        jadwals = jadwals.filter(status=filter_status)
    if filter_tahun:
        jadwals = jadwals.filter(tahun_rencana=int(filter_tahun))
    if search:
        jadwals = jadwals.filter(lokasi__icontains=search)

    # Sync status otomatis
    for j in jadwals:
        j.sync_status()

    # Attach progress ke setiap jadwal
    jadwal_data = []
    for j in jadwals:
        prog = j.get_progress()
        jadwal_data.append({'jadwal': j, 'progress': prog})

    # Summary
    semua = JadwalKunjungan.objects.filter(tahun_rencana=int(filter_tahun) if filter_tahun else date_type.today().year)
    summary = {
        'total':       semua.count(),
        'planned':     semua.filter(status='planned').count(),
        'in_progress': semua.filter(status='in_progress').count(),
        'done':        semua.filter(status='done').count(),
    }

    # Ranking prioritas lokasi yang belum punya jadwal tahun ini
    lokasi_sudah_dijadwal = set(
        JadwalKunjungan.objects
        .filter(tahun_rencana=date_type.today().year)
        .values_list('lokasi', flat=True)
    )
    lokasi_belum = [l for l in _get_lokasi_list() if l not in lokasi_sudah_dijadwal]
    ranking = []
    for lok in lokasi_belum:
        dev_count = Device.objects.filter(lokasi__iexact=lok, is_deleted=False).count()
        prioritas = _hitung_prioritas(lok)
        ranking.append({'lokasi': lok, 'prioritas': prioritas, 'device_count': dev_count})
    ranking.sort(key=lambda x: x['prioritas'], reverse=True)
    ranking = ranking[:8]

    # Daftar tahun untuk filter
    tahun_list = list(range(date_type.today().year - 2, date_type.today().year + 3))
    bulan_list = [(i, calendar.month_name[i]) for i in range(1, 13)]

    return render(request, 'jadwal/jadwal_list.html', {
        'jadwal_data':    jadwal_data,
        'summary':        summary,
        'ranking':        ranking,
        'filter_status':  filter_status,
        'filter_tahun':   filter_tahun,
        'search':         search,
        'tahun_list':     tahun_list,
        'lokasi_list':    _get_lokasi_list(),
        'bulan_list':     bulan_list,
    })


@login_required
@require_can_edit
def jadwal_create(request):
    """Buat jadwal kunjungan baru."""
    if request.method == 'POST':
        lokasi       = request.POST.get('lokasi', '').strip()
        bulan        = int(request.POST.get('bulan_rencana', 0))
        tahun        = int(request.POST.get('tahun_rencana', 0))
        catatan      = request.POST.get('catatan', '').strip()

        if lokasi and bulan and tahun:
            jadwal, created = JadwalKunjungan.objects.get_or_create(
                lokasi=lokasi.upper(),
                bulan_rencana=bulan,
                tahun_rencana=tahun,
                defaults={'catatan': catatan, 'created_by': request.user}
            )
            return redirect('jadwal_detail', pk=jadwal.pk)

    return redirect('jadwal_list')


@login_required
def jadwal_detail(request, pk):
    """Detail satu jadwal kunjungan — progress per device."""
    jadwal = get_object_or_404(JadwalKunjungan, pk=pk)
    jadwal.sync_status()

    devices = Device.objects.filter(
        lokasi__iexact=jadwal.lokasi, is_deleted=False
    ).select_related('jenis').order_by('jenis__name', 'nama')

    # Cek tiap device: sudah ada maintenance Preventive di periode ini?
    device_data = []
    for d in devices:
        maintenance_periode = Maintenance.objects.filter(
            device=d,
            maintenance_type='Preventive',
            date__year=jadwal.tahun_rencana,
            date__month=jadwal.bulan_rencana,
        ).order_by('-date').first()

        # HI device
        try:
            from health_index.calculator import calculate_hi
            hi = calculate_hi(d, save_snapshot=False)
            hi_score    = hi['score']
            hi_kategori = hi['kategori']
        except Exception:
            hi_score    = None
            hi_kategori = None

        device_data.append({
            'device':             d,
            'maintenance_periode': maintenance_periode,
            'selesai':            maintenance_periode is not None,
            'hi_score':           hi_score,
            'hi_kategori':        hi_kategori,
        })

    progress = jadwal.get_progress()

    return render(request, 'jadwal/jadwal_detail.html', {
        'jadwal':      jadwal,
        'device_data': device_data,
        'progress':    progress,
    })


@login_required
def jadwal_done(request, pk):
    """Manual tandai jadwal sebagai Done."""
    if request.method == 'POST':
        jadwal = get_object_or_404(JadwalKunjungan, pk=pk)
        jadwal.status = 'done'
        jadwal.save(update_fields=['status', 'updated_at'])
    return redirect('jadwal_detail', pk=pk)


@login_required
@require_can_delete
def jadwal_delete(request, pk):
    """Hapus jadwal."""
    if request.method == 'POST':
        jadwal = get_object_or_404(JadwalKunjungan, pk=pk)
        jadwal.delete()
    return redirect('jadwal_list')
