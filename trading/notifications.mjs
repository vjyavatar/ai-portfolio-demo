import { fresh } from "./paper.mjs";

// Once per direction per provider session, including across page reloads.
export function candidate(report, now = Date.now() / 1000) {
  if (!report || report.mode === "SAMPLE" || report.source === "SYNTHETIC SAMPLE" ||
      !fresh(report, now) || report.market_status !== "OPEN" ||
      !Number.isFinite(report.session_end) || now >= report.session_end ||
      !["LONG_RESEARCH", "BEARISH_RESEARCH"].includes(report.verdict) ||
      !Array.isArray(report.stages) || report.stages.some(s => s.status === "blocked")) return null;
  return {
    id: [report.region, report.symbol, report.verdict, report.session_start].join(":"),
    symbol: report.symbol, region: report.region, verdict: report.verdict,
    created: now, expires: Math.min(report.quote_time + 300, report.session_end),
    sourceTime: report.quote_time, reason: report.reason,
  };
}
export function enqueue(inbox, report, now = Date.now() / 1000) {
  const alert = candidate(report, now);
  if (!alert || inbox.some(item => item.id === alert.id)) return { inbox, alert: null };
  return { inbox: [alert, ...inbox].slice(0, 100), alert };
}
