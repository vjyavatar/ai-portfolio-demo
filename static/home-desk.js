(function(){
'use strict';
var HEAVY = [
  'https://cdn.jsdelivr.net/npm/chart.js',
  'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.0.9/purify.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js'
];
function addScript(src){
  return new Promise(function(resolve){
    var el = document.createElement('script');
    el.src = src;
    el.onload = el.onerror = function(){ resolve(); };
    document.body.appendChild(el);
  });
}
var heavyReady = null;
function loadHeavy(){
  if (heavyReady) return heavyReady;
  if (!document.querySelector('script[src*="googletagmanager.com/gtag"]')) {
    addScript('https://www.googletagmanager.com/gtag/js?id=G-WW55EQ7ZB8').then(function(){
      if (window.gtag) { gtag('js', new Date()); gtag('config', 'G-WW55EQ7ZB8'); }
    });
    addScript('https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2084524493538975');
  }
  var chain = Promise.resolve();
  HEAVY.forEach(function(src){ chain = chain.then(function(){ return addScript(src); }); });
  heavyReady = chain.then(function(){ window._homeAppReady = true; });
  return heavyReady;
}
var ticker = document.getElementById('ticker');
var suggestions = document.getElementById('autocomplete');
var TRIES = [
  {t:'AAPL', n:'Apple'}, {t:'RELIANCE', n:'Reliance Industries'},
  {t:'NVDA', n:'NVIDIA'}, {t:'TCS', n:'Tata Consultancy'},
  {t:'MSFT', n:'Microsoft'}, {t:'AMZN', n:'Amazon'}, {t:'MU', n:'Micron'}
];
if (ticker) {
  ticker.addEventListener('focus', function(){ loadHeavy(); });
  ticker.addEventListener('input', function(){
    if (typeof window.analyze === 'function' || !suggestions) return;
    var q = ticker.value.trim().toUpperCase();
    suggestions.replaceChildren();
    if (!q) { suggestions.classList.remove('show'); return; }
    TRIES.filter(function(item){ return item.t.indexOf(q) === 0 || item.n.toUpperCase().indexOf(q) >= 0; }).forEach(function(item){
      var row = document.createElement('div');
      row.className = 'aci';
      row.innerHTML = '<span class="act">' + item.t + '</span><span class="acn">' + item.n + '</span>';
      row.addEventListener('click', function(){ ticker.value = item.t; suggestions.classList.remove('show'); });
      suggestions.appendChild(row);
    });
    suggestions.classList.toggle('show', suggestions.childElementCount > 0);
  });
}
var analyzeBtn = document.getElementById('btn');
if (analyzeBtn) {
  analyzeBtn.addEventListener('click', function(event){
    if (typeof window.analyze === 'function') return;
    event.preventDefault();
    var label = analyzeBtn.textContent;
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = 'Analyzing...';
    loadHeavy().then(function(){
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = label;
      if (typeof window.analyze === 'function') window.analyze();
    });
  }, true);
}
document.querySelectorAll('[data-try]').forEach(function(button){
  button.addEventListener('click', function(){
    var ticker = document.getElementById('ticker');
    if (!ticker) return;
    ticker.focus();
    ticker.value = button.getAttribute('data-try') || '';
    ticker.dispatchEvent(new Event('input', {bubbles:true}));
  });
});
var watch = document.getElementById('home-watch');
if (watch) watch.addEventListener('click', function(){
  var trading = document.querySelector('[data-ws-mode="trading"]');
  if (trading) trading.click();
});
var brief = document.getElementById('home-brief-line');
if (brief) {
  fetch('/api/home-strip').then(function(r){return r.json();}).then(function(data){
    var rows = (data && data.indices) || [];
    var line = rows.slice(0, 3).map(function(row){
      var pct = typeof row.change_pct === 'number' ? (row.change_pct > 0 ? '+' : '') + row.change_pct.toFixed(1) + '%' : '';
      return row.name + (pct ? ' ' + pct : '');
    }).join(' · ');
    brief.textContent = line || 'The daily brief is refreshing.';
  }).catch(function(){ brief.textContent = 'The daily brief is refreshing.'; });
}
var row = document.getElementById('home-movers-row');
var meta = document.getElementById('home-movers-meta');
function skeleton(){
  if (!row) return;
  row.replaceChildren();
  for (var i = 0; i < 4; i += 1) {
    var cell = document.createElement('span');
    cell.className = 'home-mover home-mover--skeleton';
    cell.setAttribute('aria-hidden', 'true');
    row.append(cell);
  }
}
function paint(items, note){
  if (!row) return;
  row.replaceChildren();
  items.forEach(function(item){
    var cell = document.createElement('button');
    cell.type = 'button';
    cell.className = 'home-mover ' + ((item.change_pct || 0) >= 0 ? 'up' : 'dn');
    cell.textContent = item.symbol + ' ' + ((item.change_pct || 0) > 0 ? '+' : '') + Number(item.change_pct || 0).toFixed(1) + '%';
    cell.addEventListener('click', function(){
      var ticker = document.getElementById('ticker');
      if (!ticker) return;
      ticker.focus();
      ticker.value = item.symbol;
    });
    row.append(cell);
  });
  if (meta) meta.textContent = note;
  row.setAttribute('aria-busy', 'false');
}
function fromPayload(data){
  var preview = data && data.preview;
  var items = [];
  if (preview && ((preview.gainers || []).length || (preview.losers || []).length)) {
    items = (preview.gainers || []).concat(preview.losers || []);
  } else if (data && data.windows && data.windows['1D']) {
    var day = data.windows['1D'];
    items = (day.gainers || []).concat(day.losers || []);
  }
  var seen = {};
  var rows = [];
  items.forEach(function(item){
    if (!item || !item.symbol || seen[item.symbol]) return;
    seen[item.symbol] = true;
    var pct = item.change_pct;
    if (pct == null && item.pct != null) pct = item.pct;
    if (pct == null && item.windows) pct = item.windows['1D'];
    rows.push({symbol:item.symbol, change_pct:Number(pct) || 0});
  });
  rows.sort(function(a, b){ return b.change_pct - a.change_pct; });
  return rows.slice(0, 4);
}
function loadMovers(){
  skeleton();
  fetch('/api/movers?region=IN').then(function(r){return r.json();}).then(function(data){
    var items = fromPayload(data);
    if (items.length) {
      paint(items, data._loading ? 'A fuller scan is still running' : 'India, 1 day');
      return;
    }
    paint([], 'Movers are refreshing');
  }).catch(function(){ paint([], 'Movers are refreshing'); });
}
if (row) loadMovers();
})();
