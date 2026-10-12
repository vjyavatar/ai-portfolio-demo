import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
test("legacy validation panel makes no invented performance claim", () => {
  const source=fs.readFileSync(new URL("../static/options-engine.js",import.meta.url),"utf8");
  const body=source.slice(source.indexOf("window._renderBacktest=function"),source.indexOf("// ─── FEATURE 4:"));
  const context={window:{}};vm.runInNewContext(body,context);
  const html=context.window._renderBacktest();
  assert.match(html,/not established/);
  assert.match(html,/unavailable/);
  assert.doesNotMatch(html,/\d+%|Historical win rate/);
});
function earningsRenderers() {
 const source=fs.readFileSync(new URL('../static/premium-override.js',import.meta.url),'utf8');
 const body=source.slice(source.indexOf('window._earningsSparkline=function'),source.indexOf('// ━━━ TRADER: Signal Strength Dashboard'));
 const context={window:{}};vm.runInNewContext(body,context);return context.window;
}
test('current EPS and growth cannot fabricate a quarterly chart',()=>{
 const html=earningsRenderers()._earningsSparkline({price:100,eps:5,earnings_growth:20},'$');
 assert.match(html,/history is unavailable/);assert.doesNotMatch(html,/<svg|8Q|ACCELERATING|YoY/);
});
test('reported EPS chart preserves negative and zero actuals and orders source periods',()=>{
 const html=earningsRenderers()._earningsSparkline({earnings_history:{source:'Provider & filings',quarters:[
  {quarter:'2026-06-30',eps_actual:0},{quarter:'2026-03-31',eps_actual:-2}
 ]}},'$');
 assert.match(html,/<svg/);assert.match(html,/2 reported periods/);assert.match(html,/Latest reported EPS: \$0.00/);
 assert.match(html,/Provider &amp; filings/);assert.match(html,/2026-03-31.*2026-06-30/);
 assert.match(html,/4.00,46.00 276.00,4.00/);
});
test('untraceable, missing, duplicated or invalid EPS records remain unavailable',()=>{
 const good=[{quarter:'2026-03-31',eps_actual:1},{quarter:'2026-06-30',eps_actual:2}];
 for(const history of [{quarters:good},{source:'Provider',quarters:good.slice(0,1)},
  {source:'Provider',quarters:[good[0],good[0]]},
  {source:'Provider',quarters:[good[0],{quarter:'2026-02-30',eps_actual:2}]},
  {source:'Provider',quarters:[good[0],{quarter:'2026-06-30',eps_estimate:2}]},
  {source:'Provider',quarters:[good[0],{quarter:'2026-06-30',eps_actual:NaN}]}]) {
  assert.doesNotMatch(earningsRenderers()._earningsSparkline({earnings_history:history}),/<svg/);
 }
});
test('sector card never derives invented rankings or trading advice from one stock',()=>{
 const html=earningsRenderers()._sectorStrengthMap({price:100,rsi:80,sector:'Technology'});
 assert.match(html,/comparison is unavailable/);assert.doesNotMatch(html,/ranks #|Hold\/Add|85|width:\d+%/);
});
