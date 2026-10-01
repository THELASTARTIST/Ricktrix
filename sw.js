/* RICKTRIX service worker.
 *
 * Makes the app installable and usable with no network. The route data already
 * lives in autofare.js as a static file, so precaching the shell genuinely gets
 * you offline route search -- not a degraded version of it.
 *
 * Caching rules, and why:
 *   API calls      network only. Prices and counts change, and a stale fare is
 *                  worse than no fare. When the network is gone the page falls
 *                  back to the bundled data (see api.js).
 *   navigations    network first, so a deploy is picked up immediately; fall
 *                  back to the cached page, then to offline.html.
 *   static assets  cache first. They are versioned by CACHE below, so they
 *                  cannot go stale without the cache being dropped too.
 *
 * Bump CACHE whenever you change a file in PRECACHE.
 */

const CACHE = 'ricktrix-v1';

const PRECACHE = [
  './',
  './index.html',
  './all_routes.html',
  './saved_routes.html',
  './tracking.html',
  './community.html',
  './about.html',
  './offline.html',
  './style.css',
  './autofare.js',
  './data.js',
  './autocomplete.js',
  './api.js',
  './pwa.js',
  './app.js',
  './navigation.js',
  './translations.js',
  './manifest.webmanifest',
  './assets/icon.svg',
  './assets/icon-maskable.svg',
  './assets/icon-192.png',
  './assets/icon-512.png',
  './assets/icon-maskable-192.png',
  './assets/icon-maskable-512.png',
  './assets/apple-touch-icon.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    // addAll is atomic-ish: one bad URL rejects the whole install. Add
    // individually so a single missing optional file cannot break offline
    // support for everything else.
    await Promise.all(PRECACHE.map(async (url) => {
      try {
        await cache.add(new Request(url, { cache: 'reload' }));
      } catch (error) {
        console.warn('[sw] could not precache', url, error);
      }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))
    );
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

function isApiRequest(url) {
  return url.pathname.startsWith('/api/') || url.pathname === '/api';
}

self.addEventListener('fetch', (event) => {
  const request = event.request;

  // Only GET is cacheable; a POST must always reach the network or fail.
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Never cache the API, and never let a cross-origin request fall through to
  // the cache lookup below.
  if (isApiRequest(url) || url.origin !== self.location.origin) return;

  // Navigations: fresh if possible, cached if not.
  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        const cache = await caches.open(CACHE);
        cache.put(request, response.clone());
        return response;
      } catch (error) {
        const cache = await caches.open(CACHE);
        return (await cache.match(request))
            || (await cache.match('./index.html'))
            || (await cache.match('./offline.html'))
            || new Response('Offline', { status: 503, headers: { 'Content-Type': 'text/plain' } });
      }
    })());
    return;
  }

  // Static assets: serve from cache, refresh in the background.
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(request);
    if (cached) {
      event.waitUntil((async () => {
        try {
          const fresh = await fetch(request);
          if (fresh && fresh.ok) await cache.put(request, fresh.clone());
        } catch (error) { /* offline: the cached copy stands */ }
      })());
      return cached;
    }

    try {
      const response = await fetch(request);
      if (response && response.ok && response.type === 'basic') {
        await cache.put(request, response.clone());
      }
      return response;
    } catch (error) {
      return new Response('', { status: 504, statusText: 'Offline' });
    }
  })());
});
