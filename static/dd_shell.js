// ═══════════════════════════════════════════════════════════════════════════
// r63.72.31 — Deep DD Report Shell (institutional design system wrapper)
//
// Modern institutional B2B layout with:
//   - 5 logical sections (Verdict · Context · Analysis · Signals · External View)
//   - Sticky section nav for fast navigation
//   - Unified card chrome under .csdd-card system
//   - Section dividers with Roman numerals
//
// This module INJECTS section dividers + nav + container slots. Existing card
// renderers (positioning intel, commentary, demand curve, etc.) populate the
// container divs as before — they don't need to be rewritten.
// ═══════════════════════════════════════════════════════════════════════════

(function() {

  // Section definitions
  var DD_SECTIONS = [
    {id: 'verdict',  label: 'Verdict',       sub: 'Bottom line + cycle analysis'},
    {id: 'context',  label: 'Context',       sub: 'Market & sector environment'},
    {id: 'analysis', label: 'Analysis',      sub: '4D institutional positioning'},
    {id: 'signals',  label: 'Signals',       sub: 'Commentary · Demand · Ownership · Volume · Woodshed'},
    {id: 'external', label: 'External View', sub: 'Wall Street consensus'},
  ];

  function _h(strs) {
    var args = arguments;
    var out = strs[0];
    for (var i = 1; i < args.length; i++) {
      out += String(args[i] == null ? '' : args[i]);
      out += strs[i] || '';
    }
    return out;
  }

  // Build the sticky section nav + container slots
  window._buildDDShellHTML = function() {
    var navHTML = '<nav class="csdd-stickynav"><div class="csdd-stickynav__inner">';
    DD_SECTIONS.forEach(function(s, i) {
      navHTML += '<button class="csdd-stickynav__item' + (i === 0 ? ' csdd-stickynav__item--active' : '') +
                 '" data-csdd-nav="' + s.id + '" onclick="_csddJumpTo(\'' + s.id + '\')">' +
                 'I'.repeat(i + 1).replace(/I{4}/g, 'IV').replace(/I{5}/g, 'V') +
                 ' · ' + s.label +
                 '</button>';
    });
    navHTML += '</div></nav>';

    // Section dividers + slots are emitted from the existing renderReport via
    // injection points. We expose helpers to write each section header.
    return navHTML;
  };

  // Renders a section divider header — called from renderReport
  window._csddSectionHeader = function(roman, title, sub) {
    return '<div class="csdd-section" data-csdd-section="' + (roman || '') + '">' +
           '<div class="csdd-section__head">' +
           '<span class="csdd-section__roman">' + roman + '</span>' +
           '<span class="csdd-section__title">' + title + '</span>' +
           (sub ? '<span class="csdd-section__sub">' + sub + '</span>' : '') +
           '</div></div>';
  };

  // Sticky nav scroll behavior
  window._csddJumpTo = function(sectionId) {
    var idx = DD_SECTIONS.findIndex(function(s){ return s.id === sectionId; });
    if (idx < 0) return;
    var roman = 'I'.repeat(idx + 1).replace(/I{4}/g, 'IV').replace(/I{5}/g, 'V');
    var target = document.querySelector('[data-csdd-section="' + roman + '"]');
    if (target) {
      target.scrollIntoView({behavior: 'smooth', block: 'start'});
    }
    // Update active state
    document.querySelectorAll('.csdd-stickynav__item').forEach(function(b) {
      b.classList.toggle('csdd-stickynav__item--active', b.getAttribute('data-csdd-nav') === sectionId);
    });
  };

  // Auto-update active nav item on scroll
  window._csddInstallScrollSpy = function() {
    if (window._csddScrollSpyInstalled) return;
    window._csddScrollSpyInstalled = true;
    window.addEventListener('scroll', function() {
      if (window._csddScrollSpyTimer) return;
      window._csddScrollSpyTimer = setTimeout(function() {
        window._csddScrollSpyTimer = null;
        var sections = document.querySelectorAll('[data-csdd-section]');
        var winMid = window.scrollY + 150;
        var current = null;
        sections.forEach(function(sec) {
          var top = sec.getBoundingClientRect().top + window.scrollY;
          if (top <= winMid) {
            var roman = sec.getAttribute('data-csdd-section');
            var idx = ['I', 'II', 'III', 'IV', 'V'].indexOf(roman);
            if (idx >= 0) current = DD_SECTIONS[idx].id;
          }
        });
        if (current) {
          document.querySelectorAll('.csdd-stickynav__item').forEach(function(b) {
            b.classList.toggle('csdd-stickynav__item--active', b.getAttribute('data-csdd-nav') === current);
          });
        }
      }, 100);
    }, {passive: true});
  };

})();

// ═══════════════════════════════════════════════════════════════════════════
// Retrofit existing card HTML output to use the new design system
// (the existing renderers produce inline-styled divs; we wrap/override them)
// ═══════════════════════════════════════════════════════════════════════════

// Once a card's container has content, normalize its top-level wrapper to .csdd-card
window._csddNormalizeCard = function(containerId, opts) {
  opts = opts || {};
  var el = document.getElementById(containerId);
  if (!el) return;

  // Find the inner card div the existing renderer produced
  // Most renderers produce <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;...">
  var inner = el.querySelector(':scope > div');
  if (!inner) return;

  // Convert it to the design-system shell
  if (inner.style.background && (inner.style.background.indexOf('linear-gradient') < 0)) {
    inner.classList.add('csdd-card');
    if (opts.compact) inner.classList.add('csdd-card--compact');
    // Strip the inline padding/border/background that we now want from CSS
    inner.style.background = '';
    inner.style.border = '';
    inner.style.borderRadius = '';
    inner.style.padding = '';
    inner.style.marginBottom = '';
    inner.style.fontFamily = '';
  }
};

// Periodically normalize after async card loads
window._csddObserveAndNormalize = function() {
  if (window._csddObsInstalled) return;
  window._csddObsInstalled = true;

  var targetIds = [
    'ddMarketRegimeCard', 'ddSectorFlowCard', 'ddStock4DCard',
    'stockCommentaryCard',
    'ddDemandCurveCard', 'ddOwnershipCard', 'ddVolumeProfileCard',
    'ddWoodshedCard',
    'ddAnalystCoverageCard',
  ];

  var observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(m) {
      var id = m.target && m.target.id;
      if (targetIds.indexOf(id) >= 0) {
        var compact = id === 'ddMarketRegimeCard' || id === 'ddSectorFlowCard';
        window._csddNormalizeCard(id, {compact: compact});
      }
    });
  });

  targetIds.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) observer.observe(el, {childList: true, subtree: false});
  });
};
