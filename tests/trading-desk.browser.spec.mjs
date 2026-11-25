import {test,expect} from "@playwright/test";

test("decision, five-minute refresh, instrument isolation and market closure", async ({page}) => {
  let now=Date.parse("2026-11-25T05:30:00Z")/1000;
  await page.clock.install({time:new Date(now*1000)});
  const calls=[];
  let verdict="WAIT", stale=false;
  await page.route("**/api/trading-desk/research?*", async route=>{
    const url=new URL(route.request().url());
    const symbol=url.searchParams.get("symbol"),region=url.searchParams.get("region");
    calls.push({region,symbol});
    const t=now;
    await route.fulfill({json:{symbol,region,mode:"RESEARCH_ONLY",source:"QA fixture",price:25000,
      market_status:"OPEN",session_start:t-3600,session_end:t+3600,
      quote_time:t-5,bar_close_time:t-10,stale_cache:stale,
      bars:[{time:t-310,close:25000,open:25000,high:25001,low:24999,volume:100}],
      stages:["Data steward","Session guard","Trend analyst","Setup analyst","Risk critic","Quote guard"].map(name=>({name,status:"pass"})),
      verdict,bias:"BULLISH",reason:"Synthetic QA data only",paper_eligible:false}});
  });
  await page.route("**/api/trading-desk/options?*",route=>route.fulfill({json:{status:"WAIT",reason:"No contract"}}));
  await page.route("**/api/trading-desk/india-intelligence?*",route=>route.fulfill({json:{status:"WAIT",reason:"No verified contract",chain:{available:false},checks:[]}}));
  await page.goto("http://127.0.0.1:8765/trading/");
  await expect(page.locator("#guided-action")).toHaveText("MARKET CLOSED — NO TRADE");
  await page.locator('[data-region="IN"]').click();
  await expect(page.locator("#guided-action")).toHaveText("WAIT — NO ENTRY YET");
  await expect(page.locator("#auto-refresh")).toBeChecked();
  await expect(page.locator("#scan-cadence")).toHaveValue("5");
  await expect(page.locator(".duplicate-verdict")).toBeHidden();
  const previous=calls.filter(c=>c.region==="IN").length;
  verdict="LONG_RESEARCH";
  now+=300;
  await page.clock.fastForward(300000);
  await expect.poll(()=>calls.filter(c=>c.region==="IN").length).toBe(previous+1);
  await expect(page.locator("#guided-action")).toHaveText("WAIT — CE BIAS");
  await expect(page.locator("#guided-confidence")).toContainText("ENTRY UNCONFIRMED");
  verdict="BEARISH_RESEARCH";
  await page.locator("#symbol").fill("BANKNIFTY");
  await page.locator("#scan-button").click();
  await expect(page.locator("#guided-action")).toHaveText("WAIT — PE BIAS");
  stale=true;
  await page.locator("#scan-button").click();
  await expect(page.locator("#guided-action")).toHaveText("NO TRADE — DATA UNVERIFIED");
  await page.clock.setSystemTime(new Date("2026-11-25T11:00:00Z"));
  await page.clock.runFor(1000);
  await expect(page.locator("#guided-action")).toHaveText("MARKET CLOSED — NO TRADE");
  await expect(page.locator("#options-contract")).toHaveText("");
});

test("regional shortlist is isolated and opens fresh single-symbol research", async ({page})=>{
  const now=Date.parse("2026-11-25T15:30:00Z")/1000;
  await page.clock.install({time:new Date(now*1000)});
  const seen=[];
  await page.route("**/api/trading-desk/opportunities?*",route=>{
    const region=new URL(route.request().url()).searchParams.get("region");
    return route.fulfill({json:{region,status:"RESEARCH_CANDIDATES",coverage:{attempted:10,universe_size:10},
      cycle_completed_at:now,next_cycle_at:now+3600,
      opportunities:[{rank:1,region,symbol:region==="US"?"AAPL":"RELIANCE",direction:"BULLISH",expires_at:now+100,status:"RESEARCH_ONLY"}],last_shortlist:[]}});
  });
  await page.route("**/api/trading-desk/research?*",route=>{
    const url=new URL(route.request().url());
    seen.push(url.searchParams.get("symbol"));
    return route.fulfill({json:{symbol:url.searchParams.get("symbol"),region:url.searchParams.get("region"),stages:[],bars:[],verdict:"WAIT",bias:"UNAVAILABLE",reason:"QA only"}});
  });
  await page.route("**/api/trading-desk/options?*",route=>route.fulfill({json:{status:"WAIT"}}));
  await page.route("**/api/trading-desk/india-intelligence?*",route=>route.fulfill({json:{status:"WAIT",checks:[]}}));
  await page.goto("http://127.0.0.1:8765/trading/");
  await expect(page.locator("#opportunity-list")).toContainText("AAPL");
  await page.locator('[data-region="IN"]').click();
  await expect(page.locator("#opportunity-list")).toContainText("RELIANCE");
  await expect(page.locator("#opportunity-list")).not.toContainText("AAPL");
  await page.locator('[data-opportunity-symbol="RELIANCE"]').click();
  await expect(page.locator("#symbol")).toHaveValue("RELIANCE");
  await expect.poll(()=>seen.includes("RELIANCE")).toBe(true);
});

test("US opening ignores previous exchange-date close", async ({page})=>{
  const now=Date.parse("2026-11-25T14:32:00Z")/1000;
  await page.clock.install({time:new Date(now*1000)});
  await page.route("**/api/trading-desk/research?*",route=>{
    const u=new URL(route.request().url());
    return route.fulfill({json:{symbol:u.searchParams.get("symbol"),region:"US",market_status:"CLOSED",session_start:Date.parse("2026-11-24T14:30:00Z")/1000,session_end:Date.parse("2026-11-24T21:00:00Z")/1000,stale_cache:true,stages:[],bars:[],verdict:"WAIT",bias:"UNAVAILABLE"}});
  });
  await page.route("**/api/trading-desk/options?*",route=>route.fulfill({status:401,json:{detail:"Unauthorized"}}));
  await page.route("**/api/trading-desk/opportunities?*",route=>route.fulfill({json:{region:"US",status:"WAIT",opportunities:[],last_shortlist:[]}}));
  await page.goto("http://127.0.0.1:8765/trading/");
  await expect(page.locator("#session")).toHaveText("Session data unverified");
  await expect(page.locator("#guided-action")).not.toContainText("MARKET CLOSED");
  await expect(page.locator("#options-contract")).toHaveText("");
});
