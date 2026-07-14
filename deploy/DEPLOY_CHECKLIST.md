# Live Streaming — Checklist Deploy

Daftar semua langkah untuk menyalakan fitur Live Streaming di server
produksi. Ditulis ulang setelah deploy pertama di server FASOP (server
on-premise kantor PLN, pakai Cloudflare Tunnel) — beberapa asumsi awal
salah, checklist ini sudah mengikuti apa yang **benar-benar terbukti jalan**,
bukan cuma teori.

Jalankan dulu untuk bagian yang bisa diotomasi:
```bash
bash deploy/setup_streaming.sh
```
Aman dijalankan berulang kali.

## Rekaman: kenapa sebelumnya audio-only, dan cara video-nya masuk

Browser default kirim video WebRTC pakai codec **VP8**, tapi recorder
fMP4 MediaMTX **belum mengimplementasi VP8** (`// TODO` di source code-nya
`internal/recorder/format_fmp4.go` — sudah dicek ulang sampai branch `main`
terbaru, jadi ini BUKAN soal versi MediaMTX kurang baru, dan format
`mpegts` juga sama-sama tidak dukung VP8/VP9). Tanpa penanganan khusus,
video track di-skip diam-diam dan hasil rekaman cuma berisi audio (Opus).

**Sudah dicoba & di-revert (jangan diulangi):** memaksa browser pakai H.264
langsung lewat `RTCRtpTransceiver.setCodecPreferences()` di sisi publish —
codec berhasil ganti ke H.264, tapi malah merusak WHEP live viewing (viewer
connect tapi video tidak muncul sama sekali). Live viewing jauh lebih
prioritas daripada rekaman, jadi opsi ini ditinggalkan.

**Solusi yang dipakai — transcode di server, browser tidak disentuh:**
begitu path video mentah (`live-<key>`) mulai dipublish, MediaMTX
menjalankan `ffmpeg` **lokal** (`runOnReady` di `deploy/mediamtx.yml`) yang
menarik feed RTSP mentah dari MediaMTX sendiri lewat loopback (sama sekali
tidak lewat WebRTC/browser — live viewing yang sudah stabil tidak
tersentuh), transcode ke H.264, lalu republish ke path baru `live-<key>-rec`.
Hanya path `-rec` itu yang direkam (`recordFormat: fmp4`) — jadi sekarang
videonya ikut masuk. Prasyarat: **ffmpeg harus terinstal di server**
(`sudo apt install -y ffmpeg`, dicek otomatis oleh `setup_streaming.sh`
langkah 2b). Proses ffmpeg per sesi otomatis dihentikan MediaMTX begitu
live berakhir — tidak perlu cleanup manual. Beban CPU per sesi live ringan
(`libx264 preset veryfast`) tapi tetap nyata (real-time encode) — untuk
skala FASOP (maks 2-3 live bersamaan) harusnya tidak masalah, pantau CPU
server kalau nanti jumlah live bersamaan naik jauh.

**Kalau setelah deploy rekaman masih audio-only,** urutan cek:
1. `which ffmpeg` di server — kalau kosong, itu penyebabnya, install lalu
   restart mediamtx (`sudo systemctl restart mediamtx`) supaya `runOnReady`
   berikutnya bisa menjalankan ffmpeg.
2. `journalctl -u mediamtx --no-pager | grep -i ffmpeg` — cari error dari
   proses ffmpeg itu sendiri (mis. gagal connect ke RTSP loopback).
3. Cek file di `STREAMING_RECORDINGS_ROOT/live-<key>-rec/...` benar-benar
   ada — kalau foldernya `live-<key>` (tanpa `-rec`), berarti
   `mediamtx.generated.yml` di server belum ter-update ke versi terbaru
   (`git pull` lagi, render ulang `setup_streaming.sh`, restart mediamtx).
4. `TURN_URL`/`TURN_USERNAME`/`TURN_PASSWORD` di `.env` cocok dengan kredensial
   `mtx-internal` yang di-generate ke `mediamtx.generated.yml` (bukan ini
   penyebab paling umum, tapi kalau `mediamtx_auth_webhook` menolak
   `action=publish`/`action=read` dengan `user=mtx-internal` di log Django,
   ini penyebabnya — jarang terjadi kecuali `MEDIAMTX_AUTH_SECRET` di `.env`
   berubah tapi `mediamtx.generated.yml` belum di-render ulang).
5. Sesi live-nya kemungkinan sudah tidak `status='live'` di database saat
   ffmpeg mencoba connect (race condition kecil, jarang terjadi).

## Audio pengawas (talkback) — direkam terpisah, bukan digabung ke video

Opus (kodek audio WebRTC) didukung LANGSUNG oleh recorder fMP4 MediaMTX
(beda dengan VP8 video di atas), jadi path talkback pengawas
(`live-<key>-talk`) direkam langsung tanpa perlu ffmpeg transcode apa pun —
tinggal `record: true` di `deploy/mediamtx.yml`.

**SENGAJA tidak di-mix jadi satu file dengan video** — pengawas bisa
join/aktifkan-matikan mic kapan saja setelah teknisi live, jadi real-time
mixing ke satu file video berisiko rekaman utama ikut terpecah tiap mic
di-toggle. Disimpan ke field terpisah `LiveSession.talkback_recording_path`
dan ditampilkan sebagai `<audio>` player terpisah di halaman "Putar
Rekaman" (di bawah video, kalau ada).

**Keterbatasan yang diterima:** kalau pengawas toggle mic berkali-kali di
sesi yang sama, itu jadi beberapa segmen rekaman di disk tapi
`talkback_recording_path` cuma menyimpan segmen TERAKHIR (field tunggal,
bukan daftar) — segmen sebelumnya tetap ada di disk (dihapus saat retensi 7
hari lewat) tapi tidak lagi bisa diputar dari UI. Wajar untuk pemakaian
normal (mic diaktifkan sekali per sesi).

Setelah `git pull` yang membawa fitur ini, WAJIB migrate dulu (field baru
di model):
```bash
python manage.py migrate
```
lalu render ulang & restart seperti biasa:
```bash
bash deploy/setup_streaming.sh
sudo systemctl restart mediamtx
sudo systemctl restart gunicorn
```

## Playback lebih cepat (opsional) — nginx X-Accel-Redirect

Rekaman secara default diserve dengan Django/gunicorn membaca & mengirim
byte file-nya sendiri (`StreamingHttpResponse`) — jalan, tapi lambat untuk
file besar. Bisa dialihkan supaya nginx yang serve langsung dari disk
(jauh lebih cepat, termasuk menangani Range request untuk seek) — **opt-in,
default mati**, tidak mengubah perilaku existing sampai diaktifkan.

Langkah lengkap (termasuk snippet nginx & sanity check): lihat
`deploy/nginx-recordings-x-accel.conf.example`. Ringkasnya:
1. Tambahkan location `internal` yang di-alias ke `STREAMING_RECORDINGS_ROOT`
   ke server block nginx FASOP yang SUDAH ADA (bukan server block baru).
2. `sudo nginx -t && sudo systemctl reload nginx`.
3. Set `.env` → `STREAMING_USE_X_ACCEL_REDIRECT=True`, restart gunicorn.

Kalau video malah gagal load sama sekali setelah diaktifkan (bukan cuma
lambat), set `STREAMING_USE_X_ACCEL_REDIRECT=False` lagi untuk rollback
instan (tidak perlu ubah nginx) sambil diperiksa — kemungkinan besar
`alias` di config nginx tidak cocok persis dengan `STREAMING_RECORDINGS_ROOT`.

## Gotcha besar — `mediamtx.generated.yml` di-generate ULANG DARI NOL

`setup_streaming.sh` **selalu menulis ulang seluruh isi** `mediamtx.generated.yml`
dari template `mediamtx.yml` setiap kali dijalankan. Kalau ada nilai yang
pernah diisi/diedit **langsung di file `.generated.yml`** (bukan di `.env`),
edit itu **hilang tertimpa placeholder lagi** lain kali script ini dijalankan
— dan karena tidak ada pesan error yang jelas, gejalanya baru muncul saat
live streaming dicoba lagi (CORS `Failed to fetch` kalau origin yang hilang,
TURN tidak connect dari HP CGNAT kalau kredensial TURN yang hilang).

**Aturan wajib:** isi `FASOP_PUBLIC_ORIGIN`, `TURN_URL`, `TURN_USERNAME`,
`TURN_PASSWORD` di `.env` (bukan di `mediamtx.generated.yml`), lalu jalankan
`bash deploy/setup_streaming.sh` — nilainya otomatis disalin ke
`webrtcAllowOrigins`/`webrtcICEServers2` setiap kali. Script ini akan
mencetak `[!]` di langkah 2c kalau salah satu variabel itu belum ada di
`.env`, supaya ketahuan SEBELUM restart, bukan sesudah teknisi coba live
dan gagal.

## Otomatis oleh `setup_streaming.sh`

- [ ] `.env` → `MEDIAMTX_AUTH_SECRET` (di-generate acak kalau belum ada)
- [ ] `.env` → `STREAMING_RECORDINGS_ROOT` (default `<repo>/streaming_recordings` kalau belum diisi)
- [ ] Direktori rekaman dibuat
- [ ] Cek `ffmpeg` terinstal (dicetak `[!]` kalau belum — TIDAK diinstal otomatis)
- [ ] `.env` → `FASOP_PUBLIC_ORIGIN`, `TURN_URL`, `TURN_USERNAME`, `TURN_PASSWORD` disalin
      ke `deploy/mediamtx.generated.yml` kalau sudah diisi (dicetak `[!]` kalau belum)
- [ ] `deploy/mediamtx.generated.yml` di-render dari `deploy/mediamtx.yml` (secret, path rekaman,
      origin & TURN — yang sudah ada di `.env` — terisi)
- [ ] `deploy/mediamtx.service.generated` di-render dari `deploy/mediamtx.service` (path `ExecStart` otomatis benar)
- [ ] Cron `purge_old_recordings` terpasang (harian 03:00)

File hasil generate (`*.generated.*`) **jangan pernah di-commit** — sudah di-gitignore.

## Langkah manual — urutan yang terbukti jalan

### 1. Install & jalankan MediaMTX
```bash
curl -LO https://github.com/bluenviron/mediamtx/releases/download/vX.Y.Z/mediamtx_vX.Y.Z_linux_amd64.tar.gz
#  ^ CEK dulu versi terbaru & nama file asset PERSIS di halaman GitHub Releases —
#    nama file selalu ikut nomor versi, tebak sembarang akan gagal (pernah kejadian).
mkdir -p /opt/mediamtx && tar -xzf mediamtx_*.tar.gz -C /opt/mediamtx
sudo cp deploy/mediamtx.service.generated /etc/systemd/system/mediamtx.service
sudo nano /etc/systemd/system/mediamtx.service   # cek/isi User & Group
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx
sudo systemctl status mediamtx   # pastikan "active (running)", BUKAN restart loop
```
**Gotcha yang pernah kejadian:** kalau `status` menunjukkan restart berkali-kali
(`restart counter is at N`, N besar) tanpa pesan jelas, cek
`journalctl -xeu mediamtx` — biasanya path di `ExecStart` salah/tidak ada.

**Gotcha lain (rekaman diam-diam gagal):** direktori `STREAMING_RECORDINGS_ROOT`
dibuat oleh `setup_streaming.sh` sebagai user yang menjalankan script itu
(sering `root`), tapi `mediamtx.service` jalan sebagai `User=fasop` (baris
35 di atas) — MediaMTX akan gagal `mkdir` di dalamnya (`permission denied`
di `journalctl -u mediamtx`) tanpa mempengaruhi live streaming sama sekali
(video/live tetap jalan normal, cuma rekaman yang diam-diam tidak pernah
tersimpan). Samakan kepemilikan folder dengan user service **setelah**
`User`/`Group` di `mediamtx.service` diisi:
```bash
sudo chown -R fasop:fasop "$(grep STREAMING_RECORDINGS_ROOT .env | cut -d= -f2)"
```
(ganti `fasop` sesuai `User`/`Group` yang benar-benar diisi di langkah atas)

### 2. TURN server (coturn) — wajib untuk HP teknisi di lapangan
```bash
which turnserver ; systemctl status coturn   # cek dulu, mungkin sudah ada
sudo apt install -y coturn
sudo cp deploy/turnserver.conf.example /etc/turnserver.conf
sudo nano /etc/turnserver.conf   # isi realm, user/password, external-ip, allowed-peer-ip
sudo nano /etc/default/coturn    # uncomment TURNSERVER_ENABLED=1
sudo systemctl enable --now coturn
```
Kalau server di belakang NAT (kantor/on-premise, cuma punya IP privat):
`external-ip` di `turnserver.conf` **wajib** diisi (format `PUBLIK/PRIVAT`), dan
minta tim jaringan teruskan **UDP 3478** + **UDP 49152-49251** dari IP publik
ke IP privat server ini (range port sudah dipersempit di
`turnserver.conf.example`, jangan pakai default 49152-65535 — permintaan ke
tim jaringan jadi lebih besar tanpa perlu).

**Gotcha besar — jaringan FortiGate/SD-WAN multi-WAN-link:** kalau kantor
pakai FortiGate dengan beberapa virtual WAN link (SD-WAN), **JANGAN** ambil
IP publik dari `curl ifconfig.me` — hasilnya bisa beda tiap kali dipanggil
(pernah kejadian 3 IP beda dalam hitungan detik: `.128`, `.55`, `.51`)
karena SD-WAN pilih link keluar berbeda-beda per koneksi, ini bukan IP
publik yang dipakai untuk trafik MASUK. Gejalanya di produksi: video live
tersambung tapi tidak pernah muncul, log MediaMTX penuh `deadline exceeded
while waiting connection` berulang setiap ~5 detik.

IP yang benar untuk `external-ip` = IP di WAN interface SPESIFIK yang
di-dedikasikan admin FortiGate untuk Virtual IP (VIP)/DNAT ke server ini —
cek di FortiGate: **Network > Interfaces** (WAN fisik/logical yang dipasangi
VIP, bukan SD-WAN zone gabungan). Setup di FortiGate: buat 2 Virtual IP
(UDP 3478 dan UDP 49152-49251, keduanya map ke IP privat server ini) di WAN
interface itu, lalu Firewall Policy (incoming = WAN itu, destination = kedua
VIP, action ACCEPT, NAT off — VIP yang urus translasinya).

Setelah coturn jalan, isi kredensial yang **sama persis** di 2 tempat lain:
- `.env` → `WEBRTC_ICE_SERVERS`
- `deploy/mediamtx.generated.yml` → `webrtcICEServers2` (`password:`)

### 3. Endpoint HTTPS publik untuk MediaMTX (WHIP/WHEP signaling)

**Kalau server pakai Cloudflare Tunnel** (`cloudflared`) untuk expose app
utama — **pakai cara ini, JAUH lebih simpel** daripada nginx+certbot (tidak
perlu sertifikat sendiri, tidak perlu buka port 443 di firewall):

1. Cek dulu apakah tunnel-nya **dikelola dari dashboard** atau dari file
   lokal `/etc/cloudflared/config.yml`: buka Cloudflare **Zero Trust →
   Networks → Tunnels → (nama tunnel) → tab Overview**. Kalau ada daftar
   "Routes" dengan tombol **"+ Add route"**, berarti dashboard-managed —
   **ingress rule di `config.yml` lokal DIABAIKAN**, jangan edit file itu,
   tambahkan lewat dashboard saja.
2. Klik **"+ Add route"** → **Published application** → Subdomain `media`,
   Domain (pilih domain FASOP), Service Type `HTTP`, URL `localhost:8889`.
3. Kalau ternyata locally-managed (tidak ada tombol Add route, cuma file
   config), edit `/etc/cloudflared/config.yml` manual, tambah sebelum baris
   `- service: http_status:404`:
   ```yaml
   - hostname: media.domain-anda
     service: http://localhost:8889
   ```
   lalu `sudo cloudflared tunnel route dns <nama-tunnel> media.domain-anda`
   dan `sudo systemctl restart cloudflared`.
4. **Kalau `cloudflared` gagal connect setelah restart** (cek
   `journalctl -u cloudflared`, error `CRYPTO_ERROR ... tls: no application
   protocol` atau semacamnya berulang) — itu tanda QUIC (default protokol
   `cloudflared`) diganggu firewall/jaringan. Paksa pakai HTTP/2 (lebih
   tahan gangguan semacam ini): edit `/etc/systemd/system/cloudflared.service`,
   tambah `--protocol http2` di baris `ExecStart`, lalu
   `daemon-reload && restart`.
   **PENTING:** ini juga mempengaruhi app utama FASOP — kalau tunnel down,
   app utama ikut down. Prioritaskan perbaikan ini di atas segalanya kalau
   terjadi.

**Kalau TIDAK pakai Cloudflare Tunnel** (server exposed langsung / nginx
biasa) — pakai jalur nginx+certbot:
1. Tambah DNS A record `media.domain-anda` → IP publik server.
2. Pasang `deploy/nginx-mediamtx-temp.conf.example` dulu (port 80 saja,
   TANPA SSL) → `nginx -t && systemctl reload nginx`.
3. `sudo certbot --nginx -d media.domain-anda` (atau `certbot certonly
   --dns-cloudflare` kalau DNS di Cloudflare dan port 80 belum tentu
   terbuka dari firewall — lihat riwayat percakapan/commit untuk detail
   setup `certbot-dns-cloudflare`).
   **Jangan** langsung pasang `deploy/nginx-mediamtx.conf.example` sebelum
   sertifikatnya ada — filenya referensi cert yang belum ada, `nginx -t`
   akan gagal.
4. Setelah cert terbit, ganti ke `deploy/nginx-mediamtx.conf.example` (versi
   lengkap dengan SSL).

### 4. Sambungkan Django ke MediaMTX — LANGKAH YANG PALING SERING KELEWAT

```bash
echo "MEDIAMTX_WHIP_URL=https://media.domain-anda" >> .env
echo "MEDIAMTX_WHEP_URL=https://media.domain-anda" >> .env
sudo systemctl restart gunicorn   # WAJIB, .env baru tidak kebaca tanpa restart
```
Tanpa ini, Django jatuh ke default `http://localhost:8889` — browser HP akan
coba fetch ke `localhost` milik **HP itu sendiri**, bukan ke server, dan
selalu gagal dengan pesan generik `Failed to fetch` (pernah kejadian, gampang
kelewat karena tidak ada error jelas yang nunjuk ke `.env`).

Juga isi `webrtcAllowOrigins` di `deploy/mediamtx.generated.yml` dengan
origin **Django FASOP** (mis. `https://fasop.domain-anda`) — beda dari
domain media di atas.

### 5. Static files — jangan lupa untuk app baru manapun
```bash
python manage.py collectstatic --noinput
```
Kalau lupa, browser dapat error `whipPublish is not defined` (JS-nya
gagal ke-load karena file belum ada di `staticfiles/`). Ini bukan spesifik
fitur streaming — berlaku tiap ada static file baru, sering kelewat kalau
lupa (lihat `CLAUDE.md` Production Deployment Checklist).

### 6. Testing — hindari jebakan cache

App ini PWA (ada service worker) — kalau habis fix bug frontend tapi masih
kelihatan error lama, **jangan langsung curiga fix-nya salah**, coba dulu di
**tab Incognito baru** (bukan reload tab lama) untuk pastikan bukan cache
lama yang nyangkut.

Untuk debug endpoint WHIP tanpa perlu browser, test CORS preflight langsung:
```bash
curl -sv -X OPTIONS "https://media.domain-anda/live-XXXX/whip" \
  -H "Origin: https://fasop.domain-anda" \
  -H "Access-Control-Request-Method: POST" 2>&1 | grep -Ei "access-control|< HTTP"
```
Harus dapat `204` + header `access-control-allow-origin` yang cocok. Kalau
dapat `404` tanpa header CORS lewat domain publik padahal `curl` ke
`http://127.0.0.1:8889` langsung berhasil — itu tanda request tidak sampai
ke MediaMTX (kemungkinan besar masalah di langkah 3, cek dashboard tunnel).

## Kenapa TURN penting (jangan di-skip)

HP teknisi di lapangan hampir selalu di belakang CGNAT operator seluler.
Tanpa TURN yang valid, koneksi WebRTC akan gagal connect dari jaringan
seluler meskipun semua yang lain sudah benar.

## Yang TIDAK perlu disentuh lagi

- Migrasi Django (`streaming/migrations/`) — jalan otomatis lewat
  `manage.py migrate` seperti biasa.
- `deploy/mediamtx.yml` dan `deploy/mediamtx.service` — ini **template**,
  jangan diedit langsung untuk isi secret/path. Edit lewat
  `setup_streaming.sh` supaya hasil generate-nya yang dipakai.
