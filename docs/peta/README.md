# Aset Peta Pembangkit

Berkas sumber yang bisa diedit untuk halaman **Peta Pembangkit** (`/opsis/peta/`).
Keduanya dibuat dari kode yang sedang berjalan, jadi isinya persis sama dengan
yang dirender di layar.

| Berkas | Isi | Sumber sebenarnya di kode |
|---|---|---|
| `peta_sulawesi.svg` | Garis pantai Sulawesi, viewBox `0 0 1000 1244` | `SULAWESI_PATH` di `opsis/hop_map.py` |
| `ikon_pembangkit.svg` | 8 ikon jenis pembangkit (PLTA/PLTU/PLTD/PLTG/PLTGU/PLTB/PLTS/LAIN) | blok `<symbol id="ic-…">` di `opsis/templates/opsis/peta_pembangkit.html` |

Cara mengembalikan hasil edit ke aplikasi ditulis sebagai komentar di kepala
masing-masing berkas. Ringkasnya: edit di Inkscape/Illustrator/Figma, lalu salin
atribut `d` (peta) atau isi `<g id="ic-…">` (ikon) kembali ke berkas sumbernya.

**Peta dipakai bersama.** `SULAWESI_PATH` juga menggambar peta di Dashboard HOP
(`/opsis/hop/dashboard/`), jadi mengedit garis pantai mengubah kedua halaman.

**Jangan menggeser atau menskalakan seluruh pulau.** Posisi ikon disimpan sebagai
persen viewBox (`Pembangkit.peta_x` / `peta_y`) dan diproyeksikan dari lat/long
dengan konstanta di `opsis/hop_map.py`. Kalau pulaunya bergeser, semua ikon jadi
salah tempat. Merapikan detail garis pantai aman.

## Memilih pembangkit mana yang muncul di peta

Ikon di peta dikendalikan `Pembangkit.tampil_di_peta`, terpisah dari koordinat:

- **Lewat halaman peta** — klik **Atur Peta**, pilih ikonnya, tekan **Sembunyikan**.
  Untuk memunculkan lagi, seret namanya dari daftar "Tidak tampil di peta" ke peta.
- **Lewat site admin** — kolom *Tampilkan Ikon di Peta* bisa dicentang massal dari
  daftar Pembangkit (berguna saat menyaring, mis. hanya menampilkan pembangkit
  berbeban besar).

Menghilangkan ikon **tidak** mengeluarkan pembangkit dari tabel daya di sebelah
peta — tabel itu selalu memuat seluruh pembangkit aktif. Mengosongkan `peta_x`/
`peta_y` juga **tidak** menyembunyikan ikon: pembangkit yang namanya terdaftar di
`hop_map.py` akan muncul kembali di posisi bawaannya.
