"""Rank eligible underlying research, never executable options or win probabilities."""
from math import isfinite

def _num(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and isfinite(x)

def rank_reports(reports, region, now, universe):
    if region not in ("IN","US"):
        raise ValueError("Unsupported region")
    allowed=set(universe)
    valid={}
    observed=set()
    for report in reports:
        if not isinstance(report,dict) or report.get("region")!=region:
            continue
        symbol=report.get("symbol")
        if not isinstance(symbol,str) or symbol not in allowed:
            continue
        observed.add(symbol)
        if report.get("stale_cache") or report.get("mode")!="RESEARCH_ONLY" or report.get("market_status")!="OPEN":
            continue
        source=report.get("source")
        if not isinstance(source,str) or source.strip().lower() in ("","market-data","unknown","sample","unverified"):
            continue
        q,b,start,end,price=(report.get(k) for k in ("quote_time","bar_close_time","session_start","session_end","price"))
        if not all(_num(x) for x in (q,b,start,end,price)) or not (0<price and 0<end-start<=86400 and start<=b<=q<=now<end and now-b<=300 and now-q<=300):
            continue
        verdict=report.get("verdict")
        if verdict not in ("LONG_RESEARCH","BEARISH_RESEARCH"):
            continue
        stages=report.get("stages")
        if not isinstance(stages,list) or any(not isinstance(s,dict) or s.get("status")=="blocked" for s in stages):
            continue
        gates={s.get("name"):s.get("status") for s in stages}
        if not all(gates.get(k)=="pass" for k in ("Data steward","Session guard","Trend analyst","Setup analyst","Risk critic","Quote guard","Research coordinator")):
            continue
        scenario=report.get("scenario")
        if not isinstance(scenario,dict) or scenario.get("kind")!="UNDERLYING_ONLY":
            continue
        entry,stop,target=(scenario.get(k) for k in ("entry","stop","target"))
        if not all(_num(x) and x>0 for x in (entry,stop,target)) or not (stop<entry<target if verdict=="LONG_RESEARCH" else target<entry<stop):
            continue
        metrics=report.get("metrics")
        volume=metrics.get("relative_volume") if isinstance(metrics,dict) else None
        if not _num(volume) or volume<=0:
            continue
        item=dict(symbol=symbol,region=region,direction="BULLISH" if verdict=="LONG_RESEARCH" else "BEARISH",
            status="RESEARCH_ONLY",confidence="ENTRY_UNCONFIRMED",source=source,quote_time=q,bar_close_time=b,
            expires_at=min(q+300,b+300,end),price=price,currency="USD" if region=="US" else "INR",
            scenario=dict(kind="UNDERLYING_ONLY",entry=entry,stop=stop,target=target),option_entry_verified=False)
        if item["expires_at"]<=now:
            continue
        sort_key=(-volume,-q,symbol)
        if symbol not in valid or q>valid[symbol][1]["quote_time"]:
            valid[symbol]=(sort_key,item)
    ordered=sorted(valid.values(),key=lambda x:x[0])[:5]
    return dict(region=region,generated_at=now,coverage=dict(universe_size=len(allowed),observed=len(observed)),
        status="RESEARCH_CANDIDATES" if ordered else "NO_QUALIFYING_CANDIDATES",
        opportunities=[dict(item,rank=i) for i,(_,item) in enumerate(ordered,1)],
        note="Fresh underlying research only; not verified options entry or probability of profit.")
