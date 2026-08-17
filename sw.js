const CACHE_NAME = "sasuk-news-shell-v1";
const SHELL_FILES = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

// ติดตั้ง: cache ไฟล์หลักของแอป (shell)
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

// เปิดใช้งาน: ล้าง cache เวอร์ชันเก่า
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// กลยุทธ์ fetch:
// - news.json: พยายามดึงข้อมูลใหม่จากเน็ตก่อนเสมอ (network-first) เพื่อให้ข่าวสดใหม่
//   ถ้าออฟไลน์ ค่อย fallback ไปใช้ข้อมูลที่ cache ไว้ล่าสุด
// - ไฟล์อื่นๆ (shell): ใช้ cache-first เพื่อความเร็ว
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (url.pathname.endsWith("news.json")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      return (
        cached ||
        fetch(event.request).then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
      );
    })
  );
});
