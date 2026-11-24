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
        'kode':       'beban_trafo',
        'nama':       'Beban trafo (distribusi & IBT)',
        'penjelasan': 'Daya trafo terkini per GI/bay, dan riwayat P per menit '
                      'dari snapshot PostgreSQL. Jenisnya dipilih lewat '
                      '?jenis=distribusi (bawaan) atau ?jenis=ibt.',
        'sumber':     'MSSQL ALL_TRANS_DATA (terkini, lewat opsis/trafo.py) '
                      '+ opsis.SnapTrafo (riwayat)',
        'endpoint':   ['/api/v1/opsis/beban-trafo/',
                       '/api/v1/opsis/beban-trafo/riwayat/'],
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
    {
        'kode':       'status_monitor',
        'nama':       'Status RTU & host Zabbix',
        'penjelasan': 'Jumlah RTU UP/DOWN beserta daftar yang sedang DOWN, dan '
                      'ringkasan tiap instansi Zabbix beserta host yang sedang '
                      'PROBLEM — angka yang sama dengan halaman Device Monitor.',
        'sumber':     'device_mon.RTU (cron collect_rtu) + device_mon.ZabbixHost '
                      '(cron sync_zabbix / webhook)',
        'endpoint':   ['/api/v1/fasop/status-monitor/'],
    },
    {
        'kode':       'pemeliharaan',
        'nama':       'Pemeliharaan & jadwal kunjungan',
        'penjelasan': 'Pemeliharaan yang masih Open, rekap pemeliharaan sebulan, '
                      'dan jadwal kunjungan bulan itu beserta progresnya.',
        'sumber':     'maintenance.Maintenance + jadwal.JadwalKunjungan',
        'endpoint':   ['/api/v1/fasop/pemeliharaan/'],
    },
    {
        'kode':       'peralatan',
        'nama':       'Pencarian peralatan',
        'penjelasan': 'Cari peralatan menurut nama/lokasi/merk/tipe: jenis, '
                      'status operasi, umur, dan Health Index. Tanpa IP, serial '
                      'number, maupun spesifikasi teknis.',
        'sumber':     'devices.Device + health_index.calculator (dihitung, tidak disimpan)',
        'endpoint':   ['/api/v1/fasop/peralatan/'],
    },
    # ── Untuk DISALIN utuh (Fasop Induk). Sengaja kode baru, bukan perluasan
    #    `peralatan`/`pemeliharaan`: kunci bot WhatsApp yang sudah memegang
    #    kedua izin itu tidak boleh ikut mendapat inventaris lengkap (IP,
    #    serial number) dan seluruh hasil ukur hanya karena endpoint-nya
    #    bertambah.
    {
        'kode':       'aset',
        'nama':       'Inventaris aset lengkap',
        'penjelasan': 'Seluruh peralatan berhalaman beserta ID-nya: Asset ID, '
                      'status aset, jenis, merk, tipe, serial number, firmware, '
                      'IP address, lokasi/branch/ULTG, spesifikasi, umur, dan '
                      'Health Index. Detail per peralatan menambahkan rincian HI, '
                      'komponen, riwayat kejadian, dan eviden foto.',
        'sumber':     'devices.Device + SiteLocation + DeviceComponent + DeviceEvent '
                      '+ health_index.calculator',
        'endpoint':   ['/api/v1/fasop/aset/', '/api/v1/fasop/aset/<id>/'],
    },
    {
        'kode':       'lokasi',
        'nama':       'Lokasi GI, Branch & ULTG',
        'penjelasan': 'Master lokasi/GI beserta branch, ULTG, koordinat, dan '
                      'jumlah aset per lokasi.',
        'sumber':     'devices.SiteLocation + Branch + ULTG',
        'endpoint':   ['/api/v1/fasop/lokasi/'],
    },
    {
        'kode':       'riwayat_pemeliharaan',
        'nama':       'Riwayat & hasil pemeliharaan',
        'penjelasan': 'Seluruh pemeliharaan (Open dan Done) berhalaman, dengan '
                      'pelaksana, TTD, catatan AM, dan hasil pengukuran per jenis '
                      'peralatan beserta skema kolomnya.',
        'sumber':     'maintenance.Maintenance + tabel detail Maintenance* (hasil ukur)',
        'endpoint':   ['/api/v1/fasop/pemeliharaan/riwayat/',
                       '/api/v1/fasop/pemeliharaan/<id>/'],
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
