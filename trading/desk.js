import { classify } from "./decision-state.mjs";
import { optionView } from "./options.mjs";
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
    ["SENSEX", "BSE Sensex reference index"],
    ["RELIANCE", "Reliance Industries"],
    ["HDFCBANK", "HDFC Bank"],
  ],
};
let region = "US",
  report = null,
  optionsResult = null,
  sample = false,
  busy = false,
  timer = null,
  controller = null,
  scanId = 0;
const refreshDelay = () => Number($("scan-cadence")?.value || 5) * 60000;
let nextScanAt = null, lastScanAt = null;
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
        timeZone: region === "US" ? "America/New_York" : "Asia/Kolkata",
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
    scan();
  }
});
function resetResearch() {
  scanId++;
  controller?.abort();
  busy = false;
  $("scan-button").disabled = false;
  $("scan-button").textContent = "↗ Run research";
  report = null;
  optionsResult = null;
  sample = false;
  $("chain-summary").textContent = "No chain loaded for this instrument.";
  showEvidence([]);
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
    scan();
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
  $("coverage-state").textContent = $("auto-refresh").checked ? (document.hidden ? "Paused · hidden tab" : sample ? "Paused · sample mode" : `Every ${$("scan-cadence").value} min · selected instrument`) : "Manual · one instrument";
  $("coverage-detail").textContent = "Selected: " + $("symbol").value.toUpperCase() + " · checks stop when this page closes";
}
// Present coverage without disclosing internal scoring thresholds.
function showEvidence(checks) {
  const holder = $("evidence-checks");
  if (!holder) return;
  holder.replaceChildren();
  if (!checks.length) {
    holder.textContent = "Scan a supported India index to see available evidence and missing safeguards.";
    return;
  }
  for (const check of checks) {
    const line=document.createElement("div"), name=document.createElement("strong"),
      state=document.createElement("span"), detail=document.createElement("small");
    name.textContent=check.label; state.textContent=check.state; detail.textContent=check.detail;
    line.className="evidence-item";
    line.append(name,state,detail); holder.append(line);
  }
}
// Regular-hours display is separate from trade eligibility and provider freshness.
function regularSessionClosed(now = Date.now()/1000) {
  if (sample) return false;
  if (region === "IN" || region === "US") {
    const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", {
      timeZone:region === "IN" ? "Asia/Kolkata" : "America/New_York", weekday:"short", hour:"2-digit", minute:"2-digit", hourCycle:"h23"
    }).formatToParts(new Date(now*1000)).map(p=>[p.type,p.value]));
    const minutes = Number(parts.hour)*60+Number(parts.minute);
    if (["Sat","Sun"].includes(parts.weekday) || minutes<(region==="IN"?555:570) || minutes>=(region==="IN"?930:960)) return true;
  }
  const start=report?.session_start, end=report?.session_end;
  return report?.region===region && Number.isFinite(start) && Number.isFinite(end) &&
    start<end && end-start<=86400 && now>=end && now-end<86400 &&
    (region!=="IN" || report?.market_status!=="OPEN");
}
function currentDecision(now=Date.now()/1000) {
  return classify({report,options:optionsResult,region,symbol:$("symbol").value.trim().toUpperCase(),busy,sample,closed:regularSessionClosed(now),now});
}
function renderGuidance() {
  const d=currentDecision();
  const action=$("guided-action");
  action.textContent=d.title;
  action.dataset.state=d.state==="CLOSED"?"closed":d.state==="WAIT"||d.state==="BIAS"||d.state==="SCANNING"||d.state==="REVIEW"?"wait":"neutral";
  action.classList.remove("action-review");
  $("guided-why").textContent=d.reason;
  $("guided-next").textContent=d.state==="REVIEW"?"Verify the contract and event risk with your broker.":d.state==="CLOSED"?"Review the last available chain.":d.state==="SAMPLE"?"Practice only.":"Wait for the next scan.";
  $("guided-source").textContent="SOURCE · "+(sample?"SAMPLE":report?.source==="market-data"?"UNAVAILABLE":report?.source||"UNVERIFIED");
  $("guided-clock").textContent="BAR CLOSE · "+time(report?.bar_close_time);
  $("guided-confidence").textContent="EVIDENCE CONFIDENCE · "+d.confidence;
  renderScanStatus();
}
function renderScanStatus(){
  const seconds=nextScanAt===null?null:Math.max(0,Math.ceil((nextScanAt-Date.now())/1000));
  const countdown=seconds===null?"—":Math.floor(seconds/60)+":"+String(seconds%60).padStart(2,"0");
  $("scan-status").textContent=busy?"Scanning…":sample?"Paused · sample":!$("auto-refresh").checked?"Auto-scan off":document.hidden?"Paused · hidden tab":"Next scan "+countdown+" · Last scan "+(lastScanAt===null?"not yet":time(lastScanAt/1000));
}
function render() {
  renderReadiness();
  renderGuidance();
  const a = activeAccount();
  riskPct =
    Number.isFinite(a.riskPct) && a.riskPct >= 0.1 && a.riskPct <= 2
      ? a.riskPct
      : 0.5;
  $("risk-pct").value = riskPct;
  $("currency").textContent = region === "US" ? "USD" : "INR";
  $("capital").value = a.initial;
  $("price").textContent = fmt(report?.price);
  $("price-note").textContent = Number.isFinite(report?.price) ? (report.price_kind==="LAST_CLOSED_BAR" ? "Last closed candle: "+time(report.price_as_of) : report.price_kind==="UNVERIFIED_QUOTE_SNAPSHOT" ? "Snapshot · exchange time unknown" : "Exchange quote: "+time(report.quote_time)) : "No quote loaded";
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
    : regularSessionClosed() ? "Market closed" : report?.market_status === "OPEN"
      ? "Regular hours"
      : report
        ? "Session unverified"
        : "—";
  $("session-note").textContent = report?.session_basis==="REGULAR_HOURS_ESTIMATE"?"Regular-hours estimate · source evidence required":"Provider-reported regular hours";
  $("source-label").textContent = sample
    ? "SYNTHETIC SAMPLE"
    : report
      ? (report.source || "Provider unverified") + " · source timestamps required"
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
            `<article class="agent"><div class="agent-top"><h3>${i + 1}. ${esc(s.name)}</h3><span class="badge ${esc(s.status)}">${esc(s.status.toUpperCase())}</span></div><p>${s.status==="pass"?"Check confirmed.":s.status==="blocked"?"Required evidence unavailable or invalid.":"Not confirmed yet."}</p></article>`,
        )
        .join("")
    : '<div class="empty-state">Data steward → session guard → trend analyst → setup analyst → risk critic → review</div>';
  $("decision-note").textContent = "Market research is not an option order. Check data freshness, contract evidence and risk before acting.";
  chart();
  renderOptions();
  renderRisk();
  renderJournal();
}
function renderOptions() {
  const v = optionView(optionsResult);
  const indiaIndex = region === "IN" && ["NIFTY","BANKNIFTY","SENSEX"].includes($("symbol").value.trim().toUpperCase());
  const closed = regularSessionClosed();
  const decision = currentDecision();
  if (indiaIndex) {
    const ready = ["BIAS","WAIT","REVIEW"].includes(decision.state);
    const bias = decision.state==="BIAS" ? (report.verdict==="LONG_RESEARCH"?"CE":"PE") : null;
    $("options-title").textContent = closed ? "Last available chain" : bias ? "CE/PE contract not yet confirmed" : "No verified India contract";
    $("options-direction").textContent = closed ? "Last available data only — not live" : bias ? "Underlying directional bias only" :
      busy ? "Checking market data" : "No verified actionable setup";
    $("options-reason").textContent = closed ? "Regular session closed. Review last available option-chain data below. " + (optionsResult?.reason || "") : !ready ? "Market session or price freshness is not confirmed. No option entry." :
      (optionsResult?.reason || "Checking Indian option-chain evidence.") + " Executable option contract must be independently verified.";
  } else {
    $("options-title").textContent = closed ? "Market closed — last available data only" : decision.state==="REVIEW" ? "Contract available for review" : "No verified option entry";
    $("options-direction").textContent = v.direction;
    $("options-reason").textContent = v.reason;
  }
  const c = optionsResult?.candidate;
  const preview=optionsResult?.contractReview;
  if (indiaIndex) {
    const validPreview = decision.state==="BIAS" &&
      preview && Number.isFinite(preview.expires_at) && Date.now()/1000 < preview.expires_at &&
      preview.side === (report.verdict === "LONG_RESEARCH" ? "CE" : report.verdict === "BEARISH_RESEARCH" ? "PE" : "");
    $("options-contract").textContent = validPreview ?
      `${preview.contract} · Expiry ${preview.expiry} · Strike ₹${preview.strike} · Bid ₹${preview.bid} / Ask ₹${preview.ask} · Lot ${preview.lot_size} · Indicative premium ₹${preview.premium_per_lot} per lot · Exchange snapshot ${time(preview.feed_time)} · Broker verification required; no buy alert.` : "";
    return;
  }
  $("options-contract").textContent = decision.state==="REVIEW" && v.valid ?
    `${c.contract} · Expiry ${c.expiry} · Strike $${c.strike} · Bid $${c.bid} / ask $${c.ask}. `+
    `Bid time ${time(c.bid_time)}; ask time ${time(c.ask_time)}. `+
    `Maximum premium $${c.maximum_premium} per share; $${c.premium_at_risk} premium at risk per standard contract, plus costs. `+
    `Underlying invalidation $${c.underlying_invalidation}; underlying target $${c.underlying_target}. `+
    `Exit review on invalidation/target or before session end; no overnight plan. `+
    `Volume ${c.volume}; open interest ${c.open_interest}; delta ${c.delta}; IV ${c.iv}. `+
    `Greeks/IV estimate updated ${c.greeks_updated_at} (provider time, hourly; not live). `+
    `Skip stale quotes, widened spreads, changed setup or unchecked event risk. No quantity recommendation.` : '';
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
  lastScanAt = Date.now();
  if ($("auto-refresh").checked) nextScanAt = lastScanAt + refreshDelay();
  sample = false;
  report = null;
  optionsResult = null;
  $("chain-summary").textContent = "Waiting for verified option-chain coverage.";
  showEvidence([]);
  busy = true;
  const id = ++scanId,
    scanRegion = region;
  controller = new AbortController();
  const currentController = controller;
  const timeout = setTimeout(() => currentController.abort(), scanRegion === "IN" ? 45000 : 20000);
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
    if ($("auto-paper").checked) {
      $("auto-paper-status").textContent = autoPaper(activeAccount(), report, riskPct);
      persist();
    } else if ($("auto-exit").checked) {
      observedExits(activeAccount(), report);
      persist();
    }
    render();
    notify(d.reason);
    if (scanRegion === 'US' && ['SPY','QQQ'].includes(sym)) {
      try {
        const response = await fetch(`/api/trading-desk/options?symbol=${encodeURIComponent(sym)}&region=US`,
          {signal:currentController.signal,cache:'no-store'});
        if (!response.ok) throw Error('Options service unavailable.');
        const result = await response.json();
        if (id !== scanId) return;
        optionsResult = result;
      } catch {
        if (id !== scanId) return;
        optionsResult = {reason:'Options evidence unavailable; no buy signal.'};
      }
    } else if (scanRegion === "IN" && ["NIFTY","BANKNIFTY","SENSEX"].includes(sym)) {
      try {
        const response = await fetch(`/api/trading-desk/india-intelligence?symbol=${encodeURIComponent(sym)}`,
          {signal:currentController.signal,cache:"no-store"});
        if (!response.ok) throw Error(response.status === 401 || response.status === 403 ? "Sign in with verified full access to view Indian contracts." : "Indian option-chain provider unavailable.");
        const intel = await response.json();
        if (id !== scanId) return;
        optionsResult = {status:"WAIT",reason:intel.reason,contractReview:intel.contract_review || null};
        const details = intel.chain || {};
        $("chain-summary").textContent = details.available
          ? `${regularSessionClosed() ? "MARKET CLOSED · LAST AVAILABLE SNAPSHOT" : "OPTION-CHAIN SNAPSHOT (NOT EXECUTABLE QUOTES)"} · ${details.source || "Provider unknown"} · Latest exchange feed ${time(details.latest_exchange_time)} · Retrieved ${time(details.snapshot_fetched_at)} · Expiry ${details.expiry || "—"} · PCR ${details.pcr_oi ?? "—"} · CE OI wall ${details.highest_call_oi_strike ?? "—"} · PE OI wall ${details.highest_put_oi_strike ?? "—"} · OI changes CE ${details.total_call_oi_change ?? "—"} / PE ${details.total_put_oi_change ?? "—"}`
          : "Verified Indian option-chain snapshot unavailable.";
        showEvidence(intel.checks || []);
      } catch (error) {
        if (id !== scanId) return;
        optionsResult={status:"WAIT",reason:error?.message || "Indian contract evidence unavailable; no CE/PE buy alert."};
        $("chain-summary").textContent = "India chain could not be verified.";
        showEvidence([]);
      }
    } else optionsResult = {status:"WAIT",reason:scanRegion === "IN" ? "Indian stock options are not supported by this contract scanner. Select NIFTY, BANKNIFTY or SENSEX for index evidence." : "Verified US option contracts are supported for SPY and QQQ only."};
    // Final state is rendered after busy is cleared; alert uses the same classifier.
    alerts.process(report, optionsResult, regularSessionClosed());
  } catch (e) {
    if (id !== scanId) return;
    report = null;
  optionsResult = null;
    alerts.process({symbol:sym,region:scanRegion,verdict:"WAIT",reason:"Latest research request failed; evidence cannot be reconfirmed."}, null, regularSessionClosed());
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
      renderOptions();
      renderGuidance();
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
  nextScanAt = null;
  if ($("auto-refresh").checked) {
    nextScanAt = lastScanAt===null ? Date.now() : lastScanAt+refreshDelay();
    timer = setInterval(() => {
      if (!document.hidden && !sample && !busy && Date.now()>=nextScanAt) scan();
    }, 1000);
    notify(
      `Research refresh enabled every ${$("scan-cadence").value} minutes while this page is visible. Not continuous monitoring.`,
    );
  } else notify("Automatic refresh paused.");
  renderReadiness(); renderScanStatus();
});
$("scan-cadence").addEventListener("change", () => {
  if ($("auto-refresh").checked) $("auto-refresh").dispatchEvent(new Event("change"));
  renderReadiness();
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
  optionsResult = {reason: "Synthetic sample: options buy candidates are disabled."};
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
  renderOptions();
  renderGuidance();
  if (report && !sample) {
    $("freshness").textContent = fresh(report) ? "Recent timestamp" : "Stale / unknown";
    if (!fresh(report)) {
      $("verdict").textContent = regularSessionClosed() ? "Market closed" : "Data not current";
      $("verdict-note").textContent = "No new entry";
    }
    $("paper-button").disabled = !(
      sizing(report, activeAccount(), riskPct)?.qty > 0 && fresh(report)
    );
  }
}, 15000);
setInterval(() => {renderScanStatus(); if(!busy && !sample){renderGuidance();renderOptions();}},1000);
document.addEventListener("visibilitychange", () => { renderReadiness(); renderGuidance(); if (!document.hidden && !sample && $("auto-refresh").checked && !busy && (lastScanAt===null || Date.now()-lastScanAt>=refreshDelay())) scan(); });
function revealSection(hash) {
  if (!hash || !/^#[a-z][a-z0-9-]*$/i.test(hash)) return;
  const target=document.getElementById(hash.slice(1));
  for(let node=target;node;node=node.parentElement) {
    if(node.tagName==="DETAILS") node.open=true;
  }
}
document.addEventListener("click", (event)=>{
  const anchor=event.target.closest?.('a[href^="#"]');
  if(anchor) revealSection(anchor.getAttribute("href"));
});
window.addEventListener("hashchange",()=>revealSection(location.hash));
revealSection(location.hash);
watchlist();
render();
$("scan-cadence").value = "5";
$("auto-refresh").checked = true;
$("auto-refresh").dispatchEvent(new Event("change"));
scan();

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
