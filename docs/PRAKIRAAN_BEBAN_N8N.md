# Prakiraan Beban OPSIS — Dashboard ROH Sulbagsel → n8n → FASOP

Sumber angka prediksi di chart **Beban Kit — Hari Ini** dan halaman **Analitik
Prediksi Beban** sekarang adalah kurva prakiraan dari **Dashboard ROH Sulbagsel**
(Rencana Operasi Harian) yang dipublikasikan sebagai spreadsheet, bukan model
machine learning. Keterangan sumber ini juga ditampilkan di bawah chart supaya
pembaca dashboard tahu angka prediksinya bukan hitungan FASOP sendiri.

Dokumen ini menjelaskan bentuk spreadsheet yang diharapkan dan cara memasang
workflow n8n-nya.

Model ML-nya **tidak dihapus** — lihat [Kembali ke ML](#kembali-ke-ml) di bawah.

---

## 1. Bentuk spreadsheet

Node Code mengenali **dua layout** dan memilih otomatis — tidak perlu diatur.

### Layout MELEBAR (yang dipakai Dashboard ROH Sulbagsel)

Jam jadi **kolom**, satu baris per tanggal. Kolom pertama berisi tanggal
(header-nya boleh kosong):

|            | 0 | 0.3 | 1 | 1.3 | … | 12 | … | 18.3 | … | 23.3 |
|---|---|---|---|---|---|---|---|---|---|---|
| 18-Aug-26 | 1,593.51 | 1,546.94 | 1,511.32 | 1,492.82 | … | 1,669.59 | … | 1,710.80 | … | 1,742.50 |
| 19-Aug-26 | … | | | | | | | | | |

- Header jam boleh `0` / `0.3` (notasi jam.menit), `0.5` (setengah jam), atau
  `00:30`. Ketiganya menunjuk slot yang sama.
- Baris yang kolom tanggalnya bukan tanggal (mis. `RATA-RATA`, `MAX`) otomatis
  dilewati.
- Sheet boleh memuat sebulan penuh — hanya baris H dan H+1 yang dikirim.

### Layout MEMANJANG

Satu baris per titik waktu, grid 30 menit, 48 baris untuk satu hari:

| Tanggal | Jam | MW |
|---|---|---|
| 2026-08-19 | 00:00 | 812.5 |
| 2026-08-19 | 00:30 | 805.1 |
| … | … | … |
| 2026-08-19 | 12:00 | 1024.0 |
| … | … | … |
| 2026-08-19 | 18:30 | 1187.3 |
| … | … | … |
| 2026-08-19 | 23:30 | 890.0 |

Ketentuan:

- **Angkanya total sistem** (agregat semua pembangkit), satuan MW — sama dengan
  seri realisasi yang dipakai chart.
- **Kolom Jam** boleh `HH:MM` atau `HH:MM:SS`; boleh juga diganti kolom `menit`
  berisi menit sejak 00:00 (`0`, `30`, …, `1410`).
- **Dua konvensi angka diterima**: `1,593.51` (koma ribuan, ala Inggris — ini
  yang dipakai sheet ROH) maupun `1.593,51` / `1593,51` (koma desimal, ala
  Indonesia). Node Code membaca pemisah **terakhir** sebagai desimal, lalu
  mengirim angka murni ke FASOP.
- **Sel MW kosong dilewati diam-diam**, tidak dianggap error. Jadi sheet H+1
  yang baru terisi separuh tetap aman dikirim.
- **12:00 dan 18:30 wajib ada** kalau angka puncak siang/malam mau muncul di
  dashboard — keduanya kebetulan tepat di grid 30 menit.
- Kolom lain di spreadsheet diabaikan; kirim saja tiga kolom di atas.

## 2. Endpoint FASOP

```
POST https://<host-fasop>/api/v1/prakiraan-beban/
Header: X-API-Key: <API_KEY dari .env>
Content-Type: application/json
```

Body:

```json
{
  "tanggal": "2026-08-19",
  "sumber": "spreadsheet",
  "replace": false,
  "data": [
    {"jam": "00:00", "mw": 812.5},
    {"jam": "00:30", "mw": 805.1},
    {"jam": "12:00", "mw": 1024.0}
  ]
}
```

- `tanggal` opsional (default hari ini, zona server). Setiap baris boleh
  membawa `"tanggal"` sendiri — pakai ini untuk mengirim hari ini + besok
  dalam satu panggilan.
- **Idempoten**: upsert per `(tanggal, menit)`, jadi workflow aman jalan tiap
  15 menit sekalipun.
- `replace: true` menghapus titik lain pada tanggal yang dikirim yang tidak ada
  di payload. Dipakai kalau sheet baru dirapikan dan ada slot yang memang harus
  hilang. **Default `false`** supaya kiriman parsial tidak diam-diam
  mengosongkan kurva.

Respons:

```json
{
  "status": "ok",
  "tanggal": "2026-08-19",
  "tanggal_tertulis": ["2026-08-19"],
  "titik_ditulis": 48,
  "titik_dihapus": 0,
  "dilewati": 0,
  "errors": []
}
```

Baca balik untuk verifikasi:

```bash
curl -H "X-API-Key: $API_KEY" "https://<host-fasop>/api/v1/prakiraan-beban/?tanggal=2026-08-19"
```

## 3. Workflow n8n

Ada **dua varian**, pilih sesuai bentuk file di Google Drive:

| File di Drive | Workflow yang dipakai | Node pembaca |
|---|---|---|
| **.xlsx hasil upload** (dibuka lewat Sheets dalam *Office editing mode*) | `docs/n8n_prakiraan_beban_xlsx.workflow.json` | Google Drive (Download) → Extract From File |
| **Dokumen Google Sheets asli** (dikonversi/dibuat di Sheets) | `docs/n8n_prakiraan_beban.workflow.json` | Google Sheets (Get Rows) |

> **Salah pilih = error.** Node Google Sheets pada file .xlsx akan gagal dengan
> `Bad request — This operation is not supported for this document. The document
> must not be an Office file.` Lihat [bagian 6](#6-masalah-yang-sering-muncul).

Impor lewat n8n → Workflows → `⋯` → *Import from File*, lalu isi bagian yang
ditandai `GANTI_...`. Rinciannya di bawah.

Node **Rakit Payload** dan **Kirim ke FASOP** identik di kedua varian — yang
berbeda hanya cara membaca file.

### 3.1 Credential yang harus dibuat lebih dulu

| Credential | Tipe di n8n | Isi |
|---|---|---|
| **FASOP API Key** | *Header Auth* | Name: `X-API-Key` · Value: nilai `API_KEY` dari `.env` FASOP |
| **Google Drive FASOP** (varian .xlsx) | *Google Drive OAuth2 API* (atau *Service Account*) | Ikuti wizard n8n. Kalau pakai Service Account, **share file/foldernya ke alamat email service account itu** (akses *Viewer* sudah cukup) |
| **Google Sheets FASOP** (varian Sheets asli) | *Google Sheets OAuth2 API* (atau *Service Account*) | Sama seperti di atas, di-share ke akun/service account yang dipakai |

API key jangan diketik langsung di field node — pakai credential Header Auth
supaya tidak tersimpan sebagai teks biasa di workflow dan tidak ikut terbawa
saat workflow diekspor.

### 3.2 Yang perlu diisi di tiap node

| Node | Field | Nilai |
|---|---|---|
| **Tiap 15 Menit** (Schedule Trigger) | Minutes Interval | `15` — kurva jarang berubah; 60 juga aman |
| **Unduh .xlsx dari Drive** (Google Drive) — *varian .xlsx* | Credential | *Google Drive FASOP* |
| | File | *By URL* → tautan file .xlsx di Drive (`GANTI_DENGAN_URL_FILE_XLSX_DI_DRIVE`) |
| | Operation | `Download` |
| **Parse Excel** (Extract From File) — *varian .xlsx* | Operation | `Extract From XLSX` (pilih `Extract From XLS` kalau formatnya lama) |
| | Input Binary Field | `data` — harus sama dengan *Put Output File in Field* di node Drive |
| | Options → Sheet Name | Isi kalau tab prakiraan **bukan tab pertama**; kalau kosong, hanya sheet pertama yang dibaca |
| **Baca Sheet Prakiraan** (Google Sheets) — *varian Sheets asli* | Credential | *Google Sheets FASOP* |
| | Document | URL/ID spreadsheet prakiraan (`GANTI_DENGAN_URL_SPREADSHEET`) |
| | Sheet | Nama tab, default `Prakiraan` |
| | Operation | `Get Row(s)` — biarkan *Return All* aktif |
| **Rakit Payload** (Code) | — | Tidak perlu diubah kalau header sheet `Tanggal` / `Jam` / `MW` |
| **Kirim ke FASOP** (HTTP Request) | URL | `https://fasopup2bmks.id/api/v1/prakiraan-beban/` |
| | Authentication | Generic Credential Type → Header Auth → *FASOP API Key* |
| | Body Content Type | `JSON`, *Specify Body*: `Using JSON` |
| | Retry On Fail | aktif, 3x — endpoint idempoten, retry tidak menggandakan data |

### 3.3 Yang dilakukan node Code

- Mencocokkan kolom **tanpa peduli besar-kecil huruf atau spasi** (`Tanggal`/`Date`,
  `Jam`/`Waktu`/`Time`, `MW`/`Beban`, `Menit`).
- **Mendeteksi layout sendiri** (melebar vs memanjang) dari jumlah kolom yang
  berlabel jam, lalu melaporkannya di field `_layout` — berguna saat menebak
  kenapa hasilnya kosong.
- Menerima **berbagai bentuk sel** sekaligus, karena Sheets mengirim teks
  sedangkan Excel menyimpan tanggal & jam sebagai angka:

  | Kolom | Bentuk yang diterima |
  |---|---|
  | Tanggal | `2026-08-19`, `19/08/2026`, `18-Aug-26`, objek Date, serial Excel (`46253`) |
  | Header jam (melebar) | `0`, `0.3`, `0.5`, `18.3`, `18:30` |
  | Kolom Jam (memanjang) | `18:30`, `18:30:00`, objek Date, sel numerik .xlsx (pecahan hari: `0.5` = 12:00) |
  | Menit | angka `0`–`1439` (alternatif kolom Jam) |
  | MW | `1,593.51`, `1.593,51`, `1593,51`, `1593.51`, angka |

  Perhatikan bedanya `0.5`: sebagai **header kolom** artinya 00:30, sebagai
  **sel jam numerik di .xlsx** artinya 12:00 (pecahan hari). Keduanya ditangani
  terpisah, jangan disamakan kalau nanti kode ini diubah.

  Jam dinormalkan jadi `menit` dan MW jadi angka murni di sisi n8n, jadi FASOP
  menerima nilai yang sudah pasti — bukan tebakan format.
- **Menyaring hanya baris H dan H+1.** Ini disengaja: kurva hari lampau tidak
  boleh tertimpa, lihat [bagian 5](#5-akurasi).
- Melewati sel MW kosong dan baris judul, lalu **melempar error kalau tidak ada
  satu baris pun yang terbaca** — jadi salah nama kolom langsung kelihatan di
  eksekusi n8n, bukan diam-diam mengirim payload kosong. Pesan errornya ikut
  menyebutkan contoh nilai Jam yang gagal dibaca.
- Melaporkan `_layout`, `_dilewati` (baris di luar H/H+1), `_jam_tak_terbaca`,
  dan `_mw_rusak` di output, supaya baris bermasalah bisa dihitung tanpa
  membuka sheet. Pesan errornya menyebut layout yang terdeteksi, tanggal yang
  dicari, dan contoh tanggal/label jam yang ditemukan — biasanya itu langsung
  menunjukkan penyebabnya.

Kalau sheet Anda hanya berisi satu hari dan tanggalnya ada di judul (bukan kolom
per baris), baris tanpa kolom `Tanggal` otomatis memakai default server (hari
ini) — tidak perlu mengubah kode.

### 3.4 Uji sebelum diaktifkan

1. Klik **Execute Workflow** sekali. Node Code harus menghasilkan 48-96 item di
   `data`; node HTTP Request harus balas `{"status":"ok","titik_ditulis":...}`.
2. Cocokkan dengan FASOP:
   ```bash
   curl -H "X-API-Key: $API_KEY" "https://fasopup2bmks.id/api/v1/prakiraan-beban/?tanggal=$(date +%F)"
   ```
3. Buka dashboard OPSIS — garis putus-putus "Prediksi" harus muncul sehari penuh.
4. Baru aktifkan toggle **Active** di workflow.

Kalau `titik_ditulis` jauh lebih kecil dari jumlah baris sheet, periksa
`dilewati` dan `errors` di respons — keduanya menyebutkan nomor baris dan
alasannya.

## 4. Kalau n8n mati

Kurva bisa ditambal manual lewat Django Admin:
`/secure-panel/` → **Opsis → Prakiraan Beban**. Ini untuk memperbaiki satu-dua
titik, bukan jalur input harian.

Kalau kurva hari ini kosong sama sekali, dashboard tetap normal — seri prediksi
hanya tidak digambar (`source: "no_sheet"`), realisasi tetap jalan seperti biasa.

## 5. Akurasi

Halaman **Analitik Prediksi Beban** membandingkan setiap titik kurva prakiraan
7 hari terakhir dengan realisasi SnapLive pada jam yang sama, lalu melaporkan
MAE / RMSE / MAPE / akurasi. Karena baris prakiraan hari-hari lampau tidak
pernah dihapus, angka ini mencerminkan prakiraan yang benar-benar dipakai saat
itu — bukan hasil hitung ulang.

Konsekuensinya: **jangan menimpa kurva hari yang sudah lewat** dengan angka
realisasi. Kalau spreadsheet dispatcher biasanya di-update belakangan supaya
"cocok" dengan realisasi, kirim hanya baris H dan H+1 dari n8n (filter di node
Code), bukan seluruh sheet.

## 6. Masalah yang sering muncul

### `This operation is not supported for this document. The document must not be an Office file.`

Node **Google Sheets** ditujukan ke file **.xlsx**, bukan dokumen Google Sheets
asli. File Excel yang di-upload ke Drive tetap berformat Office walaupun bisa
dibuka lewat Sheets (*Office editing mode*) — Sheets API menolak semua operasi
di atasnya.

Dua jalan keluar:

**A. Tetap pakai .xlsx** (cocok kalau file-nya rutin ditimpa dari Dashboard ROH) —
pakai `docs/n8n_prakiraan_beban_xlsx.workflow.json`, yang membaca lewat Google
Drive (Download) + Extract From File. Tidak ada yang perlu diubah di kebiasaan
kerja operator.

Satu syarat: **File ID di Drive harus tetap sama.** Saat meng-upload versi baru,
pilih *Replace existing file* / **Manage versions → Upload new version** pada file
yang sudah ada — jangan upload sebagai file baru, karena node Drive menunjuk satu
File ID tertentu dan akan terus membaca file lama.

**B. Konversi jadi Google Sheets asli** (cocok kalau nanti diisi langsung di
Sheets) — buka file di Drive → **File → Save as Google Sheets**. Dokumen baru
akan muncul dengan ID berbeda; pakai ID itu di
`docs/n8n_prakiraan_beban.workflow.json`. Perlu diingat: hasil konversi adalah
**salinan**, tidak ikut berubah kalau .xlsx aslinya di-upload ulang.

### `Google Drive API has not been used in project <nomor> before or it is disabled`

Project Google Cloud di balik credential n8n baru mengaktifkan **Sheets API**,
belum **Drive API**. Buka link yang disebut di pesan error itu (berisi nomor
project-nya) → klik **Enable** → tunggu 1–5 menit → jalankan ulang workflow.
Gratis, tidak perlu billing.

Perlu akses Owner/Editor di project tersebut. Kalau tidak punya, minta ke
pemilik project atau buat OAuth credential baru di project sendiri dengan Drive
API aktif sejak awal.

Kalau setelah itu muncul error scope/`insufficient permissions`: credential
Drive di n8n harus **Sign in with Google** ulang — token lama dibuat untuk
Sheets dan tidak membawa izin Drive, dan izin itu hanya diberikan saat sign-in.

### "Bisa nggak bikin Sheets baru yang menarik data .xlsx pakai IMPORTRANGE?"

Tidak bisa. Google memblokir IMPORTRANGE dengan sumber file Office — hasilnya
`#REF!` dengan pesan *"Cannot use IMPORTRANGE in Office files"*. Sumber
IMPORTRANGE harus dokumen Google Sheets asli.

Kalau tetap ingin ada Sheets asli di tengah, satu-satunya yang benar-benar
otomatis adalah mengonversi ulang tiap kali file baru masuk — komponennya jauh
lebih banyak daripada sekadar membaca .xlsx-nya langsung. Konversi manual
(*File → Save as Google Sheets*) menghasilkan **salinan**: isinya beku, tidak
ikut berubah saat .xlsx aslinya di-upload ulang.

Jadi untuk alur "unduh dari Dashboard ROH → upload ke Drive", varian
`n8n_prakiraan_beban_xlsx.workflow.json` memang jalur yang paling pendek.

### Apakah file .xlsx-nya perlu diunduh dulu secara manual?

Tidak. Node **Unduh .xlsx dari Drive** menarik isi file ke memori n8n saat
workflow berjalan, lalu **Parse Excel** membacanya dari situ juga. Tidak ada
file yang tersimpan di disk mana pun, dan tidak ada langkah manual — cukup
pastikan file .xlsx-nya ada di Drive dan File ID-nya tidak berubah.

### Jam tergeser (mis. semua maju/mundur beberapa jam)

Terjadi kalau kolom Jam di Excel bertipe *waktu* dan zona waktunya ikut
tergeser. Node Code sudah menangani sel waktu-saja lewat getter UTC, tapi kalau
masih meleset, cara paling pasti: **format kolom Jam sebagai Teks** di Excel
(`00:00`, `00:30`, …), atau ganti dengan kolom **Menit** berisi angka
`0, 30, 60, …`.

### `titik_ditulis` jauh lebih kecil dari jumlah baris sheet

Periksa `dilewati` dan `errors` di respons — keduanya menyebut nomor baris dan
alasannya. Penyebab tersering: baris di luar H/H+1 (memang sengaja disaring),
sel MW kosong, atau nama kolom tidak dikenali.

### Node Code melempar "Tidak ada baris prakiraan H/H+1 yang terbaca"

Sheet terbaca tapi tidak ada baris yang lolos. Pesan errornya menyebutkan
layout yang terdeteksi, tanggal yang dicari, dan contoh tanggal/label jam yang
ditemukan — mulai dari situ:

- **`layout terdeteksi: MEMANJANG` padahal sheet-nya melebar** — header jamnya
  tidak dikenali. Deteksi butuh minimal 6 kolom berlabel jam (`0`, `0.3`, …).
  Sering terjadi kalau baris header bukan baris pertama sheet, sehingga yang
  terbaca sebagai header adalah baris judul.
- **`Tanggal lain yang ditemukan: …`** — sheet-nya terbaca, hanya belum berisi
  tanggal hari ini/besok.
- **Tab yang terbaca salah** — Extract From File hanya membaca sheet pertama
  kalau *Options → Sheet Name* dikosongkan.

## Kembali ke ML

Kode ML (`opsis/forecast.py`, command `train_beban_forecast`, `scikit-learn` di
`requirements.txt`) tetap ada dan tidak diubah. Untuk mengaktifkannya lagi:

1. Set di `.env`:
   ```env
   OPSIS_FORECAST_SOURCE=ml
   ```
2. Hidupkan lagi cron training harian:
   ```
   15 0 * * * cd /path/to/fasop && python manage.py train_beban_forecast >> /var/log/fasop/train_beban_forecast.log 2>&1
   ```
3. Restart gunicorn.

Selama `OPSIS_FORECAST_SOURCE=sheet` (default), modul ML tidak di-import sama
sekali, dan cron `train_beban_forecast` boleh dimatikan.
