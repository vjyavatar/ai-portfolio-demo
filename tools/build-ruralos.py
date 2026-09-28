"""Rebuild the public client while preserving public pages and artwork."""
from pathlib import Path
import tempfile,shutil,subprocess,json,hashlib,os,re
root=Path(__file__).resolve().parents[1]
os.chdir(root)
with tempfile.TemporaryDirectory() as tmp:
 for p in Path('ruralos').iterdir():
  if p.name in ('assets','index.html'):continue
  target=Path(tmp)/p.name
  shutil.copytree(p,target) if p.is_dir() else shutil.copy(p,target)
 vite=Path('ruralos-src/node_modules/vite/bin/vite.js')
 subprocess.run(['node',str(vite),'build','--config','ruralos-src/vite.config.mjs'],check=True)
 for p in Path(tmp).iterdir():
  target=Path('ruralos')/p.name
  shutil.copytree(p,target,dirs_exist_ok=True) if p.is_dir() else shutil.copy(p,target)
subprocess.run(['python', 'ruralos_alerts.py'],check=True)
# Research snapshots must not become offline/current-looking alerts.
files=['/ruralos/']+sorted('/'+p.as_posix() for p in Path('ruralos').rglob('*') if p.is_file() and p.name!='sw.js' and 'alerts' not in p.parts and p.name!='alerts.js')
entry=Path('ruralos/index.html').read_text()
core=['/ruralos/','/ruralos/manifest.webmanifest','/ruralos/favicon.svg','/ruralos/icon-192.png']+re.findall(r'(?:src|href)="(/ruralos/assets/[^"?]+)"',entry)
key=hashlib.sha256(''.join(files).encode()).hexdigest()[:12]
tail="""
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
"""
Path('ruralos/sw.js').write_text('const CACHE="saathi-ruralos-'+key+'",ASSETS='+json.dumps(files)+';\nconst CORE='+json.dumps(core)+';\n'+tail)
