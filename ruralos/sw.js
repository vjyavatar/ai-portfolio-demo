const CACHE="saathi-ruralos-03cc95bebfa1",ASSETS=["/ruralos/", "/ruralos/alerts.css", "/ruralos/assets/action-case-CiciHIyA.css", "/ruralos/assets/action-case-Cw6VT6Dw.js", "/ruralos/assets/app-shell-CKCIRVyn.js", "/ruralos/assets/calendar-days-hgPSjoeS.js", "/ruralos/assets/check-D6fCABRn.js", "/ruralos/assets/enterprise-guide-DZXhP6su.js", "/ruralos/assets/enterprise-guide-qdNpYZb1.css", "/ruralos/assets/how-to-guide-Db1Ptav0.js", "/ruralos/assets/index-D24FXN6q.js", "/ruralos/assets/index-Y5HRH9Dm.css", "/ruralos/assets/live-hub-DlvQaTlP.css", "/ruralos/assets/live-hub-R9zmhk46.js", "/ruralos/assets/regional-guidance-DrLEoQ1D.js", "/ruralos/assets/service-preparation-v3dwsRj5.css", "/ruralos/assets/task-assistant-CCh-F1k5.js", "/ruralos/assets/task-assistant-CQE-hO75.css", "/ruralos/assets/travel-planner-CWwMBq8l.js", "/ruralos/family.webp", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/icon-512.png", "/ruralos/index.html", "/ruralos/install/index.html", "/ruralos/integrations/index.html", "/ruralos/manifest.webmanifest", "/ruralos/sitemap.xml"];
const CORE=["/ruralos/", "/ruralos/manifest.webmanifest", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/assets/index-D24FXN6q.js", "/ruralos/assets/index-Y5HRH9Dm.css"];

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
