// ═══════════════════════════════════════════════════════════════════════════
// r63.72.25 — Stock Commentary & Day-to-Day Tracker
// Renders into a card inside the Deep DD report.
// ═══════════════════════════════════════════════════════════════════════════

window._loadStockCommentary = function(symbol, region, containerId) {
  containerId = containerId || 'stockCommentaryCard';
  symbol = (symbol || window._ddLastSymbol || '').toUpperCase();
  region = region || window._deRegion || 'US';

  var el = document.getElementById(containerId);
  if (!el) return;

  // Loading state
  el.innerHTML = '<div style="padding:24px;text-align:center;font-family:Inter,sans-serif">' +
    '<div style="font-size:11px;color:#94a3b8">Loading commentary for ' + symbol + '…</div>' +
    '</div>';

  var url = '/api/stock-commentary?symbol=' + encodeURIComponent(symbol) + '&region=' + encodeURIComponent(region);
  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(d) { window._renderStockCommentary(d, containerId); })
    .catch(function(e) {
      el.innerHTML = '<div style="padding:16px;color:#dc2626;font-family:Inter,sans-serif;font-size:12px">' +
        '⚠ Commentary unavailable: ' + (e.message || 'network error') + '</div>';
    });
};

window._renderStockCommentary = function(d, containerId) {
  var el = document.getElementById(containerId);
  if (!el) return;

  if (!d || !d.success) {
    el.innerHTML = '<div style="padding:16px;color:#dc2626;font-family:Inter,sans-serif;font-size:12px">' +
      '⚠ ' + ((d && d.error) || 'Unknown error') + '</div>';
    return;
  }

  var today = d.today_move;
  var trend = d.trend_5d;

  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin-bottom:16px;font-family:Inter,sans-serif">';

  // Header
  h += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap">';
  h += '<span style="font-size:18px">📰</span>';
  h += '<span style="font-size:13px;font-weight:800;color:#1A3A78;letter-spacing:0.3px;font-family:Sora,sans-serif">Commentary & Day-to-Day</span>';
  if (d.partial_data) {
    h += '<span style="font-size:9px;font-weight:700;color:#92400e;background:#fef3c7;border:1px solid #fde68a;padding:2px 8px;border-radius:4px;letter-spacing:0.4px">⚠ PARTIAL DATA</span>';
  }
  h += '</div>';

  // Today + 5-day pills
  if (today || trend) {
    h += '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">';
    if (today && today.pct !== null && today.pct !== undefined) {
      h += '<div style="background:' + (today.color || '#94a3b8') + ';color:#fff;padding:8px 14px;border-radius:8px;display:flex;flex-direction:column;min-width:130px">' +
           '<span style="font-size:9px;font-weight:700;opacity:0.85;letter-spacing:0.5px">TODAY</span>' +
           '<span style="font-size:16px;font-weight:900;font-family:IBM Plex Mono,monospace">' + (today.pct >= 0 ? '+' : '') + today.pct.toFixed(2) + '%</span>' +
           '<span style="font-size:10px;opacity:0.95;margin-top:1px;font-weight:600">' + (today.label || '') + '</span>' +
           '</div>';
    }
    if (trend && trend.pct !== null && trend.pct !== undefined) {
      h += '<div style="background:' + (trend.color || '#94a3b8') + ';color:#fff;padding:8px 14px;border-radius:8px;display:flex;flex-direction:column;min-width:130px">' +
           '<span style="font-size:9px;font-weight:700;opacity:0.85;letter-spacing:0.5px">5-DAY TREND</span>' +
           '<span style="font-size:16px;font-weight:900;font-family:IBM Plex Mono,monospace">' + (trend.pct >= 0 ? '+' : '') + trend.pct.toFixed(2) + '%</span>' +
           '<span style="font-size:10px;opacity:0.95;margin-top:1px;font-weight:600">' + (trend.label || '') + '</span>' +
           '</div>';
    }
    if (d.earnings && d.earnings.date) {
      var eColor = d.earnings.imminent ? '#7c3aed' : (d.earnings.passed ? '#94a3b8' : '#1A3A78');
      var eLabel = d.earnings.imminent ? 'IMMINENT' : (d.earnings.passed ? 'RECENT' : 'UPCOMING');
      h += '<div style="background:' + eColor + ';color:#fff;padding:8px 14px;border-radius:8px;display:flex;flex-direction:column;min-width:130px">' +
           '<span style="font-size:9px;font-weight:700;opacity:0.85;letter-spacing:0.5px">⚡ EARNINGS ' + eLabel + '</span>' +
           '<span style="font-size:14px;font-weight:900;font-family:IBM Plex Mono,monospace">' + d.earnings.date + '</span>' +
           '<span style="font-size:10px;opacity:0.95;margin-top:1px;font-weight:600">' + Math.abs(d.earnings.days_out) + ' days ' + (d.earnings.passed ? 'ago' : 'away') + '</span>' +
           '</div>';
    }
    h += '</div>';
  }

  // Narrative
  if (d.narrative) {
    h += '<div style="background:#f8fafc;border-left:3px solid #1A3A78;padding:10px 14px;border-radius:0 6px 6px 0;margin-bottom:14px">' +
         '<div style="font-size:9px;letter-spacing:0.5px;color:#1A3A78;font-weight:800;margin-bottom:4px;font-family:Sora,sans-serif">DAY-TO-DAY NARRATIVE</div>' +
         '<div style="font-size:12px;color:#334155;line-height:1.5">' + d.narrative + '</div>' +
         '</div>';
  }

  // Event timeline (last 7 days)
  if (d.events && d.events.length > 0) {
    h += '<div style="margin-bottom:14px">';
    h += '<div style="font-size:9px;letter-spacing:0.5px;color:#64748b;font-weight:800;margin-bottom:6px;font-family:Sora,sans-serif">RECENT DAYS</div>';
    h += '<div style="display:flex;gap:4px;flex-wrap:wrap">';
    d.events.forEach(function(ev) {
      var pctStr = ev.pct >= 0 ? '+' + ev.pct.toFixed(1) + '%' : ev.pct.toFixed(1) + '%';
      h += '<div title="' + ev.date + ' · close $' + ev.close + ' · ' + ev.label + '" style="background:' + ev.color + ';color:#fff;padding:4px 8px;border-radius:5px;font-size:10px;font-weight:700;font-family:IBM Plex Mono,monospace;letter-spacing:0.3px">' +
           ev.date.slice(5) + ' ' + pctStr +
           '</div>';
    });
    h += '</div></div>';
  }

  // Headlines
  if (d.headlines && d.headlines.length > 0) {
    h += '<div>';
    h += '<div style="font-size:9px;letter-spacing:0.5px;color:#64748b;font-weight:800;margin-bottom:6px;font-family:Sora,sans-serif">HEADLINES (' + d.headlines.length + ')</div>';
    d.headlines.slice(0, 5).forEach(function(n) {
      var sc = n.sentiment === 'bullish' ? '#10b981' : (n.sentiment === 'bearish' ? '#dc2626' : '#94a3b8');
      var icon = n.sentiment === 'bullish' ? '↑' : (n.sentiment === 'bearish' ? '↓' : '·');
      h += '<div style="display:flex;gap:8px;padding:6px 0;border-bottom:1px solid #f1f5f9;font-size:11px;align-items:flex-start">' +
           '<span style="color:' + sc + ';font-weight:900;font-family:IBM Plex Mono,monospace;flex-shrink:0;min-width:14px;text-align:center">' + icon + '</span>' +
           '<div style="flex:1">' +
           (n.link ? '<a href="' + n.link + '" target="_blank" style="color:#0f172a;text-decoration:none;font-weight:600;line-height:1.4">' + n.title + '</a>' :
                     '<span style="color:#0f172a;font-weight:600;line-height:1.4">' + n.title + '</span>') +
           (n.publisher ? '<div style="font-size:9px;color:#94a3b8;margin-top:1px">' + n.publisher + '</div>' : '') +
           '</div></div>';
    });
    h += '</div>';
  } else if (!d.partial_data) {
    h += '<div style="font-size:11px;color:#94a3b8;padding:8px 0">No recent headlines. Stock may be moving on broader market or technical factors.</div>';
  }

  // Data source notes
  if (d.partial_data || d.data_sources) {
    var noteParts = [];
    if (d.data_sources) {
      if (d.data_sources.news === 'failed') noteParts.push('News fetch timed out');
      if (d.data_sources.price === 'failed') noteParts.push('Price history unavailable');
    }
    if (noteParts.length > 0) {
      h += '<div style="margin-top:10px;padding:8px 10px;background:#fef3c7;border:1px solid #fde68a;border-radius:4px;font-size:10px;color:#92400e;line-height:1.4">' +
           '⚠ ' + noteParts.join(' · ') + '. Data sources are rate-limited; refresh in a few minutes for fresh data.' +
           '</div>';
    }
  }

  h += '</div>';
  el.innerHTML = h;
};
