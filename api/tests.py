"""
API eksternal — penguncian per jenis data, dan isi tiap endpoint baca.

Ditempatkan di `api/tests.py` walau `api` bukan app Django: test runner Django
menemukan tes lewat discovery dari direktori proyek, bukan dari INSTALLED_APPS.
Tes beban KTT yang lebih lama tinggal di `opsis/tests.py`
(`ApiEksternalBebanKttTest`) dan sengaja dibiarkan di sana — yang dijaganya
adalah janji bahwa nama konsumennya sama dengan halaman OPSIS.
"""
import datetime

from django.test import TestCase
from django.urls import NoReverseMatch, resolve, reverse
from django.utils import timezone

from api import registry
from devices.models import DatasetApi, KunciApi
from logsheet.models import LogsheetNilai, LogsheetTitik
from opsis import cache as opsis_cache
from opsis import mssql
from opsis.models import Pembangkit, SnapFreqRT, SnapLive, SnapTrafo, Trafo


def _kunci(nama, *kode, aktif=True):
    """Kunci API yang diberi izin atas `kode`, dan datanya dibuka."""
    DatasetApi.sinkron()
    k = KunciApi.objects.create(nama=nama, aktif=aktif)
    for c in kode:
        DatasetApi.objects.filter(kode=c).update(aktif=True)
        k.dataset.add(DatasetApi.objects.get(kode=c))
    return k


def _hdr(k):
    return {'x-api-key': k.kunci}


def _isi_id(path):
    """Path registry berpola `<id>` (endpoint detail) → path yang bisa dibuka.

    Id-nya sengaja tidak ada di database: yang diuji di sini penjaga izinnya,
    jadi 404 "tidak ditemukan" sudah membuktikan permintaan lolos dekorator."""
    from fasop.hashids_helper import encode
    return path.replace('<id>', encode(987654))


# ═══════════════════════════════════════════════════════════════════════════
#  Registry & sakelar admin
# ═══════════════════════════════════════════════════════════════════════════
class RegistryDatasetTest(TestCase):

    def test_setiap_data_di_registry_punya_endpoint_yang_benar_ada(self):
        """
        Registry menjanjikan path tertentu ke konsumen luar (lewat halaman
        admin dan docs/API_EKSTERNAL.md). Path yang salah ketik di sana tidak
        menimbulkan error apa pun — ia hanya membuat admin memberi tahu
        konsumen alamat yang membalas 404.
        """
        for entri in registry.SEMUA:
            for path in entri['endpoint']:
                with self.subTest(kode=entri['kode'], path=path):
                    self.assertTrue(resolve(_isi_id(path)), path)

    def test_setiap_endpoint_dijaga_kode_data_yang_terdaftar(self):
        """
        Dekorator dipasang dengan kode data sebagai string. Salah ketik di sana
        menghasilkan endpoint yang SELALU 403 (kode tak dikenal = ditutup) —
        gejala yang terbaca seperti izin admin yang kurang, bukan seperti bug.
        """
        DatasetApi.sinkron()
        k = KunciApi.objects.create(nama='Punya semua izin')
        DatasetApi.objects.update(aktif=True)
        k.dataset.set(DatasetApi.objects.all())

        for entri in registry.SEMUA:
            for path in entri['endpoint']:
                with self.subTest(path=path):
                    r = self.client.get(_isi_id(path), headers=_hdr(k))
                    self.assertNotEqual(
                        r.status_code, 403,
                        f'{path} menolak kunci yang sudah diberi SEMUA izin — '
                        f'kode data di dekoratornya kemungkinan tidak ada di registry.'
                    )

    def test_sinkron_membuat_baris_dalam_keadaan_tertutup(self):
        DatasetApi.objects.all().delete()
        n = DatasetApi.sinkron()
        self.assertEqual(n, len(registry.SEMUA_KODE))
        self.assertFalse(DatasetApi.objects.filter(aktif=True).exists())

    def test_sinkron_idempotent_dan_tidak_menyentuh_keputusan_lama(self):
        DatasetApi.sinkron()
        DatasetApi.objects.filter(kode='frekuensi').update(aktif=True)
        self.assertEqual(DatasetApi.sinkron(), 0)
        self.assertTrue(DatasetApi.objects.get(kode='frekuensi').aktif)

    def test_kode_yang_hilang_dari_registry_ditandai_tidak_dikenal(self):
        """Izin basi harus terlihat di admin, bukan diam-diam hilang."""
        basi = DatasetApi.objects.create(kode='data_lama_yang_dihapus')
        self.assertFalse(basi.terdaftar)
        self.assertIn('tidak dikenal', basi.nama)


# ═══════════════════════════════════════════════════════════════════════════
#  Penguncian: siapa boleh membaca data apa
# ═══════════════════════════════════════════════════════════════════════════
class IzinDataTest(TestCase):

    def setUp(self):
        self.url = reverse('api:opsis_frekuensi')
        self.kunci = _kunci('UP2D', 'frekuensi')

    def test_tanpa_header_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_kunci_asing_403(self):
        r = self.client.get(self.url, headers={'x-api-key': 'bukan-kunci'})
        self.assertEqual(r.status_code, 403)

    def test_kunci_baru_lahir_tanpa_izin(self):
        """
        Data baru tidak boleh diam-diam ikut terkirim ke konsumen yang sudah
        ada, dan kunci baru tidak boleh langsung bisa membaca segalanya.
        """
        k = KunciApi.objects.create(nama='Konsumen baru')
        self.assertEqual(list(k.dataset.all()), [])
        r = self.client.get(self.url, headers=_hdr(k))
        self.assertEqual(r.status_code, 403)

    def test_data_ditutup_menolak_walau_kunci_punya_izin(self):
        DatasetApi.objects.filter(kode='frekuensi').update(aktif=False)
        r = self.client.get(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 403)
        self.assertIn('tidak dibuka', r.json()['message'])

    def test_pesan_membedakan_data_ditutup_dari_izin_kurang(self):
        """
        Keduanya 403 tapi tindakannya berbeda, dan yang menerima tidak bisa
        melihat admin FASOP. Pesan yang sama untuk keduanya berarti setiap
        keluhan harus dijawab dengan membuka log server.
        """
        lain = _kunci('Tanpa izin frekuensi', 'logsheet')
        pesan_izin = self.client.get(self.url, headers=_hdr(lain)).json()['message']

        DatasetApi.objects.filter(kode='frekuensi').update(aktif=False)
        pesan_tutup = self.client.get(self.url, headers=_hdr(self.kunci)).json()['message']

        self.assertNotEqual(pesan_izin, pesan_tutup)
        self.assertIn('tidak diizinkan', pesan_izin)

    def test_izin_satu_data_tidak_membuka_data_lain(self):
        r = self.client.get(reverse('api:logsheet_pembebanan'), headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 403)

    def test_kunci_global_env_ditolak(self):
        with self.settings(API_KEY='kunci-global-yang-boleh-menulis'):
            r = self.client.get(self.url,
                                headers={'x-api-key': 'kunci-global-yang-boleh-menulis'})
        self.assertEqual(r.status_code, 403)

    def test_dekorator_tanpa_kode_data_ditolak_saat_impor(self):
        """
        @require_kunci_baca tanpa kode (bentuk lamanya) akan menghasilkan
        endpoint yang tidak menjaga apa pun. Lebih baik meledak saat modulnya
        dimuat daripada diam-diam melayani semua orang.
        """
        from api.auth import require_kunci_baca
        with self.assertRaises(TypeError):
            require_kunci_baca(lambda request: None)

    def test_boleh_menuntut_kedua_syarat(self):
        self.assertTrue(self.kunci.boleh('frekuensi'))
        DatasetApi.objects.filter(kode='frekuensi').update(aktif=False)
        self.assertFalse(self.kunci.boleh('frekuensi'))


# ═══════════════════════════════════════════════════════════════════════════
#  Frekuensi sistem
# ═══════════════════════════════════════════════════════════════════════════
class FrekuensiEndpointTest(TestCase):

    def setUp(self):
        self.url   = reverse('api:opsis_frekuensi')
        self.kunci = _kunci('UP2D', 'frekuensi')

        # Historian dimatikan supaya tes tidak menyentuh jaringan; deretnya
        # datang dari SnapFreqRT, jalur tambalan yang justru paling perlu diuji.
        asli = mssql.get_freq_range
        self.addCleanup(lambda: setattr(mssql, 'get_freq_range', asli))
        mssql.get_freq_range = lambda t0, t1: []

        self.t0 = timezone.localtime().replace(microsecond=0) - datetime.timedelta(minutes=5)
        SnapFreqRT.objects.bulk_create([
            SnapFreqRT(waktu=self.t0 + datetime.timedelta(seconds=i), hz=50.0 + i / 100)
            for i in range(3)
        ])

    def test_deret_dan_satuan(self):
        r = self.client.get(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['satuan'], 'Hz')
        self.assertEqual(data['jumlah'], 3)
        self.assertEqual([d['hz'] for d in data['deret']], [50.0, 50.01, 50.02])

    def test_menyebut_berapa_detik_ditambal_dari_mana(self):
        """
        Konsumen yang memakai deret ini untuk analisis berhak tahu bagian mana
        yang bukan dari historian — bukan cuma menerima garis yang mulus.
        """
        data = self.client.get(self.url, headers=_hdr(self.kunci)).json()
        self.assertEqual(data['sumber'], 'postgres')
        self.assertEqual(data['sumber_rincian']['historian'], 0)
        self.assertEqual(data['sumber_rincian']['postgres'], 3)
        self.assertIn('SnapFreqRT', data['sumber_teks'])

    def test_rentang_sepi_dibalas_200_bukan_503(self):
        """
        "Apakah datanya memang tidak ada" adalah pertanyaan yang sah, dan 503
        tidak menjawabnya. Beda dari endpoint terkini yang kekosongannya selalu
        berarti rusak.
        """
        r = self.client.get(self.url, {'dari': '2020-01-01T00:00',
                                       'sampai': '2020-01-01T01:00'},
                            headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['jumlah'], 0)
        self.assertEqual(r.json()['sumber'], 'kosong')

    def test_rentang_terlalu_lebar_ditolak(self):
        r = self.client.get(self.url, {'dari': '2026-09-01T00:00',
                                       'sampai': '2026-09-03T00:00'},
                            headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 400)
        self.assertIn('terlalu lebar', r.json()['message'])

    def test_waktu_salah_format_ditolak_dengan_contoh(self):
        r = self.client.get(self.url, {'dari': 'kemarin'}, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 400)
        self.assertIn('ISO', r.json()['message'])

    def test_dari_setelah_sampai_ditolak(self):
        r = self.client.get(self.url, {'dari': '2026-09-02T00:00',
                                       'sampai': '2026-09-01T00:00'},
                            headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 400)


# ═══════════════════════════════════════════════════════════════════════════
#  Beban pembangkit — terkini
# ═══════════════════════════════════════════════════════════════════════════
class BebanPembangkitTerkiniTest(TestCase):

    def setUp(self):
        opsis_cache._cache.clear()
        self.addCleanup(opsis_cache._cache.clear)

        self.url   = reverse('api:opsis_beban_pembangkit')
        self.kunci = _kunci('UP2D', 'beban_pembangkit')

        self.p = Pembangkit.objects.create(nama='PLTA Bakaru', kode='BAKARU',
                                           jenis='PLTA', kode_kit='BAKARU')

        asli_live  = mssql.get_live_data
        asli_reach = mssql.is_reachable
        self.addCleanup(lambda: setattr(mssql, 'get_live_data', asli_live))
        self.addCleanup(lambda: setattr(mssql, 'is_reachable', asli_reach))
        mssql.is_reachable = lambda: True
        mssql.get_live_data = lambda daftar, spek=None: {
            'data': {'BAKARU': {
                'mw': 61.2, 'mvar': 12.5, 'frekuensi': 50.01, 'timestamp': None,
                'units': [{'nama': 'UNIT1', 'mw': 30.6, 'mvar': 6.25},
                          {'nama': 'UNIT2', 'mw': 30.6, 'mvar': 6.25}],
            }},
            'frekuensi_sistem': 50.01,
        }

    def test_bentuk_balasan(self):
        r = self.client.get(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['jumlah'], 1)
        self.assertEqual(data['total_mw'], 61.2)
        self.assertEqual(data['frekuensi_sistem'], 50.01)
        kit = data['pembangkit'][0]
        self.assertEqual(kit['kode'], 'BAKARU')
        self.assertEqual(len(kit['unit']), 2)

    def test_unit_nol_menghilangkan_rincian_unit(self):
        data = self.client.get(self.url, {'unit': '0'}, headers=_hdr(self.kunci)).json()
        self.assertNotIn('unit', data['pembangkit'][0])

    def test_penanda_data_diragukan_ikut_keluar(self):
        """
        Kalau ruang kontrol sendiri sudah meragukan angka sebuah pembangkit,
        konsumen yang menyalinnya ke laporan berhak tahu — menyembunyikannya
        membuat angka ragu terlihat sama meyakinkan dengan angka yang benar.
        """
        self.p.data_tidak_sesuai = True
        self.p.data_keterangan = 'Telemetri unit 2 menyimpang'
        self.p.save(update_fields=['data_tidak_sesuai', 'data_keterangan'])
        opsis_cache._cache.clear()

        kit = self.client.get(self.url, headers=_hdr(self.kunci)).json()['pembangkit'][0]
        self.assertTrue(kit['diragukan'])
        self.assertIn('menyimpang', kit['keterangan'])

    def test_historian_mati_balas_503_bukan_mw_nol(self):
        mssql.is_reachable = lambda: False
        opsis_cache._cache.clear()
        r = self.client.get(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 503)
        self.assertNotIn('total_mw', r.json())


# ═══════════════════════════════════════════════════════════════════════════
#  Beban pembangkit — riwayat
# ═══════════════════════════════════════════════════════════════════════════
class BebanPembangkitRiwayatTest(TestCase):

    def setUp(self):
        self.url   = reverse('api:opsis_beban_pembangkit_riwayat')
        self.kunci = _kunci('UP2D', 'beban_pembangkit')

        self.a = Pembangkit.objects.create(nama='PLTA Bakaru', kode='BAKARU', jenis='PLTA')
        self.b = Pembangkit.objects.create(nama='PLTU Barru', kode='BARRU', jenis='PLTU')

        self.akhir = timezone.localtime().replace(second=0, microsecond=0)
        SnapLive.objects.bulk_create([
            SnapLive(pembangkit=p, waktu=self.akhir - datetime.timedelta(minutes=i),
                     mw=10.0 + i, mvar=1.0, frekuensi=50.0)
            for p in (self.a, self.b) for i in range(1, 4)
        ])

    def test_deret_per_pembangkit(self):
        r = self.client.get(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['jumlah'], 6)
        self.assertEqual({d['kode'] for d in data['pembangkit']}, {'BAKARU', 'BARRU'})

    def test_saring_per_kode(self):
        data = self.client.get(self.url, {'kode': 'bakaru'},
                               headers=_hdr(self.kunci)).json()
        self.assertEqual([d['kode'] for d in data['pembangkit']], ['BAKARU'])
        self.assertEqual(data['jumlah'], 3)

    def test_kode_tak_dikenal_404_bukan_daftar_kosong(self):
        """Daftar kosong terbaca seperti "tidak ada beban", bukan "kode salah"."""
        r = self.client.get(self.url, {'kode': 'TIDAKADA'}, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 404)

    def test_batas_rentang_eksklusif_di_ujung_atas(self):
        """
        Filternya waktu__gte/waktu__lt (bukan lookup __date, yang mematikan
        indeks). Titik tepat di `sampai` karena itu TIDAK ikut — diuji supaya
        batasnya tidak diam-diam berubah jadi inklusif saat filternya disentuh.
        """
        dari   = (self.akhir - datetime.timedelta(minutes=3)).isoformat()
        sampai = (self.akhir - datetime.timedelta(minutes=1)).isoformat()
        data = self.client.get(self.url, {'dari': dari, 'sampai': sampai, 'kode': 'BAKARU'},
                               headers=_hdr(self.kunci)).json()
        self.assertEqual(data['jumlah'], 2)     # menit -3 dan -2, bukan -1

    def test_rentang_lebih_dari_batas_ditolak(self):
        from opsis import beban_kit
        dari = (self.akhir - datetime.timedelta(days=beban_kit.MAKS_HARI_RIWAYAT + 1))
        r = self.client.get(self.url, {'dari': dari.isoformat()}, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 400)

    def test_tetap_menjawab_saat_historian_mati(self):
        """Sumbernya PostgreSQL — justru ini gunanya dibanding endpoint terkini."""
        asli = mssql.is_reachable
        self.addCleanup(lambda: setattr(mssql, 'is_reachable', asli))
        mssql.is_reachable = lambda: False
        r = self.client.get(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['jumlah'], 6)


# ═══════════════════════════════════════════════════════════════════════════
#  Logsheet pembebanan
# ═══════════════════════════════════════════════════════════════════════════
class LogsheetPembebananTest(TestCase):

    def setUp(self):
        self.url   = reverse('api:logsheet_pembebanan')
        self.kunci = _kunci('UP2D', 'logsheet')
        self.tanggal = timezone.localdate()

        self.kit = LogsheetTitik.objects.create(
            kategori='kit', besaran='mw', key='BAKARU-1:mw', nama='BAKARU U1',
            mssql_tabel='dbo.KIT_REALTIME', mssql_kolom='UNIT1_P',
            mssql_keykol='KIT', mssql_key='BAKARU',
            sheet='KIT_MW', baris=7, kol0=6,
        )
        # Titik tanpa posisi ekspor: disaring feed internal karena tak ada sel
        # untuk diisi, tapi nilainya tetap data yang sah bagi konsumen luar.
        self.bus = LogsheetTitik.objects.create(
            kategori='busbar', besaran='volt', key='GIPARE:volt', nama='GI Pare 150kV',
        )
        for slot, nilai in ((0, 30.5), (1, 31.25)):
            LogsheetNilai.objects.create(
                titik=self.kit, tanggal=self.tanggal, slot=slot,
                waktu=timezone.now(), nilai=nilai)
        LogsheetNilai.objects.create(
            titik=self.bus, tanggal=self.tanggal, slot=0,
            waktu=timezone.now(), nilai=151.2)

    def test_bentuk_balasan_dan_label_jam(self):
        r = self.client.get(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['jumlah_titik'], 2)
        self.assertEqual(data['jumlah_nilai'], 3)
        kit = next(t for t in data['titik'] if t['key'] == 'BAKARU-1:mw')
        self.assertEqual(kit['satuan'], 'MW')
        self.assertEqual([n['waktu'] for n in kit['nilai']], ['00:30', '01:00'])

    def test_titik_tanpa_posisi_ekspor_tetap_ikut(self):
        data = self.client.get(self.url, headers=_hdr(self.kunci)).json()
        self.assertIn('GIPARE:volt', [t['key'] for t in data['titik']])

    def test_tidak_membocorkan_posisi_excel_maupun_pemetaan_mssql(self):
        """
        Posisi sel adalah urusan berkas ekspor FASOP dan bisa berubah kapan saja
        tanpa mengubah arti datanya; nama tabel/kolom historian adalah rincian
        infrastruktur SCADA. Keduanya tidak ada gunanya di luar, dan sekali
        terkirim akan dipakai konsumen lalu jadi kontrak tak sengaja.
        """
        isi = self.client.get(self.url, headers=_hdr(self.kunci)).content.decode()
        for bocor in ('KIT_MW', 'dbo.KIT_REALTIME', 'UNIT1_P', 'kol0', 'baris'):
            self.assertNotIn(bocor, isi, bocor)

    def test_saring_kategori_dan_besaran(self):
        data = self.client.get(self.url, {'kategori': 'kit'},
                               headers=_hdr(self.kunci)).json()
        self.assertEqual([t['key'] for t in data['titik']], ['BAKARU-1:mw'])

        data = self.client.get(self.url, {'besaran': 'volt'},
                               headers=_hdr(self.kunci)).json()
        self.assertEqual([t['key'] for t in data['titik']], ['GIPARE:volt'])

    def test_kategori_tak_dikenal_menyebut_pilihannya(self):
        r = self.client.get(self.url, {'kategori': 'pembangkit'}, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 400)
        self.assertIn('busbar', r.json()['message'])

    def test_slot_latest_mengambil_slot_terisi_terakhir(self):
        data = self.client.get(self.url, {'slot': 'latest'}, headers=_hdr(self.kunci)).json()
        self.assertEqual(data['slot'], 1)
        self.assertEqual(data['waktu_slot'], '01:00')
        self.assertEqual(data['jumlah_nilai'], 1)

    def test_slot_di_luar_jangkauan_ditolak(self):
        r = self.client.get(self.url, {'slot': '48'}, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 400)

    def test_tanggal_tanpa_data_tetap_200(self):
        """Yang bertanya biasanya justru ingin tahu apakah datanya memang kosong."""
        r = self.client.get(self.url, {'tanggal': '2020-01-01'}, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['jumlah_nilai'], 0)
        self.assertEqual(r.json()['jumlah_titik'], 2)   # cakupan tetap terlihat

    def test_tanggal_salah_format_ditolak(self):
        r = self.client.get(self.url, {'tanggal': '21-09-2026'}, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 400)

    def test_titik_nonaktif_tidak_ikut(self):
        self.bus.aktif = False
        self.bus.save(update_fields=['aktif'])
        data = self.client.get(self.url, headers=_hdr(self.kunci)).json()
        self.assertEqual([t['key'] for t in data['titik']], ['BAKARU-1:mw'])


# ═══════════════════════════════════════════════════════════════════════════
#  Jejak pemakaian & metode
# ═══════════════════════════════════════════════════════════════════════════
class JejakPemakaianTest(TestCase):

    def setUp(self):
        self.url   = reverse('api:logsheet_pembebanan')
        self.kunci = _kunci('UP2D', 'logsheet')
        LogsheetTitik.objects.create(kategori='kit', besaran='mw', key='X:mw')

    def test_metode_selain_get_ditolak(self):
        r = self.client.post(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 405)

    def test_pemakaian_dicatat_lalu_direm(self):
        self.client.get(self.url, headers=_hdr(self.kunci))
        self.kunci.refresh_from_db()
        pertama = self.kunci.terakhir_dipakai
        self.assertIsNotNone(pertama)

        self.client.get(self.url, headers=_hdr(self.kunci))
        self.kunci.refresh_from_db()
        self.assertEqual(self.kunci.terakhir_dipakai, pertama)

    def test_penolakan_tidak_mencatat_pemakaian(self):
        """Kunci yang ditolak tidak boleh meninggalkan jejak "terakhir dipakai" —
        di admin itu terbaca seolah integrasinya berjalan normal."""
        lain = _kunci('Tanpa izin', 'frekuensi')
        self.client.get(self.url, headers=_hdr(lain))
        lain.refresh_from_db()
        self.assertIsNone(lain.terakhir_dipakai)


class UrlTerdaftarTest(TestCase):

    def test_semua_endpoint_punya_nama_url(self):
        for nama in ('opsis_beban_ktt', 'opsis_beban_pembangkit',
                     'opsis_beban_pembangkit_riwayat', 'opsis_frekuensi',
                     'logsheet_pembebanan', 'fasop_status_monitor',
                     'fasop_pemeliharaan', 'fasop_peralatan', 'fasop_aset',
                     'fasop_lokasi', 'fasop_pemeliharaan_riwayat'):
            with self.subTest(nama=nama):
                try:
                    reverse(f'api:{nama}')
                except NoReverseMatch:                      # pragma: no cover
                    self.fail(f'api:{nama} tidak terdaftar di api/urls.py')


# ═══════════════════════════════════════════════════════════════════════════
#  Halaman admin tempat izinnya diatur
# ═══════════════════════════════════════════════════════════════════════════
class HalamanAdminIzinTest(TestCase):
    """
    Seluruh pengaturannya hidup di site admin, jadi halaman yang gagal dirender
    sama artinya dengan fitur yang tidak ada. Tes status code saja sudah
    menangkap kesalahan format_html/kolom yang tidak terlihat dari kode.
    """

    def setUp(self):
        from django.contrib.auth.models import User
        self.admin = User.objects.create_superuser('admin-api', 'a@b.c', 'rahasia-uji-123')
        profile = getattr(self.admin, 'profile', None)
        if profile:
            profile.force_password_change = False
            profile.save(update_fields=['force_password_change'])
        self.client.force_login(self.admin)

    def test_daftar_data_api_menyinkronkan_registry(self):
        DatasetApi.objects.all().delete()
        r = self.client.get('/secure-panel/devices/datasetapi/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(DatasetApi.objects.count(), len(registry.SEMUA_KODE))

    def test_baris_data_api_tidak_bisa_ditambah_manual(self):
        """Kode yang diketik manual melahirkan izin yang tidak menjaga apa pun."""
        self.assertEqual(self.client.get('/secure-panel/devices/datasetapi/add/').status_code, 403)

    def test_halaman_ubah_data_api_terbuka(self):
        DatasetApi.sinkron()
        ds = DatasetApi.objects.get(kode='frekuensi')
        r = self.client.get(f'/secure-panel/devices/datasetapi/{ds.pk}/change/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'freq_history', r.content)       # rincian sumbernya ikut tampil

    def test_daftar_kunci_menampilkan_izinnya(self):
        k = _kunci('UP2D', 'frekuensi')
        r = self.client.get('/secure-panel/devices/kunciapi/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Frekuensi sistem', r.content)
        self.assertNotIn(k.kunci.encode(), r.content)   # kunci tetap tersamar

    def test_kunci_tanpa_izin_terbaca_di_daftar(self):
        """
        Kunci tanpa izin bukan kesalahan, tapi ia juga tidak bisa membaca apa
        pun — kalau itu tidak terbaca dari daftar, keluhannya akan dikira
        integrasi yang rusak.
        """
        KunciApi.objects.create(nama='Belum diatur')
        r = self.client.get('/secure-panel/devices/kunciapi/')
        self.assertIn('belum diberi izin', r.content.decode())

    def test_halaman_ubah_kunci_terbuka(self):
        k = _kunci('UP2D', 'logsheet')
        r = self.client.get(f'/secure-panel/devices/kunciapi/{k.pk}/change/')
        self.assertEqual(r.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════
#  Beban trafo — terkini
# ═══════════════════════════════════════════════════════════════════════════
class BebanTrafoTerkiniTest(TestCase):

    def setUp(self):
        opsis_cache._cache.clear()
        self.addCleanup(opsis_cache._cache.clear)

        self.url   = reverse('api:opsis_beban_trafo')
        self.kunci = _kunci('UP2D', 'beban_trafo')

        Trafo.objects.create(site='GI SUNGGUMINASA', bay='TRF52-1')
        Trafo.objects.create(site='GI SUNGGUMINASA', bay='TRF52-2')
        Trafo.objects.create(site='GITET SIDRAP',    bay='TRF65-1')

        asli_d     = mssql.get_beban_trafo
        asli_i     = mssql.get_beban_trafo_ibt
        asli_reach = mssql.is_reachable
        self.addCleanup(lambda: setattr(mssql, 'get_beban_trafo', asli_d))
        self.addCleanup(lambda: setattr(mssql, 'get_beban_trafo_ibt', asli_i))
        self.addCleanup(lambda: setattr(mssql, 'is_reachable', asli_reach))

        mssql.is_reachable = lambda: True
        mssql.get_beban_trafo = lambda: [
            {'site': 'GI SUNGGUMINASA', 'bay': 'TRF52-1', 'p': 20.0, 'q': 3.0, 'v': 20.1, 'i': 600.0},
            {'site': 'GI SUNGGUMINASA', 'bay': 'TRF52-2', 'p': -5.0, 'q': 1.0, 'v': 20.0, 'i': 150.0},
        ]
        mssql.get_beban_trafo_ibt = lambda: [
            {'site': 'GITET SIDRAP', 'bay': 'TRF65-1', 'p': 80.0, 'q': 9.0, 'v': 150.0, 'i': 320.0},
        ]

    def test_bentuk_balasan_dikelompokkan_per_gi(self):
        r = self.client.get(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['jenis'], 'distribusi')
        self.assertEqual(data['jumlah'], 2)
        self.assertEqual([g['site'] for g in data['gi']], ['GI SUNGGUMINASA'])
        self.assertEqual(len(data['gi'][0]['trafo']), 2)

    def test_nilai_per_trafo_apa_adanya_total_pakai_magnitudo(self):
        """
        Tanda minus pada P bermakna (arah aliran daya), jadi nilai per trafo
        tidak boleh di-abs(). Totalnya sebaliknya harus magnitudo — kalau
        dijumlahkan bertanda, 20 dan -5 jadi 15 dan GI terlihat lebih sepi
        daripada kenyataannya. Angka yang sama dengan kartu total di layar.
        """
        data = self.client.get(self.url, headers=_hdr(self.kunci)).json()
        p = {t['bay']: t['p'] for t in data['gi'][0]['trafo']}
        self.assertEqual(p['TRF52-2'], -5.0)
        self.assertEqual(data['total_mw'], 25.0)

    def test_jenis_ibt(self):
        data = self.client.get(self.url, {'jenis': 'ibt'}, headers=_hdr(self.kunci)).json()
        self.assertEqual(data['jenis'], 'ibt')
        self.assertEqual([g['site'] for g in data['gi']], ['GITET SIDRAP'])

    def test_jenis_tak_dikenal_ditolak_bukan_diam_diam_jadi_distribusi(self):
        """
        Kalau jatuh ke bawaan, konsumen yang salah ketik menerima angka
        distribusi dan menyalinnya sebagai angka IBT tanpa pernah tahu.
        """
        r = self.client.get(self.url, {'jenis': 'IBT2'}, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 400)
        self.assertIn('tidak dikenal', r.json()['message'])

    def test_trafo_nonaktif_tidak_ikut(self):
        Trafo.objects.filter(bay='TRF52-2').update(aktif=False)
        opsis_cache._cache.clear()
        data = self.client.get(self.url, headers=_hdr(self.kunci)).json()
        self.assertEqual(data['jumlah'], 1)
        self.assertEqual(data['total_mw'], 20.0)

    def test_historian_mati_balas_503_bukan_mw_nol(self):
        mssql.is_reachable = lambda: False
        opsis_cache._cache.clear()
        r = self.client.get(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 503)
        self.assertNotIn('total_mw', r.json())


# ═══════════════════════════════════════════════════════════════════════════
#  Beban trafo — riwayat
# ═══════════════════════════════════════════════════════════════════════════
class BebanTrafoRiwayatTest(TestCase):

    def setUp(self):
        self.url   = reverse('api:opsis_beban_trafo_riwayat')
        self.kunci = _kunci('UP2D', 'beban_trafo')

        # Registry Trafo TIDAK pernah kosong di database tes: migrasi
        # 0015_trafo_override_wotu membuat barisnya sendiri (IBT GITET Wotu).
        # Endpoint riwayat membaca registry itu langsung — beda dari endpoint
        # terkini yang hanya memuat baris yang juga ada di MSSQL — jadi tanpa
        # dikosongkan dulu, assertion di sini ikut menghitung baris migrasi.
        Trafo.objects.all().delete()

        self.a   = Trafo.objects.create(site='GI SUNGGUMINASA', bay='TRF52-1')
        self.b   = Trafo.objects.create(site='GI PANAKKUKANG', bay='TRF52-9')
        self.ibt = Trafo.objects.create(site='GITET SIDRAP', bay='TRF65-1')

        self.akhir = timezone.localtime().replace(second=0, microsecond=0)
        SnapTrafo.objects.bulk_create([
            SnapTrafo(trafo=t, waktu=self.akhir - datetime.timedelta(minutes=i),
                      p=10.0 + i)
            for t in (self.a, self.b, self.ibt) for i in range(1, 4)
        ])

    def test_deret_per_trafo_hanya_jenis_yang_diminta(self):
        data = self.client.get(self.url, headers=_hdr(self.kunci)).json()
        self.assertEqual(data['jenis'], 'distribusi')
        self.assertEqual({d['bay'] for d in data['trafo']}, {'TRF52-1', 'TRF52-9'})
        self.assertEqual(data['jumlah'], 6)          # IBT tidak ikut

    def test_jenis_ibt_memilih_bay_yang_lain(self):
        data = self.client.get(self.url, {'jenis': 'ibt'}, headers=_hdr(self.kunci)).json()
        self.assertEqual([d['bay'] for d in data['trafo']], ['TRF65-1'])
        self.assertEqual(data['jumlah'], 3)

    def test_saring_per_site(self):
        data = self.client.get(self.url, {'site': 'gi panakkukang'},
                               headers=_hdr(self.kunci)).json()
        self.assertEqual([d['bay'] for d in data['trafo']], ['TRF52-9'])

    def test_site_tak_dikenal_404_bukan_daftar_kosong(self):
        r = self.client.get(self.url, {'site': 'GI TIDAK ADA'}, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 404)

    def test_batas_rentang_eksklusif_di_ujung_atas(self):
        """waktu__gte/waktu__lt, bukan lookup __date yang mematikan indeks."""
        dari   = (self.akhir - datetime.timedelta(minutes=3)).isoformat()
        sampai = (self.akhir - datetime.timedelta(minutes=1)).isoformat()
        data = self.client.get(self.url,
                               {'dari': dari, 'sampai': sampai, 'site': 'GI SUNGGUMINASA'},
                               headers=_hdr(self.kunci)).json()
        self.assertEqual(data['jumlah'], 2)          # menit -3 dan -2, bukan -1

    def test_rentang_lebih_dari_batas_ditolak(self):
        from opsis import trafo as trafo_io
        dari = self.akhir - datetime.timedelta(days=trafo_io.MAKS_HARI_RIWAYAT + 1)
        r = self.client.get(self.url, {'dari': dari.isoformat()}, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 400)

    def test_tetap_menjawab_saat_historian_mati(self):
        """Sumbernya PostgreSQL — justru ini gunanya dibanding endpoint terkini."""
        asli = mssql.is_reachable
        self.addCleanup(lambda: setattr(mssql, 'is_reachable', asli))
        mssql.is_reachable = lambda: False
        r = self.client.get(self.url, headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['jumlah'], 6)


# ═══════════════════════════════════════════════════════════════════════════
#  Angka API harus sama dengan angka layar OPSIS
# ═══════════════════════════════════════════════════════════════════════════
class TrafoSatuSumberTest(TestCase):
    """
    Halaman OPSIS dan API eksternal wajib memakai opsis/trafo.py yang sama.
    Kalau perhitungannya disalin, layar ruang kontrol dan spreadsheet pihak
    luar bisa menyebut angka berbeda untuk trafo yang sama — dan tidak ada
    yang tahu mana yang benar.
    """

    def setUp(self):
        opsis_cache._cache.clear()
        self.addCleanup(opsis_cache._cache.clear)

        Trafo.objects.create(site='GI SUNGGUMINASA', bay='TRF52-1')
        Trafo.objects.create(site='GI SUNGGUMINASA', bay='TRF52-2')

        asli_d     = mssql.get_beban_trafo
        asli_reach = mssql.is_reachable
        self.addCleanup(lambda: setattr(mssql, 'get_beban_trafo', asli_d))
        self.addCleanup(lambda: setattr(mssql, 'is_reachable', asli_reach))
        mssql.is_reachable = lambda: True
        mssql.get_beban_trafo = lambda: [
            {'site': 'GI SUNGGUMINASA', 'bay': 'TRF52-1', 'p': 20.0, 'q': 3.0, 'v': 20.1, 'i': 600.0},
            {'site': 'GI SUNGGUMINASA', 'bay': 'TRF52-2', 'p': -5.0, 'q': 1.0, 'v': 20.0, 'i': 150.0},
        ]

    def test_total_api_sama_dengan_total_halaman_opsis(self):
        from django.contrib.auth.models import User

        kunci = _kunci('UP2D', 'beban_trafo')
        luar = self.client.get(reverse('api:opsis_beban_trafo'),
                               headers=_hdr(kunci)).json()

        # force_login, bukan login() — AxesBackend menolak authenticate()
        # tanpa request. ForcePasswordChangeMiddleware juga harus dilucuti,
        # kalau tidak user baru dialihkan ke /ganti-password/ dan yang terbaca
        # halaman HTML, bukan JSON. Pola yang sama dengan tes di opsis/tests.py.
        user = User.objects.create_superuser('admin-trafo', 'a@b.c', 'rahasia-tes-123')
        profil = getattr(user, 'profile', None)
        if profil is not None:
            profil.force_password_change = False
            profil.save(update_fields=['force_password_change'])
        self.client.force_login(user)
        opsis_cache._cache.clear()
        dalam = self.client.get(reverse('opsis_api_beban_trafo')).json()

        self.assertEqual(luar['total_mw'], dalam['total_mw'])
        self.assertEqual(luar['gi'][0]['total_mw'],
                         dalam['site_totals']['GI SUNGGUMINASA'])


# ═══════════════════════════════════════════════════════════════════════════
#  Data FASOP — status monitor, pemeliharaan, peralatan
# ═══════════════════════════════════════════════════════════════════════════
class StatusMonitorTest(TestCase):

    def setUp(self):
        from device_mon.models import RTU, ZabbixHost

        self.kunci = _kunci('Bot WA', 'status_monitor')
        now = timezone.now()
        RTU.objects.create(nama='RTU-A', lokasi='GI A', state='UP')
        RTU.objects.create(nama='RTU-B', lokasi='GI B', state='DOWN',
                           state_sejak=now - datetime.timedelta(minutes=10))
        RTU.objects.create(nama='RTU-C', lokasi='GI C', state='DOWN',
                           state_sejak=now - datetime.timedelta(hours=3))
        # Nonaktif tidak ikut dihitung — sama dengan dashboard Device Monitor.
        RTU.objects.create(nama='RTU-MATI', state='DOWN', aktif=False)

        ZabbixHost.objects.create(zabbix_hostid='1', nama='Router OK', state='OK')
        ZabbixHost.objects.create(zabbix_hostid='2', nama='VoIP Mks', state='PROBLEM',
                                  severity='High', problem_name='Interface down',
                                  state_sejak=now)
        ZabbixHost.objects.create(zabbix_hostid='3', nama='Switch', state='PROBLEM',
                                  severity='Warning', problem_name='CPU tinggi',
                                  state_sejak=now)

    def _get(self):
        r = self.client.get(reverse('api:fasop_status_monitor'), headers=_hdr(self.kunci))
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_rtu_dihitung_dan_down_terlama_di_atas(self):
        rtu = self._get()['rtu']
        self.assertEqual((rtu['jumlah'], rtu['up'], rtu['down']), (3, 1, 2))
        self.assertEqual([r['nama'] for r in rtu['daftar_down']], ['RTU-C', 'RTU-B'])
        self.assertGreaterEqual(rtu['daftar_down'][0]['durasi_menit'], 180)

    def test_zabbix_memakai_penggolongan_yang_sama_dengan_dashboard(self):
        """High = problem, Warning = warning — ambang dari state_class(), bukan salinan."""
        z = self._get()['zabbix'][0]
        self.assertEqual((z['jumlah_host'], z['ok'], z['problem'], z['warning']), (3, 1, 1, 1))
        # Severity tertinggi dulu.
        self.assertEqual([h['nama'] for h in z['host_bermasalah']], ['VoIP Mks', 'Switch'])


class PemeliharaanEndpointTest(TestCase):

    def setUp(self):
        from devices.models import Device, DeviceType
        from jadwal.models import JadwalKunjungan
        from maintenance.models import Maintenance

        self.kunci = _kunci('Bot WA', 'pemeliharaan')
        jenis = DeviceType.objects.create(name='RTU')
        self.dev = Device.objects.create(nama='RTU-01', jenis=jenis, merk='SEL',
                                         lokasi='GI TELLO')
        Device.objects.create(nama='RTU-02', jenis=jenis, merk='SEL', lokasi='GI TELLO')

        def _m(status, tipe='Preventive', hari=5, **kw):
            return Maintenance.objects.create(
                device=self.dev, maintenance_type=tipe, status=status,
                date=timezone.make_aware(datetime.datetime(2026, 9, hari, 8, 0)), **kw)

        _m('Open')
        _m('Done', hari=6)
        _m('Open', tipe='Corrective', hari=7)
        # Soft-delete tidak boleh ikut terhitung di mana pun.
        _m('Open', hari=8, is_deleted=True)
        # Bulan lain — ikut daftar Open (keadaan SAAT INI) tapi tidak ikut rekap.
        Maintenance.objects.create(
            device=self.dev, maintenance_type='Preventive', status='Open',
            date=timezone.make_aware(datetime.datetime(2026, 8, 20, 8, 0)))

        JadwalKunjungan.objects.create(lokasi='GI TELLO', bulan_rencana=9, tahun_rencana=2026)

    def _get(self, **params):
        return self.client.get(reverse('api:fasop_pemeliharaan'), params,
                               headers=_hdr(self.kunci))

    def test_rekap_bulan_dan_soft_delete_dibuang(self):
        d = self._get(bulan='2026-09').json()
        self.assertEqual(d['rekap_bulan'], {
            'preventive': {'open': 1, 'done': 1},
            'corrective': {'open': 1, 'done': 0},
        })
        # 3 Open yang hidup: dua di September + satu di Agustus.
        self.assertEqual(d['open']['jumlah'], 3)

    def test_progres_jadwal_dari_get_progress(self):
        j = self._get(bulan='2026-09').json()['jadwal'][0]
        self.assertEqual(j['lokasi'], 'GI TELLO')
        self.assertEqual((j['jumlah_peralatan'], j['sudah_dipelihara']), (2, 1))
        self.assertEqual(j['progres_persen'], 50)

    def test_bulan_salah_ditolak(self):
        self.assertEqual(self._get(bulan='09-2026').status_code, 400)
        self.assertEqual(self._get(bulan='2026-13').status_code, 400)


class PeralatanEndpointTest(TestCase):

    def setUp(self):
        from devices.models import Device, DeviceType

        self.kunci = _kunci('Bot WA', 'peralatan')
        rtu = DeviceType.objects.create(name='RTU')
        plc = DeviceType.objects.create(name='PLC')
        Device.objects.create(nama='RTU-01', jenis=rtu, merk='SEL', lokasi='GI TELLO',
                              ip_address='10.1.2.3', serial_number='SN-RAHASIA',
                              tahun_operasi=2015)
        Device.objects.create(nama='PLC-01', jenis=plc, merk='ABB', lokasi='GI TELLO')
        Device.objects.create(nama='RTU-09', jenis=rtu, merk='SEL', lokasi='GI BONE')
        Device.objects.create(nama='RTU-HAPUS', jenis=rtu, merk='SEL', lokasi='GI TELLO',
                              is_deleted=True)

    def _get(self, **params):
        return self.client.get(reverse('api:fasop_peralatan'), params,
                               headers=_hdr(self.kunci))

    def test_tanpa_kata_kunci_ditolak(self):
        self.assertEqual(self._get().status_code, 400)

    def test_semua_kata_harus_cocok(self):
        d = self._get(q='tello rtu').json()
        self.assertEqual(d['cocok'], 'semua_kata')
        self.assertEqual([p['nama'] for p in d['peralatan']], ['RTU-01'])

    def test_jatuh_ke_sebagian_kata_bila_kosong(self):
        """Kata sisa dari kalimat ("tolong") tidak boleh membuat jawabannya kosong."""
        d = self._get(q='tolong bone').json()
        self.assertEqual(d['cocok'], 'sebagian_kata')
        self.assertEqual([p['nama'] for p in d['peralatan']], ['RTU-09'])

    def test_peralatan_terhapus_tidak_ikut(self):
        d = self._get(lokasi='tello').json()
        self.assertEqual(d['jumlah'], 2)
        self.assertEqual(d['per_jenis'], {'RTU': 1, 'PLC': 1})

    def test_rincian_infrastruktur_tidak_bocor(self):
        """IP & serial number tidak boleh keluar — tujuannya chat WhatsApp."""
        r = self._get(q='RTU-01')
        teks = r.content.decode()
        self.assertNotIn('10.1.2.3', teks)
        self.assertNotIn('SN-RAHASIA', teks)
        p = r.json()['peralatan'][0]
        self.assertNotIn('ip_address', p)
        self.assertEqual(p['umur_tahun'], timezone.localdate().year - 2015)

    def test_health_index_ikut_dan_bisa_dilewati(self):
        p = self._get(q='RTU-01').json()['peralatan'][0]
        self.assertIsNotNone(p['health_index'])
        p = self._get(q='RTU-01', hi='0').json()['peralatan'][0]
        self.assertNotIn('health_index', p)


# ═══════════════════════════════════════════════════════════════════════════
#  Inventaris aset, lokasi & riwayat pemeliharaan (untuk disalin Fasop Induk)
# ═══════════════════════════════════════════════════════════════════════════
def _dt(th, bl, hr, jam=8):
    return timezone.make_aware(datetime.datetime(th, bl, hr, jam, 0))


class _DataAset:
    """Fixture bersama: dua GI ber-master, satu lokasi tanpa master."""

    def _isi(self):
        from django.contrib.auth.models import User
        from devices.models import Branch, Device, DeviceEvent, DeviceType, SiteLocation, ULTG
        from devices.models_komponen import DeviceComponent

        br = Branch.objects.create(nama='UP2B', kode='UP2B')
        tello = SiteLocation.objects.create(nama='GI TELLO', branch=br,
                                            latitude=-5.1, longitude=119.4)
        SiteLocation.objects.create(nama='GI BONE')
        ultg = ULTG.objects.create(nama='ULTG Makassar')
        ultg.lokasi.add(tello)

        self.rtu = DeviceType.objects.create(name='RTU')
        self.rect = DeviceType.objects.create(name='Rectifier')
        self.user = User.objects.create_user('teknisi1', first_name='Andi', last_name='Teknisi')

        self.d1 = Device.objects.create(
            nama='RTU-01', jenis=self.rtu, merk='SEL', type='3530', lokasi='GI TELLO',
            asset_id='100200', status_aset='UP2B', ip_address='10.1.2.3',
            serial_number='SN-01', tahun_operasi=2015, spesifikasi={'jumlah_di': 64})
        self.d2 = Device.objects.create(nama='RECT-01', jenis=self.rect, merk='Benning',
                                        lokasi='gi tello', status_aset='IPP')
        self.vm = Device.objects.create(nama='VM-SCADA', jenis=self.rtu, merk='VMware',
                                        lokasi='GI BONE', host=self.d1)
        self.d_tanpa_master = Device.objects.create(nama='PLC-X', jenis=self.rtu, merk='ABB',
                                                    lokasi='GI ANTAH')
        self.d_hapus = Device.objects.create(nama='RTU-HAPUS', jenis=self.rtu, merk='SEL',
                                             lokasi='GI TELLO', is_deleted=True)

        DeviceComponent.objects.create(device=self.d1, nama='CPU', posisi='Slot 1', merk='SEL')
        DeviceEvent.objects.create(device=self.d1, tipe=DeviceEvent.TIPE_CHOICES[0][0],
                                   tanggal=datetime.date(2026, 3, 1), komponen='PSU',
                                   dilakukan_oleh=self.user)


class AsetEndpointTest(_DataAset, TestCase):

    def setUp(self):
        self._isi()
        self.kunci = _kunci('Fasop Induk', 'aset')

    def _get(self, **params):
        return self.client.get(reverse('api:fasop_aset'), params, headers=_hdr(self.kunci))

    def test_berhalaman_urut_pk_dan_tanpa_yang_dihapus(self):
        from fasop.hashids_helper import decode
        d1 = self._get(per_halaman=3, hi='0').json()
        self.assertEqual((d1['jumlah'], d1['jumlah_halaman'], d1['halaman_berikutnya']),
                         (4, 2, 2))
        d2 = self._get(per_halaman=3, halaman=2, hi='0').json()
        self.assertIsNone(d2['halaman_berikutnya'])
        pk = [decode(a['id']) for a in d1['aset'] + d2['aset']]
        self.assertEqual(pk, sorted(pk))
        self.assertNotIn(self.d_hapus.pk, pk)
        self.assertEqual(len(pk), 4)

    def test_halaman_lewat_ujung_kosong_bukan_404(self):
        d = self._get(halaman=99, hi='0').json()
        self.assertEqual(d['aset'], [])
        self.assertIsNone(d['halaman_berikutnya'])

    def test_isi_baris_aset(self):
        a = {x['nama']: x for x in self._get().json()['aset']}
        r = a['RTU-01']
        self.assertEqual(r['asset_id'], '100200')
        self.assertEqual(r['status_aset_label'], 'UP2B')
        self.assertEqual(r['serial_number'], 'SN-01')
        self.assertEqual(r['ip_address'], '10.1.2.3')
        self.assertEqual(r['branch'], 'UP2B')
        self.assertEqual(r['ultg'], ['ULTG Makassar'])
        self.assertEqual(r['spesifikasi'], {'jumlah_di': 64})
        self.assertEqual(r['umur_tahun'], timezone.localdate().year - 2015)
        self.assertEqual(r['status_operasi'], 'operasi')
        self.assertIsNotNone(r['health_index'])
        # VM menunjuk server fisiknya dengan id yang sama dengan daftar.
        self.assertEqual(a['VM-SCADA']['host'], {'id': r['id'], 'nama': 'RTU-01'})
        # Lokasi tanpa master: tidak punya branch/ULTG, tapi asetnya tetap ada.
        self.assertIsNone(a['PLC-X']['branch'])
        self.assertEqual(a['PLC-X']['ultg'], [])

    def test_token_qr_tidak_pernah_dikirim(self):
        """public_token membuka halaman publik QR tanpa login — itu kunci."""
        teks = self._get(hi='0').content.decode()
        self.assertNotIn(self.d1.public_token, teks)

    def test_hi_bisa_dilewati(self):
        r = self._get(hi='0').json()['aset'][0]
        self.assertNotIn('health_index', r)

    def test_penyaring(self):
        d = self._get(lokasi='GI TELLO', hi='0').json()
        self.assertEqual({a['nama'] for a in d['aset']}, {'RTU-01', 'RECT-01'})
        d = self._get(jenis='rectifier', hi='0').json()
        self.assertEqual([a['nama'] for a in d['aset']], ['RECT-01'])
        d = self._get(status_aset='ipp', hi='0').json()
        self.assertEqual([a['nama'] for a in d['aset']], ['RECT-01'])

    def test_parameter_halaman_salah_ditolak(self):
        self.assertEqual(self._get(per_halaman=201).status_code, 400)
        self.assertEqual(self._get(halaman='abc').status_code, 400)
        self.assertEqual(self._get(halaman=0).status_code, 400)

    def test_kunci_bot_tidak_ikut_membaca_aset(self):
        """Kunci yang memegang `peralatan` (bot WA) tidak otomatis boleh
        membaca inventaris lengkap — itulah alasan kodenya dipisah."""
        bot = _kunci('Bot WA', 'peralatan', 'pemeliharaan')
        r = self.client.get(reverse('api:fasop_aset'), headers=_hdr(bot))
        self.assertEqual(r.status_code, 403)

    def test_detail_aset(self):
        from fasop.hashids_helper import encode
        from maintenance.models import Maintenance
        m = Maintenance.objects.create(device=self.d1, maintenance_type='Preventive',
                                       status='Done', date=_dt(2026, 9, 1))
        url = reverse('api:fasop_aset_detail', args=[self.d1.pk])
        d = self.client.get(url, headers=_hdr(self.kunci)).json()
        a = d['aset']
        self.assertEqual(a['id'], encode(self.d1.pk))
        self.assertTrue(a['rincian_hi'])
        self.assertEqual([k['nama'] for k in a['komponen']], ['CPU'])
        ev = a['riwayat_kejadian'][0]
        self.assertEqual(ev['komponen'], 'PSU')
        self.assertEqual(ev['dilakukan_oleh']['label'], 'Andi Teknisi')
        self.assertEqual(a['vm'], [{'id': encode(self.vm.pk), 'nama': 'VM-SCADA'}])
        self.assertEqual([p['id'] for p in a['pemeliharaan']], [encode(m.pk)])
        self.assertIn('riwayat_kejadian', d['skema'])
        self.assertNotIn(self.d1.public_token, str(d))

    def test_detail_aset_terhapus_404(self):
        url = reverse('api:fasop_aset_detail', args=[self.d_hapus.pk])
        self.assertEqual(self.client.get(url, headers=_hdr(self.kunci)).status_code, 404)


class LokasiEndpointTest(_DataAset, TestCase):

    def setUp(self):
        self._isi()
        self.kunci = _kunci('Fasop Induk', 'lokasi')

    def test_lokasi_branch_ultg(self):
        d = self.client.get(reverse('api:fasop_lokasi'), headers=_hdr(self.kunci)).json()
        lok = {x['nama']: x for x in d['lokasi']}
        self.assertEqual(lok['GI TELLO']['branch'], 'UP2B')
        self.assertEqual(lok['GI TELLO']['ultg'], ['ULTG Makassar'])
        self.assertEqual(lok['GI TELLO']['latitude'], -5.1)
        # RTU-01 tercatat 'GI TELLO'; RECT-01 'gi tello' tidak cocok persis
        # dengan master, jadi dihitung terpisah — sama seperti peta di FASOP.
        self.assertEqual(lok['GI TELLO']['jumlah_aset'], 1)
        self.assertEqual(lok['GI BONE']['jumlah_aset'], 1)
        self.assertEqual(d['branch'][0]['jumlah_lokasi'], 1)
        self.assertEqual(d['ultg'][0]['lokasi'], ['GI TELLO'])
        tanpa = {x['lokasi']: x['jumlah_aset'] for x in d['lokasi_tanpa_master']}
        self.assertEqual(tanpa, {'GI ANTAH': 1, 'gi tello': 1})


class RiwayatPemeliharaanTest(_DataAset, TestCase):

    def setUp(self):
        from maintenance.models import Maintenance, MaintenanceCorrective, MaintenanceRectifier

        self._isi()
        self.kunci = _kunci('Fasop Induk', 'riwayat_pemeliharaan')

        self.m_done = Maintenance.objects.create(
            device=self.d2, maintenance_type='Preventive', status='Done',
            date=_dt(2026, 9, 5), description='HAR rutin', catatan_am='OK',
            pelaksana_names=['Budi', 'Citra'], signed_by=self.user, signed_at=_dt(2026, 9, 6))
        MaintenanceRectifier.objects.create(
            maintenance=self.m_done, suhu_ruangan=24.5, rect1_kondisi='OK',
            bat1_cells=[{'cell': 1, 'v_float': 2.13}])

        self.m_cm = Maintenance.objects.create(
            device=self.d1, maintenance_type='Corrective', status='Open', date=_dt(2026, 9, 30, 23))
        self.m_cm.technicians.add(self.user)
        MaintenanceCorrective.objects.create(
            maintenance=self.m_cm, jenis_kerusakan='power',
            deskripsi_masalah='PSU mati', tindakan='Ganti PSU')

        Maintenance.objects.create(device=self.d1, maintenance_type='Preventive',
                                   status='Open', date=_dt(2026, 10, 1))
        # Dua yang tidak boleh ikut: soft-delete, dan milik peralatan terhapus.
        self.m_hapus = Maintenance.objects.create(
            device=self.d1, maintenance_type='Preventive', status='Done',
            date=_dt(2026, 9, 7), is_deleted=True)
        Maintenance.objects.create(device=self.d_hapus, maintenance_type='Preventive',
                                   status='Done', date=_dt(2026, 9, 8))

    def _get(self, **params):
        return self.client.get(reverse('api:fasop_pemeliharaan_riwayat'), params,
                               headers=_hdr(self.kunci))

    def test_open_dan_done_tanpa_yang_dihapus(self):
        d = self._get().json()
        self.assertEqual(d['jumlah'], 3)
        self.assertEqual({p['status'] for p in d['pemeliharaan']}, {'Open', 'Done'})
        self.assertNotIn('hasil_pengukuran', d['pemeliharaan'][0])

    def test_isi_baris(self):
        from fasop.hashids_helper import encode
        p = {x['id']: x for x in self._get().json()['pemeliharaan']}
        done = p[encode(self.m_done.pk)]
        self.assertEqual(done['peralatan']['id'], encode(self.d2.pk))
        self.assertEqual(done['pelaksana'], ['Budi', 'Citra'])
        self.assertEqual(done['ttd']['oleh'], 'Andi Teknisi')
        self.assertTrue(done['ttd']['sudah'])
        self.assertEqual(done['catatan_am'], 'OK')
        # Akun yang dicentang mengalahkan nama bebas — aturan ekspor Excel.
        self.assertEqual(p[encode(self.m_cm.pk)]['pelaksana'], ['Andi Teknisi'])

    def test_rentang_tanggal_inklusif(self):
        d = self._get(dari='2026-09-01', sampai='2026-09-30').json()
        # 30 Sep 23:00 tetap masuk "sampai 2026-09-30".
        self.assertEqual(d['jumlah'], 2)
        self.assertEqual(self._get(dari='2026-10-01').json()['jumlah'], 1)

    def test_penyaring_tipe_status_aset(self):
        from fasop.hashids_helper import encode
        self.assertEqual(self._get(tipe='corrective').json()['jumlah'], 1)
        self.assertEqual(self._get(status='DONE').json()['jumlah'], 1)
        self.assertEqual(self._get(aset=encode(self.d1.pk)).json()['jumlah'], 2)
        self.assertEqual(self._get(jenis='rectifier').json()['jumlah'], 1)

    def test_penyaring_salah_ditolak_bukan_diabaikan(self):
        self.assertEqual(self._get(tipe='preventif').status_code, 400)
        self.assertEqual(self._get(status='selesai').status_code, 400)
        self.assertEqual(self._get(dari='01-09-2026').status_code, 400)
        self.assertEqual(self._get(aset='!!').status_code, 400)

    def test_detail_inline_dengan_skema(self):
        from fasop.hashids_helper import encode
        d = self._get(detail='1').json()
        p = {x['id']: x for x in d['pemeliharaan']}
        hasil = p[encode(self.m_done.pk)]['hasil_pengukuran']
        self.assertEqual([h['tabel'] for h in hasil], ['rectifier'])
        self.assertEqual(hasil[0]['data']['suhu_ruangan'], 24.5)
        self.assertEqual(hasil[0]['data']['bat1_cells'], [{'cell': 1, 'v_float': 2.13}])
        self.assertNotIn('maintenance', hasil[0]['data'])
        cm = p[encode(self.m_cm.pk)]['hasil_pengukuran'][0]
        self.assertEqual(cm['tabel'], 'corrective')
        self.assertEqual(cm['data']['tindakan'], 'Ganti PSU')
        # Skema hanya untuk tabel yang muncul, dengan label & pilihan.
        self.assertEqual(set(d['skema_hasil']), {'rectifier', 'corrective'})
        kolom = {k['nama']: k for k in d['skema_hasil']['rectifier']['kolom']}
        self.assertEqual(kolom['suhu_ruangan']['label'], 'Suhu Ruangan (°C)')
        self.assertEqual(kolom['suhu_ruangan']['tipe'], 'desimal')
        self.assertEqual(kolom['rect1_kondisi']['pilihan'], {'OK': 'OK', 'NOK': 'NOK'})
        pil = {k['nama']: k for k in d['skema_hasil']['corrective']['kolom']}
        self.assertEqual(pil['jenis_kerusakan']['pilihan']['power'], 'Power / Catu Daya')

    def test_detail_satu_pemeliharaan(self):
        url = reverse('api:fasop_pemeliharaan_detail', args=[self.m_done.pk])
        d = self.client.get(url, headers=_hdr(self.kunci)).json()
        self.assertEqual(d['pemeliharaan']['hasil_pengukuran'][0]['tabel'], 'rectifier')
        self.assertIn('rectifier', d['skema_hasil'])

    def test_detail_yang_dihapus_404(self):
        url = reverse('api:fasop_pemeliharaan_detail', args=[self.m_hapus.pk])
        self.assertEqual(self.client.get(url, headers=_hdr(self.kunci)).status_code, 404)

    def test_rute_riwayat_tidak_tertelan_pola_hashid(self):
        """Regex hashid [a-zA-Z0-9]+ juga cocok dengan "riwayat"."""
        self.assertEqual(resolve('/api/v1/fasop/pemeliharaan/riwayat/').url_name,
                         'fasop_pemeliharaan_riwayat')

    def test_kunci_bot_pemeliharaan_tidak_ikut_membaca_riwayat(self):
        bot = _kunci('Bot WA', 'pemeliharaan')
        self.assertEqual(self.client.get(reverse('api:fasop_pemeliharaan_riwayat'),
                                         headers=_hdr(bot)).status_code, 403)


class TabelHasilPengukuranTest(TestCase):
    """
    Hasil pengukuran dibaca generik dari relasi OneToOne `Maintenance`, bukan
    dipetakan tangan — tes ini memastikan semua tabel benar-benar tercakup dan
    setiap tipe kolomnya bisa dijadikan JSON.
    """

    def test_semua_tabel_detail_tercakup(self):
        from api.inventaris import tabel_detail
        from maintenance.models import Maintenance
        kode = dict(tabel_detail())
        harus = {r.related_model for r in Maintenance._meta.related_objects
                 if r.one_to_one and r.related_model.__name__.startswith('Maintenance')}
        self.assertEqual(set(kode.values()), harus)
        self.assertGreaterEqual(len(kode), 20)
        self.assertIn('masterstation', kode)
        self.assertIn('corrective', kode)
        self.assertNotIn('formoffline', kode)     # berkas form, bukan hasil ukur

    def test_setiap_tabel_bisa_diserialisasi(self):
        import json
        from django.core.serializers.json import DjangoJSONEncoder
        from api.inventaris import baris, skema_tabel, tabel_detail
        for kode, M in tabel_detail():
            with self.subTest(tabel=kode):
                json.dumps(baris(M(), kecuali=('maintenance',)), cls=DjangoJSONEncoder)
        json.dumps(skema_tabel(), cls=DjangoJSONEncoder)
