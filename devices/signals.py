from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@receiver(user_logged_in)
def update_active_session(sender, request, user, **kwargs):
    """
    Saat user berhasil login, simpan session key saat ini ke UserProfile.
    Ini secara efektif menginvalidasi sesi lama di perangkat lain —
    SingleSessionMiddleware akan mendeteksi ketidakcocokan dan logout paksa.
    """
    try:
        profile = user.profile
        # Pastikan session sudah dibuat (session key tersedia)
        if not request.session.session_key:
            request.session.create()
        profile.active_session_key = request.session.session_key
        profile.save(update_fields=['active_session_key'])
    except Exception:
        pass

    # Catat log login
    try:
        from devices.models import UserLoginLog
        UserLoginLog.objects.create(
            user=user,
            action='login',
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
        )
    except Exception:
        pass


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Catat log logout dan bersihkan active_session_key."""
    if user is None:
        return
    try:
        profile = user.profile
        profile.active_session_key = ''
        profile.save(update_fields=['active_session_key'])
    except Exception:
        pass

    try:
        from devices.models import UserLoginLog
        UserLoginLog.objects.create(
            user=user,
            action='logout',
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
        )
    except Exception:
        pass
