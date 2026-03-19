from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import Notifikasi


@login_required
def notifikasi_list(request):
    """Halaman daftar semua notifikasi."""
    filter_level = request.GET.get('level', '')
    filter_read  = request.GET.get('read', '')

    notifs = Notifikasi.objects.select_related('device').all()

    if filter_level:
        notifs = notifs.filter(level=filter_level)
    if filter_read == '0':
        notifs = notifs.filter(is_read=False)
    elif filter_read == '1':
        notifs = notifs.filter(is_read=True)

    unread_count = Notifikasi.objects.filter(is_read=False).count()

    return render(request, 'notifikasi/notifikasi_list.html', {
        'notifs':        notifs,
        'unread_count':  unread_count,
        'filter_level':  filter_level,
        'filter_read':   filter_read,
    })


@login_required
def notifikasi_read(request, pk):
    """Tandai satu notifikasi sebagai sudah dibaca (AJAX)."""
    if request.method == 'POST':
        notif = get_object_or_404(Notifikasi, pk=pk)
        notif.is_read = True
        notif.read_at = timezone.now()
        notif.save()
        unread_count = Notifikasi.objects.filter(is_read=False).count()
        return JsonResponse({'ok': True, 'unread_count': unread_count})
    return JsonResponse({'ok': False}, status=405)


@login_required
def notifikasi_read_all(request):
    """Tandai semua notifikasi sebagai sudah dibaca (AJAX)."""
    if request.method == 'POST':
        Notifikasi.objects.filter(is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return JsonResponse({'ok': True, 'unread_count': 0})
    return JsonResponse({'ok': False}, status=405)


@login_required
def notifikasi_count(request):
    """API ringan — kembalikan jumlah notif belum dibaca (untuk polling)."""
    count = Notifikasi.objects.filter(is_read=False).count()
    return JsonResponse({'unread_count': count})
