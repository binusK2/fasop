"""streaming/permissions.py — role checks khusus fitur Live Streaming.

Menu Live Streaming hanya untuk Teknisi & Asisten Manager. Semua Teknisi
boleh memulai siaran; hanya Asisten Manager yang bisa menjadi Pengawas
(satu-satunya role dengan komunikasi 2 arah ke teknisi yang live).
"""
from functools import wraps

from django.shortcuts import render


def _forbidden(request, message='Anda tidak memiliki akses untuk fitur Live Streaming.'):
    return render(request, '403.html', {'message': message}, status=403)


def get_profile(user):
    try:
        return user.profile
    except Exception:
        return None


def can_access_streaming(user):
    """Hanya Teknisi & Asisten Manager (+ superuser) yang bisa buka menu Live Streaming."""
    if user.is_superuser:
        return True
    p = get_profile(user)
    return bool(p and p.role in ('technician', 'asisten_manager'))


def can_start_stream(user):
    """Semua Teknisi bisa memulai live streaming."""
    if user.is_superuser:
        return True
    p = get_profile(user)
    return bool(p and p.is_technician)


def can_join_as_pengawas(user):
    """Hanya Asisten Manager yang bisa jadi Pengawas (talkback 2 arah)."""
    if user.is_superuser:
        return True
    p = get_profile(user)
    return bool(p and p.is_asisten_manager)


def require_streaming_access(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_access_streaming(request.user):
            return _forbidden(request)
        return view_func(request, *args, **kwargs)
    return wrapper
