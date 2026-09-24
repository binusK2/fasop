from devices.models import UserProfile


def whitelist_operator(request, credentials):
    """Akun role Operator dipakai bersama banyak orang — jangan pernah dikunci django-axes."""
    username = (credentials or {}).get('username')
    if not username:
        return False
    return UserProfile.objects.filter(user__username=username, role='operator').exists()


# Panjang kolom AccessAttempt.username / AccessFailureLog.username di django-axes.
AXES_USERNAME_MAKS = 255


def username_terpotong(request, credentials):
    """Username untuk django-axes, dipotong sepanjang kolomnya.

    axes memotong User-Agent dan path sendiri tapi TIDAK memotong username,
    jadi POST /login/ dengan username ribuan karakter membuat PostgreSQL
    menolak INSERT percobaan gagalnya (varchar 255) dan halaman login jatuh
    ke HTTP 500 — ditemukan pemindai Wapiti. Tetap dicatat (bukan dibuang)
    supaya username panjang pun tetap bisa dikunci setelah 5x gagal.
    """
    username = (credentials or {}).get('username')
    if username is None:
        username = request.POST.get('username')
    if username is None:
        return None
    return str(username)[:AXES_USERNAME_MAKS]
