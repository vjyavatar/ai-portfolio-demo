(function(){
'use strict';
const root = document.getElementById('live-board-indices');
const clocks = document.getElementById('live-board-clocks');
const board = document.getElementById('live-board');
if (!root || !clocks || !board) return;

const num = v => typeof v === 'number' && Number.isFinite(v)
  ? v.toLocaleString(undefined, {maximumFractionDigits:2}) : '—';
const text = v => typeof v === 'string' ? v.trim() : '';
const freshness = row => {
  if (Number.isFinite(row.delay_seconds) && row.delay_seconds > 0)
    return Math.ceil(row.delay_seconds / 60) + ' min delayed';
  const quality = text(row.quality).toUpperCase();
  return quality === 'LIVE' ? 'Live · provider reported'
    : quality === 'DELAYED' ? 'Delayed'
    : quality === 'STALE' ? 'Stale'
    : quality === 'DISCONNECTED' ? 'Disconnected'
    : quality === 'INSUFFICIENT_DATA' ? 'Insufficient data'
    : 'Freshness unverified';
};
const HOME_TILES = [
  {label:'NIFTY', test:n => /^nifty( 50)?$/i.test(n)},
  {label:'SENSEX', test:n => /sensex/i.test(n)},
  {label:'S&P 500', test:n => /s&p|spx/i.test(n)},
  {label:'NASDAQ', test:n => /nasdaq/i.test(n) && !/vix/i.test(n)},
  {label:'USD/INR', test:n => /usd\s*\/\s*inr|usd-inr/i.test(n)},
  {label:'GOLD', test:n => /^gold\b/i.test(n)},
];
function pickTiles(rows) {
  const chosen = [];
  const used = new Set();
  for (const spec of HOME_TILES) {
    const row = rows.find((item, index) => {
      if (used.has(index) || !item) return false;
      const name = text(item.name) || text(item.symbol);
      return spec.test(name);
    });
    if (!row) continue;
    used.add(rows.indexOf(row));
    chosen.push(Object.assign({tile:spec.label}, row));
  }
  return chosen;
}
function spark(values, direction) {
  if (!Array.isArray(values) || values.length < 2) return null;
  const width = 72, height = 28;
  const min = Math.min.apply(null, values), max = Math.max.apply(null, values);
  const span = max - min || 1;
  const points = values.map((value, index) => {
    const x = (index / (values.length - 1)) * width;
    const y = height - ((value - min) / span) * (height - 4) - 2;
    return x.toFixed(1) + ',' + y.toFixed(1);
  }).join(' ');
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
  svg.setAttribute('class', 'live-spark');
  svg.setAttribute('aria-hidden', 'true');
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  line.setAttribute('points', points);
  line.setAttribute('fill', 'none');
  line.setAttribute('stroke', direction === 'up' ? '#087b68' : direction === 'dn' ? '#c03b45' : '#64748b');
  line.setAttribute('stroke-width', '1.6');
  line.setAttribute('stroke-linecap', 'round');
  line.setAttribute('stroke-linejoin', 'round');
  svg.append(line);
  return svg;
}
function chip(row) {
  const pct = typeof row.change_pct === 'number' && Number.isFinite(row.change_pct) ? row.change_pct : null;
  const direction = pct === null ? 'flat' : pct > 0 ? 'up' : pct < 0 ? 'dn' : 'flat';
  const article = document.createElement('article');
  article.className = 'live-chip live-chip--refined';
  const name = document.createElement('span'); name.className = 'live-chip__name';
  name.textContent = row.tile || text(row.name) || text(row.symbol) || 'Market';
  const price = document.createElement('strong'); price.className = 'live-chip__price'; price.textContent = num(row.price);
  const change = document.createElement('span'); change.className = 'live-chip__change';
  change.classList.add(direction);
  change.textContent = pct === null ? '—' : (pct > 0 ? '+' : '') + num(pct) + '%';
  article.append(name, price, change);
  const line = spark(row.spark, direction);
  if (line) article.append(line);
  return article;
}
function skeleton() {
  root.replaceChildren();
  for (let i = 0; i < 6; i += 1) {
    const article = document.createElement('article');
    article.className = 'live-chip live-chip--skeleton';
    article.setAttribute('aria-hidden', 'true');
    root.append(article);
  }
}
const toolbar = document.createElement('div'); toolbar.className = 'live-board-toolbar';
const status = document.createElement('p'); status.className = 'live-board-status'; status.setAttribute('role','status'); status.setAttribute('aria-live','polite');
const refresh = document.createElement('button'); refresh.type = 'button'; refresh.className = 'live-board-refresh'; refresh.textContent = 'Refresh market board';
toolbar.append(status, refresh);
clocks.insertAdjacentElement('afterend', toolbar);
let controller = null, busy = false, lastSuccess = null;
async function load(){
  if (busy) return;
  busy = true; refresh.disabled = true; refresh.textContent = 'Refreshing…';
  status.textContent = 'Checking market data…';
  controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch('/api/home-strip', {signal:controller.signal, cache:'no-store'});
    if (!response.ok) throw Error('HTTP ' + response.status);
    const data = await response.json();
    if (!data || !Array.isArray(data.indices)) throw Error('Unexpected response');
    clocks.textContent = '';
    const tiles = pickTiles(data.indices.filter(row => row && typeof row === 'object'));
    const fragment = document.createDocumentFragment();
    tiles.forEach(row => fragment.append(chip(row)));
    root.replaceChildren(fragment);
    lastSuccess = new Date();
    const providers = [...new Set(tiles.map(row => text(row.provider) || text(row.source)).filter(Boolean))];
    const nifty = tiles.find(row => row.tile === 'NIFTY');
    status.textContent = tiles.length
      ? 'Updated ' + lastSuccess.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})
        + ' · Source: ' + (providers.join(', ') || 'market data')
        + (nifty && Number.isFinite(nifty.price) ? ' · NIFTY ' + num(nifty.price) : '')
      : 'No market quotes available. Please try again later.';
  } catch(e) {
    status.textContent = 'Unable to refresh market data' + (lastSuccess
      ? ' · Showing last successful snapshot from ' + lastSuccess.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})
      : ' · No verified quotes available');
    if (!lastSuccess) {
      root.replaceChildren();
      clocks.textContent = 'Market board unavailable. Other research tools remain accessible.';
    }
  } finally {
    clearTimeout(timeout); busy = false; refresh.disabled = false; refresh.textContent = 'Refresh market board';
  }
}
refresh.addEventListener('click', load);
skeleton();
load();
setInterval(() => { if (!document.hidden) load(); }, 60000);
})();
