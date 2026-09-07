/* Freak Town service worker: app-shell cache + offline drafts page.
   Audio/TTS stays network-only (fresh voices beat stale bytes). */
const CACHE = 'freaktown-shell-v2';
const SHELL = ['/', '/manifest.json', '/icon-192.png', '/icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks =>
    Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  // API + audio: network only
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/audio/') ||
      url.pathname.startsWith('/freaks/')) return;
  // HTML pages: network first (a broken deploy must never stick),
  // images + misc: cache first
  const isPage = e.request.mode === 'navigate' ||
    url.pathname.endsWith('.html') || url.pathname === '/';
  if (!isPage) {
    e.respondWith(
      caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
        return res;
      }).catch(() => caches.match('/')))
    );
    return;
  }
  e.respondWith(
    fetch(e.request).then(res => {
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put(e.request, copy));
      return res;
    }).catch(() => caches.match(e.request)).catch(() => caches.match('/'))
  );
});
