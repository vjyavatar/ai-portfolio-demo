// ═══════════════════════════════════════════════════════════════════════════
// r63.72.12 — 360° Cycle Analysis View
// Renders 15 analytical sections from /api/cycle-analysis
// ═══════════════════════════════════════════════════════════════════════════

window._loadCycleAnalysis = function(ticker, region, marketCap, currentPrice) {
  var el = document.getElementById('deResult');
  if (!el) return;

  ticker = (ticker || window._ddLastSymbol || '').toUpperCase();
  region = region || window._deRegion || 'US';
  marketCap = marketCap || 0;
  currentPrice = currentPrice || 0;

  // Loading state
  el.innerHTML = '<div style="padding:60px 20px;text-align:center;font-family:Inter,sans-serif">' +
    '<div style="font-size:32px;margin-bottom:14px">🔬</div>' +
    '<div style="font-size:14px;font-weight:700;color:#0f172a">Running 360° Cycle Analysis on ' + ticker + '…</div>' +
    '<div style="font-size:11px;color:#94a3b8;margin-top:8px">Computing 15 institutional-quality analytical sections.</div>' +
    '</div>';

  var url = '/api/cycle-analysis?symbol=' + encodeURIComponent(ticker) +
            '&region=' + region +
            '&market_cap=' + (marketCap || 0) +
            '&price=' + (currentPrice || 0);

  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (!d.success) {
        el.innerHTML = '<div style="padding:60px 20px;text-align:center;color:#dc2626;font-family:Inter,sans-serif">' +
          '<div style="font-size:32px;margin-bottom:14px">⚠️</div>' +
          '<div style="font-size:14px;font-weight:700">Cycle Analysis Failed</div>' +
          '<div style="font-size:11px;margin-top:8px;color:#94a3b8">' + (d.error || 'unknown') + '</div>' +
          '<button onclick="loadDeepDD()" style="margin-top:14px;padding:6px 12px;border:1px solid #cbd5e1;background:#fff;border-radius:6px;font-size:11px;cursor:pointer">← Back to Deep DD</button>' +
          '</div>';
        return;
      }
      window._renderCycleAnalysis(d);
    })
    .catch(function(e) {
      el.innerHTML = '<div style="padding:60px 20px;text-align:center;color:#dc2626;font-family:Inter,sans-serif">' +
        '<div style="font-size:32px;margin-bottom:14px">⚠️</div>' +
        '<div style="font-size:14px;font-weight:700">Network Error</div>' +
        '<div style="font-size:11px;margin-top:8px">' + e.message + '</div>' +
        '</div>';
    });
};

window._renderCycleAnalysis = function(d) {
  var el = document.getElementById('deResult');
  if (!el) return;

  var ticker = d.ticker;
  var sections = d.sections || [];
  var synthesis = sections.find(function(s){ return s.section === 'synthesis'; }) || {};

  // Confidence dot helper
  function confDot(conf) {
    var color = conf === 'high' ? '#10b981' :
                conf === 'medium' ? '#f59e0b' :
                conf === 'low' ? '#dc2626' : '#cbd5e1';
    var label = conf === 'high' ? 'HIGH CONFIDENCE' :
                conf === 'medium' ? 'MEDIUM CONFIDENCE' :
                conf === 'low' ? 'LOW CONFIDENCE — data gaps' : 'NO DATA';
    return '<span title="' + label + '" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + color + ';margin-right:6px"></span>' +
           '<span style="font-size:9px;color:#94a3b8;letter-spacing:0.4px;font-weight:600">' + label + '</span>';
  }

  // Badge helper
  function badge(text, color) {
    var bg, fg;
    if (color === 'green') { bg = '#dcfce7'; fg = '#166534'; }
    else if (color === 'blue') { bg = '#dbeafe'; fg = '#1e40af'; }
    else if (color === 'yellow') { bg = '#fef3c7'; fg = '#92400e'; }
    else if (color === 'red') { bg = '#fee2e2'; fg = '#991b1b'; }
    else { bg = '#f1f5f9'; fg = '#475569'; }
    return '<span style="display:inline-block;padding:3px 10px;border-radius:6px;background:' + bg + ';color:' + fg + ';font-size:10px;font-weight:800;letter-spacing:0.4px;font-family:Sora,sans-serif">' + text + '</span>';
  }

  var h = '';
  if (typeof _renderRegionToggle === 'function') {
    h += _renderRegionToggle('loadDeepDD', window._deRegion || 'US');
  }
  h += '<div style="max-width:1200px;margin:0 auto;padding:0 8px;font-family:Inter,sans-serif">';

  // ── Header ─────────────────────────────────────────────────────────────
  h += '<div style="background:linear-gradient(135deg,#1A3A78,#7c3aed);color:#fff;padding:20px 24px;border-radius:12px;margin-bottom:14px">';
  h += '<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">';
  h += '<div>';
  h += '<div style="font-size:11px;letter-spacing:0.8px;font-weight:700;opacity:0.85;font-family:Sora,sans-serif">🔬 360° CYCLE ANALYSIS</div>';
  h += '<h2 style="margin:4px 0 0;font-size:22px;font-weight:900;font-family:Sora,sans-serif">' + ticker + (d.sector ? '  ·  ' + d.sector : '') + '</h2>';
  h += '<div style="font-size:11px;opacity:0.85;margin-top:3px">15 analytical sections · margin cycles · normalized earnings · forward P/E · margin of safety</div>';
  h += '</div>';

  // Overall verdict pill
  if (synthesis.verdict) {
    var vColor = synthesis.verdict_color === 'green' ? '#10b981' :
                 synthesis.verdict_color === 'yellow' ? '#f59e0b' :
                 synthesis.verdict_color === 'red' ? '#dc2626' :
                 '#3b82f6';
    h += '<div style="text-align:right">';
    h += '<div style="font-size:9px;letter-spacing:0.6px;opacity:0.8;font-weight:700">VERDICT</div>';
    h += '<div style="margin-top:4px;padding:8px 14px;background:' + vColor + ';color:#fff;border-radius:8px;font-size:16px;font-weight:900;font-family:Sora,sans-serif">' + synthesis.verdict + '</div>';
    if (synthesis.metrics && typeof synthesis.metrics.net_score === 'number') {
      h += '<div style="font-size:10px;opacity:0.85;margin-top:3px;font-family:IBM Plex Mono,monospace">+' + synthesis.metrics.positive_signals + ' / −' + synthesis.metrics.negative_signals + ' · net ' + (synthesis.metrics.net_score >= 0 ? '+' : '') + synthesis.metrics.net_score + '</div>';
    }
    h += '</div>';
  }
  h += '</div>';

  // Action buttons
  h += '<div style="display:flex;gap:8px;margin-top:14px;border-top:1px solid rgba(255,255,255,0.2);padding-top:12px">';
  h += '<button onclick="loadDeepDD()" style="padding:6px 12px;border:1px solid rgba(255,255,255,0.4);background:transparent;color:#fff;border-radius:6px;font-size:10px;font-weight:700;cursor:pointer;font-family:Sora,sans-serif">← Back to Deep DD</button>';
  h += '<button onclick="window._ddLastSymbol=\'' + ticker + '\';if(window._ddGenerate)window._ddGenerate();" style="padding:6px 12px;border:1px solid rgba(255,255,255,0.4);background:transparent;color:#fff;border-radius:6px;font-size:10px;font-weight:700;cursor:pointer;font-family:Sora,sans-serif">Standard DD Report</button>';
  h += '</div>';
  h += '</div>';

  // ── Synthesis summary at top ───────────────────────────────────────────
  if (synthesis.layman) {
    h += '<div style="background:#fef9c3;border:1px solid #fde68a;border-radius:10px;padding:14px 18px;margin-bottom:14px">';
    h += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">';
    h += '<span style="font-size:14px">💡</span>';
    h += '<span style="font-size:11px;letter-spacing:0.6px;font-weight:800;color:#92400e;font-family:Sora,sans-serif">LAYMAN SUMMARY</span>';
    h += '</div>';
    h += '<div style="font-size:13px;color:#451a03;line-height:1.6">' + synthesis.layman + '</div>';
    h += '</div>';
  }

  // ── 14 sections (excluding synthesis which is shown above) ─────────────
  sections.forEach(function(sec) {
    if (sec.section === 'synthesis') return;

    h += '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;margin-bottom:12px">';

    // Title row
    h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px">';
    h += '<div style="font-size:14px;font-weight:900;color:#0f172a;font-family:Sora,sans-serif">' + (sec.title || sec.section) + '</div>';
    h += '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">';

    // Section-specific status badge
    if (sec.phase) h += badge(sec.phase, sec.phase_color || 'blue');
    if (sec.grade) h += badge(sec.grade, sec.grade_color || 'blue');
    if (sec.discipline) h += badge(sec.discipline, sec.discipline_color || 'blue');
    if (sec.visibility) h += badge(sec.visibility + ' VISIBILITY', sec.visibility === 'HIGH' ? 'green' : sec.visibility === 'LOW' ? 'red' : 'blue');
    if (sec.visibility_label && !sec.visibility) h += badge(sec.visibility_label, sec.visibility_label === 'HIGH' || sec.visibility_label === 'VERY HIGH' ? 'green' : sec.visibility_label === 'LOW' ? 'red' : 'blue');
    if (sec.cycle_position) h += badge(sec.cycle_position, sec.cycle_position === 'AT PEAK' ? 'red' : sec.cycle_position === 'AT TROUGH' ? 'green' : 'blue');
    if (sec.stickiness) h += badge(sec.stickiness + ' STICKINESS', sec.stickiness === 'VERY HIGH' || sec.stickiness === 'HIGH' ? 'green' : sec.stickiness === 'LOW' ? 'red' : 'blue');
    if (sec.ttm_band) h += badge(sec.ttm_band, sec.ttm_band === 'DEEP VALUE' || sec.ttm_band === 'REASONABLE' ? 'green' : sec.ttm_band === 'EXPENSIVE' ? 'red' : 'yellow');
    if (sec.risk_band) h += badge(sec.risk_band, sec.risk_color || 'yellow');
    if (sec.verdict && sec.section !== 'synthesis') {
      var vc = sec.verdict.indexOf('OVERVALUED') >= 0 ? 'red' :
               sec.verdict.indexOf('EXPLOSIVE') >= 0 || sec.verdict.indexOf('UPSIDE') >= 0 ? 'green' : 'blue';
      h += badge(sec.verdict, vc);
    }
    h += confDot(sec.confidence);
    h += '</div>';
    h += '</div>';

    // Narrative
    if (sec.narrative) {
      h += '<div style="font-size:12px;color:#475569;line-height:1.6;margin-bottom:10px">' + sec.narrative + '</div>';
    }

    // Layman section
    if (sec.layman) {
      h += '<div style="background:#f8fafc;border-left:3px solid #7c3aed;padding:10px 14px;border-radius:0 6px 6px 0">';
      h += '<div style="font-size:9px;letter-spacing:0.6px;color:#7c3aed;font-weight:800;margin-bottom:4px;font-family:Sora,sans-serif">PLAIN ENGLISH</div>';
      h += '<div style="font-size:12px;color:#334155;line-height:1.6">' + sec.layman + '</div>';
      h += '</div>';
    }

    // Render selected metrics as a small grid
    if (sec.metrics && Object.keys(sec.metrics).length > 0) {
      h += _renderMetricsGrid(sec.section, sec.metrics);
    }

    h += '</div>';
  });

  // ── Footer disclaimer ──────────────────────────────────────────────────
  h += '<div style="padding:14px 4px;font-size:10px;color:#94a3b8;line-height:1.5">';
  h += '<strong>Methodology:</strong> All 14 sections compute deterministically from structured financial data (income statement, balance sheet, cash flow). ';
  h += 'No LLM hallucination. When data is missing, sections are flagged "LOW CONFIDENCE" rather than fabricated. ';
  h += '<strong>Section 15 (Synthesis)</strong> aggregates signals as a net score; it is one input, not a sole basis for investment decisions. ';
  h += '<strong>Qualitative factors</strong> (management quality, competitive disruption, regulatory shifts, themes like AI demand sustainability) are NOT captured by this analyzer — you must add them in your own judgment.';
  h += '</div>';

  h += '</div>';
  el.innerHTML = h;
};

// ── Metrics grid helper — render key metrics per section ─────────────────
function _renderMetricsGrid(sectionId, m) {
  function fmt(v, decimals) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') {
      var d = decimals !== undefined ? decimals : 2;
      return v.toFixed(d);
    }
    return v;
  }
  function fmtPct(v, decimals) {
    if (v === null || v === undefined) return '—';
    var col = v >= 0 ? '#10b981' : '#dc2626';
    var d = decimals !== undefined ? decimals : 1;
    return '<span style="color:' + col + '">' + (v >= 0 ? '+' : '') + v.toFixed(d) + '%</span>';
  }
  function fmtMoney(v) {
    if (!v && v !== 0) return '—';
    if (Math.abs(v) >= 1e12) return '$' + (v / 1e12).toFixed(1) + 'T';
    if (Math.abs(v) >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
    if (Math.abs(v) >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
    return '$' + Math.round(v).toLocaleString();
  }

  function _box(label, value, sub) {
    var html = '<div style="background:#f8fafc;border-radius:6px;padding:8px 10px;min-width:110px;flex:1">';
    html += '<div style="font-size:8px;color:#94a3b8;font-weight:700;letter-spacing:0.5px;text-transform:uppercase">' + label + '</div>';
    html += '<div style="font-size:13px;font-weight:800;color:#0f172a;font-family:IBM Plex Mono,monospace;margin-top:3px">' + value + '</div>';
    if (sub) html += '<div style="font-size:9px;color:#94a3b8;margin-top:1px">' + sub + '</div>';
    html += '</div>';
    return html;
  }

  var boxes = '';

  if (sectionId === 'profit_margins') {
    boxes += _box('Current OM', fmt(m.current_operating_margin) + '%', '5Y range: ' + fmt(m.trough_operating_margin) + '–' + fmt(m.peak_operating_margin) + '%');
    boxes += _box('Cycle Pos', fmt(m.cycle_position_pct, 0) + '%', 'of 5Y range');
    boxes += _box('Below Peak', fmt(m.pct_below_peak, 1) + '%', '');
    boxes += _box('Gross Margin', fmt(m.current_gross_margin) + '%', 'peak ' + fmt(m.peak_gross_margin) + '%');
  } else if (sectionId === 'normalized_earnings') {
    boxes += _box('TTM EPS', '$' + fmt(m.current_eps), '');
    boxes += _box('Normalized EPS', '$' + fmt(m.normalized_eps), 'trimmed-mean');
    boxes += _box('Over/Under', fmtPct(m.over_under_pct), 'vs normalized');
    boxes += _box('P/E (TTM)', fmt(m.pe_on_current, 1) + '×', '');
    boxes += _box('P/E Normalized', fmt(m.pe_on_normalized, 1) + '×', 'cycle-adj');
  } else if (sectionId === 'balance_sheet') {
    boxes += _box('Total Debt', fmtMoney(m.total_debt), '');
    boxes += _box('Cash', fmtMoney(m.cash), '');
    boxes += _box('Net Debt', fmtMoney(m.net_debt), '');
    if (m.debt_to_equity_pct !== null) boxes += _box('D/E', fmt(m.debt_to_equity_pct, 0) + '%', '');
    if (m.net_debt_to_ebitda !== null) boxes += _box('ND/EBITDA', fmt(m.net_debt_to_ebitda, 2) + '×', '');
  } else if (sectionId === 'revenue_visibility') {
    boxes += _box('5Y Avg Growth', fmtPct(m.avg_5y_growth_pct, 1), '');
    boxes += _box('Growth Std', fmt(m.growth_std_pp, 1) + 'pp', '');
    boxes += _box('Consistency', m.consistency, '');
  } else if (sectionId === 'supply_discipline') {
    boxes += _box('Current Capex/Rev', fmt(m.current_capex_pct_revenue, 1) + '%', '');
    boxes += _box('5Y Avg', fmt(m.avg_5y_capex_pct, 1) + '%', '');
    boxes += _box('Peak', fmt(m.peak_capex_pct, 1) + '%', '');
    boxes += _box('vs Avg', fmt(m.vs_average_pp, 1) + 'pp', '');
  } else if (sectionId === 'forward_pe') {
    boxes += _box('Price', '$' + fmt(m.current_price), '');
    boxes += _box('P/E TTM', fmt(m.pe_ttm, 1) + '×', '');
    if (m.pe_on_normalized !== null) boxes += _box('P/E Normalized', fmt(m.pe_on_normalized, 1) + '×', 'cycle-adj');
    boxes += _box('TTM EPS', '$' + fmt(m.current_eps), '');
  } else if (sectionId === 'revenue_estimation') {
    boxes += _box('Current Rev', fmtMoney(m.current_revenue), '');
    boxes += _box('1Y Base', fmtMoney(m.rev_1y_base), fmtPct(m.base_growth_pct, 1));
    boxes += _box('1Y Bull', fmtMoney(m.rev_1y_bull), fmtPct(m.bull_growth_pct, 1));
    boxes += _box('1Y Bear', fmtMoney(m.rev_1y_bear), fmtPct(m.bear_growth_pct, 1));
    boxes += _box('3Y Base', fmtMoney(m.rev_3y_base), '');
  } else if (sectionId === 'operating_profit_walk') {
    boxes += _box('Prior OP', fmtMoney(m.operating_profit_prior), 'OM ' + fmt(m.operating_margin_prior) + '%');
    boxes += _box('Current OP', fmtMoney(m.operating_profit_current), 'OM ' + fmt(m.operating_margin_current) + '%');
    boxes += _box('Volume Δ', fmtMoney(m.volume_contribution), fmt(m.volume_pct, 0) + '%');
    boxes += _box('Margin Δ', fmtMoney(m.margin_contribution), fmt(m.margin_pct_contribution, 0) + '%');
  } else if (sectionId === 'normalized_target') {
    boxes += _box('Bull EPS', '$' + fmt(m.bull_eps), 'peak');
    boxes += _box('Normalized EPS', '$' + fmt(m.normalized_eps), 'trimmed mean');
    boxes += _box('Bear EPS', '$' + fmt(m.bear_eps), 'trough');
    boxes += _box('17× Bull', '$' + fmt(m.bull_target_17x, 0), fmtPct(m.upside_bull_pct, 0));
    boxes += _box('17× Base', '$' + fmt(m.base_target_17x, 0), fmtPct(m.upside_base_pct, 0));
    boxes += _box('17× Bear', '$' + fmt(m.bear_target_17x, 0), fmtPct(m.downside_bear_pct, 0));
  } else if (sectionId === 'margin_of_safety') {
    boxes += _box('Trough EPS', '$' + fmt(m.trough_eps), '');
    boxes += _box('10× Trough', '$' + fmt(m.stress_target_10x, 0), fmtPct(m.downside_10x_pct, 0));
    boxes += _box('12× Trough', '$' + fmt(m.stress_target_12x, 0), fmtPct(m.downside_12x_pct, 0));
    boxes += _box('15× Trough', '$' + fmt(m.stress_target_15x, 0), fmtPct(m.downside_15x_pct, 0));
  } else if (sectionId === 'customer_stickiness') {
    boxes += _box('GM Avg', fmt(m.gross_margin_avg_pct, 1) + '%', '');
    boxes += _box('GM Std', fmt(m.gross_margin_std_pp, 2) + 'pp', '');
    boxes += _box('GM CV', fmt(m.gross_margin_cv, 3), 'lower = more stable');
  }

  if (!boxes) return '';
  return '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">' + boxes + '</div>';
}
