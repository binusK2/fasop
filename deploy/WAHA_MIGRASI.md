# Migrasi Gateway WhatsApp: OpenWA → WAHA

FASOP mengirim tiga jenis Early Warning ke grup WhatsApp (RTU, alarm
inspeksi, dan host Zabbix). Semuanya lewat **satu** fungsi,
`device_mon.notifications.kirim_wa()`, jadi mengganti gateway hanya
menyentuh tiga fungsi kecil di modul itu — bukan tiga app.

Dokumen ini dipakai sekali saat pindah dari OpenWA ke
[WAHA](https://github.com/devlikeapro/waha), termasuk saat servernya ikut
pindah.

---

## 1. Yang berubah, dan yang tidak

**Nama variabel `.env` FASOP tidak ada yang berubah.** `WA_API_BASE`,
`WA_API_KEY`, `WA_SESSION_ID`, `WA_CHAT_IDS*`, `WA_ALERT_ENABLED`,
`WA_TIMEOUT` semuanya tetap — namanya memang netral gateway sejak awal.
Yang berubah hanya **nilainya** (host, port, API key) dan bentuk HTTP di
balik layar:

| | OpenWA | WAHA |
|---|---|---|
| Endpoint kirim | `POST /api/sessions/{sesi}/messages/send-text` | `POST /api/sendText` |
| Nama sesi | di **path** URL | di **body** JSON (`session`) |
| Header auth | `X-API-Key` | `X-Api-Key` |
| Body | `{chatId, text}` | `{session, chatId, text}` |
| Port bawaan | 2785 | 3000 |
| Daftar grup | `GET /api/sessions/{sesi}/groups` | `GET /api/{sesi}/groups` |
| Sesi kosong | konfigurasi belum selesai | sah — berarti sesi `default` |

Baris terakhir itu yang paling gampang menggigit: guard lama menolak
mengirim kalau `WA_SESSION_ID` kosong, karena di OpenWA id sesi memang
wajib (ia bagian dari URL). Di WAHA sesi pertama bernama `default` dan
seluruh dokumentasinya memakai nama itu, jadi guard yang sama akan
**membisukan blast pada pemasangan yang sebenarnya sudah benar**.
Sekarang `WA_SESSION_ID` kosong = `default` (dijaga tes
`GatewayWahaTest`).

Isi pesan, aturan opt-in per host, ambang severity, rantai fallback tujuan,
dan tabel log (`RTUAlertLog` / `ZabbixAlertLog` / `InspectionAlertLog`)
tidak berubah sama sekali.

---

## 2. Pasang WAHA di server baru

`docker-compose.yml` minimum yang cukup untuk FASOP:

```yaml
services:
  waha:
    image: devlikeapro/waha
    restart: always
    ports:
      # Pilih SALAH SATU sesuai topologi — lihat "Satu server atau dua?"
      # di bawah. Jangan pernah dibuka ke internet.
      #   FASOP satu server dengan WAHA : "127.0.0.1:3000:3000"
      #   FASOP beda server             : "3000:3000" + firewall
      - "3000:3000"
    volumes:
      # WAJIB — tanpa volume ini sesi WhatsApp hilang tiap container
      # di-restart dan QR harus discan ulang setiap kali.
      - ./.sessions:/app/.sessions
    environment:
      # Nilai LITERAL, tanpa ${...} — lihat peringatan di bawah.
      WAHA_API_KEY: "ganti-dengan-hasil-uuidgen"
      WAHA_DASHBOARD_USERNAME: "admin"
      WAHA_DASHBOARD_PASSWORD: "ganti-dengan-sandi-kuat"
      WHATSAPP_SWAGGER_USERNAME: "admin"
      WHATSAPP_SWAGGER_PASSWORD: "ganti-dengan-sandi-kuat"
      TZ: "Asia/Makassar"
```

> **`${...}` di docker-compose BUKAN penanda "isi di sini".** Itu
> interpolasi variabel: `${admin}` berarti "nilai variabel bernama
> `admin`", bukan teks `admin`.
>
> Yang bikin repot, dua kesalahan yang bentuknya sama bisa berakibat
> beda — terverifikasi dengan `docker compose config`:
>
> | Ditulis | Yang terjadi |
> |---|---|
> | `"${admin}"` | jadi **string kosong** (nama variabelnya sah tapi tidak ada). Hanya warning — container tetap jalan, dashboard tanpa sandi. |
> | `"${fasop@mks}"` | **gagal total**: `invalid interpolation format`, karena `@` tidak sah di nama variabel. Container tidak start. |
>
> Jadi jangan menyimpulkan "compose-nya jalan, berarti sudah benar":
> yang diam justru yang berbahaya. Tulis nilainya langsung seperti
> contoh di atas.
>
> Kalau tidak mau menaruh secret di berkas compose, barulah pakai
> interpolasi — tapi nilainya harus ada di berkas `.env` di sebelah
> `docker-compose.yml` (berkas milik WAHA sendiri, **bukan** `.env`
> FASOP):
>
> ```yaml
>       WAHA_DASHBOARD_PASSWORD: "${WAHA_DASHBOARD_PASSWORD}"
> ```
> ```env
> WAHA_DASHBOARD_PASSWORD=sandi-kuat
> ```
>
> Cek hasil akhirnya sebelum menyalakan — perintah ini mencetak nilai
> yang benar-benar dipakai setelah interpolasi:
>
> ```bash
> docker compose config | grep -A8 environment
> ```

### Satu server atau dua?

Pilihan `ports` di atas bukan selera — salah pilih menghasilkan dua gejala
yang berbeda dan sama-sama membingungkan.

| Topologi | `ports` | `WA_API_BASE` di `.env` FASOP |
|---|---|---|
| WAHA & FASOP satu server | `"127.0.0.1:3000:3000"` | `http://localhost:3000` |
| WAHA & FASOP beda server | `"3000:3000"` + firewall | `http://<ip-server-waha>:3000` |

**Loopback pada topologi dua server akan memblokir FASOP.** `127.0.0.1`
berarti "hanya bisa dihubungi dari dalam server itu sendiri", jadi FASOP
dari server lain mendapat `Connection refused` — padahal container-nya
jelas jalan dan dashboard-nya terbuka normal dari server WAHA.

Kalau beda server, ganti loopback-nya dengan firewall supaya port 3000
tetap tidak terbuka untuk siapa pun selain FASOP:

```bash
sudo ufw allow from <ip-server-fasop> to any port 3000 proto tcp
sudo ufw deny 3000
```

Untuk membuka dashboard dari PC tanpa membuka port ke jaringan, pakai SSH
tunnel — `localhost:3000` di browser Anda jadi menunjuk ke server:

```bash
ssh -L 3000:localhost:3000 user@server-waha
```

**`localhost` di dashboard itu relatif terhadap browser, bukan server.**
Kalau dashboard dibuka dari PC dan Server URL-nya diisi
`http://localhost:3000`, yang dituju adalah PC Anda sendiri. Nilai itu
tersimpan di browser (localStorage), jadi mengubah compose tidak
memperbaikinya — harus disunting di halaman konfigurasi dashboard.
Ingat juga WAHA melayani **http**, bukan `https`.

### Kenapa username & password dashboard perlu diisi

Dashboard (`http://<host>:3000/dashboard`) adalah tempat men-scan QR dan
mengelola sesi, jadi ia bukan halaman hiasan.

- Tanpa `WAHA_DASHBOARD_USERNAME`, bawaannya `admin` (atau `waha`).
- Tanpa `WAHA_DASHBOARD_PASSWORD`, WAHA **membangkitkan sandi acak tiap
  start** dan mencetaknya ke log container — artinya sandinya berganti
  tiap restart dan harus dicari ulang di log.
- `WAHA_DASHBOARD_ENABLED=false` mematikannya sama sekali. Jangan dipakai
  di sini: tanpa dashboard tidak ada cara praktis men-scan QR ulang saat
  sesi putus.

`WHATSAPP_SWAGGER_USERNAME` / `_PASSWORD` menjaga halaman Swagger
(`/`). Boleh disamakan dengan sandi dashboard; FASOP sendiri tidak
memakainya.

Bangkitkan API key-nya:

```bash
uuidgen | tr -d '-'
```

Nilai itu masuk **dua** tempat yang harus sama persis: `WAHA_API_KEY` di
sisi WAHA, dan `WA_API_KEY` di `.env` FASOP.

> **Kalau `WAHA_API_KEY` tidak diisi, WAHA membangkitkan secret acak
> sendiri saat start dan mencetaknya ke log.** Artinya key-nya berganti
> tiap restart container dan blast FASOP mati tanpa ada yang mengubah
> apa pun. Selalu set eksplisit.

Jalankan, lalu buka dashboard di `http://<host>:3000/dashboard`, buat sesi
bernama `default`, dan scan QR-nya dengan nomor WhatsApp operasional.

---

## 3. Sesuaikan `.env` FASOP

```env
WA_ALERT_ENABLED=True
WA_API_BASE=http://localhost:3000        # ganti host bila WAHA beda server
WA_API_KEY=<nilai WAHA_API_KEY tadi>
WA_SESSION_ID=                            # kosongkan = sesi "default"
WA_TIMEOUT=10

WA_CHAT_IDS=                              # grup Early Warning RTU
WA_CHAT_IDS_INSPECTION=                   # grup alarm inspeksi
WA_CHAT_IDS_ZABBIX=                       # grup blast Zabbix
```

**`chatId` grup nyaris pasti berubah kalau nomor WhatsApp-nya diganti.**
Kalau nomor lama dipakai lagi, chatId grup (`...@g.us`) tetap sama dan
`WA_CHAT_IDS*` bisa disalin apa adanya. Kalau nomornya baru, nomor itu
harus dimasukkan dulu ke tiap grup, lalu ambil ulang id-nya:

```bash
python manage.py wa_groups
python manage.py wa_groups --cari "SCADA"
```

Host Zabbix yang memakai kolom **Grup WA Khusus** menyimpan chatId-nya di
database, bukan `.env` — periksa juga **Secure Panel → Device Mon → Host
Zabbix** (filter kolom itu yang tidak kosong) kalau nomornya diganti.

---

## 4. Verifikasi

Urutannya sengaja dari yang paling murah:

```bash
# 1. Sesi WAHA sudah WORKING? (tidak mengirim pesan apa pun)
python manage.py test_wa --hanya-status

# 2. Kirim satu pesan uji ke tiap tujuan
python manage.py test_wa --target rtu
python manage.py test_wa --target inspection
python manage.py test_wa --target zabbix
```

`--hanya-status` membedakan tiga kegagalan yang di OpenWA sama-sama
tampak sebagai "HTTP error":

| Yang tercetak | Artinya |
|---|---|
| `gateway tidak terjangkau` | `WA_API_BASE` salah, atau container WAHA mati |
| `HTTP 401/403 (ditolak)` | `WA_API_KEY` ≠ `WAHA_API_KEY` |
| `sesi "default" tidak ada` | sesinya belum dibuat di dashboard WAHA |
| `SCAN_QR_CODE` | sesi ada tapi belum disambungkan — scan QR |
| `STOPPED` / `FAILED` | sesi perlu di-start / di-restart dari dashboard |
| `WORKING` | siap; kalau pesan tetap tidak masuk, masalahnya di chatId |

Host Zabbix yang memakai Grup WA Khusus tidak tercakup `test_wa` — tes
lewat action **"Kirim pesan uji WA ke tujuan host terpilih"** di Admin →
Host Zabbix.

---

### Kalau dapat `401 Unauthorized`

401 berarti **server WAHA hidup dan terjangkau** — kalau tidak, hasilnya
`Connection refused`. Yang salah murni kuncinya. Tiga penyebab, berurut
dari yang paling sering:

**1. Kunci di container ternyata kosong.** Ini akibat `${WAHA_API_KEY}`
tanpa berkas `.env` di sebelah compose. Saat `WAHA_API_KEY` kosong, WAHA
membangkitkan kunci **acak** sendiri tiap start dan hanya mencetaknya ke
log — jadi kunci apa pun yang dikirim dijawab 401. Periksa apa yang
benar-benar diterima container, bukan apa yang tertulis di compose:

```bash
docker compose exec waha printenv | grep -i -E "waha|whatsapp"
docker compose logs waha 2>&1 | grep -i -E "api.?key|secret|generated"
```

**2. Yang dikirim hash-nya, bukan kunci aslinya.** `WAHA_API_KEY`
menerima dua bentuk, dan header `X-Api-Key` **selalu** berisi kunci polos:

| Di compose | Isi header `X-Api-Key` |
|---|---|
| `WAHA_API_KEY: "abc123..."` | `abc123...` |
| `WAHA_API_KEY: "sha512:98b6d1..."` | `abc123...` — kunci asli, **bukan** hash-nya |

**3. Container belum di-recreate.** Perubahan environment tidak terbaca
oleh `docker compose restart`. Harus:

```bash
docker compose up -d
```

Uji dari server WAHA dulu, baru dari server FASOP — kalau yang pertama
`200` tapi yang kedua `Connection refused`, masalahnya bukan kunci lagi
melainkan `ports`/firewall (lihat "Satu server atau dua?"):

```bash
curl -s -o /dev/null -w "%{http_code}
" http://localhost:3000/api/sessions -H "X-Api-Key: <kunci>"
curl -s -o /dev/null -w "%{http_code}
" http://<ip-server-waha>:3000/api/sessions -H "X-Api-Key: <kunci>"
```

---

## 5. Setelah pindah server

Kalau FASOP-nya ikut pindah, yang berkaitan dengan WhatsApp:

- **Jangan lupa cron `collect_rtu` dan `sync_zabbix`.** Blast berangkat
  dari cron, bukan dari halaman web — WAHA bisa `WORKING` dan `test_wa`
  hijau sementara tidak ada alert sungguhan yang pernah terkirim karena
  crontab-nya belum dipasang di server baru.
- **Kalau WAHA dan FASOP beda server**, `WA_API_BASE` tidak boleh
  `localhost` lagi, dan port 3000 harus dibuka hanya untuk IP FASOP
  (firewall), bukan ke publik.
- **Pindahkan direktori `.sessions/`** dari server lama kalau ingin sesi
  WhatsApp-nya ikut tanpa scan QR ulang. Kalau tidak, cukup scan ulang.
- Turunkan `WA_ALERT_ENABLED=False` selama masa pindah kalau kedua server
  sempat jalan bersamaan — kalau tidak, grup menerima alert dobel untuk
  gangguan yang sama.

---

## 6. Kalau suatu saat ganti gateway lagi

Sentuh **hanya** tiga fungsi di `device_mon/notifications.py`:
`_build_url()`, `_build_headers()`, `_build_payload()` — plus `sesi_wa()`
kalau gateway barunya punya konsep sesi yang berbeda. Jangan membuat klien
HTTP kedua di app lain: `inspection` dan jalur Zabbix sama-sama memanggil
`kirim_wa()` yang sama, dan itulah yang membuat pergantian gateway berhenti
di satu berkas.

`GatewayWahaTest` di `device_mon/tests.py` menjaga bentuk HTTP itu. Tes
gating lainnya mem-mock `kirim_wa` seluruhnya, jadi tanpa kelas itu path,
header, dan body bisa berubah semua tanpa satu tes pun gagal — persis yang
terjadi sewaktu OpenWA masih dipakai.
