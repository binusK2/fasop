"""
Endpoint di akar situs untuk mesin pencari (Google Search Console).

Berkas verifikasi Google harus ada di https://<domain>/googleXXXX.html — di
akar, bukan di /static/ — dan di FASOP akar dilayani Django, bukan nginx.
"""
from django.conf import settings
from django.http import Http404, HttpResponse


def google_verifikasi(request, nama):
    """
    Berkas verifikasi kepemilikan Google Search Console.

    HANYA nama yang terdaftar di GOOGLE_SITE_VERIFICATION yang dijawab. Kalau
    FASOP menjawab nama googleXXXX.html apa pun, siapa saja bisa mendaftarkan
    fasopup2bmks.id di Search Console MEREKA sendiri dan tercatat sebagai
    pemiliknya — termasuk melihat data pencarian dan meminta URL dihapus dari
    Google.
    """
    if nama not in settings.GOOGLE_SITE_VERIFICATION:
        raise Http404
    return HttpResponse(f'google-site-verification: {nama}', content_type='text/html; charset=utf-8')
