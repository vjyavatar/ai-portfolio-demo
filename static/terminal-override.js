/* ═══════════════════════════════════════════════════════════════════════════════
   CELESYS TERMINAL — Menu ↔ SubMenu Merger (JS Override)
   ═══════════════════════════════════════════════════════════════════════════════
   
   PURPOSE:
   1. Merge the 5 Overview sub-tabs (Overview, Valuation, Technical, Activity, Risk)
      from #summarySubTabs INTO #groupSubNav when the "Overview" menu is active.
   2. Hide clutter elements that CSS `display:none` can't catch (inline styles).
   3. Adjust CSS custom properties on the fly for sticky positioning.
   
   CONSTRAINT: 
   - Cannot replace #reportHeader, #mainTabBar, or #groupSubNav (JS manages them).
   - Can only HOOK into the existing switchTabGroup / switchSubTab functions.
   
   ═══════════════════════════════════════════════════════════════════════════════ */

(function() {
  'use strict';

  // ─── Wait for app.js to fully load ───
  var _ready = setInterval(function() {
    if (typeof window.switchTabGroup !== 'function') return;
    clearInterval(_ready);
    initTerminalOverride();
  }, 100);

  function initTerminalOverride() {

    // ═══════════════════════════════════════════
    // §1  CLUTTER REMOVAL (runtime)
    // ═══════════════════════════════════════════
    // Some elements have inline `display` set by JS — CSS can't fight !important inline.
    // We remove them once or on mutation.
    
    function hideClutter() {
      var ids = ['siteWatermark', 'globalDecisionBar', 'pwaInstallBanner', 'stickyTag'];
      ids.forEach(function(id) {
        var el = document.getElementById(id);
        if (el) {
          el.style.setProperty('display', 'none', 'important');
          el.style.setProperty('height', '0', 'important');
          el.style.setProperty('visibility', 'hidden', 'important');
        }
      });
      // Hide hero extras / SEO / pricing by class or ID
      ['heroExtras', 'seoHome', 'premiumPricing'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.style.setProperty('display', 'none', 'important');
      });
    }
    
    hideClutter();
    // Re-hide after analysis loads (JS may re-show some elements)
    var _obs = new MutationObserver(function() { hideClutter(); });
    _obs.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style'] });
    // BUG 14: Extend to 90s (pwaInstallBanner created at 30s)
    setTimeout(function() { _obs.disconnect(); }, 90000);

    // BUG 8: Patch _updateGlobalBar to prevent it from showing globalDecisionBar
    var _origUpdateBar = window._updateGlobalBar;
    if (typeof _origUpdateBar === 'function') {
      window._updateGlobalBar = function() {
        _origUpdateBar.apply(this, arguments);
        var gdb = document.getElementById('globalDecisionBar');
        if (gdb) {
          gdb.style.setProperty('display', 'none', 'important');
          gdb.style.setProperty('height', '0', 'important');
        }
        document.documentElement.style.setProperty('--gdb-h', '0px');
      };
    }
    // Also force --gdb-h on load
    document.documentElement.style.setProperty('--gdb-h', '0px');


    // ═══════════════════════════════════════════
    // §2  TICKER HEIGHT — Set CSS var when ticker shows
    // ═══════════════════════════════════════════
    function syncTickerHeight() {
      var ticker = document.getElementById('gticker');
      if (ticker && ticker.style.display !== 'none' && ticker.offsetHeight > 0) {
        // BUG 11: Measure actual height (news row is hidden via CSS, so only trow counts)
        var h = ticker.offsetHeight;
        document.documentElement.style.setProperty('--t-ticker', h + 'px');
        document.documentElement.style.setProperty('--ticker-h', h + 'px');
      } else {
        document.documentElement.style.setProperty('--t-ticker', '0px');
        document.documentElement.style.setProperty('--ticker-h', '0px');
      }
    }
    syncTickerHeight();
    var _tickerObs = new MutationObserver(syncTickerHeight);
    var _tickerEl = document.getElementById('gticker');
    if (_tickerEl) _tickerObs.observe(_tickerEl, { attributes: true, attributeFilter: ['style'] });


    // ═══════════════════════════════════════════
    // §3  HOOK: switchTabGroup → Merge overview sub-tabs
    // ═══════════════════════════════════════════
    // 
    // When overview group is active, the existing code sets 
    // groupSubNav to show only "Summary" (1 tab → hidden).
    // We intercept AFTER the original runs, and inject the 
    // 5 overview sub-tab buttons into groupSubNav.
    
    var _origSwitch = window.switchTabGroup;
    
    window.switchTabGroup = function(group) {
      // Call original first — it builds groupSubNav
      _origSwitch.apply(this, arguments);
      
      // After original runs, patch the submenu for overview
      if (group === 'overview') {
        injectOverviewSubTabs();
      }
      
      // Always force-hide #summarySubTabs (CSS backup)
      var sst = document.getElementById('summarySubTabs');
      if (sst) sst.style.setProperty('display', 'none', 'important');
    };


    // ═══════════════════════════════════════════
    // §4  INJECT OVERVIEW SUB-TABS INTO GROUPSUBNAV
    // ═══════════════════════════════════════════
    // 
    // Maps the 5 stab buttons from #summarySubTabs into 
    // sub-tab-btn pills inside #groupSubNav.
    // Each calls switchSubTab() just like the originals.
    
    var OVERVIEW_SUBS = [
      { id: 'overview',   label: '📊 Overview',   key: 'stOverview'  },
      { id: 'valuation',  label: '💰 Valuation',  key: 'stValuation' },
      { id: 'technical',  label: '📈 Technical',  key: 'stTechnical' },
      { id: 'activity',   label: '🏢 Activity',   key: 'stActivity'  },
      { id: 'risk',       label: '⚠ Risk',        key: 'stRisk'      }
    ];
    
    function injectOverviewSubTabs() {
      var subNav = document.getElementById('groupSubNav');
      if (!subNav) return;
      
      // Build the submenu HTML
      var h = '';
      var activeSub = window._activeSubTab || 'overview';
      
      OVERVIEW_SUBS.forEach(function(sub) {
        var isActive = (sub.id === activeSub);
        h += '<button onclick="window._termSwitchOverviewSub(\'' + sub.id + '\')" '
           + 'class="sub-tab-btn' + (isActive ? ' active' : '') + '" '
           + 'data-overview-sub="' + sub.id + '" '
           + 'style="padding:0 10px;border-radius:4px;font-size:9px;font-weight:' 
           + (isActive ? '700' : '600') + ';border:1px solid '
           + (isActive ? '#3B82F6' : 'rgba(255,255,255,.06)') + ';background:'
           + (isActive ? '#3B82F6' : 'transparent') + ';color:'
           + (isActive ? '#fff' : '#64748B') 
           + ';cursor:pointer;font-family:Plus Jakarta Sans,sans-serif;transition:all .12s;white-space:nowrap;height:20px;line-height:18px;display:inline-flex;align-items:center">'
           + sub.label + '</button>';
      });
      
      subNav.innerHTML = h;
      subNav.style.display = 'flex';
    }
    
    // Global handler for overview sub-tab clicks
    window._termSwitchOverviewSub = function(subId) {
      // Call the original switchSubTab
      if (typeof window.switchSubTab === 'function') {
        window.switchSubTab(subId);
      }
      window._activeSubTab = subId;
      
      // Update active state in groupSubNav
      var subNav = document.getElementById('groupSubNav');
      if (!subNav) return;
      
      subNav.querySelectorAll('.sub-tab-btn').forEach(function(btn) {
        var isThis = btn.getAttribute('data-overview-sub') === subId;
        btn.classList.toggle('active', isThis);
        btn.style.background = isThis ? '#3B82F6' : 'transparent';
        btn.style.color = isThis ? '#fff' : '#64748B';
        btn.style.borderColor = isThis ? '#3B82F6' : 'rgba(255,255,255,.06)';
        btn.style.fontWeight = isThis ? '700' : '600';
      });
    };


    // ═══════════════════════════════════════════
    // §5  HOOK: switchSubTab → keep groupSubNav in sync
    // ═══════════════════════════════════════════
    var _origSubSwitch = window.switchSubTab;
    
    window.switchSubTab = function(sub) {
      _origSubSwitch.apply(this, arguments);
      window._activeSubTab = sub;
      
      // If we're on overview, update groupSubNav active states
      if (window._activeGroup === 'overview') {
        var subNav = document.getElementById('groupSubNav');
        if (subNav) {
          subNav.querySelectorAll('.sub-tab-btn').forEach(function(btn) {
            var isThis = btn.getAttribute('data-overview-sub') === sub;
            btn.classList.toggle('active', isThis);
            btn.style.background = isThis ? '#3B82F6' : 'transparent';
            btn.style.color = isThis ? '#fff' : '#64748B';
            btn.style.borderColor = isThis ? '#3B82F6' : 'rgba(255,255,255,.06)';
            btn.style.fontWeight = isThis ? '700' : '600';
          });
        }
      }
      
      // Always hide #summarySubTabs
      var sst = document.getElementById('summarySubTabs');
      if (sst) sst.style.setProperty('display', 'none', 'important');
    };


    // ═══════════════════════════════════════════
    // §6  HERO COLLAPSE — Always collapsed post-analysis
    // ═══════════════════════════════════════════
    // Watch for report becoming visible and collapse hero
    var _heroObs = new MutationObserver(function() {
      var report = document.getElementById('report');
      if (report && report.classList.contains('show')) {
        var hero = document.querySelector('.hero');
        if (hero) hero.classList.add('collapsed');
      }
    });
    var _rpt = document.getElementById('report');
    if (_rpt) _heroObs.observe(_rpt, { attributes: true, attributeFilter: ['class', 'style'] });


    // ═══════════════════════════════════════════
    // §7  INITIAL STATE — If report already loaded
    // ═══════════════════════════════════════════
    if (_rpt && _rpt.classList.contains('show')) {
      var hero = document.querySelector('.hero');
      if (hero) hero.classList.add('collapsed');
      
      // If currently on overview, inject subtabs
      if (window._activeGroup === 'overview') {
        setTimeout(injectOverviewSubTabs, 50);
      }
    }


    // ═══════════════════════════════════════════
    // §8  FORCE CSS VARS — Override syncNavVars from premium-override.js
    // ═══════════════════════════════════════════
    // premium-override.js syncNavVars() measures DOM and sets --nav-h etc.
    // Since our CSS forces height !important, the measured values ARE our values.
    // But we also need --gdb-h to stay 0 and --t-* to stay in sync.
    function forceTerminalVars() {
      var root = document.documentElement;
      root.style.setProperty('--gdb-h', '0px');
      // Keep --t-* vars in sync with measured --*-h vars
      var navH = root.style.getPropertyValue('--nav-h') || '36px';
      var rhH = root.style.getPropertyValue('--rh-h') || '30px';
      var tabH = root.style.getPropertyValue('--tab-h') || '28px';
      root.style.setProperty('--t-nav', navH);
      root.style.setProperty('--t-rh', rhH);
      root.style.setProperty('--t-tab', tabH);
    }
    // Run after each sync cycle from premium-override.js
    setTimeout(forceTerminalVars, 350);
    setTimeout(forceTerminalVars, 1600);
    setTimeout(forceTerminalVars, 4100);
    window.addEventListener('resize', function() { setTimeout(forceTerminalVars, 250); }, { passive: true });


    // ═══════════════════════════════════════════
    // §9  HOOK: switchTab → force-hide #summarySubTabs after it re-shows
    // ═══════════════════════════════════════════
    // switchTab() does: if(tab==='quick') subBar.style.display='flex'
    // Our CSS display:none !important beats this, but belt-and-suspenders:
    var _origSwitchTab = window.switchTab;
    if (typeof _origSwitchTab === 'function') {
      window.switchTab = function(tab) {
        _origSwitchTab.apply(this, arguments);
        // Always hide summarySubTabs
        var sst = document.getElementById('summarySubTabs');
        if (sst) sst.style.setProperty('display', 'none', 'important');
        // Force vars after tab switch
        setTimeout(forceTerminalVars, 150);
      };
    }


    // ═══════════════════════════════════════════
    // §10  RE-ENABLE DARK THEME TOGGLE
    // ═══════════════════════════════════════════
    // app.js toggleTheme() has `return;` at line 1 — we replace it entirely.
    window.toggleTheme = function() {
      var next = (document.documentElement.getAttribute('data-theme') === 'dark') ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      window._currentTheme = next;
      try { localStorage.setItem('celesys-theme', next); } catch(e) {}
      // Update both toggle buttons (nav + reportHeader)
      var btns = [document.getElementById('themeToggleBtn'), document.querySelector('.nbtn-theme')];
      btns.forEach(function(btn) {
        if (btn) btn.innerHTML = (next === 'dark') ? '&#9728;' : '&#9790;';
      });
    };
    // Restore saved theme on load
    try {
      var saved = localStorage.getItem('celesys-theme');
      if (saved === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        window._currentTheme = 'dark';
        var btns = [document.getElementById('themeToggleBtn'), document.querySelector('.nbtn-theme')];
        btns.forEach(function(btn) { if (btn) btn.innerHTML = '&#9728;'; });
      }
    } catch(e) {}
    // Also fix the inline onclick on nav theme button (it uses a different toggle method)
    var navThemeBtn = document.querySelector('.nbtn-theme');
    if (navThemeBtn) {
      navThemeBtn.setAttribute('onclick', 'toggleTheme()');
    }


    // ═══════════════════════════════════════════
    // §11  COMPACT PRINT ICON — Replace big PDF button with tiny icon
    // ═══════════════════════════════════════════
    // The existing PDF button in #actionToolbar is already small (9px).
    // We just make sure it stays tiny and uses a printer icon.
    var pdfBtn = document.getElementById('pdfExportBtn');
    if (pdfBtn) {
      pdfBtn.innerHTML = '&#128424;'; // 🖨 printer icon
      pdfBtn.title = 'Print / Export PDF';
      pdfBtn.style.cssText = 'padding:1px 5px;font-size:11px;border-radius:4px;border:1px solid ' +
        'rgba(255,255,255,.08);background:transparent;color:#64748B;cursor:pointer;line-height:1;';
    }


    console.log('[Celesys Terminal] Menu → SubMenu architecture loaded (v3 — dark mode + print fixed)');
  }

})();
