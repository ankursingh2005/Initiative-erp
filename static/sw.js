const CACHE_NAME = 'initiative-erp-v4';
const CORE_ASSETS = [
  '/login',
  '/signup',
  '/forgot-password',
  '/home',
  '/dashboard',
  '/purchase-orders',
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
  if (url.pathname.startsWith('/auth/') || url.pathname.startsWith('/my-scope/') || url.pathname.startsWith('/sales') || url.pathname.startsWith('/schemes') || url.pathname.startsWith('/api/purchase-orders')) {
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
