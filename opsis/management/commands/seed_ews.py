"""
Management command: seed_ews

Isi awal halaman EWS Defense Scheme dari berkas
"Defense Scheme UP2B Makassar 2026.xlsx": tiga kolom parameter dan seluruh
titik skema beserta identitas + ambang setting relenya.

Yang TIDAK diisi command ini: pemetaan ke MSSQL (field sumber_*). Tiap titik
harus diarahkan sendiri ke tabel/kolom realtime yang benar sesuai lokasi
relenya lewat site admin - lihat "python manage.py probe_tabel_ews <tabel>".

Idempotent: baris yang sudah ada dicocokkan lewat (skema, kode, nama) dan
tidak ditimpa, jadi aman dijalankan ulang setelah setting diperbaiki manual.

Jalankan:
    python manage.py seed_ews
    python manage.py seed_ews --dry-run
    python manage.py seed_ews --perbarui     # timpa identitas & setting yang ada
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from opsis.models import KolomEWS, TitikEWS


KOLOM = {
    1: {
        'nama': 'Parameter Tegangan',
        'keterangan': 'UVLS - OVTS - OVCS - UVRS. Rele membaca tegangan bus GI (kV); '
                      'skema bekerja saat tegangan menembus Vset.',
        'warna': '#3987e5',
        'urutan': 1,
    },
    2: {
        'nama': 'Parameter Frekuensi',
        'keterangan': 'OFGS - UFLS. Rele membaca frekuensi sistem (Hz). Frekuensi adalah '
                      'besaran sistem, jadi seluruh skema dalam satu sistem membaca nilai yang sama.',
        'warna': '#d95926',
        'urutan': 2,
    },
    3: {
        'nama': 'Sensing Lainnya',
        'keterangan': 'OLS (arus pembebanan IBT/penghantar) - OGS - ADS - UPLS (pembangkitan) - '
                      'ISLAND (pemisahan subsistem).',
        'warna': '#199e70',
        'urutan': 3,
    },
}


BARIS = [
    {'kolom': 1, 'nama': 'GI Jeneponto', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '9', 'kode': '1.9', 'target': 'Penyulang GI Jeneponto = 8,3 MW (P. Pahlawan, P. Bantaeng, P. Arungkale)', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Bulukumba', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '9', 'kode': '1.9', 'target': 'Penyulang GI Bulukumba = 15 MW (P. Sapiria, P. Sapolohe, P. Bontomacinna, P. Pajukukkang, P. Matekko)', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': 'Nilai Vset tidak tercantum — margin tidak dapat dihitung', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': None, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Sinjai', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '9', 'kode': '1.9', 'target': 'Penyulang GI Sinjai = 15 MW (P. Balle, P. Litha, P. Lamattirilau, P. Tonra)', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': 'Nilai Vset tidak tercantum — margin tidak dapat dihitung', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': None, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Tello', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '10', 'kode': '1.10', 'target': 'Penyulang GI Tello = 15 MW', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Tallo Lama', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '10', 'kode': '1.10', 'target': 'Penyulang GI Tallo Lama = 15 MW', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Panakkukang', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '10', 'kode': '1.10', 'target': 'Penyulang GI Panakkukang = 40 MW', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Poso', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '11', 'kode': '1.11', 'target': 'Penyulang GI Poso = 7 MW', 'time_delay': '1 s (Tahap 1)', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Sidera', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '11', 'kode': '1.11', 'target': 'Penyulang GI Sidera = 10 MW', 'time_delay': '1 s (Tahap 1)', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Parigi', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '11', 'kode': '1.11', 'target': 'Penyulang GI Parigi = 9,3 MW', 'time_delay': '1 s (Tahap 1)', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Talise', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '11', 'kode': '1.11', 'target': 'Penyulang GI Talise = 25 MW', 'time_delay': '1,5 s (Tahap 2)', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Tawaeli', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '11', 'kode': '1.11', 'target': 'Penyulang GI Tawaeli = 8,8 MW', 'time_delay': '', 'status_skema': 'aktif', 'catatan': 'Tahap dan time delay tidak dinyatakan di berkas sumber', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Tambu', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '11', 'kode': '1.11', 'target': 'Penyulang GI Tambu = 8,8 MW', 'time_delay': '', 'status_skema': 'aktif', 'catatan': 'Tahap dan time delay tidak dinyatakan di berkas sumber', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Bantaeng Smelter — Tahap 1', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '12', 'kode': '1.12', 'target': 'GI Huadi-2 Yatai Tungku #2; GI Huadi-3 Wuzhou Tungku #1', 'time_delay': '1,5 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 133.5, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Bantaeng Smelter — Tahap 2', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '12', 'kode': '1.12', 'target': 'GI Huadi-2 Yatai Tungku #1; GI Huadi-3 Wuzhou Tungku #2', 'time_delay': '2 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 133.5, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Puuwatu (sisi 66 kV)', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '13', 'kode': '1.13', 'target': 'Penyulang F. Kendari TV; F. Mandonga Baru', 'time_delay': '3,5 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 66, 'setting': 59.4, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Bantaeng Switching — Tahap 1', 'skema': 'OVCS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '14', 'kode': '1.14', 'target': 'Kapasitor 25 Mvar', 'time_delay': '2,5 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 165, 'arah': 'atas'},
    {'kolom': 1, 'nama': 'GI Bantaeng Switching — Tahap 2', 'skema': 'OVCS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '14', 'kode': '1.14', 'target': 'Kapasitor 50 Mvar', 'time_delay': '3 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 165, 'arah': 'atas'},
    {'kolom': 1, 'nama': 'GI Mamuju (PMT 150 kV)', 'skema': 'UVRS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbar', 'nomor': '22', 'kode': '1.22', 'target': 'Reaktor #1 Mamuju', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': 'Satuan Vset di berkas tertulis "136.50 Hz" — seharusnya kV', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 136.5, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Malili', 'skema': 'OVTS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '23', 'kode': '1.23', 'target': 'T/L Malili – Wotu #1 (td 2,0 s); T/L Malili – Lasusua #1 (td 2,5 s)', 'time_delay': '2,0 / 2,5 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 165, 'arah': 'atas'},
    {'kolom': 1, 'nama': 'GI Lasusua', 'skema': 'OVTS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '23', 'kode': '1.23', 'target': 'T/L Lasusua – Wolo #1', 'time_delay': '3,0 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 165, 'arah': 'atas'},
    {'kolom': 1, 'nama': 'GI Andoolo', 'skema': 'OVTS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '24', 'kode': '1.24', 'target': 'T/L Kendari – Andoolo #1', 'time_delay': '2,5 s', 'status_skema': 'aktif', 'catatan': 'Keterangan detail menyebut "(Rencana)" padahal Peralatan = Terpasang & Skema Aktif', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 164, 'arah': 'atas'},
    {'kolom': 1, 'nama': 'GI Kasipute', 'skema': 'OVTS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '24', 'kode': '1.24', 'target': 'T/L Kasipute – Tinanggea #1', 'time_delay': '2,0 s', 'status_skema': 'aktif', 'catatan': 'Keterangan detail menyebut "(Rencana)" padahal Peralatan = Terpasang & Skema Aktif', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 164, 'arah': 'atas'},
    {'kolom': 1, 'nama': 'GI PLTMG Baubau', 'skema': 'OVTS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '51', 'kode': '1.2', 'target': 'T/L PLTMG Baubau – Raha #1', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 157.5, 'arah': 'atas'},
    {'kolom': 1, 'nama': 'GI Raha', 'skema': 'OVTS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '51', 'kode': '1.2', 'target': 'T/L PLTMG Baubau – Raha #1', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 157.5, 'arah': 'atas'},
    {'kolom': 1, 'nama': 'GI Antam', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '40', 'kode': '3.3', 'target': 'Beban KTT Antam (40 MVA)', 'time_delay': '1,0 s', 'status_skema': 'rencana', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 133.5, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Unity — Tahap 3', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '41', 'kode': '3.4', 'target': 'GI Huadi-Unity', 'time_delay': '2,5 s', 'status_skema': 'rencana', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 133.5, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Mamuju', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbar', 'nomor': '42', 'kode': '3.5', 'target': 'Penyulang GI Mamuju = 10 MW', 'time_delay': '2 s', 'status_skema': 'rencana', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Mamuju New', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbar', 'nomor': '42', 'kode': '3.5', 'target': 'Penyulang GI Mamuju New = 5 MW', 'time_delay': '2 s', 'status_skema': 'rencana', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Majene', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbar', 'nomor': '42', 'kode': '3.5', 'target': 'Penyulang GI Majene = 5 MW', 'time_delay': '2 s', 'status_skema': 'rencana', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Polmas', 'skema': 'UVLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbar', 'nomor': '42', 'kode': '3.5', 'target': 'Penyulang GI Polmas = 10 MW', 'time_delay': '2 s', 'status_skema': 'rencana', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 135, 'arah': 'bawah'},
    {'kolom': 1, 'nama': 'GI Pamona — Tahap 1', 'skema': 'OVTS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '43', 'kode': '3.6', 'target': 'T/L Pamona – Kolonedale', 'time_delay': '2 s', 'status_skema': 'rencana', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 162, 'arah': 'atas'},
    {'kolom': 1, 'nama': 'GI Pamona — Tahap 2', 'skema': 'OVTS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '43', 'kode': '3.6', 'target': 'T/L Kolonedale – Bungku; T/L Bungku – ACN', 'time_delay': '2,5 s', 'status_skema': 'rencana', 'catatan': '', 'besaran': 'v', 'satuan': 'kV', 'nominal': 150, 'setting': 162, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTA Malea #2', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '16', 'kode': '1.16', 'target': 'Trip PLTA Malea #2 (PMT 150 kV)', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 51.5, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTA Bakaru #2', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '15', 'kode': '1.15', 'target': 'Trip PLTA Bakaru HU #2 (PMT 150 kV)', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 51.6, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTA Poso 1 #1', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '17', 'kode': '1.17', 'target': 'Trip PLTA Poso 1 #1 (PMT 150 kV)', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 51.65, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTA Poso 2B #1', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '19', 'kode': '1.19', 'target': 'Trip PLTA Poso 2B #1 (PMT 150 kV)', 'time_delay': '1,5 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 51.7, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTA Poso 2A #1', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '18', 'kode': '1.18', 'target': 'Trip PLTA Poso 2A #1 (PMT 150 kV)', 'time_delay': '2 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 51.8, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTGU Sengkang ST28', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '20', 'kode': '1.20', 'target': 'Trip PLTGU Sengkang ST28 (PMT 150 kV)', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 51.9, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTGU Sengkang ST18', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '21', 'kode': '1.21', 'target': 'Trip PLTGU Sengkang ST18 (PMT 150 kV)', 'time_delay': '1 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 52.0, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'UFLS Sulbagsel — Tahap 1', 'skema': 'UFLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '47', 'kode': '4.1', 'target': 'Beban lepas: 63 MW (LWBP) / 93 MW (WBP)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 49.2, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Sulbagsel — Tahap 2', 'skema': 'UFLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '47', 'kode': '4.1', 'target': 'Beban lepas: 48 MW (LWBP) / 67 MW (WBP)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 49.0, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Sulbagsel — Tahap 3', 'skema': 'UFLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '47', 'kode': '4.1', 'target': 'Beban lepas: 71 MW (LWBP) / 103 MW (WBP)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 48.8, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Sulbagsel — Tahap 4', 'skema': 'UFLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '47', 'kode': '4.1', 'target': 'Beban lepas: 41 MW (LWBP) / 61 MW (WBP)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 48.6, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Sulbagsel — Tahap 5', 'skema': 'UFLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '47', 'kode': '4.1', 'target': 'Beban lepas: 54 MW (LWBP) / 84 MW (WBP)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 48.5, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Sulbagsel — Tahap 6', 'skema': 'UFLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '47', 'kode': '4.1', 'target': 'Beban lepas: 25 MW (LWBP) / 33 MW (WBP)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 48.4, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Sulbagsel — Tahap 7', 'skema': 'UFLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '47', 'kode': '4.1', 'target': 'Beban lepas: 36 MW (LWBP) / 52 MW (WBP)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 48.3, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS BauBau — Tahap 1', 'skema': 'UFLS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '56', 'kode': '4.1', 'target': 'P. Mubar (GI Raha); total 5 tahap = 23,65 MW', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 49.4, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS BauBau — Tahap 2', 'skema': 'UFLS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '56', 'kode': '4.1', 'target': 'P. Tampo (GH PLTD Raha) = 3,19 MW', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 49.2, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS BauBau — Tahap 3', 'skema': 'UFLS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '56', 'kode': '4.1', 'target': 'P. Pertamina (GH PLTD Baubau) = 3,9 MW', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 49.0, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS BauBau — Tahap 4', 'skema': 'UFLS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '56', 'kode': '4.1', 'target': 'P. Wolio / GH Watilea', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 48.8, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS BauBau — Tahap 5', 'skema': 'UFLS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '56', 'kode': '4.1', 'target': 'P. Cendana (GI Baubau) = 4,1 MW', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 48.6, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Luwuk — Tahap 1', 'skema': 'UFLS', 'sistem': 'Luwuk', 'subsistem': 'luwuk', 'nomor': '61', 'kode': '4.1', 'target': 'PMT Luwedkan (GI Luwuk); total 5 tahap = 14,80 MW', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 49.4, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Luwuk — Tahap 2', 'skema': 'UFLS', 'sistem': 'Luwuk', 'subsistem': 'luwuk', 'nomor': '61', 'kode': '4.1', 'target': 'PMT Salodik (GI Lunak) / P. Sawit', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 49.2, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Luwuk — Tahap 3', 'skema': 'UFLS', 'sistem': 'Luwuk', 'subsistem': 'luwuk', 'nomor': '61', 'kode': '4.1', 'target': 'P. Maleo (GI Toili)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 49.0, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Luwuk — Tahap 4', 'skema': 'UFLS', 'sistem': 'Luwuk', 'subsistem': 'luwuk', 'nomor': '61', 'kode': '4.1', 'target': 'P. Kintom (GI Luwuk)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 48.8, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'UFLS Luwuk — Tahap 5', 'skema': 'UFLS', 'sistem': 'Luwuk', 'subsistem': 'luwuk', 'nomor': '61', 'kode': '4.1', 'target': 'PMT Tangeban / F. BPH (GI Luwuk)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 48.6, 'arah': 'bawah'},
    {'kolom': 2, 'nama': 'Pasca Island Puuwatu — PLTD Poasia', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '33', 'kode': '3.2', 'target': 'Target trip PLTD Poasia', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'Pasca Island Puuwatu — PLTD Wuawua', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '34', 'kode': '3.2', 'target': 'Target trip PLTD Wuawua', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'Pasca Island Puuwatu — PLTMG Nii Tanassa Blok 1', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '35', 'kode': '3.2', 'target': 'Target trip PLTMG Nii Tanassa Blok 1', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'Pasca Island Puuwatu — PLTMG Nii Tanassa Blok 2', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '36', 'kode': '3.2', 'target': 'Target trip PLTMG Nii Tanassa Blok 2', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'Pasca Island Puuwatu — PLTU Nii Tanassa #3', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '37', 'kode': '3.2', 'target': 'Target trip PLTU Nii Tanassa #3', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'Pasca Island Puuwatu — PLTU Nii Tanassa #2', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '38', 'kode': '3.2', 'target': 'Target trip PLTU Nii Tanassa #2', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'Pasca Island Puuwatu — PLTU Nii Tanassa #1', 'skema': 'OFGS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '39', 'kode': '3.2', 'target': 'Target trip PLTU Nii Tanassa #1', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTMG Baubau #4', 'skema': 'OFGS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '53', 'kode': '3.2', 'target': 'Target trip PLTMG Baubau #4', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTMG Baubau #2', 'skema': 'OFGS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '54', 'kode': '3.3', 'target': 'Target trip PLTMG Baubau #2', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTU Baruta #1', 'skema': 'OFGS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '55', 'kode': '3.4', 'target': 'Target trip PLTU Baruta #1', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'Tahapan Sistem Luwuk', 'skema': 'OFGS', 'sistem': 'Luwuk', 'subsistem': 'luwuk', 'nomor': '59', 'kode': '3.1', 'target': 'Tahapan OFGS Sistem Luwuk', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 2, 'nama': 'PLTMG Luwuk', 'skema': 'OFGS', 'sistem': 'Luwuk', 'subsistem': 'luwuk', 'nomor': '60', 'kode': '3.2', 'target': 'Target trip PLTMG Luwuk · Tindak lanjut: AI 2025 (RDS KI)', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'IBT 1,2 150/70 kV Puuwatu', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '6', 'kode': '1.6', 'target': 'Penyulang GI 66 kV Puuwatu 4 MW (Tahap 1) + 4 MW (Tahap 2); total 8 MW', 'time_delay': '2,5 s / 3,5 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 112, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'IBT 3,5 150/70 kV GI Tello', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '7', 'kode': '1.7', 'target': 'Penyulang di GI Mandai = 13,3 MW', 'time_delay': '0,5 s', 'status_skema': 'nonaktif', 'catatan': 'Status Skema = Tidak Aktif pada berkas sumber', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 120, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'IBT 150/66 kV Talise', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '3', 'kode': '1.3', 'target': 'GI Talise 70 kV = 16 MW; GI Parigi 70 kV = 9,3 MW', 'time_delay': '2 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 126, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'IBT 2,3 150/70 kV GI Pangkep', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '8', 'kode': '1.8', 'target': 'Penyulang GI Mandai = 13,3 MW', 'time_delay': '2 s', 'status_skema': 'aktif', 'catatan': 'Teks detail menyebut "Tidak Aktif" tetapi kolom Status Skema = Aktif', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 253, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'IBT 1,2 275/150 kV Pamona (Tahap 1-3)', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '1', 'kode': '1.1', 'target': 'Tahap 1-5, total beban target = 145,9 MW (GI Sidera, Silae, Talise, Parigi, Pasangkayu, Tawaeli, Tambu, Kolonedale, Bungku, KTT ACN)', 'time_delay': '3 s – 5 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 346, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'IBT 1 275/150 kV Wotu (90 MVA)', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '4', 'kode': '1.4', 'target': 'Tahap 1-3, total 38,36 MW (GI Wotu, Malili, Lasusua, Kolaka, Unaaha)', 'time_delay': '2,5 s – 3,5 s', 'status_skema': 'aktif', 'catatan': 'Teks detail menyebut "Tidak aktif" tetapi kolom Status Skema = Aktif', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 358, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'SUTT 150 kV Poso – Sidera', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '2', 'kode': '1.2', 'target': 'Tahap 1: GI Sidera, Silae, Topoyo = 33,5 MW; Tahap 2: GI Talise & Pasangkayu = 15 MW', 'time_delay': '', 'status_skema': 'aktif', 'catatan': 'Teks detail menyebut "Tidak Aktif" tetapi kolom Status Skema = Aktif', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 660, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'IBT 2 275/150 kV Wotu (250 MVA)', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '5', 'kode': '1.5', 'target': 'Tahap 1: 31 MW; Tahap 2: 46 MW; total target 77 MW', 'time_delay': '1,5 s / 2 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 1000, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'Trafo #1 30 MVA GI PLTMG Baubau', 'skema': 'OLS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '50', 'kode': '1.1', 'target': 'P. BWI = 2,5 MW', 'time_delay': '3 s', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 115.5, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'SKTT 150 kV Bontoala – Tallolama', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '30', 'kode': '2.3', 'target': 'Target OLS Tallo Lama / Tello / Panakkukang', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': None, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'SUTT 150 kV Tello – Kima', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '31', 'kode': '2.4', 'target': 'Target OLS koridor Tello – Kima', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': None, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'IBT 275/150 kV Pamona #1 #2 Tahap 4', 'skema': 'OLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '32', 'kode': '3.1', 'target': 'Tahap 5: KTT ACN = 27 MW; total beban 145,9 MW', 'time_delay': '5 s', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': None, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'Trafo 30 MVA GI PLTMG Baubau (tambah target)', 'skema': 'OLS', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '52', 'kode': '3.1', 'target': 'Penambahan target OLS', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': None, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'ADS OGS IBT Latuppa', 'skema': 'ADS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '27', 'kode': '1.27', 'target': 'PLTA Poso, total beban 370 MW; I set IBT 1–4 = 208 A (sisi HV)', 'time_delay': 'instant', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 208, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'ADS IBT 1,2 275/150 kV Pamona', 'skema': 'OGS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '25', 'kode': '1.25', 'target': 'PLTA Poso, total beban 370 MW; I set IBT 1,2 = 346 A (sisi LV)', 'time_delay': 'instant', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 346, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'UPLS PLTU Site Jeneponto & Punagaya', 'skema': 'UPLS', 'sistem': 'Sulbagsel', 'subsistem': 'sulselbar', 'nomor': '28', 'kode': '2.1', 'target': '150 < ΔP < 650 MW · kombinasi load shedding penyulang & KTT Huadi · total target 362,2 MW', 'time_delay': 'instant', 'status_skema': 'nonaktif', 'catatan': 'Terpasang tetapi Status Skema = Tidak Aktif', 'besaran': 'p', 'satuan': 'MW', 'nominal': None, 'setting': 150, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'ADS Subsistem Sultra', 'skema': 'ADS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '26', 'kode': '1.26', 'target': 'ADS Subsistem Sultra (hanya diagram di berkas sumber)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': None, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'OGS IBT 1,2 150/70 kV Puuwatu', 'skema': 'OGS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '29', 'kode': '2.2', 'target': 'PLTMG Nii Tanasa Blok 1 & 2; PLTU Nii Tanasa #1, #2, #3', 'time_delay': '1 s – 3 s', 'status_skema': 'rencana', 'catatan': '', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': 112, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'ADS Subsistem Sultra (penambahan sensing)', 'skema': 'ADS', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '44', 'kode': '3.7', 'target': 'Penambahan sensing dan target load shedding', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': None, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'ADS Direct Transfer Trip (DTT) pasca lepas interkoneksi', 'skema': 'ADS', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '45', 'kode': '3.8', 'target': 'Tindak lanjut: AO 2026 (UP2B)', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Peralatan = Rencana tetapi Status Skema = Aktif\nSetting tidak tercantum di berkas sumber', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': None, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'OGS Statis PLTA Poso', 'skema': 'OGS', 'sistem': 'Sulbagsel', 'subsistem': 'sulteng', 'nomor': '46', 'kode': '3.9', 'target': 'Skema statis PLTA Poso', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'i', 'satuan': 'A', 'nominal': None, 'setting': None, 'arah': 'atas'},
    {'kolom': 3, 'nama': 'ISLAND Stage 2 Puuwatu', 'skema': 'ISLAND', 'sistem': 'Sulbagsel', 'subsistem': 'sultra', 'nomor': '49', 'kode': '4.4', 'target': 'Pisah SUTT 150 kV Kendari – Puuwatu #1 dan #2 (setting UFR Island)', 'time_delay': '160 ms', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 47.9, 'arah': 'bawah'},
    {'kolom': 3, 'nama': 'Island Stage 1 GH Baruta', 'skema': 'ISLAND', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '57', 'kode': '4.1', 'target': 'Islanding sistem Baubau pada 48 Hz', 'time_delay': '', 'status_skema': 'aktif', 'catatan': '', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': 48.0, 'arah': 'bawah'},
    {'kolom': 3, 'nama': 'ISLAND Sulbagsel Stage 1,2', 'skema': 'ISLAND', 'sistem': 'Sulbagsel', 'subsistem': 'sulbagsel', 'nomor': '48', 'kode': '4.3', 'target': 'Stage 1 dan 2 (hanya diagram di berkas sumber)', 'time_delay': '', 'status_skema': 'aktif', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'bawah'},
    {'kolom': 3, 'nama': 'Island Stage 1 GI Raha', 'skema': 'ISLAND', 'sistem': 'BauBau', 'subsistem': 'baubau', 'nomor': '58', 'kode': '4.3', 'target': 'Islanding GI Raha', 'time_delay': '', 'status_skema': 'rencana', 'catatan': 'Setting tidak tercantum di berkas sumber', 'besaran': 'f', 'satuan': 'Hz', 'nominal': 50, 'setting': None, 'arah': 'bawah'},
]


class Command(BaseCommand):
    help = 'Isi kolom & titik EWS Defense Scheme dari berkas DS UP2B Makassar 2026'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Tampilkan rencana tanpa menulis ke database')
        parser.add_argument('--perbarui', action='store_true',
                            help='Timpa identitas & setting titik yang sudah ada')

    @transaction.atomic
    def handle(self, *args, **opts):
        kering = opts['dry_run']
        perbarui = opts['perbarui']

        kolom_obj = {}
        for nomor, data in KOLOM.items():
            if kering:
                ada = KolomEWS.objects.filter(nama=data['nama']).first()
                self.stdout.write(f"  kolom {data['nama']}: {'sudah ada' if ada else 'dibuat'}")
                kolom_obj[nomor] = ada
                continue
            obj, dibuat = KolomEWS.objects.get_or_create(
                nama=data['nama'],
                defaults={'keterangan': data['keterangan'], 'warna': data['warna'],
                          'urutan': data['urutan']})
            kolom_obj[nomor] = obj
            self.stdout.write(f"  kolom {obj.nama}: {'dibuat' if dibuat else 'sudah ada'}")

        dibuat = dilewati = diperbarui = 0
        for urutan, baris in enumerate(BARIS, start=1):
            data = dict(baris)
            nomor_kolom = data.pop('kolom')
            kunci = {'skema': data['skema'], 'kode': data['kode'], 'nama': data['nama']}
            data['urutan'] = urutan

            if kering:
                ada = TitikEWS.objects.filter(**kunci).exists()
                if ada:
                    dilewati += 1
                else:
                    dibuat += 1
                continue

            obj = TitikEWS.objects.filter(**kunci).first()
            if obj is None:
                TitikEWS.objects.create(kolom=kolom_obj[nomor_kolom], **data)
                dibuat += 1
            elif perbarui:
                for k, v in data.items():
                    setattr(obj, k, v)
                obj.kolom = kolom_obj[nomor_kolom]
                obj.save()
                diperbarui += 1
            else:
                dilewati += 1

        ringkas = (f'{dibuat} titik dibuat, {diperbarui} diperbarui, '
                   f'{dilewati} dilewati (sudah ada).')
        if kering:
            self.stdout.write(self.style.WARNING('DRY RUN - tidak ada yang ditulis. ' + ringkas))
            transaction.set_rollback(True)
            return
        self.stdout.write(self.style.SUCCESS(ringkas))
        self.stdout.write(
            'Langkah berikutnya: arahkan tiap titik ke tabel/kolom realtime MSSQL di '
            'site admin (Opsis -> Titik EWS -> "Sumber Data Realtime"). '
            'Pakai "python manage.py probe_tabel_ews <tabel>" untuk melihat nama kolomnya.'
        )
