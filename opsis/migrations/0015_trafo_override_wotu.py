from django.db import migrations

# Titik IBT GITET WOTU (TRF65-1/TRF65-2) berhenti terupdate di ALL_TRANS_DATA.
# Nilainya masih hidup di dbo.TRANS_WOTU5_RT lewat bay INC56-1/INC56-2 (sisi
# 150kV dari IBT yang sama) — lihat opsis.mssql.get_nilai_override().
OVERRIDES = {
    ('GITET WOTU', 'TRF65-1'): 'INC56-1',
    ('GITET WOTU', 'TRF65-2'): 'INC56-2',
}


def apply_override(apps, schema_editor):
    Trafo = apps.get_model('opsis', 'Trafo')
    for (site, bay), sumber_bay in OVERRIDES.items():
        # update_or_create — bukan filter().update() — karena baris Trafo ini
        # baru auto-terdaftar saat halaman/collect_trafo pertama kali mengakses
        # MSSQL (opsis.views._trafo_aktif_saja), belum tentu sudah ada saat
        # migration ini jalan.
        Trafo.objects.update_or_create(
            site=site, bay=bay,
            defaults={
                'sumber_tabel': 'dbo.TRANS_WOTU5_RT',
                'sumber_mode': 'kolom',
                'sumber_filter_kolom': 'BAY',
                'sumber_filter_nilai': sumber_bay,
                'sumber_kolom_nilai': 'VALUE',
                'sumber_p': 'P',
                'sumber_q': 'Q',
                'sumber_v': 'V',
                'sumber_i': 'I',
            },
        )


def revert_override(apps, schema_editor):
    Trafo = apps.get_model('opsis', 'Trafo')
    for (site, bay) in OVERRIDES:
        Trafo.objects.filter(site=site, bay=bay).update(
            sumber_tabel='',
            sumber_mode='baris',
            sumber_filter_kolom='',
            sumber_filter_nilai='',
            sumber_kolom_nilai='VALUE',
            sumber_p='',
            sumber_q='',
            sumber_v='',
            sumber_i='',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('opsis', '0014_trafo_sumber_filter_kolom_trafo_sumber_filter_nilai_and_more'),
    ]

    operations = [
        migrations.RunPython(apply_override, revert_override),
    ]
