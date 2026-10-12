// Browser UI fixtures only. Never send a test email, order, or paid analysis request to production.
const {test,expect}=require('@playwright/test');
require('node:fs').mkdirSync('qa-output',{recursive:true});
const {execFileSync}=require('node:child_process');
const menus=JSON.parse(execFileSync('node',['qa/menu-inventory.cjs'],{encoding:'utf8'}));
const runtimeErrors=new WeakMap();
const fixtureRoles=new WeakMap();
test.afterEach(async({page})=>{expect(runtimeErrors.get(page)||[], 'Uncaught JavaScript errors, including startup and report rendering').toEqual([]);});
const stock={ticker:'AAPL',company_name:'QA fixture — not live data',currency:'USD',current_price:100,previous_close:99,market_cap:1000000000,pe_ratio:20,pb_ratio:3,dividend_yield:1,profit_margin:20,operating_margin:25,roe:18,beta:1.1,debt_to_equity:30,current_ratio:2,week52_low:80,week52_high:120,revenue:100000000,free_cash_flow:20000000,data_timestamp:'2026-01-02T16:00:00Z',data_source:'QA_FIXTURE',price_history:[95,96,98,99,100],revenue_growth:10,earnings_growth:12};
async function boot(page){
 const errors=[];runtimeErrors.set(page,errors);page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url());
  if(u.hostname==='127.0.0.1'){
   // Synthetic identity only: the original lifecycle still resolves tiers and applies gates.
   if(u.pathname==='/api/auth/verify'){
    const email=route.request().postDataJSON()?.email;
    const full=fixtureRoles.get(page)==='full'&&email==='qa@example.invalid';
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:true,premium:full,dreamAccess:full})});
   }
   if(u.pathname==='/api/validate-session')return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({authorized:u.searchParams.get('email')==='qa@example.invalid'})});
   if(u.pathname.startsWith('/api/'))return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:false,status:'UNAVAILABLE',message:'QA fixture: source deliberately unavailable',data:[],rows:[]})});
   return route.continue();
  }
  // Permit only static rendering dependencies; block analytics and remote data requests.
  if(['cdn.jsdelivr.net','cdnjs.cloudflare.com','fonts.googleapis.com','fonts.gstatic.com'].includes(u.hostname))return route.continue();
  return route.abort();
 });
 await page.goto('/');
 await page.waitForFunction(()=>window.CelesysWorkspace&&typeof window.displayReport==='function');
}
async function profile(page,role){
 fixtureRoles.set(page,role);
 await page.waitForFunction(()=>document.getElementById('email')?._celesysPatched);
 await page.evaluate(role=>{
  const email='qa@example.invalid';
  // A fixture account must survive displayReport -> checkTradesAccess and email blur.
  // Add only the reserved example.invalid identity; never borrow a real user's email.
  for(const tier of ['full_access','trades','picks','dream']){
   const members=window.CELESYS_TIERS[tier];
   const index=members.indexOf(email);if(index>=0)members.splice(index,1);
   if(role==='full')members.push(email);
  }
  const field=document.getElementById('email');field.value=email;field.dataset.real=email;
  window._verifiedEmail=email;window._isPremiumUser=role==='full';window._isDreamUser=role==='full';window._isTradingOnly=false;
  field.dispatchEvent(new Event('blur')); // Exercise the original resolver attached during startup.
  if(window._restrictTimer)clearInterval(window._restrictTimer);
 },role);
 await expect.poll(()=>page.evaluate(()=>window._userRole)).toBe(role);
}
test('desktop homepage exposes the original email, symbol and Analyze controls',async({page})=>{
 await boot(page);await expect(page.locator('#ws-account')).toBeVisible();await expect(page.locator('#ws-account #email')).toBeVisible();await expect(page.locator('#ws-account #btn')).toBeVisible();const tickerBox=await page.locator('#ticker').boundingBox();const actionBox=await page.locator('#btn').boundingBox();expect(tickerBox.width).toBeGreaterThan(240);expect(tickerBox.width).toBeGreaterThan(actionBox.width);await page.screenshot({path:'qa-output/home-desktop.png',fullPage:true});
 const width=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
 expect(width.document<=width.viewport+2,JSON.stringify(width)).toBe(true);
 await expect(page.locator('#ws-sidebar .ws-nav.active')).toHaveCount(1);
 await expect(page.locator('#ws-sidebar .ws-nav.active')).toContainText('Overview');
 await expect(page.locator('#ws-start-cards .ws-start-card')).toHaveCount(3);
 for(const card of await page.locator('#ws-start-cards .ws-start-card').all())await expect(card).toBeVisible();
 for(const id of ['ws-quick-controls','tw-panel','ws-options','ws-plan'])await expect(page.locator('#'+id)).toBeHidden();
});
test('mobile homepage keeps the original analysis form usable',async({page})=>{
 await page.setViewportSize({width:390,height:844});await boot(page);await expect(page.locator('#ws-account #btn')).toBeVisible();
 await expect(page.locator('#tw-panel')).toBeHidden();await expect(page.locator('#ws-quick-controls')).toBeHidden();
 for(const card of await page.locator('#ws-start-cards .ws-start-card').all())await expect(card).toBeVisible();
 await page.screenshot({path:'qa-output/home-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth,elements:[...document.querySelectorAll('body *')].filter(el=>{const r=el.getBoundingClientRect();const css=getComputedStyle(el);return r.height>0&&r.width>0&&css.visibility!=='hidden'&&css.display!=='none'&&r.right>innerWidth+2;}).slice(0,30).map(el=>({tag:el.tagName,id:el.id,class:typeof el.className==='string'?el.className:'',right:Math.round(el.getBoundingClientRect().right)}))}));
 expect(overflow.width<=overflow.viewport+2,JSON.stringify(overflow,null,2)).toBe(true);
});
for(const viewport of [{name:'desktop',width:1440,height:900},{name:'mobile',width:390,height:844}]){
 test('completed stock analysis stays on results after delayed callbacks — '+viewport.name,async({page})=>{
  await page.setViewportSize({width:viewport.width,height:viewport.height});await boot(page);await profile(page,'full');
  let permissionRefreshFinished=false;
  await page.route('**/api/auth/verify',async route=>{
   // Reproduce authorization arriving after the report is already on screen.
   await page.waitForFunction(()=>document.getElementById('report').classList.contains('show'));
   await page.waitForTimeout(250);
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:true,premium:true,dreamAccess:true})});
   permissionRefreshFinished=true;
  });
  await page.route('**/api/generate-report',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:true,live_data:stock,report:'QA fixture report',fund_holdings:{institutions:[],funds:[],summary:{}}})}));
  await page.locator('#ticker').fill('AAPL');
  if(viewport.name==='mobile'){
   await expect(page.locator('#autocomplete')).toBeVisible();
   const layout=await page.evaluate(()=>({suggestions:document.getElementById('autocomplete').getBoundingClientRect().bottom,analyze:document.getElementById('btn').getBoundingClientRect().top}));
   expect(layout.analyze,JSON.stringify(layout)).toBeGreaterThanOrEqual(layout.suggestions);
  }
  await page.locator('#btn').click();
  await expect(page.locator('#report')).toBeVisible();
  await expect(page.locator('#tickerTag')).toContainText('AAPL');
  // The regression was a 200 ms page-top timer scheduled after results appeared.
  // Let that timer and the 400 ms section animation complete before checking location.
  await page.waitForTimeout(1000);
  await expect.poll(()=>permissionRefreshFinished).toBe(true);
  const location=await page.evaluate(()=>({scroll:window.scrollY,reportTop:document.getElementById('report').getBoundingClientRect().top,toolbarBottom:document.querySelector('.ws-topbar').getBoundingClientRect().bottom}));
  expect(location.scroll,JSON.stringify(location)).toBeGreaterThan(0);
  expect(location.reportTop,JSON.stringify(location)).toBeLessThanOrEqual(location.toolbarBottom+100);
  expect(location.reportTop,JSON.stringify(location)).toBeGreaterThanOrEqual(location.toolbarBottom-2);
  await expect(page.locator('#report')).toBeVisible();
 });
}
test('technical charts remain visible and plotted after delayed recreation',async({page})=>{
 await boot(page);
 // Help is user-initiated; the unified workspace must not launch an obstructing tour.
 await expect(page.locator('#ws-help')).toBeHidden();
 await page.locator('#ws-help-toggle').click();
 await expect(page.locator('#ws-help')).toBeVisible();
 await page.locator('#ws-help-close').click();
 await expect(page.locator('#ws-help')).toBeHidden();
 await expect(page.locator('#onboardingOverlay')).toBeHidden();
 await profile(page,'full');await page.evaluate(stock=>window.displayReport({success:true,live_data:stock,report:'QA fixture report',fund_holdings:{institutions:[],funds:[],summary:{}}}),stock);
 await page.evaluate(()=>window.switchTabGroup('overview'));
 await expect(page.locator('#report')).toBeVisible();
 await expect(page.locator('#timestamp')).toContainText('Source timestamp');
 await expect(page.locator('#timestamp')).not.toContainText('LIVE');
 await expect(page.locator('#premiumQualityContent')).not.toContainText('Loading premium analysis');
 await expect(page.locator('#premiumQualityContent')).toContainText('QUALITY SCORE');
 const originalChartId=await page.evaluate(()=>window.Chart.getChart(document.getElementById('valChart'))?.id);
 await page.locator('#stTechnical').click();
 // Wait for the 300 ms recreation that previously hid all charts again.
 await expect.poll(()=>page.evaluate(originalId=>{const chart=window.Chart.getChart(document.getElementById('valChart'));return !!chart&&chart.id!==originalId;},originalChartId)).toBe(true);
 await expect(page.locator('#chartsCard')).toBeVisible();await expect(page.locator('#valChart')).toBeVisible();
 await expect.poll(()=>page.evaluate(()=>{
  const canvas=document.getElementById('valChart'),rect=canvas.getBoundingClientRect(),chart=window.Chart.getChart(canvas);
  const bars=chart?.getDatasetMeta(0)?.data||[];
  return rect.width>100&&rect.height>100&&chart.width>100&&chart.height>100&&bars.some(bar=>bar.height>0)&&chart.data.datasets[0].data.join(',')==='20,3,1';
 })).toBe(true);
 await page.screenshot({path:'qa-output/original-charts.png',fullPage:true});
 await page.locator('#stOverview').click();await expect(page.locator('#chartsCard')).toBeHidden();
});

for(const menu of menus){
 test('menu '+menu.group+'/'+menu.tab+' respects basic access',async({page})=>{
  await boot(page);await profile(page,'public');
  // This calls the same dispatcher as the actual directory button; renderer requests stay mocked.
  await page.evaluate(tab=>{const t=window.CelesysWorkspace.tools.find(t=>t.tab===tab);window.CelesysWorkspace.openTool(t);},menu.tab);
  if(!menu.access.public){await expect(page.locator('#ws-account')).toBeVisible();await expect(page.locator('#ws-status')).toContainText('account access');await expect(page.locator('#ws-notice')).toBeVisible();}
  else if(menu.tab==='quick'){await expect(page.locator('#ws-status')).toContainText('full report first');}
  else {await expect(page.locator('#ws-legacy-title')).toContainText(menu.label);await expect(page.locator('#report')).toBeVisible();}
 });
 test('menu '+menu.group+'/'+menu.tab+' opens for a full UI fixture',async({page})=>{
  await boot(page);await profile(page,'full');
  await page.evaluate(stock=>window.displayReport({success:true,live_data:stock,report:'QA fixture report',fund_holdings:{institutions:[],funds:[],summary:{}}}),stock);
  await expect.poll(()=>page.evaluate(()=>({role:window._userRole,premium:window._isPremiumUser,dream:window._isDreamUser}))).toEqual({role:'full',premium:true,dream:true});
  await page.evaluate(tab=>{const t=window.CelesysWorkspace.tools.find(t=>t.tab===tab);window.CelesysWorkspace.openTool(t);},menu.tab);
  if(menu.tab==='_today')await expect(page.locator('#ws-embedded')).toBeVisible();
  else if(menu.tab==='_active')await expect(page.locator('body')).toContainText(/Trading/);
  else {
   await expect(page.locator('#ws-legacy-title')).toContainText(menu.label);await expect(page.locator('#report')).toBeVisible();
   const shared=['dreamportfolio','multibagger','momentumradar','highprob','optionspulse','tradeticket','microcap','pms','mchunter','intraday','positioning','diamond','smartmoney','smv3','analyst'];
   const target=shared.includes(menu.tab)?'decision':menu.tab;
   if(menu.tab==='analyst')await expect(page.locator('#analystResultArea')).toBeVisible();
   // Inspect original content, not only the new workspace's heading.
   await expect.poll(()=>page.evaluate(target=>[...document.querySelectorAll('#report [data-tab="'+target+'"]')].some(e=>e.getBoundingClientRect().height>0&&e.textContent.trim().length>10),target)).toBe(true);
  }
 });
}
test('voice starts muted and can be stopped without requesting a microphone',async({page})=>{
 await boot(page);await expect(page.locator('#ws-voice-toggle')).toHaveAttribute('aria-pressed','false');await page.locator('#ws-voice-toggle').click();await expect(page.locator('#ws-voice-toggle')).toHaveAttribute('aria-pressed','true');await page.locator('#ws-voice-toggle').click();await expect(page.locator('#ws-voice-toggle')).toHaveAttribute('aria-pressed','false');
});

test('homepage keeps secondary quick controls collapsed',async({page})=>{
 await boot(page);
 await expect(page.locator('#ws-quick-controls')).toHaveJSProperty('open',false);
 await expect(page.locator('#ws-search')).toBeHidden();
 await expect(page.locator('#ws-account #btn')).toBeVisible();
 await expect(page.locator('#ws-quick-controls')).toBeHidden();
 await expect(page.locator('#tw-panel')).toBeHidden();
 await page.locator('#ws-sidebar [data-ws-directory]').click();
 await expect(page.locator('#ws-directory')).toBeVisible();
 await expect(page.locator('#ws-tool-grid .ws-tool')).toHaveCount(50);
 await page.screenshot({path:'qa-output/tool-library.png',fullPage:true});
 await expect(page.locator('#ws-sidebar .ws-nav.active')).toHaveCount(1);
 await expect(page.locator('#ws-sidebar .ws-nav.active')).toHaveAttribute('data-ws-directory','');
 for(const id of ['ws-account','ws-quick-controls','tw-panel','ws-options','ws-plan','ws-start-cards'])await expect(page.locator('#'+id)).toBeHidden();
});
for(const mode of ['trading','options']){
 test(mode+' sidebar opens its quick controls',async({page})=>{
  await boot(page);
  await page.locator('#ws-sidebar [data-ws-mode="'+mode+'"]').click();
  await expect(page.locator('#ws-sidebar .ws-nav.active')).toHaveCount(1);
  await expect(page.locator('#ws-sidebar .ws-nav.active')).toHaveAttribute('data-ws-mode',mode);
  await expect(page.locator('#ws-quick-controls')).toHaveJSProperty('open',true);
  await expect(page.locator('#ws-search')).toBeVisible();
  await expect(page.locator('#ws-run')).toContainText(mode==='options'?'Load option chain':'Review setup');
  await expect(page.locator('#ws-account')).toBeHidden();
  await expect(page.locator('#ws-start-cards')).toBeHidden();
  await expect(page.locator('#ws-plan')).toBeHidden();
  await page.screenshot({path:'qa-output/workspace-'+mode+'.png',fullPage:true});
  if(mode==='trading'){
   await expect(page.locator('#tw-panel')).toBeVisible();
   await expect(page.locator('#tw-disclosure')).toHaveJSProperty('open',true);
   await expect(page.locator('#ws-options')).toBeHidden();
   await page.locator('#ws-account-toggle').click();await expect(page.locator('#ws-account #email')).toBeVisible();
   await page.locator('#ws-sidebar [data-ws-mode="trading"]').click();await expect(page.locator('#ws-account')).toBeHidden();
   const scans=[];page.on('request',request=>{if(new URL(request.url()).pathname==='/api/watchlist/research')scans.push(request.url());});
   await page.locator('#tw-once').click();
   await expect(page.locator('#ws-account #email')).toBeVisible();
   await expect(page.locator('#tw-status')).toContainText('authorized email');
   expect(scans).toEqual([]);
  }else{
   await expect(page.locator('#tw-panel')).toBeHidden();
   await expect(page.locator('#ws-options')).toBeVisible();
   await page.locator('#ws-manual-plan').click();await expect(page.locator('#ws-plan')).toBeVisible();
  }
 });
}
test('stock task within quick controls stays expanded',async({page})=>{
 await boot(page);
 await page.locator('#ws-sidebar [data-ws-mode="stock"]').click();
 await expect(page.locator('#ws-account #btn')).toBeVisible();
 await expect(page.locator('#tw-panel')).toBeHidden();
 await page.locator('#ws-quick-controls > summary').click();
 await expect(page.locator('#ws-quick-controls')).toHaveJSProperty('open',true);
 await expect(page.locator('#ws-search')).toBeVisible();
 await expect(page.locator('#ws-run')).toContainText('Quick stock brief');
});
test('window focus loss does not blur the rendered report',async({page})=>{
 await boot(page);await profile(page,'full');
 await page.evaluate(stock=>window.displayReport({success:true,live_data:stock,report:'QA fixture report',fund_holdings:{institutions:[],funds:[],summary:{}}}),stock);
 await expect(page.locator('#report')).toBeVisible();
 await page.evaluate(async()=>{window.dispatchEvent(new Event('blur'));await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
 const filters=await page.evaluate(()=>[...document.querySelectorAll('#report, #report .sc, #report .dc, #report .prem-section')].filter(el=>el.getBoundingClientRect().height>0&&getComputedStyle(el).display!=='none').map(el=>getComputedStyle(el).filter));
 expect(filters.length).toBeGreaterThan(0);
 expect(filters.filter(filter=>filter.includes('blur('))).toEqual([]);
 await expect(page.locator('#report')).toBeVisible();
});
test('stock sidebar restores the loaded report without a fresh analysis request',async({page})=>{
 await boot(page);await profile(page,'full');
 await page.evaluate(stock=>window.displayReport({success:true,live_data:stock,report:'QA fixture report',fund_holdings:{institutions:[],funds:[],summary:{}}}),stock);
 await expect(page.locator('#report')).toBeVisible();
 const reportRequests=[];page.on('request',request=>{if(new URL(request.url()).pathname==='/api/generate-report')reportRequests.push(request.url());});
 await page.locator('#ws-sidebar [data-ws-mode="trading"]').click();
 await expect(page.locator('#report')).toBeHidden();
 await page.locator('#ws-sidebar [data-ws-mode="stock"]').click();
 await expect(page.locator('#report')).toBeVisible();
 await expect(page.locator('#ws-quick-controls')).toHaveJSProperty('open',false);
 expect(await page.evaluate(()=>window._stockData?.ticker)).toBe(stock.ticker);
 expect(reportRequests).toEqual([]);
});

// Closed-bar fixtures for the trading brief's protected market panel. These are
// deterministic synthetic test inputs, never represented as live provider data.
async function marketFixture(page,symbol='SPY',price=100,stale=false){
 const now=await page.evaluate(()=>Math.floor(Date.now()/1000));
 const close=now-10-(stale?600:0);
 return {symbol,region:'US',currency:'USD',source:'QA deterministic market fixture',price,
  quote_time:close+1,bar_close_time:close,session_start:now-10800,session_end:now+10800,
  market_status:'OPEN',verdict:'LONG_RESEARCH',bias:'BULLISH',reason:'Fixture closed-bar breakout; not a real trade.',
  fetched_at:now,stages:[{status:'pass'}],provider_status:{code:'RESPONSE_RECEIVED'},
  bars:Array.from({length:24},(_,i)=>({time:close-(24-i)*300,open:price-1+i*.02,high:price-.7+i*.02,low:price-1.2+i*.02,close:price-.9+i*.02,volume:1000+i}))};
}
async function mockBrief(page){
 await page.route('**/api/research-brief?**',async route=>{
  const query=new URL(route.request().url()).searchParams;
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({symbol:query.get('symbol'),region:query.get('region'),engine:'QA FIXTURE',generated_at:Date.now()/1000,assessment:'Review fixture evidence',evidence:[{label:'fixture metric',value:1,source:'QA fixture'}],counterargument:'Synthetic test input only.',missing_data:['Real provider feed'],next_check:'Verify actual provider data.'})});
 });
}
async function openTradingBrief(page,symbol='SPY'){
 if(page.viewportSize().width<760)await page.locator('#ws-menu-toggle').click();
 await page.locator('#ws-sidebar [data-ws-mode="trading"]').click();
 await page.locator('#ws-symbol').fill(symbol);
 await page.locator('#ws-run').click();
 await expect(page.locator('#ws-result-title')).toContainText(symbol);
}
for(const width of [1440,390]){
 test('trading brief displays a sourced closed-bar chart at '+width+'px',async({page})=>{
  await page.setViewportSize({width,height:1000});await boot(page);await profile(page,'full');await mockBrief(page);
  let calls=0;await page.route('**/api/watchlist/research?**',async route=>{calls++;await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(await marketFixture(page))});});
  await openTradingBrief(page);
  await expect(page.locator('#bm-panel')).toBeVisible();await expect(page.locator('#bm-price')).toContainText('100.00');
  await expect(page.locator('#bm-freshness')).toContainText('Recent source quote');
  await expect(page.locator('#bm-source-time')).not.toHaveText('');
  await expect(page.locator('#bm-chart svg')).toBeVisible();
  const points=(await page.locator('#bm-chart svg polyline').getAttribute('points')).trim().split(/\s+/).map(pair=>pair.split(',').map(Number));
  expect(points).toHaveLength(24);expect(points.every(pair=>pair.length===2&&pair.every(Number.isFinite))).toBe(true);
  expect(points.at(-1)[1]).toBeLessThan(points[0][1]); // Supplied closes rise; drawn values must match their direction.
  const rect=await page.locator('#bm-chart svg').boundingBox();expect(rect.width).toBeGreaterThan(200);expect(rect.height).toBeGreaterThan(70);
  await expect(page.locator('#ws-brief-grid .ws-brief-card')).toHaveCount(5);
  expect(calls).toBe(1);await expect(page.locator('#bm-voice')).not.toBeChecked();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await page.screenshot({path:'qa-output/brief-market-'+width+'.png',fullPage:true});
 });
}
test('public trading brief never fetches the protected market panel',async({page})=>{
 await boot(page);await profile(page,'public');await mockBrief(page);
 const calls=[];page.on('request',request=>{if(new URL(request.url()).pathname==='/api/watchlist/research')calls.push(request.url());});
 await openTradingBrief(page);await expect(page.locator('#bm-panel')).toBeVisible();
 await expect(page.locator('#bm-status')).toContainText(/access|account|authorized/i);
 await expect(page.locator('#bm-chart svg')).toHaveCount(0);expect(calls).toEqual([]);
});
test('trading brief refresh updates source evidence and suppresses stale or failed candidates',async({page})=>{
 await page.clock.install({time:new Date('2026-10-12T16:00:00Z')});await boot(page);await profile(page,'full');await mockBrief(page);
 let calls=0;await page.route('**/api/watchlist/research?**',async route=>{
  calls++;
  if(calls>=4)return route.fulfill({status:503,headers:{'Retry-After':'120'},contentType:'application/json',body:JSON.stringify({detail:'QA unavailable'})});
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(await marketFixture(page,'SPY',99+calls,calls===3))});
 });
 await openTradingBrief(page);await expect(page.locator('#bm-price')).toContainText('100.00');
 const firstStamp=await page.locator('#bm-source-time').textContent();
 await page.clock.fastForward(61000);await expect(page.locator('#bm-price')).toContainText('101.00');
 await expect(page.locator('#bm-source-time')).not.toHaveText(firstStamp);
 await page.clock.fastForward(61000);await expect(page.locator('#bm-freshness')).toContainText('Stale source quote');
 await expect(page.locator('#bm-readiness')).not.toContainText('Bullish research candidate');
 await page.clock.fastForward(61000);await expect(page.locator('#bm-status')).toContainText(/unavailable|failed|retry/i);
 await expect(page.locator('#bm-price')).toHaveText('Unavailable');await expect(page.locator('#bm-chart svg')).toHaveCount(0);
 await expect(page.locator('#bm-readiness')).not.toContainText('Bullish research candidate');
 expect(calls).toBe(4);
 await page.locator('#bm-refresh').click();await page.clock.fastForward(61000);expect(calls).toBe(4); // Manual refresh cannot bypass provider cooldown.
 await page.locator('#bm-pause').click();await page.clock.fastForward(121000);expect(calls).toBe(4);
 await expect(page.locator('#bm-pause')).toContainText('Resume');
});
test('changed brief symbol rejects an old response and navigation stops quote polling',async({page})=>{
 await page.clock.install({time:new Date('2026-10-12T16:00:00Z')});await boot(page);await profile(page,'full');await mockBrief(page);
 let release,calls=0;
 await page.route('**/api/watchlist/research?**',async route=>{
  calls++;const symbol=new URL(route.request().url()).searchParams.get('symbol');
  const body=JSON.stringify(await marketFixture(page,symbol,symbol==='MSFT'?202:100));
  if(symbol==='SPY')await new Promise(resolve=>{release=resolve;});
  await route.fulfill({status:200,contentType:'application/json',body}).catch(error=>{if(symbol!=='SPY')throw error;}); // SPY is intentionally aborted by navigation.
 });
 await openTradingBrief(page);await expect.poll(()=>typeof release).toBe('function');
 await page.locator('#ws-symbol').fill('MSFT');await page.locator('#ws-run').click();
 await expect(page.locator('#bm-title')).toContainText('MSFT');await expect(page.locator('#bm-price')).toContainText('202.00');
 release();await page.clock.fastForward(1000);
 await expect(page.locator('#bm-title')).toContainText('MSFT');await expect(page.locator('#bm-price')).toContainText('202.00');
 await page.locator('#ws-sidebar [data-ws-mode="options"]').click();await expect(page.locator('#bm-panel')).toBeHidden();
 const stopped=calls;await page.clock.fastForward(121000);expect(calls).toBe(stopped);
});

// Audio is replaced before application startup: these verify opt-in and event
// scheduling without producing sound or claiming device-speaker validation.
async function stubMarketAudio(page){
 await page.addInitScript(()=>{
  window.__qaAudio={created:0,resumes:0,starts:0};
  window.AudioContext=class{
   constructor(){window.__qaAudio.created++;this.state='suspended';this.currentTime=0;this.destination={};}
   async resume(){window.__qaAudio.resumes++;this.state='running';}
   createOscillator(){return {frequency:{setValueAtTime(){}},connect(){},disconnect(){},start(){window.__qaAudio.starts++;},stop(){this.onended?.();}};}
   createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){},disconnect(){}};}
  };
 });
}
test('market sound requires explicit enable and test clicks, and mute suppresses later chimes',async({page})=>{
 await stubMarketAudio(page);await boot(page);await profile(page,'full');await mockBrief(page);
 let bearish=false;
 await page.route('**/api/watchlist/research?**',async route=>{
  const data=await marketFixture(page,'SPY',bearish?99:100);
  data.verdict=bearish?'BEARISH_RESEARCH':'LONG_RESEARCH';data.bias=bearish?'BEARISH':'BULLISH';
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
 });
 await openTradingBrief(page);await expect(page.locator('#bm-price')).toContainText('100.00');
 await expect(page.locator('#bm-notification-list li')).toHaveCount(0);
 expect(await page.evaluate(()=>window.__qaAudio)).toEqual({created:0,resumes:0,starts:0});
 await page.locator('#bm-sound-test').click();await expect(page.locator('#bm-sound-status')).toContainText('Enable sound first');
 expect(await page.evaluate(()=>window.__qaAudio.starts)).toBe(0);
 await page.locator('#bm-sound').click();await expect(page.locator('#bm-sound')).toHaveAttribute('aria-pressed','true');
 expect(await page.evaluate(()=>window.__qaAudio)).toEqual({created:1,resumes:1,starts:0});
 await page.locator('#bm-sound-test').click();await expect(page.locator('#bm-sound-status')).toContainText('Test sound played');
 expect(await page.evaluate(()=>window.__qaAudio.starts)).toBe(1);
 bearish=true;await page.locator('#bm-refresh').click();await expect(page.locator('#bm-price')).toContainText('99.00');
 await expect(page.locator('#bm-notification-list li')).toHaveCount(1);
 await expect(page.locator('#bm-notification-list li')).toContainText('SPY · US');
 await expect.poll(()=>page.evaluate(()=>window.__qaAudio.starts)).toBe(2);
 await page.locator('#bm-sound').click();await expect(page.locator('#bm-sound')).toHaveAttribute('aria-pressed','false');
 bearish=false;await page.locator('#bm-refresh').click();await expect(page.locator('#bm-price')).toContainText('100.00');
 await expect(page.locator('#bm-notification-list li')).toHaveCount(2);
 await page.locator('#bm-sound-test').click();await expect(page.locator('#bm-sound-status')).toContainText('Enable sound first');
 expect(await page.evaluate(()=>window.__qaAudio.starts)).toBe(2);
});
test('market notifications identify the symbol and deduplicate repeated outage and recovery responses',async({page})=>{
 await stubMarketAudio(page);await boot(page);await profile(page,'full');await mockBrief(page);
 let unavailable=false,calls=0;
 await page.route('**/api/watchlist/research?**',async route=>{
  calls++;
  if(unavailable)return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'QA provider outage'})});
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(await marketFixture(page,'MSFT',202))});
 });
 await openTradingBrief(page,'MSFT');await expect(page.locator('#bm-price')).toContainText('202.00');
 await expect(page.locator('#bm-notification-list li')).toHaveCount(0);
 unavailable=true;await page.locator('#bm-refresh').click();await expect(page.locator('#bm-price')).toHaveText('Unavailable');
 await expect(page.locator('#bm-notification-list li')).toHaveCount(1);
 await expect(page.locator('#bm-notification-list li')).toContainText('MSFT · US');
 await expect(page.locator('#bm-notification-list li')).toContainText('Market provider unavailable');
 const firstOutage=await page.locator('#bm-notification-list').textContent();
 await page.locator('#bm-refresh').click();await expect.poll(()=>calls).toBe(3);await expect(page.locator('#bm-refresh')).toBeEnabled();
 await expect(page.locator('#bm-notification-list')).toHaveText(firstOutage);
 unavailable=false;await page.locator('#bm-refresh').click();await expect(page.locator('#bm-price')).toContainText('202.00');
 await expect(page.locator('#bm-notification-list li')).toHaveCount(2);
 await expect(page.locator('#bm-notification-list li').first()).toContainText('MSFT · US');
 await expect(page.locator('#bm-notification-list li').first()).toContainText('Market provider response recovered');
 const recovered=await page.locator('#bm-notification-list').textContent();
 await page.locator('#bm-refresh').click();await expect.poll(()=>calls).toBe(5);await expect(page.locator('#bm-refresh')).toBeEnabled();
 await expect(page.locator('#bm-notification-list')).toHaveText(recovered);
 expect(await page.evaluate(()=>window.__qaAudio)).toEqual({created:0,resumes:0,starts:0});
 await page.locator('#bm-notifications').screenshot({path:'qa-output/brief-market-notifications.png'});
});

test('original Decide Trader direction alerts are keyed by market and symbol and sound starts off',async({page})=>{
 await stubMarketAudio(page);await boot(page);await profile(page,'full');
 expect(await page.evaluate(()=>window._soundEnabled)).toBe(false);
 const notices=page.locator('[role="status"]').filter({hasText:'research direction:'});
 await page.evaluate(()=>{
  window._deMode='trader';window._deRegion='US';window._lastDESym='QATEST1';
  window._checkDirectionChange('QATEST1','BULLISH');
  window._checkDirectionChange('QATEST1','BULLISH');
  window._checkDirectionChange('QATEST2','BEARISH');
  window._deRegion='IN';window._checkDirectionChange('QATEST1','BEARISH');
 });
 await expect(notices).toHaveCount(0);
 await page.evaluate(()=>{
  window._deRegion='US';window._checkDirectionChange('QATEST1','BEARISH');
  window._checkDirectionChange('QATEST1','BEARISH');
 });
 await expect(notices).toHaveCount(1);
 await expect(notices).toContainText('QATEST1 · US');
 await expect(notices).toContainText('BULLISH → BEARISH');
 expect(await page.evaluate(()=>window.__qaAudio.starts)).toBe(0);
 await page.evaluate(()=>{window._deMode='investor';window._checkDirectionChange('QATEST1','BULLISH');});
 await expect(notices).toHaveCount(1);
});
test('original Decide Trader rejects obsolete responses and mismatched source symbols',async({page})=>{
 await boot(page);await profile(page,'full');
 let releaseOld;
 await page.route('**/api/decision-engine?**',async route=>{
  const symbol=new URL(route.request().url()).searchParams.get('symbol');
  if(symbol==='SPY'){
   await new Promise(resolve=>{releaseOld=resolve;});
   return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:false,error:'QA obsolete SPY response'})}).catch(()=>{}); // The older request is deliberately aborted.
  }
  const data=symbol==='MSFT'?{success:false,error:'QA current MSFT response'}:{success:true,symbol:'WRONG',region:'US'};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.evaluate(()=>{window._deMode='trader';window._deRegion='US';window.loadDE('SPY');});
 await expect.poll(()=>typeof releaseOld).toBe('function');
 await page.evaluate(()=>window.loadDE('MSFT'));
 await expect(page.locator('#deResult')).toHaveText('QA current MSFT response');
 releaseOld();await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 await expect(page.locator('#deResult')).toHaveText('QA current MSFT response');
 expect(await page.evaluate(()=>window._lastDESym)).toBe('MSFT');
 await page.evaluate(()=>window.loadDE('AAPL'));
 await expect(page.locator('#deResult')).toContainText('Source symbol or market mismatch');
 await expect(page.locator('#deResult')).not.toContainText('QA obsolete SPY response');
});
test('original Active Trading discards an unmounted scan and stops polling after exit',async({page})=>{
 await page.clock.install({time:new Date('2026-10-12T16:00:00Z')});await boot(page);await profile(page,'full');
 await page.waitForFunction(()=>typeof window.mountActiveTrading==='function');
 let releaseOld,calls=0;
 await page.route('**/api/bottom-nav-scan?**',async route=>{
  const order=++calls,region=new URL(route.request().url()).searchParams.get('region');
  if(order===1)await new Promise(resolve=>{releaseOld=resolve;});
  const data={success:true,region,tickers:[],ts:Date.now()/1000,_breaker_tripped:order===1,_breaker_provider:order===1?'nse_chain':null};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)}).catch(error=>{if(order!==1)throw error;});
 });
 await page.evaluate(()=>window.mountActiveTrading());await expect(page.locator('#activeTradingOverlay')).toBeVisible();
 await expect.poll(()=>typeof releaseOld).toBe('function');
 await page.evaluate(()=>window.unmountActiveTrading());await expect(page.locator('#activeTradingOverlay')).toHaveCount(0);
 await page.evaluate(()=>window.mountActiveTrading());await expect.poll(()=>calls).toBe(2);
 await expect(page.locator('#activeTradingOverlay')).toBeVisible();releaseOld();await page.clock.fastForward(1000);
 await expect(page.locator('#activeTradingMount')).not.toContainText('Circuit breaker auto-tripped');
 expect(await page.evaluate(()=>window._atDebug().mounted_flag)).toBe(true);
 await page.evaluate(()=>window.unmountActiveTrading());await expect(page.locator('#activeTradingOverlay')).toHaveCount(0);
 const stopped=calls;await page.clock.fastForward(601000);expect(calls).toBe(stopped);
 expect(await page.evaluate(()=>window._atDebug().mounted_flag)).toBe(false);
 expect(await page.evaluate(()=>document.body.style.overflow)).not.toBe('hidden');
});

async function openOriginalDecideTicket(page,symbol='SPY',region='US'){
 // Exercise the original dispatcher and loadDE integration, not a direct module mount.
 // The legacy report is deliberately unavailable; the separately verified ticket must still work.
 await page.route('**/api/decision-engine?**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:false,error:'QA legacy report unavailable; independent contract evidence follows.'})}));
 await page.evaluate(({symbol,region})=>{
  window.CelesysWorkspace.openTool(window.CelesysWorkspace.tools.find(t=>t.group==='decide'&&t.tab==='decision'));
  window._deMode='trader';window._deRegion=region;window.loadDE(symbol);
 },{symbol,region});
 await expect(page.locator('#de-options-ticket')).toBeVisible();
 await expect(page.locator('#deResult')).toContainText('QA legacy report unavailable');
}
function decideOptionFixture(now,side){
 return {status:'BUY_'+side+'_CANDIDATE',direction:side,source:'QA source-backed contract fixture — not live data',reason:'Conditional review candidate from mocked verified source evidence.',execution_enabled:false,candidate:{
  contract:'SPY261015'+side[0]+'00600000',expiry:'2026-10-15',strike:600,bid:2,ask:2.1,bid_time:now-2,ask_time:now-1,greeks_source_time:now-100,expires_at:now+200,contract_multiplier:100,
  entry:{kind:'QUOTED_BID_ASK_RANGE',low:2,high:2.1,limit_cap:2.1,currency:'USD',unit:'PREMIUM_PER_SHARE',fill_guaranteed:false},
  premium_risk:{maximum_loss_per_contract:210,currency:'USD',scope:'LONG_OPTION_PREMIUM_ONLY',excludes_fees:true},
  underlying_invalidation:side==='CALL'?598:602,underlying_target:side==='CALL'?605:595,
  confidence:{status:'UNCALIBRATED',success_probability:null,basis:['Fresh source timestamps','Liquidity filters passed']},
  ranking:{method:'Lowest relative spread, then delta proximity.',note:'Not a profit forecast.'},
  exit_policy:{kind:'ILLUSTRATIVE_POLICY_NOT_FORECAST',basis:'ASK_CAP_NOT_ACTUAL_FILL',stop_premium:1.58,target_premium:3.15}
 }};
}
for(const side of ['CALL','PUT'])test('original Decide Trader mounts a visible '+side+' contract ticket with entry, exits and uncalibrated confidence',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.clock.install({time:new Date('2026-10-12T16:00:00Z')});await boot(page);await profile(page,'full');
 await page.waitForFunction(()=>typeof window.mountDecideOptions==='function');
 let calls=0;
 await page.route('**/api/trading-desk/options?**',async route=>{
  calls++;const url=new URL(route.request().url());expect(url.searchParams.get('symbol')).toBe('SPY');expect(url.searchParams.get('region')).toBe('US');
  expect(route.request().headers()['x-celesys-email']).toBeUndefined();
  const now=await page.evaluate(()=>Date.now()/1000);
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(decideOptionFixture(now,side))});
 });
 await openOriginalDecideTicket(page);await page.clock.fastForward(1000);expect(calls).toBe(0);
 await expect(page.locator('#de-options-voice')).not.toBeChecked();
 await page.locator('#de-options-scan').click();await expect(page.locator('#de-options-ticket')).toHaveAttribute('data-state','candidate');expect(calls).toBe(1);
 const fields={type:'BUY '+side,strike:'$600.00',expiry:'2026-10-15',entry:'$2.00 – $2.10 · Limit cap $2.10',stop:'$1.58 · illustrative policy, not guaranteed',target:'$3.15 · illustrative policy, not a forecast',invalidation:side==='CALL'?'$598.00':'$602.00',underlyingTarget:side==='CALL'?'$605.00':'$595.00',loss:'$210.00 + costs (100 units)'};
 for(const [key,value]of Object.entries(fields)){await expect(page.locator('#de-options-'+key)).toBeVisible();await expect(page.locator('#de-options-'+key)).toContainText(value);}
 await expect(page.locator('#de-options-entry')).toContainText('fill not guaranteed');
 await expect(page.locator('#de-options-confidence')).toContainText('uncalibrated; no success probability');
 await expect(page.locator('#de-options-source')).toContainText('SPY261015'+side[0]+'00600000');await expect(page.locator('#de-options-source')).toContainText('Evidence expires');
 await expect(page.locator('#de-options-ranking')).toContainText('not a market-wide best trade');
 await page.screenshot({path:'qa-output/original-decide-'+side.toLowerCase()+'-mobile.png',fullPage:true});
 const width=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));expect(width.document<=width.viewport+2,JSON.stringify(width)).toBe(true);
 await page.clock.fastForward(202000);await expect(page.locator('#de-options-ticket')).toHaveAttribute('data-state','wait');
 await expect(page.locator('#de-options-entry')).toHaveText('Unavailable');expect(calls).toBe(1);
});
test('original Decide Trader treats server 401 as WAIT without quotes or automatic option requests',async({page})=>{
 await page.clock.install({time:new Date('2026-10-12T16:00:00Z')});await boot(page);await profile(page,'full');
 await page.waitForFunction(()=>typeof window.mountDecideOptions==='function');
 // A full-looking UI profile is intentionally insufficient when the server rejects its session.
 let calls=0;await page.route('**/api/trading-desk/options?**',route=>{calls++;return route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Verified authorized sign-in required.'})});});
 await openOriginalDecideTicket(page);await page.clock.fastForward(61000);expect(calls).toBe(0);
 await page.locator('#de-options-scan').click();await expect(page.locator('#de-options-reason')).toContainText('Verified sign-in with full trading access is required');
 await expect(page.locator('#de-options-ticket')).toHaveAttribute('data-state','wait');await expect(page.locator('#de-options-verdict')).toContainText('WAIT');
 for(const key of ['type','strike','expiry','entry','stop','target','invalidation','underlyingTarget','loss'])await expect(page.locator('#de-options-'+key)).toHaveText('Unavailable');
 await expect(page.locator('#de-options-source')).toHaveText('No current contract quote verified.');
 await page.clock.fastForward(121000);expect(calls).toBe(1);
});

function privateChainFixture(symbol,region,expiry='2026-10-15'){
 const india=region==='IN';
 return {symbol,region,currency:india?'INR':'USD',source:india?'Angel One SmartAPI':'Tradier',status:'SNAPSHOT',expiry,expiries:['2026-10-15','2026-10-22'],fetched_at:1791817200,freshness:'UNVERIFIED_OR_STALE',execution_enabled:false,message:'QA provider snapshot, not live market data.',rows:[{strike:india?25000:600,call:{bid:2,ask:2.1,oi:0,volume:100,bid_time:null,ask_time:null},put:{bid:3,ask:3.1,oi:null,volume:null,bid_time:null,ask_time:null}}]};
}
for(const market of [{symbol:'NIFTY',region:'IN',source:'Angel One SmartAPI',width:390},{symbol:'SPY',region:'US',source:'Tradier',width:1440}])test('original Decide views '+market.symbol+' private chain with selectable expiry and honest quote timing',async({page})=>{
 await page.setViewportSize({width:market.width,height:900});await page.clock.install({time:new Date('2026-10-12T16:00:00Z')});await boot(page);await profile(page,'full');
 await page.waitForFunction(()=>typeof window.mountDecideOptions==='function');const requested=[];
 await page.route('**/api/private-options/chain?**',route=>{
  const params=new URL(route.request().url()).searchParams;requested.push(params.get('expiry'));expect(params.get('symbol')).toBe(market.symbol);expect(params.get('region')).toBe(market.region);expect(route.request().headers()['x-celesys-email']).toBeUndefined();
  return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(privateChainFixture(market.symbol,market.region,params.get('expiry')||undefined))});
 });
 await openOriginalDecideTicket(page,market.symbol,market.region);await page.clock.fastForward(1000);expect(requested).toEqual([]);
 await page.locator('#de-chain-load').click();await expect(page.locator('#de-chain-table')).toBeVisible();
 await expect(page.locator('#de-chain-source')).toContainText(market.source);await expect(page.locator('#de-chain-source')).toContainText('(not quote time)');
 await expect(page.locator('#de-chain-status')).toContainText('quote timing unverified or stale');await expect(page.locator('#de-chain-status')).not.toContainText('Recent source quotes');
 const row=page.locator('#de-chain-table tbody tr');await expect(row).toHaveCount(1);await expect(row).toContainText('Bid unknown / Ask unknown');await expect(row).toContainText('0 / 100');await expect(row).toContainText('— / —');
 await expect(row).toContainText(market.region==='IN'?'₹2.00':'$2.00');await expect(row).toContainText(market.region==='IN'?'₹25,000.00':'$600.00');
 await expect(page.locator('#de-chain-expiry')).toHaveValue('2026-10-15');await page.locator('#de-chain-expiry').selectOption('2026-10-22');await expect(page.locator('#de-chain-source')).toContainText('2026-10-22');expect(requested).toEqual(['','2026-10-22']);
 // Browsing a chain never manufactures a call/put recommendation.
 await expect(page.locator('#de-options-ticket')).toHaveAttribute('data-state','wait');await expect(page.locator('#de-options-entry')).toHaveText('Unavailable');
 await page.screenshot({path:'qa-output/original-chain-'+market.region.toLowerCase()+'.png',fullPage:true});
 const width=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));expect(width.document<=width.viewport+2,JSON.stringify(width)).toBe(true);
 await page.clock.fastForward(61000);expect(requested).toHaveLength(2);
});
test('original Decide private chain rejects server 401 and ignores late responses after context changes',async({page})=>{
 await page.clock.install({time:new Date('2026-10-12T16:00:00Z')});await boot(page);await profile(page,'full');await page.waitForFunction(()=>typeof window.mountDecideOptions==='function');
 let calls=0,releaseOld;
 await page.route('**/api/private-options/chain?**',async route=>{
  const params=new URL(route.request().url()).searchParams;calls++;
  if(params.get('symbol')==='NIFTY'){
   await new Promise(resolve=>{releaseOld=resolve;});
   return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(privateChainFixture('NIFTY','IN'))}).catch(()=>{}); // Deliberately aborted old context.
  }
  return route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Verified authorized sign-in required.'})});
 });
 await openOriginalDecideTicket(page,'NIFTY','IN');expect(calls).toBe(0);await page.locator('#de-chain-load').click();await expect.poll(()=>typeof releaseOld).toBe('function');
 await page.evaluate(()=>{window._deRegion='US';window.loadDE('SPY');});await page.locator('#de-chain-load').click();await expect(page.locator('#de-chain-status')).toContainText('Verified sign-in with full access is required');
 releaseOld();await page.clock.fastForward(1000);await expect(page.locator('#de-chain-table')).toBeHidden();await expect(page.locator('#de-chain-source')).toHaveText('');await expect(page.locator('#de-chain-status')).toContainText('Verified sign-in with full access is required');
 await page.clock.fastForward(61000);expect(calls).toBe(2);
});
