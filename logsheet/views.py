import datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone

from .models import LogsheetTitik, LogsheetNilai
from . import export as xls


def _bisa_logsheet(user):
    return user.is_superuser or getattr(
        getattr(user, 'profile', None), 'role', '') in ('opsis', 'opsis_view')


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

    # ringkasan ketersediaan data untuk tanggal terpilih
    total_titik = LogsheetTitik.objects.filter(aktif=True).count()
    n_nilai = LogsheetNilai.objects.filter(tanggal=tanggal).count()
    slot_terisi = (LogsheetNilai.objects.filter(tanggal=tanggal)
                   .values_list('slot', flat=True).distinct().count())
    tanggal_tersedia = list(LogsheetNilai.objects
                            .order_by('-tanggal').values_list('tanggal', flat=True)
                            .distinct()[:31])

    return render(request, 'logsheet/index.html', {
        'pembangkit_list': _pembangkit_list(),
        'tanggal': tanggal, 'today': today,
        'total_titik': total_titik,
        'n_nilai': n_nilai, 'slot_terisi': slot_terisi,
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
