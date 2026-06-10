// Service worker do WiNS Hub Agro.
// - libs estáticas (/static/vendor/): stale-while-revalidate — serve do cache na hora
//   (instantâneo/offline) E busca uma cópia fresca em background, então o PRÓXIMO load
//   já recebe a versão nova. Evita estrandar dispositivos de campo em código velho.
// - shell do app de campo (/campo): network-first — sempre fresco online, cai no
//   cache quando offline, pra o app ABRIR sem conexão (cold start no curral).
//   Só o HTML do shell é cacheado; dados (PII) seguem só pela rede (/api nunca é cacheada).
// - resto (/api, login, outras páginas): sempre rede.
//
// IMPORTANTE: bumpar CACHE a cada deploy que mexa em ASSETS ou no shell — a troca do nome
// dispara o activate que apaga os caches antigos e força addAll dos vendors novos.
const CACHE = 'wins-agro-v4';
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

  // libs estáticas: stale-while-revalidate. Responde do cache na hora (se houver) e,
  // em paralelo, revalida com a rede atualizando o cache p/ o próximo load. Assim um
  // deploy de vendor lib chega ao dispositivo de campo sem precisar de hard refresh.
  if (url.pathname.startsWith('/static/vendor/')) {
    e.respondWith(
      caches.open(CACHE).then((c) =>
        c.match(e.request).then((hit) => {
          const network = fetch(e.request).then((res) => {
            // captive portal devolve 200 text/html p/ um .js -> NÃO cacheia isso
            // (envenenaria o vendor e quebraria o app offline). Só grava resposta
            // same-origin e que não seja HTML.
            const ct = (res && res.headers.get('content-type')) || '';
            const valido = res && res.ok && res.type !== 'opaque' && !ct.includes('text/html');
            if (valido) { c.put(e.request, res.clone()); return res; }
            return hit || res;            // resposta suspeita: prefere o cache bom
          }).catch(() => hit);            // offline: fica no cache
          return hit || network;
        })
      )
    );
    return;
  }

  // shell do app de campo: network-first, fallback p/ cache offline.
  // Só cacheia a resposta autenticada de verdade (200, sem redirect p/ /login).
  if (url.pathname === '/campo') {
    e.respondWith(
      // cache:'no-store' garante que o network-first NÃO devolva o shell velho do cache HTTP do WebView
      fetch(e.request, { cache: 'no-store' }).then((res) => {
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
