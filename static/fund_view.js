// ═══════════════════════════════════════════════════════════════════════════
// r63.72.11 — Fund View (ETF / Mutual Fund) for Deep DD
// Renders when Deep DD detects an ETF or MF instead of a stock.
// Phase 1: single-fund analytics. Phase 2: comparison mode.
// ═══════════════════════════════════════════════════════════════════════════

window._renderFundView = function(fund, region) {
  var el = document.getElementById('deResult');
  if (!el) return;

  var csym = (fund.currency === "INR" || region === "IN") ? "₹" : "$";
  var isMF = fund.type === "us_mf" || fund.type === "india_mf";
  var isIndiaMF = fund.type === "india_mf";
  var typeLabel = fund.type === "us_etf" ? "ETF" :
                  fund.type === "india_etf" ? "INDIA ETF" :
                  fund.type === "us_mf" ? "MUTUAL FUND" :
                  fund.type === "india_mf" ? "INDIA MUTUAL FUND" : "FUND";

  function fmtPct(v, decimals) {
    if (v === null || v === undefined) return '<span style="color:#cbd5e1">—</span>';
    var d = decimals !== undefined ? decimals : 2;
    var col = v >= 0 ? '#10b981' : '#dc2626';
    return '<span style="color:' + col + ';font-weight:700;font-family:IBM Plex Mono,monospace">' +
           (v >= 0 ? '+' : '') + v.toFixed(d) + '%</span>';
  }
  function fmtMoney(v) {
    if (!v) return '<span style="color:#cbd5e1">—</span>';
    if (Math.abs(v) >= 1e12) return csym + (v / 1e12).toFixed(2) + 'T';
    if (Math.abs(v) >= 1e9) return csym + (v / 1e9).toFixed(2) + 'B';
    if (Math.abs(v) >= 1e6) return csym + (v / 1e6).toFixed(2) + 'M';
    if (Math.abs(v) >= 1e3) return csym + (v / 1e3).toFixed(2) + 'K';
    return csym + v.toFixed(2);
  }
  function fmtNum(v, d) {
    if (v === null || v === undefined) return '<span style="color:#cbd5e1">—</span>';
    return v.toFixed(d !== undefined ? d : 2);
  }

  var h = '';

  // Region toggle
  if (typeof _renderRegionToggle === 'function') {
    h += _renderRegionToggle('loadDeepDD', region);
  }
  h += '<div style="max-width:1200px;margin:0 auto;padding:0 8px;font-family:Inter,sans-serif">';

  // ── Header card ────────────────────────────────────────────────────────
  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 22px;margin-bottom:14px">';
  h += '<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">';
  h += '<div style="width:48px;height:48px;background:linear-gradient(135deg,#7c3aed,#1A3A78);border-radius:8px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:18px;font-weight:900;font-family:Sora,sans-serif">' +
       (fund.ticker || '??').substring(0, 3) + '</div>';
  h += '<div style="flex:1;min-width:200px">';
  h += '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">';
  h += '<span style="font-size:16px;font-weight:900;color:#0f172a;font-family:Sora,sans-serif">' + (fund.ticker || '') + '</span>';
  h += '<span style="padding:3px 8px;background:#ede9fe;color:#5b21b6;border-radius:6px;font-size:9px;font-weight:800;letter-spacing:0.5px;font-family:Sora,sans-serif">' + typeLabel + '</span>';
  if (fund.family) {
    h += '<span style="font-size:11px;color:#64748b">· ' + fund.family + '</span>';
  }
  h += '</div>';
  h += '<div style="font-size:13px;color:#475569;margin-top:3px">' + (fund.name || '') + '</div>';
  if (fund.category) {
    h += '<div style="font-size:10px;color:#94a3b8;margin-top:2px">' + fund.category + '</div>';
  }
  h += '</div>';
  // NAV
  h += '<div style="text-align:right">';
  h += '<div style="font-size:9px;color:#94a3b8;font-weight:700;letter-spacing:0.6px">NAV</div>';
  h += '<div style="font-size:22px;font-weight:900;color:#0f172a;font-family:IBM Plex Mono,monospace">' + csym + (fund.nav ? fund.nav.toFixed(2) : '—') + '</div>';
  if (fund.nav_date) {
    h += '<div style="font-size:9px;color:#94a3b8">' + fund.nav_date + '</div>';
  }
  h += '</div>';
  h += '</div>';

  // Compare button + back button
  h += '<div style="display:flex;gap:8px;margin-top:14px;border-top:1px solid #f1f5f9;padding-top:12px">';
  h += '<button onclick="loadDeepDD()" style="padding:6px 12px;border:1px solid #cbd5e1;background:#fff;border-radius:6px;font-size:10px;font-weight:700;cursor:pointer;font-family:Sora,sans-serif">← New Ticker</button>';
  h += '<button onclick="window._showFundCompareModal(\'' + (fund.ticker || '').replace(/'/g, "\\'") + '\', \'' + region + '\')" style="padding:6px 12px;border:1px solid #7c3aed;background:#7c3aed;color:#fff;border-radius:6px;font-size:10px;font-weight:700;cursor:pointer;font-family:Sora,sans-serif">⚖ Compare Funds</button>';
  h += '</div>';
  h += '</div>';

  // ── Lens score card ────────────────────────────────────────────────────
  var ls = fund.lens_score || {};
  var verdictColor = ls.verdict === 'EXCELLENT' ? '#10b981' :
                     ls.verdict === 'GOOD' ? '#3b82f6' :
                     ls.verdict === 'FAIR' ? '#f59e0b' :
                     ls.verdict === 'POOR' ? '#dc2626' : '#94a3b8';

  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 22px;margin-bottom:14px">';
  h += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">';
  h += '<div style="font-size:11px;font-weight:800;letter-spacing:0.6px;color:#64748b;font-family:Sora,sans-serif">FUND LENS SCORE</div>';
  h += '<div style="padding:5px 12px;border-radius:6px;background:' + verdictColor + ';color:#fff;font-size:11px;font-weight:800;font-family:Sora,sans-serif">' + (ls.verdict || 'N/A') + (ls.composite !== null && ls.composite !== undefined ? ' · ' + ls.composite : '') + '</div>';
  h += '</div>';

  function _sub(label, val) {
    var col = '#94a3b8';
    var disp = 'N/A';
    if (val !== null && val !== undefined) {
      col = val >= 70 ? '#10b981' : val >= 50 ? '#3b82f6' : val >= 30 ? '#f59e0b' : '#dc2626';
      disp = Math.round(val);
    }
    return '<div style="text-align:center;flex:1;min-width:90px">' +
           '<div style="font-size:9px;color:#94a3b8;font-weight:700;letter-spacing:0.6px;margin-bottom:4px">' + label + '</div>' +
           '<div style="font-size:20px;font-weight:900;color:' + col + ';font-family:IBM Plex Mono,monospace">' + disp + '</div>' +
           '</div>';
  }
  h += '<div style="display:flex;gap:12px;flex-wrap:wrap">';
  h += _sub('COST EFFICIENCY', ls.cost_efficiency);
  h += _sub('RISK-ADJUSTED',    ls.risk_adjusted);
  h += _sub('PERFORMANCE',      ls.performance);
  h += _sub('SIZE / QUALITY',   ls.size_quality);
  h += '</div>';
  h += '<div style="margin-top:12px;font-size:10px;color:#94a3b8;line-height:1.4">' +
       'Weighted composite: Cost (25%) + Risk-Adjusted (30%) + Performance (30%) + Size Quality (15%). ' +
       'Verdict requires at least 2 input dimensions with real data.</div>';
  h += '</div>';

  // ── Key metrics row ────────────────────────────────────────────────────
  h += '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(160px, 1fr));gap:10px;margin-bottom:14px">';

  function _metricBox(label, value, sub) {
    var html = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px">';
    html += '<div style="font-size:9px;color:#94a3b8;font-weight:700;letter-spacing:0.6px">' + label + '</div>';
    html += '<div style="font-size:15px;font-weight:800;color:#0f172a;font-family:IBM Plex Mono,monospace;margin-top:4px">' + value + '</div>';
    if (sub) html += '<div style="font-size:9px;color:#94a3b8;margin-top:2px">' + sub + '</div>';
    html += '</div>';
    return html;
  }

  // Expense ratio
  var er = fund.expense_ratio;
  var erStr = er ? er.toFixed(2) + '%' : '<span style="color:#cbd5e1">—</span>';
  h += _metricBox('EXPENSE RATIO', erStr, er ? (er <= 0.1 ? 'ultra-low' : er <= 0.5 ? 'low' : er <= 1 ? 'moderate' : 'high') : null);

  // AUM
  h += _metricBox('AUM', fmtMoney(fund.total_assets), 'total assets');

  // Beta
  if (fund.beta !== undefined && fund.beta !== null && fund.beta !== 0) {
    h += _metricBox('BETA', fmtNum(fund.beta), 'vs. market');
  }

  // Sharpe ratio
  if (fund.sharpe_ratio !== undefined && fund.sharpe_ratio !== null) {
    h += _metricBox('SHARPE RATIO', fmtNum(fund.sharpe_ratio), 'risk-adjusted return');
  }

  // Volatility
  if (fund.volatility_annual !== undefined) {
    h += _metricBox('VOLATILITY', fmtNum(fund.volatility_annual, 1) + '%', 'annualized');
  }

  // Max drawdown
  if (fund.max_drawdown !== undefined) {
    h += _metricBox('MAX DRAWDOWN', fmtPct(fund.max_drawdown, 1), 'peak-to-trough');
  }

  // Yield
  if (fund.yield_pct) {
    h += _metricBox('YIELD', fmtNum(fund.yield_pct, 2) + '%', 'distribution');
  }

  // Morningstar rating
  if (fund.morningstar_rating) {
    var stars = '★'.repeat(fund.morningstar_rating) + '☆'.repeat(5 - fund.morningstar_rating);
    h += _metricBox('MORNINGSTAR', stars, 'overall rating');
  }
  h += '</div>';

  // ── Returns table ──────────────────────────────────────────────────────
  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin-bottom:14px">';
  h += '<div style="font-size:11px;font-weight:800;letter-spacing:0.6px;color:#64748b;font-family:Sora,sans-serif;margin-bottom:10px">TRAILING RETURNS</div>';
  h += '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(110px, 1fr));gap:10px">';

  var retCols = [
    {label: '1M',  val: fund.one_month_return},
    {label: '3M',  val: fund.three_month_return},
    {label: '6M',  val: fund.six_month_return},
    {label: 'YTD', val: fund.ytd_return},
    {label: '1Y',  val: fund.one_year_return},
    {label: '3Y',  val: fund.three_year_return},
    {label: '5Y',  val: fund.five_year_return},
  ];
  retCols.forEach(function(rc) {
    h += '<div style="text-align:center;padding:8px;background:#f8fafc;border-radius:6px">';
    h += '<div style="font-size:9px;color:#94a3b8;font-weight:700;letter-spacing:0.6px;margin-bottom:4px">' + rc.label + '</div>';
    h += '<div style="font-size:13px;font-weight:800;font-family:IBM Plex Mono,monospace">' + fmtPct(rc.val) + '</div>';
    h += '</div>';
  });
  h += '</div></div>';

  // ── Holdings + Sectors (side by side on wide screens) ──────────────────
  h += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">';

  // Top holdings
  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px">';
  h += '<div style="font-size:11px;font-weight:800;letter-spacing:0.6px;color:#64748b;font-family:Sora,sans-serif;margin-bottom:10px">TOP HOLDINGS</div>';
  if (fund.top_holdings && fund.top_holdings.length) {
    h += '<table style="width:100%;border-collapse:collapse;font-size:11px">';
    fund.top_holdings.slice(0, 10).forEach(function(holding, i) {
      var w = holding.weight || 0;
      h += '<tr style="border-top:' + (i === 0 ? 'none' : '1px solid #f1f5f9') + '">';
      h += '<td style="padding:6px 4px;color:#94a3b8;font-family:IBM Plex Mono,monospace;width:24px">' + (i + 1) + '</td>';
      h += '<td style="padding:6px 4px;font-weight:700;color:#0f172a;font-family:IBM Plex Mono,monospace">' + holding.ticker + '</td>';
      h += '<td style="padding:6px 4px;color:#475569;font-size:10px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (holding.name || '') + '</td>';
      h += '<td style="padding:6px 4px;text-align:right;font-family:IBM Plex Mono,monospace;font-weight:700;color:#1A3A78">' + w.toFixed(2) + '%</td>';
      h += '</tr>';
      // Mini bar
      h += '<tr><td colspan="4" style="padding:0 4px 4px"><div style="height:3px;background:#f1f5f9;border-radius:2px"><div style="height:3px;background:#7c3aed;width:' + Math.min(100, w * 5) + '%;border-radius:2px"></div></div></td></tr>';
    });
    h += '</table>';
  } else {
    h += '<div style="padding:30px 10px;text-align:center;color:#94a3b8;font-size:11px">Holdings data unavailable</div>';
  }
  h += '</div>';

  // Sector allocation
  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px">';
  h += '<div style="font-size:11px;font-weight:800;letter-spacing:0.6px;color:#64748b;font-family:Sora,sans-serif;margin-bottom:10px">SECTOR ALLOCATION</div>';
  if (fund.sectors && fund.sectors.length) {
    var sortedSectors = fund.sectors.slice().sort(function(a, b) { return b.weight - a.weight; });
    sortedSectors.forEach(function(s) {
      var w = s.weight || 0;
      h += '<div style="margin-bottom:8px">';
      h += '<div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:3px">';
      h += '<span style="color:#475569;font-weight:600">' + s.sector + '</span>';
      h += '<span style="font-family:IBM Plex Mono,monospace;color:#1A3A78;font-weight:700">' + w.toFixed(1) + '%</span>';
      h += '</div>';
      h += '<div style="height:6px;background:#f1f5f9;border-radius:3px"><div style="height:6px;background:linear-gradient(90deg,#1A3A78,#7c3aed);width:' + Math.min(100, w) + '%;border-radius:3px"></div></div>';
      h += '</div>';
    });
  } else {
    h += '<div style="padding:30px 10px;text-align:center;color:#94a3b8;font-size:11px">Sector data unavailable</div>';
  }
  h += '</div>';
  h += '</div>';

  // ── Footer note ────────────────────────────────────────────────────────
  h += '<div style="padding:14px 4px;font-size:10px;color:#94a3b8;line-height:1.5">';
  h += '<strong>Lens Score</strong> weights: Cost Efficiency (25%, lower expense ratio = better), Risk-Adjusted Return (30%, Sharpe ratio), Performance (30%, trailing returns), Size Quality (15%, AUM). ';
  h += 'Verdict bands: EXCELLENT ≥75 · GOOD ≥60 · FAIR ≥40 · POOR <40. ';
  if (isIndiaMF) {
    h += 'India MF data sourced from AMFI (NAV) + MFAPI.in (history, scheme details). ';
  } else if (fund.type === 'india_etf') {
    h += 'India ETF data sourced from NSE. ';
  } else {
    h += 'US fund data sourced from Yahoo Finance. ';
  }
  h += 'Click <strong>Compare Funds</strong> to add 1-2 more tickers for side-by-side analysis with holdings overlap.';
  h += '</div>';

  h += '</div>';  // close max-width container
  el.innerHTML = h;
};

// ── Compare modal ────────────────────────────────────────────────────────
window._showFundCompareModal = function(currentTicker, region) {
  var existing = document.getElementById('fundCompareModal');
  if (existing) existing.remove();

  var html = '<div id="fundCompareModal" style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(15,23,42,0.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px;font-family:Inter,sans-serif" onclick="if(event.target===this)this.remove()">';
  html += '<div style="background:#fff;border-radius:12px;padding:24px;max-width:560px;width:100%;max-height:90vh;overflow-y:auto" onclick="event.stopPropagation()">';
  html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">';
  html += '<h3 style="margin:0;font-size:16px;font-weight:900;color:#0f172a;font-family:Sora,sans-serif">⚖ Compare Funds</h3>';
  html += '<button onclick="document.getElementById(\'fundCompareModal\').remove()" style="background:none;border:none;font-size:20px;color:#94a3b8;cursor:pointer">×</button>';
  html += '</div>';
  html += '<div style="font-size:11px;color:#64748b;margin-bottom:14px">Comparing <strong>' + currentTicker + '</strong> with up to 2 more funds. Enter their tickers below.</div>';

  html += '<div style="margin-bottom:10px">';
  html += '<label style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.4px">FUND 2 TICKER</label>';
  html += '<input id="cmpTicker2" type="text" placeholder="e.g. VOO, QQQ, NIFTYBEES" style="width:100%;padding:8px 10px;margin-top:4px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;font-family:IBM Plex Mono,monospace;text-transform:uppercase">';
  html += '</div>';

  html += '<div style="margin-bottom:14px">';
  html += '<label style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.4px">FUND 3 TICKER (optional)</label>';
  html += '<input id="cmpTicker3" type="text" placeholder="e.g. VTI" style="width:100%;padding:8px 10px;margin-top:4px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;font-family:IBM Plex Mono,monospace;text-transform:uppercase">';
  html += '</div>';

  html += '<button onclick="window._runFundCompare(\'' + currentTicker + '\', \'' + region + '\')" style="width:100%;padding:10px;background:#7c3aed;color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:800;cursor:pointer;font-family:Sora,sans-serif">Compare →</button>';

  html += '</div></div>';
  document.body.insertAdjacentHTML('beforeend', html);
  setTimeout(function() { var i = document.getElementById('cmpTicker2'); if (i) i.focus(); }, 50);
};

window._runFundCompare = function(t1, region) {
  var t2 = (document.getElementById('cmpTicker2').value || '').trim().toUpperCase();
  var t3 = (document.getElementById('cmpTicker3').value || '').trim().toUpperCase();
  if (!t2) {
    document.getElementById('cmpTicker2').style.borderColor = '#dc2626';
    return;
  }
  var tickers = [t1, t2];
  if (t3) tickers.push(t3);
  document.getElementById('fundCompareModal').remove();

  var el = document.getElementById('deResult');
  if (el) {
    el.innerHTML = '<div style="padding:60px 20px;text-align:center;font-family:Inter,sans-serif">' +
      '<div style="font-size:32px;margin-bottom:14px">⚖</div>' +
      '<div style="font-size:14px;font-weight:700;color:#0f172a">Loading comparison for ' + tickers.join(', ') + '...</div>' +
      '</div>';
  }

  fetch('/api/fund-compare?tickers=' + encodeURIComponent(tickers.join(',')) + '&region=' + region)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (!d.success) {
        if (el) {
          el.innerHTML = '<div style="padding:60px 20px;text-align:center;color:#dc2626;font-family:Inter,sans-serif">' +
            '<div style="font-size:32px;margin-bottom:14px">⚠️</div>' +
            '<div style="font-size:14px;font-weight:700">Compare failed</div>' +
            '<div style="font-size:11px;margin-top:8px;color:#94a3b8">' + (d.error || 'unknown') + '</div>' +
            '<button onclick="loadDeepDD()" style="margin-top:14px;padding:6px 12px;border:1px solid #cbd5e1;background:#fff;border-radius:6px;font-size:11px;cursor:pointer">← Back</button>' +
            '</div>';
        }
        return;
      }
      window._renderFundCompare(d.funds, d.overlaps, region);
    });
};

window._renderFundCompare = function(funds, overlaps, region) {
  var el = document.getElementById('deResult');
  if (!el) return;

  var csym = region === 'IN' ? '₹' : '$';
  function fmtPct(v) {
    if (v === null || v === undefined) return '<span style="color:#cbd5e1">—</span>';
    var col = v >= 0 ? '#10b981' : '#dc2626';
    return '<span style="color:' + col + ';font-weight:700;font-family:IBM Plex Mono,monospace">' +
           (v >= 0 ? '+' : '') + v.toFixed(2) + '%</span>';
  }
  function fmtMoney(v) {
    if (!v) return '—';
    if (Math.abs(v) >= 1e12) return csym + (v / 1e12).toFixed(2) + 'T';
    if (Math.abs(v) >= 1e9) return csym + (v / 1e9).toFixed(2) + 'B';
    if (Math.abs(v) >= 1e6) return csym + (v / 1e6).toFixed(2) + 'M';
    return csym + v.toFixed(2);
  }

  var h = '';
  if (typeof _renderRegionToggle === 'function') h += _renderRegionToggle('loadDeepDD', region);
  h += '<div style="max-width:1400px;margin:0 auto;padding:0 8px;font-family:Inter,sans-serif">';

  // Header
  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center">';
  h += '<div><h2 style="margin:0;font-size:17px;font-weight:900;color:#0f172a;font-family:Sora,sans-serif">⚖ Fund Comparison</h2>';
  h += '<div style="font-size:11px;color:#64748b;margin-top:3px">Comparing ' + funds.length + ' funds: ' + funds.map(function(f){return f.ticker;}).join(' vs ') + '</div></div>';
  h += '<button onclick="loadDeepDD()" style="padding:6px 12px;border:1px solid #cbd5e1;background:#fff;border-radius:6px;font-size:10px;font-weight:700;cursor:pointer;font-family:Sora,sans-serif">← Back</button>';
  h += '</div>';

  // Side-by-side comparison table
  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin-bottom:14px;overflow-x:auto">';
  h += '<table style="width:100%;border-collapse:collapse;font-size:11px;min-width:700px">';
  h += '<thead><tr style="background:#f8fafc"><th style="padding:10px 8px;text-align:left;font-size:9px;letter-spacing:0.6px;color:#64748b;font-weight:800">METRIC</th>';
  funds.forEach(function(f) {
    h += '<th style="padding:10px 8px;text-align:right;font-size:9px;letter-spacing:0.6px;color:#64748b;font-weight:800">' + f.ticker + '</th>';
  });
  h += '</tr></thead><tbody>';

  var rows = [
    {label: 'Name', key: 'name'},
    {label: 'Type', key: 'type'},
    {label: 'Category', key: 'category'},
    {label: 'NAV', key: 'nav', format: 'money'},
    {label: 'AUM', key: 'total_assets', format: 'money'},
    {label: 'Expense Ratio', key: 'expense_ratio', format: 'pct'},
    {label: '1Y Return', key: 'one_year_return', format: 'pct_signed'},
    {label: '3Y Return', key: 'three_year_return', format: 'pct_signed'},
    {label: '5Y Return', key: 'five_year_return', format: 'pct_signed'},
    {label: 'Beta', key: 'beta', format: 'num'},
    {label: 'Sharpe Ratio', key: 'sharpe_ratio', format: 'num'},
    {label: 'Max Drawdown', key: 'max_drawdown', format: 'pct_signed'},
    {label: 'Volatility', key: 'volatility_annual', format: 'pct'},
  ];

  rows.forEach(function(row) {
    h += '<tr style="border-top:1px solid #f1f5f9">';
    h += '<td style="padding:8px;color:#475569;font-weight:600">' + row.label + '</td>';
    funds.forEach(function(f) {
      var v = f[row.key];
      var disp = '—';
      if (v !== null && v !== undefined && v !== '') {
        if (row.format === 'money') disp = fmtMoney(v);
        else if (row.format === 'pct_signed') disp = fmtPct(v);
        else if (row.format === 'pct') disp = (typeof v === 'number' ? v.toFixed(2) + '%' : v);
        else if (row.format === 'num') disp = (typeof v === 'number' ? v.toFixed(2) : v);
        else disp = v;
      }
      h += '<td style="padding:8px;text-align:right;font-family:IBM Plex Mono,monospace">' + disp + '</td>';
    });
    h += '</tr>';
  });

  // Lens score row
  h += '<tr style="border-top:2px solid #e2e8f0;background:#fafbfc">';
  h += '<td style="padding:10px 8px;color:#0f172a;font-weight:800">LENS VERDICT</td>';
  funds.forEach(function(f) {
    var ls = f.lens_score || {};
    var col = ls.verdict === 'EXCELLENT' ? '#10b981' :
              ls.verdict === 'GOOD' ? '#3b82f6' :
              ls.verdict === 'FAIR' ? '#f59e0b' :
              ls.verdict === 'POOR' ? '#dc2626' : '#94a3b8';
    h += '<td style="padding:10px 8px;text-align:right">' +
         '<span style="padding:3px 8px;border-radius:6px;background:' + col + ';color:#fff;font-size:10px;font-weight:800;font-family:Sora,sans-serif">' +
         (ls.verdict || 'N/A') + (ls.composite !== null && ls.composite !== undefined ? ' · ' + ls.composite : '') +
         '</span></td>';
  });
  h += '</tr>';

  h += '</tbody></table></div>';

  // Holdings overlap
  if (overlaps && overlaps.length) {
    h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin-bottom:14px">';
    h += '<div style="font-size:11px;font-weight:800;letter-spacing:0.6px;color:#64748b;font-family:Sora,sans-serif;margin-bottom:10px">HOLDINGS OVERLAP</div>';
    overlaps.forEach(function(o) {
      h += '<div style="margin-bottom:14px">';
      h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">';
      h += '<span style="font-size:13px;font-weight:800;color:#0f172a;font-family:Sora,sans-serif">' + o.ticker_a + ' ⇄ ' + o.ticker_b + '</span>';
      if (o.overlap_pct !== null && o.overlap_pct !== undefined) {
        var col = o.overlap_pct >= 70 ? '#dc2626' : o.overlap_pct >= 40 ? '#f59e0b' : '#10b981';
        var label = o.overlap_pct >= 70 ? 'HIGH OVERLAP — redundant pairing' :
                    o.overlap_pct >= 40 ? 'MODERATE OVERLAP' :
                    'LOW OVERLAP — complementary';
        h += '<span style="padding:3px 8px;border-radius:6px;background:' + col + ';color:#fff;font-size:10px;font-weight:800;font-family:Sora,sans-serif">' + o.overlap_pct.toFixed(1) + '% · ' + label + '</span>';
      } else {
        h += '<span style="color:#94a3b8;font-size:11px">' + (o.note || 'Overlap data unavailable') + '</span>';
      }
      h += '</div>';
      // Bar
      if (o.overlap_pct !== null && o.overlap_pct !== undefined) {
        h += '<div style="height:6px;background:#f1f5f9;border-radius:3px"><div style="height:6px;background:linear-gradient(90deg,#10b981,#f59e0b,#dc2626);width:' + Math.min(100, o.overlap_pct) + '%;border-radius:3px"></div></div>';
      }
      // Common tickers
      if (o.common_tickers && o.common_tickers.length) {
        h += '<div style="margin-top:8px;font-size:10px;color:#475569"><strong>Common:</strong> ';
        h += o.common_tickers.slice(0, 8).map(function(c) {
          return '<span style="display:inline-block;padding:2px 6px;background:#f1f5f9;border-radius:4px;margin:2px;font-family:IBM Plex Mono,monospace">' +
                 c.ticker + ' (' + c.weight_a.toFixed(1) + '%/' + c.weight_b.toFixed(1) + '%)' + '</span>';
        }).join('');
        h += '</div>';
      }
      h += '</div>';
    });
    h += '</div>';
  }

  // Interpretation help
  h += '<div style="padding:14px 4px;font-size:10px;color:#94a3b8;line-height:1.5">';
  h += '<strong>Reading the comparison:</strong> When holdings overlap exceeds 70%, the funds are largely duplicative — owning both adds little diversification. ';
  h += 'Overlap 40-70% means partial overlap (still meaningful diversification differences). Below 40% = complementary funds. ';
  h += 'Lens verdicts compare quality-adjusted: pick the EXCELLENT/GOOD one if you must choose. Pair funds with LOW overlap for true diversification.';
  h += '</div>';

  h += '</div>';
  el.innerHTML = h;
};
