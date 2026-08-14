const CACHE_NAME = 'websearch-admin-v2';
const STATIC_CACHE = 'websearch-static-v2';
const STATIC_ASSETS = [
'/admin',
'/admin/index.html',
'/admin/chat.html',
'/admin/styles.css',
'/admin/utils.js',
'/admin/vendor/lucide.js',
'/admin/vendor/marked.min.js',
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
keys.filter(key => key !== STATIC_CACHE && key !== CACHE_NAME)
.map(key => caches.delete(key))
)
).then(() => self.clients.claim())
);
});
self.addEventListener('fetch', event => {
if (event.request.method !== 'GET') return;
if (event.request.url.includes('/api/')) return;
if (event.request.url.includes('login.html')) return;
event.respondWith(
fetch(event.request)
.then(response => {
const responseClone = response.clone();
if (response.status === 200) {
caches.open(CACHE_NAME)
.then(cache => cache.put(event.request, responseClone));
}
return response;
})
.catch(() => {
return caches.match(event.request)
.then(cachedResponse => {
if (cachedResponse) {
return cachedResponse;
}
if (event.request.mode === 'navigate') {
return caches.match('/admin/index.html');
}
return new Response('Offline', { status: 503 });
});
})
);
});
self.addEventListener('push', event => {
const data = event.data ? event.data.json() : {};
const options = {
body: data.body || 'Nouvelle notification',
icon: '/admin/img/web.svg',
badge: '/admin/img/web.svg',
vibrate: [100, 50, 100],
data: {
url: data.url || '/admin'
}
};
event.waitUntil(
self.registration.showNotification(
data.title || 'WebSearch Agent',
options
)
);
});
self.addEventListener('notificationclick', event => {
event.notification.close();
event.waitUntil(
clients.openWindow(event.notification.data.url)
);
});