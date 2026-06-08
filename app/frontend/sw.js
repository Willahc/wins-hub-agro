// Service worker do WiNS Hub Agro.
// - libs estáticas (/static/vendor/): cache-first (instantâneo, offline).
// - shell do app de campo (/campo): network-first — sempre fresco online, cai no
//   cache quando offline, pra o app ABRIR sem conexão (cold start no curral).
//   Só o HTML do shell é cacheado; dados (PII) seguem só pela rede (/api nunca é cacheada).
// - resto (/api, login, outras páginas): sempre rede.
const CACHE = 'wins-agro-v2';
const ASSETS = [
  '/static/vendor/leaflet.css',
  '/static/vendor/leaflet.js',
  '/static/vendor/chart.umd.min.js',
  '/static/vendor/alpine.min.js',
  '/static/vendor/icon-192.png',
  '/static/vendor/icon-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;

  // libs estáticas versionadas: cache-first
  if (url.pathname.startsWith('/static/vendor/')) {
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      }))
    );
    return;
  }

  // shell do app de campo: network-first, fallback p/ cache offline.
  // Só cacheia a resposta autenticada de verdade (200, sem redirect p/ /login).
  if (url.pathname === '/campo') {
    e.respondWith(
      fetch(e.request).then((res) => {
        if (res.ok && !res.redirected) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put('/campo', copy));
        }
        return res;
      }).catch(() => caches.match('/campo'))
    );
    return;
  }
  // demais requisições: deixa a rede tratar (sem interceptar)
});
