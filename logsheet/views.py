import datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count

from devices.permissions import can_view_opsis
from .models import LogsheetTitik, LogsheetNilai
from . import export as xls

JUMLAH_SLOT = 48


def _slot_label(i):
    """slot i -> jam. slot 0 = 00:30, … slot 47 = 24:00."""
    menit = (i + 1) * 30
    if menit == 1440:
        return '24:00'
    return f'{menit // 60:02d}:{menit % 60:02d}'


def _bisa_logsheet(user):
    """Superuser, role Opsis/Opsis View, atau AM — sama dengan Respons
    Pembangkit. Aturan rolenya di devices.models.UserProfile.bisa_lihat_opsis."""
    return can_view_opsis(user)


def _pembangkit_list():
    try:
        from opsis.views import _pembangkit_aktif
        return _pembangkit_aktif()
    except Exception:
        return []


@login_required
def index(request):
    if not _bisa_logsheet(request.user):
        messages.error(request, 'Anda tidak memiliki akses ke Logsheet.')
        return redirect('/')

    today = timezone.localdate()
    tgl_raw = (request.GET.get('tanggal') or '').strip()
    try:
        tanggal = datetime.date.fromisoformat(tgl_raw) if tgl_raw else today
    except ValueError:
        tanggal = today

    # ── ringkasan ketersediaan data untuk tanggal terpilih ──
    total_titik = LogsheetTitik.objects.filter(aktif=True).count()
    n_nilai = LogsheetNilai.objects.filter(tanggal=tanggal, nilai__isnull=False).count()

    # jumlah nilai terisi per slot (semua titik aktif)
    per_slot = dict(LogsheetNilai.objects
                    .filter(tanggal=tanggal, nilai__isnull=False)
                    .values_list('slot').annotate(n=Count('id')))
    slots = []
    for i in range(JUMLAH_SLOT):
        f = per_slot.get(i, 0)
        status = 'full' if f >= total_titik and total_titik else ('part' if f else 'empty')
        slots.append({'i': i, 'label': _slot_label(i), 'filled': f, 'status': status})
    slot_terisi = sum(1 for s in slots if s['filled'])

    # ── detail per titik untuk satu sheet (default sheet pertama) ──
    sheet_list = list(LogsheetTitik.objects.filter(aktif=True)
                      .values_list('sheet', flat=True).distinct().order_by('sheet'))
    sheet = request.GET.get('sheet') or (sheet_list[0] if sheet_list else '')
    detail_titik = list(LogsheetTitik.objects.filter(aktif=True, sheet=sheet)
                        .order_by('baris', 'kol0'))
    ids = [t.id for t in detail_titik]
    by_tt = {}
    for tid, s, v in (LogsheetNilai.objects
                      .filter(titik_id__in=ids, tanggal=tanggal)
                      .values_list('titik_id', 'slot', 'nilai')):
        by_tt.setdefault(tid, {})[s] = v
    detail_rows = []
    for t in detail_titik:
        cells = by_tt.get(t.id, {})
        detail_rows.append({
            'nama': t.nama or t.key,
            'besaran': t.get_besaran_display(),
            'terisi': sum(1 for i in range(JUMLAH_SLOT) if cells.get(i) is not None),
            'cells': [cells.get(i) for i in range(JUMLAH_SLOT)],
        })

    tanggal_tersedia = list(LogsheetNilai.objects
                            .order_by('-tanggal').values_list('tanggal', flat=True)
                            .distinct()[:31])

    return render(request, 'logsheet/index.html', {
        'pembangkit_list': _pembangkit_list(),
        'tanggal': tanggal, 'today': today,
        'total_titik': total_titik,
        'n_nilai': n_nilai, 'slot_terisi': slot_terisi,
        'slots': slots,
        'slot_labels': [_slot_label(i) for i in range(JUMLAH_SLOT)],
        'sheet_list': sheet_list, 'sheet': sheet,
        'detail_rows': detail_rows,
        'tanggal_tersedia': tanggal_tersedia,
        'ada_konfig': total_titik > 0,
    })


@login_required
def export_excel(request):
    if not _bisa_logsheet(request.user):
        messages.error(request, 'Anda tidak memiliki akses ke Logsheet.')
        return redirect('/')

    tgl_raw = (request.GET.get('tanggal') or '').strip()
    try:
        tanggal = datetime.date.fromisoformat(tgl_raw) if tgl_raw else timezone.localdate()
    except ValueError:
        tanggal = timezone.localdate()

    wb = xls.build_workbook(tanggal)
    fname = f'LOGSHEET_MKS_{tanggal:%Y%m%d}.xlsx'
    return xls.workbook_to_response(wb, fname)
