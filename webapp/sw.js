// Basic service worker for PWA (caching strategy can be added later)
self.addEventListener('install', (event) => {
    console.log('Service Worker: Installing...');
    event.waitUntil(
        caches.open('gymgenius-cache-v1').then((cache) => {
            return cache.addAll([
                '/',
                '/index.html',
                '/css/style.css',
                '/js/app.js',
                '/images/icon-192x192.png',
                '/images/icon-512x512.png',
                '/plan_builder.html',
                '/css/plan_builder.css',
                '/js/plan_builder.js',
                '/analytics_dashboard.html', // New dashboard file
                '/css/dashboard.css',       // New dashboard CSS
                '/js/dashboard_charts.js'   // New dashboard JS
                // Add other assets to cache
            ]);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('Service Worker: Activating...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== 'gymgenius-cache-v1') { // Update cache name if changed
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    return self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    console.log('Service Worker: Fetching ', event.request.url);
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});
