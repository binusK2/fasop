"""
Data API eksternal: sakelar per jenis data + izin per kunci.

Migrasi datanya sengaja MEMBUKA keempat data dan MEMBERIKAN semuanya ke kunci
yang sudah ada. Alasannya cuma satu — `beban_ktt` sudah dipakai konsumen luar
sebelum izin ini ada, dan menambahkan penjaga baru tidak boleh mematikan
integrasi yang sedang jalan (pola yang sama dengan baris `ZabbixInstance`
'telkom' yang lahir dengan kredensial kosong).

Kunci yang dibuat SESUDAH migrasi ini lahir tanpa izin apa pun, dan data yang
ditambahkan ke registry nanti lahir TERTUTUP (`DatasetApi.sinkron()`).
Pembukaan sekali ini hanya berlaku untuk keadaan saat migrasi dijalankan.
"""
from django.db import migrations, models


def buka_dan_beri_izin(apps, schema_editor):
    from api.registry import SEMUA_KODE

    DatasetApi = apps.get_model('devices', 'DatasetApi')
    KunciApi   = apps.get_model('devices', 'KunciApi')

    for kode in SEMUA_KODE:
        DatasetApi.objects.get_or_create(kode=kode, defaults={'aktif': True})

    semua = list(DatasetApi.objects.all())
    for kunci in KunciApi.objects.all():
        kunci.dataset.set(semua)


def mundur(apps, schema_editor):
    # Barisnya ikut terhapus bersama tabelnya saat field/model di-reverse;
    # tidak ada yang perlu dikembalikan secara terpisah.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0069_pengumumanpemeliharaan'),
    ]

    operations = [
        migrations.CreateModel(
            name='DatasetApi',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('kode', models.CharField(
                    db_index=True, max_length=40, unique=True, verbose_name='Kode Data',
                    help_text='Dipasangkan ke view di api/registry.py. Tidak diketik manual.')),
                ('aktif', models.BooleanField(
                    default=False, verbose_name='Boleh Dikeluarkan',
                    help_text='Hilangkan centang untuk menutup data ini bagi SEMUA konsumen '
                              'sekaligus, tanpa mengubah izin per kunci.')),
                ('keterangan', models.TextField(
                    blank=True, default='', verbose_name='Catatan',
                    help_text='Mis. dasar persetujuan membuka data ini, atau alasan ditutup.')),
                ('diubah_pada', models.DateTimeField(auto_now=True, verbose_name='Diubah')),
            ],
            options={
                'verbose_name': 'Data API Eksternal',
                'verbose_name_plural': 'Data API Eksternal',
                'ordering': ['kode'],
            },
        ),
        migrations.AddField(
            model_name='kunciapi',
            name='dataset',
            field=models.ManyToManyField(
                blank=True, related_name='kunci', to='devices.datasetapi',
                verbose_name='Data yang Boleh Dibaca',
                help_text='Centang hanya data yang memang diminta konsumen ini. Kosong = kunci '
                          'berlaku tapi tidak bisa membaca apa pun.'),
        ),
        migrations.RunPython(buka_dan_beri_izin, mundur),
    ]
