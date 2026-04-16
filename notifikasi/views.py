from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import Notifikasi


@login_required
def notifikasi_list(request):
    """Halaman daftar notifikasi — per user + global."""
    from django.db.models import Q
    filter_level = request.GET.get('level', '')
    filter_read  = request.GET.get('read', '')

    notifs = Notifikasi.objects.select_related('device').filter(
        Q(user=request.user) | Q(user__isnull=True)
    )

    if filter_level:
        notifs = notifs.filter(level=filter_level)
    if filter_read == '0':
        notifs = notifs.filter(is_read=False)
    elif filter_read == '1':
        notifs = notifs.filter(is_read=True)

    unread_count = notifs.filter(is_read=False).count()

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
    """Tandai semua notifikasi user sebagai sudah dibaca."""
    from django.db.models import Q
    if request.method == 'POST':
        Notifikasi.objects.filter(
            Q(user=request.user) | Q(user__isnull=True),
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return JsonResponse({'ok': True, 'unread_count': 0})
    return JsonResponse({'ok': False}, status=405)


@login_required
def notifikasi_count(request):
    """API ringan — kembalikan jumlah notif belum dibaca (untuk polling)."""
    count = Notifikasi.objects.filter(is_read=False).count()
    return JsonResponse({'unread_count': count})


@login_required
def notifikasi_delete(request, pk):
    """Hapus satu notifikasi (AJAX POST)."""
    from django.db.models import Q
    if request.method == 'POST':
        notif = get_object_or_404(
            Notifikasi, pk=pk,
        )
        # Only allow deleting own or global notifications
        if notif.user is not None and notif.user != request.user:
            return JsonResponse({'ok': False, 'error': 'Forbidden'}, status=403)
        notif.delete()
        from django.db.models import Q
        unread_count = Notifikasi.objects.filter(
            Q(user=request.user) | Q(user__isnull=True),
            is_read=False
        ).count()
        return JsonResponse({'ok': True, 'deleted_id': pk, 'unread_count': unread_count})
    return JsonResponse({'ok': False}, status=405)


@login_required
def notifikasi_delete_read(request):
    """Hapus semua notifikasi yang sudah dibaca (AJAX POST)."""
    from django.db.models import Q
    if request.method == 'POST':
        deleted_count, _ = Notifikasi.objects.filter(
            Q(user=request.user) | Q(user__isnull=True),
            is_read=True
        ).delete()
        return JsonResponse({'ok': True, 'deleted_count': deleted_count})
    return JsonResponse({'ok': False}, status=405)


# ── Helper: kirim notif ke semua AM ──────────────────────────────────────────
def notif_ke_am(tipe, judul, pesan, level='info', url='', device=None):
    """
    Buat notifikasi untuk semua user AM dan superuser.
    Dipanggil dari views lain saat event penting terjadi.
    """
    try:
        from django.contrib.auth.models import User
        from notifikasi.models import Notifikasi

        # Ambil semua AM dan superuser
        am_users = User.objects.filter(
            profile__role='asisten_manager'
        ).union(
            User.objects.filter(is_superuser=True)
        )

        for user in am_users:
            # Cegah duplikat — cek apakah notif yang sama sudah ada & belum dibaca
            sudah_ada = Notifikasi.objects.filter(
                user=user, tipe=tipe, judul=judul, is_read=False
            ).exists()
            if not sudah_ada:
                Notifikasi.objects.create(
                    user   = user,
                    tipe   = tipe,
                    judul  = judul,
                    pesan  = pesan,
                    level  = level,
                    url    = url,
                    device = device,
                )
    except Exception:
        pass
