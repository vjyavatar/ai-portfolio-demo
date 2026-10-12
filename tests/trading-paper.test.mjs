import test from "node:test";
import assert from "node:assert/strict";
import {
  account,
  sizing,
  openPaper,
  closePaper,
  observedExits,
  fresh,
} from "../trading/paper.mjs";
const report = () => ({
  symbol: "SPY",
  region: "US",
  market_status: "OPEN",
  quote_time: 1000,
  bar_close_time: 1000,
  session_start: 500,
  session_end: 2000,
  price: 100,
  paper_eligible: true,
  source: "TEST",
  scenario: { entry: 100, stop: 98, target: 104 },
});
test("cash, risk and fee-aware sizing", () => {
  const a = account(),
    s = sizing(report(), a, 0.5);
  assert.equal(s.qty, 3);
  assert.ok(s.plannedRisk <= 10);
  assert.ok(s.cost <= a.cash);
});
test("stale quote cannot open a paper position", () => {
  assert.throws(() => openPaper(report(), account(), 0.5, 1400), /recent/);
});
test("duplicate symbol blocked", () => {
  const a = account();
  openPaper(report(), a, 0.5, 1000);
  assert.throws(() => openPaper(report(), a, 0.5, 1000), /one per symbol/);
});
test("gap below stop realizes observed loss, not imaginary stop fill", () => {
  const a = account();
  openPaper(report(), a, 0.5, 1000);
  const r = report();
  r.price = 90;
  assert.equal(observedExits(a, r, 1000), 1);
  assert.ok(a.closed[0].exit < 90);
  assert.ok(a.closed[0].pnl < -10);
  assert.equal(a.positions.length, 0);
});
test("cannot close with another symbol quote", () => {
  const a = account();
  openPaper(report(), a, 0.5, 1000);
  assert.throws(() =>
    closePaper(
      a,
      a.positions[0].id,
      { ...report(), symbol: "QQQ" },
      "MANUAL",
      1000,
    ),
  );
});
test("round trip includes two fees and adverse price adjustment", () => {
  const a = account();
  openPaper(report(), a, 0.5, 1000);
  closePaper(a, a.positions[0].id, report(), "MANUAL", 1000);
  assert.ok(a.cash < 1998);
  assert.ok(Math.abs(a.cash - 2000 - a.closed[0].pnl) < 1e-9);
});
test("missing evidence yields no sizing", () =>
  assert.equal(sizing({}, account(), 0.5), null));
test("daily realized loss guard blocks further entries", () => {
  const a = account();
  a.closed.push({ closedAt: 1000, pnl: -20 });
  assert.throws(() => openPaper(report(), a, 0.5, 1000), /loss guard/);
});
test("freshness requires the session and closed-bar evidence, not only a recent quote", () => {
  for (const patch of [
    { session_start: undefined }, { session_end: undefined },
    { session_start: 1002 }, { session_end: 1001 },
    { bar_close_time: undefined }, { bar_close_time: 700 },
    { bar_close_time: 1002 }, { quote_time: 999 },
    { market_status: "CLOSED_OR_UNVERIFIED" },
  ]) {
    const r = { ...report(), ...patch };
    assert.equal(fresh(r, 1001), false);
    assert.throws(() => openPaper(r, account(), 0.5, 1001));
  }
});
test("stale bars and elapsed session cannot fabricate observed exits", () => {
  for (const patch of [{bar_close_time: 700}, {session_end: 1001}]) {
    const a = account(); openPaper(report(), a, 0.5, 1000);
    const r = {...report(), price: 90, ...patch};
    assert.equal(observedExits(a, r, 1001), 0);
    assert.throws(() => closePaper(a, a.positions[0].id, r, "MANUAL", 1001));
    assert.equal(a.positions.length, 1);
  }
});
