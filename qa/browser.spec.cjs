// Browser UI fixtures only. Never send a test email, order, or paid analysis request to production.
const {test,expect}=require('@playwright/test');
require('node:fs').mkdirSync('qa-output',{recursive:true});
const {execFileSync}=require('node:child_process');
const menus=JSON.parse(execFileSync('node',['qa/menu-inventory.cjs'],{encoding:'utf8'}));
const stock={ticker:'AAPL',company_name:'QA fixture — not live data',currency:'USD',current_price:100,previous_close:99,market_cap:1000000000,pe_ratio:20,pb_ratio:3,dividend_yield:1,profit_margin:20,operating_margin:25,roe:18,beta:1.1,debt_to_equity:30,current_ratio:2,week52_low:80,week52_high:120,revenue:100000000,free_cash_flow:20000000,data_timestamp:'2026-01-02T16:00:00Z',data_source:'QA_FIXTURE',price_history:[95,96,98,99,100],revenue_growth:10,earnings_growth:12};
async function boot(page){
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url());
  if(u.hostname==='127.0.0.1'){
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
 await page.evaluate(role=>{window._userRole=role;window._isPremiumUser=role==='full';window._isDreamUser=role==='full';window._isTradingOnly=false;window._verifiedEmail='qa@example.invalid';if(window._restrictTimer)clearInterval(window._restrictTimer);},role);
}
test('desktop homepage exposes the original email, symbol and Analyze controls',async({page})=>{
 await boot(page);await expect(page.locator('#ws-account')).toBeVisible();await expect(page.locator('#ws-account #email')).toBeVisible();await expect(page.locator('#ws-account #btn')).toBeVisible();await page.screenshot({path:'qa-output/home-desktop.png',fullPage:true});
});
test('mobile homepage keeps the original analysis form usable',async({page})=>{
 await page.setViewportSize({width:390,height:844});await boot(page);await expect(page.locator('#ws-account #btn')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);await page.screenshot({path:'qa-output/home-mobile.png',fullPage:true});
});
test('original report renders real Chart.js instances from a deterministic fixture',async({page})=>{
 await boot(page);await profile(page,'full');await page.evaluate(stock=>window.displayReport({success:true,live_data:stock,report:'QA fixture report',fund_holdings:{institutions:[],funds:[],summary:{}}}),stock);
 await page.evaluate(()=>window.switchTabGroup('overview'));
 await expect(page.locator('#report')).toBeVisible();
 await expect.poll(()=>page.evaluate(()=>Object.keys(window.Chart?.instances||{}).length)).toBeGreaterThan(0);
 const plotted=await page.evaluate(()=>Object.values(window.Chart.instances).some(c=>c.data.datasets.some(d=>d.data.length>0)));
 expect(plotted).toBe(true);await page.screenshot({path:'qa-output/original-charts.png',fullPage:true});
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
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.evaluate(tab=>{const t=window.CelesysWorkspace.tools.find(t=>t.tab===tab);window.CelesysWorkspace.openTool(t);},menu.tab);
  if(menu.tab==='_today')await expect(page.locator('#ws-embedded')).toBeVisible();
  else if(menu.tab==='_active')await expect(page.locator('body')).toContainText(/Trading/);
  else {await expect(page.locator('#ws-legacy-title')).toContainText(menu.label);await expect(page.locator('#report')).toBeVisible();}
  expect(errors).toEqual([]);
 });
}
test('voice starts muted and can be stopped without requesting a microphone',async({page})=>{
 await boot(page);await expect(page.locator('#ws-voice-toggle')).toHaveAttribute('aria-pressed','false');await page.locator('#ws-voice-toggle').click();await expect(page.locator('#ws-voice-toggle')).toHaveAttribute('aria-pressed','true');await page.locator('#ws-voice-toggle').click();await expect(page.locator('#ws-voice-toggle')).toHaveAttribute('aria-pressed','false');
});
