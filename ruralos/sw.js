const CACHE="saathi-ruralos-4c6cc14780a5",ASSETS=["/ruralos/", "/ruralos/alerts.css", "/ruralos/assets/app-shell-D3DWAJGm.js", "/ruralos/assets/calendar-days-BEcG9CHE.js", "/ruralos/assets/check-CI05_Y_G.js", "/ruralos/assets/enterprise-guide-BGUNkyII.js", "/ruralos/assets/enterprise-guide-qdNpYZb1.css", "/ruralos/assets/how-to-guide-BBHIpB_k.js", "/ruralos/assets/index-Y5HRH9Dm.css", "/ruralos/assets/index-ovSM-02y.js", "/ruralos/assets/live-hub-DlvQaTlP.css", "/ruralos/assets/live-hub-DrH3RdE5.js", "/ruralos/assets/regional-guidance-BpN0gDfu.js", "/ruralos/assets/service-preparation-v3dwsRj5.css", "/ruralos/assets/task-assistant-CQE-hO75.css", "/ruralos/assets/task-assistant-D9vybB_6.js", "/ruralos/assets/travel-planner-BF30CK0h.js", "/ruralos/family.webp", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/icon-512.png", "/ruralos/index.html", "/ruralos/install/index.html", "/ruralos/integrations/index.html", "/ruralos/manifest.webmanifest", "/ruralos/sitemap.xml"];
const CORE=["/ruralos/", "/ruralos/manifest.webmanifest", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/assets/index-ovSM-02y.js", "/ruralos/assets/index-Y5HRH9Dm.css"];

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
