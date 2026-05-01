/**
 * Qualified dashboard service worker (Milestone Q8).
 * Bump CACHE_VERSION when static assets change so deploys pick up fresh shells.
 */
const CACHE_VERSION = "qualified-dash-v3";
const CACHE_NAME = `qualified-dash-assets-${CACHE_VERSION}`;
const ASSETS = [
  "./index.html",
  "./app.js",
  "./styles.css",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.map((key) => {
            if (key !== CACHE_NAME) return caches.delete(key);
            return Promise.resolve();
          }),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) {
    return;
  }
  /* Same-origin JSON only (e.g. mirrored snapshot); never serve from cache. */
  if (url.pathname.endsWith(".json")) {
    event.respondWith(fetch(req));
    return;
  }
  if (req.mode === "navigate" || req.destination === "document") {
    event.respondWith(
      caches.match("./index.html").then((hit) => hit || fetch(req)),
    );
    return;
  }
  event.respondWith(
    caches.match(req).then((hit) => {
      if (hit) return hit;
      return fetch(req).then((resp) => {
        if (!resp || resp.status !== 200 || resp.type !== "basic") return resp;
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        return resp;
      });
    }),
  );
});
