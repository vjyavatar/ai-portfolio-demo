/* ═══════════════════════════════════════════════════════════════
   CELESYS UI REVAMP v5 — Menu Navigation System
   Loaded AFTER app.min.js — patches tab system into menus
   ═══════════════════════════════════════════════════════════════ */

(function(){
'use strict';

// ═══ 1. BUILD MENU BAR HTML ═══
function buildMenuBar(){
  if(document.getElementById('celesysMenuBar')) return;
  
  var bar = document.createElement('div');
  bar.id = 'celesysMenuBar';
  
  // Ticker info (populated when report loads)
  bar.innerHTML = `
  <div class="menu-ticker" id="menuTicker" style="display:none">
    <span class="mt-sym" id="menuSym"></span>
    <span class="mt-name" id="menuName"></span>
    <span class="mt-live"><span class="ldot"></span> LIVE</span>
  </div>
  
  <div class="cmenu-item" data-group="overview">
    <button class="cmenu-trigger">
      <span class="cmi">⚡</span><span>Overview</span><span class="cma">▾</span>
    </button>
    <div class="cmenu-drop">
      <button onclick="window._menuNav('overview','quick');if(typeof switchSubTab==='function')switchSubTab('overview')"><span class="cmd-icon">📊</span><span class="cmd-label">Summary</span></button>
      <button onclick="window._menuNav('overview','quick');if(typeof switchSubTab==='function')switchSubTab('valuation')"><span class="cmd-icon">💰</span><span class="cmd-label">Valuation</span></button>
      <button onclick="window._menuNav('overview','quick');if(typeof switchSubTab==='function')switchSubTab('technical')"><span class="cmd-icon">📈</span><span class="cmd-label">Technical</span></button>
      <button onclick="window._menuNav('overview','quick');if(typeof switchSubTab==='function')switchSubTab('activity')"><span class="cmd-icon">🏛️</span><span class="cmd-label">Activity</span></button>
      <button onclick="window._menuNav('overview','quick');if(typeof switchSubTab==='function')switchSubTab('risk')"><span class="cmd-icon">⚠️</span><span class="cmd-label">Risk</span></button>
    </div>
  </div>
  
  <div class="cmenu-item" data-group="research">
    <button class="cmenu-trigger">
      <span class="cmi">📊</span><span>Research</span><span class="cma">▾</span>
    </button>
    <div class="cmenu-drop">
      <button onclick="window._menuNav('research','analysis');setTimeout(function(){if(typeof switchAnalysisSubTab==='function')switchAnalysisSubTab('report')},100)"><span class="cmd-icon">🤖</span><span><span class="cmd-label">AI Report</span><br><span class="cmd-desc">Deep research + verdict</span></span></button>
      <button onclick="window._menuNav('research','analysis');setTimeout(function(){if(typeof switchAnalysisSubTab==='function')switchAnalysisSubTab('earnings')},100)"><span class="cmd-icon">📊</span><span><span class="cmd-label">Earnings</span><br><span class="cmd-desc">QoQ & YoY growth trends</span></span></button>
      <button onclick="window._menuNav('research','analysis');setTimeout(function(){if(typeof switchAnalysisSubTab==='function')switchAnalysisSubTab('management')},100)"><span class="cmd-icon">👔</span><span><span class="cmd-label">Management</span><br><span class="cmd-desc">CEO confidence & holders</span></span></button>
      <button onclick="window._menuNav('research','analysis');setTimeout(function(){if(typeof switchAnalysisSubTab==='function')switchAnalysisSubTab('outlook')},100)"><span class="cmd-icon">🔮</span><span><span class="cmd-label">Outlook</span><br><span class="cmd-desc">Bull/bear & price targets</span></span></button>
      <div class="cmd-divider"></div>
      <button onclick="window._menuNav('research','dcf')"><span class="cmd-icon">💰</span><span><span class="cmd-label">DCF Valuation</span><br><span class="cmd-desc">Intrinsic value calculator</span></span></button>
      <button onclick="window._menuNav('research','equity')"><span class="cmd-icon">📋</span><span><span class="cmd-label">Equity Research</span><br><span class="cmd-desc">Research with peers</span></span></button>
      <button onclick="window._menuNav('tools','compare')"><span class="cmd-icon">⚖️</span><span><span class="cmd-label">Compare Stocks</span><br><span class="cmd-desc">Head-to-head analysis</span></span></button>
    </div>
  </div>
  
  <div class="cmenu-item" data-group="decide" id="menuDecide" style="display:none">
    <button class="cmenu-trigger">
      <span class="cmi">🎯</span><span>Decide</span><span class="cma">▾</span>
    </button>
    <div class="cmenu-drop">
      <button onclick="window._menuNav('decide','decision')"><span class="cmd-icon">🎯</span><span><span class="cmd-label">Analyze Stock</span><br><span class="cmd-desc">Visual decision dashboard</span></span></button>
      <button onclick="window._menuNav('decide','toptrades')"><span class="cmd-icon">🔥</span><span><span class="cmd-label">Top Trades</span><br><span class="cmd-desc">Highest conviction picks today</span></span></button>
      <button onclick="window._menuNav('decide','topinvest')"><span class="cmd-icon">💎</span><span><span class="cmd-label">Top Investments</span><br><span class="cmd-desc">Institutional screener</span></span></button>
      <div class="cmd-divider"></div>
      <button onclick="window._menuNav('decide','proscan')"><span class="cmd-icon">🔬</span><span><span class="cmd-label">Pro Scan</span><br><span class="cmd-desc">ROIC, Monte Carlo, Alpha</span></span></button>
      <button onclick="window._menuNav('decide','reports')"><span class="cmd-icon">📊</span><span><span class="cmd-label">Reports</span><br><span class="cmd-desc">Regional intelligence</span></span></button>
      <button onclick="window._menuNav('decide','pms')"><span class="cmd-icon">💼</span><span><span class="cmd-label">Portfolio</span><br><span class="cmd-desc">Upload, analyze, rebalance</span></span></button>
    </div>
  </div>
  
  <div class="cmenu-item" data-group="trading">
    <button class="cmenu-trigger">
      <span class="cmi">⚡</span><span>Trading</span><span class="cma">▾</span>
    </button>
    <div class="cmenu-drop">
      <button onclick="window._menuNav('trading','trades')"><span class="cmd-icon">📡</span><span><span class="cmd-label">Algo Trades</span><br><span class="cmd-desc">5-engine live signals</span></span></button>
      <button onclick="window._menuNav('trading','smarttrades')"><span class="cmd-icon">💡</span><span><span class="cmd-label">Smart Trades</span><br><span class="cmd-desc">AI daily trade ideas</span></span></button>
      <button onclick="window._menuNav('trading','stockintel')"><span class="cmd-icon">🔬</span><span><span class="cmd-label">Stock Intel</span><br><span class="cmd-desc">Complete decision engine</span></span></button>
      <div class="cmd-divider"></div>
      <button onclick="window._menuNav('trading','scanner')"><span class="cmd-icon">📡</span><span><span class="cmd-label">Scanner</span><br><span class="cmd-desc">Heatmap, screener, flow</span></span></button>
      <button onclick="window._menuNav('trading','valreport')"><span class="cmd-icon">📈</span><span><span class="cmd-label">Valuation</span><br><span class="cmd-desc">PE analysis & crash scenarios</span></span></button>
      <button onclick="window._menuNav('trading','backtest')"><span class="cmd-icon">📊</span><span><span class="cmd-label">Backtest</span><br><span class="cmd-desc">Test strategies on history</span></span></button>
      <div class="cmd-divider"></div>
      <button onclick="window._menuNav('trading','journal')"><span class="cmd-icon">📝</span><span><span class="cmd-label">Journal</span><br><span class="cmd-desc">Track trades & P/L</span></span></button>
      <button onclick="window._menuNav('trading','aiassist')"><span class="cmd-icon">🤖</span><span><span class="cmd-label">AI Assistant</span><br><span class="cmd-desc">Ask anything about stocks</span></span></button>
    </div>
  </div>
  
  <div class="cmenu-item" data-group="markets">
    <button class="cmenu-trigger">
      <span class="cmi">📈</span><span>Markets</span><span class="cma">▾</span>
    </button>
    <div class="cmenu-drop">
      <button onclick="window._menuNav('markets','indices')"><span class="cmd-icon">🏆</span><span><span class="cmd-label">Top Performers</span><br><span class="cmd-desc">YTD rankings & leaders</span></span></button>
      <button onclick="window._menuNav('markets','daily')"><span class="cmd-icon">📰</span><span><span class="cmd-label">Market Daily</span><br><span class="cmd-desc">Index analysis & PCR</span></span></button>
      <button onclick="window._menuNav('markets','newsimpact')"><span class="cmd-icon">📰</span><span><span class="cmd-label">News Impact</span><br><span class="cmd-desc">Breaking news analysis</span></span></button>
      <button onclick="window._menuNav('markets','assets')"><span class="cmd-icon">🌐</span><span><span class="cmd-label">Global Assets</span><br><span class="cmd-desc">Oil, gold, yields, crypto</span></span></button>
    </div>
  </div>
  
  <div class="cmenu-item" data-group="tools">
    <button class="cmenu-trigger">
      <span class="cmi">🛠️</span><span>Tools</span><span class="cma">▾</span>
    </button>
    <div class="cmenu-drop">
      <button onclick="window._menuNav('tools','finance')"><span class="cmd-icon">🧮</span><span><span class="cmd-label">Finance Tools</span><br><span class="cmd-desc">SIP, tax, budget calculators</span></span></button>
      <button onclick="window._menuNav('tools','education')"><span class="cmd-icon">🎓</span><span><span class="cmd-label">Education</span><br><span class="cmd-desc">Options, Greeks, strategies</span></span></button>
      <button onclick="window._menuNav('tools','compare')"><span class="cmd-icon">⚖️</span><span><span class="cmd-label">Compare Stocks</span><br><span class="cmd-desc">Side-by-side analysis</span></span></button>
    </div>
  </div>
  
  <div class="menu-actions">
    <button onclick="newSearch()" title="New search">🔍 New</button>
    <button onclick="toggleTheme()" title="Theme">🌙</button>
    <button onclick="exportPDF()" title="Export PDF" style="color:#cd004b">📄</button>
    <button onclick="shareReport('whatsapp')" title="WhatsApp" style="color:#0eb24e">💬</button>
    <button onclick="shareReport('copy')" title="Copy link">🔗</button>
  </div>`;
  
  // Insert right after nav
  var nav = document.querySelector('nav');
  if(nav && nav.nextSibling){
    nav.parentNode.insertBefore(bar, nav.nextSibling);
  } else {
    document.body.prepend(bar);
  }
  
  // Close dropdowns on outside click
  document.addEventListener('click', function(e){
    if(!e.target.closest('.cmenu-item')){
      document.querySelectorAll('.cmenu-item.open').forEach(function(m){m.classList.remove('open')});
    }
  });
  
  // Toggle dropdown on trigger click for items with drops
  document.querySelectorAll('.cmenu-item').forEach(function(item){
    var trigger = item.querySelector('.cmenu-trigger');
    var drop = item.querySelector('.cmenu-drop');
    if(!drop) return; // no dropdown, direct nav
    
    trigger.addEventListener('click', function(e){
      e.stopPropagation();
      var wasOpen = item.classList.contains('open');
      document.querySelectorAll('.cmenu-item.open').forEach(function(m){m.classList.remove('open')});
      if(!wasOpen) item.classList.add('open');
    });
  });
}

// ═══ 2. MENU NAVIGATION — bridges to existing switchTabGroup/switchTab ═══
window._menuNav = function(group, tab){
  // Close all dropdowns
  document.querySelectorAll('.cmenu-item.open').forEach(function(m){m.classList.remove('open')});
  
  // Update menu active state
  document.querySelectorAll('.cmenu-trigger').forEach(function(t){t.classList.remove('active')});
  var activeItem = document.querySelector('.cmenu-item[data-group="'+group+'"]');
  if(activeItem){
    activeItem.querySelector('.cmenu-trigger').classList.add('active');
  }
  
  // Ensure report is visible
  var rpt = document.getElementById('report');
  if(rpt){
    rpt.style.setProperty('display','block','important');
    rpt.classList.add('show');
  }
  
  // Ensure tabContentArea is visible
  var tca = document.getElementById('tabContentArea');
  if(tca) tca.style.display = '';
  
  // Remove premium gate if present
  var eg = document.getElementById('_premGate');
  if(eg) eg.remove();
  
  // Use existing switchTabGroup to set up the group (it builds sub-nav etc)
  // But first patch to prevent it from showing the old sub-nav/tab-bar
  if(typeof switchTabGroup === 'function'){
    switchTabGroup(group);
  }
  
  // Then switch to specific tab
  if(tab && typeof switchTab === 'function'){
    switchTab(tab);
  }
  
  // Force hide old UI elements that switchTabGroup might have shown
  var mtb = document.getElementById('mainTabBar');
  if(mtb){ mtb.style.display = 'none'; }
  var gsn = document.getElementById('groupSubNav');
  if(gsn){ gsn.style.display = 'none'; }
  var sst = document.getElementById('summarySubTabs');
  if(sst){ sst.style.display = 'none'; }
  
  // Scroll to top of report, NOT to bottom
  var navH = 48;
  var menuH = 42;
  var reportEl = document.getElementById('report');
  if(reportEl){
    var rect = reportEl.getBoundingClientRect();
    var scrollTarget = window.pageYOffset + rect.top - navH - menuH - 4;
    if(scrollTarget > 0){
      window.scrollTo({top: scrollTarget, behavior: 'instant'});
    }
  }
};

// ═══ 3. FIX SCROLL-TO-BOTTOM — Patch scrollIntoView calls ═══
// Override the problematic scrollIntoView in switchTab
var _origSwitchTab = window.switchTab;
if(typeof _origSwitchTab === 'function'){
  window.switchTab = function(tab){
    // Call original
    _origSwitchTab(tab);
    
    // Force hide old navigation UI
    var mtb = document.getElementById('mainTabBar');
    if(mtb) mtb.style.display = 'none';
    var gsn = document.getElementById('groupSubNav');
    if(gsn) gsn.style.display = 'none';
    var sst = document.getElementById('summarySubTabs');
    if(sst) sst.style.display = 'none';
    
    // Instead of scrollIntoView (which goes to bottom), scroll to top of content area
    requestAnimationFrame(function(){
      var firstSec = document.querySelector('.sc[data-tab="'+tab+'"]');
      if(firstSec && tab !== 'quick' && tab !== 'analysis'){
        var navH = 48, menuH = 42;
        var rect = firstSec.getBoundingClientRect();
        var target = window.pageYOffset + rect.top - navH - menuH - 8;
        window.scrollTo({top: Math.max(0, target), behavior: 'instant'});
      }
    });
  };
}

// Also patch switchTabGroup to hide old UI
var _origSwitchTabGroup = window.switchTabGroup;
if(typeof _origSwitchTabGroup === 'function'){
  window.switchTabGroup = function(group){
    _origSwitchTabGroup(group);
    
    // Always force-hide old tab bars
    requestAnimationFrame(function(){
      var mtb = document.getElementById('mainTabBar');
      if(mtb) mtb.style.display = 'none';
      var gsn = document.getElementById('groupSubNav');
      if(gsn) gsn.style.display = 'none';
      var sst = document.getElementById('summarySubTabs');
      if(sst) sst.style.display = 'none';
      var ast = document.getElementById('analysisSubTabs');
      if(ast) ast.style.display = 'none';
    });
    
    // Update menu highlights
    document.querySelectorAll('.cmenu-trigger').forEach(function(t){t.classList.remove('active')});
    var activeItem = document.querySelector('.cmenu-item[data-group="'+group+'"]');
    if(activeItem){
      activeItem.querySelector('.cmenu-trigger').classList.add('active');
    }
  };
}

// Patch switchSubTab to fix scroll position
var _origSwitchSubTab = window.switchSubTab;
if(typeof _origSwitchSubTab === 'function'){
  window.switchSubTab = function(sub){
    _origSwitchSubTab(sub);
    // Fix scroll — don't jump to bottom
    requestAnimationFrame(function(){
      var first = document.querySelector('[data-tab="quick"][data-subtab="'+sub+'"]:not([style*="display:none"]):not([style*="display: none"])');
      if(first){
        var navH = 48, menuH = 42;
        var rect = first.getBoundingClientRect();
        var target = window.pageYOffset + rect.top - navH - menuH - 8;
        window.scrollTo({top: Math.max(0, target), behavior: 'instant'});
      }
    });
  };
}

// Patch switchAnalysisSubTab to fix scroll position
var _origSwitchAnalysisSubTab = window.switchAnalysisSubTab;
if(typeof _origSwitchAnalysisSubTab === 'function'){
  window.switchAnalysisSubTab = function(sub){
    _origSwitchAnalysisSubTab(sub);
    requestAnimationFrame(function(){
      var first = document.querySelector('.sc[data-tab="analysis"][data-asub="'+sub+'"]:not([style*="display:none"])');
      if(first){
        var navH = 48, menuH = 42;
        var rect = first.getBoundingClientRect();
        var target = window.pageYOffset + rect.top - navH - menuH - 8;
        window.scrollTo({top: Math.max(0, target), behavior: 'instant'});
      }
    });
  };
}

// ═══ 4. SHOW MENU BAR WHEN REPORT IS READY ═══
function showMenuBar(){
  var bar = document.getElementById('celesysMenuBar');
  if(!bar) buildMenuBar();
  bar = document.getElementById('celesysMenuBar');
  if(bar) bar.style.display = 'flex';
  
  // Populate ticker info
  var sym = document.getElementById('tickerTag');
  var name = document.getElementById('companyName');
  var menuTicker = document.getElementById('menuTicker');
  var menuSym = document.getElementById('menuSym');
  var menuName = document.getElementById('menuName');
  
  if(sym && menuSym){
    menuSym.textContent = sym.textContent || '';
  }
  if(name && menuName){
    menuName.textContent = name.textContent || '';
  }
  if(menuTicker && menuSym && menuSym.textContent){
    menuTicker.style.display = 'flex';
  }
  
  // Show/hide Decide menu based on premium
  var decideMenu = document.getElementById('menuDecide');
  var decideBtn = document.getElementById('tabBtnDecide');
  if(decideMenu){
    decideMenu.style.display = (decideBtn && decideBtn.style.display !== 'none') ? 'flex' : 'none';
  }
  
  // Set Overview as active by default
  var ovItem = document.querySelector('.cmenu-item[data-group="overview"]');
  if(ovItem) ovItem.querySelector('.cmenu-trigger').classList.add('active');
}

// Watch for report becoming visible
var _reportObserver = new MutationObserver(function(mutations){
  var rpt = document.getElementById('report');
  if(rpt && (rpt.classList.contains('show') || rpt.style.display === 'block')){
    showMenuBar();
    
    // Also show it after analysis completes
    // Collapse hero aggressively
    var hero = document.querySelector('.hero');
    if(hero) hero.classList.add('collapsed');
  }
});

// Start observing once DOM is ready
function initMenuSystem(){
  buildMenuBar();
  
  var rpt = document.getElementById('report');
  if(rpt){
    _reportObserver.observe(rpt, {attributes: true, attributeFilter: ['class','style']});
    // If report is already showing
    if(rpt.classList.contains('show')){
      showMenuBar();
    }
  }
  
  // Also listen for the old tab bar becoming visible (signal that report loaded)
  var mtb = document.getElementById('mainTabBar');
  if(mtb){
    var _mtbObs = new MutationObserver(function(){
      if(mtb.style.display === 'flex' || !mtb.classList.contains('tab-bar-hidden')){
        mtb.style.display = 'none'; // force hide
        showMenuBar(); // show our menu instead
      }
    });
    _mtbObs.observe(mtb, {attributes: true, attributeFilter: ['style','class']});
  }
}

// ═══ 5. INIT ═══
if(document.readyState === 'loading'){
  document.addEventListener('DOMContentLoaded', initMenuSystem);
} else {
  initMenuSystem();
}

// Also re-init after a delay (some elements load late)
setTimeout(initMenuSystem, 1000);
setTimeout(function(){
  // Final cleanup — ensure old tabs are hidden
  var mtb = document.getElementById('mainTabBar');
  if(mtb) mtb.style.display = 'none';
  var gsn = document.getElementById('groupSubNav');
  if(gsn) gsn.style.display = 'none';
}, 2000);

})();
