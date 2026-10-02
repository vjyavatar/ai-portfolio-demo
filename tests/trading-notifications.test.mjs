import test from "node:test";
import assert from "node:assert/strict";
import { candidate, enqueue } from "../trading/notifications.mjs";
const report = {symbol:"SPY",region:"US",verdict:"LONG_RESEARCH",quote_time:1000,session_start:500,session_end:2000,market_status:"OPEN",stages:[{status:"pass"},{status:"watch"}]};
test("fresh research alerts expire at quote TTL or session end", () => {
  assert.equal(candidate(report, 1001).expires, 1300);
  assert.equal(candidate({...report,session_end:1100},1001).expires,1100);
});
test("sample, stale, future, blocked, closed and WAIT never alert", () => {
  for(const patch of [{mode:"SAMPLE"},{source:"SYNTHETIC SAMPLE"},{quote_time:500},{quote_time:1100},{stages:[{status:"blocked"}]},{market_status:"CLOSED_OR_UNVERIFIED"},{verdict:"WAIT"},{session_end:900}])
    assert.equal(candidate({...report,...patch},1001),null);
});
test("repeat scans and reloads deduplicate the same directional session", () => {
  const first = enqueue([],report,1001);
  assert.ok(first.alert);
  const stored=JSON.parse(JSON.stringify(first.inbox));
  assert.equal(enqueue(stored,{...report,quote_time:1050},1051).alert,null);
  assert.ok(enqueue(stored,{...report,verdict:"BEARISH_RESEARCH"},1001).alert);
});
test("new WAIT invalidates previous evidence without repeating alerts", () => {
  const first=enqueue([],report,1001);
  const next=enqueue(first.inbox,{...report,verdict:"WAIT",reason:"Breakout lost"},1002);
  assert.equal(next.alert,null);
  assert.equal(next.inbox[0].invalidated,1002);
  assert.equal(next.inbox[0].invalidationReason,"Breakout lost");
  assert.equal(enqueue(next.inbox,report,1003).alert,null);
});
test("sample and unrelated symbols do not invalidate an alert", () => {
  const first=enqueue([],report,1001);
  assert.equal(enqueue(first.inbox,{...report,mode:"SAMPLE"},1002).inbox[0].invalidated,undefined);
  assert.equal(enqueue(first.inbox,{...report,symbol:"QQQ",verdict:"WAIT"},1002).inbox[0].invalidated,undefined);
});
test("failed request invalidates previous symbol evidence", () => {
  const first=enqueue([],report,1001);
  const next=enqueue(first.inbox,{symbol:"SPY",region:"US",verdict:"WAIT"},1002);
  assert.equal(next.inbox[0].invalidated,1002);
});
