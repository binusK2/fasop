import datetime
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from fasop.hashids_helper import encode
from .models import ZabbixHost, ZabbixEventLog, ZabbixWebhookLog
from .notifications import notif_transisi

logger = logging.getLogger(__name__)


def _boundaries():
    tz_local = timezone.get_current_timezone()
    now = timezone.now()
    now_local = now.astimezone(tz_local)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return now, today_start


def _calc_avail(logs_problem, since, now, total_menit):
    down_menit = 0
    for log in logs_problem:
        start = max(log.mulai, since)
        end = min(log.selesai, now) if log.selesai else now
        down_menit += max(0, int((end - start).total_seconds() / 60))
    up_menit = max(0, total_menit - down_menit)
    return round(up_menit / total_menit * 100, 2)


@login_required
def dashboard(request):
    return render(request, 'zabbix_mon/dashboard.html')


@login_required
def api_status(request):
    """JSON: status semua host Zabbix + availability hari ini. Dipoll dashboard tiap ~30-60s."""
    now, today_start = _boundaries()

    hosts = list(ZabbixHost.objects.filter(aktif=True).select_related('device'))
    if not hosts:
        return JsonResponse({
            'total_ok': 0, 'total_problem': 0, 'total_unknown': 0, 'total_host': 0,
            'avail_hari': None, 'hosts': [], 'gangguan_terkini': [],
        })

    host_ids = [h.pk for h in hosts]
    down_today = list(
        ZabbixEventLog.objects.filter(
            host_id__in=host_ids, state='PROBLEM', mulai__lt=now,
        ).filter(Q(selesai__gt=today_start) | Q(selesai__isnull=True))
    )
    today_by_host = {}
    for log in down_today:
        today_by_host.setdefault(log.host_id, []).append(log)

    total_menit_today = max(1, int((now - today_start).total_seconds() / 60))

    host_data = []
    total_ok = total_problem = total_unknown = 0
    avail_list = []

    for h in hosts:
        if h.state == 'OK':
            total_ok += 1
        elif h.state == 'PROBLEM':
            total_problem += 1
        else:
            total_unknown += 1

        avail_hari = _calc_avail(today_by_host.get(h.pk, []), today_start, now, total_menit_today)
        avail_list.append(avail_hari)

        host_data.append({
            'id': encode(h.pk),
            'nama': h.nama,
            'lokasi': h.lokasi,
            'device': h.device.nama if h.device_id else None,
            'state': h.state,
            'severity': h.severity,
            'problem_name': h.problem_name,
            'state_sejak': h.state_sejak.isoformat() if h.state_sejak else None,
            'durasi_menit': h.durasi_menit,
            'avail_hari': avail_hari,
            'last_synced_at': h.last_synced_at.isoformat() if h.last_synced_at else None,
        })

    avg_avail = round(sum(avail_list) / len(avail_list), 2) if avail_list else None

    gangguan = (ZabbixEventLog.objects.filter(state='PROBLEM')
                .select_related('host').order_by('-mulai')[:10])
    gangguan_data = [{
        'host': g.host.nama,
        'severity': g.severity,
        'problem_name': g.problem_name,
        'mulai': g.mulai.isoformat(),
        'selesai': g.selesai.isoformat() if g.selesai else None,
        'durasi_menit': g.durasi_menit,
    } for g in gangguan]

    return JsonResponse({
        'total_ok': total_ok,
        'total_problem': total_problem,
        'total_unknown': total_unknown,
        'total_host': len(host_data),
        'avail_hari': avg_avail,
        'hosts': host_data,
        'gangguan_terkini': gangguan_data,
    })


@login_required
def host_detail(request, pk):
    host = get_object_or_404(ZabbixHost, pk=pk)
    return render(request, 'zabbix_mon/host_detail.html', {'host': host})


@login_required
def api_host_logs(request, pk):
    host = get_object_or_404(ZabbixHost, pk=pk)

    try:
        hari = min(max(int(request.GET.get('hari', 7)), 1), 30)
    except (ValueError, TypeError):
        hari = 7

    now, today_start = _boundaries()
    tz_local = timezone.get_current_timezone()
    since = now - datetime.timedelta(days=hari)

    logs = ZabbixEventLog.objects.filter(host=host, mulai__gte=since).order_by('mulai')
    total_menit = max(1, int((now - since).total_seconds() / 60))
    problem_logs = [l for l in logs if l.state == 'PROBLEM']
    avail_periode = _calc_avail(problem_logs, since, now, total_menit)

    down_today = [l for l in ZabbixEventLog.objects.filter(
        host=host, state='PROBLEM', mulai__lt=now,
    ).filter(Q(selesai__gt=today_start) | Q(selesai__isnull=True))]
    avail_hari = _calc_avail(down_today, today_start, now,
                             max(1, int((now - today_start).total_seconds() / 60)))

    log_data = []
    for l in logs:
        mulai_local = l.mulai.astimezone(tz_local)
        selesai_local = l.selesai.astimezone(tz_local) if l.selesai else None
        dur = l.durasi_menit
        if dur is None and not l.selesai:
            dur = max(0, int((now - l.mulai).total_seconds() / 60))
        log_data.append({
            'state': l.state,
            'severity': l.severity,
            'problem_name': l.problem_name,
            'source': l.source,
            'mulai': mulai_local.strftime('%d/%m %H:%M'),
            'selesai': selesai_local.strftime('%d/%m %H:%M') if selesai_local else None,
            'durasi_menit': dur,
        })

    return JsonResponse({
        'nama': host.nama,
        'lokasi': host.lokasi,
        'state': host.state,
        'severity': host.severity,
        'problem_name': host.problem_name,
        'state_sejak': host.state_sejak.astimezone(tz_local).strftime('%d/%m/%Y %H:%M') if host.state_sejak else None,
        'durasi_menit': host.durasi_menit,
        'avail_hari': avail_hari,
        'avail_periode': avail_periode,
        'hari': hari,
        'logs': log_data,
    })


@login_required
def gangguan_list(request):
    logs = (ZabbixEventLog.objects.filter(state='PROBLEM')
            .select_related('host').order_by('-mulai')[:200])
    return render(request, 'zabbix_mon/gangguan.html', {'logs': logs})


# ═══════════════════════════════════════════════════════════════════════════
#  Webhook — dipanggil oleh Zabbix Action (media type "Webhook"), push realtime
# ═══════════════════════════════════════════════════════════════════════════
def _check_webhook_token(request):
    from django.conf import settings
    expected = getattr(settings, 'ZABBIX_WEBHOOK_TOKEN', '')
    if not expected:
        return False, 'ZABBIX_WEBHOOK_TOKEN belum dikonfigurasi di server.'
    got = request.headers.get('X-Zabbix-Webhook-Token') or request.GET.get('token', '')
    import hmac
    if not got or not hmac.compare_digest(str(got), str(expected)):
        return False, 'Token webhook tidak valid.'
    return True, ''


@csrf_exempt
@require_http_methods(["POST"])
def webhook_receiver(request):
    """
    Terima push realtime dari Zabbix Action (media type Webhook) saat trigger
    naik (PROBLEM) atau pulih (OK/RESOLVED). Lihat deploy/ZABBIX_INTEGRATION.md
    untuk skrip webhook Zabbix-nya dan daftar macro yang harus diisikan.

    Auth: header X-Zabbix-Webhook-Token: <ZABBIX_WEBHOOK_TOKEN>
          (atau ?token=... kalau Zabbix versi lama tidak bisa set header custom)

    Body JSON:
      {
        "event_status": "PROBLEM" | "OK" | "RESOLVED",
        "eventid": "12345",
        "hostid": "10084",
        "host": "nama-teknis",
        "host_visible_name": "Nama Tampilan",
        "severity": "High",
        "problem_name": "Free disk space is low",
        "event_time": "2026-08-18T10:00:00+08:00"   # opsional, ISO8601
      }
    """
    ok_token, msg = _check_webhook_token(request)
    raw_body = request.body.decode('utf-8', errors='replace')[:4000]

    if not ok_token:
        ZabbixWebhookLog.objects.create(ok=False, keterangan=msg, payload=raw_body)
        return HttpResponseForbidden(msg)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        ZabbixWebhookLog.objects.create(ok=False, keterangan='Body bukan JSON valid.', payload=raw_body)
        return JsonResponse({'status': 'error', 'message': 'Body bukan JSON valid.'}, status=400)

    hostid = str(data.get('hostid', '')).strip()
    if not hostid:
        ZabbixWebhookLog.objects.create(ok=False, keterangan='Field hostid kosong.', payload=raw_body)
        return JsonResponse({'status': 'error', 'message': "Field 'hostid' wajib diisi."}, status=400)

    raw_status = str(data.get('event_status', '')).strip().upper()
    state = 'OK' if raw_status in ('OK', 'RESOLVED') else 'PROBLEM' if raw_status == 'PROBLEM' else None
    if state is None:
        ZabbixWebhookLog.objects.create(
            ok=False, keterangan=f'event_status tidak dikenali: {raw_status!r}', payload=raw_body,
        )
        return JsonResponse({'status': 'error', 'message': 'event_status harus PROBLEM/OK/RESOLVED.'}, status=400)

    host_name = (data.get('host_visible_name') or data.get('host') or hostid).strip()
    eventid = str(data.get('eventid', '')).strip()

    now = timezone.now()
    event_time_raw = data.get('event_time')
    event_time = now
    if event_time_raw:
        try:
            event_time = datetime.datetime.fromisoformat(str(event_time_raw).replace('Z', '+00:00'))
            if timezone.is_naive(event_time):
                event_time = timezone.make_aware(event_time)
        except ValueError:
            event_time = now

    host, created = ZabbixHost.objects.get_or_create(
        zabbix_hostid=hostid,
        defaults={'zabbix_host': data.get('host', '') or host_name, 'nama': host_name},
    )

    # Idempotensi: kalau eventid ini sudah pernah dicatat untuk state yang sama, jangan dobel.
    if eventid and ZabbixEventLog.objects.filter(
        host=host, zabbix_eventid=eventid, state=state,
    ).exists():
        ZabbixWebhookLog.objects.create(
            ok=True, host=host, keterangan='Duplikat eventid, diabaikan.', payload=raw_body,
        )
        return JsonResponse({'status': 'ok', 'message': 'Duplikat, diabaikan.'})

    prev_state = host.state
    dur_tutup = None
    if prev_state != state or created:
        open_log = ZabbixEventLog.objects.filter(host=host, selesai__isnull=True).first()
        if open_log:
            selesai = event_time if state == 'OK' else now
            dur = max(0, int((selesai - open_log.mulai).total_seconds() / 60))
            open_log.selesai = selesai
            open_log.durasi_menit = dur
            open_log.save(update_fields=['selesai', 'durasi_menit'])
            dur_tutup = dur

        ZabbixEventLog.objects.create(
            host=host, state=state,
            severity=data.get('severity', '') or '',
            problem_name=data.get('problem_name', '') or '',
            zabbix_eventid=eventid, source='webhook',
            mulai=event_time if state == 'PROBLEM' else now,
        )

        host.state = state
        host.severity = data.get('severity', '') or '' if state == 'PROBLEM' else ''
        host.problem_name = data.get('problem_name', '') or '' if state == 'PROBLEM' else ''
        host.state_sejak = event_time if state == 'PROBLEM' else now
        host.last_synced_at = now
        host.save(update_fields=['state', 'severity', 'problem_name', 'state_sejak', 'last_synced_at'])

        if not created and host.aktif:
            notif_transisi(host, state, dur_tutup_menit=dur_tutup)
    else:
        host.last_synced_at = now
        host.save(update_fields=['last_synced_at'])

    ZabbixWebhookLog.objects.create(ok=True, host=host, keterangan=f'{prev_state} -> {state}', payload=raw_body)
    return JsonResponse({'status': 'ok', 'host': host.nama, 'state': host.state})
