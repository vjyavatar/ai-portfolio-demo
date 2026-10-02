import { fresh } from "./paper.mjs";

// Once per direction per provider session, including across page reloads.
export function candidate(report, now = Date.now() / 1000) {
  if (!report || report.mode === "SAMPLE" || report.source === "SYNTHETIC SAMPLE" ||
      !fresh(report, now) || report.market_status !== "OPEN" ||
      !Number.isFinite(report.session_end) || now >= report.session_end ||
      !Number.isFinite(report.session_start) || now < report.session_start ||
      !["LONG_RESEARCH", "BEARISH_RESEARCH"].includes(report.verdict) ||
      !Array.isArray(report.stages) || !report.stages.length || report.stages.some(s => s.status === "blocked")) return null;
  return {
    id: [report.region, report.symbol, report.verdict, report.session_start].join(":"),
    symbol: report.symbol, region: report.region, verdict: report.verdict,
    created: now, expires: Math.min(report.quote_time + 300, report.session_end),
    sourceTime: report.quote_time, reason: report.reason,
  };
}
export function enqueue(inbox, report, now = Date.now() / 1000) {
  if (!report || report.mode === "SAMPLE" || report.source === "SYNTHETIC SAMPLE") return { inbox, alert: null };
  const alert = candidate(report, now);
  inbox = inbox.map(item => item.symbol === report.symbol && item.region === report.region &&
    !item.invalidated && (!alert || item.verdict !== alert.verdict || item.id !== alert.id)
    ? { ...item, invalidated: now, invalidationReason: report.reason || "Latest scan no longer confirms this setup." } : item);
  if (!alert || inbox.some(item => item.id === alert.id)) return { inbox, alert: null };
  return { inbox: [alert, ...inbox].slice(0, 100), alert };
}
