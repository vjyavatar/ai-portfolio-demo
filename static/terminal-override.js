/* CELESYS TERMINAL v4 — JS Override
   Clutter removal, overview subtab merge, dark theme, print icon */
(function() {
  'use strict';
  var _ready = setInterval(function() {
    if (typeof window.switchTabGroup !== 'function') return;
    clearInterval(_ready);
    init();
  }, 200);

  function init() {

    // §1 CLUTTER REMOVAL
    function hideClutter() {
      ['siteWatermark','globalDecisionBar','pwaInstallBanner','stickyTag','heroDiagram'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) { el.style.setProperty('display','none','important'); el.style.setProperty('height','0','important'); }
      });
      ['heroExtras','seoHome','premiumPricing'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.style.setProperty('display','none','important');
      });
      document.documentElement.style.setProperty('--gdb-h','0px');
    }
    hideClutter();
    var _obs = new MutationObserver(hideClutter);
    _obs.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style'] });
    setTimeout(function() { _obs.disconnect(); }, 120000);

    // §2 PATCH _updateGlobalBar
    var _origBar = window._updateGlobalBar;
    if (typeof _origBar === 'function') {
      window._updateGlobalBar = function() {
        _origBar.apply(this, arguments);
        var gdb = document.getElementById('globalDecisionBar');
        if (gdb) { gdb.style.setProperty('display','none','important'); }
        document.documentElement.style.setProperty('--gdb-h','0px');
      };
    }

    // §3 OVERVIEW SUBTABS → merge into #groupSubNav
    var OVERVIEW_SUBS = [
      { id:'overview',  label:'\u{1F4CA} Overview' },
      { id:'valuation', label:'\u{1F4B0} Valuation' },
      { id:'technical', label:'\u{1F4C8} Technical' },
      { id:'activity',  label:'\u{1F3E2} Activity' },
      { id:'risk',      label:'\u26A0 Risk' }
    ];

    function injectOverviewSubTabs() {
      var subNav = document.getElementById('groupSubNav');
      if (!subNav) return;
      var activeSub = window._activeSubTab || 'overview';
      var h = '';
      OVERVIEW_SUBS.forEach(function(sub) {
        var a = sub.id === activeSub;
        h += '<button onclick="window._termOverviewSub(\'' + sub.id + '\')" '
          + 'class="sub-tab-btn' + (a ? ' active' : '') + '" '
          + 'data-osub="' + sub.id + '">'
          + sub.label + '</button>';
      });
      subNav.innerHTML = h;
      subNav.style.display = 'flex';
    }

    window._termOverviewSub = function(subId) {
      if (typeof window.switchSubTab === 'function') window.switchSubTab(subId);
      window._activeSubTab = subId;
      var subNav = document.getElementById('groupSubNav');
      if (!subNav) return;
      subNav.querySelectorAll('.sub-tab-btn').forEach(function(btn) {
        btn.classList.toggle('active', btn.getAttribute('data-osub') === subId);
      });
    };

    // §4 HOOK switchTabGroup
    var _origGroup = window.switchTabGroup;
    window.switchTabGroup = function(group) {
      _origGroup.apply(this, arguments);
      if (group === 'overview') injectOverviewSubTabs();
      var sst = document.getElementById('summarySubTabs');
      if (sst) sst.style.setProperty('display','none','important');
    };

    // §5 HOOK switchSubTab
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
      if (sst) sst.style.setProperty('display','none','important');
    };

    // §6 HOOK switchTab
    var _origTab = window.switchTab;
    if (typeof _origTab === 'function') {
      window.switchTab = function(tab) {
        _origTab.apply(this, arguments);
        var sst = document.getElementById('summarySubTabs');
        if (sst) sst.style.setProperty('display','none','important');
      };
    }

    // §7 HERO COLLAPSE + FORCE TABBAR
    var _rpt = document.getElementById('report');
    function onReportShow() {
      var hero = document.querySelector('.hero');
      if (hero) hero.classList.add('collapsed');
      var mtb = document.getElementById('mainTabBar');
      if (mtb && !mtb.classList.contains('tab-bar-hidden')) {
        mtb.style.setProperty('display','flex','important');
      }
    }
    if (_rpt) {
      new MutationObserver(function() {
        if (_rpt.classList.contains('show')) onReportShow();
      }).observe(_rpt, { attributes: true, attributeFilter: ['class','style'] });
      if (_rpt.classList.contains('show')) {
        onReportShow();
        if (window._activeGroup === 'overview') setTimeout(injectOverviewSubTabs, 50);
      }
    }

    // §8 DARK THEME TOGGLE (replace the killed toggleTheme)
    window.toggleTheme = function() {
      var next = (document.documentElement.getAttribute('data-theme') === 'dark') ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      window._currentTheme = next;
      try { localStorage.setItem('celesys-theme', next); } catch(e) {}
      [document.getElementById('themeToggleBtn'), document.querySelector('.nbtn-theme')].forEach(function(btn) {
        if (btn) btn.innerHTML = (next === 'dark') ? '\u2600' : '\u263E';
      });
    };
    // Restore saved theme
    try {
      var saved = localStorage.getItem('celesys-theme');
      if (saved === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        window._currentTheme = 'dark';
        [document.getElementById('themeToggleBtn'), document.querySelector('.nbtn-theme')].forEach(function(btn) {
          if (btn) btn.innerHTML = '\u2600';
        });
      }
    } catch(e) {}
    var navBtn = document.querySelector('.nbtn-theme');
    if (navBtn) navBtn.setAttribute('onclick', 'toggleTheme()');

    // §9 COMPACT PRINT ICON
    var pdfBtn = document.getElementById('pdfExportBtn');
    if (pdfBtn) {
      pdfBtn.innerHTML = '\u{1F5A8}';
      pdfBtn.title = 'Print';
      pdfBtn.style.cssText = 'padding:1px 5px;font-size:11px;border-radius:4px;border:1px solid rgba(0,0,0,.1);background:transparent;color:#64748B;cursor:pointer;';
    }

    console.log('[Celesys Terminal v4] Loaded');
  }
})();
