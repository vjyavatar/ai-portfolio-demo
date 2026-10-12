'use strict';
const $ = id => document.getElementById(id);
const region = $('chain-app').dataset.region;
let controller, sequence = 0, current = null;
const n = value => Number.isFinite(value) ? new Intl.NumberFormat('en-US', {maximumFractionDigits:2}).format(value) : '—';
const stamp = value => Number.isFinite(value) ? new Date(value*1000).toLocaleString() : 'Not supplied';
function clear() {
  current = null;
  $('chain-rows').replaceChildren(); $('chain-table').hidden = true;
  $('chain-summary').hidden = true; $('chain-summary').textContent = ''; $('chain-meta').textContent = '';
}
function reset() {
  sequence++; controller?.abort(); clear(); $('load-chain').disabled = false;
  $('expiry').replaceChildren(new Option('Nearest available', ''));
  $('chain-status').textContent = 'Selection changed. Load a new chain.';
}
$('india-symbol').addEventListener('change', reset);
$('us-symbol').addEventListener('input', reset);
$('expiry').addEventListener('change', () => {
  sequence++; controller?.abort(); clear(); $('load-chain').disabled = false;
  $('chain-status').textContent = 'Expiry changed. Load the selected chain.';
});
function details(row) {
  const d = document.createElement('details'), s = document.createElement('summary');
  s.textContent = 'Evidence'; d.append(s);
  for (const kind of ['call','put']) {
    const q = row[kind]; if (!q) continue;
    for (const line of [`${kind.toUpperCase()} · ${q.contract || 'Unknown contract'}`,
      `Volume ${n(q.volume)} · Delta ${n(q.delta)} · Spread ${n(q.spread_pct)}%`,
      `Bid time: ${stamp(q.bid_time)}`, `Ask time: ${stamp(q.ask_time)}`,
      `Greeks update: ${q.greeks_time || 'Not supplied'}`]) {
      const p = document.createElement('p'); p.textContent = line; d.append(p);
    }
  }
  return d;
}
function render(data) {
  current = data;
  $('chain-status').textContent = data.message;
  if (data.expiries?.length) {
    $('expiry').replaceChildren(...data.expiries.map(e => new Option(e,e)));
    if (data.expiry) $('expiry').value = data.expiry;
  }
  if (data.status !== 'SNAPSHOT') return;
  const rows = data.rows || [];
  $('chain-meta').textContent = `${data.source} · ${data.currency} · Fetched ${stamp(data.fetched_at)} · ${data.freshness.replaceAll('_',' ')}. Fetch time is not quote time.`;
  const complete = rows.length && rows.every(r => Number.isFinite(r.call?.oi) && Number.isFinite(r.put?.oi));
  const calls = complete ? rows.reduce((a,r)=>a+r.call.oi,0) : null;
  const puts = complete ? rows.reduce((a,r)=>a+r.put.oi,0) : null;
  $('chain-summary').hidden = false;
  $('chain-summary').textContent = `${rows.length} returned strikes · Call OI ${n(calls)} · Put OI ${n(puts)} · Snapshot OI PCR ${n(calls > 0 ? puts/calls : null)}. Provider-returned coverage only.`;
  for (const row of rows) {
    const tr = document.createElement('tr');
    const quote = q => `${n(q?.bid)} / ${n(q?.ask)}`;
    for (const val of [n(row.call?.oi),n(row.call?.oi_change),quote(row.call),n(row.call?.iv_pct),n(row.strike),n(row.put?.iv_pct),quote(row.put),n(row.put?.oi_change),n(row.put?.oi)]) {
      const td = document.createElement('td'); td.textContent = val; tr.append(td);
    }
    const td = document.createElement('td'); td.append(details(row)); tr.append(td); $('chain-rows').append(tr);
  }
  $('chain-table').hidden = false;
}
$('chain-form').addEventListener('submit', async event => {
  event.preventDefault();
  const id = ++sequence; controller?.abort(); controller = new AbortController();
  const aborter = controller;
  const expiry = $('expiry').value;
  clear(); $('load-chain').disabled = true; $('chain-status').textContent = 'Checking provider connection and contract evidence…';
  const timer = setTimeout(()=>aborter.abort(),65000);
  try {
    const query = new URLSearchParams({region, symbol:(region === 'IN' ? $('india-symbol').value : $('us-symbol').value).trim().toUpperCase(),expiry});
    const response = await fetch('/api/existing-option-chain?'+query,{signal:aborter.signal});
    if (!response.ok) throw Error(response.status === 422 ? 'Check the symbol and expiry, then try again.' : 'The chain service is unavailable. Try again later.');
    const data = await response.json(); if (id !== sequence) return; render(data);
  } catch(error) {
    if (id === sequence) $('chain-status').textContent = error.name === 'AbortError' ? 'The request timed out. No prices are shown. Try again.' : error.message;
  } finally { clearTimeout(timer); if (id === sequence) $('load-chain').disabled = false; }
});
setInterval(()=>{
  if (!current || current.status !== 'SNAPSHOT') return;
  const now = Date.now()/1000;
  const times = current.rows.flatMap(r=>[r.call,r.put].filter(Boolean).flatMap(q=>[q.bid_time,q.ask_time]));
  const fresh = times.length && times.every(t=>Number.isFinite(t) && now>=t && now-t<=300);
  $('chain-meta').textContent = `${current.source} · ${current.currency} · Fetched ${stamp(current.fetched_at)} · ${fresh ? 'RECENT QUOTE TIMESTAMPS' : 'UNVERIFIED OR STALE QUOTES'} · Snapshot age ${Math.max(0,Math.floor(now-current.fetched_at))} seconds. Reload to request a new snapshot.`;
},15000);
