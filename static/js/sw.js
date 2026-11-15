/* Viking Hub service worker.
   Keeps the app's styles, scripts, icons and the offline screen on the phone so the
   installed app opens quickly. Pages themselves always come from the server, so the
   app still opens to sign in first and never shows saved student data. */
const VERSION = "__VERSION__";
const CACHE = `vh-shell-${VERSION}`;
const OFFLINE = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll([OFFLINE])).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("vh-shell-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;  // weather and other outside sites go straight through

  // Pages: always from the server. With no connection, show the offline screen.
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
    return;
  }

  // Styles, scripts and images: their links change whenever the file changes,
  // so a saved copy is always the right one.
  if (url.pathname.startsWith("/static/") && !url.pathname.endsWith(".pdf")) {
    event.respondWith(
      caches.open(CACHE).then(async (c) => {
        const hit = await c.match(req);
        if (hit) return hit;
        const res = await fetch(req);
        if (res.ok) c.put(req, res.clone());
        return res;
      })
    );
  }
  // Everything else (/api and the rest) goes to the server as usual.
});
