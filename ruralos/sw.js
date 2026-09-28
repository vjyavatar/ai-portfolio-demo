const CACHE="saathi-ruralos-37ecaab8cb4b",ASSETS=["/ruralos/", "/ruralos/alerts.css", "/ruralos/assets/app-shell-WDDNhGxM.js", "/ruralos/assets/calendar-days-CnOEstUF.js", "/ruralos/assets/check-DGaDue4z.js", "/ruralos/assets/enterprise-guide-B77Wr3Kt.js", "/ruralos/assets/enterprise-guide-qdNpYZb1.css", "/ruralos/assets/how-to-guide-DLqSFcfm.js", "/ruralos/assets/index-D5Jk8w9h.js", "/ruralos/assets/index-Y5HRH9Dm.css", "/ruralos/assets/live-hub-DeM6A1jh.js", "/ruralos/assets/regional-guidance-B-eM-j4X.js", "/ruralos/assets/service-preparation-v3dwsRj5.css", "/ruralos/assets/task-assistant-BTqXvulU.js", "/ruralos/assets/task-assistant-DjpPtKER.css", "/ruralos/assets/travel-planner-CQgp76No.js", "/ruralos/family.webp", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/icon-512.png", "/ruralos/index.html", "/ruralos/install/index.html", "/ruralos/integrations/index.html", "/ruralos/manifest.webmanifest", "/ruralos/sitemap.xml"];
const CORE=["/ruralos/", "/ruralos/manifest.webmanifest", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/assets/index-D5Jk8w9h.js", "/ruralos/assets/index-Y5HRH9Dm.css"];

self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(CORE))));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('saathi-ruralos-')&&k!==CACHE).map(k=>caches.delete(k))))));
self.addEventListener('fetch',e=>{
 const u=new URL(e.request.url);
 if(e.request.method!=='GET'||u.origin!==self.location.origin||!u.pathname.startsWith('/ruralos/')||!ASSETS.includes(u.pathname))return;
 e.respondWith(fetch(e.request).then(async r=>{
  if(r.ok&&r.type!=='opaque'&&!r.redirected){try{const c=await caches.open(CACHE);await c.put(u.pathname,r.clone())}catch{/* Full/disabled storage must not discard a successful network response. */}}
  return r;
 }).catch(()=>caches.open(CACHE).then(c=>c.match(u.pathname)).then(r=>r||Response.error())));
});
