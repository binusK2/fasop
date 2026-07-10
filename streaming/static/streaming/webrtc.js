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

/** Hentikan koneksi WHIP/WHEP: tutup RTCPeerConnection + DELETE resource di server. */
async function whipWhepStop(pc, resourceUrl) {
    if (pc) {
        try { pc.close(); } catch (e) { /* noop */ }
    }
    if (resourceUrl) {
        try { await fetch(resourceUrl, { method: 'DELETE' }); } catch (e) { /* noop */ }
    }
}
