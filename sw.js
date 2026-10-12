// Network-first navigation prevents an old homepage from trapping returning users.
const CACHE_NAME='celesys-unified-20261012';
self.addEventListener('install',event=>{self.skipWaiting();event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.add('/')));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('celesys-')&&k!==CACHE_NAME).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
 if(event.request.method!=='GET')return;
 const url=new URL(event.request.url);
 if(url.origin!==self.location.origin)return;
 if(url.pathname.startsWith('/api/')){event.respondWith(fetch(event.request));return;}
 if(event.request.mode==='navigate'){
  event.respondWith(fetch(event.request).then(response=>{if(response.ok&&url.pathname==='/'){const copy=response.clone();event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.put('/',copy)));}return response;}).catch(()=>caches.match('/').then(r=>r||new Response('Celesys is offline. Reconnect to retrieve market data.',{status:503,headers:{'Content-Type':'text/plain'}}))));return;
 }
 // JS/CSS always revalidate; never serve obsolete engine or UI code from SW cache.
 event.respondWith(fetch(event.request));
});
