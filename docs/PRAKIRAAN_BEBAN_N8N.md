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
- **Desimal boleh pakai koma** (`1010,5`) — server menormalkannya.
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

Cara cepat: **impor `docs/n8n_prakiraan_beban.workflow.json`** (n8n → Workflows →
`⋯` → *Import from File*), lalu isi 4 hal yang ditandai `GANTI_...`. Rinciannya
di bawah.

### 3.1 Credential yang harus dibuat lebih dulu

| Credential | Tipe di n8n | Isi |
|---|---|---|
| **FASOP API Key** | *Header Auth* | Name: `X-API-Key` · Value: nilai `API_KEY` dari `.env` FASOP |
| **Google Sheets FASOP** | *Google Sheets OAuth2 API* (atau *Service Account*) | Ikuti wizard n8n. Kalau pakai Service Account, **share spreadsheet-nya ke alamat email service account itu** (akses *Viewer* sudah cukup) |

API key jangan diketik langsung di field node — pakai credential Header Auth
supaya tidak tersimpan sebagai teks biasa di workflow dan tidak ikut terbawa
saat workflow diekspor.

### 3.2 Yang perlu diisi di tiap node

| Node | Field | Nilai |
|---|---|---|
| **Tiap 15 Menit** (Schedule Trigger) | Minutes Interval | `15` — kurva jarang berubah; 60 juga aman |
| **Baca Sheet Prakiraan** (Google Sheets) | Credential | *Google Sheets FASOP* |
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
- Menerima tanggal `YYYY-MM-DD`, `DD/MM/YYYY`, atau objek Date dari Sheets.
- **Menyaring hanya baris H dan H+1.** Ini disengaja: kurva hari lampau tidak
  boleh tertimpa, lihat [bagian 5](#5-akurasi).
- Melewati sel MW kosong dan baris judul, lalu **melempar error kalau tidak ada
  satu baris pun yang terbaca** — jadi salah nama kolom langsung kelihatan di
  eksekusi n8n, bukan diam-diam mengirim payload kosong.

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
