from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


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
