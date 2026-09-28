import {test} from 'node:test';import assert from 'node:assert/strict';
import {serviceScenarios,scenariosFor,scenarioResult,scenarioSources,scenarioReviewBy} from '../ruralos-src/lib/service-scenarios.ts';
const now=Date.parse('2026-09-29T00:00:00Z');
test('each reviewed scenario has distinct concrete guidance in all three languages',()=>{
 assert.equal(serviceScenarios.length,11);assert.equal(new Set(serviceScenarios.map(s=>s.id)).size,11);
 for(const s of serviceScenarios){for(const key of ['title','fact','next','prepare','followup']){assert.deepEqual(Object.keys(s[key]).sort(),['en','hi','te']);for(const l of ['en','hi','te'])assert.ok(s[key][l].length>10);assert.notEqual(s[key].en,s[key].hi);assert.notEqual(s[key].en,s[key].te)}assert.ok(scenarioSources[s.source]);assert.equal(scenarioResult(s.service,s.id,'Telangana',now).scenario,s)}
 assert.equal(new Set(serviceScenarios.map(s=>s.next.en)).size,11);
});
test('unknown and cross-service answers never produce a guessed answer',()=>{
 for(const id of ['', '__proto__','<script>alert(1)</script>','pension-oldage'])assert.equal(scenarioResult('farm',id,'Telangana',now).status,'unknown');assert.deepEqual(scenariosFor('unknown'),[]);
 assert.equal(scenarioResult('farm','farm-bank','Texas',now).status,'region');
});
test('expired, invalid and pre-review clocks suppress all factual answers',()=>{
 for(const s of serviceScenarios)for(const time of [Date.parse(scenarioReviewBy),Date.parse('2027-01-01'),Date.parse('2026-09-27'),NaN,Infinity]){const r=scenarioResult(s.service,s.id,'Delhi',time);assert.equal(r.status,'stale');assert.equal(r.scenario,null)}
});
test('every scenario uses an explicit public government route, never user data or executable schemes',()=>{
 for(const u of [...serviceScenarios.map(s=>s.url),...Object.values(scenarioSources).map(s=>s.url)]){const url=new URL(u);assert.equal(url.protocol,'https:');assert.equal(url.username,'');assert.equal(url.password,'');assert.ok(['pmkisan.gov.in','www.pib.gov.in','www.nfsa.gov.in','nfsa.gov.in','www.myscheme.gov.in'].includes(url.hostname));assert.doesNotMatch(url.search,/aadhaar|account|otp|token|email/i)}
});
test('pension amounts remain central shares, not personalised entitlement or state totals',()=>{
 for(const id of ['pension-oldage','pension-widow']){const s=serviceScenarios.find(s=>s.id===id);assert.match(s.fact.en,/central.*share|central monthly share/i);assert.match(s.fact.en,/BPL/);assert.match(s.fact.en,/State/);assert.match(s.followup.en,/state|local/i)}
 assert.match(serviceScenarios.find(s=>s.id==='farm-bank').next.en,/bank/);
 assert.match(serviceScenarios.find(s=>s.id==='farm-credit').next.en,/UTR/);
 assert.match(serviceScenarios.find(s=>s.id==='ration-away').fact.en,/existing NFSA/);
});
