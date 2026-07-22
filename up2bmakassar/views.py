from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .models import KinerjaAnalogHarian, KinerjaDigitalHarian


def _parse_tanggal(request, default_days_back=1):
    raw = request.GET.get('tanggal')
    if raw:
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError:
            pass
    return timezone.localdate() - timedelta(days=default_days_back)


def _ringkasan(qs):
    """Rata-rata performance & jumlah titik dari satu queryset kinerja harian."""
    total = qs.count()
    if total == 0:
        return {'jumlah_titik': 0, 'rata_rata': 0, 'terbaik': None, 'terburuk': None}
    rata_rata = sum(r.performance for r in qs) / total
    terbaik = max(qs, key=lambda r: r.performance)
    terburuk = min(qs, key=lambda r: r.performance)
    return {'jumlah_titik': total, 'rata_rata': rata_rata, 'terbaik': terbaik, 'terburuk': terburuk}


@login_required
def dashboard(request):
    tanggal = timezone.localdate() - timedelta(days=1)
    ringkasan_analog = _ringkasan(KinerjaAnalogHarian.objects.filter(tanggal=tanggal))
    ringkasan_digital = _ringkasan(KinerjaDigitalHarian.objects.filter(tanggal=tanggal))
    return render(request, 'up2bmakassar/dashboard.html', {
        'tanggal': tanggal,
        'ringkasan_analog': ringkasan_analog,
        'ringkasan_digital': ringkasan_digital,
    })


def _kinerja_list(request, model, template):
    tanggal = _parse_tanggal(request)
    q = request.GET.get('q', '').strip()

    qs = model.objects.filter(tanggal=tanggal).order_by('path1', 'path2', 'path3')
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(path1__icontains=q) | Q(path2__icontains=q) | Q(path3__icontains=q)
            | Q(point_number__icontains=q)
        )

    ringkasan = _ringkasan(qs)

    return render(request, template, {
        'tanggal': tanggal,
        'q': q,
        'rows': qs,
        'ringkasan': ringkasan,
    })


@login_required
def kinerja_analog(request):
    return _kinerja_list(request, KinerjaAnalogHarian, 'up2bmakassar/kinerja_analog.html')


@login_required
def kinerja_digital(request):
    return _kinerja_list(request, KinerjaDigitalHarian, 'up2bmakassar/kinerja_digital.html')
