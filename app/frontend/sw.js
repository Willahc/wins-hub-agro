// Service worker mínimo e seguro para o WiNS Hub Agro.
// Estratégia: cache-first APENAS para as libs estáticas versionadas (/static/vendor/),
// que abrem instantâneo e funcionam offline. Tudo o mais (páginas, /api, login) vai
// SEMPRE à rede — assim nunca servimos dados desatualizados nem páginas autenticadas.
const CACHE = 'wins-agro-v1';
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
  if (e.request.method === 'GET' && url.pathname.startsWith('/static/vendor/')) {
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      }))
    );
  }
  // demais requisições: deixa a rede tratar (sem interceptar)
});
