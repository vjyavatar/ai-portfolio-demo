import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const source=fs.readFileSync('ruralos/sw.js','utf8');
function harness({fail=false,full=false}={}){
 const events={},stored=new Map(),added=[];
 const cache={addAll:async paths=>added.push(...paths),put:async(path,r)=>{if(full)throw Error('quota');stored.set(path,r)},match:async p=>stored.get(p)};
 const sandbox={self:{location:{origin:'https://celesys.ai'},addEventListener:(name,fn)=>events[name]=fn},URL,Response,caches:{open:async()=>cache,keys:async()=>[],delete:async()=>true},fetch:async()=>{if(fail)throw Error('offline');return new Response('network',{status:200})}};
 vm.runInNewContext(source,sandbox);
 return {stored,added,async install(){await new Promise((resolve,reject)=>events.install({waitUntil:p=>p.then(resolve,reject)}))},async request(path,method='GET'){let result=null;events.fetch({request:{url:'https://celesys.ai'+path,method},respondWith:p=>{result=p}});return result?await result:null}};
}
test('precache loads core home but defers heavy family tools',async()=>{const h=harness();await h.install();assert.ok(h.added.includes('/ruralos/'));assert.ok(h.added.some(x=>x.endsWith('.js')));assert.ok(!h.added.some(x=>x.includes('app-shell-')));assert.ok(!h.added.some(x=>x.includes('tracking')))});
test('private routes, feeds, writes and unknown paths are never cached/intercepted',async()=>{const h=harness();for(const p of ['/ruralos/tracking','/ruralos-data/weather','/ruralos/alerts/','/ruralos/alerts/feed.json','/ruralos/alerts/india/','/ruralos/alerts.js','/api/session','/ruralos/unknown','/nextstep/'])assert.equal(await h.request(p),null);assert.equal(await h.request('/ruralos/','POST'),null)});
test('public network success is cached and quota failure still serves network',async()=>{const h=harness();assert.equal(await(await h.request('/ruralos/')).text(),'network');assert.ok(h.stored.has('/ruralos/'));const full=harness({full:true});assert.equal(await(await full.request('/ruralos/')).text(),'network')});
test('offline query navigation uses cached home; unvisited chunks fail honestly',async()=>{const h=harness({fail:true});h.stored.set('/ruralos/',new Response('saved'));assert.equal(await(await h.request('/ruralos/?service=land')).text(),'saved');const asset=source.match(/\/ruralos\/assets\/app-shell-[^" ]+\.js/)[0];assert.equal((await h.request(asset)).type,'error')});
