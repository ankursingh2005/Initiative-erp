// Bumped to v11: added the new /price-list (IDS Price System) page to the
// core asset list. Bumping the cache name forces every existing install to
// drop its old cache on the next activate, so the new page shell gets
// prefetched too instead of only being cached the first time a user
// happens to visit it.
const CACHE_NAME = 'initiative-erp-v11';
const CORE_ASSETS = [
  '/login',
  '/signup',
  '/home',
  '/dashboard',
  '/purchase-orders',
  '/analytics',
  '/daily-profitability',
  '/price-list',
  '/manifest.webmanifest',
  '/static/Initiative%20logo.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys
        .filter((key) => key !== CACHE_NAME)
        .map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

// Only these are safe to ever serve from cache: the app's own page shell
// (index/login/dashboard/etc, handled separately below via request.mode
// === 'navigate') and genuinely static files (images, the manifest, the
// service worker's own core assets). Every API/data endpoint - /brands,
// /categories, /subcategories, /stores, /api/*, /sales, /schemes,
// /products, /variants, /customers, /dealers, and anything else that
// isn't a static file - must always go to the network so master data and
// records are never stuck showing an old snapshot.
function isCacheableStaticAsset(pathname) {
  if (pathname.startsWith('/static/')) return true;
  if (pathname === '/manifest.webmanifest') return true;
  return false;
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.status === 200) {
            const cloned = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, cloned));
          }
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match('/login')))
    );
    return;
  }

  const url = new URL(request.url);
  if (!isCacheableStaticAsset(url.pathname)) {
    // Data/API request: always hit the network. Do not fall back to
    // cache on failure either - a failed API call should surface as a
    // normal network error to the page, not silently resolve with
    // whatever (possibly stale) data happened to be cached before.
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }

      return fetch(request)
        .then((response) => {
          const isHttpOk = response && response.status === 200;
          if (isHttpOk && request.url.startsWith(self.location.origin)) {
            const cloned = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, cloned));
          }
          return response;
        })
        .catch(() => caches.match('/login'));
    })
  );
});