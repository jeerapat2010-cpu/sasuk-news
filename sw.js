const CACHE_NAME = "sasuk-news-shell-v2";
const SHELL_FILES = [
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
// - หน้าเว็บหลัก (index.html / navigation) และ news.json: network-first เสมอ
//   เพื่อให้พี่จีเห็นเวอร์ชันล่าสุดทันทีที่อัปเดตไฟล์บน GitHub ไม่ค้าง cache เก่า
//   ถ้าออฟไลน์ค่อย fallback ไปใช้ที่ cache ไว้ล่าสุด
// - ไฟล์อื่นๆ ที่แทบไม่เปลี่ยน (ไอคอน, manifest): cache-first เพื่อความเร็ว
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  const isNavigation =
    event.request.mode === "navigate" || url.pathname.endsWith("index.html");
  const isNewsJson = url.pathname.endsWith("news.json");

  if (isNavigation || isNewsJson) {
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
