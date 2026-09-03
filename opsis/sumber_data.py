"""
Peta sumber data OPSIS — halaman /opsis/sumber-data/.

OPSIS menarik angka dari banyak tempat: dua tabel realtime MSSQL, tiga tabel
histori MSSQL, delapan tabel snapshot PostgreSQL yang diisi cron, plus
spreadsheet lewat n8n. Tanpa peta, mustahil menjawab pertanyaan sesederhana
"angka ini datang dari mana" — dan itu bukan soal teori: `SYS_FREQ_HIS` pernah
berhenti diisi selama 42 jam tanpa ada yang tahu, karena kartu Hz di dashboard
membaca tabel LAIN yang kebetulan masih hidup.

Modul ini mendeklarasikan petanya sebagai data, lalu memeriksa kesegaran tiap
sumber. Menambah sumber baru = menambah satu entri di SUMBER, bukan menulis
kode baru.

Catatan penting soal "kesegaran": sebagian besar tabel realtime MSSQL
(`SYS_FREQ_RT`, `ALL_TRANS_DATA`, `IND_LOAD`, `TRANS_*_RT`) **tidak punya kolom
waktu sama sekali** — nilainya ditimpa di tempat. Untuk tabel itu kesegaran
tidak bisa diperiksa langsung; yang bisa diperiksa adalah tabel snapshot
PostgreSQL yang menyalinnya, karena di sana ada kolom waktu. Kolom `DATE` di
`KIT_REALTIME` ADA tapi **tidak dipelihara** (banyak baris bertanggal 2022-2025
padahal nilainya terbarui terus), jadi ditandai tidak andal dan tidak boleh
dipakai menyimpulkan data mati.
"""
import datetime
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

MSSQL = 'mssql'
POSTGRES = 'postgres'
LUAR = 'luar'

# Urutan tampil lapisan. {% regroup %} di template hanya menggabungkan item yang
# BERURUTAN, jadi daftar harus diurutkan dulu — kalau tidak, satu lapisan bisa
# muncul dua kali begitu ada entri baru disisipkan di tempat yang salah.
LAPIS_URUT = {MSSQL: 0, POSTGRES: 1, LUAR: 2}

# Ambang status kesegaran (menit).
SEGAR_MENIT = 15
TELAT_JAM = 24


SUMBER = [
    # ── Lapis 1: MSSQL realtime (ditimpa di tempat, tanpa riwayat) ──────────
    {
        'fitur': 'Dashboard — kartu MW/MVAR, Peta Pembangkit, EWS',
        'lapis': MSSQL, 'sumber': 'dbo.KIT_REALTIME',
        'kolom_waktu': 'DATE', 'waktu_andal': False,
        'diisi': 'SCADA (langsung)',
        'catatan': 'Kolom DATE tidak dipelihara — jangan dipakai menilai kesegaran. '
                   'Kesegarannya tercermin di SnapLive.',
    },
    {
        'fitur': 'Dashboard — kartu Hz, kolektor frekuensi',
        'lapis': MSSQL, 'sumber': 'dbo.SYS_FREQ_RT',
        'kolom_waktu': None,
        'diisi': 'SCADA (langsung)',
        'catatan': 'Satu baris, tanpa kolom waktu. Kesegarannya tercermin di SnapFreqRT.',
    },
    {
        'fitur': 'Beban Trafo distribusi & IBT',
        'lapis': MSSQL, 'sumber': 'dbo.ALL_TRANS_DATA',
        'kolom_waktu': None,
        'diisi': 'SCADA (langsung)',
        'catatan': 'Tanpa kolom waktu. Sebagian trafo dialihkan ke tabel TRANS_*_RT '
                   'lewat Trafo.sumber_* di admin.',
    },
    {
        'fitur': 'Beban KTT (konsumen tegangan tinggi)',
        'lapis': MSSQL, 'sumber': 'dbo.IND_LOAD',
        'kolom_waktu': None,
        'diisi': 'SCADA (langsung)',
        'catatan': 'Tanpa kolom waktu.',
    },
    {
        'fitur': 'Dashboard — kartu Total Padam',
        'lapis': MSSQL, 'sumber': 'tabel yang didaftarkan di admin',
        'kolom_waktu': None, 'lewati_periksa': True,
        'diisi': 'SCADA (langsung)',
        'catatan': 'Tabel/kolomnya dipetakan lewat Opsis > Kartu Total Padam di admin, '
                   'jadi tidak bisa diperiksa dari sini. Pakai aksi "Uji baca nilai dari '
                   'MSSQL" di halaman admin itu.',
    },
    {
        'fitur': 'Daya Mampu (DMN/DMP) di kartu pembangkit',
        'lapis': MSSQL, 'sumber': 'dbo.KIT_DMP',
        'kolom_waktu': 'DATE', 'waktu_andal': False,
        'diisi': 'diisi manual / proses SCADA',
        'catatan': 'Kolom & baris dipetakan lewat Pembangkit.dmp_* di admin.',
    },
    {
        'fitur': 'Frekuensi per area (Sultra/Sulteng/Baubau/Luwuk)',
        'lapis': MSSQL, 'sumber': 'dbo.TRANS_*_RT',
        'kolom_waktu': None, 'lewati_periksa': True,
        'diisi': 'SCADA (langsung)',
        'catatan': 'Empat tabel terpisah per area, tanpa kolom waktu.',
    },

    # ── Lapis 2: MSSQL histori ──────────────────────────────────────────────
    {
        'fitur': 'Trend per pembangkit, Respons Pembangkit (MW)',
        'lapis': MSSQL, 'sumber': 'dbo.HIS_MEAS_KIT',
        'kolom_waktu': 'TIME',
        'diisi': 'SCADA (perekam histori)',
        'catatan': 'Armadanya TIDAK sama dengan KIT_REALTIME — lihat '
                   '`python manage.py cek_armada_kit`.',
    },
    {
        'fitur': 'Respons Pembangkit (frekuensi) — acuan',
        'lapis': MSSQL, 'sumber': 'dbo.SYS_FREQ_HIS',
        'kolom_waktu': 'TIME',
        'diisi': 'SCADA (perekam histori)',
        'catatan': 'Pernah berhenti 42 jam tanpa ketahuan. Ditambal SnapFreq + '
                   'SnapFreqRT lewat opsis/freq_history.py.',
    },

    # ── Lapis 3: PostgreSQL (snapshot hasil cron) ───────────────────────────
    {
        'fitur': 'Chart beban hari ini, Chart KIT Terpilih, Rangkuman, Ekspor beban pembangkit',
        'lapis': POSTGRES, 'sumber': 'opsis.SnapLive',
        'model': 'SnapLive', 'field_waktu': 'waktu',
        'hulu': 'dbo.KIT_REALTIME', 'diisi': 'cron collect_live (tiap menit)',
        'catatan': 'Tidak punya retensi — tumbuh terus (~440 MB + SnapUnit 1,1 GB).',
    },
    {
        'fitur': 'Detail per unit di balik SnapLive',
        'lapis': POSTGRES, 'sumber': 'opsis.SnapUnit',
        'model': 'SnapUnit', 'field_waktu': None, 'lewati_periksa': True,
        'hulu': 'dbo.KIT_REALTIME', 'diisi': 'cron collect_live (tiap menit)',
        'catatan': 'Tanpa retensi. Tabel terbesar di database (~1,1 GB).',
    },
    {
        'fitur': 'Chart frekuensi dashboard, ekspor frekuensi',
        'lapis': POSTGRES, 'sumber': 'opsis.SnapFreqRT',
        'model': 'SnapFreqRT', 'field_waktu': 'waktu',
        'hulu': 'dbo.SYS_FREQ_RT', 'diisi': 'cron collect_freq_rt (tiap menit)',
        'catatan': 'Retensi 30 hari. Pakai --loop --interval 1 agar 1 sampel/detik.',
    },
    {
        'fitur': 'Penambal riwayat frekuensi saat MSSQL tak terjangkau',
        'lapis': POSTGRES, 'sumber': 'opsis.SnapFreq',
        'model': 'SnapFreq', 'field_waktu': 'waktu',
        'hulu': 'dbo.SYS_FREQ_HIS', 'diisi': 'cron collect_freq (tiap menit)',
        'catatan': 'Retensi 30 hari. Ikut berhenti bila SYS_FREQ_HIS berhenti.',
    },
    {
        'fitur': 'Frekuensi per area (riwayat)',
        'lapis': POSTGRES, 'sumber': 'opsis.SnapFreqArea',
        'model': 'SnapFreqArea', 'field_waktu': 'waktu',
        'hulu': 'dbo.TRANS_*_RT', 'diisi': 'cron collect_freq (tiap menit)',
        'catatan': '',
    },
    {
        'fitur': 'Chart beban trafo 24 jam',
        'lapis': POSTGRES, 'sumber': 'opsis.SnapTrafo',
        'model': 'SnapTrafo', 'field_waktu': 'waktu',
        'hulu': 'dbo.ALL_TRANS_DATA', 'diisi': 'cron collect_trafo (tiap menit)',
        'catatan': 'Tidak punya retensi.',
    },

    # ── Lapis 4: sumber luar (spreadsheet / integrasi) ───────────────────────
    {
        'fitur': 'Prediksi beban (chart & halaman analitik)',
        'lapis': LUAR, 'sumber': 'opsis.PrakiraanBeban',
        'model': 'PrakiraanBeban', 'field_waktu': None, 'lewati_periksa': True,
        'hulu': 'Dashboard ROH Sulbagsel (.xlsx di Drive)',
        'diisi': 'n8n → POST /api/v1/prakiraan-beban/',
        'catatan': 'Grid 30 menit. Baris hari lampau tidak boleh dihapus — dipakai '
                   'menghitung akurasi prakiraan vs realisasi.',
    },
    {
        'fitur': 'HOP — Hari Operasi (stok bahan bakar)',
        'lapis': LUAR, 'sumber': 'opsis.HopSnapshot',
        'model': 'HopSnapshot', 'field_waktu': None, 'lewati_periksa': True,
        'hulu': 'spreadsheet HOP',
        'diisi': 'n8n / unggah manual',
        'catatan': '',
    },
    {
        'fitur': 'EWS Defense Scheme — nilai ukur per titik',
        'lapis': MSSQL, 'sumber': 'bebas (TitikEWS.sumber_tabel)',
        'kolom_waktu': None, 'lewati_periksa': True,
        'diisi': 'dipetakan per titik dari site admin',
        'catatan': 'Tabel & kolomnya ditentukan admin per titik, tidak di-hardcode.',
    },
]


def _status_dari_waktu(waktu):
    """Klasifikasi kesegaran: segar / telat / mati."""
    if waktu is None:
        return 'kosong', None
    if timezone.is_naive(waktu):
        waktu = timezone.make_aware(waktu)
    selisih = timezone.now() - waktu
    menit = selisih.total_seconds() / 60
    if menit <= SEGAR_MENIT:
        return 'segar', selisih
    if menit <= TELAT_JAM * 60:
        return 'telat', selisih
    return 'mati', selisih


def _periksa_mssql(entri):
    from opsis import mssql
    from django.conf import settings
    if not getattr(settings, 'MSSQL_HOST', ''):
        return {'status': 'takterjangkau', 'waktu': None, 'pesan': 'MSSQL belum dikonfigurasi'}
    kolom = entri.get('kolom_waktu')
    if not kolom:
        return {'status': 'tanpa_waktu', 'waktu': None,
                'pesan': 'Tabel tanpa kolom waktu — kesegaran tidak bisa diperiksa langsung'}
    tabel = entri['sumber']
    if not mssql._TABLE_RE.match(tabel) or not mssql._COLUMN_RE.match(kolom):
        return {'status': 'galat', 'waktu': None, 'pesan': 'Nama tabel/kolom tidak valid'}
    conn = None
    try:
        conn = mssql._get_connection()
        cur = conn.cursor()
        cur.execute(f'SELECT MAX({kolom}) FROM {tabel} WITH (NOLOCK)')
        waktu = cur.fetchone()[0]
        if entri.get('waktu_andal') is False:
            # Kolomnya ada tapi tidak dipelihara — nilainya boleh ditampilkan
            # sebagai keterangan, TAPI tidak boleh dipakai menyimpulkan sumber
            # ini mati. KIT_REALTIME nyata-nyata hidup meski DATE-nya 2 hari lalu.
            return {'status': 'tak_andal', 'waktu': waktu, 'selisih': None,
                    'pesan': f'Kolom {kolom} tidak dipelihara — bukan penanda kesegaran'}
        status, selisih = _status_dari_waktu(waktu)
        return {'status': status, 'waktu': waktu, 'selisih': selisih, 'pesan': ''}
    except Exception as e:
        logger.warning('sumber_data: %s gagal diperiksa: %s', tabel, e)
        return {'status': 'galat', 'waktu': None, 'pesan': str(e)[:120]}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _periksa_postgres(entri):
    from django.apps import apps
    try:
        Model = apps.get_model('opsis', entri['model'])
        field = entri.get('field_waktu')
        if not field:
            return {'status': 'tanpa_waktu', 'waktu': None,
                    'pesan': f'{Model.objects.count()} baris'}
        obj = Model.objects.order_by('-' + field).values_list(field, flat=True).first()
        status, selisih = _status_dari_waktu(obj)
        return {'status': status, 'waktu': obj, 'selisih': selisih, 'pesan': ''}
    except Exception as e:
        logger.warning('sumber_data: model %s gagal diperiksa: %s', entri.get('model'), e)
        return {'status': 'galat', 'waktu': None, 'pesan': str(e)[:120]}


def periksa_semua(dengan_mssql=True):
    """
    Peta sumber data + status kesegaran tiap sumber.

    dengan_mssql=False melewati seluruh query MSSQL (untuk halaman yang hanya
    ingin menampilkan petanya, atau saat historian sedang tidak terjangkau).
    """
    hasil = []
    for entri in sorted(SUMBER, key=lambda e: LAPIS_URUT.get(e['lapis'], 9)):
        baris = dict(entri)
        if entri.get('lewati_periksa'):
            baris['periksa'] = {'status': 'tanpa_waktu', 'waktu': None,
                                'pesan': 'Tidak diperiksa otomatis'}
        elif entri['lapis'] == MSSQL:
            baris['periksa'] = (_periksa_mssql(entri) if dengan_mssql else
                                {'status': 'dilewati', 'waktu': None, 'pesan': ''})
        elif entri.get('model'):
            baris['periksa'] = _periksa_postgres(entri)
        else:
            baris['periksa'] = {'status': 'tanpa_waktu', 'waktu': None, 'pesan': ''}
        hasil.append(baris)
    return hasil


def ringkas(hasil):
    """Hitungan per status, untuk kartu ringkasan di atas tabel."""
    n = {}
    for b in hasil:
        s = b['periksa']['status']
        n[s] = n.get(s, 0) + 1
    return n
