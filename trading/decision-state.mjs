export function classify({report=null,options=null,region,symbol,busy=false,sample=false,closed=false,now=Date.now()/1000}={}){
  const result=(state,title,reason,confidence="UNAVAILABLE",contract=null)=>({state,title,reason,confidence,contract});
  if(sample||report?.mode==="SAMPLE")return result("SAMPLE","SAMPLE — NOT TRADEABLE","Practice data only.");
  if(closed)return result("CLOSED","MARKET CLOSED — NO TRADE","Regular session closed. Last available data is for research only.");
  if(busy)return result("SCANNING","WAIT — SCANNING","Checking current market data and contract evidence.");
  if(!report||report.region!==region||report.symbol!==symbol)return result("UNAVAILABLE","NO TRADE — DATA UNAVAILABLE","No verified report for the selected instrument.");
  const validTime=t=>Number.isFinite(t)&&now>=t&&now-t<=300;
  const fresh=!report.stale_cache&&report.market_status==="OPEN"&&Number.isFinite(report.session_start)&&Number.isFinite(report.session_end)&&report.session_start<=now&&now<report.session_end&&report.session_end-report.session_start<=86400&&validTime(report.quote_time)&&validTime(report.bar_close_time)&&report.session_start<=report.bar_close_time&&report.bar_close_time<=report.quote_time&&Number.isFinite(report.price)&&report.price>0&&Array.isArray(report.bars)&&report.bars.length>0;
  if(!fresh)return result("UNAVAILABLE","NO TRADE — DATA UNVERIFIED","Price, session or timestamp evidence is missing or expired.");
  const side=report.verdict==="LONG_RESEARCH"?"CALL":report.verdict==="BEARISH_RESEARCH"?"PUT":null;
  const gates=Array.isArray(report.stages)?report.stages:[];
  const names=["Data steward","Session guard","Trend analyst","Setup analyst","Risk critic","Quote guard"];
  if(!side||gates.some(s=>!s||s.status==="blocked")||!names.every(n=>gates.some(s=>s?.name===n&&s.status==="pass")))return result("WAIT","WAIT — NO ENTRY YET","No qualifying entry. The next scan will recheck.","LOW");
  const label=region==="IN"?(side==="CALL"?"CE":"PE"):side;
  const c=options?.candidate;
  const match=region==="US"&&["SPY","QQQ"].includes(symbol)&&options?.status===`BUY_${side}_CANDIDATE`&&typeof c?.contract==="string"&&new RegExp(`^${symbol}[0-9]{6}${side[0]}[0-9]{8}$`).test(c.contract)&&Number.isFinite(c.expires_at)&&now<c.expires_at&&[c.bid_time,c.ask_time].every(t=>validTime(t)&&t>=report.bar_close_time)&&Number.isFinite(c.bid)&&Number.isFinite(c.ask)&&0<c.bid&&c.ask>=c.bid;
  return match?result("REVIEW",`WAIT — REVIEW ${label} CONTRACT`,"Contract snapshot qualifies for review; broker and event risk still require confirmation.","MODERATE — ENTRY UNCONFIRMED",c):result("BIAS",`WAIT — ${label} BIAS`,options?.reason||"Directional evidence aligns; option entry is not verified.","MODERATE — ENTRY UNCONFIRMED");
}
