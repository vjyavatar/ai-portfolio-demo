import test from "node:test";
import assert from "node:assert/strict";
import { account, autoPaper } from "../trading/paper.mjs";
const r={symbol:"SPY",region:"US",source:"test fixture",mode:"RESEARCH_ONLY",quote_time:1000,market_status:"OPEN",session_start:500,session_end:2000,price:100,scenario:{entry:100,stop:99,target:102},verdict:"LONG_RESEARCH",paper_eligible:true,stages:[{status:"pass"}]};
test("automatic paper entry deduplicates, exits at observed price and cannot reenter",()=>{
 const a=account(2000);
 assert.match(autoPaper(a,r,.5,1001),/Opened/);
 assert.equal(a.positions.length,1);
 autoPaper(a,r,.5,1002);assert.equal(a.positions.length,1);
 assert.match(autoPaper(a,{...r,price:98,verdict:"WAIT",paper_eligible:false},.5,1003),/Closed/);
 assert.equal(a.positions.length,0);assert.equal(a.closed.length,1);
 autoPaper(a,r,.5,1004);assert.equal(a.positions.length,0);
});
test("sample, stale, blocked and closed-session scans do not enter",()=>{
 for(const patch of [{mode:"SAMPLE"},{quote_time:500},{stages:[{status:"blocked"}]},{session_end:900},{verdict:"WAIT"}]){
  const a=account(2000);autoPaper(a,{...r,...patch},.5,1001);assert.equal(a.positions.length,0);
 }
});
