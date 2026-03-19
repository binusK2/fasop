"""
health_index/factors/maintenance.py — Faktor Maintenance Gap & Corrective Count
"""
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .base import BaseFactor


class MaintenanceGapFactor(BaseFactor):
    key  = 'maintenance_gap'
    nama = 'Maintenance Terakhir'
    icon = 'bi-tools'

    def calculate(self, device, bobot_maks):
        from maintenance.models import Maintenance
        now = timezone.now()

        last_m = (
            Maintenance.objects
            .filter(device=device, status='Done')
            .order_by('-date').first()
        )

        if last_m is None:
            return self._result('Belum pernah', 'Belum pernah dilakukan maintenance',
                                bobot_maks, 'danger', bobot_maks)

        rd = relativedelta(now, last_m.date)
        bulan_lalu = rd.years * 12 + rd.months
        tgl_str = last_m.date.strftime('%d %b %Y')

        if bulan_lalu > 12:
            deduksi, status, ket = round(bobot_maks * 0.80), 'danger',  f'Sudah {bulan_lalu} bulan sejak maintenance terakhir'
        elif bulan_lalu > 6:
            deduksi, status, ket = round(bobot_maks * 0.40), 'warning', f'Sudah {bulan_lalu} bulan sejak maintenance terakhir'
        else:
            deduksi, status, ket = 0, 'good', f'Maintenance rutin terpenuhi ({bulan_lalu} bulan lalu)'

        return self._result(f'{tgl_str} ({bulan_lalu} bulan lalu)', ket, deduksi, status, bobot_maks)


class CorrectiveCountFactor(BaseFactor):
    key  = 'corrective_count'
    nama = 'Corrective Maintenance (1 Tahun)'
    icon = 'bi-wrench-adjustable'

    def calculate(self, device, bobot_maks):
        from maintenance.models import Maintenance
        satu_tahun_lalu = timezone.now() - relativedelta(years=1)

        count = Maintenance.objects.filter(
            device=device,
            maintenance_type='Corrective',
            date__gte=satu_tahun_lalu
        ).count()

        if count >= 3:
            deduksi, status, ket = bobot_maks, 'danger',  f'{count}× corrective — indikasi masalah berulang'
        elif count == 2:
            deduksi, status, ket = round(bobot_maks * 0.67), 'warning', f'{count}× corrective — perlu investigasi'
        elif count == 1:
            deduksi, status, ket = round(bobot_maks * 0.33), 'info',    f'{count}× corrective dalam setahun'
        else:
            deduksi, status, ket = 0, 'good', 'Tidak ada corrective maintenance dalam 1 tahun'

        return self._result(f'{count} kali', ket, deduksi, status, bobot_maks)
