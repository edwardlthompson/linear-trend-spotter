/**
 * Qualified dashboard service worker (Milestone Q8).
 * Bump CACHE_VERSION when static assets change so deploys pick up fresh shells.
 */
const CACHE_VERSION = "qualified-dash-v18";
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

self.addEventListener("push", (event) => {
  let title = "Linear Trend Spotter";
  let body = "Scan updated — open the qualified dashboard for the latest snapshot.";
  let openUrl = self.location.origin + self.location.pathname;
  if (event.data) {
    try {
      const j = event.data.json();
      if (j && typeof j.title === "string" && j.title.trim()) title = j.title.trim().slice(0, 120);
      if (j && typeof j.body === "string" && j.body.trim()) body = j.body.trim().slice(0, 240);
      if (j && typeof j.url === "string" && j.url.trim()) openUrl = j.url.trim().slice(0, 2000);
    } catch {
      try {
        const t = event.data.text();
        if (t && t.trim()) body = t.trim().slice(0, 240);
      } catch {
        /* ignore */
      }
    }
  }
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "./icons/icon-192.png",
      badge: "./icons/icon-192.png",
      tag: "qualified-scan-push",
      data: { url: openUrl },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const raw = event.notification.data && event.notification.data.url;
  const targetUrl = typeof raw === "string" && raw.trim() ? raw.trim() : self.location.origin + self.location.pathname;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (let i = 0; i < clientList.length; i++) {
        const c = clientList[i];
        if (c.url && "focus" in c) return c.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(targetUrl);
    }),
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
