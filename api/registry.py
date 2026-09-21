"""
Daftar JENIS DATA yang bisa dibuka ke pihak luar lewat `/api/v1/`.

Deklaratif, seperti `opsis/sumber_data.py`: menambah data baru = menambah satu
entri di sini plus view-nya, bukan menulis aturan izin baru. Site admin lalu
memutuskan dua hal terpisah di atas daftar ini:

    1. Apakah data itu boleh keluar sama sekali   -> devices.DatasetApi.aktif
    2. Siapa saja yang boleh membacanya            -> devices.KunciApi.dataset

Kenapa daftarnya di KODE, bukan diketik admin: yang benar-benar menyajikan
angkanya adalah sebuah view. Kalau kodenya diketik bebas di admin, salah ketik
satu huruf menghasilkan izin yang tidak menjaga apa pun — kelihatan tercentang
di layar, padahal view-nya menanyakan kode lain. Di sini kodenya dipasangkan ke
view lewat dekorator, dan `DatasetApi.sinkron()` yang membuat barisnya.

`nama`/`penjelasan` juga sengaja bukan kolom admin: keduanya menerangkan apa
yang DIKIRIM view, jadi kalau bisa diubah terpisah dari kodenya, halaman admin
cepat atau lambat akan menjanjikan isi yang berbeda dari yang keluar.
"""

SEMUA = [
    {
        'kode':       'beban_ktt',
        'nama':       'Beban KTT (konsumen tegangan tinggi)',
        'penjelasan': 'Beban MW terkini tiap konsumen tegangan tinggi, '
                      'angka yang sama dengan halaman OPSIS → Beban KTT.',
        'sumber':     'MSSQL IND_LOAD (realtime, lewat opsis/ktt.py)',
        'endpoint':   ['/api/v1/opsis/beban-ktt/'],
    },
    {
        'kode':       'beban_pembangkit',
        'nama':       'Beban pembangkit (MW/MVAR per unit)',
        'penjelasan': 'Nilai terkini tiap pembangkit beserta unitnya, dan '
                      'riwayat per menit dari snapshot PostgreSQL.',
        'sumber':     'MSSQL (terkini, lewat opsis/beban_kit.py) + opsis.SnapLive (riwayat)',
        'endpoint':   ['/api/v1/opsis/beban-pembangkit/',
                       '/api/v1/opsis/beban-pembangkit/riwayat/'],
    },
    {
        'kode':       'frekuensi',
        'nama':       'Frekuensi sistem (Hz)',
        'penjelasan': 'Riwayat frekuensi sistem per detik, digabung dari '
                      'historian SCADA dan rekaman FASOP sendiri.',
        'sumber':     'opsis/freq_history.py (SYS_FREQ_HIS + SnapFreq + SnapFreqRT)',
        'endpoint':   ['/api/v1/opsis/frekuensi/'],
    },
    {
        'kode':       'logsheet',
        'nama':       'Logsheet pembebanan (slot 30 menit)',
        'penjelasan': 'Nilai tiap titik ukur logsheet per slot 30 menit: '
                      'pembangkit, penghantar, busbar, dan trafo/IBT.',
        'sumber':     'logsheet.LogsheetNilai (diisi cron collect_logsheet)',
        'endpoint':   ['/api/v1/logsheet/pembebanan/'],
    },
]

SEMUA_KODE = [d['kode'] for d in SEMUA]

_PETA = {d['kode']: d for d in SEMUA}


def cari(kode):
    """Entri registry sebuah kode, atau None bila kodenya tidak dikenal lagi.

    None terjadi pada baris DatasetApi yang tertinggal setelah sebuah data
    dihapus dari kode — admin menampilkannya sebagai "tidak dikenal" daripada
    diam-diam menyembunyikannya, supaya izin basi tidak menumpuk tak terlihat.
    """
    return _PETA.get(kode)


def nama(kode):
    entri = _PETA.get(kode)
    return entri['nama'] if entri else kode
