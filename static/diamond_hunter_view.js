// ═══════════════════════════════════════════════════════════════════════════
// r63.72.16 — Diamond Hunter: Post-Crash Quality Scanner
// Scans universe with simulated market correction, surfaces diamond candidates.
// ═══════════════════════════════════════════════════════════════════════════

window._diamondCrashPct = 25;
window._diamondMinMcap = 1000000000;  // $1B default
window._diamondCache = null;

window.loadDiamondHunter = function() {
  var el = document.getElementById('deResult');
  if (!el) return;

  // Render shell first
  window._renderDiamondShell();

  // Fire the actual scan
  window._runDiamondScan();
};

window._renderDiamondShell = function() {
  var el = document.getElementById('deResult');
  if (!el) return;

  var crashPct = window._diamondCrashPct;
  var minMcap = window._diamondMinMcap;

  var h = '';
  if (typeof _renderRegionToggle === 'function') {
    h += _renderRegionToggle('loadDiamondHunter', window._deRegion || 'US');
  }
  h += '<div style="max-width:1400px;margin:0 auto;padding:0 8px;font-family:Inter,sans-serif">';

  // Header
  h += '<div style="background:linear-gradient(135deg,#1A3A78,#7c3aed);color:#fff;padding:20px 24px;border-radius:12px;margin-bottom:14px">';
  h += '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">';
  h += '<div>';
  h += '<div style="font-size:11px;letter-spacing:0.8px;font-weight:700;opacity:0.85;font-family:Sora,sans-serif">💎 DIAMOND HUNTER · POST-CRASH QUALITY SCANNER</div>';
  h += '<h2 style="margin:4px 0 0;font-size:20px;font-weight:900;font-family:Sora,sans-serif">If market corrects −' + crashPct + '%, which stocks would be diamonds?</h2>';
  h += '<div style="font-size:11px;opacity:0.85;margin-top:4px;line-height:1.5">Stress-tests each name at beta-adjusted simulated price. Ranks by 5-component institutional framework: Business Strength · Valuation Compression · Institutional Flow · Moat &amp; Future · Technical Setup.</div>';
  h += '</div>';
  h += '</div>';
  h += '</div>';

  // Controls
  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin-bottom:14px">';
  h += '<div style="display:flex;gap:20px;flex-wrap:wrap;align-items:center">';

  // Crash slider
  h += '<div style="flex:2;min-width:260px">';
  h += '<div style="font-size:10px;font-weight:800;letter-spacing:0.5px;color:#64748b;margin-bottom:6px;font-family:Sora,sans-serif">SIMULATED MARKET CORRECTION</div>';
  h += '<div style="display:flex;gap:8px;flex-wrap:wrap">';
  [15, 25, 35, 50].forEach(function(pct) {
    var active = (crashPct == pct);
    h += '<button onclick="window._diamondCrashPct=' + pct + ';window._diamondCache=null;window.loadDiamondHunter();" ' +
         'style="padding:8px 14px;border-radius:8px;border:1px solid ' + (active ? '#1A3A78' : '#cbd5e1') + ';' +
         'background:' + (active ? '#1A3A78' : '#fff') + ';color:' + (active ? '#fff' : '#374151') + ';' +
         'cursor:pointer;font-family:Sora,sans-serif;font-weight:800;font-size:12px;letter-spacing:0.3px">' +
         '−' + pct + '%</button>';
  });
  h += '</div>';
  h += '</div>';

  // Min mcap toggle
  h += '<div style="flex:1;min-width:200px">';
  h += '<div style="font-size:10px;font-weight:800;letter-spacing:0.5px;color:#64748b;margin-bottom:6px;font-family:Sora,sans-serif">MIN MARKET CAP</div>';
  h += '<div style="display:flex;gap:6px;flex-wrap:wrap">';
  var mcapOpts = [
    {l:'$1B+', v: 1000000000},
    {l:'$10B+', v: 10000000000},
    {l:'$100B+', v: 100000000000},
  ];
  mcapOpts.forEach(function(o) {
    var active = (minMcap == o.v);
    h += '<button onclick="window._diamondMinMcap=' + o.v + ';window._diamondCache=null;window.loadDiamondHunter();" ' +
         'style="padding:6px 12px;border-radius:6px;border:1px solid ' + (active ? '#1A3A78' : '#cbd5e1') + ';' +
         'background:' + (active ? '#1A3A78' : '#fff') + ';color:' + (active ? '#fff' : '#374151') + ';' +
         'cursor:pointer;font-family:Sora,sans-serif;font-weight:700;font-size:10px">' +
         o.l + '</button>';
  });
  h += '</div>';
  h += '</div>';

  // Refresh
  h += '<button onclick="window._diamondCache=null;window.loadDiamondHunter();" ' +
       'style="padding:8px 14px;border-radius:6px;background:#fff;border:1px solid #cbd5e1;font-size:10px;font-weight:700;color:#374151;cursor:pointer;font-family:Sora,sans-serif">↻ Re-scan</button>';

  h += '</div></div>';

  // Results container
  h += '<div id="diamondResults">';
  if (window._diamondCache) {
    // Already loaded — caller will re-render
  } else {
    h += '<div style="padding:60px 20px;text-align:center;font-family:Inter,sans-serif">' +
         '<div style="font-size:32px;margin-bottom:14px">💎</div>' +
         '<div style="font-size:14px;font-weight:700;color:#0f172a">Hunting diamonds at −' + crashPct + '% simulated correction...</div>' +
         '<div style="font-size:11px;color:#94a3b8;margin-top:8px">Stress-testing universe across 5 institutional components. 30-60 seconds.</div>' +
         '</div>';
  }
  h += '</div>';

  h += '</div>';
  el.innerHTML = h;
};

window._runDiamondScan = function() {
  var url = '/api/diamond-hunter?crash_pct=' + window._diamondCrashPct +
            '&min_mcap=' + window._diamondMinMcap + '&limit=50';
  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      window._diamondCache = d;
      window._renderDiamondResults(d);
    })
    .catch(function(e) {
      var el = document.getElementById('diamondResults');
      if (el) el.innerHTML = '<div style="padding:40px 20px;text-align:center;color:#dc2626;font-family:Inter,sans-serif">' +
        '<div style="font-size:24px;margin-bottom:10px">⚠️</div>' +
        '<div style="font-size:13px;font-weight:700">Scan failed: ' + e.message + '</div>' +
        '</div>';
    });
};

window._renderDiamondResults = function(d) {
  var el = document.getElementById('diamondResults');
  if (!el) return;

  if (!d || !d.success) {
    el.innerHTML = '<div style="padding:40px 20px;text-align:center;color:#dc2626;font-family:Inter,sans-serif">' +
      '<div style="font-size:24px;margin-bottom:10px">⚠️</div>' +
      '<div style="font-size:13px;font-weight:700">' + ((d && d.error) || 'Unknown error') + '</div>' +
      '</div>';
    return;
  }

  var rows = d.results || [];
  if (rows.length === 0) {
    el.innerHTML = '<div style="padding:40px 20px;text-align:center;color:#94a3b8;font-family:Inter,sans-serif">' +
      '<div style="font-size:24px;margin-bottom:10px">📊</div>' +
      '<div style="font-size:13px">No tickers qualified. Try lower market-cap threshold or refresh.</div>' +
      '</div>';
    return;
  }

  // Helpers
  function fmtMoney(v) {
    if (!v) return '—';
    if (Math.abs(v) >= 1e12) return '$' + (v / 1e12).toFixed(1) + 'T';
    if (Math.abs(v) >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
    if (Math.abs(v) >= 1e6) return '$' + (v / 1e6).toFixed(0) + 'M';
    return '$' + v.toFixed(0);
  }
  function scoreCell(v) {
    if (v === null || v === undefined) return '<span style="color:#cbd5e1;font-size:9px">N/A</span>';
    var col = v >= 70 ? '#10b981' : v >= 50 ? '#3b82f6' : v >= 30 ? '#f59e0b' : '#dc2626';
    return '<span style="color:' + col + ';font-weight:800;font-family:IBM Plex Mono,monospace;font-size:12px">' + Math.round(v) + '</span>';
  }
  function verdictBadge(v) {
    var bg = '#f1f5f9', fg = '#475569';
    if (v === 'ELITE DIAMOND') { bg = '#7c3aed'; fg = '#fff'; }
    else if (v === 'STRONG DIAMOND') { bg = '#dcfce7'; fg = '#166534'; }
    else if (v === 'DIAMOND CANDIDATE') { bg = '#dbeafe'; fg = '#1e40af'; }
    else if (v === 'WATCH') { bg = '#fef3c7'; fg = '#92400e'; }
    else if (v === 'AVOID') { bg = '#fee2e2'; fg = '#991b1b'; }
    return '<span style="display:inline-block;padding:3px 8px;border-radius:6px;background:' + bg + ';color:' + fg + ';font-size:9px;font-weight:800;font-family:Sora,sans-serif;letter-spacing:0.3px;white-space:nowrap">' + v + '</span>';
  }

  var h = '';

  // Summary banner
  var elite = rows.filter(function(r){ return r.verdict === 'ELITE DIAMOND'; }).length;
  var strong = rows.filter(function(r){ return r.verdict === 'STRONG DIAMOND'; }).length;
  var candidates = rows.filter(function(r){ return r.verdict === 'DIAMOND CANDIDATE'; }).length;

  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin-bottom:14px;display:flex;gap:24px;flex-wrap:wrap;font-family:Inter,sans-serif">';
  h += '<div><div style="font-size:9px;letter-spacing:0.6px;color:#94a3b8;font-weight:700">TOTAL SCANNED</div><div style="font-size:22px;font-weight:900;color:#0f172a;font-family:IBM Plex Mono,monospace">' + (d.total_scored || 0) + '</div></div>';
  h += '<div><div style="font-size:9px;letter-spacing:0.6px;color:#7c3aed;font-weight:700">💎 ELITE DIAMONDS</div><div style="font-size:22px;font-weight:900;color:#7c3aed;font-family:IBM Plex Mono,monospace">' + elite + '</div></div>';
  h += '<div><div style="font-size:9px;letter-spacing:0.6px;color:#10b981;font-weight:700">STRONG DIAMONDS</div><div style="font-size:22px;font-weight:900;color:#10b981;font-family:IBM Plex Mono,monospace">' + strong + '</div></div>';
  h += '<div><div style="font-size:9px;letter-spacing:0.6px;color:#3b82f6;font-weight:700">CANDIDATES</div><div style="font-size:22px;font-weight:900;color:#3b82f6;font-family:IBM Plex Mono,monospace">' + candidates + '</div></div>';
  h += '<div style="flex:1;text-align:right;align-self:center"><div style="font-size:10px;color:#94a3b8;line-height:1.5">Sorted by 5-component composite score. Click a row for full DD.</div></div>';
  h += '</div>';

  // Results table
  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;font-family:Inter,sans-serif">';
  h += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:11px;min-width:1300px">';
  h += '<thead><tr style="background:#f8fafc;font-family:Sora,sans-serif">';
  var heads = [
    {l:'#', w:'34px'},
    {l:'STOCK', w:'auto', a:'left'},
    {l:'SECTOR', w:'140px', a:'left'},
    {l:'NOW', w:'72px', a:'right'},
    {l:'SIM PRICE', w:'80px', a:'right'},
    {l:'DROP', w:'56px', a:'right', tip:'Beta-adjusted simulated drawdown'},
    {l:'BUSINESS', w:'64px', a:'right', tip:'Business strength (30% weight)'},
    {l:'VAL @ SIM', w:'70px', a:'right', tip:'Valuation compression at simulated price (25% weight)'},
    {l:'INST FLOW', w:'70px', a:'right', tip:'Institutional accumulation (20% weight)'},
    {l:'MOAT/FUT', w:'70px', a:'right', tip:'Moat + future demand relevance (15% weight)'},
    {l:'TECH', w:'52px', a:'right', tip:'Technical recovery setup (10% weight)'},
    {l:'COMPOSITE', w:'78px', a:'right'},
    {l:'VERDICT', w:'130px', a:'left'},
    {l:'NARRATIVE', w:'auto', a:'left'},
  ];
  heads.forEach(function(hh){
    var tip = hh.tip ? ' title="' + hh.tip + '"' : '';
    h += '<th' + tip + ' style="padding:10px 8px;font-size:9px;letter-spacing:0.5px;color:#64748b;font-weight:800;text-align:' + (hh.a||'left') + ';width:' + hh.w + '">' + hh.l + '</th>';
  });
  h += '</tr></thead><tbody>';

  rows.forEach(function(r, i) {
    var clickAttr = 'onclick="window._ddLastSymbol=\'' + r.ticker.replace(/\'/g, "\\'") + '\';window._loadCycleAnalysis(\'' + r.ticker + '\', \'' + (window._deRegion || 'US') + '\', ' + (r.market_cap || 0) + ', ' + (r.current_price || 0) + ');"';

    var bsScore = (r.business_strength && r.business_strength.score) || null;
    var vcScore = (r.valuation_compression && r.valuation_compression.score) || null;
    var iaScore = (r.institutional_accumulation && r.institutional_accumulation.score) || null;
    var mfScore = (r.moat_future && r.moat_future.score) || null;
    var trScore = (r.technical_recovery && r.technical_recovery.score) || null;

    h += '<tr style="border-top:1px solid #f1f5f9;cursor:pointer" onmouseover="this.style.background=\'#fafbfc\'" onmouseout="this.style.background=\'\'" ' + clickAttr + '>';
    h += '<td style="padding:10px 8px;color:#94a3b8;font-family:IBM Plex Mono,monospace">' + (i+1) + '</td>';
    h += '<td style="padding:10px 8px"><div style="font-weight:800;color:#0f172a;font-family:IBM Plex Mono,monospace;font-size:12px">' + r.ticker + '</div></td>';
    h += '<td style="padding:10px 8px;color:#475569;font-size:10px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (r.sector || '—') + '</td>';
    h += '<td style="padding:10px 8px;text-align:right;color:#0f172a;font-family:IBM Plex Mono,monospace;font-weight:700">$' + (r.current_price ? r.current_price.toFixed(2) : '—') + '</td>';
    h += '<td style="padding:10px 8px;text-align:right;color:#7c3aed;font-family:IBM Plex Mono,monospace;font-weight:800">$' + (r.simulated_price ? r.simulated_price.toFixed(2) : '—') + '</td>';
    h += '<td style="padding:10px 8px;text-align:right;color:#dc2626;font-family:IBM Plex Mono,monospace;font-weight:700">−' + (r.implied_drawdown_pct ? r.implied_drawdown_pct.toFixed(0) : '—') + '%</td>';
    h += '<td style="padding:10px 8px;text-align:right">' + scoreCell(bsScore) + '</td>';
    h += '<td style="padding:10px 8px;text-align:right">' + scoreCell(vcScore) + '</td>';
    h += '<td style="padding:10px 8px;text-align:right">' + scoreCell(iaScore) + '</td>';
    h += '<td style="padding:10px 8px;text-align:right">' + scoreCell(mfScore) + '</td>';
    h += '<td style="padding:10px 8px;text-align:right">' + scoreCell(trScore) + '</td>';
    h += '<td style="padding:10px 8px;text-align:right">' + scoreCell(r.composite_score) + ' <span style="font-size:8px;color:#94a3b8">' + (r.components_present || 0) + '/5</span></td>';
    h += '<td style="padding:10px 8px">' + verdictBadge(r.verdict) + '</td>';
    h += '<td style="padding:10px 8px;color:#475569;font-size:10px;line-height:1.4">' + (r.narrative || '') + '</td>';
    h += '</tr>';
  });
  h += '</tbody></table></div></div>';

  // Methodology footer
  h += '<div style="padding:14px 4px;font-size:10px;color:#94a3b8;line-height:1.6;font-family:Inter,sans-serif">';
  h += '<strong>Methodology.</strong> For each ticker, the scanner simulates a beta-adjusted post-crash price (implied drawdown = market_drop × stock_beta, capped 60%, floored at half the market drop). At that simulated price, it scores 5 components: ';
  h += '<strong>Business Strength (30%)</strong> — revenue growth, gross margin level/stability, ROIC, FCF consistency, debt health. ';
  h += '<strong>Valuation Compression (25%)</strong> — P/S, EV/Sales, FCF yield, earnings yield, all at the simulated price. ';
  h += '<strong>Institutional Accumulation (20%)</strong> — buy/sell dominance, share velocity Q/Q, persistence, concentration. Heavy distribution caps score at 25. ';
  h += '<strong>Moat &amp; Future Demand (15%)</strong> — sector relevance (AI/semis/defense scored highest), gross margin durability, 3Y CAGR. ';
  h += '<strong>Technical Recovery (10%)</strong> — current 52W positioning + simulated entry depth sweet-spot (15-30% drawdown rewarded). ';
  h += '<br><br><strong>Verdict bands:</strong> ELITE DIAMOND ≥80 + ≥4 components · STRONG DIAMOND ≥70 + ≥4 · CANDIDATE ≥55 · WATCH ≥40 · AVOID below. INSUFFICIENT DATA when fewer than 3 components have real data.';
  h += '<br><br><strong>Limitations.</strong> Most components require fundamentals data (income statement, balance sheet). When Yahoo is blocked on Render, many rows will mark themselves N/A for those components — the scanner is honest about gaps, not fabricated. ';
  h += 'Thematic positioning (AI thesis intact, photonics exposure, defense secular trend) is approximated by sector taxonomy but cannot be extracted from structured data alone — overlay your own thesis judgment. ';
  h += 'Click any row to open the 360° Cycle Analysis for that ticker.';
  h += '</div>';

  el.innerHTML = h;
};
