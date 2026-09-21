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
                    self.assertTrue(resolve(path), path)

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
                    r = self.client.get(path, headers=_hdr(k))
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
                     'logsheet_pembebanan'):
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
