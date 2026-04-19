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
  console.log('%c[ActiveTrading] v33 loaded — 3-col layout + Live Lifecycle + Plain-English voice',
              'color:#22C55E;font-weight:bold;font-size:13px');
  console.log('%c  Middle column: consensus verdict + live ADD/REDUCE/EXIT tags per position + macro snapshot',
              'color:#64748B;font-size:11px');
  console.log('%c  Every 5m bar: engine evaluates each open position and speaks plain-English guidance',
              'color:#64748B;font-size:11px');

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

  // ── ENGINE CORE (Lean-style architectural primitives) ──────────────────
  // Not a full port of Lean — a lean (pun intended) version of its three
  // most valuable abstractions for our options-focused use case:
  //   1. Event bus   — decoupled signal/order/log flow
  //   2. Signal ledger — every 5m close emits structured Signal objects
  //                      identical to what the Python backtest consumes
  //   3. Paper portfolio — EXECUTE writes a real position with lifecycle

  // Event bus. Subscribers use bus.on('event', fn); emitters use bus.emit('event', payload).
  // Decouples signal generation from UI updates, voice alerts, and order execution.
  var bus = (function () {
    var listeners = {};
    return {
      on: function (type, fn) {
        (listeners[type] = listeners[type] || []).push(fn);
      },
      emit: function (type, payload) {
        (listeners[type] || []).forEach(function (fn) {
          try { fn(payload); } catch (e) { console.warn('[bus] handler error', type, e); }
        });
      }
    };
  })();

  // Signal ledger — append-only. Every 5m close, one Signal per top-3 trade.
  // Persisted in sessionStorage so dev can inspect the signal stream.
  // Fields match the Python backtest CSV schema: ts, sym, strike, side, score,
  // state, spot, premium, sl, target, trigger, missing_factors.
  var signalLedger = {
    _key: 'at_signals_session',
    MAX: 500,  // keep last 500 signals in memory
    all: [],

    push: function (signal) {
      this.all.push(signal);
      if (this.all.length > this.MAX) this.all.shift();
      try { sessionStorage.setItem(this._key, JSON.stringify(this.all)); } catch (e) {}
      bus.emit('signal:new', signal);
    },
    load: function () {
      try {
        var raw = sessionStorage.getItem(this._key);
        if (raw) this.all = JSON.parse(raw);
      } catch (e) {}
    },
    clear: function () {
      this.all = [];
      try { sessionStorage.removeItem(this._key); } catch (e) {}
    }
  };
  signalLedger.load();

  // Paper portfolio — tracks EXECUTE'd positions through their lifecycle.
  // State machine: pending → active → (won | lost | expired | cancelled)
  // Persisted in window.storage so positions survive tab reloads.
  // In Lean terms: this is a minimal Portfolio + TransactionHandler.
  var paperPortfolio = {
    _storageKey: 'at_paper_positions',
    positions: {},  // { id: Position }

    // Position schema:
    //   id, sym, strike, side, score, state, reason,
    //   entryPremium, sl, target, trigger, lot, region, currency,
    //   status: 'pending'|'active'|'won'|'lost'|'expired'|'cancelled',
    //   openedAt, triggeredAt, closedAt, exitPremium, realizedPct,
    //   highWater, lowWater (premium range during hold)

    load: function () {
      var self = this;
      if (window.storage && typeof window.storage.get === 'function') {
        window.storage.get(this._storageKey).then(function (r) {
          if (r && r.value) {
            try { self.positions = JSON.parse(r.value); bus.emit('portfolio:loaded'); } catch (e) {}
          }
        }).catch(function () {});
      }
    },
    save: function () {
      if (window.storage && typeof window.storage.set === 'function') {
        try {
          window.storage.set(this._storageKey, JSON.stringify(this.positions)).catch(function () {});
        } catch (e) {}
      }
    },
    open: function (trade) {
      // Accept a trade object from mapScanRowToTrade and create a Position
      var id = trade.id + '@' + Date.now();
      var pos = {
        id: id, tradeId: trade.id,
        sym: trade.symbol, strike: trade.strike, side: trade.side,
        score: trade.confidence, state: trade.state, reason: trade.reason,
        entryPremium: trade.price,
        sl: trade.sl, target: trade.target, trigger: trade.trigger,
        lot: trade.lot,
        region: state.region,
        currency: (trade._raw && trade._raw.currency) || (state.region === 'US' ? '$' : '₹'),
        status: 'pending',
        openedAt: Date.now(),
        triggeredAt: null, closedAt: null,
        exitPremium: null, realizedPct: null,
        highWater: trade.price, lowWater: trade.price
      };
      this.positions[id] = pos;
      this.save();
      bus.emit('position:opened', pos);
      return pos;
    },
    // On every 5m close, update all active positions: check triggers, SL hits,
    // target hits, or expiry. This is the Lean RealtimeHandler equivalent.
    tick: function (tradeData) {
      // tradeData: map { tradeId: currentTrade } so we can look up live premium
      var changed = false;
      for (var id in this.positions) {
        var p = this.positions[id];
        if (p.status === 'won' || p.status === 'lost' ||
            p.status === 'expired' || p.status === 'cancelled') continue;
        var cur = tradeData[p.tradeId];
        if (!cur) continue;
        var currentPremium = cur.price;
        // Track watermarks
        if (currentPremium > p.highWater) p.highWater = currentPremium;
        if (currentPremium < p.lowWater) p.lowWater = currentPremium;

        if (p.status === 'pending') {
          // Check trigger
          var triggered = p.side === 'CE'
            ? currentPremium >= p.trigger
            : currentPremium <= p.trigger;
          if (triggered) {
            p.status = 'active'; p.triggeredAt = Date.now();
            changed = true;
            bus.emit('position:activated', p);
          }
        } else if (p.status === 'active') {
          // Check SL / target
          if (currentPremium <= p.sl) {
            p.status = 'lost';
            p.closedAt = Date.now();
            p.exitPremium = currentPremium;
            p.realizedPct = (currentPremium - p.entryPremium) / p.entryPremium * 100;
            changed = true;
            bus.emit('position:closed', p);
          } else if (currentPremium >= p.target) {
            p.status = 'won';
            p.closedAt = Date.now();
            p.exitPremium = currentPremium;
            p.realizedPct = (currentPremium - p.entryPremium) / p.entryPremium * 100;
            changed = true;
            bus.emit('position:closed', p);
          }
        }
      }
      if (changed) this.save();
    },
    // Cancel still-pending positions (e.g. end of day, or user action)
    cancel: function (id) {
      var p = this.positions[id];
      if (!p || p.status !== 'pending') return;
      p.status = 'cancelled'; p.closedAt = Date.now();
      this.save();
      bus.emit('position:closed', p);
    },
    // Stats for the UI P&L widget
    stats: function () {
      var total = 0, wins = 0, losses = 0, active = 0, pending = 0;
      var totalPnlPct = 0;
      for (var id in this.positions) {
        var p = this.positions[id];
        total++;
        if (p.status === 'won') { wins++; totalPnlPct += p.realizedPct || 0; }
        else if (p.status === 'lost') { losses++; totalPnlPct += p.realizedPct || 0; }
        else if (p.status === 'active') active++;
        else if (p.status === 'pending') pending++;
      }
      var closed = wins + losses;
      return {
        total: total, wins: wins, losses: losses,
        active: active, pending: pending,
        winRate: closed > 0 ? (wins / closed * 100) : 0,
        avgPnlPct: closed > 0 ? (totalPnlPct / closed) : 0
      };
    }
  };
  paperPortfolio.load();

  // Subscribe position events to voice log + audio alerts.
  // Voice tone follows Quick Trade's plain-English conversational style.
  bus.on('position:activated', function (p) {
    try {
      pushLog('ENTRY TRIGGERED: ' + p.sym + ' ' + p.strike + ' @ ' +
              p.currency + p.entryPremium.toFixed(2), C.green);
      // Snapshot baseline state so lifecycle engine can detect drift
      if (window._atEngine && window._atEngine.liveGuide) {
        var snapshot = {
          confidence: p.score || 0,
          side: p.side,
          entryPremium: p.entryPremium
        };
        window._atEngine.liveGuide.recordEntry(p.id, snapshot);
      }
      if (state.voiceOn) {
        // "NIFTY 24500 CE entry triggered at 150 rupees. Trade is now live.
        //  I will update you every five minutes with continue, add, reduce,
        //  or exit guidance."
        speak(p.sym + ' ' + p.strike + ' entry triggered at ' +
              p.entryPremium.toFixed(2) +
              '. Trade is live. I will guide you every five minutes.');
      }
    } catch (e) {}
  });
  bus.on('position:closed', function (p) {
    try {
      var verb = p.status === 'won' ? 'WON' :
                 p.status === 'lost' ? 'LOST' :
                 p.status === 'cancelled' ? 'CANCELLED' : 'EXPIRED';
      var pnl = p.realizedPct != null ? ' (' + (p.realizedPct > 0 ? '+' : '') +
                                        p.realizedPct.toFixed(2) + '%)' : '';
      var color = p.status === 'won' ? C.green : p.status === 'lost' ? C.red : C.textSec;
      pushLog('POSITION ' + verb + ': ' + p.sym + ' ' + p.strike + pnl, color);
      // Clear lifecycle snapshot
      if (window._atEngine && window._atEngine.liveGuide) {
        window._atEngine.liveGuide.clearEntry(p.id);
      }
      if (state.voiceOn && (p.status === 'won' || p.status === 'lost')) {
        var pctAbs = Math.abs(p.realizedPct || 0).toFixed(1);
        // Friendly closing message with context
        if (p.status === 'won') {
          speak(p.sym + ' ' + p.strike + ' trade closed with profit of ' +
                pctAbs + ' percent. Well played. Ready for the next setup.');
        } else {
          speak(p.sym + ' ' + p.strike + ' trade closed with loss of ' +
                pctAbs + ' percent. Protect your capital. Wait for the next clean setup.');
        }
      } else if (state.voiceOn && p.status === 'cancelled') {
        speak(p.sym + ' ' + p.strike + ' was cancelled before triggering.');
      }
    } catch (e) {}
  });

  // ═══════════════════════════════════════════════════════════════════════
  // 1. KELLY-SIZED POSITION ALLOCATION
  // ═══════════════════════════════════════════════════════════════════════
  // Classic Kelly formula for binary outcomes (win → target, lose → SL):
  //   f* = (p·b - q) / b   where
  //     p = probability of winning
  //     q = 1 - p
  //     b = payoff ratio = (target - entry) / (entry - SL)
  //
  // We map confidence score to win probability via a calibrated curve,
  // then apply fractional Kelly (0.25× by default) for safety — full
  // Kelly maximizes compounded return but has 50%+ drawdowns. Fractional
  // Kelly is standard institutional practice.
  //
  // Win probability calibration: from our engine spec, score 55 = borderline
  // (50% win), score 95 = elite signals (~65% historically for similar 6-
  // factor OI/VWAP/trend composites per published options research).
  // Linear interpolation in absence of our own backtest data.
  var kellySizer = {
    // Tunables — these become regime-adjustable in next round
    fractional: 0.25,       // 0.25 = quarter-Kelly (very conservative)
    maxPctPerTrade: 10,     // never risk more than 10% of capital on one position
    minPctPerTrade: 0.5,    // floor — don't open sub-noise positions
    defaultCapital: 100000, // fallback if user hasn't set capital

    capital: function () {
      // Allow user to override via localStorage; else default
      try {
        var stored = localStorage.getItem('at_capital');
        if (stored) return parseFloat(stored) || this.defaultCapital;
      } catch (e) {}
      return this.defaultCapital;
    },
    setCapital: function (amount) {
      try { localStorage.setItem('at_capital', String(amount)); } catch (e) {}
    },

    // Map confidence score (0-100) to win probability (0-1)
    // Piecewise calibration reflecting that higher scores should have
    // meaningfully better outcomes — anchored to what options research
    // literature reports for multi-factor signals on 5m timeframes.
    scoreToWinProb: function (score) {
      if (score < 55) return 0.48; // below threshold — assume slight loss bias
      if (score < 68) return 0.52; // late
      if (score < 76) return 0.56; // early
      if (score < 86) return 0.60; // ideal
      if (score < 96) return 0.64; // strong
      return 0.67;                 // elite
    },

    // Returns: { pctOfCapital, lots, rupees, winProb, payoffRatio, edge, reason }
    // Inputs all from the trade object.
    size: function (trade) {
      var entry = trade.price;
      var sl = trade.sl;
      var target = trade.target;
      var lotSize = trade.lot || 1;
      if (!entry || !sl || !target || entry <= 0) {
        return { error: 'missing price/sl/target', pctOfCapital: 0, lots: 0 };
      }
      var riskPerShare = Math.abs(entry - sl);
      var rewardPerShare = Math.abs(target - entry);
      if (riskPerShare <= 0) return { error: 'zero risk', pctOfCapital: 0, lots: 0 };

      var b = rewardPerShare / riskPerShare;  // payoff ratio
      var p = this.scoreToWinProb(trade.confidence);
      var q = 1 - p;

      // Kelly fraction of capital to RISK (not to invest — crucial distinction)
      // f* tells us: "risk this fraction of bankroll on this bet"
      var fullKelly = (p * b - q) / b;
      var edge = p * b - q; // expected value per unit risk

      // If edge is negative, skip the trade entirely
      if (fullKelly <= 0) {
        return {
          pctOfCapital: 0, lots: 0, rupees: 0,
          winProb: p, payoffRatio: b, edge: edge,
          reason: 'Negative Kelly — skip', fullKelly: fullKelly
        };
      }

      // Apply fractional Kelly + cap + floor
      var kellyFrac = Math.max(0, fullKelly * this.fractional);
      var pctCapitalToRisk = Math.min(kellyFrac * 100, this.maxPctPerTrade);
      pctCapitalToRisk = Math.max(pctCapitalToRisk, this.minPctPerTrade);

      // Convert risk% → number of lots
      //   rupeesToRisk = capital × pct/100
      //   lotsToBuy    = rupeesToRisk / (riskPerShare × lotSize)
      var cap = this.capital();
      var rupeesToRisk = cap * pctCapitalToRisk / 100;
      var lots = Math.max(1, Math.floor(rupeesToRisk / (riskPerShare * lotSize)));

      // Recompute ACTUAL pct risked given lot rounding
      var actualRupeesRisked = lots * riskPerShare * lotSize;
      var actualPctRisked = (actualRupeesRisked / cap) * 100;

      return {
        pctOfCapital: actualPctRisked,
        lots: lots,
        rupees: actualRupeesRisked,
        premiumCost: lots * lotSize * entry,
        winProb: p,
        payoffRatio: b,
        edge: edge,
        fullKelly: fullKelly,
        fractionApplied: this.fractional,
        capital: cap,
        reason: 'Kelly ' + (this.fractional * 100).toFixed(0) + '% @ ' +
                (p * 100).toFixed(0) + '% win · ' + b.toFixed(2) + 'R'
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 2. EXECUTION COST MODEL
  // ═══════════════════════════════════════════════════════════════════════
  // Three cost components combined into expected cost per round-trip:
  //   (a) Slippage — premium gap between quote and fill. Scales with:
  //       - Bid-ask spread as % of premium (wider = more slip)
  //       - Order size vs available liquidity (impact)
  //   (b) Brokerage — broker-specific fixed + pct fees
  //   (c) STT / regulatory — India STT + exchange transaction + GST + SEBI
  //
  // Returns net realized return AFTER costs.
  // India defaults: Zerodha-style for F&O.
  // US defaults: typical discount broker per-contract.
  var execCostModel = {
    // Cost schedules — user-overridable
    schedules: {
      IN: {
        label: 'India F&O (Zerodha-style)',
        brokerageFlat: 20,          // ₹20 per order regardless of size
        brokeragePct: 0.03,         // 0.03% of turnover, max ₹20
        brokerageCap: 20,
        sttSellPct: 0.05,           // STT 0.05% on SELL side only (options)
        exchangeTxnPct: 0.053,      // NSE F&O option transaction charges
        gstPct: 18,                 // GST on (brokerage + exchange + SEBI)
        sebiPct: 0.0001,            // 0.0001% on turnover
        stampPct: 0.003             // Stamp duty 0.003% BUY side
      },
      US: {
        label: 'US equity options (discount broker)',
        perContract: 0.65,          // $0.65 per contract each way
        regFeePerContract: 0.02,    // OCC clearing + regulatory
        brokeragePct: 0,
        brokerageFlat: 0,
        sttSellPct: 0,
        exchangeTxnPct: 0,
        gstPct: 0,
        sebiPct: 0,
        stampPct: 0
      }
    },

    // Slippage estimator — returns % of premium lost to slip per side
    estimateSlippagePct: function (trade) {
      // Without real bid/ask we use a conservative heuristic tied to
      // option moneyness and expiry proximity.
      // - ATM: tight spreads (~0.3% per side)
      // - OTM: wider (~1.0% per side)
      // - Short-dated (<1 day): add 0.3% for illiquidity
      var raw = trade._raw || {};
      var spot = raw.spot || 0;
      var atm = raw.atm_strike || 0;
      var strikeStr = String(trade.strike).split(' ')[0];
      var strike = parseFloat(strikeStr) || atm || spot;
      if (!spot || !strike) return 0.6; // unknown → assume middle
      var moneyness = Math.abs(strike - spot) / spot; // 0 = ATM
      var base;
      if (moneyness < 0.005) base = 0.3;      // ATM
      else if (moneyness < 0.015) base = 0.5; // near-ATM
      else if (moneyness < 0.03) base = 0.8;  // OTM
      else base = 1.2;                        // far OTM
      return base;
    },

    // Main: given a planned trade, compute per-round-trip cost in rupees
    // AND the break-even required move on premium
    computeCost: function (trade, lots, region) {
      region = region || 'IN';
      var s = this.schedules[region];
      var lotSize = trade.lot || 1;
      var premium = trade.price || 0;
      var turnoverPerSide = lots * lotSize * premium;
      var total = 0;
      var breakdown = {};

      if (region === 'IN') {
        // Brokerage per side
        var brokPerSide = Math.min(
          turnoverPerSide * s.brokeragePct / 100,
          s.brokerageCap
        );
        brokPerSide = Math.min(brokPerSide, s.brokerageFlat);
        breakdown.brokerage = brokPerSide * 2;          // both sides
        // Exchange + SEBI + stamp on both sides
        breakdown.exchange = turnoverPerSide * s.exchangeTxnPct / 100 * 2;
        breakdown.sebi = turnoverPerSide * s.sebiPct / 100 * 2;
        breakdown.stamp = turnoverPerSide * s.stampPct / 100; // BUY only
        // STT on SELL side (on premium turnover for options)
        breakdown.stt = turnoverPerSide * s.sttSellPct / 100;
        // GST on (brokerage + exchange + SEBI)
        var gstBase = breakdown.brokerage + breakdown.exchange + breakdown.sebi;
        breakdown.gst = gstBase * s.gstPct / 100;
      } else if (region === 'US') {
        breakdown.brokerage = lots * (s.perContract + s.regFeePerContract) * 2; // both sides
      }

      // Slippage on both sides
      var slipPct = this.estimateSlippagePct(trade);
      breakdown.slippage = (turnoverPerSide * slipPct / 100) * 2;

      total = 0;
      for (var k in breakdown) total += breakdown[k];
      breakdown.total = total;
      breakdown.totalPctOfTurnover = (total / turnoverPerSide) * 100;

      // Break-even required: what % move on premium covers total cost
      var breakEvenPremium = total / (lots * lotSize);
      breakdown.breakEvenPremium = breakEvenPremium;
      breakdown.breakEvenPct = (breakEvenPremium / premium) * 100;

      return breakdown;
    },

    // Apply cost to realized P&L % to get NET return
    netReturn: function (grossPct, trade, lots, region) {
      var costs = this.computeCost(trade, lots, region);
      return grossPct - costs.breakEvenPct;
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 3. REGIME DETECTOR (trending vs ranging vs volatile)
  // ═══════════════════════════════════════════════════════════════════════
  // Classifies current market regime from the last N 5m candles of the
  // lead index (NIFTY for IN, SPY for US). Regime state feeds back into
  // Kelly (reduce size in volatile), scoring (deweight trend in range),
  // and the UI (visible regime badge so user knows context).
  //
  // Regimes:
  //   TRENDING_UP   — HH/HL sequence + price > VWAP + low ADX-like choppiness
  //   TRENDING_DN   — LL/LH sequence + price < VWAP
  //   RANGING       — oscillation, no HH/LL streak, low directional move
  //   VOLATILE      — high candle-range relative to ATR, whipsaw
  //   UNKNOWN       — insufficient data
  var regimeDetector = {
    current: 'UNKNOWN',
    lastUpdate: 0,
    history: [],

    // Feed bars from the lead index and classify
    classify: function (bars) {
      if (!Array.isArray(bars) || bars.length < 10) {
        this.current = 'UNKNOWN';
        return 'UNKNOWN';
      }

      var last10 = bars.slice(-10);
      // Validate bars
      for (var i = 0; i < last10.length; i++) {
        var b = last10[i];
        if (b == null || b.h == null || b.l == null || b.c == null) {
          this.current = 'UNKNOWN';
          return 'UNKNOWN';
        }
      }

      // Metric 1: directional streak (HH/HL vs LL/LH)
      var hhhl = 0, llih = 0;
      for (var i = 1; i < last10.length; i++) {
        if (last10[i].h > last10[i-1].h && last10[i].l > last10[i-1].l) hhhl++;
        else if (last10[i].l < last10[i-1].l && last10[i].h < last10[i-1].h) llih++;
      }

      // Metric 2: net move vs cumulative range (trend efficiency)
      var netMove = Math.abs(last10[9].c - last10[0].o);
      var cumRange = 0;
      for (var i = 0; i < last10.length; i++) cumRange += (last10[i].h - last10[i].l);
      var efficiency = cumRange > 0 ? netMove / cumRange : 0;
      //   efficiency > 0.4 = strong trend (net move ≥ 40% of total range)
      //   efficiency < 0.15 = ranging (price returned close to start)

      // Metric 3: volatility — stdev of bar ranges vs mean
      var ranges = last10.map(function (b) { return b.h - b.l; });
      var meanRange = ranges.reduce(function (a, b) { return a + b; }, 0) / ranges.length;
      var variance = ranges.reduce(function (s, r) {
        return s + Math.pow(r - meanRange, 2);
      }, 0) / ranges.length;
      var stdRange = Math.sqrt(variance);
      var volCV = meanRange > 0 ? stdRange / meanRange : 0;
      //   volCV > 0.6 = spiky/volatile

      // Direction sign
      var direction = last10[9].c > last10[0].o ? 1 : -1;

      var regime;
      if (volCV > 0.6 && efficiency < 0.4) {
        regime = 'VOLATILE';
      } else if (efficiency > 0.4 && hhhl >= 4 && direction > 0) {
        regime = 'TRENDING_UP';
      } else if (efficiency > 0.4 && llih >= 4 && direction < 0) {
        regime = 'TRENDING_DN';
      } else if (efficiency < 0.2) {
        regime = 'RANGING';
      } else {
        regime = 'MIXED';
      }

      this.current = regime;
      this.lastUpdate = Date.now();
      this.history.push({ ts: Date.now(), regime: regime,
                          efficiency: efficiency, hhhl: hhhl, llih: llih, volCV: volCV });
      if (this.history.length > 100) this.history.shift();
      return regime;
    },

    // Regime-adaptive multipliers for Kelly sizing
    // Returns a multiplier for the fractional Kelly value (1.0 = normal)
    kellyMultiplier: function () {
      switch (this.current) {
        case 'TRENDING_UP':
        case 'TRENDING_DN':
          return 1.2;  // trend days — slightly more aggressive
        case 'RANGING':
          return 0.7;  // chop — reduce size
        case 'VOLATILE':
          return 0.5;  // whipsaw — half size
        case 'MIXED':
        default:
          return 1.0;
      }
    },

    // Regime-adaptive score threshold
    // In volatile regime, require higher confidence to open a trade
    minScoreOverride: function (defaultMin) {
      switch (this.current) {
        case 'VOLATILE': return Math.max(defaultMin, 75);
        case 'RANGING':  return Math.max(defaultMin, 68);
        default: return defaultMin;
      }
    },

    // Human-readable label
    label: function () {
      return ({
        TRENDING_UP: '↗ TRENDING UP',
        TRENDING_DN: '↘ TRENDING DN',
        RANGING:     '↔ RANGING',
        VOLATILE:    '⚡ VOLATILE',
        MIXED:       '· MIXED',
        UNKNOWN:     '? UNKNOWN'
      })[this.current] || this.current;
    },

    // Pill color for UI
    color: function () {
      switch (this.current) {
        case 'TRENDING_UP': return '#22C55E';
        case 'TRENDING_DN': return '#EF4444';
        case 'RANGING':     return '#F59E0B';
        case 'VOLATILE':    return '#A855F7';
        default:            return '#64748B';
      }
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 4. ALPHA DECAY MONITOR
  // ═══════════════════════════════════════════════════════════════════════
  // Tracks whether high-confidence signals are STILL producing better
  // outcomes than low-confidence signals over a rolling window. If the
  // spread between ≥80 and <68 bands collapses, the engine is losing its
  // edge and needs re-tuning or a cooldown period.
  //
  // Uses closed positions (won/lost) from paperPortfolio — needs at least
  // 20 closed positions across both bands to produce a reliable read.
  var alphaDecay = {
    window: 50,      // rolling window of closed positions
    minSamples: 10,  // min closed positions per band before reporting
    warnThreshold: 3,    // if high-band avg P&L - low-band avg P&L < 3%, warn
    alertThreshold: 0,   // if difference <= 0, alert strongly

    // Compute current decay state from paperPortfolio closed positions
    read: function () {
      var positions = Object.values(paperPortfolio.positions)
        .filter(function (p) {
          return (p.status === 'won' || p.status === 'lost') &&
                  p.realizedPct != null && p.score != null;
        })
        .sort(function (a, b) { return (b.closedAt || 0) - (a.closedAt || 0); })
        .slice(0, this.window);

      var high = positions.filter(function (p) { return p.score >= 80; });
      var low = positions.filter(function (p) { return p.score < 68 && p.score >= 55; });

      function stats(arr) {
        if (arr.length === 0) return { n: 0, winRate: 0, avgPnl: 0 };
        var wins = arr.filter(function (p) { return p.status === 'won'; }).length;
        var avgPnl = arr.reduce(function (s, p) { return s + p.realizedPct; }, 0) / arr.length;
        return {
          n: arr.length,
          winRate: (wins / arr.length) * 100,
          avgPnl: avgPnl
        };
      }

      var highStats = stats(high);
      var lowStats = stats(low);
      var spread = highStats.avgPnl - lowStats.avgPnl;

      var status = 'UNKNOWN';
      if (highStats.n >= this.minSamples && lowStats.n >= this.minSamples) {
        if (spread > this.warnThreshold) status = 'HEALTHY';
        else if (spread > this.alertThreshold) status = 'DEGRADING';
        else status = 'DECAYED';
      } else {
        status = 'INSUFFICIENT_DATA';
      }

      return {
        status: status,
        spread: spread,
        highBand: highStats,
        lowBand: lowStats,
        totalSamples: positions.length
      };
    },

    // UI-ready summary string
    summary: function () {
      var r = this.read();
      if (r.status === 'INSUFFICIENT_DATA') {
        return 'Alpha: ' + r.totalSamples + '/20 samples';
      }
      var sign = r.spread > 0 ? '+' : '';
      return 'Alpha: ' + r.status + ' (≥80 edge: ' + sign + r.spread.toFixed(1) + '%)';
    },

    color: function () {
      var r = this.read();
      if (r.status === 'HEALTHY') return '#22C55E';
      if (r.status === 'DEGRADING') return '#F59E0B';
      if (r.status === 'DECAYED') return '#EF4444';
      return '#64748B';
    }
  };


  // (window._atEngine assigned below, AFTER all modules are declared —
  //  this avoids JS hoisting issue where var decls exist but assignments
  //  haven't run yet, leaving exposed references as undefined.)

  // ═══════════════════════════════════════════════════════════════════════
  // 5. BLACK-SCHOLES PRICING MATH + GREEKS
  // ═══════════════════════════════════════════════════════════════════════
  // Ported from options-engine.js _erf + _renderGreeks. Gives us Δ/Γ/Θ/Vega
  // for any option so the trader can see theta bleed and gamma exposure on
  // the selected trade. Greeks are recomputed on every render using the
  // live spot from the trade object.
  var pricingMath = {
    // Abramowitz-Stegun erf approximation (standard)
    erf: function (x) {
      var a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
      var a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
      var sign = x >= 0 ? 1 : -1;
      x = Math.abs(x);
      var t = 1 / (1 + p * x);
      var y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
      return sign * y;
    },
    // Standard normal CDF
    N: function (x) {
      return 0.5 * (1 + this.erf(x / Math.sqrt(2)));
    },
    // Standard normal PDF
    n: function (x) {
      return Math.exp(-x * x / 2) / Math.sqrt(2 * Math.PI);
    },

    // Greeks for a European option.
    //   spot, strike, dte (days), iv (% annualized), optType 'CE'|'PE'
    //   Returns { delta, gamma, theta (per day), vega (per 1% IV), fairValue }
    //   or null if any input is invalid.
    greeks: function (spot, strike, dte, ivPct, optType) {
      if (!spot || spot <= 0 || !strike || strike <= 0) return null;
      if (ivPct == null || ivPct <= 0) return null;
      var T = Math.max(dte, 0.01) / 365;
      var r = 0.07;  // risk-free; small change doesn't move Greeks materially
      var sigma = ivPct / 100;
      var sqrtT = Math.sqrt(T);

      var d1 = (Math.log(spot / strike) + (r + sigma * sigma / 2) * T) / (sigma * sqrtT);
      var d2 = d1 - sigma * sqrtT;
      var Nd1 = this.N(d1), Nd2 = this.N(d2);
      var nd1 = this.n(d1);

      var delta, theta, fairValue;
      if (optType === 'CE') {
        delta = Nd1;
        theta = -(spot * nd1 * sigma) / (2 * sqrtT) / 365
                - r * strike * Math.exp(-r * T) * Nd2 / 365;
        fairValue = spot * Nd1 - strike * Math.exp(-r * T) * Nd2;
      } else {
        delta = Nd1 - 1;
        theta = -(spot * nd1 * sigma) / (2 * sqrtT) / 365
                + r * strike * Math.exp(-r * T) * (1 - Nd2) / 365;
        fairValue = strike * Math.exp(-r * T) * (1 - Nd2) - spot * (1 - Nd1);
      }
      var gamma = nd1 / (spot * sigma * sqrtT);
      var vega = spot * nd1 * sqrtT / 100;  // per 1% IV move

      return {
        delta: delta, gamma: gamma, theta: theta, vega: vega,
        fairValue: fairValue, d1: d1, d2: d2, dte: dte
      };
    },

    // DTE from an expiry string like '27-Nov-2025' or ISO. Returns 0 if unparseable.
    dteFromExpiry: function (expiry) {
      if (!expiry) return 0;
      try {
        // Format 1: '27-Nov-2025'
        var m = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5,
                  Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 };
        var p = expiry.split('-');
        if (p.length === 3 && m[p[1]] != null) {
          var d = new Date(parseInt(p[2]), m[p[1]], parseInt(p[0]));
          return Math.max(0, Math.round((d - new Date()) / 86400000));
        }
        // Format 2: ISO '2025-11-27'
        var dd = new Date(expiry);
        if (!isNaN(dd)) return Math.max(0, Math.round((dd - new Date()) / 86400000));
      } catch (e) {}
      return 0;
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 6. IV vs HV (Implied vs Historical Volatility)
  // ═══════════════════════════════════════════════════════════════════════
  // If IV >> HV → options are overpriced (sell premium)
  // If IV << HV → options are underpriced (buy options)
  // If IV ≈ HV → fairly priced
  var volMath = {
    // Compute annualized historical volatility from OHLC bars.
    // Uses log-returns on closes; 252 trading days/year; 75 bars/day for 5m.
    // Returns % annualized, or null if insufficient data.
    computeHV: function (bars) {
      if (!Array.isArray(bars) || bars.length < 10) return null;
      var returns = [];
      for (var i = 1; i < bars.length; i++) {
        if (bars[i - 1].c > 0 && bars[i].c > 0) {
          returns.push(Math.log(bars[i].c / bars[i - 1].c));
        }
      }
      if (returns.length < 5) return null;
      var mean = returns.reduce(function (s, r) { return s + r; }, 0) / returns.length;
      var variance = returns.reduce(function (s, r) {
        return s + (r - mean) * (r - mean);
      }, 0) / (returns.length - 1);
      if (variance <= 0) return null;
      // Scale: per-bar stdev × sqrt(bars per year).
      // 5m bars: 75/day × 252 days = 18900 bars/year
      var barsPerYear = 18900;
      var annualized = Math.sqrt(variance) * Math.sqrt(barsPerYear) * 100;
      return Math.round(annualized * 10) / 10;
    },

    // Compute IV/HV ratio and verdict.
    analyze: function (iv, bars) {
      if (iv == null || iv <= 0) return { status: 'no_iv' };
      var hv = this.computeHV(bars);
      if (hv == null) return { status: 'no_hv', iv: iv };
      var ratio = iv / Math.max(hv, 1);
      var verdict, action;
      if (ratio > 1.3) {
        verdict = 'OVERPRICED'; action = 'Consider selling premium';
      } else if (ratio > 1.1) {
        verdict = 'ELEVATED'; action = 'Options expensive but usable';
      } else if (ratio < 0.75) {
        verdict = 'UNDERPRICED'; action = 'Options cheap — favor buying';
      } else if (ratio < 0.9) {
        verdict = 'DISCOUNTED'; action = 'Slightly cheap';
      } else {
        verdict = 'FAIR'; action = 'Fairly priced';
      }
      return {
        status: 'ok', iv: iv, hv: hv,
        ratio: ratio, verdict: verdict, action: action
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 7. PORTFOLIO RISK CONTROLS
  // ═══════════════════════════════════════════════════════════════════════
  // Institutional risk guardrails that override trade sizing decisions:
  //   - Max N concurrent positions
  //   - Max X% daily loss (circuit breaker — stop trading until next day)
  //   - Max Y% drawdown from session high (also a circuit breaker)
  //   - Min K minutes between consecutive opens (cooldown)
  //
  // Returns { allow: true|false, reason: 'why blocked' }.
  var portfolioRisk = {
    config: {
      maxConcurrent: 3,              // max pending+active paper positions
      maxDailyLossPct: 3,            // stop trading if session P&L < -3%
      maxDrawdownPct: 5,             // stop trading if drawdown from peak > 5%
      cooldownSeconds: 60            // min seconds between opens
    },

    _lastOpenAt: 0,
    _sessionStart: Date.now(),

    // Override config from localStorage (lets user tune without redeploy)
    loadConfig: function () {
      try {
        var stored = localStorage.getItem('at_risk_config');
        if (stored) {
          var parsed = JSON.parse(stored);
          for (var k in parsed) if (this.config[k] != null) this.config[k] = parsed[k];
        }
      } catch (e) {}
    },
    saveConfig: function () {
      try { localStorage.setItem('at_risk_config', JSON.stringify(this.config)); } catch (e) {}
    },

    // Session-scoped stats from paperPortfolio, filtered to today only
    sessionStats: function () {
      var self = this;
      var dayStart = new Date(); dayStart.setHours(0, 0, 0, 0);
      var concurrent = 0, todayClosed = 0, todayPnlPct = 0, peakPnl = 0;
      var runningPnl = 0, minRunning = 0;
      var todays = [];
      for (var id in paperPortfolio.positions) {
        var p = paperPortfolio.positions[id];
        if (p.status === 'pending' || p.status === 'active') concurrent++;
        if (p.closedAt && p.closedAt >= dayStart.getTime() &&
            (p.status === 'won' || p.status === 'lost')) {
          todays.push(p);
        }
      }
      todays.sort(function (a, b) { return a.closedAt - b.closedAt; });
      for (var i = 0; i < todays.length; i++) {
        runningPnl += (todays[i].realizedPct || 0);
        if (runningPnl > peakPnl) peakPnl = runningPnl;
        var dd = peakPnl - runningPnl;
        if (dd > -minRunning) minRunning = -dd;
        todayPnlPct += (todays[i].realizedPct || 0);
      }
      todayClosed = todays.length;
      return {
        concurrent: concurrent,
        todayClosed: todayClosed,
        todayPnlPct: todayPnlPct,
        peakPnlPct: peakPnl,
        drawdownPct: peakPnl - runningPnl,
        minutesSinceLastOpen: (Date.now() - this._lastOpenAt) / 60000
      };
    },

    // Check if we should allow a new position open
    checkAllow: function () {
      var s = this.sessionStats();
      if (s.concurrent >= this.config.maxConcurrent) {
        return { allow: false,
                 reason: 'Max concurrent positions reached (' + s.concurrent + '/' + this.config.maxConcurrent + ')' };
      }
      if (s.todayPnlPct <= -this.config.maxDailyLossPct) {
        return { allow: false,
                 reason: 'Daily loss cap hit (' + s.todayPnlPct.toFixed(1) + '% ≤ -' + this.config.maxDailyLossPct + '%)' };
      }
      if (s.drawdownPct >= this.config.maxDrawdownPct) {
        return { allow: false,
                 reason: 'Drawdown cap hit (' + s.drawdownPct.toFixed(1) + '% ≥ ' + this.config.maxDrawdownPct + '%)' };
      }
      var cooldown = this.config.cooldownSeconds - (Date.now() - this._lastOpenAt) / 1000;
      if (cooldown > 0) {
        return { allow: false,
                 reason: 'Cooldown: wait ' + Math.ceil(cooldown) + 's between opens' };
      }
      return { allow: true, reason: 'ok', stats: s };
    },

    // Mark that a position was opened — enforces cooldown
    markOpened: function () { this._lastOpenAt = Date.now(); }
  };
  portfolioRisk.loadConfig();


  // ═══════════════════════════════════════════════════════════════════════
  // 8. GEX (Gamma Exposure) ANALYZER
  // ═══════════════════════════════════════════════════════════════════════
  // Reads dealer gamma exposure from backend response. Identifies:
  //   - Flip level (above = bullish acceleration, below = bearish acceleration)
  //   - Call wall (heaviest positive GEX = resistance where dealers sell rallies)
  //   - Put wall (heaviest negative GEX = support where dealers buy dips)
  //   - Regime: POSITIVE (pinned/range) vs NEGATIVE (breakout/gamma scalping)
  //
  // The backend's /api/options-quick response includes a `gex` object with
  // { total, regime, topStrikes:[{strike,gex}], flipPoint, callWall, putWall }.
  var gexAnalyzer = {
    // Normalize raw gex data from backend. Returns null if missing.
    read: function (raw) {
      if (!raw || !raw.gex) return null;
      var g = raw.gex;
      if (!Array.isArray(g.topStrikes) || g.topStrikes.length === 0) return null;
      return {
        total: g.total || 0,
        regime: g.regime || 'NEUTRAL',
        flip: g.flipPoint || 0,
        callWall: g.callWall || 0,
        putWall: g.putWall || 0,
        topStrikes: g.topStrikes.slice()  // copy
      };
    },

    // Given raw, return a trading action tag:
    //   BREAKOUT (negative GEX — dealers amplify moves) — favor directional trades
    //   RANGE    (positive GEX — dealers dampen moves) — avoid breakouts
    //   NEUTRAL  (no data)
    actionTag: function (raw) {
      var g = this.read(raw);
      if (!g) return { tag: 'NEUTRAL', color: '#64748B', action: 'GEX unavailable' };
      if (g.regime === 'NEGATIVE') {
        return { tag: 'BREAKOUT', color: '#EF4444',
                 action: 'Dealers amplify moves · prefer directional trades' };
      }
      if (g.regime === 'POSITIVE') {
        return { tag: 'RANGE', color: '#22C55E',
                 action: 'Market pinned by gamma · avoid breakouts' };
      }
      return { tag: 'NEUTRAL', color: '#64748B', action: 'Mixed GEX regime' };
    },

    // Given spot, find zone relative to flip
    zone: function (raw, spot) {
      var g = this.read(raw);
      if (!g || !g.flip || !spot) return null;
      return {
        aboveFlip: spot > g.flip,
        distance: spot - g.flip,
        distancePct: ((spot - g.flip) / g.flip) * 100
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 9. STRIKE SELECTOR
  // ═══════════════════════════════════════════════════════════════════════
  // Given a chain of nearby strikes, ranks them by tradability.
  // Score = liquidity (OI+volume) × 0.4 + delta-fit × 0.3 + spread × 0.3.
  // "Delta fit" prefers ~0.50 for ATM (max gamma/liquidity), ~0.30-0.35 for
  // 1-OTM (cheaper entry, good on expiry days).
  var strikeSelector = {
    // Candidates: {strike, ce_ltp, pe_ltp, ce_oi, pe_oi, ce_vol, pe_vol}[]
    // side: 'CE' or 'PE'
    // atm: real ATM strike
    // Returns array of { strike, label, premium, score, reason } sorted by score desc.
    rank: function (chain, atm, spot, side, strikeStep) {
      if (!Array.isArray(chain) || chain.length === 0 || !atm) return [];
      var stepAbs = strikeStep || (chain.length >= 2
        ? Math.abs(chain[1].strike - chain[0].strike) : 1);
      var results = [];

      chain.forEach(function (row) {
        var premium = side === 'CE' ? row.ce_ltp : row.pe_ltp;
        var oi = side === 'CE' ? (row.ce_oi || 0) : (row.pe_oi || 0);
        var vol = side === 'CE' ? (row.ce_vol || 0) : (row.pe_vol || 0);
        if (!premium || premium <= 0) return;

        var distance = (row.strike - atm) / stepAbs;
        var label;
        if (Math.abs(distance) < 0.5) label = 'ATM';
        else if (side === 'CE' && distance < 0) label = Math.abs(Math.round(distance)) + '-ITM';
        else if (side === 'CE' && distance > 0) label = Math.abs(Math.round(distance)) + '-OTM';
        else if (side === 'PE' && distance > 0) label = Math.abs(Math.round(distance)) + '-ITM';
        else label = Math.abs(Math.round(distance)) + '-OTM';

        // Liquidity score: log-normalized OI+vol
        var liq = Math.log10(Math.max(1, oi + vol));
        var liqScore = Math.min(100, liq * 20);

        // Delta-fit proxy: distance from ATM (closer = higher score)
        var distScore;
        if (label === 'ATM') distScore = 100;
        else if (Math.abs(distance) < 1.5) distScore = 80;
        else if (Math.abs(distance) < 2.5) distScore = 60;
        else distScore = 30;

        // Premium-sanity: reject absurdly cheap (<0.5) or wide strikes
        if (premium < 0.5) return;

        var score = Math.round(liqScore * 0.5 + distScore * 0.5);
        var reason = label === 'ATM'
          ? 'Highest gamma, tightest spread'
          : (label.indexOf('OTM') >= 0
              ? 'Cheaper entry, lower break-even probability'
              : 'In-the-money, higher delta');

        results.push({
          strike: row.strike, label: label, premium: premium,
          oi: oi, volume: vol, score: score, reason: reason,
          side: side
        });
      });

      results.sort(function (a, b) { return b.score - a.score; });
      return results;
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 10. TRADE MONITOR (live P&L for active paper positions)
  // ═══════════════════════════════════════════════════════════════════════
  // Reads from paperPortfolio and presents real-time view of active positions
  // with progress bar between SL and target. Also computes elapsed time.
  var tradeMonitor = {
    // Returns array of active/pending positions, each with live stats.
    // Uses `priceLookup` (map of tradeId -> current trade object) for live premium.
    active: function (priceLookup) {
      priceLookup = priceLookup || {};
      var out = [];
      for (var id in paperPortfolio.positions) {
        var p = paperPortfolio.positions[id];
        if (p.status !== 'pending' && p.status !== 'active') continue;

        var live = priceLookup[p.tradeId];
        var currentPrem = live ? live.price : p.entryPremium;
        var pctChg = ((currentPrem - p.entryPremium) / p.entryPremium) * 100;
        var lots = p.sizingLots || p.lot || 1;
        var pnlRupees = (currentPrem - p.entryPremium) * lots * (p.lot || 1);

        // Progress: 0 at SL, 50 at entry, 100 at target
        var progress;
        var range = p.target - p.sl;
        if (range > 0) {
          progress = Math.max(0, Math.min(100,
            ((currentPrem - p.sl) / range) * 100));
        } else {
          progress = 50;
        }

        var elapsedMs = Date.now() - p.openedAt;
        var elapsedMin = Math.floor(elapsedMs / 60000);
        var elapsedSec = Math.floor((elapsedMs % 60000) / 1000);

        out.push({
          id: p.id, sym: p.sym, strike: p.strike, side: p.side, status: p.status,
          entryPremium: p.entryPremium, currentPremium: currentPrem,
          sl: p.sl, target: p.target, pctChg: pctChg, pnlRupees: pnlRupees,
          progress: progress, lots: lots, currency: p.currency,
          elapsedMin: elapsedMin, elapsedSec: elapsedSec,
          highWater: p.highWater, lowWater: p.lowWater
        });
      }
      return out;
    },

    // Manually close an active position at current premium (user-initiated)
    closeNow: function (id, exitPremium, reason) {
      var p = paperPortfolio.positions[id];
      if (!p || (p.status !== 'active' && p.status !== 'pending')) return false;
      p.status = exitPremium >= p.entryPremium ? 'won' : 'lost';
      p.closedAt = Date.now();
      p.exitPremium = exitPremium;
      p.realizedPct = ((exitPremium - p.entryPremium) / p.entryPremium) * 100;
      p.closeReason = reason || 'manual_close';
      paperPortfolio.save();
      bus.emit('position:closed', p);
      return true;
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 11. TREND COMPASS (long-term vs short-term alignment)
  // ═══════════════════════════════════════════════════════════════════════
  // Compares SHORT-TERM intraday structure (HH-HL on last 5 5m bars + VWAP
  // position) against LONG-TERM daily trend (SMA200/400 if available).
  // User sees immediately whether their intraday signal aligns with the
  // daily trend — strong alignment = higher conviction trade.
  var trendCompass = {
    // Reads spot + bars + daily_trend from raw response.
    // Returns { shortTerm: BULLISH|BEARISH|NEUTRAL, longTerm: ..., aligned, conflict, detail }
    analyze: function (raw) {
      if (!raw) return { status: 'no_data' };
      var spot = raw.spot || 0;
      var bars = raw.ohlc_bars || [];
      if (!spot) return { status: 'no_spot' };

      // LONG TERM: SMA200/400 from daily_trend if backend provides
      var lt = 'NEUTRAL', ltReason = 'No daily data';
      var dt = raw.daily_trend || null;
      var sma200 = dt && dt.sma200 ? dt.sma200 : 0;
      var sma400 = dt && dt.sma400 ? dt.sma400 : 0;
      if (sma200 > 0) {
        if (spot > sma200 && (sma400 === 0 || spot > sma400)) {
          lt = 'BULLISH';
          ltReason = 'Spot > SMA200' + (sma400 ? ' + SMA400' : '');
        } else if (spot < sma200 && (sma400 === 0 || spot < sma400)) {
          lt = 'BEARISH';
          ltReason = 'Spot < SMA200' + (sma400 ? ' + SMA400' : '');
        } else {
          ltReason = 'Mixed SMA position';
        }
      }

      // SHORT TERM: HH-HL structure + VWAP position on last 5 5m bars
      var st = 'NEUTRAL', stReason = 'Insufficient bars';
      var vwapPos = '', structure = '';
      if (bars.length >= 3) {
        // Real VWAP from bars (don't trust backend vwap alone)
        var vn = 0, vd = 0;
        bars.forEach(function (b) {
          if (b.h != null && b.l != null && b.c != null) {
            var tp = (b.h + b.l + b.c) / 3;
            var v = b.v || 1;
            vn += tp * v; vd += v;
          }
        });
        var barVwap = vd > 0 ? (vn / vd) : (raw.vwap || spot);
        var aboveVwap = spot > barVwap;
        vwapPos = aboveVwap ? 'Above VWAP' : 'Below VWAP';

        var recent = bars.slice(-5);
        var hh = 0, hl = 0, lh = 0, ll = 0;
        for (var i = 1; i < recent.length; i++) {
          if (recent[i].h != null && recent[i - 1].h != null) {
            if (recent[i].h > recent[i - 1].h) hh++;
            else if (recent[i].h < recent[i - 1].h) lh++;
          }
          if (recent[i].l != null && recent[i - 1].l != null) {
            if (recent[i].l > recent[i - 1].l) hl++;
            else if (recent[i].l < recent[i - 1].l) ll++;
          }
        }
        var bullStruct = hh >= 2 && hl >= 2;
        var bearStruct = lh >= 2 && ll >= 2;
        structure = bullStruct ? 'HH-HL' : bearStruct ? 'LH-LL' : 'Mixed';

        if (aboveVwap && bullStruct) { st = 'BULLISH'; stReason = 'HH-HL + above VWAP'; }
        else if (!aboveVwap && bearStruct) { st = 'BEARISH'; stReason = 'LH-LL + below VWAP'; }
        else if (aboveVwap && !bearStruct) { st = 'BULLISH'; stReason = 'Above VWAP, weak structure'; }
        else if (!aboveVwap && !bullStruct) { st = 'BEARISH'; stReason = 'Below VWAP, weak structure'; }
        else { stReason = vwapPos + ', ' + structure; }
      }

      var aligned = lt === st && lt !== 'NEUTRAL';
      var conflict = lt !== 'NEUTRAL' && st !== 'NEUTRAL' && lt !== st;

      return {
        status: 'ok',
        shortTerm: st, shortReason: stReason,
        longTerm: lt, longReason: ltReason,
        vwapPos: vwapPos, structure: structure,
        aligned: aligned, conflict: conflict,
        sma200: sma200, sma400: sma400,
        spot: spot
      };
    },

    // Conviction modifier: aligned = +1 (higher conviction),
    // conflict = -1 (dial back), neutral = 0
    convictionModifier: function (raw) {
      var a = this.analyze(raw);
      if (a.status !== 'ok') return 0;
      if (a.aligned) return 1;
      if (a.conflict) return -1;
      return 0;
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 12. CONSENSUS ENGINE — combines all module outputs into ONE verdict
  // ═══════════════════════════════════════════════════════════════════════
  // This is the layer that makes the product actually useful as a guide.
  // Instead of showing 6 separate chips (score, regime, alpha, GEX, compass,
  // IV/HV) and making the user synthesize them, we produce ONE verdict:
  //
  //   STRONG_BUY  — all signals aligned, take full Kelly size
  //   BUY         — most signals aligned, take reduced size
  //   NEUTRAL     — mixed signals, wait or take 1/4 size
  //   AVOID       — one or more hard-stop signals (negative edge, alpha
  //                 decayed, portfolio risk blocked, regime volatile)
  //
  // The verdict includes:
  //   - Action (with size recommendation as % of normal Kelly)
  //   - Reasons: list of bullets, each showing which module drove the call
  //   - Warnings: softer concerns
  //   - Blockers: hard-stops that flip to AVOID
  // ═══════════════════════════════════════════════════════════════════════
  // 12. PRICE ACTION ANALYZER (Smart Money Concepts)
  // ═══════════════════════════════════════════════════════════════════════
  // Adds institutional-grade price-action reads that the 6-factor base
  // engine does NOT cover:
  //
  //   - FVG (Fair Value Gap): 3-candle imbalance where middle candle's range
  //     doesn't overlap with candles N-2 and N (bullish FVG or bearish FVG).
  //     Untested price → magnet for future retests.
  //   - Order Block: last opposing candle before an impulsive move. Institutions
  //     defend these levels on retests.
  //   - BOS (Break of Structure): price breaks the prior swing high/low in
  //     the direction of the trend. Confirms continuation.
  //   - CHoCH (Change of Character): first lower-high in an uptrend or first
  //     higher-low in a downtrend. Early reversal signal.
  //   - Liquidity Sweep: spike beyond prior swing high/low that IMMEDIATELY
  //     reverses — institutional stop-hunt followed by genuine move.
  //   - EMA Structure: 9/21/50 ordering. Stacked bullish = 9>21>50>spot-above.
  //   - Candle Closure: 5m close strength — body size vs range, wick rejection.
  //
  // All checks return null when there's insufficient data (not fake values).
  var priceAction = {
    // ── FVG (Fair Value Gap) on last N candles ──────────────────────
    // Returns array of gaps ordered by recency: [{type, top, bottom, barIdx}]
    fvg: function (bars, lookback) {
      if (!Array.isArray(bars) || bars.length < 3) return [];
      lookback = Math.min(lookback || 20, bars.length);
      var gaps = [];
      var start = Math.max(2, bars.length - lookback);
      for (var i = start; i < bars.length; i++) {
        var b0 = bars[i - 2], b1 = bars[i - 1], b2 = bars[i];
        if (!b0 || !b1 || !b2 || b0.h == null || b2.l == null) continue;
        // Bullish FVG: b0.high < b2.low — price gapped up, leaving imbalance
        if (b0.h < b2.l) {
          gaps.push({ type: 'BULL', top: b2.l, bottom: b0.h, barIdx: i });
        }
        // Bearish FVG: b0.low > b2.high — gapped down
        if (b0.l > b2.h) {
          gaps.push({ type: 'BEAR', top: b0.l, bottom: b2.h, barIdx: i });
        }
      }
      return gaps;
    },

    // Is current spot inside (or close to) any unfilled FVG?
    // Returns { inFvg: true/false, type, distance (0 = inside) }
    spotNearFvg: function (bars, spot) {
      var gaps = this.fvg(bars, 20);
      if (gaps.length === 0 || !spot) return { inFvg: false };
      // Look at most recent 5 gaps
      var recent = gaps.slice(-5);
      for (var i = recent.length - 1; i >= 0; i--) {
        var g = recent[i];
        if (spot >= g.bottom && spot <= g.top) {
          return { inFvg: true, type: g.type, top: g.top, bottom: g.bottom, distance: 0 };
        }
      }
      return { inFvg: false };
    },

    // ── ORDER BLOCK ──────────────────────────────────────────────
    // Last BEARISH candle before a sharp bullish push = bullish order block (support)
    // Last BULLISH candle before a sharp bearish push = bearish order block (resistance)
    // Requires 3+ bars following with net move > 1.5× avg range.
    orderBlock: function (bars) {
      if (!Array.isArray(bars) || bars.length < 6) return null;
      var avgRange = 0;
      for (var i = 0; i < bars.length; i++) {
        if (bars[i].h != null && bars[i].l != null) {
          avgRange += (bars[i].h - bars[i].l);
        }
      }
      avgRange /= bars.length;
      if (avgRange <= 0) return null;

      // Scan last 15 bars for order blocks
      var start = Math.max(0, bars.length - 15);
      var latestBull = null, latestBear = null;
      for (var i = start; i < bars.length - 3; i++) {
        var b = bars[i];
        if (b.o == null || b.c == null) continue;
        // Check the 3-bar push after this one
        var afterStart = bars[i + 1], afterEnd = bars[i + 3];
        if (!afterStart || !afterEnd) continue;
        var pushMove = afterEnd.c - afterStart.o;
        var pushMag = Math.abs(pushMove);
        if (pushMag < avgRange * 1.5) continue;

        // Bullish order block: bearish candle followed by strong up push
        if (b.c < b.o && pushMove > 0) {
          latestBull = { type: 'BULL_OB', top: b.h, bottom: b.l, barIdx: i, pushMag: pushMag };
        }
        // Bearish order block: bullish candle followed by strong down push
        if (b.c > b.o && pushMove < 0) {
          latestBear = { type: 'BEAR_OB', top: b.h, bottom: b.l, barIdx: i, pushMag: pushMag };
        }
      }
      return { bull: latestBull, bear: latestBear };
    },

    // ── BOS / CHoCH ──────────────────────────────────────────────
    // Detect structure breaks by comparing last bar close to prior swing highs/lows
    bosChoch: function (bars) {
      if (!Array.isArray(bars) || bars.length < 10) return null;
      // Simple swing detection: pivot if higher/lower than 2 bars each side
      var swings = [];
      for (var i = 2; i < bars.length - 2; i++) {
        var b = bars[i];
        if (b.h == null || b.l == null) continue;
        var isHigh = b.h > bars[i-1].h && b.h > bars[i-2].h &&
                     b.h > bars[i+1].h && b.h > bars[i+2].h;
        var isLow = b.l < bars[i-1].l && b.l < bars[i-2].l &&
                    b.l < bars[i+1].l && b.l < bars[i+2].l;
        if (isHigh) swings.push({ type: 'HIGH', price: b.h, barIdx: i });
        if (isLow)  swings.push({ type: 'LOW', price: b.l, barIdx: i });
      }
      if (swings.length < 2) return null;

      // Determine prior structure direction
      var recent = swings.slice(-4);
      var highs = recent.filter(function(s){return s.type==='HIGH';}).map(function(s){return s.price;});
      var lows  = recent.filter(function(s){return s.type==='LOW';}).map(function(s){return s.price;});

      var lastBar = bars[bars.length - 1];
      var currentClose = lastBar.c;

      var lastHigh = highs.length > 0 ? highs[highs.length - 1] : null;
      var lastLow  = lows.length > 0 ? lows[lows.length - 1] : null;

      // BOS: break prior high in uptrend / break prior low in downtrend
      //       (only needs ONE prior swing high to break above)
      // CHoCH: break opposite swing, which requires 2 highs (or 2 lows) to
      //        detect the lower-high/higher-low reversal pattern.
      var signals = [];
      if (highs.length >= 1 && lastHigh && currentClose > lastHigh) {
        if (highs.length >= 2) {
          var priorHigh = highs[highs.length - 2];
          if (lastHigh < priorHigh) signals.push({ type: 'CHoCH_BULL', level: lastHigh });
          else signals.push({ type: 'BOS_BULL', level: lastHigh });
        } else {
          // Only one prior swing high — break above is BOS bull
          signals.push({ type: 'BOS_BULL', level: lastHigh });
        }
      }
      if (lows.length >= 1 && lastLow && currentClose < lastLow) {
        if (lows.length >= 2) {
          var priorLow = lows[lows.length - 2];
          if (lastLow > priorLow) signals.push({ type: 'CHoCH_BEAR', level: lastLow });
          else signals.push({ type: 'BOS_BEAR', level: lastLow });
        } else {
          signals.push({ type: 'BOS_BEAR', level: lastLow });
        }
      }
      return { signals: signals, swings: swings.slice(-4) };
    },

    // ── LIQUIDITY SWEEP ──────────────────────────────────────────
    // Price spikes BEYOND prior swing high/low, then closes back INSIDE.
    // Classic stop-hunt pattern.
    liquiditySweep: function (bars) {
      if (!Array.isArray(bars) || bars.length < 8) return null;
      var last = bars[bars.length - 1];
      if (last.h == null || last.l == null || last.c == null) return null;

      // Find highest high / lowest low of prior 7 bars (exclude current)
      var priorHigh = -Infinity, priorLow = Infinity;
      for (var i = bars.length - 8; i < bars.length - 1; i++) {
        if (bars[i].h != null && bars[i].h > priorHigh) priorHigh = bars[i].h;
        if (bars[i].l != null && bars[i].l < priorLow) priorLow = bars[i].l;
      }

      var sweeps = [];
      // Bull sweep: wick LOW went below priorLow but close held ABOVE priorLow
      if (last.l < priorLow && last.c > priorLow) {
        sweeps.push({ type: 'BULL_SWEEP', level: priorLow,
                      wickDepth: priorLow - last.l,
                      closeStrength: last.c - priorLow });
      }
      // Bear sweep: wick HIGH went above priorHigh but close held BELOW priorHigh
      if (last.h > priorHigh && last.c < priorHigh) {
        sweeps.push({ type: 'BEAR_SWEEP', level: priorHigh,
                      wickDepth: last.h - priorHigh,
                      closeStrength: priorHigh - last.c });
      }
      return sweeps.length > 0 ? sweeps : null;
    },

    // ── EMA STRUCTURE ────────────────────────────────────────────
    // Computes EMA 9/21/50 on close prices. Returns alignment:
    //   STACKED_BULL: 9 > 21 > 50 and spot > 9
    //   STACKED_BEAR: 9 < 21 < 50 and spot < 9
    //   MIXED: anything else
    ema: function (bars) {
      if (!Array.isArray(bars) || bars.length < 50) return null;
      var closes = bars.map(function(b){return b.c;}).filter(function(c){return c != null;});
      if (closes.length < 50) return null;

      function computeEma(arr, period) {
        var k = 2 / (period + 1);
        var e = arr[0];
        for (var i = 1; i < arr.length; i++) e = arr[i] * k + e * (1 - k);
        return e;
      }

      var ema9 = computeEma(closes.slice(-30), 9);
      var ema21 = computeEma(closes.slice(-50), 21);
      var ema50 = computeEma(closes, 50);
      var spot = closes[closes.length - 1];

      var alignment;
      if (ema9 > ema21 && ema21 > ema50 && spot > ema9) alignment = 'STACKED_BULL';
      else if (ema9 < ema21 && ema21 < ema50 && spot < ema9) alignment = 'STACKED_BEAR';
      else alignment = 'MIXED';

      return { ema9: ema9, ema21: ema21, ema50: ema50, spot: spot, alignment: alignment };
    },

    // ── 5M CANDLE CLOSURE STRENGTH ───────────────────────────────
    // Analyzes the just-closed 5m candle for:
    //   - body% of range (strong close > 70%)
    //   - upper/lower wick rejection (wick > 60% = rejection)
    //   - direction
    candleClosure: function (bars) {
      if (!Array.isArray(bars) || bars.length < 1) return null;
      var b = bars[bars.length - 1];
      if (b.o == null || b.c == null || b.h == null || b.l == null) return null;
      var range = b.h - b.l;
      if (range <= 0) return { strength: 'DOJI', direction: 'NEUTRAL', bodyPct: 0 };
      var body = Math.abs(b.c - b.o);
      var bodyPct = (body / range) * 100;
      var upperWick = b.h - Math.max(b.o, b.c);
      var lowerWick = Math.min(b.o, b.c) - b.l;
      var upperWickPct = (upperWick / range) * 100;
      var lowerWickPct = (lowerWick / range) * 100;
      var direction = b.c > b.o ? 'BULL' : b.c < b.o ? 'BEAR' : 'NEUTRAL';

      var strength;
      if (bodyPct >= 70) strength = 'STRONG';
      else if (bodyPct >= 50) strength = 'MODERATE';
      else if (bodyPct < 25) strength = 'INDECISION';
      else strength = 'MIXED';

      var wickSignal = null;
      if (upperWickPct >= 60) wickSignal = 'UPPER_REJECTION';  // bearish
      else if (lowerWickPct >= 60) wickSignal = 'LOWER_REJECTION';  // bullish

      return {
        direction: direction, strength: strength, bodyPct: bodyPct,
        upperWickPct: upperWickPct, lowerWickPct: lowerWickPct,
        wickSignal: wickSignal
      };
    },

    // ── ONE-CALL SUMMARY ─────────────────────────────────────────
    // Returns structured analysis of all SMC signals for the consensus engine
    analyze: function (raw) {
      if (!raw || !Array.isArray(raw.ohlc_bars) || raw.ohlc_bars.length < 3) {
        return { status: 'no_data' };
      }
      var bars = raw.ohlc_bars;
      var spot = raw.spot;
      return {
        status: 'ok',
        fvg: this.fvg(bars),
        nearFvg: this.spotNearFvg(bars, spot),
        orderBlock: this.orderBlock(bars),
        bosChoch: this.bosChoch(bars),
        liquiditySweep: this.liquiditySweep(bars),
        ema: this.ema(bars),
        candle: this.candleClosure(bars)
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 13. EXTERNAL FEEDS (GIFT NIFTY · US premarket · India VIX TS · Order flow)
  // ═══════════════════════════════════════════════════════════════════════
  // Reads pre-open / global-cue data from backend endpoints so the consensus
  // engine knows whether the wider market is risk-on or risk-off. These
  // caches are populated by polling the endpoints — missing data degrades
  // gracefully without fake values.
  var externalFeeds = {
    cache: {
      gift: null,        // /api/gift-nifty response
      usPre: null,       // /api/us-premarket response
      lastGiftFetch: 0,
      lastUsFetch: 0,
      giftTTL: 300000,   // 5 minutes — matches server cache
      usTTL: 60000       // 1 minute
    },

    // Fetch GIFT NIFTY + India global cues. Only applicable when region=IN.
    // Safe to call repeatedly — respects local TTL.
    fetchGift: function () {
      var self = this;
      var now = Date.now();
      if (self.cache.gift && (now - self.cache.lastGiftFetch) < self.cache.giftTTL) {
        return Promise.resolve(self.cache.gift);
      }
      if (typeof fetch !== 'function') return Promise.resolve(null);
      return fetch('/api/gift-nifty')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data && data.success) {
            self.cache.gift = data;
            self.cache.lastGiftFetch = now;
          }
          return data;
        })
        .catch(function () { return null; });
    },

    // US premarket — only relevant when region=US
    fetchUsPre: function () {
      var self = this;
      var now = Date.now();
      if (self.cache.usPre && (now - self.cache.lastUsFetch) < self.cache.usTTL) {
        return Promise.resolve(self.cache.usPre);
      }
      if (typeof fetch !== 'function') return Promise.resolve(null);
      return fetch('/api/us-premarket')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data && data.success) {
            self.cache.usPre = data;
            self.cache.lastUsFetch = now;
          }
          return data;
        })
        .catch(function () { return null; });
    },

    // Cached reads — return what was last fetched (null if nothing yet)
    gift: function () { return this.cache.gift; },
    usPre: function () { return this.cache.usPre; },

    // Interpret GIFT NIFTY data for consensus use.
    // Returns { status, gap, sentiment, reason } or { status:'no_data' }
    giftReport: function () {
      var g = this.cache.gift;
      if (!g || !g.success) return { status: 'no_data' };
      var gap = g.gift_gap_pct || 0;
      var sentiment = g.overall_sentiment || 'NEUTRAL';
      var label;
      if (gap >= 0.5) label = 'STRONG_GAP_UP';
      else if (gap >= 0.15) label = 'GAP_UP';
      else if (gap <= -0.5) label = 'STRONG_GAP_DOWN';
      else if (gap <= -0.15) label = 'GAP_DOWN';
      else label = 'FLAT';
      return {
        status: 'ok',
        gap: gap,
        giftPrice: g.gift_nifty || 0,
        niftyClose: g.nifty_close || 0,
        sentiment: sentiment,
        label: label,
        source: g.gift_source || '',
        vix: (g.global_cues && g.global_cues.india_vix && g.global_cues.india_vix.price) || 0,
        vixChange: (g.global_cues && g.global_cues.india_vix && g.global_cues.india_vix.change) || 0
      };
    },

    usPreReport: function () {
      var u = this.cache.usPre;
      if (!u || !u.success) return { status: 'no_data' };
      var gap = u.expected_gap_pct || 0;
      var label;
      if (gap >= 0.5) label = 'STRONG_GAP_UP';
      else if (gap >= 0.15) label = 'GAP_UP';
      else if (gap <= -0.5) label = 'STRONG_GAP_DOWN';
      else if (gap <= -0.15) label = 'GAP_DOWN';
      else label = 'FLAT';
      return {
        status: 'ok',
        gap: gap,
        sentiment: u.overall_sentiment || 'NEUTRAL',
        label: label,
        spFutChange: (u.sp500_fut && u.sp500_fut.change) || 0,
        nqFutChange: (u.nasdaq_fut && u.nasdaq_fut.change) || 0,
        vix: (u.vix && u.vix.price) || 0,
        vixChange: (u.vix && u.vix.change) || 0
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 14. IV TERM STRUCTURE ANALYZER
  // ═══════════════════════════════════════════════════════════════════════
  // Reads `iv_term_structure` from options-quick backend response. Classifies
  // the curve shape to inform consensus:
  //   NORMAL    — longer-dated IV > near-dated (contango; fair pricing)
  //   FLAT      — all tenors within ~2% (stable expectations)
  //   INVERTED  — near-dated IV > longer-dated (event risk priced in near term)
  //   HUMPED    — mid-tenor spike (specific event expected, e.g. earnings)
  var ivTermStructure = {
    // Backend format: iv_term_structure is typically a list of
    //   [{expiry: 'YYYY-MM-DD', dte: N, atm_iv: 15.3}, ...] sorted by DTE
    // or may just be an object with weekly/monthly IVs. Defensive reader.
    analyze: function (raw) {
      if (!raw) return { status: 'no_data' };
      var ts = raw.iv_term_structure;
      if (!ts) return { status: 'no_data' };

      // Normalize to { dte, iv } pairs
      var points = [];
      if (Array.isArray(ts)) {
        ts.forEach(function (p) {
          if (p && p.dte != null && (p.atm_iv != null || p.iv != null)) {
            points.push({ dte: +p.dte, iv: +(p.atm_iv != null ? p.atm_iv : p.iv) });
          }
        });
      } else if (typeof ts === 'object') {
        // Object form: { weekly: {dte, iv}, monthly: {dte, iv} }
        for (var k in ts) {
          var v = ts[k];
          if (v && v.dte != null && (v.atm_iv != null || v.iv != null)) {
            points.push({ dte: +v.dte, iv: +(v.atm_iv != null ? v.atm_iv : v.iv) });
          }
        }
      }
      if (points.length < 2) return { status: 'insufficient' };

      points.sort(function (a, b) { return a.dte - b.dte; });

      // Classification
      var near = points[0];
      var far = points[points.length - 1];
      var spread = ((far.iv - near.iv) / Math.max(near.iv, 0.01)) * 100;

      var shape;
      if (Math.abs(spread) < 2) shape = 'FLAT';
      else if (spread > 5) shape = 'NORMAL';       // contango
      else if (spread < -5) shape = 'INVERTED';    // backwardation
      else shape = 'FLAT';

      // Check for humped (middle tenor much higher than both ends)
      if (points.length >= 3) {
        var mid = points[Math.floor(points.length / 2)];
        var endsAvg = (near.iv + far.iv) / 2;
        if (mid.iv > endsAvg * 1.1) shape = 'HUMPED';
      }

      return {
        status: 'ok',
        shape: shape,
        nearIv: near.iv, nearDte: near.dte,
        farIv: far.iv, farDte: far.dte,
        spread: spread,
        points: points
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 15. ORDER FLOW ANALYZER
  // ═══════════════════════════════════════════════════════════════════════
  // Reads bid/ask from the option chain to detect:
  //   - Tight spread (<1%) = liquid, institutional participation
  //   - Wide spread (>5%) = illiquid, retail-dominated, avoid
  //   - Mid-price skew: if premium is closer to ask, buyer aggression;
  //     closer to bid, seller aggression. Rough proxy — true order flow
  //     requires tape/time&sales which we don't have.
  var orderFlow = {
    // row = chain_near_atm row; side = 'CE'|'PE'
    readRow: function (row, side) {
      if (!row) return null;
      var bid = side === 'CE' ? row.ce_bid : row.pe_bid;
      var ask = side === 'CE' ? row.ce_ask : row.pe_ask;
      var ltp = side === 'CE' ? row.ce_ltp : row.pe_ltp;
      if (bid == null || ask == null || !bid || !ask || !ltp) return null;
      var mid = (bid + ask) / 2;
      var spreadAbs = ask - bid;
      var spreadPct = (spreadAbs / Math.max(mid, 0.01)) * 100;

      // Liquidity tier
      var liquidity;
      if (spreadPct < 1) liquidity = 'TIGHT';
      else if (spreadPct < 3) liquidity = 'NORMAL';
      else if (spreadPct < 7) liquidity = 'WIDE';
      else liquidity = 'VERY_WIDE';

      // Aggression proxy
      var aggression = 'NEUTRAL';
      if (ltp > mid + spreadAbs * 0.25) aggression = 'BUYER';
      else if (ltp < mid - spreadAbs * 0.25) aggression = 'SELLER';

      return {
        bid: bid, ask: ask, ltp: ltp, mid: mid,
        spreadAbs: spreadAbs, spreadPct: spreadPct,
        liquidity: liquidity, aggression: aggression
      };
    },

    // Summarize order flow around ATM — reads 3 strikes nearest spot.
    summary: function (raw, atmStrike, side) {
      if (!raw || !Array.isArray(raw.chain_near_atm) || !atmStrike) {
        return { status: 'no_data' };
      }
      // Find rows near ATM
      var nearRows = raw.chain_near_atm.filter(function (r) {
        return Math.abs(r.strike - atmStrike) < atmStrike * 0.01;
      });
      if (nearRows.length === 0) return { status: 'no_atm_row' };

      var reads = [];
      nearRows.forEach(function (r) {
        var x = orderFlow.readRow(r, side);
        if (x) {
          x.strike = r.strike;
          reads.push(x);
        }
      });
      if (reads.length === 0) return { status: 'no_bidask' };

      // Averages
      var avgSpread = reads.reduce(function (a, b) { return a + b.spreadPct; }, 0) / reads.length;
      var buyerCount = reads.filter(function (r) { return r.aggression === 'BUYER'; }).length;
      var sellerCount = reads.filter(function (r) { return r.aggression === 'SELLER'; }).length;

      var dominantLiq;
      if (avgSpread < 1) dominantLiq = 'TIGHT';
      else if (avgSpread < 3) dominantLiq = 'NORMAL';
      else if (avgSpread < 7) dominantLiq = 'WIDE';
      else dominantLiq = 'VERY_WIDE';

      var flow;
      if (buyerCount > sellerCount) flow = 'BUYER_AGGRESSION';
      else if (sellerCount > buyerCount) flow = 'SELLER_AGGRESSION';
      else flow = 'BALANCED';

      return {
        status: 'ok',
        reads: reads,
        avgSpreadPct: avgSpread,
        liquidity: dominantLiq,
        flow: flow
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 12B. CONSENSUS ENGINE — updated to include Smart Money Concepts
  // ═══════════════════════════════════════════════════════════════════════
  var consensusEngine = {
    // Aggregate all available module outputs for a single trade
    // Returns { verdict, sizeMultiplier, reasons, warnings, blockers, score }
    evaluate: function (trade, raw) {
      raw = raw || (trade && trade._raw) || {};
      var reasons = [];
      var warnings = [];
      var blockers = [];
      var points = 0;  // signed score: positive = buy, negative = avoid

      // ── HARD BLOCKERS (any one → AVOID) ─────────────────────────────
      var gate = portfolioRisk.checkAllow();
      if (!gate.allow) blockers.push('Portfolio risk: ' + gate.reason);

      var decay = alphaDecay.read();
      if (decay.status === 'DECAYED') {
        blockers.push('Alpha DECAYED — engine has lost edge');
      }

      // ── SIGNED POINTS (additive — positive is pro-trade) ────────────

      // Base score (0-100, normalized to -50..+50)
      if (trade && trade.confidence) {
        var scoreContrib = (trade.confidence - 60);  // below 60 is net negative
        points += scoreContrib;
        if (trade.confidence >= 85) {
          reasons.push('Score ' + trade.confidence + ' — strong signal');
        } else if (trade.confidence >= 72) {
          reasons.push('Score ' + trade.confidence + ' — solid signal');
        } else if (trade.confidence >= 60) {
          warnings.push('Score ' + trade.confidence + ' — borderline');
        } else {
          warnings.push('Score ' + trade.confidence + ' — weak');
        }
      }

      // Regime
      var reg = regimeDetector.current;
      if (reg === 'TRENDING_UP' || reg === 'TRENDING_DN') {
        var dirMatch =
          (reg === 'TRENDING_UP' && trade && trade.side === 'CE') ||
          (reg === 'TRENDING_DN' && trade && trade.side === 'PE');
        if (dirMatch) {
          points += 10;
          reasons.push('Regime aligned with trade direction');
        } else if (trade && trade.side) {
          points -= 15;
          warnings.push('Regime is ' + reg + ' but trade is ' + trade.side);
        }
      } else if (reg === 'VOLATILE') {
        points -= 10;
        warnings.push('VOLATILE regime — size down, whipsaw risk');
      } else if (reg === 'RANGING') {
        points -= 5;
        warnings.push('RANGING regime — breakout trades may fail');
      }

      // GEX regime
      var gexTag = gexAnalyzer.actionTag(raw);
      if (gexTag.tag === 'BREAKOUT') {
        // Breakout regime favors directional trades (both CE and PE)
        points += 8;
        reasons.push('GEX: BREAKOUT regime (dealers amplify moves)');
      } else if (gexTag.tag === 'RANGE') {
        // Range regime punishes directional trades
        points -= 8;
        warnings.push('GEX: market pinned by gamma — prefer range plays');
      }

      // Trend compass alignment
      var cmp = trendCompass.analyze(raw);
      if (cmp.status === 'ok') {
        if (cmp.aligned) {
          // Side must match direction
          var cmpMatch =
            (cmp.shortTerm === 'BULLISH' && trade && trade.side === 'CE') ||
            (cmp.shortTerm === 'BEARISH' && trade && trade.side === 'PE');
          if (cmpMatch) {
            points += 12;
            reasons.push('Compass ALIGNED: ' + cmp.shortTerm + ' on both timeframes');
          }
        } else if (cmp.conflict) {
          points -= 10;
          warnings.push('Compass CONFLICT: short ' + cmp.shortTerm + ', long ' + cmp.longTerm);
        }
      }

      // IV vs HV
      var bars = raw.ohlc_bars || [];
      var atmIV = raw.atm_iv || 0;
      var ivhv = volMath.analyze(atmIV, bars);
      if (ivhv.status === 'ok') {
        if (ivhv.verdict === 'OVERPRICED') {
          points -= 8;
          warnings.push('IV ' + ivhv.ratio.toFixed(1) + '× HV — options OVERPRICED, reduce size');
        } else if (ivhv.verdict === 'ELEVATED') {
          points -= 3;
          warnings.push('IV elevated vs HV');
        } else if (ivhv.verdict === 'UNDERPRICED') {
          points += 8;
          reasons.push('IV ' + ivhv.ratio.toFixed(1) + '× HV — options UNDERPRICED, cheap');
        } else if (ivhv.verdict === 'DISCOUNTED') {
          points += 3;
        }
      }

      // Alpha decay (soft — only flag if DEGRADING; DECAYED already blocks)
      if (decay.status === 'DEGRADING') {
        points -= 5;
        warnings.push('Alpha DEGRADING — high-score signals losing edge');
      } else if (decay.status === 'HEALTHY') {
        points += 3;
      }

      // Kelly edge: if negative, block
      if (trade) {
        var sizing = kellySizer.size(trade);
        if (sizing.lots === 0) {
          blockers.push('Kelly sizing: ' + (sizing.reason || 'negative edge'));
        } else if (sizing.edge < 0.05) {
          warnings.push('Thin edge: Kelly ' + (sizing.winProb * 100).toFixed(0) +
                        '% win × ' + sizing.payoffRatio.toFixed(1) + 'R');
        } else if (sizing.edge > 0.3) {
          points += 5;
          reasons.push('Kelly edge strong (' + sizing.edge.toFixed(2) + ')');
        }
      }

      // ── SMART MONEY CONCEPTS (FVG, OB, BOS/CHoCH, sweeps, EMA, candle) ─
      // Each primitive contributes signed points AND populates reasons/warnings.
      // Direction awareness: a bullish SMC read rewards CE trades and penalizes
      // PE trades, and vice versa. If no trade.side is known, impact is halved.
      var pa = priceAction.analyze(raw);
      if (pa.status === 'ok') {
        var tradeIsCE = trade && trade.side === 'CE';
        var tradeIsPE = trade && trade.side === 'PE';

        // FVG — spot inside an unfilled imbalance is a magnet
        if (pa.nearFvg && pa.nearFvg.inFvg) {
          if (pa.nearFvg.type === 'BULL' && tradeIsCE) {
            points += 6;
            reasons.push('Spot inside bullish FVG — institutional magnet');
          } else if (pa.nearFvg.type === 'BEAR' && tradeIsPE) {
            points += 6;
            reasons.push('Spot inside bearish FVG — institutional magnet');
          } else if (pa.nearFvg.type === 'BULL' && tradeIsPE) {
            points -= 4;
            warnings.push('Spot inside bullish FVG — trade fights the magnet');
          } else if (pa.nearFvg.type === 'BEAR' && tradeIsCE) {
            points -= 4;
            warnings.push('Spot inside bearish FVG — trade fights the magnet');
          }
        }

        // Order Block — near an OB = institutional reaction likely
        if (pa.orderBlock && raw.spot) {
          var sp = raw.spot;
          var ob = pa.orderBlock;
          if (ob.bull && sp >= ob.bull.bottom && sp <= ob.bull.top * 1.005) {
            // spot at bullish OB (support zone)
            if (tradeIsCE) { points += 7; reasons.push('Spot at bullish Order Block — institutional support'); }
            else if (tradeIsPE) { points -= 5; warnings.push('Shorting into bullish Order Block — risky'); }
          }
          if (ob.bear && sp <= ob.bear.top && sp >= ob.bear.bottom * 0.995) {
            if (tradeIsPE) { points += 7; reasons.push('Spot at bearish Order Block — institutional resistance'); }
            else if (tradeIsCE) { points -= 5; warnings.push('Buying into bearish Order Block — risky'); }
          }
        }

        // BOS / CHoCH — structure break in trade direction is strong confirmation
        if (pa.bosChoch && pa.bosChoch.signals) {
          pa.bosChoch.signals.forEach(function (sig) {
            if (sig.type === 'BOS_BULL' && tradeIsCE) {
              points += 10; reasons.push('BOS bullish — structure broke above prior swing high');
            } else if (sig.type === 'BOS_BEAR' && tradeIsPE) {
              points += 10; reasons.push('BOS bearish — structure broke below prior swing low');
            } else if (sig.type === 'CHoCH_BULL' && tradeIsCE) {
              points += 12; reasons.push('CHoCH bullish — trend reversal confirmed');
            } else if (sig.type === 'CHoCH_BEAR' && tradeIsPE) {
              points += 12; reasons.push('CHoCH bearish — trend reversal confirmed');
            } else if (sig.type === 'BOS_BULL' && tradeIsPE) {
              points -= 12; warnings.push('BOS bullish against PE trade — reconsider');
            } else if (sig.type === 'BOS_BEAR' && tradeIsCE) {
              points -= 12; warnings.push('BOS bearish against CE trade — reconsider');
            }
          });
        }

        // Liquidity Sweep — institutional stop-hunt before real move
        if (pa.liquiditySweep && pa.liquiditySweep.length > 0) {
          pa.liquiditySweep.forEach(function (sw) {
            if (sw.type === 'BULL_SWEEP' && tradeIsCE) {
              points += 8; reasons.push('Bullish liquidity sweep — stops grabbed, real move starting');
            } else if (sw.type === 'BEAR_SWEEP' && tradeIsPE) {
              points += 8; reasons.push('Bearish liquidity sweep — stops grabbed, real move starting');
            } else if (sw.type === 'BULL_SWEEP' && tradeIsPE) {
              points -= 6; warnings.push('Bullish sweep detected — PE trade fights the fuel');
            } else if (sw.type === 'BEAR_SWEEP' && tradeIsCE) {
              points -= 6; warnings.push('Bearish sweep detected — CE trade fights the fuel');
            }
          });
        }

        // EMA Structure — stacked alignment strengthens directional trade
        if (pa.ema && pa.ema.alignment) {
          if (pa.ema.alignment === 'STACKED_BULL') {
            if (tradeIsCE) { points += 6; reasons.push('EMA 9>21>50 stacked bullish'); }
            else if (tradeIsPE) { points -= 8; warnings.push('EMA stacked bullish against PE trade'); }
          } else if (pa.ema.alignment === 'STACKED_BEAR') {
            if (tradeIsPE) { points += 6; reasons.push('EMA 9<21<50 stacked bearish'); }
            else if (tradeIsCE) { points -= 8; warnings.push('EMA stacked bearish against CE trade'); }
          } else {
            warnings.push('EMA structure MIXED — no clean trend');
          }
        }

        // 5m Candle Closure — strong body in trade direction confirms
        if (pa.candle) {
          var cd = pa.candle;
          if (cd.strength === 'STRONG') {
            if (cd.direction === 'BULL' && tradeIsCE) {
              points += 5; reasons.push('5m candle closed STRONG bullish (body ' + cd.bodyPct.toFixed(0) + '%)');
            } else if (cd.direction === 'BEAR' && tradeIsPE) {
              points += 5; reasons.push('5m candle closed STRONG bearish (body ' + cd.bodyPct.toFixed(0) + '%)');
            } else if (cd.direction === 'BULL' && tradeIsPE) {
              points -= 4; warnings.push('5m closed strong bullish — PE fights momentum');
            } else if (cd.direction === 'BEAR' && tradeIsCE) {
              points -= 4; warnings.push('5m closed strong bearish — CE fights momentum');
            }
          } else if (cd.strength === 'INDECISION') {
            warnings.push('5m candle INDECISION (body ' + cd.bodyPct.toFixed(0) + '%) — weak confirmation');
          }
          // Wick rejection is a contrarian signal
          if (cd.wickSignal === 'UPPER_REJECTION' && tradeIsCE) {
            points -= 5; warnings.push('Upper wick rejection — buyers failed at highs');
          } else if (cd.wickSignal === 'LOWER_REJECTION' && tradeIsPE) {
            points -= 5; warnings.push('Lower wick rejection — sellers failed at lows');
          } else if (cd.wickSignal === 'LOWER_REJECTION' && tradeIsCE) {
            points += 3; reasons.push('Lower wick rejection — dip bought');
          } else if (cd.wickSignal === 'UPPER_REJECTION' && tradeIsPE) {
            points += 3; reasons.push('Upper wick rejection — rally sold');
          }
        }
      } else {
        warnings.push('SMC data unavailable (insufficient bars)');
      }

      // ── EXTERNAL FEEDS (GIFT NIFTY / US premarket) ──────────────────
      // Only consulted during pre-open / first 30 min of session. Gap up
      // against a PE trade is a headwind; aligned gap is a tailwind.
      var tradeIsCE = trade && trade.side === 'CE';
      var tradeIsPE = trade && trade.side === 'PE';
      var region = (trade && trade._raw && trade._raw._region) || state.region || 'IN';
      var gift = region === 'IN' ? externalFeeds.giftReport() : { status: 'no_data' };
      var usPre = region === 'US' ? externalFeeds.usPreReport() : { status: 'no_data' };
      var ext = gift.status === 'ok' ? gift : (usPre.status === 'ok' ? usPre : null);

      if (ext) {
        // Gap up tailwind for CE, headwind for PE
        if (ext.label === 'STRONG_GAP_UP' || ext.label === 'GAP_UP') {
          if (tradeIsCE) {
            points += ext.label === 'STRONG_GAP_UP' ? 8 : 4;
            reasons.push((region === 'IN' ? 'GIFT NIFTY' : 'US futures') +
                         ' gap UP ' + ext.gap.toFixed(2) + '% — tailwind for CE');
          } else if (tradeIsPE) {
            points -= ext.label === 'STRONG_GAP_UP' ? 8 : 4;
            warnings.push((region === 'IN' ? 'GIFT NIFTY' : 'US futures') +
                          ' gap UP ' + ext.gap.toFixed(2) + '% against PE trade');
          }
        } else if (ext.label === 'STRONG_GAP_DOWN' || ext.label === 'GAP_DOWN') {
          if (tradeIsPE) {
            points += ext.label === 'STRONG_GAP_DOWN' ? 8 : 4;
            reasons.push((region === 'IN' ? 'GIFT NIFTY' : 'US futures') +
                         ' gap DOWN ' + ext.gap.toFixed(2) + '% — tailwind for PE');
          } else if (tradeIsCE) {
            points -= ext.label === 'STRONG_GAP_DOWN' ? 8 : 4;
            warnings.push((region === 'IN' ? 'GIFT NIFTY' : 'US futures') +
                          ' gap DOWN ' + ext.gap.toFixed(2) + '% against CE trade');
          }
        }

        // VIX context — rising VIX + directional trade = caution
        if (ext.vixChange != null && Math.abs(ext.vixChange) > 5) {
          if (ext.vixChange > 5) {
            warnings.push('VIX spiking +' + ext.vixChange.toFixed(1) + '% — elevated hedging activity');
            points -= 3;
          } else if (ext.vixChange < -5) {
            reasons.push('VIX falling ' + ext.vixChange.toFixed(1) + '% — risk-on environment');
            points += 2;
          }
        }
      }

      // ── IV TERM STRUCTURE ──────────────────────────────────────────
      var iv = ivTermStructure.analyze(raw);
      if (iv.status === 'ok') {
        if (iv.shape === 'INVERTED') {
          warnings.push('IV curve INVERTED — near-term event priced in (near ' +
                        iv.nearIv.toFixed(1) + '% vs far ' + iv.farIv.toFixed(1) + '%)');
          points -= 4;
        } else if (iv.shape === 'HUMPED') {
          warnings.push('IV curve HUMPED — specific mid-term event expected');
          points -= 2;
        } else if (iv.shape === 'NORMAL') {
          // Contango is healthy — no bonus, no penalty
        }
      }

      // ── ORDER FLOW (bid-ask spread + aggression proxy) ─────────────
      if (trade && trade.side) {
        // Extract ATM strike from trade
        var atmStrike = 0;
        if (trade.strike) {
          var m = String(trade.strike).match(/(\d+(\.\d+)?)/);
          if (m) atmStrike = parseFloat(m[1]);
        }
        if (atmStrike) {
          var flow = orderFlow.summary(raw, atmStrike, trade.side);
          if (flow.status === 'ok') {
            // Liquidity
            if (flow.liquidity === 'VERY_WIDE') {
              points -= 10;
              warnings.push('Order flow VERY WIDE spreads (' +
                            flow.avgSpreadPct.toFixed(1) + '%) — poor fill quality');
            } else if (flow.liquidity === 'WIDE') {
              points -= 4;
              warnings.push('Order flow WIDE spreads (' +
                            flow.avgSpreadPct.toFixed(1) + '%)');
            } else if (flow.liquidity === 'TIGHT') {
              points += 3;
              reasons.push('Order flow TIGHT spreads — institutional liquidity');
            }
            // Aggression
            if (flow.flow === 'BUYER_AGGRESSION' && tradeIsCE) {
              points += 4;
              reasons.push('Order flow: buyer aggression on CE');
            } else if (flow.flow === 'SELLER_AGGRESSION' && tradeIsPE) {
              points += 4;
              reasons.push('Order flow: seller aggression on PE');
            } else if (flow.flow === 'SELLER_AGGRESSION' && tradeIsCE) {
              points -= 3;
              warnings.push('Order flow: sellers dominant on CE');
            } else if (flow.flow === 'BUYER_AGGRESSION' && tradeIsPE) {
              points -= 3;
              warnings.push('Order flow: buyers dominant against PE');
            }
          }
        }
      }

      // ── VERDICT + SIZE MULTIPLIER ───────────────────────────────────
      var verdict, sizeMultiplier, color;
      if (blockers.length > 0) {
        verdict = 'AVOID';
        sizeMultiplier = 0;
        color = '#EF4444';
      } else if (points >= 35 && warnings.length <= 1) {
        verdict = 'STRONG_BUY';
        sizeMultiplier = 1.0;
        color = '#22C55E';
      } else if (points >= 18) {
        verdict = 'BUY';
        sizeMultiplier = 0.75;
        color = '#22C55E';
      } else if (points >= 5) {
        verdict = 'BUY_SMALL';
        sizeMultiplier = 0.5;
        color = '#378ADD';
      } else if (points >= -5) {
        verdict = 'NEUTRAL';
        sizeMultiplier = 0.25;
        color = '#F59E0B';
      } else {
        verdict = 'AVOID';
        sizeMultiplier = 0;
        color = '#EF4444';
      }

      return {
        verdict: verdict,
        sizeMultiplier: sizeMultiplier,
        color: color,
        points: points,
        reasons: reasons,
        warnings: warnings,
        blockers: blockers
      };
    },

    // One-line summary for the UI
    oneLine: function (verdictObj) {
      var v = verdictObj;
      var multPct = Math.round(v.sizeMultiplier * 100);
      switch (v.verdict) {
        case 'STRONG_BUY': return 'STRONG BUY — full size (' + multPct + '% of Kelly)';
        case 'BUY':        return 'BUY — ' + multPct + '% of Kelly size';
        case 'BUY_SMALL':  return 'BUY SMALL — ' + multPct + '% of Kelly, mixed signals';
        case 'NEUTRAL':    return 'NEUTRAL — consider waiting, ' + multPct + '% if must trade';
        case 'AVOID':      return 'AVOID' + (v.blockers.length ? ' (' + v.blockers[0] + ')' : '');
        default:           return v.verdict;
      }
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16. LIVE TRADE GUIDE — lifecycle re-evaluation every 5m bar
  // ═══════════════════════════════════════════════════════════════════════
  // Re-assesses every open paper position against fresh data at each 5m
  // candle close. Emits one of:
  //   CONTINUE — hold current size, signal still intact
  //   ADD      — signal strengthening, consider adding 25-50%
  //   REDUCE   — signal weakening but not broken, trim to half
  //   EXIT     — signal flipped or broken, close now
  // Each recommendation includes a plain-English reason the user can act
  // on without reading the numbers.
  //
  // This is what makes it a "live guide" instead of a static scanner.
  // Quick Trade had terse one-shot voice; we now mirror its conversational
  // style and extend it across the full position lifecycle.
  var liveTradeGuide = {
    // Per-position snapshot taken at entry time, used for drift detection
    _entrySnapshots: {},

    // Record the baseline state of a position at entry. Used to detect
    // material changes over time. Called from paperPortfolio.activate().
    recordEntry: function (positionId, tradeSnapshot) {
      this._entrySnapshots[positionId] = {
        score: tradeSnapshot.confidence,
        side: tradeSnapshot.side,
        regime: regimeDetector.current,
        entryTime: Date.now()
      };
    },

    // Clear snapshot on close
    clearEntry: function (positionId) {
      delete this._entrySnapshots[positionId];
    },

    // The core evaluator: for an active position, compare current signals
    // vs entry snapshot and current market state. Returns:
    //   { action: 'CONTINUE'|'ADD'|'REDUCE'|'EXIT',
    //     confidence: 0-100 (how strongly we believe the action),
    //     reason: plain-English explanation,
    //     pnlPct: current P&L % }
    evaluate: function (position, trade, raw) {
      if (!position || position.status !== 'active') return null;
      var snap = this._entrySnapshots[position.id];
      var currentPrice = trade ? trade.price : position.entryPremium;
      var pnlPct = ((currentPrice - position.entryPremium) / position.entryPremium) * 100;

      // Hit target
      if (currentPrice >= position.target) {
        return {
          action: 'EXIT',
          confidence: 100,
          reason: 'Target reached at ' + position.target.toFixed(2) +
                  '. Book the profit of ' + pnlPct.toFixed(1) + ' percent. Excellent trade.',
          pnlPct: pnlPct,
          voiceUrgent: true
        };
      }

      // Hit stop-loss
      if (currentPrice <= position.sl) {
        return {
          action: 'EXIT',
          confidence: 100,
          reason: 'Stop loss hit at ' + position.sl.toFixed(2) +
                  '. Close the position. Loss is ' + Math.abs(pnlPct).toFixed(1) +
                  ' percent. Move on to the next setup.',
          pnlPct: pnlPct,
          voiceUrgent: true
        };
      }

      // Ask consensus engine what it says about the CURRENT setup (new bars)
      var freshConsensus = consensusEngine.evaluate(trade, raw);

      // Strong flip — if consensus now says AVOID or has blockers, exit
      if (freshConsensus.verdict === 'AVOID') {
        return {
          action: 'EXIT',
          confidence: 90,
          reason: 'Setup has invalidated. ' +
                  (freshConsensus.blockers.length > 0
                    ? freshConsensus.blockers[0]
                    : 'Signals have turned against us') +
                  '. Close out at the market.',
          pnlPct: pnlPct,
          voiceUrgent: true
        };
      }

      // Signal strengthening — add to position
      // Criteria: fresh points > 35 AND we're in profit AND original score >= 80
      if (freshConsensus.points >= 35 &&
          pnlPct > 5 &&
          snap && snap.score >= 80 &&
          freshConsensus.verdict === 'STRONG_BUY') {
        return {
          action: 'ADD',
          confidence: 80,
          reason: 'Signal strengthening with ' + pnlPct.toFixed(1) +
                  ' percent in profit. Consensus is STRONG BUY. ' +
                  'Consider adding 25 to 50 percent more to the position.',
          pnlPct: pnlPct,
          voiceUrgent: false
        };
      }

      // Signal weakening — reduce size
      // Criteria: fresh points < 5 OR compass flipped to conflict OR regime flipped
      var compassNow = trendCompass.analyze(raw);
      var regimeFlipped = snap && snap.regime !== regimeDetector.current &&
        ((snap.regime === 'TRENDING_UP' && regimeDetector.current !== 'TRENDING_UP') ||
         (snap.regime === 'TRENDING_DN' && regimeDetector.current !== 'TRENDING_DN'));

      if (freshConsensus.points < 5 ||
          (compassNow.status === 'ok' && compassNow.conflict) ||
          regimeFlipped) {
        var weakenReason;
        if (regimeFlipped) {
          weakenReason = 'Market regime has changed from ' + snap.regime.replace('_', ' ').toLowerCase() +
                         ' to ' + regimeDetector.current.replace('_', ' ').toLowerCase() +
                         '. Reduce the position to half size and set a tighter stop.';
        } else if (compassNow.conflict) {
          weakenReason = 'Short-term and long-term trends are now in conflict. ' +
                         'Reduce the position to half size. If momentum fades further, exit.';
        } else {
          weakenReason = 'Signals are weakening. Consensus score dropped to ' + freshConsensus.points +
                         '. Reduce the position to half size and protect profits.';
        }
        return {
          action: 'REDUCE',
          confidence: 75,
          reason: weakenReason,
          pnlPct: pnlPct,
          voiceUrgent: false
        };
      }

      // Default: continue holding. Give encouraging or cautious tone based on P&L
      var continueReason;
      if (pnlPct > 15) {
        continueReason = 'Up ' + pnlPct.toFixed(1) + ' percent. Trail your stop ' +
                         'to lock in profits. Signal still intact. Hold.';
      } else if (pnlPct > 5) {
        continueReason = 'In profit by ' + pnlPct.toFixed(1) +
                         ' percent. Signal still intact. Continue holding for target.';
      } else if (pnlPct > -5) {
        continueReason = 'Trade is tracking normally at ' + (pnlPct >= 0 ? 'plus ' : '') +
                         pnlPct.toFixed(1) + ' percent. Signal intact. Continue.';
      } else {
        continueReason = 'Drawdown of ' + Math.abs(pnlPct).toFixed(1) +
                         ' percent but signal still valid. Give the trade room. ' +
                         'Stop is at ' + position.sl.toFixed(2) + '.';
      }
      return {
        action: 'CONTINUE',
        confidence: 70,
        reason: continueReason,
        pnlPct: pnlPct,
        voiceUrgent: false
      };
    },

    // Run evaluation on every active position and return list of recommendations.
    // Called from on5mClose().
    evaluateAll: function (rawPriceMap) {
      var out = [];
      for (var id in paperPortfolio.positions) {
        var p = paperPortfolio.positions[id];
        if (p.status !== 'active') continue;
        var trade = rawPriceMap ? rawPriceMap[p.tradeId] : null;
        var raw = trade ? trade._raw : null;
        var rec = this.evaluate(p, trade || { price: p.entryPremium, side: p.side }, raw);
        if (rec) {
          rec.positionId = p.id;
          rec.symbol = p.sym;
          rec.strike = p.strike;
          rec.side = p.side;
          out.push(rec);
        }
      }
      return out;
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 17. PLAIN-ENGLISH VOICE HELPERS — mirror Quick Trade's conversational tone
  // ═══════════════════════════════════════════════════════════════════════
  // Convert jargon-y data into user-friendly voice sentences. Quick Trade
  // says "Early entry detected. Optimal risk to reward. Entry score 84 out
  // of 100. Execute now." We want the same approachable style.
  var voiceGuide = {
    // Convert consensus verdict to plain English
    verdictLine: function (verdict, tradeSummary) {
      tradeSummary = tradeSummary || '';
      switch (verdict.verdict) {
        case 'STRONG_BUY':
          return tradeSummary + ' is a strong buy. ' +
                 'All signals are aligned. Take full size.';
        case 'BUY':
          return tradeSummary + ' is a buy with three-quarters size. ' +
                 'Most signals support this trade.';
        case 'BUY_SMALL':
          return tradeSummary + ' is a small buy only. Mixed signals — ' +
                 'take half size and watch closely.';
        case 'NEUTRAL':
          return tradeSummary + ' is neutral. Consider waiting for cleaner setup.';
        case 'AVOID':
          return 'Avoid ' + tradeSummary + '. ' +
                 (verdict.blockers.length > 0
                    ? verdict.blockers[0]
                    : 'Signals are not aligned');
        default:
          return tradeSummary + ' status unclear';
      }
    },

    // Lifecycle recommendations
    lifecycleLine: function (rec) {
      var prefix = rec.symbol + ' ' + rec.strike + ' ';
      switch (rec.action) {
        case 'CONTINUE': return prefix + rec.reason;
        case 'ADD':      return prefix + '— ' + rec.reason;
        case 'REDUCE':   return prefix + '— ' + rec.reason;
        case 'EXIT':     return prefix + '— ' + rec.reason;
        default:         return prefix + rec.reason;
      }
    }
  };


  // ── EXPOSED ENGINE API ─────────────────────────────────────────────────
  // Placed AFTER all module declarations so every reference below points
  // to a fully-initialized object (not undefined due to var hoisting).
  window._atEngine = {
    bus: bus,
    signals: signalLedger,
    portfolio: paperPortfolio,
    kelly: kellySizer,
    cost: execCostModel,
    regime: regimeDetector,
    alphaDecay: alphaDecay,
    pricing: pricingMath,
    vol: volMath,
    risk: portfolioRisk,
    gex: gexAnalyzer,
    strikes: strikeSelector,
    monitor: tradeMonitor,
    compass: trendCompass,
    priceAction: priceAction,
    externals: externalFeeds,
    ivTerm: ivTermStructure,
    orderFlow: orderFlow,
    consensus: consensusEngine,
    liveGuide: liveTradeGuide,
    voiceGuide: voiceGuide,

    // Dump signals as CSV (for feeding external backtest tools)
    exportSignalsCSV: function () {
      if (!signalLedger.all.length) return '';
      var keys = ['ts', 'sym', 'strike', 'side', 'score', 'state', 'spot',
                  'premium', 'sl', 'target', 'trigger', 'missing'];
      var rows = [keys.join(',')];
      signalLedger.all.forEach(function (s) {
        rows.push(keys.map(function (k) {
          var v = s[k];
          if (v == null) return '';
          if (Array.isArray(v)) v = v.join(';');
          return typeof v === 'string' ? '"' + v.replace(/"/g, '""') + '"' : v;
        }).join(','));
      });
      return rows.join('\n');
    }
  };


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

    // ATM strike: prefer backend-provided value. If absent, derive from the
    // REAL option chain — find the strike closest to spot among strikes that
    // actually exist in chain_near_atm. This is NOT fabrication: every strike
    // in chain_near_atm comes from NSE/yfinance, so "closest actual strike"
    // is by definition a real tradable strike.
    var atm = row.atm_strike;
    if ((atm == null || atm <= 0) && Array.isArray(row.chain_near_atm) && row.chain_near_atm.length > 0) {
      var closestStrike = null;
      row.chain_near_atm.forEach(function (r) {
        if (r.strike != null && (closestStrike == null || Math.abs(r.strike - spot) < Math.abs(closestStrike - spot))) {
          closestStrike = r.strike;
        }
      });
      atm = closestStrike;
    }
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

    // Terminal wrapper — fills the overlay mount area (100% of available
    // height, which is 100vh minus the top-bar's 44px). Flex column so
    // inner panels can claim vertical real estate cleanly.
    var wrap = el('div', {
      style: {
        width: '100%',
        height: '100%',          // fill overlay (was fixed 880px which caused overflow)
        background: C.bg,
        color: C.textPri,
        fontFamily: '"Sora", system-ui, sans-serif',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        minHeight: 0
      }
    });

    wrap.appendChild(renderHeader());

    var body = el('div', {
      style: {
        flex: '1 1 auto',        // claim all remaining vertical space
        display: 'grid',
        // 3-column layout: TopTrades (28%) | Live Monitor (34%) | Detail (38%)
        // Middle column consolidates live lifecycle guidance + key metrics
        // so the user sees everything important WITHOUT scrolling the right
        // column. User sees: trade signals on left, what to do with open
        // positions in middle, full detail on right.
        gridTemplateColumns: '28% 34% 38%',
        minHeight: 0,
        overflow: 'hidden',
        background: C.bg
      }
    });
    body.appendChild(renderTopTrades());
    body.appendChild(renderLiveMonitor());
    body.appendChild(renderQuickTrade());
    wrap.appendChild(body);

    // Scanner sits at the BOTTOM as a fixed-height band (spans full width).
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

      // RIGHT: paper P&L + alerts + voice + user profile
      el('div', { style: { display: 'flex', alignItems: 'center', gap: '6px' } }, [
        // Regime pill — TRENDING / RANGING / VOLATILE
        (function () {
          var regimeColor = regimeDetector.color();
          return el('div', {
            title: 'Market regime (from lead index ' + (state.region === 'US' ? 'SPY' : 'NIFTY') + ')\n' +
                   'Adjusts Kelly sizing: ×' + regimeDetector.kellyMultiplier().toFixed(2),
            style: {
              fontSize: '10px', fontWeight: 800, padding: '3px 7px',
              border: '1px solid ' + regimeColor + '55',
              background: regimeColor + '18', color: regimeColor,
              borderRadius: '4px', fontFamily: MONO, letterSpacing: '0.2px'
            }
          }, regimeDetector.label());
        })(),
        // Alpha decay chip — shows edge health
        (function () {
          var decay = alphaDecay.read();
          var color = alphaDecay.color();
          var label = alphaDecay.summary();
          return el('div', {
            title: 'Alpha decay monitor\n' +
                   'Compares closed ≥80 vs <68 score bands\n' +
                   'High band: ' + decay.highBand.n + ' trades, ' +
                   decay.highBand.avgPnl.toFixed(1) + '% avg\n' +
                   'Low band: ' + decay.lowBand.n + ' trades, ' +
                   decay.lowBand.avgPnl.toFixed(1) + '% avg',
            style: {
              fontSize: '10px', fontWeight: 700, padding: '3px 7px',
              border: '1px solid ' + color + '55',
              background: color + '11', color: color,
              borderRadius: '4px', fontFamily: MONO, letterSpacing: '0.2px'
            }
          }, label);
        })(),
        // Risk gate chip — OK or why blocked
        (function () {
          var gate = portfolioRisk.checkAllow();
          var s = gate.stats || portfolioRisk.sessionStats();
          var color = gate.allow ? C.green : C.red;
          var label = gate.allow
            ? ('Risk OK · ' + s.concurrent + '/' + portfolioRisk.config.maxConcurrent)
            : 'Risk BLOCKED';
          var tooltip =
            'Portfolio risk gate\n' +
            'Concurrent: ' + s.concurrent + '/' + portfolioRisk.config.maxConcurrent + '\n' +
            'Today P&L: ' + s.todayPnlPct.toFixed(2) + '% (cap -' +
              portfolioRisk.config.maxDailyLossPct + '%)\n' +
            'Drawdown: ' + s.drawdownPct.toFixed(2) + '% (cap ' +
              portfolioRisk.config.maxDrawdownPct + '%)\n' +
            (gate.allow ? 'All checks pass' : 'BLOCKED: ' + gate.reason);
          return el('div', {
            title: tooltip,
            style: {
              fontSize: '10px', fontWeight: 700, padding: '3px 7px',
              border: '1px solid ' + color + '55',
              background: color + '11', color: color,
              borderRadius: '4px', fontFamily: MONO, letterSpacing: '0.2px'
            }
          }, label);
        })(),
        // Paper portfolio stats pill
        (function () {
          var s = paperPortfolio.stats();
          var label;
          if (s.total === 0) {
            label = 'Paper: 0';
          } else if (s.wins + s.losses === 0) {
            label = 'Paper: ' + (s.pending + s.active) + ' open';
          } else {
            label = 'Paper: ' + s.wins + 'W/' + s.losses + 'L · ' +
                    s.winRate.toFixed(0) + '% · ' +
                    (s.avgPnlPct > 0 ? '+' : '') + s.avgPnlPct.toFixed(1) + '%';
          }
          var color = s.avgPnlPct > 0 ? C.green : s.avgPnlPct < 0 ? C.red : C.textSec;
          return el('div', {
            title: 'Paper-trade performance (this browser only)\n' +
                   s.total + ' total · ' + s.pending + ' pending · ' + s.active + ' active',
            style: {
              fontSize: '10px', fontWeight: 700, padding: '3px 7px',
              border: '1px solid ' + color + '55',
              background: color + '11', color: color,
              borderRadius: '4px', fontFamily: MONO, letterSpacing: '0.2px'
            }
          }, label);
        })(),
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
        padding: '8px', height: '100%',
        background: C.bg,  // explicit — don't rely on inheritance
        display: 'flex', flexDirection: 'column', minHeight: 0
      }
    });

    // Header row — title + search
    var header = el('div', {
      style: {
        display: 'flex', alignItems: 'center', gap: '8px',
        marginBottom: '6px', padding: '0 2px', flex: '0 0 auto'
      }
    });
    header.appendChild(el('div', {
      style: {
        fontSize: '10px', fontWeight: 800, color: C.textMute,
        letterSpacing: '1.5px', whiteSpace: 'nowrap'
      }
    }, 'TOP TRADES · 5M CLOSE'));

    // Search input — filters trades + scanner by symbol substring
    var search = el('input', {
      type: 'text',
      placeholder: 'Search symbol (e.g. NIFTY, AAPL)...',
      value: state.searchFilter || '',
      onInput: function (e) {
        state.searchFilter = e.target.value.toUpperCase();
        rerender();
        // Put focus back on input after rerender (DOM got replaced)
        setTimeout(function () {
          var newInput = document.querySelector('[data-at-search]');
          if (newInput) {
            newInput.focus();
            newInput.setSelectionRange(newInput.value.length, newInput.value.length);
          }
        }, 0);
      },
      style: {
        flex: '1 1 auto', minWidth: 0,
        background: C.card, border: '1px solid ' + C.divider,
        color: C.textPri, fontSize: '11px', fontFamily: MONO,
        padding: '4px 8px', borderRadius: '4px', outline: 'none'
      }
    });
    search.setAttribute('data-at-search', '1');
    header.appendChild(search);

    // Clear button (only if search has value)
    if (state.searchFilter) {
      header.appendChild(el('button', {
        onClick: function () { state.searchFilter = ''; rerender(); },
        title: 'Clear search',
        style: {
          background: 'transparent', border: '1px solid ' + C.divider,
          color: C.textSec, cursor: 'pointer', fontSize: '10px',
          padding: '3px 6px', borderRadius: '3px', fontFamily: MONO
        }
      }, '✕'));
    }
    panel.appendChild(header);

    // Filtered trade list
    var filter = state.searchFilter || '';
    var displayTrades = filter
      ? state.trades.filter(function (t) {
          return t && (t.symbol || '').toUpperCase().indexOf(filter) >= 0;
        })
      : state.trades;

    // Scrollable body
    var body = el('div', {
      style: {
        flex: '1 1 auto', overflowY: 'auto', overflowX: 'hidden',
        minHeight: 0,
        scrollbarWidth: 'thin',
        scrollbarColor: C.divider + ' ' + C.bg
      }
    });

    if (filter && displayTrades.length === 0) {
      body.appendChild(el('div', {
        style: {
          color: C.textMute, fontSize: '11px', fontStyle: 'italic',
          textAlign: 'center', padding: '20px 12px'
        }
      }, 'No top trades match "' + filter + '". Try secondary scanner below.'));
    } else {
      // If filter active, show only matching trades (no placeholders)
      if (filter) {
        displayTrades.forEach(function (t) { body.appendChild(tradeCard(t)); });
      } else {
        // Normal: show top 3 (with placeholders for empty slots)
        for (var i = 0; i < 3; i++) {
          var t = state.trades[i];
          if (!t) {
            var placeholderText;
            if (!state.loaded) {
              placeholderText = 'Loading…';
            } else if (state.lastFetchMsg) {
              placeholderText = state.lastFetchMsg;
            } else {
              placeholderText = 'No high-confidence trades';
            }
            body.appendChild(el('div', {
              style: {
                height: '104px', marginBottom: '6px', borderRadius: '12px',
                border: '1px dashed ' + C.divider, display: 'flex',
                alignItems: 'center', justifyContent: 'center',
                color: C.textMute, fontSize: '12px', fontStyle: 'italic',
                padding: '0 12px', textAlign: 'center', lineHeight: 1.3
              }
            }, placeholderText));
          } else {
            body.appendChild(tradeCard(t));
          }
        }
      }
    }
    panel.appendChild(body);

    return panel;
  }

  function tradeCard(trade) {
    var isSelected = state.selected && state.selected.id === trade.id;
    var history = state.scoreHistory[trade.id] || [];

    var card = el('div', {
      onClick: function () { selectTrade(trade); },
      style: {
        height: '104px', padding: '8px',  // bumped to fit Buy/Trig/SL/Target line
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

    // Row 1 col 1 — symbol + strike (stacked with Buy/Trig/SL/Target below)
    var symCell = el('div', {
      style: {
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
        gap: '2px', overflow: 'hidden'
      }
    });
    var sym = el('div', {
      style: {
        fontSize: '17px', fontWeight: 600, color: C.textPri,
        lineHeight: 1.1, fontFamily: MONO, whiteSpace: 'nowrap',
        overflow: 'hidden', textOverflow: 'ellipsis'
      }
    });
    sym.appendChild(document.createTextNode(trade.symbol + ' '));
    sym.appendChild(el('span', { style: { color: C.textSec } }, trade.strike));
    symCell.appendChild(sym);

    // Option entry price + trigger + SL + target — what the user actually trades on
    var currency = (trade._raw && trade._raw.currency) ? trade._raw.currency : '₹';
    var priceLine = el('div', {
      style: {
        fontSize: '11px', color: C.textSec, fontFamily: MONO, lineHeight: 1.1,
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
      }
    });
    priceLine.appendChild(document.createTextNode('Buy '));
    priceLine.appendChild(el('span', {
      style: { color: C.textPri, fontWeight: 700 }
    }, currency + trade.price.toFixed(2)));
    priceLine.appendChild(document.createTextNode(' · Trig '));
    priceLine.appendChild(el('span', {
      style: { color: C.textPri, fontWeight: 600 }
    }, trade.trigger.toFixed(2)));
    priceLine.appendChild(document.createTextNode(' · SL '));
    priceLine.appendChild(el('span', {
      style: { color: C.red, fontWeight: 600 }
    }, currency + trade.sl.toFixed(2)));
    priceLine.appendChild(document.createTextNode(' · Tgt '));
    priceLine.appendChild(el('span', {
      style: { color: C.green, fontWeight: 600 }
    }, currency + trade.target.toFixed(2)));
    symCell.appendChild(priceLine);

    card.appendChild(symCell);

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

  // ── LIVE MONITOR — middle column ────────────────────────────────────────
  // Consolidates everything the user needs to see at a glance:
  //   1. Consensus verdict for currently-selected trade (ONE sentence)
  //   2. Active positions with lifecycle tags (CONTINUE/ADD/REDUCE/EXIT)
  //   3. Macro snapshot: regime, alpha health, pre-open gap, VIX
  //
  // This makes the key actionable content visible without scrolling
  // the right-column detail panel. The right column stays for deep dives
  // (Greeks, chain, SMC primitives, etc.).
  function renderLiveMonitor() {
    var panel = el('div', {
      style: {
        background: C.bg,
        borderLeft: '1px solid ' + C.divider,
        height: '100%', display: 'flex', flexDirection: 'column',
        minHeight: 0, overflow: 'hidden'
      }
    });

    // Header
    panel.appendChild(el('div', {
      style: {
        fontSize: '10px', fontWeight: 800, color: C.textMute,
        letterSpacing: '1.5px', padding: '8px 10px 6px',
        borderBottom: '1px solid ' + C.divider,
        flex: '0 0 auto'
      }
    }, 'LIVE MONITOR · ALL OPEN + SELECTED'));

    // Scrollable body
    var scroll = el('div', {
      style: {
        flex: '1 1 auto', minHeight: 0,
        overflowY: 'auto', overflowX: 'hidden',
        scrollbarWidth: 'thin',
        scrollbarColor: C.divider + ' ' + C.bg
      }
    });

    // 1. SELECTED TRADE CONSENSUS (if a trade is selected but not yet opened)
    if (state.selected) {
      var t = state.selected;
      var raw = t._raw || {};
      var v = consensusEngine.evaluate(t, raw);
      var sel = el('div', {
        style: {
          padding: '10px 10px 6px', borderBottom: '1px solid ' + C.divider
        }
      });
      sel.appendChild(el('div', {
        style: {
          fontSize: '9px', fontWeight: 700, color: C.textSec,
          letterSpacing: '0.8px', marginBottom: '6px'
        }
      }, 'SELECTED: ' + t.symbol + ' ' + t.strike));

      // Big verdict card
      var verdictCard = el('div', {
        style: {
          background: v.color + '18', borderLeft: '3px solid ' + v.color,
          borderRadius: '3px', padding: '8px 10px', marginBottom: '6px'
        }
      });
      verdictCard.appendChild(el('div', {
        style: {
          fontSize: '13px', fontWeight: 800, color: v.color,
          fontFamily: MONO, lineHeight: 1.2
        }
      }, consensusEngine.oneLine(v)));
      verdictCard.appendChild(el('div', {
        style: {
          fontSize: '10px', color: C.textSec, marginTop: '4px', lineHeight: 1.3
        }
      }, v.reasons.length + ' pros · ' + v.warnings.length + ' caveats · ' +
         'points: ' + (v.points >= 0 ? '+' : '') + v.points));
      sel.appendChild(verdictCard);

      // Top 2 reasons (quick scan)
      if (v.reasons.length > 0) {
        v.reasons.slice(0, 3).forEach(function (r) {
          sel.appendChild(el('div', {
            style: {
              fontSize: '10px', color: C.green, fontFamily: MONO,
              lineHeight: 1.35, marginTop: '2px'
            }
          }, '✓ ' + r));
        });
      }
      if (v.warnings.length > 0) {
        v.warnings.slice(0, 3).forEach(function (w) {
          sel.appendChild(el('div', {
            style: {
              fontSize: '10px', color: C.orange, fontFamily: MONO,
              lineHeight: 1.35, marginTop: '2px'
            }
          }, '⚠ ' + w));
        });
      }
      if (v.blockers.length > 0) {
        v.blockers.forEach(function (b) {
          sel.appendChild(el('div', {
            style: {
              fontSize: '10px', color: C.red, fontFamily: MONO,
              fontWeight: 700, lineHeight: 1.35, marginTop: '2px'
            }
          }, '🚫 ' + b));
        });
      }
      scroll.appendChild(sel);
    }

    // 2. ACTIVE POSITIONS WITH LIFECYCLE TAGS
    var priceLookup = {};
    (state.trades || []).forEach(function (t) { priceLookup[t.id] = t; });
    if (state.selected) priceLookup[state.selected.id] = state.selected;

    var activePositions = [];
    for (var id in paperPortfolio.positions) {
      var p = paperPortfolio.positions[id];
      if (p.status === 'active' || p.status === 'pending') activePositions.push(p);
    }

    var positionsSection = el('div', {
      style: { padding: '10px 10px 6px' }
    });
    positionsSection.appendChild(el('div', {
      style: {
        fontSize: '9px', fontWeight: 700, color: C.textSec,
        letterSpacing: '0.8px', marginBottom: '6px'
      }
    }, 'OPEN POSITIONS (' + activePositions.length + ')'));

    if (activePositions.length === 0) {
      positionsSection.appendChild(el('div', {
        style: {
          fontSize: '11px', color: C.textMute, fontStyle: 'italic',
          padding: '6px 0', textAlign: 'center'
        }
      }, 'No open positions yet. Hit EXECUTE on a trade to start.'));
    } else {
      activePositions.forEach(function (pos) {
        var liveTrade = priceLookup[pos.tradeId];
        var currentPrice = liveTrade ? liveTrade.price : pos.entryPremium;
        var pnlPct = ((currentPrice - pos.entryPremium) / pos.entryPremium) * 100;

        // Get lifecycle recommendation
        var rec = null;
        if (pos.status === 'active' && liveTrade) {
          rec = liveTradeGuide.evaluate(pos, liveTrade, liveTrade._raw);
        }

        var statusColor = pos.status === 'active' ? C.green : C.orange;
        var actionColor = !rec ? C.textMute
                         : rec.action === 'EXIT' ? C.red
                         : rec.action === 'REDUCE' ? C.orange
                         : rec.action === 'ADD' ? C.green : C.blue;
        var pnlColor = pnlPct >= 0 ? C.green : C.red;

        var posCard = el('div', {
          style: {
            background: C.card,
            borderLeft: '3px solid ' + actionColor,
            borderRadius: '3px',
            padding: '6px 8px',
            marginBottom: '6px'
          }
        });

        // Line 1: symbol + status + P&L
        posCard.appendChild(el('div', {
          style: {
            display: 'flex', justifyContent: 'space-between',
            alignItems: 'center', marginBottom: '3px',
            fontSize: '11px', fontFamily: MONO
          }
        }, [
          el('span', { style: { color: C.textPri, fontWeight: 700 } },
            pos.sym + ' ' + pos.strike),
          el('span', { style: { color: pnlColor, fontWeight: 700 } },
            (pnlPct >= 0 ? '+' : '') + pnlPct.toFixed(1) + '%')
        ]));

        // Line 2: status + entry/current prices
        posCard.appendChild(el('div', {
          style: {
            display: 'flex', justifyContent: 'space-between',
            fontSize: '9px', fontFamily: MONO, color: C.textSec,
            marginBottom: '4px'
          }
        }, [
          el('span', {
            style: { color: statusColor, fontWeight: 700 }
          }, pos.status.toUpperCase()),
          el('span', {}, (pos.currency || '₹') + pos.entryPremium.toFixed(2) +
                          ' → ' + (pos.currency || '₹') + currentPrice.toFixed(2))
        ]));

        // Line 3: lifecycle action tag
        if (rec) {
          posCard.appendChild(el('div', {
            style: {
              background: actionColor + '22',
              color: actionColor,
              padding: '3px 6px', borderRadius: '2px',
              fontSize: '10px', fontWeight: 800,
              fontFamily: MONO, letterSpacing: '1px',
              display: 'inline-block', marginBottom: '4px'
            }
          }, rec.action));

          // Reason text (wrapped)
          posCard.appendChild(el('div', {
            style: {
              fontSize: '10px', color: C.textSec, lineHeight: 1.35,
              marginTop: '2px'
            }
          }, rec.reason));
        } else if (pos.status === 'pending') {
          posCard.appendChild(el('div', {
            style: {
              fontSize: '10px', color: C.textMute, fontStyle: 'italic'
            }
          }, 'Waiting for trigger at ' + (pos.currency || '₹') +
             pos.trigger.toFixed(2)));
        }

        positionsSection.appendChild(posCard);
      });
    }
    scroll.appendChild(positionsSection);

    // 3. MACRO SNAPSHOT — regime, alpha, external feeds
    var macroSection = el('div', {
      style: {
        padding: '10px', borderTop: '1px solid ' + C.divider
      }
    });
    macroSection.appendChild(el('div', {
      style: {
        fontSize: '9px', fontWeight: 700, color: C.textSec,
        letterSpacing: '0.8px', marginBottom: '6px'
      }
    }, 'MACRO CONTEXT'));

    // Regime
    var regColor = regimeDetector.color();
    macroSection.appendChild(macroRow('Regime', regimeDetector.label(), regColor));

    // Alpha
    var alphaColor = alphaDecay.color();
    macroSection.appendChild(macroRow('Alpha edge',
      alphaDecay.summary(), alphaColor));

    // Gap (region-aware)
    var region = state.region || 'IN';
    var ext = region === 'IN'
      ? externalFeeds.giftReport()
      : externalFeeds.usPreReport();
    if (ext && ext.status === 'ok') {
      var gapColor = ext.gap > 0.15 ? C.green : ext.gap < -0.15 ? C.red : C.textSec;
      macroSection.appendChild(macroRow(
        region === 'IN' ? 'GIFT NIFTY gap' : 'Futures gap',
        (ext.gap >= 0 ? '+' : '') + ext.gap.toFixed(2) + '%',
        gapColor));
    } else {
      macroSection.appendChild(macroRow(
        region === 'IN' ? 'GIFT NIFTY' : 'US Futures',
        'awaiting feed', C.textMute));
    }

    // VIX
    if (ext && ext.status === 'ok' && ext.vix) {
      var vixColor = ext.vixChange > 5 ? C.red : ext.vixChange < -5 ? C.green : C.textSec;
      macroSection.appendChild(macroRow(
        region === 'IN' ? 'India VIX' : 'VIX',
        ext.vix.toFixed(2) + ' (' + (ext.vixChange >= 0 ? '+' : '') +
          ext.vixChange.toFixed(1) + '%)',
        vixColor));
    }

    // Portfolio risk
    var riskGate = portfolioRisk.checkAllow();
    macroSection.appendChild(macroRow(
      'Risk gate',
      riskGate.allow ? 'OK' : 'BLOCKED',
      riskGate.allow ? C.green : C.red));

    scroll.appendChild(macroSection);
    panel.appendChild(scroll);
    return panel;
  }

  // Small helper row for macro section
  function macroRow(label, value, color) {
    return el('div', {
      style: {
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', fontSize: '11px', fontFamily: MONO,
        padding: '2px 0', lineHeight: 1.3
      }
    }, [
      el('span', { style: { color: C.textSec, fontWeight: 600 } }, label),
      el('span', { style: { color: color, fontWeight: 700 } }, value)
    ]);
  }

  function renderQuickTrade() {
    var panel = el('div', {
      style: {
        background: C.bg, borderLeft: '1px solid ' + C.divider,
        height: '100%', display: 'flex', flexDirection: 'column',
        opacity: state.selected ? 1 : 0.4,
        transition: 'opacity 200ms ease',
        minHeight: 0, overflow: 'hidden'
      }
    });

    // Header stays fixed at top
    panel.appendChild(renderSelectedHeader());

    // Scrollable body — all analysis panels stack inside with internal scroll
    var scroll = el('div', {
      style: {
        flex: '1 1 auto', overflowY: 'auto', overflowX: 'hidden',
        minHeight: 0,
        // custom dark scrollbar
        scrollbarWidth: 'thin',
        scrollbarColor: C.divider + ' ' + C.bg
      }
    });
    // Consensus panel FIRST — the combined verdict is the most important thing
    scroll.appendChild(renderConsensusPanel());
    scroll.appendChild(renderExternalsPanel());
    scroll.appendChild(renderEntryEngine());
    scroll.appendChild(renderCandlestickPanel());
    scroll.appendChild(renderPriceActionPanel());
    scroll.appendChild(renderGexCompassPanel());
    scroll.appendChild(renderGreeksVolPanel());
    scroll.appendChild(renderLivePositionsPanel());
    scroll.appendChild(renderOptionChain());
    scroll.appendChild(renderRiskBlock());
    panel.appendChild(scroll);

    // Voice log pinned at bottom (smaller height, its own scroll)
    panel.appendChild(renderVoiceLog());
    return panel;
  }

  // ── CONSENSUS PANEL — combined verdict from all modules ─────────────────
  // This is THE primary recommendation. Sits at the top of the detail panel
  // so it's the first thing the user sees after selecting a trade.
  function renderConsensusPanel() {
    var wrap = el('div', {
      style: {
        background: C.card, borderBottom: '1px solid ' + C.divider,
        padding: '10px 12px'
      }
    });
    if (!state.selected) {
      wrap.appendChild(el('div', {
        style: {
          color: C.textMute, fontSize: '11px', fontStyle: 'italic',
          textAlign: 'center'
        }
      }, 'Select a trade for overall recommendation'));
      return wrap;
    }

    var t = state.selected;
    var raw = t._raw || {};
    var v = consensusEngine.evaluate(t, raw);

    // Header row — verdict badge + size multiplier
    var header = el('div', {
      style: {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: '8px'
      }
    }, [
      el('span', {
        style: { fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px', color: C.textSec }
      }, 'CONSENSUS · ALL SIGNALS COMBINED')
    ]);
    wrap.appendChild(header);

    // Big verdict card
    var verdictCard = el('div', {
      style: {
        background: v.color + '15', borderLeft: '4px solid ' + v.color,
        padding: '10px 12px', borderRadius: '4px', marginBottom: '8px'
      }
    });
    verdictCard.appendChild(el('div', {
      style: {
        fontSize: '16px', fontWeight: 800, color: v.color,
        fontFamily: MONO, letterSpacing: '0.5px', lineHeight: 1.2
      }
    }, consensusEngine.oneLine(v)));
    verdictCard.appendChild(el('div', {
      style: {
        fontSize: '10px', color: C.textSec, marginTop: '3px'
      }
    }, 'Signal points: ' + (v.points >= 0 ? '+' : '') + v.points +
       (v.blockers.length ? ' · ' + v.blockers.length + ' blocker(s)' : '') +
       ' · ' + v.reasons.length + ' pros · ' + v.warnings.length + ' caveats'));
    wrap.appendChild(verdictCard);

    // Blockers (red) — show first if any
    if (v.blockers.length > 0) {
      var blockBox = el('div', {
        style: {
          background: '#EF444415', border: '1px solid #EF444455',
          borderRadius: '4px', padding: '6px 8px', marginBottom: '6px'
        }
      });
      blockBox.appendChild(el('div', {
        style: { fontSize: '9px', fontWeight: 800, color: '#EF4444', marginBottom: '3px' }
      }, '🚫 BLOCKERS'));
      v.blockers.forEach(function (b) {
        blockBox.appendChild(el('div', {
          style: { fontSize: '10px', color: '#EF4444', fontFamily: MONO, lineHeight: 1.4 }
        }, '· ' + b));
      });
      wrap.appendChild(blockBox);
    }

    // Two-column: reasons + warnings
    var cols = el('div', {
      style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }
    });

    // Reasons (green)
    var reasonsCol = el('div', {
      style: {
        background: C.bg, borderLeft: '2px solid ' + C.green,
        borderRadius: '4px', padding: '6px 8px'
      }
    });
    reasonsCol.appendChild(el('div', {
      style: { fontSize: '9px', fontWeight: 800, color: C.green, marginBottom: '3px' }
    }, '✓ PROS (' + v.reasons.length + ')'));
    if (v.reasons.length === 0) {
      reasonsCol.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'No strong positives'));
    }
    v.reasons.forEach(function (r) {
      reasonsCol.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textPri, fontFamily: MONO, lineHeight: 1.4 }
      }, '· ' + r));
    });
    cols.appendChild(reasonsCol);

    // Warnings (orange)
    var warnCol = el('div', {
      style: {
        background: C.bg, borderLeft: '2px solid ' + C.orange,
        borderRadius: '4px', padding: '6px 8px'
      }
    });
    warnCol.appendChild(el('div', {
      style: { fontSize: '9px', fontWeight: 800, color: C.orange, marginBottom: '3px' }
    }, '⚠ CAVEATS (' + v.warnings.length + ')'));
    if (v.warnings.length === 0) {
      warnCol.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'No concerns'));
    }
    v.warnings.forEach(function (w) {
      warnCol.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textSec, fontFamily: MONO, lineHeight: 1.4 }
      }, '· ' + w));
    });
    cols.appendChild(warnCol);

    wrap.appendChild(cols);
    return wrap;
  }

  // ── GEX heatmap + Trend compass (ported from Quick Trade) ───────────────
  // Two side-by-side institutional context panels:
  //   LEFT: GEX — regime tag, flip level, call/put walls, top strikes
  //   RIGHT: Trend Compass — short-term structure + long-term SMA alignment
  function renderGexCompassPanel() {
    var wrap = el('div', {
      style: {
        background: C.card, borderBottom: '1px solid ' + C.divider,
        padding: '8px 10px'
      }
    });
    if (!state.selected) return wrap;
    var raw = state.selected._raw || {};

    // GEX section
    var gexData = gexAnalyzer.read(raw);
    var gexAction = gexAnalyzer.actionTag(raw);
    var zone = gexAnalyzer.zone(raw, raw.spot);

    // Compass section
    var compass = trendCompass.analyze(raw);

    // Header
    wrap.appendChild(el('div', {
      style: {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: '6px'
      }
    }, [
      el('span', {
        style: { fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px', color: C.textSec }
      }, 'GAMMA & TREND CONTEXT'),
      el('span', {
        title: gexAction.action,
        style: {
          fontSize: '9px', fontWeight: 800, padding: '2px 6px',
          background: gexAction.color + '22', color: gexAction.color,
          borderRadius: '3px', letterSpacing: '0.3px'
        }
      }, gexAction.tag)
    ]));

    // Two-column layout
    var row = el('div', {
      style: {
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px'
      }
    });

    // LEFT: GEX key levels
    var gexCol = el('div', {
      style: {
        background: C.bg, borderRadius: '4px', padding: '6px',
        borderLeft: '2px solid ' + gexAction.color
      }
    });
    if (gexData) {
      var levels = [
        { label: 'Flip', val: gexData.flip, color: C.orange,
          tip: 'Above = bullish accel, below = bearish accel' },
        { label: 'Call Wall', val: gexData.callWall, color: C.red,
          tip: 'Resistance (dealers sell rallies)' },
        { label: 'Put Wall', val: gexData.putWall, color: C.green,
          tip: 'Support (dealers buy dips)' }
      ];
      levels.forEach(function (lv) {
        if (!lv.val) return;
        gexCol.appendChild(el('div', {
          title: lv.tip,
          style: {
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            fontSize: '10px', fontFamily: MONO, padding: '1px 0'
          }
        }, [
          el('span', { style: { color: lv.color, fontWeight: 700 } }, lv.label),
          el('span', { style: { color: C.textPri } }, lv.val.toFixed(lv.val > 1000 ? 0 : 2))
        ]));
      });
      if (zone) {
        gexCol.appendChild(el('div', {
          style: {
            fontSize: '9px', color: zone.aboveFlip ? C.green : C.red,
            marginTop: '3px', fontWeight: 700
          }
        }, zone.aboveFlip
          ? '↗ ' + zone.distancePct.toFixed(2) + '% above flip'
          : '↘ ' + Math.abs(zone.distancePct).toFixed(2) + '% below flip'));
      }
    } else {
      gexCol.appendChild(el('div', {
        style: { fontSize: '9px', color: C.textMute, fontStyle: 'italic' }
      }, 'GEX data unavailable'));
    }

    // RIGHT: Trend compass
    var cmpCol = el('div', {
      style: { background: C.bg, borderRadius: '4px', padding: '6px' }
    });
    if (compass.status === 'ok') {
      var stColor = compass.shortTerm === 'BULLISH' ? C.green
                  : compass.shortTerm === 'BEARISH' ? C.red : C.textSec;
      var ltColor = compass.longTerm === 'BULLISH' ? C.green
                  : compass.longTerm === 'BEARISH' ? C.red : C.textSec;
      cmpCol.appendChild(el('div', {
        style: {
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          fontSize: '10px', fontFamily: MONO, padding: '1px 0'
        }
      }, [
        el('span', { style: { color: C.textSec, fontWeight: 700 } }, 'Short'),
        el('span', { style: { color: stColor, fontWeight: 700 } }, compass.shortTerm)
      ]));
      cmpCol.appendChild(el('div', {
        style: {
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          fontSize: '10px', fontFamily: MONO, padding: '1px 0'
        }
      }, [
        el('span', { style: { color: C.textSec, fontWeight: 700 } }, 'Long'),
        el('span', { style: { color: ltColor, fontWeight: 700 } }, compass.longTerm)
      ]));
      var alignColor = compass.aligned ? C.green : compass.conflict ? C.red : C.textMute;
      var alignText = compass.aligned ? 'ALIGNED' : compass.conflict ? 'CONFLICT' : 'MIXED';
      cmpCol.appendChild(el('div', {
        title: 'Short: ' + compass.shortReason + '\nLong: ' + compass.longReason,
        style: {
          fontSize: '9px', color: alignColor, fontWeight: 700,
          marginTop: '3px', textAlign: 'center'
        }
      }, alignText));
    } else {
      cmpCol.appendChild(el('div', {
        style: { fontSize: '9px', color: C.textMute, fontStyle: 'italic' }
      }, 'Compass: insufficient data'));
    }

    row.appendChild(gexCol);
    row.appendChild(cmpCol);
    wrap.appendChild(row);

    return wrap;
  }

  // ── Live positions panel (trade monitor) ────────────────────────────────
  // Shows all pending + active paper positions with live P&L, progress bar,
  // elapsed time, and a Close button for manual exit.
  function renderLivePositionsPanel() {
    var wrap = el('div', {
      style: {
        background: C.card, borderBottom: '1px solid ' + C.divider,
        padding: '8px 10px'
      }
    });

    // Build price lookup from current trades
    var priceLookup = {};
    (state.trades || []).forEach(function (t) { priceLookup[t.id] = t; });

    var positions = tradeMonitor.active(priceLookup);
    wrap.appendChild(el('div', {
      style: {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: '6px'
      }
    }, [
      el('span', {
        style: { fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px', color: C.textSec }
      }, 'LIVE POSITIONS'),
      el('span', {
        style: { fontSize: '9px', color: C.textMute, fontFamily: MONO }
      }, positions.length + ' open')
    ]));

    if (positions.length === 0) {
      wrap.appendChild(el('div', {
        style: {
          fontSize: '10px', color: C.textMute, fontStyle: 'italic', padding: '4px 0'
        }
      }, 'No active paper positions — EXECUTE a trade to track here'));
      return wrap;
    }

    positions.forEach(function (p) {
      var pnlColor = p.pnlRupees >= 0 ? C.green : C.red;
      var row = el('div', {
        style: {
          background: C.bg, borderRadius: '4px', padding: '5px 8px',
          marginBottom: '4px', borderLeft: '2px solid ' + pnlColor,
          fontSize: '10px', fontFamily: MONO
        }
      });
      // Line 1: sym + strike + status
      row.appendChild(el('div', {
        style: {
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: '2px'
        }
      }, [
        el('span', { style: { color: C.textPri, fontWeight: 700 } },
          p.sym + ' ' + p.strike + ' · ' + p.lots + ' lot' + (p.lots > 1 ? 's' : '')),
        el('span', {
          style: {
            color: p.status === 'active' ? C.green : C.orange,
            fontSize: '9px', padding: '1px 5px',
            background: (p.status === 'active' ? C.green : C.orange) + '22',
            borderRadius: '2px'
          }
        }, p.status.toUpperCase())
      ]));
      // Line 2: prices
      row.appendChild(el('div', {
        style: {
          display: 'flex', justifyContent: 'space-between',
          color: C.textSec, fontSize: '10px', marginBottom: '3px'
        }
      }, [
        el('span', {}, 'Entry ' + p.currency + p.entryPremium.toFixed(2) +
                       ' · Now ' + p.currency + p.currentPremium.toFixed(2)),
        el('span', { style: { color: pnlColor, fontWeight: 700 } },
          (p.pctChg >= 0 ? '+' : '') + p.pctChg.toFixed(2) + '%')
      ]));
      // Line 3: progress bar SL → Target
      var progWrap = el('div', {
        style: {
          display: 'flex', alignItems: 'center', gap: '4px',
          fontSize: '9px', fontFamily: MONO, marginBottom: '3px'
        }
      });
      progWrap.appendChild(el('span', { style: { color: C.red, minWidth: '36px' } },
        p.currency + p.sl.toFixed(0)));
      var bar = el('div', {
        style: {
          flex: 1, height: '4px', background: C.active,
          borderRadius: '2px', overflow: 'hidden', position: 'relative'
        }
      });
      bar.appendChild(el('div', {
        style: {
          width: p.progress + '%', height: '100%',
          background: 'linear-gradient(90deg, ' + C.red + ', ' + C.orange + ', ' + C.green + ')',
          transition: 'width 200ms ease'
        }
      }));
      progWrap.appendChild(bar);
      progWrap.appendChild(el('span', {
        style: { color: C.green, minWidth: '36px', textAlign: 'right' }
      }, p.currency + p.target.toFixed(0)));
      row.appendChild(progWrap);
      // Line 4: elapsed + close button
      var footer = el('div', {
        style: {
          display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }
      });
      footer.appendChild(el('span', {
        style: { fontSize: '9px', color: C.textMute }
      }, '⏱ ' + p.elapsedMin + ':' + (p.elapsedSec < 10 ? '0' : '') + p.elapsedSec));
      footer.appendChild(el('button', {
        onClick: (function (posId, curPrem) {
          return function (e) {
            e.stopPropagation();
            if (tradeMonitor.closeNow(posId, curPrem, 'user_manual')) {
              pushLog('MANUAL CLOSE: ' + p.sym + ' ' + p.strike + ' @ ' +
                      p.currency + curPrem.toFixed(2), C.blue);
              rerender();
            }
          };
        })(p.id, p.currentPremium),
        style: {
          padding: '2px 8px', fontSize: '9px', fontWeight: 700,
          background: 'transparent', color: C.blue,
          border: '1px solid ' + C.blue + '55', borderRadius: '3px',
          cursor: 'pointer'
        }
      }, 'Close'));
      row.appendChild(footer);

      wrap.appendChild(row);
    });

    return wrap;
  }

  // ── Candlestick chart with VWAP overlay (ported from Quick Trade) ───────
  // Compact inline SVG — last N 5m bars of the selected symbol, VWAP line,
  // day high/low bands. Works for any number of bars ≥ 3.
  function renderCandlestickPanel() {
    var wrap = el('div', {
      style: {
        background: C.card, borderBottom: '1px solid ' + C.divider,
        padding: '6px 10px'
      }
    });
    if (!state.selected) return wrap;

    var t = state.selected;
    var raw = t._raw || {};
    var bars = Array.isArray(raw.ohlc_bars) ? raw.ohlc_bars : [];
    var vwap = raw.vwap || 0;
    var high = raw.today_high || 0;
    var low = raw.today_low || 0;

    if (bars.length < 3) {
      wrap.appendChild(el('div', {
        style: {
          fontSize: '9px', color: C.textMute, fontStyle: 'italic',
          padding: '4px 0', textAlign: 'center'
        }
      }, 'Chart: waiting for 5m bar data (' + bars.length + ' bars)'));
      return wrap;
    }

    // Header
    wrap.appendChild(el('div', {
      style: {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: '4px'
      }
    }, [
      el('span', {
        style: { fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px', color: C.textSec }
      }, '5M CANDLESTICK · ' + bars.length + ' BARS'),
      el('span', {
        style: { fontSize: '9px', color: C.purple, fontFamily: MONO }
      }, vwap > 0 ? 'VWAP ' + vwap.toFixed(2) : '')
    ]));

    // Compute SVG dimensions
    var W = 320, H = 110, padT = 6, padB = 14, padL = 4, padR = 40;
    var plotW = W - padL - padR, plotH = H - padT - padB;
    var maxBars = Math.min(bars.length, 30);
    var use = bars.slice(-maxBars);
    var barW = plotW / use.length;
    var wickW = 1;
    var bodyW = Math.max(2, barW - 2);

    // Price range — extend slightly so body edges don't touch
    var hi = -Infinity, lo = Infinity;
    use.forEach(function (b) {
      if (b.h > hi) hi = b.h;
      if (b.l < lo) lo = b.l;
    });
    if (high > hi) hi = high;
    if (low > 0 && low < lo) lo = low;
    if (vwap > 0) { if (vwap > hi) hi = vwap; if (vwap < lo) lo = vwap; }
    var rng = hi - lo || 1;
    var pad = rng * 0.04;
    hi += pad; lo -= pad; rng = hi - lo;
    function y(price) {
      return padT + plotH - ((price - lo) / rng) * plotH;
    }

    var svgNS = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.style.display = 'block';
    svg.style.maxWidth = '100%';

    // Background
    var bg = document.createElementNS(svgNS, 'rect');
    bg.setAttribute('x', 0); bg.setAttribute('y', 0);
    bg.setAttribute('width', W); bg.setAttribute('height', H);
    bg.setAttribute('fill', C.bg);
    svg.appendChild(bg);

    // VWAP line
    if (vwap > 0 && vwap >= lo && vwap <= hi) {
      var vy = y(vwap);
      var vline = document.createElementNS(svgNS, 'line');
      vline.setAttribute('x1', padL); vline.setAttribute('x2', W - padR);
      vline.setAttribute('y1', vy); vline.setAttribute('y2', vy);
      vline.setAttribute('stroke', C.purple);
      vline.setAttribute('stroke-width', 1);
      vline.setAttribute('stroke-dasharray', '3,2');
      vline.setAttribute('opacity', 0.7);
      svg.appendChild(vline);
    }

    // Today high line
    if (high > 0 && high >= lo && high <= hi) {
      var hy = y(high);
      var hl = document.createElementNS(svgNS, 'line');
      hl.setAttribute('x1', padL); hl.setAttribute('x2', W - padR);
      hl.setAttribute('y1', hy); hl.setAttribute('y2', hy);
      hl.setAttribute('stroke', C.green); hl.setAttribute('stroke-width', 0.5);
      hl.setAttribute('stroke-dasharray', '1,3'); hl.setAttribute('opacity', 0.5);
      svg.appendChild(hl);
    }

    // Today low line
    if (low > 0 && low >= lo && low <= hi) {
      var ly = y(low);
      var ll = document.createElementNS(svgNS, 'line');
      ll.setAttribute('x1', padL); ll.setAttribute('x2', W - padR);
      ll.setAttribute('y1', ly); ll.setAttribute('y2', ly);
      ll.setAttribute('stroke', C.red); ll.setAttribute('stroke-width', 0.5);
      ll.setAttribute('stroke-dasharray', '1,3'); ll.setAttribute('opacity', 0.5);
      svg.appendChild(ll);
    }

    // Candles
    use.forEach(function (b, i) {
      var cx = padL + i * barW + barW / 2;
      var color = b.c >= b.o ? C.green : C.red;
      // Wick
      var w = document.createElementNS(svgNS, 'line');
      w.setAttribute('x1', cx); w.setAttribute('x2', cx);
      w.setAttribute('y1', y(b.h)); w.setAttribute('y2', y(b.l));
      w.setAttribute('stroke', color); w.setAttribute('stroke-width', wickW);
      svg.appendChild(w);
      // Body
      var by1 = y(Math.max(b.o, b.c));
      var by2 = y(Math.min(b.o, b.c));
      var bodyH = Math.max(1, by2 - by1);
      var body = document.createElementNS(svgNS, 'rect');
      body.setAttribute('x', cx - bodyW / 2); body.setAttribute('y', by1);
      body.setAttribute('width', bodyW); body.setAttribute('height', bodyH);
      body.setAttribute('fill', color);
      svg.appendChild(body);
    });

    // Right-axis labels (hi, vwap, lo)
    function axisLabel(val, yPos, color) {
      var tx = document.createElementNS(svgNS, 'text');
      tx.setAttribute('x', W - padR + 3);
      tx.setAttribute('y', yPos + 3);
      tx.setAttribute('fill', color);
      tx.setAttribute('font-family', MONO);
      tx.setAttribute('font-size', '8');
      tx.textContent = val.toFixed(val > 1000 ? 0 : 2);
      svg.appendChild(tx);
    }
    axisLabel(hi, padT, C.textMute);
    axisLabel(lo, padT + plotH, C.textMute);
    if (vwap > 0 && vwap >= lo && vwap <= hi) axisLabel(vwap, y(vwap), C.purple);

    wrap.appendChild(svg);
    return wrap;
  }

  // ── Price Action / Smart Money Concepts panel ──────────────────────────
  // Renders FVG, Order Block, BOS/CHoCH, liquidity sweep, EMA alignment,
  // 5m candle closure verdict. Every element degrades to "—" when data
  // is insufficient — nothing fake is ever displayed.
  function renderPriceActionPanel() {
    var wrap = el('div', {
      style: {
        background: C.card, borderBottom: '1px solid ' + C.divider,
        padding: '8px 10px'
      }
    });
    if (!state.selected) return wrap;
    var raw = state.selected._raw || {};
    var pa = priceAction.analyze(raw);

    // Header
    wrap.appendChild(el('div', {
      style: {
        fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px',
        color: C.textSec, marginBottom: '6px'
      }
    }, 'PRICE ACTION · SMART MONEY CONCEPTS'));

    if (pa.status !== 'ok') {
      wrap.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'Insufficient 5m bars for SMC analysis'));
      return wrap;
    }

    // 2-column grid — left: structure reads, right: candle + EMA
    var grid = el('div', {
      style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }
    });

    // ── LEFT: FVG + OB + BOS/CHoCH + Sweep ─────────────────────
    var leftCol = el('div', {
      style: { background: C.bg, borderRadius: '4px', padding: '6px 8px' }
    });

    // FVG
    var fvgText, fvgColor = C.textMute;
    if (pa.nearFvg && pa.nearFvg.inFvg) {
      fvgText = 'Inside ' + pa.nearFvg.type + ' FVG';
      fvgColor = pa.nearFvg.type === 'BULL' ? C.green : C.red;
    } else if (pa.fvg.length > 0) {
      fvgText = pa.fvg.length + ' recent FVG(s), none active';
    } else {
      fvgText = 'No recent FVGs';
    }
    leftCol.appendChild(smcRow('FVG', fvgText, fvgColor));

    // Order Block
    var obText = '—', obColor = C.textMute;
    if (pa.orderBlock) {
      if (pa.orderBlock.bull && pa.orderBlock.bear) {
        obText = 'Bull OB + Bear OB active';
      } else if (pa.orderBlock.bull) {
        obText = 'Bull OB at ' + pa.orderBlock.bull.bottom.toFixed(2);
        obColor = C.green;
      } else if (pa.orderBlock.bear) {
        obText = 'Bear OB at ' + pa.orderBlock.bear.top.toFixed(2);
        obColor = C.red;
      } else {
        obText = 'No active OB';
      }
    }
    leftCol.appendChild(smcRow('Order Block', obText, obColor));

    // BOS / CHoCH
    var bcText = '—', bcColor = C.textMute;
    if (pa.bosChoch && pa.bosChoch.signals && pa.bosChoch.signals.length > 0) {
      var sigs = pa.bosChoch.signals.map(function (s) { return s.type.replace('_', ' '); }).join(', ');
      bcText = sigs;
      var anyBull = pa.bosChoch.signals.some(function (s) { return s.type.indexOf('BULL') > 0; });
      bcColor = anyBull ? C.green : C.red;
    } else {
      bcText = 'Structure intact';
    }
    leftCol.appendChild(smcRow('BOS/CHoCH', bcText, bcColor));

    // Liquidity Sweep
    var swText = '—', swColor = C.textMute;
    if (pa.liquiditySweep && pa.liquiditySweep.length > 0) {
      var swType = pa.liquiditySweep[0].type.replace('_', ' ');
      swText = swType;
      swColor = swType.indexOf('BULL') >= 0 ? C.green : C.red;
    } else {
      swText = 'No sweep';
    }
    leftCol.appendChild(smcRow('Liq Sweep', swText, swColor));

    grid.appendChild(leftCol);

    // ── RIGHT: EMA + Candle ───────────────────────────────────
    var rightCol = el('div', {
      style: { background: C.bg, borderRadius: '4px', padding: '6px 8px' }
    });

    // EMA alignment
    if (pa.ema) {
      var emaLabel = pa.ema.alignment.replace('_', ' ');
      var emaColor = pa.ema.alignment === 'STACKED_BULL' ? C.green
                    : pa.ema.alignment === 'STACKED_BEAR' ? C.red : C.textSec;
      rightCol.appendChild(smcRow('EMA 9/21/50', emaLabel, emaColor));
      rightCol.appendChild(smcRow('EMA values',
        pa.ema.ema9.toFixed(1) + ' / ' + pa.ema.ema21.toFixed(1) + ' / ' + pa.ema.ema50.toFixed(1),
        C.textSec));
    } else {
      rightCol.appendChild(smcRow('EMA 9/21/50', 'insufficient bars', C.textMute));
    }

    // Candle closure
    if (pa.candle) {
      var candleLabel = pa.candle.direction + ' · ' + pa.candle.strength;
      var candleColor = pa.candle.direction === 'BULL' ? C.green
                      : pa.candle.direction === 'BEAR' ? C.red : C.textSec;
      rightCol.appendChild(smcRow('5m candle', candleLabel, candleColor));
      rightCol.appendChild(smcRow('Body %', pa.candle.bodyPct.toFixed(0) + '%', C.textSec));
      if (pa.candle.wickSignal) {
        rightCol.appendChild(smcRow('Wick', pa.candle.wickSignal.replace('_', ' '), C.orange));
      }
    } else {
      rightCol.appendChild(smcRow('5m candle', 'no data', C.textMute));
    }

    grid.appendChild(rightCol);
    wrap.appendChild(grid);
    return wrap;
  }

  // Small helper for SMC rows — label on left, value on right
  function smcRow(label, value, color) {
    return el('div', {
      style: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '2px 0', fontSize: '10px', fontFamily: MONO, lineHeight: 1.3
      }
    }, [
      el('span', { style: { color: C.textSec, fontWeight: 600 } }, label),
      el('span', { style: { color: color, fontWeight: 700, textAlign: 'right' } }, value)
    ]);
  }

  // ── External feeds panel (GIFT NIFTY / US premarket + IV term + order flow) ─
  // Shows pre-open context above the main detail stack. Degrades to
  // "awaiting feed" when data isn't cached yet.
  function renderExternalsPanel() {
    var wrap = el('div', {
      style: {
        background: C.card, borderBottom: '1px solid ' + C.divider,
        padding: '8px 10px'
      }
    });
    if (!state.selected) return wrap;
    var raw = state.selected._raw || {};

    // Header
    wrap.appendChild(el('div', {
      style: {
        fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px',
        color: C.textSec, marginBottom: '6px'
      }
    }, 'EXTERNAL FEEDS · PRE-OPEN CONTEXT'));

    // Get the right feed for current region
    var region = (raw._region) || state.region || 'IN';
    var gift = externalFeeds.giftReport();
    var usPre = externalFeeds.usPreReport();
    var ext = region === 'IN' ? gift : usPre;
    var feedName = region === 'IN' ? 'GIFT NIFTY' : 'US Futures';

    // Three-column grid: Gap | VIX | IV Curve
    var grid = el('div', {
      style: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }
    });

    // Col 1: Pre-open gap
    var gapCol = el('div', {
      style: { background: C.bg, borderRadius: '4px', padding: '6px 8px' }
    });
    gapCol.appendChild(el('div', {
      style: { fontSize: '9px', fontWeight: 700, color: C.textSec, marginBottom: '3px' }
    }, feedName));
    if (ext && ext.status === 'ok') {
      var gapColor = ext.gap > 0.15 ? C.green : ext.gap < -0.15 ? C.red : C.textSec;
      gapCol.appendChild(el('div', {
        style: { fontSize: '14px', fontWeight: 800, color: gapColor, fontFamily: MONO }
      }, (ext.gap >= 0 ? '+' : '') + ext.gap.toFixed(2) + '%'));
      gapCol.appendChild(el('div', {
        style: { fontSize: '9px', color: C.textMute, fontFamily: MONO, marginTop: '2px' }
      }, ext.label.replace(/_/g, ' ')));
    } else {
      gapCol.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'awaiting feed'));
    }
    grid.appendChild(gapCol);

    // Col 2: VIX
    var vixCol = el('div', {
      style: { background: C.bg, borderRadius: '4px', padding: '6px 8px' }
    });
    vixCol.appendChild(el('div', {
      style: { fontSize: '9px', fontWeight: 700, color: C.textSec, marginBottom: '3px' }
    }, region === 'IN' ? 'INDIA VIX' : 'VIX'));
    if (ext && ext.status === 'ok' && ext.vix) {
      var vixColor = ext.vixChange > 5 ? C.red : ext.vixChange < -5 ? C.green : C.textSec;
      vixCol.appendChild(el('div', {
        style: { fontSize: '14px', fontWeight: 800, color: C.textPri, fontFamily: MONO }
      }, ext.vix.toFixed(2)));
      vixCol.appendChild(el('div', {
        style: { fontSize: '9px', color: vixColor, fontFamily: MONO, marginTop: '2px' }
      }, (ext.vixChange >= 0 ? '+' : '') + ext.vixChange.toFixed(2) + '%'));
    } else {
      vixCol.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'awaiting feed'));
    }
    grid.appendChild(vixCol);

    // Col 3: IV term structure
    var ivCol = el('div', {
      style: { background: C.bg, borderRadius: '4px', padding: '6px 8px' }
    });
    ivCol.appendChild(el('div', {
      style: { fontSize: '9px', fontWeight: 700, color: C.textSec, marginBottom: '3px' }
    }, 'IV TERM CURVE'));
    var iv = ivTermStructure.analyze(raw);
    if (iv.status === 'ok') {
      var shapeColor = iv.shape === 'INVERTED' ? C.red
                      : iv.shape === 'HUMPED' ? C.orange
                      : iv.shape === 'NORMAL' ? C.green : C.textSec;
      ivCol.appendChild(el('div', {
        style: { fontSize: '13px', fontWeight: 800, color: shapeColor, fontFamily: MONO }
      }, iv.shape));
      ivCol.appendChild(el('div', {
        style: { fontSize: '9px', color: C.textMute, fontFamily: MONO, marginTop: '2px' }
      }, iv.nearIv.toFixed(1) + '% → ' + iv.farIv.toFixed(1) + '%'));
    } else {
      ivCol.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'no term data'));
    }
    grid.appendChild(ivCol);

    wrap.appendChild(grid);

    // Order flow row — if trade is selected with ATM strike, show summary
    var atmMatch = state.selected.strike
      ? String(state.selected.strike).match(/(\d+(\.\d+)?)/) : null;
    if (atmMatch) {
      var atmStrike = parseFloat(atmMatch[1]);
      var flow = orderFlow.summary(raw, atmStrike, state.selected.side);
      if (flow.status === 'ok') {
        var flowRow = el('div', {
          style: {
            marginTop: '6px', padding: '6px 8px',
            background: C.bg, borderRadius: '4px',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            fontSize: '10px', fontFamily: MONO
          }
        });
        var liqColor = flow.liquidity === 'TIGHT' ? C.green
                      : flow.liquidity === 'NORMAL' ? C.textSec
                      : flow.liquidity === 'WIDE' ? C.orange : C.red;
        var flowColor = flow.flow === 'BUYER_AGGRESSION' ? C.green
                       : flow.flow === 'SELLER_AGGRESSION' ? C.red : C.textSec;
        flowRow.appendChild(el('span', {
          style: { color: C.textSec, fontWeight: 700 }
        }, 'ORDER FLOW'));
        flowRow.appendChild(el('span', {
          style: { color: liqColor, fontWeight: 700 }
        }, flow.liquidity + ' spreads ' + flow.avgSpreadPct.toFixed(1) + '%'));
        flowRow.appendChild(el('span', {
          style: { color: flowColor, fontWeight: 700 }
        }, flow.flow.replace(/_/g, ' ')));
        wrap.appendChild(flowRow);
      }
    }

    return wrap;
  }

  // ── Greeks + IV/HV panel (ported from Quick Trade) ──────────────────────
  // Renders Δ/Γ/Θ/Vega for the selected trade's option plus IV vs HV
  // comparison. Shows nothing if no trade selected.
  function renderGreeksVolPanel() {
    var wrap = el('div', {
      style: {
        background: C.card, borderBottom: '1px solid ' + C.divider,
        padding: '8px 10px', fontFamily: MONO
      }
    });
    if (!state.selected) {
      wrap.appendChild(el('div', {
        style: { color: C.textMute, fontSize: '10px', fontStyle: 'italic' }
      }, 'Select a trade to see Greeks and IV/HV'));
      return wrap;
    }

    var t = state.selected;
    var raw = t._raw || {};
    var spot = raw.spot || 0;
    var atmIV = raw.atm_iv || 0;
    var bars = raw.ohlc_bars || [];

    // Parse strike from "24500 CE" → 24500
    var strikeNum = 0;
    var strikeStr = String(t.strike).split(' ')[0];
    strikeNum = parseFloat(strikeStr) || raw.atm_strike || 0;
    var optType = t.side || 'CE';

    // DTE
    var dte = pricingMath.dteFromExpiry(raw.expiry);
    var g = pricingMath.greeks(spot, strikeNum, dte, atmIV, optType);

    // Header
    wrap.appendChild(el('div', {
      style: {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: '6px'
      }
    }, [
      el('span', {
        style: { fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px', color: C.textSec }
      }, 'GREEKS & VOLATILITY'),
      el('span', {
        style: { fontSize: '9px', color: C.textMute }
      }, dte + 'D · IV ' + (atmIV > 0 ? atmIV.toFixed(1) + '%' : '—'))
    ]));

    if (!g) {
      wrap.appendChild(el('div', {
        style: { color: C.textMute, fontSize: '10px', fontStyle: 'italic' }
      }, 'Greeks unavailable (missing spot/strike/IV)'));
      return wrap;
    }

    // Greeks row
    var greeks = [
      { label: 'Δ', name: 'Delta', val: g.delta.toFixed(3), color: C.blue,
        tip: 'Premium change per 1-unit spot move' },
      { label: 'Γ', name: 'Gamma', val: g.gamma.toFixed(4), color: C.orange,
        tip: 'Delta change per 1-unit spot move' },
      { label: 'Θ', name: 'Theta', val: g.theta.toFixed(2), color: C.red,
        tip: 'Premium decay per day' },
      { label: 'Vega', name: 'Vega', val: g.vega.toFixed(2), color: C.green,
        tip: 'Premium change per 1% IV move' }
    ];

    var greeksRow = el('div', {
      style: {
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px',
        marginBottom: '6px'
      }
    });
    greeks.forEach(function (gr) {
      greeksRow.appendChild(el('div', {
        title: gr.name + ': ' + gr.tip,
        style: {
          background: C.bg, borderRadius: '4px', padding: '4px 6px',
          borderTop: '2px solid ' + gr.color, textAlign: 'center'
        }
      }, [
        el('div', { style: { fontSize: '9px', color: gr.color, fontWeight: 800 } }, gr.label),
        el('div', { style: { fontSize: '12px', color: C.textPri, fontWeight: 700 } }, gr.val)
      ]));
    });
    wrap.appendChild(greeksRow);

    // Gamma explosion warning for 0-1 DTE
    if (dte <= 1 && g.gamma > 0) {
      wrap.appendChild(el('div', {
        style: {
          background: C.orange + '15', borderLeft: '2px solid ' + C.orange,
          padding: '4px 6px', fontSize: '9px', color: C.orange,
          fontWeight: 700, marginBottom: '6px'
        }
      }, '⚡ ' + dte + 'D expiry — gamma ' + g.gamma.toFixed(4) +
          ' means small spot moves create large premium swings'));
    }

    // IV vs HV block
    var iv_hv = volMath.analyze(atmIV, bars);
    if (iv_hv.status === 'ok') {
      var verdictColor =
        iv_hv.verdict === 'OVERPRICED' || iv_hv.verdict === 'ELEVATED' ? C.red :
        iv_hv.verdict === 'UNDERPRICED' || iv_hv.verdict === 'DISCOUNTED' ? C.green :
        C.blue;
      var ivHvRow = el('div', {
        style: {
          background: C.bg, borderRadius: '4px', padding: '6px 8px',
          borderLeft: '2px solid ' + verdictColor
        }
      });
      ivHvRow.appendChild(el('div', {
        style: {
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: '3px'
        }
      }, [
        el('span', { style: { fontSize: '9px', color: verdictColor, fontWeight: 800 } },
          'IV/HV: ' + iv_hv.ratio.toFixed(2) + '× — ' + iv_hv.verdict),
        el('span', { style: { fontSize: '9px', color: C.textSec, fontFamily: MONO } },
          'IV ' + iv_hv.iv.toFixed(1) + '% · HV ' + iv_hv.hv.toFixed(1) + '%')
      ]));
      ivHvRow.appendChild(el('div', {
        style: { fontSize: '9px', color: C.textMute }
      }, iv_hv.action));
      wrap.appendChild(ivHvRow);
    } else {
      wrap.appendChild(el('div', {
        style: { fontSize: '9px', color: C.textMute, fontStyle: 'italic' }
      }, iv_hv.status === 'no_iv' ? 'IV not available' : 'HV needs more bars'));
    }

    return wrap;
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
        flex: '0 0 180px',    // fixed height; don't stretch into sibling territory
        height: '180px',
        background: C.bg, padding: '6px',
        borderTop: '1px solid ' + C.divider,
        overflow: 'hidden',
        display: 'flex', flexDirection: 'column'
      }
    });

    wrap.appendChild(el('div', {
      style: {
        fontSize: '10px', fontWeight: 800, color: C.textMute, letterSpacing: '1.5px',
        marginBottom: '4px', padding: '0 2px', flex: '0 0 auto'
      }
    }, 'VOICE LOG'));

    var list = el('div', {
      style: {
        flex: '1 1 auto', minHeight: 0,
        overflowY: 'auto', overflowX: 'hidden',
        scrollbarWidth: 'thin', scrollbarColor: C.divider + ' ' + C.bg
      }
    });
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
        display: 'grid', gridTemplateColumns: '16% 20% 8% 10% 18% 1fr',
        padding: '4px 8px',
        fontSize: '10px', fontWeight: 800, color: C.textMute, letterSpacing: '1.5px',
        borderBottom: '1px solid ' + C.divider
      }
    }, [
      el('div', {}, 'SYMBOL'),
      el('div', {}, 'STRIKE'),
      el('div', {}, 'DIR'),
      el('div', {}, 'SCORE'),
      el('div', {}, 'STATE'),
      el('div', {}, 'TREND')
    ]));

    var body = el('div', {
      style: {
        flex: 1, overflowY: 'auto', overflowX: 'hidden', minHeight: 0,
        scrollbarWidth: 'thin', scrollbarColor: C.divider + ' ' + C.bg
      }
    });
    // Apply search filter to scanner too
    var scanFilter = state.searchFilter || '';
    var scanSource = scanFilter
      ? state.scanner.filter(function (r) {
          return (r.symbol || '').toUpperCase().indexOf(scanFilter) >= 0;
        })
      : state.scanner;
    // If filter active show everything matching, else top 6
    var displayScan = scanFilter ? scanSource : scanSource.slice(0, 6);

    if (displayScan.length === 0) {
      body.appendChild(el('div', {
        style: {
          color: C.textMute, fontSize: '10px', fontStyle: 'italic',
          padding: '10px', textAlign: 'center'
        }
      }, scanFilter ? 'No scanner matches for "' + scanFilter + '"' : 'Loading scanner…'));
    }
    displayScan.forEach(function (r, i) {
      var trend = r.trend || [r.score, r.score, r.score];
      var up = trend[trend.length - 1] > trend[0];
      var dn = trend[trend.length - 1] < trend[0];
      var tColor = up ? C.green : dn ? C.red : C.textSec;
      var tMark = up ? '▲' : dn ? '▼' : '■';

      body.appendChild(el('div', {
        style: {
          display: 'grid', gridTemplateColumns: '16% 20% 8% 10% 18% 1fr',
          height: '26px', alignItems: 'center', padding: '0 8px',
          fontSize: '13px', fontFamily: MONO,
          borderBottom: i < displayScan.length - 1 ? '1px solid ' + C.divider : 'none',
          color: C.textPri, lineHeight: 1.1
        }
      }, [
        el('div', { style: { fontWeight: 600 } }, r.symbol),
        el('div', { style: { color: C.textSec, fontFamily: MONO } }, r.strike || '—'),
        el('div', { style: { color: r.direction === 'CE' ? C.green : C.red, fontWeight: 700 } }, r.direction),
        el('div', { style: { color: confColor(r.score), fontWeight: 700 } }, String(r.score)),
        el('div', {}, pill(r.state, true)),
        el('div', { style: { color: tColor, display: 'flex', alignItems: 'center', gap: '6px' } }, [
          el('span', {}, trend.join(' → ')),
          el('span', {}, tMark)
        ])
      ]));
    });

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
    // ── Portfolio risk guardrails — check before anything else ──
    var gate = portfolioRisk.checkAllow();
    if (!gate.allow) {
      pushLog('BLOCKED: ' + gate.reason, C.red);
      if (state.voiceOn) speak('Trade blocked: ' + gate.reason);
      return;
    }

    // Regime-adjusted Kelly sizing — no more fixed lot
    var baseSaved = kellySizer.fractional;
    kellySizer.fractional = baseSaved * regimeDetector.kellyMultiplier();
    var sizing = kellySizer.size(t);
    kellySizer.fractional = baseSaved;

    if (sizing.lots === 0 || sizing.error) {
      pushLog('SKIP ' + t.symbol + ' — ' + (sizing.reason || sizing.error), C.orange);
      speak('Skipping ' + t.symbol + ' — negative edge');
      return;
    }

    // Execution cost forecast
    var costs = execCostModel.computeCost(t, sizing.lots, state.region);

    // Attach sizing info to trade so paperPortfolio.open captures it
    t.sizingLots = sizing.lots;
    t.sizingRupees = sizing.rupees;
    t.sizingPct = sizing.pctOfCapital;
    t.costTotal = costs.total;
    t.costBreakEvenPct = costs.breakEvenPct;

    var pos = paperPortfolio.open(t);
    portfolioRisk.markOpened();
    pos.sizingLots = sizing.lots;
    pos.sizingPct = sizing.pctOfCapital;
    pos.costBreakEvenPct = costs.breakEvenPct;
    paperPortfolio.save();

    var ccy = pos.currency || (state.region === 'US' ? '$' : '₹');
    pushLog('OPEN ' + t.symbol + ' ' + t.strike + ' · ' +
            sizing.lots + ' lot' + (sizing.lots > 1 ? 's' : '') +
            ' (' + sizing.pctOfCapital.toFixed(1) + '% cap) · ' +
            'BE ' + costs.breakEvenPct.toFixed(2) + '% · ' +
            'Kelly ' + (sizing.winProb * 100).toFixed(0) + '%@' + sizing.payoffRatio.toFixed(1) + 'R',
            C.green);
    pushLog('  cost: ' + ccy + costs.total.toFixed(2) +
            ' (' + costs.totalPctOfTurnover.toFixed(2) + '% turnover) · ' +
            'regime: ' + regimeDetector.label(), C.textSec);
    // Voice covers: symbol, strike, lot sizing, capital %, break-even %.
    // Short enough to not delay but complete enough for hands-off trading.
    speak(t.symbol + ' ' + t.strike + ' opened. ' +
          sizing.lots + ' lot' + (sizing.lots > 1 ? 's' : '') +
          ', ' + sizing.pctOfCapital.toFixed(0) + ' percent capital' +
          ', break even ' + costs.breakEvenPct.toFixed(1) + ' percent');
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
        var rejectDetails = []; // for console table
        raw.forEach(function (row) {
          var sym = row.sym || row.symbol || '?';
          if (!row.sym && !row.symbol) {
            rejectDetails.push({ sym: '?', reason: 'no symbol field' });
            return;
          }
          if (row.spot == null || row.spot <= 0) {
            rejectReasons.noSpot++;
            rejectDetails.push({ sym: sym, reason: 'no spot price', spot: row.spot });
            return;
          }
          if (!Array.isArray(row.chain_near_atm) || row.chain_near_atm.length === 0) {
            rejectReasons.noChain++;
            rejectDetails.push({ sym: sym, reason: 'no option chain', spot: row.spot });
            return;
          }
          var tr = mapScanRowToTrade(row);
          if (tr) {
            mapped.push(tr);
          } else {
            rejectReasons.insufficientFactors++;
            // Re-derive WHY it failed inside mapScanRowToTrade by checking each factor
            var reasonDetail = [];
            var bars = row.ohlc_bars || [];
            if (bars.length < 3) reasonDetail.push('bars<3');
            if (bars.length < 5) reasonDetail.push('bars<5 (VWAP)');
            if (bars.length < 6) reasonDetail.push('bars<6 (vol)');
            if (row.vwap == null || row.vwap <= 0) reasonDetail.push('no vwap');
            if (row._fallback) reasonDetail.push('fallback mode');
            rejectDetails.push({
              sym: sym, reason: 'mapScan returned null',
              spot: row.spot, bars: bars.length,
              vwap: row.vwap, fallback: row._fallback,
              chainLen: row.chain_near_atm.length,
              detail: reasonDetail.join(',')
            });
          }
        });
        mapped.sort(function (a, b) { return b.confidence - a.confidence; });

        // LOG: detailed per-ticker breakdown to console on every scan
        if (rejectDetails.length > 0 && typeof console.table === 'function') {
          console.log('%c[ActiveTrading] Scan results: ' + mapped.length + ' accepted, ' +
                      rejectDetails.length + ' rejected (out of ' + raw.length + ' scanned)',
                      'color:#F59E0B;font-weight:bold');
          if (mapped.length > 0) {
            console.log('Accepted:', mapped.map(function(t) {
              return { sym: t.symbol, conf: t.confidence, side: t.side, state: t.state, reason: t.reason };
            }));
          }
          if (rejectDetails.length > 0 && rejectDetails.length <= 20) {
            console.log('Rejected breakdown:');
            console.table(rejectDetails);
          } else if (rejectDetails.length > 20) {
            console.log('Rejected breakdown (first 10):');
            console.table(rejectDetails.slice(0, 10));
          }
        }

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

        // ── REGIME DETECTION — update from lead index's bars ─────────────
        // Find the lead ticker for the active region (NIFTY for IN, SPY for US)
        var leadSym = state.region === 'US' ? 'SPY' : 'NIFTY';
        var leadRow = raw.filter(function (r) {
          return (r.sym === leadSym || r.symbol === leadSym);
        })[0];
        if (leadRow && Array.isArray(leadRow.ohlc_bars)) {
          var priorRegime = regimeDetector.current;
          var newRegime = regimeDetector.classify(leadRow.ohlc_bars);
          // Voice-alert on regime TRANSITION (not every scan — avoid chatter)
          if (priorRegime !== newRegime && priorRegime !== 'UNKNOWN' && newRegime !== 'UNKNOWN') {
            var spoken = ({
              TRENDING_UP: 'Trending up. Size up',
              TRENDING_DN: 'Trending down. Size up',
              RANGING:     'Regime changed: ranging. Reduce size',
              VOLATILE:    'Regime changed: volatile. Half size, raise minimum score',
              MIXED:       'Regime mixed'
            })[newRegime] || 'Regime changed';
            if (state.voiceOn) speak(spoken);
            pushLog('REGIME: ' + priorRegime + ' → ' + newRegime + ' (Kelly ×' +
                    regimeDetector.kellyMultiplier().toFixed(2) + ')', C.orange);
          }
        }

        // ── ALPHA DECAY — voice-alert on status transition ────────────────
        // Only fire when we have enough data AND status has changed since last check
        var priorDecayStatus = state._priorDecayStatus || 'INSUFFICIENT_DATA';
        var currentDecay = alphaDecay.read();
        if (currentDecay.status !== priorDecayStatus &&
            currentDecay.status !== 'INSUFFICIENT_DATA') {
          var decayMsg = ({
            HEALTHY:   'Alpha healthy. Engine has edge',
            DEGRADING: 'Alpha degrading. High score signals losing edge',
            DECAYED:   'Alert: alpha decayed. Engine is noise. Pause trading'
          })[currentDecay.status];
          if (decayMsg) {
            if (state.voiceOn) speak(decayMsg);
            pushLog('ALPHA: ' + priorDecayStatus + ' → ' + currentDecay.status +
                    ' (edge ' + (currentDecay.spread >= 0 ? '+' : '') +
                    currentDecay.spread.toFixed(1) + '%)',
                    currentDecay.status === 'DECAYED' ? C.red :
                    currentDecay.status === 'DEGRADING' ? C.orange : C.green);
          }
        }
        state._priorDecayStatus = currentDecay.status;

        // ── LEAN-STYLE: emit Signals + tick paper portfolio on each scan ──
        // Each top-3 trade becomes a Signal record in the ledger. The paper
        // portfolio checks triggers/SL/target against current premium.
        var nowIso = new Date().toISOString();
        top3.forEach(function (t) {
          signalLedger.push({
            ts: nowIso, sym: t.symbol, strike: t.strike, side: t.side,
            score: t.confidence, state: t.state, reason: t.reason,
            spot: t._raw && t._raw.spot, premium: t.price,
            sl: t.sl, target: t.target, trigger: t.trigger,
            region: state.region,
            missing: t.missingFactors || []
          });
        });
        // Also tick portfolio with current trade data so pending → active,
        // active → won/lost transitions can fire.
        var tradeDataMap = {};
        top3.forEach(function (t) { tradeDataMap[t.id] = t; });
        paperPortfolio.tick(tradeDataMap);

        // Secondary scanner — ranks 4-9, uses score history for real trend arrows
        var scannerPool = mapped.filter(function (m) {
          return top3.filter(function (t) { return t.id === m.id; }).length === 0;
        });
        state.scanner = scannerPool.slice(0, 6).map(function (t) {
          var h = state.scoreHistory[t.id];
          var trend = (h && h.length >= 2) ? h : [t.confidence, t.confidence, t.confidence];
          return {
            symbol: t.symbol, direction: t.side,
            strike: t.strike, // spec: show strike alongside symbol for clarity
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
    //
    // Also kicks off external-feed refresh (GIFT NIFTY / US premarket).
    // These are independently cached inside externalFeeds with their own
    // TTL, so calling on every 5m bar is safe — cached hits return instantly.
    var promises = [refreshTopTrades(), refreshChain()];
    if (state.region === 'IN') {
      promises.push(externalFeeds.fetchGift().catch(function () { return null; }));
    } else {
      promises.push(externalFeeds.fetchUsPre().catch(function () { return null; }));
    }
    return Promise.all(promises);
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

        // Entry confirmed check — plain English
        if ((state.selected.side === 'CE' && newClose >= state.selected.trigger) ||
            (state.selected.side === 'PE' && newClose <= state.selected.trigger)) {
          pushLog('Entry confirmed, confidence ' + state.selected.confidence + '%', C.green);
          speak(state.selected.symbol + ' ' + state.selected.strike +
                ' entry confirmed. Confidence ' + state.selected.confidence +
                ' percent. You can enter the trade now.');
        }
      }

      // ═══════════════════════════════════════════════════════════════════
      // LIVE TRADE LIFECYCLE — re-evaluate every open position
      // ═══════════════════════════════════════════════════════════════════
      // Build price lookup from current trades
      var priceLookup = {};
      (state.trades || []).forEach(function (t) { priceLookup[t.id] = t; });
      // Also include the selected trade in case it's an open position
      if (state.selected) priceLookup[state.selected.id] = state.selected;

      // Get recommendations per active position
      var recs = liveTradeGuide.evaluateAll(priceLookup);
      state.liveRecs = recs;  // stash for UI panel

      recs.forEach(function (rec) {
        var voiceLine = voiceGuide.lifecycleLine(rec);
        // Log in appropriate color
        var logColor = rec.action === 'EXIT' ? C.red
                     : rec.action === 'REDUCE' ? C.orange
                     : rec.action === 'ADD' ? C.green : C.blue;
        pushLog(rec.action + ': ' + rec.symbol + ' ' + rec.strike +
                ' · ' + rec.reason, logColor);
        // Only speak EXIT/ADD/REDUCE changes (every-bar CONTINUE is noisy).
        // Speak CONTINUE only if P&L crossed a notable threshold vs last bar.
        var shouldSpeak =
          rec.action === 'EXIT' ||
          rec.action === 'ADD' ||
          rec.action === 'REDUCE';

        // For CONTINUE, remember last spoken pnl bucket per position to avoid spam
        if (rec.action === 'CONTINUE') {
          state._lastSpokenBucket = state._lastSpokenBucket || {};
          var bucket = Math.floor(rec.pnlPct / 10) * 10;
          if (state._lastSpokenBucket[rec.positionId] !== bucket) {
            state._lastSpokenBucket[rec.positionId] = bucket;
            shouldSpeak = true;
          }
        }

        // For EXIT/REDUCE — auto-action on paper positions per institutional
        // discipline. On live broker integration this would stay advisory.
        if (rec.action === 'EXIT' && priceLookup[rec.positionId]) {
          // Trigger the monitor.closeNow which fires position:closed bus event
          // with the appropriate win/lost status based on exit price.
          var pos = paperPortfolio.positions[rec.positionId];
          if (pos) tradeMonitor.closeNow(rec.positionId, priceLookup[rec.positionId]
                    ? priceLookup[rec.positionId].price : pos.entryPremium,
                    'lifecycle_exit');
        }

        if (shouldSpeak && state.voiceOn) {
          speak(voiceLine);
        }
      });

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
    // ═══════════════════════════════════════════════════════════════════════
    // FULL-SCREEN OVERLAY MOUNT
    // ═══════════════════════════════════════════════════════════════════════
    // Previous versions modified the host page (.sc, .sbody, #deControls,
    // body.at-mode) to force the dark theme. When unmount didn't fire cleanly
    // (tab switches, back button), those modifications leaked into other
    // tabs and left them broken (Investor/Trader/Options).
    //
    // Clean fix: render Active Trading as a `position:fixed` overlay on top
    // of the whole page, with its own z-index sandbox. Host page is never
    // touched. Back button unmounts cleanly.
    //
    // The containerId arg is kept for API compatibility but NOT used for
    // DOM targeting — we always mount to <body> as an overlay.

    // Idempotent mounting — clean any prior instance
    if (mounted || document.getElementById('activeTradingOverlay')) {
      if (window.unmountActiveTrading) window.unmountActiveTrading();
    }

    installScopedStyles();

    // Build overlay host: full viewport, fixed, high z-index
    var overlay = document.createElement('div');
    overlay.id = 'activeTradingOverlay';
    overlay.setAttribute('style',
      'position:fixed;' +
      'top:0;left:0;right:0;bottom:0;' +
      'width:100vw;height:100vh;' +
      'background:#020617;' +
      'z-index:9999;' +
      'overflow:hidden;' +
      'display:flex;flex-direction:column;' +
      'color:#F8FAFC;' +
      'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif'
    );

    // Top bar with Back button — always visible at top of overlay
    var topBar = document.createElement('div');
    topBar.id = 'atTopBar';
    topBar.setAttribute('style',
      'flex:0 0 auto;' +
      'height:44px;' +
      'background:#0F172A;' +
      'border-bottom:1px solid #1E293B;' +
      'display:flex;align-items:center;' +
      'padding:0 12px;gap:10px'
    );

    // Back button — leaves overlay and returns to normal page
    var backBtn = document.createElement('button');
    backBtn.setAttribute('style',
      'background:transparent;border:1px solid #1E293B;' +
      'color:#F8FAFC;cursor:pointer;' +
      'padding:5px 12px;border-radius:4px;' +
      'font-size:12px;font-weight:700;letter-spacing:0.5px'
    );
    backBtn.textContent = '← BACK';
    backBtn.onclick = function () {
      if (window.unmountActiveTrading) window.unmountActiveTrading();
      // Also flip host app's mode so the tab buttons highlight correctly
      // and the user sees a real tab instead of a blank Decide with nothing mounted
      if (typeof window.switchDEMode === 'function') {
        try { window.switchDEMode('investor'); } catch (e) {}
      }
    };
    topBar.appendChild(backBtn);

    // Title
    var title = document.createElement('div');
    title.setAttribute('style',
      'flex:1;font-size:13px;font-weight:700;' +
      'letter-spacing:1px;color:#378ADD;font-family:monospace'
    );
    title.textContent = 'CELESYS · ACTIVE TRADING';
    topBar.appendChild(title);

    overlay.appendChild(topBar);

    // Main content — everything rendered by render() goes here
    var mountDiv = document.createElement('div');
    mountDiv.id = 'activeTradingMount';
    mountDiv.setAttribute('style',
      'flex:1 1 auto;' +
      'min-height:0;' +
      'overflow:hidden;' +
      'background:#020617;' +
      'display:flex;flex-direction:column'
    );
    overlay.appendChild(mountDiv);

    document.body.appendChild(overlay);

    // Prevent host page from scrolling behind the overlay
    state._prevBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    mounted = true;
    render(mountDiv);
    refreshAll();
    startTimers();

    // Debug helper for console
    window._atDebug = function () {
      var ov = document.getElementById('activeTradingOverlay');
      var mt = document.getElementById('activeTradingMount');
      var out = {
        overlay_present: !!ov,
        mount_present: !!mt,
        overlay_children: ov ? ov.children.length : 0,
        mount_children: mt ? mt.children.length : 0,
        mounted_flag: mounted,
        state_trades: state.trades.length,
        state_scanner: state.scanner.length,
        state_selected: state.selected ? state.selected.symbol : null,
        region: state.region,
        regime: regimeDetector.current,
        open_positions: (function () {
          var n = 0;
          for (var id in paperPortfolio.positions) {
            var p = paperPortfolio.positions[id];
            if (p.status === 'pending' || p.status === 'active') n++;
          }
          return n;
        })()
      };
      console.table([out]);
      return out;
    };

    console.log('%c[ActiveTrading] overlay mounted — host page untouched',
                'color:#22C55E;font-weight:bold;background:#020617;padding:4px 8px');
  };

  window.unmountActiveTrading = function () {
    mounted = false;
    stopTimers();

    // Stop any legacy MutationObserver / poll timer that may still be around
    // from prior buggy mount versions (nobody should have these anymore,
    // but being defensive).
    if (state._observer) { state._observer.disconnect(); state._observer = null; }
    if (state._pollTimer) { clearInterval(state._pollTimer); state._pollTimer = null; }
    if (state._raf) { cancelAnimationFrame(state._raf); state._raf = null; }

    // Restore host body scroll
    if (state._prevBodyOverflow != null) {
      document.body.style.overflow = state._prevBodyOverflow;
      state._prevBodyOverflow = null;
    }

    // LEGACY CLEANUP — if any prior mount version left host-page mutations
    // behind (body.at-mode, data-at-host attr, brutedNodes, hiddenSiblings),
    // undo them all now. Safe no-op when clean.
    document.body.classList.remove('at-mode');
    var legacyHosts = document.querySelectorAll('.sc[data-at-host="1"]');
    for (var i = 0; i < legacyHosts.length; i++) {
      legacyHosts[i].removeAttribute('data-at-host');
    }
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

    // Remove the overlay. Host page is untouched since mount didn't mutate it.
    var overlay = document.getElementById('activeTradingOverlay');
    if (overlay && overlay.parentNode) {
      overlay.parentNode.removeChild(overlay);
    }

    console.log('%c[ActiveTrading] overlay unmounted — host page restored',
                'color:#64748B;font-weight:bold');
  };
})();
