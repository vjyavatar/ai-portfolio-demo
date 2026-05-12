// ═══════════════════════════════════════════════════════════════════════════
// r63.72.26 — DD Forward View
// Three new cards: Demand Curve · Ownership Activity · Volume Profile (Order Book proxy)
// ═══════════════════════════════════════════════════════════════════════════

window._loadDDForwardView = function(symbol, region) {
  symbol = (symbol || window._ddLastSymbol || '').toUpperCase();
  region = region || window._deRegion || 'US';
  if (!symbol) return;

  ['ddDemandCurveCard', 'ddOwnershipCard', 'ddVolumeProfileCard'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.innerHTML = '<div style="padding:20px;text-align:center;font-size:11px;color:#94a3b8;font-family:Inter,sans-serif">Loading…</div>';
  });

  // Fire all three in parallel
  fetch('/api/dd-demand-curve?symbol=' + encodeURIComponent(symbol) + '&region=' + encodeURIComponent(region))
    .then(function(r){return r.json();}).then(function(d){ window._renderDemandCurve(d); })
    .catch(function(e){ _ddRenderError('ddDemandCurveCard', 'Demand Curve', e.message); });

  fetch('/api/dd-ownership-activity?symbol=' + encodeURIComponent(symbol) + '&region=' + encodeURIComponent(region))
    .then(function(r){return r.json();}).then(function(d){ window._renderOwnershipActivity(d); })
    .catch(function(e){ _ddRenderError('ddOwnershipCard', 'Ownership Activity', e.message); });

  fetch('/api/dd-volume-profile?symbol=' + encodeURIComponent(symbol) + '&region=' + encodeURIComponent(region))
    .then(function(r){return r.json();}).then(function(d){ window._renderVolumeProfile(d); })
    .catch(function(e){ _ddRenderError('ddVolumeProfileCard', 'Volume Profile', e.message); });
};

function _ddRenderError(containerId, sectionName, msg) {
  var el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div style="padding:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;font-family:Inter,sans-serif;font-size:11px;color:#7f1d1d">' +
    '⚠ ' + sectionName + ' unavailable: ' + msg +
    '</div>';
}

function _ddPriceImplPill(impl) {
  if (!impl || impl.pct_contribution === null || impl.pct_contribution === undefined) {
    return '<span style="background:#f1f5f9;color:#64748b;padding:3px 8px;border-radius:4px;font-size:9px;font-weight:700;letter-spacing:0.3px;font-family:Sora,sans-serif">NEUTRAL</span>';
  }
  var col = impl.direction === 'bullish' ? '#10b981' : (impl.direction === 'bearish' ? '#dc2626' : '#94a3b8');
  var sign = impl.pct_contribution >= 0 ? '+' : '';
  return '<span style="background:' + col + ';color:#fff;padding:3px 10px;border-radius:4px;font-size:10px;font-weight:800;letter-spacing:0.3px;font-family:Sora,sans-serif">' +
    sign + impl.pct_contribution.toFixed(0) + '% FAIR VALUE' +
    '</span>';
}

function _ddCardHeader(icon, title, headline, impl, confidence, partial) {
  var h = '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">';
  h += '<span style="font-size:18px">' + icon + '</span>';
  h += '<span style="font-size:13px;font-weight:800;color:#1A3A78;letter-spacing:0.3px;font-family:Sora,sans-serif">' + title + '</span>';
  if (partial) {
    h += '<span style="font-size:9px;font-weight:700;color:#92400e;background:#fef3c7;border:1px solid #fde68a;padding:2px 8px;border-radius:4px;letter-spacing:0.4px">⚠ PARTIAL</span>';
  }
  if (confidence) {
    var cc = confidence === 'high' ? '#10b981' : (confidence === 'medium' ? '#f59e0b' : '#dc2626');
    h += '<span style="font-size:9px;color:' + cc + ';font-weight:700;letter-spacing:0.4px">● ' + confidence.toUpperCase() + ' CONFIDENCE</span>';
  }
  h += '<span style="margin-left:auto">' + _ddPriceImplPill(impl) + '</span>';
  h += '</div>';
  if (headline) {
    h += '<div style="font-size:12px;font-weight:600;color:#0f172a;margin-bottom:10px;line-height:1.4">' + headline + '</div>';
  }
  return h;
}

function _ddCardLayman(layman, impl) {
  var h = '<div style="background:#f8fafc;border-left:3px solid #1A3A78;padding:10px 14px;border-radius:0 6px 6px 0;margin-top:10px">';
  h += '<div style="font-size:9px;letter-spacing:0.5px;color:#1A3A78;font-weight:800;margin-bottom:4px;font-family:Sora,sans-serif">LAYMAN — 360° VIEW</div>';
  h += '<div style="font-size:12px;color:#334155;line-height:1.6">' + layman + '</div>';
  if (impl && impl.target_band) {
    h += '<div style="font-size:10px;color:#64748b;margin-top:8px;font-family:IBM Plex Mono,monospace">' +
         'Estimated price range from this signal: <strong style="color:#1A3A78">$' + impl.target_band.low.toFixed(2) + ' – $' + impl.target_band.high.toFixed(2) + '</strong>' +
         '</div>';
  }
  h += '</div>';
  return h;
}

// ─── SECTION 1: DEMAND CURVE ─────────────────────────────────────────────

window._renderDemandCurve = function(d) {
  var el = document.getElementById('ddDemandCurveCard');
  if (!el) return;
  if (!d || !d.success) {
    _ddRenderError('ddDemandCurveCard', 'Demand Curve', (d && d.error) || 'failed');
    return;
  }
  var cd = d.chart_data || {};
  var series = cd.series || [];

  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin-bottom:16px;font-family:Inter,sans-serif">';
  h += _ddCardHeader('📈', 'Demand Curve · 7-Year View', d.headline, d.price_implication, d.confidence, d.partial_data);

  // SVG chart
  if (series.length > 0) {
    h += _renderDemandSVG(series, cd);
  } else {
    h += '<div style="padding:20px;text-align:center;color:#94a3b8;font-size:11px">No data available</div>';
  }

  // Growth pills
  if (cd.historical_class && cd.forward_class) {
    h += '<div style="display:flex;gap:10px;margin-top:10px;flex-wrap:wrap">';
    h += '<div style="background:' + cd.historical_class.color + ';color:#fff;padding:6px 10px;border-radius:6px;font-size:10px;font-weight:700;font-family:Sora,sans-serif">' +
         'HIST: ' + cd.historical_cagr.toFixed(1) + '% · ' + cd.historical_class.label +
         '</div>';
    h += '<div style="background:' + cd.forward_class.color + ';color:#fff;padding:6px 10px;border-radius:6px;font-size:10px;font-weight:700;font-family:Sora,sans-serif">' +
         'FWD: ' + cd.forward_cagr.toFixed(1) + '% · ' + cd.forward_class.label +
         '</div>';
    if (cd.has_analyst_estimate) {
      h += '<div style="background:#dbeafe;color:#1e40af;padding:6px 10px;border-radius:6px;font-size:10px;font-weight:700;font-family:Sora,sans-serif">' +
           '✓ ANALYST CONSENSUS USED' +
           '</div>';
    } else {
      h += '<div style="background:#f1f5f9;color:#64748b;padding:6px 10px;border-radius:6px;font-size:10px;font-weight:700;font-family:Sora,sans-serif">' +
           '◌ SLOPE EXTRAPOLATION' +
           '</div>';
    }
    h += '</div>';
  }

  h += _ddCardLayman(d.layman, d.price_implication);
  h += '</div>';
  el.innerHTML = h;
};

function _renderDemandSVG(series, cd) {
  // Series: [{year, revenue, actual}, ...]
  var w = 720, hgt = 220, pad = 40;
  var maxRev = Math.max.apply(null, series.map(function(s){ return s.revenue; }));
  var minRev = Math.min.apply(null, series.map(function(s){ return s.revenue; }));
  var range = maxRev - minRev || 1;
  var nPts = series.length;
  var xScale = function(i) { return pad + (i / Math.max(1, nPts - 1)) * (w - pad * 2); };
  var yScale = function(v) { return hgt - pad - ((v - minRev) / range) * (hgt - pad * 2); };

  var svg = '<svg viewBox="0 0 ' + w + ' ' + hgt + '" style="width:100%;height:auto;display:block;background:#fafbfc;border-radius:6px">';
  // Grid lines
  for (var g = 0; g <= 4; g++) {
    var gy = pad + g * ((hgt - pad * 2) / 4);
    svg += '<line x1="' + pad + '" y1="' + gy + '" x2="' + (w - pad) + '" y2="' + gy + '" stroke="#e2e8f0" stroke-width="1"/>';
  }
  // Path: historical (solid) + forward (dashed)
  var firstForwardIdx = series.findIndex(function(s) { return !s.actual; });
  if (firstForwardIdx < 0) firstForwardIdx = series.length;

  // Historical area fill
  if (firstForwardIdx > 0) {
    var histPath = 'M ' + xScale(0) + ' ' + (hgt - pad);
    for (var i = 0; i < firstForwardIdx; i++) {
      histPath += ' L ' + xScale(i) + ' ' + yScale(series[i].revenue);
    }
    histPath += ' L ' + xScale(firstForwardIdx - 1) + ' ' + (hgt - pad) + ' Z';
    svg += '<path d="' + histPath + '" fill="rgba(26,58,120,0.15)"/>';
  }
  // Forward area fill (different color)
  if (firstForwardIdx < series.length) {
    var fwdPath = 'M ' + xScale(firstForwardIdx - 1) + ' ' + (hgt - pad);
    for (var j = Math.max(0, firstForwardIdx - 1); j < series.length; j++) {
      fwdPath += ' L ' + xScale(j) + ' ' + yScale(series[j].revenue);
    }
    fwdPath += ' L ' + xScale(series.length - 1) + ' ' + (hgt - pad) + ' Z';
    svg += '<path d="' + fwdPath + '" fill="rgba(124,58,237,0.15)"/>';
  }
  // Lines
  var histLine = '';
  for (var k = 0; k < firstForwardIdx; k++) {
    histLine += (k === 0 ? 'M ' : ' L ') + xScale(k) + ' ' + yScale(series[k].revenue);
  }
  if (histLine) svg += '<path d="' + histLine + '" fill="none" stroke="#1A3A78" stroke-width="2.5"/>';

  var fwdLine = '';
  for (var m = Math.max(0, firstForwardIdx - 1); m < series.length; m++) {
    fwdLine += (m === Math.max(0, firstForwardIdx - 1) ? 'M ' : ' L ') + xScale(m) + ' ' + yScale(series[m].revenue);
  }
  if (fwdLine) svg += '<path d="' + fwdLine + '" fill="none" stroke="#7c3aed" stroke-width="2.5" stroke-dasharray="6,4"/>';

  // Points + labels
  for (var p = 0; p < series.length; p++) {
    var px = xScale(p), py = yScale(series[p].revenue);
    var ptColor = series[p].actual ? '#1A3A78' : '#7c3aed';
    svg += '<circle cx="' + px + '" cy="' + py + '" r="4" fill="' + ptColor + '"/>';
    // Year label
    svg += '<text x="' + px + '" y="' + (hgt - pad + 16) + '" text-anchor="middle" font-size="10" fill="#64748b" font-family="IBM Plex Mono,monospace">' + series[p].year + '</text>';
    // Revenue label (just for endpoints + current)
    if (p === 0 || p === series.length - 1 || (series[p].actual && p === firstForwardIdx - 1)) {
      var revLabel = series[p].revenue >= 1e9 ? '$' + (series[p].revenue / 1e9).toFixed(1) + 'B' : '$' + (series[p].revenue / 1e6).toFixed(0) + 'M';
      svg += '<text x="' + px + '" y="' + (py - 10) + '" text-anchor="middle" font-size="10" fill="' + ptColor + '" font-weight="700" font-family="IBM Plex Mono,monospace">' + revLabel + '</text>';
    }
  }
  // Legend
  svg += '<g transform="translate(' + (w - 200) + ', 10)">';
  svg += '<rect x="0" y="0" width="12" height="3" fill="#1A3A78"/>';
  svg += '<text x="16" y="4" font-size="9" fill="#64748b">Historical (actual)</text>';
  svg += '<rect x="0" y="14" width="12" height="3" fill="#7c3aed"/>';
  svg += '<text x="16" y="18" font-size="9" fill="#64748b">Forward (projected)</text>';
  svg += '</g>';

  svg += '</svg>';
  return svg;
}

// ─── SECTION 2: OWNERSHIP ACTIVITY ────────────────────────────────────────

window._renderOwnershipActivity = function(d) {
  var el = document.getElementById('ddOwnershipCard');
  if (!el) return;
  if (!d || !d.success) {
    _ddRenderError('ddOwnershipCard', 'Ownership Activity', (d && d.error) || 'failed');
    return;
  }
  var cd = d.chart_data || {};

  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin-bottom:16px;font-family:Inter,sans-serif">';
  h += _ddCardHeader('👥', 'Insider & Institutional Activity', d.headline, d.price_implication, d.confidence, d.partial_data);

  // Insider summary bars
  h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:14px">';

  // Insider transactions box
  h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px">';
  h += '<div style="font-size:9px;letter-spacing:0.5px;color:#64748b;font-weight:700;margin-bottom:6px">INSIDER TRANSACTIONS (6mo)</div>';
  var totalTx = (cd.insider_buys_6mo || 0) + (cd.insider_sells_6mo || 0);
  if (totalTx > 0) {
    var buyPct = ((cd.insider_buys_6mo || 0) / totalTx) * 100;
    h += '<div style="display:flex;height:24px;border-radius:4px;overflow:hidden;background:#e2e8f0;margin-bottom:6px">';
    h += '<div style="background:#10b981;width:' + buyPct + '%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:10px;font-weight:700;font-family:IBM Plex Mono,monospace">' + (buyPct > 15 ? cd.insider_buys_6mo + ' BUYS' : '') + '</div>';
    h += '<div style="background:#dc2626;width:' + (100 - buyPct) + '%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:10px;font-weight:700;font-family:IBM Plex Mono,monospace">' + ((100 - buyPct) > 15 ? cd.insider_sells_6mo + ' SELLS' : '') + '</div>';
    h += '</div>';
    h += '<div style="font-size:11px;color:#0f172a;font-weight:700">Buy ratio: ' + cd.insider_buy_ratio_pct + '%</div>';
  } else {
    h += '<div style="font-size:11px;color:#94a3b8;padding:8px 0">No transactions reported</div>';
  }
  h += '</div>';

  // Institutional %
  h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px">';
  h += '<div style="font-size:9px;letter-spacing:0.5px;color:#64748b;font-weight:700;margin-bottom:6px">INSTITUTIONAL OWNERSHIP</div>';
  if (cd.inst_pct !== null && cd.inst_pct !== undefined) {
    var instPct = cd.inst_pct;
    h += '<div style="display:flex;align-items:baseline;gap:6px;margin-bottom:4px">';
    h += '<span style="font-size:22px;font-weight:900;color:#1A3A78;font-family:IBM Plex Mono,monospace">' + instPct.toFixed(0) + '%</span>';
    h += '<span style="font-size:10px;color:#64748b">of shares</span>';
    h += '</div>';
    // Bar
    h += '<div style="height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden">';
    h += '<div style="background:#1A3A78;height:100%;width:' + Math.min(100, instPct) + '%"></div>';
    h += '</div>';
    h += '<div style="font-size:9px;color:#94a3b8;margin-top:4px">Class: ' + (cd.inst_class || '').replace(/_/g, ' ') + '</div>';
  } else {
    h += '<div style="font-size:11px;color:#94a3b8;padding:8px 0">Not reported</div>';
  }
  h += '</div>';

  // Insider holdings %
  h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px">';
  h += '<div style="font-size:9px;letter-spacing:0.5px;color:#64748b;font-weight:700;margin-bottom:6px">INSIDER HOLDINGS</div>';
  if (cd.insider_pct !== null && cd.insider_pct !== undefined) {
    h += '<div style="display:flex;align-items:baseline;gap:6px">';
    h += '<span style="font-size:22px;font-weight:900;color:#7c3aed;font-family:IBM Plex Mono,monospace">' + cd.insider_pct.toFixed(1) + '%</span>';
    h += '<span style="font-size:10px;color:#64748b">held by insiders</span>';
    h += '</div>';
    h += '<div style="font-size:9px;color:#94a3b8;margin-top:8px">' +
         (cd.insider_pct >= 10 ? 'High insider stake — strong skin in the game' :
          cd.insider_pct >= 3 ? 'Moderate insider stake' :
          'Low insider stake — diluted founder presence') +
         '</div>';
  } else {
    h += '<div style="font-size:11px;color:#94a3b8;padding:8px 0">Not reported</div>';
  }
  h += '</div>';
  h += '</div>';

  // Recent transactions table
  if (cd.insider_recent_tx && cd.insider_recent_tx.length > 0) {
    h += '<div style="margin-bottom:10px">';
    h += '<div style="font-size:9px;letter-spacing:0.5px;color:#64748b;font-weight:800;margin-bottom:6px;font-family:Sora,sans-serif">RECENT INSIDER TRANSACTIONS</div>';
    h += '<div style="max-height:140px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:6px">';
    cd.insider_recent_tx.slice(0, 6).forEach(function(tx) {
      var color = tx.type === 'buy' ? '#10b981' : '#dc2626';
      var icon  = tx.type === 'buy' ? '▲' : '▼';
      h += '<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid #f1f5f9;font-size:11px">';
      h += '<span style="color:' + color + ';font-weight:900;width:14px">' + icon + '</span>';
      h += '<span style="font-weight:700;color:#0f172a;text-transform:uppercase;letter-spacing:0.4px;font-size:10px;width:40px">' + tx.type + '</span>';
      h += '<span style="font-family:IBM Plex Mono,monospace;color:#475569;font-size:11px;flex:1">' + Math.abs(tx.shares).toLocaleString() + ' sh</span>';
      h += '<span style="font-size:10px;color:#94a3b8;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px">' + (tx.name || '') + '</span>';
      h += '</div>';
    });
    h += '</div></div>';
  }

  h += _ddCardLayman(d.layman, d.price_implication);
  h += '</div>';
  el.innerHTML = h;
};

// ─── SECTION 3: VOLUME PROFILE ─────────────────────────────────────────────

window._renderVolumeProfile = function(d) {
  var el = document.getElementById('ddVolumeProfileCard');
  if (!el) return;
  if (!d || !d.success) {
    _ddRenderError('ddVolumeProfileCard', 'Volume Profile', (d && d.error) || 'failed');
    return;
  }
  var cd = d.chart_data || {};

  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin-bottom:16px;font-family:Inter,sans-serif">';
  h += _ddCardHeader('📊', 'Volume Profile · Order Book Proxy (90d)', d.headline, d.price_implication, d.confidence, d.partial_data);

  // Volume-by-price horizontal bars
  if (cd.buckets && cd.buckets.length > 0) {
    h += _renderVolumeProfileSVG(cd);
  }

  // Support / Resistance summary
  h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-top:14px">';
  h += '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:8px 12px">';
  h += '<div style="font-size:9px;letter-spacing:0.5px;color:#15803d;font-weight:700;margin-bottom:4px">⊥ NEAREST SUPPORT</div>';
  if (cd.support_levels && cd.support_levels.length > 0) {
    cd.support_levels.forEach(function(s) {
      h += '<div style="font-size:12px;color:#0f172a;font-family:IBM Plex Mono,monospace;font-weight:700">$' + s.price.toFixed(2) + ' <span style="font-size:9px;color:#64748b;font-weight:500">(' + s.volume_pct.toFixed(1) + '% of vol)</span></div>';
    });
  } else {
    h += '<div style="font-size:11px;color:#94a3b8">None below current price</div>';
  }
  h += '</div>';
  h += '<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:8px 12px">';
  h += '<div style="font-size:9px;letter-spacing:0.5px;color:#b91c1c;font-weight:700;margin-bottom:4px">⊤ NEAREST RESISTANCE</div>';
  if (cd.resistance_levels && cd.resistance_levels.length > 0) {
    cd.resistance_levels.forEach(function(r) {
      h += '<div style="font-size:12px;color:#0f172a;font-family:IBM Plex Mono,monospace;font-weight:700">$' + r.price.toFixed(2) + ' <span style="font-size:9px;color:#64748b;font-weight:500">(' + r.volume_pct.toFixed(1) + '% of vol)</span></div>';
    });
  } else {
    h += '<div style="font-size:11px;color:#94a3b8">None above current price</div>';
  }
  h += '</div>';
  h += '<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:8px 12px">';
  h += '<div style="font-size:9px;letter-spacing:0.5px;color:#1e40af;font-weight:700;margin-bottom:4px">⊕ POINT OF CONTROL</div>';
  h += '<div style="font-size:14px;color:#1A3A78;font-family:IBM Plex Mono,monospace;font-weight:900">$' + cd.poc_price.toFixed(2) + '</div>';
  h += '<div style="font-size:9px;color:#64748b">' + cd.poc_volume_pct + '% of 90-day volume traded near here</div>';
  h += '</div>';
  h += '</div>';

  h += _ddCardLayman(d.layman, d.price_implication);
  h += '</div>';
  el.innerHTML = h;
};

function _renderVolumeProfileSVG(cd) {
  var buckets = cd.buckets.slice().reverse();  // High price at top
  var w = 720, hgt = 320;
  var leftLabel = 70, rightMargin = 20;
  var rowH = (hgt - 20) / buckets.length;
  var maxVol = Math.max.apply(null, buckets.map(function(b){ return b.volume; }));
  var currentPrice = cd.current_price;

  var svg = '<svg viewBox="0 0 ' + w + ' ' + hgt + '" style="width:100%;height:auto;display:block;background:#fafbfc;border-radius:6px">';

  buckets.forEach(function(b, idx) {
    var y = 10 + idx * rowH;
    var barW = (b.volume / maxVol) * (w - leftLabel - rightMargin);
    var color = b.in_value_area ? '#7c3aed' : '#94a3b8';
    // POC bucket gets special highlight
    if (Math.abs(b.mid - cd.poc_price) < 0.01) color = '#1A3A78';

    // Price label (left)
    svg += '<text x="' + (leftLabel - 6) + '" y="' + (y + rowH / 2 + 3) + '" text-anchor="end" font-size="9" fill="#64748b" font-family="IBM Plex Mono,monospace">$' + b.mid.toFixed(2) + '</text>';
    // Bar
    svg += '<rect x="' + leftLabel + '" y="' + (y + 1) + '" width="' + barW + '" height="' + (rowH - 2) + '" fill="' + color + '" opacity="' + (b.in_value_area ? 0.85 : 0.55) + '"/>';
    // Volume pct label inside or after
    if (barW > 40) {
      svg += '<text x="' + (leftLabel + barW - 4) + '" y="' + (y + rowH / 2 + 3) + '" text-anchor="end" font-size="9" fill="#fff" font-weight="700" font-family="IBM Plex Mono,monospace">' + b.volume_pct.toFixed(1) + '%</text>';
    }
  });

  // Current price horizontal line
  if (currentPrice !== undefined) {
    // Find vertical position
    var minP = Math.min.apply(null, buckets.map(function(b){ return b.low; }));
    var maxP = Math.max.apply(null, buckets.map(function(b){ return b.high; }));
    if (maxP > minP) {
      var priceY = 10 + ((maxP - currentPrice) / (maxP - minP)) * (hgt - 20);
      svg += '<line x1="' + leftLabel + '" y1="' + priceY + '" x2="' + (w - rightMargin) + '" y2="' + priceY + '" stroke="#dc2626" stroke-width="2" stroke-dasharray="4,3"/>';
      svg += '<text x="' + (w - rightMargin - 4) + '" y="' + (priceY - 4) + '" text-anchor="end" font-size="10" fill="#dc2626" font-weight="800" font-family="IBM Plex Mono,monospace">NOW $' + currentPrice.toFixed(2) + '</text>';
    }
  }

  // Legend
  svg += '<g transform="translate(' + leftLabel + ', ' + (hgt - 6) + ')">';
  svg += '<rect x="0" y="-8" width="10" height="6" fill="#7c3aed" opacity="0.85"/>';
  svg += '<text x="14" y="-3" font-size="9" fill="#64748b">Value Area (70% of volume)</text>';
  svg += '<rect x="160" y="-8" width="10" height="6" fill="#1A3A78"/>';
  svg += '<text x="174" y="-3" font-size="9" fill="#64748b">Point of Control</text>';
  svg += '<rect x="280" y="-8" width="10" height="6" fill="#94a3b8" opacity="0.55"/>';
  svg += '<text x="294" y="-3" font-size="9" fill="#64748b">Outside Value Area</text>';
  svg += '</g>';

  svg += '</svg>';
  return svg;
}
