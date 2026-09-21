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

### Izin per jenis data

Satu kunci **tidak otomatis membuka semua data**. Tiap kunci diberi izin per
jenis data (Beban KTT, Beban pembangkit, Beban trafo, Frekuensi sistem,
Logsheet pembebanan), dan admin FASOP juga bisa menutup satu jenis data sekaligus untuk
semua konsumen. Jadi data yang belum Anda minta akan dibalas `403`, dan
penambahan data baru di FASOP tidak diam-diam ikut terkirim ke Anda.

Kalau butuh jenis data tambahan, mintakan izinnya — kuncinya tidak perlu
diganti.

Balasan penolakan:

| Kode | Arti | Tindakan |
|---|---|---|
| `401` | Header `X-API-Key` tidak dikirim | periksa cara mengirim header |
| `403` | Kunci tidak dikenal atau sudah dicabut | minta kunci baru ke admin FASOP |
| `403` | Kunci ini tidak diizinkan membaca data tsb. | minta izinnya ditambahkan |
| `403` | Data sedang ditutup untuk akses luar | tanyakan ke tim FASOP |
| `404` | Penyaring tidak cocok dengan apa pun (mis. kode pembangkit salah) | perbaiki parameternya |
| `400` | Parameter salah format atau rentang terlalu lebar | lihat pesannya |
| `405` | Metode selain `GET` | |
| `503` | Data sedang tidak tersedia (historian SCADA tidak terjangkau) | lewati putaran ini |

Ketiga `403` di atas membawa pesan yang berbeda di field `message` — bacalah
pesannya, itu yang membedakan "kunci saya salah" dari "izin saya kurang".

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

## 3. `GET /api/v1/opsis/beban-pembangkit/`

MW/MVAR terkini tiap pembangkit aktif, beserta rincian per unit.

Parameter: `?unit=0` menghilangkan rincian unit (balasan jauh lebih kecil bila
yang dibutuhkan hanya total per pembangkit).

```json
{
  "status": "ok",
  "waktu": "2026-09-21T14:32:10+08:00",
  "satuan": { "mw": "MW", "mvar": "MVAR", "frekuensi": "Hz" },
  "frekuensi_sistem": 50.01,
  "total_mw": 1284.6,
  "jumlah": 23,
  "pembangkit": [
    {
      "kode": "BAKARU", "nama": "PLTA Bakaru", "jenis": "PLTA",
      "mw": 61.2, "mvar": 12.5,
      "diragukan": false, "keterangan": "",
      "unit": [ { "nama": "UNIT1", "mw": 30.6, "mvar": 6.25 } ]
    }
  ]
}
```

| Field | Arti |
|---|---|
| `kode` | **pakai ini sebagai kunci**, bukan `nama` |
| `mw` / `mvar` | total semua unit; `null` bila titiknya tidak terbaca |
| `diragukan` | operator OPSIS menandai angka pembangkit ini tidak sesuai kenyataan |
| `keterangan` | alasan penandaan itu |

⚠️ **`diragukan: true` berarti jangan dipakai untuk laporan tanpa dicek.**
Ruang kontrol FASOP sendiri sedang meragukan angka itu. Ia tetap dikirim
supaya Anda bisa memutuskan, bukan supaya diabaikan.

Historian mati → `503`, bukan daftar berisi nol.

---

## 4. `GET /api/v1/opsis/beban-pembangkit/riwayat/`

Riwayat MW/MVAR **per menit** dari snapshot PostgreSQL FASOP.

| Parameter | Bawaan | Catatan |
|---|---|---|
| `dari`, `sampai` | 60 menit terakhir | waktu ISO, mis. `2026-09-21T08:00` |
| `kode` | semua pembangkit aktif | dipisah koma, mis. `BAKARU,BARRU` |

Rentang maksimum **3 hari** sekali permintaan.

```json
{
  "status": "ok",
  "dari": "2026-09-21T13:32:10+08:00",
  "sampai": "2026-09-21T14:32:10+08:00",
  "sumber": "opsis.SnapLive (snapshot PostgreSQL, 1 titik per menit)",
  "jumlah": 1380,
  "pembangkit": [
    {
      "kode": "BAKARU", "nama": "PLTA Bakaru", "jenis": "PLTA", "jumlah": 60,
      "deret": [ { "waktu": "2026-09-21T13:33:00+08:00", "mw": 61.2, "mvar": 12.5, "hz": 50.01 } ]
    }
  ]
}
```

Endpoint ini **tetap menjawab saat historian SCADA mati** — sumbernya
PostgreSQL. Imbalannya, nilai paling baru bisa tertinggal sampai satu menit;
yang butuh angka detik ini memakai endpoint terkini di atas.

---

## 5. `GET /api/v1/opsis/beban-trafo/`

Daya terkini tiap trafo, dikelompokkan per GI.

| Parameter | Bawaan | Catatan |
|---|---|---|
| `jenis` | `distribusi` | `distribusi` (BAY TRF52/TRF42) atau `ibt` (BAY TRF65/TRF54) |

```json
{
  "status": "ok",
  "jenis": "distribusi",
  "waktu": "2026-09-21T14:32:10+08:00",
  "sumber": "OPSIS — ALL_TRANS_DATA (historian SCADA)",
  "satuan": { "p": "MW", "q": "MVAR", "v": "kV", "i": "A" },
  "total_mw": 25.0,
  "jumlah": 2,
  "gi": [
    {
      "site": "GI SUNGGUMINASA",
      "total_mw": 25.0,
      "trafo": [
        { "bay": "TRF52-1", "p": 20.0, "q": 3.0, "v": 20.1, "i": 600.0 },
        { "bay": "TRF52-2", "p": -5.0, "q": 1.0, "v": 20.0, "i": 150.0 }
      ]
    }
  ]
}
```

**`p` bisa negatif, dan tandanya bermakna** — arah aliran daya lewat trafo (dua
arah, terutama pada IBT). Jangan membuang tandanya saat menyalin per-trafo.

**`total_mw` dan `total_mw` per GI memakai magnitudo** (`abs`), menyamai kartu
total di layar OPSIS. Pada contoh di atas 20 dan −5 menjadi **25**, bukan 15:
dijumlahkan bertanda, dua trafo berlawanan arah saling meniadakan dan GI yang
sibuk akan terlihat nyaris tanpa beban.

`jenis` yang tidak dikenal dibalas `400`, **tidak** diam-diam jatuh ke
`distribusi` — supaya salah ketik tidak membuat Anda mencatat angka distribusi
sebagai angka IBT.

Trafo yang dinonaktifkan di FASOP tidak ikut. Kalau ada GI/bay yang Anda
harapkan tapi tidak muncul, itu yang pertama perlu dicek ke pengelola FASOP.

---

## 6. `GET /api/v1/opsis/beban-trafo/riwayat/`

Riwayat daya aktif (**P saja**) per menit dari snapshot PostgreSQL FASOP.

| Parameter | Bawaan | Catatan |
|---|---|---|
| `jenis` | `distribusi` | sama seperti di atas |
| `dari`, `sampai` | 60 menit terakhir | waktu ISO, mis. `2026-09-21T08:00` |
| `site` | semua GI | dipisah koma, mis. `GI SUNGGUMINASA,GI PANAKKUKANG` |

Rentang maksimum **3 hari** sekali permintaan.

```json
{
  "status": "ok",
  "jenis": "distribusi",
  "dari": "2026-09-21T13:32:10+08:00",
  "sampai": "2026-09-21T14:32:10+08:00",
  "sumber": "opsis.SnapTrafo (snapshot PostgreSQL, 1 titik per menit)",
  "satuan": { "p": "MW" },
  "jumlah": 120,
  "trafo": [
    {
      "site": "GI SUNGGUMINASA", "bay": "TRF52-1", "jumlah": 60,
      "deret": [ { "waktu": "2026-09-21T13:33:00+08:00", "p": 20.0 } ]
    }
  ]
}
```

**Hanya P yang tersedia di riwayat.** Q, V, dan I tidak disimpan ke snapshot,
jadi keduanya cuma ada di endpoint terkini (bagian 5).

Seperti riwayat beban pembangkit, endpoint ini **tetap menjawab saat historian
SCADA mati** — sumbernya PostgreSQL. Imbalannya nilai paling baru bisa
tertinggal sampai satu menit.

---

## 7. `GET /api/v1/opsis/frekuensi/`

Riwayat frekuensi sistem **per detik**.

| Parameter | Bawaan | Catatan |
|---|---|---|
| `dari`, `sampai` | 60 menit terakhir | waktu ISO |

Rentang maksimum **6 jam** sekali permintaan (1 baris/detik → 6 jam ≈ 21.600
titik).

```json
{
  "status": "ok",
  "satuan": "Hz",
  "sumber": "gabungan",
  "sumber_teks": "Historian SCADA (SYS_FREQ_HIS): 3100 detik + Rekaman FASOP (SnapFreqRT, dari SYS_FREQ_RT): 500 detik",
  "sumber_rincian": { "historian": 3100, "snapfreq": 0, "postgres": 500 },
  "jumlah": 3600,
  "deret": [ { "waktu": "2026-09-21T13:33:00+08:00", "hz": 50.01 } ]
}
```

`sumber_rincian` menyebut berapa detik diambil dari masing-masing sumber.
FASOP menggabungkan tiga sumber supaya deretnya tetap terisi saat job penulis
historian SCADA berhenti — pernah terjadi selama ±42 jam. Kalau Anda memakai
deret ini untuk analisis, angka itu memberi tahu bagian mana yang ditambal.

Rentang yang memang sepi dibalas `200` dengan `deret: []`, **bukan** `503` —
"tidak ada data pada jam itu" adalah jawaban yang sah.

---

## 8. `GET /api/v1/logsheet/pembebanan/`

Nilai logsheet pembebanan per **slot 30 menit** untuk satu tanggal: pembangkit,
penghantar, busbar, dan trafo/IBT.

| Parameter | Bawaan | Pilihan |
|---|---|---|
| `tanggal` | hari ini | `YYYY-MM-DD` |
| `kategori` | semua | `kit`, `transmisi`, `busbar`, `trafo` |
| `besaran` | semua | `mw`, `mvar`, `amp`, `volt` |
| `slot` | semua slot terisi | `0`..`47`, atau `latest` |

Slot `0` = 00:30, `47` = 24:00.

```json
{
  "status": "ok",
  "tanggal": "2026-09-21",
  "slot": null,
  "jumlah_titik": 214,
  "jumlah_nilai": 8902,
  "titik": [
    {
      "key": "BAKARU-1:mw", "nama": "BAKARU U1",
      "kategori": "kit", "besaran": "mw", "satuan": "MW",
      "jumlah": 44,
      "nilai": [ { "slot": 0, "waktu": "00:30", "nilai": 30.5 } ]
    }
  ]
}
```

| Field | Arti |
|---|---|
| `key` | **identitas titik — pakai ini sebagai kunci**, nama bisa berubah |
| `jumlah` | banyaknya slot yang sudah terisi pada titik itu |

Titik yang belum ada nilainya tetap muncul dengan `nilai: []` — laporan ini
gunanya menunjukkan **cakupan**, bukan hanya yang terisi. Retensi datanya
bergulir sekitar satu bulan, jadi ambil arsipnya sebelum itu bila diperlukan.

---

## 9. Seberapa sering boleh ditarik

Angkanya diperbarui di sisi FASOP setiap beberapa detik. **Tarik paling cepat
sekali per menit** — lebih sering dari itu tidak menambah informasi, hanya
menambah beban ke historian SCADA yang dipakai bersama ruang kontrol.

Kalau butuh yang lebih cepat dari itu, bicarakan dulu dengan tim FASOP.

---

## 10. Contoh — Google Apps Script

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

## 11. Kalau ada masalah

Sebutkan ke tim FASOP: **nama konsumen di kunci Anda**, jam kejadian, dan kode
HTTP yang diterima. Pemakaian tiap kunci (kapan terakhir dipakai, dari IP mana)
terlihat di Admin FASOP, jadi keluhan bisa ditelusuri tanpa menebak.
