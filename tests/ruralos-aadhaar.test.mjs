import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mobileRoute,mobileCopy,mobileReviewBy} from '../ruralos-src/lib/aadhaar-mobile.ts';
const now=Date.parse('2026-09-28T20:00:00Z');
for(const access of ['yes','no','first','unknown'])for(const app of ['same','different','unknown'])test(`Aadhaar route: ${access}/${app}`,()=>{
 const expected=access==='no'||access==='first'?'centre':access==='unknown'||app==='unknown'?'unknown':app;
 assert.equal(mobileRoute(access,app,now),expected);
});
test('expired and invalid observation times require source review, not a route',()=>{
 for(const access of ['yes','no','first','unknown'])assert.equal(mobileRoute(access,'same',Date.parse(mobileReviewBy)),'review');
 assert.equal(mobileRoute('yes','same',NaN),'review');
 assert.equal(mobileRoute('<script>','same',now),'unknown');
});
test('each Aadhaar language includes every route and control without requesting IDs',()=>{
 const keys=Object.keys(mobileCopy.en).sort();for(const language of ['hi','te'])assert.deepEqual(Object.keys(mobileCopy[language]).sort(),keys);
 for(const c of Object.values(mobileCopy)){assert.equal(c.choices.length,4);assert.equal(c.appChoices.length,3);for(const v of Object.values(c))assert.ok(v.length);}
});
