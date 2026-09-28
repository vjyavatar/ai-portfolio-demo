const CACHE="saathi-ruralos-ea6b339c500c",ASSETS=["/ruralos/", "/ruralos/alerts.css", "/ruralos/assets/app-shell-CrTTy-zU.js", "/ruralos/assets/calendar-days-C9kwmBqo.js", "/ruralos/assets/check-C7p3LUoV.js", "/ruralos/assets/how-to-guide-DK32RatO.js", "/ruralos/assets/index-U45Z4c9K.css", "/ruralos/assets/index-_j5yrBWP.js", "/ruralos/assets/live-hub-BWVyNyaH.js", "/ruralos/assets/regional-guidance-DXQNhfd7.js", "/ruralos/assets/service-preparation-v3dwsRj5.css", "/ruralos/assets/task-assistant-DW-6wJLT.js", "/ruralos/assets/task-assistant-DjpPtKER.css", "/ruralos/assets/travel-planner-qMYswHxx.js", "/ruralos/family.webp", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/icon-512.png", "/ruralos/index.html", "/ruralos/install/index.html", "/ruralos/integrations/index.html", "/ruralos/manifest.webmanifest", "/ruralos/sitemap.xml"];
const CORE=["/ruralos/", "/ruralos/manifest.webmanifest", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/assets/index-_j5yrBWP.js", "/ruralos/assets/index-U45Z4c9K.css"];

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
