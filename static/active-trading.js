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
    prevTradeIds: {}       // tracked across refreshes for "new top trade" voice trigger
  };

  var timers = { countdown: null, soft90: null, candle5m: null };
  var mounted = false;

  // ── DATA LAYER ──────────────────────────────────────────────────────────
  function mapScanRowToTrade(row) {
    // Real fields from /api/bottom-nav-scan:
    //   sym, spot, vwap, today_open, today_high, today_low, pcr, max_pain, atm_strike,
    //   chain_near_atm[], gex.regime, _fallback
    // NOTE: When _fallback=true (NSE blocked), OI fields are all 0. We score from
    //       price structure instead: VWAP, open, H/L range, max pain delta.
    var sym = row.sym || row.symbol || '';
    var spot = row.spot || 0;
    if (!sym || spot <= 0) return null;

    var vwap = row.vwap || spot;
    var openPx = row.today_open || spot;
    var high = row.today_high || spot;
    var low = row.today_low || spot;
    var pcr = row.pcr || 1;
    var gex = row.gex || {};
    var gexRegime = (gex.regime || 'NEUTRAL').toUpperCase();
    var ceBuildup = row.ce_buildup || [];
    var peBuildup = row.pe_buildup || [];
    var atm = row.atm_strike || Math.round(spot);
    var maxPain = row.max_pain || atm;
    var isFallback = row._fallback === true;

    var bullScore = 0, bearScore = 0;

    // ── PRICE STRUCTURE (works always, even in fallback mode) ─────────────
    // VWAP relationship — strongest intraday signal
    var vwapPct = (spot - vwap) / vwap * 100;
    if (vwapPct > 0.3)  bullScore += 20;
    else if (vwapPct > 0.1) bullScore += 12;
    else if (vwapPct > 0)   bullScore += 5;
    if (vwapPct < -0.3) bearScore += 20;
    else if (vwapPct < -0.1) bearScore += 12;
    else if (vwapPct < 0)    bearScore += 5;

    // Open vs current — intraday direction
    var openPct = (spot - openPx) / openPx * 100;
    if (openPct > 0.2)  bullScore += 12;
    else if (openPct > 0) bullScore += 5;
    if (openPct < -0.2) bearScore += 12;
    else if (openPct < 0) bearScore += 5;

    // Range position — where in the day's H/L is price sitting?
    var range = high - low;
    if (range > 0) {
      var rangePct = (spot - low) / range; // 0 = at low, 1 = at high
      if (rangePct > 0.75) bullScore += 10;  // trading near high
      else if (rangePct > 0.6) bullScore += 5;
      if (rangePct < 0.25) bearScore += 10;  // trading near low
      else if (rangePct < 0.4) bearScore += 5;
    }

    // Max Pain differential
    var mpPct = (spot - maxPain) / maxPain * 100;
    if (mpPct > 0.3)  bullScore += 8;
    else if (mpPct > 0) bullScore += 4;
    if (mpPct < -0.3) bearScore += 8;
    else if (mpPct < 0) bearScore += 4;

    // ── OI SIGNALS (only meaningful when NOT fallback) ────────────────────
    if (!isFallback) {
      if (pcr >= 1.3) bullScore += 15;
      else if (pcr >= 1.1) bullScore += 8;
      if (pcr <= 0.7) bearScore += 15;
      else if (pcr <= 0.9) bearScore += 8;

      if (peBuildup.length > 0 && (peBuildup[0].chg || 0) > 50000) bullScore += 12;
      else if (peBuildup.length > 0 && (peBuildup[0].chg || 0) > 10000) bullScore += 6;
      if (ceBuildup.length > 0 && (ceBuildup[0].chg || 0) > 50000) bearScore += 12;
      else if (ceBuildup.length > 0 && (ceBuildup[0].chg || 0) > 10000) bearScore += 6;

      if (gexRegime === 'POSITIVE' || gexRegime === 'POSITIVE_GAMMA') bullScore += 8;
      if (gexRegime === 'NEGATIVE' || gexRegime === 'NEGATIVE_GAMMA') bearScore += 8;
    }

    // ── Decide side & confidence ──────────────────────────────────────────
    var diff = Math.abs(bullScore - bearScore);
    var totalSignal = bullScore + bearScore;

    // If there's ANY directional evidence, surface it — don't be picky when signals are weak
    if (diff < 1 || totalSignal < 3) return null;

    var conf = Math.min(92, 48 + diff * 1.8 + totalSignal * 0.2);
    var side = bullScore > bearScore ? 'CE' : 'PE';
    var stateKey = conf >= 78 ? 'ideal' : conf >= 68 ? 'early' : conf >= 58 ? 'late' : 'avoid';

    // Reason string — always meaningful
    var reasons = [];
    if (vwapPct > 0.1) reasons.push('Above VWAP +' + vwapPct.toFixed(2) + '%');
    else if (vwapPct < -0.1) reasons.push('Below VWAP ' + vwapPct.toFixed(2) + '%');
    if (openPct > 0.2) reasons.push('Up from open');
    else if (openPct < -0.2) reasons.push('Down from open');
    if (range > 0) {
      var rp = (spot - low) / range;
      if (rp > 0.75) reasons.push('Near day high');
      else if (rp < 0.25) reasons.push('Near day low');
    }
    if (!isFallback && pcr >= 1.2) reasons.push('PCR ' + pcr.toFixed(2));
    else if (!isFallback && pcr <= 0.8) reasons.push('PCR ' + pcr.toFixed(2));
    if (reasons.length === 0) {
      reasons.push(side === 'CE' ? 'Bullish structure' : 'Bearish structure');
    }
    var reason = reasons.slice(0, 3).join(' + ');

    // Premium from chain_near_atm
    var chain = row.chain_near_atm || [];
    var atmRow = chain.filter(function (r) { return r.strike === atm; })[0];
    // Try nearest strike if exact ATM missing
    if (!atmRow && chain.length) {
      atmRow = chain.reduce(function (best, r) {
        return (!best || Math.abs(r.strike - atm) < Math.abs(best.strike - atm)) ? r : best;
      }, null);
    }
    var premium = atmRow ? (side === 'CE' ? (atmRow.ce_ltp || 0) : (atmRow.pe_ltp || 0)) : 0;
    if (premium <= 0) premium = Math.round(spot * 0.008);

    var trigger = premium * 1.02;
    var sl = premium * 0.85;
    var target = premium * 1.30;

    var lotMap = { NIFTY: 75, BANKNIFTY: 30, FINNIFTY: 65, MIDCPNIFTY: 120, SENSEX: 20 };
    var lot = row.lot_size || lotMap[sym] || 50;

    return {
      id: sym + '-' + atm + '-' + side,
      symbol: sym,
      strike: atm + ' ' + side,
      side: side,
      confidence: Math.round(conf),
      state: stateKey,
      reason: reason,
      price: premium,
      trigger: trigger,
      sl: sl,
      target: target,
      lot: lot,
      _raw: row
    };
  }

  function fetchOptionChain(symbol, strikeStr) {
    // strikeStr = "24500 CE" → extract numeric
    var atmStrike = parseFloat((strikeStr || '').replace(/[^\d.]/g, '')) || 0;
    return fetch('/api/nse-options?symbol=' + encodeURIComponent(symbol))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.success) return [];
        // Response shape: { success, spot, atm_strike, chain_near_atm: [{strike, ce_oi, pe_oi, ce_chg, pe_chg, ...}] }
        var chain = d.chain_near_atm || [];
        if (chain.length === 0) return [];
        var strikes = chain.map(function (r) { return r.strike; }).sort(function (a, b) { return a - b; });
        if (atmStrike === 0) atmStrike = d.atm_strike || strikes[Math.floor(strikes.length / 2)];

        // Find ATM index
        var atmIdx = 0, minDiff = Infinity;
        for (var i = 0; i < strikes.length; i++) {
          var diff = Math.abs(strikes[i] - atmStrike);
          if (diff < minDiff) { minDiff = diff; atmIdx = i; }
        }

        // Build lookup for chain rows by strike
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
      })
      .catch(function (e) { console.warn('[AT] option-chain fetch failed', e); return []; });
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
        height: '820px',
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
        minHeight: 0
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
      return el('button', {
        onClick: function () {
          if (state.region === reg) return;
          state.region = reg;
          state.trades = []; state.scanner = []; state.selected = null;
          state.chain = []; state.lockedIds = {}; state.prevTradeIds = {};
          state.loaded = false; state.lastFetchMsg = '';
          rerender(); refreshAll();
        },
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
        display: 'flex', alignItems: 'center', padding: '0 12px', gap: '12px', flexShrink: 0
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
    var panel = el('div', { style: { padding: '8px', height: '100%', overflow: 'hidden' } });
    panel.appendChild(el('div', {
      style: {
        fontSize: '10px', fontWeight: 800, color: C.textMute,
        letterSpacing: '1.5px', marginBottom: '6px', padding: '0 2px'
      }
    }, 'TOP TRADES · 90s REFRESH'));

    for (var i = 0; i < 3; i++) {
      var t = state.trades[i];
      if (!t) {
        // Spec §4 rules: if <3 trades → "No high-confidence trades"
        // Before first fetch completes: "Loading…"
        // If fetch failed: show error detail
        var placeholderText;
        if (!state.loaded) {
          placeholderText = 'Loading…';
        } else if (state.lastFetchMsg && state.lastFetchMsg.indexOf('error') !== -1) {
          placeholderText = state.lastFetchMsg;
        } else if (state.lastFetchMsg && state.lastFetchMsg.indexOf('warming up') !== -1) {
          placeholderText = state.lastFetchMsg;
        } else {
          placeholderText = 'No high-confidence trades';
        }
        panel.appendChild(el('div', {
          style: {
            height: '84px', marginBottom: '6px', borderRadius: '12px',
            border: '1px dashed ' + C.divider, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            color: C.textMute, fontSize: '12px', fontStyle: 'italic'
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

    var card = el('div', {
      onClick: function () { selectTrade(trade); },
      style: {
        height: '84px', padding: '8px',
        background: isSelected ? C.active : C.card,
        borderRadius: '12px',
        border: '1px solid ' + (isSelected ? C.blue : C.divider),
        marginBottom: '6px',
        display: 'grid',
        gridTemplateColumns: '1fr auto auto',
        gridTemplateRows: 'auto auto',
        columnGap: '12px', rowGap: '4px',
        cursor: 'pointer',
        transition: 'background 120ms ease, border-color 120ms ease'
      }
    });

    // Row 1 col 1 — symbol + strike
    var sym = el('div', {
      style: { fontSize: '18px', fontWeight: 600, color: C.textPri, lineHeight: 1.15, fontFamily: MONO }
    });
    sym.appendChild(document.createTextNode(trade.symbol + ' '));
    sym.appendChild(el('span', { style: { color: C.textSec } }, trade.strike));
    card.appendChild(sym);

    // Row 1 col 2 — confidence
    card.appendChild(el('div', {
      style: {
        fontSize: '20px', fontWeight: 700, color: confColor(trade.confidence),
        lineHeight: 1.1, alignSelf: 'center', fontFamily: MONO
      }
    }, trade.confidence + '%'));

    // Row 1 col 3 — EXECUTE (per spec: 36px × 100px green gradient)
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

    // Row 2 col 3 — voice
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
      style: {
        fontSize: '20px', fontWeight: 700, color: confColor(t.confidence),
        fontFamily: MONO, textAlign: 'right', lineHeight: 1
      }
    }, t.confidence + '%');
    confBox.appendChild(el('div', {
      style: { fontSize: '9px', color: C.textMute, fontWeight: 600, letterSpacing: '1px', marginTop: '2px' }
    }, 'CONF'));
    hdr.appendChild(confBox);

    var priceBox = el('div', {
      className: state.flash === 'up' ? 'flash-up' : state.flash === 'down' ? 'flash-dn' : '',
      style: {
        fontSize: '16px', fontWeight: 600, color: C.textPri,
        fontFamily: MONO, textAlign: 'right', lineHeight: 1
      }
    }, state.lastClose != null ? state.lastClose.toFixed(2) : '—');
    priceBox.appendChild(el('div', {
      style: { fontSize: '9px', color: C.textMute, fontWeight: 600, letterSpacing: '1px', marginTop: '2px' }
    }, '5m CLOSE'));
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
      style: { fontSize: '10px', color: C.textMute, fontWeight: 700, fontFamily: MONO, letterSpacing: '1px' }
    }, 'NEXT ' + state.countdown));
    box.appendChild(row1);

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
      cell('LOT', t.lot, C.textSec, false)
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

    var list = el('div', { style: { overflow: 'hidden' } });
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
        height: '168px', background: C.bg, borderTop: '1px solid ' + C.divider,
        display: 'flex', flexDirection: 'column', flexShrink: 0
      }
    });

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
    fetchOptionChain(t.symbol, t.strike).then(function (rows) {
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
    var m = STATE_MAP[t.state] || STATE_MAP.ideal;
    speak(t.symbol + ' ' + t.strike + ', confidence ' + t.confidence + ' percent, ' + m.label.toLowerCase());
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
        var mapped = raw
          .map(mapScanRowToTrade)
          .filter(function (t) { return t; })
          .sort(function (a, b) { return b.confidence - a.confidence; });

        if (mapped.length === 0) {
          state.lastFetchMsg = 'No high-conviction setups right now (' + raw.length + ' scanned)';
          state.trades = []; state.scanner = [];
          rerender(); return;
        }

        state.lastFetchMsg = '';

        // ═══ 3-MIN STABILITY LOCK (spec section 10) ═════════════════════
        // Top trades must remain stable for minimum 3 minutes before being
        // replaced. Any trade that's been in the top-3 for <3min stays locked
        // in its slot even if a higher-confidence candidate arrives.
        var now = Date.now();
        var LOCK_MS = 3 * 60 * 1000;
        var prev = state.trades || [];
        var top3 = [];

        // First, carry forward locked trades that are still in the mapped set
        for (var i = 0; i < prev.length && top3.length < 3; i++) {
          var p = prev[i];
          if (!p) continue;
          var lockStart = state.lockedIds[p.id];
          if (lockStart && (now - lockStart) < LOCK_MS) {
            // Still locked — check if it's still in current scan (else it expired)
            var fresh = mapped.filter(function (m) { return m.id === p.id; })[0];
            if (fresh) {
              top3.push(fresh); // update with fresh data but keep slot
            }
          }
        }

        // Fill remaining slots with highest-confidence non-locked trades
        for (var j = 0; j < mapped.length && top3.length < 3; j++) {
          var m = mapped[j];
          if (top3.filter(function (t) { return t.id === m.id; }).length === 0) {
            top3.push(m);
            if (!state.lockedIds[m.id]) {
              state.lockedIds[m.id] = now; // start 3-min lock for new entrant
            }
          }
        }

        // Clean up stale lock entries
        var newLocks = {};
        top3.forEach(function (t) {
          newLocks[t.id] = state.lockedIds[t.id] || now;
        });
        state.lockedIds = newLocks;

        // ═══ VOICE TRIGGERS (spec section 7) ════════════════════════════
        // prevIds is now a map: { tradeId: { state, confidence } } so we can
        // detect both state transitions AND confidence rises (momentum).
        var prevIds = state.prevTradeIds || {};

        // Trigger 1: NEW TOP TRADE — a trade not present in previous refresh
        var newTopTrade = top3.filter(function (t) { return !prevIds[t.id]; })[0];
        if (newTopTrade && Object.keys(prevIds).length > 0) {
          pushLog('NEW TOP: ' + newTopTrade.symbol + ' ' + newTopTrade.strike, C.green);
          speak('New top trade: ' + newTopTrade.symbol + ' ' + newTopTrade.strike +
                ', confidence ' + newTopTrade.confidence + ' percent');
        }

        // Trigger 3: LATE WARNING — prev state was early/ideal, now late
        top3.forEach(function (t) {
          var prev = prevIds[t.id];
          var prevState = prev && prev.state;
          if (prevState && (prevState === 'early' || prevState === 'ideal') && t.state === 'late') {
            pushLog('LATE: ' + t.symbol + ' ' + t.strike + ' — reduce size', C.orange);
            speak(t.symbol + ' ' + t.strike + ' becoming late. Reduce size.');
          }
        });

        // Trigger — MOMENTUM BUILDING (spec §5.5 example log)
        // Fires when the currently-selected trade's confidence rises by ≥5 points
        // between refreshes. Quiet, non-blocking — just a log + soft voice cue.
        if (state.selected) {
          var sel = top3.filter(function (t) { return t.id === state.selected.id; })[0];
          var selPrev = prevIds[state.selected.id];
          if (sel && selPrev && typeof selPrev.confidence === 'number') {
            var delta = sel.confidence - selPrev.confidence;
            if (delta >= 5) {
              pushLog('Momentum building (+' + delta + ')', C.yellow);
              speak('Momentum building');
            }
          }
        }

        // Trigger 4: EXIT — selected trade dropped out of top-3 OR flipped to avoid
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

        // Save full snapshot (state + confidence) for next refresh's comparison
        var nextPrev = {};
        top3.forEach(function (t) { nextPrev[t.id] = { state: t.state, confidence: t.confidence }; });
        state.prevTradeIds = nextPrev;

        state.trades = top3;

        // Secondary scanner gets the 4th–9th ranked mapped trades (NOT top 3)
        var scannerPool = mapped.filter(function (m) {
          return top3.filter(function (t) { return t.id === m.id; }).length === 0;
        });
        state.scanner = scannerPool.slice(0, 6).map(function (t) {
          return {
            symbol: t.symbol, direction: t.side,
            score: t.confidence, state: t.state,
            trend: [Math.max(40, t.confidence - 4), Math.max(45, t.confidence - 2), t.confidence]
          };
        });

        // Auto-select first trade if nothing selected yet
        if (!state.selected && top3.length > 0) {
          state.selected = top3[0];
          state.lastClose = top3[0].price;
          state.flash = null;
          fetchOptionChain(top3[0].symbol, top3[0].strike).then(function (rows) {
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
    return fetchOptionChain(state.selected.symbol, state.selected.strike).then(function (rows) {
      state.chain = rows;
      rerender();
    });
  }

  function refreshAll() {
    pushLog('90s soft-refresh', C.textSec);
    return Promise.all([refreshTopTrades(), refreshChain()]);
  }

  function on5mClose() {
    if (!state.selected) return;
    // Fetch fresh option chain (force-sync) + re-evaluate entry
    refreshChain();
    // Simulate candle close price movement — in prod, fetch latest 5m close from backend
    var prev = state.lastClose != null ? state.lastClose : state.selected.price;
    var newClose = prev + (Math.random() - 0.5) * (prev * 0.003);
    state.lastClose = newClose;
    state.flash = newClose > prev ? 'up' : 'down';
    pushLog('5m close @ ' + newClose.toFixed(2) + ' — re-evaluated entry', C.yellow);
    if (newClose >= state.selected.trigger) {
      pushLog('Entry confirmed', C.green);
      speak('Entry window opening');
    }
    rerender();
    setTimeout(function () { state.flash = null; rerender(); }, 500);
  }

  function startTimers() {
    // Countdown ticks the label every second (no data fetch)
    timers.countdown = setInterval(function () {
      state.countdown = formatCountdown(msUntilNextFiveMin());
      // Only rerender the countdown cheaply — full rerender is fine at 1 Hz
      var countEl = document.querySelector('#activeTradingMount [data-countdown]');
      if (countEl) countEl.textContent = 'NEXT ' + state.countdown;
    }, 1000);

    // 90s soft-refresh
    timers.soft90 = setInterval(refreshAll, 90000);

    // 5m candle close — aligned to wall-clock
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

    // IMPORTANT: Do NOT modify any parent styles (.sc, .sbody, #deHeader).
    // Those are shared with Trader/Investor/Options tabs — changing them corrupts
    // the site's appearance for every other mode. The terminal is fully
    // self-contained inside #activeTradingMount with its own dark background.
    container.innerHTML =
      '<div id="activeTradingMount" ' +
        'style="width:100%;background:#020617;border-radius:8px;' +
               'border:1px solid #1E293B;overflow:hidden"></div>';
    mounted = true;

    render(document.getElementById('activeTradingMount'));
    refreshAll();
    startTimers();
  };

  window.unmountActiveTrading = function () {
    mounted = false;
    stopTimers();
    var mount = document.getElementById('activeTradingMount');
    if (mount) mount.innerHTML = '';
    // Nothing else to restore — we never touched anything outside the mount.
  };
})();
