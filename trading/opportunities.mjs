const $=id=>document.getElementById(id);
let region="US",requestId=0,controller=null;
const label={SCANNING:"Scanning",AWAITING_FIRST_CYCLE:"Awaiting scan",SCANNER_DISABLED:"Not enabled",MARKET_CLOSED_REGULAR_HOURS:"Market closed",RESEARCH_CANDIDATES:"Research candidates",NO_FRESH_CANDIDATES:"No fresh setups"};
function stamp(value){
  return Number.isFinite(value)?new Date(value*1000).toLocaleTimeString("en-US",{timeZone:region==="US"?"America/New_York":"Asia/Kolkata",hour:"2-digit",minute:"2-digit",timeZoneName:"short"}):"—";
}
function cell(tag,text,cls){
  const el=document.createElement(tag);
  el.textContent=text;
  if(cls)el.className=cls;
  return el;
}
function render(data){
  if(data.region!==region)throw Error("Wrong region");
  const now=Date.now()/1000;
  const fresh=Array.isArray(data.opportunities)?data.opportunities.filter(x=>x.region===region&&Number.isFinite(x.expires_at)&&x.expires_at>now&&x.status==="RESEARCH_ONLY"&&["BULLISH","BEARISH"].includes(x.direction)&&/^[A-Z][A-Z0-9.-]{0,19}$/.test(x.symbol)).slice(0,5):[];
  const historical=!fresh.length&&Array.isArray(data.last_shortlist)?data.last_shortlist.filter(x=>/^[A-Z][A-Z0-9.-]{0,19}$/.test(x.symbol)&&["BULLISH","BEARISH"].includes(x.direction)).slice(0,5):[];
  $("opportunity-state").textContent=label[data.status]||"Unverified";
  $("opportunity-scope").textContent=(region==="US"?"USA":"India")+" · hourly liquid watchlist · research only";
  $("opportunity-meta").textContent="Scanned "+(data.coverage?.attempted??0)+"/"+(data.coverage?.universe_size??"—")+" · Last cycle "+stamp(data.cycle_completed_at)+" · Next "+stamp(data.next_cycle_at);
  const list=$("opportunity-list");
  list.replaceChildren();
  if(!fresh.length&&!historical.length){list.append(cell("p",data.status==="MARKET_CLOSED_REGULAR_HOURS"?"No current entries outside regular hours.":"No verified qualifying setup to display.","opportunity-empty"));return;}
  if(historical.length)list.append(cell("p","Previous shortlist · expired, not a current signal","opportunity-empty"));
  for(const row of fresh.length?fresh:historical){
    const button=cell("button","","opportunity-row");
    button.type="button";
    button.dataset.opportunitySymbol=row.symbol;
    button.append(cell("span",String(row.rank??"—"),"opportunity-rank"),cell("strong",row.symbol),
      cell("span",row.direction==="BULLISH"?"Bullish":"Bearish",row.direction==="BULLISH"?"opportunity-up":"opportunity-down"),
      cell("span",historical.length?"Expired · recheck":"WAIT · entry unconfirmed","opportunity-entry"));
    list.append(button);
  }
}
async function load(){
  const id=++requestId;
  controller?.abort();
  controller=new AbortController();
  const signal=controller.signal;
  const timeout=setTimeout(()=>controller?.abort(),10000);
  try{
    const response=await fetch("/api/trading-desk/opportunities?region="+region,{cache:"no-store",signal});
    if(!response.ok)throw Error("Scanner unavailable");
    const data=await response.json();
    if(id===requestId)render(data);
  }catch(e){
    if(id!==requestId)return;
    $("opportunity-state").textContent="Data unavailable";
    $("opportunity-meta").textContent="No verified ranking available.";
    $("opportunity-list").replaceChildren();
  }finally{clearTimeout(timeout);}
}
for(const button of document.querySelectorAll("[data-region]")){
  if(button.getAttribute("aria-pressed")==="true")region=button.dataset.region;
  button.addEventListener("click",()=>{region=button.dataset.region;$("opportunity-list").replaceChildren();$("opportunity-state").textContent="Checking";load();});
}
$("opportunity-list").addEventListener("click",event=>{
  const row=event.target.closest("[data-opportunity-symbol]");
  if(!row)return;
  $("symbol").value=row.dataset.opportunitySymbol;
  $("symbol").dispatchEvent(new Event("input",{bubbles:true}));
  $("scan-form").requestSubmit();
  $("guided-action").scrollIntoView({block:"nearest",behavior:"auto"});
});
document.addEventListener("visibilitychange",()=>{if(!document.hidden)load();});
setInterval(()=>{if(!document.hidden)load();},30000);
load();
