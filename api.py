/* ═══════════════════════════════════════════════════════════════
   CELESYS PREMIUM — INSTITUTIONAL WHITE + NAVY THEME (v2 CLEAN)
   Targets: colors, typography, polish. Leaves layout to index.html.
   NO [onclick] nuclear rules. NO conflicting sticky overrides.
   ═══════════════════════════════════════════════════════════════ */

/* ─── 1. CSS VARIABLES ─── */
:root {
  --bg: #fafbfc; --bg2: #f1f5f9; --bg3: #e9ecef;
  --surface: #fff; --glass: rgba(255,255,255,.97);
  --border: #e2e5ea; --border2: #ced4da;
  --blue: #1A3A78; --blue2: #1e40af;
  --cyan: #0891b2; --teal: #0d9488;
  --green: #059669; --green2: #047857;
  --amber: #d97706; --red: #dc2626; --purple: #7c3aed;
  --text: #0A1628; --text2: #374151; --text3: #6b7280;
  --mono: 'IBM Plex Mono', monospace;
  --gdb-h: 0px;
}
body {
  background: var(--bg); color: var(--text);
  -webkit-font-smoothing: antialiased;
}

/* ─── 2. DARK THEME KILL (force white everywhere) ─── */
[data-theme="dark"] {
  --bg: #fafbfc; --bg2: #f1f5f9; --bg3: #e9ecef;
  --surface: #fff; --border: #e2e5ea; --border2: #ced4da;
  --text: #0A1628; --text2: #374151; --text3: #6b7280;
}
[data-theme="dark"] body { background: #fafbfc !important; color: #0A1628 !important; }
[data-theme="dark"] .hero { background: linear-gradient(180deg, #f8faff, #fafbfc) !important; }
[data-theme="dark"] .hero::before { background: radial-gradient(ellipse at 50% 0%, rgba(26,58,120,.04), transparent 60%) !important; }
[data-theme="dark"] input,
[data-theme="dark"] select { background: #fff !important; color: #0A1628 !important; border-color: #e2e5ea !important; }
[data-theme="dark"] .sc,
[data-theme="dark"] .mcard,
[data-theme="dark"] .ccard,
[data-theme="dark"] .icard,
[data-theme="dark"] .feat-card { background: #fff !important; border-color: #e2e5ea !important; }
[data-theme="dark"] details { background: #fff; border-color: #e2e5ea; }
[data-theme="dark"] thead th { background: #f8fafc !important; color: #6b7280 !important; }
[data-theme="dark"] table th { color: #6b7280 !important; }
[data-theme="dark"] table td { color: #0A1628 !important; border-color: #f1f3f5 !important; }
[data-theme="dark"] .qpick,
[data-theme="dark"] .hb { background: #fff !important; border-color: #e2e5ea !important; color: #4a4a4a !important; }
[data-theme="dark"] .ac { background: #fff !important; border-color: #e2e5ea !important; }
[data-theme="dark"] .ipt { background: #fafbfc !important; border-color: #e2e5ea !important; color: #0A1628 !important; }
[data-theme="dark"] .sticky-tagline { background: rgba(255,255,255,.98) !important; }
[data-theme="dark"] #reportHeader { background: #fff !important; border-color: #e2e5ea !important; }
[data-theme="dark"] .gridbg { background: #fafbfc !important; }
[data-theme="dark"] nav { background: #0A1628 !important; }
[data-theme="dark"] .tab-bar { background: #fff !important; border-bottom-color: #e2e5ea !important; }
[data-theme="dark"] .tab-btn { color: #6b7280 !important; background: transparent !important; }
[data-theme="dark"] .tab-btn:hover:not(.active) { background: #f8fafc !important; }
[data-theme="dark"] .tab-btn.active { color: #1A3A78 !important; background: rgba(26,58,120,.04) !important; border-bottom-color: #1A3A78 !important; }


/* ═══════════════════════════════════════════════
   3. NAV BAR — Institutional Navy (colors only)
   ═══════════════════════════════════════════════ */
nav {
  background: #0A1628 !important;
  border-bottom: 1px solid rgba(255,255,255,.06) !important;
  box-shadow: 0 2px 12px rgba(10,22,40,.15) !important;
}
.nname { color: #fff !important; }
.nname span { color: #60a5fa !important; }
.ntag { color: rgba(255,255,255,.35) !important; }
.nlogo {
  background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
  color: #fff !important;
  border: 1px solid rgba(255,255,255,.15) !important;
  box-shadow: 0 2px 8px rgba(37,99,235,.35) !important;
}
.npill { background: rgba(255,255,255,.06) !important; border: 1px solid rgba(255,255,255,.1) !important; color: rgba(255,255,255,.6) !important; }
.npill .v { color: #60a5fa !important; }
.nlive { background: rgba(16,185,129,.08) !important; border: 1px solid rgba(16,185,129,.2) !important; color: #34d399 !important; }
.ldot { background: #34d399 !important; box-shadow: 0 0 8px rgba(52,211,153,.6) !important; }
.nbtn-theme {
  border: 1px solid rgba(255,255,255,.1) !important;
  background: rgba(255,255,255,.05) !important;
  color: rgba(255,255,255,.6) !important;
  display: flex !important;
  opacity: 1 !important;
  visibility: visible !important;
}
.nbtn-theme:hover { background: rgba(255,255,255,.1) !important; color: #fff !important; }


/* ═══════════════════════════════════════════════
   4. GLOBAL TICKER — Navy
   ═══════════════════════════════════════════════ */
.gticker { background: #0A1628 !important; border-bottom: 1px solid rgba(255,255,255,.06) !important; }
.gticker .trow, .gticker .nrow { background: #0A1628 !important; }
.gticker .nrow { border-top: 1px solid rgba(255,255,255,.04) !important; }
.gticker .ti { border-right: 1px solid rgba(255,255,255,.06) !important; color: rgba(255,255,255,.6) !important; }
.gticker .ti .tn { color: rgba(255,255,255,.45) !important; }
.gticker .tp { color: #fff !important; }
.gticker .tup { color: #34d399 !important; }
.gticker .tdn { color: #f87171 !important; }
.gticker .ni { color: rgba(255,255,255,.5) !important; }
.gticker .ni strong { color: rgba(255,255,255,.8) !important; }


/* ═══════════════════════════════════════════════
   5. MAIN TAB BAR — Clean underline style (NOT filled navy blocks)
   ═══════════════════════════════════════════════ */
.tab-bar {
  background: #fff !important;
  border-bottom: 2px solid #e2e5ea !important;
  box-shadow: 0 1px 4px rgba(0,0,0,.03) !important;
}
.tab-btn {
  color: #6b7280 !important;
  background: transparent !important;
  font-weight: 700 !important;
  letter-spacing: .2px !important;
  border-bottom: 3px solid transparent !important;
  border-radius: 0 !important;
  transition: all .2s ease !important;
  box-shadow: none !important;
}
.tab-btn .tab-icon { background: transparent !important; }
.tab-btn:hover:not(.active) {
  background: #f8fafc !important;
  color: #1A3A78 !important;
}
.tab-btn.active {
  color: #1A3A78 !important;
  background: rgba(26,58,120,.04) !important;
  border-bottom: 3px solid #1A3A78 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  font-weight: 800 !important;
}
.tab-btn.active .tab-icon {
  background: rgba(26,58,120,.1) !important;
  color: #1A3A78 !important;
}
.tab-btn[data-color].active {
  color: #1A3A78 !important;
  border-bottom-color: #1A3A78 !important;
  background: rgba(26,58,120,.04) !important;
  box-shadow: none !important;
  border-radius: 0 !important;
}
.tab-btn[data-color].active .tab-icon {
  background: rgba(26,58,120,.1) !important;
  color: #1A3A78 !important;
}


/* ═══════════════════════════════════════════════
   6. GROUP SUB-NAV (#groupSubNav)
   ═══════════════════════════════════════════════ */
#groupSubNav {
  background: #fff !important;
  border-bottom: 1px solid #f1f3f5 !important;
}
#groupSubNav .sub-tab-btn,
#groupSubNav button:not([onclick*="switchDEMode"]):not([onclick*="Region"]) {
  background: #f8fafc;
  border: 1px solid #e2e5ea;
  color: #6b7280;
  font-weight: 600;
  border-radius: 100px;
  padding: 6px 14px;
  font-size: 11px;
  transition: all .2s;
}
#groupSubNav .sub-tab-btn:hover:not(.active),
#groupSubNav button:not(.active):hover {
  background: #f1f5f9;
  color: #1A3A78;
  border-color: #c7d2fe;
}
#groupSubNav .sub-tab-btn.active,
#groupSubNav button.active {
  background: #1A3A78 !important;
  color: #fff !important;
  border-color: #1A3A78 !important;
  box-shadow: 0 2px 8px rgba(26,58,120,.2);
}


/* ═══════════════════════════════════════════════
   7. SUMMARY SUB-TABS (Overview / Valuation / Technical / Activity / Risk)
   Clean pill style — NOT fat dark blobs
   ═══════════════════════════════════════════════ */
#summarySubTabs {
  background: #fff !important;
  border-bottom: 1px solid #f1f3f5 !important;
}
#summarySubTabs .stab {
  background: #f8fafc !important;
  border: 1.5px solid #e2e5ea !important;
  color: #6b7280 !important;
  font-weight: 600 !important;
  font-size: 11px !important;
  padding: 7px 16px !important;
  border-radius: 100px !important;
  transition: all .2s !important;
  cursor: pointer;
  white-space: nowrap;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
}
#summarySubTabs .stab:hover:not(.active) {
  background: #f1f5f9 !important;
  color: #1A3A78 !important;
  border-color: #c7d2fe !important;
}
#summarySubTabs .stab.active {
  background: #1A3A78 !important;
  color: #fff !important;
  border-color: #1A3A78 !important;
  box-shadow: 0 2px 8px rgba(26,58,120,.2) !important;
  font-weight: 700 !important;
}

/* Generic .stab outside #summarySubTabs */
.stab {
  background: #f8fafc !important;
  border: 1.5px solid #e2e5ea !important;
  color: #6b7280 !important;
  font-weight: 600 !important;
  border-radius: 100px !important;
  transition: all .2s !important;
}
.stab:hover:not(.active) {
  background: #f1f5f9 !important;
  color: #1A3A78 !important;
  border-color: #c7d2fe !important;
}
.stab.active {
  background: #1A3A78 !important;
  color: #fff !important;
  border-color: #1A3A78 !important;
  box-shadow: 0 2px 8px rgba(26,58,120,.2) !important;
}


/* ═══════════════════════════════════════════════
   8. ALGO BUTTONS (.algo-btn) + SUB-TAB BUTTONS
   ═══════════════════════════════════════════════ */
.algo-btn {
  background: #f8fafc !important;
  border: 1px solid #e2e5ea !important;
  color: #6b7280 !important;
  font-weight: 600 !important;
  border-radius: 8px !important;
  transition: all .2s !important;
}
.algo-btn:hover:not(.active) {
  background: #f1f5f9 !important;
  color: #1A3A78 !important;
  border-color: #c7d2fe !important;
}
.algo-btn.active {
  background: linear-gradient(135deg, #1A3A78, #1e40af) !important;
  color: #fff !important;
  border-color: transparent !important;
  box-shadow: 0 2px 10px rgba(26,58,120,.25) !important;
}
.sub-tab-btn {
  background: #f8fafc !important;
  border: 1px solid #e2e5ea !important;
  color: #6b7280 !important;
  font-weight: 600 !important;
  transition: all .2s !important;
}
.sub-tab-btn:hover:not(.active) {
  background: #f1f5f9 !important;
  color: #1A3A78 !important;
  border-color: #c7d2fe !important;
}
.sub-tab-btn.active {
  background: #1A3A78 !important;
  color: #fff !important;
  border-color: #1A3A78 !important;
  box-shadow: 0 2px 8px rgba(26,58,120,.2) !important;
}


/* ═══════════════════════════════════════════════
   9. REGION TOGGLE BUTTONS (India / USA)
   These use INLINE styles for active/inactive state.
   We only ensure consistent sizing — DO NOT override bg/color
   (the JS sets background inline on click).
   ═══════════════════════════════════════════════ */
#algoRegIN, #algoRegUS,
#scanRegIN, #scanRegUS,
#stRegIN, #stRegUS,
#deRegIN, #deRegUS,
#ttRegIN, #ttRegUS,
#tiRegIN, #tiRegUS,
#idxRegIN, #idxRegUS,
#erBtnIN, #erBtnUS,
#valRegIN, #valRegUS,
#aiRegIN, #aiRegUS,
#siRegIN, #siRegUS {
  min-width: 70px !important;
  text-align: center !important;
  transition: all .2s !important;
  cursor: pointer !important;
  font-family: Sora, sans-serif !important;
  font-weight: 800 !important;
  font-size: 11px !important;
  padding: 6px 16px !important;
}
/* PMS region toggles now use divs — no CSS needed */


/* ═══════════════════════════════════════════════
   10. PRIMARY BUTTON & INPUT
   ═══════════════════════════════════════════════ */
.btn {
  background: linear-gradient(135deg, #1A3A78, #1e40af) !important;
  color: #fff !important;
  box-shadow: 0 4px 16px rgba(26,58,120,.25) !important;
}
.btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #0f2a5e, #1A3A78) !important;
  box-shadow: 0 6px 20px rgba(26,58,120,.35) !important;
}
input[type="text"], input[type="email"], input[type="search"],
input[type="number"], textarea, select {
  background: var(--bg) !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
}
.ipt:focus {
  border-color: #1A3A78 !important;
  box-shadow: 0 0 0 3px rgba(26,58,120,.08), 0 4px 12px rgba(26,58,120,.06) !important;
}
.icard { background: #fff !important; border-color: #e2e5ea !important; }
.ac.show { box-shadow: 0 12px 36px rgba(26,58,120,.1) !important; border-color: #c7d2fe !important; }


/* ═══════════════════════════════════════════════
   11. SECTION CARDS (.sc) + REPORT HEADER
   ═══════════════════════════════════════════════ */
.sc {
  background: #fff !important;
  border-color: #e2e5ea !important;
  box-shadow: 0 1px 6px rgba(0,0,0,.03) !important;
  border-radius: 14px !important;
}
.sc:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,.06) !important;
}
.sc:hover .st { color: #1A3A78 !important; }
.mcard, .ccard { background: #fff !important; border-color: #e2e5ea !important; }
.mcard:hover { border-color: #1A3A78 !important; box-shadow: 0 2px 8px rgba(0,47,108,.08) !important; }
#reportHeader {
  background: #fff !important;
  border-bottom: 1px solid #e2e5ea !important;
  box-shadow: 0 1px 4px rgba(0,0,0,.03) !important;
}


/* ═══════════════════════════════════════════════
   12. CROSS-MARKET SCANNER & SIMILAR STOCKS BUTTONS
   ═══════════════════════════════════════════════ */
button[id="xmScanBtn"],
button[id="xmSameScanBtn"],
button[onclick*="runCrossMarketScan"] {
  background: linear-gradient(135deg, #1A3A78, #1e40af) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 14px !important;
  padding: 14px 18px !important;
  cursor: pointer !important;
  font-family: Sora, sans-serif !important;
  box-shadow: 0 4px 16px rgba(26,58,120,.2) !important;
  flex: 1 !important;
  min-width: 180px !important;
}
button[id="xmScanBtn"]:hover,
button[id="xmSameScanBtn"]:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 24px rgba(26,58,120,.3) !important;
}
button[id="xmScanBtn"] div,
button[id="xmSameScanBtn"] div,
button[onclick*="runCrossMarketScan"] div {
  color: #fff !important;
}
button[onclick*="_openProScan"],
button[onclick*="_runV3Context"] {
  background: linear-gradient(135deg, #1A3A78, #1e40af) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 14px !important;
  cursor: pointer !important;
  box-shadow: 0 4px 16px rgba(26,58,120,.25) !important;
}
button[onclick*="_openProScan"] div,
button[onclick*="_runV3Context"] div {
  color: #fff !important;
}


/* ═══════════════════════════════════════════════
   13. HIDE GLOBAL DECISION BAR (causes overlap)
   ═══════════════════════════════════════════════ */
#globalDecisionBar {
  display: none !important;
  height: 0 !important;
}


/* ═══════════════════════════════════════════════
   14. STICKY NAVIGATION STACK
   Base positioning handled by index.html via CSS vars.
   Only override backgrounds and z-index here.
   ═══════════════════════════════════════════════ */
.tab-bar {
  background: #fff !important;
  z-index: 200 !important;
}
#groupSubNav {
  background: #fff !important;
  z-index: 190 !important;
}
#summarySubTabs {
  background: #fff !important;
  z-index: 190 !important;
}
#reportHeader {
  background: #fff !important;
  z-index: 210 !important;
}


/* ═══════════════════════════════════════════════
   15. DETAILS / ACCORDION + TABLES + MISC
   ═══════════════════════════════════════════════ */
details { background: #fff; border-color: #e2e5ea; box-shadow: 0 1px 4px rgba(0,0,0,.03); }
details[open] { box-shadow: 0 4px 20px rgba(26,58,120,.05) !important; border-color: #c7d2fe !important; }
details summary:hover { background: rgba(26,58,120,.02) !important; }
details > summary { list-style: none !important; }
details > summary::-webkit-details-marker { display: none !important; }
details > summary::after { content: '▼'; font-size: 10px; color: #94a3b8; transition: transform .2s; }
details[open] > summary::after { transform: rotate(180deg); }

thead th { text-transform: uppercase !important; letter-spacing: .5px !important; font-size: 9px !important; background: #f8fafc !important; color: #6b7280 !important; }
table { border-collapse: separate !important; border-spacing: 0 !important; }

.dc-verdict-text { font-size: 52px !important; font-weight: 900 !important; letter-spacing: -2px !important; }

.hb { background: #fff !important; border: 1px solid #e2e5ea !important; color: #4a4a4a !important; }
.hb:hover { border-color: #c7d2fe !important; box-shadow: 0 2px 8px rgba(26,58,120,.06) !important; }
.qpick { font-weight: 700 !important; }
.feat-card::after { background: linear-gradient(90deg, transparent, #1A3A78, transparent) !important; }
.feat-card:hover { border-color: #1A3A78 !important; }
.sbar { border-radius: 12px !important; }
.sbar.info { background: rgba(26,58,120,.03) !important; border-color: rgba(26,58,120,.1) !important; color: #1A3A78 !important; }
.sbar.success { background: rgba(5,150,105,.04) !important; border-color: rgba(5,150,105,.15) !important; }
.sbar.error { background: rgba(220,38,38,.04) !important; border-color: rgba(220,38,38,.15) !important; }

a { color: #1A3A78; }
a:hover { color: #0f2a5e; }
* { text-rendering: optimizeLegibility !important; }
html { scroll-behavior: smooth !important; }

/* ═══════════════════════════════════════════════
   20. GLOBAL BUTTON NORMALIZATION
   Ensures every button on the site has consistent
   font, cursor, transition, and border-radius.
   Individual classes override specific properties.
   ═══════════════════════════════════════════════ */
button {
  font-family: 'Sora', sans-serif;
  cursor: pointer;
  transition: all .2s ease;
  -webkit-tap-highlight-color: transparent;
  border-radius: 8px;
}
button:active {
  transform: scale(.96);
}
/* Toolbar action buttons (New, PDF, Share, etc) */
#actionToolbar button {
  border-radius: 6px !important;
  font-family: Sora, sans-serif !important;
  font-size: 10px !important;
  font-weight: 600 !important;
  padding: 3px 8px !important;
}
/* Screener preset filter pills — tinted outline style */
button[onclick*="runScreener"] {
  border-radius: 6px !important;
  font-family: Sora, sans-serif !important;
  font-size: 9px !important;
  font-weight: 700 !important;
  transition: all .2s !important;
}
button[onclick*="runScreener"]:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0,0,0,.08);
}

/* Focus & accessibility */
button:focus-visible, input:focus-visible, a:focus-visible {
  outline: 2px solid #1A3A78 !important;
  outline-offset: 2px !important;
}

/* Smooth transitions */
.sc, .mcard, .ccard, .icard, .feat-card, .stab, .sub-tab-btn, .algo-btn, .qpick, .btt {
  transition: all .25s cubic-bezier(.4, 0, .2, 1) !important;
}
canvas { border-radius: 8px !important; }
[style*="JetBrains Mono"], [style*="font-family:var(--mono)"] {
  font-variant-numeric: tabular-nums !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(26,58,120,.12); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(26,58,120,.25); }

.sub-nav { backdrop-filter: blur(16px) !important; -webkit-backdrop-filter: blur(16px) !important; }

.shimmer, .skel {
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%) !important;
  background-size: 200% 100% !important;
}
@keyframes shimmer { 0% { background-position: -400px 0; } 100% { background-position: 400px 0; } }


/* ═══════════════════════════════════════════════
   16. PMS / DE SECTION
   ═══════════════════════════════════════════════ */
#deResult table th { background: #f8fafc !important; color: #6b7280 !important; font-size: 9px !important; }
#deResult table td { padding: 10px !important; border-bottom: 1px solid #f1f3f5 !important; }
#deResult table tr:hover td { background: #f8fafc !important; }
#deResult > div:empty { display: none !important; }
#instTrading:empty, #instCharts:empty, #traderGapFills:empty, #decideGapFills:empty,
#pmsChartsPack:empty, #pmsGapFills:empty, #pmsDecisionBarEl:empty { display: none !important; }

/* Tighten Decide tab controls */
#deModeTrader, #deModeInvestor { padding: 6px 16px !important; font-size: 10px !important; }
#deRegIN, #deRegUS { padding: 5px 12px !important; font-size: 9px !important; }


/* ═══════════════════════════════════════════════
   MOBILE RESPONSIVE
   ═══════════════════════════════════════════════ */
@media (max-width: 640px) {
  nav { padding: 0 14px !important; height: 48px !important; }
  .nname { font-size: 12px !important; }
  .ntag { display: none !important; }
  .npill { display: none !important; }
  .nlive { padding: 4px 8px !important; font-size: 8px !important; }
  .nbtn-theme { width: 26px !important; height: 26px !important; font-size: 12px !important; }
  .nlogo { width: 24px !important; height: 24px !important; font-size: 11px !important; }

  /* Sticky stack — let CSS vars from index.html handle tops */
  .tab-bar {
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch !important;
    scrollbar-width: none !important;
  }
  .tab-bar::-webkit-scrollbar { display: none !important; }
  .tab-btn { padding: 10px 12px !important; font-size: 10px !important; white-space: nowrap !important; }

  #groupSubNav {
    padding: 6px 10px !important;
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
  }
  #groupSubNav::-webkit-scrollbar { display: none; }
  #groupSubNav .sub-tab-btn,
  #groupSubNav button {
    font-size: 9px !important;
    padding: 5px 12px !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
  }

  #summarySubTabs {
    padding: 6px 10px !important;
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    gap: 6px !important;
  }
  #summarySubTabs::-webkit-scrollbar { display: none; }
  #summarySubTabs .stab {
    font-size: 10px !important;
    padding: 6px 12px !important;
    flex-shrink: 0 !important;
  }

  .hero { padding: 28px 16px 14px !important; }
  .hero h1 { font-size: 22px !important; }
  .hero-sub { font-size: 12px !important; }
  .isection { padding: 0 12px 16px !important; }
  .icard { padding: 16px !important; }
  .irow { grid-template-columns: 1fr !important; gap: 8px !important; }
  .btn { padding: 12px !important; font-size: 12px !important; }
  #report { padding: 0 10px 24px !important; }
  .sc { border-radius: 10px !important; margin-bottom: 10px !important; }
  .sbody { padding: 0 14px 14px !important; }
  .algo-btn { font-size: 9px !important; padding: 4px 10px !important; }
  .dc { border-radius: 14px !important; }
  .dc-hero { padding: 20px 16px 14px !important; }
  .dc-verdict-text { font-size: 32px !important; }
  table { font-size: 10px !important; }
  .deep-modal-panel { border-radius: 16px 16px 0 0 !important; }
  .btt { bottom: 16px !important; right: 16px !important; }
  .qpick { font-size: 9px !important; padding: 4px 10px !important; }
  details > summary { padding: 12px 14px !important; font-size: 11px !important; }
  [style*="display:grid;grid-template-columns:repeat(4"] { grid-template-columns: repeat(2, 1fr) !important; }
  [style*="display:grid;grid-template-columns:repeat(5"] { grid-template-columns: repeat(2, 1fr) !important; }
}

@media (max-width: 480px) {
  nav { height: 40px !important; padding: 0 8px !important; }
  .nlive { display: none; }
  .nname { font-size: 11px !important; }
  .tab-btn { font-size: 8px !important; padding: 6px 6px !important; }
  .tab-btn .tab-icon { width: 14px !important; height: 14px !important; font-size: 9px !important; }
  #summarySubTabs .stab { font-size: 9px !important; padding: 5px 10px !important; }
  .hero h1 { font-size: 17px !important; }
  .mgrid { grid-template-columns: 1fr !important; }
}

/* Tablet */
@media (min-width: 641px) and (max-width: 1024px) {
  nav { padding: 0 20px !important; }
  .isection { max-width: 600px !important; }
  #report { max-width: 900px !important; }
}

/* Large screens */
@media (min-width: 1400px) {
  #report { max-width: 1120px !important; }
}

/* Print */
@media print {
  nav, .gticker, .sticky-tagline, .btt, footer, .tab-bar, #groupSubNav, .nbtn-theme,
  #premiumPricing, #floatingUpgradeCTA { display: none !important; }
  body { padding-top: 0 !important; margin-top: 0 !important; background: #fff !important; }
  .sc { break-inside: avoid !important; box-shadow: none !important; }
  #report { padding: 0 !important; max-width: 100% !important; }
}

/* Premium Pricing responsive */
@media (max-width: 640px) {
  #premiumPricing > div:nth-child(2) { grid-template-columns: 1fr !important; }
  #premiumPricing h2 { font-size: 20px !important; }
}

/* ═══ AUTOFILL FIX — prevent browser from resizing email input ═══ */
input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus {
  -webkit-box-shadow: 0 0 0 30px #fff inset !important;
  -webkit-text-fill-color: #0A1628 !important;
  border: 1.5px solid #e2e5ea !important;
  font-size: 14px !important;
}
.ipt {
  box-sizing: border-box !important;
}

/* ═══ ZERO GAP between sticky nav layers ═══ */
#reportHeader {
  margin: 0 !important;
  padding-top: 4px !important;
  padding-bottom: 4px !important;
  flex-wrap: nowrap !important;
  overflow-x: auto !important;
  scrollbar-width: none !important;
}
#reportHeader::-webkit-scrollbar { display: none !important; }
.tab-bar {
  margin: 0 !important;
  border-top: none !important;
}
#groupSubNav {
  margin: 0 !important;
  border-top: none !important;
}
#summarySubTabs {
  margin: 0 !important;
  border-top: none !important;
}

/* ═══ Segmented region buttons — flat edges inside container ═══ */
div[style*="overflow:hidden"] > button,
div[style*="overflow: hidden"] > button {
  border-radius: 0 !important;
}

/* ═══ Mobile touch targets ═══ */
@media (max-width: 640px) {
  button, [onclick], .algo-btn, .stab, .sub-tab-btn {
    min-height: 32px !important;
  }
  #actionToolbar button, #actionToolbar div[onclick] {
    min-height: 28px !important;
    padding: 4px 8px !important;
  }
}
