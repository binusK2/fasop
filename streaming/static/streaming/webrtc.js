/**
 * streaming/webrtc.js — helper WHIP (publish) / WHEP (playback) murni via
 * fetch + RTCPeerConnection, tanpa library eksternal. Dipakai oleh
 * broadcast.html, pengawas.html, dan viewer.html.
 *
 * Server target: MediaMTX (lihat deploy/mediamtx.yml). ICE non-trickle —
 * menunggu ICE gathering selesai sebelum kirim offer, supaya alur tetap
 * satu request/response (lebih sederhana, cukup untuk skala kecil).
 */

function _waitIceGatheringComplete(pc, timeoutMs) {
    if (pc.iceGatheringState === 'complete') return Promise.resolve();
    return new Promise((resolve) => {
        function check() {
            if (pc.iceGatheringState === 'complete') {
                pc.removeEventListener('icegatheringstatechange', check);
                clearTimeout(timer);
                resolve();
            }
        }
        pc.addEventListener('icegatheringstatechange', check);
        const timer = setTimeout(resolve, timeoutMs || 4000);
    });
}

function _basicAuthHeader(token) {
    return 'Basic ' + btoa(token + ':');
}

function _resolveResourceUrl(baseUrl, locationHeader) {
    if (!locationHeader) return null;
    try {
        return new URL(locationHeader, baseUrl).toString();
    } catch (e) {
        return null;
    }
}

/**
 * Publish local media stream ke MediaMTX via WHIP.
 * Return { pc, resourceUrl } — simpan resourceUrl untuk dipakai saat stop().
 *
 * CATATAN: sempat dicoba paksa codec H.264 (recorder MediaMTX tidak
 * mengimplementasi VP8, rekaman jadi audio-only) tapi malah merusak live
 * viewing (WHEP tersambung tapi video tidak muncul) — direvert, live
 * streaming (fitur utama) lebih prioritas daripada rekaman video lengkap.
 * Rekaman untuk sementara audio-only; investigasi kenapa H.264 WHEP
 * gagal di MediaMTX adalah follow-up terpisah, bukan blocker.
 */
async function whipPublish(baseUrl, path, token, stream, iceServers) {
    const pc = new RTCPeerConnection({ iceServers: iceServers || [] });
    stream.getTracks().forEach((track) => pc.addTrack(track, stream));

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await _waitIceGatheringComplete(pc);

    const resp = await fetch(`${baseUrl.replace(/\/$/, '')}/${path}/whip`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/sdp',
            'Authorization': _basicAuthHeader(token),
        },
        body: pc.localDescription.sdp,
    });
    if (!resp.ok) {
        pc.close();
        throw new Error(`WHIP publish gagal (HTTP ${resp.status})`);
    }
    const answerSdp = await resp.text();
    await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

    return { pc, resourceUrl: _resolveResourceUrl(baseUrl, resp.headers.get('Location')) };
}

/**
 * Subscribe (playback) dari MediaMTX via WHEP, hasil track dipasang ke mediaEl.srcObject.
 * Return { pc, resourceUrl }.
 */
async function whepPlay(baseUrl, path, token, mediaEl, iceServers) {
    const pc = new RTCPeerConnection({ iceServers: iceServers || [] });
    pc.addTransceiver('video', { direction: 'recvonly' });
    pc.addTransceiver('audio', { direction: 'recvonly' });

    const remoteStream = new MediaStream();
    mediaEl.srcObject = remoteStream;
    pc.ontrack = (event) => {
        remoteStream.addTrack(event.track);
    };

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await _waitIceGatheringComplete(pc);

    const resp = await fetch(`${baseUrl.replace(/\/$/, '')}/${path}/whep`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/sdp',
            'Authorization': _basicAuthHeader(token),
        },
        body: pc.localDescription.sdp,
    });
    if (!resp.ok) {
        pc.close();
        throw new Error(`WHEP playback gagal (HTTP ${resp.status})`);
    }
    const answerSdp = await resp.text();
    await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

    return { pc, resourceUrl: _resolveResourceUrl(baseUrl, resp.headers.get('Location')) };
}

/**
 * Hentikan koneksi WHIP/WHEP: tutup RTCPeerConnection + DELETE resource di server.
 *
 * `keepalive: true` PENTING — tanpa ini, kalau dipanggil dari handler
 * unload/pagehide (mis. saat pindah halaman viewer -> pengawas), browser
 * membatalkan fetch DELETE begitu navigasi mulai sehingga sesi WHEP lama
 * tidak pernah ditutup di server (MediaMTX) dan baru hilang sendiri setelah
 * timeout ICE. Selama menunggu timeout itu, koneksi WHEP baru di halaman
 * berikutnya bisa gagal dapat alokasi relay TURN (pool port dipersempit ke
 * 100 port) sehingga status tampak "terhubung" tapi video tidak tampil.
 */
async function whipWhepStop(pc, resourceUrl) {
    if (pc) {
        try { pc.close(); } catch (e) { /* noop */ }
    }
    if (resourceUrl) {
        try { await fetch(resourceUrl, { method: 'DELETE', keepalive: true }); } catch (e) { /* noop */ }
    }
}
