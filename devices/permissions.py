"""
devices/permissions.py — Helper terpusat permission checking.
"""
from functools import wraps


def _forbidden(request, message='Anda tidak memiliki akses untuk melakukan tindakan ini.'):
    from django.shortcuts import render
    return render(request, '403.html', {'message': message}, status=403)


def get_profile(user):
    try:
        return user.profile
    except Exception:
        return None


def can_delete(user):
    """Hanya superuser."""
    return user.is_superuser


def can_edit(user):
    """Superuser, AM, Technician — bukan Viewer."""
    if user.is_superuser:
        return True
    p = get_profile(user)
    return p.can_edit if p else False


def can_manage_lokasi(user):
    """Superuser dan AM."""
    if user.is_superuser:
        return True
    p = get_profile(user)
    return p.can_manage_lokasi if p else False


def is_viewer_only(user):
    if user.is_superuser:
        return False
    p = get_profile(user)
    return p.is_viewer if p else False


def is_operator(user):
    if user.is_superuser:
        return False
    p = get_profile(user)
    return p.is_operator if p else False


def require_can_edit(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_edit(request.user):
            return _forbidden(request, 'Akun Viewer tidak bisa melakukan perubahan data.')
        return view_func(request, *args, **kwargs)
    return wrapper


def require_can_delete(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_delete(request.user):
            return _forbidden(request, 'Hanya Administrator yang bisa menghapus data.')
        return view_func(request, *args, **kwargs)
    return wrapper


def require_can_manage_lokasi(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_manage_lokasi(request.user):
            return _forbidden(request, 'Hanya Asisten Manager yang bisa mengelola lokasi.')
        return view_func(request, *args, **kwargs)
    return wrapper
