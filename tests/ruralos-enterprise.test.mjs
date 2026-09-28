import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {programmes,goals,forGoal,fresh} from '../ruralos-src/lib/enterprise.ts';
import {resolveSpokenService} from '../ruralos-src/lib/service-directory.ts';
test('seven programmes, distinct support types, no guessed goal',()=>{
 assert.equal(programmes.length,7);assert.equal(new Set(programmes.map(p=>p.id)).size,7);
 assert.deepEqual(forGoal('__proto__'),[]);assert.deepEqual(forGoal('not a real purpose'),[]);
 for(const g of goals)assert.ok(forGoal(g.id).length);
 assert.ok(!forGoal('grow').some(p=>p.id==='pmegp'));
 assert.deepEqual(forGoal('innovation').map(p=>p.id),['seed']);
});
test('dated financial guidance fails closed on stale and invalid clocks',()=>{
 for(const n of [NaN,Infinity,0,Date.parse('2026-10-12T00:00:00Z')])assert.equal(fresh(n),false);
 assert.equal(fresh(Date.parse('2026-09-29T00:00:00Z')),true);
});
test('every programme has three-language substance and a secure official route',()=>{
 const hosts=new Set(['financialservices.gov.in','www.kviconline.gov.in','pmvishwakarma.gov.in','www.pib.gov.in','seedfund.startupindia.gov.in','www.cgtmse.in','udyamregistration.gov.in','ati.msme.gov.in']);
 for(const p of programmes){for(const key of ['type','benefit','fit','next','caution'])for(const lang of ['en','hi','te'])assert.ok(p[key][lang].length>12);
  for(const raw of [p.url,p.evidence].filter(Boolean)){const u=new URL(raw);assert.equal(u.protocol,'https:');assert.ok(hosts.has(u.hostname));assert.equal(u.username,'');assert.ok(!/aadhaar|account|otp/i.test(u.search));}
 }
 assert.match(programmes.find(p=>p.id==='mudra').benefit.en,/successfully repaying/);
 assert.match(programmes.find(p=>p.id==='seed').caution.en,/not verified/);
 assert.match(programmes.find(p=>p.id==='cgtmse').benefit.en,/not a direct/);
 assert.match(programmes.find(p=>p.id==='udyam').caution.en,/not company incorporation/);
});
test('business programmes are discoverable by exact programme name',()=>{
 for(const q of ['MUDRA','PMEGP','CGTMSE','entrepreneurship'])assert.equal(resolveSpokenService(q),'business');
});
test('real local tutorial with three caption files, no autoplay or video precache',()=>{
 const media=fs.readFileSync('ruralos/media/saathi-tour-v1.mp4');assert.ok(media.length>1000&&media.length<1000000);assert.equal(media.toString('ascii',4,8),'ftyp');
 for(const lang of ['en','hi','te']){const v=fs.readFileSync(`ruralos/media/saathi-tour-v1-${lang}.vtt`,'utf8');assert.match(v,/^WEBVTT/);assert.equal((v.match(/-->/g)||[]).length,4);assert.match(v,/00:00:28.000/);}
 const component=fs.readFileSync('ruralos-src/app/home-video.tsx','utf8');assert.match(component,/preload="none"/);assert.doesNotMatch(component,/autoPlay|auto[Pp]lay=/);assert.match(component,/onError/);
 assert.doesNotMatch(fs.readFileSync('ruralos/sw.js','utf8'),/\/ruralos\/media\//);
});
