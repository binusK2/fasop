from django.db import migrations, models
import django.db.models.deletion


# Data seed tipe komponen
SEED_DATA = [
    ('Umum', 10, [
        ('psu',            'Power Supply Unit',   10),
        ('fan',            'Fan / Cooling',       20),
        ('modul_generic',  'Modul (Umum)',        30),
    ]),
    ('Multiplexer', 20, [
        ('modul_cpu',      'Modul CPU',           10),
        ('modul_slot',     'Modul Slot (Card)',    20),
        ('modul_hs',       'Modul HS (High Speed)', 30),
    ]),
    ('Router / Switch', 30, [
        ('sfp',            'SFP / Transceiver',   10),
        ('port_lan',       'Port LAN',            20),
        ('port_uplink',    'Port Uplink',         30),
    ]),
    ('Rectifier / Catu Daya', 40, [
        ('modul_rectifier', 'Modul Rectifier',    10),
        ('battery',         'Battery Bank',       20),
        ('battery_cell',    'Battery Cell',       30),
    ]),
    ('Radio', 50, [
        ('antena',          'Antena',             10),
        ('modul_radio',     'Modul Radio TX/RX',  20),
    ]),
    ('PLC', 60, [
        ('modul_plc',       'Modul PLC',          10),
        ('wave_trap',       'Wave Trap',          20),
        ('imu',             'IMU / Coupling',     30),
    ]),
    ('Lainnya', 99, [
        ('lainnya',         'Lainnya',            99),
    ]),
]


def seed_tipe_komponen(apps, schema_editor):
    """Seed data tipe komponen ke database."""
    GrupTipeKomponen = apps.get_model('devices', 'GrupTipeKomponen')
    TipeKomponen = apps.get_model('devices', 'TipeKomponen')

    for grup_nama, grup_urutan, tipes in SEED_DATA:
        grup, _ = GrupTipeKomponen.objects.get_or_create(
            nama=grup_nama,
            defaults={'urutan': grup_urutan},
        )
        for kode, nama, urutan in tipes:
            TipeKomponen.objects.get_or_create(
                kode=kode,
                defaults={'nama': nama, 'grup': grup, 'urutan': urutan},
            )


def convert_tipe_charfield_to_fk(apps, schema_editor):
    """
    Convert data lama: tipe_komponen CharField ('sfp', 'psu', dll)
    → tipe_komponen_new ForeignKey (id dari TipeKomponen).
    """
    DeviceComponent = apps.get_model('devices', 'DeviceComponent')
    TipeKomponen = apps.get_model('devices', 'TipeKomponen')

    # Buat mapping kode → id
    tipe_map = {t.kode: t.id for t in TipeKomponen.objects.all()}

    for comp in DeviceComponent.objects.all():
        old_val = comp.tipe_komponen_old or ''
        new_id = tipe_map.get(old_val.strip())
        if new_id:
            comp.tipe_komponen_new_id = new_id
            comp.save(update_fields=['tipe_komponen_new_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0019_device_public_token'),
    ]

    operations = [
        # ── Step 1: Buat tabel GrupTipeKomponen ────────────────
        migrations.CreateModel(
            name='GrupTipeKomponen',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama', models.CharField(max_length=50, unique=True, verbose_name='Nama Grup')),
                ('urutan', models.PositiveSmallIntegerField(default=0, verbose_name='Urutan Tampil')),
            ],
            options={
                'verbose_name': 'Grup Tipe Komponen',
                'verbose_name_plural': 'Grup Tipe Komponen',
                'ordering': ['urutan', 'nama'],
            },
        ),

        # ── Step 2: Buat tabel TipeKomponen ────────────────────
        migrations.CreateModel(
            name='TipeKomponen',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kode', models.CharField(help_text='Kode pendek unik, e.g. psu, sfp, modul_cpu', max_length=30, unique=True, verbose_name='Kode')),
                ('nama', models.CharField(max_length=100, verbose_name='Nama Tipe')),
                ('urutan', models.PositiveSmallIntegerField(default=0, verbose_name='Urutan Tampil')),
                ('grup', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tipe_komponen', to='devices.gruptipekomponen', verbose_name='Grup')),
            ],
            options={
                'verbose_name': 'Tipe Komponen',
                'verbose_name_plural': 'Tipe Komponen',
                'ordering': ['grup__urutan', 'urutan', 'nama'],
            },
        ),

        # ── Step 3: Seed data tipe komponen ────────────────────
        migrations.RunPython(seed_tipe_komponen, noop),

        # ── Step 4: Rename field lama → _old ───────────────────
        migrations.RenameField(
            model_name='devicecomponent',
            old_name='tipe_komponen',
            new_name='tipe_komponen_old',
        ),

        # ── Step 5: Tambah field FK baru ───────────────────────
        migrations.AddField(
            model_name='devicecomponent',
            name='tipe_komponen_new',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='komponen_new',
                to='devices.tipekomponen',
                verbose_name='Tipe Komponen',
            ),
        ),

        # ── Step 6: Convert data lama ke FK ────────────────────
        migrations.RunPython(convert_tipe_charfield_to_fk, noop),

        # ── Step 7: Hapus field lama ───────────────────────────
        migrations.RemoveField(
            model_name='devicecomponent',
            name='tipe_komponen_old',
        ),

        # ── Step 8: Rename field baru → nama final ─────────────
        migrations.RenameField(
            model_name='devicecomponent',
            old_name='tipe_komponen_new',
            new_name='tipe_komponen',
        ),
    ]
