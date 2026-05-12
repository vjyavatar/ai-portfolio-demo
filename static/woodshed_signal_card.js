// ═══════════════════════════════════════════════════════════════════════════
// r63.72.27 — Woodshed Signal: capitulation detection card
// ═══════════════════════════════════════════════════════════════════════════

window._loadWoodshedSignal = function(symbol, region) {
  symbol = (symbol || window._ddLastSymbol || '').toUpperCase();
  region = region || window._deRegion || 'US';
  if (!symbol) return;
  var el = document.getElementById('ddWoodshedCard');
  if (!el) return;
  el.innerHTML = '<div style="padding:20px;text-align:center;font-size:11px;color:#94a3b8;font-family:Inter,sans-serif">Detecting woodshed signals…</div>';

  fetch('/api/dd-woodshed-signal?symbol=' + encodeURIComponent(symbol) + '&region=' + encodeURIComponent(region))
    .then(function(r){ return r.json(); })
    .then(function(d){ window._renderWoodshedSignal(d); })
    .catch(function(e){
      el.innerHTML = '<div style="padding:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;font-family:Inter,sans-serif;font-size:11px;color:#7f1d1d">⚠ Woodshed Signal unavailable: ' + (e.message || 'network error') + '</div>';
    });
};

window._renderWoodshedSignal = function(d) {
  var el = document.getElementById('ddWoodshedCard');
  if (!el) return;

  if (!d || !d.success) {
    el.innerHTML = '<div style="padding:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;font-family:Inter,sans-serif;font-size:11px;color:#7f1d1d">⚠ ' + ((d && d.error) || 'Unknown error') + '</div>';
    return;
  }

  var comp = d.components || {};
  var verdict = d.verdict || 'INSUFFICIENT DATA';
  var verdictColor = d.verdict_color || '#94a3b8';
  var composite = d.composite_score;

  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin-bottom:16px;font-family:Inter,sans-serif">';

  // ── Header
  h += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap">';
  h += '<span style="font-size:18px">🪓</span>';
  h += '<span style="font-size:13px;font-weight:800;color:#1A3A78;letter-spacing:0.3px;font-family:Sora,sans-serif">Woodshed Signal · Capitulation Detector</span>';
  if (d.partial_data) {
    h += '<span style="font-size:9px;font-weight:700;color:#92400e;background:#fef3c7;border:1px solid #fde68a;padding:2px 8px;border-radius:4px;letter-spacing:0.4px">⚠ PARTIAL</span>';
  }
  if (d.confidence) {
    var cc = d.confidence === 'high' ? '#10b981' : (d.confidence === 'medium' ? '#f59e0b' : '#dc2626');
    h += '<span style="font-size:9px;color:' + cc + ';font-weight:700;letter-spacing:0.4px">● ' + d.confidence.toUpperCase() + ' CONFIDENCE</span>';
  }
  var impl = d.price_implication;
  if (impl && impl.pct_contribution !== null && impl.pct_contribution !== undefined) {
    var implCol = impl.direction === 'bullish' ? '#10b981' : (impl.direction === 'bearish' ? '#dc2626' : '#94a3b8');
    var sign = impl.pct_contribution >= 0 ? '+' : '';
    h += '<span style="margin-left:auto;background:' + implCol + ';color:#fff;padding:3px 10px;border-radius:4px;font-size:10px;font-weight:800;letter-spacing:0.3px;font-family:Sora,sans-serif">' + sign + impl.pct_contribution.toFixed(0) + '% FAIR VALUE</span>';
  }
  h += '</div>';

  // ── Verdict banner
  h += '<div style="background:' + verdictColor + ';color:#fff;padding:14px 18px;border-radius:8px;margin-bottom:14px;display:flex;align-items:center;gap:16px;flex-wrap:wrap">';
  h += '<div style="flex:1;min-width:200px">';
  h += '<div style="font-size:9px;font-weight:800;letter-spacing:0.8px;opacity:0.9">VERDICT</div>';
  h += '<div style="font-size:20px;font-weight:900;letter-spacing:0.3px;font-family:Sora,sans-serif;line-height:1.1;margin-top:2px">' + verdict + '</div>';
  if (d.verdict_label) {
    h += '<div style="font-size:11px;opacity:0.95;margin-top:4px;font-weight:500">' + d.verdict_label + '</div>';
  }
  h += '</div>';
  if (composite !== null && composite !== undefined) {
    h += '<div style="text-align:right">';
    h += '<div style="font-size:9px;font-weight:800;letter-spacing:0.8px;opacity:0.9">SCORE</div>';
    h += '<div style="font-size:34px;font-weight:900;font-family:IBM Plex Mono,monospace;line-height:1">' + Math.round(composite) + '</div>';
    h += '<div style="font-size:9px;opacity:0.85;margin-top:1px">' + (d.components_present || 0) + ' of 5 components</div>';
    h += '</div>';
  }
  h += '</div>';

  // ── Headline
  if (d.headline) {
    h += '<div style="font-size:12px;font-weight:600;color:#0f172a;margin-bottom:14px;line-height:1.4;padding:0 2px">' + d.headline + '</div>';
  }

  // ── Component breakdown
  h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:14px">';

  // Drawdown
  h += _wsComponentBox(
    '📉', 'DRAWDOWN',  '40%',
    comp.drawdown,
    function(c) {
      return '<div style="font-size:22px;font-weight:900;color:#dc2626;font-family:IBM Plex Mono,monospace;line-height:1">−' + c.dd_pct.toFixed(0) + '%</div>' +
             '<div style="font-size:9px;color:#64748b;margin-top:3px">From 52w high $' + c.high_52w.toFixed(2) + '</div>';
    }
  );

  // RSI
  h += _wsComponentBox(
    '🌡️', 'RSI (14)',  '20%',
    comp.rsi,
    function(c) {
      var rsiCol = c.rsi < 30 ? '#dc2626' : (c.rsi < 40 ? '#f59e0b' : (c.rsi < 50 ? '#94a3b8' : '#10b981'));
      var rsiLabel = c.rsi < 30 ? 'OVERSOLD' : (c.rsi < 40 ? 'WEAKENING' : (c.rsi < 50 ? 'NEUTRAL' : 'STRONG'));
      return '<div style="font-size:22px;font-weight:900;color:' + rsiCol + ';font-family:IBM Plex Mono,monospace;line-height:1">' + c.rsi.toFixed(0) + '</div>' +
             '<div style="font-size:9px;color:#64748b;margin-top:3px">' + rsiLabel + '</div>';
    }
  );

  // Volume climax
  h += _wsComponentBox(
    '📊', 'VOL CAPITULATION',  '15%',
    comp.vol_climax,
    function(c) {
      return '<div style="font-size:22px;font-weight:900;color:' + (c.capit_days_10 >= 2 ? '#dc2626' : '#94a3b8') + ';font-family:IBM Plex Mono,monospace;line-height:1">' + c.capit_days_10 + '</div>' +
             '<div style="font-size:9px;color:#64748b;margin-top:3px">Capit days (10) · ' + (c.vol_drying ? 'drying' : 'steady') + '</div>';
    }
  );

  // Insider
  h += _wsComponentBox(
    '👥', 'INSIDER FLOW',  '15%',
    comp.insider,
    function(c) {
      var col = c.buy_ratio >= 70 ? '#10b981' : (c.buy_ratio >= 50 ? '#f59e0b' : '#dc2626');
      return '<div style="font-size:22px;font-weight:900;color:' + col + ';font-family:IBM Plex Mono,monospace;line-height:1">' + c.buys + 'b/' + c.sells + 's</div>' +
             '<div style="font-size:9px;color:#64748b;margin-top:3px">' + c.buy_ratio.toFixed(0) + '% buy ratio</div>';
    }
  );

  // Support proximity
  h += _wsComponentBox(
    '⊥', 'SUPPORT NEAR',  '10%',
    comp.support,
    function(c) {
      return '<div style="font-size:18px;font-weight:900;color:#1A3A78;font-family:IBM Plex Mono,monospace;line-height:1">$' + c.support_price.toFixed(2) + '</div>' +
             '<div style="font-size:9px;color:#64748b;margin-top:3px">' + c.distance_pct.toFixed(1) + '% from current</div>';
    }
  );

  h += '</div>';

  // ── Layman
  h += '<div style="background:#f8fafc;border-left:3px solid ' + verdictColor + ';padding:10px 14px;border-radius:0 6px 6px 0">';
  h += '<div style="font-size:9px;letter-spacing:0.5px;color:#1A3A78;font-weight:800;margin-bottom:4px;font-family:Sora,sans-serif">LAYMAN — 360° VIEW</div>';
  h += '<div style="font-size:12px;color:#334155;line-height:1.6">' + (d.layman || '—') + '</div>';
  if (impl && impl.target_band) {
    h += '<div style="font-size:10px;color:#64748b;margin-top:8px;font-family:IBM Plex Mono,monospace">' +
         'Estimated price range from this signal: <strong style="color:#1A3A78">$' + impl.target_band.low.toFixed(2) + ' – $' + impl.target_band.high.toFixed(2) + '</strong></div>';
  }
  h += '</div>';

  h += '</div>';
  el.innerHTML = h;
};

function _wsComponentBox(icon, title, weight, comp, valueFn) {
  var h = '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px">';
  h += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">';
  h += '<span style="font-size:9px;letter-spacing:0.5px;color:#64748b;font-weight:700">' + icon + ' ' + title + '</span>';
  h += '<span style="font-size:8px;font-weight:700;color:#94a3b8;background:#fff;padding:1px 5px;border-radius:3px">' + weight + '</span>';
  h += '</div>';
  if (comp && comp.score !== null && comp.score !== undefined) {
    h += valueFn(comp);
    // Score bar
    var scoreCol = comp.score >= 70 ? '#10b981' : (comp.score >= 40 ? '#f59e0b' : '#94a3b8');
    h += '<div style="margin-top:8px;height:5px;background:#e2e8f0;border-radius:3px;overflow:hidden">';
    h += '<div style="background:' + scoreCol + ';height:100%;width:' + Math.min(100, comp.score) + '%"></div>';
    h += '</div>';
    h += '<div style="font-size:9px;color:#94a3b8;margin-top:3px;font-family:IBM Plex Mono,monospace">Score: ' + comp.score.toFixed(0) + '/100</div>';
  } else {
    h += '<div style="font-size:11px;color:#cbd5e1;padding:8px 0">N/A</div>';
  }
  h += '</div>';
  return h;
}
