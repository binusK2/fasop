"""
Diagnosa read-only integrasi Ezviz.

Menjawab pertanyaan yang berulang kali muncul saat kamera tidak mau tampil,
dengan menanyakannya langsung ke Ezviz alih-alih menebak dari pesan di layar:

  - kredensialnya terbaca atau tidak, dan menghadap platform yang mana
  - region mana yang sebenarnya dipakai (areaDomain dari Ezviz sendiri)
  - kamera apa saja yang dilihat akun ini di cloud
  - dan yang paling menentukan: bentuk alamat ezopen mana yang DITERIMA
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
from streaming.models import KameraEzviz, PengaturanEzviz, konfigurasi_ezviz


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
        konf = konfigurasi_ezviz()
        baris = PengaturanEzviz.ambil()
        sumber = 'Admin → Pengaturan Ezviz' if baris.app_key else '.env'
        self.stdout.write(f'  appKey        : {konf.app_key[:6]}… ({len(konf.app_key)} karakter, dari {sumber})')
        self.stdout.write(f'  Host API      : {konf.api_base}')

        self._bagian('Token & region')
        try:
            token = ezviz.ambil_access_token()
        except ezviz.EzvizError as e:
            self.stderr.write(self.style.ERROR(f'  GAGAL: {e}'))
            return
        domain = ezviz.domain_aktif()
        self.stdout.write(self.style.SUCCESS(f'  accessToken   : {token[:12]}… (berhasil)'))
        self.stdout.write(f'  domain region : {domain}')
        if domain != konf.api_base:
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

        hosts = self._host_kandidat(domain)
        self.stdout.write(f"  Host yang dicoba di dalam alamat ezopen: {', '.join(hosts)}")
        self.stdout.write('')

        berhasil = {}
        for kamera in daftar:
            self.stdout.write(f'  {kamera.serial}/{kamera.channel} — {kamera.nama}')
            menang = None
            for host, mutu, url in self._kandidat_alamat(kamera, hosts):
                kode, pesan = self._uji_alamat(domain, token, url)
                if kode == '200':
                    self.stdout.write(self.style.SUCCESS(f'      OK      {url}'))
                    menang = (host, mutu)
                    break
                self.stdout.write(self.style.ERROR(f'      DITOLAK {url}'))
                self.stdout.write(f'              code={kode} msg={pesan!r}')
                self._petunjuk(kode)
            if menang:
                berhasil[kamera.serial] = menang
            self.stdout.write('')

        self._ringkasan(daftar, berhasil)

    # ── alamat yang dicoba ────────────────────────────────────────────
    def _host_kandidat(self, domain):
        """
        Host yang ditulis DI DALAM alamat ezopen.

        Dokumentasi Ezviz selalu memakai open.ys7.com, tapi seluruh platform
        ini terikat region — dan penolakan host yang salah muncul sebagai
        "illegal parameter ezopen" yang tidak menyebut apa pun. Jadi jangan
        diasumsikan: dicoba semuanya sampai ada yang diterima.
        """
        region = domain.split('//')[-1].strip('/')
        hosts = ['open.ys7.com']
        for h in (region, 'open.ezviz.com', 'open.ezvizlife.com'):
            if h and h not in hosts:
                hosts.append(h)
        return hosts

    def _kandidat_alamat(self, kamera, hosts):
        """
        Varian HD dan SD dicoba dua-duanya kalau kamera diset HD: sebagian
        perangkat tidak punya main stream, dan bedanya cuma terlihat dari
        balasan server ini — tidak dari mana pun di UI.
        """
        mutu = ['hd.live', 'live'] if kamera.hd else ['live']
        # Kode verifikasi ikut disertakan kalau ada — kamera yang enkripsi
        # videonya masih aktif ditolak tanpa itu, dan hasil uji ini harus sama
        # dengan yang benar-benar dipakai browser.
        awalan = f'{kamera.kode_verifikasi}@' if kamera.kode_verifikasi else ''
        for host in hosts:
            for m in mutu:
                yield host, m, f'ezopen://{awalan}{host}/{kamera.serial}/{kamera.channel}.{m}'

    # ── pemanggilan ──────────────────────────────────────────────────
    # Field yang dikirim EZUIKit ke endpoint ini (lihat ezuikit.js: isFlv,
    # userAgent, isHttp, needStreamToken, accessToken, ezopen). Harus SAMA
    # PERSIS supaya hasil perintah ini bisa dibandingkan dengan yang terjadi
    # di browser: menghilangkan userAgent/needStreamToken saja sudah membuat
    # server membalas "传入参数为空" (parameter kosong) alih-alih menilai
    # alamat ezopen-nya — jawaban yang terlihat meyakinkan tapi menyesatkan.
    USER_AGENT = (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
    )

    def _uji_alamat(self, domain, token, url):
        data = {
            'isFlv': 'false',
            'userAgent': self.USER_AGENT,
            'isHttp': 'false',
            'needStreamToken': '1',
            'accessToken': token,
            'ezopen': url,
        }
        try:
            resp = requests.post(
                domain.rstrip('/') + '/api/lapp/live/url/ezopen',
                data=data, timeout=settings.EZVIZ_TIMEOUT,
            )
            payload = resp.json()
        except (requests.RequestException, ValueError) as e:
            return '', f'tidak bisa dihubungi: {e}'
        return str(payload.get('code', '')), payload.get('msg')

    def _petunjuk(self, kode):
        if kode == '10001':
            self.stdout.write(
                '              10001 = format alamat ditolak. Kalau SEMUA host gagal, '
                'periksa serial & channel di Admin → Kamera CCTV Ezviz.'
            )
        elif kode in ('20002', '20014'):
            self.stdout.write(
                '              Serial tidak dikenal di akun ini — pastikan kameranya benar-benar '
                'terdaftar di akun Ezviz yang appKey-nya dipakai.'
            )
        elif kode == '60020':
            self.stdout.write('              appKey tidak punya izin untuk perangkat ini.')

    def _ringkasan(self, daftar, berhasil):
        self._bagian('Ringkasan')
        if not berhasil:
            self.stdout.write(self.style.ERROR(
                '  Tidak ada satu pun alamat yang diterima. Karena tokennya sendiri berhasil,\n'
                '  penyebabnya kemungkinan bukan kredensial melainkan izin appKey atas perangkat,\n'
                '  atau kameranya berada di akun Ezviz yang berbeda dari pemilik appKey.'
            ))
            return

        hosts = {h for h, _ in berhasil.values()}
        mutus = {m for _, m in berhasil.values()}
        self.stdout.write(f'  Diterima untuk {len(berhasil)} dari {len(daftar)} kamera.')
        self.stdout.write(f"  Host yang diterima : {', '.join(sorted(hosts))}")
        self.stdout.write(f"  Mutu yang diterima : {', '.join(sorted(mutus))}")

        if hosts != {'open.ys7.com'}:
            self.stdout.write(self.style.WARNING(
                '  Host yang dipakai FASOP saat ini (open.ys7.com) BUKAN yang diterima —\n'
                '  setel EZVIZ_EZOPEN_HOST di .env ke host di atas.'
            ))
        if mutus == {'live'}:
            self.stdout.write(self.style.WARNING(
                '  Hanya varian SD yang diterima — matikan centang "Putar Kualitas HD"\n'
                '  pada kamera terkait di Admin.'
            ))

    def _bagian(self, judul):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'== {judul} =='))
