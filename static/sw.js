const CACHE = 'idspl-static-v20';
const BASE = new URL('./', self.registration.scope).pathname.replace(/\/$/, '');
const asset = path => BASE + path;
const STATIC = [asset('/offline'), asset('/manifest.webmanifest'), asset('/static/app-shell.css'), asset('/static/app-shell.js'), asset('/static/Initiative%20logo.png'), asset('/static/icons/icon-192.png'), asset('/static/icons/icon-512.png'), asset('/static/icons/icon-maskable-512.png')];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(STATIC)));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('idspl-static-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET' || request.headers.has('Authorization')) return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const relative = BASE && url.pathname.startsWith(BASE + '/') ? url.pathname.slice(BASE.length) : url.pathname;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request, {cache: 'no-cache'}).catch(() => caches.match(asset('/offline'))));
    return;
  }
  if (!relative.startsWith('/static/') && relative !== '/manifest.webmanifest') return;
  // HTTP cache handles freshness and ETags; service-worker storage is only
  // an offline fallback. API responses never enter this cache.
  event.respondWith(caches.open(CACHE).then(async cache => {
    try {
      const response = await fetch(request);
      if (response.ok && response.type === 'basic' && response.status !== 206) {
        event.waitUntil(cache.put(request, response.clone()));
      }
      return response;
    } catch (error) {
      const cached = await cache.match(request);
      if (cached) return cached;
      throw error;
    }
  }));
});