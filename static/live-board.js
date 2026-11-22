(function(){
'use strict';
const root = document.getElementById('live-board-indices');
const clocks = document.getElementById('live-board-clocks');
if(!root || !clocks) return;
const num = v => (typeof v === 'number' && Number.isFinite(v)) ? v.toLocaleString(undefined,{maximumFractionDigits:2}) : '—';
function chip(row){
  const pct = row.change_pct;
  const dir = typeof pct !== 'number' ? '' : pct > 0.005 ? 'up' : pct < -0.005 ? 'dn' : '';
  const delay = row.delay_seconds ? Math.round(row.delay_seconds/60)+'m delay' : (row.quality||'');
  const el = document.createElement('article');
  el.className = 'live-chip';
  const name = document.createElement('span');
  name.textContent = (row.flag?row.flag+' ':'') + (row.name||row.symbol||'');
  const price = document.createElement('b');
  price.textContent = num(row.price);
  const change = document.createElement('span');
  change.className = dir;
  change.textContent = (pct>0?'+':'') + num(pct) + '% · ' + delay + ' · ' + (row.session||'');
  el.append(name, price, change);
  return el;
}
async function load(){
  const response = await fetch('/api/live/overview');
  if(!response.ok) throw Error('board unavailable');
  const data = await response.json();
  const sessions = data.sessions || {};
  const ex = sessions.exchanges || {};
  const c = sessions.clocks || {};
  clocks.textContent = 'US ' + (c.et||'') + ' · ' + ((ex.US&&ex.US.session)||'') + '    India ' + (c.ist||'') + ' · ' + ((ex.IN&&ex.IN.session)||'');
  root.replaceChildren();
  (data.indices||[]).forEach(row => root.append(chip(row)));
  if(!root.childElementCount) clocks.textContent = 'Market board has no quotes right now. The rest of the workspace is unchanged.';
}
load().catch(()=>{clocks.textContent='Market board is unavailable. Existing research tools are unchanged.';});
setInterval(()=>{load().catch(()=>{});}, 60000);
})();
