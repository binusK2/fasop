import hmac
import json
import logging
import os
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    HttpResponse,
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

from fasop.hashids_helper import decode, encode
from notifikasi.views import notif_ke_am, notif_ke_teknisi

from . import ezviz
from .models import KameraEzviz, LiveSession, LiveViewerHeartbeat
from .permissions import (
    can_join_as_pengawas,
    can_manage_ezviz,
    can_start_stream,
    require_streaming_access,
)

logger = logging.getLogger(__name__)

# Heartbeat penonton dianggap basi (tidak lagi nonton) setelah sekian detik
# tanpa ping baru — harus lebih besar dari interval kirim di viewer.html
# (10 detik) supaya toleran jaringan lambat, tapi tetap terasa "real-time".
VIEWER_HEARTBEAT_STALE_SECONDS = 20

# Batas jumlah kotak yang digambar sekaligus di Multi View
# (streaming/grid.html). Tiap kotak = satu koneksi WebRTC (sesi kamera
# perangkat) atau satu decoder wasm EZUIKit (sesi Ezviz); di atas angka ini
# browser kelas laptop kantor mulai patah-patah dan CPU-nya habis. Sesi
# selebihnya tetap terdaftar dan bisa dibuka satu per satu dari daftar.
GRID_MAKS_TILE = 9


@login_required
@require_streaming_access
def session_list(request):
    # Bereskan sesi hantu sebelum menggambar daftarnya — kalau tidak, sesi
    # yang penyiarnya sudah lama pergi akan terus tampil "Sedang Live".
    LiveSession.akhiri_yang_terbengkalai()

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
        'kamera_list': KameraEzviz.objects.filter(aktif=True),
        'ezviz_siap': ezviz.terkonfigurasi(),
        'can_sync_ezviz': can_manage_ezviz(request.user),
    })


@login_required
@require_streaming_access
@require_POST
def start_session(request):
    if not can_start_stream(request.user):
        return HttpResponseForbidden('Hanya Teknisi yang bisa memulai live streaming.')

    judul = request.POST.get('judul', '').strip()
    nama_teknisi = request.user.profile.get_display_name() if hasattr(request.user, 'profile') else request.user.username

    # Sumber video dipilih di modal "Mulai Live". Nilai tak dikenal jatuh ke
    # 'perangkat' — sumber yang selalu tersedia dan tidak bergantung pada
    # konfigurasi/koneksi luar apa pun.
    sumber = request.POST.get('sumber', 'perangkat')
    if sumber not in dict(LiveSession.SUMBER_CHOICES):
        sumber = 'perangkat'

    kamera = None
    if sumber == 'ezviz':
        if not ezviz.terkonfigurasi():
            messages.error(request, 'Sumber Ezviz belum dikonfigurasi (EZVIZ_APP_KEY/EZVIZ_APP_SECRET kosong).')
            return redirect('streaming:list')
        kamera = KameraEzviz.objects.filter(pk=request.POST.get('kamera') or 0, aktif=True).first()
        if kamera is None:
            messages.error(request, 'Pilih dulu kamera CCTV Ezviz yang mau disiarkan.')
            return redirect('streaming:list')

    session = LiveSession.objects.create(
        teknisi=request.user,
        judul=judul or (f'CCTV {kamera.nama}' if kamera else f'Live Pemeliharaan — {nama_teknisi}'),
        sumber=sumber,
        kamera=kamera,
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
        'pernah_tersiar': session.pernah_tersiar,
    }

    # Sesi Ezviz dilayani SATU template untuk ketiga peran (teknisi, pengawas,
    # viewer) — beda dari sesi kamera perangkat yang punya tiga template.
    # Alasannya: yang membedakan ketiga peran di sesi Ezviz cuma tombol
    # (akhiri live / mic talkback / jadi pengawas), sedangkan videonya sama
    # persis untuk semua orang — tidak ada yang mem-publish video dari
    # browsernya, jadi tidak ada logika kamera lokal yang perlu dipisah.
    if session.is_ezviz:
        context['ezviz_domain'] = settings.EZVIZ_API_BASE
        return render(request, 'streaming/ezviz.html', context)

    if is_broadcaster:
        return render(request, 'streaming/broadcast.html', context)
    if is_pengawas:
        return render(request, 'streaming/pengawas.html', context)
    return render(request, 'streaming/viewer.html', context)


@login_required
@require_streaming_access
def ezviz_token(request):
    """
    accessToken akun Ezviz untuk dipakai EZUIKit di browser.

    Sengaja endpoint terpisah, bukan ditanam di HTML halaman:
      - Multi View butuh SATU token untuk banyak kotak sekaligus; menanam
        token di tiap kotak berarti me-render ulang halaman tiap kali daftar
        sesi berubah.
      - Token berumur 7 hari dan bisa dicabut kapan saja dari sisi Ezviz;
        halaman yang dibiarkan terbuka semalaman bisa mengambil yang baru
        tanpa reload.

    CATATAN KEAMANAN: token ini berlaku untuk SELURUH akun Ezviz, bukan per
    kamera — itu memang bentuk yang disediakan Open Platform untuk EZUIKit.
    Karena itu endpoint ini dijaga login + require_streaming_access (Teknisi
    & AM saja), dan token tidak pernah muncul di halaman yang bisa dibuka
    tanpa login.
    """
    if not ezviz.terkonfigurasi():
        return JsonResponse({'ok': False, 'error': 'Sumber Ezviz belum dikonfigurasi di server.'}, status=503)
    try:
        token = ezviz.ambil_access_token()
    except ezviz.EzvizError as e:
        logger.warning('Gagal ambil accessToken Ezviz: %s', e)
        return JsonResponse({'ok': False, 'error': str(e)}, status=502)
    return JsonResponse({'ok': True, 'access_token': token, 'domain': settings.EZVIZ_API_BASE})


@login_required
@require_streaming_access
@require_POST
def ezviz_sync(request):
    """Tarik daftar kamera dari akun Ezviz ke tabel KameraEzviz (lihat ezviz.sinkron_kamera)."""
    if not can_manage_ezviz(request.user):
        return HttpResponseForbidden('Hanya Asisten Manager yang bisa menyinkronkan daftar kamera Ezviz.')
    if not ezviz.terkonfigurasi():
        messages.error(request, 'Sumber Ezviz belum dikonfigurasi (EZVIZ_APP_KEY/EZVIZ_APP_SECRET kosong).')
        return redirect('streaming:list')

    try:
        hasil = ezviz.sinkron_kamera()
    except ezviz.EzvizError as e:
        messages.error(request, f'Sinkronisasi kamera Ezviz gagal: {e}')
        return redirect('streaming:list')

    pesan = (
        f"Sinkronisasi Ezviz selesai — {hasil['total']} kamera di cloud: "
        f"{hasil['dibuat']} baru, {hasil['diperbarui']} diperbarui"
    )
    if hasil['hilang']:
        pesan += f", {hasil['hilang']} tidak lagi ada di cloud (ditandai, tidak dihapus)"
    messages.success(request, pesan + '.')
    return redirect('streaming:list')


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
        # Beda dari is_live: sesi bisa 'live' tapi tidak ada video sama sekali
        # (halaman teknisi ter-refresh / tabnya tertutup). Penonton perlu tahu
        # bedanya, kalau tidak ia menunggu gambar yang memang tidak akan datang.
        'siaran_aktif': session.siaran_aktif,
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
def publisher_heartbeat(request, pk):
    """
    Dikirim browser TEKNISI selama WHIP publish-nya hidup — dasar
    `LiveSession.siaran_aktif` dan pembersihan sesi terbengkalai.

    Terpisah dari session_heartbeat (yang menghitung PENONTON): yang satu
    menjawab "berapa orang menonton", yang ini menjawab "apakah ada yang
    dikirim sama sekali". Dulu tidak ada yang menjawab pertanyaan kedua,
    sehingga sesi yang penyiarnya sudah pergi tetap tampil Sedang Live.

    `berhenti=1` mengosongkan penanda seketika (dipakai saat teknisi menekan
    stop dan saat halaman ditutup lewat sendBeacon) — supaya statusnya tidak
    perlu menunggu PUBLISHER_STALE_SECONDS lewat dulu.
    """
    session = get_object_or_404(LiveSession, pk=pk)
    if request.user.id != session.teknisi_id:
        return HttpResponseForbidden('Hanya teknisi pemilik sesi yang mengirim status siaran.')

    berhenti = request.POST.get('berhenti') == '1'
    # .update() supaya tidak menyentuh field lain (dan tidak menimpa perubahan
    # yang sedang dilakukan tab lain) — ini dipanggil tiap 10 detik.
    LiveSession.objects.filter(pk=session.pk).update(
        publisher_last_seen=None if berhenti else timezone.now(),
    )
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


@login_required
@require_streaming_access
def session_grid(request):
    """
    Multi View — semua sesi live sekaligus dalam satu layar grid.

    Halaman ini SENGAJA tidak menerima daftar sesi lewat context render:
    isinya digambar dari /streaming/api/sesi-live/ dan disegarkan berkala,
    supaya sesi yang mulai/berakhir setelah halaman dibuka muncul & hilang
    sendiri. Halaman ini dipasang di layar monitoring yang dibiarkan menyala
    berjam-jam — kalau isinya ditentukan saat render, layar itu akan
    membeku pada keadaan beberapa jam lalu tanpa ada yang sadar.
    """
    return render(request, 'streaming/grid.html', {
        'whep_url': settings.MEDIAMTX_WHEP_URL,
        'ice_servers_json': settings.WEBRTC_ICE_SERVERS,
        'ezviz_domain': settings.EZVIZ_API_BASE,
        'maks_tile': GRID_MAKS_TILE,
    })


def _data_sesi(session):
    """Bentuk satu sesi live jadi dict siap dipakai satu kotak di Multi View."""
    teknisi = session.teknisi
    nama = teknisi.username
    profile = getattr(teknisi, 'profile', None)
    if profile:
        nama = profile.get_display_name() or nama

    data = {
        # Hashid, bukan pk mentah — PK integer tidak pernah diekspos ke
        # browser di FASOP (lihat fasop/hashids_helper.py).
        'id': encode(session.pk),
        'judul': session.judul,
        'teknisi': nama,
        'sumber': session.sumber,
        'mulai': timezone.localtime(session.started_at).strftime('%d/%m %H:%M'),
        'ada_pengawas': session.pengawas_id is not None,
        # Kotak Multi View perlu membedakan "belum tersambung" dari "penyiarnya
        # memang sudah tidak ada" — dua keadaan yang tampak sama-sama hitam.
        'siaran_aktif': session.siaran_aktif,
        'detail_url': reverse('streaming:detail', kwargs={'pk': session.pk}),
    }
    if session.is_ezviz:
        # Tanpa accessToken — token diambil sekali oleh halaman lewat
        # /streaming/api/ezviz-token/, bukan diulang di tiap kotak tiap poll.
        data['ezopen_url'] = session.ezopen_url
        data['kamera'] = str(session.kamera) if session.kamera_id else ''
    else:
        data['video_path'] = session.video_path
        data['view_token'] = session.view_token
    return data


@login_required
@require_streaming_access
def api_live_sessions(request):
    """
    Daftar sesi yang sedang live, untuk Multi View.

    Query `nonton=<id>,<id>,...` sekaligus mencatat heartbeat penonton untuk
    sesi-sesi itu. Digabung ke satu request DENGAN SENGAJA: Multi View menonton
    sampai 9 sesi sekaligus, dan heartbeat terpisah per kotak berarti 9 POST
    tiap 10 detik dari satu tab saja. Hitungan "x menonton" yang dilihat
    teknisi tetap sama akuratnya.
    """
    LiveSession.akhiri_yang_terbengkalai()

    sessions = list(
        LiveSession.objects.filter(status='live')
        .select_related('teknisi', 'teknisi__profile', 'kamera')
    )

    # `nonton` berisi hashid (bentuk yang sama dengan yang dikirim _data_sesi),
    # jadi harus di-decode dulu. decode() mengembalikan None untuk id ngawur,
    # dan pencocokan dibatasi ke sesi yang memang sedang live — id asing tidak
    # bisa membuat baris heartbeat apa pun.
    nonton = {decode(x) for x in request.GET.get('nonton', '').split(',') if x}
    nonton.discard(None)
    if nonton:
        for sesi in sessions:
            if sesi.pk in nonton:
                LiveViewerHeartbeat.objects.update_or_create(session=sesi, user=request.user)

    return JsonResponse({
        'sessions': [_data_sesi(x) for x in sessions],
        'maks_tile': GRID_MAKS_TILE,
    })


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
    if not settings.MEDIAMTX_AUTH_SECRET or not hmac.compare_digest(str(request.GET.get('key', '')), str(settings.MEDIAMTX_AUTH_SECRET)):
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
    # baru direkam.
    #
    # Sisi BACA (ffmpeg menarik feed mentah) divalidasi di sini lewat
    # kredensial RTSP khusus ("mtx-internal" + MEDIAMTX_AUTH_SECRET) yang
    # tidak pernah dibagikan ke browser — SENGAJA BUKAN dicek lewat IP
    # 127.0.0.1: kalau browser mengakses MediaMTX lewat reverse proxy di
    # server yang sama (mis. Cloudflare Tunnel ke localhost:8889, seperti
    # setup FASOP), traffic WHIP/WHEP asli dari browser pun akan tampak
    # datang dari 127.0.0.1 juga, jadi cek IP saja bisa salah mengizinkan
    # baca video tanpa token asli.
    #
    # Sisi PUBLISH (ffmpeg republish ke "<key>-rec") TIDAK divalidasi di
    # sini — dikecualikan total lewat authHTTPExclude di deploy/mediamtx.yml
    # (path "-rec" tidak pernah dipakai browser manapun untuk publish, jadi
    # aman) karena muxer RTSP publish ffmpeg gagal menangani challenge 401
    # walau kredensial URL sudah benar (keterbatasan ffmpeg, sudah dicoba &
    # selalu gagal "Server returned 401 Unauthorized" di log MediaMTX).
    if (settings.MEDIAMTX_AUTH_SECRET and token == 'mtx-internal'
            and hmac.compare_digest(str(payload.get('pass', '')), str(settings.MEDIAMTX_AUTH_SECRET))):
        if action == 'read' and path.startswith('live-') and not path.endswith('-talk') and not path.endswith('-rec'):
            stream_key = path[len('live-'):]
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
    if not settings.MEDIAMTX_AUTH_SECRET or not hmac.compare_digest(str(request.GET.get('key', '')), str(settings.MEDIAMTX_AUTH_SECRET)):
        return HttpResponseForbidden('invalid secret')

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseForbidden('bad payload')

    path = payload.get('path', '')
    segment_path = payload.get('segment_path', '')
    if not path.startswith('live-') or not segment_path:
        return JsonResponse({'ok': True})

    if path.endswith('-rec'):
        # Video (hasil transcode H.264 — lihat runOnReady di deploy/mediamtx.yml).
        stream_key = path[len('live-'):-len('-rec')]
        field = 'recording_path'
    elif path.endswith('-talk'):
        # Audio talkback pengawas — direkam TERPISAH dari video (lihat
        # catatan di LiveSession.talkback_recording_path), bukan di-mix
        # jadi satu file supaya pipeline rekaman video yang sudah stabil
        # tidak ikut berisiko tiap pengawas toggle mic.
        stream_key = path[len('live-'):-len('-talk')]
        field = 'talkback_recording_path'
    else:
        # Path video mentah (VP8, tidak pernah direkam sama sekali).
        return JsonResponse({'ok': True})

    session = LiveSession.objects.filter(stream_key=stream_key).first()
    if not session:
        return HttpResponseForbidden('unknown session')

    root = os.path.normpath(settings.STREAMING_RECORDINGS_ROOT)
    normalized = os.path.normpath(segment_path)
    if normalized != root and not normalized.startswith(root + os.sep):
        logger.warning('segment_path %s di luar STREAMING_RECORDINGS_ROOT, ditolak.', segment_path)
        return HttpResponseForbidden('invalid segment_path')

    setattr(session, field, segment_path)
    session.save(update_fields=[field])
    return JsonResponse({'ok': True})


@login_required
@require_streaming_access
def session_recording(request, pk):
    session = get_object_or_404(LiveSession, pk=pk)
    if not session.has_recording and not session.has_talkback_recording:
        raise Http404('Rekaman belum tersedia untuk sesi ini.')
    return render(request, 'streaming/playback.html', {'session': session})


_RANGE_RE = re.compile(r'bytes\s*=\s*(\d+)-(\d*)', re.I)


def _serve_file_x_accel(file_path, content_type, download_name):
    """
    Serve lewat header X-Accel-Redirect — nginx yang baca & kirim byte file
    langsung dari disk (termasuk menangani Range request untuk seek),
    jauh lebih cepat untuk file besar daripada Django streaming manual
    lewat gunicorn. Django di sini cuma memvalidasi akses (login,
    has_recording, dst di view pemanggil) lalu bilang ke nginx file MANA
    yang boleh diserve — tidak pernah baca isi filenya sendiri.

    HANYA dipanggil kalau STREAMING_USE_X_ACCEL_REDIRECT=True — nginx WAJIB
    sudah dikonfigurasi sesuai deploy/nginx-recordings-x-accel.conf.example
    dulu, kalau belum, request ini akan gagal (nginx tidak tahu apa itu
    X-Accel-Redirect kalau location `internal`-nya belum ada).
    """
    root = os.path.normpath(settings.STREAMING_RECORDINGS_ROOT)
    normalized = os.path.normpath(file_path)
    if normalized != root and not normalized.startswith(root + os.sep):
        # Rekaman seharusnya SELALU di bawah STREAMING_RECORDINGS_ROOT
        # (lihat recordPath di deploy/mediamtx.yml) — kalau tidak, jangan
        # ekspos lewat internal redirect nginx sama sekali.
        logger.warning('Recording path %s di luar STREAMING_RECORDINGS_ROOT, X-Accel-Redirect dibatalkan.', file_path)
        return HttpResponseNotFound('Rekaman tidak ditemukan.')

    relative = os.path.relpath(normalized, root)
    resp = HttpResponse(content_type=content_type)
    resp['X-Accel-Redirect'] = settings.STREAMING_X_ACCEL_REDIRECT_PREFIX.rstrip('/') + '/' + relative
    resp['Content-Disposition'] = f'inline; filename="{download_name}"'
    return resp


def _serve_file_range(request, file_path, content_type, download_name):
    """
    Serve satu file dengan dukungan HTTP Range, dipakai baik untuk rekaman
    video maupun klip audio talkback — supaya player bisa di-seek, bukan
    cuma diputar berurutan dari awal.
    """
    root = os.path.normpath(settings.STREAMING_RECORDINGS_ROOT)
    normalized = os.path.normpath(file_path)
    if normalized != root and not normalized.startswith(root + os.sep):
        logger.warning('Recording path %s di luar STREAMING_RECORDINGS_ROOT, ditolak.', file_path)
        return HttpResponseNotFound('Rekaman tidak ditemukan.')

    if not os.path.isfile(normalized):
        return HttpResponseNotFound('Rekaman tidak ditemukan.')

    if settings.STREAMING_USE_X_ACCEL_REDIRECT:
        return _serve_file_x_accel(file_path, content_type, download_name)

    file_size = os.path.getsize(normalized)
    range_header = request.META.get('HTTP_RANGE', '')
    range_match = _RANGE_RE.match(range_header)

    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        end = min(end, file_size - 1)
        length = max(0, end - start + 1)

        def stream():
            with open(normalized, 'rb') as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        resp = StreamingHttpResponse(stream(), status=206, content_type=content_type)
        resp['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        resp['Content-Length'] = str(length)
    else:
        resp = StreamingHttpResponse(open(normalized, 'rb'), content_type=content_type)
        resp['Content-Length'] = str(file_size)

    resp['Accept-Ranges'] = 'bytes'
    resp['Content-Disposition'] = f'inline; filename="{download_name}"'
    return resp


@login_required
@require_streaming_access
def serve_recording(request, pk):
    session = get_object_or_404(LiveSession, pk=pk)
    if not session.has_recording:
        return HttpResponseNotFound('Rekaman tidak ditemukan.')
    safe_judul = re.sub(r'[^A-Za-z0-9]+', '-', session.judul).strip('-') or 'live'
    download_name = f'{safe_judul}-{session.started_at:%Y%m%d-%H%M}.mp4'
    return _serve_file_range(request, session.recording_path, 'video/mp4', download_name)


@login_required
@require_streaming_access
def serve_talkback_recording(request, pk):
    session = get_object_or_404(LiveSession, pk=pk)
    if not session.has_talkback_recording:
        return HttpResponseNotFound('Rekaman audio pengawas tidak ditemukan.')
    safe_judul = re.sub(r'[^A-Za-z0-9]+', '-', session.judul).strip('-') or 'live'
    download_name = f'{safe_judul}-pengawas-{session.started_at:%Y%m%d-%H%M}.mp4'
    return _serve_file_range(request, session.talkback_recording_path, 'audio/mp4', download_name)
