# API Eksternal FASOP — Panduan Konsumen

Endpoint **baca** yang dibuka FASOP untuk aplikasi pihak lain (UP2D dsb.).
Semuanya `GET`, membalas JSON, dan dikunci satu header.

Base URL: `https://<domain-fasop>/api/v1/`

---

## 1. Kunci akses

Setiap permintaan wajib membawa header:

```
X-API-Key: <kunci-anda>
```

Kuncinya diterbitkan admin FASOP dari **Admin → Devices → Kunci API**, satu
kunci per konsumen. Perlakukan seperti password:

- **Jangan** ditulis di dalam kode yang dibagikan atau di sel spreadsheet.
  Di Google Apps Script, simpan di **Project Settings → Script Properties**.
- Kalau bocor atau berpindah tangan, minta admin FASOP membuat ulang kuncinya —
  kunci lama langsung berhenti berlaku, konsumen lain tidak terganggu.
- Kunci ini **hanya bisa membaca**. Ia tidak bisa mengubah apa pun di FASOP.

Balasan penolakan:

| Kode | Arti |
|---|---|
| `401` | Header `X-API-Key` tidak dikirim |
| `403` | Kunci tidak dikenal atau sudah dicabut |
| `405` | Metode selain `GET` |
| `503` | Data sedang tidak tersedia (historian SCADA tidak terjangkau) |

---

## 2. `GET /api/v1/opsis/beban-ktt/`

Beban konsumen tegangan tinggi (KTT) terkini — angka yang sama persis dengan
halaman **OPSIS → Beban KTT** di FASOP.

### Contoh balasan berhasil (`200`)

```json
{
  "status": "ok",
  "waktu": "2026-09-07T14:32:10+08:00",
  "sumber": "OPSIS — IND_LOAD (historian SCADA)",
  "satuan": "MW",
  "terputus": false,
  "total_mw": 103.75,
  "jumlah": 3,
  "konsumen": [
    { "kode": "IND_ANTAM",  "nama": "ANTAM",   "mw": 61.25 },
    { "kode": "IND_HUADI2", "nama": "HUADI 2", "mw": 30.5 },
    { "kode": "IND_BARU",   "nama": "IND_BARU", "mw": 12.0 }
  ]
}
```

| Field | Arti |
|---|---|
| `waktu` | Waktu FASOP membaca nilainya (WITA), **bukan** timestamp di historian |
| `total_mw` | Total sistem dari baris `IND_TOTAL`; kalau baris itu tidak ada, dijumlahkan dari konsumen |
| `jumlah` | Banyaknya konsumen (baris total tidak ikut dihitung) |
| `konsumen[].kode` | Kode di historian — **pakai ini sebagai kunci**, bukan `nama` |
| `konsumen[].nama` | Nama yang dikenal orang; konsumen yang belum dipetakan memakai kodenya sendiri |
| `konsumen[].mw` | Beban dalam MW, bisa `null` bila titiknya tidak terbaca |

### Kalau data tidak tersedia (`503`)

```json
{
  "status": "error",
  "message": "Data beban KTT sedang tidak tersedia (historian SCADA tidak terjangkau).",
  "terputus": true
}
```

⚠️ **Perlakukan `503` sebagai "lewati putaran ini", bukan sebagai 0 MW.**
FASOP sengaja tidak pernah mengirim `total_mw: 0` saat historian mati, justru
supaya angka nol palsu tidak masuk ke laporan Anda. Kalau aplikasi Anda mengisi
0 sendiri saat gagal, jaminan itu hilang.

---

## 3. Seberapa sering boleh ditarik

Angkanya diperbarui di sisi FASOP setiap beberapa detik. **Tarik paling cepat
sekali per menit** — lebih sering dari itu tidak menambah informasi, hanya
menambah beban ke historian SCADA yang dipakai bersama ruang kontrol.

Kalau butuh yang lebih cepat dari itu, bicarakan dulu dengan tim FASOP.

---

## 4. Contoh — Google Apps Script

```javascript
const FASOP_URL = 'https://<domain-fasop>/api/v1/opsis/beban-ktt/';

function ambilBebanKtt() {
  // Kunci disimpan di Project Settings > Script Properties, BUKAN di kode ini.
  const kunci = PropertiesService.getScriptProperties().getProperty('FASOP_API_KEY');

  const resp = UrlFetchApp.fetch(FASOP_URL, {
    method: 'get',
    headers: { 'X-API-Key': kunci },
    muteHttpExceptions: true,      // supaya 503 bisa ditangani, bukan melempar
  });

  const kode = resp.getResponseCode();
  if (kode === 503) {
    console.log('Data KTT belum tersedia — lewati putaran ini.');
    return;                        // JANGAN tulis 0 ke sheet
  }
  if (kode !== 200) {
    throw new Error('FASOP menolak: HTTP ' + kode + ' — ' + resp.getContentText());
  }

  const data = JSON.parse(resp.getContentText());
  const sheet = SpreadsheetApp.getActive().getSheetByName('Beban KTT');

  const baris = data.konsumen.map(k => [data.waktu, k.kode, k.nama, k.mw]);
  baris.push([data.waktu, 'TOTAL', 'TOTAL SISTEM', data.total_mw]);
  sheet.getRange(sheet.getLastRow() + 1, 1, baris.length, 4).setValues(baris);
}
```

Pasang trigger **Time-driven → Minutes timer → Every minute** (atau lebih
jarang) di menu Triggers.

### Kalau sebelumnya menarik data dengan login akun FASOP

Cara lama — `UrlFetchApp` yang login ke `/login/` lalu membawa cookie sesi —
sebaiknya dihentikan setelah beralih ke kunci API:

- Password akun FASOP tidak perlu lagi tersimpan di Apps Script.
- Tiap eksekusi tidak lagi membuat sesi login baru yang menumpuk di server.
- Akses Anda tidak ikut terputus saat password akun itu diganti.

---

## 5. Kalau ada masalah

Sebutkan ke tim FASOP: **nama konsumen di kunci Anda**, jam kejadian, dan kode
HTTP yang diterima. Pemakaian tiap kunci (kapan terakhir dipakai, dari IP mana)
terlihat di Admin FASOP, jadi keluhan bisa ditelusuri tanpa menebak.
