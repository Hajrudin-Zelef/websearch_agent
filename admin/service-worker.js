const SW_VERSION = 'v7';
const STATIC_CACHE = `websearch-static-${SW_VERSION}`;
const RUNTIME_CACHE = `websearch-runtime-${SW_VERSION}`;

const STATIC_ASSETS = [
  '/admin/index.html',
  '/admin/login.html',
  '/admin/styles.css',
  '/admin/utils.js',
  '/admin/js/init.js',
  '/admin/js/apikeys.js',
  '/admin/vendor/lucide.js',
  '/admin/vendor/marked.min.js',
  '/admin/img/icon-192.png',
  '/admin/img/icon-512.png',
  '/admin/img/icon-512-maskable.png',
  '/admin/img/icon-180.png',
  '/admin/img/web.svg',
  '/admin/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== STATIC_CACHE && key !== RUNTIME_CACHE)
          .map(key => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

function isStaticAsset(url) {
  return /\.(css|js|png|svg|jpg|jpeg|webp|woff2?)$/.test(new URL(url).pathname);
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  if (req.url.includes('/api/')) return;
  // Allow login.html to be fetched normally (will be cached as static asset)

  // Cache-first pour assets statiques (CSS/JS/images)
  if (isStaticAsset(req.url)) {
    event.respondWith(
      caches.match(req).then(cached => {
        if (cached) return cached;
        return fetch(req).then(res => {
          if (res.status === 200) {
            const clone = res.clone();
            caches.open(STATIC_CACHE).then(cache => cache.put(req, clone));
          }
          return res;
        });
      })
    );
    return;
  }

  // Network-first pour pages HTML / navigation
  event.respondWith(
    fetch(req)
      .then(res => {
        if (res.status === 200) {
          const clone = res.clone();
          caches.open(RUNTIME_CACHE).then(cache => cache.put(req, clone));
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then(cached => {
          if (cached) return cached;
          if (req.mode === 'navigate') {
            return caches.match('/admin/index.html');
          }
          return new Response('Offline', { status: 503 });
        })
      )
  );
});

self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const options = {
    body: data.body || 'Nouvelle notification',
    icon: '/admin/img/icon-192.png',
    badge: '/admin/img/icon-192.png',
    vibrate: [100, 50, 100],
    data: { url: data.url || '/admin/index.html' }
  };
  event.waitUntil(
    self.registration.showNotification(data.title || 'WebSearch Agent', options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});

self.addEventListener('message', event => {
  if (event.data === 'skipWaiting') self.skipWaiting();
});
