from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib.auth import logout


class OpsisMaintenanceMiddleware:
    """
    Mode pemeliharaan OPSIS — selama opsis.ModePemeliharaan.aktif dicentang di
    site admin, semua permintaan ke /opsis/* dijawab halaman pemeliharaan
    (HTTP 503) alih-alih halamannya sendiri.

    Ditangani di middleware, bukan di tiap view, supaya rute OPSIS yang baru
    otomatis ikut tertutup tanpa perlu diingat satu per satu.

    Dua pengecualian:
    - Superuser tetap bisa masuk bila "Superuser Tetap Bisa Masuk" dicentang;
      request-nya ditandai `request.opsis_pemeliharaan = True` sehingga
      opsis_base.html menampilkan pita penanda bahwa OPSIS sedang ditutup
      untuk pengguna lain.
    - Permintaan ke /opsis/api/* (dan XHR lain) dijawab JSON, bukan HTML,
      supaya poller di halaman lain tidak menelan HTML sebagai JSON.

    Cron pengumpul data tidak lewat sini sama sekali — sakelar ini hanya
    menutup akses web.
    """

    PREFIX = '/opsis/'
    API_PREFIX = '/opsis/api/'
    RETRY_AFTER = '1800'          # detik — saran ke klien/monitoring kapan mencoba lagi

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(self.PREFIX):
            return self.get_response(request)

        from opsis.models import ModePemeliharaan
        mode = ModePemeliharaan.status()
        if mode is None or not mode.aktif:
            return self.get_response(request)

        user = getattr(request, 'user', None)
        if mode.boleh_superuser and user is not None and user.is_authenticated and user.is_superuser:
            request.opsis_pemeliharaan = True
            return self.get_response(request)

        if (request.path.startswith(self.API_PREFIX)
                or request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
            resp = JsonResponse({'ok': False, 'pemeliharaan': True, 'error': mode.judul},
                                status=503)
        else:
            resp = render(request, 'opsis/pemeliharaan.html', {'mode': mode}, status=503)
        resp['Retry-After'] = self.RETRY_AFTER
        return resp


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
    - Inspection (/inspection/...) KECUALI /inspection/pengujian-* (milik Dispatcher)
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

    # Prefix yang TIDAK boleh diakses operator meski masuk ALLOWED_PREFIXES
    BLOCKED_PREFIXES = (
        '/inspection/pengujian-',
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
                blocked = any(path.startswith(p) for p in self.BLOCKED_PREFIXES)
                allowed = (
                    not blocked
                    and (
                        any(path.startswith(p) for p in self.ALLOWED_PREFIXES)
                        or path in self.ALLOWED_EXACT
                    )
                )
                if not allowed:
                    return redirect('inspection_lokasi')

        return self.get_response(request)


class OpsisAccessMiddleware:
    """
    Middleware untuk role Opsis — hanya bisa akses:
    - /opsis/ dan sub-URL-nya
    - /login/, /logout/, /ganti-password/
    - static, media
    Semua URL lain → redirect ke /opsis/.
    """

    ALLOWED_PREFIXES = (
        '/opsis/',
        '/static/',
        '/media/',
        '/logout/',
        '/login/',
        '/ganti-password/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            try:
                role = request.user.profile.role
            except Exception:
                role = ''

            if role in ('opsis', 'opsis_view'):
                path = request.path
                allowed = any(path.startswith(p) for p in self.ALLOWED_PREFIXES)
                if not allowed:
                    return redirect('/opsis/')

        return self.get_response(request)


class Up2dAccessMiddleware:
    """
    Middleware untuk role UP2D — hanya bisa akses:
    - /opsis/up2d/
    - /opsis/beban-trafo/, /opsis/beban-ktt/ (halaman detail dari card up2d)
    - API OPSIS yang dibutuhkan dashboard UP2D
    - /login/, /logout/, /ganti-password/
    - static, media
    Semua URL lain → redirect ke /opsis/up2d/.
    """

    ALLOWED_EXACT = (
        '/opsis/up2d/',
        '/opsis/beban-trafo/',
        '/opsis/beban-ktt/',
    )
    ALLOWED_PREFIXES = (
        '/opsis/api/hz/',
        '/opsis/api/hz-sultra/',
        '/opsis/api/hz-baubau/',
        '/opsis/api/freq/',
        '/opsis/api/beban-trafo/',
        '/opsis/api/beban-ktt/',
        '/static/',
        '/media/',
        '/logout/',
        '/login/',
        '/ganti-password/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            try:
                role = request.user.profile.role
            except Exception:
                role = ''

            if role == 'up2d':
                path = request.path
                allowed = (
                    path in self.ALLOWED_EXACT
                    or any(path.startswith(p) for p in self.ALLOWED_PREFIXES)
                )
                if not allowed:
                    return redirect('/opsis/up2d/')

        return self.get_response(request)


class DispatcherAccessMiddleware:
    """
    Middleware untuk role Dispatcher — hanya bisa akses:
    - /inspection/pengujian-* (Pengujian Telekomunikasi)
    - /profile/, /logout/, /login/, /ganti-password/
    - /static/, /media/, /notifikasi/
    Semua URL lain → redirect ke pengujian_telecom_dashboard.
    """

    ALLOWED_PREFIXES = (
        '/inspection/pengujian-',
        '/static/',
        '/media/',
        '/logout/',
        '/login/',
        '/ganti-password/',
        '/notifikasi/',
        '/maintenance/profile/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            try:
                role = request.user.profile.role
            except Exception:
                role = ''

            if role == 'dispatcher':
                path = request.path
                allowed = any(path.startswith(p) for p in self.ALLOWED_PREFIXES)
                if not allowed:
                    return redirect('pengujian_telecom_dashboard')

        return self.get_response(request)


class SingleSessionMiddleware:
    """
    Middleware single active session per user.
    Dikecualikan untuk role Operator, Opsis View, dan UP2D — akun-akun ini
    dipakai bersama di beberapa perangkat/layar monitoring sekaligus.
    Role Opsis (bisa input data HOP) TIDAK dikecualikan → sesi tunggal.
    """

    # Opsis View & UP2D dipakai bersama di banyak layar → multi-sesi.
    # Role Opsis (input data) sengaja TIDAK di sini → dibatasi sesi tunggal.
    MULTI_SESSION_ROLES = ('operator', 'opsis_view', 'up2d')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            path = request.path
            if path.startswith('/static/') or path.startswith('/media/'):
                return self.get_response(request)

            # Admin panel dikecualikan — Django admin merotasi session key setelah
            # password change (update_session_auth_hash), sehingga stored_key
            # tidak cocok dan menyebabkan admin ter-logout.
            if path.startswith('/secure-panel/'):
                return self.get_response(request)

            try:
                logout_url = reverse('logout')
                login_url  = reverse('login')
            except Exception:
                logout_url = '/logout/'
                login_url  = '/login/'

            if path not in (logout_url, login_url):
                try:
                    profile = request.user.profile
                    # ── Operator/Opsis/UP2D dikecualikan dari single-session ──
                    if profile.role in self.MULTI_SESSION_ROLES:
                        return self.get_response(request)

                    current_key = request.session.session_key or ''
                    stored_key  = profile.active_session_key or ''

                    if stored_key and current_key and stored_key != current_key:
                        logout(request)
                        return redirect(f"{login_url}?session_expired=1")
                except Exception:
                    pass

        return self.get_response(request)

