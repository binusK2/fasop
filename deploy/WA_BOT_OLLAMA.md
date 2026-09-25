# Bot Chat WhatsApp: WAHA → n8n → Ollama

Bot tanya-jawab WhatsApp memakai LLM lokal. Alurnya:

```
WhatsApp ──► WAHA ──(webhook "message")──► n8n ──(/api/chat)──► Ollama
                ▲                                │
                └────────(POST /api/sendText)────┘
```

Workflow siap-impor: [`n8n_wa_bot_ollama.json`](n8n_wa_bot_ollama.json).
Semuanya di luar Django — FASOP sendiri tidak berubah, dan blast Early
Warning tetap lewat `device_mon.notifications.kirim_wa()` seperti biasa.

---

## 1. Keputusan pertama: nomor bot TERPISAH dari nomor blast

**Sangat disarankan bot memakai nomor WhatsApp dan container WAHA sendiri**,
bukan sesi `default` yang dipakai blast Early Warning.

- **Risiko blokir.** WhatsApp memblokir nomor yang terdeteksi sebagai bot
  (membalas cepat ke banyak orang). Kalau nomor blast yang terblokir, alert
  RTU/Zabbix/inspeksi ikut mati diam-diam — dan itu baru ketahuan saat ada
  gangguan sungguhan yang tidak terkabarkan.
- **Grup operasional.** Nomor blast adalah anggota grup Early Warning.
  Workflow ini memang menolak semua pesan grup secara bawaan
  (`IZINKAN_GRUP = false`), tapi memisahkan nomornya menghapus risiko itu
  sepenuhnya, bukan cuma bergantung pada satu `if`.
- **WAHA Core (gratis) hanya mendukung satu sesi (`default`) per container.**
  Multi-sesi butuh WAHA Plus. Jadi nomor kedua = container WAHA kedua.

Tambahkan di `docker-compose.yml` WAHA yang sudah ada (sesi blast tidak
disentuh):

```yaml
  waha-bot:
    image: devlikeapro/waha
    restart: always
    ports:
      - "127.0.0.1:3001:3000"      # port beda dari WAHA blast
    volumes:
      - ./.sessions-bot:/app/.sessions   # WAJIB, direktori BEDA dari blast
    environment:
      WAHA_API_KEY: "kunci-bot-hasil-uuidgen"      # beda dari kunci blast
      WAHA_DASHBOARD_USERNAME: "admin"
      WAHA_DASHBOARD_PASSWORD: "sandi-kuat"
      WHATSAPP_SWAGGER_USERNAME: "admin"
      WHATSAPP_SWAGGER_PASSWORD: "sandi-kuat"
      TZ: "Asia/Makassar"
```

Semua peringatan di [`WAHA_MIGRASI.md`](WAHA_MIGRASI.md) berlaku sama:
nilai literal (bukan `${...}`), volume sesi wajib, `WAHA_API_KEY` wajib
diisi eksplisit, dan `docker compose up -d` (bukan `restart`) setelah
mengubah environment.

```bash
docker compose up -d waha-bot
```

Buka `http://localhost:3001/dashboard` (lewat SSH tunnel bila dari PC), buat
sesi `default`, scan QR dengan nomor bot.

> Kalau tetap ingin memakai nomor blast: di workflow isi `WAHA_URL` ke WAHA
> blast dan biarkan `IZINKAN_GRUP = false`. Pasang webhook dari **dashboard**
> (langkah 4), jangan lewat env `WHATSAPP_HOOK_URL` — env itu butuh recreate
> container, dan blast padam selama itu.

---

## 2. Supaya n8n bisa menjangkau Ollama

**Ollama bawaannya hanya mendengar di `127.0.0.1:11434`.** Kalau n8n jalan di
Docker, `localhost` di dalam container adalah container itu sendiri — bukan
host — jadi `http://localhost:11434` dari n8n selalu `ECONNREFUSED` walau
`curl localhost:11434` di host berhasil.

Buat Ollama mendengar di semua interface (Linux, systemd):

```bash
sudo systemctl edit ollama
```
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```
```bash
sudo systemctl restart ollama
sudo ufw deny 11434          # jangan buka Ollama ke jaringan; container tetap bisa
```

> `ufw deny` tidak memblokir lalu lintas dari bridge Docker di banyak
> setup, tapi kalau ternyata ikut terblokir, izinkan subnet Docker saja:
> `sudo ufw allow from 172.16.0.0/12 to any port 11434 proto tcp`.

Lalu di service n8n pada compose-nya tambahkan:

```yaml
  n8n:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Uji dari dalam container n8n (bukan dari host):

```bash
docker compose exec n8n wget -qO- http://host.docker.internal:11434/api/tags
```

Keluar daftar model = siap. Pilih model dari `ollama list` dan isi di
`MODEL`. Untuk Bahasa Indonesia, `qwen2.5:7b` / `gemma2:9b` / `llama3.1:8b`
umumnya layak; di mesin tanpa GPU pakai versi 3B–4B supaya jawaban tidak
lebih dari semenit.

**Kalau Ollama beda server**, ganti `OLLAMA_URL` jadi `http://<ip>:11434` dan
buka port 11434 hanya untuk IP server n8n.

### Ollama di PC Windows (pemasangan UP2B)

Ollama jalan di PC Windows di LAN kantor (GPU lokal), n8n di server FASOP —
subnet berbeda (`192.168.30.x` → `192.168.68.x`). Yang dibutuhkan, berurutan:

1. `setx OLLAMA_HOST "0.0.0.0:11434"` lalu **Quit & buka lagi** Ollama dari
   tray — variabelnya hanya terbaca saat start. Periksa dengan
   `Get-NetTCPConnection -LocalPort 11434 -State Listen`: alamatnya harus
   `0.0.0.0`/`::`, bukan `127.0.0.1`.
2. Firewall Windows PC: izinkan TCP 11434 **hanya dari IP server n8n**,
   `-Profile Any` (jaringan kantor terdeteksi sebagai profil Public).
3. **Firewall kantor antar-subnet** harus membuka TCP 11434 dari server n8n
   ke PC itu. Ini yang terakhir menahan pemasangan UP2B.
4. DHCP reservation untuk IP PC — kalau IP-nya berganti, bot hanya membalas
   pesan maaf.

**Timeout ≠ connection refused, dan bedanya menunjukkan lokasi masalah.**
`curl` dari server yang *timeout* (paket dibuang tanpa jawaban) berarti
blokirnya di jaringan — firewall kantor atau firewall PC. *Connection
refused* (ditolak seketika) berarti paketnya sampai ke PC tapi tidak ada yang
mendengar di alamat itu — langkah 1 belum berlaku. Jangan mengutak-atik
Ollama saat gejalanya timeout.

Ollama harus menyala tanpa menunggu orang login: PC yang restart karena
Windows Update lalu diam di layar login = bot mati.

---

## 3. Supaya WAHA bisa menjangkau n8n (dan sebaliknya)

Dua arah, dua URL berbeda — keduanya dilihat **dari dalam container**:

| Arah | Diisi di | Contoh (satu host, satu compose) |
|---|---|---|
| WAHA → n8n (webhook) | konfigurasi sesi WAHA | `http://n8n:5678/webhook/waha-bot` |
| n8n → WAHA (kirim balasan) | `WAHA_URL` di workflow | `http://waha-bot:3000` |

Nama service (`n8n`, `waha-bot`) hanya terjangkau kalau kedua container ada
di **network Docker yang sama** (satu `docker-compose.yml`, atau network
eksternal bersama). Kalau beda compose, pakai
`http://host.docker.internal:<port>` + `extra_hosts` seperti di atas, atau
IP server.

Perhatikan port di kolom kanan adalah **port di dalam container** (3000),
bukan port yang dipublikasikan ke host (3001).

---

## 4. Impor workflow & pasang webhook di WAHA

1. n8n → **Workflows → Import from File** → `deploy/n8n_wa_bot_ollama.json`.
2. Buat dua credential **Header Auth**:
   - **WAHA API Key** — Name `X-Api-Key`, Value = `WAHA_API_KEY` container bot.
     Pasang di node *Tampilkan mengetik* dan *Kirim balasan WA*.
   - **WAHA webhook token** — Name `X-Bot-Token`, Value = string acak baru
     (`uuidgen | tr -d '-'`). Pasang di node *Webhook WAHA*. Tanpa ini siapa
     pun yang tahu URL webhook bisa menyuruh bot mengirim pesan.
3. Buka node **Saring & siapkan prompt**, sesuaikan blok PENGATURAN
   (`WAHA_URL`, `OLLAMA_URL`, `MODEL`, `DAFTAR_IZIN`, `SYSTEM_PROMPT`).
4. **Aktifkan workflow** (toggle Active). Lihat catatan "URL test vs
   production" di bawah.
5. Di dashboard WAHA bot → sesi `default` → **Configuration → Webhooks**:
   - URL: `http://n8n:5678/webhook/waha-bot`
   - Events: **`message`** saja
   - Custom headers: `X-Bot-Token` = nilai credential tadi

   Simpan. Menyimpan konfigurasi bisa me-restart sesi sebentar.

Kirim "halo" dari nomor lain ke nomor bot.

---

## 5. Perilaku yang sengaja dipilih

- **Event `message`, bukan `message.any`.** `message.any` ikut mengirim
  pesan yang dikirim nomor itu sendiri — termasuk setiap balasan bot dan,
  kalau memakai nomor blast, setiap alert. Workflow juga membuang `fromMe`
  sebagai lapis kedua, karena bot yang membalas dirinya sendiri adalah
  loop tanpa akhir yang menghabiskan kuota dan mengundang blokir.
- **Webhook dijawab seketika (`Respond: Immediately`).** Ollama di CPU bisa
  butuh puluhan detik. Kalau webhook menunggu jawaban LLM, WAHA menganggapnya
  timeout dan **mengirim ulang** — hasilnya bot menjawab pertanyaan yang sama
  dua-tiga kali. Karena itu juga ada penyaring `payload.id` ganda.
- **Grup ditolak secara bawaan.** Dengan `IZINKAN_GRUP = true`, bot hanya
  menjawab pesan berawalan `!bot`; tanpa prefix itu semua obrolan di grup
  akan dijawab.
- **Riwayat percakapan** disimpan di static data workflow: 10 pesan terakhir
  per chat, basi setelah 60 menit tanpa obrolan. Ketik `/reset` untuk mulai
  baru. Pertanyaan yang gagal dijawab tidak ikut disimpan.
- **Ollama gagal = balasan maaf, bukan diam.** Diam membuat orang mengirim
  ulang pertanyaan berkali-kali.
- **System prompt melarang mengarang data realtime.** LLM ini tidak punya
  akses ke SCADA/FASOP; tanpa larangan itu ia dengan yakin akan menyebut
  angka beban atau status RTU karangan — di konteks operasi sistem tenaga,
  itu lebih berbahaya daripada tidak menjawab. Kalau nanti bot perlu
  data FASOP, jalurnya adalah memanggil API baca FASOP dari n8n
  (lihat [`docs/API_EKSTERNAL.md`](../docs/API_EKSTERNAL.md), kunci
  `KunciApi` sendiri untuk bot) lalu menyisipkan hasilnya ke prompt —
  bukan membiarkan model menebak.

---

## 6. Pemasangan UP2B (September 2026) — yang benar-benar dipakai

Keputusan akhirnya **satu nomor**: bot menumpang sesi blast yang sudah ada.

| | Nilai |
|---|---|
| Sesi WAHA | `fasop-blast` (bukan `default`) — `SESI` di node *Saring* |
| Webhook WAHA → n8n | URL **publik** `https://n8n.fasopup2bmks.id/webhook/waha-bot`, event `message` |
| Ollama | PC Windows `192.168.68.118:11434`, GPU RTX 5050, `qwen2.5:7b` (~1–4 dtk/jawaban) |

Jebakan yang menghabiskan waktu saat memasangnya, berurutan:

- **Webhook lewat URL publik n8n**, bukan jaringan Docker: container `waha`
  tidak perlu dibuat ulang (= blast tidak padam) untuk bisa menjangkau n8n.
- **Dua credential Header Auth, bukan satu.** *WAHA webhook token*
  (`X-Bot-Token`, untuk node Webhook) dan *WAHA API Key* (`X-Api-Key`, untuk
  *Tampilkan mengetik* + *Kirim balasan WA*). Keduanya bertipe sama, jadi
  gampang cuma membuat satu dan memakainya di tiga node — lalu setiap
  perbaikan di satu arah merusak arah lainnya (webhook 403 ↔ kirim 401).
  Buat yang kedua lewat **Create new credential**, bukan ikon edit.
- **Nama sesi** terlihat di log WAHA (`session:fasop-blast`). Salah nama
  sesi = semua pesan dibuang diam-diam di node *Saring*.
- **`DAFTAR_IZIN` berisi id `@lid`, bukan nomor HP.** WhatsApp mengirim
  `from` sebagai `225464341790828@lid`; nomor telepon tidak akan pernah
  cocok. Ambil nilainya dari tab Input node *Saring* setelah orangnya
  mengirim satu chat.
- **Node Code yang mengembalikan `[]` tampil "sukses"** dan eksekusi berhenti
  di situ tanpa error. Eksekusi yang "berhenti di node X" hampir selalu
  berarti node *sebelumnya* mengeluarkan 0 item — lihat jumlah item-nya.
- **WAHA mengulang webhook yang gagal sampai 15× dengan jeda eksponensial.**
  Setelah 403/404 diperbaiki, pesan-pesan lama ikut tiba terlambat dan
  sebagian dibuang penyaring pesan ganda — jangan dikira pesan tes baru.
- **Request ke Ollama tiba dari `192.168.68.1`** (router kantor melakukan
  NAT), bukan dari IP server n8n. Aturan firewall Windows di PC harus
  mengizinkan alamat router itu; pembatasan sesungguhnya ada di firewall
  kantor.

## 7. Data OPSIS & FASOP untuk bot

Tanpa data, bot hanya bisa mengarahkan ke FASOP — system prompt sengaja
melarangnya menyebut angka, karena model 7B yang tidak diberi data akan
mengarang angka beban atau status RTU dengan sangat meyakinkan.

Alurnya sekarang:

```
Saring (deteksi topik) → Ambil ×6 (API FASOP) → Ringkas data (teks) → Ollama
```

| Topik (kata kunci di node *Saring*) | Endpoint |
|---|---|
| pembangkit, beban, MW, frekuensi, Hz, sistem, PLTU/PLTA/… | `/api/v1/opsis/beban-pembangkit/?unit=0` (sudah memuat frekuensi) |
| KTT, konsumen, smelter, industri | `/api/v1/opsis/beban-ktt/` |
| trafo, IBT, gardu induk | `/api/v1/opsis/beban-trafo/?jenis=distribusi\|ibt` |
| RTU, Zabbix, down, offline, putus, VoIP, router, … | `/api/v1/fasop/status-monitor/` |
| pemeliharaan, maintenance, jadwal, kunjungan, TTD | `/api/v1/fasop/pemeliharaan/` |
| peralatan, perangkat, merk, tipe, health, umur, cari | `/api/v1/fasop/peralatan/?q=<kalimat tanpa kata umum>` |

### Memasangnya

1. **Deploy FASOP** yang memuat tiga endpoint `fasop/*` (lihat
   `docs/API_EKSTERNAL.md` bagian 9–11).
2. **Admin → Devices → Data API Eksternal**: buka (`aktif`) data
   `status_monitor`, `pemeliharaan`, `peralatan`. Data baru selalu lahir
   TERTUTUP.
3. **Admin → Devices → Kunci API**: buat kunci **"Bot WhatsApp"**, centang
   `beban_pembangkit`, `beban_ktt`, `beban_trafo`, `status_monitor`,
   `pemeliharaan`, `peralatan`. Kunci terpisah untuk bot, bukan `API_KEY`
   global (yang juga bisa MENULIS) dan bukan kunci konsumen lain — supaya
   bot bisa dicabut sendiri tanpa memutus UP2D dan sebaliknya.
4. **n8n → Credentials**: credential Header Auth ketiga, **FASOP API bot**
   (Name `X-API-Key`, Value = kunci tadi). Lagi-lagi *Create new credential*,
   jangan menyunting credential WAHA.
5. Impor ulang `n8n_wa_bot_ollama.json` (atau salin node-nodenya), isi blok
   PENGATURAN di node *Saring* termasuk `FASOP_URL`, dan pasang credential di
   ketiga jenis node.

### Kenapa dirancang begini

- **Kata kunci, bukan tool-calling LLM.** Model 7B kadang lupa memanggil
  tool lalu tetap menjawab dengan angka karangan. Kata kunci bisa salah memilih
  data, tapi tidak pernah mengarang, dan menambah kata kunci cukup di satu
  tempat. Kata pendek dicocokkan utuh (`kit` ≠ "kita", `alat` ≠ "alamat");
  `hi` sengaja bukan pemicu karena juga sapaan.
- **Tanpa node IF.** Endpoint yang tidak dibutuhkan pertanyaan ini diarahkan
  ke `/api/v1/ping/` — rantainya tetap lurus. Node IF pernah membuat eksekusi
  tampak "macet" padahal penyebabnya node sebelumnya mengeluarkan 0 item.
- **Data jadi teks, disisipkan tepat sebelum pertanyaan, dan TIDAK disimpan
  ke riwayat.** Model kecil lebih memperhatikan yang dekat dengan pertanyaan,
  dan angka basi tidak boleh terbawa ke pertanyaan berikutnya.
- **MW 2 desimal**, sama dengan kartu dashboard OPSIS. Pembulatan berbeda
  berarti angka di WhatsApp tidak akan pernah cocok dengan layar ruang kontrol.
- **503 diteruskan sebagai "TIDAK TERSEDIA (alasan)"**, dan system prompt
  melarang menarik kesimpulan darinya. Diuji langsung ke `qwen2.5:7b`: tanpa
  larangan itu, "ada RTU yang down?" saat data tidak tersedia dijawab
  *"Tidak ada RTU yang tercatat down"* — terbaca sebagai "semua normal".
- **Penanda `diragukan` operator OPSIS ikut disebut** bersama angkanya.

**Data yang tidak ada di sini tetap dijawab "tidak punya datanya"** — termasuk
tiket gangguan (`gangguan.Gangguan`), yang belum punya endpoint. Menambahkannya
= endpoint baru di `api/` + entri `api/registry.py` + satu node *Ambil* + satu
blok di node *Ringkas*.

**Siapa pun di `DAFTAR_IZIN` bisa membaca data ini lewat WhatsApp**, dan isi
chat melewati server WhatsApp. Kosongkan `DAFTAR_IZIN` hanya kalau memang itu
yang diinginkan.

## 8. Kalau tidak jalan

| Gejala | Penyebab paling mungkin |
|---|---|
| Tidak ada eksekusi sama sekali di n8n | workflow belum **Active**, atau URL webhook memakai `/webhook-test/` |
| Eksekusi ada tapi berhenti di *Saring* tanpa output | pesan tersaring: grup, `fromMe`, `DAFTAR_IZIN`, atau `session` ≠ `SESI` — lihat input node |
| *Webhook WAHA* merah `403`/`Authorization data is wrong` | `X-Bot-Token` di WAHA ≠ credential n8n |
| *Tanya Ollama* `ECONNREFUSED` | Ollama masih `127.0.0.1`, atau `extra_hosts` belum dipasang (langkah 2) |
| *Tanya Ollama* `model not found` | nama `MODEL` tidak persis sama dengan `ollama list` (termasuk tag `:7b`) |
| Balasan "Maaf, bot sedang tidak bisa menjawab" setelah ±3 menit | model terlalu besar untuk CPU — pakai model lebih kecil atau naikkan timeout |
| *Kirim balasan WA* `401` | credential **WAHA API Key** ≠ `WAHA_API_KEY` container bot |
| Bot menjawab dua kali | workflow diimpor dua kali dan keduanya aktif |
| Bot lupa percakapan saat dites manual | lihat catatan static data di bawah |

**URL test vs production.** n8n punya dua URL webhook:
`/webhook-test/waha-bot` hanya hidup selama tombol *Listen for test event*
ditekan, `/webhook/waha-bot` hidup selama workflow **Active**. WAHA harus
menunjuk yang kedua — kalau menunjuk yang pertama, bot tampak jalan saat
dites lalu mati begitu tab editor ditutup.

**Static data hanya tersimpan pada eksekusi production** (dipicu webhook
saat workflow Active), bukan pada eksekusi manual/test. Jadi riwayat
percakapan dan penyaring pesan ganda tampak "tidak bekerja" selama menguji
dari editor. Itu bukan bug.

Riwayat juga bisa kehilangan satu giliran kalau dua pesan dari chat yang
sama tiba bersamaan (eksekusi paralel, yang terakhir selesai menang). Untuk
bot tanya-jawab ini dapat diterima; kalau suatu saat butuh memori yang
andal, pindahkan ke Postgres/Redis.

Cek sesi WAHA bot tanpa mengirim apa pun:

```bash
curl -s http://localhost:3001/api/sessions -H "X-Api-Key: <kunci-bot>"
```

Status harus `WORKING`. Arti status lainnya sama dengan tabel di
`WAHA_MIGRASI.md` bagian 4.
