import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _targets():
    from django.conf import settings
    raw = getattr(settings, 'WA_CHAT_IDS_INSPECTION', '') or ''
    return [c.strip() for c in raw.split(',') if c.strip()]


def pesan_alarm(insp, pesan_detail):
    device = insp.device
    lokasi = device.lokasi or '-'
    jenis  = insp.get_jenis_display()
    operator = 'operator'
    if insp.operator:
        operator = insp.operator.get_full_name() or insp.operator.username
    tgl = timezone.localtime(insp.tanggal).strftime('%d-%m-%Y %H:%M:%S')
    kondisi = '\n'.join(f'• {d}' for d in (pesan_detail or []))

    return (
        '🔴 *INSPEKSI ALARM*\n'
        f'Peralatan : {device.nama}\n'
        f'Lokasi    : {lokasi}\n'
        f'Jenis     : {jenis}\n'
        f'Operator  : {operator}\n'
        f'Waktu     : {tgl}\n'
        f'Kondisi   :\n{kondisi}'
        '\n_FASOP — Inspeksi Inservice_'
    )


def alert_inspection(insp, pesan_detail):
    from device_mon.notifications import kirim_wa
    from inspection.models import InspectionAlertLog

    try:
        pesan = pesan_alarm(insp, pesan_detail)
        terkirim, total, ket = kirim_wa(pesan, chat_ids=_targets())

        InspectionAlertLog.objects.create(
            inspection=insp,
            pesan=pesan,
            terkirim=terkirim > 0,
            keterangan=(ket or '')[:255],
        )
        return terkirim > 0
    except Exception as e:
        logger.error('alert_inspection error [%s]: %s',
                     getattr(insp, 'pk', '?'), e)
        return False
