// Local simulation only. No networking, credentials, or broker APIs.
export function fresh(report, now = Date.now() / 1000) {
  return (
    !!report &&
    Number.isFinite(report.quote_time) &&
    now >= report.quote_time &&
    now - report.quote_time <= 300
  );
}
export function account(initial = 2000) {
  return { initial, cash: initial, positions: [], closed: [] };
}
export function sizing(report, a, riskPct) {
  const s = report?.scenario;
  if (
    !s ||
    !report.paper_eligible ||
    ![s.entry, s.stop, s.target, a.cash, a.initial, riskPct].every(
      Number.isFinite,
    ) ||
    s.stop <= 0 ||
    s.entry <= s.stop ||
    s.target <= s.entry ||
    riskPct < 0.1 ||
    riskPct > 2
  )
    return null;
  const fill = s.entry * 1.0005,
    budget = (a.initial * riskPct) / 100,
    fees = 2;
  const qty = Math.max(
    0,
    Math.min(
      Math.floor((a.cash - 1) / fill),
      Math.floor((budget - fees) / (fill - s.stop * 0.9995)),
    ),
  );
  return {
    qty,
    fill,
    cost: qty * fill + 1,
    plannedRisk: qty * (fill - s.stop * 0.9995) + fees,
    budget,
  };
}
export function openPaper(report, a, riskPct, now = Date.now() / 1000) {
  if (!fresh(report, now) || report.market_status !== "OPEN")
    throw Error(
      "A recent regular-session quote is required. Run research again.",
    );
  if (
    a.positions.length >= 3 ||
    a.positions.some((p) => p.symbol === report.symbol)
  )
    throw Error("Maximum three paper positions; one per symbol.");
  const day = new Date(now * 1000).toISOString().slice(0, 10);
  const pnl = a.closed
    .filter(
      (p) => new Date(p.closedAt * 1000).toISOString().slice(0, 10) === day,
    )
    .reduce((n, p) => n + p.pnl, 0);
  if (pnl <= -a.initial * 0.01)
    throw Error(
      "Paper daily realized-loss guard reached (1% of starting balance, UTC day).",
    );
  const size = sizing(report, a, riskPct);
  if (!size || size.qty < 1)
    throw Error(
      "No whole-share position fits cash and the modeled risk budget.",
    );
  a.cash -= size.cost;
  a.positions.push({
    id: now + "-" + report.symbol,
    symbol: report.symbol,
    region: report.region,
    qty: size.qty,
    entry: size.fill,
    stop: report.scenario.stop,
    target: report.scenario.target,
    openedAt: now,
    source: report.source,
  });
  return size;
}
export function closePaper(
  a,
  id,
  report,
  reason = "MANUAL",
  now = Date.now() / 1000,
) {
  const p = a.positions.find((p) => p.id === id);
  if (
    !p ||
    p.symbol !== report?.symbol ||
    p.region !== report?.region ||
    !fresh(report, now) ||
    report.market_status !== "OPEN" ||
    !Number.isFinite(report.price) ||
    report.price <= 0
  )
    throw Error(
      "Scan this position during its regular session for a fresh exit quote.",
    );
  const exit = report.price * 0.9995,
    pnl = (exit - p.entry) * p.qty - 2;
  a.cash += exit * p.qty - 1;
  a.positions = a.positions.filter((x) => x.id !== id);
  a.closed.unshift({ ...p, exit, pnl, reason, closedAt: now });
  return pnl;
}
export function observedExits(a, report, now = Date.now() / 1000) {
  if (!fresh(report, now) || report.market_status !== "OPEN") return 0;
  let count = 0;
  for (const p of [...a.positions])
    if (
      p.symbol === report.symbol &&
      p.region === report.region &&
      (report.price <= p.stop || report.price >= p.target)
    ) {
      closePaper(
        a,
        p.id,
        report,
        report.price <= p.stop ? "OBSERVED_STOP" : "OBSERVED_TARGET",
        now,
      );
      count++;
    }
  return count;
}

export function autoPaper(a, report, riskPct, now = Date.now() / 1000) {
  if (!report || report.mode === "SAMPLE" || report.source === "SYNTHETIC SAMPLE")
    return "Automatic paper trading skips sample data.";
  if (!fresh(report, now) || report.market_status !== "OPEN" ||
      !Number.isFinite(report.session_end) || now >= report.session_end ||
      !Number.isFinite(report.session_start) || now < report.session_start)
    return "Waiting for fresh regular-session data.";
  const exits = observedExits(a, report, now);
  if (exits) return "Closed " + exits + " paper position at the observed quote.";
  if (!report.paper_eligible || report.verdict !== "LONG_RESEARCH" ||
      !Array.isArray(report.stages) || !report.stages.length ||
      report.stages.some(s => s.status === "blocked"))
    return "No qualifying long stock/ETF setup; no paper entry.";
  const key = [report.region, report.symbol, report.session_start].join(":");
  if ([...a.positions, ...a.closed].some(p => p.autoKey === key))
    return "This instrument already had an automatic entry this session.";
  try {
    const size = openPaper(report, a, riskPct, now);
    a.positions[a.positions.length - 1].autoKey = key;
    return "Opened " + size.qty + " simulated shares of " + report.symbol + ".";
  } catch (error) { return error.message; }
}
