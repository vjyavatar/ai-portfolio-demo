import test from "node:test";
import assert from "node:assert/strict";
import {
  account,
  sizing,
  openPaper,
  closePaper,
  observedExits,
} from "../trading/paper.mjs";
const report = () => ({
  symbol: "SPY",
  region: "US",
  market_status: "OPEN",
  quote_time: 1000,
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
