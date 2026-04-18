/* ═══════════════════════════════════════════════════════════════════════════
 * CELESYS · ACTIVE TRADING
 * Institutional trading terminal mounted under Decide → Active Trading.
 *
 * Refresh cadences (no tick-level updates anywhere):
 *   - Top Trades panel:           90s soft-refresh
 *   - Quick Trade Header + Entry: 5m candle close (wall-clock aligned)
 *   - Quick Trade Option Chain:   90s + force-sync on 5m close
 *   - Quick Trade Risk Block:     90s + force-sync on 5m close
 *   - Voice Feedback:             event-driven
 *   - Secondary Scanner:          90s soft-refresh
 *
 * Data sources (reuses existing FastAPI endpoints, no backend changes):
 *   /api/bottom-nav-scan?region=IN   → Top Trades + Secondary Scanner
 *   /api/nse-options?symbol=X        → Option Chain (ATM ±2)
 * ═══════════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  // Loud startup log so we can verify the deployed version at a glance
  console.log('%c[ActiveTrading] v21 loaded — dark theme with MutationObserver enforcement',
              'color:#22C55E;font-weight:bold;font-size:13px');

  // ── COLOR TOKENS ────────────────────────────────────────────────────────
  var C = {
    bg: '#020617',
    card: '#0F172A',
    active: '#1E293B',
    divider: '#1E293B',
    textPri: '#E2E8F0',
    textSec: '#94A3B8',
    textMute: '#64748B',
    green: '#22C55E',
    yellow: '#F59E0B',
    orange: '#FB923C',
    red: '#EF4444',
    blue: '#3B82F6'
  };
  var MONO = '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace';

  var STATE_MAP = {
    early:   { color: C.green,  label: 'ENTER AGGRESSIVE' },
    ideal:   { color: C.blue,   label: 'ENTER NOW' },
    late:    { color: C.orange, label: 'ENTER SMALL' },
    avoid:   { color: C.red,    label: 'AVOID' }
  };

  var confColor = function (c) { return c >= 80 ? C.green : c >= 60 ? C.yellow : C.red; };

  // ── SCOPED CSS ──────────────────────────────────────────────────────────
  // The Celesys site has hard-override rules:
  //   [data-theme="dark"] .sc { background: #fff !important; ... }
  //   .sbody { padding: 16px 20px 18px; }
  // These force a white border around our dark terminal and add whitespace.
  //
  // Strategy: while Active Trading is mounted, we add `at-mode` class to
  // document.body. Scoped rules below activate ONLY when that class exists
  // AND ONLY for the .sc that contains #activeTradingMount (via :has selector
  // with fallback). When unmounted, the class is removed and every other tab
  // (Trader/Investor/Options) goes back to pristine white styling.
  function installScopedStyles() {
    if (document.getElementById('activeTradingScopedCSS')) return;
    var css = [
      // Terminal interior
      '#activeTradingMount,',
      '#activeTradingMount * {',
      '  box-sizing: border-box;',
      '}',
      '#activeTradingMount {',
      '  background: #020617 !important;',
      '  color: #E2E8F0 !important;',
      '  font-family: "Sora", "Inter", system-ui, sans-serif !important;',
      '}',
      '#activeTradingMount button,',
      '#activeTradingMount input,',
      '#activeTradingMount select {',
      '  font-family: inherit;',
      '}',
      // Every descendant div of the mount defaults to DARK background, not
      // transparent or inherited. This makes it impossible for site-wide
      // rules (e.g. [data-theme="dark"] .sc .sbody [style*=...]) to paint
      // any intermediate div white. The header and panels with their own
      // distinct colors opt out by carrying a stronger inline !important.
      '#activeTradingMount div {',
      '  background-color: #020617;',
      '}',

      // Parent overrides — ONLY active while body.at-mode is set
      // Uses :has() where supported (Chrome 105+, Safari 15.4+, Firefox 121+).
      // Fallback: mount-level data attributes on the ancestors (set by JS).
      'body.at-mode .sc:has(#activeTradingMount) {',
      '  background: #020617 !important;',
      '  border: 1px solid #1E293B !important;',
      '  border-left: 3px solid #0F172A !important;',
      '  box-shadow: none !important;',
      '  padding: 0 !important;',
      '}',
      'body.at-mode .sc:has(#activeTradingMount) .sbody {',
      '  background: #020617 !important;',
      '  padding: 0 !important;',
      '}',
      'body.at-mode .sc:has(#activeTradingMount) #deHeader,',
      'body.at-mode .sc:has(#activeTradingMount) .sh {',
      '  display: none !important;',
      '}',

      // Fallback for older browsers without :has() — JS sets [data-at-host="1"]
      'body.at-mode .sc[data-at-host="1"] {',
      '  background: #020617 !important;',
      '  border: 1px solid #1E293B !important;',
      '  border-left: 3px solid #0F172A !important;',
      '  box-shadow: none !important;',
      '  padding: 0 !important;',
      '}',
      'body.at-mode .sc[data-at-host="1"] .sbody {',
      '  background: #020617 !important;',
      '  padding: 0 !important;',
      '}',
      'body.at-mode .sc[data-at-host="1"] > .sh,',
      'body.at-mode .sc[data-at-host="1"] #deHeader {',
      '  display: none !important;',
      '}',

      // Price flash animations (5m CLOSE field)
      '@keyframes atPriceUp   { 0% { color: #22C55E; } 100% { color: #E2E8F0; } }',
      '@keyframes atPriceDown { 0% { color: #EF4444; } 100% { color: #E2E8F0; } }',
      '#activeTradingMount .at-flash-up { animation: atPriceUp .5s ease both; }',
      '#activeTradingMount .at-flash-dn { animation: atPriceDown .5s ease both; }',

      // Dark-theme scrollbars (Webkit + Firefox) — visible but subtle
      '#activeTradingMount ::-webkit-scrollbar { width: 8px; height: 8px; }',
      '#activeTradingMount ::-webkit-scrollbar-track { background: #020617; }',
      '#activeTradingMount ::-webkit-scrollbar-thumb { background: #1E293B; border-radius: 4px; }',
      '#activeTradingMount ::-webkit-scrollbar-thumb:hover { background: #334155; }',
      '#activeTradingMount { scrollbar-color: #1E293B #020617; scrollbar-width: thin; }',

      // Spec §8: Crossfade (opacity fade, 200-300ms, no slide/resize)
      // Applied to Tier 1 value containers (confidence, state pill, price).
      '@keyframes atCrossfade {',
      '  0%   { opacity: 0.3; }',
      '  100% { opacity: 1; }',
      '}',
      '#activeTradingMount .at-fade { animation: atCrossfade .25s ease both; }'
    ].join('\n');
    var s = document.createElement('style');
    s.id = 'activeTradingScopedCSS';
    s.textContent = css;
    document.head.appendChild(s);
  }

  // ── WALL-CLOCK 5m BOUNDARY ──────────────────────────────────────────────
  function nextFiveMinBoundary() {
    var d = new Date();
    d.setSeconds(0, 0);
    d.setMinutes(d.getMinutes() + (5 - (d.getMinutes() % 5)));
    return d;
  }
  function msUntilNextFiveMin() { return nextFiveMinBoundary().getTime() - Date.now(); }
  function formatCountdown(ms) {
    var total = Math.max(0, Math.floor(ms / 1000));
    var m = Math.floor(total / 60), s = total % 60;
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }

  function formatAgo(seconds) {
    // Spec §9: "Last Updated: 01:30 ago"
    if (seconds < 10) return 'just now';
    if (seconds < 60) return seconds + 's ago';
    var m = Math.floor(seconds / 60);
    var s = seconds % 60;
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s + ' ago';
  }

  // ── MODULE STATE ────────────────────────────────────────────────────────
  var state = {
    index: 'NIFTY',
    voiceOn: true,         // per spec requirement: ON by default
    alertsOn: true,
    region: 'IN',
    trades: [],
    scanner: [],
    selected: null,
    chain: [],
    lastClose: null,
    flash: null,
    countdown: formatCountdown(msUntilNextFiveMin()),
    logs: [],
    loaded: false,
    lastFetchMsg: '',
    lockedIds: {},         // { tradeId: firstSeenTimestamp } — for 3-min stability lock
    prevTradeIds: {},      // tracked across refreshes for voice triggers
    // v3 additions
    scoreHistory: {},      // { tradeId: [prev3, prev2, prev1] } — for trend display
    lastFullRefreshAt: 0,  // ms timestamp of last Tier 1 (5m close) update
    lastTier2RefreshAt: 0, // ms timestamp of last Tier 2 (90s) update
    gammaModeIds: {},      // { tradeId: true } trades currently in expiry-day gamma override
    gammaHistory: {},      // { tradeId: { triggeredAtClose: <priceAtTrigger>, referenceClose } } for kill-switch
    fadeTick: 0            // incremented on every 5m close; keyed into render to restart crossfade
  };

  var timers = { countdown: null, soft90: null, candle5m: null };
  var mounted = false;

  // ── DATA LAYER ──────────────────────────────────────────────────────────

  // ═══════════════════════════════════════════════════════════════════════
  // v3 CONFIDENCE SCORE ENGINE
  // Weighted composite: 0.25·Trend + 0.20·VWAP + 0.20·OI + 0.15·Vol + 0.10·Strike + 0.10·R:R
  // All factors normalized to 0-100, clamped [0,100] at end.
  // Computed ONLY at 5m candle close. Persisted for the full 5-min interval.
  // ═══════════════════════════════════════════════════════════════════════

  function scoreTrendStrength(row, side) {
    // Spec: last 3 × 5m candles.
    // No fake neutral: if we don't have ≥3 candles, return null → caller
    // excludes this trade from scoring rather than substituting 50.
    var bars = row.ohlc_bars || [];
    if (bars.length < 3) return null;
    var last3 = bars.slice(-3);
    // All 3 candles must have real close values
    for (var i = 0; i < 3; i++) {
      if (last3[i] == null || last3[i].c == null || last3[i].h == null || last3[i].l == null) {
        return null;
      }
    }
    var hh = 0, hc = 0, ll = 0, lc = 0;
    for (var j = 1; j < 3; j++) {
      if (last3[j].h > last3[j-1].h) hh++;
      if (last3[j].c > last3[j-1].c) hc++;
      if (last3[j].l < last3[j-1].l) ll++;
      if (last3[j].c < last3[j-1].c) lc++;
    }
    var bullSeq = hh + hc;
    var bearSeq = ll + lc;
    var raw = side === 'CE' ? bullSeq : bearSeq;
    var map = [30, 50, 65, 80, 95];
    return map[Math.max(0, Math.min(4, raw))];
  }

  function scoreVwapAlignment(row, side) {
    // Requires real spot + real VWAP. No substitution.
    // ATR computed from last 5 bars; must have ≥5 real bars with h/l values.
    var bars = row.ohlc_bars || [];
    var spot = row.spot;
    var vwap = row.vwap;
    if (spot == null || spot <= 0) return null;
    if (vwap == null || vwap <= 0) return null;
    if (bars.length < 5) return null;

    var sum = 0;
    for (var i = bars.length - 5; i < bars.length; i++) {
      if (bars[i] == null || bars[i].h == null || bars[i].l == null) return null;
      sum += (bars[i].h - bars[i].l);
    }
    var atr = sum / 5;
    if (atr <= 0) return null; // no real range = can't compute

    var dist = (spot - vwap) / atr;
    var signed = side === 'CE' ? dist : -dist;
    if (signed >= 1.5) return 95;
    if (signed >= 0.5) return 80;
    if (signed >= 0) return 65;
    if (signed >= -0.5) return 40;
    return 20;
  }

  function scoreOiStructure(row, side, isFallback) {
    // No fake neutral. If NSE is blocked (fallback mode) OR OI data genuinely
    // absent, return null so caller can exclude this trade from Top Trades.
    if (isFallback) return null;

    var ceBuildup = row.ce_buildup;
    var peBuildup = row.pe_buildup;
    // Both sides must have buildup arrays — else we have no OI view
    if (!Array.isArray(ceBuildup) || !Array.isArray(peBuildup)) return null;
    if (ceBuildup.length === 0 && peBuildup.length === 0) return null;

    var ceTopChg = ceBuildup[0] && ceBuildup[0].chg != null ? ceBuildup[0].chg : null;
    var peTopChg = peBuildup[0] && peBuildup[0].chg != null ? peBuildup[0].chg : null;
    // Need at least one real side
    if (ceTopChg == null && peTopChg == null) return null;
    // Treat missing side as 0 (flat), real zeros are valid signal
    ceTopChg = ceTopChg == null ? 0 : ceTopChg;
    peTopChg = peTopChg == null ? 0 : peTopChg;

    var pcr = row.pcr;

    function classify(chg) {
      if (chg > 50000) return 2;
      if (chg > 10000) return 1;
      if (chg < -10000) return -1;
      return 0;
    }
    var ceSignal = classify(ceTopChg);
    var peSignal = classify(peTopChg);

    if (side === 'CE') {
      if (ceSignal >= 1 && peSignal >= 2) return 95;
      if (ceSignal >= 1 && peSignal >= 1) return 82;
      if (peSignal >= 2) return 75;
      if (ceSignal >= 1 || peSignal >= 1) return 65;
      if (peSignal < 0) return 35;
      if (pcr != null && pcr >= 1.3) return 60;
      return 45;
    } else {
      if (peSignal >= 1 && ceSignal >= 2) return 95;
      if (peSignal >= 1 && ceSignal >= 1) return 82;
      if (ceSignal >= 2) return 75;
      if (peSignal >= 1 || ceSignal >= 1) return 65;
      if (ceSignal < 0) return 35;
      if (pcr != null && pcr <= 0.7) return 60;
      return 45;
    }
  }

  function scoreVolumeConfirmation(row) {
    // Requires ≥6 real bars (1 current + 5 prior) all with real volume.
    // No fake neutral — if any bar has v=0 or missing, return null (treat as
    // "no signal" and exclude from score).
    var bars = row.ohlc_bars;
    if (!Array.isArray(bars) || bars.length < 6) return null;
    var last = bars[bars.length - 1];
    if (last == null || last.v == null || last.v <= 0) return null;

    var prev5 = bars.slice(-6, -1);
    var sum = 0;
    for (var i = 0; i < 5; i++) {
      if (prev5[i] == null || prev5[i].v == null || prev5[i].v <= 0) return null;
      sum += prev5[i].v;
    }
    var avg = sum / 5;
    if (avg <= 0) return null;
    var ratio = last.v / avg;
    if (ratio >= 1.5) return 92;
    if (ratio >= 1.2) return 78;
    if (ratio >= 1.0) return 62;
    return 45;
  }

  function scoreStrikeQuality(atm, spot, strikeStep) {
    if (spot == null || spot <= 0 || atm == null || atm <= 0) return null;
    if (strikeStep == null || strikeStep <= 0) return null;
    var distance = Math.abs(atm - spot) / strikeStep;
    if (distance < 0.5) return 95;
    if (distance < 1.5) return 80;
    if (distance < 2.5) return 65;
    return 45;
  }

  function scoreRiskReward(target, sl, premium) {
    if (target == null || sl == null || premium == null) return null;
    if (premium <= 0 || target <= 0 || sl <= 0) return null;
    var reward = Math.abs(target - premium);
    var risk = Math.abs(premium - sl);
    if (risk <= 0) return null;
    var rr = reward / risk;
    if (rr >= 2.0) return 92;
    if (rr >= 1.5) return 78;
    if (rr >= 1.2) return 65;
    return 45;
  }

  // Detect side from price structure + OI before we compute the full score
  function detectSide(row) {
    var spot = row.spot || 0;
    var vwap = row.vwap || spot;
    var openPx = row.today_open || spot;
    var high = row.today_high || spot;
    var low = row.today_low || spot;
    var maxPain = row.max_pain || row.atm_strike || spot;
    var pcr = row.pcr || 1;
    var isFallback = row._fallback === true;

    var bullHints = 0, bearHints = 0;
    if (spot > vwap) bullHints += 2;
    if (spot < vwap) bearHints += 2;
    if (spot > openPx) bullHints += 1;
    if (spot < openPx) bearHints += 1;
    if (high > low) {
      var rp = (spot - low) / (high - low);
      if (rp > 0.6) bullHints += 1;
      if (rp < 0.4) bearHints += 1;
    }
    if (spot > maxPain) bullHints += 1;
    if (spot < maxPain) bearHints += 1;
    if (!isFallback) {
      if (pcr >= 1.2) bullHints += 1;
      if (pcr <= 0.8) bearHints += 1;
    }
    if (bullHints === bearHints) return null;
    return bullHints > bearHints ? 'CE' : 'PE';
  }

  // ═══════════════════════════════════════════════════════════════════════
  // §13 FALSE BREAKOUT FILTER — evaluated at 5m close
  // Returns { triggered: bool, penalty: 15-25, downgrade: bool }
  // ═══════════════════════════════════════════════════════════════════════
  function checkFalseBreakout(row, side, isFallback) {
    if (isFallback) return { triggered: false, penalty: 0 };
    var spot = row.spot || 0, vwap = row.vwap || spot;
    var ceBuildup = row.ce_buildup || [];
    var peBuildup = row.pe_buildup || [];
    var ceChg = ceBuildup[0] ? (ceBuildup[0].chg || 0) : 0;
    var peChg = peBuildup[0] ? (peBuildup[0].chg || 0) : 0;

    if (side === 'CE') {
      // Bullish breakout: price ABOVE VWAP + CE OI↓ (or flat) + PE OI↑ = DIVERGENCE
      var aboveVwap = spot > vwap;
      var ceDivergent = ceChg <= 0;
      var peDivergent = peChg > 20000;
      if (aboveVwap && (ceDivergent || peDivergent)) {
        var severity = (ceDivergent ? 1 : 0) + (peDivergent ? 1 : 0);
        return { triggered: true, penalty: severity === 2 ? 25 : 15 };
      }
    } else {
      var belowVwap = spot < vwap;
      var peDivergentBear = peChg <= 0;
      var ceDivergentBear = ceChg > 20000;
      if (belowVwap && (peDivergentBear || ceDivergentBear)) {
        var severityB = (peDivergentBear ? 1 : 0) + (ceDivergentBear ? 1 : 0);
        return { triggered: true, penalty: severityB === 2 ? 25 : 15 };
      }
    }
    return { triggered: false, penalty: 0 };
  }

  function downgradeState(stateKey) {
    // §13 spec table: Early→Late, Ideal→Late, Late→Avoid
    if (stateKey === 'early' || stateKey === 'ideal') return 'late';
    if (stateKey === 'late') return 'avoid';
    return stateKey;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // §12 EXPIRY-DAY GAMMA OVERRIDE
  // ═══════════════════════════════════════════════════════════════════════
  function isSameDayExpiry(row) {
    var exp = row.expiry;
    if (!exp) return false;
    try {
      // NSE format: "18-Apr-2026" or similar
      var d = new Date(exp);
      if (isNaN(d)) {
        // try "DD-MMM-YYYY"
        var parts = String(exp).split('-');
        if (parts.length === 3) {
          d = new Date(parts[1] + ' ' + parts[0] + ' ' + parts[2]);
        }
      }
      if (isNaN(d)) return false;
      var today = new Date();
      return d.getDate() === today.getDate() &&
             d.getMonth() === today.getMonth() &&
             d.getFullYear() === today.getFullYear();
    } catch (e) { return false; }
  }

  function isInGammaTimeWindow(region) {
    var now = new Date();
    if (region === 'IN') {
      // IST 11:30+
      var istMs = now.getTime() + (5.5 * 60 * 60 * 1000) + (now.getTimezoneOffset() * 60 * 1000);
      var ist = new Date(istMs);
      var mm = ist.getUTCHours() * 60 + ist.getUTCMinutes();
      return mm >= (11 * 60 + 30) && mm <= (15 * 60 + 30);
    } else {
      // ET 12:00+ (approx via UTC)
      var hh = now.getUTCHours();
      var mm2 = hh * 60 + now.getUTCMinutes();
      return mm2 >= (16 * 60) && mm2 <= (20 * 60); // 12pm-4pm ET approx
    }
  }

  function checkGammaOverride(row, side, region, isFallback) {
    if (isFallback) return { triggered: false };
    if (!isSameDayExpiry(row)) return { triggered: false };
    if (!isInGammaTimeWindow(region)) return { triggered: false };

    var spot = row.spot || 0;
    var atm = row.atm_strike || spot;
    var bars = row.ohlc_bars || [];
    if (bars.length < 5) return { triggered: false };
    var last = bars[bars.length - 1];

    // (a) Candle body ≥ 1.2× ATR — spec §12 "Large candle body"
    var ranges = bars.slice(-5).map(function (b) { return b.h - b.l; });
    var atr = ranges.reduce(function (a, b) { return a + b; }, 0) / ranges.length;
    var body = Math.abs(last.c - last.o);
    var bigBody = atr > 0 && body >= atr * 1.2;

    // (b) Strong close — spec §12 "top/bottom 25% of range"
    var range = last.h - last.l;
    var closePos = range > 0 ? (last.c - last.l) / range : 0.5;
    var strongClose = side === 'CE' ? closePos >= 0.75 : closePos <= 0.25;

    // (c) Break key strike ATM±1 — spec §12
    var stepApprox = spot * 0.005;
    var brokenStrike = side === 'CE'
      ? spot > atm + stepApprox * 0.5
      : spot < atm - stepApprox * 0.5;

    // (d) OI spike >1.5× AVG of chain — spec §12 strict
    // Compute chain-wide average of absolute OI change (all strikes, both sides)
    var chain = row.chain_near_atm || [];
    var chgSum = 0, chgCount = 0;
    chain.forEach(function (r) {
      if (r.ce_chg != null) { chgSum += Math.abs(r.ce_chg); chgCount++; }
      if (r.pe_chg != null) { chgSum += Math.abs(r.pe_chg); chgCount++; }
    });
    var chainAvgChg = chgCount > 0 ? chgSum / chgCount : 0;

    // Focus strike: the side-appropriate top-buildup strike
    var bld = side === 'CE' ? (row.pe_buildup || []) : (row.ce_buildup || []);
    var focusChg = bld[0] ? Math.abs(bld[0].chg || 0) : 0;
    var oiSpike = chainAvgChg > 0
      ? focusChg > chainAvgChg * 1.5
      : focusChg > 50000; // fallback to absolute threshold if chain data missing

    // (e) ATM straddle concentration — spec §12 "ATM straddle OI concentration"
    // Check if ATM strike's CE+PE OI dominate the near-ATM chain.
    var atmRow = chain.filter(function (r) { return r.strike === atm; })[0];
    var atmStraddleConcentrated = false;
    if (atmRow && chain.length >= 3) {
      var atmOi = (atmRow.ce_oi || 0) + (atmRow.pe_oi || 0);
      var totalOi = chain.reduce(function (s, r) {
        return s + (r.ce_oi || 0) + (r.pe_oi || 0);
      }, 0);
      // ATM straddle is >30% of near-ATM chain = gamma pin zone
      if (totalOi > 0 && atmOi / totalOi > 0.30) atmStraddleConcentrated = true;
    }

    // Spec §12 trigger: ALL of (breaks strike, OI spike, strong close)
    // PLUS signal inputs: (big body, ATM straddle concentration)
    // Require all 4 hard conditions; straddle concentration is a boost hint.
    if (bigBody && strongClose && brokenStrike && oiSpike) {
      // Boost size scales with straddle concentration (stronger pin = bigger boost)
      var boost = atmStraddleConcentrated ? 18 : 14;
      return {
        triggered: true,
        boost: boost,
        atmStraddleConcentrated: atmStraddleConcentrated
      };
    }
    return { triggered: false };
  }

  function promoteStateForGamma(stateKey) {
    // §12 spec table
    if (stateKey === 'early') return 'ideal'; // Aggressive
    if (stateKey === 'ideal') return 'ideal'; // Strong Entry (still ideal pill)
    if (stateKey === 'late') return 'early';  // Still Valid (promoted to early)
    return stateKey;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // MAIN: build a trade object from one ticker row
  // ═══════════════════════════════════════════════════════════════════════
  function mapScanRowToTrade(row) {
    var sym = row.sym || row.symbol || '';
    var spot = row.spot;

    // HARD REQUIREMENT: real symbol + real spot. No substitutes.
    if (!sym) return null;
    if (spot == null || spot <= 0) return null;

    var isFallback = row._fallback === true;

    // HARD REQUIREMENT: real ATM strike. No rounding spot to invent one.
    var atm = row.atm_strike;
    if (atm == null || atm <= 0) return null;

    // Real strike step — no default by spot * 0.005 heuristic
    var stepMap = { NIFTY: 50, BANKNIFTY: 100, FINNIFTY: 50, MIDCPNIFTY: 25, SENSEX: 100 };
    var strikeStep = stepMap[sym];
    // For non-index symbols, derive from chain_near_atm (two adjacent strikes)
    if (strikeStep == null && Array.isArray(row.chain_near_atm) && row.chain_near_atm.length >= 2) {
      var strikes = row.chain_near_atm.map(function (r) { return r.strike; }).sort(function(a,b){return a-b;});
      strikeStep = strikes[1] - strikes[0];
    }
    if (strikeStep == null || strikeStep <= 0) return null;

    // Step 1: determine side (requires real price structure)
    var side = detectSide(row);
    if (!side) return null;

    // Step 2: real premium from embedded chain. NO fabrication.
    var chain = Array.isArray(row.chain_near_atm) ? row.chain_near_atm : [];
    if (chain.length === 0) return null; // no chain = can't trade

    var atmRow = chain.filter(function (r) { return r.strike === atm; })[0];
    if (!atmRow) {
      // ATM strike not found in chain — take closest but only if within 1 step
      atmRow = chain.reduce(function (best, r) {
        return (!best || Math.abs(r.strike - atm) < Math.abs(best.strike - atm)) ? r : best;
      }, null);
      if (!atmRow || Math.abs(atmRow.strike - atm) > strikeStep) return null;
    }
    var premium = side === 'CE' ? atmRow.ce_ltp : atmRow.pe_ltp;
    if (premium == null || premium <= 0) return null; // no real price = no trade

    // Step 3: SL/Target/trigger (these are DERIVED from real premium, not fake)
    // A 15% SL and 30% target are risk policy choices applied to real premium
    // — not substitutions for missing data. That's legitimate.
    var sl = premium * 0.85;
    var target = premium * 1.30;
    var trigger = premium * 1.02;

    // Step 4: six factor scores. Each returns null if data absent.
    // We do NOT substitute null with 50.
    var f = {
      trend:  scoreTrendStrength(row, side),
      vwap:   scoreVwapAlignment(row, side),
      oi:     scoreOiStructure(row, side, isFallback),
      vol:    scoreVolumeConfirmation(row),
      strike: scoreStrikeQuality(atm, spot, strikeStep),
      rr:     scoreRiskReward(target, sl, premium)
    };

    // Track which factors are real vs missing
    var availableFactors = [];
    var missingFactors = [];
    var weights = { trend: 0.25, vwap: 0.20, oi: 0.20, vol: 0.15, strike: 0.10, rr: 0.10 };
    for (var key in weights) {
      if (f[key] == null) missingFactors.push(key);
      else availableFactors.push(key);
    }

    // REQUIRE: at least the structural factors (trend + vwap + strike + rr)
    // These 4 provide 65% of the weight and don't depend on NSE OI/volume.
    // If any of them is missing we genuinely cannot evaluate this trade.
    var structuralRequired = ['trend', 'vwap', 'strike', 'rr'];
    for (var si = 0; si < structuralRequired.length; si++) {
      if (f[structuralRequired[si]] == null) return null;
    }

    // Step 5: weighted composite. Renormalize weights so missing factors
    // don't silently pull the score toward zero. Only real signals count.
    var numerator = 0, denom = 0;
    for (var k in weights) {
      if (f[k] != null) {
        numerator += weights[k] * f[k];
        denom += weights[k];
      }
    }
    var baseScore = denom > 0 ? (numerator / denom) : 0;

    // Step 6: False Breakout Filter
    var fb = checkFalseBreakout(row, side, isFallback);
    var postFilterScore = baseScore - fb.penalty;

    var stateKey = postFilterScore >= 80 ? 'ideal'
                 : postFilterScore >= 68 ? 'early'
                 : postFilterScore >= 60 ? 'late'
                 : 'avoid';

    if (fb.triggered) stateKey = downgradeState(stateKey);

    // Step 7: Gamma Override
    var gamma = checkGammaOverride(row, side, state.region, isFallback);
    var gammaMode = false;
    var finalScore = postFilterScore;

    var id = sym + '-' + atm + '-' + side;
    var gammaHist = state.gammaHistory && state.gammaHistory[id];
    var killed = false;
    if (gammaHist) {
      var bars = row.ohlc_bars || [];
      if (bars.length >= 2) {
        var last = bars[bars.length - 1];
        var move = last.c - gammaHist.referenceOpen;
        var prevMove = gammaHist.triggeredAtClose - gammaHist.referenceOpen;
        if (prevMove !== 0) {
          var reversalPct = -move / prevMove;
          if (reversalPct > 0.5) killed = true;
        }
      }
      var bld = side === 'CE' ? (row.pe_buildup || []) : (row.ce_buildup || []);
      var prevBldChg = gammaHist.referenceBuildupChg || 0;
      var curBldChg = bld[0] ? (bld[0].chg || 0) : 0;
      if (prevBldChg > 0 && curBldChg < prevBldChg * 0.3) killed = true;
    }

    if (gamma.triggered && !killed) {
      finalScore += gamma.boost;
      stateKey = promoteStateForGamma(stateKey);
      target = premium * 1.30 * 1.3;
      gammaMode = true;
    }

    // Clamp
    finalScore = Math.max(0, Math.min(100, Math.round(finalScore)));
    if (finalScore < 55) return null; // too weak

    // Build reason string (institutional vocabulary). Skip any factor that's
    // null — we don't want to claim "VWAP reclaim" when VWAP data is missing.
    var reasons = [];
    if (side === 'CE') {
      if (f.vwap != null && f.vwap >= 80) reasons.push('VWAP reclaim');
      else if (f.vwap != null && f.vwap >= 65) reasons.push('VWAP hold');
      if (f.oi != null && f.oi >= 72) reasons.push('Put writing');
      if (f.trend != null && f.trend >= 80) reasons.push('3-candle bullish');
      if (f.vol != null && f.vol >= 78) reasons.push('Volume surge');
      if (gammaMode) reasons.push('Gamma break');
      if (fb.triggered) reasons.push('Weak OI confirm');
    } else {
      if (f.vwap != null && f.vwap >= 80) reasons.push('VWAP breakdown');
      else if (f.vwap != null && f.vwap >= 65) reasons.push('Below VWAP');
      if (f.oi != null && f.oi >= 72) reasons.push('Call writing');
      if (f.trend != null && f.trend >= 80) reasons.push('3-candle bearish');
      if (f.vol != null && f.vol >= 78) reasons.push('Volume surge');
      if (gammaMode) reasons.push('Gamma break');
      if (fb.triggered) reasons.push('Weak OI confirm');
    }
    if (reasons.length === 0) {
      reasons.push(side === 'CE' ? 'Bullish structure' : 'Bearish structure');
    }
    var reason = reasons.slice(0, 3).join(' + ');

    // Lot size: prefer real value from backend. For known indices use the
    // officially-published lot sizes. If backend didn't send one and it's an
    // unknown stock, return null rather than inventing 50.
    var lotMap = { NIFTY: 75, BANKNIFTY: 30, FINNIFTY: 65, MIDCPNIFTY: 120, SENSEX: 20 };
    var lot = row.lot_size;
    if (lot == null && lotMap[sym] != null) lot = lotMap[sym];
    // else lot stays null — UI will display "—"

    return {
      id: id,
      symbol: sym,
      strike: atm + ' ' + side,
      side: side,
      confidence: finalScore,
      state: stateKey,
      reason: reason,
      price: premium,
      trigger: trigger,
      sl: sl,
      target: target,
      lot: lot,
      gammaMode: gammaMode,
      falseBreakout: fb.triggered,
      factors: f,
      availableFactors: availableFactors,
      missingFactors: missingFactors,
      _raw: row
    };
  }

  function fetchOptionChain(symbol, strikeStr, selectedTrade) {
    // EMBED-ONLY: use chain_near_atm that already arrived with bottom-nav-scan.
    // We never call /api/nse-options per-stock — that would risk rate-limiting.
    // If the embedded chain is missing (backend didn't attach one for this
    // ticker), we return empty rows and the UI shows "—" placeholders.
    var atmStrike = parseFloat((strikeStr || '').replace(/[^\d.]/g, '')) || 0;

    if (selectedTrade && selectedTrade._raw && selectedTrade._raw.chain_near_atm) {
      var embedded = selectedTrade._raw.chain_near_atm;
      if (embedded.length > 0) {
        return Promise.resolve(
          buildChainRows(embedded, atmStrike, selectedTrade._raw.atm_strike)
        );
      }
    }
    return Promise.resolve([]);
  }

  function buildChainRows(chain, atmStrike, apiAtmStrike) {
    var strikes = chain.map(function (r) { return r.strike; }).sort(function (a, b) { return a - b; });
    if (atmStrike === 0) atmStrike = apiAtmStrike || strikes[Math.floor(strikes.length / 2)];

    // Find ATM index
    var atmIdx = 0, minDiff = Infinity;
    for (var i = 0; i < strikes.length; i++) {
      var diff = Math.abs(strikes[i] - atmStrike);
      if (diff < minDiff) { minDiff = diff; atmIdx = i; }
    }

    var lookup = {};
    chain.forEach(function (c) { lookup[c.strike] = c; });

    var rows = [];
    for (var k = atmIdx - 2; k <= atmIdx + 2; k++) {
      if (k < 0 || k >= strikes.length) continue;
      var st = strikes[k];
      var oi = lookup[st] || {};
      rows.push({
        strike: st,
        callOi: Math.round(oi.ce_chg || 0),
        putOi: Math.round(oi.pe_chg || 0),
        volSpike: Math.abs(oi.ce_chg || 0) > 50000 || Math.abs(oi.pe_chg || 0) > 50000,
        isAtm: k === atmIdx
      });
    }
    while (rows.length < 5) rows.push({ strike: 0, callOi: 0, putOi: 0, volSpike: false, isAtm: false });
    return rows;
  }

  // ── DOM HELPERS ─────────────────────────────────────────────────────────
  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) {
        if (k === 'style' && typeof attrs[k] === 'object') {
          for (var sk in attrs[k]) e.style[sk] = attrs[k][sk];
        } else if (k === 'onClick') {
          e.addEventListener('click', attrs[k]);
        } else if (k === 'className') {
          e.className = attrs[k];
        } else {
          e.setAttribute(k, attrs[k]);
        }
      }
    }
    if (children) {
      if (!Array.isArray(children)) children = [children];
      children.forEach(function (c) {
        if (c === null || c === undefined || c === false) return;
        e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
      });
    }
    return e;
  }

  function pill(stateKey, compact) {
    var m = STATE_MAP[stateKey] || STATE_MAP.ideal;
    return el('span', {
      style: {
        fontSize: (compact ? 12 : 12) + 'px', // spec §4.3: state pill is 12px
        fontWeight: 700,
        padding: compact ? '3px 8px' : '3px 8px',
        borderRadius: '999px',
        background: m.color + '22',
        color: m.color,
        border: '1px solid ' + m.color + '55',
        letterSpacing: '0.3px',
        lineHeight: 1,
        whiteSpace: 'nowrap',
        display: 'inline-block'
      }
    }, m.label);
  }

  // ── RENDER ──────────────────────────────────────────────────────────────
  function render(root) {
    root.innerHTML = '';

    // Terminal wrapper — fixed institutional terminal, dark
    var wrap = el('div', {
      style: {
        width: '100%',
        height: '880px',
        background: C.bg,
        color: C.textPri,
        fontFamily: '"Sora", system-ui, sans-serif',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        borderRadius: '8px',
        border: '1px solid ' + C.divider
      }
    });

    wrap.appendChild(renderHeader());

    var body = el('div', {
      style: {
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '65% 35%',
        minHeight: 0,
        background: C.bg  // explicit — parent inheritance isn't reliable
      }
    });
    body.appendChild(renderTopTrades());
    body.appendChild(renderQuickTrade());
    wrap.appendChild(body);

    wrap.appendChild(renderScanner());
    root.appendChild(wrap);
  }

  function isIndianMarketOpen() {
    // IST = UTC+5:30. NSE open 09:15–15:30 IST, Mon–Fri
    var now = new Date();
    var istMs = now.getTime() + (5.5 * 60 * 60 * 1000) + (now.getTimezoneOffset() * 60 * 1000);
    var ist = new Date(istMs);
    var day = ist.getUTCDay(); // Sun=0, Sat=6
    if (day === 0 || day === 6) return false;
    var hours = ist.getUTCHours();
    var mins = ist.getUTCMinutes();
    var mm = hours * 60 + mins;
    return mm >= (9 * 60 + 15) && mm <= (15 * 60 + 30);
  }

  function renderHeader() {
    // Contextual index list based on region
    var indexList = state.region === 'US'
      ? ['SPY', 'QQQ', 'IWM']
      : ['NIFTY', 'BANKNIFTY', 'SENSEX'];

    // Reset to first index when region changes if current isn't in list
    if (indexList.indexOf(state.index) === -1) {
      state.index = indexList[0];
    }

    var indexBtns = indexList.map(function (ix) {
      var active = state.index === ix;
      return el('button', {
        onClick: function () { state.index = ix; rerender(); refreshAll(); },
        style: {
          fontSize: '11px', fontWeight: 700, padding: '4px 10px',
          border: '1px solid ' + (active ? C.blue : C.divider),
          background: active ? C.blue + '22' : 'transparent',
          color: active ? C.blue : C.textSec,
          borderRadius: '4px', cursor: 'pointer', letterSpacing: '0.3px'
        }
      }, ix);
    });

    var regionBtn = function (reg, label) {
      var active = state.region === reg;
      var src = reg === 'IN' ? 'NSE direct (yfinance fallback)' : 'yfinance primary';
      return el('button', {
        onClick: function () {
          if (state.region === reg) return;
          state.region = reg;
          state.trades = []; state.scanner = []; state.selected = null;
          state.chain = []; state.lockedIds = {}; state.prevTradeIds = {};
          state.loaded = false; state.lastFetchMsg = '';
          rerender(); refreshAll();
        },
        title: 'Data source: ' + src,
        style: {
          fontSize: '10px', fontWeight: 800, padding: '3px 8px',
          border: '1px solid ' + (active ? C.green : C.divider),
          background: active ? C.green + '22' : 'transparent',
          color: active ? C.green : C.textSec,
          borderRadius: '4px', cursor: 'pointer', letterSpacing: '0.5px',
          fontFamily: MONO
        }
      }, label);
    };

    var isLive = state.region === 'IN' ? isIndianMarketOpen() : isUSMarketOpen();
    var marketBadge = el('span', {
      style: {
        fontSize: '9px', fontWeight: 800, padding: '2px 6px', borderRadius: '4px',
        background: isLive ? C.green + '22' : C.textMute + '22',
        color: isLive ? C.green : C.textMute,
        border: '1px solid ' + (isLive ? C.green + '55' : C.textMute + '55'),
        letterSpacing: '0.5px', marginLeft: '8px'
      }
    }, isLive ? '● LIVE' : '● CLOSED');

    return el('div', {
      style: {
        height: '36px', background: C.card, borderBottom: '1px solid ' + C.divider,
        display: 'flex', alignItems: 'center', padding: '0 12px', gap: '12px', flexShrink: 0,
        position: 'sticky', top: 0, zIndex: 10  // spec §3: sticky (always visible)
      }
    }, [
      // LEFT: app name + market badge
      el('div', {
        style: {
          fontSize: '13px', fontWeight: 800, color: C.textPri, letterSpacing: '0.5px',
          fontFamily: MONO, display: 'flex', alignItems: 'center'
        }
      }, ['CELESYS · ACTIVE TRADING', marketBadge]),

      // CENTER: region toggle + index selector
      el('div', {
        style: { flex: 1, display: 'flex', justifyContent: 'center', gap: '8px', alignItems: 'center' }
      }, [
        el('div', { style: { display: 'flex', gap: '2px', padding: '2px', background: C.bg, borderRadius: '5px' } }, [
          regionBtn('IN', 'IN'),
          regionBtn('US', 'US')
        ]),
        el('div', { style: { width: '1px', height: '16px', background: C.divider } }),
        el('div', { style: { display: 'flex', gap: '4px' } }, indexBtns)
      ]),

      // RIGHT: alerts + voice + user profile
      el('div', { style: { display: 'flex', alignItems: 'center', gap: '8px' } }, [
        iconBtn('🔔', state.alertsOn, function () { state.alertsOn = !state.alertsOn; rerender(); }),
        iconBtn('🎙', state.voiceOn, function () { state.voiceOn = !state.voiceOn; rerender(); }),
        el('div', {
          title: 'Profile',
          style: {
            width: '24px', height: '24px', borderRadius: '50%',
            background: 'linear-gradient(135deg, #1A3A78, #3B82F6)',
            color: '#fff',
            border: '1px solid ' + C.divider,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '10px', fontWeight: 800, cursor: 'pointer',
            fontFamily: MONO, letterSpacing: '0.3px'
          }
        }, 'V')
      ])
    ]);
  }

  function isUSMarketOpen() {
    // US equities: Mon–Fri 09:30–16:00 ET. Approximate via UTC
    var now = new Date();
    var day = now.getUTCDay();
    if (day === 0 || day === 6) return false;
    // ET = UTC-5 (EST) or UTC-4 (EDT). Use a rough window that covers both
    var hours = now.getUTCHours();
    var mins = now.getUTCMinutes();
    var mm = hours * 60 + mins;
    return mm >= (13 * 60 + 30) && mm <= (20 * 60 + 0);
  }

  function iconBtn(icon, on, handler) {
    return el('button', {
      onClick: handler,
      style: {
        width: '24px', height: '24px',
        border: '1px solid ' + (on ? C.green : C.divider),
        background: on ? C.green + '22' : 'transparent',
        color: on ? C.green : C.textSec,
        borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0
      }
    }, icon);
  }

  function renderTopTrades() {
    var panel = el('div', {
      style: {
        padding: '8px', height: '100%', overflow: 'hidden',
        background: C.bg  // explicit — don't rely on inheritance
      }
    });
    panel.appendChild(el('div', {
      style: {
        fontSize: '10px', fontWeight: 800, color: C.textMute,
        letterSpacing: '1.5px', marginBottom: '6px', padding: '0 2px'
      }
    }, 'TOP TRADES · 5M CLOSE'));

    for (var i = 0; i < 3; i++) {
      var t = state.trades[i];
      if (!t) {
        // Spec §4 rules: if <3 trades → "No high-confidence trades"
        // Before first fetch completes: "Loading…"
        // If fetch failed: show error detail
        var placeholderText;
        if (!state.loaded) {
          placeholderText = 'Loading…';
        } else if (state.lastFetchMsg) {
          placeholderText = state.lastFetchMsg;
        } else {
          placeholderText = 'No high-confidence trades';
        }
        panel.appendChild(el('div', {
          style: {
            height: '96px', marginBottom: '6px', borderRadius: '12px',
            border: '1px dashed ' + C.divider, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            color: C.textMute, fontSize: '12px', fontStyle: 'italic',
            padding: '0 12px', textAlign: 'center', lineHeight: 1.3
          }
        }, placeholderText));
      } else {
        panel.appendChild(tradeCard(t));
      }
    }
    return panel;
  }

  function tradeCard(trade) {
    var isSelected = state.selected && state.selected.id === trade.id;
    var history = state.scoreHistory[trade.id] || [];

    var card = el('div', {
      onClick: function () { selectTrade(trade); },
      style: {
        height: '96px', padding: '8px',  // bumped from 84 to fit trend row
        background: isSelected ? C.active : C.card,
        borderRadius: '12px',
        border: '1px solid ' + (isSelected ? C.blue : (trade.gammaMode ? '#F59E0B' : C.divider)),
        marginBottom: '6px',
        display: 'grid',
        gridTemplateColumns: '1fr auto auto',
        gridTemplateRows: 'auto auto auto',
        columnGap: '12px', rowGap: '3px',
        cursor: 'pointer',
        transition: 'background 120ms ease, border-color 120ms ease',
        position: 'relative'
      }
    });

    // GAMMA MODE badge (top-right absolute) — spec §12
    if (trade.gammaMode) {
      card.appendChild(el('div', {
        style: {
          position: 'absolute', top: '4px', right: '4px',
          fontSize: '9px', fontWeight: 800, padding: '2px 6px',
          borderRadius: '3px', background: 'linear-gradient(90deg, #F59E0B, #FB923C)',
          color: '#1A1400', letterSpacing: '0.5px',
          boxShadow: '0 0 0 1px #F59E0B88'
        }
      }, '⚡ GAMMA MODE'));
    }

    // Row 1 col 1 — symbol + strike
    var sym = el('div', {
      style: { fontSize: '18px', fontWeight: 600, color: C.textPri, lineHeight: 1.15, fontFamily: MONO }
    });
    sym.appendChild(document.createTextNode(trade.symbol + ' '));
    sym.appendChild(el('span', { style: { color: C.textSec } }, trade.strike));
    card.appendChild(sym);

    // Row 1 col 2 — confidence (crossfade on 5m close, spec §8)
    card.appendChild(el('div', {
      className: 'at-fade at-fade-' + (state.fadeTick || 0),
      style: {
        fontSize: '20px', fontWeight: 700, color: confColor(trade.confidence),
        lineHeight: 1.1, alignSelf: 'center', fontFamily: MONO,
        minWidth: '54px', textAlign: 'right'  // reserve for "100%" max-width
      }
    }, trade.confidence + '%'));

    // Row 1 col 3 — EXECUTE (spec §4.5: 36 × 100 green gradient)
    card.appendChild(el('button', {
      onClick: function (e) { e.stopPropagation(); onExecute(trade); },
      style: {
        height: '36px', width: '100px',
        background: 'linear-gradient(180deg, ' + C.green + ', #16A34A)',
        color: '#062B17', fontWeight: 800, fontSize: '11px',
        border: 'none', borderRadius: '6px', cursor: 'pointer',
        letterSpacing: '0.8px', alignSelf: 'center',
        boxShadow: '0 0 0 1px ' + C.green + '66, 0 4px 12px ' + C.green + '33'
      }
    }, 'EXECUTE'));

    // Row 2 col 1 — reason
    card.appendChild(el('div', {
      style: {
        fontSize: '13px', color: C.textSec, lineHeight: 1.2,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
      }
    }, trade.reason));

    // Row 2 col 2 — state pill
    card.appendChild(el('div', { style: { alignSelf: 'center' } }, pill(trade.state, true)));

    // Row 2 col 3 — voice mic
    card.appendChild(el('button', {
      onClick: function (e) { e.stopPropagation(); onVoice(trade); },
      title: 'Speak trade',
      style: {
        width: '32px', height: '24px',
        border: '1px solid ' + C.divider, background: 'transparent',
        color: C.textSec, borderRadius: '4px', cursor: 'pointer',
        fontSize: '12px', alignSelf: 'center', padding: 0
      }
    }, '🎙'));

    // Row 3 col 1 — score trend (spec §5: "78 → 82 → 85" green if rising, red if falling)
    var trendRow = el('div', {
      style: {
        fontSize: '11px', color: C.textMute, fontFamily: MONO,
        display: 'flex', alignItems: 'center', gap: '8px', lineHeight: 1,
        overflow: 'hidden', whiteSpace: 'nowrap'
      }
    });
    if (history.length >= 2) {
      var first = history[0], last = history[history.length - 1];
      var trendColor = last > first ? C.green : last < first ? C.red : C.textMute;
      trendRow.appendChild(el('span', {}, 'Score: '));
      trendRow.appendChild(el('span', { style: { color: trendColor, fontWeight: 600 } },
        history.join(' → ')));
    } else {
      trendRow.appendChild(el('span', { style: { color: C.textMute } },
        'Score: ' + trade.confidence + ' (building history…)'));
    }

    // Transparency: show which factors contributed vs were unavailable
    // e.g. "OI+Vol unavailable" — makes "no fake data" visible to user
    if (trade.missingFactors && trade.missingFactors.length > 0) {
      var short = { oi: 'OI', vol: 'Vol', trend: 'Trend', vwap: 'VWAP', strike: 'Strike', rr: 'R:R' };
      var labels = trade.missingFactors.map(function (k) { return short[k] || k; });
      trendRow.appendChild(el('span', {
        title: 'These factors had no real data and were excluded from scoring',
        style: {
          color: C.textMute, fontSize: '10px', fontWeight: 600,
          marginLeft: '8px', letterSpacing: '0.2px',
          border: '1px solid ' + C.divider, padding: '1px 5px', borderRadius: '3px'
        }
      }, labels.join('+') + ' unavailable'));
    }

    // False-breakout warning (spec §13)
    if (trade.falseBreakout) {
      trendRow.appendChild(el('span', {
        style: {
          color: C.orange, fontSize: '10px', fontWeight: 700,
          marginLeft: 'auto', letterSpacing: '0.3px'
        }
      }, '⚠ Weak OI confirmation'));
    }
    card.appendChild(trendRow);
    // Row 3 cols 2-3 reserved (empty) so grid stays consistent
    card.appendChild(el('div', {}));
    card.appendChild(el('div', {}));

    return card;
  }

  function renderQuickTrade() {
    var panel = el('div', {
      style: {
        background: C.bg, borderLeft: '1px solid ' + C.divider,
        height: '100%', display: 'flex', flexDirection: 'column',
        opacity: state.selected ? 1 : 0.4,
        transition: 'opacity 200ms ease'
      }
    });

    panel.appendChild(renderSelectedHeader());
    panel.appendChild(renderEntryEngine());
    panel.appendChild(renderOptionChain());
    panel.appendChild(renderRiskBlock());
    panel.appendChild(renderVoiceLog());
    return panel;
  }

  function renderSelectedHeader() {
    if (!state.selected) {
      return el('div', {
        style: {
          height: '52px', padding: '8px', background: C.card,
          borderBottom: '1px solid ' + C.divider,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: C.textMute, fontSize: '13px', fontStyle: 'italic'
        }
      }, 'Select a trade above');
    }

    var t = state.selected;
    var hdr = el('div', {
      style: {
        height: '52px', padding: '6px 8px', background: C.card,
        borderBottom: '1px solid ' + C.divider,
        display: 'grid', gridTemplateColumns: '1fr auto auto',
        alignItems: 'center', columnGap: '12px'
      }
    });

    var left = el('div', {
      style: { fontSize: '18px', fontWeight: 600, color: C.textPri, fontFamily: MONO, lineHeight: 1.15 }
    });
    left.appendChild(document.createTextNode(t.symbol + ' '));
    left.appendChild(el('span', { style: { color: C.textSec } }, t.strike));
    left.appendChild(el('div', { style: { marginTop: '2px' } }, pill(t.state, true)));
    hdr.appendChild(left);

    var confBox = el('div', {
      className: 'at-fade at-fade-' + (state.fadeTick || 0),
      style: {
        fontSize: '20px', fontWeight: 700, color: confColor(t.confidence),
        fontFamily: MONO, textAlign: 'right', lineHeight: 1,
        minWidth: '54px'  // spec §8: reserve for "100%"
      }
    }, t.confidence + '%');
    confBox.appendChild(el('div', {
      style: { fontSize: '9px', color: C.textMute, fontWeight: 600, letterSpacing: '1px', marginTop: '2px' }
    }, 'CONF'));
    hdr.appendChild(confBox);

    var priceBox = el('div', {
      className: (state.flash === 'up' ? 'at-flash-up' : state.flash === 'down' ? 'at-flash-dn' : '') +
                 ' at-fade at-fade-' + (state.fadeTick || 0),
      title: 'Last completed 5-minute candle close price',
      style: {
        fontSize: '16px', fontWeight: 600, color: C.textPri,
        fontFamily: MONO, textAlign: 'right', lineHeight: 1,
        minWidth: '70px'  // spec §8: reserve for max digits (e.g., "99999.99")
      }
    }, state.lastClose != null ? state.lastClose.toFixed(2) : '—');
    priceBox.appendChild(el('div', {
      style: { fontSize: '9px', color: C.textMute, fontWeight: 600, letterSpacing: '1px', marginTop: '2px' }
    }, '5M CLOSE'));
    hdr.appendChild(priceBox);

    return hdr;
  }

  function renderEntryEngine() {
    if (!state.selected) {
      return el('div', { style: { height: '72px', borderBottom: '1px solid ' + C.divider } });
    }
    var t = state.selected;
    var lc = state.lastClose != null ? state.lastClose : t.price;
    var dist = t.trigger - lc;
    var status;
    if (lc >= t.trigger || Math.abs(dist) < t.trigger * 0.001) {
      status = { label: 'ACTIVE', color: C.green, dot: '🟢' };
    } else if (Math.abs(dist) < t.trigger * 0.005) {
      status = { label: 'WATCHING', color: C.yellow, dot: '🟡' };
    } else {
      status = { label: 'INVALID', color: C.red, dot: '🔴' };
    }
    var pct = Math.max(0, Math.min(1, 1 - Math.abs(dist) / (t.trigger * 0.01)));

    var box = el('div', {
      style: {
        height: '72px', padding: '6px', background: C.card,
        borderBottom: '1px solid ' + C.divider,
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between'
      }
    });

    // Row 1: ENTRY + pill + countdown
    var row1 = el('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' } });
    var left = el('div', { style: { display: 'flex', alignItems: 'center', gap: '6px' } }, [
      el('span', { style: { fontSize: '10px', fontWeight: 800, color: C.textMute, letterSpacing: '1.2px' } }, 'ENTRY'),
      el('span', {
        style: {
          fontSize: '11px', fontWeight: 800, padding: '2px 8px', borderRadius: '999px',
          background: status.color + '22', color: status.color,
          border: '1px solid ' + status.color + '55', letterSpacing: '0.5px'
        }
      }, status.dot + ' ' + status.label)
    ]);
    row1.appendChild(left);
    row1.appendChild(el('div', {
      'data-countdown': '1',
      style: { fontSize: '10px', color: C.textMute, fontWeight: 700, fontFamily: MONO, letterSpacing: '1px' }
    }, 'Next Evaluation In: ' + state.countdown));
    box.appendChild(row1);

    // Spec §6: "Basis: Last 5m candle close" line
    box.appendChild(el('div', {
      style: { fontSize: '10px', color: C.textMute, fontFamily: MONO, letterSpacing: '0.3px', marginTop: '-2px' }
    }, 'Basis: Last 5m candle close'));

    // Row 2: trigger + current — spec §5.2 format: "Break above 243.50"
    var triggerVerb = t.side === 'PE' ? 'Break below' : 'Break above';
    var triggerLine = el('div', {
      style: { fontSize: '12px', color: C.textSec, lineHeight: 1.2, fontFamily: MONO }
    });
    triggerLine.appendChild(document.createTextNode('Trigger: '));
    triggerLine.appendChild(el('span', { style: { color: C.textPri } }, triggerVerb + ' ' + t.trigger.toFixed(2)));
    triggerLine.appendChild(document.createTextNode('   ·   Current: '));
    triggerLine.appendChild(el('span', { style: { color: status.color } },
      (lc != null ? lc.toFixed(2) : '—') + ' → ' + status.label.toLowerCase()));
    box.appendChild(triggerLine);

    // Row 3: distance bar
    var bar = el('div', { style: { height: '4px', background: C.active, borderRadius: '2px', overflow: 'hidden' } });
    bar.appendChild(el('div', {
      style: { width: (pct * 100) + '%', height: '100%', background: status.color, transition: 'width 600ms ease' }
    }));
    box.appendChild(bar);

    return box;
  }

  function renderOptionChain() {
    var rows = state.chain;
    // Find row with max abs OI change
    var maxIdx = -1, maxAbs = 0;
    rows.forEach(function (r, i) {
      var abs = Math.max(Math.abs(r.callOi || 0), Math.abs(r.putOi || 0));
      if (abs > maxAbs) { maxAbs = abs; maxIdx = i; }
    });

    var wrap = el('div', { style: { borderBottom: '1px solid ' + C.divider } });

    // Header row
    var header = el('div', {
      style: {
        fontSize: '10px', fontWeight: 800, color: C.textMute, letterSpacing: '1.5px',
        padding: '4px 8px', background: C.card,
        display: 'grid', gridTemplateColumns: '25% 25% 25% 25%'
      }
    }, [
      el('div', {}, 'STRIKE'),
      el('div', { style: { textAlign: 'right' } }, 'CALL OI Δ'),
      el('div', { style: { textAlign: 'right' } }, 'PUT OI Δ'),
      el('div', { style: { textAlign: 'center' } }, 'VOL')
    ]);
    wrap.appendChild(header);

    rows.forEach(function (r, i) {
      var row = el('div', {
        style: {
          height: '24px',
          display: 'grid', gridTemplateColumns: '25% 25% 25% 25%',
          alignItems: 'center', padding: '0 8px',
          background: r.isAtm ? C.active : C.card,
          borderLeft: i === maxIdx ? '2px solid ' + C.green : '2px solid transparent',
          fontSize: '13px', fontFamily: MONO, lineHeight: 1.1
        }
      }, [
        el('div', {
          style: { fontWeight: r.isAtm ? 700 : 500, color: r.strike === 0 ? C.textMute : C.textPri }
        }, r.strike === 0 ? '—' : String(r.strike)),
        el('div', {
          style: { textAlign: 'right', color: (r.callOi || 0) >= 0 ? C.green : C.red }
        }, (r.callOi > 0 ? '+' : '') + (r.callOi || 0)),
        el('div', {
          style: { textAlign: 'right', color: (r.putOi || 0) >= 0 ? C.green : C.red }
        }, (r.putOi > 0 ? '+' : '') + (r.putOi || 0)),
        el('div', { style: { textAlign: 'center' } }, r.volSpike ? '🔥' : '')
      ]);
      wrap.appendChild(row);
    });

    return wrap;
  }

  function renderRiskBlock() {
    if (!state.selected) {
      return el('div', { style: { height: '64px', borderBottom: '1px solid ' + C.divider } });
    }
    var t = state.selected;
    var lc = state.lastClose != null ? state.lastClose : t.price;
    var reward = Math.abs(t.target - lc);
    var risk = Math.abs(lc - t.sl);
    var rr = risk > 0 ? reward / risk : 0;
    var rrDanger = rr < 1.5;

    function cell(label, value, color, bold) {
      return el('div', {
        style: {
          padding: '4px',
          display: 'flex', flexDirection: 'column', justifyContent: 'center',
          borderRight: '1px solid ' + C.divider, borderBottom: '1px solid ' + C.divider
        }
      }, [
        el('div', { style: { fontSize: '9px', color: C.textMute, fontWeight: 700, letterSpacing: '1px' } }, label),
        el('div', {
          style: { fontSize: '14px', color: color, fontWeight: bold ? 700 : 500, fontFamily: MONO, lineHeight: 1.1 }
        }, String(value))
      ]);
    }

    return el('div', {
      style: {
        height: '64px', background: C.card,
        display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr',
        borderBottom: '1px solid ' + C.divider
      }
    }, [
      cell('SL', t.sl.toFixed(2), C.red, false),
      cell('TARGET', t.target.toFixed(2), C.green, false),
      cell('R:R', '1 : ' + rr.toFixed(1), rrDanger ? C.red : C.textPri, true),
      cell('LOT', t.lot != null ? String(t.lot) : '—', C.textSec, false)
    ]);
  }

  function renderVoiceLog() {
    var wrap = el('div', {
      style: {
        flex: 1, minHeight: '120px', background: C.bg, padding: '6px',
        borderTop: '1px solid ' + C.divider, overflow: 'hidden',
        display: 'flex', flexDirection: 'column'
      }
    });

    wrap.appendChild(el('div', {
      style: {
        fontSize: '10px', fontWeight: 800, color: C.textMute, letterSpacing: '1.5px',
        marginBottom: '4px', padding: '0 2px'
      }
    }, 'VOICE LOG'));

    var list = el('div', { style: { overflowY: 'auto', overflowX: 'hidden', flex: 1 } });
    if (state.logs.length === 0) {
      list.appendChild(el('div', {
        style: { color: C.textMute, fontSize: '11px', fontStyle: 'italic', padding: '4px' }
      }, 'Awaiting events…'));
    } else {
      state.logs.slice(0, 20).forEach(function (log, i) {
        var row = el('div', {
          style: {
            height: '22px',
            display: 'flex', alignItems: 'center', gap: '6px',
            fontSize: '12px', lineHeight: 1.1, fontFamily: MONO,
            opacity: Math.max(0.35, 1 - i * 0.05)
          }
        }, [
          el('span', { style: { color: C.textMute, minWidth: '62px' } }, log.time),
          el('span', { style: { color: log.color } }, '●'),
          el('span', {
            style: {
              color: C.textSec, overflow: 'hidden',
              textOverflow: 'ellipsis', whiteSpace: 'nowrap'
            }
          }, log.text)
        ]);
        list.appendChild(row);
      });
    }
    wrap.appendChild(list);
    return wrap;
  }

  function renderScanner() {
    var wrap = el('div', {
      style: {
        height: '186px', background: C.bg, borderTop: '1px solid ' + C.divider,
        display: 'flex', flexDirection: 'column', flexShrink: 0
      }
    });

    // Spec §9: "Last Updated: 01:30 ago" label
    var lastUpText = 'Last Updated: —';
    if (state.lastFullRefreshAt) {
      var ago = Math.floor((Date.now() - state.lastFullRefreshAt) / 1000);
      lastUpText = 'Last Updated: ' + formatAgo(ago);
    }
    wrap.appendChild(el('div', {
      style: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '4px 8px 2px',
        fontSize: '9px', fontWeight: 700, color: C.textMute,
        letterSpacing: '0.8px', fontFamily: MONO
      }
    }, [
      el('span', {}, 'SECONDARY SCANNER'),
      el('span', { 'data-last-up': '1' }, lastUpText)
    ]));

    wrap.appendChild(el('div', {
      style: {
        display: 'grid', gridTemplateColumns: '20% 10% 10% 20% 1fr',
        padding: '4px 8px',
        fontSize: '10px', fontWeight: 800, color: C.textMute, letterSpacing: '1.5px',
        borderBottom: '1px solid ' + C.divider
      }
    }, [
      el('div', {}, 'SYMBOL'),
      el('div', {}, 'DIR'),
      el('div', {}, 'SCORE'),
      el('div', {}, 'STATE'),
      el('div', {}, 'TREND')
    ]));

    var body = el('div', { style: { flex: 1, overflow: 'hidden' } });
    state.scanner.slice(0, 6).forEach(function (r, i) {
      var trend = r.trend || [r.score, r.score, r.score];
      var up = trend[trend.length - 1] > trend[0];
      var dn = trend[trend.length - 1] < trend[0];
      var tColor = up ? C.green : dn ? C.red : C.textSec;
      var tMark = up ? '▲' : dn ? '▼' : '■';

      body.appendChild(el('div', {
        style: {
          display: 'grid', gridTemplateColumns: '20% 10% 10% 20% 1fr',
          height: '26px', alignItems: 'center', padding: '0 8px',
          fontSize: '13px', fontFamily: MONO,
          borderBottom: i < state.scanner.length - 1 ? '1px solid ' + C.divider : 'none',
          color: C.textPri, lineHeight: 1.1
        }
      }, [
        el('div', { style: { fontWeight: 600 } }, r.symbol),
        el('div', { style: { color: r.direction === 'CE' ? C.green : C.red, fontWeight: 700 } }, r.direction),
        el('div', { style: { color: confColor(r.score), fontWeight: 700 } }, String(r.score)),
        el('div', {}, pill(r.state, true)),
        el('div', { style: { color: tColor, display: 'flex', alignItems: 'center', gap: '6px' } }, [
          el('span', {}, trend.join(' → ')),
          el('span', {}, tMark)
        ])
      ]));
    });

    // Empty-state
    if (state.scanner.length === 0) {
      body.appendChild(el('div', {
        style: {
          color: C.textMute, fontSize: '11px', fontStyle: 'italic',
          padding: '16px', textAlign: 'center'
        }
      }, 'Loading scanner…'));
    }

    wrap.appendChild(body);
    return wrap;
  }

  // ── ACTIONS ─────────────────────────────────────────────────────────────
  function selectTrade(t) {
    state.selected = t;
    state.lastClose = t.price;
    state.flash = null; // NEVER flash on user selection — only on 5m close price change
    fetchOptionChain(t.symbol, t.strike, t).then(function (rows) {
      state.chain = rows;
      rerender();
    });
    pushLog('Selected ' + t.symbol + ' ' + t.strike, C.blue);
    rerender();
  }

  function onExecute(t) {
    pushLog('EXECUTE ' + t.symbol + ' ' + t.strike + ' @ ' + (t.price || 0).toFixed(2), C.green);
    speak('Executing ' + t.symbol + ' ' + t.strike);
    rerender();
  }

  function onVoice(t) {
    // Spec §4.6: speaks "NIFTY 24500 CE, confidence 84%, entry now"
    // Phrase is fixed — not derived from state pill. Use "entry now" always.
    speak(t.symbol + ' ' + t.strike + ', confidence ' + t.confidence + ' percent, entry now');
  }

  function speak(text) {
    if (!state.voiceOn) return;
    try {
      if ('speechSynthesis' in window) {
        var u = new SpeechSynthesisUtterance(text);
        u.rate = 1.1; u.pitch = 1; u.volume = 0.8;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(u);
      }
    } catch (e) {}
  }

  function pushLog(text, color) {
    var time = new Date().toTimeString().slice(0, 8);
    state.logs.unshift({ id: Date.now() + Math.random(), time: time, text: text, color: color });
    state.logs = state.logs.slice(0, 20);
  }

  // ── REFRESH CYCLES ──────────────────────────────────────────────────────
  function refreshTopTrades() {
    var url = '/api/bottom-nav-scan?region=' + state.region;
    return fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        state.loaded = true;
        if (!d || !d.success) {
          state.lastFetchMsg = 'API error — check /api/bottom-nav-scan';
          state.trades = []; state.scanner = [];
          rerender(); return;
        }
        var raw = d.tickers || [];
        if (raw.length === 0) {
          state.lastFetchMsg = 'Scanner still warming up (boot takes ~30s) — retrying';
          state.trades = []; state.scanner = [];
          rerender(); return;
        }

        // Track WHY tickers are being rejected so we surface real diagnostics
        // instead of the vague "No setups" message.
        var rejectReasons = { noSpot: 0, noAtm: 0, noChain: 0, noPremium: 0,
                              noSide: 0, insufficientFactors: 0, belowThreshold: 0 };
        var mapped = [];
        raw.forEach(function (row) {
          // Quick pre-check to categorize rejection reason
          if (!row.sym && !row.symbol) return;
          if (row.spot == null || row.spot <= 0) { rejectReasons.noSpot++; return; }
          if (row.atm_strike == null || row.atm_strike <= 0) { rejectReasons.noAtm++; return; }
          if (!Array.isArray(row.chain_near_atm) || row.chain_near_atm.length === 0) {
            rejectReasons.noChain++; return;
          }
          var tr = mapScanRowToTrade(row);
          if (tr) mapped.push(tr);
          else rejectReasons.insufficientFactors++;
        });
        mapped.sort(function (a, b) { return b.confidence - a.confidence; });

        if (mapped.length === 0) {
          // Real diagnostic instead of generic "no setups"
          var diag = [];
          if (rejectReasons.noSpot) diag.push(rejectReasons.noSpot + ' no spot');
          if (rejectReasons.noAtm) diag.push(rejectReasons.noAtm + ' no ATM strike');
          if (rejectReasons.noChain) diag.push(rejectReasons.noChain + ' no option chain');
          if (rejectReasons.insufficientFactors) diag.push(rejectReasons.insufficientFactors + ' insufficient data');
          state.lastFetchMsg = 'No trades — ' + raw.length + ' scanned (' +
                               (diag.join(', ') || 'all below threshold') + ')';
          state.trades = []; state.scanner = [];
          rerender(); return;
        }

        state.lastFetchMsg = '';

        // ═══ 3-MIN STABILITY LOCK + +12% OVERRIDE RULE (v3 §5) ══════════
        // Normal rule: top-3 slots lock for 3 minutes.
        // Override exception (v3): if a candidate's score exceeds the current
        // trade's score by >12% AND the current trade isn't in ACTIVE ENTRY,
        // allow replacement even within lock window.
        var now = Date.now();
        var LOCK_MS = 3 * 60 * 1000;
        var OVERRIDE_DELTA = 12; // percentage points
        var prev = state.trades || [];
        var top3 = [];

        // Pass 1: carry forward locked trades that (a) are still in the
        // mapped set AND (b) don't have a candidate exceeding them by +12%.
        var activeEntryId = null;
        if (state.selected) {
          // Approximation: "ACTIVE ENTRY" = selected trade whose current price
          // has crossed its trigger. We check via _lastClose.
          var lc = state.lastClose != null ? state.lastClose : state.selected.price;
          var crossed = state.selected.side === 'CE'
            ? lc >= state.selected.trigger
            : lc <= state.selected.trigger;
          if (crossed) activeEntryId = state.selected.id;
        }

        for (var i = 0; i < prev.length && top3.length < 3; i++) {
          var p = prev[i];
          if (!p) continue;
          var lockStart = state.lockedIds[p.id];
          if (lockStart && (now - lockStart) < LOCK_MS) {
            var fresh = mapped.filter(function (m) { return m.id === p.id; })[0];
            if (!fresh) continue; // expired from mapped set

            // v3 §5 override: a candidate beats this locked slot by >12% AND
            // the locked trade isn't the user's ACTIVE ENTRY → allow replacement
            var beaten = mapped.some(function (m) {
              return m.id !== p.id && (m.confidence - fresh.confidence) > OVERRIDE_DELTA;
            });
            if (beaten && p.id !== activeEntryId) continue; // skip — Pass 2 fills

            top3.push(fresh);
          }
        }

        // Pass 2: fill remaining slots from highest-confidence non-locked
        for (var j = 0; j < mapped.length && top3.length < 3; j++) {
          var m2 = mapped[j];
          if (top3.filter(function (t) { return t.id === m2.id; }).length === 0) {
            top3.push(m2);
            if (!state.lockedIds[m2.id]) state.lockedIds[m2.id] = now;
          }
        }

        // GC stale lock entries
        var newLocks = {};
        top3.forEach(function (t) { newLocks[t.id] = state.lockedIds[t.id] || now; });
        state.lockedIds = newLocks;

        // ═══ SCORE HISTORY — v3 §5 "Score: 78 → 82 → 85" trend display ══
        // Persist last 3 confidence scores per trade id. Only updated here at
        // 5m close (Tier 1). Stale entries cleaned up.
        var newHist = {};
        top3.forEach(function (t) {
          var h = (state.scoreHistory[t.id] || []).slice();
          // Only append if changed (avoid stuttering on no-op refreshes)
          if (h.length === 0 || h[h.length - 1] !== t.confidence) {
            h.push(t.confidence);
          }
          if (h.length > 3) h = h.slice(-3);
          newHist[t.id] = h;
        });
        state.scoreHistory = newHist;

        // ═══ v3 VOICE TRIGGERS (spec §7) ════════════════════════════════
        // Spec: fire only on candle close OR state transition.
        // This function is called on 5m close via on5mClose() → refreshAll().
        var prevIds = state.prevTradeIds || {};

        // Trigger 1: NEW TOP TRADE
        var newTopTrade = top3.filter(function (t) { return !prevIds[t.id]; })[0];
        if (newTopTrade && Object.keys(prevIds).length > 0) {
          pushLog('NEW TOP: ' + newTopTrade.symbol + ' ' + newTopTrade.strike, C.green);
          speak('New top trade: ' + newTopTrade.symbol + ' ' + newTopTrade.strike +
                ', confidence ' + newTopTrade.confidence + ' percent');
        }

        // Trigger: FALSE BREAKOUT (v3 §13)
        top3.forEach(function (t) {
          var prevHad = prevIds[t.id];
          if (t.falseBreakout && (!prevHad || !prevHad.falseBreakout)) {
            pushLog('⚠ ' + t.symbol + ' ' + t.strike + ' — weak OI confirmation', C.orange);
            speak(t.symbol + ' breakout lacks institutional support. Avoid entry.');
          }
        });

        // Trigger: GAMMA MODE activation (v3 §12)
        top3.forEach(function (t) {
          if (t.gammaMode && !state.gammaModeIds[t.id]) {
            pushLog('⚡ GAMMA MODE: ' + t.symbol + ' ' + t.strike, C.yellow);
            speak('Gamma mode active on ' + t.symbol);
          }
        });
        var newGammaIds = {};
        var newGammaHist = {};
        top3.forEach(function (t) {
          if (t.gammaMode) {
            newGammaIds[t.id] = true;
            // Record reference data for next-candle kill-switch check
            var bars = t._raw.ohlc_bars || [];
            var lastBar = bars[bars.length - 1] || {};
            var bld = t.side === 'CE' ? (t._raw.pe_buildup || []) : (t._raw.ce_buildup || []);
            newGammaHist[t.id] = {
              triggeredAtClose: lastBar.c || t.price,
              referenceOpen: lastBar.o || t.price,
              referenceBuildupChg: bld[0] ? (bld[0].chg || 0) : 0
            };
          }
        });
        state.gammaModeIds = newGammaIds;
        state.gammaHistory = newGammaHist;

        // Trigger 3: LATE WARNING (spec §7: "Momentum weakening — reduce position")
        top3.forEach(function (t) {
          var pr = prevIds[t.id];
          var prevState = pr && pr.state;
          if (prevState && (prevState === 'early' || prevState === 'ideal') && t.state === 'late') {
            pushLog('Momentum weakening: ' + t.symbol + ' ' + t.strike + ' — reduce position', C.orange);
            speak('Momentum weakening — reduce position');
          }
        });

        // Trigger 4: EXIT
        if (state.selected) {
          var stillIn = top3.filter(function (t) { return t.id === state.selected.id; })[0];
          if (!stillIn && prevIds[state.selected.id]) {
            pushLog('EXIT: ' + state.selected.symbol + ' ' + state.selected.strike +
                    ' — momentum fading', C.red);
            speak('Exit ' + state.selected.symbol + ', momentum fading');
          } else if (stillIn && stillIn.state === 'avoid') {
            pushLog('EXIT SIGNAL: ' + stillIn.symbol + ' invalidated', C.red);
            speak('Exit now, setup invalidated');
          }
        }

        // Snapshot for next 5m close's comparison
        var nextPrev = {};
        top3.forEach(function (t) {
          nextPrev[t.id] = {
            state: t.state, confidence: t.confidence, falseBreakout: t.falseBreakout
          };
        });
        state.prevTradeIds = nextPrev;

        state.trades = top3;

        // Secondary scanner — ranks 4-9, uses score history for real trend arrows
        var scannerPool = mapped.filter(function (m) {
          return top3.filter(function (t) { return t.id === m.id; }).length === 0;
        });
        state.scanner = scannerPool.slice(0, 6).map(function (t) {
          var h = state.scoreHistory[t.id];
          // Use real history if we have it; else show current as flat
          var trend = (h && h.length >= 2) ? h : [t.confidence, t.confidence, t.confidence];
          return {
            symbol: t.symbol, direction: t.side,
            score: t.confidence, state: t.state,
            trend: trend
          };
        });

        // Auto-select first trade on first load
        if (!state.selected && top3.length > 0) {
          state.selected = top3[0];
          state.lastClose = top3[0].price;
          state.flash = null;
          fetchOptionChain(top3[0].symbol, top3[0].strike, top3[0]).then(function (rows) {
            state.chain = rows;
            rerender();
          });
        }
        rerender();
      })
      .catch(function (e) {
        console.warn('[AT] bottom-nav fetch failed', e);
        state.loaded = true;
        state.lastFetchMsg = 'Network error — backend unreachable';
        rerender();
      });
  }

  function refreshChain() {
    if (!state.selected) return Promise.resolve();
    return fetchOptionChain(state.selected.symbol, state.selected.strike, state.selected).then(function (rows) {
      state.chain = rows;
      rerender();
    });
  }

  function refreshAll() {
    // TIER 1 fetch + full recompute. Called at:
    //   (a) initial mount (so user sees something)
    //   (b) every 5m wall-clock candle close
    // NOT called on 90s. Spec §2/§3 forbids mid-cycle Tier 1 updates.
    return Promise.all([refreshTopTrades(), refreshChain()]);
  }

  function refreshTier2() {
    // Tier 2 allowed updates per spec §3:
    //   - "Last Updated" label on scanner
    //   - OI context (option chain Δ view)
    // NEVER touches: trade ranking, confidence, entry state, SL/target.
    state.lastTier2RefreshAt = Date.now();
    rerender();
  }

  function on5mClose() {
    // Spec §2: T+0s close → T+2s all engines recompute → single UI batch
    state.lastFullRefreshAt = Date.now();
    state.fadeTick = (state.fadeTick || 0) + 1; // spec §8: crossfade Tier 1 values
    refreshAll().then(function () {
      // Record the selected trade's 5m close price for Entry Engine display
      if (state.selected) {
        var prev = state.lastClose != null ? state.lastClose : state.selected.price;
        var newClose = state.selected.price;
        if (Math.abs(newClose - prev) > 0.001) {
          state.flash = newClose > prev ? 'up' : 'down';
          setTimeout(function () { state.flash = null; rerender(); }, 500);
        }
        state.lastClose = newClose;

        pushLog('5m close @ ' + newClose.toFixed(2), C.yellow);

        // Entry confirmed check
        if ((state.selected.side === 'CE' && newClose >= state.selected.trigger) ||
            (state.selected.side === 'PE' && newClose <= state.selected.trigger)) {
          pushLog('Entry confirmed, confidence ' + state.selected.confidence + '%', C.green);
          speak(state.selected.symbol + ' ' + state.selected.strike +
                ' entry confirmed, confidence ' + state.selected.confidence + ' percent');
        }
      }
      rerender();
    });
  }

  function startTimers() {
    // Countdown: label-only update, no data fetch, no rerender of anything else
    timers.countdown = setInterval(function () {
      state.countdown = formatCountdown(msUntilNextFiveMin());
      var countEl = document.querySelector('#activeTradingMount [data-countdown]');
      if (countEl) countEl.textContent = 'Next Evaluation In: ' + state.countdown;
      // Scanner "Last Updated" label (spec §9)
      var lastUpEl = document.querySelector('#activeTradingMount [data-last-up]');
      if (lastUpEl && state.lastFullRefreshAt) {
        var ago = Math.floor((Date.now() - state.lastFullRefreshAt) / 1000);
        lastUpEl.textContent = 'Last Updated: ' + formatAgo(ago);
      }
    }, 1000);

    // 90s Tier 2 refresh — scanner "Last Updated" label + non-decision fields only.
    // NEVER touches Top Trades ranking, confidence, entry state, SL/target.
    timers.soft90 = setInterval(refreshTier2, 90000);

    // 5m candle close — the ONLY moment Tier 1 decision fields recompute.
    function scheduleNext5m() {
      var ms = msUntilNextFiveMin();
      timers.candle5m = setTimeout(function () {
        on5mClose();
        scheduleNext5m();
      }, ms);
    }
    scheduleNext5m();
  }

  function stopTimers() {
    if (timers.countdown) clearInterval(timers.countdown);
    if (timers.soft90) clearInterval(timers.soft90);
    if (timers.candle5m) clearTimeout(timers.candle5m);
    timers.countdown = timers.soft90 = timers.candle5m = null;
  }

  var _rerenderScheduled = false;
  function rerender() {
    if (_rerenderScheduled || !mounted) return;
    _rerenderScheduled = true;
    requestAnimationFrame(function () {
      _rerenderScheduled = false;
      var root = document.getElementById('activeTradingMount');
      if (root) render(root);
    });
  }

  // ── ENTRY POINT ─────────────────────────────────────────────────────────
  window.mountActiveTrading = function (containerId) {
    var container = document.getElementById(containerId || 'deResult');
    if (!container) return;

    installScopedStyles();

    // Set body-level marker + tag ancestor .sc so CSS can scope override
    // without touching any inline styles. Everything is undone on unmount.
    document.body.classList.add('at-mode');
    var sc = container.closest ? container.closest('.sc') : null;
    if (sc) sc.setAttribute('data-at-host', '1');

    // Remove leftover injected elements (PDF export buttons, investor/trader
    // report fragments) that premium-override.js and other modules add to
    // #deResult. These carry white inline backgrounds that bleed through.
    var leftoverIds = ['celesysExportBtns', 'investorReport', 'traderReport',
                       'optionsReport', 'investorExportBtns'];
    leftoverIds.forEach(function (id) {
      var e = document.getElementById(id);
      if (e && e.parentElement) e.parentElement.removeChild(e);
    });

    // ═══ BRUTE-FORCE DARK BACKGROUND ═══════════════════════════════════
    // CSS rules keep losing to something on the deployed site. We now
    // write inline styles DIRECTLY on the ancestor chain. Inline styles
    // with !important beat external stylesheets regardless of specificity.
    // Store originals on a custom property so unmount can restore.
    var nodesToStyle = [];
    if (sc) {
      nodesToStyle.push({ el: sc, orig: sc.getAttribute('style') || '' });
      sc.setAttribute('style',
        (sc.getAttribute('style') || '') +
        ';background:#020617 !important' +
        ';border:1px solid #1E293B !important' +
        ';border-left:3px solid #0F172A !important' +
        ';box-shadow:none !important' +
        ';padding:0 !important'
      );

      var sbody = sc.querySelector('.sbody');
      if (sbody) {
        nodesToStyle.push({ el: sbody, orig: sbody.getAttribute('style') || '' });
        sbody.setAttribute('style',
          (sbody.getAttribute('style') || '') +
          ';background:#020617 !important' +
          ';padding:0 !important'
        );
      }

      // Hide every sibling of #deResult inside .sbody (deHeader via .sh,
      // #deControls with its mode/region rows, any injected report blocks)
      var hiddenSiblings = [];
      var sh = sc.querySelector('#deHeader') || sc.querySelector('.sh');
      if (sh) {
        hiddenSiblings.push({ el: sh, orig: sh.getAttribute('style') || '' });
        sh.setAttribute('style', (sh.getAttribute('style') || '') + ';display:none !important');
      }
      var deCtrl = sc.querySelector('#deControls');
      if (deCtrl) {
        hiddenSiblings.push({ el: deCtrl, orig: deCtrl.getAttribute('style') || '' });
        deCtrl.setAttribute('style', (deCtrl.getAttribute('style') || '') + ';display:none !important');
      }
      // Any other direct children of .sbody besides our #deResult
      if (sbody) {
        var kids = sbody.children;
        for (var i = 0; i < kids.length; i++) {
          if (kids[i] !== container && kids[i].id !== 'deControls') {
            hiddenSiblings.push({ el: kids[i], orig: kids[i].getAttribute('style') || '' });
            kids[i].setAttribute('style',
              (kids[i].getAttribute('style') || '') + ';display:none !important'
            );
          }
        }
      }
      // Also force #deResult itself to dark so no white strip shows around
      // the terminal if it has any padding/margin from a CSS rule.
      nodesToStyle.push({ el: container, orig: container.getAttribute('style') || '' });
      container.setAttribute('style',
        (container.getAttribute('style') || '') +
        ';background:#020617 !important' +
        ';padding:0 !important' +
        ';margin:0 !important' +
        ';min-height:0 !important'
      );

      state._hiddenSiblings = hiddenSiblings;
    }
    state._brutedNodes = nodesToStyle;

    container.innerHTML =
      '<div id="activeTradingMount" ' +
        'style="width:100%;background:#020617 !important;border-radius:8px;' +
               'border:1px solid #1E293B;overflow:hidden"></div>';
    mounted = true;

    render(document.getElementById('activeTradingMount'));
    refreshAll();
    startTimers();

    // ═══ MUTATION OBSERVER — BULLETPROOF DARK ENFORCEMENT ════════════════
    // CSS rules, inline styles, and scoped stylesheets all failed in Vijay's
    // real browser. This runs in a loop: on every DOM change inside the
    // terminal (or on the ancestor .sc/.sbody) we re-apply dark backgrounds.
    // Any script or stylesheet that tries to paint white gets overridden
    // the moment they do it, on the next animation frame.
    function enforceDark() {
      if (!mounted) return;
      // Force dark on all key elements
      var targets = [
        { el: sc, props: { background: '#020617', padding: '0', boxShadow: 'none' } },
        { el: sc && sc.querySelector('.sbody'), props: { background: '#020617', padding: '0' } },
        { el: container, props: { background: '#020617', padding: '0', minHeight: '0' } },
        { el: document.getElementById('activeTradingMount'),
          props: { background: '#020617' } }
      ];
      targets.forEach(function (t) {
        if (!t.el) return;
        for (var prop in t.props) {
          // setProperty with 'important' priority — most forceful JS API
          t.el.style.setProperty(
            prop.replace(/([A-Z])/g, '-$1').toLowerCase(),
            t.props[prop],
            'important'
          );
        }
      });
      // All descendants of the mount — force dark if they have any bg other
      // than our allowed colors (card #0F172A, active #1E293B, bg #020617)
      var mount = document.getElementById('activeTradingMount');
      if (mount) {
        var allDivs = mount.querySelectorAll('div');
        for (var i = 0; i < allDivs.length; i++) {
          var div = allDivs[i];
          var cs = window.getComputedStyle(div);
          var bg = cs.backgroundColor;
          // Allow transparent, our dark palette, and semi-transparent colored pills
          var allowedExact = {
            'rgba(0, 0, 0, 0)': 1, 'transparent': 1,
            'rgb(2, 6, 23)': 1,    // C.bg
            'rgb(15, 23, 42)': 1,  // C.card
            'rgb(30, 41, 59)': 1   // C.active
          };
          if (allowedExact[bg]) continue;
          // Allow low-alpha colored pills (state tags, warnings) — these use
          // rgba with alpha < 0.5 and are fine
          var m = bg.match(/rgba?\(([^)]+)\)/);
          if (m) {
            var parts = m[1].split(',').map(function (x) { return parseFloat(x); });
            if (parts.length === 4 && parts[3] < 0.5) continue;
          }
          // Anything else (white, light gray, etc.) → force dark
          div.style.setProperty('background-color', '#020617', 'important');
        }
      }
    }

    // Run once immediately
    enforceDark();
    // Run again after any DOM change (React-style re-renders, injected scripts)
    if (state._observer) state._observer.disconnect();
    state._observer = new MutationObserver(function () {
      // Throttle via rAF — don't block every mutation, coalesce per frame
      if (state._raf) return;
      state._raf = requestAnimationFrame(function () {
        state._raf = null;
        enforceDark();
      });
    });
    // Observe the ENTIRE document body for style/attribute/child changes,
    // because something OUTSIDE the mount may be repainting parent .sc.
    state._observer.observe(document.body, {
      attributes: true,       // catches style=".." attribute changes
      attributeFilter: ['style', 'class'],
      childList: true,
      subtree: true
    });
    // Also poll every 500ms as a safety net in case MutationObserver misses
    // something (e.g. computed style changes driven by media queries)
    if (state._pollTimer) clearInterval(state._pollTimer);
    state._pollTimer = setInterval(enforceDark, 500);

    // ═══ DEBUG: log computed backgrounds so we can see what's white ═══
    // Expose a function the user can call from console: window._atDebug()
    window._atDebug = function () {
      var rows = [];
      function inspect(sel, label) {
        var el = typeof sel === 'string' ? document.querySelector(sel) : sel;
        if (!el) { rows.push({ label: label, bg: '[MISSING]', inline: '', rule: '' }); return; }
        var cs = window.getComputedStyle(el);
        rows.push({
          label: label,
          bg: cs.backgroundColor,
          inline: el.getAttribute('style') ? el.getAttribute('style').substring(0, 100) : '',
          width: cs.width, height: cs.height
        });
      }
      inspect('html', 'html');
      inspect('body', 'body');
      inspect('.sc[data-at-host="1"]', 'sc (host)');
      inspect('.sc[data-at-host="1"] .sbody', 'sbody');
      inspect('#deResult', '#deResult');
      inspect('#activeTradingMount', '#activeTradingMount');
      var mount = document.getElementById('activeTradingMount');
      if (mount) {
        inspect(mount.children[0], 'wrap (child 1)');
        if (mount.children[0] && mount.children[0].children[1]) {
          inspect(mount.children[0].children[1], 'body grid');
          if (mount.children[0].children[1].children[0]) {
            inspect(mount.children[0].children[1].children[0], 'top trades panel');
          }
        }
      }
      console.table(rows);
      return rows;
    };
    // Auto-run once after mount so user sees it immediately in console
    setTimeout(function () {
      console.log('%c[ActiveTrading] v21 MUTATION OBSERVER active — call window._atDebug() anytime',
                  'color:#22C55E;font-weight:bold;background:#020617;padding:4px 8px');
      window._atDebug();
    }, 500);
  };

  window.unmountActiveTrading = function () {
    mounted = false;
    stopTimers();

    // Stop mutation observer + polling immediately so they don't fight the
    // theme restoration below.
    if (state._observer) { state._observer.disconnect(); state._observer = null; }
    if (state._pollTimer) { clearInterval(state._pollTimer); state._pollTimer = null; }
    if (state._raf) { cancelAnimationFrame(state._raf); state._raf = null; }

    document.body.classList.remove('at-mode');
    var allHosts = document.querySelectorAll('.sc[data-at-host="1"]');
    for (var i = 0; i < allHosts.length; i++) {
      allHosts[i].removeAttribute('data-at-host');
    }

    // Restore the brute-forced inline styles
    if (state._brutedNodes) {
      state._brutedNodes.forEach(function (n) {
        if (n.el) {
          if (n.orig) n.el.setAttribute('style', n.orig);
          else n.el.removeAttribute('style');
        }
      });
      state._brutedNodes = null;
    }
    if (state._hiddenSiblings) {
      state._hiddenSiblings.forEach(function (h) {
        if (h.el) {
          if (h.orig) h.el.setAttribute('style', h.orig);
          else h.el.removeAttribute('style');
        }
      });
      state._hiddenSiblings = null;
    }

    var mount = document.getElementById('activeTradingMount');
    if (mount) mount.innerHTML = '';
  };
})();
