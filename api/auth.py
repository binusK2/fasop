import functools
import hmac

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

        if not hmac.compare_digest(str(api_key), str(expected)):
            return JsonResponse(
                {'status': 'error', 'message': 'API Key tidak valid.'},
                status=403
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def require_kunci_baca(view_func):
    """
    Decorator untuk endpoint BACA yang dibuka ke pihak luar.

    Berbeda dari `require_api_key`, yang diterima di sini BUKAN
    `settings.API_KEY` melainkan baris `devices.KunciApi` yang aktif. Kunci
    global sengaja ditolak: ia juga membuka endpoint tulis (upsert inventaris
    device, HOP, prakiraan beban), jadi kalau ia ikut diterima di sini, cepat
    atau lambat kunci itulah yang dibagikan ke pihak luar "karena bisa".

    Kunci yang cocok disimpan di `request.kunci_api` supaya view bisa
    mencatatnya bila perlu.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from devices.models import KunciApi

        kunci = request.headers.get('X-Api-Key') or request.headers.get('X-API-Key')
        if not kunci:
            return JsonResponse(
                {'status': 'error', 'message': 'Header X-API-Key tidak ditemukan.'},
                status=401
            )

        obj = KunciApi.objects.filter(kunci=kunci, aktif=True).first()
        if obj is None:
            return JsonResponse(
                {'status': 'error', 'message': 'Kunci API tidak valid atau sudah dicabut.'},
                status=403
            )

        request.kunci_api = obj
        try:
            obj.catat_pemakaian(_client_ip(request))
        except Exception:
            pass    # jejak pemakaian tidak boleh menggagalkan permintaan data

        return view_func(request, *args, **kwargs)

    return wrapper
