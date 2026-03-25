"""
devices/device_audit.py

Helper untuk mencatat perubahan Device ke DeviceLog.
"""

# Field yang di-track beserta label tampilan
TRACKED_FIELDS = [
    ('nama',             'Nama'),
    ('merk',             'Merk'),
    ('type',             'Model / Type'),
    ('serial_number',    'Serial Number'),
    ('firmware_version', 'Firmware'),
    ('ip_address',       'IP Address'),
    ('lokasi',           'Lokasi'),
    ('status_operasi',   'Status Operasi'),
    ('tahun_operasi',    'Tahun Operasi'),
    ('keterangan',       'Keterangan'),
]


def _get_display(device, field):
    """Ambil nilai field dalam format yang bisa ditampilkan."""
    val = getattr(device, field, None)
    if val is None or val == '':
        return '—'
    # Status operasi → tampilkan label
    if field == 'status_operasi':
        choices = dict(device.STATUS_CHOICES)
        return choices.get(str(val), str(val))
    return str(val)


def log_create(device, user):
    """Catat event pembuatan device baru."""
    try:
        from devices.models import DeviceLog
        DeviceLog.objects.create(
            device=device,
            user=user,
            aksi='create',
            perubahan=[],
        )
    except Exception:
        pass


def log_edit(device_before, device_after, user):
    """
    Bandingkan device sebelum dan sesudah edit.
    Simpan log hanya kalau ada field yang berubah.
    """
    try:
        from devices.models import DeviceLog

        perubahan = []
        for field, label in TRACKED_FIELDS:
            dari = _get_display(device_before, field)
            ke   = _get_display(device_after,  field)
            if dari != ke:
                perubahan.append({
                    'field': field,
                    'label': label,
                    'dari':  dari,
                    'ke':    ke,
                })

        if perubahan:
            DeviceLog.objects.create(
                device=device_after,
                user=user,
                aksi='edit',
                perubahan=perubahan,
            )
    except Exception:
        pass


def log_delete(device, user):
    """Catat event penghapusan device."""
    try:
        from devices.models import DeviceLog
        DeviceLog.objects.create(
            device=device,
            user=user,
            aksi='delete',
            perubahan=[],
        )
    except Exception:
        pass
