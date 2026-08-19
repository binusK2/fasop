"""
Management command: sync_zabbix
Tarik status host dari Zabbix API (pull) setiap beberapa menit, deteksi
transisi state (OK <-> PROBLEM), simpan ke ZabbixEventLog, dan update
master ZabbixHost.

Ini pelengkap webhook (device_mon.views.zbx_webhook_receiver) yang push
realtime saat trigger naik/turun — sync_zabbix tetap dibutuhkan sebagai
sumber kebenaran periodik: kalau webhook gagal terkirim (Zabbix server
down, jaringan putus, Action belum dikonfigurasi dengan benar) status di
FASOP tidak akan basi lebih dari interval cron ini, dan host BARU yang
belum pernah trigger problem otomatis muncul (dibuat dengan state OK).

Crontab (disarankan tiap 2-5 menit — problem.get relatif ringan):
    */2 * * * * cd /path/to/fasop && /path/to/venv/bin/python manage.py sync_zabbix >> /var/log/fasop/sync_zabbix.log 2>&1

Env yang dibutuhkan (lihat fasop/settings.py blok "Zabbix Integration"):
    ZABBIX_API_URL, dan salah satu dari:
      ZABBIX_API_TOKEN
      ZABBIX_API_USER + ZABBIX_API_PASSWORD
    ZABBIX_HOST_GROUPS (opsional, filter host group)
"""
import datetime
import logging

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from device_mon.models import ZabbixHost, ZabbixEventLog
from device_mon.zabbix_api import get_current_status, ZabbixAPIError
from device_mon.notifications import notif_zabbix_transisi

logger = logging.getLogger(__name__)

RETENSI_HARI = 365   # hapus log lebih dari 1 tahun, sama seperti collect_rtu


def _group_names():
    raw = getattr(settings, 'ZABBIX_HOST_GROUPS', '') or ''
    names = [g.strip() for g in raw.split(',') if g.strip()]
    return names or None


class Command(BaseCommand):
    help = 'Tarik status host dari Zabbix API -> deteksi transisi -> simpan ZabbixEventLog'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Tampilkan output tanpa menyimpan')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        now = timezone.now()

        try:
            status = get_current_status(group_names=_group_names())
        except ZabbixAPIError as e:
            self.stderr.write(f'[ERROR] {e}')
            return
        except Exception as e:
            logger.error('sync_zabbix error tak terduga: %s', e)
            self.stderr.write(f'[ERROR] {e}')
            return

        if not status:
            self.stdout.write('Tidak ada host dari Zabbix API (cek ZABBIX_HOST_GROUPS / status host).')
            return

        transisi = 0
        error = 0
        host_baru = 0

        for hostid, info in status.items():
            try:
                state = info['state']
                if dry_run:
                    self.stdout.write(
                        f"[DRY] {info['name'] or info['host']} ({hostid}): {state} "
                        f"{info['problem_name'] or ''}"
                    )
                    continue

                host, created = ZabbixHost.objects.get_or_create(
                    zabbix_hostid=hostid,
                    defaults={
                        'zabbix_host': info['host'],
                        'nama': info['name'] or info['host'] or hostid,
                    },
                )
                if created:
                    host_baru += 1
                # Technical name/nama tampilan bisa berubah di sisi Zabbix — refresh ringan
                update_fields = []
                if info['host'] and host.zabbix_host != info['host']:
                    host.zabbix_host = info['host']
                    update_fields.append('zabbix_host')

                prev_state = host.state
                clock = info.get('clock')
                event_since = (
                    timezone.make_aware(datetime.datetime.fromtimestamp(int(clock)))
                    if clock else now
                )

                if prev_state != state or created:
                    # ── Transisi state terdeteksi ──────────────────────
                    dur_tutup = None
                    open_log = ZabbixEventLog.objects.filter(host=host, selesai__isnull=True).first()
                    if open_log:
                        selesai = event_since if state == 'OK' else now
                        dur = max(0, int((selesai - open_log.mulai).total_seconds() / 60))
                        open_log.selesai = selesai
                        open_log.durasi_menit = dur
                        open_log.save(update_fields=['selesai', 'durasi_menit'])
                        dur_tutup = dur

                    ZabbixEventLog.objects.create(
                        host=host,
                        state=state,
                        severity=info.get('severity', ''),
                        problem_name=info.get('problem_name', ''),
                        zabbix_eventid=info.get('eventid') or '',
                        source='api',
                        mulai=event_since if state == 'PROBLEM' else now,
                    )

                    host.state = state
                    host.severity = info.get('severity', '')
                    host.problem_name = info.get('problem_name', '')
                    host.state_sejak = event_since if state == 'PROBLEM' else now
                    update_fields += ['state', 'severity', 'problem_name', 'state_sejak']

                    self.stdout.write(
                        f"  [TRANSISI] {host.nama}: {prev_state} -> {state} "
                        f"({info.get('problem_name') or '-'})"
                    )
                    transisi += 1

                    if not created and host.aktif:
                        notif_zabbix_transisi(host, state, dur_tutup_menit=dur_tutup)
                else:
                    # State sama — sinkronkan problem_name/severity kalau berubah
                    # (mis. severity naik tapi masih 1 problem yang sama).
                    if state == 'PROBLEM' and (
                        host.problem_name != info.get('problem_name', '') or
                        host.severity != info.get('severity', '')
                    ):
                        host.problem_name = info.get('problem_name', '')
                        host.severity = info.get('severity', '')
                        update_fields += ['problem_name', 'severity']

                host.last_synced_at = now
                update_fields.append('last_synced_at')
                if update_fields:
                    host.save(update_fields=list(set(update_fields)))

            except Exception as e:
                logger.error('sync_zabbix error [%s]: %s', hostid, e)
                error += 1

        if not dry_run:
            batas = now - timezone.timedelta(days=RETENSI_HARI)
            deleted, _ = ZabbixEventLog.objects.filter(mulai__lt=batas).delete()
        else:
            deleted = 0

        tz_local = timezone.get_current_timezone()
        now_str = now.astimezone(tz_local).strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(
            f'[{now_str}] host={len(status)} baru={host_baru} transisi={transisi} '
            f'error={error} purged={deleted}'
        )
