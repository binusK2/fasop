{% load static %}// FASOP PWA Service Worker
// Scope: root ("/") — di-serve lewat view Django agar bisa mengontrol seluruh path.
// Strategi:
//   - Navigasi (dokumen HTML): network-first, fallback ke halaman offline.
//   - Aset statis (CSS/JS/gambar/font) same-origin & CDN: stale-while-revalidate.
//   - Request non-GET / POST (submit form inspeksi): selalu network, tidak di-cache.

const CACHE_VERSION = 'fasop-pwa-v1';
const STATIC_CACHE  = CACHE_VERSION + '-static';
const RUNTIME_CACHE = CACHE_VERSION + '-runtime';
const OFFLINE_URL   = '/offline/';

// Aset inti yang di-precache saat install.
const PRECACHE_URLS = [
  OFFLINE_URL,
  '{% static "favicon/android-chrome-192x192.png" %}',
  '{% static "favicon/android-chrome-512x512.png" %}',
  '{% static "favicon/apple-touch-icon.png" %}',
  '{% static "favicon/favicon-32x32.png" %}',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== STATIC_CACHE && k !== RUNTIME_CACHE)
            .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// Izinkan halaman memerintahkan SW untuk aktif segera.
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

function isStaticAsset(url) {
  return /\.(?:css|js|png|jpg|jpeg|gif|svg|webp|ico|woff2?|ttf|eot)$/i.test(url.pathname);
}

self.addEventListener('fetch', (event) => {
  const req = event.request;

  // Hanya tangani GET. POST (submit inspeksi, upload foto) langsung ke jaringan.
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Jangan ganggu media upload & admin/auth agar selalu fresh.
  if (url.pathname.startsWith('/media/') ||
      url.pathname.startsWith('/secure-panel/') ||
      url.pathname.startsWith('/login/') ||
      url.pathname.startsWith('/logout/')) {
    return;
  }

  // Navigasi dokumen: network-first, fallback offline.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(RUNTIME_CACHE).then((c) => c.put(req, copy)).catch(() => {});
          return res;
        })
        .catch(() =>
          caches.match(req).then((cached) => cached || caches.match(OFFLINE_URL))
        )
    );
    return;
  }

  // Aset statis (same-origin & CDN): stale-while-revalidate.
  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const network = fetch(req)
          .then((res) => {
            if (res && (res.ok || res.type === 'opaque')) {
              const copy = res.clone();
              caches.open(RUNTIME_CACHE).then((c) => c.put(req, copy)).catch(() => {});
            }
            return res;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
  }
});
