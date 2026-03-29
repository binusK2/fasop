import functools
from django.conf import settings
from django.http import JsonResponse


def require_api_key(view_func):
    """
    Decorator untuk melindungi API endpoint dengan API Key.
    Key dikirim via header: X-API-Key: <key>
    Key dikonfigurasi di .env: API_KEY=<key>
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        api_key = request.headers.get('X-Api-Key') or request.headers.get('X-API-Key')
        expected = getattr(settings, 'API_KEY', None)

        if not expected:
            return JsonResponse(
                {'status': 'error', 'message': 'API_KEY belum dikonfigurasi di server.'},
                status=500
            )

        if not api_key:
            return JsonResponse(
                {'status': 'error', 'message': 'Header X-API-Key tidak ditemukan.'},
                status=401
            )

        if api_key != expected:
            return JsonResponse(
                {'status': 'error', 'message': 'API Key tidak valid.'},
                status=403
            )

        return view_func(request, *args, **kwargs)

    return wrapper
