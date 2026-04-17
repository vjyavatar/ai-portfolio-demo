/* CELESYS TERMINAL v8 — Production JS Override */
(function() {
  'use strict';
  var _ready = setInterval(function() {
    if (typeof window.switchTabGroup !== 'function') return;
    clearInterval(_ready);
    init();
  }, 200);

  function init() {
    // §1 FORCE DARK THEME immediately
    document.documentElement.setAttribute('data-theme', 'dark');
    window._currentTheme = 'dark';

    // §2 CLUTTER REMOVAL
    function hideClutter() {
      ['siteWatermark','globalDecisionBar','pwaInstallBanner','stickyTag','heroDiagram','premiumPricing','floatingUpgradeCTA'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) { el.style.setProperty('display','none','important'); el.style.setProperty('height','0','important'); }
      });
      document.documentElement.style.setProperty('--gdb-h','0px');
    }
    hideClutter();
    var _obs = new MutationObserver(hideClutter);
    _obs.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style'] });
    setTimeout(function() { _obs.disconnect(); }, 120000);

    // §3 OVERVIEW SUBTABS merge into groupSubNav
    var OSUBS = [
      { id: 'overview',  label: 'Overview' },
      { id: 'valuation', label: 'Valuation' },
      { id: 'technical', label: 'Technical' },
      { id: 'activity',  label: 'Activity' },
      { id: 'risk',      label: 'Risk' }
    ];
    function injectOverviewSubTabs() {
      var subNav = document.getElementById('groupSubNav');
      if (!subNav) return;
      var activeSub = window._activeSubTab || 'overview';
      var h = '';
      OSUBS.forEach(function(sub) {
        var a = sub.id === activeSub;
        h += '<button onclick="window._termOSub(\'' + sub.id + '\')" class="sub-tab-btn' + (a ? ' active' : '') + '" data-osub="' + sub.id + '">' + sub.label + '</button>';
      });
      subNav.innerHTML = h;
      subNav.style.display = 'flex';
    }
    window._termOSub = function(subId) {
      if (typeof window.switchSubTab === 'function') window.switchSubTab(subId);
      window._activeSubTab = subId;
      var subNav = document.getElementById('groupSubNav');
      if (subNav) subNav.querySelectorAll('.sub-tab-btn').forEach(function(btn) {
        btn.classList.toggle('active', btn.getAttribute('data-osub') === subId);
      });
    };

    // §4 HOOKS
    var _origGroup = window.switchTabGroup;
    window.switchTabGroup = function(group) {
      _origGroup.apply(this, arguments);
      if (group === 'overview') injectOverviewSubTabs();
      var sst = document.getElementById('summarySubTabs');
      if (sst) sst.style.setProperty('display', 'none', 'important');
    };
    var _origSub = window.switchSubTab;
    window.switchSubTab = function(sub) {
      _origSub.apply(this, arguments);
      window._activeSubTab = sub;
      if (window._activeGroup === 'overview') {
        var subNav = document.getElementById('groupSubNav');
        if (subNav) subNav.querySelectorAll('.sub-tab-btn').forEach(function(btn) {
          btn.classList.toggle('active', btn.getAttribute('data-osub') === sub);
        });
      }
      var sst = document.getElementById('summarySubTabs');
      if (sst) sst.style.setProperty('display', 'none', 'important');
    };
    var _origTab = window.switchTab;
    if (typeof _origTab === 'function') {
      window.switchTab = function(tab) {
        _origTab.apply(this, arguments);
        var sst = document.getElementById('summarySubTabs');
        if (sst) sst.style.setProperty('display', 'none', 'important');
      };
    }

    // §5 PATCH _updateGlobalBar
    var _origBar = window._updateGlobalBar;
    if (typeof _origBar === 'function') {
      window._updateGlobalBar = function() {
        _origBar.apply(this, arguments);
        var gdb = document.getElementById('globalDecisionBar');
        if (gdb) gdb.style.setProperty('display', 'none', 'important');
        document.documentElement.style.setProperty('--gdb-h', '0px');
      };
    }

    // §6 HERO COLLAPSE + FORCE TABBAR
    var _rpt = document.getElementById('report');
    function onReportShow() {
      var hero = document.querySelector('.hero');
      if (hero) hero.classList.add('collapsed');
      var mtb = document.getElementById('mainTabBar');
      if (mtb && !mtb.classList.contains('tab-bar-hidden')) {
        mtb.style.setProperty('display', 'flex', 'important');
      }
    }
    if (_rpt) {
      new MutationObserver(function() {
        if (_rpt.classList.contains('show')) onReportShow();
      }).observe(_rpt, { attributes: true, attributeFilter: ['class', 'style'] });
      if (_rpt.classList.contains('show')) {
        onReportShow();
        if (window._activeGroup === 'overview') setTimeout(injectOverviewSubTabs, 50);
      }
    }

    // §7 THEME TOGGLE (dark only by default, but allow toggling)
    window.toggleTheme = function() {
      var cur = document.documentElement.getAttribute('data-theme');
      var next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      window._currentTheme = next;
      try { localStorage.setItem('celesys-theme', next); } catch(e) {}
      [document.getElementById('themeToggleBtn'), document.querySelector('.nbtn-theme')].forEach(function(btn) {
        if (btn) btn.innerHTML = next === 'dark' ? '\u2600' : '\u263E';
      });
    };
    // Set theme toggle button
    [document.getElementById('themeToggleBtn'), document.querySelector('.nbtn-theme')].forEach(function(btn) {
      if (btn) { btn.innerHTML = '\u2600'; btn.setAttribute('onclick', 'toggleTheme()'); }
    });

    // §8 SCROLL TO TOP on load
    window.scrollTo(0, 0);
    setTimeout(function() { window.scrollTo(0, 0); }, 300);

    // §9 AUTO-OPEN details in cockpit
    function autoOpenDetails() {
      ['deResult', 'algoResult'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.querySelectorAll('details:not([open])').forEach(function(d) { d.setAttribute('open', ''); });
      });
      document.querySelectorAll('.dc details:not([open])').forEach(function(d) { d.setAttribute('open', ''); });
    }
    var _origLoadDE = window.loadDE;
    if (typeof _origLoadDE === 'function') {
      window.loadDE = function() {
        _origLoadDE.apply(this, arguments);
        setTimeout(autoOpenDetails, 500);
        setTimeout(autoOpenDetails, 2000);
      };
    }
    var _origAlgo = window.algoSelect;
    if (typeof _origAlgo === 'function') {
      window.algoSelect = function() {
        _origAlgo.apply(this, arguments);
        setTimeout(autoOpenDetails, 500);
        setTimeout(autoOpenDetails, 2000);
      };
    }

    // §10 HIDE FLOATING CTA (appears after scroll)
    setInterval(function() {
      var cta = document.getElementById('floatingUpgradeCTA');
      if (cta) cta.style.setProperty('display', 'none', 'important');
    }, 3000);

    // §11 COMPACT PRINT ICON
    var pdfBtn = document.getElementById('pdfExportBtn');
    if (pdfBtn) { pdfBtn.innerHTML = 'PDF'; pdfBtn.title = 'Export PDF'; }

    console.log('[Celesys Terminal v8] Production loaded - dark theme active');
  }
})();

// §12 INDEX SELECTOR — inject NIFTY/BANKNIFTY/SENSEX buttons into nav (per spec)
function injectIndexSelector() {
  var nav = document.querySelector('nav');
  if (!nav || document.getElementById('terminalIndexSel')) return;
  var container = document.createElement('div');
  container.id = 'terminalIndexSel';
  container.style.cssText = 'display:flex;gap:4px;align-items:center;margin-left:auto;margin-right:12px';
  ['NIFTY','BANKNIFTY','SENSEX'].forEach(function(idx, i) {
    var btn = document.createElement('button');
    btn.textContent = idx;
    btn.style.cssText = 'padding:4px 14px;border-radius:5px;font-size:11px;font-weight:700;cursor:pointer;font-family:inherit;border:1px solid ' + (i === 0 ? '#3B82F6' : '#1E293B') + ';background:' + (i === 0 ? 'rgba(59,130,246,.1)' : 'transparent') + ';color:' + (i === 0 ? '#3B82F6' : '#64748B');
    btn.onclick = function() {
      container.querySelectorAll('button').forEach(function(b) {
        b.style.borderColor = '#1E293B';
        b.style.background = 'transparent';
        b.style.color = '#64748B';
      });
      btn.style.borderColor = '#3B82F6';
      btn.style.background = 'rgba(59,130,246,.1)';
      btn.style.color = '#3B82F6';
      // Trigger the index in the options engine if available
      if (typeof window._loadOptionsDecide === 'function') window._loadOptionsDecide(idx);
    };
    container.appendChild(btn);
  });
  // Insert before the right-side elements
  var rightSection = nav.querySelector('.nlive') || nav.querySelector('.npill');
  if (rightSection && rightSection.parentElement === nav) {
    nav.insertBefore(container, rightSection);
  } else {
    nav.appendChild(container);
  }
}
injectIndexSelector();

// §13 DECIDE TAB — Post-render DOM restructuring
// After loadDE or options-engine renders, wrap sections into left/right panels
function restructureDecideLayout() {
  var dc = document.querySelector('.dc');
  if (!dc) return;
  // Mark dc for CSS grid layout
  dc.setAttribute('data-terminal-split', 'true');
}

// Hook into loadDE to apply restructuring after render
var _origLoadDE2 = window.loadDE;
if (typeof _origLoadDE2 === 'function') {
  window.loadDE = function() {
    _origLoadDE2.apply(this, arguments);
    setTimeout(restructureDecideLayout, 800);
    setTimeout(restructureDecideLayout, 2000);
  };
}
