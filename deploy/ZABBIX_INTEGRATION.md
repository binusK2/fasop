# Integrasi Zabbix (`device_mon`)

Menampilkan status host/peralatan yang dipantau Zabbix di dashboard FASOP
(**Device Monitor → Zabbix**, `/device-mon/zabbix/`), lewat dua jalur yang
saling melengkapi. Sengaja satu app dengan RTU (`/device-mon/`) — keduanya
"status peralatan realtime", jadi tetap ketemu di satu tempat (Device
Monitor) alih-alih tersebar ke app terpisah per sumber data.

| Jalur | Arah | Peran |
|---|---|---|
| **Pull — Zabbix API** | FASOP → Zabbix (cron `sync_zabbix`) | Sumber kebenaran periodik. Membuat host baru otomatis, memulihkan status kalau webhook sempat gagal terkirim. |
| **Push — Webhook** | Zabbix → FASOP (`/device-mon/zabbix/webhook/`) | Update realtime (detik) saat trigger PROBLEM/pulih, tanpa menunggu jadwal cron. |

Keduanya menulis ke tabel yang sama (`ZabbixHost`, `ZabbixEventLog`), jadi
boleh dipakai salah satu saja untuk mulai (disarankan: setup pull dulu,
webhook menyusul untuk latensi lebih rendah).

---

## 1. Siapkan akses Zabbix API (untuk `sync_zabbix`)

Buat user Zabbix baru khusus, role **Read only** — jangan pakai akun admin
biasa. Lalu pilih salah satu cara autentikasi:

### Opsi A — API token (direkomendasikan, Zabbix ≥ 5.4)
1. Login sebagai admin → **Users → API tokens → Create API token**.
2. User: pilih user read-only yang tadi dibuat. Expires: kosongkan/atur
   sesuai kebijakan.
3. Simpan token yang muncul (hanya ditampilkan sekali) → isi ke `.env`:
   ```env
   ZABBIX_API_TOKEN=<token-yang-digenerate>
   ```

### Opsi B — Username/password (fallback, Zabbix lama)
```env
ZABBIX_API_USER=fasop-readonly
ZABBIX_API_PASSWORD=<password-kuat>
```

### Endpoint & filter
```env
ZABBIX_API_URL=http://zabbix.contoh.local/api_jsonrpc.php   # atau .../zabbix/api_jsonrpc.php
ZABBIX_API_TIMEOUT=10
ZABBIX_HOST_GROUPS=SCADA,Telkom      # opsional — kosong = semua host
```

### Cron
```bash
*/2 * * * * cd /path/to/fasop && /path/to/venv/bin/python manage.py sync_zabbix >> /var/log/fasop/sync_zabbix.log 2>&1
```

Uji koneksi tanpa menulis apa pun ke database:
```bash
python manage.py sync_zabbix --dry-run
```

---

## 2. Siapkan Webhook (push realtime)

### 2.1. Token bersama
Isi string acak yang kuat di `.env` FASOP — akan dipakai lagi di skrip
webhook Zabbix pada langkah berikutnya:
```env
ZABBIX_WEBHOOK_TOKEN=<string-acak-yang-kuat>
```
Endpoint `/device-mon/zabbix/webhook/` **tanpa login** (dipanggil server
Zabbix, bukan browser) — keamanannya murni dari token ini, jadi wajib
diisi sebelum dipakai di produksi.

### 2.2. Buat Media Type "Webhook" di Zabbix
**Alerts → Media types → Create media type**
- Name: `FASOP Webhook`
- Type: `Webhook`
- Parameters (tambahkan satu-satu, kolom kiri = nama parameter, kanan =
  nilai/macro):

  | Name | Value |
  |---|---|
  | `url` | `https://fasop.domain-anda/device-mon/zabbix/webhook/` |
  | `token` | `<isi sama dengan ZABBIX_WEBHOOK_TOKEN>` |
  | `event_status` | `{EVENT.STATUS}` |
  | `eventid` | `{EVENT.ID}` |
  | `hostid` | `{HOST.ID}` |
  | `host` | `{HOST.HOST}` |
  | `host_visible_name` | `{HOST.NAME}` |
  | `severity` | `{EVENT.SEVERITY}` |
  | `problem_name` | `{EVENT.NAME}` |

  `{EVENT.STATUS}` Zabbix persis menghasilkan `PROBLEM` atau `RESOLVED` —
  cocok langsung dengan kontrak endpoint (lihat §3), tidak perlu mapping
  tambahan.

- Script (tab **Script**):
  ```javascript
  try {
      var params = JSON.parse(value);

      var payload = JSON.stringify({
          event_status:      params.event_status,
          eventid:           params.eventid,
          hostid:            params.hostid,
          host:               params.host,
          host_visible_name: params.host_visible_name,
          severity:          params.severity,
          problem_name:      params.problem_name
      });

      var req = new HttpRequest();
      req.addHeader('Content-Type: application/json');
      req.addHeader('X-Zabbix-Webhook-Token: ' + params.token);

      var resp = req.post(params.url, payload);

      if (req.getStatus() < 200 || req.getStatus() >= 300) {
          throw 'HTTP ' + req.getStatus() + ': ' + resp;
      }
      return 'OK: ' + resp;
  } catch (error) {
      Zabbix.log(4, '[FASOP Webhook] ERROR: ' + error);
      throw 'FASOP Webhook gagal: ' + error;
  }
  ```
- Klik **Test** di pojok kanan atas form untuk mencoba kirim payload dummy
  sebelum dipakai di Action sungguhan — cara tercepat memastikan
  `ZABBIX_WEBHOOK_TOKEN` dan URL sudah benar (harus dapat respons
  `{"status": "ok", ...}`).

### 2.3. Buat user penerima notifikasi
**Users → Users → Create user**
- Username: mis. `fasop-webhook` (tidak perlu login interaktif, jadi
  password boleh acak & tidak dibagikan)
- User group: buat/gunakan grup dengan permission minimal (tidak perlu akses
  frontend Zabbix)
- Tab **Media**: tambahkan media `FASOP Webhook`, severity: centang semua
  level yang ingin diteruskan ke FASOP, "Active time": `1-7,00:00-24:00`

### 2.4. Buat Action
**Alerts → Actions → Trigger actions → Create action**
- Name: `Kirim status ke FASOP`
- Conditions: sesuaikan (mis. batasi ke host group tertentu), atau kosongkan
  untuk semua problem
- Tab **Operations**: tambah operation → Send message to users → pilih user
  `fasop-webhook` → **Send only to**: `FASOP Webhook`
- Tab **Recovery operations**: tambah operation yang sama (send message,
  user `fasop-webhook`, media `FASOP Webhook`) — **wajib** diisi juga,
  supaya event `RESOLVED` (host pulih) ikut terkirim, bukan cuma saat
  PROBLEM muncul.
- Enabled: ya

---

## 3. Kontrak payload webhook (referensi)

```
POST /device-mon/zabbix/webhook/
Header:  X-Zabbix-Webhook-Token: <ZABBIX_WEBHOOK_TOKEN>
         (atau ?token=... di query string kalau Zabbix versi lama tidak
         bisa set header custom lewat HttpRequest)
Body:
{
  "event_status": "PROBLEM" | "OK" | "RESOLVED",
  "eventid": "12345",
  "hostid": "10084",
  "host": "nama-teknis-host",
  "host_visible_name": "Nama Tampilan Host",
  "severity": "High",
  "problem_name": "Interface eth0 down",
  "event_time": "2026-08-18T10:00:00+08:00"   # opsional, default: waktu server FASOP
}
```

Idempoten: request dengan `eventid` + `event_status` yang sama persis dua
kali (Zabbix retry) tidak akan membuat log ganda. Setiap request — berhasil
atau ditolak (token salah, JSON tidak valid, dsb.) — dicatat di
**Admin → Device Monitor → Log Webhook Zabbix**, cara tercepat
mendiagnosis kalau Action di Zabbix sudah jalan tapi status di FASOP tidak
berubah.

---

## 4. Sisi FASOP

```bash
git pull origin main
pip install -r requirements.txt      # tidak ada paket baru — 'requests' sudah ada
python manage.py migrate
```

Lalu tambahkan ke `.env` server (lihat ringkasan semua variabel di
`CLAUDE.md` bagian *Environment Variables*):
```env
ZABBIX_API_URL=
ZABBIX_API_TOKEN=
ZABBIX_HOST_GROUPS=
ZABBIX_WEBHOOK_TOKEN=
```

Cron `sync_zabbix` (lihat §1). Dashboard: sidebar **Device Monitor →
Zabbix**, atau langsung `/device-mon/zabbix/`.

### Perhitungan availability — hanya severity High

Angka availability (dashboard, per grup, per host) **hanya menghitung
problem dengan severity `High`** sebagai downtime. Problem severity lain
(Warning, Average, Information, Not classified, Disaster) tetap tampil
di dashboard, daftar problem terkini, dan histori host — hanya saja tidak
menurunkan persentase availability.

Diatur lewat konstanta `SEVERITY_DIHITUNG` di `device_mon/views.py`
(mis. jadikan `['High', 'Disaster']` kalau Disaster juga mau dihitung).

### Tampilan per Host Group

`ZABBIX_HOST_GROUPS` boleh diisi lebih dari satu, dipisah koma, mis.
`ZABBIX_HOST_GROUPS=VoIP Mks,CRS,ROIP,Router,VoIP Baubau,VoIP ICON+,VoIP Luwuk`
— nama harus PERSIS sama dengan nama Host Group di Zabbix (**Data
collection → Host groups**), termasuk kapitalisasi.

- `/device-mon/zabbix/` (Ringkasan) menampilkan total status + satu kartu
  ringkas per Host Group (jumlah OK/PROBLEM/availability), bukan daftar
  semua host — supaya tetap mudah dibaca walau host-nya banyak.
- Klik kartu grup (atau link-nya di sidebar) → halaman detail grup
  (`/device-mon/zabbix/group/<nama grup>/`) berisi grid semua host di
  grup itu + chart availability + problem terkini, khusus grup tsb.
- Sidebar Device Monitor menampilkan daftar grup secara **otomatis**
  dari data host yang sudah tersinkron (bukan langsung dari
  `ZABBIX_HOST_GROUPS`) — jadi grup baru baru muncul di sidebar setelah
  `sync_zabbix` berhasil menariknya minimal sekali (atau webhook pertama
  masuk, lalu dilengkapi grup-nya oleh `sync_zabbix` berikutnya —
  webhook sendiri tidak membawa info Host Group).
- Satu host boleh tercatat di lebih dari satu Host Group (mis. host yang
  masuk `CRS` sekaligus `ROIP`) — otomatis muncul di kedua halaman grup.

Opsional — hubungkan host Zabbix ke aset FASOP yang sudah ada: buka
**Secure Panel → Device Monitor → Host Zabbix**, pilih host, isi field
**Perangkat FASOP** (autocomplete dari `devices.Device`). Tidak wajib —
dashboard tetap berfungsi penuh tanpa mapping ini.

Field **Lokasi / Gardu** juga bukan teks bebas — dropdown search-as-you-type
ke master data **Lokasi Site** FASOP yang sama (`devices.SiteLocation`,
yang juga dipakai `Device`), supaya penamaan lokasi konsisten di seluruh
aplikasi. Kalau lokasi yang dicari belum ada di daftar, tambahkan dulu di
**Secure Panel → Devices → Lokasi Site** — Zabbix API sendiri tidak
menyediakan info lokasi/GPS, jadi field ini selalu diisi manual.

---

## 5. Debug koneksi Zabbix API gagal

Kalau `sync_zabbix --dry-run` error atau tidak mengembalikan host sama
sekali, urutan pengecekan yang paling sering menemukan masalahnya:

1. **URL API salah path.** `ZABBIX_API_URL` harus menunjuk persis ke file
   `api_jsonrpc.php`, bukan ke root Zabbix. Tergantung instalasi, bisa
   `http://host/api_jsonrpc.php` **atau** `http://host/zabbix/api_jsonrpc.php`
   (kalau Zabbix di-deploy di subpath `/zabbix/`). Coba `curl` manual dari
   server FASOP dulu sebelum menuduh kode:
   ```bash
   curl -sS -X POST -H 'Content-Type: application/json-rpc' \
     -d '{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}' \
     "$ZABBIX_API_URL"
   ```
   Respons yang benar: `{"jsonrpc":"2.0","result":"7.0.x","id":1}`. Kalau
   ini gagal (timeout, connection refused, 404 HTML bukan JSON), masalahnya
   di jaringan/URL — **bukan** di kode Python, jadi cek dulu sebelum lanjut
   ke poin berikutnya.
2. **Jaringan tersambung tapi port/firewall API beda dari port biasa
   diakses.** "Server FASOP sudah terhubung ke jaringan Zabbix" biasanya
   berarti bisa ping/traceroute — belum tentu port HTTP/HTTPS Zabbix
   frontend (biasanya 80/443, kadang custom) dibuka untuk IP FASOP secara
   spesifik. Uji dengan `curl` di atas (bukan `ping`), atau `nc -zv <host>
   <port>` untuk cek port saja.
3. **Token/kredensial salah atau kedaluwarsa.** Zabbix API akan balas JSON
   error yang jelas (`"error":{"message":"...", "data":"..."}"`) — baca
   `data`-nya, sync_zabbix meneruskan pesan itu apa adanya ke stderr/log.
4. **HTTPS dengan sertifikat self-signed / internal CA.** `requests` (dipakai
   `device_mon/zabbix_api.py`) akan menolak sertifikat yang tidak dipercaya
   default Python — kalau `ZABBIX_API_URL` pakai `https://` dan sertifikatnya
   bukan dari CA publik, curl manual di atas juga akan gagal dengan error SSL
   yang sama. Solusi: pasang CA internal ke trust store OS server FASOP
   (bukan menonaktifkan verifikasi TLS).
5. **`ZABBIX_HOST_GROUPS` menyaring semua host.** Kalau diisi, nama harus
   PERSIS sama (case-sensitive) dengan nama Host Group di Zabbix
   (**Data collection → Host groups**). Salah ketik = hasil kosong tanpa
   error. Kosongkan dulu untuk isolasi masalah, isi lagi setelah koneksi
   dasar terbukti jalan.
6. **User API tidak punya akses ke host group manapun.** Role "Read only"
   saja tidak cukup kalau user itu tidak di-assign ke Host Group yang
   relevan (**Users → Users → [user] → Permissions**) — hasilnya
   `host.get` sukses tapi mengembalikan list kosong, bukan error.

Setelah `curl` manual di poin 1 berhasil, `sync_zabbix --dry-run` hampir
pasti akan berhasil juga — kalau masih gagal di titik ini, errornya
biasanya di token/permission (poin 3/6), bukan jaringan lagi.

## 6. Debug cepat (setelah koneksi API/webhook jalan)

- Host tidak muncul sama sekali → jalankan `python manage.py sync_zabbix
  --dry-run` dan baca error-nya (lihat §5).
- Host muncul tapi status basi (`last_synced_at` lama) → cron `sync_zabbix`
  tidak jalan atau error — cek `/var/log/fasop/sync_zabbix.log`.
- Webhook tidak pernah masuk → cek **Log Webhook Zabbix** di admin
  (kosong sama sekali = Action di Zabbix belum ke-trigger atau URL salah;
  ada baris tapi `ok=False` = baca kolom Keterangan, biasanya token salah
  atau payload tidak sesuai kontrak §3).
