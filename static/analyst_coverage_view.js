// ═══════════════════════════════════════════════════════════════════════════
// r63.72.30 — Analyst Coverage Explorer
//   Top-level filterable feed of analyst ratings + a per-ticker panel
//   (the panel is also embedded inside the Deep DD report)
// ═══════════════════════════════════════════════════════════════════════════

// Filter state — persists across re-renders
window._analystFilters = {
  days_back:     30,
  action_filter: 'all',
  sector_filter: '',
  ticker_filter: '',
  firm_filter:   '',
  sort_by:       'date_desc',
  limit:         200,
};

window.loadAnalystCoverage = function(forceReg) {
  var el = document.getElementById('deResult');
  if (!el) return;
  var reg = forceReg || window._deRegion || 'US';
  window._deRegion = reg;

  el.innerHTML =
    (typeof _renderRegionToggle === 'function' ? _renderRegionToggle('loadAnalystCoverage', reg) : '') +
    '<div style="max-width:1400px;margin:0 auto;padding:0 8px;font-family:Inter,sans-serif">' +
      _renderAnalystHeader() +
      _renderAnalystFilters() +
      '<div id="analystResultArea" style="padding:24px;text-align:center;color:#94a3b8;font-size:11px">Loading analyst coverage…</div>' +
    '</div>';

  _fetchAnalystCoverage();
};

function _renderAnalystHeader() {
  var h = '<div style="background:linear-gradient(135deg,#1A3A78,#7c3aed);color:#fff;padding:18px 22px;border-radius:12px;margin-bottom:14px">';
  h += '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">';
  h += '<div>';
  h += '<div style="font-size:11px;letter-spacing:0.8px;font-weight:700;opacity:0.85;font-family:Sora,sans-serif">📊 ANALYST COVERAGE EXPLORER</div>';
  h += '<div style="font-size:18px;font-weight:900;margin-top:2px;font-family:Sora,sans-serif">Recent Ratings · Upgrades · Price Targets</div>';
  h += '<div style="font-size:11px;margin-top:6px;opacity:0.85;line-height:1.4">Searchable feed of analyst actions across the tracked universe. Filter by date, sector, action type, ticker, or firm.</div>';
  h += '</div>';
  h += '<button onclick="_forceAnalystRefresh()" style="padding:8px 16px;border:1px solid rgba(255,255,255,0.3);background:rgba(255,255,255,0.1);color:#fff;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;font-family:Sora,sans-serif">↻ FORCE REFRESH (slow)</button>';
  h += '</div></div>';
  return h;
}

function _renderAnalystFilters() {
  var f = window._analystFilters;
  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;margin-bottom:14px">';

  // Filter row 1: action + date range + sort
  h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:10px">';

  // Date range
  h += '<div>';
  h += '<div style="font-size:9px;font-weight:800;letter-spacing:0.5px;color:#64748b;margin-bottom:4px;font-family:Sora,sans-serif">DATE RANGE</div>';
  h += '<select id="analystFilterDays" onchange="window._analystFilters.days_back=parseInt(this.value);_fetchAnalystCoverage()" style="width:100%;padding:7px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:11px;background:#fff;font-family:Inter,sans-serif;cursor:pointer">';
  [['1', 'Last 24h'], ['7', 'Last 7 days'], ['30', 'Last 30 days'], ['90', 'Last 90 days'], ['365', 'Last year']].forEach(function(opt) {
    h += '<option value="' + opt[0] + '"' + (parseInt(opt[0]) === f.days_back ? ' selected' : '') + '>' + opt[1] + '</option>';
  });
  h += '</select></div>';

  // Action filter
  h += '<div>';
  h += '<div style="font-size:9px;font-weight:800;letter-spacing:0.5px;color:#64748b;margin-bottom:4px;font-family:Sora,sans-serif">ACTION</div>';
  h += '<select id="analystFilterAction" onchange="window._analystFilters.action_filter=this.value;_fetchAnalystCoverage()" style="width:100%;padding:7px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:11px;background:#fff;font-family:Inter,sans-serif;cursor:pointer">';
  [['all', 'All actions'], ['up', '↑ Upgrades only'], ['down', '↓ Downgrades only'], ['init', '★ Initiations'], ['reit', '= Reiterates']].forEach(function(opt) {
    h += '<option value="' + opt[0] + '"' + (opt[0] === f.action_filter ? ' selected' : '') + '>' + opt[1] + '</option>';
  });
  h += '</select></div>';

  // Sector filter
  h += '<div>';
  h += '<div style="font-size:9px;font-weight:800;letter-spacing:0.5px;color:#64748b;margin-bottom:4px;font-family:Sora,sans-serif">SECTOR</div>';
  h += '<select id="analystFilterSector" onchange="window._analystFilters.sector_filter=this.value;_fetchAnalystCoverage()" style="width:100%;padding:7px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:11px;background:#fff;font-family:Inter,sans-serif;cursor:pointer">';
  h += '<option value=""' + (f.sector_filter === '' ? ' selected' : '') + '>All sectors</option>';
  (window._analystSectorsCache || []).forEach(function(s) {
    h += '<option value="' + s + '"' + (s === f.sector_filter ? ' selected' : '') + '>' + s + '</option>';
  });
  h += '</select></div>';

  // Ticker filter
  h += '<div>';
  h += '<div style="font-size:9px;font-weight:800;letter-spacing:0.5px;color:#64748b;margin-bottom:4px;font-family:Sora,sans-serif">TICKER</div>';
  h += '<input id="analystFilterTicker" type="text" placeholder="e.g. NVDA" value="' + (f.ticker_filter || '') + '" oninput="window._analystFilters.ticker_filter=this.value.toUpperCase();clearTimeout(window._analystTickerTimeout);window._analystTickerTimeout=setTimeout(_fetchAnalystCoverage, 350)" style="width:100%;padding:7px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:11px;background:#fff;font-family:Inter,sans-serif;text-transform:uppercase">';
  h += '</div>';

  // Firm filter
  h += '<div>';
  h += '<div style="font-size:9px;font-weight:800;letter-spacing:0.5px;color:#64748b;margin-bottom:4px;font-family:Sora,sans-serif">FIRM</div>';
  h += '<input id="analystFilterFirm" type="text" placeholder="e.g. Goldman" value="' + (f.firm_filter || '') + '" oninput="window._analystFilters.firm_filter=this.value;clearTimeout(window._analystFirmTimeout);window._analystFirmTimeout=setTimeout(_fetchAnalystCoverage, 350)" style="width:100%;padding:7px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:11px;background:#fff;font-family:Inter,sans-serif">';
  h += '</div>';

  // Sort
  h += '<div>';
  h += '<div style="font-size:9px;font-weight:800;letter-spacing:0.5px;color:#64748b;margin-bottom:4px;font-family:Sora,sans-serif">SORT BY</div>';
  h += '<select id="analystFilterSort" onchange="window._analystFilters.sort_by=this.value;_fetchAnalystCoverage()" style="width:100%;padding:7px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:11px;background:#fff;font-family:Inter,sans-serif;cursor:pointer">';
  [['date_desc', 'Newest first'], ['date_asc', 'Oldest first'], ['ticker', 'Ticker A-Z']].forEach(function(opt) {
    h += '<option value="' + opt[0] + '"' + (opt[0] === f.sort_by ? ' selected' : '') + '>' + opt[1] + '</option>';
  });
  h += '</select></div>';

  h += '</div>';

  // Clear button row
  h += '<div style="display:flex;gap:8px;align-items:center">';
  h += '<button onclick="_clearAnalystFilters()" style="padding:5px 12px;border:1px solid #e2e8f0;background:#fff;border-radius:5px;font-size:10px;font-weight:700;cursor:pointer;color:#64748b;font-family:Inter,sans-serif">CLEAR ALL FILTERS</button>';
  h += '<span id="analystResultMeta" style="font-size:10px;color:#94a3b8;margin-left:auto;font-family:IBM Plex Mono,monospace"></span>';
  h += '</div>';

  h += '</div>';
  return h;
}

window._clearAnalystFilters = function() {
  window._analystFilters = {
    days_back: 30, action_filter: 'all', sector_filter: '',
    ticker_filter: '', firm_filter: '', sort_by: 'date_desc', limit: 200,
  };
  loadAnalystCoverage();
};

window._forceAnalystRefresh = function() {
  var btn = event && event.target;
  if (btn) { btn.disabled = true; btn.innerHTML = '⏳ Refreshing…'; }
  var reg = window._deRegion || 'US';
  fetch('/api/analyst-coverage-refresh?region=' + reg, {method: 'POST'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (btn) { btn.disabled = false; btn.innerHTML = '↻ FORCE REFRESH (slow)'; }
      _fetchAnalystCoverage();
    })
    .catch(function(e){
      if (btn) { btn.disabled = false; btn.innerHTML = '↻ FORCE REFRESH (slow)'; }
      alert('Refresh failed: ' + e.message);
    });
};

window._fetchAnalystCoverage = function() {
  var area = document.getElementById('analystResultArea');
  if (!area) return;

  var reg = window._deRegion || 'US';
  var f = window._analystFilters;
  var params = new URLSearchParams({
    region:        reg,
    days_back:     String(f.days_back),
    action_filter: f.action_filter,
    sector_filter: f.sector_filter,
    ticker_filter: f.ticker_filter,
    firm_filter:   f.firm_filter,
    sort_by:       f.sort_by,
    limit:         String(f.limit),
  });

  area.innerHTML = '<div style="padding:40px 20px;text-align:center;color:#94a3b8;font-size:12px">⏳ Fetching analyst actions…</div>';

  fetch('/api/analyst-coverage?' + params.toString())
    .then(function(r){ return r.json(); })
    .then(function(d){ _renderAnalystCoverageResults(d); })
    .catch(function(e){
      area.innerHTML = '<div style="padding:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;color:#7f1d1d;font-size:11px">⚠ Failed: ' + (e.message || 'network') + '</div>';
    });
};

function _renderAnalystCoverageResults(d) {
  var area = document.getElementById('analystResultArea');
  if (!area) return;

  if (!d || !d.success) {
    area.innerHTML = '<div style="padding:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;color:#7f1d1d;font-size:11px">⚠ ' + ((d && d.error) || 'Unknown error') + '</div>';
    return;
  }

  // Cache the sectors list for the filter dropdown (only updates filter dropdown next render)
  if (d.sectors && d.sectors.length > 0) {
    window._analystSectorsCache = d.sectors;
  }

  // Refresh meta line
  var metaEl = document.getElementById('analystResultMeta');
  if (metaEl) {
    var ageMin = d.refresh_age_sec ? Math.round(d.refresh_age_sec / 60) : null;
    var metaParts = [
      d.total_filtered + ' of ' + d.total_in_store + ' actions',
      'Universe ' + d.universe_size + ' tickers',
    ];
    if (ageMin !== null) metaParts.push('Refreshed ' + ageMin + 'm ago');
    if (d.store_warming) metaParts.push('⚠ Cache warming, retry in 30s');
    metaEl.textContent = metaParts.join(' · ');
  }

  var h = '';

  // Data-coverage banner (always show)
  if (d.data_note) {
    h += '<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:10px;color:#1e40af;line-height:1.5">' +
         'ℹ ' + d.data_note +
         '</div>';
  }

  // Empty state — store warming OR no results after filter
  if (!d.actions || d.actions.length === 0) {
    if (d.store_warming) {
      h += '<div style="padding:60px 20px;text-align:center;background:#fff;border:1px solid #e2e8f0;border-radius:10px">';
      h += '<div style="font-size:32px;margin-bottom:10px">⏳</div>';
      h += '<div style="font-size:14px;font-weight:800;color:#0f172a;font-family:Sora,sans-serif">Cache warming up</div>';
      h += '<div style="font-size:11px;color:#64748b;margin-top:6px;line-height:1.5">First-time load fetches ratings for ~100 tracked tickers from yfinance.<br>Background prefetch in progress · retry in 20-40 seconds.</div>';
      h += '<button onclick="_fetchAnalystCoverage()" style="margin-top:14px;padding:8px 16px;border:1px solid #1A3A78;background:#1A3A78;color:#fff;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;font-family:Sora,sans-serif">↻ CHECK AGAIN</button>';
      h += '</div>';
    } else {
      h += '<div style="padding:40px 20px;text-align:center;background:#fff;border:1px solid #e2e8f0;border-radius:10px;color:#94a3b8;font-size:12px">';
      h += 'No analyst actions match your filters. Try widening the date range or clearing the action filter.';
      h += '</div>';
    }
    area.innerHTML = h;
    return;
  }

  // Render table
  h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">';
  h += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-family:Inter,sans-serif;font-size:11px">';

  // Header
  h += '<thead><tr style="background:#f8fafc;border-bottom:1px solid #e2e8f0">';
  ['DATE', 'TICKER', 'SECTOR', 'ACTION', 'FIRM', 'FROM → TO', 'TARGET', 'UPSIDE'].forEach(function(col) {
    h += '<th style="padding:8px 10px;text-align:left;font-size:9px;font-weight:800;letter-spacing:0.5px;color:#64748b;font-family:Sora,sans-serif;white-space:nowrap">' + col + '</th>';
  });
  h += '</tr></thead><tbody>';

  d.actions.forEach(function(a, idx) {
    var rowBg = idx % 2 === 0 ? '#fff' : '#fafbfc';
    var am = a.action_meta || {color: '#94a3b8', icon: '?', label: 'OTHER'};

    h += '<tr style="background:' + rowBg + ';border-bottom:1px solid #f1f5f9" onclick="loadDeepDDFor(\'' + a.ticker + '\', \'' + (window._deRegion || 'US') + '\')" onmouseover="this.style.background=\'#eff6ff\'" onmouseout="this.style.background=\'' + rowBg + '\'" style="cursor:pointer">';
    h += '<td style="padding:7px 10px;font-family:IBM Plex Mono,monospace;color:#64748b;white-space:nowrap">' + a.date + '</td>';
    h += '<td style="padding:7px 10px;font-weight:800;color:#1A3A78;font-family:IBM Plex Mono,monospace">' + a.ticker + '</td>';
    h += '<td style="padding:7px 10px;color:#475569;font-size:10px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (a.sector || '—') + '</td>';
    h += '<td style="padding:7px 10px;white-space:nowrap"><span style="background:' + am.color + ';color:#fff;padding:2px 7px;border-radius:4px;font-size:9px;font-weight:800;letter-spacing:0.3px;font-family:Sora,sans-serif">' + am.icon + ' ' + am.label + '</span></td>';
    h += '<td style="padding:7px 10px;color:#334155;font-weight:600;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (a.firm || '—') + '</td>';

    // From → To grade
    var fromG = a.from_grade || '—';
    var toG = a.to_grade || '—';
    h += '<td style="padding:7px 10px;font-size:10px;color:#475569;white-space:nowrap">';
    if (fromG !== '—' && toG !== '—') {
      h += '<span style="color:#94a3b8">' + fromG + '</span>';
      h += ' <span style="color:' + am.color + '">→</span> ';
      h += '<span style="color:' + am.color + ';font-weight:700">' + toG + '</span>';
    } else if (toG !== '—') {
      h += '<span style="color:' + am.color + ';font-weight:700">' + toG + '</span>';
    } else {
      h += '<span style="color:#cbd5e1">—</span>';
    }
    h += '</td>';

    // Target (current consensus, not the per-action target since yfinance doesn't reliably expose that)
    h += '<td style="padding:7px 10px;font-family:IBM Plex Mono,monospace;color:#0f172a;white-space:nowrap">';
    h += a.target_mean != null ? '$' + Number(a.target_mean).toFixed(2) : '<span style="color:#cbd5e1">—</span>';
    h += '</td>';

    // Upside
    h += '<td style="padding:7px 10px;font-family:IBM Plex Mono,monospace;font-weight:700;white-space:nowrap">';
    if (a.upside_pct !== null && a.upside_pct !== undefined) {
      var upColor = a.upside_pct > 5 ? '#10b981' : (a.upside_pct < -5 ? '#dc2626' : '#94a3b8');
      h += '<span style="color:' + upColor + '">' + (a.upside_pct >= 0 ? '+' : '') + a.upside_pct.toFixed(1) + '%</span>';
    } else {
      h += '<span style="color:#cbd5e1">—</span>';
    }
    h += '</td>';

    h += '</tr>';
  });
  h += '</tbody></table></div></div>';

  // Footer hint
  h += '<div style="margin-top:8px;font-size:9px;color:#94a3b8;text-align:right;font-style:italic">';
  h += 'Click any row to open the Deep DD report for that ticker. Target = current consensus mean target. Upside = vs current price.';
  h += '</div>';

  area.innerHTML = h;
}

// Helper: open DD for ticker (used from row click)
window.loadDeepDDFor = function(symbol, region) {
  if (!symbol) return;
  window._deRegion = region || 'US';
  if (typeof showTab === 'function') {
    showTab('deepdd');
    setTimeout(function(){
      var input = document.getElementById('ddSymbol');
      if (input) {
        input.value = symbol;
        if (typeof submitDeepDD === 'function') submitDeepDD();
        else if (typeof loadDeepDD === 'function') loadDeepDD();
      }
    }, 200);
  }
};

// ─── PER-TICKER PANEL (embedded in DD report) ─────────────────────────────

window._loadAnalystCoverageTicker = function(symbol, region) {
  symbol = (symbol || window._ddLastSymbol || '').toUpperCase();
  region = region || window._deRegion || 'US';
  if (!symbol) return;
  var el = document.getElementById('ddAnalystCoverageCard');
  if (!el) return;

  el.innerHTML = '<div style="padding:20px;text-align:center;font-size:11px;color:#94a3b8;font-family:Inter,sans-serif">Loading analyst coverage…</div>';

  fetch('/api/analyst-coverage-ticker?symbol=' + encodeURIComponent(symbol) + '&region=' + encodeURIComponent(region))
    .then(function(r){ return r.json(); })
    .then(function(d){ _renderAnalystCoverageTicker(d); })
    .catch(function(e){
      el.innerHTML = '<div style="padding:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;font-family:Inter,sans-serif;font-size:11px;color:#7f1d1d">⚠ Analyst coverage unavailable: ' + (e.message || 'network') + '</div>';
    });
};

function _renderAnalystCoverageTicker(d) {
  var el = document.getElementById('ddAnalystCoverageCard');
  if (!el) return;

  if (!d || !d.success) {
    el.innerHTML = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin-bottom:14px;font-family:Inter,sans-serif;font-size:11px;color:#94a3b8">📊 Analyst Coverage — ' + ((d && d.reason) || 'no data') + '</div>';
    return;
  }

  var h = '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin-bottom:16px;font-family:Inter,sans-serif">';

  // Header
  h += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap">';
  h += '<span style="font-size:18px">📊</span>';
  h += '<span style="font-size:13px;font-weight:800;color:#1A3A78;letter-spacing:0.3px;font-family:Sora,sans-serif">Analyst Coverage</span>';
  if (d.consensus_label) {
    h += '<span style="background:' + d.consensus_color + ';color:#fff;padding:3px 10px;border-radius:4px;font-size:10px;font-weight:800;letter-spacing:0.4px;font-family:Sora,sans-serif">' + d.consensus_label + '</span>';
  }
  h += '<span style="margin-left:auto;font-size:10px;color:#64748b;font-family:IBM Plex Mono,monospace">' + d.ticker + '</span>';
  h += '</div>';

  // Target box
  h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:12px">';

  h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px">';
  h += '<div style="font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.4px;margin-bottom:4px;font-family:Sora,sans-serif">CONSENSUS TARGET</div>';
  h += '<div style="font-size:20px;font-weight:900;color:#1A3A78;font-family:IBM Plex Mono,monospace;line-height:1">' + (d.target_mean != null ? '$' + Number(d.target_mean).toFixed(2) : '—') + '</div>';
  h += '<div style="font-size:9px;color:#94a3b8;margin-top:3px">' + (d.target_count != null ? d.target_count + ' analysts' : '') + '</div>';
  h += '</div>';

  h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px">';
  h += '<div style="font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.4px;margin-bottom:4px;font-family:Sora,sans-serif">TARGET RANGE</div>';
  if (d.target_low != null && d.target_high != null) {
    h += '<div style="font-size:13px;color:#0f172a;font-family:IBM Plex Mono,monospace;font-weight:700">$' + Number(d.target_low).toFixed(2) + ' — $' + Number(d.target_high).toFixed(2) + '</div>';
    var spread = Number(d.target_high) - Number(d.target_low);
    h += '<div style="font-size:9px;color:#94a3b8;margin-top:3px">Spread $' + spread.toFixed(2) + '</div>';
  } else {
    h += '<div style="font-size:12px;color:#cbd5e1">—</div>';
  }
  h += '</div>';

  h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px">';
  h += '<div style="font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.4px;margin-bottom:4px;font-family:Sora,sans-serif">IMPLIED UPSIDE</div>';
  if (d.upside_pct != null) {
    var col = d.upside_pct > 5 ? '#10b981' : (d.upside_pct < -5 ? '#dc2626' : '#94a3b8');
    h += '<div style="font-size:20px;font-weight:900;color:' + col + ';font-family:IBM Plex Mono,monospace;line-height:1">' + (d.upside_pct >= 0 ? '+' : '') + d.upside_pct.toFixed(1) + '%</div>';
    h += '<div style="font-size:9px;color:#94a3b8;margin-top:3px">vs current $' + (d.current_price ? Number(d.current_price).toFixed(2) : '—') + '</div>';
  } else {
    h += '<div style="font-size:12px;color:#cbd5e1">—</div>';
  }
  h += '</div>';

  h += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px">';
  h += '<div style="font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.4px;margin-bottom:4px;font-family:Sora,sans-serif">RECENT ACTIONS</div>';
  h += '<div style="font-size:20px;font-weight:900;color:#7c3aed;font-family:IBM Plex Mono,monospace;line-height:1">' + (d.action_count || 0) + '</div>';
  h += '<div style="font-size:9px;color:#94a3b8;margin-top:3px">past 90 days</div>';
  h += '</div>';

  h += '</div>';

  // Recent actions
  if (d.actions && d.actions.length > 0) {
    h += '<div style="margin-top:8px">';
    h += '<div style="font-size:9px;letter-spacing:0.5px;color:#64748b;font-weight:800;margin-bottom:6px;font-family:Sora,sans-serif">RECENT ACTIONS</div>';
    h += '<div style="max-height:240px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:6px">';
    d.actions.slice(0, 12).forEach(function(a) {
      var am = a.action_meta || {color: '#94a3b8', icon: '?', label: 'OTHER'};
      h += '<div style="display:flex;align-items:center;gap:8px;padding:7px 10px;border-bottom:1px solid #f1f5f9;font-size:10px">';
      h += '<span style="color:#94a3b8;font-family:IBM Plex Mono,monospace;width:80px;flex-shrink:0">' + a.date + '</span>';
      h += '<span style="background:' + am.color + ';color:#fff;padding:1px 6px;border-radius:3px;font-size:8px;font-weight:800;letter-spacing:0.3px;flex-shrink:0">' + am.icon + ' ' + am.label + '</span>';
      h += '<span style="color:#334155;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600">' + (a.firm || '—') + '</span>';
      if (a.from_grade && a.to_grade) {
        h += '<span style="color:#94a3b8;font-size:9px">' + a.from_grade + ' → </span>';
        h += '<span style="color:' + am.color + ';font-size:9px;font-weight:700">' + a.to_grade + '</span>';
      } else if (a.to_grade) {
        h += '<span style="color:' + am.color + ';font-size:9px;font-weight:700">' + a.to_grade + '</span>';
      }
      h += '</div>';
    });
    h += '</div>';
    if (d.actions.length > 12) {
      h += '<div style="font-size:9px;color:#94a3b8;margin-top:4px;text-align:right">Showing 12 of ' + d.actions.length + ' recent actions</div>';
    }
    h += '</div>';
  } else {
    h += '<div style="padding:12px;text-align:center;color:#94a3b8;font-size:11px">No recent rating actions in the past 90 days</div>';
  }

  h += '</div>';
  el.innerHTML = h;
}
