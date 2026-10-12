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
  container.hidden=false;container.append(root);
  let live=true,sequence=0,controller=null,timeout=null,result=null,retryAt=0;
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
  function abort(){sequence++;if(controller)controller.abort();controller=null;clearTimeout(timeout);timeout=null;scan.disabled=false;}
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
  function visibility(){if(document.hidden){abort();result={reason:'Page was hidden. Scan again to verify current account access and contract evidence.'};}else show();}
  scan.addEventListener('click',load);read.addEventListener('click',readTicket);document.addEventListener('visibilitychange',visibility);
  const interval=setInterval(()=>{if(connected()&&!document.hidden&&result?.candidate)show();else if(!connected())dispose();},1000);
  function dispose(){if(!live)return;live=false;abort();clearInterval(interval);document.removeEventListener('visibilitychange',visibility);root.remove();container.hidden=true;if(disposeCurrent===dispose)disposeCurrent=null;}
  disposeCurrent=dispose;show();return dispose;
};
})();
