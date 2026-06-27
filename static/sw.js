// 孔夫子查价 · Service Worker
// 提供离线时基本的页面缓存（核心功能需要网络）

const CACHE = "kongfz-price-v1";
const PRECACHE_URLS = [
  "/",
  "/static/manifest.json",
  "/static/icon.svg",
];

// 安装：缓存基本页面
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

// 激活：清理旧缓存
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// 拦截请求：API 请求走网络不缓存；静态文件缓存优先
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // API 请求永不缓存（走网络）
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  // 静态文件：缓存优先
  e.respondWith(
    caches.match(e.request).then((cached) => cached || fetch(e.request))
  );
});
