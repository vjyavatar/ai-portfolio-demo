import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {directory} from '../ruralos-src/lib/service-directory.ts';
import {playbooks} from '../ruralos-src/lib/service-playbooks.ts';
import {startTask,answerTask,confirmTask,executeTask,editTask} from '../ruralos-src/lib/task-engine.ts';
import {readFeed,feedIsOld,feedSources} from '../ruralos-src/lib/live-feed.ts';
const now=Date.parse('2026-09-29T00:00:00Z');
const good={status:'recent',source:feedSources.weather,message:'Recently retrieved',retrievedAt:now,items:[{id:'VIDP',name:'Delhi airport',temperatureC:22,observedAt:now-1000}]};
test('public feed rejects corrupt payloads, hostile source links and future times',()=>{
 assert.deepEqual(readFeed(good,'weather',now),good);
 for(const d of [null,{}, {...good,items:{}},{...good,source:'javascript:alert(1)'},{...good,retrievedAt:now+400000},{...good,retrievedAt:null},{...good,items:[{...good.items[0],temperatureC:NaN}]},{...good,items:[good.items[0],good.items[0]]},{...good,generatedAt:Infinity}])assert.throws(()=>readFeed(d,'weather',now));
 assert.throws(()=>readFeed(good,'earthquakes',now));
});
test('time passing makes cached public data stale without a fresh network response',()=>{
 assert.equal(feedIsOld(good,now),false);assert.equal(feedIsOld(good,now+600001),true);
 assert.equal(feedIsOld({...good,status:'stale'},now),true);assert.equal(feedIsOld(good,NaN),true);
 assert.equal(feedIsOld({...good,items:[{...good.items[0],observedAt:now-10800001}]},now),true);
});
for(const s of directory.filter(s=>playbooks[s.id])) test(s.id+': review, correct, reject private identifiers, never execute',()=>{
 let t=startTask(s.id);
 assert.throws(()=>confirmTask(t));
 assert.throws(()=>answerTask(t,'Not a state'));
 t=answerTask(t,'Telangana');
 assert.throws(()=>answerTask(t,'OTP 123456'));
 t=answerTask(t,playbooks[s.id].goals[0]);
 assert.equal(t.status,'review');t=confirmTask(t);
 assert.equal(t.status,'handoff');assert.throws(()=>executeTask(t));
 t=editTask(t,'goal');assert.equal(t.status,'collecting');assert.throws(()=>confirmTask(t));
 t=answerTask(t,playbooks[s.id].goals[1]);assert.equal(t.status,'review');
});
test('audit covers every catalogue service once with specific unresolved work',()=>{
 const a=JSON.parse(fs.readFileSync('data/ruralos-service-audit.json','utf8'));
 assert.deepEqual(a.services.map(x=>x.id),directory.map(x=>x.id));
 for(const s of a.services){assert.equal(s.transaction,'pending');assert.equal(s.ruralValidation,'pending');assert.ok(s.gap.length>45);assert.ok(s.goals.length);}
});
test('tracking styling is independently imported and does not imply positions are available',()=>{
 const c=fs.readFileSync('ruralos-src/app/live-hub.tsx','utf8');
 assert.match(c,/import '.\/live-hub.css'/);assert.match(c,/Pending integration/);assert.match(c,/readFeed\(await r.json/);assert.match(c,/feedIsOld\(data,now\)/);
 assert.match(c,/href="\/ruralos\/tracking"/);assert.match(c,/setBusy\(false\);setError\(''\)/);
});
