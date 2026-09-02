/**
 * streaming/ezviz-player.js — pembungkus tipis EZUIKit (ezuikit.js).
 *
 * Dipakai halaman sesi Ezviz (ezviz.html) dan Multi View (grid.html).
 * Isinya cuma dua hal yang tidak boleh berbeda antar halaman:
 *
 *   1. accessToken diambil SEKALI per halaman, tidak per pemutar. Multi View
 *      bisa menggambar 9 kotak sekaligus; kalau tiap kotak menembak
 *      /api/ezviz-token/ sendiri, satu halaman = 9 request untuk satu
 *      nilai yang sama persis.
 *   2. Bentuk opsi EZUIKitPlayer (template, env.domain, scaleMode) sama di
 *      semua halaman — supaya kamera yang tampil benar di satu halaman
 *      tidak tiba-tiba gagal di halaman lain karena domain region beda.
 *
 * Prasyarat: ezuikit.js sudah dimuat lebih dulu (global `EZUIKit`).
 */

let _tokenPromise = null;

/**
 * accessToken akun Ezviz. Hasilnya di-cache sebagai Promise, jadi pemanggil
 * yang datang bersamaan (9 kotak Multi View yang dibuat dalam satu loop) ikut
 * menunggu request yang sama alih-alih memicu request baru.
 */
function ezvizToken(tokenUrl) {
    if (!_tokenPromise) {
        _tokenPromise = fetch(tokenUrl)
            .then(async (resp) => {
                const data = await resp.json().catch(() => ({}));
                if (!resp.ok || !data.access_token) {
                    throw new Error(data.error || `Gagal ambil token Ezviz (HTTP ${resp.status})`);
                }
                return data;
            })
            .catch((err) => {
                // Jangan simpan kegagalan selamanya — kalau tidak, satu
                // gangguan jaringan sesaat membuat SELURUH kamera di halaman
                // ini mati sampai halaman di-reload manual.
                _tokenPromise = null;
                throw err;
            });
    }
    return _tokenPromise;
}

/**
 * Buat satu EZUIKitPlayer di dalam elemen ber-id `containerId`.
 *
 * opts:
 *   tokenUrl   — endpoint /streaming/api/ezviz-token/
 *   url        — alamat ezopen:// kamera
 *   domain     — EZVIZ_API_BASE dari server (harus sama dengan yang dipakai
 *                server saat meminta token; beda domain = token ditolak)
 *   width/height — ukuran piksel awal
 *   audio      — true untuk langsung bersuara (default false: Multi View
 *                dengan 9 kamera bersuara sekaligus tidak bisa didengarkan)
 *   template   — tema EZUIKit ('simple' polos, 'pcLive' lengkap dengan tombol)
 *   onError    — dipanggil dengan pesan siap-tampil kalau gagal
 */
async function buatPemutarEzviz(containerId, opts) {
    const data = await ezvizToken(opts.tokenUrl);
    return new EZUIKit.EZUIKitPlayer({
        id: containerId,
        accessToken: data.access_token,
        url: opts.url,
        width: opts.width,
        height: opts.height,
        audio: opts.audio ? 1 : 0,
        template: opts.template || 'simple',
        // 1 = etalase isi video diskalakan proporsional. Default (0) menarik
        // gambar sampai memenuhi kotak, dan kamera CCTV 4:3 di kotak 16:9
        // jadi gepeng — menyesatkan saat dipakai memeriksa keadaan lapangan.
        scaleMode: 1,
        // Domain dari balasan token (areaDomain) menang atas nilai setting:
        // accessToken hanya berlaku di region itu, jadi player harus memanggil
        // host yang sama dengan yang menerbitkan tokennya.
        env: { domain: data.domain || opts.domain || 'https://open.ys7.com' },
        loggerOptions: { level: 'ERROR', name: 'ezuikit' },
        handleError: (err) => {
            console.error('EZUIKit error', err);
            if (opts.onError) opts.onError(pesanErrorEzviz(err));
        },
    });
}

/** Terjemahkan error EZUIKit jadi kalimat yang berguna buat operator. */
function pesanErrorEzviz(err) {
    const kode = err && err.data && err.data.nErrorCode;
    if (kode === 5) return 'Kamera terenkripsi — perlu kode verifikasi perangkat.';
    if (err && err.type === 'handleRunTimeInfoError') return `Cloud Ezviz menolak pemutaran (kode ${kode}).`;
    return 'Gagal memutar kamera Ezviz — periksa koneksi ke cloud Ezviz.';
}

/** Hentikan & bersihkan pemutar. Aman dipanggil untuk pemutar yang sudah mati. */
async function hentikanPemutarEzviz(player) {
    if (!player) return;
    try {
        if (typeof player.stop === 'function') await player.stop();
    } catch (e) { /* noop */ }
    try {
        if (typeof player.destroy === 'function') await player.destroy();
    } catch (e) { /* noop */ }
}
