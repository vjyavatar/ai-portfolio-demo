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
 await boot(page);await expect(page.locator('#ws-account')).toBeVisible();await expect(page.locator('#ws-account #email')).toBeVisible();await expect(page.locator('#ws-account #btn')).toBeVisible();await page.screenshot({path:'qa-output/home-desktop.png',fullPage:true});
 const width=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
 expect(width.document<=width.viewport+2,JSON.stringify(width)).toBe(true);
 await expect(page.locator('#ws-sidebar .ws-nav.active')).toHaveCount(1);
 await expect(page.locator('#ws-sidebar .ws-nav.active')).toContainText('Overview');
});
test('mobile homepage keeps the original analysis form usable',async({page})=>{
 await page.setViewportSize({width:390,height:844});await boot(page);await expect(page.locator('#ws-account #btn')).toBeVisible();
 await page.screenshot({path:'qa-output/home-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth,elements:[...document.querySelectorAll('body *')].filter(el=>{const r=el.getBoundingClientRect();const css=getComputedStyle(el);return r.height>0&&r.width>0&&css.visibility!=='hidden'&&css.display!=='none'&&r.right>innerWidth+2;}).slice(0,30).map(el=>({tag:el.tagName,id:el.id,class:typeof el.className==='string'?el.className:'',right:Math.round(el.getBoundingClientRect().right)}))}));
 expect(overflow.width<=overflow.viewport+2,JSON.stringify(overflow,null,2)).toBe(true);
});
test('technical charts remain visible and plotted after delayed recreation',async({page})=>{
 await boot(page);
 // First-visit onboarding is a real modal interaction, not an element to bypass.
 const skipTour=page.getByRole('button',{name:'Skip tour',exact:true});
 await expect(skipTour).toBeVisible({timeout:10000});
 await skipTour.click();
 await expect(page.locator('#onboardingOverlay')).toBeHidden();
 expect(await page.evaluate(()=>localStorage.getItem('celesys-onboarded'))).toBe('1');
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
  if(!menu.access.public){await expect(page.locator('#ws-account')).toBeVisible();await expect(page.locator('#ws-status')).toContainText('account access');}
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
 });
}
test('stock task within quick controls stays expanded',async({page})=>{
 await boot(page);
 await page.locator('#ws-sidebar [data-ws-mode="trading"]').click();
 await page.locator('#ws-quick-controls [data-ws-mode="stock"]').click();
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
