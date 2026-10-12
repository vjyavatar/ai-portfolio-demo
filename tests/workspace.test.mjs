import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),core=require('../static/workspace-core.js');
const app=fs.readFileSync(new URL('../static/app.js',import.meta.url),'utf8');
const groups={};vm.runInNewContext(app.slice(app.indexOf('var TAB_GROUPS ='),app.indexOf("window._activeGroup = 'overview'")),groups);
test('all 48 original tools remain catalogued once with valid groups',()=>{const items=core.catalog(groups.TAB_GROUPS,{});assert.equal(items.length,48);assert.equal(new Set(items.map(x=>x.tab)).size,48);for(const t of items){assert.ok(groups.TAB_GROUPS[t.group].tabs.includes(t.tab));assert.ok(t.label);}});
test('menu directory respects public, trading, full and dream access',()=>{for(const g of ['research','decide','dream','markets','movers','moat','structural','scanner360','intradayopt','trading'])assert.equal(core.canOpen(g,'x',{role:'public'}),false);assert.equal(core.canOpen('tools','education',{}),true);assert.equal(core.canOpen('trading','trades',{role:'trading'}),true);assert.equal(core.canOpen('trading','journal',{role:'trading'}),false);assert.equal(core.canOpen('dream','optionspulse',{role:'full',dream:false}),false);assert.equal(core.canOpen('dream','optionspulse',{role:'full',dream:true}),true);});
test('CSV preserves zero versus missing, comma-quoted numbers and both sides',()=>{const rows=core.parseCSV('strike,ce_bid,ce_ask,ce_oi,pe_bid,pe_ask,pe_oi\n"25,000",100,102,0,-,80,"1,400"');assert.equal(rows[0].strike,25000);assert.equal(rows[0].call.oi,0);assert.equal(rows[0].put.bid,null);assert.equal(rows[0].put.oi,1400);assert.equal(rows[0].call.bid_time,null);});
test('standard NSE call / strike / put column layout parses correctly',()=>{const h=['','OI','CHNG IN OI','VOLUME','IV','LTP','CHNG','BID QTY','BID','ASK','ASK QTY','STRIKE','BID QTY','BID','ASK','ASK QTY','CHNG','LTP','IV','VOLUME','CHNG IN OI','OI',''];const r=['',100,2,20,15,50,1,10,49,51,10,25000,10,59,61,10,-1,60,16,21,3,200,''];const rows=core.parseCSV('CALLS,,,,,,,,,,,PUTS\n'+h.join(',')+'\n'+r.join(','));assert.equal(rows[0].call.bid,49);assert.equal(rows[0].put.ask,61);assert.equal(rows[0].put.oi,200);assert.equal(rows[0].call.iv_pct,15);});
test('ambiguous, oversized and malformed CSVs are rejected',()=>{assert.throws(()=>core.parseCSV('strike,ce_bid\n100,2\n100,3'),/Duplicate/);assert.throws(()=>core.parseCSV('foo,bar\n1,2'),/strike/);assert.throws(()=>core.parseCSV('strike,ce_bid\n100,"2'),/quoted/);assert.throws(()=>core.parseCSV('x'.repeat(1000001)),/1 MB/);});
test('position sizing never forces one lot beyond risk or capital',()=>{const v={capital:1000,risk:1,entry:20,stop:10,target:40,multiplier:100};assert.equal(core.sizePlan(v).lots,0);const p=core.sizePlan({...v,capital:10000,risk:2,multiplier:10});assert.equal(p.lots,2);assert.equal(p.plannedRisk,200);assert.equal(p.cost,400);assert.equal(p.rr,2);});
test('invalid direction, multiplier, risk or nonfinite inputs cannot form a plan',()=>{const v={capital:10000,risk:1,entry:100,stop:90,target:120,multiplier:1};for(const patch of [{stop:100},{target:90},{multiplier:1.5},{risk:0},{capital:Infinity}])assert.throws(()=>core.sizePlan({...v,...patch}));});
test('runtime frontend has no broker login/status calls',()=>{for(const path of ['app.js','app.min.js','active-trading.js','workspace.js']){const text=fs.readFileSync(new URL('../static/'+path,import.meta.url),'utf8');assert.doesNotMatch(text,/\/api\/upstox-(?:login|status)/);}});
test('simplified trading view preserves the existing report DOM',()=>{const block=app.slice(app.indexOf('window._loadTradingView=function'),app.indexOf('window._renderTradingView=function'));assert.match(block,/host\.appendChild\(rpt\)/);assert.match(block,/getElementById\('tradingOnlyView'\)/);});
// Lightweight DOM interaction harness. No external market calls or speech services.
class Element{
 constructor(id=''){this.id=id;this.value='';this.hidden=false;this.textContent='';this.events={};this.children=[];this.dataset={};this.style={setProperty(){}};this.tagName='INPUT';this.classList={toggle(){},add(){},remove(){},contains(){return false;}};}
 addEventListener(k,f){this.events[k]=f;}append(...v){this.children.push(...v);}insertBefore(child,before){const i=this.children.indexOf(before);if(i<0)this.children.push(child);else this.children.splice(i,0,child);}replaceChildren(...v){this.children=[...v];}setAttribute(k,v){this[k]=v;}getAttribute(k){return this[k];}removeAttribute(k){delete this[k];}scrollIntoView(){}focus(){}click(){}async emit(k){return this.events[k]?.({preventDefault(){},target:this});}
}
function setup(){const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,new Element(id));return nodes.get(id);};get('ws-symbol').value='AAPL';get('ws-region').value='US';let response;
const context={document:{getElementById:get,createElement:()=>new Element(),querySelector:()=>null,querySelectorAll:()=>[],addEventListener(){},body:{classList:{remove(){},toggle(){return false;}}}},CelesysWorkspaceCore:core,TAB_GROUPS:groups.TAB_GROUPS,URLSearchParams,AbortController,Intl,Date,Blob,URL,location:{search:''},navigator:{},setTimeout:()=>1,clearTimeout(){},fetch:()=>new Promise(r=>response=r),speechSynthesis:{cancel(){}},_voiceEnabled:false};context.window=context;vm.runInNewContext(fs.readFileSync(new URL('../static/workspace.js',import.meta.url),'utf8'),context);return {get,context,respond:d=>response({ok:true,json:async()=>d})};}
test('changing symbols clears old evidence, contract and position plan',async()=>{const a=setup();a.get('ws-entry').value='120';a.get('ws-plan-contract').textContent='old contract';await a.get('ws-symbol').emit('input');assert.equal(a.get('ws-entry').value,'');assert.equal(a.get('ws-plan-contract').textContent,'Choose inputs');assert.equal(a.get('ws-results').hidden,true);});
test('late response cannot overwrite a changed symbol',async()=>{const a=setup(),pending=a.get('ws-search').emit('submit');a.get('ws-symbol').value='MSFT';await a.get('ws-symbol').emit('input');a.respond({symbol:'AAPL',evidence:[],missing_data:[],generated_at:1});await pending;assert.equal(a.get('ws-results').hidden,true);});
test('brief renders all five sections as literal text and preserves existing assessment',async()=>{const a=setup(),pending=a.get('ws-search').emit('submit');a.respond({symbol:'AAPL',region:'US',engine:'stock-dashboard',assessment:'<script>text only</script>',counterargument:'Risk',next_check:'Verify',evidence:[],missing_data:['price'],generated_at:1});await pending;assert.equal(a.get('ws-brief-grid').children.length,5);assert.equal(a.get('ws-brief-grid').children[0].children[1].textContent,'<script>text only</script>');});
test('blocked original tool does not call its renderer',()=>{const a=setup();a.context.switchTabGroup=()=>{throw Error('Must not run');};a.context.CelesysWorkspace.openTool({group:'dream',tab:'optionspulse',label:'Options Pulse'});assert.equal(a.get('ws-account').hidden,false);assert.match(a.get('ws-status').textContent,/account access/);});
test('voice is opt-in and stop mutes the shared voice flag',async()=>{const a=setup();assert.equal(a.context._voiceEnabled,false);await a.get('ws-voice-toggle').emit('click');assert.equal(a.context._voiceEnabled,true);assert.equal(a.get('ws-voice-toggle')['aria-pressed'],'true');await a.get('ws-stop').emit('click');assert.equal(a.context._voiceEnabled,false);});
test('unsupported microphone leaves a usable typed-input fallback',async()=>{const a=setup();await a.get('ws-dictate').emit('click');assert.match(a.get('ws-status').textContent,/Type a symbol/);assert.equal(a.get('ws-symbol').value,'AAPL');});
test('original email allowlist controls actual menu visibility for every role',()=>{
 const source=app.slice(app.indexOf('  function applyTabAccess(email){'),app.indexOf('  // ═══ 4. IDLE CHECK'));
 for(const [email,role] of [['visitor@example.org','public'],['allowed@example.org','full'],['tmp@cls.com','trading'],['vj@vnky.com','admin'],['ALLOWED@EXAMPLE.ORG','full'],['','public']]){
  const nodes=new Map(),ctx={CELESYS_TIERS:{full_access:['allowed@example.org']},console:{log(){}},setInterval(){return 1;},clearInterval(){},setTimeout(){},document:{querySelectorAll(sel){if(!nodes.has(sel))nodes.set(sel,{style:{}});return [nodes.get(sel)];}}};ctx.window=ctx;
  vm.runInNewContext(source+';applyTabAccess('+JSON.stringify(email)+');',ctx);
  assert.equal(ctx._userRole,role);
  assert.equal(nodes.get('#tabBtnResearch').style.display,['admin','full'].includes(role)?'':'none');
  assert.equal(nodes.get('#tabBtnTrading').style.display,role==='public'?'none':'');
  assert.equal(nodes.get('#pdfExportBtn').style.display,role==='admin'?'':'none');
 }
});
test('original chart form is visible before the optional quick brief',()=>{
 const html=fs.readFileSync(new URL('../static/workspace.html',import.meta.url),'utf8');
 assert.doesNotMatch(html,/<section id="ws-account"[^>]*\bhidden/);
 assert.ok(html.indexOf('id="ws-legacy-search"')<html.indexOf('id="ws-search"'));
 assert.match(app,/try\{createCharts\(d\)\}/);
});
test('return to charts reveals an existing report without refetching or rebuilding it',async()=>{
 const a=setup();let shown=false,scrolled=false;
 a.get('report').classList.contains=()=>true;
 a.get('report').style.setProperty=(key,val)=>{shown=key==='display'&&val==='block';};
 a.get('report').scrollIntoView=()=>{scrolled=true;};
 a.get('report').children=['existing charts'];
 await a.get('ws-return-report').emit('click');
 assert.equal(shown,true);assert.equal(scrolled,true);assert.deepEqual(a.get('report').children,['existing charts']);
});
// Exercise the actual workspace dispatcher for every catalogued tool in six permission profiles.
for(const tool of setup().context.CelesysWorkspace.tools){
 test('all-menu dispatcher: '+tool.group+'/'+tool.tab,()=>{
  const profiles=[{role:'public'},{role:'trading'},{role:'full'},{role:'full',premium:true},{role:'full',premium:true,dream:true},{role:'admin',premium:true,dream:true}];
  for(const profile of profiles){
   const a=setup();Object.assign(a.context,{_userRole:profile.role,_isPremiumUser:profile.premium,_isDreamUser:profile.dream,_stockData:{ticker:'QA'},_verifiedEmail:'qa@example.invalid'});
   let opened=false;
   a.context.switchTabGroup=()=>{opened=true;};a.context.switchTab=()=>{};a.context.switchDEMode=()=>{opened=true;};
   a.context.CelesysWorkspace.openTool(tool);
   const groupAllowed=['overview','tools'].includes(tool.group)||(['trading','intradayopt'].includes(tool.group)?['trading','full','admin'].includes(profile.role):['full','admin'].includes(profile.role));
   const permitted=groupAllowed&&((tool.group!=='dream'&&!['mchunter','intraday'].includes(tool.tab))||!!profile.dream)&&(!['smarttrades','journal','aiassist','valreport','backtest','stockintel','pms','proscan'].includes(tool.tab)||!!profile.premium);
   if(!permitted){assert.equal(opened,false);assert.match(a.get('ws-status').textContent,/account access/);}
   else if(tool.tab==='_today'){assert.equal(a.get('ws-embedded').hidden,false);assert.match(a.get('ws-today-frame').src,/^\/today\?email=/);}
   else assert.equal(opened,true,profile.role+' should reach '+tool.tab);
  }
 });
}

test('homepage keeps secondary controls collapsed and trading/options open them',()=>{
 const a=setup();assert.equal(a.get('ws-quick-controls').open,false);
 for(const mode of ['trading','options']){a.context.CelesysWorkspace.setMode(mode);assert.equal(a.get('ws-quick-controls').open,true);}
 a.context.CelesysWorkspace.setMode('stock');assert.equal(a.get('ws-quick-controls').open,false);
});
test('internal quick stock task keeps its form open and leaves original report hidden',()=>{
 const a=setup();let shown=false;a.get('report').style.setProperty=(k,v)=>{shown=v==='block';};a.get('report').classList.contains=()=>true;
 a.context.CelesysWorkspace.setMode('stock',false,true);
 assert.equal(a.get('ws-quick-controls').open,true);assert.equal(shown,false);
});
test('stock navigation restores original overview and retained charts after another tool',()=>{
 const a=setup();let selected='',shown=false;a.context._stockData={ticker:'AAPL'};
 a.context.switchTabGroup=g=>{selected=g;};a.get('report').classList.contains=()=>true;a.get('report').style.setProperty=(k,v)=>{shown=v==='block';};
 a.context.CelesysWorkspace.setMode('stock');assert.equal(selected,'overview');assert.equal(shown,true);
});
test('browser focus and developer tools never blur reports or block the whole page',()=>{
 assert.doesNotMatch(app,/classList\.add\('trades-blurred'\)/);
 assert.doesNotMatch(app,/devtoolsOverlay|Screen capture blocked/);
 assert.match(app,/function applyTabAccess\(email\)/);
});
test('analyzing a full report closes secondary controls',async()=>{
 const a=setup();a.get('ws-quick-controls').open=true;await a.get('btn').emit('click');assert.equal(a.get('ws-quick-controls').open,false);
});
test('late permission refresh retains access checks without initiating navigation',()=>{
 const source=app.slice(app.indexOf('function _applyPremiumGating('),app.indexOf('// Email listeners —'));
 const calls=[],report={classList:{contains:()=>true}},button={style:{}};
 const scope={document:{getElementById:id=>id==='report'?report:button,querySelectorAll:()=>[]},TRADING_ONLY_EMAILS:[],initTradesProtection(){},renderPicks(){},renderFunds(){},switchTabGroup:(...args)=>calls.push(args)};scope.window=scope;
 vm.runInNewContext(source,scope);
 scope._activeGroup='research';scope._applyPremiumGating(false,false,'qa@example.invalid');
 assert.equal(calls[0][0],'overview');assert.equal(calls[0][1].scroll,false);
 scope._activeGroup='dream';scope._applyDreamGating(true);
 assert.equal(calls[1][0],'dream');assert.equal(calls[1][1].scroll,false);
});
test('summary and research refreshes suppress scroll only when explicitly requested',()=>{
 const source=app.slice(app.indexOf('function switchAnalysisSubTab('),app.indexOf('// ═══ TAB GROUP SYSTEM'));
 let scrolls=0;const section={scrollIntoView(){scrolls++;}},button={classList:{add(){},remove(){}}};
 const scope={document:{querySelectorAll:()=>[],querySelector:()=>section,getElementById:()=>button},setTimeout(){}};scope.window=scope;
 vm.runInNewContext(source,scope);
 scope.switchSubTab('overview',{scroll:false});scope.switchAnalysisSubTab('report',{scroll:false});
 assert.equal(scrolls,0);
 scope.switchSubTab('overview');scope.switchAnalysisSubTab('report');assert.equal(scrolls,2);
});

test('focused views keep scanner out of home and open it only for trading',()=>{const a=setup();assert.equal(a.get('tw-panel').hidden,true);assert.equal(a.get('ws-quick-controls').hidden,true);assert.equal(a.get('ws-start-cards').hidden,false);a.context.CelesysWorkspace.setMode('trading');assert.equal(a.get('tw-panel').hidden,false);assert.equal(a.get('tw-disclosure').open,true);assert.equal(a.get('ws-account').hidden,true);assert.equal(a.get('ws-plan').hidden,true);a.context.CelesysWorkspace.setMode('options');assert.equal(a.get('tw-panel').hidden,true);assert.equal(a.get('ws-options').hidden,false);assert.equal(a.get('ws-plan').hidden,true);});
test('leaving trading stops scanner and opening account reveals the retained form',()=>{const a=setup();let stopped=0;a.get('tw-stop').click=()=>stopped++;a.context.CelesysWorkspace.setMode('trading');a.context.CelesysWorkspace.openAccount();assert.equal(a.get('ws-account').hidden,false);a.context.CelesysWorkspace.setMode('stock');assert.equal(stopped,1);});
test('tool library replaces competing panels and preserves all tools',()=>{const a=setup();a.context.CelesysWorkspace.showDirectory();assert.equal(a.get('ws-account').hidden,true);assert.equal(a.get('tw-panel').hidden,true);assert.equal(a.get('ws-directory').hidden,false);assert.equal(a.get('ws-tool-grid').children.length,50);});

test('report-dependent tool explains the next step when research is missing',()=>{const a=setup();a.context.CelesysWorkspace.openTool({group:'overview',tab:'quick',label:'Overview'});assert.equal(a.get('ws-notice').hidden,false);assert.match(a.get('ws-notice').textContent,/Generate a full report/);assert.equal(a.get('ws-account').hidden,false);});

test('Intraday Setups and Micro-Cap Hunter preserve their existing dream renderer requirement',()=>{
 for(const tab of ['intraday','mchunter']){
  for(const profile of [{role:'public',dream:true},{role:'trading',dream:true},{role:'full'},{role:'full',premium:true,dream:false}])assert.equal(core.canOpen('decide',tab,profile),false,tab+' must not advertise unavailable access');
  assert.equal(core.canOpen('decide',tab,{role:'full',dream:true}),true);
  assert.equal(core.canOpen('decide',tab,{role:'admin',dream:true,premium:true}),true);
 }
});
