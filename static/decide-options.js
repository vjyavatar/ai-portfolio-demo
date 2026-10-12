(function () {
'use strict';
let disposeCurrent=null;
const roles=['admin','full','trading'];
function node(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
function money(n){return Number.isFinite(n)?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(n):'Unavailable';}
window.unmountDecideOptions=function(){if(disposeCurrent)disposeCurrent();};
window.mountDecideOptions=function(container,context){
  window.unmountDecideOptions();
  if(typeof container==='string')container=document.getElementById(container);
  if(!container||!context)return function(){};
  const symbol=String(context.symbol||'').toUpperCase(),region=context.region;
  if(!/^[A-Z][A-Z0-9.\-]{0,19}$/.test(symbol)||!['IN','US'].includes(region))return function(){};
  const root=node('section');root.id='de-options-ticket';root.setAttribute('aria-label','Call and put buy research ticket');
  const style=node('style');style.textContent='#de-options-ticket{margin:18px 0;padding:22px;border:1px solid var(--border2,#cedbe7);border-top:3px solid var(--teal,#087b68);border-radius:14px;background:var(--surface,#fff);color:var(--text,#18324b);font:14px system-ui;text-align:left}#de-options-ticket h3{margin:0 0 8px;font-size:20px}#de-options-ticket p{line-height:1.6}#de-options-ticket button{padding:11px 16px;border:1px solid var(--border2,#cad6df);border-radius:8px;background:var(--bg2,#eef6f4);color:var(--text,#18324b);font:inherit;cursor:pointer}#de-options-ticket button:disabled{opacity:.6;cursor:wait}#de-options-ticket .do-controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center}#de-options-ticket dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}#de-options-ticket dl>div{padding:12px;border-radius:8px;background:var(--bg2,#f3f6f9)}#de-options-ticket dt{font-size:11px;color:var(--text2,#52677a)}#de-options-ticket dd{margin:5px 0 0;overflow-wrap:anywhere;font-weight:650}#de-options-ticket small{color:var(--text2,#52677a);line-height:1.6}#de-options-ticket input{width:18px;height:18px;vertical-align:middle}#de-options-ticket [data-state=wait]{color:var(--amber,#94620b)}@media(max-width:700px){#de-options-ticket{padding:16px}#de-options-ticket dl{grid-template-columns:repeat(2,minmax(0,1fr))}}';root.append(style);
  root.append(node('h3',symbol+' · Call / put buy ticket'),node('p','Existing analysis supplies the context. This ticket separately checks a supported option contract and its source quotes. No order is sent.'));
  const controls=node('div');controls.className='do-controls';
  const scan=node('button','Scan call / put buys');scan.id='de-options-scan';scan.type='button';
  const voiceLabel=node('label');const voice=node('input');voice.id='de-options-voice';voice.type='checkbox';voiceLabel.append(voice,node('span',' Enable spoken readout'));
  const read=node('button','Read ticket');read.id='de-options-read';read.type='button';controls.append(scan,voiceLabel,read);root.append(controls);
  const title=node('h4','WAIT — scan contract evidence');title.id='de-options-verdict';
  const reason=node('p');reason.id='de-options-reason';reason.setAttribute('role','status');
  const direction=node('p');direction.id='de-options-direction';direction.textContent='Original underlying direction: '+String(context.direction||'Unverified')+'. A direction alone is not a call / put buy signal.';
  const confidence=node('p');confidence.id='de-options-confidence';
  const score=Number.isFinite(context.modelScore)&&context.modelScore>=0&&context.modelScore<=100?String(context.modelScore):'Unavailable';
  const scorePrefix=score==='Unavailable'?'':'Original model score: '+score+' / 100. Model score is not a win probability. ';
  confidence.textContent=scorePrefix+'Contract confidence: uncalibrated; no tested success probability.';
  const fields=node('dl');const values={};
  for(const [key,label]of [['type','Contract side'],['strike','Strike'],['expiry','Expiry'],['entry','Entry range / limit'],['stop','Premium stop'],['target','Premium target'],['invalidation','Underlying invalidation'],['underlyingTarget','Underlying target'],['loss','Maximum contract loss']]){const item=node('div'),v=node('dd','Unavailable');v.id='de-options-'+key;values[key]=v;item.append(node('dt',label),v);fields.append(item);}
  const source=node('p');source.id='de-options-source';const ranking=node('p');ranking.id='de-options-ranking';
  root.append(title,reason,direction,confidence,fields,source,ranking,node('small','Candidate only. Reconfirm broker quotes, liquidity and events. Stops are not guaranteed; the full premium plus costs can be lost. Exercise may create separate underlying exposure. Greeks are hourly provider estimates, not live ticks.'));
  const chainWrap=node('section');chainWrap.id='de-option-chain';
  chainWrap.append(node('h4','Private option chain'));
  const chainControls=node('div');chainControls.className='do-controls';
  const chainButton=node('button','View option chain');chainButton.id='de-chain-load';chainButton.type='button';
  const expiryLabel=node('label','Expiry '),expirySelect=node('select');expirySelect.id='de-chain-expiry';expirySelect.disabled=true;expiryLabel.append(expirySelect);
  chainControls.append(chainButton,expiryLabel);chainWrap.append(chainControls);
  const chainStatus=node('p','Source not checked. View the chain to request an authorized provider snapshot.');chainStatus.id='de-chain-status';chainStatus.setAttribute('role','status');
  const chainSource=node('p');chainSource.id='de-chain-source';
  const chainAnalytics=node('p');chainAnalytics.id='de-chain-analytics';chainAnalytics.hidden=true;
  const chainScroll=node('div');chainScroll.style.overflowX='auto';chainScroll.setAttribute('tabindex','0');chainScroll.setAttribute('aria-label','Scrollable option chain');
  const chainTable=node('table');chainTable.id='de-chain-table';chainTable.hidden=true;chainTable.style.cssText='width:100%;min-width:850px;border-collapse:collapse;font-size:12px;text-align:right';
  const caption=node('caption','Call / put quotes — snapshot research only, no automatic buy recommendation');chainTable.append(caption);
  const head=node('thead'),header=node('tr');for(const label of ['Call bid / ask','Call OI / volume','Call quote time','Strike','Put bid / ask','Put OI / volume','Put quote time']){const th=node('th',label);th.setAttribute('scope','col');th.style.padding='10px';header.append(th);}head.append(header);chainTable.append(head);
  const chainBody=node('tbody');chainTable.append(chainBody);chainScroll.append(chainTable);chainWrap.append(chainStatus,chainSource,chainAnalytics,chainScroll);root.append(chainWrap);
  container.hidden=false;container.append(root);
  let live=true,sequence=0,controller=null,timeout=null,result=null,retryAt=0;
  let chainController=null,chainTimeout=null,chainSequence=0,chainResult=null,chainRetryAt=0;
  const chainCache=new Map();
  const supported=region==='US'&&['SPY','QQQ'].includes(symbol);
  const connected=()=>live&&root.isConnected!==false;
  const allowed=()=>roles.includes(window._userRole);
  const now=()=>Date.now()/1000;
  const recent=(v,age)=>Number.isFinite(v)&&v>0&&now()>=v&&now()-v<=age;
  function eligible(data){
    const c=data?.candidate,type=data?.status==='BUY_CALL_CANDIDATE'?'CALL':data?.status==='BUY_PUT_CANDIDATE'?'PUT':null;
    if(!allowed()||!supported||!type||!c||data.direction!==type||!/^\d{4}-\d{2}-\d{2}$/.test(c.expiry||''))return false;
    const occ=symbol+c.expiry.replaceAll('-','').slice(2)+type[0]+String(Math.round(c.strike*1000)).padStart(8,'0');
    return c.contract===occ&&Number.isFinite(c.strike)&&c.strike>0&&Number.isFinite(c.bid)&&Number.isFinite(c.ask)&&c.bid>0&&c.ask>=c.bid&&
      recent(c.bid_time,300)&&recent(c.ask_time,300)&&recent(c.greeks_source_time,3600)&&Number.isFinite(c.expires_at)&&now()<c.expires_at&&
      c.expires_at<=Math.min(c.bid_time+300,c.ask_time+300,c.greeks_source_time+3600)&&
      c.entry?.kind==='QUOTED_BID_ASK_RANGE'&&c.entry.currency==='USD'&&c.entry.unit==='PREMIUM_PER_SHARE'&&c.entry.fill_guaranteed===false&&
      c.entry.low===c.bid&&c.entry.high===c.ask&&Number.isFinite(c.entry.limit_cap)&&c.entry.limit_cap>=c.bid&&c.entry.limit_cap<=c.ask&&
      c.contract_multiplier===100&&c.premium_risk?.scope==='LONG_OPTION_PREMIUM_ONLY'&&c.premium_risk.currency==='USD'&&
      Number.isFinite(c.premium_risk.maximum_loss_per_contract)&&Math.abs(c.premium_risk.maximum_loss_per_contract-c.entry.limit_cap*100)<0.001;
  }
  function blank(){confidence.textContent=scorePrefix+'Contract confidence: uncalibrated; no tested success probability.';for(const v of Object.values(values))v.textContent='Unavailable';source.textContent='No current contract quote verified.';ranking.textContent='';}
  function show(){
    if(!connected())return;
    if(!allowed())result={reason:'Verified sign-in with full trading access is required. Scan again after signing in.'};
    const valid=eligible(result);root.dataset.state=valid?'candidate':'wait';title.textContent=valid?result.status.replaceAll('_',' '):'WAIT — no current buy candidate';title.dataset.state=valid?'candidate':'wait';
    if(!valid){blank();reason.textContent=result?.candidate?'Contract evidence expired or failed identity / source checks. Scan again; do not reuse this ticket.':result?.reason||(!supported?'Automated option candidates currently support US SPY and QQQ only. India and other symbols require a connected, verified option feed.':'Scan to check a source-backed option candidate.');return;}
    const c=result.candidate;reason.textContent=result.reason||'Review current source quotes before considering this candidate.';
    values.type.textContent='BUY '+result.direction+' · review candidate';values.strike.textContent=money(c.strike);values.expiry.textContent=c.expiry;
    values.entry.textContent=money(c.entry.low)+' – '+money(c.entry.high)+' · Limit cap '+money(c.entry.limit_cap)+' (fill not guaranteed)';
    const policy=c.exit_policy?.kind==='ILLUSTRATIVE_POLICY_NOT_FORECAST'&&c.exit_policy.basis==='ASK_CAP_NOT_ACTUAL_FILL'?c.exit_policy:null;
    values.stop.textContent=policy&&Number.isFinite(policy.stop_premium)?money(policy.stop_premium)+' · illustrative policy, not guaranteed':'Not supplied — review underlying invalidation';
    values.target.textContent=policy&&Number.isFinite(policy.target_premium)?money(policy.target_premium)+' · illustrative policy, not a forecast':'Not supplied — review underlying target';
    values.invalidation.textContent=money(c.underlying_invalidation);values.underlyingTarget.textContent=money(c.underlying_target);values.loss.textContent=money(c.premium_risk.maximum_loss_per_contract)+' + costs (100 units)';
    const conf=c.confidence||result.confidence;
    confidence.textContent=scorePrefix+'Contract confidence: '+(conf?.status==='UNCALIBRATED'?'uncalibrated; no success probability is established.':'unavailable; no verified success probability.')+' Model score is not a win probability.';
    ranking.textContent=(Array.isArray(conf?.basis)?'Evidence: '+conf.basis.filter(v=>typeof v==='string').join(' · ')+'. ':'')+(typeof c.ranking?.method==='string'?'Selection: '+c.ranking.method+' ':'')+(typeof c.ranking?.note==='string'?c.ranking.note+' ':'')+'Coverage: nearest non-0DTE expiry in the returned provider chain only; not a market-wide best trade.';
    source.textContent=c.contract+' · '+String(result.source||'Provider')+' · Bid '+money(c.bid)+' at '+new Date(c.bid_time*1000).toLocaleString()+' · Ask '+money(c.ask)+' at '+new Date(c.ask_time*1000).toLocaleString()+'. Evidence expires '+new Date(c.expires_at*1000).toLocaleTimeString()+'.';
  }
  function abort(){abortChain();sequence++;if(controller)controller.abort();controller=null;clearTimeout(timeout);timeout=null;scan.disabled=false;}
  async function load(){
    if(!connected()||document.hidden||controller)return;
    if(!allowed()){result={reason:'An authorized trading account is required.'};show();return;}
    if(!supported){result=null;show();return;}
    if(Date.now()<retryAt){reason.textContent='Provider cooldown active. Retry after '+new Date(retryAt).toLocaleTimeString()+'.';return;}
    const id=++sequence,current=new AbortController();controller=current;scan.disabled=true;result=null;show();reason.textContent='Checking '+symbol+' option source quotes…';
    timeout=setTimeout(()=>current.abort(),25000);
    try{
      const response=await fetch('/api/trading-desk/options?'+new URLSearchParams({symbol,region}),{credentials:'same-origin',signal:current.signal});
      if(!connected()||id!==sequence||current.signal.aborted)return;
      const retry=response.headers?.get?.('Retry-After');if(retry){const date=/^\d+$/.test(retry)?Date.now()+Number(retry)*1000:Date.parse(retry);if(Number.isFinite(date))retryAt=Math.max(retryAt,date);}
      if(!response.ok)throw Error(response.status===401||response.status===403?'Verified sign-in with full trading access is required. An email header alone does not authenticate this request.':'Option provider unavailable (HTTP '+response.status+'). No buy ticket.');
      const data=await response.json();if(!connected()||id!==sequence||current.signal.aborted)return;
      result=data&&typeof data==='object'?data:{reason:'Invalid option response. No buy ticket.'};show();
    }catch(error){if(connected()&&id===sequence){result={reason:current.signal.aborted?'Option request timed out. No buy ticket.':error.message};show();}}
    finally{if(id===sequence){clearTimeout(timeout);controller=null;scan.disabled=false;}}
  }
  function clearChain(text){chainAnalytics.hidden=true;chainAnalytics.textContent='';chainResult=null;chainBody.replaceChildren();chainTable.hidden=true;chainSource.textContent='';if(text)chainStatus.textContent=text;}
  function abortChain(){chainSequence++;if(chainController)chainController.abort();chainController=null;clearTimeout(chainTimeout);chainTimeout=null;chainButton.disabled=false;}
  function chainValid(data,expiry){
    if(!data||data.symbol!==symbol||data.region!==region||data.currency!==(region==='IN'?'INR':'USD')||typeof data.source!=='string'||!Array.isArray(data.rows)||data.rows.length>2000)throw Error('Chain source identity or schema could not be verified.');
    if(data.status!=='SNAPSHOT')return data;
    if(!/^\d{4}-\d{2}-\d{2}$/.test(data.expiry||'')||(expiry&&data.expiry!==expiry)||!Array.isArray(data.expiries)||!data.expiries.includes(data.expiry))throw Error('Chain expiry could not be verified.');
    const strikes=new Set();for(const row of data.rows){if(!row||!Number.isFinite(row.strike)||row.strike<=0||strikes.has(row.strike))throw Error('Invalid or duplicate chain strikes.');strikes.add(row.strike);for(const side of [row.call,row.put]){if(side!=null&&typeof side!=='object')throw Error('Invalid chain quote.');}}
    return data;
  }
  function quoteTimes(side){
    if(!side)return '—';
    const bid=Number.isFinite(side.bid_time)&&side.bid_time>0?new Date(side.bid_time*1000).toLocaleString():'unknown';
    const ask=Number.isFinite(side.ask_time)&&side.ask_time>0?new Date(side.ask_time*1000).toLocaleString():'unknown';
    const feed=side.feed_time_kind==='EXCHANGE_FEED_SNAPSHOT_IST_NOT_SIDE_SPECIFIC'&&Number.isFinite(side.feed_time)&&side.feed_time>0?' · Exchange feed snapshot '+new Date(side.feed_time*1000).toLocaleString()+' (not side-specific)':'';
    return 'Bid '+bid+' / Ask '+ask+feed;
  }
  function chainFreshness(){
    if(!chainResult)return;
    if(!allowed()){chainCache.clear();clearChain('Verified sign-in with full access is required. View the chain again after signing in.');return;}
    const quotes=chainResult.rows.flatMap(r=>[r.call,r.put]).filter(Boolean);
    const verified=quotes.length>0&&quotes.every(q=>recent(q.bid_time,300)&&recent(q.ask_time,300)&&Number.isFinite(q.bid)&&Number.isFinite(q.ask)&&q.bid>0&&q.ask>=q.bid);
    chainStatus.textContent=(verified?'Recent source quotes (session not verified). ':'Snapshot / quote timing unverified or stale. ')+String(chainResult.message||'')+' Chain data alone does not qualify a buy ticket.';
  }
  function showChain(data){
    if(!connected()||!allowed())return;
    clearChain();chainResult=data;
    if(data.status!=='SNAPSHOT'||!data.rows.length){chainResult=null;chainSource.textContent=data.source+' · '+symbol+' · No usable chain returned.';chainStatus.textContent=data.message||'No chain quotes available.';return;}
    const expiryOptions=data.expiries.filter(d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d));
    expirySelect.replaceChildren(...expiryOptions.map(d=>{const option=node('option',d);option.value=d;return option;}));expirySelect.value=data.expiry;expirySelect.disabled=false;
    const number=value=>Number.isFinite(value)&&value>=0?String(value):'—';
    const price=value=>Number.isFinite(value)&&value>=0?new Intl.NumberFormat('en-US',{style:'currency',currency:data.currency}).format(value):'—';
    for(const row of data.rows.slice().sort((a,b)=>a.strike-b.strike)){
      const tr=node('tr');
      const columns=[];for(const side of [row.call,row.put]){
        const crossed=side&&Number.isFinite(side.bid)&&Number.isFinite(side.ask)&&side.bid>side.ask;
        columns.push(crossed?'Invalid crossed quote':price(side?.bid)+' / '+price(side?.ask),number(side?.oi)+' / '+number(side?.volume)+(Number.isInteger(side?.lot_size)&&side.lot_size>0?' · Lot '+side.lot_size:''),quoteTimes(side));
      }
      columns.splice(3,0,price(row.strike));for(const value of columns){const cell=node('td',value);cell.style.cssText='padding:10px;border-top:1px solid var(--border,#e2e5ea);white-space:nowrap';tr.append(cell);}chainBody.append(tr);
    }
    chainTable.hidden=false;
    const fetched=Number.isFinite(data.fetched_at)?new Date(data.fetched_at*1000).toLocaleString():'Not supplied';
    chainSource.textContent=data.source+' · '+symbol+' · '+data.expiry+' · '+data.rows.length+' strikes · Fetched '+fetched+' (not quote time). OI and volume are provider snapshots; unknown bid / ask times remain unknown.';
    if(data.coverage?.scope==='BOUNDED_NEAR_SPOT_WINDOW_NOT_FULL_CHAIN'){
      const coverage=data.coverage;
      chainSource.textContent+=' Partial coverage: at most 25 strikes near the underlying price, not the full chain.'+
        (Number.isInteger(coverage.returned_strikes)&&Number.isInteger(coverage.available_paired_strikes)?' Returned '+coverage.returned_strikes+' of '+coverage.available_paired_strikes+' available paired strikes.':'')+
        (Number.isInteger(coverage.returned_contracts)&&Number.isInteger(coverage.requested_contracts)?' Returned '+coverage.returned_contracts+' of '+coverage.requested_contracts+' requested contracts.':'');
    }
    const analytics=window.CelesysOptionsAnalytics;
    if(analytics&&typeof analytics.analyze==='function'){
      try{
        const metrics=analytics.analyze(data.rows);
        const ratio=x=>Number.isFinite(x)?x.toFixed(2):'Unavailable';
        const pain=Number.isFinite(metrics.maxPain?.strike)?String(metrics.maxPain.strike):'Unavailable (missing, zero or tied evidence)';
        chainAnalytics.textContent='Chain analytics v1 · Returned strikes only: OI put/call ratio '+ratio(metrics.pcr?.oi)+
          ' · Volume put/call ratio '+ratio(metrics.pcr?.volume)+' · Minimum expiry payout strike '+pain+
          '. Subset calculation, not a forecast, full-market max-pain level or buy recommendation. '+
          'Uses the snapshot above; stale or incomplete data limits interpretation.';
        chainAnalytics.hidden=false;
      }catch(_){chainAnalytics.textContent='Chain analytics unavailable: source rows failed validation.';chainAnalytics.hidden=false;}
    }
    chainFreshness();
  }
  async function loadChain(expiry){
    expiry=typeof expiry==='string'?expiry:'';
    if(!connected()||document.hidden||chainController)return;
    if(!allowed()){clearChain('Verified sign-in with full access is required to view the private chain.');return;}
    if(region==='IN'&&!['NIFTY','BANKNIFTY'].includes(symbol)){clearChain('This India chain viewer currently supports NIFTY and BANKNIFTY.');return;}
    if(chainResult&&expiry&&chainResult.expiry!==expiry)clearChain('Checking selected expiry…');
    const cached=chainCache.get(expiry);if(cached&&Date.now()-cached.receivedAt<60000){showChain(cached.data);return;}
    if(Date.now()<chainRetryAt){chainStatus.textContent='Provider cooldown active. Retry after '+new Date(chainRetryAt).toLocaleTimeString()+'.';return;}
    const id=++chainSequence,current=new AbortController();chainController=current;chainButton.disabled=true;clearChain('Fetching authorized option-chain snapshot…');
    chainTimeout=setTimeout(()=>current.abort(),30000);
    try{
      const response=await fetch('/api/private-options/chain?'+new URLSearchParams({region,symbol,expiry}),{credentials:'same-origin',signal:current.signal});
      if(!connected()||id!==chainSequence||current.signal.aborted)return;
      const header=response.headers?.get?.('Retry-After');if(header){const until=/^\d+$/.test(header)?Date.now()+Number(header)*1000:Date.parse(header);if(Number.isFinite(until))chainRetryAt=Math.max(chainRetryAt,until);}
      if(!response.ok)throw Error([401,403].includes(response.status)?'Verified sign-in with full access is required.':'Option chain unavailable (HTTP '+response.status+').');
      const data=await response.json();if(!connected()||id!==chainSequence||current.signal.aborted)return;
      const checked=chainValid(data,expiry);if(Number.isFinite(checked.retry_after))chainRetryAt=Math.max(chainRetryAt,checked.retry_after*1000);
      if(checked.status==='SNAPSHOT'){chainCache.set(expiry,{data:checked,receivedAt:Date.now()});chainCache.set(checked.expiry,{data:checked,receivedAt:Date.now()});}
      showChain(checked);
    }catch(error){if(connected()&&id===chainSequence)clearChain(current.signal.aborted?'Option chain request timed out. No substitute quotes shown.':error.message);}
    finally{if(id===chainSequence){clearTimeout(chainTimeout);chainController=null;chainButton.disabled=false;}}
  }
  chainButton.addEventListener('click',()=>loadChain(expirySelect.value||''));
  expirySelect.addEventListener('change',()=>{abortChain();loadChain(expirySelect.value);});
  function readTicket(){
    if(!connected())return;
    if(!voice.checked||window._voiceEnabled!==true){reason.textContent='Enable spoken readout and the workspace Voice control first.';return;}
    if(!allowed()||document.hidden)return;
    show();
    let text=symbol+'. WAIT. '+reason.textContent;
    if(eligible(result)){
      const c=result.candidate;
      text=symbol+'. '+result.direction+' research candidate. Strike '+c.strike+', expiry '+c.expiry+', entry limit '+c.entry.limit_cap+'. '+
        'Premium stop: '+values.stop.textContent+'. Premium target: '+values.target.textContent+'. These optional policy levels are illustrative, not forecasts, and must be recalculated from the actual fill. '+
        'Underlying invalidation '+values.invalidation.textContent+', underlying target '+values.underlyingTarget.textContent+'. '+
        'Maximum premium loss per contract '+money(c.premium_risk.maximum_loss_per_contract)+' plus costs. Stops do not cap this loss. '+
        'Confidence is uncalibrated. Model score is not a win probability. Review risk, events and live broker quotes.';
    }
    window._speak?.(text,false);
  }
  function visibility(){if(document.hidden){abort();chainCache.clear();clearChain('Page was hidden. View the chain again to verify current access and source quotes.');result={reason:'Page was hidden. Scan again to verify current account access and contract evidence.'};}else show();}
  scan.addEventListener('click',load);read.addEventListener('click',readTicket);document.addEventListener('visibilitychange',visibility);
  const interval=setInterval(()=>{if(connected()&&!document.hidden&&chainResult)chainFreshness();if(connected()&&!document.hidden&&result?.candidate)show();else if(!connected())dispose();},1000);
  function dispose(){if(!live)return;live=false;abort();clearInterval(interval);document.removeEventListener('visibilitychange',visibility);root.remove();container.hidden=true;if(disposeCurrent===dispose)disposeCurrent=null;}
  disposeCurrent=dispose;show();return dispose;
};
})();
