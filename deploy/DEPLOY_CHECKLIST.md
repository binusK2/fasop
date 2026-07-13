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

## Keterbatasan diketahui: rekaman audio-only (belum ada video)

Browser default kirim video WebRTC pakai codec **VP8**, tapi recorder
fMP4 MediaMTX v1.19.2 **belum mengimplementasi VP8** (`// TODO` di source
code-nya) — video track di-skip diam-diam, hasil rekaman cuma berisi
audio (Opus). Live streaming & talkback TIDAK terpengaruh, cuma rekaman-
nya yang tidak ada videonya.

**Sudah dicoba & di-revert:** memaksa browser pakai H.264 (yang didukung
recorder) lewat `RTCRtpTransceiver.setCodecPreferences()` — video codec-nya
berhasil ganti H.264, tapi malah merusak WHEP (viewer connect tapi video
tidak muncul sama sekali). Diputuskan revert karena live streaming lebih
prioritas daripada rekaman lengkap. Kalau mau digali lagi nanti: cek kenapa
MediaMTX WHEP gagal kirim video H.264 ke viewer padahal publish-nya
sukses — kemungkinan butuh konfigurasi profil H.264 spesifik atau versi
MediaMTX lebih baru yang sudah dukung VP8 di recorder-nya.

## Otomatis oleh `setup_streaming.sh`

- [ ] `.env` → `MEDIAMTX_AUTH_SECRET` (di-generate acak kalau belum ada)
- [ ] `.env` → `STREAMING_RECORDINGS_ROOT` (default `<repo>/streaming_recordings` kalau belum diisi)
- [ ] Direktori rekaman dibuat
- [ ] `deploy/mediamtx.generated.yml` di-render dari `deploy/mediamtx.yml` (secret & path rekaman terisi)
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
