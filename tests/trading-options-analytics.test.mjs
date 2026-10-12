import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const ctx = {};
vm.runInNewContext(fs.readFileSync('static/options-analytics.js', 'utf8'), ctx);
const analyze = rows => JSON.parse(JSON.stringify(ctx.CelesysOptionsAnalytics.analyze(rows)));
const row = (strike, callOI, putOI, cv = 20, pv = 40) => ({strike, call:{oi:callOI,volume:cv},put:{oi:putOI,volume:pv}});
test('pinned upstream arithmetic is adapted to normalized rows without directional inference', () => {
  const r = analyze([row(90,10,1), row(100,20,20), row(110,1,10)]);
  assert.deepEqual(r.pcr, {oi:1,volume:2});
  assert.equal(r.maxPain.strike,100);
  assert.equal(r.maxPain.status,'RETURNED_ROWS_ESTIMATE');
  assert.equal(r.coverage.scope,'RETURNED_ROWS_ONLY');
  assert.equal('interpretation' in r, false);
  assert.match(r.notes.join(' '), /not a direction signal/);
});
test('zero is real data but zero denominator and all-zero OI never become synthetic ratio or strike', () => {
  assert.equal(analyze([row(90,5,0),row(100,5,0)]).pcr.oi,0);
  const r=analyze([row(90,0,0),row(100,0,0)]);
  assert.equal(r.pcr.oi,null); assert.equal(r.maxPain.strike,null); assert.deepEqual(r.maxPain.strikes,[]);
  assert.equal(analyze([row(90,0,5),row(100,0,5)]).pcr.oi,null);
});
test('partial OI never masquerades as complete PCR/max pain; independent volume remains valid', () => {
  for (const bad of [null,undefined,NaN,Infinity,-1,'10',false]) {
    const r=analyze([row(90,10,20),row(100,bad,10)]);
    assert.equal(r.pcr.oi,null); assert.equal(r.maxPain.strike,null); assert.equal(r.pcr.volume,2);
    assert.equal(r.coverage.oiPairs,1);
  }
});
test('missing sides and missing volume do not coerce to zero', () => {
  const r=analyze([row(90,5,5),{strike:100,call:{oi:10,volume:20}}]);
  assert.deepEqual(r.pcr,{oi:null,volume:null}); assert.equal(r.maxPain.strike,null);
  const partial=analyze([row(90,5,5),row(100,10,10,null,null)]);
  assert.equal(partial.pcr.oi,1); assert.equal(partial.pcr.volume,null);
});
test('tied minima are explicit and not silently resolved to first strike', () => {
  const r=analyze([row(90,10,0),row(100,0,10)]);
  assert.equal(r.maxPain.strike,null); assert.deepEqual(r.maxPain.strikes,[90,100]);
  assert.equal(r.maxPain.status,'TIED_RETURNED_ROWS_ESTIMATE');
});
test('unsorted rows do not mutate input and produce the same strike', () => {
  const rows=[row(110,1,10),row(90,10,1),row(100,20,20)];
  const before=JSON.stringify(rows); assert.equal(analyze(rows).maxPain.strike,100); assert.equal(JSON.stringify(rows),before);
});
test('invalid and duplicate strike sets fail closed', () => {
  for (const rows of [[row(90,1,1),row(90,1,1)], [null], [row(0,1,1)], [row('90',1,1)], [row(Infinity,1,1)], Array.from({length:1001},(_,i)=>row(i+1,1,1))]) {
    const r=analyze(rows); assert.equal(r.pcr.oi,null); assert.equal(r.maxPain.strike,null);
  }
});
test('empty and single strike chains cannot invent a minimum-payout strike', () => {
  for(const rows of [[],null,{},[row(100,1,1)]]) assert.equal(analyze(rows).maxPain.strike,null);
});
test('inconsistent and partially supplied multipliers withhold minimum payout', () => {
  for(const lots of [[65,65,30,30],[65,65,null,null],[0,0,0,0]]) {
    const rows=[row(90,10,1),row(100,1,10)];
    [rows[0].call,rows[0].put,rows[1].call,rows[1].put].forEach((c,i)=>c.lot_size=lots[i]);
    assert.equal(analyze(rows).maxPain.status,'INSUFFICIENT_DATA');
  }
});
test('overflow cannot expose infinite ratios or payouts', () => {
  const r=analyze([row(1,Number.MAX_VALUE,Number.MAX_VALUE),row(1e100,Number.MAX_VALUE,Number.MAX_VALUE)]);
  assert.equal(r.pcr.oi,null);assert.equal(r.maxPain.strike,null);assert.deepEqual(r.maxPain.strikes,[]);
});
