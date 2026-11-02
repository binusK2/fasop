"""Pulihkan Device.created_by yang terhapus oleh form edit.

DeviceForm dulu memakai fields='__all__', sehingga created_by ikut menjadi
field form padahal tidak pernah dirender — setiap edit peralatan menimpanya
dengan NULL dan "Ditambahkan oleh" di halaman detail jadi kosong. Pembuatnya
masih tercatat di DeviceLog aksi='create' (log_create di device_create), jadi
dari situ nilainya dikembalikan.

Hanya mengisi yang kosong; baris yang sudah punya created_by tidak disentuh.
Peralatan tanpa log 'create' (lebih tua dari DeviceLog) atau yang dibuat lewat
API (log tanpa user) tetap kosong — memang tidak ada sumbernya.

Yang TIDAK bisa dipulihkan dari database: public_token yang sudah terlanjur
diganti dan wiring_json yang sudah terhapus oleh bug yang sama.
"""
from collections import defaultdict

from django.db import migrations


def isi_ulang(apps, schema_editor):
    Device = apps.get_model('devices', 'Device')
    DeviceLog = apps.get_model('devices', 'DeviceLog')

    log = (DeviceLog.objects
           .filter(aksi='create', user__isnull=False,
                   device__created_by__isnull=True)
           .order_by('device_id', 'created_at', 'pk')
           .values_list('device_id', 'user_id'))

    pembuat = {}
    for device_id, user_id in log:
        pembuat.setdefault(device_id, user_id)   # log 'create' paling awal

    per_user = defaultdict(list)
    for device_id, user_id in pembuat.items():
        per_user[user_id].append(device_id)

    for user_id, device_ids in per_user.items():
        Device.objects.filter(pk__in=device_ids, created_by__isnull=True) \
                      .update(created_by_id=user_id)


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0071_userprofile_role_dispatcher_monitoring'),
    ]

    operations = [
        migrations.RunPython(isi_ulang, migrations.RunPython.noop),
    ]
