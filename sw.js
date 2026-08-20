const CACHE_NAME = "eduguide-ls-shell-v35";
const APP_SHELL = [
  "/",
  "/index.html",
  "/styles.css",
  "/app.js",
  "/data/catalog.js",
  "/data/admin-catalog.js",
  "/data/source-manifest.json",
  "/data/supabase-config.js",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
  "/icons/icon-192.svg",
  "/icons/icon-512.svg"
];
const CACHE_FIRST_PATHS = new Set([
  "/styles.css",
  "/app.js",
  "/manifest.webmanifest",
  "/data/catalog.js",
  "/data/admin-catalog.js",
  "/data/source-manifest.json",
  "/data/supabase-config.js"
]);

function isCacheFirstAsset(url) {
  return CACHE_FIRST_PATHS.has(url.pathname) || url.pathname.startsWith("/icons/");
}

async function putInCache(request, response) {
  if (!response || !response.ok) return;
  const cache = await caches.open(CACHE_NAME);
  await cache.put(request, response.clone());
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  const network = fetch(request)
    .then((response) => {
      putInCache(request, response).catch(() => {});
      return response;
    })
    .catch(() => cached);
  return cached || network.then((response) => response || caches.match("/index.html"));
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    putInCache(request, response).catch(() => {});
    return response;
  } catch (error) {
    return caches.match(request).then((cached) => cached || caches.match("/index.html"));
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  event.respondWith(isCacheFirstAsset(url) ? cacheFirst(event.request) : networkFirst(event.request));
});
