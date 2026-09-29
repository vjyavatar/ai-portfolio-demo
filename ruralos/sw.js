const CACHE="saathi-ruralos-50f9c6dd40a4",ASSETS=["/ruralos/", "/ruralos/alerts.css", "/ruralos/assets/app-shell-DfahOhcj.js", "/ruralos/assets/calendar-days-CtyKOLME.js", "/ruralos/assets/check-BiqiGBPf.js", "/ruralos/assets/enterprise-guide-DgLAIqbm.js", "/ruralos/assets/enterprise-guide-qdNpYZb1.css", "/ruralos/assets/how-to-guide-AZUgslIM.js", "/ruralos/assets/index-BFL2EX7r.js", "/ruralos/assets/index-Y5HRH9Dm.css", "/ruralos/assets/live-hub-Bv-gLi6h.js", "/ruralos/assets/live-hub-DlvQaTlP.css", "/ruralos/assets/regional-guidance-CwdHH3Tx.js", "/ruralos/assets/service-preparation-v3dwsRj5.css", "/ruralos/assets/task-assistant-BjysFDu_.js", "/ruralos/assets/task-assistant-DjpPtKER.css", "/ruralos/assets/travel-planner-Dkzu97G9.js", "/ruralos/family.webp", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/icon-512.png", "/ruralos/index.html", "/ruralos/install/index.html", "/ruralos/integrations/index.html", "/ruralos/manifest.webmanifest", "/ruralos/sitemap.xml"];
const CORE=["/ruralos/", "/ruralos/manifest.webmanifest", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/assets/index-BFL2EX7r.js", "/ruralos/assets/index-Y5HRH9Dm.css"];

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
