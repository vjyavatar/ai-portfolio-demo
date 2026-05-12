// ═══════════════════════════════════════════════════════════════════════════
// r63.72.28 — Mood Gauges (Market vs Sector vs Stock) — semi-circle gauges
// ═══════════════════════════════════════════════════════════════════════════

window._loadMoodGauges = function(symbol, sector, region) {
  symbol = (symbol || window._ddLastSymbol || '').toUpperCase();
  sector = sector || window._ddLastSector || '';
  region = region || window._deRegion || 'US';
  if (!symbol) return;

  var el = document.getElementById('ddMoodGaugesCard');
  if (!el) return;
  el.innerHTML = '<div style="padding:20px;text-align:center;font-size:11px;color:#94a3b8;font-family:Inter,sans-serif">Calculating market · sector · stock mood…</div>';

  var url = '/api/dd-mood-gauges?symbol=' + encodeURIComponent(symbol) +
            '&sector=' + encodeURIComponent(sector) +
            '&region=' + encodeURIComponent(region);

  fetch(url)
    .then(function(r){ return r.json(); })
    .then(function(d){ window._renderMoodGauges(d); })
    .catch(function(e){
      el.innerHTML = '<div style="padding:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;font-family:Inter,sans-serif;font-size:11px;color:#7f1d1d">⚠ Mood gauges unavailable: ' + (e.message || 'network error') + '</div>';
    });
};

window._renderMoodGauges = function(d) {
  var el = document.getElementById('ddMoodGaugesCard');
  if (!el) return;

  if (!d || !d.success) {
    el.innerHTML = '<div style="padding:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;font-family:Inter,sans-serif;font-size:11px;color:#7f1d1d">⚠ ' + ((d && d.error) || 'Unknown error') + '</div>';
    return;
  }

  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin-bottom:16px;font-family:Inter,sans-serif">';

  // Header
  h += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap">';
  h += '<span style="font-size:18px">🎭</span>';
  h += '<span style="font-size:13px;font-weight:800;color:#1A3A78;letter-spacing:0.3px;font-family:Sora,sans-serif">Market · Sector · Stock Mood</span>';
  if (d.partial_data) {
    h += '<span style="font-size:9px;font-weight:700;color:#92400e;background:#fef3c7;border:1px solid #fde68a;padding:2px 8px;border-radius:4px;letter-spacing:0.4px">⚠ PARTIAL</span>';
  }
  if (d.confidence) {
    var cc = d.confidence === 'high' ? '#10b981' : (d.confidence === 'medium' ? '#f59e0b' : '#dc2626');
    h += '<span style="font-size:9px;color:' + cc + ';font-weight:700;letter-spacing:0.4px">● ' + d.confidence.toUpperCase() + ' CONFIDENCE</span>';
  }
  h += '</div>';

  // Three gauges side-by-side
  h += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:14px">';
  h += _renderSingleGauge(d.market, '🌍');
  h += _renderSingleGauge(d.sector_mood, '🏭');
  h += _renderSingleGauge(d.stock, '📌');
  h += '</div>';

  // Layman + divergence narrative
  if (d.layman) {
    h += '<div style="background:#f8fafc;border-left:3px solid #1A3A78;padding:10px 14px;border-radius:0 6px 6px 0">';
    h += '<div style="font-size:9px;letter-spacing:0.5px;color:#1A3A78;font-weight:800;margin-bottom:4px;font-family:Sora,sans-serif">LAYMAN — 360° VIEW</div>';
    h += '<div style="font-size:12px;color:#334155;line-height:1.6">' + d.layman + '</div>';
    h += '</div>';
  }

  h += '</div>';
  el.innerHTML = h;
};

function _renderSingleGauge(mood, fallbackIcon) {
  if (!mood) {
    return '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 12px;text-align:center"><div style="font-size:11px;color:#94a3b8">No data</div></div>';
  }

  var score = mood.score;
  var band = mood.band || {};
  var label = mood.label || '—';
  var instrument = mood.instrument || mood.symbol || '';

  var bandColor = band.color || '#94a3b8';
  var bandLabel = band.label || 'NO DATA';

  // SVG dimensions
  var w = 200, hgt = 130;
  var cx = w / 2, cy = hgt - 18;
  var r = 75;
  var strokeW = 14;

  // Arc paths for the colored zones (5 segments mapping the 0-100 scale)
  // Semicircle goes from 180° (left, fear) to 0° (right, greed)
  // 0-25 deep red, 25-45 red, 45-55 gray, 55-75 green, 75-100 deep green
  function polarToCart(angleDeg) {
    var rad = (angleDeg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
  }
  function arcPath(startAngle, endAngle) {
    // angles in degrees, 0 = right, 180 = left
    var s = polarToCart(startAngle);
    var e = polarToCart(endAngle);
    var largeArc = (Math.abs(endAngle - startAngle) > 180) ? 1 : 0;
    var sweep = startAngle > endAngle ? 1 : 0;
    return 'M ' + s.x + ' ' + s.y + ' A ' + r + ' ' + r + ' 0 ' + largeArc + ' ' + sweep + ' ' + e.x + ' ' + e.y;
  }

  // Map score (0-100) to angle (180° = score 0, 0° = score 100)
  function scoreToAngle(s) { return 180 - (s / 100) * 180; }

  var svg = '<svg viewBox="0 0 ' + w + ' ' + hgt + '" style="width:100%;height:auto;display:block">';

  // Background arc segments (5 zones)
  var zones = [
    { from: 0,  to: 25,  color: '#991b1b' },  // extreme fear
    { from: 25, to: 45,  color: '#dc2626' },  // fear
    { from: 45, to: 55,  color: '#94a3b8' },  // neutral
    { from: 55, to: 75,  color: '#10b981' },  // greed
    { from: 75, to: 100, color: '#059669' },  // extreme greed
  ];
  zones.forEach(function(z) {
    var a1 = scoreToAngle(z.from);
    var a2 = scoreToAngle(z.to);
    svg += '<path d="' + arcPath(a1, a2) + '" stroke="' + z.color + '" stroke-width="' + strokeW + '" fill="none" stroke-linecap="butt" opacity="0.85"/>';
  });

  // Needle — only if we have a score
  if (score !== null && score !== undefined) {
    var needleAngle = scoreToAngle(score);
    var needleEnd = polarToCart(needleAngle);
    var needleInnerR = 8;
    var needleInner = {
      x: cx + needleInnerR * Math.cos((needleAngle * Math.PI) / 180),
      y: cy - needleInnerR * Math.sin((needleAngle * Math.PI) / 180)
    };
    // Pull needle slightly inside the arc
    var needleOuterR = r - strokeW / 2 - 2;
    var needleOuter = {
      x: cx + needleOuterR * Math.cos((needleAngle * Math.PI) / 180),
      y: cy - needleOuterR * Math.sin((needleAngle * Math.PI) / 180)
    };
    svg += '<line x1="' + needleInner.x + '" y1="' + needleInner.y + '" x2="' + needleOuter.x + '" y2="' + needleOuter.y + '" stroke="#0f172a" stroke-width="3" stroke-linecap="round"/>';
    svg += '<circle cx="' + cx + '" cy="' + cy + '" r="6" fill="#0f172a"/>';
    svg += '<circle cx="' + cx + '" cy="' + cy + '" r="3" fill="#fff"/>';
  } else {
    // Dim center, no needle
    svg += '<circle cx="' + cx + '" cy="' + cy + '" r="6" fill="#cbd5e1"/>';
  }

  // Score number large in center-bottom
  if (score !== null && score !== undefined) {
    svg += '<text x="' + cx + '" y="' + (cy - 28) + '" text-anchor="middle" font-size="26" font-weight="900" fill="' + bandColor + '" font-family="IBM Plex Mono,monospace">' + Math.round(score) + '</text>';
  } else {
    svg += '<text x="' + cx + '" y="' + (cy - 28) + '" text-anchor="middle" font-size="18" font-weight="700" fill="#cbd5e1" font-family="IBM Plex Mono,monospace">—</text>';
  }

  // Endpoint labels (0 left, 100 right)
  svg += '<text x="' + (cx - r - 2) + '" y="' + (cy + 16) + '" text-anchor="middle" font-size="8" fill="#94a3b8" font-family="Sora,sans-serif">FEAR</text>';
  svg += '<text x="' + (cx + r + 2) + '" y="' + (cy + 16) + '" text-anchor="middle" font-size="8" fill="#94a3b8" font-family="Sora,sans-serif">GREED</text>';

  svg += '</svg>';

  // Wrapping card
  var h = '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 10px;text-align:center">';
  h += '<div style="font-size:9px;letter-spacing:0.5px;color:#64748b;font-weight:800;margin-bottom:2px;font-family:Sora,sans-serif">' + (mood.label || '').toUpperCase() + ' MOOD</div>';
  h += '<div style="font-size:10px;color:#94a3b8;margin-bottom:6px;font-family:IBM Plex Mono,monospace">' + instrument + '</div>';
  h += svg;
  h += '<div style="background:' + bandColor + ';color:#fff;padding:4px 10px;border-radius:4px;font-size:10px;font-weight:800;letter-spacing:0.4px;font-family:Sora,sans-serif;display:inline-block;margin-top:4px">' + bandLabel + '</div>';

  // Component breakdown — compact
  if (mood.components) {
    var compRows = [];
    Object.keys(mood.components).forEach(function(k) {
      var c = mood.components[k];
      if (c && c.score !== null && c.score !== undefined) {
        var label = k.replace(/_/g, ' ');
        compRows.push('<div style="display:flex;justify-content:space-between;font-size:9px;color:#64748b;font-family:IBM Plex Mono,monospace"><span>' + label + '</span><span style="font-weight:700;color:#334155">' + c.score.toFixed(0) + '</span></div>');
      }
    });
    if (compRows.length > 0) {
      h += '<div style="margin-top:6px;padding-top:6px;border-top:1px solid #e2e8f0">' + compRows.join('') + '</div>';
    }
  }

  if (mood.reason_unavailable) {
    h += '<div style="margin-top:6px;font-size:9px;color:#94a3b8;font-style:italic">' + mood.reason_unavailable + '</div>';
  }

  h += '</div>';
  return h;
}
