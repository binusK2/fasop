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
Logsheet pembebanan, Inventaris aset, Lokasi, Riwayat pemeliharaan, dst.), dan admin FASOP juga bisa menutup satu jenis data sekaligus untuk
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

## 9. `GET /api/v1/fasop/status-monitor/`

Status terkini RTU dan host Zabbix — isi yang sama dengan halaman Device
Monitor. Tanpa parameter.

```json
{
  "status": "ok",
  "waktu": "2026-09-25T14:30:05+08:00",
  "rtu": {
    "jumlah": 120, "up": 117, "down": 2, "unknown": 1,
    "daftar_down": [
      { "nama": "RTU-TELLO", "lokasi": "GI TELLO",
        "sejak": "2026-09-25T11:02:00+08:00", "durasi_menit": 208 }
    ],
    "daftar_down_terpotong": false
  },
  "zabbix": [
    {
      "kode": "telkom", "nama": "Zabbix Telkom",
      "jumlah_host": 64, "ok": 61, "warning": 2, "problem": 1, "unknown": 0,
      "sinkron_terakhir": "2026-09-25T14:28:00+08:00",
      "host_bermasalah": [
        { "nama": "VoIP Makassar", "lokasi": "GI TELLO", "severity": "High",
          "problem": "Interface down", "sejak": "...", "durasi_menit": 12 }
      ],
      "host_bermasalah_terpotong": false
    }
  ]
}
```

- `daftar_down` diurutkan dari yang **paling lama** DOWN; `host_bermasalah`
  dari severity tertinggi. Masing-masing dirinci paling banyak 50, sisanya
  ditandai `*_terpotong: true` — angka jumlahnya tetap lengkap.
- `problem` = severity **High ke atas**, `warning` = di bawahnya — ambang yang
  sama dengan warna merah/kuning di layar Device Monitor.
- **Perhatikan `sinkron_terakhir`.** Status host hanya sesegar sinkronisasi
  Zabbix terakhir; "0 problem" dari data yang sudah basi sejam tidak sama
  artinya dengan "0 problem" barusan.

---

## 10. `GET /api/v1/fasop/pemeliharaan/`

| Parameter | Bawaan | Pilihan |
|---|---|---|
| `bulan` | bulan berjalan | `YYYY-MM` |

```json
{
  "status": "ok",
  "bulan": "2026-09",
  "open": {
    "jumlah": 7,
    "daftar": [
      { "peralatan": "RTU-01", "jenis": "RTU", "lokasi": "GI TELLO",
        "tipe": "Preventive", "tanggal": "2026-09-05T08:00:00+08:00", "sudah_ttd": false }
    ],
    "terpotong": false
  },
  "rekap_bulan": {
    "preventive": { "open": 3, "done": 41 },
    "corrective": { "open": 1, "done": 6 }
  },
  "jadwal": [
    { "lokasi": "GI TELLO", "minggu": 2, "status": "Sedang Berjalan",
      "jumlah_peralatan": 12, "sudah_dipelihara": 8, "progres_persen": 67 }
  ]
}
```

- `open` adalah keadaan **saat ini** dan tidak ikut parameter `bulan`;
  `rekap_bulan` dan `jadwal` mengikuti `bulan`.
- `progres_persen` dihitung dengan cara yang sama dengan halaman Jadwal:
  peralatan di lokasi itu yang sudah punya pemeliharaan Preventive di bulan
  tersebut.

---

## 11. `GET /api/v1/fasop/peralatan/`

Pencarian peralatan. Wajib mengisi `q` atau `lokasi`.

| Parameter | Arti |
|---|---|
| `q` | kata kunci dipisah spasi, dicari di nama, lokasi, merk, tipe, dan jenis |
| `lokasi` | hanya peralatan yang lokasinya mengandung teks ini |
| `hi` | `0` = lewati perhitungan Health Index (lebih cepat) |

```json
{
  "status": "ok",
  "q": "tello rtu",
  "kata": ["tello", "rtu"],
  "cocok": "semua_kata",
  "jumlah": 3,
  "per_jenis": { "RTU": 3 },
  "per_status": { "Operasi": 3 },
  "terpotong": false,
  "peralatan": [
    { "nama": "RTU-01", "jenis": "RTU", "merk": "SEL", "tipe": "3530",
      "lokasi": "GI TELLO", "status_operasi": "Operasi",
      "tahun_operasi": 2015, "umur_tahun": 11,
      "health_index": 78, "kategori_hi": "Baik" }
  ]
}
```

- Tiap kata harus cocok (`cocok: "semua_kata"`). Kalau hasilnya kosong,
  pencarian diulang dengan kata mana saja yang cocok (`"sebagian_kata"`).
- Paling banyak 20 peralatan dirinci; `jumlah`, `per_jenis`, dan
  `per_status` tetap menghitung seluruh hasil.
- **Tidak berisi** IP address, serial number, maupun spesifikasi teknis.

---

## 12. Menyalin inventaris & riwayat pemeliharaan (Fasop Induk)

Empat endpoint di bawah dibuat untuk aplikasi yang **menyalin seluruh isinya**
ke database sendiri secara berkala (konsumen pertamanya Fasop Induk, dashboard
UIP3B). Bedanya dengan `fasop/peralatan/` dan `fasop/pemeliharaan/` (dibuat
untuk bot WhatsApp):

- **Setiap baris punya `id`** — string hashid yang sama dengan id di URL
  FASOP (mis. `YgAzAD`). Pakai sebagai kunci upsert. Id ini stabil selama
  `SECRET_KEY` server FASOP tidak diganti; kalau diganti, semua id berubah dan
  salinan harus ditarik ulang dari kosong.
- **Semua daftar berhalaman dan diurutkan dari baris tertua** (urut pk), jadi
  menarik halaman 1 sampai `halaman_berikutnya` bernilai `null` selalu
  menghasilkan seluruh data.
- **Izin datanya terpisah**: `aset`, `lokasi`, `riwayat_pemeliharaan`. Kunci
  yang memegang izin `peralatan`/`pemeliharaan` (bot) tidak otomatis bisa
  membacanya.

### Halaman

| Parameter | Bawaan | Batas |
|---|---|---|
| `halaman` | `1` | mulai dari 1 |
| `per_halaman` | `100` | maks `200` — lebih dari itu **ditolak** `400`, bukan dipotong |

Setiap balasan berhalaman membawa:

```json
{ "halaman": 1, "per_halaman": 100, "jumlah": 1834,
  "jumlah_halaman": 19, "halaman_berikutnya": 2 }
```

Halaman yang melewati ujung dibalas `200` dengan daftar kosong, bukan `404`.

### Cara menyalin yang disarankan

FASOP **belum punya penanda "diubah sejak"** di data aset maupun pemeliharaan,
jadi salinan dilakukan **penuh**: tarik semua halaman, upsert per `id`, lalu
hapus di sisi Anda baris yang **tidak muncul lagi** — itulah satu-satunya cara
penghapusan (soft-delete di FASOP) sampai ke salinan. Lakukan penghapusan hanya
kalau semua halaman berhasil ditarik dan jumlahnya sama dengan `jumlah`; kalau
satu halaman gagal, lewati penghapusan putaran itu.

Peralatan yang dihapus di FASOP tidak muncul, dan pemeliharaan miliknya juga
tidak — setiap pemeliharaan selalu menunjuk aset yang ada di `fasop/aset/`.

---

## 13. `GET /api/v1/fasop/aset/` dan `/api/v1/fasop/aset/<id>/`

Izin data: **`aset`**.

| Parameter | Arti |
|---|---|
| `halaman`, `per_halaman` | lihat bagian 12 |
| `lokasi` | nama lokasi persis (huruf besar/kecil bebas), mis. `GI TELLO` |
| `jenis` | nama jenis persis, mis. `RTU` |
| `status_aset` | `UP2B`, `IPP`, atau `BELUM_STAP` |
| `hi` | `0` = lewati Health Index (jauh lebih cepat) |

```json
{
  "status": "ok", "dataset": "aset", "waktu": "2026-11-24T15:00:00+08:00",
  "halaman": 1, "per_halaman": 100, "jumlah": 1834, "jumlah_halaman": 19,
  "halaman_berikutnya": 2,
  "aset": [
    {
      "id": "YgAzAD", "nama": "RTU-01", "asset_id": "100200",
      "status_aset": "UP2B", "status_aset_label": "UP2B",
      "jenis": "RTU", "merk": "SEL", "tipe": "3530",
      "serial_number": "SN-01", "firmware_version": null, "ip_address": "10.1.2.3",
      "lokasi": "GI TELLO", "lokasi_id": "k5Dz8a", "branch": "UP2B",
      "ultg": ["ULTG Makassar"],
      "status_operasi": "operasi", "status_operasi_label": "Operasi",
      "tahun_operasi": 2015, "umur_tahun": 11,
      "host": null,
      "keterangan": null, "spesifikasi": { "jumlah_di": 64 },
      "foto": ["/media/device_photos/RTU-01_RTU_20250101_080000.jpg"],
      "dibuat_pada": "2025-01-01T08:00:00+08:00",
      "health_index": 78, "kategori_hi": "Baik"
    }
  ]
}
```

- `asset_id` adalah nomor aset (isian FASOP), **bukan** `id`. Bisa kosong.
- `status_aset`: hanya `UP2B` yang dihitung sebagai jumlah aset di FASOP.
- `branch`/`ultg` diambil dari master lokasi. Lokasi yang tidak punya master
  (lihat `lokasi_tanpa_master` di bagian 14) bernilai `null`/`[]`.
- `host` diisi untuk VM: `{ "id": ..., "nama": ... }` server fisiknya.
- `foto` berupa path relatif — gabungkan dengan domain FASOP.
- Health Index **dihitung saat diminta**, sama dengan halaman Health Index
  FASOP (sekitar 17 query per peralatan). Untuk salinan yang sering, tarik
  dengan `hi=0` dan perbarui HI cukup sekali sehari.

**`/api/v1/fasop/aset/<id>/`** — satu peralatan selengkapnya: semua field di
atas, ditambah

| Field | Isi |
|---|---|
| `rincian_hi` | tiap faktor HI: `faktor`, `nilai`, `keterangan`, `deduksi`, `maks`, `status` |
| `jumlah_pemeliharaan`, `jumlah_gangguan` | dari perhitungan HI |
| `komponen` | komponen terpasang (modul/kartu/PSU), semua kolomnya |
| `riwayat_kejadian` | penggantian komponen, relokasi, pembongkaran, dsb. |
| `eviden` | foto eviden tambahan: `foto`, `keterangan`, `diunggah_pada` |
| `vm` | VM di dalam server ini: `[{ "id", "nama" }]` |
| `pemeliharaan` | `[{ "id", "tanggal", "tipe", "status" }]`, terbaru dulu |
| `gambar_wiring` | path gambar wiring diagram, atau `null` |

Kolom relasi di `komponen`/`riwayat_kejadian` berbentuk
`{ "id": ..., "label": ... }`. Arti tiap kolomnya ada di `skema.komponen` dan
`skema.riwayat_kejadian` (bentuknya sama dengan `skema_hasil` di bagian 15).
Peralatan yang tidak ada atau sudah dihapus dibalas `404`.

Yang **tidak pernah** dikirim: token halaman publik QR (itu kunci akses, bukan
data) dan data mentah editor wiring diagram.

---

## 14. `GET /api/v1/fasop/lokasi/`

Izin data: **`lokasi`**. Tanpa halaman.

```json
{
  "status": "ok", "dataset": "lokasi",
  "lokasi": [
    { "id": "k5Dz8a", "nama": "GI TELLO", "branch": "UP2B", "branch_id": "Qb7x2m",
      "ultg": ["ULTG Makassar"], "latitude": -5.1, "longitude": 119.4,
      "keterangan": null, "jumlah_aset": 42 }
  ],
  "branch": [
    { "id": "Qb7x2m", "nama": "UP2B", "kode": "UP2B", "keterangan": null, "jumlah_lokasi": 31 }
  ],
  "ultg": [
    { "id": "Ma9kq1", "nama": "ULTG Makassar", "keterangan": null,
      "lokasi": ["GI BONTOALA", "GI TELLO"] }
  ],
  "lokasi_tanpa_master": [ { "lokasi": "GI ANTAH", "jumlah_aset": 1 } ]
}
```

- Lokasi peralatan di FASOP berupa teks yang harus **sama persis** dengan nama
  master lokasi. `lokasi_tanpa_master` menyebut teks lokasi peralatan yang
  tidak cocok dengan master mana pun — aset di sana tidak punya branch/ULTG.
- Satu lokasi bisa dibawahi lebih dari satu ULTG, karena itu `ultg` berupa list.

---

## 15. `GET /api/v1/fasop/pemeliharaan/riwayat/` dan `/api/v1/fasop/pemeliharaan/<id>/`

Izin data: **`riwayat_pemeliharaan`**. Semua pemeliharaan, **Open maupun
Done**.

| Parameter | Arti |
|---|---|
| `halaman`, `per_halaman` | lihat bagian 12 |
| `dari`, `sampai` | tanggal pemeliharaan `YYYY-MM-DD`, keduanya **inklusif** |
| `tipe` | `Preventive` atau `Corrective` (huruf besar/kecil bebas) |
| `status` | `Open` atau `Done` |
| `lokasi` | lokasi peralatan, persis |
| `jenis` | jenis peralatan, persis |
| `aset` | `id` satu peralatan |
| `detail` | `1` = sertakan hasil pengukuran + skemanya |

Nilai penyaring yang tidak dikenal (mis. `tipe=preventif`) **ditolak** `400`,
bukan diabaikan.

```json
{
  "status": "ok", "dataset": "riwayat_pemeliharaan",
  "halaman": 1, "per_halaman": 100, "jumlah": 5210, "jumlah_halaman": 53,
  "halaman_berikutnya": 2,
  "pemeliharaan": [
    {
      "id": "p3LxZa",
      "peralatan": { "id": "YgAzAD", "nama": "RECT-01", "asset_id": null,
                     "jenis": "Rectifier", "lokasi": "GI TELLO" },
      "tipe": "Preventive", "status": "Done",
      "tanggal": "2026-09-05T08:00:00+08:00",
      "deskripsi": "HAR rutin",
      "pelaksana": ["Budi", "Citra"],
      "ttd": { "sudah": true, "oleh": "Andi Teknisi", "pada": "2026-09-06T08:00:00+08:00" },
      "catatan_am": "OK",
      "foto": null,
      "dibuat_pada": "2026-09-05T09:12:44+08:00",
      "hasil_pengukuran": [
        { "tabel": "rectifier",
          "data": { "suhu_ruangan": 24.5, "rect1_kondisi": "OK",
                    "bat1_cells": [ { "cell": 1, "v_float": 2.13 } ], "...": "..." } }
      ]
    }
  ],
  "skema_hasil": {
    "rectifier": {
      "nama": "Maintenance Rectifier & Battery",
      "kolom": [
        { "nama": "suhu_ruangan", "label": "Suhu Ruangan (°C)", "tipe": "desimal" },
        { "nama": "rect1_kondisi", "label": "rect1 kondisi", "tipe": "teks",
          "pilihan": { "OK": "OK", "NOK": "NOK" } }
      ]
    }
  }
}
```

- `hasil_pengukuran` dan `skema_hasil` hanya ada dengan `detail=1`.
- `hasil_pengukuran` berupa **list**: biasanya satu tabel, tapi pemeliharaan
  Corrective bisa membawa tabel `corrective` (jenis kerusakan, tindakan,
  komponen diganti, durasi) **dan** tabel jenis peralatannya.
- `data` berisi **semua kolom** tabel hasil itu apa adanya, termasuk JSON per
  sel baterai dan modul. Kodenya: `plc`, `router`, `radio`, `repeater`, `voip`,
  `mux`, `rectifier`, `corrective`, `teleproteksi`, `genset`, `rtu`, `sas`,
  `rtugeneric`, `bcu`, `frequencyrelay`, `roip`, `ups`, `mastertrip`, `dfr`,
  `masterstation`. Tabel baru di FASOP otomatis ikut dengan kodenya sendiri.
- `skema_hasil` hanya memuat tabel yang muncul di halaman itu. Tiap kolom:
  `label` (teks di layar FASOP), `tipe` (`teks`, `desimal`, `bulat`,
  `boolean`, `tanggal`, `waktu`, `jam`, `json`, `berkas`, `relasi`), dan
  `pilihan` bila isiannya dari daftar — memetakan nilai tersimpan ke teks yang
  tampil.
- Kolom `berkas` (foto sebelum/sesudah) berisi path relatif; kolom `relasi`
  berisi `{ "id", "label" }`.
- `pelaksana`: akun FASOP yang dicentang; kalau tidak ada, nama yang diketik
  bebas — aturan yang sama dengan ekspor Excel FASOP.

**`/api/v1/fasop/pemeliharaan/<id>/`** — satu pemeliharaan dengan
`hasil_pengukuran` dan `skema_hasil` selalu disertakan. Yang tidak ada atau
sudah dihapus dibalas `404`.

---

## 16. Seberapa sering boleh ditarik

Angkanya diperbarui di sisi FASOP setiap beberapa detik. **Tarik paling cepat
sekali per menit** — lebih sering dari itu tidak menambah informasi, hanya
menambah beban ke historian SCADA yang dipakai bersama ruang kontrol.

Kalau butuh yang lebih cepat dari itu, bicarakan dulu dengan tim FASOP.

Inventaris dan riwayat pemeliharaan (bagian 12–15) berubah dalam hitungan jam,
bukan detik: **salin paling sering sekali per jam**, dan Health Index cukup
sekali sehari (tarik `fasop/aset/` dengan `hi=0` di putaran lainnya).

---

## 17. Contoh — Google Apps Script

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

## 18. Kalau ada masalah

Sebutkan ke tim FASOP: **nama konsumen di kunci Anda**, jam kejadian, dan kode
HTTP yang diterima. Pemakaian tiap kunci (kapan terakhir dipakai, dari IP mana)
terlihat di Admin FASOP, jadi keluhan bisa ditelusuri tanpa menebak.
