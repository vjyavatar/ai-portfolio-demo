import { notificationCenter } from "./notifications-ui.js";
import {
  autoPaper,
  account,
  sizing,
  openPaper,
  closePaper,
  observedExits,
  fresh,
} from "./paper.mjs";
const $ = (id) => document.getElementById(id),
  esc = (x) =>
    String(x ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
const lists = {
  US: [
    ["SPY", "S&P 500 ETF"],
    ["QQQ", "Nasdaq 100 ETF"],
    ["NVDA", "NVIDIA"],
    ["SPX", "S&P 500 reference index"],
  ],
  IN: [
    ["NIFTY", "Nifty 50 reference index"],
    ["BANKNIFTY", "Bank Nifty reference index"],
    ["RELIANCE", "Reliance Industries"],
    ["HDFCBANK", "HDFC Bank"],
  ],
};
let region = "US",
  report = null,
  sample = false,
  busy = false,
  timer = null,
  controller = null,
  scanId = 0;
const alerts = notificationCenter(() => report, () => sample);
let accounts = {},
  riskPct = 0.5;
try {
  const stored = JSON.parse(localStorage.getItem("celesys.desk.v1") || "{}");
  if (stored && typeof stored === "object") accounts = stored;
} catch {}
function activeAccount() {
  const key = (sample ? "SAMPLE:" : "MARKET:") + region;
  const a = accounts[key];
  if (
    !a ||
    !Number.isFinite(a.initial) ||
    a.initial <= 0 ||
    !Number.isFinite(a.cash) ||
    a.cash < 0 ||
    !Array.isArray(a.positions) ||
    !Array.isArray(a.closed)
  )
    accounts[key] = account(region === "US" ? 2000 : 100000);
  return accounts[key];
}
function persist() {
  try {
    localStorage.setItem("celesys.desk.v1", JSON.stringify(accounts));
  } catch {
    notify(
      "Browser storage unavailable. Export the journal before closing this page.",
    );
  }
}
function fmt(x) {
  return Number.isFinite(x)
    ? new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: region === "US" ? "USD" : "INR",
        maximumFractionDigits: 2,
      }).format(x)
    : "—";
}
function time(t) {
  return Number.isFinite(t)
    ? new Date(t * 1000).toLocaleString("en-US", {
        timeZone: region === "US" ? "America/Chicago" : "Asia/Kolkata",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      })
    : "Unknown";
}
function notify(message) {
  $("notice").textContent =
    (sample
      ? "SAMPLE EXERCISE · Synthetic prices, not a market opportunity. "
      : "") + message;
  $("notice").classList.toggle("demo", sample);
}
function watchlist() {
  const sym = $("symbol").value.toUpperCase();
  $("watchlist").innerHTML = lists[region]
    .map(
      ([s, n]) =>
        `<button class="watch-item ${s === sym ? "active" : ""}" data-symbol="${esc(s)}"><span><strong>${esc(s)}</strong><small>${esc(n)}</small></span><span>↗</span></button>`,
    )
    .join("");
  $("chart-title").textContent = sym + " / Price structure";
}
$("watchlist").addEventListener("click", (e) => {
  const b = e.target.closest("[data-symbol]");
  if (b) {
    $("symbol").value = b.dataset.symbol;
    resetResearch();
    watchlist();
    notify("Instrument selected. Run research to load its data.");
  }
});
function resetResearch() {
  scanId++;
  controller?.abort();
  busy = false;
  $("scan-button").disabled = false;
  $("scan-button").textContent = "↗ Run research";
  report = null;
  sample = false;
  render();
}
for (const b of document.querySelectorAll("[data-region]"))
  b.addEventListener("click", () => {
    region = b.dataset.region;
    $("symbol").value = lists[region][0][0];
    for (const x of document.querySelectorAll("[data-region]")) {
      x.classList.toggle("selected", x === b);
      x.setAttribute("aria-pressed", String(x === b));
    }
    resetResearch();
    watchlist();
    notify("Market changed. Run a fresh research check.");
  });
$("symbol").addEventListener("input", () => {
  resetResearch();
  watchlist();
});
function chart() {
  const bars = report?.bars || [];
  if (!bars.length) {
    $("chart").className = "chart-empty";
    $("chart").innerHTML =
      '<span class="empty-icon">⌁</span><strong>A clear view starts with real data.</strong><p>No verified session bars available.</p>';
    return;
  }
  const W = 800,
    H = 300,
    pad = 35,
    prices = bars.map((b) => b.close),
    min = Math.min(...prices),
    max = Math.max(...prices),
    range = max - min || max * 0.001;
  const y = (p) => H - pad - ((p - min) / range) * (H - pad * 2),
    x = (i) => pad + (i * (W - pad * 2)) / Math.max(1, bars.length - 1);
  const points = bars.map((b, i) => `${x(i)},${y(b.close)}`).join(" ");
  const lines = Array.from({ length: 5 }, (_, i) => {
    const price = min + (range * i) / 4;
    return `<line x1="${pad}" x2="${W - pad}" y1="${y(price)}" y2="${y(price)}" stroke="#253540"/><text x="${pad}" y="${y(price) - 7}" fill="#9babba" font-size="10">${esc(fmt(price))}</text>`;
  }).join("");
  $("chart").className = "chart-data";
  $("chart").innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(report.symbol)} closed five-minute prices, ${esc(sample ? "synthetic sample" : "Yahoo source")}">${lines}<polyline points="${points}" fill="none" stroke="#74dfb4" stroke-width="2.5"/><circle cx="${x(bars.length - 1)}" cy="${y(prices.at(-1))}" r="4" fill="#74dfb4"/><text x="35" y="295" fill="#9babba" font-size="10">${esc(time(bars[0].time))}</text><text x="765" y="295" text-anchor="end" fill="#9babba" font-size="10">${esc(time(bars.at(-1).time))}</text></svg>`;
}
function renderReadiness() {
  const status = report?.provider_status;
  const labels = {LOCAL_PACING:"Request pacing active",REQUEST_IN_PROGRESS:"Provider request in progress",NOT_CHECKED:"Not checked",RATE_LIMITED:"Provider rate-limited",ACCESS_DENIED:"Provider access denied",HTTP_ERROR:"Provider HTTP error",CONNECTION_FAILURE:"Connection failed",INVALID_RESPONSE:"Invalid provider response",PROVIDER_FAILURE:"Provider unavailable",RESPONSE_RECEIVED:"Response received"};
  $("connection-state").textContent = sample ? "Synthetic exercise" : status ? labels[status.code] || "Unverified" : report ? "Unverified" : "Not checked";
  $("connection-detail").textContent = sample ? "No market-data connection used" : status?.code === "RESPONSE_RECEIVED" ? "Source freshness is evaluated separately" : status?.retry_after ? "Retry after " + time(status.retry_after) : "Run research to test the provider";
  $("coverage-state").textContent = $("auto-refresh").checked ? (document.hidden ? "Paused · hidden tab" : sample ? "Paused · sample mode" : "Every 5 min · one instrument") : "Manual · one instrument";
  $("coverage-detail").textContent = "Selected: " + $("symbol").value.toUpperCase() + " · checks stop when this page closes";
}
function render() {
  renderReadiness();
  const a = activeAccount();
  riskPct =
    Number.isFinite(a.riskPct) && a.riskPct >= 0.1 && a.riskPct <= 2
      ? a.riskPct
      : 0.5;
  $("risk-pct").value = riskPct;
  $("currency").textContent = region === "US" ? "USD" : "INR";
  $("capital").value = a.initial;
  $("price").textContent = fmt(report?.price);
  $("price-note").textContent = report
    ? "Quote: " + time(report.quote_time)
    : "No quote loaded";
  $("verdict").textContent = report
    ? {
        LONG_RESEARCH: "Long candidate",
        BEARISH_RESEARCH: "Bearish watch",
        WAIT: "Wait / no trade",
      }[report.verdict] || "Wait"
    : "Not scanned";
  $("verdict-note").textContent = report
    ? "Underlying research only"
    : "Evidence comes first";
  $("freshness").textContent = sample
    ? "Sample data"
    : report
      ? fresh(report)
        ? "Recent timestamp"
        : "Stale / unknown"
      : "Unverified";
  $("freshness-note").textContent = report
    ? "Latest closed bar: " + time(report.bar_close_time)
    : "Source timestamp required";
  $("session").textContent = sample
    ? "Simulated"
    : report?.market_status === "OPEN"
      ? "Regular hours"
      : report
        ? "Closed / unknown"
        : "—";
  $("source-label").textContent = sample
    ? "SYNTHETIC SAMPLE"
    : report
      ? "Yahoo Finance · latency unverified"
      : "Source not loaded";
  $("chart-sub").textContent = report
    ? "Closed five-minute bars · " +
      (sample ? "synthetic exercise" : report.bias.toLowerCase() + " structure")
    : "Closed five-minute bars · regular session only";
  $("agent-count").textContent = report
    ? `${report.stages.filter((s) => s.status === "pass").length}/${report.stages.length} CHECKS PASS`
    : "AWAITING RUN";
  $("agents").innerHTML = report?.stages.length
    ? report.stages
        .map(
          (s, i) =>
            `<article class="agent"><div class="agent-top"><h3>${i + 1}. ${esc(s.name)}</h3><span class="badge ${esc(s.status)}">${esc(s.status.toUpperCase())}</span></div><p>${esc(s.detail)}</p></article>`,
        )
        .join("")
    : '<div class="empty-state">Data steward → session guard → trend analyst → setup analyst → risk critic → review</div>';
  $("decision-note").textContent =
    report?.reason ||
    "Call/put contract selection needs verified options quotes and contract metadata. This desk evaluates the underlying only.";
  chart();
  renderRisk();
  renderJournal();
}
function renderRisk() {
  const a = activeAccount(),
    size = sizing(report, a, riskPct),
    s = report?.scenario;
  $("paper-button").disabled = !(size?.qty > 0 && fresh(report));
  $("risk-result").innerHTML = s
    ? `<div class="risk-levels"><div><span>REFERENCE ENTRY</span><strong>${esc(fmt(s.entry))}</strong></div><div><span>STOP SCENARIO</span><strong>${esc(fmt(s.stop))}</strong></div><div><span>TARGET SCENARIO</span><strong>${esc(fmt(s.target))}</strong></div></div><div>${size ? `${size.qty} whole shares · planned stop risk ${esc(fmt(size.plannedRisk))} · purchase ${esc(fmt(size.cost))}` : "No eligible long stock/ETF paper position."}</div><p class="help">Underlying levels only. Full purchase can be lost; stop risk is not a guaranteed cap.</p>`
    : "No eligible price scenario. Missing evidence means no paper entry.";
}
function renderJournal() {
  const a = activeAccount();
  const realized = a.closed.reduce((n, p) => n + p.pnl, 0);
  $("journal-summary").innerHTML =
    `<span>Account <strong>${sample ? "Sample exercise" : "Market research"} / ${region}</strong></span><span>Cash <strong>${esc(fmt(a.cash))}</strong></span><span>Realized P&L <strong>${esc(fmt(realized))}</strong></span><span>Open <strong>${a.positions.length}</strong></span>`;
  const rows = [
    ...a.positions.map((p) => ({ ...p, state: "OPEN" })),
    ...a.closed.map((p) => ({ ...p, state: "CLOSED" })),
  ];
  $("journal").innerHTML = rows.length
    ? `<table><thead><tr><th>INSTRUMENT</th><th>STATE</th><th>SHARES</th><th>ENTRY</th><th>EXIT</th><th>NET P&L</th><th>ACTION / REASON</th></tr></thead><tbody>${rows.map((p) => `<tr><td>${esc(p.symbol)}</td><td>${p.state}</td><td>${esc(p.qty)}</td><td>${esc(fmt(p.entry))}</td><td>${esc(fmt(p.exit))}</td><td>${esc(fmt(p.pnl))}</td><td>${p.state === "OPEN" ? `<button class="button secondary" data-close="${esc(p.id)}">Close paper position</button>` : esc(p.reason)}</td></tr>`).join("")}</tbody></table>`
    : '<div class="empty-state">No paper trades yet. Research a setup before committing simulated capital.</div>';
}
async function scan() {
  if (busy || !$("scan-form").reportValidity()) return;
  const sym = $("symbol").value.trim().toUpperCase();
  sample = false;
  report = null;
  busy = true;
  const id = ++scanId,
    scanRegion = region;
  controller = new AbortController();
  const currentController = controller;
  const timeout = setTimeout(() => currentController.abort(), 20000);
  $("scan-button").disabled = true;
  $("scan-button").textContent = "Researching…";
  notify("Checking data, session, trend, setup and risk.");
  render();
  try {
    const r = await fetch(
      `/api/trading-desk/research?symbol=${encodeURIComponent(sym)}&region=${scanRegion}`,
      { signal: controller.signal, cache: "no-store" },
    );
    if (!r.ok)
      throw Error(
        r.status === 429
          ? "Research capacity busy. Please retry in a minute."
          : "Research service unavailable (" + r.status + ").",
      );
    const d = await r.json();
    if (id !== scanId) return;
    if (
      d.symbol !== sym ||
      d.region !== scanRegion ||
      !Array.isArray(d.stages) ||
      !Array.isArray(d.bars)
    )
      throw Error("Unexpected research response; no signal issued.");
    report = d;
    alerts.process(d);
    if ($("auto-paper").checked) {
      $("auto-paper-status").textContent = autoPaper(activeAccount(), report, riskPct);
      persist();
    } else if ($("auto-exit").checked) {
      observedExits(activeAccount(), report);
      persist();
    }
    render();
    notify(d.reason);
  } catch (e) {
    if (id !== scanId) return;
    report = null;
    alerts.process({symbol:sym,region:scanRegion,verdict:"WAIT",reason:"Latest research request failed; evidence cannot be reconfirmed."});
    render();
    notify(
      e.name === "AbortError"
        ? "Research timed out. No signal issued. Try again later."
        : e.message,
    );
  } finally {
    clearTimeout(timeout);
    if (id === scanId) {
      busy = false;
      $("scan-button").disabled = false;
      $("scan-button").textContent = "↗ Run research";
    }
  }
}
$("scan-form").addEventListener("submit", (e) => {
  e.preventDefault();
  scan();
});
$("auto-refresh").addEventListener("change", () => {
  clearInterval(timer);
  timer = null;
  if ($("auto-refresh").checked) {
    timer = setInterval(() => {
      if (!document.hidden && !sample) scan();
    }, 300000);
    notify(
      "Five-minute refresh enabled while this page is visible. This is not continuous trade monitoring.",
    );
  } else notify("Automatic refresh paused.");
});
$("risk-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const a = activeAccount(),
    initial = Number($("capital").value);
  riskPct = Number($("risk-pct").value);
  if (a.positions.length && initial !== a.initial) {
    notify("Close paper positions before changing the starting balance.");
    $("capital").value = a.initial;
    return;
  }
  const nextCash = a.cash + initial - a.initial;
  if (nextCash < 0) {
    notify("Starting balance cannot be reduced below accumulated losses.");
    $("capital").value = a.initial;
    return;
  }
  a.cash = nextCash;
  a.initial = initial;
  a.riskPct = riskPct;
  persist();
  renderRisk();
  renderJournal();
  notify("Paper risk settings saved. These do not move real money.");
});
$("paper-button").addEventListener("click", () => {
  try {
    openPaper(report, activeAccount(), riskPct);
    persist();
    render();
    notify("Simulated stock purchase recorded. No real order was sent.");
  } catch (e) {
    notify(e.message);
  }
});
$("journal").addEventListener("click", (e) => {
  const b = e.target.closest("[data-close]");
  if (!b) return;
  try {
    closePaper(activeAccount(), b.dataset.close, report);
    persist();
    render();
    notify(
      "Paper position closed using the observed quote with simulated costs.",
    );
  } catch (e) {
    notify(e.message);
  }
});
$("export-button").addEventListener("click", () => {
  const blob = new Blob(
    [
      JSON.stringify(
        { exported_at: new Date().toISOString(), mode: "PAPER_ONLY", accounts },
        null,
        2,
      ),
    ],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = "celesys-paper-journal.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("demo-button").addEventListener("click", async () => {
  resetResearch();
  $("auto-refresh").checked = false;
  clearInterval(timer);
  timer = null;
  sample = true;
  const demoId = scanId;
  try {
    const r = await fetch("/trading/sample.json");
    if (!r.ok) throw Error("Sample unavailable");
    const demo = await r.json();
    if (demoId !== scanId) return;
    report = demo;
    report.region = region;
    report.currency = region === "US" ? "USD" : "INR";
    const offset = Date.now() / 1000 - report.quote_time;
    report.quote_time += offset;
    report.bar_close_time += offset;
    if (report.session_start) report.session_start += offset;
    if (report.session_end) report.session_end += offset;
    for (const b of report.bars) b.time += offset;
    $("symbol").value = report.symbol;
    watchlist();
    render();
    notify(
      "Explore the research trail and practice with a separate sample paper account.",
    );
  } catch (e) {
    notify(e.message);
  }
});
setInterval(() => {
  $("clock").textContent =
    "Dallas · " +
    new Date().toLocaleTimeString("en-US", {
      timeZone: "America/Chicago",
      hour: "2-digit",
      minute: "2-digit",
    });
  renderReadiness();
  if (report && !sample) {
    $("freshness").textContent = fresh(report) ? "Recent timestamp" : "Stale / unknown";
    if (!fresh(report)) {
      $("verdict").textContent = "Expired / rescan";
      $("verdict-note").textContent = "Previous result no longer current";
    }
    $("paper-button").disabled = !(
      sizing(report, activeAccount(), riskPct)?.qty > 0 && fresh(report)
    );
  }
}, 15000);
document.addEventListener("visibilitychange", renderReadiness);
watchlist();
render();

$("auto-paper").addEventListener("change", () => {
  const enabled = $("auto-paper").checked;
  $("auto-paper-status").textContent = enabled
    ? "Running for the selected instrument while this tab is visible. Waiting for a qualifying scan."
    : "Automatic paper trading stopped. Existing paper positions remain in the journal.";
  if (enabled) {
    $("auto-refresh").checked = true;
    $("auto-refresh").dispatchEvent(new Event("change"));
    scan();
  }
});
