"""
Management command: sync_zabbix
Tarik status host dari setiap Instansi Zabbix AKTIF (device_mon.ZabbixInstance
— mis. "Zabbix Telkom", "Zabbix Prosis") lewat Zabbix API (pull) setiap
beberapa menit, deteksi transisi state (OK <-> PROBLEM), simpan ke
ZabbixEventLog, dan update master ZabbixHost.

Ini pelengkap webhook (device_mon.views.zbx_webhook_receiver) yang push
realtime saat trigger naik/turun — sync_zabbix tetap dibutuhkan sebagai
sumber kebenaran periodik: kalau webhook gagal terkirim (Zabbix server
down, jaringan putus, Action belum dikonfigurasi dengan benar) status di
FASOP tidak akan basi lebih dari interval cron ini, dan host BARU yang
belum pernah trigger problem otomatis muncul (dibuat dengan state OK).

Satu instansi gagal (URL salah, kredensial kedaluwarsa) tidak menghentikan
instansi lain — pola yang sama dengan opsis.SumberKit: "satu sumber rusak
hanya memadamkan pembangkit yang memakainya".

Crontab (disarankan tiap 2-5 menit — problem.get relatif ringan):
    */2 * * * * cd /path/to/fasop && /path/to/venv/bin/python manage.py sync_zabbix >> /var/log/fasop/sync_zabbix.log 2>&1

Kredensial per instansi diatur dari Admin -> Device Mon -> Instansi Zabbix.
Field yang dikosongkan di sana jatuh ke ZABBIX_API_* di .env (lihat
device_mon.models.ZabbixInstance) — pemasangan lama (satu instansi, "Zabbix
Telkom") tidak perlu mengisi apa pun di .env selain yang sudah ada.
"""
import datetime
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from device_mon.models import ZabbixInstance, ZabbixHost, ZabbixEventLog
from device_mon.zabbix_api import get_current_status, get_resolve_clock, ZabbixAPIError
from device_mon.notifications import notif_zabbix_transisi

logger = logging.getLogger(__name__)

RETENSI_HARI = 365   # hapus log lebih dari 1 tahun, sama seperti collect_rtu


class Command(BaseCommand):
    help = ('Tarik status host dari setiap Instansi Zabbix aktif -> deteksi transisi -> '
            'simpan ZabbixEventLog')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Tampilkan output tanpa menyimpan')
        parser.add_argument('--instansi', default='',
                            help='Batasi ke satu kode instansi (mis. telkom). '
                                 'Kosong = semua instansi aktif.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        kode_filter = (options.get('instansi') or '').strip()
        now = timezone.now()

        instansi_qs = ZabbixInstance.objects.filter(aktif=True)
        if kode_filter:
            instansi_qs = instansi_qs.filter(kode=kode_filter)
        instansi_list = list(instansi_qs)

        if not instansi_list:
            self.stdout.write(
                'Tidak ada Instansi Zabbix aktif yang cocok '
                '(Admin > Device Mon > Instansi Zabbix).'
            )
            return

        total = {'host': 0, 'baru': 0, 'transisi': 0, 'error': 0}
        for instansi in instansi_list:
            hasil = self._sync_instansi(instansi, now, dry_run)
            for k in total:
                total[k] += hasil[k]

        if not dry_run:
            batas = now - timezone.timedelta(days=RETENSI_HARI)
            deleted, _ = ZabbixEventLog.objects.filter(mulai__lt=batas).delete()
        else:
            deleted = 0

        tz_local = timezone.get_current_timezone()
        now_str = now.astimezone(tz_local).strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(
            f"[{now_str}] instansi={len(instansi_list)} host={total['host']} "
            f"baru={total['baru']} transisi={total['transisi']} error={total['error']} "
            f'purged={deleted}'
        )

    def _sync_instansi(self, instansi, now, dry_run):
        hasil = {'host': 0, 'baru': 0, 'transisi': 0, 'error': 0}
        client = instansi.client()

        try:
            status = get_current_status(group_names=instansi.host_groups_list(), client=client)
        except ZabbixAPIError as e:
            self.stderr.write(f'[ERROR] {instansi.nama}: {e}')
            return hasil
        except Exception as e:
            logger.error('sync_zabbix error tak terduga [%s]: %s', instansi.kode, e)
            self.stderr.write(f'[ERROR] {instansi.nama}: {e}')
            return hasil

        if not status:
            self.stdout.write(
                f'{instansi.nama}: tidak ada host dari Zabbix API '
                f'(cek Filter Host Group / status host).'
            )
            return hasil

        hasil['host'] = len(status)

        for hostid, info in status.items():
            try:
                state = info['state']
                if dry_run:
                    self.stdout.write(
                        f"[DRY {instansi.kode}] {info['name'] or info['host']} ({hostid}): "
                        f"{state} {info['problem_name'] or ''}"
                    )
                    continue

                host, created = ZabbixHost.objects.get_or_create(
                    instance=instansi, zabbix_hostid=hostid,
                    defaults={
                        'zabbix_host': info['host'],
                        'nama': info['name'] or info['host'] or hostid,
                        'groups': info.get('groups', ''),
                    },
                )
                if created:
                    hasil['baru'] += 1
                # Technical name/nama tampilan/grup bisa berubah di sisi Zabbix — refresh ringan
                update_fields = []
                if info['host'] and host.zabbix_host != info['host']:
                    host.zabbix_host = info['host']
                    update_fields.append('zabbix_host')
                if not created and host.groups != info.get('groups', ''):
                    host.groups = info.get('groups', '')
                    update_fields.append('groups')

                prev_state = host.state
                clock = info.get('clock')
                event_since = (
                    timezone.make_aware(datetime.datetime.fromtimestamp(int(clock)))
                    if clock else None
                )

                if prev_state != state or created:
                    # ── Transisi state terdeteksi ──────────────────────
                    # Timestamp SELALU dari Zabbix, bukan "kapan cron ini
                    # kebetulan jalan": PROBLEM pakai `clock` problem.get
                    # (event_since di atas); OK/resolve pakai r_clock dari
                    # event resolve-nya (lookup event.get terpisah, lihat
                    # get_resolve_clock) — problem.get sendiri tidak
                    # mengembalikan waktu resolve untuk problem yang sudah
                    # tidak aktif lagi. Fallback ke `now` FASOP hanya kalau
                    # datanya benar-benar tidak ada (mis. host baru pertama
                    # kali muncul dan sudah OK sejak awal, tidak ada event
                    # untuk ditelusuri).
                    dur_tutup = None
                    open_log = ZabbixEventLog.objects.filter(host=host, selesai__isnull=True).first()

                    if state == 'OK' and open_log and open_log.zabbix_eventid:
                        try:
                            resolve_ts = get_resolve_clock(open_log.zabbix_eventid, client=client)
                        except ZabbixAPIError as e:
                            logger.warning('get_resolve_clock gagal [%s/%s]: %s',
                                           instansi.kode, hostid, e)
                            resolve_ts = None
                        state_change_ts = (
                            timezone.make_aware(datetime.datetime.fromtimestamp(resolve_ts))
                            if resolve_ts else now
                        )
                    elif state == 'PROBLEM' and event_since:
                        state_change_ts = event_since
                    else:
                        state_change_ts = now

                    if open_log:
                        dur = max(0, int((state_change_ts - open_log.mulai).total_seconds() / 60))
                        open_log.selesai = state_change_ts
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
                        mulai=state_change_ts,
                    )

                    host.state = state
                    host.severity = info.get('severity', '')
                    host.problem_name = info.get('problem_name', '')
                    host.state_sejak = state_change_ts
                    update_fields += ['state', 'severity', 'problem_name', 'state_sejak']

                    self.stdout.write(
                        f"  [TRANSISI {instansi.kode}] {host.nama}: {prev_state} -> {state} "
                        f"({info.get('problem_name') or '-'})"
                    )
                    hasil['transisi'] += 1

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
                logger.error('sync_zabbix error [%s/%s]: %s', instansi.kode, hostid, e)
                hasil['error'] += 1

        return hasil
