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
function chip(row) {
  const pct = typeof row.change_pct === 'number' && Number.isFinite(row.change_pct) ? row.change_pct : null;
  const article = document.createElement('article');
  article.className = 'live-chip live-chip--refined';
  const top = document.createElement('div'); top.className = 'live-chip__top';
  const name = document.createElement('span'); name.className = 'live-chip__name';
  name.textContent = (text(row.flag) ? row.flag + ' ' : '') + (text(row.name) || text(row.symbol) || 'Unknown instrument');
  const quality = document.createElement('span'); quality.className = 'live-chip__quality';
  const qualityText = freshness(row);
  quality.textContent = qualityText;
  quality.dataset.state = qualityText.startsWith('Live') ? 'live'
    : qualityText.includes('delayed') || qualityText === 'Delayed' ? 'delayed' : 'unknown';
  top.append(name, quality);
  const price = document.createElement('strong'); price.className = 'live-chip__price'; price.textContent = num(row.price);
  const change = document.createElement('span'); change.className = 'live-chip__change';
  change.classList.add(pct === null ? 'flat' : pct > 0 ? 'up' : pct < 0 ? 'dn' : 'flat');
  change.textContent = pct === null ? 'Change unavailable' : (pct > 0 ? '+' : '') + num(pct) + '%';
  const foot = document.createElement('div'); foot.className = 'live-chip__foot';
  const source = document.createElement('span');
  // Never claim Finnhub or Angel One unless the backend actually identifies it.
  const provider = text(row.provider) || text(row.source);
  source.textContent = provider ? 'Source: ' + provider : 'Source not verified';
  const session = document.createElement('span'); session.textContent = text(row.session) || 'Session unknown';
  foot.append(source, session);
  article.append(top, price, change, foot);
  return article;
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
    const response = await fetch('/api/live/overview', {signal:controller.signal, cache:'no-store'});
    if (!response.ok) throw Error('HTTP ' + response.status);
    const data = await response.json();
    if (!data || !Array.isArray(data.indices)) throw Error('Unexpected response');
    const sessions = data.sessions || {}, ex = sessions.exchanges || {}, c = sessions.clocks || {};
    clocks.textContent = 'US ' + (text(c.et) || 'time unavailable') + ' · ' + (text(ex.US && ex.US.session) || 'session unknown') +
      '  |  India ' + (text(c.ist) || 'time unavailable') + ' · ' + (text(ex.IN && ex.IN.session) || 'session unknown');
    const fragment = document.createDocumentFragment();
    data.indices.forEach(row => { if (row && typeof row === 'object') fragment.append(chip(row)); });
    root.replaceChildren(fragment);
    lastSuccess = new Date();
    status.textContent = root.childElementCount
      ? 'Updated ' + lastSuccess.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) + ' · Data quality shown per instrument'
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
load();
setInterval(() => { if (!document.hidden) load(); }, 60000);
})();
