from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import logout


class ForcePasswordChangeMiddleware:
    """
    Middleware yang memeriksa apakah user wajib ganti password.
    Jika UserProfile.force_password_change == True, redirect ke halaman
    ganti password. Hanya mengizinkan akses ke:
    - halaman force-change-password itu sendiri
    - logout
    - static / media files
    """

    ALLOWED_URLS = None  # akan di-set saat pertama kali

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Skip untuk static/media
            path = request.path
            if path.startswith('/static/') or path.startswith('/media/'):
                return self.get_response(request)

            # Build allowed URLs list
            allowed = [
                reverse('force_change_password'),
                reverse('logout'),
            ]

            if path not in allowed:
                try:
                    profile = request.user.profile
                    if profile.force_password_change:
                        return redirect('force_change_password')
                except Exception:
                    pass

        return self.get_response(request)


class OperatorAccessMiddleware:
    """
    Middleware untuk role Operator — hanya bisa akses:
    - Dashboard (/)
    - Inspection (/inspection/...)
    - Logout, login, password change, static, media
    Semua URL lain → redirect ke inspection_lokasi.
    """

    # Prefix URL yang boleh diakses operator
    ALLOWED_PREFIXES = (
        '/inspection/',
        '/static/',
        '/media/',
        '/logout/',
        '/login/',
        '/ganti-password/',
        '/notifikasi/',
    )

    # Exact URL yang boleh (dashboard)
    ALLOWED_EXACT = ('/',)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            try:
                role = request.user.profile.role
            except Exception:
                role = ''

            if role == 'operator':
                path = request.path
                allowed = (
                    any(path.startswith(p) for p in self.ALLOWED_PREFIXES)
                    or path in self.ALLOWED_EXACT
                )
                if not allowed:
                    return redirect('inspection_lokasi')

        return self.get_response(request)


class SingleSessionMiddleware:
    """
    Middleware yang memastikan setiap user hanya bisa login dari satu perangkat
    dalam satu waktu (single active session).

    Cara kerja:
    - Saat user login (ditangani oleh signal user_logged_in di signals.py),
      session key aktif disimpan ke UserProfile.active_session_key.
    - Setiap request dari user yang sudah login, middleware membandingkan
      session key request saat ini dengan yang tersimpan di profil.
    - Jika tidak cocok (user sudah login di perangkat lain), session ini
      di-logout paksa dan diarahkan ke halaman login dengan pesan peringatan.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            path = request.path
            # Lewati static/media
            if path.startswith('/static/') or path.startswith('/media/'):
                return self.get_response(request)

            try:
                logout_url = reverse('logout')
                login_url = reverse('login')
            except Exception:
                logout_url = '/logout/'
                login_url = '/login/'

            # Lewati halaman logout/login agar tidak loop
            if path not in (logout_url, login_url):
                try:
                    profile = request.user.profile
                    current_key = request.session.session_key or ''
                    stored_key = profile.active_session_key or ''

                    if stored_key and current_key and stored_key != current_key:
                        # Session tidak cocok → logout paksa
                        logout(request)
                        return redirect(f"{login_url}?session_expired=1")
                except Exception:
                    pass

        return self.get_response(request)

