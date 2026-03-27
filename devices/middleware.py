from django.shortcuts import redirect
from django.urls import reverse


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
