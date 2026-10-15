"""
Tes Kinerja RC: satu perintah RC = satu RC, walau OFDB mencatatnya beberapa baris.

Trigger tr1_scd_his_message menulis dua baris scd_his_rc untuk tiap perintah --
satu kosong, satu placeholder GAGAL (datum_2 = datum_1) -- dan versi lama
sync_rc menyimpan keduanya sebagai RC terpisah, sehingga performance tiap bay
tidak pernah bisa lewat 50%. Data uji di sini disalin dari OFDB sungguhan
(BKARU5 / TRFG-1 / CB, 5 Okt 2026 17:20:16), bukan karangan -- kecuali nama
operatornya, yang sengaja disamarkan ('OPR1').
"""
from datetime import datetime
from importlib import import_module
from unittest import mock

from django.apps import apps
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from up2bmakassar import ofdb
from up2bmakassar.models import RemoteControl

PERINTAH = datetime(2026, 10, 5, 17, 20, 16)
BALASAN = datetime(2026, 10, 5, 17, 20, 18)


def baris_rc(id_his_rc, datum_1=PERINTAH, status_1='Close', datum_2=None, status_2='',
             cek_remote=None, operator='OPR1', path1='BKARU5', path3='TRFG-1'):
    """Satu baris seperti yang dikembalikan ofdb.get_rc_events()."""
    return (
        id_his_rc, path1, '150', path3, 'CB', 'Status',
        'BAKARU 150 KV', '150', 'TRAFO GENERATOR 1', 'CB',
        datum_1, status_1, datum_2, status_2, operator, cek_remote,
    )


def pasangan_trigger(id_his_rc, datum_1=PERINTAH, **kw):
    """Dua baris yang ditulis trigger untuk SATU pesan perintah 'OR'."""
    return [
        baris_rc(id_his_rc, datum_1=datum_1, **kw),
        baris_rc(id_his_rc + 1, datum_1=datum_1, datum_2=datum_1, status_2='GAGAL',
                 cek_remote=1, **kw),
    ]


class GabungRcKembarTest(SimpleTestCase):

    def test_pasangan_trigger_jadi_satu_perintah(self):
        perintah = ofdb.gabung_rc_kembar(pasangan_trigger(14781))
        self.assertEqual(len(perintah), 1)
        wakil, kembar, hasil_ofdb = perintah[0]
        self.assertEqual(wakil[0], 14781)
        self.assertEqual(kembar, [14782])
        # Placeholder GAGAL bukan hasil -- harus dicari di scd_his_message.
        self.assertIsNone(hasil_ofdb)

    def test_pesan_soe_terduplikasi_tetap_satu_perintah(self):
        # TELLO5/PKANG5-1 9 Okt 2026: pesan OR-nya sendiri tercatat dua kali di
        # scd_his_message (stempel waktu & msec sama), jadi 4 baris scd_his_rc.
        events = pasangan_trigger(14883) + pasangan_trigger(14887)
        perintah = ofdb.gabung_rc_kembar(events)
        self.assertEqual(len(perintah), 1)
        self.assertEqual(perintah[0][0][0], 14883)
        self.assertEqual(perintah[0][1], [14884, 14887, 14888])

    def test_wakil_id_terkecil_walau_urutan_acak(self):
        perintah = ofdb.gabung_rc_kembar(list(reversed(pasangan_trigger(14781))))
        self.assertEqual(perintah[0][0][0], 14781)
        self.assertEqual(perintah[0][1], [14782])

    def test_placeholder_tunggal_tidak_dipakai_sebagai_hasil(self):
        # Perintah bertag 'O*' hanya melahirkan placeholder-nya. BLUSU5 15 Sep 2026
        # dibalas 'R*' (BERHASIL) sedetik kemudian, padahal placeholder-nya GAGAL.
        events = [baris_rc(14371, status_1='Open', datum_2=PERINTAH, status_2='GAGAL',
                           cek_remote=1)]
        perintah = ofdb.gabung_rc_kembar(events)
        self.assertEqual(len(perintah), 1)
        self.assertEqual(perintah[0][1], [])
        self.assertIsNone(perintah[0][2])

    def test_hasil_job_lama_dipercaya(self):
        # Era job up2bmakassar masih hidup (s.d. Okt 2023): satu baris diselesaikan
        # job, kembarannya placeholder. Balasan di detik yang sama tetap sah.
        events = [
            baris_rc(3775, datum_2=PERINTAH, status_2='BERHASIL', cek_remote=1),
            baris_rc(3776, datum_2=PERINTAH, status_2='GAGAL', cek_remote=1),
        ]
        _wakil, kembar, hasil_ofdb = ofdb.gabung_rc_kembar(events)[0]
        self.assertEqual(kembar, [3776])
        self.assertEqual(hasil_ofdb, (PERINTAH, 'BERHASIL'))

    def test_gagal_job_lama_dengan_waktu_balasan_dipercaya(self):
        events = [baris_rc(3757, datum_2=BALASAN, status_2='GAGAL', cek_remote=1)]
        self.assertEqual(ofdb.gabung_rc_kembar(events)[0][2], (BALASAN, 'GAGAL'))

    def test_perintah_ulang_beberapa_detik_kemudian_tetap_dua(self):
        # LASSA5/MLILI5-1 7 Okt 2026: operator mengulang perintah 4 detik kemudian.
        events = pasangan_trigger(14851) + pasangan_trigger(
            14853, datum_1=datetime(2026, 10, 7, 12, 59, 20))
        self.assertEqual(len(ofdb.gabung_rc_kembar(events)), 2)

    def test_arah_berbeda_di_detik_sama_tetap_dua(self):
        events = [baris_rc(1, status_1='Open'), baris_rc(2, status_1='Close')]
        self.assertEqual(len(ofdb.gabung_rc_kembar(events)), 2)

    def test_bay_berbeda_tetap_dua(self):
        events = [baris_rc(1), baris_rc(2, path3='TRFG-2')]
        self.assertEqual(len(ofdb.gabung_rc_kembar(events)), 2)

    def test_spasi_padding_tidak_memecah_perintah(self):
        self.assertEqual(
            ofdb.kunci_perintah_rc('BKARU5  ', '150 ', 'TRFG-1', 'CB', 'Status  ',
                                   PERINTAH, 'Close   ', 'OPR1  '),
            ofdb.kunci_perintah_rc('BKARU5', '150', 'TRFG-1', 'CB', 'Status',
                                   PERINTAH, 'Close', 'OPR1'),
        )


def aware(dt):
    return timezone.make_aware(dt, timezone.get_current_timezone())


class SyncRcTest(TestCase):
    """sync_rc dengan OFDB tiruan -- tidak ada koneksi ke 192.168.19.1."""

    def jalankan(self, events, hasil_soe=(BALASAN, 490, 'BERHASIL'), **opsi):
        with mock.patch.object(ofdb, 'get_connection') as conn, \
                mock.patch.object(ofdb, 'get_rc_events', return_value=events), \
                mock.patch.object(ofdb, 'resolve_rc_result', return_value=hasil_soe) as resolve:
            conn.return_value.cursor.return_value = mock.Mock()
            call_command('sync_rc', date='2026-10-05', days=1, stdout=mock.Mock(), **opsi)
        return resolve

    def simpan(self, id_his_rc, status_respon, datum_respon):
        return RemoteControl.objects.create(
            ofdb_id_his_rc=id_his_rc, path1='BKARU5', path2='150', path3='TRFG-1',
            path4='CB', path5='Status', b1='BAKARU 150 KV', b2='150',
            b3='TRAFO GENERATOR 1', elem='CB', operator='OPR1',
            tanggal=PERINTAH.date(), datum_eksekusi=aware(PERINTAH),
            status_eksekusi='Close', datum_respon=aware(datum_respon),
            status_respon=status_respon,
        )

    def test_satu_perintah_disimpan_satu_rc(self):
        resolve = self.jalankan(pasangan_trigger(14781))
        rc = RemoteControl.objects.get()
        self.assertEqual(rc.ofdb_id_his_rc, 14781)
        self.assertEqual(rc.status_respon, 'BERHASIL')
        self.assertEqual(rc.datum_respon, aware(BALASAN))
        resolve.assert_called_once()

    def test_kembar_lama_dihapus_walau_wakil_sudah_final(self):
        # Keadaan sebelum perbaikan: dua RC untuk satu perintah.
        self.simpan(14781, 'BERHASIL', BALASAN)
        self.simpan(14782, 'GAGAL', PERINTAH)
        resolve = self.jalankan(pasangan_trigger(14781))
        self.assertEqual(
            list(RemoteControl.objects.values_list('ofdb_id_his_rc', 'status_respon')),
            [(14781, 'BERHASIL')],
        )
        # Wakil yang sudah final tetap tidak di-resolve ulang ke OFDB.
        resolve.assert_not_called()

    def test_placeholder_tunggal_diselesaikan_dari_soe(self):
        events = [baris_rc(14371, status_1='Open', datum_2=PERINTAH, status_2='GAGAL',
                           cek_remote=1)]
        resolve = self.jalankan(events)
        resolve.assert_called_once()
        self.assertEqual(RemoteControl.objects.get().status_respon, 'BERHASIL')

    def test_dry_run_tidak_menghapus(self):
        self.simpan(14781, 'BERHASIL', BALASAN)
        self.simpan(14782, 'GAGAL', PERINTAH)
        self.jalankan(pasangan_trigger(14781), dry_run=True)
        self.assertEqual(RemoteControl.objects.count(), 2)

    def test_halaman_kinerja_rc_menghitung_satu_perintah(self):
        self.jalankan(pasangan_trigger(14781))
        user = User.objects.create_superuser('admin_rc', 'a@example.com', 'x')
        # ForcePasswordChangeMiddleware mengalihkan user baru ke /ganti-password/.
        profile = getattr(user, 'profile', None)
        if profile is not None:
            profile.force_password_change = False
            profile.save(update_fields=['force_password_change'])
        self.client.force_login(user)
        resp = self.client.get(reverse('up2b_kinerja_rc'), {
            'tanggal_dari': '2026-10-05', 'tanggal_sampai': '2026-10-05',
        })
        self.assertEqual(resp.status_code, 200)
        ringkasan = resp.context['ringkasan']
        self.assertEqual(ringkasan['total_rc'], 1)
        self.assertEqual(ringkasan['total_gagal'], 0)
        self.assertEqual(ringkasan['rata_rata'], 100)


class MigrasiSatukanRcKembarTest(TestCase):
    """Migrasi 0005 membersihkan RC kembar yang terlanjur tersimpan."""

    satukan = staticmethod(
        import_module('up2bmakassar.migrations.0005_satukan_rc_kembar').satukan_rc_kembar
    )

    def simpan(self, id_his_rc, status_respon, datum_eksekusi=PERINTAH, path1='BKARU5'):
        RemoteControl.objects.create(
            ofdb_id_his_rc=id_his_rc, path1=path1, path2='150', path3='TRFG-1',
            path4='CB', path5='Status', operator='OPR1', tanggal=datum_eksekusi.date(),
            datum_eksekusi=aware(datum_eksekusi), status_eksekusi='Close',
            datum_respon=aware(datum_eksekusi), status_respon=status_respon,
        )

    def sisa(self):
        return list(RemoteControl.objects.order_by('ofdb_id_his_rc')
                    .values_list('ofdb_id_his_rc', 'status_respon'))

    def test_sisakan_wakil_berhasil(self):
        self.simpan(14781, 'BERHASIL')
        self.simpan(14782, 'GAGAL')
        self.satukan(apps, None)
        self.assertEqual(self.sisa(), [(14781, 'BERHASIL')])

    def test_berhasil_menang_walau_bukan_id_terkecil(self):
        self.simpan(3775, 'GAGAL')
        self.simpan(3776, 'BERHASIL')
        self.satukan(apps, None)
        self.assertEqual(self.sisa(), [(3776, 'BERHASIL')])

    def test_padding_lama_tetap_terkelompok(self):
        self.simpan(14781, 'GAGAL')
        self.simpan(14782, 'GAGAL', path1='BKARU5  ')
        self.satukan(apps, None)
        self.assertEqual(self.sisa(), [(14781, 'GAGAL')])

    def test_perintah_berbeda_tidak_tersentuh(self):
        self.simpan(14781, 'BERHASIL')
        self.simpan(14783, 'GAGAL', datum_eksekusi=datetime(2026, 10, 5, 17, 25, 0))
        self.simpan(14785, 'GAGAL', path1='BKARU6')
        self.satukan(apps, None)
        self.assertEqual(len(self.sisa()), 3)
