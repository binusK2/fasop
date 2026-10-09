"""
Header keamanan yang tidak dipasang SecurityMiddleware bawaan Django:
Content-Security-Policy dan Permissions-Policy.

Isi kebijakannya hidup di settings.py (SECURE_CSP, CSP_TAMBAHAN_EZVIZ,
PERMISSIONS_POLICY) — modul ini hanya memasangnya ke respons. Lihat
"Header Keamanan" di CLAUDE.md untuk alasan tiap pilihan.
"""
from django.conf import settings
from django.middleware.csp import ContentSecurityPolicyMiddleware


def _adalah_html(response):
    return response.get('Content-Type', '').startswith('text/html')


def gabung_csp(dasar, tambahan):
    """
    Kebijakan `dasar` yang diperluas dengan sumber dari `tambahan`.

    Direktif yang tidak ada di `dasar` dimulai dari isi default-src-nya, bukan
    dari kosong — kalau tidak, menambah `worker-src blob:` diam-diam membuang
    'self' yang selama ini berlaku lewat fallback ke default-src.
    """
    hasil = {k: _daftar(v) for k, v in dasar.items()}
    for direktif, sumber in tambahan.items():
        daftar = hasil.get(direktif)
        if not isinstance(daftar, list):
            daftar = hasil[direktif] = _daftar(dasar.get('default-src', []))
        daftar.extend(s for s in sumber if s not in daftar)
    return hasil


def _daftar(nilai):
    """Salinan list dari nilai direktif; True/None (direktif tanpa sumber) dibiarkan."""
    if isinstance(nilai, (list, tuple, set)):
        return list(nilai)
    if isinstance(nilai, str):
        return [nilai]
    return nilai


def izinkan_ezviz(response):
    """
    Tandai respons halaman pemutar EZUIKit supaya CSP-nya diperluas dengan
    CSP_TAMBAHAN_EZVIZ. Dipanggil di view, hanya untuk respons yang memang
    menggambar pemutar Ezviz — halaman lain tetap memakai kebijakan dasar.
    """
    response._csp_ezviz = True
    return response


class HtmlContentSecurityPolicyMiddleware(ContentSecurityPolicyMiddleware):
    """
    ContentSecurityPolicyMiddleware bawaan Django, dengan dua beda:

    - Hanya respons HTML yang diberi header. Yang paling penting di sini
      /service-worker.js: service worker tunduk pada CSP RESPONS SKRIPNYA
      sendiri, bukan CSP halaman. Service worker FASOP mengambil ulang aset
      CDN (Bootstrap, Chart.js, font) lewat fetch(); kalau skripnya ikut
      membawa connect-src halaman, semua fetch itu ditolak dan setiap
      halaman kehilangan CSS/JS-nya sekaligus. PDF, JSON, dan file rekaman
      juga tidak butuh CSP.
    - Respons yang ditandai izinkan_ezviz() memakai kebijakan yang diperluas,
      baik dalam mode enforce maupun report-only.
    """

    def process_response(self, request, response):
        if not _adalah_html(response):
            return response
        if getattr(response, '_csp_ezviz', False):
            tambahan = settings.CSP_TAMBAHAN_EZVIZ
            if settings.SECURE_CSP:
                response._csp_config = gabung_csp(settings.SECURE_CSP, tambahan)
            if settings.SECURE_CSP_REPORT_ONLY:
                response._csp_ro_config = gabung_csp(settings.SECURE_CSP_REPORT_ONLY, tambahan)
        return super().process_response(request, response)


def susun_permissions_policy(kebijakan):
    """{'camera': ['self'], 'usb': []} → 'camera=(self), usb=()'."""
    bagian = []
    for fitur, izin in kebijakan.items():
        isi = ' '.join(s if s in ('self', 'src') else f'"{s}"' for s in izin)
        bagian.append(f'{fitur}=({isi})')
    return ', '.join(bagian)


class PermissionsPolicyMiddleware:
    """Pasang header Permissions-Policy dari settings.PERMISSIONS_POLICY."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        nilai = susun_permissions_policy(settings.PERMISSIONS_POLICY)
        if nilai and 'Permissions-Policy' not in response:
            response['Permissions-Policy'] = nilai
        return response
