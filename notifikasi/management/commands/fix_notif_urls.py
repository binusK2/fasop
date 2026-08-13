"""
One-time command: rewrite stale integer-based notification URLs to hashid URLs.
Run: python manage.py fix_notif_urls
"""
import re
from django.core.management.base import BaseCommand
from notifikasi.models import Notifikasi
from fasop.hashids_helper import encode


_PATTERNS = [
    (re.compile(r'^/health-index/(\d+)/$'),       '/health-index/{}/'),
    (re.compile(r'^/view/(\d+)/$'),               '/view/{}/'),
    (re.compile(r'^/inspection/riwayat/(\d+)/$'), '/inspection/riwayat/{}/'),
    (re.compile(r'^/maintenance/view/(\d+)/$'),   '/maintenance/view/{}/'),
    (re.compile(r'^/gangguan/(\d+)/$'),           '/gangguan/{}/'),
]


class Command(BaseCommand):
    help = 'Rewrite notification URLs from raw integer PKs to hashids'

    def handle(self, *args, **options):
        updated = 0
        for notif in Notifikasi.objects.exclude(url='').exclude(url=None):
            for pattern, template in _PATTERNS:
                m = pattern.match(notif.url or '')
                if m:
                    new_url = template.format(encode(int(m.group(1))))
                    notif.url = new_url
                    notif.save(update_fields=['url'])
                    updated += 1
                    break
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} notification URL(s).'))
