/**
 * 智慧校园失物登记认领系统 - Service Worker
 * 缓存策略：
 *  - 同源 GET 请求：cache-first，网络成功后回写缓存
 *  - /uploads/ 图片 与 /api/ 请求：network-first，保证数据新鲜
 *  - POST / 非 GET：直接走网络，不缓存
 *  - activate 时清理旧版本缓存
 */

const CACHE_NAME = 'laf-v2-1';

const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/login.html',
  '/register.html',
  '/my.html',
  '/admin.html',
  '/detail.html',
  '/post-lost.html',
  '/post-notice.html',
  '/css/style.css',
  '/js/common.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
      .catch((err) => {
        // 预缓存失败不阻塞安装（例如某资源 404）
        console.warn('[SW] precache failed:', err);
      })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // POST/其他方法直接走网络

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // 跨域不处理

  // /api/ 与 /uploads/ 走网络优先，保证数据/图片新鲜
  const isNetworkFirst = url.pathname.startsWith('/api/') ||
                         url.pathname.startsWith('/uploads/');

  if (isNetworkFirst) {
    event.respondWith(networkFirst(req));
  } else {
    event.respondWith(cacheFirst(req));
  }
});

async function cacheFirst(req) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(req);
  if (cached) return cached;
  try {
    const resp = await fetch(req);
    if (resp && resp.ok) cache.put(req, resp.clone());
    return resp;
  } catch (err) {
    return new Response('离线状态，暂时无法加载', { status: 503, statusText: 'Offline' });
  }
}

async function networkFirst(req) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const resp = await fetch(req);
    if (resp && resp.ok) cache.put(req, resp.clone());
    return resp;
  } catch (err) {
    const cached = await cache.match(req);
    if (cached) return cached;
    return new Response('离线状态，暂时无法获取数据', { status: 503, statusText: 'Offline' });
  }
}
