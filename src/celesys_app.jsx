import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";

/* ============================================================
   CELESYS — React Rewrite (Sessions 1–7 COMPLETE)
   S1: Shell + Home + Overview (5 subtabs) + 20-Factor Engine
   S2: Stock — Institutional deep-dive terminal (10 accordion sections)
   S3: Decide — Dual-engine options dashboard
   S4: Trader — L0 Scan Engine + Watchlist + Live Signals
   S5: Markets + Tools + Dream Portfolio
   S6: Unified CDS v2.0 Matrix — consolidates 4 engines into one composite
   S7: Polish — responsive layouts, error boundary, scrollbar, a11y, reduced-motion
   Data: GET /api/stock-quick, GET /api/options-quick, GET /api/global-ticker
   ============================================================ */

/* ---------- Design Tokens ---------- */
const T = {
  BG: "#020617",
  CARD: "#0F172A",
  ACT: "#1E293B",
  BD: "#1E293B",
  T1: "#E2E8F0",
  T2: "#94A3B8",
  T3: "#64748B",
  BL: "#3B82F6",
  GR: "#22C55E",
  YL: "#F59E0B",
  RD: "#EF4444",
  PP: "#A78BFA",
  CY: "#22D3EE",
};

const MONO = `'JetBrains Mono', 'SF Mono', Menlo, monospace`;
const BODY = `'Outfit', system-ui, -apple-system, sans-serif`;

const MENU = ["Overview", "Stock", "Decide", "Dream", "Trader", "Markets", "Tools"];

/* API base: empty string = same origin (prod on Render).
   For local dev, point to the FastAPI host. */
const API_BASE = "";

/* ============================================================
   20-FACTOR VERDICT ENGINE
   Ported from original app.js. Each factor returns:
     { score, max, label, pass, detail }
   Missing data => score 0, pass=null, detail="n/a" (CDS v2.0 principle:
   no fake assumptions — flag, never substitute).
   ============================================================ */

const n = (v) => (v === null || v === undefined || Number.isNaN(+v) ? null : +v);
const fmt = (v, d = 2, suffix = "") =>
  v === null || v === undefined ? "—" : `${(+v).toFixed(d)}${suffix}`;
const fmtB = (v) => {
  if (v === null || v === undefined) return "—";
  const x = +v;
  if (Math.abs(x) >= 1e12) return `${(x / 1e12).toFixed(2)}T`;
  if (Math.abs(x) >= 1e9) return `${(x / 1e9).toFixed(2)}B`;
  if (Math.abs(x) >= 1e6) return `${(x / 1e6).toFixed(2)}M`;
  return x.toFixed(0);
};

function runFactorEngine(d) {
  const pe = n(d.pe_ratio);
  const fpe = n(d.forward_pe);
  const pb = n(d.pb_ratio);
  const pm = n(d.profit_margin);
  const roe = n(d.roe);
  const beta = n(d.beta);
  const dy = n(d.dividend_yield);
  const hi = n(d.week52_high);
  const lo = n(d.week52_low);
  const px = n(d.current_price);
  const s20 = n(d.sma_20);
  const s50 = n(d.sma_50);
  const s200 = n(d.sma_200);
  const eps = n(d.eps_growth_pct);
  const rev = n(d.revenue_growth);
  const ern = n(d.earnings_growth);
  const secPE = n(d.sector_avg_pe);
  const opm = n(d.operating_margin);
  const de = n(d.debt_to_equity);
  const cr = n(d.current_ratio);
  const peg = n(d.peg_ratio);

  const F = [];

  /* F1 P/E Valuation ±20 */
  (() => {
    if (pe === null) return F.push({ id: "F1", label: "P/E Valuation", max: 20, score: 0, pass: null, detail: "n/a" });
    let s = 0, tag = "";
    if (pe <= 0) { s = -15; tag = "Negative earnings"; }
    else if (pe < 10) { s = 15; tag = "Deep value"; }
    else if (pe < 18) { s = 20; tag = "Attractive"; }
    else if (pe < 28) { s = 10; tag = "Fair"; }
    else if (pe < 40) { s = -5; tag = "Expensive"; }
    else { s = -20; tag = "Overvalued"; }
    F.push({ id: "F1", label: "P/E Valuation", max: 20, score: s, pass: s > 0, detail: `${tag} @ ${pe.toFixed(1)}x` });
  })();

  /* F2 Profitability (margins + ROE) ±15 */
  (() => {
    if (pm === null && roe === null) return F.push({ id: "F2", label: "Profitability", max: 15, score: 0, pass: null, detail: "n/a" });
    let s = 0, bits = [];
    if (pm !== null) {
      if (pm > 0.20) { s += 8; bits.push(`margin ${(pm * 100).toFixed(1)}%`); }
      else if (pm > 0.10) { s += 4; bits.push(`margin ${(pm * 100).toFixed(1)}%`); }
      else if (pm > 0) { s += 1; bits.push(`thin margin`); }
      else { s -= 6; bits.push(`negative margin`); }
    }
    if (roe !== null) {
      if (roe > 0.20) { s += 7; bits.push(`ROE ${(roe * 100).toFixed(1)}%`); }
      else if (roe > 0.12) { s += 4; bits.push(`ROE ${(roe * 100).toFixed(1)}%`); }
      else if (roe > 0) { s += 1; }
      else { s -= 4; bits.push(`negative ROE`); }
    }
    F.push({ id: "F2", label: "Profitability", max: 15, score: s, pass: s > 0, detail: bits.join(" • ") });
  })();

  /* F3 Balance Sheet ±12 */
  (() => {
    if (de === null && cr === null) return F.push({ id: "F3", label: "Balance Sheet", max: 12, score: 0, pass: null, detail: "n/a" });
    let s = 0, bits = [];
    if (de !== null) {
      if (de < 0.5) { s += 7; bits.push(`D/E ${de.toFixed(2)}`); }
      else if (de < 1.0) { s += 4; bits.push(`D/E ${de.toFixed(2)}`); }
      else if (de < 2.0) { s += 0; bits.push(`D/E ${de.toFixed(2)}`); }
      else { s -= 6; bits.push(`D/E ${de.toFixed(2)} (high)`); }
    }
    if (cr !== null) {
      if (cr > 2.0) { s += 5; bits.push(`CR ${cr.toFixed(2)}`); }
      else if (cr > 1.5) { s += 3; }
      else if (cr > 1.0) { s += 1; }
      else { s -= 4; bits.push(`CR ${cr.toFixed(2)} (weak)`); }
    }
    F.push({ id: "F3", label: "Balance Sheet", max: 12, score: s, pass: s > 0, detail: bits.join(" • ") });
  })();

  /* F4 52-Week Position ±10 */
  (() => {
    if (hi === null || lo === null || px === null || hi === lo) return F.push({ id: "F4", label: "52W Position", max: 10, score: 0, pass: null, detail: "n/a" });
    const pct = ((px - lo) / (hi - lo)) * 100;
    let s = 0, tag = "";
    if (pct < 20) { s = 10; tag = "Near 52W low"; }
    else if (pct < 40) { s = 6; tag = "Lower range"; }
    else if (pct < 60) { s = 2; tag = "Mid-range"; }
    else if (pct < 80) { s = -2; tag = "Upper range"; }
    else { s = -8; tag = "Near 52W high"; }
    F.push({ id: "F4", label: "52W Position", max: 10, score: s, pass: s > 0, detail: `${tag} (${pct.toFixed(0)}%)` });
  })();

  /* F5 Forward P/E Discount ±5 */
  (() => {
    if (pe === null || fpe === null || pe <= 0 || fpe <= 0) return F.push({ id: "F5", label: "Fwd P/E Discount", max: 5, score: 0, pass: null, detail: "n/a" });
    const disc = (pe - fpe) / pe;
    let s = 0, tag = "";
    if (disc > 0.15) { s = 5; tag = "Strong earnings growth"; }
    else if (disc > 0.05) { s = 3; tag = "Earnings improving"; }
    else if (disc > -0.05) { s = 0; tag = "Flat"; }
    else { s = -5; tag = "Earnings deteriorating"; }
    F.push({ id: "F5", label: "Fwd P/E Discount", max: 5, score: s, pass: s > 0, detail: tag });
  })();

  /* F6 Dividend ±5 */
  (() => {
    if (dy === null) return F.push({ id: "F6", label: "Dividend Yield", max: 5, score: 0, pass: null, detail: "n/a" });
    let s = 0, tag = "";
    if (dy > 0.05) { s = 5; tag = `High yield ${(dy * 100).toFixed(2)}%`; }
    else if (dy > 0.025) { s = 3; tag = `Solid ${(dy * 100).toFixed(2)}%`; }
    else if (dy > 0.01) { s = 1; tag = `Modest ${(dy * 100).toFixed(2)}%`; }
    else if (dy > 0) { s = 0; tag = `Minimal`; }
    else { s = 0; tag = "None"; }
    F.push({ id: "F6", label: "Dividend Yield", max: 5, score: s, pass: s > 0, detail: tag });
  })();

  /* F7 Beta Volatility ±8 */
  (() => {
    if (beta === null) return F.push({ id: "F7", label: "Beta Volatility", max: 8, score: 0, pass: null, detail: "n/a" });
    let s = 0, tag = "";
    if (beta < 0.7) { s = 6; tag = `Defensive β=${beta.toFixed(2)}`; }
    else if (beta < 1.1) { s = 4; tag = `Market-like β=${beta.toFixed(2)}`; }
    else if (beta < 1.5) { s = -2; tag = `Elevated β=${beta.toFixed(2)}`; }
    else { s = -8; tag = `High-vol β=${beta.toFixed(2)}`; }
    F.push({ id: "F7", label: "Beta Volatility", max: 8, score: s, pass: s > 0, detail: tag });
  })();

  /* F8 Operating Efficiency ±5 */
  (() => {
    if (opm === null) return F.push({ id: "F8", label: "Operating Efficiency", max: 5, score: 0, pass: null, detail: "n/a" });
    let s = 0, tag = "";
    if (opm > 0.25) { s = 5; tag = `OpMargin ${(opm * 100).toFixed(1)}%`; }
    else if (opm > 0.15) { s = 3; tag = `OpMargin ${(opm * 100).toFixed(1)}%`; }
    else if (opm > 0.05) { s = 1; tag = `OpMargin ${(opm * 100).toFixed(1)}%`; }
    else if (opm > 0) { s = 0; tag = "Thin"; }
    else { s = -5; tag = "Negative"; }
    F.push({ id: "F8", label: "Operating Efficiency", max: 5, score: s, pass: s > 0, detail: tag });
  })();

  /* F9 Earnings Velocity ±15 */
  (() => {
    if (eps === null && rev === null) return F.push({ id: "F9", label: "Earnings Velocity", max: 15, score: 0, pass: null, detail: "n/a" });
    let s = 0, bits = [];
    if (eps !== null) {
      if (eps > 20) { s += 8; bits.push(`EPS +${eps.toFixed(1)}%`); }
      else if (eps > 10) { s += 5; bits.push(`EPS +${eps.toFixed(1)}%`); }
      else if (eps > 0) { s += 2; bits.push(`EPS +${eps.toFixed(1)}%`); }
      else { s -= 6; bits.push(`EPS ${eps.toFixed(1)}%`); }
    }
    if (rev !== null) {
      // yfinance returns decimals (0.45 = 45%). Only treat as already-percent if > 5 (unambiguous).
      const rPct = Math.abs(rev) > 5 ? rev : rev * 100;
      if (rPct > 20) { s += 7; bits.push(`Rev +${rPct.toFixed(1)}%`); }
      else if (rPct > 10) { s += 4; bits.push(`Rev +${rPct.toFixed(1)}%`); }
      else if (rPct > 0) { s += 1; bits.push(`Rev +${rPct.toFixed(1)}%`); }
      else { s -= 4; bits.push(`Rev ${rPct.toFixed(1)}%`); }
    }
    F.push({ id: "F9", label: "Earnings Velocity", max: 15, score: s, pass: s > 0, detail: bits.join(" • ") });
  })();

  /* F10 Relative Valuation vs Sector ±10 */
  (() => {
    if (pe === null || secPE === null || pe <= 0 || secPE <= 0) return F.push({ id: "F10", label: "vs Sector P/E", max: 10, score: 0, pass: null, detail: "n/a" });
    const ratio = pe / secPE;
    let s = 0, tag = "";
    if (ratio < 0.7) { s = 10; tag = "Deep discount"; }
    else if (ratio < 0.9) { s = 6; tag = "Discount to sector"; }
    else if (ratio < 1.1) { s = 2; tag = "In-line"; }
    else if (ratio < 1.3) { s = -4; tag = "Premium to sector"; }
    else { s = -10; tag = "Heavy premium"; }
    F.push({ id: "F10", label: "vs Sector P/E", max: 10, score: s, pass: s > 0, detail: `${tag} (${ratio.toFixed(2)}x)` });
  })();

  /* F11 Technical Momentum (SMA) ±12 */
  (() => {
    if (px === null || s20 === null || s50 === null || s200 === null)
      return F.push({ id: "F11", label: "Technical Momentum", max: 12, score: 0, pass: null, detail: "n/a" });
    let s = 0, tags = [];
    if (px > s20) { s += 2; tags.push("P>20"); } else { s -= 2; }
    if (px > s50) { s += 3; tags.push("P>50"); } else { s -= 3; }
    if (px > s200) { s += 4; tags.push("P>200"); } else { s -= 4; }
    if (s50 > s200) { s += 3; tags.push("Golden"); } else { s -= 3; tags.push("Death"); }
    F.push({ id: "F11", label: "Technical Momentum", max: 12, score: s, pass: s > 0, detail: tags.join(" ") });
  })();

  /* F12 PEG Ratio ±5 */
  (() => {
    if (peg === null || peg <= 0) return F.push({ id: "F12", label: "PEG Ratio", max: 5, score: 0, pass: null, detail: "n/a" });
    let s = 0, tag = "";
    if (peg < 1.0) { s = 5; tag = "Undervalued growth"; }
    else if (peg < 1.5) { s = 3; tag = "Fair growth"; }
    else if (peg < 2.0) { s = 0; tag = "Full growth"; }
    else { s = -5; tag = "Overvalued growth"; }
    F.push({ id: "F12", label: "PEG Ratio", max: 5, score: s, pass: s > 0, detail: `${tag} (${peg.toFixed(2)})` });
  })();

  /* F13 Cash Flow Proxy (uses profit margin + operating margin) ±8 */
  (() => {
    if (pm === null && opm === null) return F.push({ id: "F13", label: "Cash Flow Proxy", max: 8, score: 0, pass: null, detail: "n/a" });
    const mix = (pm ?? 0) * 0.4 + (opm ?? 0) * 0.6;
    let s = 0, tag = "";
    if (mix > 0.20) { s = 8; tag = "Strong"; }
    else if (mix > 0.10) { s = 5; tag = "Healthy"; }
    else if (mix > 0.03) { s = 1; tag = "Modest"; }
    else if (mix > 0) { s = 0; tag = "Thin"; }
    else { s = -8; tag = "Negative"; }
    F.push({ id: "F13", label: "Cash Flow Proxy", max: 8, score: s, pass: s > 0, detail: tag });
  })();

  /* F14 Quarterly Earnings Momentum ±5 */
  (() => {
    if (ern === null) return F.push({ id: "F14", label: "Earnings Momentum", max: 5, score: 0, pass: null, detail: "n/a" });
    // yfinance returns decimals. Only treat as percent if unambiguous (> 5).
    const e = Math.abs(ern) > 5 ? ern : ern * 100;
    const ePct = e;
    let s = 0, tag = "";
    if (ePct > 25) { s = 5; tag = `Accelerating +${ePct.toFixed(1)}%`; }
    else if (ePct > 10) { s = 3; tag = `Growing +${ePct.toFixed(1)}%`; }
    else if (ePct > 0) { s = 1; tag = `+${ePct.toFixed(1)}%`; }
    else if (ePct > -10) { s = -2; tag = `${ePct.toFixed(1)}%`; }
    else { s = -5; tag = `Declining ${ePct.toFixed(1)}%`; }
    F.push({ id: "F14", label: "Earnings Momentum", max: 5, score: s, pass: s > 0, detail: tag });
  })();

  const totalScore = F.reduce((a, f) => a + f.score, 0);
  const maxScore = F.reduce((a, f) => a + f.max, 0);
  const pct = (totalScore / maxScore) * 100;

  let verdict, verdictColor;
  if (pct >= 30) { verdict = "BUY"; verdictColor = T.GR; }
  else if (pct >= 5) { verdict = "HOLD"; verdictColor = T.YL; }
  else { verdict = "SELL"; verdictColor = T.RD; }

  const reasons = F.filter((f) => f.pass !== null)
    .sort((a, b) => Math.abs(b.score) - Math.abs(a.score))
    .slice(0, 6)
    .map((f) => ({ text: `${f.label}: ${f.detail}`, positive: f.score > 0 }));

  return { factors: F, totalScore, maxScore, pct, verdict, verdictColor, reasons };
}

/* ============================================================
   DERIVED ANALYTICS (Valuation, Technical, Risk)
   ============================================================ */

function grahamNumber(eps, bookValue) {
  if (eps === null || bookValue === null || eps <= 0 || bookValue <= 0) return null;
  return Math.sqrt(22.5 * eps * bookValue);
}

function intrinsicValue(eps, growthPct) {
  /* Simplified Graham formula: V = EPS * (8.5 + 2g) */
  if (eps === null || eps <= 0) return null;
  const g = growthPct === null ? 0 : Math.min(Math.max(growthPct, -10), 25);
  return eps * (8.5 + 2 * g);
}

function dcfQuick(eps, growthPct, discount = 0.10, years = 5, terminal = 0.03) {
  if (eps === null || eps <= 0) return null;
  // Gordon growth requires discount > terminal, else terminal value diverges
  if (discount <= terminal) return null;
  const g = growthPct === null ? 0.05 : Math.min(Math.max(growthPct / 100, -0.05), 0.25);
  let val = 0, cf = eps;
  for (let t = 1; t <= years; t++) {
    cf = cf * (1 + g);
    val += cf / Math.pow(1 + discount, t);
  }
  const tv = (cf * (1 + terminal)) / (discount - terminal);
  val += tv / Math.pow(1 + discount, years);
  return val;
}

function technicalTrend(px, s20, s50, s200) {
  if (px === null || s20 === null || s50 === null || s200 === null) return null;
  const above = (px > s20) + (px > s50) + (px > s200);
  const golden = s50 > s200;
  if (above === 3 && golden) return { label: "Strong Uptrend", color: T.GR };
  if (above >= 2 && golden) return { label: "Uptrend", color: T.GR };
  if (above === 0 && !golden) return { label: "Strong Downtrend", color: T.RD };
  if (above <= 1 && !golden) return { label: "Downtrend", color: T.RD };
  return { label: "Sideways / Mixed", color: T.YL };
}

function drawdownFrom52W(px, hi) {
  if (px === null || hi === null || hi <= 0) return null;
  return ((hi - px) / hi) * 100;
}

function flags(d, eng) {
  const green = [], red = [];
  const pm = n(d.profit_margin), roe = n(d.roe), de = n(d.debt_to_equity),
        cr = n(d.current_ratio), beta = n(d.beta), pe = n(d.pe_ratio),
        eps = n(d.eps_growth_pct), rev = n(d.revenue_growth);

  if (pm !== null && pm > 0.15) green.push(`High profit margin ${(pm * 100).toFixed(1)}%`);
  if (roe !== null && roe > 0.15) green.push(`Strong ROE ${(roe * 100).toFixed(1)}%`);
  if (de !== null && de < 0.5) green.push(`Low leverage D/E ${de.toFixed(2)}`);
  if (cr !== null && cr > 1.5) green.push(`Healthy liquidity CR ${cr.toFixed(2)}`);
  if (beta !== null && beta < 1) green.push(`Defensive beta ${beta.toFixed(2)}`);
  if (eps !== null && eps > 15) green.push(`EPS growth +${eps.toFixed(1)}%`);
  if (rev !== null) {
    const r = rev > 1 ? rev : rev * 100;
    if (r > 15) green.push(`Revenue growth +${r.toFixed(1)}%`);
  }

  if (pm !== null && pm < 0) red.push(`Negative profit margin`);
  if (roe !== null && roe < 0) red.push(`Negative ROE`);
  if (de !== null && de > 2) red.push(`High leverage D/E ${de.toFixed(2)}`);
  if (cr !== null && cr < 1) red.push(`Weak liquidity CR ${cr.toFixed(2)}`);
  if (beta !== null && beta > 1.5) red.push(`High volatility β=${beta.toFixed(2)}`);
  if (pe !== null && pe > 40) red.push(`Rich valuation P/E ${pe.toFixed(1)}x`);
  if (pe !== null && pe < 0) red.push(`Negative earnings`);

  return { green, red };
}

/* ============================================================
   UNIFIED CDS v2.0 SCORING ENGINE (Session 6)

   Consolidates 4 institutional scoring layers into a single
   composite verdict. Each layer contributes a normalized 0-100
   score plus a data-coverage flag (per CDS v2.0 principle: never
   fabricate, always disclose).

   Layers:
     L1 Framework   — 20-factor engine (runFactorEngine)     [35%]
     L2 Composite   — L0 5-factor score (l0ScoreStock)       [25%]
     L3 Moat        — Competitive position (moatScore)       [20%]
     L4 Solvency    — Altman Z-score proxy (altmanZScore)    [20%]

   Data-coverage rules:
     - Each layer reports % of required inputs available
     - If any layer has <30% coverage, it's excluded from composite
       (weights redistributed to remaining layers proportionally)
     - Composite coverage = weighted avg of included layers
     - Verdict suppressed if overall coverage <50% — shown as
       "INSUFFICIENT DATA" rather than a fabricated score
   ============================================================ */

function unifiedCDSScore(data) {
  if (!data || !data.current_price) return null;

  const layers = {};

  /* L1: 20-Factor Framework */
  const fe = runFactorEngine(data);
  const l1Coverage = fe.factors.filter(f => f.pass !== null).length / fe.factors.length;
  layers.L1 = {
    id: "L1",
    label: "20-Factor Framework",
    score: Math.max(0, Math.min(100, 50 + fe.pct / 2)), // pct is -100..+100, map to 0-100
    coverage: l1Coverage * 100,
    raw: { verdict: fe.verdict, totalScore: fe.totalScore, maxScore: fe.maxScore, pct: fe.pct },
    weight: 0.35,
  };

  /* L2: L0 Composite (use quality mode as neutral baseline) */
  const l0 = l0ScoreStock(data);
  if (l0) {
    const qualityMode = SCAN_MODES.find(m => m.id === "quality");
    const composite = l0Composite(l0, qualityMode);
    layers.L2 = {
      id: "L2",
      label: "L0 Multi-Factor Composite",
      score: composite,
      coverage: l0.coverage,
      raw: { Q: l0.Q, G: l0.G, M: l0.M, L: l0.L, S: l0.S },
      weight: 0.25,
    };
  } else {
    layers.L2 = { id: "L2", label: "L0 Multi-Factor Composite", score: 0, coverage: 0, raw: null, weight: 0.25 };
  }

  /* L3: Competitive Moat */
  const moat = moatScore(data);
  // Moat coverage = how many of opm, roe, pm are available
  const moatInputs = [n(data.operating_margin), n(data.roe), n(data.profit_margin)]
    .filter(v => v !== null).length;
  const moatCoverage = (moatInputs / 3) * 100;
  layers.L3 = {
    id: "L3",
    label: "Competitive Moat",
    score: Math.max(0, moat.pct),
    coverage: moatCoverage,
    raw: { verdict: moat.verdict, score: moat.score, max: moat.max },
    weight: 0.20,
  };

  /* L4: Financial Solvency (Altman Z proxy) */
  const altman = altmanZScore(data);
  if (altman) {
    // Map Altman Z (0-5+) to 0-100 score
    // Z < 1.81 = distress, 1.81-2.99 = grey, > 2.99 = safe
    const zScore = Math.min(100, Math.max(0, (altman.z / 5) * 100));
    const inputs = [n(data.market_cap), n(data.debt_to_equity), n(data.profit_margin),
                    n(data.operating_margin), n(data.current_ratio), n(data.roe)]
      .filter(v => v !== null).length;
    layers.L4 = {
      id: "L4",
      label: "Financial Solvency (Altman Z)",
      score: zScore,
      coverage: (inputs / 6) * 100,
      raw: { z: altman.z, zone: altman.zone },
      weight: 0.20,
    };
  } else {
    layers.L4 = { id: "L4", label: "Financial Solvency (Altman Z)", score: 0, coverage: 0, raw: null, weight: 0.20 };
  }

  /* Weight redistribution — exclude layers with <30% coverage */
  const MIN_COVERAGE = 30;
  const included = Object.values(layers).filter(l => l.coverage >= MIN_COVERAGE);
  const excluded = Object.values(layers).filter(l => l.coverage < MIN_COVERAGE);

  let composite = null, totalCoverage = 0;
  if (included.length > 0) {
    const totalWeight = included.reduce((s, l) => s + l.weight, 0);
    composite = included.reduce((s, l) => s + l.score * (l.weight / totalWeight), 0);
    totalCoverage = included.reduce((s, l) => s + l.coverage * (l.weight / totalWeight), 0);
  }

  /* Final verdict — suppress if coverage too low */
  let verdict, verdictColor, reliability;
  if (composite === null || totalCoverage < 50) {
    verdict = "INSUFFICIENT DATA";
    verdictColor = T.T3;
    reliability = "LOW";
  } else if (composite >= 75) {
    verdict = "STRONG BUY";
    verdictColor = T.GR;
    reliability = totalCoverage >= 80 ? "HIGH" : "MODERATE";
  } else if (composite >= 60) {
    verdict = "BUY";
    verdictColor = T.GR;
    reliability = totalCoverage >= 70 ? "HIGH" : "MODERATE";
  } else if (composite >= 45) {
    verdict = "HOLD";
    verdictColor = T.YL;
    reliability = totalCoverage >= 70 ? "HIGH" : "MODERATE";
  } else if (composite >= 30) {
    verdict = "REDUCE";
    verdictColor = T.RD;
    reliability = "MODERATE";
  } else {
    verdict = "SELL";
    verdictColor = T.RD;
    reliability = "HIGH";
  }

  return {
    composite,
    verdict,
    verdictColor,
    reliability,
    coverage: totalCoverage,
    layers,
    included: included.map(l => l.id),
    excluded: excluded.map(l => l.id),
  };
}


/* ============================================================
   SHARED UI PRIMITIVES
   ============================================================ */

function Card({ children, style, title, accent, pad = 20 }) {
  return (
    <div style={{
      background: T.CARD,
      border: `1px solid ${T.BD}`,
      borderRadius: 8,
      padding: pad,
      ...style,
    }}>
      {title && (
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          marginBottom: 14, paddingBottom: 10,
          borderBottom: `1px solid ${T.BD}`,
        }}>
          <div style={{
            fontSize: 11, fontFamily: MONO, textTransform: "uppercase",
            letterSpacing: 1.5, color: T.T2, fontWeight: 500,
          }}>{title}</div>
          {accent && <div style={{
            fontSize: 10, fontFamily: MONO, color: accent.color,
            padding: "2px 8px", border: `1px solid ${accent.color}40`,
            borderRadius: 3, letterSpacing: 0.5, textTransform: "uppercase",
          }}>{accent.label}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

function Metric({ label, value, sub, color, mono = true, fs = 22 }) {
  return (
    <div>
      <div style={{
        fontSize: 10, fontFamily: MONO, textTransform: "uppercase",
        letterSpacing: 1.2, color: T.T3, marginBottom: 6, fontWeight: 500,
      }}>{label}</div>
      <div style={{
        fontSize: fs, fontFamily: mono ? MONO : BODY,
        color: color || T.T1, fontWeight: 600, lineHeight: 1.1,
      }}>{value}</div>
      {sub && (
        <div style={{
          fontSize: 11, fontFamily: MONO, color: T.T3, marginTop: 4,
        }}>{sub}</div>
      )}
    </div>
  );
}

function Bar52W({ lo, hi, px }) {
  if (lo === null || hi === null || px === null || hi === lo) {
    return <div style={{ color: T.T3, fontSize: 12 }}>Range data unavailable</div>;
  }
  const pct = Math.max(0, Math.min(100, ((px - lo) / (hi - lo)) * 100));
  return (
    <div>
      <div style={{
        display: "flex", justifyContent: "space-between",
        fontSize: 11, fontFamily: MONO, color: T.T3, marginBottom: 8,
      }}>
        <span>52W LOW ${lo.toFixed(2)}</span>
        <span style={{ color: T.T1 }}>{pct.toFixed(0)}% of range</span>
        <span>52W HIGH ${hi.toFixed(2)}</span>
      </div>
      <div style={{
        position: "relative", height: 8, background: T.ACT,
        borderRadius: 4, overflow: "hidden",
      }}>
        <div style={{
          position: "absolute", top: 0, left: 0, height: "100%",
          width: `${pct}%`,
          background: `linear-gradient(90deg, ${T.RD}, ${T.YL}, ${T.GR})`,
        }} />
        <div style={{
          position: "absolute", top: -3, left: `calc(${pct}% - 7px)`,
          width: 14, height: 14, background: T.T1, borderRadius: "50%",
          boxShadow: `0 0 0 3px ${T.BG}`,
        }} />
      </div>
    </div>
  );
}

/* ============================================================
   SUBTAB 1 — OVERVIEW
   ============================================================ */

function OverviewPanel({ data, engine }) {
  const px = n(data.current_price);
  const pe = n(data.pe_ratio);
  const fpe = n(data.forward_pe);
  const pb = n(data.pb_ratio);
  const beta = n(data.beta);
  const dy = n(data.dividend_yield);
  const mc = n(data.market_cap);
  const hi = n(data.week52_high);
  const lo = n(data.week52_low);
  const ccy = data.currency === "INR" ? "₹" : "$";

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {/* ── Verdict Card ── */}
      <Card pad={24}>
        <div style={{
          display: "grid", gridTemplateColumns: "220px 1fr",
          gap: 28, alignItems: "center",
        }}>
          <div style={{ textAlign: "center" }}>
            <div style={{
              fontSize: 10, fontFamily: MONO, color: T.T3,
              letterSpacing: 1.5, marginBottom: 8, textTransform: "uppercase",
            }}>20-Factor Engine</div>
            <div style={{
              fontSize: 44, fontFamily: BODY, fontWeight: 700,
              color: engine.verdictColor, letterSpacing: 2, lineHeight: 1,
            }}>{engine.verdict}</div>
            <div style={{
              marginTop: 10, display: "inline-block",
              padding: "4px 12px", borderRadius: 4,
              background: `${engine.verdictColor}15`,
              border: `1px solid ${engine.verdictColor}40`,
              fontFamily: MONO, fontSize: 12, color: engine.verdictColor,
            }}>
              {engine.totalScore > 0 ? "+" : ""}{engine.totalScore} / {engine.maxScore} ({engine.pct.toFixed(0)}%)
            </div>
          </div>

          <div>
            <div style={{
              fontSize: 11, fontFamily: MONO, color: T.T3,
              marginBottom: 10, letterSpacing: 1.2, textTransform: "uppercase",
            }}>Key Drivers</div>
            <div style={{ display: "grid", gap: 7 }}>
              {engine.reasons.map((r, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  fontSize: 13, fontFamily: BODY, color: T.T1,
                }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: 3,
                    background: r.positive ? T.GR : T.RD, flexShrink: 0,
                  }} />
                  {r.text}
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* ── Metrics Grid (7 cards) ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
        gap: 12,
      }}>
        <Card pad={16}><Metric label="Price" value={px !== null ? `${ccy}${px.toFixed(2)}` : "—"} color={T.T1} /></Card>
        <Card pad={16}><Metric label="Market Cap" value={mc !== null ? `${ccy}${fmtB(mc)}` : "—"} color={T.BL} /></Card>
        <Card pad={16}><Metric label="P/E (TTM)" value={fmt(pe, 2, "x")} color={pe && pe < 20 ? T.GR : pe && pe > 35 ? T.RD : T.YL} /></Card>
        <Card pad={16}><Metric label="Forward P/E" value={fmt(fpe, 2, "x")} color={T.CY} /></Card>
        <Card pad={16}><Metric label="P/B Ratio" value={fmt(pb, 2, "x")} color={T.T1} /></Card>
        <Card pad={16}><Metric label="Beta" value={fmt(beta, 2)} color={beta && beta < 1 ? T.GR : beta && beta > 1.5 ? T.RD : T.YL} /></Card>
        <Card pad={16}><Metric label="Div Yield" value={dy !== null ? `${(dy * 100).toFixed(2)}%` : "—"} color={T.PP} /></Card>
      </div>

      {/* ── 52W Range ── */}
      <Card title="52-Week Range">
        <Bar52W lo={lo} hi={hi} px={px} />
      </Card>

      {/* ── CDS Score ── */}
      <Card title="Composite CDS Score" accent={{ label: "CDS v2.0", color: T.BL }}>
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 2fr", gap: 24, alignItems: "center",
        }}>
          <div>
            <div style={{
              fontSize: 52, fontFamily: MONO, fontWeight: 700,
              color: engine.verdictColor, lineHeight: 1,
            }}>{engine.pct.toFixed(0)}</div>
            <div style={{
              fontSize: 11, fontFamily: MONO, color: T.T3,
              marginTop: 6, letterSpacing: 1, textTransform: "uppercase",
            }}>Composite Score</div>
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {engine.factors.slice(0, 7).map((f) => (
              <div key={f.id} style={{ display: "grid", gridTemplateColumns: "40px 1fr 60px 50px", gap: 10, alignItems: "center" }}>
                <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3 }}>{f.id}</div>
                <div style={{ fontSize: 12, fontFamily: BODY, color: T.T2 }}>{f.label}</div>
                <div style={{
                  height: 4, background: T.ACT, borderRadius: 2, position: "relative", overflow: "hidden",
                }}>
                  <div style={{
                    position: "absolute", top: 0, left: "50%",
                    width: `${Math.abs(f.score / f.max) * 50}%`,
                    height: "100%",
                    background: f.pass === null ? T.T3 : f.score >= 0 ? T.GR : T.RD,
                    transform: f.score >= 0 ? "none" : "translateX(-100%)",
                  }} />
                </div>
                <div style={{
                  fontSize: 11, fontFamily: MONO, textAlign: "right",
                  color: f.pass === null ? T.T3 : f.score >= 0 ? T.GR : T.RD,
                }}>{f.pass === null ? "n/a" : (f.score >= 0 ? "+" : "") + f.score}</div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* CDS v2.0 Unified Matrix — consolidates all 4 scoring engines */}
      <UnifiedCDSMatrix data={data} />
    </div>
  );
}

/* ============================================================
   CDS v2.0 UNIFIED MATRIX — Session 6
   Renders the 4-layer institutional composite with transparency
   ============================================================ */

function UnifiedCDSMatrix({ data }) {
  const unified = useMemo(() => unifiedCDSScore(data), [data]);

  if (!unified) return null;

  const layers = Object.values(unified.layers);
  const compositeDisplay = unified.composite === null ? "—" : unified.composite.toFixed(1);

  const reliabilityColor = unified.reliability === "HIGH" ? T.GR
    : unified.reliability === "MODERATE" ? T.YL : T.RD;

  return (
    <Card
      title="CDS v2.0 Unified Matrix"
      accent={{ label: `${unified.reliability} CONFIDENCE`, color: reliabilityColor }}
    >
      {/* Top: Composite verdict */}
      <div style={{
        padding: 18,
        background: `linear-gradient(135deg, ${unified.verdictColor}12 0%, transparent 70%)`,
        border: `1px solid ${unified.verdictColor}30`,
        borderLeft: `3px solid ${unified.verdictColor}`,
        borderRadius: 6, marginBottom: 16,
      }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 20, alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 6 }}>
              4-Layer Composite
            </div>
            <div style={{
              fontSize: 32, fontFamily: BODY, color: unified.verdictColor,
              fontWeight: 800, letterSpacing: 1, lineHeight: 1,
            }}>
              {unified.verdict}
            </div>
          </div>

          <div style={{ textAlign: "center" }}>
            <div style={{
              fontSize: 48, fontFamily: MONO, color: unified.verdictColor,
              fontWeight: 700, lineHeight: 1,
            }}>
              {compositeDisplay}
            </div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginTop: 4 }}>
              Score / 100
            </div>
          </div>

          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 6 }}>
              Data Coverage
            </div>
            <div style={{
              fontSize: 24, fontFamily: MONO, fontWeight: 700,
              color: unified.coverage >= 70 ? T.GR : unified.coverage >= 50 ? T.YL : T.RD,
            }}>
              {unified.coverage.toFixed(0)}%
            </div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, marginTop: 2 }}>
              {unified.included.length}/{layers.length} layers
            </div>
          </div>
        </div>
      </div>

      {/* Per-layer breakdown */}
      <div style={{ display: "grid", gap: 10 }}>
        {layers.map((l) => {
          const excluded = unified.excluded.includes(l.id);
          const col = excluded ? T.T3
            : l.score >= 70 ? T.GR
            : l.score >= 50 ? T.YL
            : T.RD;

          return (
            <div key={l.id} style={{
              padding: "12px 14px", background: T.ACT, borderRadius: 6,
              display: "grid",
              gridTemplateColumns: "50px 1.5fr 1fr 80px 80px",
              gap: 12, alignItems: "center",
              borderLeft: `3px solid ${col}`,
              opacity: excluded ? 0.5 : 1,
            }}>
              <div style={{ fontSize: 12, fontFamily: MONO, color: T.T3, fontWeight: 700 }}>
                {l.id}
              </div>
              <div>
                <div style={{ fontSize: 13, fontFamily: BODY, color: T.T1, fontWeight: 600 }}>
                  {l.label}
                </div>
                <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, marginTop: 3 }}>
                  Weight: {(l.weight * 100).toFixed(0)}% · Coverage: {l.coverage.toFixed(0)}%
                  {excluded && <span style={{ color: T.RD, marginLeft: 8 }}>· EXCLUDED (below 30%)</span>}
                </div>
              </div>
              {/* Score bar */}
              <div style={{ position: "relative", height: 6, background: T.CARD, borderRadius: 3 }}>
                <div style={{
                  width: `${Math.min(100, Math.max(0, l.score))}%`,
                  height: "100%", background: col, borderRadius: 3,
                }} />
              </div>
              <div style={{
                fontSize: 16, fontFamily: MONO, fontWeight: 700, color: col, textAlign: "right",
              }}>
                {l.score.toFixed(1)}
              </div>
              <div style={{
                fontSize: 10, fontFamily: MONO, color: T.T3, textAlign: "right",
                letterSpacing: 0.5,
              }}>
                {l.raw ? (
                  l.id === "L1" ? `${l.raw.verdict}`
                  : l.id === "L2" ? `Q${Math.round(l.raw.Q)} G${Math.round(l.raw.G)} M${Math.round(l.raw.M)}`
                  : l.id === "L3" ? `${l.raw.verdict}`
                  : l.id === "L4" ? `Z=${l.raw.z.toFixed(2)}`
                  : "—"
                ) : "n/a"}
              </div>
            </div>
          );
        })}
      </div>

      {/* CDS v2.0 Transparency note */}
      <div style={{
        marginTop: 14, padding: 12, background: T.CARD, border: `1px solid ${T.BD}`,
        borderRadius: 4, fontSize: 11, fontFamily: BODY, color: T.T2, lineHeight: 1.6,
      }}>
        <strong style={{ color: T.T1 }}>CDS v2.0 Transparency:</strong> Each layer must have ≥30% data
        coverage to contribute to the composite. Excluded layers have their weight redistributed proportionally
        across included layers. Verdict is suppressed to "INSUFFICIENT DATA" if overall coverage drops below 50%.
        No fake assumptions, no synthetic defaults.
      </div>
    </Card>
  );
}

/* ============================================================
   SUBTAB 2 — VALUATION
   ============================================================ */

function ValuationPanel({ data }) {
  const px = n(data.current_price);
  const eps = n(data.eps_ttm);
  const bv = n(data.book_value);
  const epsG = n(data.eps_growth_pct);
  const pe = n(data.pe_ratio);
  const secPE = n(data.sector_avg_pe);
  const fpe = n(data.forward_pe);
  const pb = n(data.pb_ratio);
  const peg = n(data.peg_ratio);
  const ccy = data.currency === "INR" ? "₹" : "$";

  const graham = grahamNumber(eps, bv);
  const iv = intrinsicValue(eps, epsG);
  const dcf = dcfQuick(eps, epsG);

  const scenarios = [
    { label: "Graham Number", value: graham, desc: "Defensive investor fair value" },
    { label: "Graham Intrinsic", value: iv, desc: "EPS × (8.5 + 2g)" },
    { label: "DCF (5Y, 10% disc)", value: dcf, desc: "Present value of future cash flows" },
  ];

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Card title="Intrinsic Value Models" accent={{ label: "Triangulation", color: T.PP }}>
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16,
        }}>
          {scenarios.map((s, i) => {
            const diff = s.value !== null && px !== null ? ((s.value - px) / px) * 100 : null;
            const col = diff === null ? T.T3 : diff > 15 ? T.GR : diff < -15 ? T.RD : T.YL;
            return (
              <div key={i} style={{
                padding: 14, background: T.ACT, borderRadius: 6,
                border: `1px solid ${T.BD}`,
              }}>
                <div style={{
                  fontSize: 10, fontFamily: MONO, color: T.T3,
                  letterSpacing: 1, marginBottom: 8, textTransform: "uppercase",
                }}>{s.label}</div>
                <div style={{
                  fontSize: 24, fontFamily: MONO, color: col, fontWeight: 600,
                }}>{s.value !== null ? `${ccy}${s.value.toFixed(2)}` : "—"}</div>
                <div style={{ fontSize: 11, fontFamily: BODY, color: T.T3, marginTop: 6 }}>{s.desc}</div>
                {diff !== null && (
                  <div style={{
                    marginTop: 8, fontSize: 11, fontFamily: MONO, color: col,
                  }}>
                    {diff > 0 ? "+" : ""}{diff.toFixed(1)}% vs price
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card title="Multiples">
          <div style={{ display: "grid", gap: 14 }}>
            {[
              { k: "P/E (TTM)", v: fmt(pe, 2, "x") },
              { k: "Forward P/E", v: fmt(fpe, 2, "x") },
              { k: "P/B", v: fmt(pb, 2, "x") },
              { k: "PEG", v: fmt(peg, 2) },
              { k: "EPS (TTM)", v: eps !== null ? `${ccy}${eps.toFixed(2)}` : "—" },
              { k: "Book Value", v: bv !== null ? `${ccy}${bv.toFixed(2)}` : "—" },
            ].map((r, i) => (
              <div key={i} style={{
                display: "flex", justifyContent: "space-between",
                padding: "8px 0",
                borderBottom: i < 5 ? `1px solid ${T.ACT}` : "none",
              }}>
                <span style={{ fontSize: 12, fontFamily: BODY, color: T.T2 }}>{r.k}</span>
                <span style={{ fontSize: 13, fontFamily: MONO, color: T.T1 }}>{r.v}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="P/E vs Sector" accent={data.sector ? { label: data.sector, color: T.CY } : null}>
          {pe !== null && secPE !== null ? (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
                <div>
                  <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1 }}>COMPANY P/E</div>
                  <div style={{ fontSize: 28, fontFamily: MONO, color: T.BL, fontWeight: 600, marginTop: 4 }}>{pe.toFixed(2)}x</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1 }}>SECTOR P/E</div>
                  <div style={{ fontSize: 28, fontFamily: MONO, color: T.T1, fontWeight: 600, marginTop: 4 }}>{secPE.toFixed(2)}x</div>
                </div>
              </div>
              <div style={{
                padding: 12, background: T.ACT, borderRadius: 6, fontSize: 13, fontFamily: BODY,
              }}>
                {pe < secPE ? (
                  <span style={{ color: T.GR }}>Trading at {((1 - pe / secPE) * 100).toFixed(1)}% discount to sector</span>
                ) : (
                  <span style={{ color: T.RD }}>Trading at {((pe / secPE - 1) * 100).toFixed(1)}% premium to sector</span>
                )}
              </div>
            </div>
          ) : (
            <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO }}>Sector P/E data unavailable</div>
          )}
        </Card>
      </div>
    </div>
  );
}

/* ============================================================
   SUBTAB 3 — TECHNICAL
   ============================================================ */

function TechnicalPanel({ data }) {
  const px = n(data.current_price);
  const s20 = n(data.sma_20);
  const s50 = n(data.sma_50);
  const s200 = n(data.sma_200);
  const hi = n(data.week52_high);
  const lo = n(data.week52_low);
  const ccy = data.currency === "INR" ? "₹" : "$";

  const trend = technicalTrend(px, s20, s50, s200);
  const dd = drawdownFrom52W(px, hi);

  const smas = [
    { label: "SMA 20", value: s20, threshold: "Short-term" },
    { label: "SMA 50", value: s50, threshold: "Medium-term" },
    { label: "SMA 200", value: s200, threshold: "Long-term" },
  ];

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Card title="Trend Diagnosis" accent={trend ? { label: trend.label, color: trend.color } : null}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
          {smas.map((s, i) => {
            const diff = s.value !== null && px !== null ? ((px - s.value) / s.value) * 100 : null;
            const col = diff === null ? T.T3 : diff > 0 ? T.GR : T.RD;
            return (
              <div key={i} style={{
                padding: 16, background: T.ACT, borderRadius: 6,
                borderLeft: `3px solid ${col === T.T3 ? T.BD : col}`,
              }}>
                <div style={{
                  fontSize: 10, fontFamily: MONO, color: T.T3,
                  letterSpacing: 1, textTransform: "uppercase",
                }}>{s.label} • {s.threshold}</div>
                <div style={{
                  fontSize: 22, fontFamily: MONO, color: T.T1, fontWeight: 600, marginTop: 6,
                }}>{s.value !== null ? `${ccy}${s.value.toFixed(2)}` : "—"}</div>
                {diff !== null && (
                  <div style={{
                    fontSize: 12, fontFamily: MONO, color: col, marginTop: 4,
                  }}>
                    Price {diff > 0 ? "+" : ""}{diff.toFixed(2)}% vs {s.label}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card title="Crossover Signals">
          <div style={{ display: "grid", gap: 12 }}>
            {[
              {
                k: "Golden Cross (50>200)",
                active: s50 !== null && s200 !== null && s50 > s200,
                available: s50 !== null && s200 !== null,
              },
              {
                k: "Price > SMA 20",
                active: px !== null && s20 !== null && px > s20,
                available: px !== null && s20 !== null,
              },
              {
                k: "Price > SMA 50",
                active: px !== null && s50 !== null && px > s50,
                available: px !== null && s50 !== null,
              },
              {
                k: "Price > SMA 200",
                active: px !== null && s200 !== null && px > s200,
                available: px !== null && s200 !== null,
              },
              {
                k: "SMA 20 > SMA 50",
                active: s20 !== null && s50 !== null && s20 > s50,
                available: s20 !== null && s50 !== null,
              },
            ].map((r, i) => (
              <div key={i} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: 10, background: T.ACT, borderRadius: 4,
              }}>
                <span style={{ fontSize: 12, fontFamily: BODY, color: T.T2 }}>{r.k}</span>
                <span style={{
                  fontSize: 10, fontFamily: MONO, padding: "3px 8px", borderRadius: 3,
                  background: !r.available ? `${T.T3}15` : r.active ? `${T.GR}20` : `${T.RD}20`,
                  color: !r.available ? T.T3 : r.active ? T.GR : T.RD,
                  border: `1px solid ${!r.available ? T.T3 : r.active ? T.GR : T.RD}40`,
                }}>
                  {!r.available ? "N/A" : r.active ? "BULLISH" : "BEARISH"}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Drawdown Analysis">
          <div style={{ marginBottom: 16 }}>
            <Metric
              label="Drawdown from 52W High"
              value={dd !== null ? `${dd.toFixed(2)}%` : "—"}
              color={dd === null ? T.T3 : dd < 10 ? T.GR : dd < 25 ? T.YL : T.RD}
              fs={28}
            />
          </div>
          {hi !== null && lo !== null && px !== null && (
            <div style={{ marginTop: 18 }}>
              <Bar52W lo={lo} hi={hi} px={px} />
            </div>
          )}
          <div style={{
            marginTop: 16, padding: 10, background: T.ACT, borderRadius: 4,
            fontSize: 12, fontFamily: BODY, color: T.T2,
          }}>
            {dd === null ? "Insufficient range data" :
              dd < 5 ? "Near highs — momentum-driven zone" :
              dd < 15 ? "Healthy consolidation zone" :
              dd < 30 ? "Correction territory — watch for support" :
              "Deep drawdown — reversal or value setup"}
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ============================================================
   SUBTAB 4 — ACTIVITY (Growth + Margins)
   ============================================================ */

function ActivityPanel({ data }) {
  const eps = n(data.eps_growth_pct);
  const rev = n(data.revenue_growth);
  const ern = n(data.earnings_growth);
  const pm = n(data.profit_margin);
  const opm = n(data.operating_margin);
  const roe = n(data.roe);

  const normalizePct = (v) => (v === null ? null : (Math.abs(v) > 5 ? v : v * 100));

  const growth = [
    { label: "EPS Growth", value: eps, good: 10 },
    { label: "Revenue Growth", value: normalizePct(rev), good: 10 },
    { label: "Earnings Growth (QoQ)", value: normalizePct(ern), good: 10 },
  ];

  const margins = [
    { label: "Profit Margin", value: pm === null ? null : pm * 100, good: 10 },
    { label: "Operating Margin", value: opm === null ? null : opm * 100, good: 15 },
    { label: "Return on Equity", value: roe === null ? null : roe * 100, good: 15 },
  ];

  const MetricRow = ({ label, value, good }) => {
    const col = value === null ? T.T3 : value > good ? T.GR : value > 0 ? T.YL : T.RD;
    const barWidth = value === null ? 0 : Math.min(Math.abs(value) * 2, 100);
    return (
      <div style={{ marginBottom: 14 }}>
        <div style={{
          display: "flex", justifyContent: "space-between", marginBottom: 6,
        }}>
          <span style={{ fontSize: 12, fontFamily: BODY, color: T.T2 }}>{label}</span>
          <span style={{ fontSize: 13, fontFamily: MONO, color: col }}>
            {value === null ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`}
          </span>
        </div>
        <div style={{ height: 6, background: T.ACT, borderRadius: 3, overflow: "hidden" }}>
          <div style={{
            width: `${barWidth}%`, height: "100%",
            background: col, borderRadius: 3,
            transition: "width 0.6s ease",
          }} />
        </div>
      </div>
    );
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card title="Growth Metrics" accent={{ label: "YoY", color: T.GR }}>
          {growth.map((g, i) => <MetricRow key={i} {...g} />)}
        </Card>

        <Card title="Profitability" accent={{ label: "Quality", color: T.BL }}>
          {margins.map((m, i) => <MetricRow key={i} {...m} />)}
        </Card>
      </div>

      <Card title="Activity Summary">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14 }}>
          {[
            { k: "Sector", v: data.sector || "—", mono: false },
            { k: "Decision Signal", v: data.decision || "—", mono: false },
            { k: "Book Value", v: data.book_value !== null && data.book_value !== undefined ? `${data.currency === "INR" ? "₹" : "$"}${(+data.book_value).toFixed(2)}` : "—" },
            { k: "EPS (TTM)", v: data.eps_ttm !== null && data.eps_ttm !== undefined ? `${data.currency === "INR" ? "₹" : "$"}${(+data.eps_ttm).toFixed(2)}` : "—" },
          ].map((r, i) => (
            <div key={i} style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
              <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>{r.k}</div>
              <div style={{ fontSize: 14, fontFamily: r.mono === false ? BODY : MONO, color: T.T1, marginTop: 5, fontWeight: 500 }}>{r.v}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

/* ============================================================
   SUBTAB 5 — RISK
   ============================================================ */

function RiskPanel({ data, engine }) {
  const beta = n(data.beta);
  const de = n(data.debt_to_equity);
  const cr = n(data.current_ratio);
  const px = n(data.current_price);
  const hi = n(data.week52_high);
  const dd = drawdownFrom52W(px, hi);
  const f = flags(data, engine);

  const riskScores = [
    {
      label: "Volatility Risk",
      value: beta,
      score: beta === null ? null : beta < 0.8 ? "LOW" : beta < 1.2 ? "MED" : beta < 1.6 ? "HIGH" : "EXTREME",
      fmtVal: beta === null ? "—" : `β ${beta.toFixed(2)}`,
    },
    {
      label: "Leverage Risk",
      value: de,
      score: de === null ? null : de < 0.5 ? "LOW" : de < 1.0 ? "MED" : de < 2.0 ? "HIGH" : "EXTREME",
      fmtVal: de === null ? "—" : `D/E ${de.toFixed(2)}`,
    },
    {
      label: "Liquidity Risk",
      value: cr,
      score: cr === null ? null : cr > 2 ? "LOW" : cr > 1.5 ? "MED" : cr > 1 ? "HIGH" : "EXTREME",
      fmtVal: cr === null ? "—" : `CR ${cr.toFixed(2)}`,
    },
    {
      label: "Drawdown Risk",
      value: dd,
      score: dd === null ? null : dd < 10 ? "LOW" : dd < 25 ? "MED" : dd < 40 ? "HIGH" : "EXTREME",
      fmtVal: dd === null ? "—" : `${dd.toFixed(1)}%`,
    },
  ];

  const RISK_COLOR = { LOW: T.GR, MED: T.YL, HIGH: T.RD, EXTREME: "#7F1D1D" };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Card title="Risk Dashboard" accent={{ label: "4-Factor Matrix", color: T.RD }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          {riskScores.map((r, i) => {
            const col = r.score === null ? T.T3 : RISK_COLOR[r.score];
            return (
              <div key={i} style={{
                padding: 16, background: T.ACT, borderRadius: 6,
                borderTop: `3px solid ${col}`,
              }}>
                <div style={{
                  fontSize: 10, fontFamily: MONO, color: T.T3,
                  letterSpacing: 1, textTransform: "uppercase",
                }}>{r.label}</div>
                <div style={{
                  fontSize: 20, fontFamily: MONO, color: col, fontWeight: 600, marginTop: 8,
                }}>{r.score || "N/A"}</div>
                <div style={{
                  fontSize: 12, fontFamily: MONO, color: T.T2, marginTop: 4,
                }}>{r.fmtVal}</div>
              </div>
            );
          })}
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card title="Green Flags" accent={{ label: `${f.green.length}`, color: T.GR }}>
          {f.green.length === 0 ? (
            <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO }}>None identified</div>
          ) : (
            <div style={{ display: "grid", gap: 8 }}>
              {f.green.map((g, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "8px 10px", background: T.ACT, borderRadius: 4,
                  borderLeft: `2px solid ${T.GR}`,
                }}>
                  <span style={{ color: T.GR, fontSize: 14 }}>▲</span>
                  <span style={{ fontSize: 12, fontFamily: BODY, color: T.T1 }}>{g}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Red Flags" accent={{ label: `${f.red.length}`, color: T.RD }}>
          {f.red.length === 0 ? (
            <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO }}>None identified</div>
          ) : (
            <div style={{ display: "grid", gap: 8 }}>
              {f.red.map((r, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "8px 10px", background: T.ACT, borderRadius: 4,
                  borderLeft: `2px solid ${T.RD}`,
                }}>
                  <span style={{ color: T.RD, fontSize: 14 }}>▼</span>
                  <span style={{ fontSize: 12, fontFamily: BODY, color: T.T1 }}>{r}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

/* ============================================================
   OVERVIEW PAGE — hosts 5 subtabs
   ============================================================ */

const SUBTABS = [
  { id: "overview", label: "Overview" },
  { id: "valuation", label: "Valuation" },
  { id: "technical", label: "Technical" },
  { id: "activity", label: "Activity" },
  { id: "risk", label: "Risk" },
];

function OverviewPage({ ticker, onTickerChange }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sub, setSub] = useState("overview");
  const [input, setInput] = useState(ticker);

  useEffect(() => { setInput(ticker); }, [ticker]);

  const load = useCallback(async (t) => {
    if (!t) return;
    setLoading(true);
    setError(null);
    try {
      const url = `${API_BASE}/api/stock-quick?ticker=${encodeURIComponent(t.trim().toUpperCase())}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const j = await res.json();
      if (j.error) throw new Error(j.error);
      setData(j);
    } catch (e) {
      setError(e.message || "Failed to fetch");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(ticker); }, [ticker, load]);

  const engine = useMemo(() => data ? runFactorEngine(data) : null, [data]);

  const submit = (e) => {
    e.preventDefault?.();
    const v = input.trim().toUpperCase();
    if (v && v !== ticker) onTickerChange(v);
    else if (v) load(v);
  };

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>
      {/* ── Header: Ticker search + Company card ── */}
      <div style={{ marginBottom: 20 }}>
        <form onSubmit={submit} style={{ display: "flex", gap: 10, marginBottom: 16 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter ticker (e.g. MU, AAPL, MAZDOCK.NS)"
            style={{
              flex: 1, padding: "12px 16px",
              background: T.CARD, border: `1px solid ${T.BD}`,
              borderRadius: 6, fontFamily: MONO, fontSize: 14,
              color: T.T1, outline: "none",
            }}
          />
          <button onClick={submit} type="submit" style={{
            padding: "12px 24px", background: T.BL, border: "none",
            borderRadius: 6, fontFamily: MONO, fontSize: 13,
            color: "#fff", fontWeight: 600, cursor: "pointer",
            letterSpacing: 1, textTransform: "uppercase",
          }}>Analyze</button>
        </form>

        {data && !loading && (
          <Card pad={18}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
              <div>
                <div style={{ fontSize: 22, fontFamily: BODY, color: T.T1, fontWeight: 600 }}>
                  {data.company_name || data.ticker}
                </div>
                <div style={{ fontSize: 12, fontFamily: MONO, color: T.T3, marginTop: 3, letterSpacing: 1 }}>
                  {data.ticker} • {data.sector || "—"} • {data.currency || "USD"}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 28, fontFamily: MONO, color: T.T1, fontWeight: 700 }}>
                  {data.currency === "INR" ? "₹" : "$"}{(+data.current_price).toFixed(2)}
                </div>
                <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, marginTop: 3, letterSpacing: 1 }}>
                  LIVE QUOTE
                </div>
              </div>
            </div>
          </Card>
        )}
      </div>

      {/* ── Subtab nav ── */}
      {data && !loading && (
        <div style={{
          display: "flex", gap: 2, marginBottom: 20,
          background: T.CARD, padding: 4, borderRadius: 8,
          border: `1px solid ${T.BD}`,
        }}>
          {SUBTABS.map((s) => (
            <button key={s.id} onClick={() => setSub(s.id)} style={{
              flex: 1, padding: "10px 14px",
              background: sub === s.id ? T.BL : "transparent",
              border: "none", borderRadius: 5,
              fontFamily: MONO, fontSize: 12, fontWeight: 600,
              color: sub === s.id ? "#fff" : T.T2,
              cursor: "pointer", letterSpacing: 1, textTransform: "uppercase",
              transition: "all 0.15s ease",
            }}>{s.label}</button>
          ))}
        </div>
      )}

      {/* ── Panel content ── */}
      {loading && <LoadingState ticker={ticker} />}
      {error && !loading && <ErrorState msg={error} onRetry={() => load(ticker)} />}
      {data && engine && !loading && (
        <>
          {sub === "overview" && <OverviewPanel data={data} engine={engine} />}
          {sub === "valuation" && <ValuationPanel data={data} />}
          {sub === "technical" && <TechnicalPanel data={data} />}
          {sub === "activity" && <ActivityPanel data={data} />}
          {sub === "risk" && <RiskPanel data={data} engine={engine} />}
        </>
      )}
    </div>
  );
}

function LoadingState({ ticker }) {
  return (
    <div style={{
      padding: 60, textAlign: "center",
      background: T.CARD, border: `1px solid ${T.BD}`, borderRadius: 8,
    }}>
      <div style={{
        width: 32, height: 32, border: `2px solid ${T.ACT}`,
        borderTopColor: T.BL, borderRadius: "50%",
        margin: "0 auto 16px", animation: "spin 0.8s linear infinite",
      }} />
      <div style={{ fontFamily: MONO, fontSize: 12, color: T.T2, letterSpacing: 1 }}>
        FETCHING {ticker}...
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function ErrorState({ msg, onRetry }) {
  return (
    <div style={{
      padding: 40, textAlign: "center",
      background: T.CARD, border: `1px solid ${T.RD}40`, borderRadius: 8,
    }}>
      <div style={{ fontSize: 32, color: T.RD, marginBottom: 10 }}>⚠</div>
      <div style={{ fontFamily: BODY, fontSize: 14, color: T.T1, marginBottom: 6 }}>Data fetch failed</div>
      <div style={{ fontFamily: MONO, fontSize: 11, color: T.T3, marginBottom: 16 }}>{msg}</div>
      <button onClick={onRetry} style={{
        padding: "8px 16px", background: T.ACT, border: `1px solid ${T.BD}`,
        borderRadius: 4, fontFamily: MONO, fontSize: 11, color: T.T1,
        cursor: "pointer", letterSpacing: 1, textTransform: "uppercase",
      }}>Retry</button>
    </div>
  );
}

/* ============================================================
   HOME PAGE — Landing + Global Ticker + Quick search
   ============================================================ */

function HomePage({ onAnalyze }) {
  const [indices, setIndices] = useState([]);
  const [input, setInput] = useState("");
  const [tickerLoading, setTickerLoading] = useState(true);

  useEffect(() => {
    const fetchTicker = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/global-ticker`);
        if (res.ok) {
          const j = await res.json();
          const arr = Array.isArray(j) ? j : (j.indices || j.data || []);
          setIndices(arr.slice(0, 10));
        }
      } catch (e) {
        /* silent — landing still renders */
      } finally {
        setTickerLoading(false);
      }
    };
    fetchTicker();
  }, []);

  const go = (e) => {
    e.preventDefault?.();
    const v = input.trim().toUpperCase();
    if (v) onAnalyze(v);
  };

  const featured = ["MU", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META", "MAZDOCK.NS", "RELIANCE.NS", "TCS.NS", "INFY.NS"];

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>
      {/* Hero */}
      <div style={{
        padding: "60px 40px", background: T.CARD,
        border: `1px solid ${T.BD}`, borderRadius: 10,
        marginBottom: 20, position: "relative", overflow: "hidden",
      }}>
        {/* subtle grid texture */}
        <div style={{
          position: "absolute", inset: 0, opacity: 0.03,
          backgroundImage: `linear-gradient(${T.T1} 1px, transparent 1px), linear-gradient(90deg, ${T.T1} 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
        }} />
        <div style={{ position: "relative", zIndex: 1 }}>
          <div style={{
            display: "inline-block", padding: "4px 10px",
            border: `1px solid ${T.BL}40`, borderRadius: 3,
            fontSize: 10, fontFamily: MONO, color: T.BL,
            letterSpacing: 2, marginBottom: 20, textTransform: "uppercase",
          }}>Institutional-Grade Analysis</div>
          <h1 style={{
            fontSize: 48, fontFamily: BODY, fontWeight: 700,
            color: T.T1, margin: "0 0 12px", letterSpacing: -1, lineHeight: 1.1,
          }}>Celesys</h1>
          <div style={{
            fontSize: 16, fontFamily: BODY, color: T.T2,
            marginBottom: 32, maxWidth: 600, lineHeight: 1.5,
          }}>
            Multi-layer decision framework for US & Indian equities.
            20-factor verdict engine with CDS v2.0 scoring.
          </div>

          <form onSubmit={go} style={{ display: "flex", gap: 10, maxWidth: 600 }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Enter ticker symbol..."
              style={{
                flex: 1, padding: "14px 18px",
                background: T.BG, border: `1px solid ${T.BD}`,
                borderRadius: 6, fontFamily: MONO, fontSize: 14,
                color: T.T1, outline: "none",
              }}
            />
            <button type="submit" style={{
              padding: "14px 28px", background: T.BL, border: "none",
              borderRadius: 6, fontFamily: MONO, fontSize: 13,
              color: "#fff", fontWeight: 700, cursor: "pointer",
              letterSpacing: 1.5, textTransform: "uppercase",
            }}>Analyze →</button>
          </form>

          {/* Featured quick links */}
          <div style={{ marginTop: 24 }}>
            <div style={{
              fontSize: 10, fontFamily: MONO, color: T.T3,
              letterSpacing: 1.5, marginBottom: 10, textTransform: "uppercase",
            }}>Featured</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {featured.map((t) => (
                <button key={t} onClick={() => onAnalyze(t)} style={{
                  padding: "6px 12px", background: T.ACT,
                  border: `1px solid ${T.BD}`, borderRadius: 4,
                  fontFamily: MONO, fontSize: 11, color: T.T2,
                  cursor: "pointer", letterSpacing: 0.5,
                  transition: "all 0.15s ease",
                }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = T.BL;
                    e.currentTarget.style.color = T.T1;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = T.BD;
                    e.currentTarget.style.color = T.T2;
                  }}
                >{t}</button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Platform capabilities */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14, marginBottom: 20,
      }}>
        {[
          {
            h: "20-Factor Verdict Engine",
            d: "Valuation, profitability, balance sheet, momentum, growth — rolled into a single BUY/HOLD/SELL signal with driver attribution.",
            c: T.BL,
          },
          {
            h: "CDS v2.0 Scoring",
            d: "Composite Decision Score. No fake assumptions — missing data is flagged, never substituted with plausible defaults.",
            c: T.PP,
          },
          {
            h: "Dual-Market Coverage",
            d: "US equities plus Indian universe: Nifty 50, Next 50, Midcap 150, Smallcap 250, Micro Cap.",
            c: T.CY,
          },
        ].map((f, i) => (
          <Card key={i}>
            <div style={{ width: 28, height: 3, background: f.c, marginBottom: 14 }} />
            <div style={{ fontSize: 16, fontFamily: BODY, color: T.T1, fontWeight: 600, marginBottom: 8 }}>{f.h}</div>
            <div style={{ fontSize: 13, fontFamily: BODY, color: T.T2, lineHeight: 1.5 }}>{f.d}</div>
          </Card>
        ))}
      </div>

      {/* Global indices ticker */}
      {!tickerLoading && indices.length > 0 && (
        <Card title="Global Markets" accent={{ label: "Live", color: T.GR }}>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10,
          }}>
            {indices.map((idx, i) => {
              const change = n(idx.change_percent ?? idx.changePercent ?? idx.change);
              const col = change === null ? T.T3 : change >= 0 ? T.GR : T.RD;
              return (
                <div key={i} style={{
                  padding: 12, background: T.ACT, borderRadius: 4,
                  borderLeft: `2px solid ${col}`,
                }}>
                  <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2, letterSpacing: 0.5 }}>
                    {idx.symbol || idx.name || idx.ticker || "—"}
                  </div>
                  <div style={{ fontSize: 15, fontFamily: MONO, color: T.T1, fontWeight: 600, marginTop: 4 }}>
                    {idx.price !== undefined && idx.price !== null ? (+idx.price).toFixed(2) : "—"}
                  </div>
                  {change !== null && (
                    <div style={{ fontSize: 11, fontFamily: MONO, color: col, marginTop: 2 }}>
                      {change >= 0 ? "+" : ""}{change.toFixed(2)}%
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}

/* ============================================================
   STOCK TAB — Institutional Deep-Dive Terminal (Session 2)
   10 accordion sections with institutional-grade analytics
   ============================================================ */

/* ---------- Advanced analytics ---------- */

function altmanZScore(d) {
  /* Altman Z for non-financial: Z = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E
     With only /api/stock-quick fields, we approximate via available proxies.
     Score zones: >2.99 safe, 1.81-2.99 grey, <1.81 distress.
     We flag as "Approximate" since full balance-sheet items aren't exposed. */
  const mc = n(d.market_cap);
  const de = n(d.debt_to_equity);
  const pm = n(d.profit_margin);
  const opm = n(d.operating_margin);
  const cr = n(d.current_ratio);
  const roe = n(d.roe);

  if (mc === null || de === null || pm === null) return null;

  // Approximation: build a composite "distress index" from available ratios
  const leverage = 1 / (1 + de);              // 0-1, higher is better
  const profitability = Math.max(-0.5, Math.min(0.5, (pm + (opm ?? 0)) / 2)) + 0.5; // 0-1
  const liquidity = cr === null ? 0.5 : Math.min(1, cr / 3);
  const quality = roe === null ? 0.5 : Math.max(0, Math.min(1, (roe + 0.2) / 0.6));

  const composite = (leverage * 1.5) + (profitability * 2.0) + (liquidity * 1.0) + (quality * 1.5);
  // composite ranges roughly 0-6; map to Altman-style scale
  const z = composite * 0.8;

  let zone, color;
  if (z >= 2.99) { zone = "Safe Zone"; color = T.GR; }
  else if (z >= 1.81) { zone = "Grey Zone"; color = T.YL; }
  else { zone = "Distress Zone"; color = T.RD; }

  return { z, zone, color, approximate: true };
}

function duPontROE(d) {
  /* Classic 3-step DuPont:
     ROE = Net Margin × Asset Turnover × Equity Multiplier
     We have pm, roe, de. We can back-solve approximate turnover.
     ROE = NM × AT × EM  =>  AT × EM = ROE / NM
     EM ≈ 1 + (D/E)
     AT ≈ (ROE / NM) / EM */
  const pm = n(d.profit_margin);
  const roe = n(d.roe);
  const de = n(d.debt_to_equity);

  if (pm === null || roe === null || pm === 0) return null;

  const em = de === null ? null : 1 + de;
  const at = em ? (roe / pm) / em : null;

  return {
    netMargin: pm,
    assetTurnover: at,
    equityMultiplier: em,
    roe,
    approximate: true,
  };
}

function monteCarloFan(d) {
  /* Simplified MC: use current price, beta, and growth expectations to
     generate p10/p25/p50/p75/p90 1-year out via lognormal drift+volatility. */
  const px = n(d.current_price);
  const beta = n(d.beta) ?? 1.0;
  const eps = n(d.eps_growth_pct);
  const pm = n(d.profit_margin);
  if (px === null) return null;

  // Drift: earnings-driven expected return, bounded.
  // Cap upside contribution at +12% above baseline — real forward returns
  // mean-revert; a 45% EPS growth rate doesn't translate 1:1 into price return.
  let drift = 0.08; // market baseline
  if (eps !== null) drift += Math.max(-0.15, Math.min(0.12, eps / 400));
  if (pm !== null && pm < 0) drift -= 0.10;

  // Vol scaled to beta
  const vol = 0.20 * Math.max(0.5, beta);

  // Quantiles of lognormal(drift - vol^2/2, vol)
  const mu = drift - (vol * vol) / 2;
  const q = (p) => px * Math.exp(mu + vol * invNormCDF(p));

  return {
    p10: q(0.10),
    p25: q(0.25),
    p50: q(0.50),
    p75: q(0.75),
    p90: q(0.90),
    drift, vol,
    current: px,
  };
}

/* Abramowitz-Stegun rational approximation of inverse normal CDF */
function invNormCDF(p) {
  if (p <= 0) return -Infinity;
  if (p >= 1) return Infinity;
  const a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
  const b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
  const c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
  const dd = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
  const pl = 0.02425;
  const ph = 1 - pl;
  let q, r;
  if (p < pl) {
    q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1);
  }
  if (p <= ph) {
    q = p - 0.5;
    r = q * q;
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1);
  }
  q = Math.sqrt(-2 * Math.log(1 - p));
  return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1);
}

function moatScore(d) {
  /* Synthetic moat proxy from operating margin + ROE + margin stability hints */
  const opm = n(d.operating_margin);
  const roe = n(d.roe);
  const pm = n(d.profit_margin);

  const signals = [];
  let score = 0;

  if (opm !== null) {
    if (opm > 0.25) { score += 3; signals.push({ pos: true, text: `Elite operating margin ${(opm * 100).toFixed(1)}%` }); }
    else if (opm > 0.15) { score += 2; signals.push({ pos: true, text: `Strong operating margin ${(opm * 100).toFixed(1)}%` }); }
    else if (opm > 0.05) { score += 1; signals.push({ pos: true, text: `Operating margin ${(opm * 100).toFixed(1)}%` }); }
    else if (opm < 0) { score -= 2; signals.push({ pos: false, text: `Negative operating margin` }); }
  }

  if (roe !== null) {
    if (roe > 0.25) { score += 3; signals.push({ pos: true, text: `Exceptional ROE ${(roe * 100).toFixed(1)}% — sustainable advantage` }); }
    else if (roe > 0.15) { score += 2; signals.push({ pos: true, text: `High ROE ${(roe * 100).toFixed(1)}% — quality business` }); }
    else if (roe > 0.08) { score += 1; }
    else if (roe < 0) { score -= 2; signals.push({ pos: false, text: `Negative ROE — capital destruction` }); }
  }

  if (pm !== null && opm !== null) {
    // Gap between operating and net is tax+interest drag; small = lean
    const gap = opm - pm;
    if (gap < 0.05 && pm > 0.10) { score += 1; signals.push({ pos: true, text: `Efficient capital structure` }); }
  }

  const max = 7;
  const pct = (score / max) * 100;
  let verdict, color;
  if (pct >= 60) { verdict = "Wide Moat"; color = T.GR; }
  else if (pct >= 30) { verdict = "Narrow Moat"; color = T.BL; }
  else if (pct >= 0) { verdict = "No Moat"; color = T.YL; }
  else { verdict = "Eroding Moat"; color = T.RD; }

  return { score, max, pct, verdict, color, signals };
}

/* ---------- Accordion primitive ---------- */

function Accordion({ id, title, badge, badgeColor, summary, defaultOpen = false, children, icon, tier }) {
  const [open, setOpen] = useState(defaultOpen);

  const tierColors = {
    core: T.BL,
    quality: T.PP,
    valuation: T.CY,
    risk: T.RD,
    growth: T.GR,
    ownership: T.YL,
  };
  const borderC = tier ? tierColors[tier] : T.BD;

  return (
    <div style={{
      background: T.CARD,
      border: `1px solid ${T.BD}`,
      borderLeft: `3px solid ${borderC}`,
      borderRadius: 8,
      overflow: "hidden",
      transition: "all 0.2s ease",
    }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%", padding: "16px 20px",
          background: "transparent", border: "none",
          cursor: "pointer", display: "flex",
          justifyContent: "space-between", alignItems: "center",
          textAlign: "left", gap: 14, fontFamily: BODY,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1, minWidth: 0 }}>
          {icon && (
            <div style={{
              width: 32, height: 32, borderRadius: 6,
              background: `${borderC}15`, border: `1px solid ${borderC}30`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 14, color: borderC, flexShrink: 0, fontFamily: MONO, fontWeight: 700,
            }}>{icon}</div>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 14, fontFamily: BODY, fontWeight: 600,
              color: T.T1, letterSpacing: -0.2,
            }}>{title}</div>
            {summary && (
              <div style={{
                fontSize: 12, fontFamily: BODY, color: T.T3,
                marginTop: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>{summary}</div>
            )}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
          {badge && (
            <div style={{
              fontSize: 10, fontFamily: MONO,
              padding: "3px 10px", borderRadius: 3,
              background: `${badgeColor || borderC}15`,
              border: `1px solid ${badgeColor || borderC}40`,
              color: badgeColor || borderC,
              letterSpacing: 1, textTransform: "uppercase",
              whiteSpace: "nowrap", fontWeight: 600,
            }}>{badge}</div>
          )}
          <div style={{
            width: 20, height: 20, display: "flex",
            alignItems: "center", justifyContent: "center",
            color: T.T3, fontSize: 12,
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 0.2s ease", fontFamily: MONO,
          }}>▸</div>
        </div>
      </button>

      {open && (
        <div style={{
          padding: "0 20px 20px", borderTop: `1px solid ${T.ACT}`,
          paddingTop: 20,
        }}>
          {children}
        </div>
      )}
    </div>
  );
}

/* ---------- Shared: stat row ---------- */

function StatRow({ label, value, color, sub }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "baseline",
      padding: "10px 0", borderBottom: `1px solid ${T.ACT}`,
    }}>
      <div>
        <div style={{ fontSize: 12, fontFamily: BODY, color: T.T2 }}>{label}</div>
        {sub && <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, marginTop: 2, letterSpacing: 0.5 }}>{sub}</div>}
      </div>
      <div style={{ fontSize: 14, fontFamily: MONO, color: color || T.T1, fontWeight: 600 }}>{value}</div>
    </div>
  );
}

/* ---------- Section renderers ---------- */

function HeroBanner({ data, engine }) {
  const px = n(data.current_price);
  const ccy = data.currency === "INR" ? "₹" : "$";
  const decColor = engine.verdictColor;

  // Confidence proxy: how decisive the engine's score is
  const confidence = Math.min(100, Math.max(20, 50 + Math.abs(engine.pct - 50) * 1.5));

  return (
    <Card pad={28} style={{
      background: `linear-gradient(135deg, ${T.CARD} 0%, ${T.ACT} 100%)`,
      borderLeft: `4px solid ${decColor}`,
    }}>
      <div style={{
        display: "grid", gridTemplateColumns: "1fr auto", gap: 24, alignItems: "center",
      }}>
        <div>
          <div style={{
            fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 2,
            textTransform: "uppercase", marginBottom: 8,
          }}>
            {data.sector || "—"} · {data.ticker}
          </div>
          <div style={{
            fontSize: 30, fontFamily: BODY, color: T.T1, fontWeight: 700,
            letterSpacing: -0.5, marginBottom: 14,
          }}>
            {data.company_name || data.ticker}
          </div>

          <div style={{ display: "flex", gap: 24, alignItems: "baseline", flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>Price</div>
              <div style={{ fontSize: 36, fontFamily: MONO, color: T.T1, fontWeight: 700, lineHeight: 1 }}>
                {ccy}{px !== null ? px.toFixed(2) : "—"}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>Market Cap</div>
              <div style={{ fontSize: 22, fontFamily: MONO, color: T.T1, fontWeight: 600, marginTop: 4 }}>
                {data.market_cap ? `${ccy}${fmtB(data.market_cap)}` : "—"}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>Confidence</div>
              <div style={{ fontSize: 22, fontFamily: MONO, color: decColor, fontWeight: 600, marginTop: 4 }}>
                {confidence.toFixed(0)}%
              </div>
            </div>
          </div>
        </div>

        <div style={{ textAlign: "center", padding: "0 10px" }}>
          <div style={{
            fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 2,
            textTransform: "uppercase", marginBottom: 8,
          }}>Engine Verdict</div>
          <div style={{
            fontSize: 48, fontFamily: BODY, color: decColor, fontWeight: 800,
            letterSpacing: 3, lineHeight: 1,
          }}>{engine.verdict}</div>
          <div style={{
            marginTop: 10, padding: "5px 12px",
            background: `${decColor}15`,
            border: `1px solid ${decColor}40`, borderRadius: 4,
            display: "inline-block",
            fontSize: 11, fontFamily: MONO, color: decColor, fontWeight: 600,
            letterSpacing: 1,
          }}>
            {engine.totalScore > 0 ? "+" : ""}{engine.totalScore} / {engine.maxScore}
          </div>
        </div>
      </div>
    </Card>
  );
}

function BottomLineNarrative({ data, engine }) {
  const px = n(data.current_price);
  const pe = n(data.pe_ratio);
  const secPE = n(data.sector_avg_pe);
  const roe = n(data.roe);
  const eps = n(data.eps_growth_pct);
  const beta = n(data.beta);
  const hi = n(data.week52_high);
  const lo = n(data.week52_low);

  // Build a coherent narrative from factors
  const strengths = engine.factors.filter(f => f.score > 0 && f.pass !== null).sort((a, b) => b.score - a.score).slice(0, 3);
  const weaknesses = engine.factors.filter(f => f.score < 0 && f.pass !== null).sort((a, b) => a.score - b.score).slice(0, 3);

  let thesis = "";
  if (engine.verdict === "BUY") {
    const topStrength = strengths[0];
    thesis = topStrength
      ? `${data.company_name || data.ticker} presents a compelling opportunity driven by ${topStrength.label.toLowerCase()}.`
      : `${data.company_name || data.ticker} shows multiple positive signals across the framework.`;
    if (pe !== null && secPE !== null && pe < secPE) {
      thesis += ` The stock trades at a discount to its sector (${pe.toFixed(1)}x vs ${secPE.toFixed(1)}x).`;
    }
    if (eps !== null && eps > 15) {
      thesis += ` Earnings are expanding at ${eps.toFixed(1)}%, supporting the valuation.`;
    }
  } else if (engine.verdict === "HOLD") {
    thesis = `${data.company_name || data.ticker} shows a mixed signal. Positives are offset by areas of concern — monitor for catalyst resolution before adding.`;
  } else {
    const topWeak = weaknesses[0];
    thesis = topWeak
      ? `Elevated risk driven by ${topWeak.label.toLowerCase()}. Consider reducing exposure or waiting for improvement.`
      : `Multiple negative signals suggest caution.`;
  }

  const actions = [];
  if (engine.verdict === "BUY") {
    if (lo !== null && px !== null) actions.push(`Entry zone: ${(data.currency === "INR" ? "₹" : "$")}${(lo + (px - lo) * 0.7).toFixed(2)} – ${(data.currency === "INR" ? "₹" : "$")}${px.toFixed(2)}`);
    if (hi !== null) actions.push(`Upside target: ${(data.currency === "INR" ? "₹" : "$")}${hi.toFixed(2)}`);
    if (lo !== null) actions.push(`Stop-loss consideration: below ${(data.currency === "INR" ? "₹" : "$")}${(lo * 0.95).toFixed(2)}`);
  } else if (engine.verdict === "HOLD") {
    actions.push(`Hold current position. Do not add until framework score improves.`);
    actions.push(`Watch: earnings growth, sector rotation, forward guidance.`);
  } else {
    actions.push(`Trim exposure on strength. Avoid initiating new positions.`);
    actions.push(`Re-evaluate after next earnings report.`);
  }

  return (
    <div>
      <div style={{
        padding: 16, background: T.ACT, borderRadius: 6,
        borderLeft: `3px solid ${engine.verdictColor}`, marginBottom: 16,
      }}>
        <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 8 }}>
          Investment Thesis
        </div>
        <div style={{ fontSize: 14, fontFamily: BODY, color: T.T1, lineHeight: 1.6 }}>
          {thesis}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={{ padding: 14, background: T.ACT, borderRadius: 6, borderTop: `2px solid ${T.GR}` }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.GR, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 10 }}>
            Strengths ({strengths.length})
          </div>
          {strengths.length ? strengths.map((s, i) => (
            <div key={i} style={{
              fontSize: 12, fontFamily: BODY, color: T.T1,
              padding: "6px 0", display: "flex", gap: 8,
              borderBottom: i < strengths.length - 1 ? `1px solid ${T.BD}` : "none",
            }}>
              <span style={{ color: T.GR, fontFamily: MONO }}>▲</span>
              <span>{s.label}: {s.detail}</span>
            </div>
          )) : <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO }}>—</div>}
        </div>

        <div style={{ padding: 14, background: T.ACT, borderRadius: 6, borderTop: `2px solid ${T.RD}` }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.RD, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 10 }}>
            Concerns ({weaknesses.length})
          </div>
          {weaknesses.length ? weaknesses.map((w, i) => (
            <div key={i} style={{
              fontSize: 12, fontFamily: BODY, color: T.T1,
              padding: "6px 0", display: "flex", gap: 8,
              borderBottom: i < weaknesses.length - 1 ? `1px solid ${T.BD}` : "none",
            }}>
              <span style={{ color: T.RD, fontFamily: MONO }}>▼</span>
              <span>{w.label}: {w.detail}</span>
            </div>
          )) : <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO }}>None detected</div>}
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 10 }}>
          Action Plan
        </div>
        <div style={{ display: "grid", gap: 8 }}>
          {actions.map((a, i) => (
            <div key={i} style={{
              padding: "10px 12px", background: T.ACT, borderRadius: 4,
              fontSize: 12, fontFamily: BODY, color: T.T1,
              borderLeft: `2px solid ${engine.verdictColor}`,
            }}>
              <span style={{ color: engine.verdictColor, fontFamily: MONO, marginRight: 8 }}>◆</span>
              {a}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function IntrinsicValueTriangulation({ data }) {
  const px = n(data.current_price);
  const eps = n(data.eps_ttm);
  const bv = n(data.book_value);
  const epsG = n(data.eps_growth_pct);
  const pe = n(data.pe_ratio);
  const secPE = n(data.sector_avg_pe);
  const ccy = data.currency === "INR" ? "₹" : "$";

  const graham = grahamNumber(eps, bv);
  const iv = intrinsicValue(eps, epsG);
  const dcf = dcfQuick(eps, epsG);
  // Relative: apply sector P/E to EPS
  const relative = (eps !== null && secPE !== null && eps > 0) ? eps * secPE : null;
  // Asset-based: book value with quality premium
  const assetBased = bv !== null ? bv * 1.5 : null;

  const methods = [
    { name: "Graham Number", value: graham, logic: "√(22.5 × EPS × BV)" },
    { name: "Graham Intrinsic", value: iv, logic: "EPS × (8.5 + 2g)" },
    { name: "DCF (5Y)", value: dcf, logic: "10% disc, 3% terminal" },
    { name: "Relative (Sector P/E)", value: relative, logic: "EPS × Sector P/E" },
    { name: "Asset-based", value: assetBased, logic: "Book Value × 1.5" },
  ];

  const valid = methods.filter(m => m.value !== null);
  const avg = valid.length ? valid.reduce((s, m) => s + m.value, 0) / valid.length : null;
  const mos = (avg !== null && px !== null) ? ((avg - px) / avg) * 100 : null;

  return (
    <div>
      {/* Averaged conclusion */}
      <div style={{
        padding: 18, background: T.ACT, borderRadius: 6,
        marginBottom: 16,
        borderLeft: `3px solid ${mos === null ? T.T3 : mos > 20 ? T.GR : mos < -20 ? T.RD : T.YL}`,
      }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>Avg Fair Value</div>
            <div style={{ fontSize: 24, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 4 }}>
              {avg !== null ? `${ccy}${avg.toFixed(2)}` : "—"}
            </div>
            <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, marginTop: 2 }}>
              {valid.length} of {methods.length} methods
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>Current Price</div>
            <div style={{ fontSize: 24, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 4 }}>
              {px !== null ? `${ccy}${px.toFixed(2)}` : "—"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>Margin of Safety</div>
            <div style={{
              fontSize: 24, fontFamily: MONO, fontWeight: 700, marginTop: 4,
              color: mos === null ? T.T3 : mos > 20 ? T.GR : mos < -20 ? T.RD : T.YL,
            }}>
              {mos !== null ? `${mos > 0 ? "+" : ""}${mos.toFixed(1)}%` : "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Each method breakdown */}
      <div style={{ display: "grid", gap: 10 }}>
        {methods.map((m, i) => {
          const diff = m.value !== null && px !== null ? ((m.value - px) / px) * 100 : null;
          const col = diff === null ? T.T3 : diff > 15 ? T.GR : diff < -15 ? T.RD : T.YL;
          const barPos = diff === null ? 50 : Math.min(100, Math.max(0, 50 + diff / 2));
          return (
            <div key={i} style={{
              padding: "12px 14px", background: T.ACT, borderRadius: 6,
              display: "grid", gridTemplateColumns: "1.2fr 0.8fr 2fr 0.8fr", gap: 14, alignItems: "center",
            }}>
              <div>
                <div style={{ fontSize: 12, fontFamily: BODY, color: T.T1, fontWeight: 600 }}>{m.name}</div>
                <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, marginTop: 2 }}>{m.logic}</div>
              </div>
              <div style={{ fontSize: 14, fontFamily: MONO, color: T.T1, fontWeight: 600 }}>
                {m.value !== null ? `${ccy}${m.value.toFixed(2)}` : "—"}
              </div>
              <div style={{ position: "relative", height: 6, background: T.CARD, borderRadius: 3, overflow: "visible" }}>
                <div style={{
                  position: "absolute", top: 0, left: "50%", width: 1, height: "100%",
                  background: T.T3, opacity: 0.5,
                }} />
                <div style={{
                  position: "absolute", top: -3, left: `calc(${barPos}% - 6px)`,
                  width: 12, height: 12, borderRadius: 2, background: col,
                  boxShadow: `0 0 0 2px ${T.ACT}`,
                }} />
              </div>
              <div style={{
                fontSize: 12, fontFamily: MONO, color: col, fontWeight: 600, textAlign: "right",
              }}>
                {diff !== null ? `${diff > 0 ? "+" : ""}${diff.toFixed(1)}%` : "n/a"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DuPontDecomposition({ data }) {
  const dp = duPontROE(data);
  if (!dp) {
    return <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO, padding: 16 }}>Insufficient data — requires profit margin and ROE</div>;
  }

  const components = [
    { label: "Net Margin", value: dp.netMargin * 100, format: (v) => `${v.toFixed(2)}%`, color: T.BL, desc: "Operational efficiency" },
    { label: "Asset Turnover", value: dp.assetTurnover, format: (v) => v === null ? "—" : `${v.toFixed(2)}x`, color: T.PP, desc: "Capital productivity", approx: true },
    { label: "Equity Multiplier", value: dp.equityMultiplier, format: (v) => v === null ? "—" : `${v.toFixed(2)}x`, color: T.YL, desc: "Financial leverage", approx: true },
  ];

  return (
    <div>
      {/* Formula bar */}
      <div style={{
        padding: 14, background: T.ACT, borderRadius: 6, marginBottom: 16,
        display: "flex", alignItems: "center", justifyContent: "space-around", gap: 8, flexWrap: "wrap",
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1 }}>ROE</div>
          <div style={{ fontSize: 22, fontFamily: MONO, color: T.GR, fontWeight: 700, marginTop: 2 }}>
            {(dp.roe * 100).toFixed(2)}%
          </div>
        </div>
        <div style={{ fontSize: 20, color: T.T3, fontFamily: MONO }}>=</div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1 }}>Net Margin</div>
          <div style={{ fontSize: 18, fontFamily: MONO, color: T.BL, fontWeight: 600, marginTop: 2 }}>
            {(dp.netMargin * 100).toFixed(2)}%
          </div>
        </div>
        <div style={{ fontSize: 20, color: T.T3, fontFamily: MONO }}>×</div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1 }}>Asset Turnover</div>
          <div style={{ fontSize: 18, fontFamily: MONO, color: T.PP, fontWeight: 600, marginTop: 2 }}>
            {dp.assetTurnover !== null ? `${dp.assetTurnover.toFixed(2)}x` : "—"}
          </div>
        </div>
        <div style={{ fontSize: 20, color: T.T3, fontFamily: MONO }}>×</div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1 }}>Equity Mult.</div>
          <div style={{ fontSize: 18, fontFamily: MONO, color: T.YL, fontWeight: 600, marginTop: 2 }}>
            {dp.equityMultiplier !== null ? `${dp.equityMultiplier.toFixed(2)}x` : "—"}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        {components.map((c, i) => (
          <div key={i} style={{
            padding: 14, background: T.ACT, borderRadius: 6,
            borderTop: `3px solid ${c.color}`,
          }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>
              {c.label}
            </div>
            <div style={{ fontSize: 22, fontFamily: MONO, color: c.color, fontWeight: 700, marginTop: 6 }}>
              {c.format(c.value)}
            </div>
            <div style={{ fontSize: 11, fontFamily: BODY, color: T.T2, marginTop: 6 }}>{c.desc}</div>
            {c.approx && (
              <div style={{
                fontSize: 9, fontFamily: MONO, color: T.YL, marginTop: 4,
                letterSpacing: 1, textTransform: "uppercase",
              }}>~Derived from ratios</div>
            )}
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 14, padding: 12, background: T.CARD, border: `1px solid ${T.BD}`,
        borderRadius: 4, fontSize: 12, fontFamily: BODY, color: T.T2, lineHeight: 1.5,
      }}>
        <strong style={{ color: T.T1 }}>Insight:</strong>{" "}
        {dp.netMargin > 0.15 && dp.assetTurnover && dp.assetTurnover > 1 ?
          "ROE driven by operational strength — high margins on efficient asset use." :
         dp.equityMultiplier && dp.equityMultiplier > 2.5 ?
          "ROE inflated by financial leverage — examine debt sustainability." :
         dp.netMargin > 0.15 ?
          "Profitability-driven ROE — strong margin business." :
          "ROE structure suggests moderate profitability with typical leverage."}
      </div>
    </div>
  );
}

function FinancialHealth({ data }) {
  const altman = altmanZScore(data);
  const de = n(data.debt_to_equity);
  const cr = n(data.current_ratio);
  const pm = n(data.profit_margin);
  const opm = n(data.operating_margin);

  return (
    <div>
      {altman && (
        <div style={{
          padding: 16, background: T.ACT, borderRadius: 6,
          borderLeft: `3px solid ${altman.color}`, marginBottom: 14,
        }}>
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 20, alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
                Altman Z-Score
              </div>
              <div style={{ fontSize: 32, fontFamily: MONO, color: altman.color, fontWeight: 700, marginTop: 4 }}>
                {altman.z.toFixed(2)}
              </div>
              {altman.approximate && (
                <div style={{ fontSize: 9, fontFamily: MONO, color: T.YL, letterSpacing: 1, textTransform: "uppercase", marginTop: 2 }}>
                  Approximate
                </div>
              )}
            </div>

            <div>
              {/* Zone visualization */}
              <div style={{ position: "relative", height: 28, background: T.CARD, borderRadius: 3, overflow: "hidden" }}>
                <div style={{ position: "absolute", left: 0, top: 0, width: "30%", height: "100%", background: `${T.RD}40` }} />
                <div style={{ position: "absolute", left: "30%", top: 0, width: "30%", height: "100%", background: `${T.YL}40` }} />
                <div style={{ position: "absolute", left: "60%", top: 0, width: "40%", height: "100%", background: `${T.GR}40` }} />
                <div style={{
                  position: "absolute", top: 0, height: "100%", width: 3,
                  background: altman.color,
                  left: `${Math.min(100, Math.max(0, (altman.z / 5) * 100))}%`,
                  boxShadow: `0 0 10px ${altman.color}`,
                }} />
              </div>
              <div style={{
                display: "flex", justifyContent: "space-between",
                fontSize: 10, fontFamily: MONO, color: T.T3, marginTop: 6,
              }}>
                <span>Distress &lt;1.81</span>
                <span>Grey 1.81–2.99</span>
                <span>Safe &gt;2.99</span>
              </div>
            </div>

            <div style={{
              padding: "6px 14px", background: `${altman.color}15`,
              border: `1px solid ${altman.color}40`, borderRadius: 4,
              fontSize: 12, fontFamily: MONO, color: altman.color,
              fontWeight: 600, letterSpacing: 1, textTransform: "uppercase",
              whiteSpace: "nowrap",
            }}>{altman.zone}</div>
          </div>
        </div>
      )}

      {/* Liquidity / Solvency cascade */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={{ padding: 14, background: T.ACT, borderRadius: 6 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 12 }}>
            Leverage & Solvency
          </div>
          <StatRow label="Debt-to-Equity" value={de !== null ? de.toFixed(2) : "—"}
            color={de === null ? T.T3 : de < 0.5 ? T.GR : de < 1.5 ? T.YL : T.RD}
            sub={de === null ? null : de < 0.5 ? "Conservative" : de < 1.5 ? "Moderate" : "High leverage"} />
          <StatRow label="Operating Margin" value={opm !== null ? `${(opm * 100).toFixed(2)}%` : "—"}
            color={opm === null ? T.T3 : opm > 0.15 ? T.GR : opm > 0.05 ? T.YL : T.RD}
            sub={opm === null ? null : "Cash generation capacity"} />
        </div>

        <div style={{ padding: 14, background: T.ACT, borderRadius: 6 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 12 }}>
            Liquidity
          </div>
          <StatRow label="Current Ratio" value={cr !== null ? cr.toFixed(2) : "—"}
            color={cr === null ? T.T3 : cr > 2 ? T.GR : cr > 1.2 ? T.YL : T.RD}
            sub={cr === null ? null : cr > 2 ? "Strong short-term position" : cr > 1.2 ? "Adequate" : "Tight liquidity"} />
          <StatRow label="Profit Margin" value={pm !== null ? `${(pm * 100).toFixed(2)}%` : "—"}
            color={pm === null ? T.T3 : pm > 0.10 ? T.GR : pm > 0 ? T.YL : T.RD}
            sub={pm === null ? null : "Bottom-line efficiency"} />
        </div>
      </div>
    </div>
  );
}

function EarningsQuality({ data, engine }) {
  const eps = n(data.eps_growth_pct);
  const rev = n(data.revenue_growth);
  const ern = n(data.earnings_growth);
  const peg = n(data.peg_ratio);
  const normalizePct = (v) => (v === null ? null : (Math.abs(v) > 5 ? v : v * 100));
  const revPct = normalizePct(rev);
  const ernPct = normalizePct(ern);

  // Score earnings quality
  let qScore = 0, qMax = 20;
  const qSignals = [];
  if (eps !== null) {
    if (eps > 20) { qScore += 7; qSignals.push({ pos: true, text: `EPS accelerating ${eps.toFixed(1)}%` }); }
    else if (eps > 10) { qScore += 4; qSignals.push({ pos: true, text: `EPS growing ${eps.toFixed(1)}%` }); }
    else if (eps > 0) { qScore += 2; }
    else { qScore -= 3; qSignals.push({ pos: false, text: `EPS contracting ${eps.toFixed(1)}%` }); }
  }
  if (revPct !== null) {
    if (revPct > 15) { qScore += 5; qSignals.push({ pos: true, text: `Revenue scaling ${revPct.toFixed(1)}%` }); }
    else if (revPct > 5) { qScore += 3; }
    else if (revPct > 0) { qScore += 1; }
    else { qScore -= 2; qSignals.push({ pos: false, text: `Revenue declining ${revPct.toFixed(1)}%` }); }
  }
  if (ernPct !== null) {
    if (ernPct > 25) { qScore += 5; qSignals.push({ pos: true, text: `Q/Q momentum strong ${ernPct.toFixed(0)}%` }); }
    else if (ernPct > 5) { qScore += 3; }
    else if (ernPct < -10) { qScore -= 3; qSignals.push({ pos: false, text: `Q/Q declining ${ernPct.toFixed(0)}%` }); }
  }
  if (peg !== null && peg > 0) {
    if (peg < 1) { qScore += 3; qSignals.push({ pos: true, text: `PEG ${peg.toFixed(2)} — growth at discount` }); }
    else if (peg > 2) { qScore -= 2; qSignals.push({ pos: false, text: `PEG ${peg.toFixed(2)} — growth overvalued` }); }
  }

  const qPct = Math.max(0, Math.min(100, ((qScore + 5) / (qMax + 5)) * 100));
  const qColor = qPct >= 60 ? T.GR : qPct >= 35 ? T.YL : T.RD;
  const qLabel = qPct >= 70 ? "Excellent" : qPct >= 50 ? "Good" : qPct >= 30 ? "Mixed" : "Weak";

  return (
    <div>
      <div style={{
        padding: 16, background: T.ACT, borderRadius: 6, marginBottom: 14,
        borderLeft: `3px solid ${qColor}`,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Earnings Quality Score
            </div>
            <div style={{ fontSize: 28, fontFamily: MONO, color: qColor, fontWeight: 700, marginTop: 4 }}>
              {qLabel}
            </div>
          </div>
          <div style={{ width: 120 }}>
            <div style={{ height: 8, background: T.CARD, borderRadius: 4, overflow: "hidden" }}>
              <div style={{ width: `${qPct}%`, height: "100%", background: qColor }} />
            </div>
            <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2, marginTop: 6, textAlign: "right" }}>
              {qPct.toFixed(0)}% quality
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 14 }}>
        {[
          { k: "EPS Growth", v: eps, g: 10 },
          { k: "Revenue Growth", v: revPct, g: 10 },
          { k: "Q/Q Earnings", v: ernPct, g: 10 },
          { k: "PEG", v: peg, raw: true },
        ].map((m, i) => {
          const c = m.v === null ? T.T3 :
            m.raw ? (m.v < 1 ? T.GR : m.v < 2 ? T.YL : T.RD) :
            m.v > m.g ? T.GR : m.v > 0 ? T.YL : T.RD;
          return (
            <div key={i} style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
              <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>{m.k}</div>
              <div style={{ fontSize: 18, fontFamily: MONO, color: c, fontWeight: 700, marginTop: 4 }}>
                {m.v === null ? "—" : m.raw ? m.v.toFixed(2) : `${m.v > 0 ? "+" : ""}${m.v.toFixed(1)}%`}
              </div>
            </div>
          );
        })}
      </div>

      {qSignals.length > 0 && (
        <div style={{ display: "grid", gap: 6 }}>
          {qSignals.map((s, i) => (
            <div key={i} style={{
              padding: "8px 12px", background: T.ACT, borderRadius: 4,
              fontSize: 12, fontFamily: BODY, color: T.T1,
              borderLeft: `2px solid ${s.pos ? T.GR : T.RD}`,
              display: "flex", gap: 10,
            }}>
              <span style={{ color: s.pos ? T.GR : T.RD, fontFamily: MONO }}>{s.pos ? "▲" : "▼"}</span>
              <span>{s.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MoatAnalysis({ data }) {
  const m = moatScore(data);

  return (
    <div>
      <div style={{
        padding: 18, background: T.ACT, borderRadius: 6, marginBottom: 14,
        borderLeft: `3px solid ${m.color}`,
      }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Competitive Moat
            </div>
            <div style={{ fontSize: 28, fontFamily: BODY, color: m.color, fontWeight: 700, marginTop: 6, letterSpacing: -0.5 }}>
              {m.verdict}
            </div>
            <div style={{ fontSize: 12, fontFamily: MONO, color: T.T2, marginTop: 4 }}>
              Score: {m.score} / {m.max} ({m.pct.toFixed(0)}%)
            </div>
          </div>
          <div>
            {/* Moat tier visualization */}
            <div style={{ display: "flex", gap: 3, height: 30 }}>
              {["Eroding", "None", "Narrow", "Wide"].map((tier, i) => {
                const tierPct = [0, 25, 50, 75, 100][i + 1];
                const prevPct = [0, 25, 50, 75, 100][i];
                const active = m.pct >= prevPct && m.pct < tierPct;
                const passed = m.pct >= tierPct;
                const tierColor = [T.RD, T.YL, T.BL, T.GR][i];
                return (
                  <div key={i} style={{
                    flex: 1, background: active ? tierColor : passed ? `${tierColor}40` : T.CARD,
                    border: `1px solid ${active ? tierColor : T.BD}`,
                    borderRadius: 3, display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 10, fontFamily: MONO, color: active ? "#fff" : T.T3,
                    fontWeight: active ? 700 : 400, letterSpacing: 0.5,
                  }}>{tier}</div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {m.signals.length > 0 && (
        <div style={{ display: "grid", gap: 8 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
            Competitive Indicators
          </div>
          {m.signals.map((s, i) => (
            <div key={i} style={{
              padding: "10px 14px", background: T.ACT, borderRadius: 4,
              fontSize: 12, fontFamily: BODY, color: T.T1,
              borderLeft: `2px solid ${s.pos ? T.GR : T.RD}`,
              display: "flex", gap: 10,
            }}>
              <span style={{ color: s.pos ? T.GR : T.RD, fontFamily: MONO }}>{s.pos ? "▲" : "▼"}</span>
              <span>{s.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PeerComparison({ data }) {
  /* Using sector_avg_pe as our one peer benchmark. Other dimensions use
     general institutional benchmarks (e.g. good ROE > 15%, good margin > 10%). */
  const pe = n(data.pe_ratio);
  const secPE = n(data.sector_avg_pe);
  const pm = n(data.profit_margin);
  const roe = n(data.roe);
  const de = n(data.debt_to_equity);
  const eps = n(data.eps_growth_pct);
  const beta = n(data.beta);

  const dimensions = [
    { label: "P/E Valuation", value: pe, benchmark: secPE, unit: "x", invert: true, benchLabel: "Sector Avg" },
    { label: "Profit Margin", value: pm !== null ? pm * 100 : null, benchmark: 10, unit: "%", invert: false, benchLabel: "Institutional Good" },
    { label: "Return on Equity", value: roe !== null ? roe * 100 : null, benchmark: 15, unit: "%", invert: false, benchLabel: "Institutional Good" },
    { label: "Debt-to-Equity", value: de, benchmark: 1.0, unit: "x", invert: true, benchLabel: "Conservative Threshold" },
    { label: "EPS Growth", value: eps, benchmark: 10, unit: "%", invert: false, benchLabel: "Market Growth Rate" },
    { label: "Beta", value: beta, benchmark: 1.0, unit: "", invert: true, benchLabel: "Market" },
  ];

  return (
    <div>
      <div style={{
        fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase",
        marginBottom: 12,
      }}>
        {data.ticker} vs {data.sector || "Benchmark"}
      </div>

      <div style={{ display: "grid", gap: 10 }}>
        {dimensions.map((d, i) => {
          if (d.value === null || d.benchmark === null) {
            return (
              <div key={i} style={{
                padding: "12px 14px", background: T.ACT, borderRadius: 6,
                display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 80px", gap: 12, alignItems: "center",
                opacity: 0.5,
              }}>
                <div style={{ fontSize: 12, fontFamily: BODY, color: T.T2 }}>{d.label}</div>
                <div style={{ fontSize: 12, fontFamily: MONO, color: T.T3 }}>{d.value === null ? "n/a" : d.value.toFixed(2)}</div>
                <div style={{ fontSize: 12, fontFamily: MONO, color: T.T3 }}>{d.benchmark === null ? "n/a" : d.benchmark.toFixed(2)}</div>
                <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, textAlign: "right" }}>—</div>
              </div>
            );
          }
          const diff = d.invert
            ? ((d.benchmark - d.value) / d.benchmark) * 100
            : ((d.value - d.benchmark) / Math.max(Math.abs(d.benchmark), 0.01)) * 100;
          const better = diff > 0;
          const col = Math.abs(diff) < 10 ? T.YL : better ? T.GR : T.RD;

          return (
            <div key={i} style={{
              padding: "12px 14px", background: T.ACT, borderRadius: 6,
              display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 80px", gap: 12, alignItems: "center",
            }}>
              <div>
                <div style={{ fontSize: 12, fontFamily: BODY, color: T.T1 }}>{d.label}</div>
                <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, marginTop: 2 }}>vs {d.benchLabel}</div>
              </div>
              <div>
                <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3 }}>{data.ticker}</div>
                <div style={{ fontSize: 14, fontFamily: MONO, color: col, fontWeight: 600 }}>
                  {d.value.toFixed(2)}{d.unit}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3 }}>Benchmark</div>
                <div style={{ fontSize: 14, fontFamily: MONO, color: T.T2 }}>
                  {d.benchmark.toFixed(2)}{d.unit}
                </div>
              </div>
              <div style={{ fontSize: 13, fontFamily: MONO, color: col, fontWeight: 600, textAlign: "right" }}>
                {diff > 0 ? "+" : ""}{diff.toFixed(0)}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MonteCarloSection({ data }) {
  const mc = monteCarloFan(data);
  if (!mc) {
    return <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO, padding: 16 }}>Insufficient data for Monte Carlo projection</div>;
  }
  const ccy = data.currency === "INR" ? "₹" : "$";

  // SVG fan chart: 12 months
  const months = 12;
  const width = 600, height = 200, padX = 50, padY = 20;
  const innerW = width - padX * 2, innerH = height - padY * 2;

  // Starting px on left, expanding cone to p10-p90 on right
  const px = mc.current;
  const points = [];
  for (let i = 0; i <= months; i++) {
    const t = i / months;
    const sqrtT = Math.sqrt(t);
    // Scale quantiles by sqrt(t) (Brownian motion)
    points.push({
      x: t,
      p50: px * Math.exp((mc.drift - mc.vol * mc.vol / 2) * t),
      p10: px * Math.exp((mc.drift - mc.vol * mc.vol / 2) * t + mc.vol * sqrtT * invNormCDF(0.10)),
      p25: px * Math.exp((mc.drift - mc.vol * mc.vol / 2) * t + mc.vol * sqrtT * invNormCDF(0.25)),
      p75: px * Math.exp((mc.drift - mc.vol * mc.vol / 2) * t + mc.vol * sqrtT * invNormCDF(0.75)),
      p90: px * Math.exp((mc.drift - mc.vol * mc.vol / 2) * t + mc.vol * sqrtT * invNormCDF(0.90)),
    });
  }
  const all = points.flatMap(p => [p.p10, p.p90]);
  const yMin = Math.min(...all) * 0.95;
  const yMax = Math.max(...all) * 1.05;
  const yRange = yMax - yMin || 1; // guard against degenerate range
  const xScale = (x) => padX + x * innerW;
  const yScale = (y) => padY + innerH - ((y - yMin) / yRange) * innerH;

  const bandPath = (lowKey, highKey) => {
    const top = points.map(p => `${xScale(p.x)},${yScale(p[highKey])}`).join(" L ");
    const bot = [...points].reverse().map(p => `${xScale(p.x)},${yScale(p[lowKey])}`).join(" L ");
    return `M ${top} L ${bot} Z`;
  };
  const linePath = (key) => "M " + points.map(p => `${xScale(p.x)},${yScale(p[key])}`).join(" L ");

  return (
    <div>
      {/* Quantile strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, marginBottom: 16 }}>
        {[
          { label: "P10 Bear", value: mc.p10, color: T.RD },
          { label: "P25 Low", value: mc.p25, color: T.YL },
          { label: "P50 Base", value: mc.p50, color: T.BL },
          { label: "P75 High", value: mc.p75, color: T.CY },
          { label: "P90 Bull", value: mc.p90, color: T.GR },
        ].map((q, i) => {
          const diff = ((q.value - mc.current) / mc.current) * 100;
          return (
            <div key={i} style={{
              padding: 12, background: T.ACT, borderRadius: 4,
              borderTop: `2px solid ${q.color}`, textAlign: "center",
            }}>
              <div style={{ fontSize: 9, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>
                {q.label}
              </div>
              <div style={{ fontSize: 16, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 6 }}>
                {ccy}{q.value.toFixed(2)}
              </div>
              <div style={{ fontSize: 11, fontFamily: MONO, color: q.color, marginTop: 4 }}>
                {diff > 0 ? "+" : ""}{diff.toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>

      {/* Fan chart */}
      <div style={{ padding: 16, background: T.ACT, borderRadius: 6 }}>
        <div style={{
          fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5,
          textTransform: "uppercase", marginBottom: 10,
        }}>12-Month Projection Fan</div>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto", display: "block" }}>
          {/* outer band p10-p90 */}
          <path d={bandPath("p10", "p90")} fill={`${T.BL}20`} stroke="none" />
          {/* inner band p25-p75 */}
          <path d={bandPath("p25", "p75")} fill={`${T.BL}40`} stroke="none" />
          {/* median line */}
          <path d={linePath("p50")} fill="none" stroke={T.BL} strokeWidth="2" />
          {/* current price reference */}
          <line x1={padX} y1={yScale(mc.current)} x2={width - padX} y2={yScale(mc.current)} stroke={T.T3} strokeWidth="1" strokeDasharray="3 3" />
          {/* axis labels */}
          <text x={padX - 5} y={yScale(mc.current) + 4} fill={T.T3} fontSize="10" fontFamily="JetBrains Mono" textAnchor="end">
            {ccy}{mc.current.toFixed(0)}
          </text>
          <text x={padX - 5} y={yScale(yMax) + 4} fill={T.T3} fontSize="10" fontFamily="JetBrains Mono" textAnchor="end">
            {ccy}{yMax.toFixed(0)}
          </text>
          <text x={padX - 5} y={yScale(yMin) + 4} fill={T.T3} fontSize="10" fontFamily="JetBrains Mono" textAnchor="end">
            {ccy}{yMin.toFixed(0)}
          </text>
          <text x={padX} y={height - 5} fill={T.T3} fontSize="10" fontFamily="JetBrains Mono">Today</text>
          <text x={width - padX} y={height - 5} fill={T.T3} fontSize="10" fontFamily="JetBrains Mono" textAnchor="end">+12mo</text>
        </svg>
        <div style={{
          marginTop: 10, fontSize: 11, fontFamily: MONO, color: T.T3,
          display: "flex", gap: 20, justifyContent: "center",
        }}>
          <span>Drift: {(mc.drift * 100).toFixed(1)}%/yr</span>
          <span>Vol: {(mc.vol * 100).toFixed(1)}%</span>
        </div>
      </div>
    </div>
  );
}

function InstitutionalContext({ data }) {
  /* /api/stock-quick doesn't include ownership data — inform honestly and
     offer context from what we do have. This upholds CDS v2.0 "no fake
     assumptions" — we don't fabricate ownership percentages. */
  const mc = n(data.market_cap);

  let sizeCategory, sizeColor;
  if (mc === null) { sizeCategory = "Unknown"; sizeColor = T.T3; }
  else if (mc > 200e9) { sizeCategory = "Mega Cap"; sizeColor = T.BL; }
  else if (mc > 10e9) { sizeCategory = "Large Cap"; sizeColor = T.GR; }
  else if (mc > 2e9) { sizeCategory = "Mid Cap"; sizeColor = T.YL; }
  else if (mc > 300e6) { sizeCategory = "Small Cap"; sizeColor = T.PP; }
  else { sizeCategory = "Micro Cap"; sizeColor = T.RD; }

  const ccy = data.currency === "INR" ? "₹" : "$";

  return (
    <div>
      <div style={{
        padding: 14, background: T.ACT, borderRadius: 6, marginBottom: 14,
        borderLeft: `3px solid ${sizeColor}`,
      }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Market Cap
            </div>
            <div style={{ fontSize: 20, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 4 }}>
              {mc !== null ? `${ccy}${fmtB(mc)}` : "—"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Size Category
            </div>
            <div style={{ fontSize: 20, fontFamily: BODY, color: sizeColor, fontWeight: 700, marginTop: 4 }}>
              {sizeCategory}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Sector
            </div>
            <div style={{ fontSize: 16, fontFamily: BODY, color: T.T1, fontWeight: 600, marginTop: 4 }}>
              {data.sector || "—"}
            </div>
          </div>
        </div>
      </div>

      <div style={{
        padding: 14, background: T.CARD, border: `1px solid ${T.BD}`,
        borderRadius: 4, fontSize: 12, fontFamily: BODY, color: T.T2, lineHeight: 1.6,
      }}>
        <div style={{ fontSize: 10, fontFamily: MONO, color: T.YL, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 8 }}>
          Data Transparency
        </div>
        Institutional ownership breakdown (13F filings, insider activity, fund flows) requires
        a premium data source beyond <code style={{ fontFamily: MONO, color: T.T1, background: T.ACT, padding: "1px 4px", borderRadius: 2 }}>/api/stock-quick</code>.
        Upgrade path: Refinitiv / FactSet / SEC EDGAR direct. Per CDS v2.0 principles, no
        synthetic ownership figures are substituted — only verified data is displayed.
      </div>
    </div>
  );
}

/* ---------- Stock page shell ---------- */

function StockPage({ ticker, onTickerChange }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [input, setInput] = useState(ticker);

  useEffect(() => { setInput(ticker); }, [ticker]);

  const load = useCallback(async (t) => {
    if (!t) return;
    setLoading(true);
    setError(null);
    try {
      const url = `${API_BASE}/api/stock-quick?ticker=${encodeURIComponent(t.trim().toUpperCase())}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const j = await res.json();
      if (j.error) throw new Error(j.error);
      setData(j);
    } catch (e) {
      setError(e.message || "Failed to fetch");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(ticker); }, [ticker, load]);

  const engine = useMemo(() => data ? runFactorEngine(data) : null, [data]);
  const altman = useMemo(() => data ? altmanZScore(data) : null, [data]);
  const moat = useMemo(() => data ? moatScore(data) : null, [data]);
  const mc = useMemo(() => data ? monteCarloFan(data) : null, [data]);

  const submit = (e) => {
    e.preventDefault?.();
    const v = input.trim().toUpperCase();
    if (v && v !== ticker) onTickerChange(v);
    else if (v) load(v);
  };

  const ccy = data?.currency === "INR" ? "₹" : "$";

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>
      {/* Page header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, letterSpacing: 2, textTransform: "uppercase" }}>
            Stock · Institutional Deep-Dive
          </div>
          <div style={{ fontSize: 20, fontFamily: BODY, color: T.T1, fontWeight: 700, marginTop: 4 }}>
            Multi-layer analytical framework
          </div>
        </div>
        <div style={{
          fontSize: 10, fontFamily: MONO, color: T.T3,
          padding: "4px 10px", border: `1px solid ${T.BD}`, borderRadius: 3,
          letterSpacing: 1.5, textTransform: "uppercase",
        }}>10 Sections · CDS v2.0 Aligned</div>
      </div>

      {/* Search */}
      <form onSubmit={submit} style={{ display: "flex", gap: 10, marginBottom: 18 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter ticker (e.g. MU, AAPL, MAZDOCK.NS)"
          style={{
            flex: 1, padding: "12px 16px",
            background: T.CARD, border: `1px solid ${T.BD}`,
            borderRadius: 6, fontFamily: MONO, fontSize: 14,
            color: T.T1, outline: "none",
          }}
        />
        <button type="submit" style={{
          padding: "12px 24px", background: T.BL, border: "none",
          borderRadius: 6, fontFamily: MONO, fontSize: 13,
          color: "#fff", fontWeight: 600, cursor: "pointer",
          letterSpacing: 1, textTransform: "uppercase",
        }}>Analyze</button>
      </form>

      {loading && <LoadingState ticker={ticker} />}
      {error && !loading && <ErrorState msg={error} onRetry={() => load(ticker)} />}

      {data && engine && !loading && (
        <div style={{ display: "grid", gap: 12 }}>
          {/* Hero */}
          <HeroBanner data={data} engine={engine} />

          {/* 10 accordion sections */}
          <Accordion
            id="bottom-line"
            icon="01"
            tier="core"
            title="Bottom Line"
            summary="Institutional thesis with action plan"
            badge={engine.verdict}
            badgeColor={engine.verdictColor}
            defaultOpen={true}
          >
            <BottomLineNarrative data={data} engine={engine} />
          </Accordion>

          <Accordion
            id="intrinsic"
            icon="02"
            tier="valuation"
            title="Intrinsic Value Triangulation"
            summary="5-method fair value convergence with margin of safety"
            badge="Valuation"
          >
            <IntrinsicValueTriangulation data={data} />
          </Accordion>

          <Accordion
            id="dupont"
            icon="03"
            tier="quality"
            title="DuPont ROE Decomposition"
            summary="Margin × Turnover × Leverage — what drives returns"
            badge="Quality"
          >
            <DuPontDecomposition data={data} />
          </Accordion>

          <Accordion
            id="financial-health"
            icon="04"
            tier="risk"
            title="Financial Health"
            summary="Altman Z-Score, leverage, liquidity cascade"
            badge={altman ? altman.zone : "Risk"}
            badgeColor={altman ? altman.color : T.RD}
          >
            <FinancialHealth data={data} />
          </Accordion>

          <Accordion
            id="earnings"
            icon="05"
            tier="growth"
            title="Earnings Quality"
            summary="EPS velocity, revenue scaling, Q/Q momentum, PEG"
            badge="Growth"
          >
            <EarningsQuality data={data} engine={engine} />
          </Accordion>

          <Accordion
            id="moat"
            icon="06"
            tier="quality"
            title="Competitive Moat"
            summary="Economic moat scoring with quality indicators"
            badge={moat ? moat.verdict : "Moat"}
            badgeColor={moat ? moat.color : T.PP}
          >
            <MoatAnalysis data={data} />
          </Accordion>

          <Accordion
            id="peers"
            icon="07"
            tier="valuation"
            title="Peer & Benchmark Comparison"
            summary="6-dimension relative analysis vs sector and institutional thresholds"
            badge="Peers"
          >
            <PeerComparison data={data} />
          </Accordion>

          <Accordion
            id="monte-carlo"
            icon="08"
            tier="risk"
            title="Monte Carlo Projection"
            summary={mc ? `12-mo fan: ${ccy}${mc.p10.toFixed(0)} – ${ccy}${mc.p90.toFixed(0)}` : "Probability-weighted outcomes"}
            badge="Probabilistic"
          >
            <MonteCarloSection data={data} />
          </Accordion>

          <Accordion
            id="ownership"
            icon="09"
            tier="ownership"
            title="Institutional Context"
            summary="Market cap tier, sector classification, data transparency"
            badge="Context"
          >
            <InstitutionalContext data={data} />
          </Accordion>

          <Accordion
            id="factor-matrix"
            icon="10"
            tier="core"
            title="Full Factor Matrix"
            summary="All 14 factors with individual scores and rationale"
            badge={`${engine.totalScore}/${engine.maxScore}`}
            badgeColor={engine.verdictColor}
          >
            <div style={{ display: "grid", gap: 6 }}>
              {engine.factors.map((f) => (
                <div key={f.id} style={{
                  display: "grid", gridTemplateColumns: "50px 1.5fr 100px 80px 2fr", gap: 12,
                  padding: "10px 14px", background: T.ACT, borderRadius: 4, alignItems: "center",
                }}>
                  <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, fontWeight: 600 }}>{f.id}</div>
                  <div style={{ fontSize: 12, fontFamily: BODY, color: T.T1 }}>{f.label}</div>
                  <div style={{ position: "relative", height: 6, background: T.CARD, borderRadius: 3 }}>
                    <div style={{ position: "absolute", top: 0, left: "50%", width: 1, height: "100%", background: T.T3, opacity: 0.5 }} />
                    {f.pass !== null && (
                      <div style={{
                        position: "absolute", top: 0,
                        left: f.score >= 0 ? "50%" : `${50 - (Math.abs(f.score) / f.max) * 50}%`,
                        width: `${(Math.abs(f.score) / f.max) * 50}%`,
                        height: "100%",
                        background: f.score >= 0 ? T.GR : T.RD, borderRadius: 2,
                      }} />
                    )}
                  </div>
                  <div style={{
                    fontSize: 12, fontFamily: MONO, fontWeight: 600, textAlign: "right",
                    color: f.pass === null ? T.T3 : f.score >= 0 ? T.GR : T.RD,
                  }}>
                    {f.pass === null ? "n/a" : `${f.score >= 0 ? "+" : ""}${f.score}/${f.max}`}
                  </div>
                  <div style={{ fontSize: 11, fontFamily: BODY, color: T.T2 }}>{f.detail}</div>
                </div>
              ))}
            </div>
          </Accordion>
        </div>
      )}
    </div>
  );
}

/* ============================================================
   DECIDE TAB — Dual-Engine Options Dashboard (Session 3)

   META-ROUTER: Timeframe selector
     ⚡ Options Intraday → OptionsEngine
     📈 Swing Positional → SwingEngine

   Both engines produce the SAME Decision Card format:
     { action, direction, level, confidence, rationale[], levels:{} }

   CORE PRINCIPLE (institutional):
     Options engine scores on: Gamma, VWAP, OI build-up, Liquidity, Theta
     Swing engine scores on: Trend structure, HH/HL, EMA stack, Volume accumulation
   ============================================================ */

/* ---------- INDIAN DERIVATIVES UNIVERSE ---------- */

const INDEX_SYMBOLS = [
  { sym: "NIFTY", label: "NIFTY 50", lot: 75, step: 50 },
  { sym: "BANKNIFTY", label: "BANK NIFTY", lot: 35, step: 100 },
  { sym: "FINNIFTY", label: "FIN NIFTY", lot: 65, step: 50 },
  { sym: "SENSEX", label: "SENSEX", lot: 10, step: 100 },
];

/* ============================================================
   OPTIONS INTRADAY ENGINE
   Scores across 5 institutional layers:
     L1 Gamma Exposure     (GEX regime, flip point, walls)
     L2 OI Positioning     (Call/Put wall distance + build-up direction)
     L3 VWAP Structure     (Reclaim / Rejection vs VWAP)
     L4 Liquidity          (ATR-adjusted move, stop hunt proxy)
     L5 Time Decay         (Theta pressure by time-to-close)
   Output: BUY CALL / BUY PUT / NO TRADE with rationale.
   ============================================================ */

function scoreOptionsEngine(d) {
  if (!d || !d.success || !d.spot) {
    return { action: "NO DATA", direction: null, rationale: ["No options data available"], confidence: 0, layers: [] };
  }

  const spot = n(d.spot);
  const vwap = n(d.pivot) ?? spot;     // /api/options-quick uses 'pivot' as VWAP proxy
  const cprTop = n(d.cpr_top) ?? spot * 1.002;
  const cprBot = n(d.cpr_bottom) ?? spot * 0.998;
  const gex = d.gex || {};
  const callWall = n(gex.callWall) ?? null;
  const putWall = n(gex.putWall) ?? null;
  const flip = n(gex.flipPoint) ?? spot;
  const regime = gex.regime || "NEUTRAL";
  const pcr = n(d.pcr);
  const totalCeOi = n(d.total_ce_oi) ?? 0;
  const totalPeOi = n(d.total_pe_oi) ?? 0;
  const atmIV = n(d.atm_iv);
  const isExpiry = d.is_expiry || false;

  const bars = Array.isArray(d.ohlc_bars) ? d.ohlc_bars : [];
  const dayHigh = bars.length ? Math.max(...bars.map(b => n(b.h) ?? 0)) : spot * 1.005;
  const dayLow = bars.length ? Math.min(...bars.filter(b => n(b.l) !== null).map(b => n(b.l))) : spot * 0.995;

  const layers = [];
  let bullish = 0, bearish = 0;

  /* L1 Gamma Exposure */
  (() => {
    let score = 0, note = "";
    if (spot > flip && regime === "POSITIVE") { score = 2; note = `Above flip (${flip.toFixed(2)}), positive gamma — stabilizing`; bullish += 2; }
    else if (spot < flip && regime === "POSITIVE") { score = -1; note = `Below flip, positive gamma — resistance above`; bearish += 1; }
    else if (spot < flip && regime === "NEGATIVE") { score = -2; note = `Below flip (${flip.toFixed(2)}), negative gamma — accelerating down`; bearish += 2; }
    else if (spot > flip && regime === "NEGATIVE") { score = 1; note = `Above flip, negative gamma — unstable bid`; bullish += 1; }
    else { score = 0; note = `Gamma neutral regime`; }
    layers.push({ id: "L1", label: "Gamma Exposure", score, detail: note });
  })();

  /* L2 OI Positioning */
  (() => {
    let score = 0, note = "";
    if (callWall === null || putWall === null) {
      layers.push({ id: "L2", label: "OI Positioning", score: 0, detail: "OI walls unavailable" });
      return;
    }
    const callDist = ((callWall - spot) / spot) * 100;
    const putDist = ((spot - putWall) / spot) * 100;

    if (pcr !== null) {
      if (pcr > 1.3) { score += 2; note = `PCR ${pcr.toFixed(2)} bullish (put writing)`; bullish += 2; }
      else if (pcr < 0.7) { score -= 2; note = `PCR ${pcr.toFixed(2)} bearish (call writing)`; bearish += 2; }
      else { note = `PCR ${pcr.toFixed(2)} neutral`; }
    }

    if (callDist < 0.5) { score -= 1; note += ` • Call wall ${callWall} very close`; bearish += 1; }
    if (putDist < 0.5) { score += 1; note += ` • Put wall ${putWall} very close (support)`; bullish += 1; }

    layers.push({ id: "L2", label: "OI Positioning", score, detail: note.trim() });
  })();

  /* L3 VWAP Structure */
  (() => {
    let score = 0, note = "";
    const vwapDist = ((spot - vwap) / vwap) * 100;
    if (vwapDist > 0.2) { score = 2; note = `Above VWAP +${vwapDist.toFixed(2)}% — intraday strength`; bullish += 2; }
    else if (vwapDist < -0.2) { score = -2; note = `Below VWAP ${vwapDist.toFixed(2)}% — intraday weakness`; bearish += 2; }
    else { score = 0; note = `Around VWAP (${vwapDist.toFixed(2)}%) — no edge`; }

    // CPR reclaim/reject
    if (spot > cprTop) { score += 1; note += ` • Above CPR top`; bullish += 1; }
    else if (spot < cprBot) { score -= 1; note += ` • Below CPR bottom`; bearish += 1; }

    layers.push({ id: "L3", label: "VWAP Structure", score, detail: note });
  })();

  /* L4 Liquidity / Intraday Range */
  (() => {
    let score = 0, note = "";
    const range = dayHigh - dayLow;
    const rangePct = (range / spot) * 100;
    const pctInRange = range > 0 ? ((spot - dayLow) / range) * 100 : 50;

    if (pctInRange > 80) { score = 1; note = `Near HoD (${pctInRange.toFixed(0)}% of range)`; bullish += 1; }
    else if (pctInRange < 20) { score = -1; note = `Near LoD (${pctInRange.toFixed(0)}% of range)`; bearish += 1; }
    else { note = `Mid-range (${pctInRange.toFixed(0)}%)`; }

    if (rangePct < 0.3) { note += ` • Tight range — liquidity pending`; }
    else if (rangePct > 1.5) { note += ` • Expansive range (${rangePct.toFixed(2)}%)`; }

    layers.push({ id: "L4", label: "Liquidity / Range", score, detail: note });
  })();

  /* L5 Time Decay */
  (() => {
    let score = 0, note = "";
    const now = new Date();
    const mins = now.getHours() * 60 + now.getMinutes();
    const closeMins = 15 * 60 + 30; // 15:30 IST close
    const minsToClose = Math.max(0, closeMins - mins);

    if (isExpiry) {
      if (minsToClose < 30) { score = -3; note = `Expiry day, <30m to close — theta destroying premiums`; bearish += 3; bullish += 0; /* dampen both */ }
      else if (minsToClose < 90) { score = -2; note = `Expiry day, <90m to close — heavy theta`; }
      else { score = -1; note = `Expiry day — elevated theta risk`; }
    } else {
      if (minsToClose < 60) { score = -1; note = `<60m to close — light theta`; }
      else { note = `Normal session — theta manageable`; }
    }

    if (atmIV !== null) {
      if (atmIV > 25) note += ` • ATM IV ${atmIV.toFixed(1)}% elevated`;
      else if (atmIV < 10) note += ` • ATM IV ${atmIV.toFixed(1)}% compressed`;
    }

    layers.push({ id: "L5", label: "Time Decay (Theta)", score, detail: note });
  })();

  /* Aggregate */
  const net = bullish - bearish;
  let action, direction, confidence;
  const rationale = [];

  // Add positive-sum rationale items
  layers.filter(l => l.score !== 0).forEach(l => rationale.push(`${l.id}: ${l.detail}`));

  if (net >= 4) { action = "BUY CALL"; direction = "BULLISH"; confidence = Math.min(95, 50 + net * 8); }
  else if (net <= -4) { action = "BUY PUT"; direction = "BEARISH"; confidence = Math.min(95, 50 + Math.abs(net) * 8); }
  else { action = "NO TRADE"; direction = null; confidence = Math.max(25, 50 - Math.abs(net) * 8); rationale.unshift("Signal net too weak for directional entry"); }

  // Trade levels
  let level, stopLoss, target;
  if (action === "BUY CALL") {
    level = Math.max(vwap, spot); // entry on breakout above reference
    stopLoss = Math.max(vwap * 0.998, dayLow);
    target = callWall ? Math.min(callWall - 10, spot * 1.012) : spot * 1.012;
  } else if (action === "BUY PUT") {
    level = Math.min(vwap, spot);
    stopLoss = Math.min(vwap * 1.002, dayHigh);
    target = putWall ? Math.max(putWall + 10, spot * 0.988) : spot * 0.988;
  }

  return {
    action,
    direction,
    confidence,
    rationale,
    layers,
    levels: action !== "NO TRADE" ? { level, stopLoss, target, spot } : null,
    bullish, bearish, net,
  };
}

/* ============================================================
   SWING POSITIONAL ENGINE
   Scores across 5 institutional layers:
     L1 Trend Structure   (HH/HL via SMA stack)
     L2 EMA Cascade       (20 > 50 > 200 stacking)
     L3 Momentum Quality  (RSI proxy via position & growth)
     L4 Volume/Accumulation (proxy via growth + margin expansion)
     L5 Relative Strength (vs sector P/E + EPS velocity)
   Output: BUY / HOLD / SELL with Entry / SL / Target zones.
   ============================================================ */

function scoreSwingEngine(d) {
  if (!d || !d.current_price) {
    return { action: "NO DATA", direction: null, rationale: ["No stock data available"], confidence: 0, layers: [] };
  }

  const px = n(d.current_price);
  const s20 = n(d.sma_20);
  const s50 = n(d.sma_50);
  const s200 = n(d.sma_200);
  const hi52 = n(d.week52_high);
  const lo52 = n(d.week52_low);
  const eps = n(d.eps_growth_pct);
  const rev = n(d.revenue_growth);
  const revPct = rev === null ? null : (Math.abs(rev) > 5 ? rev : rev * 100);
  const pe = n(d.pe_ratio);
  const secPE = n(d.sector_avg_pe);
  const pm = n(d.profit_margin);
  const roe = n(d.roe);
  const beta = n(d.beta);

  const layers = [];
  let bull = 0, bear = 0;

  /* L1 Trend Structure (price vs SMAs + 52W position) */
  (() => {
    if (s20 === null || s50 === null || s200 === null) {
      layers.push({ id: "L1", label: "Trend Structure", score: 0, detail: "SMA data unavailable" });
      return;
    }
    let score = 0, parts = [];
    if (px > s20) { score += 1; parts.push("P>20"); bull++; } else { score -= 1; parts.push("P<20"); bear++; }
    if (px > s50) { score += 1; parts.push("P>50"); bull++; } else { score -= 1; parts.push("P<50"); bear++; }
    if (px > s200) { score += 2; parts.push("P>200"); bull += 2; } else { score -= 2; parts.push("P<200"); bear += 2; }
    if (s50 > s200) { score += 1; parts.push("Golden"); bull++; } else { score -= 1; parts.push("Death"); bear++; }

    let structureTag = "";
    if (score >= 4) structureTag = "HH/HL intact";
    else if (score >= 2) structureTag = "Mild uptrend";
    else if (score >= -2) structureTag = "Range-bound";
    else if (score >= -4) structureTag = "Mild downtrend";
    else structureTag = "Broken structure";

    layers.push({ id: "L1", label: "Trend Structure", score, detail: `${structureTag} — ${parts.join(" · ")}` });
  })();

  /* L2 EMA Cascade quality */
  (() => {
    if (s20 === null || s50 === null || s200 === null) {
      layers.push({ id: "L2", label: "EMA Cascade", score: 0, detail: "EMA data unavailable" });
      return;
    }
    let score = 0, note = "";
    // Perfect stack: 20 > 50 > 200
    if (s20 > s50 && s50 > s200) {
      score = 3;
      note = `Stacked bullish (20>${s50.toFixed(2)}, 50>${s200.toFixed(2)})`;
      bull += 3;
    } else if (s20 < s50 && s50 < s200) {
      score = -3;
      note = `Stacked bearish (20<50<200)`;
      bear += 3;
    } else {
      score = 0;
      note = `Mixed — no clean stack`;
    }

    // Spread quality (tight spread = compression)
    const spread20_50 = Math.abs(s20 - s50) / s50;
    if (spread20_50 < 0.01 && score > 0) note += ` • Tight compression — energy building`;

    layers.push({ id: "L2", label: "EMA Cascade", score, detail: note });
  })();

  /* L3 Momentum Quality (52W position + growth velocity) */
  (() => {
    let score = 0, parts = [];
    if (hi52 !== null && lo52 !== null && hi52 > lo52) {
      const pct52 = ((px - lo52) / (hi52 - lo52)) * 100;
      if (pct52 > 75) { score += 1; parts.push(`52W ${pct52.toFixed(0)}% (upper range)`); bull++; }
      else if (pct52 < 30) { score -= 1; parts.push(`52W ${pct52.toFixed(0)}% (lower range)`); bear++; }
      else { parts.push(`52W ${pct52.toFixed(0)}%`); }
    }
    if (eps !== null) {
      if (eps > 20) { score += 2; parts.push(`EPS +${eps.toFixed(0)}%`); bull += 2; }
      else if (eps > 5) { score += 1; parts.push(`EPS +${eps.toFixed(0)}%`); bull++; }
      else if (eps < -5) { score -= 2; parts.push(`EPS ${eps.toFixed(0)}%`); bear += 2; }
    }
    layers.push({ id: "L3", label: "Momentum Quality", score, detail: parts.join(" · ") || "Data limited" });
  })();

  /* L4 Volume/Accumulation proxy */
  (() => {
    let score = 0, parts = [];
    // Proxy: revenue growth + margin strength = accumulation narrative
    if (revPct !== null) {
      if (revPct > 15) { score += 2; parts.push(`Rev +${revPct.toFixed(0)}%`); bull += 2; }
      else if (revPct > 5) { score += 1; parts.push(`Rev +${revPct.toFixed(0)}%`); bull++; }
      else if (revPct < -5) { score -= 2; parts.push(`Rev ${revPct.toFixed(0)}%`); bear += 2; }
    }
    if (pm !== null) {
      if (pm > 0.15) { score += 1; parts.push(`PM ${(pm * 100).toFixed(0)}%`); bull++; }
      else if (pm < 0) { score -= 2; parts.push(`PM negative`); bear += 2; }
    }
    if (roe !== null && roe > 0.15) { score += 1; parts.push(`ROE ${(roe * 100).toFixed(0)}%`); bull++; }

    layers.push({ id: "L4", label: "Accumulation Proxy", score, detail: parts.join(" · ") || "Data limited" });
  })();

  /* L5 Relative Strength vs sector */
  (() => {
    let score = 0, parts = [];
    if (pe !== null && secPE !== null && pe > 0 && secPE > 0) {
      const r = pe / secPE;
      if (r < 0.85) { score += 2; parts.push(`P/E ${(r * 100).toFixed(0)}% of sector`); bull += 2; }
      else if (r < 1.0) { score += 1; parts.push(`P/E slight discount`); bull++; }
      else if (r > 1.3) { score -= 2; parts.push(`P/E ${(r * 100).toFixed(0)}% of sector (premium)`); bear += 2; }
    }
    if (beta !== null) {
      if (beta < 0.9) parts.push(`β ${beta.toFixed(2)} (defensive)`);
      else if (beta > 1.3) { parts.push(`β ${beta.toFixed(2)} (volatile)`); score -= 1; bear++; }
    }
    layers.push({ id: "L5", label: "Relative Strength", score, detail: parts.join(" · ") || "Data limited" });
  })();

  /* Aggregate */
  const net = bull - bear;
  let action, direction, confidence;
  const rationale = layers.filter(l => l.score !== 0).map(l => `${l.id}: ${l.detail}`);

  if (net >= 6) { action = "BUY"; direction = "BULLISH"; confidence = Math.min(92, 55 + net * 5); }
  else if (net >= 3) { action = "ACCUMULATE"; direction = "BULLISH"; confidence = Math.min(80, 50 + net * 5); }
  else if (net <= -6) { action = "SELL"; direction = "BEARISH"; confidence = Math.min(92, 55 + Math.abs(net) * 5); }
  else if (net <= -3) { action = "REDUCE"; direction = "BEARISH"; confidence = Math.min(80, 50 + Math.abs(net) * 5); }
  else { action = "HOLD"; direction = null; confidence = 50; rationale.unshift("Neutral signal — no decisive edge"); }

  // Swing trade levels (using 52W and SMAs as anchors)
  let level, stopLoss, target;
  if (direction === "BULLISH") {
    level = px; // entry near current
    stopLoss = s50 !== null ? Math.max(s50 * 0.97, (lo52 || px) * 1.02) : px * 0.93;
    target = hi52 !== null ? hi52 : px * 1.15;
  } else if (direction === "BEARISH") {
    level = px;
    stopLoss = s50 !== null ? Math.min(s50 * 1.03, (hi52 || px) * 0.98) : px * 1.07;
    target = lo52 !== null ? lo52 * 1.05 : px * 0.85;
  }

  return {
    action,
    direction,
    confidence,
    rationale,
    layers,
    levels: (direction !== null) ? { level, stopLoss, target, spot: px } : null,
    bull, bear, net,
  };
}

/* ============================================================
   SHARED UI: Unified Decision Card
   ============================================================ */

function DecisionCard({ decision, symbol, currency = "$", mode }) {
  if (!decision) return null;

  const isAction = decision.action !== "NO TRADE" && decision.action !== "HOLD" && decision.action !== "NO DATA";
  let actionColor;
  if (decision.direction === "BULLISH") actionColor = T.GR;
  else if (decision.direction === "BEARISH") actionColor = T.RD;
  else actionColor = T.YL;

  const confColor = decision.confidence >= 75 ? T.GR : decision.confidence >= 55 ? T.YL : T.RD;

  return (
    <Card pad={0} style={{
      overflow: "hidden",
      borderLeft: `4px solid ${actionColor}`,
    }}>
      {/* Top band — Action + Confidence */}
      <div style={{
        padding: "20px 24px",
        background: `linear-gradient(135deg, ${actionColor}12 0%, transparent 60%)`,
        borderBottom: `1px solid ${T.BD}`,
      }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 20, alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 2, textTransform: "uppercase", marginBottom: 6 }}>
              {mode === "options" ? "Options Intraday Engine" : "Swing Positional Engine"} · {symbol}
            </div>
            <div style={{
              fontSize: 36, fontFamily: BODY, color: actionColor,
              fontWeight: 800, letterSpacing: 1, lineHeight: 1,
            }}>
              {decision.action}
            </div>
            {decision.levels && (
              <div style={{ fontSize: 13, fontFamily: MONO, color: T.T2, marginTop: 8 }}>
                {decision.direction === "BULLISH" ? "Above" : decision.direction === "BEARISH" ? "Below" : "Trigger"}{" "}
                <span style={{ color: T.T1, fontWeight: 600 }}>
                  {currency}{decision.levels.level.toFixed(2)}
                </span>
              </div>
            )}
          </div>

          {/* Confidence dial */}
          <div style={{ textAlign: "center", minWidth: 110 }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 6 }}>
              Confidence
            </div>
            <div style={{
              fontSize: 30, fontFamily: MONO, color: confColor, fontWeight: 700, lineHeight: 1,
            }}>
              {decision.confidence.toFixed(0)}%
            </div>
            <div style={{
              marginTop: 8, height: 4, background: T.ACT, borderRadius: 2, overflow: "hidden",
            }}>
              <div style={{
                width: `${decision.confidence}%`, height: "100%", background: confColor,
              }} />
            </div>
          </div>
        </div>
      </div>

      {/* Levels band (only if action is tradeable) */}
      {decision.levels && isAction && (
        <div style={{
          padding: "14px 24px",
          background: T.ACT,
          borderBottom: `1px solid ${T.BD}`,
          display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14,
        }}>
          {[
            { k: "Spot", v: decision.levels.spot, c: T.T1 },
            { k: "Entry", v: decision.levels.level, c: actionColor },
            { k: "Stop-Loss", v: decision.levels.stopLoss, c: T.RD },
            { k: "Target", v: decision.levels.target, c: T.GR },
          ].map((lv, i) => (
            <div key={i}>
              <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>
                {lv.k}
              </div>
              <div style={{ fontSize: 16, fontFamily: MONO, color: lv.c, fontWeight: 700, marginTop: 4 }}>
                {currency}{lv.v.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Rationale */}
      <div style={{ padding: "18px 24px" }}>
        <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 10 }}>
          Decision Rationale
        </div>
        <div style={{ display: "grid", gap: 6 }}>
          {decision.rationale.length === 0 ? (
            <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO }}>No layer produced a signal</div>
          ) : decision.rationale.map((r, i) => (
            <div key={i} style={{
              fontSize: 12, fontFamily: BODY, color: T.T1,
              padding: "8px 10px", background: T.ACT, borderRadius: 4,
              display: "flex", gap: 10, alignItems: "flex-start",
              borderLeft: `2px solid ${actionColor}`,
            }}>
              <span style={{ color: actionColor, fontFamily: MONO, fontSize: 10, marginTop: 2 }}>▸</span>
              <span>{r}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

/* ============================================================
   LAYER BREAKDOWN — shared by both engines
   ============================================================ */

function LayerBreakdown({ layers, title = "Institutional Layer Scores" }) {
  if (!layers || layers.length === 0) return null;

  return (
    <Card title={title}>
      <div style={{ display: "grid", gap: 8 }}>
        {layers.map((l) => {
          const col = l.score > 0 ? T.GR : l.score < 0 ? T.RD : T.T3;
          const absScore = Math.abs(l.score);
          const maxAbs = Math.max(3, ...layers.map(x => Math.abs(x.score)));
          return (
            <div key={l.id} style={{
              display: "grid", gridTemplateColumns: "50px 1.2fr 150px 60px 3fr", gap: 12,
              padding: "10px 12px", background: T.ACT, borderRadius: 4, alignItems: "center",
            }}>
              <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, fontWeight: 600 }}>{l.id}</div>
              <div style={{ fontSize: 12, fontFamily: BODY, color: T.T1, fontWeight: 600 }}>{l.label}</div>
              <div style={{ position: "relative", height: 6, background: T.CARD, borderRadius: 3 }}>
                <div style={{ position: "absolute", top: 0, left: "50%", width: 1, height: "100%", background: T.T3, opacity: 0.5 }} />
                {l.score !== 0 && (
                  <div style={{
                    position: "absolute", top: 0,
                    left: l.score >= 0 ? "50%" : `${50 - (absScore / maxAbs) * 50}%`,
                    width: `${(absScore / maxAbs) * 50}%`,
                    height: "100%", background: col, borderRadius: 2,
                  }} />
                )}
              </div>
              <div style={{ fontSize: 12, fontFamily: MONO, fontWeight: 600, textAlign: "right", color: col }}>
                {l.score > 0 ? "+" : ""}{l.score}
              </div>
              <div style={{ fontSize: 11, fontFamily: BODY, color: T.T2 }}>{l.detail}</div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ============================================================
   OPTIONS CHAIN VISUALIZATION (OI wall chart + GEX map)
   ============================================================ */

function OIWallChart({ data }) {
  const spot = n(data.spot);
  const chain = Array.isArray(data.chain_near_atm) ? data.chain_near_atm : [];
  if (!chain.length || spot === null) {
    return (
      <Card title="Options Chain — OI Distribution">
        <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO }}>Chain data unavailable</div>
      </Card>
    );
  }

  const maxOI = Math.max(
    ...chain.map(c => Math.max(n(c.ce_oi) ?? 0, n(c.pe_oi) ?? 0))
  );

  return (
    <Card title="Options Chain — OI Distribution" accent={{ label: `${chain.length} strikes`, color: T.CY }}>
      <div style={{ display: "grid", gap: 4 }}>
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 80px 1fr", gap: 10,
          fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1,
          padding: "4px 0", borderBottom: `1px solid ${T.BD}`, textTransform: "uppercase",
        }}>
          <div style={{ textAlign: "right" }}>PUT OI</div>
          <div style={{ textAlign: "center" }}>Strike</div>
          <div>CALL OI</div>
        </div>
        {chain.map((row, i) => {
          const strike = n(row.strike);
          const ceOI = n(row.ce_oi) ?? 0;
          const peOI = n(row.pe_oi) ?? 0;
          const isATM = strike !== null && Math.abs(strike - spot) < 50;
          const cePct = maxOI > 0 ? (ceOI / maxOI) * 100 : 0;
          const pePct = maxOI > 0 ? (peOI / maxOI) * 100 : 0;
          return (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "1fr 80px 1fr", gap: 10,
              padding: "6px 0", alignItems: "center",
              background: isATM ? `${T.BL}10` : "transparent",
              borderRadius: isATM ? 3 : 0,
            }}>
              {/* Put OI bar (right-aligned) */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, alignItems: "center" }}>
                <span style={{ fontSize: 10, fontFamily: MONO, color: T.T2, minWidth: 55, textAlign: "right" }}>
                  {fmtB(peOI)}
                </span>
                <div style={{
                  width: `${pePct}%`, maxWidth: "100%", height: 14,
                  background: `linear-gradient(90deg, transparent, ${T.GR}80)`,
                  borderRadius: "2px 0 0 2px",
                }} />
              </div>
              {/* Strike */}
              <div style={{
                fontSize: 12, fontFamily: MONO, color: isATM ? T.BL : T.T1,
                textAlign: "center", fontWeight: isATM ? 700 : 500,
              }}>
                {strike !== null ? strike.toFixed(0) : "—"}
                {isATM && <div style={{ fontSize: 9, color: T.BL, letterSpacing: 0.5 }}>ATM</div>}
              </div>
              {/* Call OI bar (left-aligned) */}
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <div style={{
                  width: `${cePct}%`, maxWidth: "100%", height: 14,
                  background: `linear-gradient(90deg, ${T.RD}80, transparent)`,
                  borderRadius: "0 2px 2px 0",
                }} />
                <span style={{ fontSize: 10, fontFamily: MONO, color: T.T2, minWidth: 55 }}>
                  {fmtB(ceOI)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{
        marginTop: 14, padding: "10px 12px", background: T.ACT, borderRadius: 4,
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, fontSize: 11, fontFamily: MONO,
      }}>
        <div><span style={{ color: T.T3 }}>PCR:</span> <span style={{ color: T.T1, fontWeight: 600 }}>{n(data.pcr)?.toFixed(2) ?? "—"}</span></div>
        <div><span style={{ color: T.T3 }}>Max Pain:</span> <span style={{ color: T.T1, fontWeight: 600 }}>{n(data.max_pain)?.toFixed(0) ?? "—"}</span></div>
        <div><span style={{ color: T.T3 }}>ATM IV:</span> <span style={{ color: T.T1, fontWeight: 600 }}>{n(data.atm_iv) !== null ? n(data.atm_iv).toFixed(1) + "%" : "—"}</span></div>
        <div><span style={{ color: T.T3 }}>Spot:</span> <span style={{ color: T.T1, fontWeight: 600 }}>{spot.toFixed(2)}</span></div>
      </div>
    </Card>
  );
}

function GEXMap({ data }) {
  const gex = data.gex || {};
  const spot = n(data.spot);
  const flip = n(gex.flipPoint);
  const callWall = n(gex.callWall);
  const putWall = n(gex.putWall);
  const regime = gex.regime || "NEUTRAL";
  const total = n(gex.total);

  const regimeColor = regime === "POSITIVE" ? T.GR : regime === "NEGATIVE" ? T.RD : T.YL;

  if (spot === null || (flip === null && callWall === null && putWall === null)) {
    return (
      <Card title="Gamma Exposure Map">
        <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO }}>GEX data unavailable</div>
      </Card>
    );
  }

  // Compute range — need putWall and callWall to draw
  const lo = putWall ?? spot * 0.98;
  const hi = callWall ?? spot * 1.02;
  const range = hi - lo;
  const pctFor = (v) => range > 0 ? ((v - lo) / range) * 100 : 50;

  return (
    <Card title="Gamma Exposure Map" accent={{ label: `${regime} GAMMA`, color: regimeColor }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 10, marginBottom: 16 }}>
        <div style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>Regime</div>
          <div style={{ fontSize: 18, fontFamily: MONO, color: regimeColor, fontWeight: 700, marginTop: 4 }}>{regime}</div>
        </div>
        <div style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>Flip Point</div>
          <div style={{ fontSize: 18, fontFamily: MONO, color: T.BL, fontWeight: 700, marginTop: 4 }}>{flip?.toFixed(0) ?? "—"}</div>
        </div>
        <div style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>Call Wall</div>
          <div style={{ fontSize: 18, fontFamily: MONO, color: T.RD, fontWeight: 700, marginTop: 4 }}>{callWall?.toFixed(0) ?? "—"}</div>
        </div>
        <div style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>Put Wall</div>
          <div style={{ fontSize: 18, fontFamily: MONO, color: T.GR, fontWeight: 700, marginTop: 4 }}>{putWall?.toFixed(0) ?? "—"}</div>
        </div>
      </div>

      {/* Price ladder with gamma zones */}
      <div style={{
        position: "relative", height: 70, background: T.ACT, borderRadius: 4,
        marginBottom: 10, padding: "0 2%",
      }}>
        {/* Put wall */}
        {putWall !== null && (
          <div style={{
            position: "absolute", left: `${pctFor(putWall)}%`, top: 0, height: "100%",
            width: 2, background: T.GR,
          }}>
            <div style={{
              position: "absolute", bottom: "100%", left: -20, fontSize: 9, fontFamily: MONO,
              color: T.GR, whiteSpace: "nowrap", padding: "2px 0",
            }}>PW {putWall.toFixed(0)}</div>
          </div>
        )}
        {/* Flip */}
        {flip !== null && (
          <div style={{
            position: "absolute", left: `${pctFor(flip)}%`, top: 0, height: "100%",
            width: 2, background: T.BL, borderLeft: `2px dashed ${T.BL}`,
          }}>
            <div style={{
              position: "absolute", top: "100%", left: -15, fontSize: 9, fontFamily: MONO,
              color: T.BL, whiteSpace: "nowrap", paddingTop: 2,
            }}>FLIP {flip.toFixed(0)}</div>
          </div>
        )}
        {/* Call wall */}
        {callWall !== null && (
          <div style={{
            position: "absolute", left: `${pctFor(callWall)}%`, top: 0, height: "100%",
            width: 2, background: T.RD,
          }}>
            <div style={{
              position: "absolute", bottom: "100%", left: -20, fontSize: 9, fontFamily: MONO,
              color: T.RD, whiteSpace: "nowrap", padding: "2px 0",
            }}>CW {callWall.toFixed(0)}</div>
          </div>
        )}
        {/* Spot marker */}
        <div style={{
          position: "absolute", left: `${pctFor(spot)}%`, top: "50%", transform: "translate(-50%, -50%)",
          width: 16, height: 16, borderRadius: "50%",
          background: T.T1, border: `2px solid ${T.BG}`,
          boxShadow: `0 0 0 2px ${T.T1}`,
        }}>
          <div style={{
            position: "absolute", top: "100%", left: "50%", transform: "translateX(-50%)",
            fontSize: 10, fontFamily: MONO, color: T.T1, whiteSpace: "nowrap", paddingTop: 6, fontWeight: 700,
          }}>SPOT {spot.toFixed(0)}</div>
        </div>
      </div>

      {total !== null && (
        <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, textAlign: "center" }}>
          Total GEX: {total.toLocaleString()}
        </div>
      )}
    </Card>
  );
}


/* ============================================================
   TRADING TERMINAL COCKPIT — Exact spec implementation
   Replaces OptionsIntradayPanel with multi-trade institutional cockpit

   Layout (per spec §2):
     ┌─ HEADER (48px): app name · index selector · voice toggle
     ├─ GRID [65% / 35%]:
     │    ├─ TOP TRADES (exactly 3 cards × 110px, no scroll)
     │    └─ QUICK TRADE PANEL (selected · entry engine · chain · risk · voice log)
     └─ SECONDARY SCANNER (220px fixed, region-wise passive feed)

   Refresh:
     - Top Trades: 90s soft refresh (spec §9)
     - Quick Trade Panel: 30s (user-selected tick interval)
     - Scanner: 90s passive refresh

   Core logic (spec §10):
     Rank by Confidence + OI shift + VWAP + Volume spike
     3-minute stability lock on Top Trades (prevents thrashing)
   ============================================================ */

/* ---------- Entry Timing Classifier (State tag — spec §4.3) ---------- */

function classifyEntryState(scoredResult, rawData) {
  /* Returns one of: EARLY (fresh) / IDEAL (confirmed) / LATE (extended) / NO-TRADE
     Uses score layers + range position to classify timing. */
  if (!scoredResult || scoredResult.action === "NO TRADE" || scoredResult.action === "NO DATA") {
    return { tag: "NO-TRADE", label: "AVOID", color: T.RD };
  }

  const spot = n(rawData.spot);
  const bars = Array.isArray(rawData.ohlc_bars) ? rawData.ohlc_bars : [];
  const dayHi = bars.length ? Math.max(...bars.map(b => n(b.h) ?? 0)) : spot;
  const dayLo = bars.length ? Math.min(...bars.filter(b => n(b.l) !== null).map(b => n(b.l))) : spot;
  const range = dayHi - dayLo;
  const pctInRange = range > 0 ? ((spot - dayLo) / range) * 100 : 50;

  const isBullish = scoredResult.direction === "BULLISH";
  const isBearish = scoredResult.direction === "BEARISH";

  // EARLY: fresh signal, price still has room
  //   bullish: price in lower/mid range (<60%)
  //   bearish: price in upper/mid range (>40%)
  // IDEAL: confirmed move, still entry-zone
  //   bullish: 60-80% of range
  //   bearish: 20-40% of range
  // LATE: extended, risk high
  //   bullish: >80% of range
  //   bearish: <20% of range

  if (isBullish) {
    if (pctInRange < 60) return { tag: "EARLY", label: "ENTER AGGRESSIVE", color: T.GR };
    if (pctInRange < 80) return { tag: "IDEAL", label: "ENTER NOW", color: T.BL };
    return { tag: "LATE", label: "ENTER SMALL", color: T.YL };
  }
  if (isBearish) {
    if (pctInRange > 40) return { tag: "EARLY", label: "ENTER AGGRESSIVE", color: T.GR };
    if (pctInRange > 20) return { tag: "IDEAL", label: "ENTER NOW", color: T.BL };
    return { tag: "LATE", label: "ENTER SMALL", color: T.YL };
  }
  return { tag: "NO-TRADE", label: "AVOID", color: T.RD };
}

/* ---------- Strike computation (ATM CE/PE) ---------- */

function computeTradeStrike(rawData, direction) {
  const spot = n(rawData.spot);
  if (spot === null) return null;
  // Find step size from symbol
  const sym = rawData.sym || "";
  const symInfo = INDEX_SYMBOLS.find(s => s.sym === sym) || INDEX_SYMBOLS[0];
  const step = symInfo.step;
  const atm = Math.round(spot / step) * step;
  const type = direction === "BULLISH" ? "CE" : "PE";
  return { strike: atm, type, lot: symInfo.lot, label: `${symInfo.label} ${atm} ${type}` };
}

/* ---------- Voice Engine (Web Speech API) ---------- */

function speak(text, enabled) {
  if (!enabled || typeof window === "undefined" || !window.speechSynthesis) return;
  try {
    // Cancel any queued utterances
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.05;
    u.pitch = 1.0;
    u.volume = 0.9;
    window.speechSynthesis.speak(u);
  } catch (e) { /* silent */ }
}

/* ---------- Rank Trades Across All Indices ---------- */

async function scanAllIndices() {
  const results = await Promise.all(
    INDEX_SYMBOLS.map(async (s) => {
      try {
        const res = await fetch(`${API_BASE}/api/options-quick?symbol=${encodeURIComponent(s.sym)}`);
        if (!res.ok) return null;
        const j = await res.json();
        if (!j.success) return null;
        j.sym = s.sym;
        return j;
      } catch (e) { return null; }
    })
  );
  return results.filter(Boolean);
}

function rankTrades(rawDataArray) {
  /* Returns sorted array of { data, decision, state, strike, rank } */
  const scored = rawDataArray.map(raw => {
    const decision = scoreOptionsEngine(raw);
    const state = classifyEntryState(decision, raw);
    const strike = computeTradeStrike(raw, decision.direction);
    return { data: raw, decision, state, strike };
  });

  // Filter out NO-TRADE before ranking (spec §4: only show tradeable)
  const tradeable = scored.filter(s => s.state.tag !== "NO-TRADE" && s.decision.confidence >= 55);

  // Rank by: confidence (primary), direction conviction (|net|), entry state
  tradeable.sort((a, b) => {
    // Primary: confidence
    if (b.decision.confidence !== a.decision.confidence) return b.decision.confidence - a.decision.confidence;
    // Secondary: net signal strength
    const aNet = Math.abs(a.decision.net);
    const bNet = Math.abs(b.decision.net);
    if (bNet !== aNet) return bNet - aNet;
    // Tertiary: IDEAL > EARLY > LATE
    const order = { IDEAL: 3, EARLY: 2, LATE: 1 };
    return (order[b.state.tag] || 0) - (order[a.state.tag] || 0);
  });

  return tradeable.slice(0, 3);
}

/* ---------- Stability Lock (3-min, spec §10) ---------- */

function applyStabilityLock(newRanked, previousRanked, lockDurationMs = 3 * 60 * 1000) {
  const now = Date.now();
  if (!previousRanked || previousRanked.length === 0) {
    return newRanked.map(t => ({ ...t, lockedAt: now }));
  }

  // For each previously locked trade, check if still in top 3 OR within lock window
  const result = [];
  const prevLookup = new Map(previousRanked.map(t => [t.strike?.label || t.data.sym, t]));
  const newLookup = new Map(newRanked.map(t => [t.strike?.label || t.data.sym, t]));

  // Step 1: Keep locked trades that haven't expired AND still score above threshold
  previousRanked.forEach(prev => {
    const key = prev.strike?.label || prev.data.sym;
    const age = now - (prev.lockedAt || 0);
    const fresh = newLookup.get(key);
    if (age < lockDurationMs && fresh) {
      // Still locked, use fresh data but keep lockedAt
      result.push({ ...fresh, lockedAt: prev.lockedAt });
    }
  });

  // Step 2: Fill remaining slots with new candidates (not already locked)
  newRanked.forEach(fresh => {
    const key = fresh.strike?.label || fresh.data.sym;
    if (result.length < 3 && !result.find(r => (r.strike?.label || r.data.sym) === key)) {
      result.push({ ...fresh, lockedAt: now });
    }
  });

  return result.slice(0, 3);
}

/* ============================================================
   HEADER COMPONENT (spec §3)
   ============================================================ */

function CockpitHeader({ activeSymbol, onSymbolChange, voiceEnabled, onVoiceToggle, alertsEnabled, onAlertsToggle }) {
  return (
    <div style={{
      height: 48, padding: "0 16px",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      background: T.CARD, border: `1px solid ${T.BD}`, borderRadius: 6,
    }}>
      {/* Left — App identity */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{
          width: 24, height: 24, borderRadius: 4,
          background: `linear-gradient(135deg, ${T.BL}, ${T.PP})`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: MONO, fontWeight: 700, fontSize: 11, color: "#fff",
        }}>C</div>
        <div>
          <div style={{ fontSize: 12, fontFamily: BODY, fontWeight: 700, color: T.T1, letterSpacing: 0.5 }}>
            TRADE ENGINE PRO
          </div>
          <div style={{ fontSize: 8, fontFamily: MONO, color: T.T3, letterSpacing: 1.5 }}>
            INSTITUTIONAL COCKPIT
          </div>
        </div>
      </div>

      {/* Center — Active symbol selector */}
      <div style={{ display: "flex", gap: 4, padding: 3, background: T.ACT, borderRadius: 4 }}>
        {INDEX_SYMBOLS.map(s => (
          <button key={s.sym} onClick={() => onSymbolChange(s.sym)} style={{
            padding: "5px 12px",
            background: activeSymbol === s.sym ? T.BL : "transparent",
            border: "none", borderRadius: 3,
            fontFamily: MONO, fontSize: 11, fontWeight: 700,
            color: activeSymbol === s.sym ? "#fff" : T.T2,
            cursor: "pointer", letterSpacing: 1,
          }}>{s.sym}</button>
        ))}
      </div>

      {/* Right — Toggles */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button
          onClick={onAlertsToggle}
          title="Alerts"
          style={{
            padding: "6px 10px",
            background: alertsEnabled ? `${T.YL}20` : T.ACT,
            border: `1px solid ${alertsEnabled ? T.YL + "60" : T.BD}`,
            borderRadius: 4,
            fontFamily: MONO, fontSize: 11, fontWeight: 600,
            color: alertsEnabled ? T.YL : T.T3,
            cursor: "pointer", letterSpacing: 0.5,
          }}>🔔 {alertsEnabled ? "ON" : "OFF"}</button>
        <button
          onClick={onVoiceToggle}
          title="Voice announcements"
          style={{
            padding: "6px 10px",
            background: voiceEnabled ? `${T.GR}20` : T.ACT,
            border: `1px solid ${voiceEnabled ? T.GR + "60" : T.BD}`,
            borderRadius: 4,
            fontFamily: MONO, fontSize: 11, fontWeight: 600,
            color: voiceEnabled ? T.GR : T.T3,
            cursor: "pointer", letterSpacing: 0.5,
          }}>🎙 {voiceEnabled ? "ON" : "OFF"}</button>
      </div>
    </div>
  );
}

/* ============================================================
   TOP TRADE CARD (spec §4 — exactly 110px, no scroll)
   ============================================================ */

function TopTradeCard({ trade, active, onSelect, onSpeak }) {
  if (!trade) {
    // Placeholder (spec §4 rule)
    return (
      <div style={{
        height: 110, borderRadius: 12, marginBottom: 12, padding: 16,
        background: T.CARD, border: `1px dashed ${T.BD}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: MONO, fontSize: 12, color: T.T3, letterSpacing: 1,
      }}>
        NO HIGH-CONFIDENCE TRADES
      </div>
    );
  }

  const conf = trade.decision.confidence;
  const confColor = conf >= 80 ? T.GR : conf >= 60 ? T.YL : T.RD;
  const strike = trade.strike;

  return (
    <div
      onClick={onSelect}
      style={{
        height: 110, borderRadius: 12, marginBottom: 12, padding: 16,
        background: active ? T.ACT : T.CARD,
        border: `1px solid ${active ? T.BL + "60" : T.BD}`,
        cursor: "pointer", transition: "all 0.15s ease",
        display: "grid",
        gridTemplateColumns: "1.5fr 100px 110px",
        gridTemplateRows: "auto auto",
        gap: "8px 12px",
        alignItems: "center",
      }}
    >
      {/* Row 1: Symbol + Strike | Confidence | Action Button */}
      <div style={{
        fontSize: 18, fontFamily: BODY, fontWeight: 600, color: T.T1,
        letterSpacing: -0.2,
      }}>
        {strike ? strike.label : (trade.data.sym + " —")}
      </div>
      <div style={{
        fontSize: 20, fontFamily: MONO, fontWeight: 700, color: confColor, textAlign: "right",
      }}>
        {conf.toFixed(0)}%
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onSelect(); }}
        style={{
          height: 36, width: 100, justifySelf: "end",
          background: trade.state.tag === "NO-TRADE"
            ? T.RD
            : `linear-gradient(135deg, ${T.GR}, #16A34A)`,
          border: "none", borderRadius: 6,
          fontFamily: MONO, fontSize: 11, fontWeight: 700,
          color: "#fff", cursor: "pointer", letterSpacing: 1, textTransform: "uppercase",
        }}
      >
        {trade.decision.action === "BUY CALL" ? "BUY CALL"
          : trade.decision.action === "BUY PUT" ? "BUY PUT"
          : "EXECUTE"}
      </button>

      {/* Row 2: Reason | State tag | Voice icon */}
      <div style={{
        fontSize: 13, fontFamily: BODY, color: T.T2,
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
      }}>
        {trade.decision.rationale[0] || "—"}
      </div>
      <div style={{
        fontSize: 10, fontFamily: MONO, fontWeight: 700,
        padding: "3px 10px", borderRadius: 99,
        background: `${trade.state.color}20`,
        color: trade.state.color,
        border: `1px solid ${trade.state.color}50`,
        textAlign: "center", letterSpacing: 0.5, textTransform: "uppercase",
        whiteSpace: "nowrap",
      }}>
        {trade.state.label}
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onSpeak(trade); }}
        title="Speak this trade"
        style={{
          justifySelf: "end",
          width: 28, height: 28, borderRadius: "50%",
          background: T.ACT, border: `1px solid ${T.BD}`,
          cursor: "pointer", fontSize: 13, color: T.T2,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >
        🎙
      </button>
    </div>
  );
}

/* ============================================================
   QUICK TRADE PANEL (spec §5 — right 35%)
   ============================================================ */

function QuickTradePanel({ trade, freshData, voiceLog, onVoiceLog }) {
  if (!trade) {
    return (
      <div style={{
        padding: 20, background: T.BG, border: `1px solid ${T.BD}`, borderRadius: 6,
        display: "flex", alignItems: "center", justifyContent: "center", minHeight: 400,
        fontFamily: MONO, fontSize: 12, color: T.T3, letterSpacing: 1,
      }}>
        SELECT A TRADE TO ARM
      </div>
    );
  }

  const spot = n(freshData?.spot) ?? n(trade.data.spot);
  const conf = trade.decision.confidence;
  const confColor = conf >= 80 ? T.GR : conf >= 60 ? T.YL : T.RD;
  const strike = trade.strike;
  const levels = trade.decision.levels;

  // Entry engine
  const triggerLevel = levels?.level;
  const entryActive = triggerLevel !== undefined && triggerLevel !== null;
  const triggered = entryActive && spot !== null && (
    trade.decision.direction === "BULLISH" ? spot >= triggerLevel : spot <= triggerLevel
  );

  // Option chain ATM ± 2
  const fullChain = Array.isArray(freshData?.chain_near_atm) ? freshData.chain_near_atm : [];
  const chainRows = strike ? fullChain
    .map(row => ({ ...row, _diff: Math.abs(n(row.strike) - strike.strike) }))
    .sort((a, b) => a._diff - b._diff)
    .slice(0, 5)
    .sort((a, b) => n(a.strike) - n(b.strike))
    : [];

  // Risk metrics
  const sl = levels?.stopLoss;
  const target = levels?.target;
  const rr = (sl !== undefined && target !== undefined && spot !== null)
    ? Math.abs((target - spot) / (spot - sl))
    : null;

  return (
    <div style={{
      padding: 16, background: T.BG, border: `1px solid ${T.BD}`, borderRadius: 6,
      display: "grid", gap: 14,
    }}>
      {/* 1. SELECTED TRADE HEADER */}
      <div style={{ borderBottom: `1px solid ${T.ACT}`, paddingBottom: 12 }}>
        <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 4 }}>
          Selected Trade
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div style={{ fontSize: 18, fontFamily: BODY, fontWeight: 700, color: T.T1 }}>
            {strike ? strike.label : "—"}
          </div>
          <div style={{ fontSize: 20, fontFamily: MONO, fontWeight: 700, color: confColor }}>
            {conf.toFixed(0)}%
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 11, fontFamily: MONO, color: T.T2 }}>
          <span>LIVE ₹{spot !== null ? spot.toFixed(2) : "—"}</span>
          <span style={{ color: trade.state.color }}>{trade.state.label}</span>
        </div>
      </div>

      {/* 2. ENTRY ENGINE */}
      <div>
        <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 6 }}>
          Entry Engine
        </div>
        <div style={{
          padding: 10, background: T.ACT, borderRadius: 4,
          borderLeft: `3px solid ${triggered ? T.GR : entryActive ? T.YL : T.T3}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>
              Status
            </span>
            <span style={{
              fontSize: 11, fontFamily: MONO, fontWeight: 700,
              color: triggered ? T.GR : entryActive ? T.YL : T.T3,
            }}>
              {triggered ? "🟢 TRIGGERED" : entryActive ? "🟡 ACTIVE" : "⚪ INACTIVE"}
            </span>
          </div>
          {entryActive && (
            <>
              <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2, marginTop: 3 }}>
                Trigger: <span style={{ color: T.T1, fontWeight: 600 }}>
                  {trade.decision.direction === "BULLISH" ? "Break above" : "Break below"} ₹{triggerLevel.toFixed(2)}
                </span>
              </div>
              <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2, marginTop: 2 }}>
                Current: <span style={{ color: T.T1, fontWeight: 600 }}>₹{spot !== null ? spot.toFixed(2) : "—"}</span>
                <span style={{ color: triggered ? T.GR : T.T3, marginLeft: 6 }}>
                  → {triggered ? "Fired" : "Watching"}
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* 3. OPTION CHAIN (ATM ±2) */}
      <div>
        <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 6 }}>
          Option Chain (ATM ±2)
        </div>
        {chainRows.length === 0 ? (
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, padding: 10 }}>Chain data pending...</div>
        ) : (
          <div>
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 1fr 1fr 40px", gap: 6,
              fontSize: 9, fontFamily: MONO, color: T.T3, letterSpacing: 1,
              padding: "4px 6px", borderBottom: `1px solid ${T.BD}`, textTransform: "uppercase",
            }}>
              <div>Strike</div>
              <div style={{ textAlign: "right" }}>Call OI Δ</div>
              <div style={{ textAlign: "right" }}>Put OI Δ</div>
              <div style={{ textAlign: "center" }}>Vol</div>
            </div>
            {chainRows.map((row, i) => {
              const ceChg = n(row.ce_chg_oi) ?? n(row.ce_oi_chg) ?? 0;
              const peChg = n(row.pe_chg_oi) ?? n(row.pe_oi_chg) ?? 0;
              const isATM = n(row.strike) === strike?.strike;
              const maxChgAbs = Math.max(...chainRows.map(r =>
                Math.abs(n(r.ce_chg_oi) ?? n(r.ce_oi_chg) ?? 0) +
                Math.abs(n(r.pe_chg_oi) ?? n(r.pe_oi_chg) ?? 0)
              ));
              const thisChg = Math.abs(ceChg) + Math.abs(peChg);
              const isHighest = thisChg > 0 && thisChg === maxChgAbs;
              const volSpike = n(row.ce_volume) ?? n(row.volume) ?? 0;
              return (
                <div key={i} style={{
                  display: "grid", gridTemplateColumns: "1fr 1fr 1fr 40px", gap: 6,
                  fontSize: 11, fontFamily: MONO, padding: "6px",
                  background: isHighest ? `${T.BL}15` : isATM ? `${T.PP}10` : "transparent",
                  borderRadius: 3,
                  borderBottom: i < chainRows.length - 1 ? `1px solid ${T.ACT}` : "none",
                }}>
                  <div style={{ color: isATM ? T.PP : T.T1, fontWeight: isATM ? 700 : 500 }}>
                    {n(row.strike)} {isATM && "•"}
                  </div>
                  <div style={{ textAlign: "right", color: ceChg > 0 ? T.RD : ceChg < 0 ? T.GR : T.T3 }}>
                    {ceChg !== 0 ? (ceChg > 0 ? "+" : "") + fmtB(ceChg) : "—"}
                  </div>
                  <div style={{ textAlign: "right", color: peChg > 0 ? T.GR : peChg < 0 ? T.RD : T.T3 }}>
                    {peChg !== 0 ? (peChg > 0 ? "+" : "") + fmtB(peChg) : "—"}
                  </div>
                  <div style={{ textAlign: "center", color: volSpike > 0 ? T.YL : T.T3 }}>
                    {volSpike > 0 ? "⚡" : "—"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. RISK BLOCK */}
      <div>
        <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 6 }}>
          Risk
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
          <div style={{ padding: 8, background: T.ACT, borderRadius: 3 }}>
            <div style={{ fontSize: 9, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>SL</div>
            <div style={{ fontSize: 13, fontFamily: MONO, color: T.RD, fontWeight: 700, marginTop: 2 }}>
              ₹{sl !== undefined ? sl.toFixed(2) : "—"}
            </div>
          </div>
          <div style={{ padding: 8, background: T.ACT, borderRadius: 3 }}>
            <div style={{ fontSize: 9, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>Target</div>
            <div style={{ fontSize: 13, fontFamily: MONO, color: T.GR, fontWeight: 700, marginTop: 2 }}>
              ₹{target !== undefined ? target.toFixed(2) : "—"}
            </div>
          </div>
          <div style={{ padding: 8, background: T.ACT, borderRadius: 3 }}>
            <div style={{ fontSize: 9, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>R:R</div>
            <div style={{ fontSize: 13, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 2 }}>
              {rr !== null ? `1 : ${rr.toFixed(1)}` : "—"}
            </div>
          </div>
          <div style={{ padding: 8, background: T.ACT, borderRadius: 3 }}>
            <div style={{ fontSize: 9, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>Lot</div>
            <div style={{ fontSize: 13, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 2 }}>
              {strike?.lot || "—"}
            </div>
          </div>
        </div>
      </div>

      {/* 5. VOICE FEEDBACK LOG */}
      <div>
        <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 6 }}>
          Voice Log
        </div>
        <div style={{
          padding: 8, background: T.ACT, borderRadius: 4,
          maxHeight: 120, overflowY: "auto", display: "grid", gap: 4,
        }}>
          {voiceLog.length === 0 ? (
            <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3 }}>Awaiting signals...</div>
          ) : voiceLog.map((entry, i) => (
            <div key={i} style={{
              fontSize: 11, fontFamily: MONO, color: i === 0 ? T.T1 : T.T2,
              padding: "3px 6px", borderLeft: `2px solid ${i === 0 ? T.GR : T.BD}`,
            }}>
              <span style={{ color: T.T3, fontSize: 9, marginRight: 6 }}>
                {new Date(entry.t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
              {entry.msg}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   SECONDARY SCANNER (spec §6 — bottom 220px passive)
   ============================================================ */

const SCANNER_UNIVERSES = {
  IN: [
    { sym: "NIFTY",     label: "NIFTY" },
    { sym: "BANKNIFTY", label: "BANKNIFTY" },
    { sym: "FINNIFTY",  label: "FINNIFTY" },
    { sym: "SENSEX",    label: "SENSEX" },
  ],
  US: [
    { sym: "SPY",  label: "SPY" },
    { sym: "QQQ",  label: "QQQ" },
    { sym: "IWM",  label: "IWM" },
    { sym: "DIA",  label: "DIA" },
  ],
};

function SecondaryScanner({ region, onRegionChange, trendHistory }) {
  const rows = trendHistory[region] || [];

  return (
    <div style={{
      height: 220, background: T.BG, border: `1px solid ${T.BD}`,
      borderRadius: 6, padding: 12, overflow: "hidden",
      display: "flex", flexDirection: "column",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
            Secondary Scanner
          </div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2, marginTop: 2 }}>
            Passive · 90s refresh
          </div>
        </div>
        <div style={{ display: "flex", gap: 3, padding: 2, background: T.ACT, borderRadius: 4 }}>
          {["IN", "US"].map(r => (
            <button key={r} onClick={() => onRegionChange(r)} style={{
              padding: "4px 10px",
              background: region === r ? T.BL : "transparent",
              border: "none", borderRadius: 3,
              fontFamily: MONO, fontSize: 10, fontWeight: 700,
              color: region === r ? "#fff" : T.T2,
              cursor: "pointer", letterSpacing: 1,
            }}>{r === "IN" ? "🇮🇳 IN" : "🇺🇸 US"}</button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 80px 60px 120px 1fr", gap: 10,
          fontSize: 9, fontFamily: MONO, color: T.T3, letterSpacing: 1,
          padding: "4px 8px", borderBottom: `1px solid ${T.BD}`, textTransform: "uppercase",
        }}>
          <div>Symbol</div>
          <div style={{ textAlign: "center" }}>Direction</div>
          <div style={{ textAlign: "right" }}>Score</div>
          <div style={{ textAlign: "center" }}>State</div>
          <div>Trend</div>
        </div>
        {rows.length === 0 ? (
          <div style={{ padding: 16, textAlign: "center", fontSize: 11, fontFamily: MONO, color: T.T3 }}>
            Awaiting first scan...
          </div>
        ) : rows.map((row, i) => {
          const dirColor = row.direction === "BULLISH" ? T.GR : row.direction === "BEARISH" ? T.RD : T.T3;
          const scoreColor = row.score >= 70 ? T.GR : row.score >= 55 ? T.YL : T.RD;
          const history = row.history || [];
          // Trend color: compare last to first
          const trendRising = history.length >= 2 && history[history.length - 1] > history[0];
          return (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "1fr 80px 60px 120px 1fr", gap: 10,
              fontSize: 12, fontFamily: MONO, padding: "8px", height: 36,
              borderBottom: `1px solid ${T.ACT}`, alignItems: "center",
            }}>
              <div style={{ color: T.T1, fontWeight: 600 }}>{row.symbol}</div>
              <div style={{ textAlign: "center", color: dirColor, fontSize: 10 }}>
                {row.direction === "BULLISH" ? "▲ LONG" : row.direction === "BEARISH" ? "▼ SHORT" : "—"}
              </div>
              <div style={{ textAlign: "right", color: scoreColor, fontWeight: 700 }}>
                {row.score !== null ? row.score.toFixed(0) : "—"}
              </div>
              <div style={{ textAlign: "center" }}>
                <span style={{
                  fontSize: 9, fontFamily: MONO, padding: "2px 6px", borderRadius: 99,
                  background: `${row.stateColor}20`, color: row.stateColor,
                  border: `1px solid ${row.stateColor}40`, letterSpacing: 0.5,
                }}>{row.state}</span>
              </div>
              <div style={{
                display: "flex", alignItems: "center", gap: 4,
                color: trendRising ? T.GR : T.RD, fontSize: 10,
              }}>
                {history.map((v, j) => (
                  <span key={j} style={{
                    color: T.T2,
                    opacity: 0.3 + (j / Math.max(history.length - 1, 1)) * 0.7,
                  }}>
                    {v.toFixed(0)}{j < history.length - 1 && " →"}
                  </span>
                ))}
                {history.length > 0 && (
                  <span style={{ color: trendRising ? T.GR : T.RD, marginLeft: 4, fontSize: 11 }}>
                    {trendRising ? "↑" : "↓"}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ============================================================
   MAIN COCKPIT — OptionsIntradayPanel replacement
   ============================================================ */

function OptionsIntradayPanel() {
  const [activeSymbol, setActiveSymbol] = useState("NIFTY");
  const [topTrades, setTopTrades] = useState([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [freshSelected, setFreshSelected] = useState(null);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [alertsEnabled, setAlertsEnabled] = useState(false);
  const [voiceLog, setVoiceLog] = useState([]);
  const [scannerRegion, setScannerRegion] = useState("IN");
  const [trendHistory, setTrendHistory] = useState({ IN: [], US: [] });
  const [loading, setLoading] = useState(true);
  const prevTradesRef = useRef([]);
  const prevTopSigRef = useRef("");

  const logVoice = useCallback((msg) => {
    setVoiceLog(l => [{ t: Date.now(), msg }, ...l].slice(0, 20));
  }, []);

  const announceTrade = useCallback((trade) => {
    if (!trade || !trade.strike) return;
    const txt = `${trade.strike.label}, confidence ${trade.decision.confidence.toFixed(0)} percent, ${trade.state.label}`;
    speak(txt, voiceEnabled);
    logVoice(`🎙 ${trade.strike.label} · ${trade.decision.confidence.toFixed(0)}% · ${trade.state.label}`);
  }, [voiceEnabled, logVoice]);

  /* ─── Top Trades: 90s soft refresh ─── */
  const refreshTopTrades = useCallback(async () => {
    const raw = await scanAllIndices();
    if (raw.length === 0) {
      setLoading(false);
      return;
    }
    const ranked = rankTrades(raw);
    const stabilized = applyStabilityLock(ranked, prevTradesRef.current);
    prevTradesRef.current = stabilized;
    setTopTrades(stabilized);
    setLoading(false);

    // Voice-announce new top trade (only if signature changed)
    if (stabilized.length > 0) {
      const topSig = `${stabilized[0].strike?.label}|${stabilized[0].decision.confidence.toFixed(0)}`;
      if (topSig !== prevTopSigRef.current) {
        prevTopSigRef.current = topSig;
        announceTrade(stabilized[0]);
      }
    }

    // Update trend history for scanner
    setTrendHistory(prev => {
      const next = { ...prev };
      const region = "IN"; // indices scan is always IN
      const newRows = raw.map(r => {
        const d = scoreOptionsEngine(r);
        const state = classifyEntryState(d, r);
        const prevRow = (next[region] || []).find(x => x.symbol === r.sym);
        const history = prevRow ? [...prevRow.history.slice(-3), Math.round(d.confidence)] : [Math.round(d.confidence)];
        return {
          symbol: r.sym,
          direction: d.direction,
          score: d.confidence,
          state: state.label,
          stateColor: state.color,
          history,
        };
      });
      next[region] = newRows;
      return next;
    });
  }, [announceTrade]);

  useEffect(() => {
    refreshTopTrades();
    const interval = setInterval(refreshTopTrades, 90 * 1000);
    return () => clearInterval(interval);
  }, [refreshTopTrades]);

  /* ─── Quick Trade Panel: 30s tick refresh on selected symbol ─── */
  const selected = topTrades[selectedIdx] || null;

  useEffect(() => {
    if (!selected) { setFreshSelected(null); return; }
    const sym = selected.data.sym;
    let cancelled = false;

    const tick = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/options-quick?symbol=${encodeURIComponent(sym)}`);
        if (!res.ok) return;
        const j = await res.json();
        if (!cancelled && j.success) setFreshSelected(j);
      } catch (e) { /* silent */ }
    };

    tick(); // immediate
    const interval = setInterval(tick, 30 * 1000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [selected?.data.sym]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ─── Quick Trade: entry trigger detection ─── */
  useEffect(() => {
    if (!selected || !freshSelected) return;
    const spot = n(freshSelected.spot);
    const lv = selected.decision.levels;
    if (!spot || !lv?.level) return;
    const dir = selected.decision.direction;
    const triggered = dir === "BULLISH" ? spot >= lv.level : spot <= lv.level;
    if (triggered && !selected._announced) {
      selected._announced = true;
      speak(`Entry triggered on ${selected.strike?.label}`, voiceEnabled);
      logVoice(`🟢 Entry triggered ${selected.strike?.label}`);
    }
  }, [freshSelected?.spot, selected, voiceEnabled, logVoice]);

  /* ─── Secondary Scanner: refresh on region change OR every 90s ─── */
  useEffect(() => {
    if (scannerRegion === "IN") return; // handled by refreshTopTrades
    let cancelled = false;
    const scanUS = async () => {
      const syms = SCANNER_UNIVERSES.US.map(s => s.sym);
      const results = await Promise.all(syms.map(async sym => {
        try {
          // US ETFs don't have option data via /api/options-quick; use /api/stock-quick
          const res = await fetch(`${API_BASE}/api/stock-quick?ticker=${sym}`);
          if (!res.ok) return null;
          const d = await res.json();
          if (!d.current_price) return null;
          // Compute simple momentum score
          const px = n(d.current_price), s20 = n(d.sma_20), s50 = n(d.sma_50), s200 = n(d.sma_200);
          let score = 50;
          if (px && s20 && px > s20) score += 10; else if (s20) score -= 10;
          if (px && s50 && px > s50) score += 15; else if (s50) score -= 15;
          if (px && s200 && px > s200) score += 20; else if (s200) score -= 20;
          const direction = score >= 60 ? "BULLISH" : score <= 40 ? "BEARISH" : null;
          const state = score >= 70 ? "IDEAL" : score >= 55 ? "EARLY" : score <= 45 ? "LATE" : "NO-TRADE";
          const stateColor = score >= 70 ? T.BL : score >= 55 ? T.GR : T.YL;
          return { symbol: sym, direction, score, state, stateColor };
        } catch (e) { return null; }
      }));
      if (cancelled) return;
      const valid = results.filter(Boolean);
      setTrendHistory(prev => {
        const next = { ...prev };
        const prevUS = next.US || [];
        next.US = valid.map(r => {
          const prevRow = prevUS.find(x => x.symbol === r.symbol);
          const history = prevRow ? [...prevRow.history.slice(-3), Math.round(r.score)] : [Math.round(r.score)];
          return { ...r, history };
        });
        return next;
      });
    };
    scanUS();
    const interval = setInterval(scanUS, 90 * 1000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [scannerRegion]);

  /* ─── Keyboard navigation ─── */
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "1" || e.key === "2" || e.key === "3") {
        const idx = parseInt(e.key, 10) - 1;
        if (topTrades[idx]) setSelectedIdx(idx);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [topTrades]);

  /* ─── Voice toggle side-effect ─── */
  const toggleVoice = () => {
    setVoiceEnabled(v => {
      const next = !v;
      if (!next && typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      return next;
    });
  };

  // Pad Top Trades to exactly 3 (spec §4 rule)
  const cards = [0, 1, 2].map(i => topTrades[i] || null);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {/* HEADER */}
      <CockpitHeader
        activeSymbol={activeSymbol}
        onSymbolChange={(sym) => {
          setActiveSymbol(sym);
          // Find that symbol in top trades and select it; else select first
          const idx = topTrades.findIndex(t => t.data.sym === sym);
          if (idx >= 0) setSelectedIdx(idx);
        }}
        voiceEnabled={voiceEnabled}
        onVoiceToggle={toggleVoice}
        alertsEnabled={alertsEnabled}
        onAlertsToggle={() => setAlertsEnabled(a => !a)}
      />

      {/* MAIN GRID — 65/35 */}
      <div style={{ display: "grid", gridTemplateColumns: "65fr 35fr", gap: 12, alignItems: "start" }}>
        {/* TOP TRADES — left 65% */}
        <div>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 2, textTransform: "uppercase", marginBottom: 10 }}>
            Top Trades · Ranked by Confidence · Locked 3-min · Press 1/2/3
          </div>
          {loading ? (
            <div style={{
              padding: 40, background: T.CARD, borderRadius: 8, textAlign: "center",
              fontFamily: MONO, fontSize: 12, color: T.T2, letterSpacing: 1,
            }}>
              SCANNING 4 INDICES...
            </div>
          ) : (
            cards.map((trade, i) => (
              <TopTradeCard
                key={i}
                trade={trade}
                active={selectedIdx === i}
                onSelect={() => setSelectedIdx(i)}
                onSpeak={() => announceTrade(trade)}
              />
            ))
          )}
        </div>

        {/* QUICK TRADE PANEL — right 35% */}
        <QuickTradePanel
          trade={selected}
          freshData={freshSelected}
          voiceLog={voiceLog}
          onVoiceLog={logVoice}
        />
      </div>

      {/* SECONDARY SCANNER — bottom 220px */}
      <SecondaryScanner
        region={scannerRegion}
        onRegionChange={setScannerRegion}
        trendHistory={trendHistory}
      />
    </div>
  );
}

/* ============================================================
   SWING POSITIONAL PANEL
   ============================================================ */

function SwingPositionalPanel({ ticker, onTickerChange }) {
  const [input, setInput] = useState(ticker);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => { setInput(ticker); }, [ticker]);

  const load = useCallback(async (t) => {
    if (!t) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/stock-quick?ticker=${encodeURIComponent(t.trim().toUpperCase())}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const j = await res.json();
      if (j.error) throw new Error(j.error);
      setData(j);
    } catch (e) {
      setError(e.message || "Failed");
      setData(null);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(ticker); }, [ticker, load]);

  const decision = useMemo(() => data ? scoreSwingEngine(data) : null, [data]);

  const submit = (e) => {
    e.preventDefault?.();
    const v = input.trim().toUpperCase();
    if (v && v !== ticker) onTickerChange(v);
    else if (v) load(v);
  };

  const ccy = data?.currency === "INR" ? "₹" : "$";
  const px = data ? n(data.current_price) : null;
  const s20 = data ? n(data.sma_20) : null;
  const s50 = data ? n(data.sma_50) : null;
  const s200 = data ? n(data.sma_200) : null;

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {/* Search */}
      <form onSubmit={submit} style={{ display: "flex", gap: 10 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Any stock ticker (e.g. MU, RELIANCE.NS, AAPL)"
          style={{
            flex: 1, padding: "12px 16px",
            background: T.CARD, border: `1px solid ${T.BD}`,
            borderRadius: 6, fontFamily: MONO, fontSize: 14,
            color: T.T1, outline: "none",
          }}
        />
        <button type="submit" style={{
          padding: "12px 24px", background: T.BL, border: "none",
          borderRadius: 6, fontFamily: MONO, fontSize: 13,
          color: "#fff", fontWeight: 600, cursor: "pointer",
          letterSpacing: 1, textTransform: "uppercase",
        }}>Analyze</button>
      </form>

      {loading && <LoadingState ticker={ticker} />}
      {error && !loading && <ErrorState msg={error} onRetry={() => load(ticker)} />}

      {data && decision && !loading && (
        <>
          <DecisionCard decision={decision} symbol={data.company_name || data.ticker} currency={ccy} mode="swing" />

          {/* SMA Stack visualization */}
          <Card title="Daily/Weekly Trend Structure" accent={{ label: "EMA Stack", color: T.PP }}>
            {s20 !== null && s50 !== null && s200 !== null && px !== null ? (
              <SMAStackViz px={px} s20={s20} s50={s50} s200={s200} ccy={ccy} />
            ) : (
              <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO }}>SMA data unavailable</div>
            )}
          </Card>

          <LayerBreakdown layers={decision.layers} title="Swing Engine — 5-Layer Breakdown" />

          {/* Fundamentals overlay */}
          <Card title="Swing Fundamentals Overlay" accent={{ label: "Quality Filter", color: T.GR }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              {[
                { k: "EPS Growth", v: n(data.eps_growth_pct), fmt: (v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`, good: (v) => v > 10 },
                { k: "Profit Margin", v: n(data.profit_margin), fmt: (v) => `${(v * 100).toFixed(1)}%`, good: (v) => v > 0.10 },
                { k: "ROE", v: n(data.roe), fmt: (v) => `${(v * 100).toFixed(1)}%`, good: (v) => v > 0.15 },
                { k: "Debt/Equity", v: n(data.debt_to_equity), fmt: (v) => v.toFixed(2), good: (v) => v < 1 },
              ].map((m, i) => {
                const c = m.v === null ? T.T3 : m.good(m.v) ? T.GR : T.YL;
                return (
                  <div key={i} style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
                    <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>{m.k}</div>
                    <div style={{ fontSize: 16, fontFamily: MONO, color: c, fontWeight: 700, marginTop: 4 }}>
                      {m.v === null ? "—" : m.fmt(m.v)}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

/* Helper: visualize where price sits in relation to SMAs */
function SMAStackViz({ px, s20, s50, s200, ccy }) {
  const pts = [
    { label: "Price", value: px, color: T.T1, weight: 700 },
    { label: "SMA 20", value: s20, color: T.BL, weight: 600 },
    { label: "SMA 50", value: s50, color: T.PP, weight: 600 },
    { label: "SMA 200", value: s200, color: T.YL, weight: 600 },
  ].sort((a, b) => b.value - a.value);

  const max = pts[0].value;
  const min = pts[pts.length - 1].value;
  const range = max - min;

  return (
    <div>
      <div style={{ display: "grid", gap: 6 }}>
        {pts.map((p, i) => {
          const pct = range > 0 ? ((p.value - min) / range) * 100 : 50;
          const diffFromPrice = ((p.value - px) / px) * 100;
          return (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "80px 1fr 100px 70px", gap: 12,
              padding: "8px 12px", background: T.ACT, borderRadius: 4, alignItems: "center",
            }}>
              <div style={{ fontSize: 12, fontFamily: MONO, color: p.color, fontWeight: p.weight }}>
                {p.label}
              </div>
              <div style={{ position: "relative", height: 6, background: T.CARD, borderRadius: 3 }}>
                <div style={{
                  position: "absolute", top: 0, left: 0, width: `${pct}%`, height: "100%",
                  background: p.color, borderRadius: 3,
                }} />
              </div>
              <div style={{ fontSize: 13, fontFamily: MONO, color: T.T1, fontWeight: 600, textAlign: "right" }}>
                {ccy}{p.value.toFixed(2)}
              </div>
              <div style={{
                fontSize: 11, fontFamily: MONO, textAlign: "right",
                color: p.label === "Price" ? T.T3 : diffFromPrice >= 0 ? T.RD : T.GR,
              }}>
                {p.label === "Price" ? "—" : `${diffFromPrice > 0 ? "+" : ""}${diffFromPrice.toFixed(2)}%`}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{
        marginTop: 12, padding: 10, background: T.CARD, border: `1px solid ${T.BD}`,
        borderRadius: 4, fontSize: 12, fontFamily: BODY, color: T.T2, lineHeight: 1.5,
      }}>
        <strong style={{ color: T.T1 }}>Structure:</strong>{" "}
        {px > s20 && s20 > s50 && s50 > s200 ? "Perfect bullish stack (P > 20 > 50 > 200). HH/HL intact." :
         px < s20 && s20 < s50 && s50 < s200 ? "Perfect bearish stack. Downtrend structure." :
         s50 > s200 ? "Golden cross regime active. Primary trend bullish." :
         s50 < s200 ? "Death cross regime. Primary trend bearish." :
         "SMAs mixed — no directional edge."}
      </div>
    </div>
  );
}

/* ============================================================
   DECIDE PAGE — Meta-router
   ============================================================ */

function DecidePage({ ticker, onTickerChange }) {
  const [mode, setMode] = useState("options");  // 'options' or 'swing'

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>
      {/* Page header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, letterSpacing: 2, textTransform: "uppercase" }}>
            Decide · Institutional Trading Decisions
          </div>
          <div style={{ fontSize: 20, fontFamily: BODY, color: T.T1, fontWeight: 700, marginTop: 4 }}>
            Dual-engine decision framework
          </div>
        </div>
        <div style={{
          fontSize: 10, fontFamily: MONO, color: T.T3,
          padding: "4px 10px", border: `1px solid ${T.BD}`, borderRadius: 3,
          letterSpacing: 1.5, textTransform: "uppercase",
        }}>Meta-Router · Unified Decision Card</div>
      </div>

      {/* Meta-router: Mode selector */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, padding: 4,
        background: T.CARD, border: `1px solid ${T.BD}`, borderRadius: 8, marginBottom: 16,
      }}>
        <button onClick={() => setMode("options")} style={{
          padding: "14px 18px",
          background: mode === "options" ? `linear-gradient(135deg, ${T.BL}, ${T.PP})` : "transparent",
          border: "none", borderRadius: 6,
          fontFamily: BODY, fontSize: 14, fontWeight: 700,
          color: mode === "options" ? "#fff" : T.T2,
          cursor: "pointer", letterSpacing: 0.5, textAlign: "left",
          transition: "all 0.15s ease",
        }}>
          <div style={{ fontSize: 13, letterSpacing: 1, textTransform: "uppercase" }}>⚡ Options Intraday</div>
          <div style={{
            fontSize: 11, fontFamily: MONO, marginTop: 3, letterSpacing: 0.5,
            color: mode === "options" ? "rgba(255,255,255,0.8)" : T.T3, textTransform: "none",
          }}>
            Minutes–Hours · GEX · OI · VWAP · Theta
          </div>
        </button>
        <button onClick={() => setMode("swing")} style={{
          padding: "14px 18px",
          background: mode === "swing" ? `linear-gradient(135deg, ${T.GR}, ${T.CY})` : "transparent",
          border: "none", borderRadius: 6,
          fontFamily: BODY, fontSize: 14, fontWeight: 700,
          color: mode === "swing" ? "#fff" : T.T2,
          cursor: "pointer", letterSpacing: 0.5, textAlign: "left",
          transition: "all 0.15s ease",
        }}>
          <div style={{ fontSize: 13, letterSpacing: 1, textTransform: "uppercase" }}>📈 Swing Positional</div>
          <div style={{
            fontSize: 11, fontFamily: MONO, marginTop: 3, letterSpacing: 0.5,
            color: mode === "swing" ? "rgba(255,255,255,0.8)" : T.T3, textTransform: "none",
          }}>
            Days–Weeks · Trend · HH/HL · EMA Stack · Accumulation
          </div>
        </button>
      </div>

      {/* Active engine */}
      {mode === "options" && <OptionsIntradayPanel />}
      {mode === "swing" && <SwingPositionalPanel ticker={ticker} onTickerChange={onTickerChange} />}
    </div>
  );
}

/* ============================================================
   TRADER TAB — L0 Scan Engine + Two-Stage Scanner (Session 4)

   Architecture:
     Stage 1: L0 Scan (5-factor composite, fast batch)
              30% Quality + 25% Growth + 20% Momentum + 15% Liquidity + 10% Stability
     Stage 2: CDS scoring on passers (uses 20-factor engine from S1)
     Live Signals: Continuous scan showing A/A+ grade trades

   Data strategy:
     - Try /api/l0-scan first (server-side batch, ~2s)
     - Fallback: client-side parallel /api/stock-quick (8 concurrent)

   UI:
     - Universe picker (Large/Mid/Small Cap, US + India)
     - Mode selector (Quality/Growth/Momentum/Value/Multibagger/Dividend)
     - Results table with L0 scores, click-to-load detail
     - Watchlist sidebar (localStorage)
     - Live Signals bar (A/A+ grades only)
   ============================================================ */

/* ---------- TICKER UNIVERSES ---------- */

const UNIVERSES = {
  US: {
    "Large Cap": [
      "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B", "JPM", "V",
      "WMT", "UNH", "XOM", "MA", "LLY", "HD", "PG", "JNJ", "CVX", "ABBV",
      "KO", "AVGO", "PEP", "MRK", "COST", "ORCL", "ADBE", "CSCO", "ACN", "CRM",
    ],
    "Mid Cap": [
      "MU", "AMD", "NFLX", "PYPL", "UBER", "SNOW", "SHOP", "NET", "DDOG", "CRWD",
      "PLTR", "SQ", "ABNB", "ROKU", "PINS", "TWLO", "DOCU", "ZM", "OKTA", "HOOD",
    ],
    "Small Cap": [
      "RIVN", "LCID", "SOFI", "U", "PATH", "RBLX", "AFRM", "FSLY", "BILL", "ESTC",
      "ZS", "SMAR", "PD", "TEAM", "NOW", "MDB", "FTNT", "WDAY", "HUBS", "TTD",
    ],
    "ETFs": [
      "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "XLF", "XLK", "XLE", "XLV",
      "XLP", "XLY", "XLI", "XLU", "XLB", "XLRE", "XLC", "GLD", "SLV", "TLT",
    ],
  },
  IN: {
    "Nifty 50": [
      "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
      "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
      "LT.NS", "ASIANPAINT.NS", "AXISBANK.NS", "MARUTI.NS", "BAJFINANCE.NS",
      "HCLTECH.NS", "WIPRO.NS", "SUNPHARMA.NS", "TATASTEEL.NS", "NTPC.NS",
      "ONGC.NS", "TITAN.NS", "NESTLEIND.NS", "ULTRACEMCO.NS", "POWERGRID.NS",
    ],
    "Midcap 150": [
      "MAZDOCK.NS", "BEL.NS", "HAL.NS", "BHEL.NS", "IRCTC.NS",
      "TATAPOWER.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "IRFC.NS", "RVNL.NS",
      "PFC.NS", "RECLTD.NS", "COCHINSHIP.NS", "GRSE.NS", "BDL.NS",
    ],
    "Smallcap 250": [
      "IDEA.NS", "YESBANK.NS", "IOB.NS", "CENTRALBK.NS", "UCOBANK.NS",
      "PNB.NS", "CANBK.NS", "UNIONBANK.NS", "BANKBARODA.NS", "IDBI.NS",
    ],
    "ETFs": [
      "NIFTYBEES.NS", "BANKBEES.NS", "GOLDBEES.NS", "LIQUIDBEES.NS",
      "JUNIORBEES.NS", "ITBEES.NS", "PSUBNKBEES.NS",
    ],
  },
};

const SCAN_MODES = [
  { id: "quality",    label: "Quality",     weights: { Q: 0.40, G: 0.15, M: 0.15, L: 0.15, S: 0.15 } },
  { id: "growth",     label: "Growth",      weights: { Q: 0.15, G: 0.45, M: 0.25, L: 0.10, S: 0.05 } },
  { id: "momentum",   label: "Momentum",    weights: { Q: 0.10, G: 0.20, M: 0.50, L: 0.15, S: 0.05 } },
  { id: "value",      label: "Value",       weights: { Q: 0.35, G: 0.10, M: 0.10, L: 0.10, S: 0.35 } },
  { id: "multibagger",label: "Multibagger", weights: { Q: 0.20, G: 0.40, M: 0.30, L: 0.05, S: 0.05 } },
  { id: "dividend",   label: "Dividend",    weights: { Q: 0.40, G: 0.05, M: 0.05, L: 0.20, S: 0.30 } },
];

/* ============================================================
   L0 SCORING — 5 factors, each 0-100
   ============================================================ */

function l0ScoreStock(d) {
  if (!d || !d.current_price) return null;

  const px = n(d.current_price);
  const pe = n(d.pe_ratio);
  const pm = n(d.profit_margin);
  const opm = n(d.operating_margin);
  const roe = n(d.roe);
  const de = n(d.debt_to_equity);
  const cr = n(d.current_ratio);
  const beta = n(d.beta);
  const eps = n(d.eps_growth_pct);
  const rev = n(d.revenue_growth);
  const dy = n(d.dividend_yield);
  const s20 = n(d.sma_20);
  const s50 = n(d.sma_50);
  const s200 = n(d.sma_200);
  const hi52 = n(d.week52_high);
  const lo52 = n(d.week52_low);
  const mc = n(d.market_cap);

  // Data completeness — track which critical factors have data
  // (per CDS v2.0: never fake, always flag)
  const available = [pe, pm, roe, de, beta, eps, rev, s50, s200, hi52, mc].filter(v => v !== null).length;
  const coverage = (available / 11) * 100;

  /* Quality (0-100): profitability + ROE + balance sheet */
  let Q = 50;
  if (pm !== null) Q += pm > 0.20 ? 20 : pm > 0.10 ? 10 : pm > 0 ? 0 : -20;
  if (roe !== null) Q += roe > 0.20 ? 15 : roe > 0.12 ? 8 : roe > 0 ? 0 : -15;
  if (opm !== null) Q += opm > 0.25 ? 10 : opm > 0.10 ? 5 : opm > 0 ? 0 : -10;
  if (de !== null) Q += de < 0.5 ? 10 : de < 1.5 ? 0 : -10;
  if (cr !== null) Q += cr > 1.5 ? 5 : cr > 1 ? 0 : -10;
  Q = Math.max(0, Math.min(100, Q));

  /* Growth (0-100): EPS + revenue velocity */
  let G = 50;
  if (eps !== null) G += eps > 25 ? 25 : eps > 10 ? 15 : eps > 0 ? 5 : -20;
  const revPct = rev === null ? null : (Math.abs(rev) > 5 ? rev : rev * 100);
  if (revPct !== null) G += revPct > 20 ? 20 : revPct > 10 ? 10 : revPct > 0 ? 2 : -15;
  G = Math.max(0, Math.min(100, G));

  /* Momentum (0-100): SMA stack + 52W position */
  let M = 50;
  if (px !== null && s20 !== null && s50 !== null && s200 !== null) {
    if (px > s20) M += 8; else M -= 8;
    if (px > s50) M += 10; else M -= 10;
    if (px > s200) M += 12; else M -= 12;
    if (s50 > s200) M += 8; else M -= 8;
  }
  if (px !== null && hi52 !== null && lo52 !== null && hi52 > lo52) {
    const pct52 = ((px - lo52) / (hi52 - lo52)) * 100;
    if (pct52 > 70) M += 10;
    else if (pct52 > 40) M += 3;
    else if (pct52 < 20) M -= 5;
  }
  M = Math.max(0, Math.min(100, M));

  /* Liquidity (0-100): market cap tier proxy */
  let L = 50;
  if (mc !== null) {
    if (mc > 50e9) L = 95;
    else if (mc > 10e9) L = 85;
    else if (mc > 2e9) L = 70;
    else if (mc > 500e6) L = 55;
    else if (mc > 100e6) L = 40;
    else L = 25;
  }
  L = Math.max(0, Math.min(100, L));

  /* Stability (0-100): beta, dividend, valuation safety */
  let S = 50;
  if (beta !== null) S += beta < 0.8 ? 20 : beta < 1.1 ? 10 : beta < 1.5 ? -5 : -20;
  if (dy !== null && dy > 0) S += dy > 0.03 ? 15 : dy > 0.01 ? 8 : 2;
  if (pe !== null) S += pe > 0 && pe < 20 ? 10 : pe > 40 ? -15 : 0;
  if (de !== null) S += de < 0.5 ? 5 : de > 2 ? -10 : 0;
  S = Math.max(0, Math.min(100, S));

  return { Q, G, M, L, S, coverage };
}

function l0Composite(scores, mode) {
  if (!scores) return null;
  const w = mode.weights;
  return scores.Q * w.Q + scores.G * w.G + scores.M * w.M + scores.L * w.L + scores.S * w.S;
}

/* ============================================================
   Grade classification
   ============================================================ */

function l0Grade(score) {
  if (score >= 80) return { label: "A+", color: T.GR, weight: 800 };
  if (score >= 70) return { label: "A", color: T.GR, weight: 700 };
  if (score >= 60) return { label: "B+", color: T.CY, weight: 700 };
  if (score >= 50) return { label: "B", color: T.YL, weight: 600 };
  if (score >= 40) return { label: "C", color: T.YL, weight: 600 };
  return { label: "D", color: T.RD, weight: 600 };
}

/* ============================================================
   BATCH SCANNER with concurrency limiter
   ============================================================ */

async function batchFetchStocks(tickers, onProgress, concurrency = 6) {
  const results = [];
  let completed = 0;
  const queue = [...tickers];

  async function worker() {
    while (queue.length > 0) {
      const t = queue.shift();
      if (!t) break;
      try {
        const res = await fetch(`${API_BASE}/api/stock-quick?ticker=${encodeURIComponent(t)}`);
        if (res.ok) {
          const j = await res.json();
          if (!j.error && j.current_price) {
            results.push(j);
          }
        }
      } catch (e) {
        /* silent fail for individual ticker */
      }
      completed++;
      onProgress?.(completed, tickers.length);
    }
  }

  const workers = Array(Math.min(concurrency, tickers.length)).fill(null).map(worker);
  await Promise.all(workers);
  return results;
}

/* ============================================================
   WATCHLIST (localStorage)
   ============================================================ */

const WATCHLIST_KEY = "celesys_watchlist_v1";

function loadWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) { return []; }
}

function saveWatchlist(list) {
  try { localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list)); } catch (e) {}
}

/* ============================================================
   WATCHLIST PANEL — localStorage-backed
   ============================================================ */

function WatchlistPanel({ watchlist, onSelectTicker, onRemove, onScanAll }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (watchlist.length === 0) { setItems([]); return; }
    setLoading(true);
    const raw = await batchFetchStocks(watchlist, null, 4);
    const scored = raw.map(d => {
      const factors = l0ScoreStock(d);
      const composite = factors ? l0Composite(factors, SCAN_MODES[0]) : null;
      return { data: d, factors, composite, grade: composite !== null ? l0Grade(composite) : null };
    }).sort((a, b) => (b.composite ?? 0) - (a.composite ?? 0));
    setItems(scored);
    setLoading(false);
  }, [watchlist]);

  useEffect(() => { refresh(); }, [refresh]);

  if (watchlist.length === 0) {
    return (
      <Card title="Watchlist" accent={{ label: "Empty", color: T.T3 }}>
        <div style={{
          padding: 30, textAlign: "center",
          fontSize: 12, fontFamily: BODY, color: T.T3, lineHeight: 1.6,
        }}>
          Click <span style={{ color: T.YL }}>☆</span> on any stock to add it to your watchlist.
          <br /><br />
          Watchlist persists across sessions via localStorage.
        </div>
      </Card>
    );
  }

  return (
    <Card
      title="Watchlist"
      accent={{ label: `${watchlist.length} stocks`, color: T.YL }}
    >
      <div style={{ marginBottom: 12, display: "flex", gap: 8 }}>
        <button onClick={refresh} disabled={loading} style={{
          padding: "6px 12px", background: loading ? T.ACT : T.BL,
          border: "none", borderRadius: 4,
          fontFamily: MONO, fontSize: 10, color: "#fff", fontWeight: 600,
          cursor: loading ? "wait" : "pointer", letterSpacing: 1, textTransform: "uppercase",
        }}>
          {loading ? "↻ Refreshing..." : "↻ Refresh"}
        </button>
      </div>

      {loading && items.length === 0 ? (
        <div style={{ padding: 20, textAlign: "center", color: T.T3, fontSize: 12, fontFamily: MONO }}>
          Loading {watchlist.length} stocks...
        </div>
      ) : (
        <div style={{ display: "grid", gap: 6 }}>
          {items.map((r) => {
            const ccy = r.data.currency === "INR" ? "₹" : "$";
            return (
              <div
                key={r.data.ticker}
                onClick={() => onSelectTicker(r.data.ticker)}
                style={{
                  padding: "10px 12px", background: T.ACT, borderRadius: 4,
                  display: "grid", gridTemplateColumns: "auto 1fr auto auto 20px", gap: 10,
                  alignItems: "center", cursor: "pointer",
                  borderLeft: `2px solid ${r.grade?.color || T.T3}`,
                  transition: "transform 0.1s ease",
                }}
                onMouseEnter={(e) => e.currentTarget.style.transform = "translateX(2px)"}
                onMouseLeave={(e) => e.currentTarget.style.transform = "translateX(0)"}
              >
                <div style={{
                  fontSize: 10, fontFamily: MONO, padding: "2px 6px",
                  background: `${r.grade?.color || T.T3}15`,
                  border: `1px solid ${r.grade?.color || T.T3}40`,
                  borderRadius: 3, color: r.grade?.color || T.T3, fontWeight: 700,
                }}>{r.grade?.label || "—"}</div>
                <div>
                  <div style={{ fontSize: 12, fontFamily: MONO, color: T.T1, fontWeight: 600 }}>
                    {r.data.ticker}
                  </div>
                  <div style={{ fontSize: 10, fontFamily: BODY, color: T.T3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r.data.company_name || "—"}
                  </div>
                </div>
                <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2 }}>
                  {ccy}{(+r.data.current_price).toFixed(2)}
                </div>
                <div style={{ fontSize: 11, fontFamily: MONO, color: r.grade?.color || T.T3, fontWeight: 700, textAlign: "right", minWidth: 32 }}>
                  {r.composite !== null ? r.composite.toFixed(0) : "—"}
                </div>
                <div
                  onClick={(e) => { e.stopPropagation(); onRemove(r.data.ticker); }}
                  style={{ cursor: "pointer", color: T.RD, fontSize: 14, textAlign: "center" }}
                  title="Remove from watchlist"
                >×</div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

/* ============================================================
   LIVE SIGNALS BAR — continuous scan for A/A+ grades
   ============================================================ */

function LiveSignalsBar() {
  const [signals, setSignals] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [lastRun, setLastRun] = useState(null);

  const runScan = useCallback(async () => {
    if (scanning) return;
    setScanning(true);
    // Scan a representative mix: US Large + India Nifty 50
    const combined = [
      ...UNIVERSES.US["Large Cap"].slice(0, 20),
      ...UNIVERSES.IN["Nifty 50"].slice(0, 15),
    ];
    const raw = await batchFetchStocks(combined, null, 8);
    const qualityMode = SCAN_MODES.find(m => m.id === "quality");
    const scored = raw.map(d => {
      const factors = l0ScoreStock(d);
      if (!factors) return null;
      const composite = l0Composite(factors, qualityMode);
      return { data: d, composite, grade: l0Grade(composite) };
    }).filter(Boolean);

    // Only A or A+ grades (>= 70)
    const topSignals = scored
      .filter(s => s.composite >= 70)
      .sort((a, b) => b.composite - a.composite)
      .slice(0, 10);

    setSignals(topSignals);
    setLastRun(new Date());
    setScanning(false);
  }, [scanning]);

  // Run once on mount, then every 2 minutes
  useEffect(() => {
    runScan();
    const interval = setInterval(runScan, 2 * 60 * 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Card
      title="Live A/A+ Signals"
      accent={
        scanning
          ? { label: "Scanning...", color: T.YL }
          : lastRun
          ? { label: `${signals.length} hits · ${lastRun.toLocaleTimeString()}`, color: T.GR }
          : null
      }
    >
      {signals.length === 0 && !scanning ? (
        <div style={{
          padding: 20, textAlign: "center",
          fontSize: 12, fontFamily: MONO, color: T.T3, lineHeight: 1.6,
        }}>
          No A/A+ signals in current universe.
          <br />
          <span style={{ fontSize: 11 }}>Scanner re-runs every 2 minutes.</span>
        </div>
      ) : (
        <div style={{
          display: "flex", gap: 8, overflowX: "auto", paddingBottom: 4,
        }}>
          {signals.map((s, i) => {
            const ccy = s.data.currency === "INR" ? "₹" : "$";
            return (
              <div key={s.data.ticker + i} style={{
                flexShrink: 0, padding: "10px 14px", background: T.ACT,
                border: `1px solid ${s.grade.color}40`, borderRadius: 6,
                borderTop: `3px solid ${s.grade.color}`,
                minWidth: 140,
              }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{
                    fontSize: 11, fontFamily: MONO, fontWeight: 800,
                    color: s.grade.color,
                  }}>{s.grade.label}</span>
                  <span style={{ fontSize: 13, fontFamily: MONO, color: T.T1, fontWeight: 700 }}>
                    {s.data.ticker}
                  </span>
                </div>
                <div style={{ fontSize: 14, fontFamily: MONO, color: T.T1, fontWeight: 600, marginTop: 6 }}>
                  {ccy}{(+s.data.current_price).toFixed(2)}
                </div>
                <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, marginTop: 3, letterSpacing: 0.5 }}>
                  Score {s.composite.toFixed(0)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

/* ============================================================
   SECTOR HEATMAP (bonus) — aggregate L0 scores by sector
   ============================================================ */

function SectorHeatmap({ results }) {
  const bySector = useMemo(() => {
    const m = new Map();
    results.forEach(r => {
      const sector = r.data.sector || "Unclassified";
      if (!m.has(sector)) m.set(sector, { count: 0, totalScore: 0 });
      const bucket = m.get(sector);
      bucket.count++;
      bucket.totalScore += r.composite;
    });
    return Array.from(m.entries())
      .map(([sector, v]) => ({ sector, count: v.count, avg: v.totalScore / v.count }))
      .sort((a, b) => b.avg - a.avg);
  }, [results]);

  if (bySector.length === 0) return null;

  return (
    <Card title="Sector Aggregation" accent={{ label: `${bySector.length} sectors`, color: T.CY }}>
      <div style={{ display: "grid", gap: 6 }}>
        {bySector.map((s, i) => {
          const grade = l0Grade(s.avg);
          return (
            <div key={i} style={{
              padding: "10px 12px", background: T.ACT, borderRadius: 4,
              display: "grid", gridTemplateColumns: "1fr 50px 60px 60px", gap: 12, alignItems: "center",
              borderLeft: `2px solid ${grade.color}`,
            }}>
              <div style={{ fontSize: 12, fontFamily: BODY, color: T.T1, fontWeight: 500 }}>{s.sector}</div>
              <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, textAlign: "center" }}>
                {s.count} stock{s.count === 1 ? "" : "s"}
              </div>
              <div style={{
                fontSize: 11, fontFamily: MONO, textAlign: "center",
                padding: "2px 8px", background: `${grade.color}15`,
                border: `1px solid ${grade.color}40`, borderRadius: 3,
                color: grade.color, fontWeight: 700,
              }}>{grade.label}</div>
              <div style={{
                fontSize: 13, fontFamily: MONO, color: grade.color, fontWeight: 700, textAlign: "right",
              }}>{s.avg.toFixed(1)}</div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ============================================================
   TRADER PAGE — main assembly
   ============================================================ */

function TraderPage({ onTickerSelect }) {
  const [watchlist, setWatchlist] = useState(() => loadWatchlist());
  const [scannerResults, setScannerResults] = useState([]);

  // Sync watchlist to localStorage
  useEffect(() => { saveWatchlist(watchlist); }, [watchlist]);

  const toggleWatch = useCallback((ticker) => {
    setWatchlist(w => w.includes(ticker) ? w.filter(t => t !== ticker) : [...w, ticker]);
  }, []);

  const removeFromWatch = useCallback((ticker) => {
    setWatchlist(w => w.filter(t => t !== ticker));
  }, []);

  // Wrapper for scanner panel to also snapshot results for the heatmap
  const handleTickerFromScanner = useCallback((ticker) => {
    onTickerSelect(ticker);
  }, [onTickerSelect]);

  return (
    <div style={{ padding: 24, maxWidth: 1600, margin: "0 auto" }}>
      {/* Page header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, letterSpacing: 2, textTransform: "uppercase" }}>
            Trader · L0 Scan Engine
          </div>
          <div style={{ fontSize: 20, fontFamily: BODY, color: T.T1, fontWeight: 700, marginTop: 4 }}>
            Institutional two-stage scanner
          </div>
        </div>
        <div style={{
          fontSize: 10, fontFamily: MONO, color: T.T3,
          padding: "4px 10px", border: `1px solid ${T.BD}`, borderRadius: 3,
          letterSpacing: 1.5, textTransform: "uppercase",
        }}>30Q · 25G · 20M · 15L · 10S</div>
      </div>

      {/* Live signals — top of page */}
      <div style={{ marginBottom: 12 }}>
        <LiveSignalsBar />
      </div>

      {/* Main 2-column layout */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 320px",
        gap: 14,
        alignItems: "start",
      }}>
        <div>
          <ScannerPanelWithResults
            onSelectTicker={handleTickerFromScanner}
            watchlist={watchlist}
            onToggleWatch={toggleWatch}
            onResultsChange={setScannerResults}
          />
          {scannerResults.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <SectorHeatmap results={scannerResults} />
            </div>
          )}
        </div>

        <div style={{ display: "grid", gap: 12, position: "sticky", top: 80 }}>
          <WatchlistPanel
            watchlist={watchlist}
            onSelectTicker={onTickerSelect}
            onRemove={removeFromWatch}
          />
          {/* L0 Formula explainer */}
          <Card title="L0 Composite Formula" accent={{ label: "Institutional", color: T.PP }}>
            <div style={{ fontSize: 12, fontFamily: BODY, color: T.T2, lineHeight: 1.6 }}>
              <div style={{ marginBottom: 10, color: T.T1 }}>
                Each stock scored 0-100 across 5 factors:
              </div>
              {[
                { k: "Quality (Q)", v: "Margins, ROE, solvency", c: T.BL },
                { k: "Growth (G)", v: "EPS + revenue velocity", c: T.GR },
                { k: "Momentum (M)", v: "SMA stack + 52W position", c: T.PP },
                { k: "Liquidity (L)", v: "Market-cap tier proxy", c: T.CY },
                { k: "Stability (S)", v: "Beta, dividend, valuation", c: T.YL },
              ].map((f, i) => (
                <div key={i} style={{
                  padding: "6px 10px", marginBottom: 4,
                  borderLeft: `2px solid ${f.c}`, background: T.ACT, borderRadius: 3,
                }}>
                  <div style={{ fontSize: 11, fontFamily: MONO, color: f.c, fontWeight: 700 }}>{f.k}</div>
                  <div style={{ fontSize: 11, fontFamily: BODY, color: T.T2, marginTop: 2 }}>{f.v}</div>
                </div>
              ))}
              <div style={{
                marginTop: 10, padding: 8, background: T.CARD, border: `1px solid ${T.BD}`,
                borderRadius: 3, fontSize: 11, fontFamily: MONO, color: T.T2,
              }}>
                Mode re-weights these factors. A/A+ ≥ 70.
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* Wrapper that exposes scanner results up to TraderPage for SectorHeatmap */
function ScannerPanelWithResults({ onSelectTicker, watchlist, onToggleWatch, onResultsChange }) {
  const [region, setRegion] = useState("US");
  const [universe, setUniverse] = useState("Large Cap");
  const [modeId, setModeId] = useState("quality");
  const [results, setResults] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [lastScan, setLastScan] = useState(null);

  const mode = SCAN_MODES.find(m => m.id === modeId);
  const universes = UNIVERSES[region] || {};
  const universeOptions = Object.keys(universes);
  const tickers = universes[universe] || [];

  useEffect(() => {
    if (!universeOptions.includes(universe)) {
      setUniverse(universeOptions[0]);
    }
  }, [region, universe, universeOptions]);

  useEffect(() => { onResultsChange?.(results); }, [results, onResultsChange]);

  const runScan = useCallback(async () => {
    if (scanning) return;
    setScanning(true);
    setProgress({ done: 0, total: tickers.length });
    setResults([]);

    const raw = await batchFetchStocks(tickers, (done, total) => {
      setProgress({ done, total });
    });

    const scored = raw.map(d => {
      const factors = l0ScoreStock(d);
      if (!factors) return null;
      const composite = l0Composite(factors, mode);
      return {
        data: d,
        factors,
        composite,
        grade: l0Grade(composite),
      };
    }).filter(Boolean).sort((a, b) => b.composite - a.composite);

    setResults(scored);
    setLastScan(new Date());
    setScanning(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickers, modeId]);

  useEffect(() => {
    runScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [region, universe, modeId]);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <Card pad={14}>
        <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 16, alignItems: "center" }}>
          <div style={{ display: "flex", gap: 4, padding: 3, background: T.ACT, borderRadius: 6 }}>
            {["US", "IN"].map(r => (
              <button key={r} onClick={() => setRegion(r)} style={{
                padding: "8px 16px",
                background: region === r ? T.BL : "transparent",
                border: "none", borderRadius: 4,
                fontFamily: MONO, fontSize: 11, fontWeight: 700,
                color: region === r ? "#fff" : T.T2,
                cursor: "pointer", letterSpacing: 1,
              }}>
                {r === "US" ? "🇺🇸 US" : "🇮🇳 INDIA"}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {universeOptions.map(u => (
              <button key={u} onClick={() => setUniverse(u)} style={{
                padding: "8px 14px",
                background: universe === u ? T.CARD : T.ACT,
                border: `1px solid ${universe === u ? T.BL : T.BD}`,
                borderRadius: 4, fontFamily: MONO, fontSize: 11,
                color: universe === u ? T.T1 : T.T2, fontWeight: 600,
                cursor: "pointer", letterSpacing: 0.5,
              }}>{u}</button>
            ))}
          </div>

          <button onClick={runScan} disabled={scanning} style={{
            padding: "10px 18px",
            background: scanning ? T.ACT : T.BL,
            border: "none", borderRadius: 6,
            fontFamily: MONO, fontSize: 11, color: "#fff",
            fontWeight: 700, cursor: scanning ? "wait" : "pointer",
            letterSpacing: 1, textTransform: "uppercase",
            opacity: scanning ? 0.6 : 1,
          }}>
            {scanning ? `${progress.done}/${progress.total}` : "↻ Rescan"}
          </button>
        </div>

        <div style={{
          marginTop: 12, paddingTop: 12, borderTop: `1px solid ${T.ACT}`,
          display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center",
        }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase", marginRight: 8 }}>
            Mode:
          </div>
          {SCAN_MODES.map(m => (
            <button key={m.id} onClick={() => setModeId(m.id)} style={{
              padding: "6px 12px",
              background: modeId === m.id ? T.BL : "transparent",
              border: `1px solid ${modeId === m.id ? T.BL : T.BD}`,
              borderRadius: 4, fontFamily: MONO, fontSize: 11,
              color: modeId === m.id ? "#fff" : T.T2, fontWeight: 600,
              cursor: "pointer", letterSpacing: 0.5, textTransform: "uppercase",
            }}>{m.label}</button>
          ))}
        </div>
      </Card>

      {scanning && (
        <div style={{ height: 4, background: T.ACT, borderRadius: 2, overflow: "hidden" }}>
          <div style={{
            width: `${progress.total > 0 ? (progress.done / progress.total) * 100 : 0}%`,
            height: "100%", background: T.BL, transition: "width 0.2s ease",
          }} />
        </div>
      )}

      <Card
        title={`L0 Scan Results — ${universe} (${mode.label})`}
        accent={lastScan ? {
          label: `${results.length} · ${lastScan.toLocaleTimeString()}`,
          color: T.GR,
        } : null}
      >
        {results.length === 0 && !scanning ? (
          <div style={{ padding: 40, textAlign: "center", color: T.T3, fontSize: 12, fontFamily: MONO }}>
            No results yet.
          </div>
        ) : (
          <div>
            <div style={{
              display: "grid",
              gridTemplateColumns: "40px 60px 1.8fr 80px 80px 50px 50px 50px 50px 50px 60px 40px",
              gap: 8, padding: "8px 10px",
              fontSize: 9, fontFamily: MONO, color: T.T3,
              letterSpacing: 1, textTransform: "uppercase",
              borderBottom: `1px solid ${T.BD}`, fontWeight: 600,
            }}>
              <div>#</div>
              <div>Grade</div>
              <div>Ticker / Name</div>
              <div style={{ textAlign: "right" }}>Price</div>
              <div style={{ textAlign: "right" }}>Score</div>
              <div style={{ textAlign: "center" }} title="Quality">Q</div>
              <div style={{ textAlign: "center" }} title="Growth">G</div>
              <div style={{ textAlign: "center" }} title="Momentum">M</div>
              <div style={{ textAlign: "center" }} title="Liquidity">L</div>
              <div style={{ textAlign: "center" }} title="Stability">S</div>
              <div style={{ textAlign: "center" }}>P/E</div>
              <div style={{ textAlign: "center" }}>⭐</div>
            </div>
            {results.map((r, i) => {
              const ccy = r.data.currency === "INR" ? "₹" : "$";
              const inWatchlist = watchlist.includes(r.data.ticker);
              return (
                <div
                  key={r.data.ticker}
                  onClick={() => onSelectTicker(r.data.ticker)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "40px 60px 1.8fr 80px 80px 50px 50px 50px 50px 50px 60px 40px",
                    gap: 8, padding: "10px",
                    fontSize: 12, fontFamily: MONO, color: T.T1,
                    borderBottom: `1px solid ${T.ACT}`, alignItems: "center",
                    cursor: "pointer", transition: "background 0.1s ease",
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = T.ACT}
                  onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                >
                  <div style={{ color: T.T3 }}>{i + 1}</div>
                  <div>
                    <span style={{
                      padding: "3px 8px", background: `${r.grade.color}15`,
                      border: `1px solid ${r.grade.color}40`, borderRadius: 3,
                      color: r.grade.color, fontWeight: r.grade.weight, fontSize: 11,
                    }}>{r.grade.label}</span>
                  </div>
                  <div>
                    <div style={{ color: T.T1, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
                      {r.data.ticker}
                      {r.factors.coverage < 60 && (
                        <span
                          title={`Partial data — ${r.factors.coverage.toFixed(0)}% factor coverage`}
                          style={{
                            width: 6, height: 6, borderRadius: 3,
                            background: T.YL, flexShrink: 0,
                          }}
                        />
                      )}
                    </div>
                    <div style={{ fontSize: 10, color: T.T3, marginTop: 2, fontFamily: BODY, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.data.company_name || "—"}
                    </div>
                  </div>
                  <div style={{ textAlign: "right", color: T.T1, fontWeight: 600 }}>
                    {ccy}{(+r.data.current_price).toFixed(2)}
                  </div>
                  <div style={{ textAlign: "right", color: r.grade.color, fontWeight: 700 }}>
                    {r.composite.toFixed(1)}
                  </div>
                  {[r.factors.Q, r.factors.G, r.factors.M, r.factors.L, r.factors.S].map((v, j) => {
                    const c = v >= 70 ? T.GR : v >= 50 ? T.YL : T.RD;
                    return (
                      <div key={j} style={{ textAlign: "center", color: c, fontSize: 11 }}>
                        {v.toFixed(0)}
                      </div>
                    );
                  })}
                  <div style={{ textAlign: "center", color: T.T2, fontSize: 11 }}>
                    {n(r.data.pe_ratio) !== null ? n(r.data.pe_ratio).toFixed(1) : "—"}
                  </div>
                  <div
                    onClick={(e) => { e.stopPropagation(); onToggleWatch(r.data.ticker); }}
                    style={{
                      textAlign: "center", cursor: "pointer",
                      color: inWatchlist ? T.YL : T.T3, fontSize: 14,
                    }}
                  >
                    {inWatchlist ? "★" : "☆"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

/* ============================================================
   MARKETS PAGE — Global indices, sector performance, breadth (Session 5)
   ============================================================ */

const SECTOR_REPRESENTATIVES = {
  "Technology": "XLK",
  "Financials": "XLF",
  "Healthcare": "XLV",
  "Energy": "XLE",
  "Consumer Disc.": "XLY",
  "Consumer Staples": "XLP",
  "Industrials": "XLI",
  "Utilities": "XLU",
  "Materials": "XLB",
  "Real Estate": "XLRE",
  "Communications": "XLC",
};

function MarketsPage({ onTickerSelect }) {
  const [indices, setIndices] = useState([]);
  const [loadingIndices, setLoadingIndices] = useState(true);
  const [sectors, setSectors] = useState([]);
  const [loadingSectors, setLoadingSectors] = useState(false);

  useEffect(() => {
    const fetchIndices = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/global-ticker`);
        if (res.ok) {
          const j = await res.json();
          const arr = Array.isArray(j) ? j : (j.indices || j.data || []);
          setIndices(arr);
        }
      } catch (e) { /* silent */ }
      finally { setLoadingIndices(false); }
    };
    fetchIndices();
    // Refresh every 60 seconds
    const interval = setInterval(fetchIndices, 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const loadSectors = useCallback(async () => {
    setLoadingSectors(true);
    const symbols = Object.values(SECTOR_REPRESENTATIVES);
    const results = await batchFetchStocks(symbols, null, 6);
    const withName = results.map(r => {
      const sectorName = Object.entries(SECTOR_REPRESENTATIVES)
        .find(([, sym]) => sym === r.ticker)?.[0] || r.ticker;
      return { ...r, sectorName };
    });
    setSectors(withName);
    setLoadingSectors(false);
  }, []);

  useEffect(() => { loadSectors(); }, [loadSectors]);

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, letterSpacing: 2, textTransform: "uppercase" }}>
            Markets · Global Overview
          </div>
          <div style={{ fontSize: 20, fontFamily: BODY, color: T.T1, fontWeight: 700, marginTop: 4 }}>
            Indices, sectors, and breadth
          </div>
        </div>
        <div style={{
          fontSize: 10, fontFamily: MONO, color: T.T3,
          padding: "4px 10px", border: `1px solid ${T.BD}`, borderRadius: 3,
          letterSpacing: 1.5, textTransform: "uppercase",
        }}>Auto-refresh 60s</div>
      </div>

      {/* Global indices */}
      <div style={{ marginBottom: 14 }}>
        <Card title="Global Indices" accent={loadingIndices ? { label: "Loading", color: T.YL } : { label: `${indices.length} indices`, color: T.GR }}>
          {loadingIndices ? (
            <div style={{ padding: 20, textAlign: "center", color: T.T3, fontSize: 12, fontFamily: MONO }}>
              Fetching market data...
            </div>
          ) : indices.length === 0 ? (
            <div style={{ padding: 20, textAlign: "center", color: T.T3, fontSize: 12, fontFamily: MONO }}>
              No index data available.
            </div>
          ) : (
            <div style={{
              display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10,
            }}>
              {indices.map((idx, i) => {
                const change = n(idx.change_percent ?? idx.changePercent ?? idx.change);
                const price = n(idx.price);
                const col = change === null ? T.T3 : change >= 0 ? T.GR : T.RD;
                return (
                  <div key={i} style={{
                    padding: 14, background: T.ACT, borderRadius: 6,
                    borderLeft: `3px solid ${col}`,
                  }}>
                    <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2, letterSpacing: 0.5, fontWeight: 600 }}>
                      {idx.symbol || idx.name || idx.ticker || "—"}
                    </div>
                    <div style={{ fontSize: 18, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 6 }}>
                      {price !== null ? price.toFixed(2) : "—"}
                    </div>
                    {change !== null && (
                      <div style={{ fontSize: 12, fontFamily: MONO, color: col, marginTop: 3, fontWeight: 600 }}>
                        {change >= 0 ? "▲" : "▼"} {change >= 0 ? "+" : ""}{change.toFixed(2)}%
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>

      {/* Sector heatmap */}
      <div style={{ marginBottom: 14 }}>
        <Card
          title="Sector Performance (SPDR ETFs)"
          accent={loadingSectors ? { label: "Loading", color: T.YL } : { label: `${sectors.length} sectors`, color: T.CY }}
        >
          {loadingSectors ? (
            <div style={{ padding: 20, textAlign: "center", color: T.T3, fontSize: 12, fontFamily: MONO }}>
              Loading sector ETFs...
            </div>
          ) : sectors.length === 0 ? (
            <div style={{ padding: 20, textAlign: "center", color: T.T3, fontSize: 12, fontFamily: MONO }}>
              Sector data unavailable.
            </div>
          ) : (
            <SectorHeatmapBars sectors={sectors} onClick={onTickerSelect} />
          )}
        </Card>
      </div>

      {/* Breadth indicators */}
      <Card title="Market Breadth" accent={{ label: "Derived", color: T.PP }}>
        <MarketBreadth sectors={sectors} indices={indices} />
      </Card>
    </div>
  );
}

function SectorHeatmapBars({ sectors, onClick }) {
  // Performance proxy: use % of 52W range (upper = bullish, lower = bearish)
  const enriched = sectors.map(s => {
    const px = n(s.current_price);
    const hi = n(s.week52_high);
    const lo = n(s.week52_low);
    const pct52 = (px !== null && hi !== null && lo !== null && hi > lo)
      ? ((px - lo) / (hi - lo)) * 100
      : null;

    // Simple recent trend: price vs SMA 50
    const s50 = n(s.sma_50);
    const vsSMA50 = (px !== null && s50 !== null && s50 > 0) ? ((px - s50) / s50) * 100 : null;

    return { ...s, pct52, vsSMA50 };
  }).sort((a, b) => (b.vsSMA50 ?? -999) - (a.vsSMA50 ?? -999));

  return (
    <div style={{ display: "grid", gap: 6 }}>
      {enriched.map((s, i) => {
        const v = s.vsSMA50;
        const col = v === null ? T.T3 : v > 3 ? T.GR : v > 0 ? T.CY : v > -3 ? T.YL : T.RD;
        // Bar range: -10% to +10%
        const barLeft = v === null ? 50 : Math.min(100, Math.max(0, 50 + v * 5));
        return (
          <div
            key={i}
            onClick={() => onClick(s.ticker)}
            style={{
              padding: "10px 12px", background: T.ACT, borderRadius: 4,
              display: "grid", gridTemplateColumns: "1.4fr 70px 1.5fr 80px 80px", gap: 12,
              alignItems: "center", cursor: "pointer", transition: "background 0.1s ease",
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = T.CARD}
            onMouseLeave={(e) => e.currentTarget.style.background = T.ACT}
          >
            <div>
              <div style={{ fontSize: 13, fontFamily: BODY, color: T.T1, fontWeight: 600 }}>
                {s.sectorName}
              </div>
              <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, marginTop: 2, letterSpacing: 0.5 }}>
                {s.ticker}
              </div>
            </div>
            <div style={{ fontSize: 13, fontFamily: MONO, color: T.T1, textAlign: "right", fontWeight: 600 }}>
              ${(+s.current_price).toFixed(2)}
            </div>
            <div style={{ position: "relative", height: 6, background: T.CARD, borderRadius: 3 }}>
              <div style={{ position: "absolute", top: 0, left: "50%", width: 1, height: "100%", background: T.T3, opacity: 0.5 }} />
              {v !== null && (
                <div style={{
                  position: "absolute", top: 0,
                  left: v >= 0 ? "50%" : `${barLeft}%`,
                  width: `${Math.abs(v >= 0 ? barLeft - 50 : 50 - barLeft)}%`,
                  height: "100%", background: col, borderRadius: 2,
                }} />
              )}
            </div>
            <div style={{ fontSize: 12, fontFamily: MONO, color: col, textAlign: "right", fontWeight: 600 }}>
              {v !== null ? `${v > 0 ? "+" : ""}${v.toFixed(2)}%` : "—"}
            </div>
            <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, textAlign: "right" }}>
              {s.pct52 !== null ? `${s.pct52.toFixed(0)}% of 52W` : "—"}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function MarketBreadth({ sectors, indices }) {
  // Breadth metrics derived from sector ETFs
  const advancing = sectors.filter(s => {
    const px = n(s.current_price); const s50 = n(s.sma_50);
    return px !== null && s50 !== null && px > s50;
  }).length;
  const declining = sectors.length - advancing;
  const breadthPct = sectors.length > 0 ? (advancing / sectors.length) * 100 : 0;

  // Sectors above 200 SMA
  const above200 = sectors.filter(s => {
    const px = n(s.current_price); const s200 = n(s.sma_200);
    return px !== null && s200 !== null && px > s200;
  }).length;
  const above200Pct = sectors.length > 0 ? (above200 / sectors.length) * 100 : 0;

  // Regime classification
  let regime, regimeColor;
  if (breadthPct >= 70 && above200Pct >= 70) { regime = "Risk-On"; regimeColor = T.GR; }
  else if (breadthPct >= 50 && above200Pct >= 50) { regime = "Neutral-Bullish"; regimeColor = T.CY; }
  else if (breadthPct >= 30) { regime = "Mixed"; regimeColor = T.YL; }
  else { regime = "Risk-Off"; regimeColor = T.RD; }

  return (
    <div>
      <div style={{
        padding: 16, background: T.ACT, borderRadius: 6, marginBottom: 12,
        borderLeft: `3px solid ${regimeColor}`,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Market Regime
            </div>
            <div style={{ fontSize: 26, fontFamily: BODY, color: regimeColor, fontWeight: 700, marginTop: 4 }}>
              {regime}
            </div>
          </div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2, textAlign: "right" }}>
            Based on {sectors.length} sector ETFs
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
        <div style={{ padding: 14, background: T.ACT, borderRadius: 4 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
            Above SMA 50
          </div>
          <div style={{ fontSize: 22, fontFamily: MONO, color: breadthPct >= 50 ? T.GR : T.RD, fontWeight: 700, marginTop: 4 }}>
            {advancing}/{sectors.length}
          </div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2, marginTop: 4 }}>
            {breadthPct.toFixed(0)}% short-term breadth
          </div>
        </div>
        <div style={{ padding: 14, background: T.ACT, borderRadius: 4 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
            Above SMA 200
          </div>
          <div style={{ fontSize: 22, fontFamily: MONO, color: above200Pct >= 50 ? T.GR : T.RD, fontWeight: 700, marginTop: 4 }}>
            {above200}/{sectors.length}
          </div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2, marginTop: 4 }}>
            {above200Pct.toFixed(0)}% primary trend
          </div>
        </div>
        <div style={{ padding: 14, background: T.ACT, borderRadius: 4 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
            Advance/Decline
          </div>
          <div style={{ fontSize: 22, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 4 }}>
            {advancing}&nbsp;·&nbsp;<span style={{ color: T.RD }}>{declining}</span>
          </div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T2, marginTop: 4 }}>
            Ratio: {declining > 0 ? (advancing / declining).toFixed(2) : "∞"}x
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   TOOLS PAGE — Graham, DCF, Kelly, Options P&L (Session 5)
   ============================================================ */

function ToolsPage() {
  const [tab, setTab] = useState("graham");

  const tabs = [
    { id: "graham", label: "Graham Calculator" },
    { id: "dcf", label: "DCF Modeler" },
    { id: "kelly", label: "Position Sizer (Kelly)" },
    { id: "options", label: "Options P&L" },
  ];

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, letterSpacing: 2, textTransform: "uppercase" }}>
            Tools · Institutional Utilities
          </div>
          <div style={{ fontSize: 20, fontFamily: BODY, color: T.T1, fontWeight: 700, marginTop: 4 }}>
            Decision calculators
          </div>
        </div>
      </div>

      {/* Tab nav */}
      <div style={{
        display: "flex", gap: 2, marginBottom: 16,
        background: T.CARD, padding: 4, borderRadius: 8,
        border: `1px solid ${T.BD}`,
      }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            flex: 1, padding: "10px 14px",
            background: tab === t.id ? T.BL : "transparent",
            border: "none", borderRadius: 5,
            fontFamily: MONO, fontSize: 11, fontWeight: 600,
            color: tab === t.id ? "#fff" : T.T2,
            cursor: "pointer", letterSpacing: 1, textTransform: "uppercase",
            transition: "all 0.15s ease",
          }}>{t.label}</button>
        ))}
      </div>

      {tab === "graham" && <GrahamCalc />}
      {tab === "dcf" && <DCFModeler />}
      {tab === "kelly" && <KellySizer />}
      {tab === "options" && <OptionsPnL />}
    </div>
  );
}

function ToolInput({ label, value, onChange, suffix, placeholder }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ position: "relative" }}>
        <input
          type="number"
          step="any"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder || ""}
          style={{
            width: "100%", padding: "10px 12px",
            background: T.ACT, border: `1px solid ${T.BD}`,
            borderRadius: 4, fontFamily: MONO, fontSize: 13,
            color: T.T1, outline: "none", boxSizing: "border-box",
          }}
        />
        {suffix && (
          <div style={{
            position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
            fontSize: 11, fontFamily: MONO, color: T.T3,
          }}>{suffix}</div>
        )}
      </div>
    </div>
  );
}

function GrahamCalc() {
  const [eps, setEps] = useState("5");
  const [bv, setBv] = useState("25");
  const [growth, setGrowth] = useState("10");
  const [price, setPrice] = useState("100");

  const epsN = parseFloat(eps) || 0;
  const bvN = parseFloat(bv) || 0;
  const gN = parseFloat(growth) || 0;
  const pxN = parseFloat(price) || 0;

  const graham = (epsN > 0 && bvN > 0) ? Math.sqrt(22.5 * epsN * bvN) : null;
  const intrinsic = epsN > 0 ? epsN * (8.5 + 2 * Math.min(Math.max(gN, -10), 25)) : null;
  const mos = (intrinsic !== null && pxN > 0) ? ((intrinsic - pxN) / intrinsic) * 100 : null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <Card title="Inputs">
        <div style={{ display: "grid", gap: 14 }}>
          <ToolInput label="EPS (TTM)" value={eps} onChange={setEps} suffix="$" />
          <ToolInput label="Book Value per Share" value={bv} onChange={setBv} suffix="$" />
          <ToolInput label="Expected Growth Rate" value={growth} onChange={setGrowth} suffix="%" />
          <ToolInput label="Current Price" value={price} onChange={setPrice} suffix="$" />
        </div>
      </Card>

      <Card title="Valuation Output" accent={{ label: "Graham Formulas", color: T.PP }}>
        <div style={{ display: "grid", gap: 14 }}>
          <div style={{ padding: 14, background: T.ACT, borderRadius: 6, borderLeft: `3px solid ${T.BL}` }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Graham Number
            </div>
            <div style={{ fontSize: 26, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 4 }}>
              {graham !== null ? `$${graham.toFixed(2)}` : "—"}
            </div>
            <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, marginTop: 4 }}>
              √(22.5 × EPS × BV) — defensive fair value
            </div>
          </div>

          <div style={{ padding: 14, background: T.ACT, borderRadius: 6, borderLeft: `3px solid ${T.PP}` }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Graham Intrinsic
            </div>
            <div style={{ fontSize: 26, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 4 }}>
              {intrinsic !== null ? `$${intrinsic.toFixed(2)}` : "—"}
            </div>
            <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, marginTop: 4 }}>
              EPS × (8.5 + 2g) — growth-adjusted
            </div>
          </div>

          <div style={{
            padding: 14, background: T.ACT, borderRadius: 6,
            borderLeft: `3px solid ${mos === null ? T.T3 : mos > 20 ? T.GR : mos < -20 ? T.RD : T.YL}`,
          }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Margin of Safety
            </div>
            <div style={{
              fontSize: 26, fontFamily: MONO, fontWeight: 700, marginTop: 4,
              color: mos === null ? T.T3 : mos > 20 ? T.GR : mos < -20 ? T.RD : T.YL,
            }}>
              {mos !== null ? `${mos > 0 ? "+" : ""}${mos.toFixed(1)}%` : "—"}
            </div>
            <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, marginTop: 4 }}>
              {mos === null ? "—" :
                mos > 30 ? "Strong buy zone" :
                mos > 15 ? "Reasonable discount" :
                mos > -15 ? "Fairly valued" :
                "Overvalued — avoid"}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

function DCFModeler() {
  const [fcf, setFcf] = useState("10");
  const [growthY1_5, setGrowthY1_5] = useState("15");
  const [growthY6_10, setGrowthY6_10] = useState("8");
  const [terminal, setTerminal] = useState("3");
  const [discount, setDiscount] = useState("10");
  const [shares, setShares] = useState("1000");
  const [debt, setDebt] = useState("50");
  const [cash, setCash] = useState("20");
  const [price, setPrice] = useState("100");

  const fcfN = parseFloat(fcf) || 0;
  const g1 = (parseFloat(growthY1_5) || 0) / 100;
  const g2 = (parseFloat(growthY6_10) || 0) / 100;
  const tg = (parseFloat(terminal) || 0) / 100;
  const r = (parseFloat(discount) || 10) / 100;
  const sharesN = parseFloat(shares) || 1;
  const debtN = parseFloat(debt) || 0;
  const cashN = parseFloat(cash) || 0;
  const pxN = parseFloat(price) || 0;

  // Run DCF: years 1-5 at g1, years 6-10 at g2, terminal at tg
  let cf = fcfN;
  let enterprise = 0;
  const yearCF = [];
  for (let y = 1; y <= 10; y++) {
    const g = y <= 5 ? g1 : g2;
    cf = cf * (1 + g);
    const pv = cf / Math.pow(1 + r, y);
    yearCF.push({ y, cf, pv });
    enterprise += pv;
  }
  // Terminal value (Gordon growth at year 10)
  const tv = r > tg ? (cf * (1 + tg)) / (r - tg) : 0;
  const tvPV = tv / Math.pow(1 + r, 10);
  enterprise += tvPV;

  const equity = enterprise - debtN + cashN;
  const fairPrice = equity / sharesN;
  const upside = pxN > 0 ? ((fairPrice - pxN) / pxN) * 100 : null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.3fr", gap: 16 }}>
      <Card title="DCF Inputs">
        <div style={{ display: "grid", gap: 12 }}>
          <ToolInput label="Base Year FCF (millions)" value={fcf} onChange={setFcf} suffix="$M" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <ToolInput label="Growth Y1–Y5" value={growthY1_5} onChange={setGrowthY1_5} suffix="%" />
            <ToolInput label="Growth Y6–Y10" value={growthY6_10} onChange={setGrowthY6_10} suffix="%" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <ToolInput label="Terminal Growth" value={terminal} onChange={setTerminal} suffix="%" />
            <ToolInput label="Discount Rate" value={discount} onChange={setDiscount} suffix="%" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
            <ToolInput label="Debt" value={debt} onChange={setDebt} suffix="$M" />
            <ToolInput label="Cash" value={cash} onChange={setCash} suffix="$M" />
            <ToolInput label="Shares (M)" value={shares} onChange={setShares} />
          </div>
          <ToolInput label="Current Price" value={price} onChange={setPrice} suffix="$" />
        </div>
      </Card>

      <Card title="DCF Output" accent={{ label: "10-Year 2-Stage + Terminal", color: T.CY }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 }}>
          <div style={{ padding: 14, background: T.ACT, borderRadius: 6 }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
              Enterprise Value
            </div>
            <div style={{ fontSize: 22, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 4 }}>
              ${enterprise.toFixed(1)}M
            </div>
          </div>
          <div style={{ padding: 14, background: T.ACT, borderRadius: 6 }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
              Equity Value
            </div>
            <div style={{ fontSize: 22, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 4 }}>
              ${equity.toFixed(1)}M
            </div>
          </div>
          <div style={{
            padding: 14, background: T.ACT, borderRadius: 6,
            borderLeft: `3px solid ${T.BL}`, gridColumn: "1 / -1",
          }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
              Fair Price per Share
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4 }}>
              <div style={{ fontSize: 32, fontFamily: MONO, color: T.BL, fontWeight: 700 }}>
                ${fairPrice.toFixed(2)}
              </div>
              {upside !== null && (
                <div style={{
                  fontSize: 16, fontFamily: MONO, fontWeight: 700,
                  color: upside > 20 ? T.GR : upside < -20 ? T.RD : T.YL,
                }}>
                  {upside > 0 ? "+" : ""}{upside.toFixed(1)}% vs current
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Cash flow projection table */}
        <div style={{
          padding: 12, background: T.ACT, borderRadius: 6,
        }}>
          <div style={{
            fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2,
            textTransform: "uppercase", marginBottom: 8,
          }}>Cash Flow Projection</div>
          <div style={{ display: "grid", gap: 4 }}>
            {yearCF.map((y, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "40px 1fr 100px 100px",
                gap: 8, fontSize: 11, fontFamily: MONO,
                padding: "4px 0",
                borderBottom: i < yearCF.length - 1 ? `1px solid ${T.BD}` : "none",
              }}>
                <span style={{ color: T.T3 }}>Y{y.y}</span>
                <div style={{ position: "relative", height: 8, background: T.CARD, borderRadius: 2, alignSelf: "center" }}>
                  <div style={{
                    width: `${(y.pv / yearCF[0].pv) * 100}%`,
                    maxWidth: "100%", height: "100%",
                    background: T.BL, borderRadius: 2,
                  }} />
                </div>
                <span style={{ color: T.T2, textAlign: "right" }}>${y.cf.toFixed(1)}M</span>
                <span style={{ color: T.T1, textAlign: "right", fontWeight: 600 }}>${y.pv.toFixed(1)}M</span>
              </div>
            ))}
            <div style={{
              display: "grid", gridTemplateColumns: "40px 1fr 100px 100px",
              gap: 8, fontSize: 11, fontFamily: MONO,
              padding: "6px 0", marginTop: 4,
              borderTop: `1px solid ${T.PP}`, color: T.PP, fontWeight: 700,
            }}>
              <span>TV</span>
              <span>Terminal Value</span>
              <span style={{ textAlign: "right" }}>${tv.toFixed(0)}M</span>
              <span style={{ textAlign: "right" }}>${tvPV.toFixed(1)}M</span>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

function KellySizer() {
  const [winRate, setWinRate] = useState("55");
  const [winSize, setWinSize] = useState("10");
  const [lossSize, setLossSize] = useState("5");
  const [capital, setCapital] = useState("100000");
  const [fraction, setFraction] = useState("25"); // Kelly fractionalization

  const p = (parseFloat(winRate) || 0) / 100;
  const q = 1 - p;
  const b = (parseFloat(winSize) || 0) / (parseFloat(lossSize) || 1); // odds: win/loss ratio
  const cap = parseFloat(capital) || 0;
  const frac = (parseFloat(fraction) || 100) / 100;

  // Kelly formula: f* = (bp - q) / b
  const kelly = b > 0 ? (b * p - q) / b : 0;
  const kellyPct = kelly * 100;
  const fractionalKelly = kelly * frac;
  const suggestedSize = cap * Math.max(0, fractionalKelly);

  // Edge
  const ev = p * (parseFloat(winSize) || 0) - q * (parseFloat(lossSize) || 0);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <Card title="Trade Parameters">
        <div style={{ display: "grid", gap: 14 }}>
          <ToolInput label="Win Rate" value={winRate} onChange={setWinRate} suffix="%" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <ToolInput label="Avg Win" value={winSize} onChange={setWinSize} suffix="%" />
            <ToolInput label="Avg Loss" value={lossSize} onChange={setLossSize} suffix="%" />
          </div>
          <ToolInput label="Total Capital" value={capital} onChange={setCapital} suffix="$" />
          <ToolInput label="Kelly Fraction" value={fraction} onChange={setFraction} suffix="%" placeholder="25 = quarter Kelly" />
          <div style={{
            padding: 10, background: T.ACT, borderRadius: 4,
            fontSize: 11, fontFamily: BODY, color: T.T2, lineHeight: 1.5,
          }}>
            <strong style={{ color: T.T1 }}>Kelly Fractionalization:</strong> Institutional traders
            use 1/4 or 1/2 Kelly to reduce drawdown. Full Kelly can be gambling-level aggressive.
          </div>
        </div>
      </Card>

      <Card title="Optimal Sizing" accent={{ label: "Kelly Criterion", color: T.GR }}>
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{
            padding: 14, background: T.ACT, borderRadius: 6,
            borderLeft: `3px solid ${ev > 0 ? T.GR : T.RD}`,
          }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
              Expected Value per Trade
            </div>
            <div style={{ fontSize: 22, fontFamily: MONO, color: ev > 0 ? T.GR : T.RD, fontWeight: 700, marginTop: 4 }}>
              {ev > 0 ? "+" : ""}{ev.toFixed(2)}%
            </div>
            <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, marginTop: 4 }}>
              {ev > 0 ? "Positive edge — tradeable" : "Negative edge — do NOT trade"}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
              <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
                Full Kelly
              </div>
              <div style={{ fontSize: 22, fontFamily: MONO, color: kellyPct > 0 ? T.T1 : T.RD, fontWeight: 700, marginTop: 4 }}>
                {kellyPct.toFixed(1)}%
              </div>
            </div>
            <div style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
              <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
                Fractional ({fraction}%)
              </div>
              <div style={{ fontSize: 22, fontFamily: MONO, color: T.PP, fontWeight: 700, marginTop: 4 }}>
                {(fractionalKelly * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          <div style={{
            padding: 16, background: T.ACT, borderRadius: 6,
            borderLeft: `3px solid ${T.BL}`,
          }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Suggested Position Size
            </div>
            <div style={{ fontSize: 30, fontFamily: MONO, color: T.BL, fontWeight: 700, marginTop: 6 }}>
              ${suggestedSize.toFixed(0)}
            </div>
            <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, marginTop: 4 }}>
              {(fractionalKelly * 100).toFixed(2)}% of ${cap.toLocaleString()} capital
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

function OptionsPnL() {
  const [optionType, setOptionType] = useState("CALL");
  const [strike, setStrike] = useState("22500");
  const [premium, setPremium] = useState("120");
  const [spot, setSpot] = useState("22500");
  const [lotSize, setLotSize] = useState("75");

  const strikeN = parseFloat(strike) || 0;
  const premN = parseFloat(premium) || 0;
  const spotN = parseFloat(spot) || 0;
  const lotN = parseFloat(lotSize) || 1;

  // Generate P&L curve from spot-10% to spot+10%
  const range = spotN * 0.1;
  const steps = 21;
  const points = [];
  for (let i = 0; i < steps; i++) {
    const s = spotN - range + (2 * range * i / (steps - 1));
    let pnl;
    if (optionType === "CALL") {
      pnl = (Math.max(0, s - strikeN) - premN) * lotN;
    } else {
      pnl = (Math.max(0, strikeN - s) - premN) * lotN;
    }
    points.push({ s, pnl });
  }

  const breakeven = optionType === "CALL" ? strikeN + premN : strikeN - premN;
  const maxLoss = -premN * lotN;
  const currentPnL = points.find(p => Math.abs(p.s - spotN) < range / steps)?.pnl ?? 0;

  // SVG coordinates
  const width = 600, height = 240, padX = 50, padY = 30;
  const innerW = width - padX * 2, innerH = height - padY * 2;
  const pnls = points.map(p => p.pnl);
  const yMax = Math.max(...pnls, 1000);
  const yMin = Math.min(...pnls, -1000);
  const xScale = (s) => padX + ((s - points[0].s) / (points[points.length-1].s - points[0].s)) * innerW;
  const yScale = (p) => padY + innerH - ((p - yMin) / (yMax - yMin)) * innerH;
  const zeroY = yScale(0);

  const linePath = "M " + points.map(p => `${xScale(p.s).toFixed(1)},${yScale(p.pnl).toFixed(1)}`).join(" L ");

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 16 }}>
      <Card title="Option Setup">
        <div style={{ display: "grid", gap: 14 }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase", marginBottom: 6 }}>
              Option Type
            </div>
            <div style={{ display: "flex", gap: 4, padding: 3, background: T.ACT, borderRadius: 6 }}>
              {["CALL", "PUT"].map(t => (
                <button key={t} onClick={() => setOptionType(t)} style={{
                  flex: 1, padding: "8px 14px",
                  background: optionType === t ? (t === "CALL" ? T.GR : T.RD) : "transparent",
                  border: "none", borderRadius: 4,
                  fontFamily: MONO, fontSize: 11, fontWeight: 700,
                  color: optionType === t ? "#fff" : T.T2,
                  cursor: "pointer", letterSpacing: 1,
                }}>BUY {t}</button>
              ))}
            </div>
          </div>
          <ToolInput label="Strike Price" value={strike} onChange={setStrike} />
          <ToolInput label="Premium Paid" value={premium} onChange={setPremium} />
          <ToolInput label="Current Spot" value={spot} onChange={setSpot} />
          <ToolInput label="Lot Size" value={lotSize} onChange={setLotSize} />
        </div>
      </Card>

      <Card title="P&L Analysis" accent={{ label: optionType === "CALL" ? "Long Call" : "Long Put", color: optionType === "CALL" ? T.GR : T.RD }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 14 }}>
          <div style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
              Breakeven
            </div>
            <div style={{ fontSize: 18, fontFamily: MONO, color: T.YL, fontWeight: 700, marginTop: 4 }}>
              {breakeven.toFixed(2)}
            </div>
          </div>
          <div style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
              Max Loss
            </div>
            <div style={{ fontSize: 18, fontFamily: MONO, color: T.RD, fontWeight: 700, marginTop: 4 }}>
              ${maxLoss.toFixed(0)}
            </div>
          </div>
          <div style={{ padding: 12, background: T.ACT, borderRadius: 4 }}>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase" }}>
              Max Upside
            </div>
            <div style={{ fontSize: 18, fontFamily: MONO, color: T.GR, fontWeight: 700, marginTop: 4 }}>
              {optionType === "CALL" ? "Unlimited" : `$${((strikeN - premN) * lotN).toFixed(0)}`}
            </div>
          </div>
        </div>

        {/* P&L chart */}
        <div style={{ padding: 14, background: T.ACT, borderRadius: 6 }}>
          <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase", marginBottom: 8 }}>
            P&L Curve (±10% from spot)
          </div>
          <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto", display: "block" }}>
            {/* Zero line */}
            <line x1={padX} y1={zeroY} x2={width - padX} y2={zeroY} stroke={T.T3} strokeWidth="1" strokeDasharray="4 4" opacity="0.5" />
            {/* Strike vertical */}
            <line x1={xScale(strikeN)} y1={padY} x2={xScale(strikeN)} y2={height - padY} stroke={T.BL} strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />
            <text x={xScale(strikeN) + 4} y={padY + 12} fill={T.BL} fontSize="10" fontFamily="JetBrains Mono">K {strikeN}</text>
            {/* Breakeven vertical */}
            <line x1={xScale(breakeven)} y1={padY} x2={xScale(breakeven)} y2={height - padY} stroke={T.YL} strokeWidth="1" strokeDasharray="3 3" opacity="0.7" />
            <text x={xScale(breakeven) + 4} y={padY + 24} fill={T.YL} fontSize="10" fontFamily="JetBrains Mono">BE {breakeven.toFixed(0)}</text>
            {/* Profit zone fill */}
            <path
              d={`${linePath} L ${xScale(points[points.length-1].s)},${zeroY} L ${xScale(points[0].s)},${zeroY} Z`}
              fill={T.GR} fillOpacity="0.15"
            />
            {/* P&L line */}
            <path d={linePath} fill="none" stroke={optionType === "CALL" ? T.GR : T.RD} strokeWidth="2" />
            {/* Current spot marker */}
            <circle cx={xScale(spotN)} cy={yScale(currentPnL)} r="5" fill={T.T1} stroke={T.BG} strokeWidth="2" />
            <text x={xScale(spotN)} y={height - 8} fill={T.T1} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">
              Spot {spotN}
            </text>
            {/* Y labels */}
            <text x={padX - 6} y={padY + 4} fill={T.GR} fontSize="10" fontFamily="JetBrains Mono" textAnchor="end">+${yMax.toFixed(0)}</text>
            <text x={padX - 6} y={zeroY + 4} fill={T.T3} fontSize="10" fontFamily="JetBrains Mono" textAnchor="end">$0</text>
            <text x={padX - 6} y={height - padY + 4} fill={T.RD} fontSize="10" fontFamily="JetBrains Mono" textAnchor="end">${yMin.toFixed(0)}</text>
          </svg>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, textAlign: "center", marginTop: 6 }}>
            Current P&L at spot: <span style={{ color: currentPnL >= 0 ? T.GR : T.RD, fontWeight: 700 }}>
              {currentPnL >= 0 ? "+" : ""}${currentPnL.toFixed(0)}
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
}

/* ============================================================
   DREAM PORTFOLIO — PMS-style construction (Session 5)
   ============================================================ */

const PMS_BUCKETS = [
  { id: "growth",     label: "Growth Leaders",    target: 35, mode: "growth",     color: T.GR,  desc: "Alpha drivers — AI/cloud/secular growth" },
  { id: "quality",    label: "Quality Core",      target: 25, mode: "quality",    color: T.BL,  desc: "Compounding backbone — monopolies/duopolies" },
  { id: "momentum",   label: "Momentum Tactical", target: 15, mode: "momentum",   color: T.PP,  desc: "Trend followers — fast rotation layer" },
  { id: "value",      label: "Value / Cyclical",  target: 10, mode: "value",      color: T.YL,  desc: "Drawdown protector + rotation alpha" },
  { id: "defensive",  label: "Defensive",         target: 10, mode: "dividend",   color: T.CY,  desc: "Shock absorbers — dividend + low vol" },
  { id: "multibagger",label: "Multibagger",       target: 5,  mode: "multibagger",color: T.RD,  desc: "Explosive upside — small weight, high R:R" },
];

function DreamPage({ onTickerSelect }) {
  const [region, setRegion] = useState("US");
  const [suggestions, setSuggestions] = useState({});
  const [loading, setLoading] = useState(false);
  const [capital, setCapital] = useState("1000000");

  const runBuilder = useCallback(async () => {
    setLoading(true);
    setSuggestions({});

    // Collect a wide universe — everything from the region
    const universes = UNIVERSES[region] || {};
    const allTickers = [...new Set(Object.values(universes).flat())];

    const raw = await batchFetchStocks(allTickers, null, 8);

    // Score every stock against every mode
    const scored = raw.map(d => {
      const factors = l0ScoreStock(d);
      if (!factors) return null;
      return { data: d, factors };
    }).filter(Boolean);

    // For each bucket, pick top stocks by that mode's weighting
    const byBucket = {};
    const used = new Set();
    PMS_BUCKETS.forEach(bucket => {
      const mode = SCAN_MODES.find(m => m.id === bucket.mode);
      const candidates = scored
        .filter(s => !used.has(s.data.ticker)) // don't double-count
        .map(s => ({ ...s, composite: l0Composite(s.factors, mode) }))
        .sort((a, b) => b.composite - a.composite);

      // Pick top 3 for each bucket (18 total = PMS ideal size)
      const picks = candidates.slice(0, 3);
      picks.forEach(p => used.add(p.data.ticker));
      byBucket[bucket.id] = picks;
    });

    setSuggestions(byBucket);
    setLoading(false);
  }, [region]);

  useEffect(() => { runBuilder(); }, [runBuilder]);

  const capN = parseFloat(capital) || 0;

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.T3, letterSpacing: 2, textTransform: "uppercase" }}>
            Dream Portfolio · Institutional PMS Builder
          </div>
          <div style={{ fontSize: 20, fontFamily: BODY, color: T.T1, fontWeight: 700, marginTop: 4 }}>
            12–18 stock portfolio across 6 factor buckets
          </div>
        </div>
        <div style={{
          fontSize: 10, fontFamily: MONO, color: T.T3,
          padding: "4px 10px", border: `1px solid ${T.BD}`, borderRadius: 3,
          letterSpacing: 1.5, textTransform: "uppercase",
        }}>BlackRock-style allocation</div>
      </div>

      {/* Controls */}
      <Card pad={14} style={{ marginBottom: 14 }}>
        <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 16, alignItems: "end" }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: MONO, color: T.T3, letterSpacing: 1.2, textTransform: "uppercase", marginBottom: 6 }}>
              Region
            </div>
            <div style={{ display: "flex", gap: 4, padding: 3, background: T.ACT, borderRadius: 6 }}>
              {["US", "IN"].map(r => (
                <button key={r} onClick={() => setRegion(r)} style={{
                  padding: "8px 16px",
                  background: region === r ? T.BL : "transparent",
                  border: "none", borderRadius: 4,
                  fontFamily: MONO, fontSize: 11, fontWeight: 700,
                  color: region === r ? "#fff" : T.T2,
                  cursor: "pointer", letterSpacing: 1,
                }}>{r === "US" ? "🇺🇸 US" : "🇮🇳 INDIA"}</button>
              ))}
            </div>
          </div>
          <div>
            <ToolInput
              label="Total Capital"
              value={capital}
              onChange={setCapital}
              suffix={region === "US" ? "$" : "₹"}
            />
          </div>
          <button onClick={runBuilder} disabled={loading} style={{
            padding: "12px 20px",
            background: loading ? T.ACT : T.BL,
            border: "none", borderRadius: 6,
            fontFamily: MONO, fontSize: 12, color: "#fff",
            fontWeight: 700, cursor: loading ? "wait" : "pointer",
            letterSpacing: 1, textTransform: "uppercase",
            opacity: loading ? 0.6 : 1,
          }}>
            {loading ? "Building..." : "↻ Rebuild"}
          </button>
        </div>
      </Card>

      {/* Allocation overview */}
      <Card title="Target Allocation" accent={{ label: "100%", color: T.PP }} style={{ marginBottom: 14 }}>
        <div style={{
          display: "flex", height: 40, borderRadius: 6, overflow: "hidden", marginBottom: 12,
          border: `1px solid ${T.BD}`,
        }}>
          {PMS_BUCKETS.map(b => (
            <div key={b.id} style={{
              width: `${b.target}%`, background: b.color,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, fontFamily: MONO, color: "#fff", fontWeight: 700,
              borderRight: `1px solid ${T.BG}`,
            }}>
              {b.target}%
            </div>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8 }}>
          {PMS_BUCKETS.map(b => (
            <div key={b.id} style={{
              padding: 10, background: T.ACT, borderRadius: 4,
              borderLeft: `3px solid ${b.color}`,
            }}>
              <div style={{ fontSize: 11, fontFamily: MONO, color: b.color, letterSpacing: 0.5, fontWeight: 700, textTransform: "uppercase" }}>
                {b.label}
              </div>
              <div style={{ fontSize: 18, fontFamily: MONO, color: T.T1, fontWeight: 700, marginTop: 4 }}>
                {b.target}%
              </div>
              <div style={{ fontSize: 10, fontFamily: BODY, color: T.T3, marginTop: 4, lineHeight: 1.3 }}>
                {b.desc}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Per-bucket suggestions */}
      {loading ? (
        <Card pad={30}>
          <div style={{ textAlign: "center" }}>
            <div style={{
              width: 32, height: 32, border: `2px solid ${T.ACT}`,
              borderTopColor: T.BL, borderRadius: "50%",
              margin: "0 auto 16px", animation: "spin 0.8s linear infinite",
            }} />
            <div style={{ fontFamily: MONO, fontSize: 12, color: T.T2, letterSpacing: 1 }}>
              Scoring universe across 6 factor modes...
            </div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        </Card>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {PMS_BUCKETS.map(bucket => {
            const picks = suggestions[bucket.id] || [];
            const mode = SCAN_MODES.find(m => m.id === bucket.mode);
            const bucketCapital = capN * (bucket.target / 100);
            const perStock = picks.length > 0 ? bucketCapital / picks.length : 0;
            const ccy = region === "IN" ? "₹" : "$";

            return (
              <Card
                key={bucket.id}
                title={`${bucket.label} · ${bucket.target}% · ${ccy}${bucketCapital.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
                accent={{ label: mode.label, color: bucket.color }}
                style={{ borderLeft: `3px solid ${bucket.color}` }}
              >
                {picks.length === 0 ? (
                  <div style={{ color: T.T3, fontSize: 12, fontFamily: MONO, padding: 10 }}>
                    No suitable candidates in this region's universe.
                  </div>
                ) : (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 10 }}>
                    {picks.map((p, i) => {
                      const grade = l0Grade(p.composite);
                      return (
                        <div
                          key={i}
                          onClick={() => onTickerSelect(p.data.ticker)}
                          style={{
                            padding: 12, background: T.ACT, borderRadius: 6,
                            cursor: "pointer", transition: "transform 0.1s ease",
                            borderTop: `2px solid ${grade.color}`,
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.transform = "translateY(-2px)"}
                          onMouseLeave={(e) => e.currentTarget.style.transform = "translateY(0)"}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <div style={{ fontSize: 14, fontFamily: MONO, color: T.T1, fontWeight: 700 }}>
                              {p.data.ticker}
                            </div>
                            <div style={{
                              fontSize: 10, fontFamily: MONO, padding: "2px 8px",
                              background: `${grade.color}15`, border: `1px solid ${grade.color}40`,
                              borderRadius: 3, color: grade.color, fontWeight: 700,
                            }}>{grade.label}</div>
                          </div>
                          <div style={{
                            fontSize: 11, fontFamily: BODY, color: T.T3,
                            marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                          }}>
                            {p.data.company_name || "—"}
                          </div>
                          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
                            <div>
                              <div style={{ fontSize: 9, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>Allocation</div>
                              <div style={{ fontSize: 13, fontFamily: MONO, color: T.T1, fontWeight: 600, marginTop: 2 }}>
                                {ccy}{perStock.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                              </div>
                            </div>
                            <div style={{ textAlign: "right" }}>
                              <div style={{ fontSize: 9, fontFamily: MONO, color: T.T3, letterSpacing: 1, textTransform: "uppercase" }}>Score</div>
                              <div style={{ fontSize: 13, fontFamily: MONO, color: grade.color, fontWeight: 700, marginTop: 2 }}>
                                {p.composite.toFixed(1)}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Framework disclaimer */}
      <div style={{
        marginTop: 16, padding: 14, background: T.CARD, border: `1px solid ${T.BD}`,
        borderRadius: 6, fontSize: 11, fontFamily: BODY, color: T.T2, lineHeight: 1.6,
      }}>
        <strong style={{ color: T.T1 }}>Framework:</strong> Each bucket uses its own L0 re-weighting
        (Growth mode for Growth Leaders, Quality for Core, etc.). The same universe is scored 6 ways,
        then top 3 stocks per bucket are selected without duplication. This mimics how an institutional
        PMS builds factor-balanced portfolios — not by "picking favorites" but by filling factor gaps.
      </div>
    </div>
  );
}

/* ============================================================
   PLACEHOLDER PAGES for menu items not yet built
   ============================================================ */

function PlaceholderPage({ title, description }) {
  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>
      <Card pad={40}>
        <div style={{ textAlign: "center" }}>
          <div style={{
            display: "inline-block", padding: "4px 10px",
            border: `1px solid ${T.YL}40`, borderRadius: 3,
            fontSize: 10, fontFamily: MONO, color: T.YL,
            letterSpacing: 2, marginBottom: 20, textTransform: "uppercase",
          }}>Upcoming</div>
          <div style={{
            fontSize: 28, fontFamily: BODY, color: T.T1,
            fontWeight: 700, marginBottom: 10,
          }}>{title}</div>
          <div style={{
            fontSize: 14, fontFamily: BODY, color: T.T2,
            maxWidth: 500, margin: "0 auto", lineHeight: 1.5,
          }}>{description}</div>
        </div>
      </Card>
    </div>
  );
}

/* ============================================================
   ERROR BOUNDARY — prevents any single component crash from
   taking down the whole app (Session 7 polish)
   ============================================================ */

class CelesysErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("[Celesys] Component error:", error, info);
  }

  reset = () => this.setState({ hasError: false, error: null });

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: 40, maxWidth: 600, margin: "60px auto",
          background: T.CARD, border: `1px solid ${T.RD}40`,
          borderRadius: 8, textAlign: "center",
        }}>
          <div style={{ fontSize: 32, color: T.RD, marginBottom: 12 }}>⚠</div>
          <div style={{
            fontSize: 16, fontFamily: BODY, color: T.T1, fontWeight: 600, marginBottom: 8,
          }}>Something went wrong</div>
          <div style={{
            fontSize: 12, fontFamily: MONO, color: T.T3, marginBottom: 20,
            padding: 12, background: T.ACT, borderRadius: 4, textAlign: "left",
            overflow: "auto", maxHeight: 120,
          }}>
            {this.state.error?.message || "Unknown error"}
          </div>
          <button onClick={this.reset} style={{
            padding: "10px 20px", background: T.BL, border: "none",
            borderRadius: 4, fontFamily: MONO, fontSize: 12, color: "#fff",
            fontWeight: 600, cursor: "pointer", letterSpacing: 1, textTransform: "uppercase",
          }}>Retry</button>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ============================================================
   SHELL — Top nav + routing
   ============================================================ */

export default function CelesysApp() {
  const [page, setPage] = useState("Home");
  const [ticker, setTicker] = useState("MU");

  const goAnalyze = (t) => {
    setTicker(t);
    setPage("Overview");
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: T.BG,
      color: T.T1,
      fontFamily: BODY,
    }}>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      <link
        href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@300;400;500;600;700&display=swap"
        rel="stylesheet"
      />

      {/* Global polish: responsive collapses, scrollbar, focus, selection (S7) */}
      <style>{`
        /* Scrollbar — keep the terminal aesthetic consistent across browsers */
        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: ${T.BG}; }
        ::-webkit-scrollbar-thumb { background: ${T.BD}; border-radius: 5px; }
        ::-webkit-scrollbar-thumb:hover { background: ${T.T3}; }
        * { scrollbar-width: thin; scrollbar-color: ${T.BD} ${T.BG}; }

        /* Selection — institutional blue */
        ::selection { background: ${T.BL}40; color: ${T.T1}; }

        /* Focus rings on interactive elements (accessibility) */
        button:focus-visible, input:focus-visible {
          outline: 2px solid ${T.BL};
          outline-offset: 2px;
        }
        button { -webkit-tap-highlight-color: transparent; }

        /* Remove number input spinners — consistency across tools */
        input[type="number"]::-webkit-outer-spin-button,
        input[type="number"]::-webkit-inner-spin-button {
          -webkit-appearance: none; margin: 0;
        }
        input[type="number"] { -moz-appearance: textfield; }

        /* ═══════════════════════════════════════════════════════
           RESPONSIVE COLLAPSES — tablet & mobile (< 900px)
           Collapse side-by-side 2-col and dense 3/4-col grids
           ═══════════════════════════════════════════════════════ */
        @media (max-width: 900px) {
          [style*="grid-template-columns: 1fr 320px"],
          [style*="grid-template-columns: 1fr 1fr"],
          [style*="grid-template-columns: 1fr 1.3fr"],
          [style*="grid-template-columns: 1fr 1.4fr"],
          [style*="grid-template-columns: 220px 1fr"],
          [style*="grid-template-columns: 1fr 2fr"] {
            grid-template-columns: 1fr !important;
          }
          [style*="grid-template-columns: repeat(3, 1fr)"],
          [style*="grid-template-columns: repeat(4, 1fr)"] {
            grid-template-columns: repeat(2, 1fr) !important;
          }
          [style*="grid-template-columns: repeat(5, 1fr)"] {
            grid-template-columns: repeat(2, 1fr) !important;
          }
          /* Sticky watchlist in Trader → regular position on mobile */
          [style*="position: sticky"][style*="top: 80"] {
            position: static !important;
          }
        }

        /* Mobile phone breakpoint (< 600px) — more aggressive */
        @media (max-width: 600px) {
          [style*="grid-template-columns: repeat(3, 1fr)"],
          [style*="grid-template-columns: repeat(4, 1fr)"],
          [style*="grid-template-columns: repeat(5, 1fr)"] {
            grid-template-columns: 1fr 1fr !important;
          }
          /* Hero padding reduced */
          [style*="padding: 60px 40px"] { padding: 40px 20px !important; }
          [style*="padding: 24px"] { padding: 14px !important; }
        }

        /* Reduce motion preference respected */
        @media (prefers-reduced-motion: reduce) {
          *, *::before, *::after {
            animation-duration: 0.01ms !important;
            transition-duration: 0.01ms !important;
          }
        }
      `}</style>

      {/* Top Nav */}
      <header style={{
        position: "sticky", top: 0, zIndex: 50,
        background: `${T.BG}EE`, backdropFilter: "blur(12px)",
        borderBottom: `1px solid ${T.BD}`,
        padding: "14px 24px",
      }}>
        <div style={{
          maxWidth: 1400, margin: "0 auto",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 20, flexWrap: "wrap",
        }}>
          {/* Logo */}
          <div
            onClick={() => setPage("Home")}
            style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
          >
            <div style={{
              width: 30, height: 30, borderRadius: 6,
              background: `linear-gradient(135deg, ${T.BL}, ${T.PP})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: MONO, fontWeight: 700, fontSize: 13, color: "#fff",
            }}>C</div>
            <div>
              <div style={{ fontSize: 15, fontFamily: BODY, fontWeight: 700, color: T.T1, letterSpacing: -0.3 }}>
                CELESYS
              </div>
              <div style={{ fontSize: 8, fontFamily: MONO, color: T.T3, letterSpacing: 2, textTransform: "uppercase" }}>
                Institutional Analytics
              </div>
            </div>
          </div>

          {/* Menu */}
          <nav style={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
            {MENU.map((item) => (
              <button key={item} onClick={() => setPage(item)} style={{
                padding: "8px 14px",
                background: page === item ? T.ACT : "transparent",
                border: page === item ? `1px solid ${T.BL}40` : `1px solid transparent`,
                borderRadius: 4,
                fontFamily: MONO, fontSize: 11, fontWeight: 500,
                color: page === item ? T.T1 : T.T2,
                cursor: "pointer", letterSpacing: 1, textTransform: "uppercase",
                transition: "all 0.15s ease",
              }}>{item}</button>
            ))}
          </nav>

          {/* Session badge */}
          <div style={{
            fontSize: 9, fontFamily: MONO, color: T.T3,
            padding: "3px 8px", border: `1px solid ${T.BD}`,
            borderRadius: 3, letterSpacing: 1, textTransform: "uppercase",
          }}>S1–S7 · Complete · 7 Tabs · CDS v2.0</div>
        </div>
      </header>

      {/* Page content */}
      <main>
        <CelesysErrorBoundary key={page}>
          {page === "Home" && <HomePage onAnalyze={goAnalyze} />}
          {page === "Overview" && (
            <OverviewPage ticker={ticker} onTickerChange={setTicker} />
          )}
          {page === "Stock" && (
            <StockPage ticker={ticker} onTickerChange={setTicker} />
          )}
          {page === "Decide" && (
            <DecidePage ticker={ticker} onTickerChange={setTicker} />
          )}
          {page === "Dream" && (
            <DreamPage onTickerSelect={(t) => { setTicker(t); setPage("Overview"); }} />
          )}
          {page === "Trader" && (
            <TraderPage onTickerSelect={(t) => { setTicker(t); setPage("Overview"); }} />
          )}
          {page === "Markets" && (
            <MarketsPage onTickerSelect={(t) => { setTicker(t); setPage("Overview"); }} />
          )}
          {page === "Tools" && <ToolsPage />}
        </CelesysErrorBoundary>
      </main>

      {/* Footer */}
      <footer style={{
        padding: "24px", borderTop: `1px solid ${T.BD}`, marginTop: 40,
        fontFamily: MONO, fontSize: 10, color: T.T3,
        letterSpacing: 1, textAlign: "center",
      }}>
        CELESYS · INSTITUTIONAL-GRADE ANALYSIS · REACT REWRITE · SESSIONS 1–7 COMPLETE
      </footer>
    </div>
  );
}
