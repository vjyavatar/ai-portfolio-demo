const CACHE_NAME = 'celesys-v38';
const ASSETS = ['/'];

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS)));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => 
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  // ALWAYS bypass SW cache for these JS files so updates deploy immediately.
  // Cache-busting via ?v=N query params alone doesn't work once SW has cached
  // a resource — we must explicitly always-fetch.
  if (
    e.request.url.includes('app.min.js') ||
    e.request.url.includes('app.js') ||
    e.request.url.includes('active-trading.js')
  ) {
    e.respondWith(fetch(e.request));
    return;
  }
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
