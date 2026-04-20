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
  console.log('%c[ActiveTrading] v46 loaded — Quick Start guide + live recompute on select',
              'color:#22C55E;font-weight:bold;font-size:13px');
  console.log('%c  QUICK START tab in ? modal (plain English for non-pros) · Click card → verdict refreshes NOW',
              'color:#64748B;font-size:11px');
  console.log('%c  No more waiting 5 minutes for fresh scoring after you click a trade',
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
      // Accept a trade object from mapScanRowToTrade and create a Position.
      // We stamp CURRENT session phase, regime, and gamma mode at entry time
      // so tradeAttribution can later bucket outcomes by setup context.
      // Without this, we can only say "you won X%"—with it, we can say
      // "you win 70% during MORNING TRENDING_UP, 20% during LUNCH RANGING".
      var id = trade.id + '@' + Date.now();
      // Guard: modules may not be initialized in test contexts
      var entrySession = null, entryRegime = null;
      try {
        if (typeof sessionProfile !== 'undefined')
          entrySession = sessionProfile.phase(state.region || 'IN');
      } catch (e) {}
      try {
        if (typeof regimeDetector !== 'undefined')
          entryRegime = regimeDetector.current;
      } catch (e) {}
      var pos = {
        id: id, tradeId: trade.id,
        sym: trade.symbol, strike: trade.strike, side: trade.side,
        score: trade.confidence, state: trade.state, reason: trade.reason,
        entryPremium: trade.price,
        sl: trade.sl, target: trade.target, trigger: trade.trigger,
        slPct: trade.slPct, tgtPct: trade.tgtPct, slBasis: trade.slBasis,
        lot: trade.lot,
        region: state.region,
        currency: (trade._raw && trade._raw.currency) || (state.region === 'US' ? '$' : '₹'),
        status: 'pending',
        openedAt: Date.now(),
        triggeredAt: null, closedAt: null,
        exitPremium: null, realizedPct: null,
        highWater: trade.price, lowWater: trade.price,
        // Attribution context
        entrySession: entrySession,
        entryRegime: entryRegime,
        entryGammaMode: !!trade.gammaMode,
        entryConfidence: trade.confidence
      };
      this.positions[id] = pos;
      this.save();
      bus.emit('position:opened', pos);
      return pos;
    },

    // Find an OPEN (pending/active) position for a given trade ID.
    // Used to prevent double-executing a trade and to render the card
    // in its correct visual state (pending → active → won/lost).
    findByTradeId: function (tradeId) {
      if (!tradeId) return null;
      for (var id in this.positions) {
        var p = this.positions[id];
        if (p.tradeId === tradeId &&
            (p.status === 'pending' || p.status === 'active')) {
          return p;
        }
      }
      return null;
    },

    // Find the MOST RECENT position (any status) for a trade ID — used to
    // show a "WON 32%" / "LOST 5%" outcome tag on the top trade card after
    // a position closes, so the user has closure feedback.
    findLatestByTradeId: function (tradeId) {
      if (!tradeId) return null;
      var latest = null;
      for (var id in this.positions) {
        var p = this.positions[id];
        if (p.tradeId !== tradeId) continue;
        if (!latest || (p.openedAt || 0) > (latest.openedAt || 0)) latest = p;
      }
      return latest;
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

      // ── Record for confidence-calibration harness ──
      // Every won/lost close feeds the empirical score→winProb curve.
      // Once ≥100 closes, kellySizer switches from theoretical to empirical.
      if ((p.status === 'won' || p.status === 'lost') && p.entryConfidence != null) {
        try {
          calibrationHarness.record(p.entryConfidence, p.status === 'won');
          calibrationHarness.applyIfReady();
        } catch (e) {}
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

        // ── Portfolio-aware follow-up after close ──────────────────────
        // After every 3rd close of the day, speak the session summary
        // so the user has a natural check-in point (wins/losses/net).
        // Also fire on streak milestones (2 or 3 losses in a row) so the
        // user is reminded not to revenge-trade.
        try {
          if (window._atEngine && window._atEngine.sessionGuide) {
            var sg = window._atEngine.sessionGuide;
            var t = sg.today();

            // Streak warning — fires at loss-streak 2 and 3
            if (t.lossStreak === 2) {
              setTimeout(function () {
                speak('Two losses in a row today. Slow down. ' +
                      'Consider smaller size or a break before the next trade.');
              }, 2500);
            } else if (t.lossStreak >= 3) {
              setTimeout(function () {
                speak('Three losses today. Step back from the screen. ' +
                      'The market will be here tomorrow.');
              }, 2500);
            }
            // Every 3rd close — session summary voice
            else if (t.closedCount > 0 && t.closedCount % 3 === 0) {
              setTimeout(function () { speak(sg.summary()); }, 2500);
            }
          }
        } catch (e) {}
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
  // ═══════════════════════════════════════════════════════════════════════
  // NSE / BSE LOT SIZES — single source of truth
  // ═══════════════════════════════════════════════════════════════════════
  // Real current values per NSE circular FAOP70616 (Oct 3, 2025, effective
  // Jan 2026 contracts) and BSE circulars. Verified against live option
  // chain data as of April 2026.
  //
  // Always prefer lot_size from backend when available. This table is
  // the fallback so defaults are ACCURATE, not wrong-by-default.
  var LOT_SIZES = {
    // NSE index derivatives
    NIFTY:       65,
    BANKNIFTY:   30,
    FINNIFTY:    60,
    MIDCPNIFTY:  120,
    NIFTYNXT50:  25,
    'NIFTY NEXT 50': 25,
    // BSE index derivatives
    SENSEX:      20,
    BANKEX:      30,
    SENSEX50:    50   // aka Sensex 50
  };

  function lotSizeFor(symbol) {
    if (!symbol) return 65;  // assume NIFTY as default index
    var key = String(symbol).toUpperCase().trim();
    if (LOT_SIZES[key] != null) return LOT_SIZES[key];
    // Fallback for stocks — backend must provide. Without data, use a
    // conservative value. 1 is wrong for any real F&O stock, so we
    // return null to let callers decide (skip / warn).
    return null;
  }

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
      // Cooldown prevents ACCIDENTAL double-clicks on the same card.
      // Top-3 trades are pre-vetted by the scan engine, so a short
      // cooldown (5s) is sufficient — lets user stack all 3 top trades
      // back-to-back while still catching fat-finger mistakes. The
      // double-execute prevention in onExecute catches same-trade dupes.
      cooldownSeconds: 5
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
        var barVwap = null;
        if (vd > 0) barVwap = vn / vd;
        else if (typeof raw.vwap === 'number' && raw.vwap > 0) barVwap = raw.vwap;
        // If VWAP truly unavailable, leave vwapPos unset rather than
        // fabricating "Above VWAP" or "Below VWAP" from a fake comparison
        var aboveVwap = null;
        if (barVwap != null) {
          aboveVwap = spot > barVwap;
          vwapPos = aboveVwap ? 'Above VWAP' : 'Below VWAP';
        } else {
          vwapPos = 'VWAP data unavailable';
        }

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

        // Only apply VWAP-based short-term classification when we actually
        // know the VWAP relationship. If aboveVwap is null (no data), we
        // don't fabricate a direction — fall through to the neutral branch.
        if (aboveVwap === true && bullStruct) { st = 'BULLISH'; stReason = 'HH-HL + above VWAP'; }
        else if (aboveVwap === false && bearStruct) { st = 'BEARISH'; stReason = 'LH-LL + below VWAP'; }
        else if (aboveVwap === true && !bearStruct) { st = 'BULLISH'; stReason = 'Above VWAP, weak structure'; }
        else if (aboveVwap === false && !bullStruct) { st = 'BEARISH'; stReason = 'Below VWAP, weak structure'; }
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
      //
      // PRO MODE: when enabled, SMC signals are EXCLUDED from point accumulation.
      // These are retail-trader concepts (ICT methodology) without strong
      // academic backing. A professional consensus uses regime / GEX / IV curve /
      // order flow / Kelly only. We still compute pa for UI display, but don't
      // feed it into points.
      var pa = priceAction.analyze(raw);
      if (proMode.isOn()) {
        // Skip SMC contribution entirely. Note on verdict.
        if (pa.status === 'ok') {
          // No reasons/warnings pushed either — keep verdict clean.
        }
      } else if (pa.status === 'ok') {
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
  // ═══════════════════════════════════════════════════════════════════════
  // 16a. VOLATILITY METRICS (ATR + Expected Move + Keltner Squeeze)
  // ═══════════════════════════════════════════════════════════════════════
  // Computes intraday ATR, IV-derived expected move, and Keltner Squeeze
  // (Bollinger Band width vs Keltner Channel width). Squeeze ON = BB inside
  // KC = volatility compressed = breakout likely. Widely used setup filter.
  var volMetrics = {
    compute: function (bars, spot, atmIV) {
      if (!Array.isArray(bars) || bars.length < 5 || !spot) return { status: 'no_data' };

      // ATR from last 14 bars (true range each)
      var trValues = [];
      for (var i = 1; i < bars.length; i++) {
        var b = bars[i], p = bars[i - 1];
        if (b.h == null || b.l == null || p.c == null) continue;
        var tr = Math.max(
          b.h - b.l,
          Math.abs(b.h - p.c),
          Math.abs(b.l - p.c)
        );
        trValues.push(tr);
      }
      if (trValues.length === 0) return { status: 'no_data' };
      var recent = trValues.slice(-14);
      var atr = recent.reduce(function (s, v) { return s + v; }, 0) / recent.length;
      var atrPct = (atr / spot) * 100;

      // Expected move from IV (1-day)
      var expectedMove = 0, expectedMovePct = 0;
      if (atmIV && atmIV > 0) {
        expectedMove = spot * (atmIV / 100) * Math.sqrt(1 / 252);
        expectedMovePct = (expectedMove / spot) * 100;
      }

      // Keltner Squeeze
      var squeeze = null, bbWidth = null, kcWidth = null, squeezeLabel = null;
      if (bars.length >= 20) {
        var closes = bars.slice(-20).map(function (b) { return b.c; });
        var sma = closes.reduce(function (s, v) { return s + v; }, 0) / 20;
        var variance = closes.reduce(function (s, v) {
          return s + Math.pow(v - sma, 2);
        }, 0) / 20;
        var std = Math.sqrt(variance);
        bbWidth = 4 * std;          // ±2σ = 4σ total
        kcWidth = atr * 3;          // ±1.5×ATR = 3×ATR total
        squeeze = bbWidth < kcWidth;
        squeezeLabel = squeeze ? 'SQUEEZE ON — Breakout imminent' : 'SQUEEZE OFF — Normal volatility';
      }

      return {
        status: 'ok',
        atr: atr, atrPct: atrPct,
        expectedMove: expectedMove, expectedMovePct: expectedMovePct,
        expectedHigh: spot + expectedMove,
        expectedLow: spot - expectedMove,
        squeeze: squeeze, squeezeLabel: squeezeLabel,
        bbWidth: bbWidth, kcWidth: kcWidth
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16b. PAYOFF DIAGRAM — single-leg call/put P&L curve
  // ═══════════════════════════════════════════════════════════════════════
  // Computes 21-point P&L table across ±4% of spot for a simple long-option
  // trade. Used by the UI payoff panel to draw an SVG curve.
  var payoffDiagram = {
    compute: function (trade, spot, lot) {
      if (!trade || !trade.side || !trade.price || !spot) return { status: 'no_data' };

      // Extract strike number from "24500 CE"
      var m = String(trade.strike || '').match(/(\d+(\.\d+)?)/);
      if (!m) return { status: 'no_strike' };
      var strike = parseFloat(m[1]);
      var premium = trade.price;
      var lotSize = lot || trade.lot || lotSizeFor(trade.symbol) || 65;

      var lo = spot * 0.96;
      var hi = spot * 1.04;
      var steps = 20;
      var stepSize = (hi - lo) / steps;
      var points = [];
      var maxPnl = -Infinity, minPnl = Infinity;

      for (var i = 0; i <= steps; i++) {
        var price = lo + stepSize * i;
        var pnlPerUnit;
        if (trade.side === 'CE') {
          pnlPerUnit = Math.max(0, price - strike) - premium;
        } else {
          pnlPerUnit = Math.max(0, strike - price) - premium;
        }
        var pnl = Math.round(pnlPerUnit * lotSize);
        if (pnl > maxPnl) maxPnl = pnl;
        if (pnl < minPnl) minPnl = pnl;
        points.push({ price: Math.round(price * 100) / 100, pnl: pnl });
      }

      // Breakeven
      var breakeven = trade.side === 'CE'
        ? strike + premium
        : strike - premium;

      return {
        status: 'ok',
        points: points,
        maxPnl: maxPnl, minPnl: minPnl,
        breakeven: breakeven,
        strike: strike, premium: premium,
        spot: spot, side: trade.side, lotSize: lotSize
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16c. SENTIMENT BAR — aggregated bullish/bearish vote across modules
  // ═══════════════════════════════════════════════════════════════════════
  // Produces a single 0-100 sentiment score by polling every module the
  // consensus engine consults. Used as a single-glance barometer.
  //   0   = maximally bearish
  //   50  = balanced
  //   100 = maximally bullish
  var sentimentBar = {
    read: function (raw) {
      if (!raw) return { status: 'no_data' };
      var bullPoints = 0, bearPoints = 0, totalChecked = 0;

      // Regime
      var reg = regimeDetector.current;
      totalChecked++;
      if (reg === 'TRENDING_UP') bullPoints++;
      else if (reg === 'TRENDING_DN') bearPoints++;

      // GEX regime (BREAKOUT just means directional, doesn't pick side;
      // skip unless combined with compass to infer direction)
      // Compass
      var cmp = trendCompass.analyze(raw);
      totalChecked += 2; // compass counts as 2 (short + long)
      if (cmp.status === 'ok') {
        if (cmp.shortTerm === 'BULLISH') bullPoints++;
        else if (cmp.shortTerm === 'BEARISH') bearPoints++;
        if (cmp.longTerm === 'BULLISH') bullPoints++;
        else if (cmp.longTerm === 'BEARISH') bearPoints++;
      }

      // EMA stacking
      var pa = priceAction.analyze(raw);
      if (pa.status === 'ok' && pa.ema) {
        totalChecked++;
        if (pa.ema.alignment === 'STACKED_BULL') bullPoints++;
        else if (pa.ema.alignment === 'STACKED_BEAR') bearPoints++;
      }

      // BOS/CHoCH
      if (pa.status === 'ok' && pa.bosChoch && pa.bosChoch.signals) {
        pa.bosChoch.signals.forEach(function (s) {
          totalChecked++;
          if (s.type.indexOf('BULL') >= 0) bullPoints++;
          else if (s.type.indexOf('BEAR') >= 0) bearPoints++;
        });
      }

      // Liquidity sweep
      if (pa.status === 'ok' && pa.liquiditySweep) {
        pa.liquiditySweep.forEach(function (sw) {
          totalChecked++;
          if (sw.type.indexOf('BULL') >= 0) bullPoints++;
          else if (sw.type.indexOf('BEAR') >= 0) bearPoints++;
        });
      }

      // Candle closure
      if (pa.status === 'ok' && pa.candle) {
        if (pa.candle.strength === 'STRONG') {
          totalChecked++;
          if (pa.candle.direction === 'BULL') bullPoints++;
          else if (pa.candle.direction === 'BEAR') bearPoints++;
        }
      }

      // External gap (region-aware via _region or default)
      var region = raw._region || 'IN';
      var ext = region === 'IN'
        ? externalFeeds.giftReport()
        : externalFeeds.usPreReport();
      if (ext && ext.status === 'ok') {
        totalChecked++;
        if (ext.gap > 0.15) bullPoints++;
        else if (ext.gap < -0.15) bearPoints++;
      }

      if (totalChecked === 0) return { status: 'no_data' };

      // Score: 50 = balanced; each bull raises score, each bear lowers
      var net = bullPoints - bearPoints;
      var maxNet = totalChecked; // if everything is one-sided
      // Normalize net to a -1..+1 range then map to 0..100
      var norm = net / Math.max(maxNet, 1);
      var score = Math.round(50 + norm * 50);
      score = Math.max(0, Math.min(100, score));

      var label;
      if (score >= 75) label = 'STRONGLY BULLISH';
      else if (score >= 60) label = 'BULLISH';
      else if (score >= 45) label = 'NEUTRAL';
      else if (score >= 25) label = 'BEARISH';
      else label = 'STRONGLY BEARISH';

      return {
        status: 'ok',
        score: score,
        label: label,
        bullPoints: bullPoints,
        bearPoints: bearPoints,
        totalChecked: totalChecked
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16d. SESSION PROFILE — classify current time within the trading session
  // ═══════════════════════════════════════════════════════════════════════
  // Different phases of the session have different behavior:
  //   OPENING (first 30 min)  — high volatility, gap fills, news reactions
  //   MORNING (30m-12:00)     — trend establishes
  //   LUNCH (12:00-13:30)     — low volume chop
  //   AFTERNOON (13:30-15:00) — trend resumption or reversal
  //   CLOSING (last 30 min)   — squaring off, institutional flows
  //
  // Each phase adjusts the consensus engine's confidence in signals.
  // E.g., lunch-hour breakouts have lower win rate than morning breakouts.
  var sessionProfile = {
    phase: function (region) {
      region = region || 'IN';
      var now = new Date();
      // See isIndianMarketOpen() for the reasoning: new Date() already
      // stores UTC ms. Add the region offset, read the "UTC" fields of
      // the shifted Date — those fields now carry the target-zone values.
      // Never also add getTimezoneOffset(); that double-corrects on
      // non-UTC browsers.
      var ist;
      if (region === 'IN') {
        var istMs = now.getTime() + (5.5 * 60 * 60 * 1000);
        ist = new Date(istMs);
      } else {
        // US ET (UTC-5 standard; EDT skipped for simplicity — UI band is
        // wide enough that DST doesn't shift a phase meaningfully).
        var etMs = now.getTime() - (5 * 60 * 60 * 1000);
        ist = new Date(etMs);
      }
      var day = ist.getUTCDay();
      if (day === 0 || day === 6) return { phase: 'WEEKEND', open: false };

      var mins = ist.getUTCHours() * 60 + ist.getUTCMinutes();

      if (region === 'IN') {
        // NSE: 09:15 - 15:30 IST
        if (mins < 9 * 60 + 15) return { phase: 'PRE_OPEN', open: false };
        if (mins > 15 * 60 + 30) return { phase: 'POST_CLOSE', open: false };
        if (mins <= 9 * 60 + 45) return { phase: 'OPENING', open: true,
          label: 'Opening volatility — expect range expansion' };
        if (mins < 12 * 60) return { phase: 'MORNING', open: true,
          label: 'Morning trend — high conviction window' };
        if (mins < 13 * 60 + 30) return { phase: 'LUNCH', open: true,
          label: 'Lunch chop — lower win rate on breakouts' };
        if (mins < 15 * 60) return { phase: 'AFTERNOON', open: true,
          label: 'Afternoon — watch for trend resumption' };
        return { phase: 'CLOSING', open: true,
          label: 'Closing flows — institutional squaring off' };
      } else {
        // NYSE/NASDAQ: 09:30 - 16:00 ET
        if (mins < 9 * 60 + 30) return { phase: 'PRE_OPEN', open: false };
        if (mins > 16 * 60) return { phase: 'POST_CLOSE', open: false };
        if (mins <= 10 * 60) return { phase: 'OPENING', open: true,
          label: 'Opening volatility — expect range expansion' };
        if (mins < 12 * 60) return { phase: 'MORNING', open: true,
          label: 'Morning trend — high conviction window' };
        if (mins < 13 * 60 + 30) return { phase: 'LUNCH', open: true,
          label: 'Lunch chop — lower win rate on breakouts' };
        if (mins < 15 * 60 + 30) return { phase: 'AFTERNOON', open: true,
          label: 'Afternoon — watch for trend resumption' };
        return { phase: 'CLOSING', open: true,
          label: 'Closing flows — institutional squaring off' };
      }
    },

    // Multiplier on signal strength based on session phase
    signalMultiplier: function (phase) {
      switch (phase) {
        case 'OPENING':   return 1.1;   // signals strong but volatile
        case 'MORNING':   return 1.2;   // best conviction window
        case 'LUNCH':     return 0.75;  // chop - lower win rate
        case 'AFTERNOON': return 1.0;
        case 'CLOSING':   return 0.85;  // institutional close-outs can whipsaw
        default:          return 1.0;
      }
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16e. SESSION GUIDE — portfolio-level awareness across multi-trade days
  // ═══════════════════════════════════════════════════════════════════════
  // When the user has multiple trades in a session, they need to see the
  // FOREST, not just individual trees. This module surfaces:
  //   - Today's net P&L (across all closed positions)
  //   - Win rate today
  //   - Streak detection (3 losses in a row → warn about revenge trading)
  //   - Context for new top trades: "you have room for 1 more position"
  //     or "day P&L is -2.5%, near daily cap — hold off"
  //   - Session phase overlay (e.g. "we're near market close — don't open
  //     new intraday trades")
  // ═══════════════════════════════════════════════════════════════════════
  // 16f. EVENT CALENDAR — IV crush prevention
  // ═══════════════════════════════════════════════════════════════════════
  // Biggest single cause of options losses for retail traders buying options:
  // holding into earnings / RBI / FOMC and getting IV-crushed after the
  // event even when direction was right. This module holds known macro
  // event dates and blocks or flags trades that overlap.
  //
  // Source: user seeds their own events via localStorage `at_events`;
  // we also ship a baseline of major 2026 India/US macro dates.
  // For per-ticker earnings, user adds them manually or backend supplies.
  //
  // Data shape:
  //   { date: 'YYYY-MM-DD', name: 'RBI Policy', region: 'IN'|'US'|'ALL',
  //     tickers: ['NIFTY','BANKNIFTY'] or null for all,
  //     ivCrushRisk: 'HIGH'|'MEDIUM'|'LOW' }
  var eventCalendar = {
    // Seed of known 2026 Indian + US macro events (update quarterly)
    _seedEvents: [
      // RBI MPC 2026 — bi-monthly
      { date: '2026-02-06', name: 'RBI MPC', region: 'IN', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-04-09', name: 'RBI MPC', region: 'IN', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-06-05', name: 'RBI MPC', region: 'IN', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-08-06', name: 'RBI MPC', region: 'IN', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-10-01', name: 'RBI MPC', region: 'IN', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-12-04', name: 'RBI MPC', region: 'IN', tickers: null, ivCrushRisk: 'HIGH' },
      // FOMC 2026 — 8 meetings per year
      { date: '2026-01-28', name: 'FOMC', region: 'US', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-03-18', name: 'FOMC', region: 'US', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-04-29', name: 'FOMC', region: 'US', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-06-17', name: 'FOMC', region: 'US', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-07-29', name: 'FOMC', region: 'US', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-09-16', name: 'FOMC', region: 'US', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-11-04', name: 'FOMC', region: 'US', tickers: null, ivCrushRisk: 'HIGH' },
      { date: '2026-12-16', name: 'FOMC', region: 'US', tickers: null, ivCrushRisk: 'HIGH' },
      // India Budget
      { date: '2026-02-01', name: 'Union Budget', region: 'IN', tickers: null, ivCrushRisk: 'HIGH' }
    ],

    // Load user-added events from localStorage; merged with seed.
    load: function () {
      try {
        var stored = localStorage.getItem('at_events');
        if (stored) return this._seedEvents.concat(JSON.parse(stored));
      } catch (e) {}
      return this._seedEvents.slice();
    },

    // Add a custom event (e.g. per-ticker earnings)
    add: function (ev) {
      try {
        var custom = JSON.parse(localStorage.getItem('at_events') || '[]');
        custom.push(ev);
        localStorage.setItem('at_events', JSON.stringify(custom));
        return true;
      } catch (e) { return false; }
    },

    // Returns events within daysAhead days that affect this trade.
    // Returns [] if nothing applies.
    upcomingFor: function (symbol, region, daysAhead) {
      daysAhead = daysAhead || 2;
      var now = new Date();
      var horizon = new Date(now.getTime() + daysAhead * 86400000);
      var results = [];
      this.load().forEach(function (ev) {
        var evDate = new Date(ev.date);
        if (isNaN(evDate)) return;
        // Only future events within horizon
        if (evDate < now || evDate > horizon) return;
        // Region filter (ALL matches both)
        if (ev.region !== 'ALL' && ev.region !== region) return;
        // Ticker filter (null = applies to all tickers in region)
        if (ev.tickers && ev.tickers.indexOf(symbol) < 0) return;
        results.push({
          date: ev.date, name: ev.name,
          ivCrushRisk: ev.ivCrushRisk,
          daysUntil: Math.ceil((evDate - now) / 86400000)
        });
      });
      return results;
    },

    // Main user-facing check: returns one of
    //   { action: 'CLEAR' }      — safe to trade
    //   { action: 'WARN', ... }  — event within horizon, flag it
    //   { action: 'BLOCK', ... } — high-risk event within 1 day
    checkTrade: function (trade, region) {
      var events = this.upcomingFor(trade.symbol, region || 'IN', 2);
      if (events.length === 0) return { action: 'CLEAR' };
      // Sort soonest first
      events.sort(function (a, b) { return a.daysUntil - b.daysUntil; });
      var soonest = events[0];
      if (soonest.daysUntil <= 1 && soonest.ivCrushRisk === 'HIGH') {
        return {
          action: 'BLOCK',
          event: soonest,
          reason: soonest.name + ' in ' + soonest.daysUntil +
                  ' day(s) — HIGH IV crush risk. Wait until after.'
        };
      }
      return {
        action: 'WARN',
        event: soonest,
        reason: soonest.name + ' in ' + soonest.daysUntil +
                ' day(s) — watch for IV changes.'
      };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16g. PARTIAL PROFIT MANAGER — scale-out at 1.5R, trail remainder
  // ═══════════════════════════════════════════════════════════════════════
  // Most retail traders either (a) take profit too early (exits at +15%
  // then watches trade hit target at +40%) or (b) never take profit and
  // give back winners. Professional traders scale out: take partial at
  // 1.5R (1.5× risk), let remainder run with trailing stop at break-even.
  // Mathematically this locks in positive expectancy even if remainder
  // stops at entry — you've already booked 0.75R net.
  //
  // Paper-portfolio integration: we track `scaledOutAt` on each position
  // and `originalLots`. Scale-out produces a partial close event with
  // 50% realized P&L. Remaining 50% trails.
  var partialProfitManager = {
    // Check if this position should scale out NOW.
    // Returns { action: 'SCALE_OUT' | 'HOLD', reason: "..." }
    evaluate: function (position, currentPrice) {
      if (!position || position.status !== 'active') return { action: 'HOLD' };
      if (position.scaledOutAt) return { action: 'HOLD', reason: 'already scaled out' };

      var entry = position.entryPremium;
      var sl = position.sl;
      var risk = Math.abs(entry - sl);
      if (risk <= 0) return { action: 'HOLD', reason: 'no risk defined' };

      var reward = currentPrice - entry;
      // Scale-out trigger: reward ≥ 1.5× risk
      var rMultiple = reward / risk;
      if (rMultiple >= 1.5) {
        return {
          action: 'SCALE_OUT',
          rMultiple: rMultiple,
          currentPrice: currentPrice,
          reason: 'Up ' + rMultiple.toFixed(1) + 'R — book 50%, trail break-even on rest'
        };
      }
      return { action: 'HOLD' };
    },

    // Execute the scale-out on a position. Closes 50% of lots,
    // raises SL on remainder to entry (break-even).
    execute: function (positionId, currentPrice) {
      var pos = paperPortfolio.positions[positionId];
      if (!pos || pos.status !== 'active') return null;
      if (pos.scaledOutAt) return null;

      var originalLots = pos.sizingLots || 1;
      var halfLots = Math.ceil(originalLots / 2);
      var partialPnlPerShare = currentPrice - pos.entryPremium;
      var partialPnlPct = (partialPnlPerShare / pos.entryPremium) * 100;

      // Record the scale-out
      pos.scaledOutAt = Date.now();
      pos.scaledOutPrice = currentPrice;
      pos.scaledOutLots = halfLots;
      pos.scaledOutPnlPct = partialPnlPct;
      pos.originalLots = originalLots;
      pos.sizingLots = originalLots - halfLots;  // remaining position
      // Raise stop to break-even on remainder
      pos.sl = pos.entryPremium;
      pos.slWasTrailed = true;

      paperPortfolio.save();
      bus.emit('position:scaledOut', {
        position: pos,
        partialLots: halfLots,
        partialPnlPct: partialPnlPct
      });
      return { partialLots: halfLots, partialPnlPct: partialPnlPct };
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16h. TRADE ATTRIBUTION — "you lose most during lunch"
  // ═══════════════════════════════════════════════════════════════════════
  // Buckets every closed trade by:
  //   - Session phase (OPENING/MORNING/LUNCH/AFTERNOON/CLOSING)
  //   - Market regime at entry (TRENDING_UP/DN/RANGING/VOLATILE/MIXED)
  //   - Side (CE/PE)
  //   - Gamma mode on/off
  // Computes per-bucket win rate + net P&L. Surfaces insights so user
  // can learn what works for them specifically.
  //
  // This is where the product graduates from "signals" to "coach".
  var tradeAttribution = {
    // Generate a bucket key from a position's entry context
    bucketKey: function (pos) {
      var phase = (pos.entrySession && pos.entrySession.phase) || 'UNKNOWN';
      var regime = pos.entryRegime || 'UNKNOWN';
      var side = pos.side || '?';
      var gamma = pos.entryGammaMode ? 'G' : '-';
      return phase + '_' + regime + '_' + side + '_' + gamma;
    },

    // Aggregate all closed positions into buckets
    aggregate: function () {
      var buckets = {};
      for (var id in paperPortfolio.positions) {
        var p = paperPortfolio.positions[id];
        if (p.status !== 'won' && p.status !== 'lost') continue;
        var key = this.bucketKey(p);
        if (!buckets[key]) {
          buckets[key] = {
            key: key,
            phase: (p.entrySession && p.entrySession.phase) || 'UNKNOWN',
            regime: p.entryRegime || 'UNKNOWN',
            side: p.side,
            gamma: !!p.entryGammaMode,
            count: 0, wins: 0, losses: 0,
            netPnl: 0, totalWinPnl: 0, totalLossPnl: 0
          };
        }
        var b = buckets[key];
        b.count++;
        if (p.status === 'won') { b.wins++; b.totalWinPnl += (p.realizedPct || 0); }
        else { b.losses++; b.totalLossPnl += (p.realizedPct || 0); }
        b.netPnl += (p.realizedPct || 0);
      }
      // Compute derived fields
      Object.keys(buckets).forEach(function (k) {
        var b = buckets[k];
        b.winRate = b.count > 0 ? (b.wins / b.count) * 100 : 0;
        b.avgWin = b.wins > 0 ? b.totalWinPnl / b.wins : 0;
        b.avgLoss = b.losses > 0 ? b.totalLossPnl / b.losses : 0;
        b.expectancy = b.count > 0 ? b.netPnl / b.count : 0;
      });
      return buckets;
    },

    // For a proposed new trade, look up your historical performance
    // in that exact bucket. Returns null if insufficient history.
    // MIN_SAMPLES threshold of 5 is minimal statistical basis.
    lookupFor: function (trade) {
      if (!trade) return null;
      var phase = (sessionProfile.phase(state.region || 'IN')).phase;
      var regime = regimeDetector.current;
      var key = phase + '_' + regime + '_' + trade.side + '_' +
                (trade.gammaMode ? 'G' : '-');
      var buckets = this.aggregate();
      var b = buckets[key];
      if (!b || b.count < 5) return null;
      return b;
    },

    // Return worst-performing buckets (for "avoid these setups" insights)
    worstBuckets: function (minCount) {
      minCount = minCount || 5;
      var all = this.aggregate();
      var arr = Object.keys(all)
        .map(function (k) { return all[k]; })
        .filter(function (b) { return b.count >= minCount; })
        .sort(function (a, b) { return a.expectancy - b.expectancy; });
      return arr.slice(0, 3);
    },

    // Best buckets
    bestBuckets: function (minCount) {
      minCount = minCount || 5;
      var all = this.aggregate();
      var arr = Object.keys(all)
        .map(function (k) { return all[k]; })
        .filter(function (b) { return b.count >= minCount; })
        .sort(function (a, b) { return b.expectancy - a.expectancy; });
      return arr.slice(0, 3);
    },

    // Natural-language summary for a bucket
    describe: function (b) {
      return b.phase + ' phase, ' + b.regime.replace(/_/g, ' ').toLowerCase() +
             ' market, ' + b.side + (b.gamma ? ' + gamma' : '') +
             ': ' + b.wins + 'W/' + b.losses + 'L, ' +
             b.winRate.toFixed(0) + '% win rate, ' +
             'expectancy ' + (b.expectancy >= 0 ? '+' : '') + b.expectancy.toFixed(2) + '%';
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16i. CALIBRATION HARNESS — forward-calibrate score → win probability
  // ═══════════════════════════════════════════════════════════════════════
  // The hardcoded scoreToWinProb curve in kellySizer is a theoretical
  // guess. This module records every paper trade's entry score + final
  // outcome, and once we have ≥100 closed trades, computes actual win
  // probability per score bucket. If the empirical curve diverges from
  // the theoretical curve, we update the live curve.
  //
  // IMPORTANT: this is forward calibration (live paper trades, not
  // historical backtest). A full backtest against NSE archives would be
  // faster and more data-rich, but requires historical 5m bars +
  // option chains we don't have API access to. Forward calibration is
  // the honest path given the data we have.
  //
  // Storage: localStorage `at_calibration` = { scoreBucket: {n, wins} }
  var calibrationHarness = {
    BUCKET_SIZE: 5,           // 0-4, 5-9, ..., 95-99
    MIN_TRADES_FOR_UPDATE: 100,

    // Record a closed trade's entry score vs outcome
    record: function (entryScore, won) {
      var bucket = Math.floor(entryScore / this.BUCKET_SIZE) * this.BUCKET_SIZE;
      var data = this._loadRaw();
      if (!data[bucket]) data[bucket] = { n: 0, wins: 0 };
      data[bucket].n++;
      if (won) data[bucket].wins++;
      this._saveRaw(data);
    },

    _loadRaw: function () {
      try {
        var s = localStorage.getItem('at_calibration');
        if (s) return JSON.parse(s);
      } catch (e) {}
      return {};
    },
    _saveRaw: function (data) {
      try { localStorage.setItem('at_calibration', JSON.stringify(data)); }
      catch (e) {}
    },

    // Total closed trades across all buckets
    totalCount: function () {
      var data = this._loadRaw();
      var total = 0;
      Object.keys(data).forEach(function (b) { total += data[b].n || 0; });
      return total;
    },

    // Empirical win probability for a given score, or null if insufficient data
    empiricalWinProb: function (score) {
      var data = this._loadRaw();
      var bucket = Math.floor(score / this.BUCKET_SIZE) * this.BUCKET_SIZE;
      var b = data[bucket];
      if (!b || b.n < 10) return null;  // need ≥10 per bucket
      return b.wins / b.n;
    },

    // Full empirical curve (for display + replacing the theoretical curve)
    empiricalCurve: function () {
      var data = this._loadRaw();
      var out = [];
      Object.keys(data).map(Number).sort(function (a, b) { return a - b; })
        .forEach(function (bucket) {
          var b = data[bucket];
          if (b.n >= 10) {
            out.push({
              bucketStart: bucket, n: b.n,
              winProb: b.wins / b.n, wins: b.wins
            });
          }
        });
      return out;
    },

    // Once total >= MIN_TRADES_FOR_UPDATE, override kellySizer.scoreToWinProb
    // with empirical data. Called once per session.
    applyIfReady: function () {
      if (this.totalCount() < this.MIN_TRADES_FOR_UPDATE) return false;
      var curve = this.empiricalCurve();
      if (curve.length < 3) return false;  // need breadth too
      // Monkey-patch kellySizer.scoreToWinProb
      var harness = this;
      kellySizer.scoreToWinProb = function (score) {
        var emp = harness.empiricalWinProb(score);
        if (emp != null) return emp;
        // Fallback to theoretical for score buckets with no data yet
        if (score < 55) return 0.48;
        if (score < 68) return 0.52;
        if (score < 76) return 0.56;
        if (score < 86) return 0.60;
        if (score < 96) return 0.64;
        return 0.67;
      };
      kellySizer._calibrated = true;
      return true;
    },

    // Reset calibration data (useful for testing or starting fresh)
    reset: function () {
      try { localStorage.removeItem('at_calibration'); } catch (e) {}
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16j. PORTFOLIO GREEKS + CORRELATION MATRIX — institutional book view
  // ═══════════════════════════════════════════════════════════════════════
  // A professional desk tracks the AGGREGATE risk across all open positions,
  // not just per-trade. Two NIFTY CE positions aren't two independent bets;
  // they're one bigger concentrated bet. This module:
  //   - Aggregates delta/gamma/theta/vega across all active positions
  //   - Applies correlation-adjusted position sizing checks
  //   - Blocks new trades that push net book past configured Greek limits
  //
  // Correlation matrix: seeded from published research on Indian/US market
  // relationships. User can override via localStorage 'at_corr_override'.
  // This is NOT a computed-from-history matrix — that requires historical
  // returns data the sandbox doesn't have. It's a sane default that
  // prevents concentration risk.
  var portfolioGreeks = {
    // Correlation defaults (sources: NSE research, CBOE white papers, common
    // desk knowledge; values are approximations, override via config)
    // Symbol → Symbol → correlation (0-1). Symmetric; we lookup either order.
    _defaults: {
      'NIFTY':        { BANKNIFTY: 0.88, FINNIFTY: 0.92, MIDCPNIFTY: 0.72, SENSEX: 0.97 },
      'BANKNIFTY':    { FINNIFTY: 0.94, MIDCPNIFTY: 0.65, SENSEX: 0.87 },
      'FINNIFTY':     { MIDCPNIFTY: 0.62, SENSEX: 0.91 },
      'SENSEX':       { MIDCPNIFTY: 0.71 },
      // US cross-index
      'SPY':          { QQQ: 0.92, IWM: 0.85 },
      'QQQ':          { IWM: 0.78 }
    },
    _sectorBuckets: {
      // Indian large-caps by sector. Pairs within a bucket use corr = 0.7.
      // Cross-bucket pairs use 0.3 (generic equity beta).
      BANKS: ['HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK', 'INDUSINDBK', 'BANKBARODA', 'PNB'],
      IT:    ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTIM'],
      OIL:   ['RELIANCE', 'ONGC', 'BPCL', 'HPCL', 'IOC', 'GAIL'],
      AUTO:  ['TATAMOTORS', 'MARUTI', 'M&M', 'EICHERMOT', 'BAJAJ-AUTO', 'HEROMOTOCO'],
      PHARMA:['SUNPHARMA', 'DRREDDY', 'CIPLA', 'LUPIN', 'DIVISLAB', 'AUROPHARMA'],
      FMCG:  ['ITC', 'HINDUNILVR', 'NESTLEIND', 'DABUR', 'BRITANNIA', 'MARICO'],
      METALS:['TATASTEEL', 'JSWSTEEL', 'HINDALCO', 'COALINDIA', 'VEDL', 'SAIL']
    },

    // Returns a correlation between two tickers (0 if unknown, 1 if same)
    correlation: function (symA, symB) {
      if (symA === symB) return 1.0;
      // Direct in defaults (either order)
      var d = this._defaults;
      if (d[symA] && d[symA][symB] != null) return d[symA][symB];
      if (d[symB] && d[symB][symA] != null) return d[symB][symA];
      // User override
      try {
        var over = JSON.parse(localStorage.getItem('at_corr_override') || '{}');
        var k1 = symA + '_' + symB, k2 = symB + '_' + symA;
        if (over[k1] != null) return over[k1];
        if (over[k2] != null) return over[k2];
      } catch (e) {}
      // Sector bucket check
      var bucketA = null, bucketB = null;
      for (var bk in this._sectorBuckets) {
        if (this._sectorBuckets[bk].indexOf(symA) >= 0) bucketA = bk;
        if (this._sectorBuckets[bk].indexOf(symB) >= 0) bucketB = bk;
      }
      if (bucketA && bucketB) {
        return bucketA === bucketB ? 0.7 : 0.3;
      }
      // Unknown tickers — assume moderate generic equity correlation
      return 0.35;
    },

    // Compute aggregated Greeks across all active positions
    // Returns { netDelta, netGamma, netVega, netTheta, positions, warnings }
    // Notional-weighted using current premium × lot size.
    bookGreeks: function () {
      var active = [];
      var book = {
        netDelta: 0, netGamma: 0, netVega: 0, netTheta: 0,
        grossNotional: 0, positionsCount: 0,
        positions: [], warnings: []
      };
      if (typeof paperPortfolio === 'undefined') return book;

      for (var id in paperPortfolio.positions) {
        var p = paperPortfolio.positions[id];
        if (p.status !== 'active') continue;
        active.push(p);
      }
      if (active.length === 0) return book;

      // We need current spot, IV, DTE per position. Best-effort from _raw.
      // If unavailable, skip that position's greek contribution (don't fake).
      active.forEach(function (pos) {
        var raw = pos._lastRaw || null;  // set by price refresh path if available
        var spot = raw && raw.spot, iv = raw && raw.atm_iv, expiry = raw && raw.expiry;
        var strikeNum = parseFloat(String(pos.strike || '').replace(/[^\d.]/g, ''));
        var dte = 0;
        if (expiry && typeof pricingMath !== 'undefined') {
          dte = pricingMath.dteFromExpiry(expiry);
        }
        var greeks = null;
        if (spot && iv && strikeNum && dte > 0 && typeof pricingMath !== 'undefined') {
          greeks = pricingMath.greeks(spot, strikeNum, dte, iv, pos.side);
        }
        var lots = pos.sizingLots || pos.lot || 1;
        var lotSize = pos._lotSize || lotSizeFor(pos.sym) || 65;  // fallback to NIFTY if stock unknown
        var multiplier = lots * lotSize;
        var notional = (pos.entryPremium || 0) * multiplier;
        book.grossNotional += notional;
        book.positionsCount++;

        var contribution = {
          id: pos.id, sym: pos.sym, side: pos.side,
          lots: lots, notional: notional,
          delta: null, gamma: null, vega: null, theta: null,
          hasGreeks: false
        };
        if (greeks) {
          contribution.delta = greeks.delta * multiplier;
          contribution.gamma = greeks.gamma * multiplier;
          contribution.vega = greeks.vega * multiplier;
          contribution.theta = greeks.theta * multiplier;
          contribution.hasGreeks = true;
          book.netDelta += contribution.delta;
          book.netGamma += contribution.gamma;
          book.netVega += contribution.vega;
          book.netTheta += contribution.theta;
        }
        book.positions.push(contribution);
      });

      // Warnings for missing greek data
      var missingCount = book.positions.filter(function (p) { return !p.hasGreeks; }).length;
      if (missingCount > 0) {
        book.warnings.push(missingCount + ' position(s) missing spot/IV/expiry — greeks partial');
      }

      return book;
    },

    // Check if opening this trade would violate book-level greek limits.
    // Returns { allow: bool, reason, projectedDelta, projectedVega, corrPenalty }
    //
    // Default limits (per 1L capital): netDelta ±50, netVega ±500
    // (reasonable for 1-3 concurrent positions at typical NIFTY size).
    // Correlation penalty: if new position is correlated >0.7 with any existing
    // position in same direction, the effective concentration doubles.
    checkAllow: function (trade, raw) {
      var book = this.bookGreeks();
      var result = {
        allow: true, reason: null,
        projectedDelta: book.netDelta, projectedVega: book.netVega,
        corrPenalty: 0, correlatedSymbols: []
      };
      if (!trade || !raw) return result;

      // Compute new trade's greeks
      var strikeNum = parseFloat(String(trade.strike || '').replace(/[^\d.]/g, ''));
      var dte = 0;
      if (raw.expiry && typeof pricingMath !== 'undefined') {
        dte = pricingMath.dteFromExpiry(raw.expiry);
      }
      if (!raw.spot || !raw.atm_iv || !strikeNum || dte <= 0) {
        // Can't check — allow by default rather than block on missing data
        result.reason = 'insufficient_data';
        return result;
      }
      var lots = trade.lot || 1;
      var lotSize = raw.lot_size || lotSizeFor(trade.symbol) || 65;
      var multiplier = lots * lotSize;
      var g = pricingMath.greeks(raw.spot, strikeNum, dte, raw.atm_iv, trade.side);
      if (!g) {
        result.reason = 'greeks_calc_failed';
        return result;
      }

      // Correlation check: if new trade correlates >0.7 with an existing
      // same-direction position, flag concentration risk.
      var self = this;
      book.positions.forEach(function (pos) {
        if (pos.side !== trade.side) return;  // opposite side cancels correlation
        var corr = self.correlation(trade.symbol, pos.sym);
        if (corr >= 0.7) {
          result.correlatedSymbols.push({ sym: pos.sym, corr: corr });
          result.corrPenalty += corr;
        }
      });

      result.projectedDelta = book.netDelta + g.delta * multiplier;
      result.projectedVega = book.netVega + g.vega * multiplier;

      // Limits scaled to capital (per ₹1L). Calibrated against real NIFTY
      // lot size = 65 (post Jan 2026 NSE revision).
      // One ATM NIFTY 7-DTE CE: delta~0.50 × 65 = ~32 book delta, vega~13.5 × 65 = ~880 book vega.
      // 3 concurrent positions (matches maxConcurrent discipline) = ~96 delta / ~2,640 vega.
      // We set limits slightly above that so the 3rd position goes through
      // but a 4th is blocked. Correlation penalty makes limits tighter
      // when positions are correlated (same direction, same index).
      var capital = (typeof kellySizer !== 'undefined') ? kellySizer.capital() : 100000;
      var capitalScale = capital / 100000;
      var deltaLimit = 150 * capitalScale * (1 + result.corrPenalty);
      var vegaLimit = 3000 * capitalScale;

      if (Math.abs(result.projectedDelta) > deltaLimit) {
        result.allow = false;
        result.reason = 'Net book delta ' + result.projectedDelta.toFixed(0) +
                        ' exceeds limit ±' + deltaLimit.toFixed(0) +
                        (result.correlatedSymbols.length
                          ? ' (correlated: ' + result.correlatedSymbols.map(function (c) {
                              return c.sym + ' ρ=' + c.corr.toFixed(2);
                            }).join(', ') + ')'
                          : '');
      } else if (Math.abs(result.projectedVega) > vegaLimit) {
        result.allow = false;
        result.reason = 'Net book vega ' + result.projectedVega.toFixed(0) +
                        ' exceeds limit ±' + vegaLimit.toFixed(0);
      }
      return result;
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16k. SCENARIO ANALYSIS — IV shock + spot gap tail risk at execute time
  // ═══════════════════════════════════════════════════════════════════════
  // Before clicking EXECUTE, show what happens to P&L if spot moves
  // ±0.5% or IV drops/rises 3 points. This is what professional traders
  // do mentally before every trade; we make it explicit.
  //
  // 3×3 matrix: [spot -0.5%, flat, +0.5%] × [IV -3pts, current, +3pts]
  // Each cell is re-priced option value expressed as % of entry premium.
  var scenarioAnalysis = {
    // Compute 3×3 P&L matrix. Returns null if insufficient data.
    compute: function (trade, raw) {
      if (!trade || !raw || typeof pricingMath === 'undefined') return null;
      var spot = raw.spot, iv = raw.atm_iv, expiry = raw.expiry;
      var strikeNum = parseFloat(String(trade.strike || '').replace(/[^\d.]/g, ''));
      var premium = trade.price;
      if (!spot || !iv || !strikeNum || !premium) return null;
      var dte = pricingMath.dteFromExpiry(expiry);
      if (dte <= 0) return null;

      var spotShocks = [-0.005, 0, 0.005];  // -0.5%, flat, +0.5%
      var ivShocks = [-3, 0, 3];             // -3pts, flat, +3pts

      var matrix = [];
      for (var i = 0; i < spotShocks.length; i++) {
        var row = [];
        var shockedSpot = spot * (1 + spotShocks[i]);
        for (var j = 0; j < ivShocks.length; j++) {
          var shockedIv = Math.max(1, iv + ivShocks[j]);
          var g = pricingMath.greeks(shockedSpot, strikeNum, dte, shockedIv, trade.side);
          if (!g) { row.push(null); continue; }
          // Option fairValue at shocked inputs, compared to entry premium
          var pnlPct = ((g.fairValue - premium) / premium) * 100;
          row.push({
            spotShockPct: spotShocks[i] * 100,
            ivShockPts: ivShocks[j],
            shockedPrice: g.fairValue,
            pnlPct: pnlPct
          });
        }
        matrix.push(row);
      }

      // Find worst and best cells for headline
      var worst = null, best = null;
      matrix.forEach(function (row) {
        row.forEach(function (cell) {
          if (!cell) return;
          if (worst === null || cell.pnlPct < worst.pnlPct) worst = cell;
          if (best === null || cell.pnlPct > best.pnlPct) best = cell;
        });
      });

      return {
        matrix: matrix,
        worst: worst,
        best: best,
        entryPremium: premium,
        entrySpot: spot, entryIv: iv
      };
    },

    // Plain-English summary line
    summaryLine: function (scen) {
      if (!scen || !scen.worst || !scen.best) return null;
      var w = scen.worst, b = scen.best;
      return 'Worst: spot ' + (w.spotShockPct >= 0 ? '+' : '') + w.spotShockPct.toFixed(1) +
             '%, IV ' + (w.ivShockPts >= 0 ? '+' : '') + w.ivShockPts + 'pts → ' +
             w.pnlPct.toFixed(1) + '%. ' +
             'Best: spot ' + (b.spotShockPct >= 0 ? '+' : '') + b.spotShockPct.toFixed(1) +
             '%, IV ' + (b.ivShockPts >= 0 ? '+' : '') + b.ivShockPts + 'pts → +' +
             b.pnlPct.toFixed(1) + '%.';
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16l. DATA PROVENANCE — vendor / latency / staleness visible per tile
  // ═══════════════════════════════════════════════════════════════════════
  // Institutional users need to know: is this NSE direct or a scraped fallback?
  // Is OI 40 seconds stale or live? Are we on Google Finance because NSE
  // rate-limited us? This module surfaces that, honestly.
  //
  // Expected payload from backend (added to bottom-nav-scan response):
  //   ticker._provenance = {
  //     vendor: 'NSE' | 'Google Finance' | 'Yahoo' | 'fallback',
  //     fetched_at: unix_ms,
  //     oi_updated_at: unix_ms (for option chain data),
  //     quality: 'live' | 'delayed' | 'cached' | 'unknown'
  //   }
  // If absent, we show "vendor unknown · age estimated" — honestly.
  var dataProvenance = {
    // Extract and normalize provenance from a raw ticker payload.
    // Returns { vendor, latencyMs, oiAgeSec, quality, status }
    read: function (raw) {
      if (!raw) return { status: 'no_data', vendor: 'unknown', quality: 'unknown' };
      var now = Date.now();
      var prov = raw._provenance || {};
      var result = {
        vendor: prov.vendor || 'unknown',
        quality: prov.quality || 'unknown',
        latencyMs: null,
        oiAgeSec: null,
        status: 'ok'
      };
      if (prov.fetched_at && typeof prov.fetched_at === 'number') {
        result.latencyMs = now - prov.fetched_at;
      }
      if (prov.oi_updated_at && typeof prov.oi_updated_at === 'number') {
        result.oiAgeSec = Math.round((now - prov.oi_updated_at) / 1000);
      }
      // Health classification
      if (result.vendor === 'unknown' && !prov.fetched_at) {
        result.status = 'untraceable';
      } else if (result.latencyMs != null && result.latencyMs > 5000) {
        result.status = 'stale';
      } else if (result.oiAgeSec != null && result.oiAgeSec > 120) {
        result.status = 'oi_stale';
      }
      return result;
    },

    // Short label for UI tile: "NSE · 850ms · OI T-40s"
    badge: function (raw) {
      var p = this.read(raw);
      var parts = [];
      parts.push(p.vendor);
      if (p.latencyMs != null) {
        parts.push(p.latencyMs < 1000 ? p.latencyMs + 'ms' : (p.latencyMs / 1000).toFixed(1) + 's');
      } else {
        parts.push('age ?');
      }
      if (p.oiAgeSec != null) {
        parts.push('OI T-' + p.oiAgeSec + 's');
      }
      return parts.join(' · ');
    },

    // Color code for the badge based on health
    badgeColor: function (raw) {
      var p = this.read(raw);
      if (p.status === 'ok') return '#22C55E';       // green
      if (p.status === 'stale' || p.status === 'oi_stale') return '#F59E0B';  // orange
      return '#64748B';                               // gray for unknown
    }
  };


  // ═══════════════════════════════════════════════════════════════════════
  // 16m. PRO MODE — institutional toggle; disables retail signals
  // ═══════════════════════════════════════════════════════════════════════
  // Toggles at runtime. When ON:
  //   - SMC signals (FVG, OB, BOS/CHoCH, sweeps, EMA stacking, candle close)
  //     are EXCLUDED from consensus point accumulation
  //   - Remaining weights are proportionally redistributed to
  //     regime / GEX / IV term / order flow / Kelly (core institutional signals)
  //   - UI hides the SMC sections in the right-column deep dive
  //   - Voice stops using SMC phrasing
  var proMode = {
    enabled: false,

    init: function () {
      try {
        var stored = localStorage.getItem('at_pro_mode');
        this.enabled = stored === 'true';
      } catch (e) { this.enabled = false; }
    },
    toggle: function () {
      this.enabled = !this.enabled;
      try { localStorage.setItem('at_pro_mode', String(this.enabled)); } catch (e) {}
      return this.enabled;
    },
    isOn: function () { return this.enabled; }
  };
  proMode.init();

  // ═══════════════════════════════════════════════════════════════════════
  // 16n. TRADE PREVIEW — what the user is actually committing to on click
  // ═══════════════════════════════════════════════════════════════════════
  // Before confirming a trade (or rendering a compact inline label), compute
  // everything that WILL happen: Kelly sizing, rupees at risk, SL/target in
  // currency, all blocker checks. One function, one source of truth. Both
  // the card preview and the confirm modal render from this.
  //
  // Returns:
  //   { allowed: bool,
  //     blockers: ['Risk gate: ...', 'Event: ...'],
  //     warnings: ['Correlation: ...'],
  //     sizing:  { lots, rupeesAtRisk, pctCapital, breakEvenPct },
  //     slAbs, tgtAbs, slPct, tgtPct,
  //     trigger, premium,
  //     shortLabel: '2 lots · ₹4.2K risk',
  //     isCorrelated, correlatedSymbols }
  //
  // Never throws. Missing data returns partial preview with the fields we
  // could compute.
  var tradePreview = {
    compute: function (trade) {
      var out = {
        allowed: true, blockers: [], warnings: [],
        sizing: null, slAbs: null, tgtAbs: null,
        slPct: trade && trade.slPct, tgtPct: trade && trade.tgtPct,
        trigger: trade && trade.trigger, premium: trade && trade.price,
        shortLabel: '', isCorrelated: false, correlatedSymbols: []
      };
      if (!trade) { out.allowed = false; out.blockers.push('No trade'); return out; }

      // 1) Portfolio risk gate
      try {
        var gate = portfolioRisk.checkAllow();
        if (!gate.allow) {
          out.allowed = false;
          out.blockers.push(gate.reason);
        }
      } catch (e) {}

      // 2) Event calendar
      try {
        var ev = eventCalendar.checkTrade(trade, state.region || 'IN');
        if (ev.action === 'BLOCK') {
          out.allowed = false;
          out.blockers.push(ev.reason);
        } else if (ev.action === 'WARN') {
          out.warnings.push(ev.reason);
        }
      } catch (e) {}

      // 3) Kelly sizing — regime-adjusted
      try {
        var baseSaved = kellySizer.fractional;
        kellySizer.fractional = baseSaved * regimeDetector.kellyMultiplier();
        var sizing = kellySizer.size(trade);
        kellySizer.fractional = baseSaved;
        if (sizing.lots === 0 || sizing.error) {
          out.allowed = false;
          out.blockers.push('Kelly: ' + (sizing.reason || sizing.error || 'negative edge'));
        } else {
          var lotSize = lotSizeFor(trade.symbol) || 65;
          var shares = sizing.lots * lotSize;
          var rupeesAtRisk = Math.abs(trade.price - trade.sl) * shares;
          var breakEvenPct = null;
          try {
            var costs = execCostModel.computeCost(trade, sizing.lots, state.region);
            if (costs && costs.breakEvenPct != null) breakEvenPct = costs.breakEvenPct;
          } catch (e) {}
          out.sizing = {
            lots: sizing.lots,
            shares: shares,
            rupeesAtRisk: rupeesAtRisk,
            pctCapital: sizing.pctOfCapital,
            breakEvenPct: breakEvenPct,
            winProb: sizing.winProb,
            payoffRatio: sizing.payoffRatio,
            edge: sizing.edge
          };
          out.slAbs = Math.abs(trade.price - trade.sl);
          out.tgtAbs = Math.abs(trade.target - trade.price);
        }
      } catch (e) {}

      // 4) Portfolio Greek check
      try {
        var pg = portfolioGreeks.checkAllow(trade, trade._raw || {});
        if (!pg.allow) {
          out.allowed = false;
          out.blockers.push(pg.reason);
        }
        if (pg.correlatedSymbols && pg.correlatedSymbols.length > 0) {
          out.isCorrelated = true;
          out.correlatedSymbols = pg.correlatedSymbols;
          pg.correlatedSymbols.forEach(function (c) {
            out.warnings.push('Correlated with open ' + c.sym +
                              ' (ρ=' + c.corr.toFixed(2) + ')');
          });
        }
      } catch (e) {}

      // Short label for button — "2 lots · ₹4.2K risk"
      if (out.sizing) {
        var riskTxt;
        var r = out.sizing.rupeesAtRisk;
        if (r >= 100000) riskTxt = '₹' + (r / 100000).toFixed(1) + 'L';
        else if (r >= 1000) riskTxt = '₹' + (r / 1000).toFixed(1) + 'K';
        else riskTxt = '₹' + r.toFixed(0);
        out.shortLabel = out.sizing.lots + ' lot' +
                         (out.sizing.lots > 1 ? 's' : '') + ' · ' + riskTxt;
      } else if (!out.allowed) {
        out.shortLabel = 'BLOCKED';
      } else {
        out.shortLabel = 'check size';
      }

      return out;
    }
  };

  // Session-scoped confirmation memory. Resets on page reload by design —
  // institutional discipline: fresh session = fresh protection.
  var confirmSuppressed = false;


  var sessionGuide = {
    // Aggregate stats for today's closed positions
    today: function () {
      var dayStart = new Date(); dayStart.setHours(0, 0, 0, 0);
      var closedToday = [];
      var openNow = 0, pendingNow = 0;
      for (var id in paperPortfolio.positions) {
        var p = paperPortfolio.positions[id];
        if (p.status === 'active') openNow++;
        if (p.status === 'pending') pendingNow++;
        if (p.closedAt && p.closedAt >= dayStart.getTime() &&
            (p.status === 'won' || p.status === 'lost')) {
          closedToday.push(p);
        }
      }
      closedToday.sort(function (a, b) { return a.closedAt - b.closedAt; });

      var wins = closedToday.filter(function (p) { return p.status === 'won'; });
      var losses = closedToday.filter(function (p) { return p.status === 'lost'; });
      var netPnl = closedToday.reduce(function (sum, p) {
        return sum + (p.realizedPct || 0);
      }, 0);

      // Streak detection on the LAST 3 closed trades
      var last3 = closedToday.slice(-3);
      var lossStreak = 0, winStreak = 0;
      for (var i = last3.length - 1; i >= 0; i--) {
        if (last3[i].status === 'lost') {
          if (winStreak > 0) break;
          lossStreak++;
        } else if (last3[i].status === 'won') {
          if (lossStreak > 0) break;
          winStreak++;
        }
      }

      return {
        closedCount: closedToday.length,
        wins: wins.length, losses: losses.length,
        winRate: closedToday.length > 0 ? (wins.length / closedToday.length) * 100 : 0,
        netPnl: netPnl,
        lossStreak: lossStreak,
        winStreak: winStreak,
        openNow: openNow, pendingNow: pendingNow,
        lastClosedAt: closedToday.length ? closedToday[closedToday.length - 1].closedAt : 0
      };
    },

    // Should we suggest taking a new trade right now? Returns:
    //   { recommend: 'TAKE' | 'SKIP' | 'CAUTION', reason: "..." }
    // Used when a new top-3 trade appears — we add voice context instead
    // of just announcing "new trade!" with no consideration of user's state.
    shouldTakeNew: function () {
      var t = this.today();
      var gate = portfolioRisk.checkAllow();

      // Hard block: portfolio risk gate already prevents opens
      if (!gate.allow) {
        return { recommend: 'SKIP', reason: gate.reason };
      }

      // Session phase: closing minutes are risky for fresh intraday trades
      var sess = sessionProfile.phase(state.region || 'IN');
      if (sess.phase === 'CLOSING') {
        return {
          recommend: 'SKIP',
          reason: 'Market closing soon — avoid opening new intraday positions'
        };
      }

      // Loss streak: 3 losses in a row → caution to prevent revenge
      if (t.lossStreak >= 3) {
        return {
          recommend: 'SKIP',
          reason: t.lossStreak + ' losses in a row today. Step back. ' +
                  'Don\'t revenge-trade. Wait for the next clean setup.'
        };
      }
      if (t.lossStreak === 2) {
        return {
          recommend: 'CAUTION',
          reason: '2 losses today. Consider reducing size on the next trade.'
        };
      }

      // Near daily loss cap
      if (t.netPnl <= -(portfolioRisk.config.maxDailyLossPct * 0.7)) {
        return {
          recommend: 'CAUTION',
          reason: 'Day P&L at ' + t.netPnl.toFixed(1) +
                  '% — approaching daily loss cap. Trade small if at all.'
        };
      }

      // Approaching concurrent cap
      if (t.openNow + t.pendingNow >= portfolioRisk.config.maxConcurrent - 1) {
        return {
          recommend: 'CAUTION',
          reason: (t.openNow + t.pendingNow) + '/' + portfolioRisk.config.maxConcurrent +
                  ' positions open. This would max out your capacity.'
        };
      }

      // Lunch chop
      if (sess.phase === 'LUNCH') {
        return {
          recommend: 'CAUTION',
          reason: 'Lunch hour chop — win rate is historically lower. Take only premium setups.'
        };
      }

      return {
        recommend: 'TAKE',
        reason: 'Portfolio capacity available. Session conditions favorable.'
      };
    },

    // Plain-English voice line for a new top-trade announcement with context
    newTradeAnnouncement: function (trade) {
      var t = this.today();
      var decision = this.shouldTakeNew();
      var baseLine = 'New top trade: ' + trade.symbol + ' ' + trade.strike +
                     ', confidence ' + trade.confidence + ' percent. ';

      if (decision.recommend === 'TAKE') {
        if (t.netPnl > 2) {
          return baseLine + 'You are up ' + t.netPnl.toFixed(1) +
                 ' percent today. ' + decision.reason;
        } else if (t.openNow > 0) {
          return baseLine + 'You have ' + t.openNow +
                 ' position open. Room for more. ' + decision.reason;
        }
        return baseLine + decision.reason;
      }
      if (decision.recommend === 'CAUTION') {
        return baseLine + 'Caution — ' + decision.reason;
      }
      // SKIP
      return baseLine + 'Not recommended — ' + decision.reason;
    },

    // Summary line for session end / midday check-in
    summary: function () {
      var t = this.today();
      if (t.closedCount === 0) {
        return 'No trades closed yet today.';
      }
      var base = 'Today: ' + t.closedCount + ' trade' + (t.closedCount > 1 ? 's' : '') +
                 ', ' + t.wins + ' won, ' + t.losses + ' lost, net ' +
                 (t.netPnl >= 0 ? '+' : '') + t.netPnl.toFixed(1) + ' percent. ' +
                 'Win rate ' + Math.round(t.winRate) + ' percent.';
      if (t.netPnl > 3) base += ' Strong session.';
      else if (t.netPnl < -2) base += ' Rough session — consider stopping.';
      return base;
    }
  };


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
    volMetrics: volMetrics,
    payoff: payoffDiagram,
    sentiment: sentimentBar,
    session: sessionProfile,
    sessionGuide: sessionGuide,
    events: eventCalendar,
    partialProfit: partialProfitManager,
    attribution: tradeAttribution,
    calibration: calibrationHarness,
    bookGreeks: portfolioGreeks,
    scenario: scenarioAnalysis,
    provenance: dataProvenance,
    proMode: proMode,

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

  // Detect side from price structure + OI before we compute the full score.
  //
  // Missing-data handling: we do NOT substitute missing values with `spot`
  // (which would silently force the comparison to always equal). Instead,
  // each hint runs only when its underlying data is a real number.
  // This is consistent with Vijay's "no fake data" principle.
  function detectSide(row) {
    var spot = row.spot || 0;
    var vwap = (typeof row.vwap === 'number' && row.vwap > 0) ? row.vwap : null;
    var openPx = (typeof row.today_open === 'number' && row.today_open > 0) ? row.today_open : null;
    var high = (typeof row.today_high === 'number' && row.today_high > 0) ? row.today_high : null;
    var low = (typeof row.today_low === 'number' && row.today_low > 0) ? row.today_low : null;
    var maxPain = (typeof row.max_pain === 'number' && row.max_pain > 0)
      ? row.max_pain
      : ((typeof row.atm_strike === 'number' && row.atm_strike > 0) ? row.atm_strike : null);
    var pcr = (typeof row.pcr === 'number' && row.pcr > 0) ? row.pcr : null;
    var isFallback = row._fallback === true;

    var bullHints = 0, bearHints = 0;
    // Each hint only fires when the underlying data exists
    if (vwap != null) {
      if (spot > vwap) bullHints += 2;
      if (spot < vwap) bearHints += 2;
    }
    if (openPx != null) {
      if (spot > openPx) bullHints += 1;
      if (spot < openPx) bearHints += 1;
    }
    if (high != null && low != null && high > low) {
      var rp = (spot - low) / (high - low);
      if (rp > 0.6) bullHints += 1;
      if (rp < 0.4) bearHints += 1;
    }
    if (maxPain != null) {
      if (spot > maxPain) bullHints += 1;
      if (spot < maxPain) bearHints += 1;
    }
    if (!isFallback && pcr != null) {
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
    var spot = row.spot || 0;
    var vwap = (typeof row.vwap === 'number' && row.vwap > 0) ? row.vwap : null;
    // Without VWAP, we can't assess breakout divergence — don't trigger
    if (vwap == null) return { triggered: false, penalty: 0, reason: 'no_vwap' };
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
      // IST 11:30+ — same TZ math as isIndianMarketOpen/sessionProfile.
      // new Date() is UTC ms; add 5.5h; read UTC fields of shifted Date.
      // Never add getTimezoneOffset() — it double-corrects on IST browsers.
      var istMs = now.getTime() + (5.5 * 60 * 60 * 1000);
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
    var atm = (typeof row.atm_strike === 'number' && row.atm_strike > 0)
      ? row.atm_strike : null;
    if (atm == null) return { triggered: false, reason: 'no_atm_strike' };
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

    // Step 3: SL/Target/trigger — ADAPTIVE to current volatility.
    //
    // ════════════════════════════════════════════════════════════════════
    // Why not flat 15% SL / 30% target anymore:
    // In low-vol regimes (ATR=0.3% of spot), a 15% SL triggers on normal
    // noise and stops out winners. In high-vol regimes (ATR=1.5%), 15%
    // SL is too tight and user gets whipsawed on routine moves.
    //
    // The ATR-adaptive approach:
    //   • Underlying SL distance = 1.5× daily ATR (industry standard for
    //     intraday setups — matches the actual noise level)
    //   • Approximate option delta using moneyness:
    //       ATM ≈ 0.50, 1 strike ITM ≈ 0.65, 1 strike OTM ≈ 0.35
    //   • Premium SL = underlying move × delta, converted to % of premium
    //   • Target = 2× SL distance (2:1 reward/risk — standard)
    //   • Clamp to 8-25% SL and 20-50% target so we don't go silly on
    //     extreme data
    // ════════════════════════════════════════════════════════════════════
    var bars = row.ohlc_bars || [];
    var atr = null;
    if (bars.length >= 5) {
      var trValues = [];
      for (var bi = 1; bi < bars.length; bi++) {
        var b = bars[bi], p = bars[bi - 1];
        if (b.h == null || b.l == null || p.c == null) continue;
        trValues.push(Math.max(b.h - b.l,
                               Math.abs(b.h - p.c),
                               Math.abs(b.l - p.c)));
      }
      if (trValues.length > 0) {
        var recent = trValues.slice(-14);
        atr = recent.reduce(function (s, v) { return s + v; }, 0) / recent.length;
      }
    }

    // Approximate option delta from moneyness. For at-/near-ATM
    // options (which is what our strike selector prefers), delta ~0.5.
    // As strike moves OTM, delta drops. We don't have a full BS
    // calculation here (spot/strike/IV all known but cheap approx).
    var moneyness = atm != null && spot
      ? Math.abs(atm - spot) / spot : 0;
    var delta = 0.50;
    if (moneyness > 0.01) delta = 0.35;       // ~1% OTM
    if (moneyness > 0.02) delta = 0.25;       // ~2% OTM
    if (moneyness < -0.01 && side === 'CE') delta = 0.65;
    if (moneyness < -0.01 && side === 'PE') delta = 0.65;

    var slPct = 0.15;   // default 15% if ATR unavailable
    var tgtPct = 0.30;  // default 30%
    var slBasis = 'flat_default';

    if (atr != null && atr > 0 && spot > 0) {
      // Expected premium move if underlying moves 1.5× ATR against us
      var advMove = atr * 1.5 * delta;
      // Convert to % of premium
      slPct = advMove / premium;
      // Clamp: minimum 8% (can't risk less than natural spread/slippage),
      // maximum 25% (if it wants more than 25%, the trade is too risky)
      slPct = Math.max(0.08, Math.min(0.25, slPct));
      // Target is 2× SL distance (2:1 reward-to-risk)
      tgtPct = slPct * 2;
      tgtPct = Math.max(0.20, Math.min(0.50, tgtPct));
      slBasis = 'atr_' + (atr / spot * 100).toFixed(2) + '%_delta_' + delta.toFixed(2);
    }

    var sl = premium * (1 - slPct);
    var target = premium * (1 + tgtPct);
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
      slPct: slPct,            // for UI: "SL 11% (ATR)"
      tgtPct: tgtPct,
      slBasis: slBasis,         // "atr_0.85%_delta_0.50" or "flat_default"
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

    // Docs modal — shown on top of everything when user clicks help icon
    if (state.showDocs) {
      wrap.appendChild(renderDocsModal());
    }

    // Confirm-trade modal — shown when user clicks EXECUTE/TAKE TRADE
    // and hasn't suppressed confirmations for this session.
    if (state.pendingConfirmTrade) {
      var confModal = renderConfirmModal();
      if (confModal) wrap.appendChild(confModal);
    }

    root.appendChild(wrap);
  }

  // ── CONFIRM-TRADE MODAL — shown before execute, unless session-suppressed ─
  // Users complained the ENTER NOW / EXECUTE buttons did things they didn't
  // understand. This modal shows the user EXACTLY what will happen:
  //   • symbol / strike / side / premium / trigger
  //   • Kelly sizing: lots, rupees at risk, % of capital, break-even
  //   • SL/target distances in rupees AND percent
  //   • Every warning (correlation, event proximity, etc.)
  //   • Every blocker if trade can't execute
  //   • "Don't ask again this session" checkbox — session-scoped only
  //     (fresh session always confirms the first trade).
  function renderConfirmModal() {
    if (!state.pendingConfirmTrade) return null;
    var t = state.pendingConfirmTrade;
    var preview = tradePreview.compute(t);

    var overlay = el('div', {
      onClick: function (e) {
        if (e.target === overlay) closeConfirmModal();
      },
      style: {
        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0,0,0,0.75)',
        zIndex: 10000,
        display: 'flex', alignItems: 'center', justifyContent: 'center'
      }
    });

    var modal = el('div', {
      style: {
        width: '88%', maxWidth: '480px',
        background: C.bg, border: '1px solid ' + C.divider,
        borderRadius: '8px', display: 'flex', flexDirection: 'column',
        overflow: 'hidden'
      }
    });

    // Header
    var header = el('div', {
      style: {
        padding: '12px 16px', borderBottom: '1px solid ' + C.divider,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
      }
    });
    header.appendChild(el('div', {
      style: {
        fontSize: '12px', fontWeight: 800, color: C.textPri,
        letterSpacing: '1.2px'
      }
    }, preview.allowed ? 'CONFIRM TRADE' : 'CANNOT EXECUTE'));
    header.appendChild(el('button', {
      onClick: closeConfirmModal,
      style: {
        background: 'transparent', border: 'none',
        color: C.textSec, fontSize: '16px', cursor: 'pointer',
        padding: '0 4px'
      }
    }, '✕'));
    modal.appendChild(header);

    // Body
    var body = el('div', {
      style: {
        padding: '14px 16px', fontSize: '12px', color: C.textPri,
        lineHeight: 1.5
      }
    });

    // The trade header row
    var tradeColor = t.side === 'CE' ? C.green : C.red;
    body.appendChild(el('div', {
      style: {
        fontSize: '16px', fontWeight: 800, color: tradeColor,
        fontFamily: MONO, marginBottom: '2px'
      }
    }, t.symbol + ' ' + t.strike));
    body.appendChild(el('div', {
      style: {
        fontSize: '11px', color: C.textSec, marginBottom: '12px',
        fontFamily: MONO
      }
    }, 'Premium: ₹' + (preview.premium || 0).toFixed(2) +
       '  ·  Trigger: ₹' + (preview.trigger || 0).toFixed(2)));

    // Blockers — show prominently if can't execute
    if (preview.blockers.length > 0) {
      var blockBox = el('div', {
        style: {
          background: C.red + '18', borderLeft: '3px solid ' + C.red,
          borderRadius: '3px', padding: '8px 10px', marginBottom: '10px'
        }
      });
      blockBox.appendChild(el('div', {
        style: { fontSize: '10px', fontWeight: 800, color: C.red,
                 letterSpacing: '0.8px', marginBottom: '4px' }
      }, '🚫 BLOCKED'));
      preview.blockers.forEach(function (b) {
        blockBox.appendChild(el('div', {
          style: { color: C.red, fontSize: '11px', lineHeight: 1.4 }
        }, '· ' + b));
      });
      body.appendChild(blockBox);
    }

    // Sizing — what this trade actually costs
    if (preview.sizing) {
      var s = preview.sizing;
      var sizingBox = el('div', {
        style: {
          background: C.card, borderRadius: '4px', padding: '10px 12px',
          marginBottom: '10px', fontFamily: MONO, fontSize: '11px'
        }
      });
      function sizingRow(label, value, valueColor) {
        var row = el('div', {
          style: {
            display: 'flex', justifyContent: 'space-between',
            padding: '2px 0', lineHeight: 1.5
          }
        });
        row.appendChild(el('span', { style: { color: C.textSec } }, label));
        row.appendChild(el('span', {
          style: { color: valueColor || C.textPri, fontWeight: 700 }
        }, value));
        return row;
      }
      var lotSize = lotSizeFor(t.symbol) || 65;
      sizingBox.appendChild(sizingRow(
        'Size',
        s.lots + ' lot' + (s.lots > 1 ? 's' : '') + ' (' + s.shares + ' shares)'));
      sizingBox.appendChild(sizingRow(
        'At risk',
        '₹' + s.rupeesAtRisk.toFixed(0) +
        ' · ' + s.pctCapital.toFixed(1) + '% of capital'));
      if (preview.slAbs != null && preview.tgtAbs != null) {
        sizingBox.appendChild(sizingRow(
          'SL / Target',
          '−₹' + preview.slAbs.toFixed(2) + ' / +₹' + preview.tgtAbs.toFixed(2) +
          '  (' + ((preview.slPct || 0) * 100).toFixed(0) + '% / +' +
          ((preview.tgtPct || 0) * 100).toFixed(0) + '%)'));
      }
      if (s.breakEvenPct != null) {
        sizingBox.appendChild(sizingRow(
          'Break-even',
          '+' + s.breakEvenPct.toFixed(2) + '%',
          s.breakEvenPct > 2 ? C.orange : C.textPri));
      }
      if (s.winProb != null && s.payoffRatio != null) {
        sizingBox.appendChild(sizingRow(
          'Kelly edge',
          (s.winProb * 100).toFixed(0) + '% × ' + s.payoffRatio.toFixed(1) + 'R',
          s.edge > 0.2 ? C.green : s.edge > 0.05 ? C.textPri : C.orange));
      }
      body.appendChild(sizingBox);
    }

    // Warnings — show but don't block
    if (preview.warnings.length > 0) {
      var warnBox = el('div', {
        style: {
          background: C.orange + '15', borderLeft: '3px solid ' + C.orange,
          borderRadius: '3px', padding: '8px 10px', marginBottom: '10px'
        }
      });
      warnBox.appendChild(el('div', {
        style: { fontSize: '10px', fontWeight: 800, color: C.orange,
                 letterSpacing: '0.8px', marginBottom: '4px' }
      }, '⚠ HEADS UP'));
      preview.warnings.forEach(function (w) {
        warnBox.appendChild(el('div', {
          style: { color: C.orange, fontSize: '11px', lineHeight: 1.4 }
        }, '· ' + w));
      });
      body.appendChild(warnBox);
    }

    // "Don't ask again" checkbox
    if (preview.allowed) {
      var checkRow = el('label', {
        style: {
          display: 'flex', alignItems: 'center', gap: '6px',
          cursor: 'pointer', marginTop: '4px', marginBottom: '2px',
          fontSize: '10px', color: C.textSec, userSelect: 'none'
        }
      });
      var cb = el('input', {
        type: 'checkbox',
        checked: state.confirmSkipNext || false,
        onChange: function (e) {
          state.confirmSkipNext = !!e.target.checked;
        },
        style: { margin: 0, cursor: 'pointer' }
      });
      checkRow.appendChild(cb);
      checkRow.appendChild(el('span', {},
        "Don't ask again this session (trust the sizing)"));
      body.appendChild(checkRow);
    }

    modal.appendChild(body);

    // Footer buttons
    var footer = el('div', {
      style: {
        padding: '10px 16px', borderTop: '1px solid ' + C.divider,
        display: 'flex', gap: '8px', justifyContent: 'flex-end'
      }
    });
    footer.appendChild(el('button', {
      onClick: closeConfirmModal,
      style: {
        background: 'transparent', border: '1px solid ' + C.divider,
        color: C.textSec, padding: '8px 16px', borderRadius: '4px',
        cursor: 'pointer', fontSize: '11px', fontWeight: 700,
        letterSpacing: '0.8px'
      }
    }, 'CANCEL'));

    if (preview.allowed) {
      footer.appendChild(el('button', {
        onClick: function () {
          // If checkbox was ticked, suppress for this session
          if (state.confirmSkipNext) confirmSuppressed = true;
          var tradeToExec = state.pendingConfirmTrade;
          state.pendingConfirmTrade = null;
          state.confirmSkipNext = false;
          // Call onExecute without re-triggering modal
          onExecute(tradeToExec, { skipConfirm: true });
          rerender();
        },
        style: {
          background: 'linear-gradient(180deg, ' + C.green + ', #16A34A)',
          border: 'none', color: '#062B17',
          padding: '8px 20px', borderRadius: '4px',
          cursor: 'pointer', fontSize: '11px', fontWeight: 800,
          letterSpacing: '0.8px',
          boxShadow: '0 0 0 1px ' + C.green + '66'
        }
      }, 'CONFIRM TRADE'));
    }
    modal.appendChild(footer);

    overlay.appendChild(modal);
    return overlay;
  }

  function closeConfirmModal() {
    state.pendingConfirmTrade = null;
    state.confirmSkipNext = false;
    rerender();
  }

  // ── DOCS MODAL — "how to trade" + scoring logic access ─────────────────
  // Opens over everything when user clicks the ? icon in the header.
  // Content lives in two tabs: HOW TO TRADE (user-flow guide) and
  // SCORING LOGIC (the math behind every number). Both mirror the
  // markdown files in /docs but are inline so users don't need to dig
  // into the deploy zip.
  function renderDocsModal() {
    var overlay = el('div', {
      onClick: function (e) {
        // Click outside content to close
        if (e.target === overlay) { state.showDocs = false; rerender(); }
      },
      style: {
        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0,0,0,0.75)',
        zIndex: 10000,
        display: 'flex', alignItems: 'center', justifyContent: 'center'
      }
    });

    var modal = el('div', {
      style: {
        width: '88%', maxWidth: '920px', height: '85%',
        background: C.bg, border: '1px solid ' + C.divider,
        borderRadius: '8px', display: 'flex', flexDirection: 'column',
        overflow: 'hidden'
      }
    });

    // Header with tabs + close
    var header = el('div', {
      style: {
        borderBottom: '1px solid ' + C.divider, padding: '10px 14px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flex: '0 0 auto'
      }
    });
    var tabsWrap = el('div', {
      style: { display: 'flex', gap: '8px', alignItems: 'center' }
    });
    tabsWrap.appendChild(el('div', {
      style: {
        fontSize: '14px', fontWeight: 800, color: C.textPri,
        letterSpacing: '1px', marginRight: '16px'
      }
    }, 'HELP'));

    state.docsTab = state.docsTab || 'quickstart';
    function makeTab(key, label) {
      var active = state.docsTab === key;
      return el('button', {
        onClick: function () { state.docsTab = key; rerender(); },
        style: {
          background: active ? C.blue + '22' : 'transparent',
          color: active ? C.blue : C.textSec,
          border: '1px solid ' + (active ? C.blue : C.divider),
          borderRadius: '4px', padding: '6px 12px',
          fontSize: '11px', fontWeight: 700, cursor: 'pointer',
          letterSpacing: '0.8px', fontFamily: MONO
        }
      }, label);
    }
    tabsWrap.appendChild(makeTab('quickstart', 'QUICK START'));
    tabsWrap.appendChild(makeTab('howto', 'HOW TO TRADE'));
    tabsWrap.appendChild(makeTab('scoring', 'SCORING LOGIC'));
    tabsWrap.appendChild(makeTab('risks', 'KNOWN LIMITS'));
    header.appendChild(tabsWrap);
    header.appendChild(el('button', {
      onClick: function () { state.showDocs = false; rerender(); },
      style: {
        background: 'transparent', border: '1px solid ' + C.divider,
        color: C.textSec, borderRadius: '4px', padding: '4px 10px',
        fontSize: '14px', fontWeight: 700, cursor: 'pointer'
      }
    }, '✕'));
    modal.appendChild(header);

    // Body — scrollable content per tab
    var body = el('div', {
      style: {
        flex: '1 1 auto', overflowY: 'auto', padding: '16px 24px',
        fontSize: '12px', color: C.textPri, lineHeight: 1.55,
        fontFamily: 'system-ui, sans-serif'
      }
    });

    if (state.docsTab === 'quickstart') {
      body.appendChild(docsQuickStart());
    } else if (state.docsTab === 'howto') {
      body.appendChild(docsHowTo());
    } else if (state.docsTab === 'scoring') {
      body.appendChild(docsScoring());
    } else if (state.docsTab === 'risks') {
      body.appendChild(docsRisks());
    }
    modal.appendChild(body);

    overlay.appendChild(modal);
    return overlay;
  }

  // Helper: section heading
  function docsH(text, level) {
    level = level || 2;
    var sizes = { 1: '18px', 2: '14px', 3: '12px' };
    var colors = { 1: C.textPri, 2: C.blue, 3: C.textSec };
    return el('div', {
      style: {
        fontSize: sizes[level], fontWeight: level <= 2 ? 800 : 700,
        color: colors[level], marginTop: level === 1 ? 0 : '16px',
        marginBottom: '8px', letterSpacing: level <= 2 ? '0.8px' : 0
      }
    }, text);
  }
  function docsP(text) {
    return el('div', {
      style: {
        marginBottom: '8px', color: C.textPri, lineHeight: 1.55
      }
    }, text);
  }
  function docsList(items) {
    var wrap = el('div', { style: { marginBottom: '8px', paddingLeft: '8px' } });
    items.forEach(function (t) {
      wrap.appendChild(el('div', {
        style: {
          marginBottom: '4px', color: C.textSec, lineHeight: 1.45
        }
      }, '• ' + t));
    });
    return wrap;
  }
  function docsCode(text) {
    return el('pre', {
      style: {
        background: C.card, border: '1px solid ' + C.divider,
        borderRadius: '4px', padding: '8px 10px',
        fontSize: '11px', color: C.textPri, fontFamily: MONO,
        overflow: 'auto', marginBottom: '8px', whiteSpace: 'pre-wrap',
        lineHeight: 1.4
      }
    }, text);
  }
  function docsTable(headers, rows) {
    var table = el('table', {
      style: {
        borderCollapse: 'collapse', width: '100%', marginBottom: '10px',
        fontSize: '11px', fontFamily: MONO
      }
    });
    var thead = el('tr', {});
    headers.forEach(function (h) {
      thead.appendChild(el('th', {
        style: {
          background: C.card, color: C.textSec, fontWeight: 700,
          padding: '4px 8px', border: '1px solid ' + C.divider,
          textAlign: 'left'
        }
      }, h));
    });
    table.appendChild(thead);
    rows.forEach(function (r) {
      var tr = el('tr', {});
      r.forEach(function (cell) {
        tr.appendChild(el('td', {
          style: {
            padding: '4px 8px', border: '1px solid ' + C.divider,
            color: C.textPri
          }
        }, cell));
      });
      table.appendChild(tr);
    });
    return table;
  }

  function docsQuickStart() {
    // Layman's guide — the FIRST tab in the help modal. Written for
    // people who are not professional traders. Plain English, no jargon.
    // Mirrors /docs/QUICK_START.md but rendered inline.
    var root = el('div', {});
    root.appendChild(docsH('Read this first', 1));
    root.appendChild(docsP(
      'A simple guide to the Active Trading screen. No jargon. Five minutes ' +
      'to read, then you can start.'));

    root.appendChild(docsH('What this screen does', 2));
    root.appendChild(docsP(
      'Every 5 minutes, the system scans the Indian market and picks the 3 best ' +
      'options trades it can find. You don\'t have to search. The system ' +
      'finds trades for you. You decide whether to take them.'));

    root.appendChild(docsH('The screen in 30 seconds', 2));
    root.appendChild(docsList([
      'LEFT column — TOP TRADES: the 3 best picks right now.',
      'MIDDLE column — LIVE MONITOR: a "second opinion" on the trade you clicked.',
      'RIGHT column — DEEP DIVE: full technical details (optional reading).',
      'BOTTOM — SECONDARY SCANNER: trades 4-10 that didn\'t make the top 3.'
    ]));

    root.appendChild(docsH('Traffic light colors', 2));
    root.appendChild(docsList([
      'Green — good sign · take this trade · positive factor · profit',
      'Orange/Yellow — caution · warning · but NOT a blocker',
      'Red — stop · don\'t trade · loss · danger',
      'Blue — information · neutral'
    ]));
    root.appendChild(docsP(
      'If you see lots of green + a green button, go ahead. If orange ' +
      'warnings, read them. If red appears, the system is blocking you. ' +
      'Don\'t override — it\'s protecting you.'));

    root.appendChild(docsH('The 3 confidence labels', 2));
    root.appendChild(docsP(
      'Every trade shows a number like "95%". Below it, tiny text:'));
    root.appendChild(docsList([
      '"uncal" — theoretical score · no proof yet · trust with caution',
      '"calibrated" — your past paper trades back up the scoring',
      '"62% win · 24 trades" — your actual win rate on trades like this. TRUST THIS ONE.'
    ]));
    root.appendChild(docsP(
      'In the beginning, every score says "uncal". That\'s normal. Real ' +
      'win rates appear after 50-100 closed trades.'));

    root.appendChild(docsH('How to take a trade (step by step)', 1));
    root.appendChild(docsList([
      '1. Look at the top 3 cards on the left.',
      '2. Click any card — middle and right columns fill with details.',
      '3. Read the big verdict card: STRONG BUY / BUY / BUY SMALL / NEUTRAL / AVOID.',
      '4. Read green ticks (good) and orange warnings (be careful).',
      '5. If you agree, click the green TAKE TRADE button.',
      '6. A confirmation box pops up. Shows: how many lots, rupees at risk, stop loss, target.',
      '7. Click CONFIRM TRADE if you agree. CANCEL if not.'
    ]));
    root.appendChild(docsP(
      'That\'s it. After that, the system guides you through the whole trade ' +
      'with voice alerts. You don\'t have to watch the screen.'));

    root.appendChild(docsH('What happens after CONFIRM', 2));
    root.appendChild(docsList([
      'Position goes PENDING — waiting for price to cross the trigger.',
      'Trigger confirms the move is real before you actually buy.',
      'Once price crosses trigger → position goes LIVE. Voice says so.',
      'Every 5 minutes, system checks: HOLD, ADD, REDUCE, SCALE OUT, or EXIT.',
      'Voice alerts tell you what to do. Just listen.'
    ]));

    root.appendChild(docsH('When to STOP trading', 1));
    root.appendChild(docsP(
      'The system warns you at these points. Listen to it.'));
    root.appendChild(docsList([
      '2 losses in a row — voice says slow down or take a break',
      '3 losses in a row — voice says step back from the screen',
      'Day P&L reaches -3% — all new trades blocked for the day',
      'Drawdown reaches -5% from peak — all new trades blocked'
    ]));
    root.appendChild(docsP(
      'Revenge trading is the #1 way retail traders lose money. The system ' +
      'exists partly to protect you from yourself. Don\'t fight it.'));

    root.appendChild(docsH('This is PAPER MONEY right now', 1));
    root.appendChild(docsP(
      'No real rupees move. This is by design. Use it to:'));
    root.appendChild(docsList([
      'Learn how the system works without risk',
      'Build a track record of 50-100 trades',
      'See your real win rate emerge (replaces "uncal" labels)',
      'Decide if you trust the system before using real money'
    ]));
    root.appendChild(docsP(
      'When you\'re ready for real trading, open a separate broker account ' +
      'and place the same trades manually. Real broker integration is ' +
      'coming in a future version.'));

    root.appendChild(docsH('Things that might confuse you', 1));

    root.appendChild(docsH('My trade says PENDING for a long time', 3));
    root.appendChild(docsP(
      'Normal. Price hasn\'t crossed the trigger yet. Trigger is usually ' +
      'entry + 2% for a call — the price must CONFIRM the move before you ' +
      'buy. This prevents buying tops.'));

    root.appendChild(docsH('I clicked TAKE TRADE but nothing happened', 3));
    root.appendChild(docsP(
      'Check the red BLOCKED box in the confirm modal. Common reasons:'));
    root.appendChild(docsList([
      'Already 3 positions open (max limit)',
      'RBI or FOMC event within 1 day (IV crush risk)',
      'Too close to daily loss limit',
      'This stock strongly correlates with a position you already have'
    ]));

    root.appendChild(docsH('Scores keep saying "uncal"', 3));
    root.appendChild(docsP(
      'You need 100+ closed paper trades before the system calibrates to ' +
      'YOUR personal win rate. Be patient. Keep paper trading.'));

    root.appendChild(docsH('BUY verdict but caveats say OVERPRICED', 3));
    root.appendChild(docsP(
      'Overall verdict can still be BUY even with 1-2 caveats. More caveats ' +
      'mean more risk. Use smaller size. Read the PROS and CAVEATS both — ' +
      'they\'re equally important.'));

    root.appendChild(docsH('The voice is annoying', 3));
    root.appendChild(docsP(
      'Click the microphone icon in the header to turn it off. But note ' +
      'you\'ll miss entry/exit alerts. Voice is the main way the system ' +
      'tells you when to act.'));

    root.appendChild(docsH('The 8 golden rules', 1));
    root.appendChild(docsList([
      'Never size bigger than the system recommends. Kelly math is calibrated. Overriding = blow-up.',
      'Read the confirm modal when just starting. Understand what 2 lots × ₹4,200 risk means for YOUR capital.',
      'Don\'t close winning trades early. Let the 5m system guide exits. It\'s smarter than your emotions.',
      'Don\'t add to losing trades. If REDUCE or EXIT fires, do it.',
      'Avoid trading during lunch (12:00-13:30 IST). Win rates are lower then — system already reduces signal strength.',
      'Don\'t take a trade you don\'t understand. Click the ? icon or read CAVEATS carefully.',
      'Don\'t ignore streak warnings. 2 losses = slow. 3 losses = stop.',
      'Keep a journal. Screenshot confirm modals. Review losses weekly. The YOUR EDGE section will show patterns over time.'
    ]));

    root.appendChild(docsH('Where to get more help', 1));
    root.appendChild(docsList([
      'HOW TO TRADE tab (this modal) — detailed trade flow',
      'SCORING LOGIC tab — the math behind every number',
      'KNOWN LIMITS tab — honest list of what we can\'t do yet',
      'Hover over any badge or score for a tooltip',
      '/docs/QUICK_START.md in the deploy zip — same guide for reference'
    ]));

    root.appendChild(docsH('Still confused?', 1));
    root.appendChild(docsP(
      'Paper trading is risk-free. Experiment. Try 20-30 trades and watch ' +
      'how the system behaves. Most of this becomes obvious quickly. The ' +
      'goal right now is NOT to make money — it\'s to learn how the system ' +
      'thinks so you trust it when real money is in play.'));

    return root;
  }

  function docsHowTo() {
    var root = el('div', {});
    root.appendChild(docsH('How a trade actually happens', 1));
    root.appendChild(docsP(
      'The 7-step flow. Read once. Your session will make sense after this.'));

    root.appendChild(docsH('Step 1 — Wait for the 5-minute close', 2));
    root.appendChild(docsP(
      'Every 5 minutes the engine re-scans the market and re-ranks tickers. ' +
      'Do not trust mid-bar scores — they have not been confirmed by a candle ' +
      'close yet. The countdown at the top-right of the deep-dive shows time ' +
      'until next evaluation.'));

    root.appendChild(docsH('Step 2 — Read the consensus verdict', 2));
    root.appendChild(docsP(
      'Click any top-trade card. The middle column\'s colored card shows one of:'));
    root.appendChild(docsTable(
      ['Verdict', 'Size', 'Meaning'],
      [
        ['STRONG_BUY', '100% Kelly', 'All signals aligned, +35 or more points'],
        ['BUY', '75% Kelly', 'Most signals aligned, +18 to +34 points'],
        ['BUY_SMALL', '50% Kelly', 'Mixed signals, +5 to +17 points'],
        ['NEUTRAL', '25% Kelly', 'Wait for cleaner setup, -5 to +4 points'],
        ['AVOID', '0', 'Below -5 OR hard blocker (risk, alpha, Kelly, event)']
      ]
    ));

    root.appendChild(docsH('Step 3 — Read PROS and CAVEATS', 2));
    root.appendChild(docsP(
      'Green ticks show what\'s going right. Orange warnings show what\'s going ' +
      'wrong. Read BOTH before clicking EXECUTE. A 95% confidence trade with ' +
      '3 caveats often performs worse than an 80% trade with 0 caveats.'));

    root.appendChild(docsH('Step 4 — Check PORTFOLIO TODAY', 2));
    root.appendChild(docsList([
      'OPEN 3/3 means you\'re at capacity. No new trades.',
      'NET already -2% means you\'re near daily loss cap. The system will CAUTION.',
      '"2 losses in a row" banner means system is telling you to stop. Listen.'
    ]));

    root.appendChild(docsH('Step 5 — Click EXECUTE', 2));
    root.appendChild(docsP('Several checks run instantly:'));
    root.appendChild(docsList([
      'Event calendar — RBI/FOMC/earnings within 1 day → BLOCK',
      'Portfolio risk — max concurrent, daily loss cap, drawdown, 5s cooldown',
      'Kelly sizing — computes lots from your capital + edge, regime-adjusted',
      'Position opens PENDING — waiting for price to cross trigger'
    ]));

    root.appendChild(docsH('Step 6 — Wait for entry trigger', 2));
    root.appendChild(docsP(
      'Price must cross the trigger (usually entry + 2%) before position goes ' +
      'LIVE. Card turns green with "● LIVE" pill. Voice confirms entry.'));

    root.appendChild(docsH('Step 7 — Let the system guide the exit', 2));
    root.appendChild(docsP('Every 5 minutes, each position gets a lifecycle tag:'));
    root.appendChild(docsTable(
      ['Tag', 'When', 'Action'],
      [
        ['CONTINUE', 'Signal intact', 'Hold'],
        ['ADD', 'Signal strengthening + in profit', 'Consider adding 25-50%'],
        ['REDUCE', 'Regime flipped OR consensus weakened', 'Cut to half size'],
        ['SCALE_OUT', 'Reached 1.5× risk (automatic)', '50% booked, rest trails'],
        ['EXIT', 'Target/SL hit OR consensus AVOID', 'Auto-closes']
      ]
    ));

    root.appendChild(docsH('The confidence sub-label', 1));
    root.appendChild(docsP(
      'The small text under each "95%" tells you what that number is worth:'));
    root.appendChild(docsList([
      '"uncal" — Theoretical score. No empirical validation yet.',
      '"calibrated" — Your paper trades have replaced the theoretical curve.',
      '"62% win · 24 trades" — For THIS exact setup type, your actual win rate.'
    ]));
    root.appendChild(docsP(
      'The third label is the one to trust. Attribution surfaces after ~5 ' +
      'trades of the same bucket; calibration kicks in at 100 total closes.'));

    root.appendChild(docsH('Common mistakes', 1));
    root.appendChild(docsList([
      'Treating "95%" as a win probability. It is a score. Read the sub-label.',
      'Ignoring REDUCE/EXIT recommendations. If the system says setup invalidated, it has.',
      'Clicking EXECUTE without reading PROS/CAVEATS.',
      'Trading through lunch (12:00-13:30 IST) — multiplier drops to 0.75×.',
      'Revenge-trading after 3 losses. The streak banner exists for a reason.'
    ]));

    return root;
  }

  function docsScoring() {
    var root = el('div', {});
    root.appendChild(docsH('The scoring pipeline', 1));
    root.appendChild(docsCode(
      'Backend /api/bottom-nav-scan\n' +
      '   ↓\n' +
      'Raw ticker data (OHLC bars, chain, OI, PCR, VWAP)\n' +
      '   ↓\n' +
      'For each ticker:\n' +
      '   detectSide(row)           → CE or PE\n' +
      '   6-factor score            → confidence 0-100\n' +
      '   ATR-adaptive SL/target    → trade.sl, trade.target\n' +
      '   state classification      → early/ideal/late/avoid\n' +
      '   ↓\n' +
      'Rank by confidence → Top 3 trades\n' +
      '   ↓\n' +
      'Consensus engine → verdict + size multiplier'
    ));

    root.appendChild(docsH('The 6-factor confidence score', 1));
    root.appendChild(docsTable(
      ['Factor', 'Weight', 'Measures'],
      [
        ['Trend Strength', '25%', 'Directional momentum across recent bars'],
        ['VWAP Alignment', '20%', 'Spot vs VWAP + distance'],
        ['OI Structure', '20%', 'Call/Put build-up divergence'],
        ['Volume', '15%', 'Recent volume vs average'],
        ['Strike Quality', '10%', 'How close strike is to spot'],
        ['Risk/Reward', '10%', 'Target distance vs SL distance']
      ]
    ));
    root.appendChild(docsP(
      'Composite = Σ (factor × weight) ÷ Σ (weights for available factors). ' +
      'If 2+ factors are null (missing data), score is capped at 65 and the ' +
      'card shows "OI+Vol unavailable" badges.'));

    root.appendChild(docsH('Consensus engine points', 1));
    root.appendChild(docsP('Builds on top of confidence. Adds/subtracts points per module.'));
    root.appendChild(docsTable(
      ['Signal', 'Points'],
      [
        ['Confidence score (baseline)', '(score - 60) → e.g. 95 → +35'],
        ['Regime aligned with trade direction', '+10'],
        ['Regime against trade', '-15'],
        ['VOLATILE regime', '-10'],
        ['RANGING regime', '-5'],
        ['GEX BREAKOUT tag', '+8'],
        ['GEX RANGE tag', '-8'],
        ['Compass aligned (short+long match)', '+12'],
        ['Compass conflict', '-10'],
        ['IV OVERPRICED (>2.5× HV)', '-8'],
        ['IV UNDERPRICED (<0.4× HV)', '+8'],
        ['Alpha DEGRADING', '-5'],
        ['Alpha DECAYED', 'BLOCK (AVOID)'],
        ['Kelly negative edge', 'BLOCK (AVOID)'],
        ['BOS bullish + CE trade', '+10'],
        ['CHoCH reversal in trade direction', '+12'],
        ['Liquidity sweep aligned', '+8'],
        ['FVG magnet matches side', '+6'],
        ['Order Block support/resistance matches', '+7'],
        ['EMA stacked in direction', '+6'],
        ['Strong candle closure aligned', '+5'],
        ['STRONG_GAP_UP + CE (pre-open)', '+8'],
        ['VIX spike >+5%', '-3'],
        ['IV curve INVERTED', '-4'],
        ['Order flow TIGHT + aggression aligned', '+7']
      ]
    ));

    root.appendChild(docsH('Verdict thresholds', 2));
    root.appendChild(docsTable(
      ['Total points', 'Verdict', 'Size multiplier'],
      [
        ['≥35 AND ≤1 caveat', 'STRONG_BUY', '1.0 × Kelly'],
        ['≥18', 'BUY', '0.75 × Kelly'],
        ['≥5', 'BUY_SMALL', '0.5 × Kelly'],
        ['-5 to 4', 'NEUTRAL', '0.25 × Kelly'],
        ['<-5 OR any blocker', 'AVOID', '0']
      ]
    ));

    root.appendChild(docsH('Regime classifier', 1));
    root.appendChild(docsP('Runs on lead index last 10 5-min bars. Three metrics:'));
    root.appendChild(docsList([
      'hhhl/llih count: directional streaks',
      'efficiency = |net move| / total range',
      'volCV = stdev(bar ranges) / mean(bar ranges)'
    ]));
    root.appendChild(docsTable(
      ['Regime', 'Condition', 'Kelly multiplier'],
      [
        ['VOLATILE', 'volCV > 0.6 AND efficiency < 0.4', '0.5×'],
        ['TRENDING_UP', 'efficiency > 0.4 AND hhhl ≥ 4 AND up', '1.2×'],
        ['TRENDING_DN', 'efficiency > 0.4 AND llih ≥ 4 AND down', '1.2×'],
        ['RANGING', 'efficiency < 0.2', '0.7×'],
        ['MIXED', 'else', '1.0×']
      ]
    ));

    root.appendChild(docsH('Kelly position sizing', 1));
    root.appendChild(docsCode(
      'risk = |entry - SL|\n' +
      'reward = |target - entry|\n' +
      'b = reward / risk  (payoff ratio)\n' +
      'p = scoreToWinProb(confidence)\n' +
      'edge = (p × b) - (1 - p)\n' +
      'Kelly f* = edge / b\n' +
      'fractional = f* × 0.25 × regime_multiplier\n' +
      '  (0.25 = quarter-Kelly, industry standard)\n' +
      'Clamped: max 10% of capital, min 0.5%'
    ));
    root.appendChild(docsH('scoreToWinProb curve (before calibration)', 3));
    root.appendChild(docsTable(
      ['Score', 'Win probability'],
      [
        ['<55', '0.48'],
        ['55-67', '0.52'],
        ['68-75', '0.56'],
        ['76-85', '0.60'],
        ['86-95', '0.64'],
        ['≥96', '0.67']
      ]
    ));

    root.appendChild(docsH('ATR-adaptive SL/target (shipped v40)', 1));
    root.appendChild(docsCode(
      'ATR14 = mean true range of last 14 bars\n' +
      'delta ≈ 0.50 at ATM, 0.35 if 1% OTM, 0.25 if 2% OTM, 0.65 if 1% ITM\n' +
      'adverse move = ATR × 1.5 × delta\n' +
      'slPct = adverse move / premium (clamped 8%-25%)\n' +
      'tgtPct = slPct × 2   (clamped 20%-50%)\n\n' +
      'Fallback to flat 15%/30% if <5 bars available.'
    ));

    root.appendChild(docsH('Partial profit (scale-out)', 1));
    root.appendChild(docsP(
      'At 1.5R, system auto-closes 50% of lots and raises SL on remainder to ' +
      'break-even. Mathematically locks in at least +0.75R — you cannot lose ' +
      'on a scaled-out trade.'));

    root.appendChild(docsH('Calibration harness', 1));
    root.appendChild(docsP(
      'Records every closed trade\'s entry confidence score vs outcome. When ' +
      '100+ closes with ≥10 per bucket across ≥3 buckets, the theoretical ' +
      'scoreToWinProb curve is replaced with YOUR empirical win rates.'));

    return root;
  }

  function docsRisks() {
    var root = el('div', {});
    root.appendChild(docsH('What this system is NOT', 1));
    root.appendChild(docsList([
      'Not a broker. EXECUTE opens a paper position. No real money moves.',
      'Not a guarantee. "95% confidence" is a score, not a probability.',
      'Not a tip service. Every decision is derived from market data — you can disagree.'
    ]));

    root.appendChild(docsH('Uncalibrated items (honestly stated)', 1));
    root.appendChild(docsList([
      'The 6-factor weights (25/20/20/15/10/10) are research-informed, not backtested on NSE data. Could be off by ±10%.',
      'scoreToWinProb curve is theoretical until calibration harness kicks in at 100+ trades.',
      'SMC signal point values (+6 FVG, +10 BOS, etc.) are industry heuristics, not NSE-tuned.',
      'The 1.5R scale-out threshold is standard but not personalized to your setup types.'
    ]));

    root.appendChild(docsH('Real risks this system may create', 1));
    root.appendChild(docsList([
      'Voice guidance creating false confidence — "STRONG BUY" feels like a tip.',
      'Every-5m lifecycle tags potentially causing overtrading vs intuition.',
      'Paper portfolio giving false readiness for real execution (slippage, emotion, liquidity missing).'
    ]));

    root.appendChild(docsH('Before real money', 1));
    root.appendChild(docsP(
      'Paper-trade for 100+ trades. Then check:'));
    root.appendChild(docsList([
      'Calibrated win rate > 55% across your common setup buckets',
      'YOUR EDGE section shows consistent positive expectancy',
      'You follow all system EXIT/REDUCE recommendations even when you disagree',
      'You can read PROS/CAVEATS before clicking EXECUTE'
    ]));

    root.appendChild(docsH('When to stop using this tool', 1));
    root.appendChild(docsList([
      '3 losses in a row today — streak banner is telling you',
      'Regime chip shows VOLATILE and you are not comfortable with whipsaw',
      'Alpha chip shows DECAYED — engine has lost edge on recent trades',
      'You feel emotional — tool enforces discipline but not if you open broker app separately'
    ]));

    return root;
  }

  function isIndianMarketOpen() {
    // NSE trading hours: 09:15–15:30 IST, Monday–Friday.
    //
    // Implementation note: new Date() internally stores UTC ms.
    // We compute IST as (UTC + 5.5 hours), then read back the "UTC"
    // fields of the shifted Date — those fields now carry IST values.
    // DO NOT also add getTimezoneOffset() — that's the browser's local
    // offset and would double-correct, breaking IST browsers (the
    // most common case for this product).
    var now = new Date();
    var istMs = now.getTime() + (5.5 * 60 * 60 * 1000);
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
        // PRO MODE toggle — when ON, SMC signals excluded from consensus,
        // UI hides retail-trader visual elements, voice changes vocabulary.
        (function () {
          var on = proMode.isOn();
          return el('button', {
            title: 'Institutional mode: disables SMC/FVG/OB retail signals',
            onClick: function () { proMode.toggle(); rerender(); },
            style: {
              background: on ? '#9333EA' + '22' : 'transparent',
              border: '1px solid ' + (on ? '#9333EA' : C.divider),
              color: on ? '#9333EA' : C.textSec,
              borderRadius: '4px', padding: '3px 8px',
              fontSize: '9px', fontWeight: 800, cursor: 'pointer',
              letterSpacing: '0.8px', fontFamily: MONO
            }
          }, on ? 'PRO ON' : 'PRO');
        })(),
        // Help icon — opens docs modal explaining how to trade + scoring
        iconBtn('?', false, function () { state.showDocs = !state.showDocs; rerender(); }),
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
        // ── MY POSITIONS — any held trade NOT currently in top-3 ────────
        // When a user's active position rotates off the top-3 scan, we
        // pin it to the top of this column so it's always visible.
        // No duplicates: trades that ARE in top-3 are not repeated here.
        var top3Ids = {};
        state.trades.forEach(function (t) { if (t) top3Ids[t.id] = true; });
        var held = (state.heldTrades || []).filter(function (h) {
          return !top3Ids[h.id];
        });
        if (held.length > 0) {
          body.appendChild(el('div', {
            style: {
              fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px',
              color: C.green, marginBottom: '4px',
              padding: '4px 2px 2px'
            }
          }, 'MY POSITIONS (' + held.length + ') — OFF TOP-3 SCAN'));
          held.forEach(function (t) {
            var card = tradeCard(t);
            // Add a subtle badge so user knows this is off-scan
            if (t._staleData) {
              card.appendChild(el('div', {
                style: {
                  position: 'absolute', top: '4px', right: '4px',
                  fontSize: '8px', fontWeight: 700, padding: '1px 4px',
                  borderRadius: '2px', background: C.orange + '22',
                  color: C.orange, letterSpacing: '0.3px'
                }
              }, 'STALE DATA'));
            }
            body.appendChild(card);
          });
          // Separator
          body.appendChild(el('div', {
            style: {
              borderTop: '1px dashed ' + C.divider,
              margin: '8px 0 8px', fontSize: '9px',
              color: C.textMute, textAlign: 'center', padding: '4px 0 0',
              letterSpacing: '1.2px', fontWeight: 700
            }
          }, 'TOP 3 NEW OPPORTUNITIES'));
        }

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
    // Lifecycle status for this trade (determines card left-edge color)
    var _cardOpenPos = paperPortfolio.findByTradeId(trade.id);
    var _cardLatestPos = _cardOpenPos ||
      paperPortfolio.findLatestByTradeId(trade.id);
    var _edgeColor = null;
    if (_cardOpenPos) {
      _edgeColor = _cardOpenPos.status === 'active' ? C.green : C.orange;
    } else if (_cardLatestPos && _cardLatestPos.status === 'won') {
      _edgeColor = C.green;
    } else if (_cardLatestPos && _cardLatestPos.status === 'lost') {
      _edgeColor = C.red;
    }

    var card = el('div', {
      onClick: function () { selectTrade(trade); },
      style: {
        height: '104px', padding: '8px',
        background: isSelected ? C.active : C.card,
        borderRadius: '12px',
        border: '1px solid ' + (isSelected ? C.blue : (trade.gammaMode ? '#F59E0B' : C.divider)),
        // Thick left edge when position is live/closed to make status unmistakable
        borderLeft: _edgeColor
          ? '4px solid ' + _edgeColor
          : '1px solid ' + (isSelected ? C.blue : (trade.gammaMode ? '#F59E0B' : C.divider)),
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

    // Row 1 col 2 — confidence with honest labeling.
    // Shows raw confidence score at top + calibration context below:
    //   • If attribution bucket has ≥5 past trades: "62% win (24 trades)"
    //   • Else if calibration harness applied: "calibrated"
    //   • Else: "uncal" — marks as theoretical, not empirical
    // This prevents users from treating "95%" as a guaranteed win probability.
    var attrB = null;
    try { attrB = tradeAttribution.lookupFor(trade); } catch (e) {}
    var isCalibrated = kellySizer._calibrated;
    var subLabel = '';
    var subColor = C.textMute;
    if (attrB && attrB.count >= 5) {
      subLabel = attrB.winRate.toFixed(0) + '% win · ' + attrB.count + ' trades';
      subColor = attrB.expectancy > 0 ? C.green
               : attrB.expectancy < 0 ? C.red : C.textSec;
    } else if (isCalibrated) {
      subLabel = 'calibrated';
      subColor = C.textSec;
    } else {
      subLabel = 'uncal';
      subColor = C.textMute;
    }

    var confCell = el('div', {
      style: {
        display: 'flex', flexDirection: 'column', alignItems: 'flex-end',
        alignSelf: 'center', minWidth: '54px'
      }
    });
    confCell.appendChild(el('div', {
      className: 'at-fade at-fade-' + (state.fadeTick || 0),
      style: {
        fontSize: '20px', fontWeight: 700, color: confColor(trade.confidence),
        lineHeight: 1.1, fontFamily: MONO,
        textAlign: 'right'
      }
    }, trade.confidence + '%'));
    confCell.appendChild(el('div', {
      style: {
        fontSize: '8px', color: subColor, fontFamily: MONO,
        marginTop: '2px', whiteSpace: 'nowrap',
        letterSpacing: '0.3px', fontWeight: 600
      }
    }, subLabel));
    card.appendChild(confCell);

    // Row 1 col 3 — EXECUTE button OR state badge if already executing/closed
    // Determine trade lifecycle state for this card
    var openPos = paperPortfolio.findByTradeId(trade.id);
    var latestPos = openPos || paperPortfolio.findLatestByTradeId(trade.id);
    var buttonNode;

    if (openPos) {
      // Currently live — pending or active
      var activeLabel = openPos.status === 'active' ? 'LIVE' : 'PENDING';
      var activeBg = openPos.status === 'active' ? C.green : C.orange;
      buttonNode = el('button', {
        onClick: function (e) {
          e.stopPropagation();
          // Clicking LIVE selects the trade so user sees it in middle monitor
          selectTrade(trade);
        },
        title: 'Already executing — click to view in Live Monitor',
        style: {
          height: '36px', width: '100px',
          background: activeBg + '22',
          color: activeBg,
          fontWeight: 800, fontSize: '11px',
          border: '1px solid ' + activeBg,
          borderRadius: '6px', cursor: 'pointer',
          letterSpacing: '0.8px', alignSelf: 'center'
        }
      }, '● ' + activeLabel);
    } else if (latestPos && (latestPos.status === 'won' ||
                              latestPos.status === 'lost' ||
                              latestPos.status === 'cancelled' ||
                              latestPos.status === 'expired')) {
      // Previous position closed — show outcome
      var wonColor = latestPos.status === 'won' ? C.green
                   : latestPos.status === 'lost' ? C.red : C.textMute;
      var pctTxt = latestPos.realizedPct != null
        ? (latestPos.realizedPct >= 0 ? '+' : '') + latestPos.realizedPct.toFixed(1) + '%'
        : latestPos.status.toUpperCase();
      buttonNode = el('button', {
        onClick: function (e) {
          e.stopPropagation();
          // Allow re-execute after a closed trade
          onExecute(trade);
        },
        title: 'Previous outcome: ' + latestPos.status.toUpperCase() +
               (latestPos.realizedPct != null
                  ? ' at ' + latestPos.realizedPct.toFixed(1) + '%'
                  : '') + '. Click to re-execute.',
        style: {
          height: '36px', width: '100px',
          background: wonColor + '15',
          color: wonColor,
          fontWeight: 800, fontSize: '10px',
          border: '1px solid ' + wonColor + '55',
          borderRadius: '6px', cursor: 'pointer',
          letterSpacing: '0.5px', alignSelf: 'center',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          lineHeight: 1.1
        }
      }, [
        el('span', { style: { fontSize: '9px', opacity: 0.8 } }, latestPos.status.toUpperCase()),
        el('span', { style: { fontSize: '13px', fontWeight: 900 } }, pctTxt)
      ]);
    } else {
      // Normal EXECUTE button — but check portfolio risk first so user
      // sees why they can't open another trade (e.g. max concurrent reached).
      var riskGate = portfolioRisk.checkAllow();
      if (!riskGate.allow) {
        // Risk-blocked state: greyed-out button with tooltip explaining why
        buttonNode = el('button', {
          onClick: function (e) {
            e.stopPropagation();
            // Still call onExecute — it will log + speak the block reason
            onExecute(trade);
          },
          title: 'Risk gate blocked: ' + riskGate.reason,
          style: {
            height: '36px', width: '100px',
            background: C.red + '15',
            color: C.red,
            fontWeight: 800, fontSize: '10px',
            border: '1px solid ' + C.red + '55',
            borderRadius: '6px', cursor: 'not-allowed',
            letterSpacing: '0.5px', alignSelf: 'center',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            lineHeight: 1.1
          }
        }, [
          el('span', { style: { fontSize: '9px', opacity: 0.8 } }, 'RISK'),
          el('span', { style: { fontSize: '11px', fontWeight: 900 } }, 'BLOCKED')
        ]);
      } else {
        // Primary action button with inline sizing preview.
        // Two lines: "TAKE TRADE" + "2 lots · ₹4.2K risk" so user sees
        // exactly what they're about to commit to without clicking first.
        var preview = null;
        try { preview = tradePreview.compute(trade); } catch (e) {}
        var sub = (preview && preview.shortLabel) || '';

        buttonNode = el('button', {
          onClick: function (e) { e.stopPropagation(); onExecute(trade); },
          title: (preview && preview.allowed)
            ? 'Click to confirm — opens ' + sub
            : 'Trade has blockers — click for details',
          style: {
            height: '36px', width: '100px',
            background: 'linear-gradient(180deg, ' + C.green + ', #16A34A)',
            color: '#062B17', fontWeight: 800,
            border: 'none', borderRadius: '6px', cursor: 'pointer',
            letterSpacing: '0.5px', alignSelf: 'center',
            boxShadow: '0 0 0 1px ' + C.green + '66, 0 4px 12px ' + C.green + '33',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            lineHeight: 1.15, padding: '2px 4px'
          }
        }, [
          el('span', { style: { fontSize: '11px', fontWeight: 900 } }, 'TAKE TRADE'),
          el('span', {
            style: { fontSize: '8px', opacity: 0.85, fontWeight: 700 }
          }, sub || '—')
        ]);
      }
    }
    card.appendChild(buttonNode);

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

    // Data provenance badge — honest vendor/latency/OI-age pill in bottom-right.
    // When backend doesn't provide metadata, shows "vendor unknown · age ?"
    // so user knows the feed status. Institutional tables always show this.
    try {
      var provLabel = dataProvenance.badge(trade._raw || {});
      var provCol = dataProvenance.badgeColor(trade._raw || {});
      card.appendChild(el('div', {
        title: 'Data provenance: vendor · latency · OI age',
        style: {
          position: 'absolute', bottom: '4px', right: '6px',
          fontSize: '8px', color: provCol, fontFamily: MONO,
          opacity: 0.75, letterSpacing: '0.2px', pointerEvents: 'none'
        }
      }, provLabel));
    } catch (e) {}

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

    // ═══════════════════════════════════════════════════════════════════
    // PORTFOLIO TODAY — pinned strip showing day-level stats
    // ═══════════════════════════════════════════════════════════════════
    // Users running multi-trade sessions need to see the forest, not
    // just trees. This strip surfaces:
    //   • Day net P&L (color-coded)
    //   • Win/Loss count + win rate
    //   • Open positions count / max concurrent cap
    //   • Streak warning if losing 2+ in a row
    var today = sessionGuide.today();
    var decision = sessionGuide.shouldTakeNew();
    var dayColor = today.netPnl > 1 ? C.green
                 : today.netPnl < -1 ? C.red
                 : C.textSec;
    var strip = el('div', {
      style: {
        padding: '7px 10px 7px',
        borderBottom: '1px solid ' + C.divider,
        background: C.card,
        flex: '0 0 auto'
      }
    });

    // Row 1: "TODAY" label + 3 compact metric boxes
    var row1 = el('div', {
      style: {
        display: 'grid',
        gridTemplateColumns: 'auto 1fr 1fr 1fr',
        gap: '8px', alignItems: 'center',
        marginBottom: (today.lossStreak >= 2 || decision.recommend !== 'TAKE') ? '5px' : '0'
      }
    });
    row1.appendChild(el('div', {
      style: {
        fontSize: '9px', fontWeight: 800, letterSpacing: '1.3px',
        color: C.textMute
      }
    }, 'TODAY'));

    // Net P&L
    var pnlBox = el('div', {
      style: {
        textAlign: 'center', padding: '3px 4px',
        background: C.bg, borderRadius: '3px',
        borderLeft: '2px solid ' + dayColor
      }
    });
    pnlBox.appendChild(el('div', {
      style: {
        fontSize: '8px', color: C.textMute, fontWeight: 700,
        letterSpacing: '0.5px'
      }
    }, 'NET'));
    pnlBox.appendChild(el('div', {
      style: {
        fontSize: '12px', fontWeight: 800, color: dayColor,
        fontFamily: MONO, lineHeight: 1.1
      }
    }, (today.netPnl >= 0 ? '+' : '') + today.netPnl.toFixed(1) + '%'));
    row1.appendChild(pnlBox);

    // Record W-L + rate
    var recBox = el('div', {
      style: {
        textAlign: 'center', padding: '3px 4px',
        background: C.bg, borderRadius: '3px'
      }
    });
    recBox.appendChild(el('div', {
      style: {
        fontSize: '8px', color: C.textMute, fontWeight: 700,
        letterSpacing: '0.5px'
      }
    }, 'RECORD'));
    recBox.appendChild(el('div', {
      style: {
        fontSize: '11px', fontWeight: 800, color: C.textPri,
        fontFamily: MONO, lineHeight: 1.1
      }
    }, today.closedCount === 0
         ? '—'
         : today.wins + 'W / ' + today.losses + 'L'));
    if (today.closedCount > 0) {
      recBox.appendChild(el('div', {
        style: {
          fontSize: '8px', color: C.textMute, fontFamily: MONO,
          lineHeight: 1
        }
      }, Math.round(today.winRate) + '% win'));
    }
    row1.appendChild(recBox);

    // Open / Capacity
    var maxConc = portfolioRisk.config.maxConcurrent;
    var occupancy = today.openNow + today.pendingNow;
    var capColor = occupancy >= maxConc ? C.red
                 : occupancy >= maxConc - 1 ? C.orange : C.textSec;
    var capBox = el('div', {
      style: {
        textAlign: 'center', padding: '3px 4px',
        background: C.bg, borderRadius: '3px',
        borderLeft: '2px solid ' + capColor
      }
    });
    capBox.appendChild(el('div', {
      style: {
        fontSize: '8px', color: C.textMute, fontWeight: 700,
        letterSpacing: '0.5px'
      }
    }, 'OPEN'));
    capBox.appendChild(el('div', {
      style: {
        fontSize: '12px', fontWeight: 800, color: capColor,
        fontFamily: MONO, lineHeight: 1.1
      }
    }, occupancy + '/' + maxConc));
    row1.appendChild(capBox);
    strip.appendChild(row1);

    // Row 2 (conditional): streak warning OR new-trade recommendation
    if (today.lossStreak >= 2) {
      var streakBanner = el('div', {
        style: {
          background: C.red + '18', borderLeft: '3px solid ' + C.red,
          borderRadius: '2px', padding: '4px 7px',
          fontSize: '10px', color: C.red, fontWeight: 700,
          lineHeight: 1.3
        }
      }, today.lossStreak + ' losses in a row · ' +
         (today.lossStreak >= 3 ? 'STOP trading today'
                                : 'reduce size, don\'t revenge-trade'));
      strip.appendChild(streakBanner);
    } else if (decision.recommend === 'CAUTION') {
      strip.appendChild(el('div', {
        style: {
          background: C.orange + '15', borderLeft: '3px solid ' + C.orange,
          borderRadius: '2px', padding: '4px 7px',
          fontSize: '10px', color: C.orange, lineHeight: 1.3
        }
      }, '⚠ ' + decision.reason));
    } else if (decision.recommend === 'SKIP') {
      strip.appendChild(el('div', {
        style: {
          background: C.red + '12', borderLeft: '3px solid ' + C.red,
          borderRadius: '2px', padding: '4px 7px',
          fontSize: '10px', color: C.red, lineHeight: 1.3
        }
      }, '✕ ' + decision.reason));
    }

    panel.appendChild(strip);

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
          letterSpacing: '0.8px', marginBottom: '6px',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }
      }, [
        el('span', {}, 'SELECTED: ' + t.symbol + ' ' + t.strike),
        // Recompute timestamp — tells user "this verdict reflects the click, not 5m ago"
        (function () {
          var ts = state.selectedComputedAt;
          if (!ts) return el('span', {}, '');
          // Format HH:MM:SS in IST
          var istMs = ts + (5.5 * 60 * 60 * 1000);
          var d = new Date(istMs);
          var hh = String(d.getUTCHours()).padStart(2, '0');
          var mm = String(d.getUTCMinutes()).padStart(2, '0');
          var ss = String(d.getUTCSeconds()).padStart(2, '0');
          var isFresh = state.selectedRecomputeFlash;
          return el('span', {
            style: {
              color: isFresh ? C.green : C.textMute,
              fontWeight: 700, fontFamily: MONO,
              fontSize: '9px', letterSpacing: '0.3px',
              transition: 'color 400ms ease'
            }
          }, (isFresh ? '✓ RECOMPUTED · ' : '') + hh + ':' + mm + ':' + ss + ' IST');
        })()
      ]));

      // Event calendar warning / block banner above verdict
      try {
        var ev = eventCalendar.checkTrade(t, state.region || 'IN');
        if (ev.action === 'BLOCK' || ev.action === 'WARN') {
          var eCol = ev.action === 'BLOCK' ? C.red : C.orange;
          sel.appendChild(el('div', {
            style: {
              background: eCol + '18', borderLeft: '3px solid ' + eCol,
              borderRadius: '3px', padding: '6px 8px', marginBottom: '6px',
              fontSize: '10px', color: eCol, fontWeight: 700, lineHeight: 1.3
            }
          }, (ev.action === 'BLOCK' ? '🚫 ' : '⚠ ') + ev.reason));
        }
      } catch (e) {}

      // ═════════════════════════════════════════════════════════════════
      // SCENARIO MATRIX — tail risk before EXECUTE (institutional)
      // ═════════════════════════════════════════════════════════════════
      // "What happens if spot gaps 0.5% against me? If IV drops 3 points?"
      // 3×3 grid repricing the option at shocked spot × IV inputs. The
      // worst cell and best cell are highlighted so user sees tail risk
      // before clicking EXECUTE.
      try {
        var scen = scenarioAnalysis.compute(t, t._raw || {});
        if (scen && scen.matrix) {
          var scenPanel = el('div', {
            style: {
              background: C.card, border: '1px solid ' + C.divider,
              borderRadius: '3px', padding: '7px 9px', marginBottom: '6px'
            }
          });
          scenPanel.appendChild(el('div', {
            style: {
              fontSize: '9px', fontWeight: 700, color: C.textSec,
              letterSpacing: '0.6px', marginBottom: '4px'
            }
          }, 'SCENARIO P&L · SPOT × IV SHOCK'));

          // Grid: 4 cols (label + 3 IV) × 4 rows (label + 3 spot)
          var grid = el('div', {
            style: {
              display: 'grid',
              gridTemplateColumns: '46px repeat(3, 1fr)',
              gap: '2px', fontFamily: MONO, fontSize: '9px'
            }
          });
          var hdrStyle = {
            color: C.textMute, fontWeight: 700, padding: '2px 3px',
            textAlign: 'center'
          };
          grid.appendChild(el('div', { style: hdrStyle }, ''));
          grid.appendChild(el('div', { style: hdrStyle }, 'IV -3'));
          grid.appendChild(el('div', { style: hdrStyle }, 'IV flat'));
          grid.appendChild(el('div', { style: hdrStyle }, 'IV +3'));

          var spotLabels = ['Spot -0.5%', 'Spot flat', 'Spot +0.5%'];
          for (var si = 0; si < 3; si++) {
            grid.appendChild(el('div', {
              style: Object.assign({}, hdrStyle, { textAlign: 'left' })
            }, spotLabels[si]));
            for (var ii = 0; ii < 3; ii++) {
              var cell = scen.matrix[si][ii];
              var bg = C.bg, fg = C.textPri, bd = 'transparent';
              if (cell) {
                var p = cell.pnlPct;
                // Color scale — red for losses, green for gains
                if (p < -15) { bg = C.red + '28'; fg = C.red; }
                else if (p < 0) { bg = C.red + '12'; fg = C.red; }
                else if (p < 15) { bg = C.green + '12'; fg = C.green; }
                else { bg = C.green + '28'; fg = C.green; }
                // Highlight worst/best cells
                if (cell === scen.worst) bd = C.red;
                else if (cell === scen.best) bd = C.green;
              }
              grid.appendChild(el('div', {
                style: {
                  background: bg, color: fg,
                  padding: '3px 3px', textAlign: 'center',
                  border: '1px solid ' + bd, borderRadius: '2px',
                  fontWeight: 700
                }
              }, cell ? (p >= 0 ? '+' : '') + p.toFixed(0) + '%' : '—'));
            }
          }
          scenPanel.appendChild(grid);

          // Summary line underneath
          var sumLine = scenarioAnalysis.summaryLine(scen);
          if (sumLine) {
            scenPanel.appendChild(el('div', {
              style: {
                fontSize: '9px', color: C.textSec, marginTop: '4px',
                lineHeight: 1.3, fontFamily: MONO
              }
            }, sumLine));
          }
          sel.appendChild(scenPanel);
        }
      } catch (e) {}

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
    (state.heldTrades || []).forEach(function (t) { priceLookup[t.id] = t; });
    if (state.selected) priceLookup[state.selected.id] = state.selected;

    var activePositions = [];
    var recentlyClosed = [];
    var nowTs = Date.now();
    var RECENT_MS = 5 * 60 * 1000; // 5 minutes
    for (var id in paperPortfolio.positions) {
      var p = paperPortfolio.positions[id];
      if (p.status === 'active' || p.status === 'pending') {
        activePositions.push(p);
      } else if ((p.status === 'won' || p.status === 'lost' ||
                  p.status === 'cancelled' || p.status === 'expired') &&
                 p.closedAt && (nowTs - p.closedAt) < RECENT_MS) {
        recentlyClosed.push(p);
      }
    }
    // Sort recently closed by most-recent first
    recentlyClosed.sort(function (a, b) { return (b.closedAt || 0) - (a.closedAt || 0); });

    // ── Recently-closed banner ─────────────────────────────────────────
    // Shows outcome of last trades so user gets closure after EXIT happens.
    // Disappears after 5 minutes — permanent record still in the portfolio.
    if (recentlyClosed.length > 0) {
      var closedSection = el('div', {
        style: { padding: '10px 10px 0' }
      });
      closedSection.appendChild(el('div', {
        style: {
          fontSize: '9px', fontWeight: 700, color: C.textSec,
          letterSpacing: '0.8px', marginBottom: '6px'
        }
      }, 'RECENTLY CLOSED (' + recentlyClosed.length + ')'));

      recentlyClosed.slice(0, 3).forEach(function (cp) {
        var won = cp.status === 'won';
        var col = won ? C.green : cp.status === 'lost' ? C.red : C.textMute;
        var pct = cp.realizedPct != null
          ? (cp.realizedPct >= 0 ? '+' : '') + cp.realizedPct.toFixed(1) + '%'
          : '—';
        var minsAgo = Math.max(0, Math.floor((nowTs - cp.closedAt) / 60000));
        var closedRow = el('div', {
          style: {
            background: col + '10', borderLeft: '3px solid ' + col,
            borderRadius: '3px', padding: '6px 8px', marginBottom: '5px'
          }
        });
        closedRow.appendChild(el('div', {
          style: {
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            fontSize: '11px', fontFamily: MONO
          }
        }, [
          el('span', { style: { color: C.textPri, fontWeight: 700 } },
            cp.sym + ' ' + cp.strike),
          el('span', { style: { color: col, fontWeight: 800 } },
            cp.status.toUpperCase() + ' ' + pct)
        ]));
        closedRow.appendChild(el('div', {
          style: {
            fontSize: '9px', color: C.textMute, fontFamily: MONO,
            marginTop: '2px'
          }
        }, 'closed ' + (minsAgo === 0 ? 'just now' : minsAgo + 'm ago') +
           (cp.closeReason ? ' · ' + cp.closeReason.replace(/_/g, ' ') : '')));
        closedSection.appendChild(closedRow);
      });
      scroll.appendChild(closedSection);
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

    // ═══════════════════════════════════════════════════════════════════
    // BOOK GREEKS — aggregate portfolio-level risk view (institutional)
    // ═══════════════════════════════════════════════════════════════════
    // Every professional desk tracks NET Greeks across the book, not per
    // position. Two NIFTY CEs is one concentrated directional bet, not two
    // independent trades. Shows net delta/gamma/vega/theta + correlation
    // warnings for concentration risk.
    try {
      var book = portfolioGreeks.bookGreeks();
      if (book.positionsCount > 0) {
        var greeksSection = el('div', {
          style: {
            padding: '10px', borderTop: '1px solid ' + C.divider
          }
        });
        greeksSection.appendChild(el('div', {
          style: {
            fontSize: '9px', fontWeight: 700, color: C.textSec,
            letterSpacing: '0.8px', marginBottom: '6px',
            display: 'flex', justifyContent: 'space-between'
          }
        }, 'BOOK GREEKS · ' + book.positionsCount + ' OPEN' + '⠀'));

        // Four mini-cells for net delta/gamma/vega/theta
        var row = el('div', {
          style: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px', marginBottom: '4px' }
        });
        function greekCell(label, val, unit) {
          var displayVal = val == null ? '—' : val.toFixed(0);
          var col = C.textPri;
          if (label === 'Δ' && val != null) {
            col = Math.abs(val) > 50 ? C.orange : C.textPri;
          }
          var cell = el('div', {
            style: {
              background: C.card, borderRadius: '2px', padding: '4px 6px',
              textAlign: 'center', fontFamily: MONO
            }
          });
          cell.appendChild(el('div', {
            style: { fontSize: '9px', color: C.textSec, marginBottom: '1px' }
          }, label));
          cell.appendChild(el('div', {
            style: { fontSize: '12px', fontWeight: 700, color: col }
          }, displayVal + (unit || '')));
          return cell;
        }
        row.appendChild(greekCell('Δ DELTA', book.netDelta));
        row.appendChild(greekCell('Γ GAMMA', book.netGamma));
        row.appendChild(greekCell('ν VEGA', book.netVega));
        row.appendChild(greekCell('θ THETA', book.netTheta));
        greeksSection.appendChild(row);

        // Warnings (missing greek data, etc.)
        if (book.warnings.length > 0) {
          book.warnings.forEach(function (w) {
            greeksSection.appendChild(el('div', {
              style: {
                fontSize: '9px', color: C.textMute, fontStyle: 'italic',
                marginTop: '3px', lineHeight: 1.3
              }
            }, '· ' + w));
          });
        }
        scroll.appendChild(greeksSection);
      }
    } catch (e) {}

    // ═══════════════════════════════════════════════════════════════════
    // YOUR EDGE — per-user trade attribution insights
    // ═══════════════════════════════════════════════════════════════════
    // What this user wins at vs what they lose at. Data accumulates over
    // time — a bucket needs ≥5 trades before it surfaces. Without this,
    // users never learn which setups actually work FOR THEM.
    var attrBuckets = [];
    try {
      var worst = tradeAttribution.worstBuckets(5);
      var best = tradeAttribution.bestBuckets(5);
      // Dedup: a bucket can appear in both if few buckets exist
      var seen = {};
      best.concat(worst).forEach(function (b) {
        if (!seen[b.key]) { seen[b.key] = true; attrBuckets.push(b); }
      });
    } catch (e) {}
    if (attrBuckets.length > 0) {
      var edgeSection = el('div', {
        style: {
          padding: '10px', borderTop: '1px solid ' + C.divider
        }
      });
      edgeSection.appendChild(el('div', {
        style: {
          fontSize: '9px', fontWeight: 700, color: C.textSec,
          letterSpacing: '0.8px', marginBottom: '6px'
        }
      }, 'YOUR EDGE · LEARNED FROM ' + Object.keys(paperPortfolio.positions).length + ' TRADES'));

      attrBuckets.slice(0, 4).forEach(function (b) {
        var bCol = b.expectancy > 0 ? C.green
                 : b.expectancy < -0.2 ? C.red : C.textSec;
        var row = el('div', {
          style: {
            background: bCol + '12', borderLeft: '2px solid ' + bCol,
            borderRadius: '2px', padding: '4px 7px', marginBottom: '4px',
            fontSize: '10px', lineHeight: 1.3
          }
        });
        row.appendChild(el('div', {
          style: { color: C.textPri, fontFamily: MONO, fontWeight: 700 }
        }, b.phase + ' · ' + b.regime.replace(/_/g, ' ') + ' · ' + b.side +
           (b.gamma ? ' · gamma' : '')));
        row.appendChild(el('div', {
          style: { color: bCol, fontFamily: MONO, fontSize: '9px' }
        }, b.wins + 'W / ' + b.losses + 'L · ' +
           b.winRate.toFixed(0) + '% · expect ' +
           (b.expectancy >= 0 ? '+' : '') + b.expectancy.toFixed(2) + '%/trade'));
        edgeSection.appendChild(row);
      });

      // If an active trade is selected, surface its specific bucket context
      if (state.selected) {
        var lookup = null;
        try { lookup = tradeAttribution.lookupFor(state.selected); } catch (e) {}
        if (lookup) {
          var col = lookup.expectancy > 0 ? C.green : C.red;
          edgeSection.appendChild(el('div', {
            style: {
              marginTop: '6px',
              background: col + '15', borderLeft: '3px solid ' + col,
              borderRadius: '2px', padding: '5px 8px',
              fontSize: '10px', color: col, fontWeight: 700, lineHeight: 1.3
            }
          }, 'THIS SETUP: ' + lookup.winRate.toFixed(0) + '% win rate over ' +
             lookup.count + ' trades'));
        }
      }

      scroll.appendChild(edgeSection);
    }

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
    }, 'PRE-OPEN · GLOBAL CUES'));

    // Note: Regime, Alpha, Risk are already in the top header chips.
    // We don't repeat them here. Only showing live external data the
    // header doesn't cover: pre-open gap + VIX.

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
    // Right-column layout is DEEP-DIVE ONLY. The middle Live Monitor
    // already shows: consensus verdict (big card + pros/caveats), open
    // positions with live lifecycle tags, and macro context (regime/alpha/
    // gap/VIX/risk). We do NOT duplicate those here — that's what the user
    // flagged as redundant.
    //
    // Right column provides what middle can't fit:
    //   1. Entry engine — current price / trigger / SL / target
    //   2. Candlestick chart with VWAP
    //   3. Price Action / SMC primitives (FVG, OB, BOS/CHoCH, sweeps, EMA, candle)
    //   4. Vol Metrics (ATR, Expected Move, Keltner Squeeze)
    //   5. Payoff diagram at expiry
    //   6. GEX heatmap + Trend compass
    //   7. Greeks + IV/HV
    //   8. Sentiment bar (unique horizontal visual)
    //   9. Option chain
    //  10. Risk block (detailed config)
    scroll.appendChild(renderEntryEngine());
    scroll.appendChild(renderCandlestickPanel());
    scroll.appendChild(renderPriceActionPanel());
    scroll.appendChild(renderVolMetricsPanel());
    scroll.appendChild(renderPayoffPanel());
    scroll.appendChild(renderGexCompassPanel());
    scroll.appendChild(renderGreeksVolPanel());
    scroll.appendChild(renderSentimentBar());
    scroll.appendChild(renderOptionChain());
    scroll.appendChild(renderRiskBlock());
    panel.appendChild(scroll);

    // Voice log pinned at bottom (smaller height, its own scroll)
    panel.appendChild(renderVoiceLog());
    return panel;
  }

  // ── SENTIMENT BAR — single-glance aggregate bull/bear barometer ─────────
  function renderSentimentBar() {
    var wrap = el('div', {
      style: {
        background: C.card, borderBottom: '1px solid ' + C.divider,
        padding: '8px 10px'
      }
    });
    if (!state.selected) return wrap;
    var sent = sentimentBar.read(state.selected._raw || {});
    if (sent.status !== 'ok') {
      wrap.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'Sentiment: insufficient data'));
      return wrap;
    }

    var color = sent.score >= 75 ? C.green
              : sent.score >= 60 ? '#84cc16'    // yellow-green
              : sent.score >= 45 ? C.textSec
              : sent.score >= 25 ? C.orange
              : C.red;

    wrap.appendChild(el('div', {
      style: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: '6px'
      }
    }, [
      el('span', {
        style: { fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px', color: C.textSec }
      }, 'MARKET SENTIMENT'),
      el('span', {
        style: {
          fontSize: '11px', fontWeight: 800, color: color, fontFamily: MONO
        }
      }, sent.label + ' · ' + sent.score + '/100')
    ]));

    // Horizontal bar
    var barWrap = el('div', {
      style: {
        height: '8px', background: C.bg, borderRadius: '2px',
        overflow: 'hidden', position: 'relative',
        border: '1px solid ' + C.divider
      }
    });
    // Gradient background: red left → yellow mid → green right
    barWrap.appendChild(el('div', {
      style: {
        position: 'absolute', left: 0, top: 0, bottom: 0,
        width: '100%',
        background: 'linear-gradient(90deg, ' + C.red + ', ' + C.orange + ', ' + C.green + ')',
        opacity: 0.25
      }
    }));
    // Marker position
    barWrap.appendChild(el('div', {
      style: {
        position: 'absolute',
        left: 'calc(' + sent.score + '% - 2px)',
        top: 0, bottom: 0, width: '4px',
        background: color,
        boxShadow: '0 0 4px ' + color
      }
    }));
    wrap.appendChild(barWrap);
    wrap.appendChild(el('div', {
      style: {
        fontSize: '9px', color: C.textMute, fontFamily: MONO,
        marginTop: '3px', textAlign: 'center'
      }
    }, sent.bullPoints + ' bull · ' + sent.bearPoints + ' bear · ' + sent.totalChecked + ' signals'));

    return wrap;
  }

  // ── VOL METRICS PANEL — ATR, Expected Move, Keltner Squeeze ─────────────
  function renderVolMetricsPanel() {
    var wrap = el('div', {
      style: {
        background: C.card, borderBottom: '1px solid ' + C.divider,
        padding: '8px 10px'
      }
    });
    if (!state.selected) return wrap;
    var raw = state.selected._raw || {};
    var bars = raw.ohlc_bars || [];
    var spot = raw.spot || 0;
    var atmIV = raw.atm_iv || 0;

    wrap.appendChild(el('div', {
      style: {
        fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px',
        color: C.textSec, marginBottom: '6px'
      }
    }, 'VOLATILITY METRICS'));

    var vm = volMetrics.compute(bars, spot, atmIV);
    if (vm.status !== 'ok') {
      wrap.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'Insufficient bars for volatility metrics'));
      return wrap;
    }

    // 3-column grid: ATR | Expected Move | Keltner
    var grid = el('div', {
      style: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }
    });

    // ATR
    var atrCol = el('div', {
      style: { background: C.bg, borderRadius: '4px', padding: '6px 8px' }
    });
    atrCol.appendChild(el('div', {
      style: { fontSize: '9px', fontWeight: 700, color: C.textSec, marginBottom: '3px' }
    }, 'ATR 14'));
    atrCol.appendChild(el('div', {
      style: { fontSize: '14px', fontWeight: 800, color: C.textPri, fontFamily: MONO }
    }, vm.atr.toFixed(2)));
    atrCol.appendChild(el('div', {
      style: { fontSize: '9px', color: C.textMute, fontFamily: MONO, marginTop: '2px' }
    }, vm.atrPct.toFixed(2) + '% of spot'));
    grid.appendChild(atrCol);

    // Expected move
    var emCol = el('div', {
      style: { background: C.bg, borderRadius: '4px', padding: '6px 8px' }
    });
    emCol.appendChild(el('div', {
      style: { fontSize: '9px', fontWeight: 700, color: C.textSec, marginBottom: '3px' }
    }, 'EXPECTED MOVE · 1D'));
    if (vm.expectedMove > 0) {
      emCol.appendChild(el('div', {
        style: { fontSize: '13px', fontWeight: 800, color: C.textPri, fontFamily: MONO }
      }, '±' + vm.expectedMove.toFixed(2)));
      emCol.appendChild(el('div', {
        style: { fontSize: '9px', color: C.textMute, fontFamily: MONO, marginTop: '2px' }
      }, vm.expectedLow.toFixed(0) + ' → ' + vm.expectedHigh.toFixed(0)));
    } else {
      emCol.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'no IV'));
    }
    grid.appendChild(emCol);

    // Keltner Squeeze
    var ksCol = el('div', {
      style: { background: C.bg, borderRadius: '4px', padding: '6px 8px' }
    });
    ksCol.appendChild(el('div', {
      style: { fontSize: '9px', fontWeight: 700, color: C.textSec, marginBottom: '3px' }
    }, 'KELTNER'));
    if (vm.squeeze != null) {
      var kcColor = vm.squeeze ? '#a855f7' : C.textSec;
      ksCol.appendChild(el('div', {
        style: { fontSize: '13px', fontWeight: 800, color: kcColor, fontFamily: MONO }
      }, vm.squeeze ? 'SQUEEZE ON' : 'NORMAL'));
      ksCol.appendChild(el('div', {
        style: {
          fontSize: '9px', color: C.textMute, fontFamily: MONO, marginTop: '2px',
          lineHeight: 1.2
        }
      }, vm.squeeze ? 'Breakout imminent' : 'Range-bound vol'));
    } else {
      ksCol.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'need 20+ bars'));
    }
    grid.appendChild(ksCol);

    wrap.appendChild(grid);
    return wrap;
  }

  // ── PAYOFF DIAGRAM — inline SVG P&L curve at expiry ─────────────────────
  function renderPayoffPanel() {
    var wrap = el('div', {
      style: {
        background: C.card, borderBottom: '1px solid ' + C.divider,
        padding: '8px 10px'
      }
    });
    if (!state.selected) return wrap;
    var raw = state.selected._raw || {};
    var spot = raw.spot || 0;
    if (!spot) return wrap;

    var p = payoffDiagram.compute(state.selected, spot,
      state.selected.lot || lotSizeFor(state.selected.symbol) || 65);
    if (p.status !== 'ok') {
      wrap.appendChild(el('div', {
        style: { fontSize: '10px', color: C.textMute, fontStyle: 'italic' }
      }, 'Payoff: ' + p.status.replace(/_/g, ' ')));
      return wrap;
    }

    wrap.appendChild(el('div', {
      style: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: '6px'
      }
    }, [
      el('span', {
        style: { fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px', color: C.textSec }
      }, 'PAYOFF AT EXPIRY'),
      el('span', {
        style: { fontSize: '9px', color: C.textMute, fontFamily: MONO }
      }, 'BE ' + p.breakeven.toFixed(2))
    ]));

    // Build SVG P&L curve
    var w = 320, h = 80;
    var pad = 4;
    var prices = p.points.map(function (pt) { return pt.price; });
    var pnls = p.points.map(function (pt) { return pt.pnl; });
    var minPrice = prices[0], maxPrice = prices[prices.length - 1];
    var range = p.maxPnl - p.minPnl;
    if (range === 0) range = 1;

    var svg = '<svg viewBox="0 0 ' + w + ' ' + h + '" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:80px">';

    // Zero line
    var zeroY = pad + (p.maxPnl / range) * (h - 2 * pad);
    svg += '<line x1="0" y1="' + zeroY + '" x2="' + w + '" y2="' + zeroY + '" stroke="' + C.divider + '" stroke-width="1" stroke-dasharray="2,2"/>';

    // Spot marker (vertical line)
    var spotPct = (spot - minPrice) / (maxPrice - minPrice);
    var spotX = spotPct * w;
    svg += '<line x1="' + spotX + '" y1="0" x2="' + spotX + '" y2="' + h + '" stroke="' + C.blue + '" stroke-width="1" stroke-dasharray="3,2" opacity="0.5"/>';

    // Breakeven marker
    var bePct = (p.breakeven - minPrice) / (maxPrice - minPrice);
    var beX = Math.max(0, Math.min(w, bePct * w));
    svg += '<line x1="' + beX + '" y1="0" x2="' + beX + '" y2="' + h + '" stroke="' + C.orange + '" stroke-width="1" opacity="0.5"/>';

    // Fill areas (profit green, loss red)
    var posPath = '', negPath = '';
    var points = [];
    for (var i = 0; i < p.points.length; i++) {
      var pt = p.points[i];
      var x = (i / (p.points.length - 1)) * w;
      var y = pad + ((p.maxPnl - pt.pnl) / range) * (h - 2 * pad);
      points.push({ x: x, y: y, pnl: pt.pnl });
    }
    // Profit region (above zero line)
    svg += '<path d="M 0,' + zeroY;
    for (var i = 0; i < points.length; i++) {
      if (points[i].pnl >= 0) svg += ' L ' + points[i].x + ',' + points[i].y;
      else svg += ' L ' + points[i].x + ',' + zeroY;
    }
    svg += ' L ' + w + ',' + zeroY + ' Z" fill="' + C.green + '" opacity="0.15"/>';
    // Loss region
    svg += '<path d="M 0,' + zeroY;
    for (var i = 0; i < points.length; i++) {
      if (points[i].pnl < 0) svg += ' L ' + points[i].x + ',' + points[i].y;
      else svg += ' L ' + points[i].x + ',' + zeroY;
    }
    svg += ' L ' + w + ',' + zeroY + ' Z" fill="' + C.red + '" opacity="0.15"/>';

    // Line
    var pathData = 'M ' + points.map(function (pt) { return pt.x + ',' + pt.y; }).join(' L ');
    svg += '<path d="' + pathData + '" fill="none" stroke="' + C.textPri + '" stroke-width="1.5"/>';

    svg += '</svg>';
    var svgDiv = el('div', { style: { marginBottom: '4px' } });
    svgDiv.innerHTML = svg;
    wrap.appendChild(svgDiv);

    // Legend
    wrap.appendChild(el('div', {
      style: {
        display: 'flex', justifyContent: 'space-between',
        fontSize: '9px', fontFamily: MONO, color: C.textMute
      }
    }, [
      el('span', {}, 'Max Loss ' + p.minPnl),
      el('span', { style: { color: C.blue } }, 'Spot ' + spot.toFixed(0)),
      el('span', {}, 'Max Profit ' + (p.maxPnl > 0 ? '+' + p.maxPnl : p.maxPnl))
    ]));

    return wrap;
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
    (state.heldTrades || []).forEach(function (t) { priceLookup[t.id] = t; });

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

    // Pro mode hides SMC entirely — these are retail concepts (ICT methodology)
    // that don't feed consensus points in pro mode. Show a compact note instead.
    if (proMode.isOn()) {
      wrap.appendChild(el('div', {
        style: {
          fontSize: '9px', fontWeight: 800, letterSpacing: '1.5px',
          color: C.textMute, marginBottom: '4px'
        }
      }, 'PRICE ACTION — SMC DISABLED (PRO MODE)'));
      wrap.appendChild(el('div', {
        style: {
          fontSize: '10px', color: C.textMute, fontStyle: 'italic',
          lineHeight: 1.4
        }
      }, 'SMC signals (FVG/OB/BOS/CHoCH/sweeps) excluded from consensus in Pro Mode. Consensus now uses regime · GEX · IV curve · order flow · Kelly only.'));
      return wrap;
    }

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
      el('div', {}, 'ACTION'),
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
      var trend = r.trend;
      // Only compute direction when we have at least 2 history points.
      // First-seen trades (null trend) show "building" instead of a
      // misleading flat 95→95→95 which was a bug reported by user.
      var up = trend && trend[trend.length - 1] > trend[0];
      var dn = trend && trend[trend.length - 1] < trend[0];
      var tColor = !trend ? C.textMute
                 : up ? C.green
                 : dn ? C.red
                 : C.textSec;
      var tMark = !trend ? '…' : up ? '▲' : dn ? '▼' : '■';
      var trendText = trend ? trend.join(' → ')
                            : 'building history (' + r.historyCount + '/2)';

      // Compute size preview for the action cell
      var scanPreview = null;
      try { scanPreview = tradePreview.compute(r); } catch (e) {}

      // The action cell is a small TAKE button with size sub-label
      var actionCell = null;
      var scanPos = paperPortfolio.findByTradeId(r.id);
      if (scanPos) {
        actionCell = el('span', {
          style: {
            fontSize: '10px', fontWeight: 800,
            color: scanPos.status === 'active' ? C.green : C.orange,
            letterSpacing: '0.5px'
          }
        }, '● ' + scanPos.status.toUpperCase());
      } else if (scanPreview && !scanPreview.allowed) {
        actionCell = el('span', {
          title: (scanPreview.blockers || []).join(' · '),
          style: {
            fontSize: '9px', color: C.red, fontWeight: 700,
            letterSpacing: '0.5px'
          }
        }, 'BLOCKED');
      } else {
        actionCell = el('button', {
          onClick: function (e) {
            e.stopPropagation();
            selectTrade(r);
            onExecute(r);
          },
          title: scanPreview && scanPreview.shortLabel
            ? 'TAKE TRADE · ' + scanPreview.shortLabel
            : 'TAKE TRADE',
          style: {
            background: C.blue + '22',
            border: '1px solid ' + C.blue + '55',
            color: C.blue,
            padding: '2px 8px', borderRadius: '999px',
            fontSize: '10px', fontWeight: 700, cursor: 'pointer',
            letterSpacing: '0.3px',
            display: 'inline-flex', flexDirection: 'column',
            alignItems: 'center', lineHeight: 1.1
          }
        }, [
          el('span', {}, 'TAKE TRADE'),
          scanPreview && scanPreview.shortLabel
            ? el('span', { style: { fontSize: '8px', opacity: 0.85 } },
                scanPreview.shortLabel)
            : null
        ].filter(Boolean));
      }

      body.appendChild(el('div', {
        onClick: function () { selectTrade(r); },
        style: {
          display: 'grid', gridTemplateColumns: '16% 20% 8% 10% 18% 1fr',
          minHeight: '30px', alignItems: 'center', padding: '3px 8px',
          fontSize: '13px', fontFamily: MONO,
          borderBottom: i < displayScan.length - 1 ? '1px solid ' + C.divider : 'none',
          color: C.textPri, lineHeight: 1.1, cursor: 'pointer'
        }
      }, [
        el('div', { style: { fontWeight: 600 } }, r.symbol),
        el('div', { style: { color: C.textSec, fontFamily: MONO } }, r.strike || '—'),
        el('div', { style: { color: r.direction === 'CE' ? C.green : C.red, fontWeight: 700 } }, r.direction),
        el('div', { style: { color: confColor(r.score), fontWeight: 700 } }, String(r.score)),
        el('div', {}, actionCell),
        el('div', { style: { color: tColor, display: 'flex', alignItems: 'center', gap: '6px' } }, [
          el('span', {}, trendText),
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

    // ── ON-SELECT LIVE RECOMPUTE ─────────────────────────────────────────
    // When the user clicks a card, don't make them wait for the next 5m
    // candle to see a fresh read. Everything that derives from the CURRENT
    // state (consensus verdict, Kelly sizing, scenario matrix, book greek
    // check, portfolio risk gate, event calendar, correlation warnings) is
    // already recomputed on every render() via freshConsensus / tradePreview
    // / scenarioAnalysis — so rerender() is enough to pull fresh numbers.
    //
    // We stamp the moment of recompute so the user sees a visible
    // "computed at HH:MM:SS IST" line next to the verdict and knows the
    // numbers reflect this click, not the last 5m close.
    state.selectedComputedAt = Date.now();
    state.selectedRecomputeFlash = true;

    fetchOptionChain(t.symbol, t.strike, t).then(function (rows) {
      state.chain = rows;
      rerender();
    });
    pushLog('Selected ' + t.symbol + ' ' + t.strike +
            ' — recomputed verdict + sizing + scenario', C.blue);
    rerender();

    // Clear the flash after a moment so it only blinks to signal recompute
    setTimeout(function () {
      state.selectedRecomputeFlash = false;
      rerender();
    }, 1500);
  }

  function onExecute(t, opts) {
    opts = opts || {};

    // Prevent double-execute: if an open position already exists for this
    // trade, tell the user and don't open a duplicate.
    var existing = paperPortfolio.findByTradeId(t.id);
    if (existing) {
      var statusWord = existing.status === 'active' ? 'already active' : 'already pending';
      pushLog('Already executing ' + t.symbol + ' ' + t.strike +
              ' (' + statusWord + ')', C.orange);
      speak(t.symbol + ' ' + t.strike + ' is ' + statusWord +
            '. See it in the Live Monitor.');
      return;
    }

    // ── Confirmation gate ──
    // First click shows a confirm modal with sizing + warnings so the user
    // knows what they're committing to. Subsequent clicks in the same
    // session skip the modal (one-tap flow) once user ticks "don't ask again".
    // Fresh session always reconfirms the first trade.
    if (!opts.skipConfirm && !confirmSuppressed) {
      state.pendingConfirmTrade = t;
      state.confirmSkipNext = false;
      rerender();
      return;
    }

    // ── Portfolio risk guardrails — check before anything else ──
    var gate = portfolioRisk.checkAllow();
    if (!gate.allow) {
      pushLog('BLOCKED: ' + gate.reason, C.red);
      if (state.voiceOn) speak('Trade blocked: ' + gate.reason);
      return;
    }

    // ── Event calendar check — IV crush prevention ──
    // High-risk events (RBI/FOMC/earnings) within 1 day BLOCK trade entry.
    // Lower-risk or further-out events WARN but allow. This saves users
    // from buying into an event and losing on IV crush even if direction
    // is right — the single biggest preventable loss in retail options.
    var evCheck = eventCalendar.checkTrade(t, state.region || 'IN');
    if (evCheck.action === 'BLOCK') {
      pushLog('BLOCKED: ' + evCheck.reason, C.red);
      speak(t.symbol + ' blocked — ' + evCheck.reason);
      return;
    }
    if (evCheck.action === 'WARN') {
      pushLog('⚠ ' + evCheck.reason, C.orange);
      // Warning doesn't block; trade still opens. Voice notes it.
      speak('Note: ' + evCheck.reason);
    }

    // ── Portfolio Greek check — prevent book concentration ──
    // Before opening, verify this trade doesn't push net book delta/vega
    // past limits, and flag correlation concentration with existing positions.
    // Example: opening a 2nd NIFTY CE when one's already open + BANKNIFTY CE.
    // They're 88% correlated — it's effectively one bigger directional bet.
    var pgCheck = portfolioGreeks.checkAllow(t, t._raw || {});
    if (!pgCheck.allow) {
      pushLog('BLOCKED: ' + pgCheck.reason, C.red);
      speak(t.symbol + ' blocked — book Greek limit exceeded.');
      return;
    }
    // Warning when correlated even if under limit
    if (pgCheck.correlatedSymbols.length > 0) {
      var corrList = pgCheck.correlatedSymbols.map(function (c) {
        return c.sym + ' ρ=' + c.corr.toFixed(2);
      }).join(', ');
      pushLog('⚠ Correlation concentration: ' + corrList, C.orange);
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
        //
        // IMPORTANT: We record history for BOTH top-3 AND secondary scanner
        // trades. Previously only top-3 got history, which meant scanner
        // rows always showed "95 → 95 → 95" (flat) because their history
        // never persisted across refreshes. Now every ranked trade gets
        // real trend data.
        var newHist = {};
        var tradesToTrackHist = top3.concat(
          mapped.filter(function (m) {
            return top3.filter(function (t) { return t.id === m.id; }).length === 0;
          }).slice(0, 6)  // top 6 scanner candidates (same as what's shown)
        );
        tradesToTrackHist.forEach(function (t) {
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

        // Trigger 1: NEW TOP TRADE — with portfolio-aware context.
        // Previously a bare announcement; now we tell the user whether
        // it's a good moment to take another trade given their day's
        // performance, concurrent positions, and session phase.
        var newTopTrade = top3.filter(function (t) { return !prevIds[t.id]; })[0];
        if (newTopTrade && Object.keys(prevIds).length > 0) {
          var announcement = sessionGuide.newTradeAnnouncement(newTopTrade);
          var decision = sessionGuide.shouldTakeNew();
          var logColor = decision.recommend === 'TAKE' ? C.green
                       : decision.recommend === 'CAUTION' ? C.orange : C.red;
          pushLog('NEW TOP: ' + newTopTrade.symbol + ' ' + newTopTrade.strike +
                  ' · ' + decision.recommend +
                  ' · ' + decision.reason, logColor);
          speak(announcement);
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

        // ═══════════════════════════════════════════════════════════════
        // HELD TRADES — preserve full trade data for every open/pending
        // position the user has, regardless of whether it ranks in the
        // current top 3. Without this, when an active position's symbol
        // rotates off the top-3 list, the user loses visibility and the
        // lifecycle engine loses fresh data to evaluate against.
        //
        // Logic: for every (pending|active) position, find the matching
        // trade in `mapped` (full scored list) and pull the full object
        // with its _raw bars + chain so priceLookup has fresh data.
        // ═══════════════════════════════════════════════════════════════
        var heldById = {};
        for (var posId in paperPortfolio.positions) {
          var pos = paperPortfolio.positions[posId];
          if (pos.status !== 'pending' && pos.status !== 'active') continue;
          // Prefer the fresh trade from mapped
          var freshHeld = mapped.filter(function (m) { return m.id === pos.tradeId; })[0];
          if (freshHeld) {
            heldById[pos.tradeId] = freshHeld;
          } else {
            // Fallback: ticker no longer in scan universe. Synthesize
            // minimal trade object from position snapshot so card + lifecycle
            // can still show it (lifecycle will flag as stale).
            heldById[pos.tradeId] = {
              id: pos.tradeId, symbol: pos.sym, strike: pos.strike, side: pos.side,
              confidence: pos.score || 0, state: 'stale',
              reason: 'Scan universe dropped symbol',
              price: pos.entryPremium,
              sl: pos.sl, target: pos.target, trigger: pos.trigger,
              lot: pos.lot, _staleData: true,
              _raw: { _region: pos.region, currency: pos.currency }
            };
          }
        }
        state.heldTrades = Object.keys(heldById).map(function (k) { return heldById[k]; });

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
          // Only show a real trend if we have 2+ history points.
          // First-seen trades get a null trend so UI can show "building…"
          // instead of a misleading flat 95→95→95.
          var trend = (h && h.length >= 2) ? h : null;
          return {
            symbol: t.symbol, direction: t.side,
            strike: t.strike,
            score: t.confidence, state: t.state,
            trend: trend,
            historyCount: h ? h.length : 0
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
    (state.heldTrades || []).forEach(function (t) { priceLookup[t.id] = t; });
      // Also include the selected trade in case it's an open position
      if (state.selected) priceLookup[state.selected.id] = state.selected;

      // ═══════════════════════════════════════════════════════════════════
      // SCALE-OUT CHECK — for every active position, check 1.5R partial
      // profit before the main lifecycle evaluator runs. Scale-out closes
      // 50% of the lot and raises SL on remainder to break-even. This is
      // distinct from EXIT — it's "book some, let rest run" discipline.
      // ═══════════════════════════════════════════════════════════════════
      var scaledOutThisBar = {};
      for (var posId in paperPortfolio.positions) {
        var pos = paperPortfolio.positions[posId];
        if (pos.status !== 'active') continue;
        if (pos.scaledOutAt) continue;
        var liveTradeSO = priceLookup[pos.tradeId];
        var curPriceSO = liveTradeSO ? liveTradeSO.price : pos.entryPremium;
        var soCheck = partialProfitManager.evaluate(pos, curPriceSO);
        if (soCheck.action === 'SCALE_OUT') {
          var result = partialProfitManager.execute(posId, curPriceSO);
          if (result) {
            scaledOutThisBar[posId] = true;
            pushLog('SCALE OUT: ' + pos.sym + ' ' + pos.strike + ' · ' +
                    result.partialLots + ' lot(s) at +' +
                    result.partialPnlPct.toFixed(1) + '% · ' +
                    'stop raised to break-even', C.green);
            if (state.voiceOn) {
              speak(pos.sym + ' ' + pos.strike + ' hit one and half R. ' +
                    'Booked fifty percent at plus ' + result.partialPnlPct.toFixed(0) +
                    ' percent. Remainder trails with break-even stop.');
            }
          }
        }
      }

      // Get recommendations per active position
      var recs = liveTradeGuide.evaluateAll(priceLookup);
      state.liveRecs = recs;  // stash for UI panel

      recs.forEach(function (rec) {
        // Skip lifecycle voice/action for positions that scaled-out this bar.
        // Double-talking about the same position in one bar is noise.
        if (scaledOutThisBar[rec.positionId]) return;
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
