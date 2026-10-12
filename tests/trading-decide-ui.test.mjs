import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const src=fs.readFileSync('static/app.js','utf8');
function harness(){
 const timers=new Map(),notices=[],events={},calls=[],result={innerHTML:''};let id=0;
 const context={window:{_deMode:'trader',_deRegion:'US',_lastDESym:'SPY'},document:{hidden:false,addEventListener:(n,f)=>events[n]=f,getElementById:n=>n==='deResult'?result:null,querySelectorAll:()=>[],body:{appendChild:n=>notices.push(n)},createElement:()=>({setAttribute(){},remove(){},style:{}})},Date,AbortController,console,
 setTimeout:(f,ms)=>{timers.set(++id,{f,ms});return id;},clearTimeout:n=>timers.delete(n),clearInterval:n=>timers.delete(n),_autoRefreshTimer:null,_autoRefreshCount:0,
 loadDE:(...args)=>calls.push(args)};
 vm.createContext(context);
 vm.runInContext(src.slice(src.indexOf('var _deRequestSeq=0'),src.indexOf('// ═══ TOP INDEX TRADES')),context);
 return {context,timers,notices,events,calls,result};
}
test('original Decide direction notifications are symbol scoped and deduplicated',()=>{
 const h=harness(),c=h.context;
 c._checkDirectionChange('SPY','BULLISH');c._checkDirectionChange('QQQ','BEARISH');assert.equal(h.notices.length,0);
 c._checkDirectionChange('SPY','BEARISH');c._checkDirectionChange('SPY','BEARISH');assert.equal(h.notices.length,1);
 assert.match(h.notices[0].textContent,/SPY.*US.*unverified/);assert.equal(c.window._soundEnabled,false);
 c._checkDirectionChange('INVALID');assert.equal(h.notices.length,1);
 c.document.hidden=true;c._checkDirectionChange('SPY','BULLISH');assert.equal(h.notices.length,1);
});
test('original Decide auto refresh has one five-minute timer and stops when hidden',()=>{
 const h=harness(),c=h.context;c.startAutoRefresh('SPY');assert.equal(h.timers.size,1);
 const timer=[...h.timers.values()][0];assert.ok(timer.ms>0&&timer.ms<=301500);timer.f();
 assert.equal(h.calls.length,1);assert.deepEqual([...h.calls[0]],['SPY',null,true]);
 c.document.hidden=true;h.events.visibilitychange();assert.equal(c._deAutoContext,null);assert.equal(c._autoRefreshTimer,null);
});
test('legacy price timer is cleared when Decide refresh stops',()=>{
 const h=harness(),c=h.context;c.window._arPriceTimer=c.setTimeout(()=>{},30000);c.stopAutoRefresh();
 assert.equal(c.window._arPriceTimer,null);assert.equal(h.timers.size,0);
});
test('original Decide rejects old symbol/region/mode request generations',()=>{
 const {context:c}=harness();assert.equal(c._deCurrent(0,'SPY','US'),true);
 c._cancelDERequest();assert.equal(c._deCurrent(0,'SPY','US'),false);
 assert.equal(c._deCurrent(1,'QQQ','US'),false);assert.equal(c._deCurrent(1,'SPY','IN'),false);
 c.window._deMode='investor';assert.equal(c._deCurrent(1,'SPY','US'),false);
});
test('late original-engine failure cannot replace a newer symbol result',async()=>{
 const h=harness(),c=h.context,pending=[];c.fetch=(url,options)=>new Promise(resolve=>pending.push({resolve,options}));
 vm.runInContext(src.slice(src.indexOf('function loadDE(sym,autoTab,refreshRun){'),src.indexOf('// ═══ NEWS IMPACT ANALYZER')),c);
 c.loadDE('SPY');c.loadDE('QQQ');assert.equal(pending[0].options.signal.aborted,true);
 pending[1].resolve({ok:true,json:async()=>({success:false,error:'QQQ unavailable'})});await new Promise(r=>setImmediate(r));
 assert.match(h.result.innerHTML,/QQQ unavailable/);
 pending[0].resolve({ok:true,json:async()=>({success:false,error:'old SPY error'})});await new Promise(r=>setImmediate(r));
 assert.match(h.result.innerHTML,/QQQ unavailable/);assert.doesNotMatch(h.result.innerHTML,/old SPY/);
});
