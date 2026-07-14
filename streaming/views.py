import json
import os
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    HttpResponseForbidden,
    HttpResponseNotFound,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from notifikasi.views import notif_ke_am, notif_ke_teknisi

from .models import LiveSession, LiveViewerHeartbeat
from .permissions import (
    can_join_as_pengawas,
    can_start_stream,
    require_streaming_access,
)

# Heartbeat penonton dianggap basi (tidak lagi nonton) setelah sekian detik
# tanpa ping baru — harus lebih besar dari interval kirim di viewer.html
# (10 detik) supaya toleran jaringan lambat, tapi tetap terasa "real-time".
VIEWER_HEARTBEAT_STALE_SECONDS = 20


@login_required
@require_streaming_access
def session_list(request):
    active_sessions = (
        LiveSession.objects.filter(status='live')
        .select_related('teknisi', 'teknisi__profile', 'pengawas', 'pengawas__profile')
    )
    recent_sessions = (
        LiveSession.objects.filter(status='ended')
        .select_related('teknisi', 'teknisi__profile', 'pengawas', 'pengawas__profile')[:20]
    )
    return render(request, 'streaming/list.html', {
        'active_sessions': active_sessions,
        'recent_sessions': recent_sessions,
        'can_start': can_start_stream(request.user),
    })


@login_required
@require_streaming_access
@require_POST
def start_session(request):
    if not can_start_stream(request.user):
        return HttpResponseForbidden('Hanya Teknisi yang bisa memulai live streaming.')

    judul = request.POST.get('judul', '').strip()
    nama_teknisi = request.user.profile.get_display_name() if hasattr(request.user, 'profile') else request.user.username

    session = LiveSession.objects.create(
        teknisi=request.user,
        judul=judul or f'Live Pemeliharaan — {nama_teknisi}',
    )

    detail_url = reverse('streaming:detail', kwargs={'pk': session.pk})
    pesan = f'{nama_teknisi} memulai live streaming: {session.judul}'
    notif_ke_teknisi(
        tipe='live_dimulai', judul='Live Streaming Dimulai', pesan=pesan,
        level='info', url=detail_url, exclude_user=request.user,
    )
    notif_ke_am(
        tipe='live_dimulai', judul='Live Streaming Dimulai', pesan=pesan,
        level='info', url=detail_url,
    )

    return redirect('streaming:detail', pk=session.pk)


@login_required
@require_streaming_access
def session_detail(request, pk):
    session = get_object_or_404(LiveSession, pk=pk)
    is_broadcaster = request.user.id == session.teknisi_id
    is_pengawas = session.pengawas_id == request.user.id
    can_claim_pengawas = (
        session.is_live and session.pengawas_id is None
        and not is_broadcaster and can_join_as_pengawas(request.user)
    )

    context = {
        'session': session,
        'is_broadcaster': is_broadcaster,
        'is_pengawas': is_pengawas,
        'can_claim_pengawas': can_claim_pengawas,
        'whip_url': settings.MEDIAMTX_WHIP_URL,
        'whep_url': settings.MEDIAMTX_WHEP_URL,
        'ice_servers_json': settings.WEBRTC_ICE_SERVERS,
    }

    if is_broadcaster:
        return render(request, 'streaming/broadcast.html', context)
    if is_pengawas:
        return render(request, 'streaming/pengawas.html', context)
    return render(request, 'streaming/viewer.html', context)


@login_required
@require_streaming_access
def session_status(request, pk):
    """
    JSON ringan untuk di-poll halaman broadcaster & viewer — supaya tahu
    kapan pengawas gabung / sesi berakhir SETELAH halaman sudah dibuka
    (dicek sekali saat render saja tidak cukup untuk kejadian yang terjadi
    belakangan, semua page ini tidak pakai websocket).
    """
    session = get_object_or_404(LiveSession, pk=pk)
    batas = timezone.now() - timezone.timedelta(seconds=VIEWER_HEARTBEAT_STALE_SECONDS)
    viewer_count = LiveViewerHeartbeat.objects.filter(session=session, last_seen__gte=batas).count()
    return JsonResponse({
        'is_live': session.is_live,
        'has_pengawas': session.pengawas_id is not None,
        'viewer_count': viewer_count,
    })


@login_required
@require_streaming_access
@require_POST
def session_heartbeat(request, pk):
    """Dipanggil berkala oleh viewer.html/pengawas.html selama nonton — dasar hitung penonton aktif."""
    session = get_object_or_404(LiveSession, pk=pk)
    LiveViewerHeartbeat.objects.update_or_create(session=session, user=request.user)
    return JsonResponse({'ok': True})


@login_required
@require_streaming_access
@require_POST
def join_pengawas(request, pk):
    session = get_object_or_404(LiveSession, pk=pk)
    if not can_join_as_pengawas(request.user):
        return HttpResponseForbidden('Hanya Asisten Manager yang bisa menjadi pengawas.')
    if not session.is_live:
        return HttpResponseForbidden('Sesi live sudah berakhir.')
    if session.pengawas_id and session.pengawas_id != request.user.id:
        return HttpResponseForbidden('Sudah ada pengawas lain untuk sesi ini.')
    session.assign_pengawas(request.user)
    return redirect('streaming:detail', pk=session.pk)


@login_required
@require_streaming_access
@require_POST
def end_session(request, pk):
    session = get_object_or_404(LiveSession, pk=pk)
    if request.user.id != session.teknisi_id and not request.user.is_superuser:
        return HttpResponseForbidden('Hanya Teknisi yang memulai sesi ini yang bisa mengakhiri.')
    session.end()
    return redirect('streaming:list')


@csrf_exempt
def mediamtx_auth_webhook(request):
    """
    Webhook auth untuk MediaMTX (authMethod: http, lihat deploy/mediamtx.yml).
    Dipanggil server-to-server oleh MediaMTX — BUKAN oleh browser — sehingga
    divalidasi via shared secret di query string, bukan session/login Django.

    Body JSON dari MediaMTX: {user, pass, ip, action, path, protocol, id, query}
    Balas HTTP 2xx untuk mengizinkan, selain itu untuk menolak.
    """
    if request.method != 'POST':
        return HttpResponseForbidden('method not allowed')
    if not settings.MEDIAMTX_AUTH_SECRET or request.GET.get('key') != settings.MEDIAMTX_AUTH_SECRET:
        return HttpResponseForbidden('invalid secret')

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseForbidden('bad payload')

    action = payload.get('action', '')
    path = payload.get('path', '')
    token = payload.get('user', '')

    if action not in ('publish', 'read'):
        # Aksi lain (mis. 'playback', 'api', 'metrics') — izinkan agar tidak
        # memblokir fitur bawaan MediaMTX yang tidak berkaitan dengan sesi live.
        return JsonResponse({'ok': True})

    # Pipeline transcode rekaman (lihat runOnReady di deploy/mediamtx.yml):
    # video WebRTC dari browser selalu VP8, dan recorder fMP4 MediaMTX belum
    # mengimplementasi VP8 — jadi ffmpeg LOKAL di server yang sama menarik
    # feed RTSP mentah lalu republish sebagai H.264 ke path "<key>-rec" yang
    # baru direkam. ffmpeg diberi kredensial RTSP khusus ("mtx-internal" +
    # MEDIAMTX_AUTH_SECRET) yang tidak pernah dibagikan ke browser — SENGAJA
    # BUKAN dicek lewat IP 127.0.0.1: kalau browser mengakses MediaMTX lewat
    # reverse proxy di server yang sama (mis. Cloudflare Tunnel ke
    # localhost:8889, seperti setup FASOP), traffic WHIP/WHEP asli dari
    # browser pun akan tampak datang dari 127.0.0.1 juga, jadi cek IP saja
    # bisa salah mengizinkan baca video tanpa token asli.
    if (settings.MEDIAMTX_AUTH_SECRET and token == 'mtx-internal'
            and payload.get('pass') == settings.MEDIAMTX_AUTH_SECRET):
        if action == 'read' and path.startswith('live-') and not path.endswith('-talk') and not path.endswith('-rec'):
            stream_key = path[len('live-'):]
            if LiveSession.objects.filter(stream_key=stream_key, status='live').exists():
                return JsonResponse({'ok': True})
        elif action == 'publish' and path.startswith('live-') and path.endswith('-rec'):
            stream_key = path[len('live-'):-len('-rec')]
            if LiveSession.objects.filter(stream_key=stream_key, status='live').exists():
                return JsonResponse({'ok': True})
        return HttpResponseForbidden('not allowed')

    session = (
        LiveSession.objects.filter(stream_key=token).first()
        or LiveSession.objects.filter(view_token=token).first()
        or LiveSession.objects.filter(pengawas_key=token).first()
    )
    if not session:
        return HttpResponseForbidden('unknown token')

    allowed = False
    if action == 'publish':
        if path == session.video_path and token == session.stream_key and session.is_live:
            allowed = True
        elif (path == session.talkback_path and session.pengawas_key
              and token == session.pengawas_key and session.is_live):
            allowed = True
    elif action == 'read':
        if path == session.video_path and token in (
            session.view_token, session.stream_key, session.pengawas_key
        ):
            allowed = True
        elif path == session.talkback_path and token == session.stream_key:
            # Hanya teknisi pemilik sesi yang boleh mendengar talkback pengawas.
            allowed = True

    if allowed:
        return JsonResponse({'ok': True})
    return HttpResponseForbidden('not allowed')


@csrf_exempt
def mediamtx_record_webhook(request):
    """
    Dipanggil oleh hook `runOnRecordSegmentComplete` MediaMTX (lihat
    deploy/mediamtx.yml) setiap file rekaman selesai ditulis ke disk.
    Server-to-server, divalidasi via shared secret sama seperti auth webhook.

    Body JSON: {path, segment_path} — path = nama path MediaMTX yang direkam.
    Sejak rekaman dipindah ke path hasil transcode ("<video_path>-rec", lihat
    runOnReady di deploy/mediamtx.yml — video_path asli dari browser selalu
    VP8 yang recorder fMP4 MediaMTX tidak dukung), path di sini punya akhiran
    "-rec" yang perlu dilepas dulu untuk dapat stream_key aslinya.
    segment_path = path absolut file MP4 di disk.
    """
    if request.method != 'POST':
        return HttpResponseForbidden('method not allowed')
    if not settings.MEDIAMTX_AUTH_SECRET or request.GET.get('key') != settings.MEDIAMTX_AUTH_SECRET:
        return HttpResponseForbidden('invalid secret')

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseForbidden('bad payload')

    path = payload.get('path', '')
    segment_path = payload.get('segment_path', '')
    if not path.startswith('live-') or not path.endswith('-rec') or not segment_path:
        # Cuma rekam path hasil transcode ("-rec") — path video mentah
        # (VP8, tidak direkam sama sekali) dan talkback tidak masuk sini.
        return JsonResponse({'ok': True})

    stream_key = path[len('live-'):-len('-rec')]
    session = LiveSession.objects.filter(stream_key=stream_key).first()
    if not session:
        return HttpResponseForbidden('unknown session')

    session.recording_path = segment_path
    session.save(update_fields=['recording_path'])
    return JsonResponse({'ok': True})


@login_required
@require_streaming_access
def session_recording(request, pk):
    session = get_object_or_404(LiveSession, pk=pk)
    if not session.has_recording:
        raise Http404('Rekaman belum tersedia untuk sesi ini.')
    return render(request, 'streaming/playback.html', {'session': session})


_RANGE_RE = re.compile(r'bytes\s*=\s*(\d+)-(\d*)', re.I)


@login_required
@require_streaming_access
def serve_recording(request, pk):
    """
    Serve file rekaman dengan dukungan HTTP Range agar video bisa di-seek
    di player, bukan cuma diputar berurutan dari awal.
    """
    session = get_object_or_404(LiveSession, pk=pk)
    if not session.has_recording or not os.path.isfile(session.recording_path):
        return HttpResponseNotFound('Rekaman tidak ditemukan.')

    file_path = session.recording_path
    file_size = os.path.getsize(file_path)
    safe_judul = re.sub(r'[^A-Za-z0-9]+', '-', session.judul).strip('-') or 'live'
    download_name = f'{safe_judul}-{session.started_at:%Y%m%d-%H%M}.mp4'
    range_header = request.META.get('HTTP_RANGE', '')
    range_match = _RANGE_RE.match(range_header)

    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        end = min(end, file_size - 1)
        length = max(0, end - start + 1)

        def stream():
            with open(file_path, 'rb') as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        resp = StreamingHttpResponse(stream(), status=206, content_type='video/mp4')
        resp['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        resp['Content-Length'] = str(length)
    else:
        resp = StreamingHttpResponse(open(file_path, 'rb'), content_type='video/mp4')
        resp['Content-Length'] = str(file_size)

    resp['Accept-Ranges'] = 'bytes'
    resp['Content-Disposition'] = f'inline; filename="{download_name}"'
    return resp
