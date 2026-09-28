import fs from 'node:fs';
import path from 'node:path';
const required=['ruralos/index.html','ruralos/sw.js','ruralos/manifest.webmanifest','ruralos/icon-192.png','ruralos/icon-512.png'];
for(const f of required)if(!fs.existsSync(f))throw Error('Missing '+f);
const html=fs.readFileSync('ruralos/index.html','utf8');
for(const [,asset] of html.matchAll(/(?:src|href)="(\/ruralos\/assets\/[^"?#]+)"/g))if(!fs.existsSync(asset.slice(1)))throw Error('Missing '+asset);
// Dynamic chunks are only opened after a service selection. Verify them too.
for(const filename of fs.readdirSync('ruralos/assets').filter(f=>f.endsWith('.js'))){
 const data=fs.readFileSync('ruralos/assets/'+filename,'utf8');
 for(const [,chunk] of data.matchAll(/(?:from\s*|import\()?["']\.\/([^"']+\.(?:js|css))["']/g))if(!fs.existsSync(path.join('ruralos/assets',chunk)))throw Error('Missing dynamic asset '+chunk);
 if(/sk-proj-[A-Za-z0-9]{15}|AIza[A-Za-z0-9_-]{20}|-----BEGIN PRIVATE KEY-----/.test(data))throw Error('Potential secret in public bundle');
}
const sw=fs.readFileSync('ruralos/sw.js','utf8');const assets=JSON.parse(sw.match(/ASSETS=(\[[^;]+\]);/)?.[1]??'null');
if(!Array.isArray(assets))throw Error('Invalid offline manifest');
for(const a of assets){if(!a.startsWith('/ruralos/')||a.includes('tracking'))throw Error('Unsafe cache entry '+a);if(a!=='/ruralos/'&&!fs.existsSync(a.slice(1)))throw Error('Missing offline asset '+a)}
console.log('Rural OS entry, dynamic chunks, public cache and secret-pattern checks passed');
