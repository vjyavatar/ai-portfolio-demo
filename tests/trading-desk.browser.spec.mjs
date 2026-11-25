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
