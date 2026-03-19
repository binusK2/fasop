"""
health_index/factors/kualitas.py

Faktor Kualitas Hasil Pemeliharaan.
Membaca hasil checklist OK/NOK dari maintenance terakhir
(Router, Switch, PLC, VoIP, MUX, Rectifier).
"""
from .base import BaseFactor


def _count_nok(obj, fields):
    """Hitung berapa field bernilai 'NOK' dari sebuah objek maintenance detail."""
    if obj is None:
        return None, 0
    total_checked = 0
    nok_count = 0
    for field in fields:
        val = getattr(obj, field, '')
        if val in ('OK', 'NOK'):
            total_checked += 1
            if val == 'NOK':
                nok_count += 1
    return total_checked, nok_count


class KualitasHasilFactor(BaseFactor):
    key  = 'kualitas_hasil'
    nama = 'Kualitas Hasil Pemeliharaan'
    icon = 'bi-clipboard2-check'

    # Field checklist OK/NOK per jenis maintenance detail
    CHECKLIST_FIELDS = {
        'MaintenanceRouter': [
            'kondisi_fisik', 'led_link', 'kondisi_kabel', 'status_routing'
        ],
        'MaintenancePLC': [
            'akses_plc', 'remote_akses_plc', 'time_sync',
            'wave_trap', 'imu', 'kabel_coaxial'
        ],
        'MaintenanceVoIP': [
            'kondisi_fisik', 'ntp_server', 'webconfig', 'ps_status'
        ],
        'MaintenanceMux': [
            'psu1_status', 'psu2_status', 'fan_status'
        ],
        'MaintenanceRectifier': [
            'rect1_kondisi', 'bat1_kondisi',
            'bat1_kondisi_kabel', 'bat1_kondisi_mur_baut', 'bat1_kondisi_sel_rak'
        ],
    }

    def calculate(self, device, bobot_maks):
        from maintenance.models import (
            Maintenance, MaintenanceRouter, MaintenancePLC,
            MaintenanceVoIP, MaintenanceMux, MaintenanceRectifier
        )

        # Ambil maintenance Preventive terakhir yang Done
        last_m = (
            Maintenance.objects
            .filter(device=device, status='Done', maintenance_type='Preventive')
            .order_by('-date').first()
        )

        if last_m is None:
            return self._result(
                'Tidak ada data',
                'Belum ada maintenance Preventive tercatat',
                round(bobot_maks * 0.50), 'unknown', bobot_maks
            )

        # Coba ambil detail maintenance sesuai jenis
        detail_map = [
            (MaintenanceRouter,    'MaintenanceRouter'),
            (MaintenancePLC,       'MaintenancePLC'),
            (MaintenanceVoIP,      'MaintenanceVoIP'),
            (MaintenanceMux,       'MaintenanceMux'),
            (MaintenanceRectifier, 'MaintenanceRectifier'),
        ]

        total_checked = 0
        nok_count     = 0
        detail_nama   = None

        for ModelClass, model_name in detail_map:
            try:
                detail = ModelClass.objects.get(maintenance=last_m)
                fields = self.CHECKLIST_FIELDS.get(model_name, [])
                tc, nc = _count_nok(detail, fields)
                total_checked += tc
                nok_count     += nc
                detail_nama    = model_name.replace('Maintenance', '')
                break
            except ModelClass.DoesNotExist:
                continue

        if total_checked == 0:
            return self._result(
                'Tidak ada checklist',
                'Jenis peralatan tidak memiliki checklist OK/NOK',
                0, 'info', bobot_maks
            )

        tgl = last_m.date.strftime('%d %b %Y')
        nilai = f'{nok_count} NOK dari {total_checked} item ({tgl})'

        if nok_count == 0:
            deduksi, status, ket = 0, 'good', f'Semua {total_checked} item checklist OK'
        elif nok_count <= 2:
            deduksi = round(bobot_maks * 0.35)
            status, ket = 'warning', f'{nok_count} item NOK — perlu tindak lanjut'
        elif nok_count <= 4:
            deduksi = round(bobot_maks * 0.65)
            status, ket = 'danger', f'{nok_count} item NOK — kondisi mengkhawatirkan'
        else:
            deduksi = bobot_maks
            status, ket = 'danger', f'{nok_count} item NOK — banyak anomali ditemukan'

        return self._result(nilai, ket, deduksi, status, bobot_maks)
