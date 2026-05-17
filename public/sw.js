// Observer service worker.
//
// Strategy:
//   - GET requests for API routes (/api/*)        → network-only, never cached.
//                                                   Heartbeat data is real-time;
//                                                   serving stale state is worse
//                                                   than a load spinner.
//   - GET requests for the app shell + assets     → cache-first with a network
//                                                   fallback. Lets the
//                                                   "Add to Home Screen" install
//                                                   load instantly on second open
//                                                   and survive brief offline
//                                                   conditions.
//   - Anything non-GET (POST/PUT/DELETE)          → network-only, never cached.
//   - Navigation requests when offline + no cache → fall back to the cached
//                                                   index.html so the SPA at
//                                                   least boots and shows its
//                                                   own UI rather than the
//                                                   browser's default offline
//                                                   page.

const CACHE_VERSION = "observer-v1";
const APP_SHELL = ["/", "/index.html", "/icon.svg", "/manifest.json"];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL).catch(() => {}))
    );
    // New worker takes over on next page load instead of waiting for tabs to close.
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
            )
        )
    );
    self.clients.claim();
});

function isApiRequest(url) {
    return url.pathname.startsWith("/api/");
}

function isAssetRequest(url) {
    // Vite's hashed-name assets: /assets/<name>-<hash>.{js,css,svg,…}
    return url.pathname.startsWith("/assets/");
}

self.addEventListener("fetch", (event) => {
    const req = event.request;
    if (req.method !== "GET") {
        return;  // pass-through; never intercept mutations
    }

    let url;
    try {
        url = new URL(req.url);
    } catch (e) {
        return;
    }

    if (url.origin !== self.location.origin) {
        return;  // pass-through cross-origin (e.g. tile servers, badges to GitHub)
    }

    if (isApiRequest(url)) {
        return;  // network-only; let the browser handle it
    }

    if (isAssetRequest(url)) {
        // Hashed assets are immutable — cache forever, fall back to network.
        event.respondWith(
            caches.match(req).then((hit) => {
                if (hit) {
                    return hit;
                }
                return fetch(req).then((res) => {
                    if (res.ok) {
                        const copy = res.clone();
                        caches.open(CACHE_VERSION).then((c) => c.put(req, copy));
                    }
                    return res;
                });
            })
        );
        return;
    }

    if (req.mode === "navigate") {
        // Navigation: try network first (so the user gets the freshest
        // index.html in case we shipped an update), fall back to cached
        // shell when offline.
        event.respondWith(
            fetch(req)
                .then((res) => {
                    const copy = res.clone();
                    caches.open(CACHE_VERSION).then((c) => c.put("/index.html", copy));
                    return res;
                })
                .catch(() => caches.match("/index.html"))
        );
        return;
    }
});
