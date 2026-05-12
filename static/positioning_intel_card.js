// ═══════════════════════════════════════════════════════════════════════════
// r63.72.29 — Positioning Intelligence (replaces Mood Gauges)
//   Card A: Market Regime
//   Card B: Sector Flow
//   Card C: Stock 4D Positioning + Synthesis (good company/stock/trade/entry?)
// ═══════════════════════════════════════════════════════════════════════════

window._loadPositioningIntel = function(symbol, sector, region) {
  symbol = (symbol || window._ddLastSymbol || '').toUpperCase();
  sector = sector || window._ddLastSector || '';
  region = region || window._deRegion || 'US';
  if (!symbol) return;

  ['ddMarketRegimeCard', 'ddSectorFlowCard', 'ddStock4DCard'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.innerHTML = '<div style="padding:20px;text-align:center;font-size:11px;color:#94a3b8;font-family:Inter,sans-serif">Calculating…</div>';
  });

  var url = '/api/dd-positioning-intelligence?symbol=' + encodeURIComponent(symbol) +
            '&sector=' + encodeURIComponent(sector) +
            '&region=' + encodeURIComponent(region);
  fetch(url)
    .then(function(r){ return r.json(); })
    .then(function(d){ window._renderPositioningIntel(d); })
    .catch(function(e){
      ['ddMarketRegimeCard', 'ddSectorFlowCard', 'ddStock4DCard'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.innerHTML = '<div style="padding:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;font-family:Inter,sans-serif;font-size:11px;color:#7f1d1d">⚠ Positioning Intelligence unavailable: ' + (e.message || 'network') + '</div>';
      });
    });
};

window._renderPositioningIntel = function(d) {
  if (!d || !d.success) {
    var msg = (d && d.error) || 'Unknown error';
    ['ddMarketRegimeCard', 'ddSectorFlowCard', 'ddStock4DCard'].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.innerHTML = '<div style="padding:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;font-family:Inter,sans-serif;font-size:11px;color:#7f1d1d">⚠ ' + msg + '</div>';
    });
    return;
  }

  _renderMarketRegimeCard(d);
  _renderSectorFlowCard(d);
  _renderStock4DCard(d);
};

// ─── CARD A: MARKET REGIME ──────────────────────────────────────────────

function _renderMarketRegimeCard(d) {
  var el = document.getElementById('ddMarketRegimeCard');
  if (!el) return;

  var mr = d.market_regime || {};
  if (!mr.success) {
    el.innerHTML = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin-bottom:14px;font-family:Inter,sans-serif"><div style="font-size:12px;color:#94a3b8">🌐 Market Regime — ' + (mr.layman || 'data unavailable') + '</div></div>';
    return;
  }

  var comps = mr.components || {};
  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px 18px;margin-bottom:14px;font-family:Inter,sans-serif">';

  // Header
  h += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">';
  h += '<span style="font-size:18px">🌐</span>';
  h += '<span style="font-size:13px;font-weight:800;color:#1A3A78;letter-spacing:0.3px;font-family:Sora,sans-serif">LAYER 1 · Market Regime</span>';
  h += '<span style="margin-left:auto;font-size:10px;color:#64748b;font-family:IBM Plex Mono,monospace">' + (mr.index_symbol || '') + '</span>';
  h += '</div>';

  // Verdict
  if (mr.verdict) {
    h += '<div style="font-size:13px;font-weight:700;color:#0f172a;margin-bottom:10px">' + mr.verdict + '</div>';
  }

  // 3 mini-meters horizontal
  h += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px">';
  ['liquidity', 'volatility_regime', 'breadth'].forEach(function(k) {
    var c = comps[k];
    if (!c) {
      h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 10px;text-align:center"><div style="font-size:10px;color:#94a3b8">No data</div></div>';
      return;
    }
    h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 10px">';
    h += '<div style="font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.4px;margin-bottom:4px;font-family:Sora,sans-serif">' + (c.label || k).toUpperCase() + '</div>';
    h += '<div style="display:flex;align-items:baseline;gap:6px">';
    h += '<span style="font-size:20px;font-weight:900;color:' + c.band.color + ';font-family:IBM Plex Mono,monospace">' + Math.round(c.score) + '</span>';
    h += '<span style="font-size:9px;font-weight:700;color:' + c.band.color + ';letter-spacing:0.3px">' + c.band.label + '</span>';
    h += '</div>';
    h += '<div style="height:4px;background:#e2e8f0;border-radius:2px;overflow:hidden;margin-top:4px"><div style="height:100%;background:' + c.band.color + ';width:' + Math.max(2, Math.min(100, c.score)) + '%"></div></div>';
    h += '<div style="font-size:9px;color:#94a3b8;margin-top:4px">' + (c.detail || '') + '</div>';
    h += '</div>';
  });
  h += '</div>';

  // Layman
  if (mr.layman) {
    h += '<div style="background:#f8fafc;border-left:3px solid #1A3A78;padding:8px 12px;border-radius:0 4px 4px 0;font-size:11px;color:#475569;line-height:1.5">' + mr.layman + '</div>';
  }

  h += '</div>';
  el.innerHTML = h;
}

// ─── CARD B: SECTOR FLOW ────────────────────────────────────────────────

function _renderSectorFlowCard(d) {
  var el = document.getElementById('ddSectorFlowCard');
  if (!el) return;

  var sf = d.sector_flow || {};
  if (!sf.success) {
    el.innerHTML = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin-bottom:14px;font-family:Inter,sans-serif"><div style="font-size:12px;color:#94a3b8">🏭 Sector Flow — ' + (sf.reason || sf.layman || 'unavailable') + '</div></div>';
    return;
  }

  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px 18px;margin-bottom:14px;font-family:Inter,sans-serif">';

  // Header
  h += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">';
  h += '<span style="font-size:18px">🏭</span>';
  h += '<span style="font-size:13px;font-weight:800;color:#1A3A78;letter-spacing:0.3px;font-family:Sora,sans-serif">LAYER 2 · Sector Flow</span>';
  h += '<span style="margin-left:auto;font-size:10px;color:#64748b;font-family:IBM Plex Mono,monospace">' + (sf.etf_symbol || '') + ' · ' + (sf.etf_label || '') + '</span>';
  h += '</div>';

  h += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px">';

  // Flow Strength
  var fb = sf.flow_band || {};
  h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px">';
  h += '<div style="font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.4px;margin-bottom:4px;font-family:Sora,sans-serif">FLOW STRENGTH</div>';
  h += '<div style="font-size:24px;font-weight:900;color:' + (fb.color || '#94a3b8') + ';font-family:IBM Plex Mono,monospace;line-height:1">' + Math.round(sf.flow_score || 0) + '</div>';
  h += '<div style="font-size:10px;color:' + (fb.color || '#94a3b8') + ';margin-top:3px;font-weight:700">' + (fb.label || '—') + '</div>';
  h += '<div style="font-size:9px;color:#94a3b8;margin-top:3px">20d ret ' + (sf.ret_20d_pct >= 0 ? '+' : '') + (sf.ret_20d_pct || 0).toFixed(1) + '%</div>';
  h += '</div>';

  // Leadership rank
  h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px">';
  h += '<div style="font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.4px;margin-bottom:4px;font-family:Sora,sans-serif">LEADERSHIP RANK</div>';
  if (sf.leadership_rank !== null && sf.leadership_rank !== undefined) {
    var rankColor = sf.leadership_rank <= 3 ? '#059669' : (sf.leadership_rank <= 6 ? '#10b981' : (sf.leadership_rank <= 9 ? '#94a3b8' : '#dc2626'));
    h += '<div style="font-size:24px;font-weight:900;color:' + rankColor + ';font-family:IBM Plex Mono,monospace;line-height:1">#' + sf.leadership_rank + '</div>';
    h += '<div style="font-size:10px;color:' + rankColor + ';margin-top:3px;font-weight:700">of ' + sf.leadership_universe_size + ' sectors</div>';
    h += '<div style="font-size:9px;color:#94a3b8;margin-top:3px">by 20-day return</div>';
  } else {
    h += '<div style="font-size:12px;color:#94a3b8;padding:6px 0">N/A</div>';
  }
  h += '</div>';

  // Institutional rotation
  h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px">';
  h += '<div style="font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.4px;margin-bottom:4px;font-family:Sora,sans-serif">INST. ROTATION</div>';
  if (sf.rotation_vs_bench_pp !== null && sf.rotation_vs_bench_pp !== undefined) {
    var rotColor = sf.rotation_vs_bench_pp > 1 ? '#059669' : (sf.rotation_vs_bench_pp > -1 ? '#94a3b8' : '#dc2626');
    var rotIcon = sf.rotation_vs_bench_pp > 1 ? '↗' : (sf.rotation_vs_bench_pp > -1 ? '→' : '↘');
    h += '<div style="font-size:22px;font-weight:900;color:' + rotColor + ';font-family:IBM Plex Mono,monospace;line-height:1">' + rotIcon + ' ' + (sf.rotation_vs_bench_pp >= 0 ? '+' : '') + sf.rotation_vs_bench_pp.toFixed(1) + 'pp</div>';
    h += '<div style="font-size:10px;color:' + rotColor + ';margin-top:3px;font-weight:700">' + (sf.rotation_vs_bench_pp > 1 ? 'INFLOWS' : sf.rotation_vs_bench_pp > -1 ? 'NEUTRAL' : 'OUTFLOWS') + '</div>';
    h += '<div style="font-size:9px;color:#94a3b8;margin-top:3px">vs benchmark, 20d</div>';
  } else {
    h += '<div style="font-size:12px;color:#94a3b8;padding:6px 0">N/A</div>';
  }
  h += '</div>';

  h += '</div>';

  if (sf.layman) {
    h += '<div style="background:#f8fafc;border-left:3px solid #1A3A78;padding:8px 12px;border-radius:0 4px 4px 0;font-size:11px;color:#475569;line-height:1.5">' + sf.layman + '</div>';
  }

  h += '</div>';
  el.innerHTML = h;
}

// ─── CARD C: STOCK 4D POSITIONING + SYNTHESIS ───────────────────────────

function _renderStock4DCard(d) {
  var el = document.getElementById('ddStock4DCard');
  if (!el) return;

  var s4 = d.stock_4d || {};
  var synth = d.synthesis || {};

  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin-bottom:16px;font-family:Inter,sans-serif">';

  // Header
  h += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap">';
  h += '<span style="font-size:18px">📌</span>';
  h += '<span style="font-size:13px;font-weight:800;color:#1A3A78;letter-spacing:0.3px;font-family:Sora,sans-serif">LAYER 3 · Stock 4D Positioning</span>';
  h += '<span style="margin-left:auto;font-size:10px;color:#64748b;font-family:IBM Plex Mono,monospace">' + (d.ticker || '') + '</span>';
  if (d.confidence) {
    var cc = d.confidence === 'high' ? '#10b981' : (d.confidence === 'medium' ? '#f59e0b' : '#dc2626');
    h += '<span style="font-size:9px;color:' + cc + ';font-weight:700;letter-spacing:0.4px">● ' + d.confidence.toUpperCase() + '</span>';
  }
  h += '</div>';

  // 4-dimensional grid
  h += '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:14px">';
  h += _render4DGauge('🌊', 'FLOW STRENGTH', 'Are buyers chasing this right now?', s4.flow, false);
  h += _render4DGauge('💰', 'VALUATION COMFORT', 'Is this price reasonable? (HIGH = cheap)', s4.valuation, false);
  h += _render4DGauge('🏛️', 'BUSINESS QUALITY', 'Is this a good company, independent of price?', s4.quality, false);
  h += _render4DGauge('⚠️', 'RISK / CROWDING', 'How extended is this trade? (HIGH = safe; LOW = crowded)', s4.risk, true);
  h += '</div>';

  // Cycle warning if applied
  if (s4.valuation && s4.valuation.cycle_peak_warning) {
    var cw = s4.valuation.components && s4.valuation.components.cycle_peak_warning;
    if (cw && cw.applied) {
      h += '<div style="background:#fef3c7;border:1px solid #fde68a;border-left:4px solid #f59e0b;border-radius:6px;padding:10px 14px;margin-bottom:14px">';
      h += '<div style="font-size:11px;font-weight:800;color:#92400e;margin-bottom:3px;letter-spacing:0.3px">⚠ CYCLE-PEAK PENALTY APPLIED (-' + cw.penalty_pct + '%)</div>';
      h += '<div style="font-size:10px;color:#78350f;line-height:1.5">' + cw.explain;
      if (cw.rev_growth_pct !== null) h += ' Revenue growth ' + cw.rev_growth_pct + '%';
      if (cw.op_margin_pct !== null) h += ', operating margins ' + cw.op_margin_pct + '%';
      h += '.</div></div>';
    }
  }

  // SYNTHESIS — the 4 institutional questions
  h += '<div style="background:linear-gradient(135deg,#1A3A78 0%,#2563eb 100%);color:#fff;border-radius:10px;padding:14px 16px;margin-bottom:10px">';
  h += '<div style="font-size:10px;font-weight:800;letter-spacing:0.8px;margin-bottom:10px;opacity:0.9">🎯 INSTITUTIONAL SYNTHESIS — FOUR QUESTIONS</div>';
  h += '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px">';
  [
    ['good_company',   'Good company?',    '"A great business, regardless of price"'],
    ['good_stock',     'Good stock?',      '"A great business the market is recognizing"'],
    ['good_trade',     'Good trade?',      '"Strong momentum without being too crowded"'],
    ['good_entry_now', 'Good entry NOW?',  '"Right time to buy — price is reasonable, trade isn\'t parabolic"'],
  ].forEach(function(pair) {
    var key = pair[0], label = pair[1], expl = pair[2];
    var q = synth[key] || {};
    var sc = q.score;
    var verdict = q.verdict || 'NO DATA';
    var verdictColor = verdict.indexOf('STRONG') >= 0 ? '#10b981' :
                        verdict.indexOf('YES') >= 0 ? '#86efac' :
                        verdict === 'MIXED' ? '#fbbf24' :
                        verdict === 'NO' ? '#fca5a5' :
                        verdict === 'LEAN NO' ? '#fdba74' : '#cbd5e1';
    h += '<div style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);border-radius:6px;padding:8px 10px">';
    h += '<div style="display:flex;justify-content:space-between;align-items:baseline">';
    h += '<span style="font-size:11px;font-weight:800;letter-spacing:0.3px">' + label + '</span>';
    h += '<span style="font-size:14px;font-weight:900;font-family:IBM Plex Mono,monospace">' + (sc !== null && sc !== undefined ? Math.round(sc) : '—') + '</span>';
    h += '</div>';
    h += '<div style="font-size:11px;font-weight:800;color:' + verdictColor + ';margin-top:3px;letter-spacing:0.3px">' + verdict + '</div>';
    h += '<div style="font-size:9px;opacity:0.7;margin-top:2px;line-height:1.3">' + expl + '</div>';
    h += '</div>';
  });
  h += '</div>';
  h += '</div>';

  // Methodology note
  h += '<div style="margin-top:8px;font-size:9px;color:#94a3b8;line-height:1.4;font-style:italic">';
  h += '4D positioning never blends scores into one number — that would conflate momentum with valuation. Read each dimension independently. ';
  h += 'Business Quality measures quantitative financial strength; it does not capture sector-specific tailwinds like AI/HBM positioning.';
  h += '</div>';

  h += '</div>';
  el.innerHTML = h;
}

function _render4DGauge(icon, title, layman, dim, inverted) {
  var sc = dim && dim.score !== null && dim.score !== undefined ? dim.score : null;
  var band = (dim && dim.band) || {label: 'NO DATA', color: '#cbd5e1'};

  var h = '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px">';

  // Header row: icon + title + value
  h += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">';
  h += '<span style="font-size:11px;font-weight:800;letter-spacing:0.3px;color:#0f172a;font-family:Sora,sans-serif">' + icon + ' ' + title + '</span>';
  h += '<span style="font-size:22px;font-weight:900;color:' + band.color + ';font-family:IBM Plex Mono,monospace;line-height:1">' + (sc !== null ? Math.round(sc) : '—') + '</span>';
  h += '</div>';

  // Layman one-liner
  h += '<div style="font-size:10px;color:#64748b;margin-bottom:6px;line-height:1.4;font-style:italic">' + layman + '</div>';

  // Score bar
  h += '<div style="height:6px;background:#e2e8f0;border-radius:3px;overflow:hidden;margin-bottom:5px">';
  h += '<div style="height:100%;background:' + band.color + ';width:' + (sc !== null ? Math.max(2, Math.min(100, sc)) : 0) + '%"></div>';
  h += '</div>';

  // Band label
  h += '<div style="font-size:10px;font-weight:800;color:' + band.color + ';letter-spacing:0.4px;margin-bottom:6px">' + band.label + (inverted && sc !== null ? ' · ' + (sc >= 55 ? '(SAFE)' : '(CROWDED)') : '') + '</div>';

  // Components (compact)
  if (dim && dim.components) {
    var rows = [];
    Object.keys(dim.components).forEach(function(k) {
      var c = dim.components[k];
      if (!c) return;
      // Skip cycle_peak_warning (rendered separately above)
      if (k === 'cycle_peak_warning') return;
      if (c.score === null || c.score === undefined) return;
      var displayK = k.replace(/_/g, ' ');
      rows.push('<div style="display:flex;justify-content:space-between;font-size:9px;color:#64748b;font-family:IBM Plex Mono,monospace"><span>' + displayK + '</span><span style="color:#334155;font-weight:700">' + Math.round(c.score) + '</span></div>');
    });
    if (rows.length > 0) {
      h += '<div style="border-top:1px solid #e2e8f0;padding-top:5px;margin-top:3px">' + rows.join('') + '</div>';
    }
  }

  h += '</div>';
  return h;
}
