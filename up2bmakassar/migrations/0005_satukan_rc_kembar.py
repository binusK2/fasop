from django.db import migrations


def satukan_rc_kembar(apps, schema_editor):
    """
    Hapus RemoteControl yang sebenarnya kembaran perintah lain.

    Trigger OFDB menulis dua baris scd_his_rc untuk setiap perintah RC (lihat
    ofdb.gabung_rc_kembar), dan sync_rc versi sebelumnya menyimpan keduanya
    sebagai RC terpisah: satu berisi hasil sungguhan, satu lagi placeholder
    GAGAL dari trigger. Kunci perintahnya sama dengan ofdb.kunci_perintah_rc --
    ditulis ulang di sini karena migrasi tidak boleh ikut berubah kalau modul
    itu berubah.

    Per perintah disisakan satu baris: yang BERHASIL kalau ada (placeholder
    selalu GAGAL, jadi BERHASIL pasti hasil pemeriksaan sungguhan), selain itu
    yang ofdb_id_his_rc-nya terkecil -- wakil yang sama dengan pilihan sync_rc.
    """
    RemoteControl = apps.get_model('up2bmakassar', 'RemoteControl')

    def t(v):
        return (v or '').strip()

    kelompok = {}
    baris = RemoteControl.objects.exclude(datum_eksekusi=None).values_list(
        'pk', 'ofdb_id_his_rc', 'path1', 'path2', 'path3', 'path4', 'path5',
        'datum_eksekusi', 'status_eksekusi', 'operator', 'status_respon',
    )
    for (pk, id_his_rc, p1, p2, p3, p4, p5, datum, status_eksekusi, operator,
         status_respon) in baris.iterator(chunk_size=2000):
        kunci = (t(p1), t(p2), t(p3), t(p4), t(p5), datum, t(status_eksekusi), t(operator))
        kelompok.setdefault(kunci, []).append((t(status_respon) != 'BERHASIL', id_his_rc, pk))

    hapus = []
    for anggota in kelompok.values():
        if len(anggota) > 1:
            anggota.sort()
            hapus.extend(pk for _gagal, _id, pk in anggota[1:])

    for i in range(0, len(hapus), 1000):
        RemoteControl.objects.filter(pk__in=hapus[i:i + 1000]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('up2bmakassar', '0004_kinerja_jenis_dan_label'),
    ]

    operations = [
        # Tidak bisa dibalik, dan memang tidak perlu: isinya turunan OFDB yang
        # bisa dibangun ulang dengan `sync_rc --ulang`.
        migrations.RunPython(satukan_rc_kembar, migrations.RunPython.noop),
    ]
