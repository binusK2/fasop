"""
Management command: train_beban_forecast
Latih ulang model prediksi beban kit (opsis.forecast) dari seluruh histori
SnapLive dan simpan ke ML_MODEL_ROOT/beban_forecast.joblib.

Jalankan manual:
    python manage.py train_beban_forecast
    python manage.py train_beban_forecast --dry-run   # latih + laporkan MAE/RMSE, jangan simpan

Jadwal via crontab (harian, setelah tengah malam supaya data kemarin lengkap):
    15 0 * * * cd /path/to/fasop && python manage.py train_beban_forecast >> /var/log/fasop/train_beban_forecast.log 2>&1
"""
import logging

from django.core.management.base import BaseCommand

from opsis import forecast

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Latih ulang model prediksi beban kit dari histori SnapLive'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Latih dan laporkan metrik (MAE/RMSE) tanpa menyimpan model',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        prefix = '[DRY-RUN] ' if dry_run else ''

        try:
            metrics = forecast.train(dry_run=dry_run)
        except ValueError as e:
            self.stdout.write(f"{prefix}gagal training: {e}")
            return
        except Exception as e:
            logger.error('train_beban_forecast error: %s', e, exc_info=True)
            self.stdout.write(f"{prefix}error tak terduga: {e}")
            return

        self.stdout.write(
            f"{prefix}rows={metrics['rows']} "
            f"train={metrics['train_rows']} holdout={metrics['holdout_rows']} "
            f"mae={metrics['mae']:.2f} rmse={metrics['rmse']:.2f} "
            f"saved={metrics['saved']}"
        )
