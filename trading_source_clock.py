"""Trading Desk-specific session and source-time normalization.
Never infer an executable quote from a retrieval timestamp or candle close.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from trading_research import number

def normalize(payload,region,now):
    rows=(payload.get("chart") or {}).get("result") if isinstance(payload,dict) else None
    if not isinstance(rows,list) or not rows or not isinstance(rows[0],dict):
        return payload
    raw=rows[0]
    meta=raw.get("meta")
    if not isinstance(meta,dict):
        return payload
    local=datetime.fromtimestamp(now,ZoneInfo("America/New_York" if region=="US" else "Asia/Kolkata"))
    start_clock,end_clock=((9,30),(16,0)) if region=="US" else ((9,15),(15,30))
    start=local.replace(hour=start_clock[0],minute=start_clock[1],second=0,microsecond=0).timestamp()
    end=local.replace(hour=end_clock[0],minute=end_clock[1],second=0,microsecond=0).timestamp()
    meta["currentTradingPeriod"]={"regular":{"start":start,"end":end}} if local.weekday()<5 else {}
    meta["sessionBasis"]="REGULAR_HOURS_ESTIMATE"
    # A provider price without a source timestamp is a display-only snapshot.
    quote=number(meta.get("providerQuotePrice"))
    stamp=number(meta.get("exchangeQuoteTime"))
    qsource=meta.get("quoteSource")
    candle_source=meta.get("candleSource")
    if meta.get("quoteStale") or not qsource or not stamp or not 0<stamp<=now or quote is None or quote<=0:
        stamp=None
    meta["regularMarketTime"]=stamp
    meta["regularMarketPrice"]=quote if quote and quote>0 else None
    meta["priceKind"]="SOURCE_QUOTE" if stamp else "UNVERIFIED_QUOTE_SNAPSHOT"
    meta["source"]=qsource or candle_source or "market-data"
    if not meta["regularMarketPrice"]:
        # Show a genuine *closed* bar price, never treat it as a current quote.
        ts=raw.get("timestamp") or []
        indicators=raw.get("indicators") or {}
        q=(indicators.get("quote") or [{}])[0]
        closes=q.get("close") or [] if isinstance(q,dict) else []
        for t,c in reversed(list(zip(ts,closes))):
            t,c=number(t),number(c)
            if t is not None and c is not None and c>0 and t+300<=now:
                meta["regularMarketPrice"]=c
                meta["priceKind"]="LAST_CLOSED_BAR"
                meta["priceAsOf"]=t+300
                meta["source"]=candle_source or "market-data"
                break
    if meta.get("candleStale"):
        # Never derive an entry from a provider's stale candle cache.
        meta["regularMarketTime"]=None
    if stamp is not None and not start<=stamp<=now<end:
        # An old or out-of-session quote may be shown but does not establish an open session.
        meta["sessionEvidence"]=False
    else:
        meta["sessionEvidence"]=bool(stamp is not None and start<=stamp<=now<end and now-stamp<=300 and local.weekday()<5)
    return payload
