(function () {
'use strict';
function mount() {
const grid = document.getElementById('ws-brief-grid');
if (!grid || document.getElementById('bm-panel')) return;
const PERIOD = 60000, TIMEOUT = 25000;
let context = null, generation = 0, paused = false, denied = false;
let timer = null, flight = null, report = null, retryAt = 0, lastSignal = null, requestError = ''; 
const nodes = {};
function make(tag, id, text) {
  const n = document.createElement(tag);
  if (id) { n.id = id; nodes[id] = n; }
  if (text !== undefined) n.textContent = text;
  return n;
}
const panel = make('section', 'bm-panel'); panel.hidden = true;
panel.setAttribute('aria-label', 'Separate market quote and closed-bar chart');
const heading = make('div'); heading.className = 'bm-heading';
heading.append(make('h3', 'bm-title', 'Market data'));
const controls = make('div'); controls.className = 'bm-controls';
const pause = make('button', 'bm-pause', 'Pause updates'); pause.type = 'button';
const refresh = make('button', 'bm-refresh', 'Refresh'); refresh.type = 'button';
const voiceLabel = make('label');
const voice = make('input', 'bm-voice'); voice.type = 'checkbox';
voiceLabel.append(voice, make('span', null, 'Speak changes'));
controls.append(pause, refresh, voiceLabel); heading.append(controls); panel.append(heading);
panel.append(make('p', null, 'Separate market-data feed. The original five-step brief below retains its own sources and timestamps. Feed latency is not guaranteed real-time.'));
const facts = make('div'); facts.className = 'bm-facts';
for (const [label, id] of [['Underlying price','bm-price'],['Quote freshness','bm-freshness'],['Session','bm-session'],['Underlying direction','bm-direction'],['Entry readiness','bm-readiness']]) {
  const item = make('div'); item.append(make('span', null, label), make('strong', id, '—')); facts.append(item);
}
panel.append(facts, make('p', 'bm-reason', 'Waiting for source evidence.'), make('div', 'bm-chart'));
const times = make('div'); times.className = 'bm-times';
times.append(make('p', 'bm-source-time'), make('p', 'bm-fetch-time')); panel.append(times);
const status = make('p', 'bm-status'); status.setAttribute('role','status'); status.setAttribute('aria-live','polite'); panel.append(status);
panel.append(make('small', null, 'Underlying research only. No option contract, broker execution or guaranteed outcome is implied.'));
grid.parentNode.insertBefore(panel, grid);
const now = () => Date.now() / 1000;
const allowed = () => ['admin','full','trading'].includes(window._userRole);
const active = () => !!context && !paused && !denied && !document.hidden && allowed();
function email() { const field=document.getElementById('email'); return String(window._verifiedEmail || field?.dataset.real || '').trim(); }
function message(text) { status.textContent = text; }
function stopRequest() {
  generation++; clearTimeout(timer); timer=null;
  if (flight) { clearTimeout(flight.timeout); flight.controller.abort(); }
  refresh.disabled = false;
}
function validate(data, expected) {
  if (!data || typeof data!=='object' || data.symbol!==expected.symbol || data.region!==expected.region ||
      data.currency!==(expected.region==='IN'?'INR':'USD') || typeof data.source!=='string' ||
      !Array.isArray(data.bars) || data.bars.length>2000) throw Error('Source identity or schema mismatch.');
  if (data.price!=null && (!Number.isFinite(data.price) || data.price<=0)) throw Error('Invalid source price.');
  let previous=null;
  for (const b of data.bars) {
    if (!b || !['time','open','high','low','close','volume'].every(k=>Number.isFinite(b[k])) ||
        Math.min(b.open,b.high,b.low,b.close)<=0 || b.volume<0 || b.time+300>now() ||
        b.low>Math.min(b.open,b.close) || b.high<Math.max(b.open,b.close) ||
        (previous!==null && b.time-previous!==300)) throw Error('Closed-bar data is invalid or incomplete.');
    previous=b.time;
  }
  if (data.bars.length && data.bar_close_time!==previous+300) throw Error('Closed-bar timestamp does not match source history.');
  return data;
}
function state(r) {
  const t=now(), quote=!!r && Number.isFinite(r.quote_time) && r.quote_time>0;
  const recent=quote && Number.isFinite(r.price) && t>=r.quote_time && t-r.quote_time<=300;
  const session=!!r && Number.isFinite(r.session_start) && Number.isFinite(r.session_end) && r.session_start<r.session_end;
  const open=session && r.market_status==='OPEN' && r.session_start<=t && t<r.session_end;
  const closed=session && t>=r.session_end;
  const bars=!!r && r.bars.length>=21 && Number.isFinite(r.bar_close_time) && t>=r.bar_close_time && t-r.bar_close_time<=300;
  const aligned=recent && bars && r.quote_time>=r.bar_close_time && r.bar_close_time>=r.session_start;
  const ready=open && aligned && ['LONG_RESEARCH','BEARISH_RESEARCH'].includes(r.verdict) &&
    !(Array.isArray(r.stages) && r.stages.some(s=>s.status==='blocked'));
  return {recent,open,closed,ready,bars,aligned,signal:ready?r.verdict:'WAIT',
    freshness:!quote?'Timestamp unavailable':t<r.quote_time?'Future timestamp — unverified':recent?'Recent source quote':'Stale source quote'};
}
function speakChange(s) {
  const previous=lastSignal; lastSignal=s.signal;
  if (previous===null || previous===s.signal || !active() || !voice.checked || !window._voiceEnabled || !report) return;
  if (s.ready) window._speak?.(context.symbol+'. '+(s.signal==='LONG_RESEARCH'?'Bullish':'Bearish')+' underlying research conditions changed. Review current source quotes, event risk and position size.',false);
  else if (previous!=='WAIT') window._speak?.(context.symbol+'. The previous underlying candidate is no longer confirmed. Review freshness and session checks.',false);
}
function stamp(value) { return Number.isFinite(value) && value>0 ? new Date(value*1000).toLocaleString() : 'Not supplied'; }
function chart() {
  const box=nodes['bm-chart']; box.replaceChildren();
  if (!report || report.bars.length<2) { box.append(make('p',null,'Closed five-minute history is unavailable. No substitute chart is generated.')); return; }
  const bars=report.bars, values=bars.map(b=>b.close), low=Math.min(...values), high=Math.max(...values), range=high-low||1;
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'); svg.setAttribute('viewBox','0 0 640 170'); svg.setAttribute('role','img');
  const description=bars.length+' actual closed five-minute prices for '+report.symbol+', '+stamp(bars[0].time)+' to '+stamp(report.bar_close_time)+'. Range '+low.toFixed(2)+' to '+high.toFixed(2)+' '+report.currency+'.';
  svg.setAttribute('aria-label',description);
  const title=document.createElementNS(svg.namespaceURI,'title'); title.textContent=description;
  const line=document.createElementNS(svg.namespaceURI,'polyline');
  line.setAttribute('points',values.map((v,i)=>(12+i/(values.length-1)*616).toFixed(2)+','+(152-(v-low)/range*136).toFixed(2)).join(' '));
  line.setAttribute('fill','none'); line.setAttribute('stroke','currentColor'); line.setAttribute('stroke-width','2');
  svg.append(title,line); box.append(svg,make('small',null,bars.length+' closed five-minute bars · '+report.source+' · Last close '+stamp(report.bar_close_time)));
}
function render() {
  const s=state(report);
  nodes['bm-price'].textContent=report && Number.isFinite(report.price)?new Intl.NumberFormat('en-US',{style:'currency',currency:report.currency}).format(report.price):'Unavailable';
  nodes['bm-freshness'].textContent=s.freshness;
  nodes['bm-session'].textContent=s.open?'Regular session open':s.closed?'Market closed':'Closed or session unverified';
  nodes['bm-direction'].textContent=report && ['BULLISH','BEARISH','MIXED'].includes(report.bias)?report.bias+' · source assessment':'Unavailable';
  nodes['bm-readiness'].textContent=s.ready?(s.signal==='LONG_RESEARCH'?'Bullish research candidate':'Bearish research candidate'):'WAIT / REVIEW';
  nodes['bm-reason'].textContent=report?(s.ready?report.reason||'Review the source checks.':!s.open?'Entry readiness blocked: market closed or regular session unverified.':!s.recent?'Entry readiness blocked: quote is stale or its timestamp is unverified.':!s.bars?'Entry readiness blocked: closed five-minute history is stale, missing or insufficient.':!s.aligned?'Entry readiness blocked: source quote predates the signal bar or session alignment is unverified.':report.reason||'Source conditions do not confirm an entry.'):'No usable source evidence returned.';
  nodes['bm-source-time'].textContent='Quote source time: '+stamp(report?.quote_time);
  nodes['bm-fetch-time'].textContent='Provider response fetched: '+stamp(report?.fetched_at)+' (not quote time)';
  panel.dataset.ready=String(s.ready); panel.dataset.state=!report?'unavailable':s.recent?'recent':'stale'; speakChange(s);
}
function schedule() {
  clearTimeout(timer); timer=null;
  if (!active()) return;
  const delay=Math.min(86400000,Math.max(PERIOD,retryAt-Date.now()));
  timer=setTimeout(()=>{timer=null;request();},delay);
  message((requestError ? requestError+' ' : '')+(retryAt>Date.now()?'Provider cooldown until '+new Date(retryAt).toLocaleTimeString()+'. Current display remains a snapshot.':'Updates every 60 seconds while this brief is visible.'));
}
function retryHeader(response) {
  const value=response.headers?.get?.('Retry-After'); if (!value) return;
  const delay=/^\d+$/.test(value)?Date.now()+Number(value)*1000:Date.parse(value);
  if (Number.isFinite(delay)) retryAt=Math.max(retryAt,delay);
}
async function request() {
  if (!active() || flight) return;
  if (Date.now()<retryAt) { schedule(); return; }
  clearTimeout(timer); timer=null;
  const id=generation, expected={...context}, current={controller:new AbortController(),timeout:null};
  flight=current; requestError=''; refresh.disabled=true; message('Checking '+expected.symbol+' market data…');
  current.timeout=setTimeout(()=>current.controller.abort(),TIMEOUT);
  try {
    const response=await fetch('/api/watchlist/research?'+new URLSearchParams({symbol:expected.symbol,region:expected.region}),
      {credentials:'same-origin',headers:{'X-Celesys-Email':email()},signal:current.controller.signal});
    if (id!==generation || current.controller.signal.aborted) return;
    retryHeader(response);
    if (response.status===401 || response.status===403) { denied=true; report=null; chart();render();message('Access denied. Verify an authorized account, then resume.');return; }
    if (!response.ok) { if(response.status===429)retryAt=Math.max(retryAt,Date.now()+PERIOD);throw Error('Market source unavailable (HTTP '+response.status+').'); }
    const data=await response.json();
    if (id!==generation || current.controller.signal.aborted) return;
    report=validate(data,expected);
    if (Number.isFinite(data.provider_status?.retry_after)) retryAt=Math.max(retryAt,data.provider_status.retry_after*1000);
    chart();render();
  } catch(error) {
    if (id!==generation) return;
    report=null; chart();render();
    requestError=current.controller.signal.aborted?'Market request timed out. No substitute quote is shown.':error.message; message(requestError);
  } finally {
    clearTimeout(current.timeout);
    if (flight===current) flight=null;
    refresh.disabled=false;
    if (id===generation) { if(denied){pause.textContent='Resume updates';}else schedule(); }
    else if(active()) request();
  }
}
document.addEventListener('celesys:brief-context',event=>{
  stopRequest(); report=null;lastSignal=null;paused=false;denied=false;requestError='';
  const d=event.detail;
  if (!d || !d.active || d.mode!=='trading' || !['US','IN'].includes(d.region) || typeof d.symbol!=='string' || !/^[A-Z][A-Z0-9.\-]{0,19}$/.test(d.symbol)) { context=null;panel.hidden=true;return; }
  context={symbol:d.symbol,region:d.region};panel.hidden=false;pause.textContent='Pause updates';
  nodes['bm-title'].textContent='Market data · '+d.symbol+' · '+d.region;
  chart();render();lastSignal=null;
  if(!allowed()){message('Live-source updates require an authorized trading account. The original brief remains available.');return;}
  if(document.hidden){message('Paused while this tab is hidden.');return;}request();
});
pause.addEventListener('click',()=>{
  if (!context) return;
  if (paused || denied) { paused=false;denied=false;lastSignal=null;pause.textContent='Pause updates';request(); }
  else { paused=true;stopRequest();pause.textContent='Resume updates';message('Updates paused. Displayed values remain a snapshot.'); }
});
refresh.addEventListener('click',()=>{if(paused){message('Resume updates to request a new quote.');return;}request();});
voice.addEventListener('change',()=>{lastSignal=report?state(report).signal:null;if(voice.checked&&!window._voiceEnabled)message('Enable Voice in the workspace toolbar to hear future status changes.');});
document.addEventListener('visibilitychange',()=>{
  if(!context)return;
  if(document.hidden){stopRequest();message('Paused while this tab is hidden.');}
  else if(!paused&&!denied){lastSignal=null;render();lastSignal=null;request();}
});
window.addEventListener('pagehide',()=>{context=null;stopRequest();});
setInterval(()=>{if(context&&!document.hidden){render();if(!allowed())stopRequest();}},15000);
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',mount,{once:true});
else mount();
})();
