(function(){
'use strict';
const $=id=>document.getElementById(id);if(!$('tw-panel'))return;
const PERIOD=300000,PACE=20000;let generation=0,automatic=false,running=false,alertsActive=false,timer=null,aborter=null,nextAt=0,rows=new Map(),lastSignals=new Map();
function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
function message(text){$('tw-status').textContent=text;}
function stop(reason='Scanner stopped. Displayed results are historical snapshots.'){
 generation++;automatic=false;running=false;alertsActive=false;window._speakQueue=[];window.speechSynthesis?.cancel();clearTimeout(timer);aborter?.abort();nextAt=0;$('tw-start').disabled=false;$('tw-once').disabled=false;message(reason);
}
function config(){const region=$('tw-region').value,syms=[...new Set($('tw-symbols').value.toUpperCase().split(/[\s,]+/).filter(Boolean))];if(!syms.length||syms.length>6||syms.some(s=>! /^[A-Z][A-Z0-9.\-]{0,19}$/.test(s)))throw Error('Enter one to six valid symbols, separated by commas.');return {region,syms};}
function candidate(r){const now=Date.now()/1000;return ['LONG_RESEARCH','BEARISH_RESEARCH'].includes(r.verdict)&&r.market_status==='OPEN'&&Number.isFinite(r.session_start)&&Number.isFinite(r.session_end)&&r.session_start<=now&&now<r.session_end&&Number.isFinite(r.bar_close_time)&&Number.isFinite(r.quote_time)&&r.quote_time>=r.bar_close_time&&now-r.quote_time>=0&&now-r.quote_time<=300&&now-r.bar_close_time>=0&&now-r.bar_close_time<=300;}

function draw(){
 const body=$('tw-rows');body.replaceChildren();const list=[...rows.values()].sort((a,b)=>Number(candidate(b))-Number(candidate(a))||a.symbol.localeCompare(b.symbol));
 for(const r of list){const tr=el('tr'),sym=el('td');sym.append(el('strong',r.symbol),el('small',r.region+' · '+(r.market_status||'Unavailable')));tr.append(sym);
 const price=el('td',Number.isFinite(r.price)?new Intl.NumberFormat('en-US',{style:'currency',currency:r.region==='IN'?'INR':'USD'}).format(r.price):'—');
 const closes=(r.bars||[]).map(b=>b.close).filter(Number.isFinite);
 if(closes.length>1){const lo=Math.min(...closes),span=Math.max(...closes)-lo||1,svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),line=document.createElementNS(svg.namespaceURI,'polyline');svg.setAttribute('viewBox','0 0 140 32');svg.setAttribute('role','img');svg.setAttribute('aria-label','Closed five-minute prices for '+r.symbol);line.setAttribute('points',closes.map((v,i)=>(i*140/(closes.length-1)).toFixed(2)+','+(30-(v-lo)/span*28).toFixed(2)).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke','currentColor');line.setAttribute('stroke-width','2');svg.append(line);price.append(svg);}tr.append(price);
 const result=el('td');result.append(el('strong',candidate(r)?(r.verdict==='LONG_RESEARCH'?'Bullish research candidate':'Bearish research candidate'):'WAIT / REVIEW'),el('small',r.reason||'Source unavailable'));
 const stages=r.stages||[];if(stages.length){const details=el('details');details.append(el('summary',stages.filter(s=>s.status==='pass').length+'/'+stages.length+' checks passed'));for(const s of stages)details.append(el('p',s.name+': '+s.status+' — '+s.detail));result.append(details);}tr.append(result);
 const age=el('td');age.append(el('span',r.quote_time?new Date(r.quote_time*1000).toLocaleString():'No quote timestamp'),el('small',(r.source||'Unverified source')+' · '+(candidate(r)?'Recent source time; feed latency not guaranteed':'Closed, stale, incomplete or setup not aligned')));tr.append(age);
 const action=el('td'),chain=el('button','Review options');chain.type='button';chain.addEventListener('click',()=>{$('ws-region').value=r.region;window.CelesysWorkspace.setMode('options');$('ws-symbol').value=r.symbol;$('ws-search').scrollIntoView({block:'center'});message('Select Load option chain to inspect '+r.symbol+'. Underlying signals are not option entry prices.');});action.append(chain);tr.append(action);body.append(tr);
 }
}
function announce(r){const key=r.region+':'+r.symbol,signal=candidate(r)?r.verdict:'WAIT',previous=lastSignals.get(key);lastSignals.set(key,signal);if(!$('tw-voice').checked||!window._voiceEnabled||previous===signal)return;
 if(signal!=='WAIT')window._speak?.(r.symbol+'. '+(signal==='LONG_RESEARCH'?'Bullish':'Bearish')+' research conditions aligned. Review current option quotes, event risk and position size before acting.',false);
 else if(previous&&previous!=='WAIT')window._speak?.(r.symbol+'. Previous candidate is no longer confirmed. Data may have expired, the market may have closed, or the setup changed. Review the updated checks.',false);
}
async function requestSymbol(symbol,region,id){aborter=new AbortController();const timeout=setTimeout(()=>aborter.abort(),25000);try{const res=await fetch('/api/watchlist/research?'+new URLSearchParams({symbol,region}),{signal:aborter.signal,credentials:'same-origin',headers:{'X-Celesys-Email':email()}});if(res.status===401||res.status===403){if(id===generation)stop('Scan access denied. Enter your authorized email or verify your session.');return;}if(!res.ok)throw Error('Research service HTTP '+res.status);const r=await res.json();if(id!==generation)return;if(r.symbol!==symbol||r.region!==region)throw Error('Source identity mismatch');rows.set(symbol,r);announce(r);}catch(e){if(id!==generation)return;const r={symbol,region,verdict:'WAIT',reason:e.name==='AbortError'?'Request timed out; no substitute prices.':'Research unavailable. Retry later.',stages:[]};rows.set(symbol,r);announce(r);}finally{clearTimeout(timeout);if(id===generation)draw();}}
function cycle(id,cfg,index=0){if(id!==generation||document.hidden)return;if(index>=cfg.syms.length){running=false;$('tw-once').disabled=automatic;if(!automatic){$('tw-start').disabled=false;message('Scan complete. Research snapshots only; review each source timestamp.');return;}nextAt=(Math.floor(Date.now()/PERIOD)+1)*PERIOD+5000;timer=setTimeout(()=>{nextAt=0;running=true;cycle(id,cfg);},nextAt-Date.now());return;}
 message('Scanning '+cfg.syms[index]+' · '+(index+1)+' of '+cfg.syms.length+'. Requests are paced to respect the provider.');requestSymbol(cfg.syms[index],cfg.region,id).then(()=>{if(id!==generation)return;timer=setTimeout(()=>cycle(id,cfg,index+1),index+1<cfg.syms.length?PACE:0);});}
function start(auto){try{if(!['full','admin','trading'].includes(window._userRole)){message('Enter your authorized email in the original account form to scan.');window.CelesysWorkspace?.openAccount?.();$('ws-account').hidden=false;$('ws-account').scrollIntoView({block:'center'});return;}const cfg=config();stop();automatic=auto;running=true;alertsActive=true;rows.clear();lastSignals.clear();draw();$('tw-start').disabled=true;$('tw-once').disabled=true;cycle(generation,cfg);}catch(e){message(e.message);}}
$('tw-start').addEventListener('click',()=>start(true));$('tw-once').addEventListener('click',()=>start(false));$('tw-stop').addEventListener('click',()=>stop());
$('tw-region').addEventListener('change',()=>{stop('Market changed. Start a new scan.');rows.clear();draw();$('tw-symbols').value=$('tw-region').value==='IN'?'NIFTY, BANKNIFTY, RELIANCE':'SPY, QQQ, AAPL';});$('tw-symbols').addEventListener('input',()=>stop('Watchlist changed. Start a new scan.'));
$('tw-voice').addEventListener('change',()=>{if($('tw-voice').checked&&!window._voiceEnabled)$('ws-voice-toggle').click();if(!$('tw-voice').checked){window._speakQueue=[];window.speechSynthesis?.cancel();}});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop('Paused because this tab is hidden. Start again when ready.');});window.addEventListener('pagehide',()=>stop());
setInterval(()=>{if(automatic&&nextAt)message('Next five-minute scan in '+Math.max(0,Math.ceil((nextAt-Date.now())/1000))+' seconds. Keep this tab visible.');},1000);
setInterval(()=>{if(rows.size){if(alertsActive&&!document.hidden)for(const r of rows.values())announce(r);draw();}},30000);
async function feedStatus(){
 const target=$('tw-feed-status');if(!target)return;
 try{const response=await fetch('/api/trading-desk/status',{credentials:'same-origin'});if(!response.ok)throw Error();const data=await response.json();
 const accounts=data.options_accounts||{};target.textContent='Underlying research: '+(data.source||'source unverified')+'; real-time latency is not guaranteed. '+['IN','US'].map(region=>region+' options account feed ('+(accounts[region]?.provider||'unconfigured provider')+'): '+(accounts[region]?.configured?'configured; live connection still requires verification':'not configured')).join('. ')+'. Public snapshots are checked separately. '+(data.authentication?.configured?'Verified sign-in configured.':'Verified sign-in needs email-service setup.');
 }catch(e){target.textContent='Connection status unavailable. Check source timestamps on each result; no live connection is assumed.';}
}
$('tw-feed-refresh')?.addEventListener('click',feedStatus);feedStatus();
// Verified sign-in setup is separate from the original email-only compatibility gate.
async function access(path,body){const r=await fetch('/api/access/'+path,{method:body?'POST':'GET',credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(d.detail||'Sign-in unavailable');return d;}
function email(){const input=$('email');return (input?.dataset.real||input?.value||'').trim();}
$('tw-send-code').addEventListener('click',async()=>{try{const d=await access('start',{email:email()});$('tw-auth-status').textContent=d.message;}catch(e){$('tw-auth-status').textContent=e.message;}});
$('tw-confirm-code').addEventListener('click',async()=>{try{await access('confirm',{email:email(),code:$('tw-code').value.trim()});$('tw-code').value='';$('tw-auth-status').textContent='Verified session active for two hours. Your server permissions apply.';}catch(e){$('tw-auth-status').textContent=e.message;}});
$('tw-signout').addEventListener('click',async()=>{try{await access('logout',{});stop('Signed out.');$('tw-auth-status').textContent='Verified session ended.';}catch(e){$('tw-auth-status').textContent=e.message;}});
access('status').then(d=>{$('tw-auth-status').textContent=d.verified?'Verified session active.':d.configured?'Enter your email above and request a sign-in code.':'Verified sign-in awaits email-service setup. Existing email-only access remains in compatibility mode.';}).catch(()=>{$('tw-auth-status').textContent='Could not check verified sign-in status.';});
})();
