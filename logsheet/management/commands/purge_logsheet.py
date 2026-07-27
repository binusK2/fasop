"""Hapus nilai logsheet lebih lama dari retensi (default 30 hari). Cron harian."""
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Hapus LogsheetNilai lebih lama dari N hari (retensi bergulir).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        from logsheet.models import LogsheetNilai
        batas = timezone.localdate() - datetime.timedelta(days=opts['days'])
        qs = LogsheetNilai.objects.filter(tanggal__lt=batas)
        n = qs.count()
        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(f'[dry-run] {n} baris < {batas} akan dihapus.'))
            return
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f'{n} baris logsheet < {batas} dihapus.'))
