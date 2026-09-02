"""
Diagnosa read-only integrasi Ezviz.

Menjawab pertanyaan yang berulang kali muncul saat kamera tidak mau tampil,
dengan menanyakannya langsung ke Ezviz alih-alih menebak dari pesan di layar:

  - kredensialnya terbaca atau tidak, dan menghadap platform yang mana
  - region mana yang sebenarnya dipakai (areaDomain dari Ezviz sendiri)
  - kamera apa saja yang dilihat akun ini di cloud
  - dan yang paling menentukan: apakah alamat ezopen tiap kamera DITERIMA
    server (`/api/lapp/live/url/ezopen`), lengkap dengan balasan mentahnya

Endpoint terakhir itu yang dipanggil EZUIKit di browser, dan penolakannya
("illegal parameter ezopen", kode 10001) tidak menyebut alamat mana yang
ditolak — jadi tanpa perintah ini satu-satunya cara memeriksanya adalah
membuka devtools di halaman live.
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from streaming import ezviz
from streaming.models import KameraEzviz


class Command(BaseCommand):
    help = 'Diagnosa read-only konfigurasi & alamat kamera Ezviz.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--serial',
            help='Uji satu serial saja (huruf otomatis dikapitalkan). Default: semua kamera aktif.',
        )
        parser.add_argument(
            '--channel', type=int, default=1,
            help='Channel untuk --serial. Default 1.',
        )
        parser.add_argument(
            '--cloud', action='store_true',
            help='Tarik juga daftar kamera dari cloud (bukan hanya yang terdaftar di FASOP).',
        )

    def handle(self, *args, **opts):
        self._bagian('Konfigurasi')
        if not ezviz.terkonfigurasi():
            self.stderr.write(self.style.ERROR(
                'EZVIZ_APP_KEY/EZVIZ_APP_SECRET kosong — fitur Ezviz mati total.'
            ))
            return
        self.stdout.write(f'  appKey        : {settings.EZVIZ_APP_KEY[:6]}… ({len(settings.EZVIZ_APP_KEY)} karakter)')
        self.stdout.write(f'  EZVIZ_API_BASE: {settings.EZVIZ_API_BASE}')

        self._bagian('Token & region')
        try:
            token = ezviz.ambil_access_token()
        except ezviz.EzvizError as e:
            self.stderr.write(self.style.ERROR(f'  GAGAL: {e}'))
            return
        domain = ezviz.domain_aktif()
        self.stdout.write(self.style.SUCCESS(f'  accessToken   : {token[:12]}… (berhasil)'))
        self.stdout.write(f'  domain region : {domain}')
        if domain != settings.EZVIZ_API_BASE:
            self.stdout.write(
                '  catatan       : region ini datang dari Ezviz (areaDomain), '
                'bukan dari EZVIZ_API_BASE — dan region inilah yang dipakai.'
            )

        if opts['cloud']:
            self._bagian('Kamera di cloud')
            try:
                for c in ezviz.daftar_kamera_cloud():
                    self.stdout.write(f"  {c['serial']}/{c['channel']:<3} {c['status']:<8} {c['nama']}")
            except ezviz.EzvizError as e:
                self.stderr.write(self.style.ERROR(f'  GAGAL: {e}'))

        self._bagian('Uji alamat ezopen')
        if opts['serial']:
            daftar = [KameraEzviz(
                nama='(diuji manual)', serial=opts['serial'].strip().upper(), channel=opts['channel'],
            )]
        else:
            daftar = list(KameraEzviz.objects.filter(aktif=True))
            if not daftar:
                self.stdout.write('  Belum ada kamera aktif terdaftar. Pakai --serial untuk menguji manual.')
                return

        for kamera in daftar:
            for url in self._alamat_yang_dicoba(kamera):
                self._uji_alamat(domain, token, kamera, url)

    def _alamat_yang_dicoba(self, kamera):
        """
        Varian HD dan SD dicoba dua-duanya kalau kamera diset HD: sebagian
        perangkat tidak punya main stream, dan bedanya cuma terlihat dari
        balasan server ini — tidak dari mana pun di UI.
        """
        alamat = [kamera.ezopen_url]
        if kamera.hd:
            alamat.append(f'ezopen://open.ys7.com/{kamera.serial}/{kamera.channel}.live')
        return alamat

    def _uji_alamat(self, domain, token, kamera, url):
        try:
            resp = requests.post(
                domain.rstrip('/') + '/api/lapp/live/url/ezopen',
                data={
                    'accessToken': token,
                    'ezopen': url,
                    'isFlv': 'false',
                    'isHttp': 'false',
                },
                timeout=settings.EZVIZ_TIMEOUT,
            )
            payload = resp.json()
        except (requests.RequestException, ValueError) as e:
            self.stderr.write(self.style.ERROR(f'  {url}\n      tidak bisa dihubungi: {e}'))
            return

        kode = str(payload.get('code', ''))
        if kode == '200':
            self.stdout.write(self.style.SUCCESS(f'  OK     {url}'))
        else:
            self.stdout.write(self.style.ERROR(
                f"  DITOLAK{url}\n      code={kode} msg={payload.get('msg')!r}"
            ))
            if kode == '10001':
                self.stdout.write(
                    '      10001 = format alamat salah. Periksa serial (huruf harus KAPITAL) '
                    'dan channel-nya di Admin → Kamera CCTV Ezviz.'
                )
            elif kode in ('20002', '20014'):
                self.stdout.write(
                    '      Serial tidak dikenal / tidak ada di akun ini — pastikan kameranya '
                    'benar-benar terdaftar di akun Ezviz yang appKey-nya dipakai.'
                )
            elif kode == '60020':
                self.stdout.write('      appKey tidak punya izin untuk perangkat ini.')

    def _bagian(self, judul):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'== {judul} =='))
