const CACHE="saathi-ruralos-61477f2641f1",ASSETS=["/ruralos/", "/ruralos/assets/app-shell-B9mjE2uW.js", "/ruralos/assets/index-1j-veDDz.js", "/ruralos/assets/index-C-330lm_.css", "/ruralos/assets/live-hub-BpOI5sNl.js", "/ruralos/assets/regional-guidance-CSB29cG6.js", "/ruralos/assets/task-assistant-8GGY7tVB.js", "/ruralos/family.webp", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/icon-512.png", "/ruralos/index.html", "/ruralos/install/index.html", "/ruralos/integrations/index.html", "/ruralos/manifest.webmanifest", "/ruralos/sitemap.xml"];
const CORE=["/ruralos/", "/ruralos/manifest.webmanifest", "/ruralos/favicon.svg", "/ruralos/icon-192.png", "/ruralos/assets/index-1j-veDDz.js", "/ruralos/assets/index-C-330lm_.css"];

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
