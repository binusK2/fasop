"""
PWA (Progressive Web App) endpoints untuk FASOP.

Service worker & manifest sengaja di-serve dari root ("/") lewat view Django
(bukan sebagai file statis di /static/) supaya scope service worker mencakup
seluruh aplikasi — khususnya alur Inservice Inspection untuk role Operator.

Ketiga endpoint ini publik (tanpa login) karena browser mengambilnya sebelum
sesi login terbentuk saat proses install / update PWA.
"""
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views.decorators.cache import cache_control


@cache_control(max_age=0, no_cache=True)
def service_worker(request):
    """Serve service worker dari root agar scope-nya '/'."""
    js = render_to_string('pwa/service-worker.js', request=request)
    resp = HttpResponse(js, content_type='application/javascript')
    # Service worker tidak boleh di-cache lama agar update cepat terdeteksi.
    resp['Service-Worker-Allowed'] = '/'
    return resp


def manifest(request):
    """Serve web app manifest."""
    body = render_to_string('pwa/manifest.webmanifest', request=request)
    return HttpResponse(body, content_type='application/manifest+json')


def offline(request):
    """Halaman fallback saat perangkat offline."""
    html = render_to_string('pwa/offline.html', request=request)
    return HttpResponse(html)
