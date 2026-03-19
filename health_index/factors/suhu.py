"""
health_index/factors/suhu.py — Faktor Kondisi Suhu
"""
from .base import BaseFactor


class KondisiSuhuFactor(BaseFactor):
    key  = 'kondisi_suhu'
    nama = 'Kondisi Suhu Perangkat'
    icon = 'bi-thermometer-half'

    def calculate(self, device, bobot_maks):
        from maintenance.models import (
            Maintenance, MaintenanceRouter, MaintenanceRadio,
            MaintenanceVoIP, MaintenanceMux, MaintenanceRectifier
        )

        last_m = (
            Maintenance.objects
            .filter(device=device, status='Done')
            .order_by('-date').first()
        )
        if last_m is None:
            return self._result('Tidak ada data', 'Belum ada data suhu tercatat', 0, 'info', bobot_maks)

        suhu = None
        # Coba ambil suhu dari berbagai model detail
        for ModelClass, field in [
            (MaintenanceRouter,    'suhu_perangkat'),
            (MaintenanceRadio,     'suhu_ruangan'),
            (MaintenanceVoIP,      'suhu_ruangan'),
            (MaintenanceMux,       'suhu_ruangan'),
            (MaintenanceRectifier, 'suhu_ruangan'),
        ]:
            try:
                detail = ModelClass.objects.get(maintenance=last_m)
                val = getattr(detail, field, None)
                if val is not None:
                    suhu = val
                    break
            except ModelClass.DoesNotExist:
                continue

        if suhu is None:
            return self._result('Tidak ada data', 'Data suhu tidak tersedia', 0, 'info', bobot_maks)

        tgl = last_m.date.strftime('%d %b %Y')
        nilai = f'{suhu}°C ({tgl})'

        if suhu <= 30:
            deduksi, status, ket = 0, 'good', f'Suhu normal ({suhu}°C)'
        elif suhu <= 40:
            deduksi = round(bobot_maks * 0.50)
            status, ket = 'warning', f'Suhu hangat ({suhu}°C) — perlu ventilasi'
        else:
            deduksi = bobot_maks
            status, ket = 'danger', f'Suhu tinggi ({suhu}°C) — risiko kerusakan'

        return self._result(nilai, ket, deduksi, status, bobot_maks)


"""
health_index/factors/performa.py — Faktor Performa Jaringan (Router/Switch)
"""
from .base import BaseFactor as _BaseFactor


class PerformaJaringanFactor(_BaseFactor):
    key  = 'performa_jaringan'
    nama = 'Performa Jaringan (CPU & Memory)'
    icon = 'bi-cpu'
    jenis_support = ['Router', 'Switch', 'router', 'switch']

    def calculate(self, device, bobot_maks):
        from maintenance.models import Maintenance, MaintenanceRouter

        last_m = (
            Maintenance.objects
            .filter(device=device, status='Done')
            .order_by('-date').first()
        )
        if last_m is None:
            return self._result('Tidak ada data', 'Belum ada data maintenance', 0, 'info', bobot_maks)

        try:
            detail = MaintenanceRouter.objects.get(maintenance=last_m)
        except MaintenanceRouter.DoesNotExist:
            return self._result('Tidak ada data', 'Data performa tidak tersedia', 0, 'info', bobot_maks)

        cpu = detail.cpu_load
        mem = detail.memory_usage
        tgl = last_m.date.strftime('%d %b %Y')

        if cpu is None and mem is None:
            return self._result('Tidak ada data', 'Data CPU/Memory tidak diisi', 0, 'info', bobot_maks)

        nilai = f'CPU {cpu or "?"}% | Mem {mem or "?"}% ({tgl})'
        max_val = max(v for v in [cpu, mem] if v is not None)

        if max_val < 70:
            deduksi, status, ket = 0, 'good', f'Performa normal (CPU {cpu}%, Mem {mem}%)'
        elif max_val < 85:
            deduksi = round(bobot_maks * 0.50)
            status, ket = 'warning', f'Beban cukup tinggi (maks {max_val:.0f}%) — monitor berkala'
        else:
            deduksi = bobot_maks
            status, ket = 'danger', f'Beban sangat tinggi (maks {max_val:.0f}%) — perlu investigasi'

        return self._result(nilai, ket, deduksi, status, bobot_maks)


"""
health_index/factors/power.py — Faktor Kondisi Power (Rectifier/Catu Daya)
"""
from .base import BaseFactor as _BaseFactor2


class KondisiPowerFactor(_BaseFactor2):
    key  = 'kondisi_power'
    nama = 'Kondisi Power & Battery'
    icon = 'bi-battery-charging'
    jenis_support = ['Catu Daya', 'Rectifier', 'catu daya', 'rectifier', 'UPS', 'ups']

    def calculate(self, device, bobot_maks):
        from maintenance.models import Maintenance, MaintenanceRectifier

        last_m = (
            Maintenance.objects
            .filter(device=device, status='Done')
            .order_by('-date').first()
        )
        if last_m is None:
            return self._result('Tidak ada data', 'Belum ada data maintenance', 0, 'info', bobot_maks)

        try:
            detail = MaintenanceRectifier.objects.get(maintenance=last_m)
        except MaintenanceRectifier.DoesNotExist:
            return self._result('Tidak ada data', 'Data power tidak tersedia', 0, 'info', bobot_maks)

        nok_items = []
        checks = {
            'Rectifier 1': detail.rect1_kondisi,
            'Battery 1':   detail.bat1_kondisi,
            'Kabel Bat':   detail.bat1_kondisi_kabel,
            'Mur Baut':    detail.bat1_kondisi_mur_baut,
            'Sel Rak':     detail.bat1_kondisi_sel_rak,
        }
        for nama, val in checks.items():
            if val == 'NOK':
                nok_items.append(nama)

        tgl = last_m.date.strftime('%d %b %Y')
        nilai = f'{len(nok_items)} NOK dari {len([v for v in checks.values() if v])} item ({tgl})'

        if not nok_items:
            deduksi, status, ket = 0, 'good', 'Semua komponen power dalam kondisi OK'
        elif len(nok_items) == 1:
            deduksi = round(bobot_maks * 0.40)
            status, ket = 'warning', f'{nok_items[0]} dalam kondisi NOK'
        else:
            deduksi = bobot_maks
            status, ket = 'danger', f'Beberapa komponen NOK: {", ".join(nok_items)}'

        return self._result(nilai, ket, deduksi, status, bobot_maks)
