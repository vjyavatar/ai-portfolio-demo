"""Read-only research stages for the Celesys Trading Desk. No broker execution."""
from datetime import datetime, timezone
import math

VERSION = 'trading-desk-1.0'

def number(value):
    if isinstance(value, bool): return None
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError): return None

def ema(values, span):
    result = values[0]
    for v in values[1:]: result += (v-result)*2/(span+1)
    return result

def analyze_chart(payload, symbol, region, now):
    stages=[]
    def stage(name, status, detail):
        stages.append(dict(name=name,status=status,detail=detail))
    out=dict(version=VERSION,symbol=symbol,region=region,currency='USD' if region=='US' else 'INR',
        mode='RESEARCH_ONLY',generated_at=now,source='Yahoo Finance chart',source_latency='Not guaranteed real-time',
        verdict='WAIT',bias='UNAVAILABLE',reason='Insufficient verified data',paper_eligible=False,
        stages=stages,bars=[],metrics={},quote_time=None,bar_close_time=None,
        limitations=['Rule-based research stages; no LLM or calibrated win probability',
          'No option chain, Greeks, event-calendar or broker execution in this workspace',
          'Targets and stops are illustrative underlying-price levels, not option premiums'])
    result=(payload.get('chart') or {}).get('result') if isinstance(payload,dict) else None
    if not isinstance(result,list) or not result or not isinstance(result[0],dict):
        stage('Data steward','blocked','Provider returned no usable chart data.')
        return out
    raw=result[0];meta=raw.get('meta') or {}
    regular=((meta.get('currentTradingPeriod') or {}).get('regular') or {})
    start,end=number(regular.get('start')),number(regular.get('end'))
    session_known=bool(start and end and start<end and end-start<=86400)
    market_open=bool(session_known and start<=now<end)
    out['market_status']='OPEN' if market_open else 'CLOSED_OR_UNVERIFIED'
    out['session_start']=start;out['session_end']=end
    quote_time=number(meta.get('regularMarketTime'))
    price=number(meta.get('regularMarketPrice'))
    out['quote_time']=quote_time
    out['price']=price if price and price>0 else None
    quotes=((raw.get('indicators') or {}).get('quote') or [{}])[0]
    timestamps=raw.get('timestamp') or []
    if not isinstance(timestamps,list) or len(timestamps)>2000 or not isinstance(quotes,dict):
        stage('Data steward','blocked','Malformed or oversized chart data.');return out
    bars=[];invalid=False;previous=None
    for i,t in enumerate(timestamps):
        ts=number(t)
        if ts is None or (previous is not None and ts<=previous): invalid=True;break
        previous=ts
        # Provider timestamps are bar openings; exclude current forming bar.
        if not session_known or ts<start or ts>=end or ts+300>now: continue
        vals=[]
        for k in ('open','high','low','close','volume'):
            series=quotes.get(k)
            vals.append(number(series[i]) if isinstance(series,list) and i<len(series) else None)
        o,h,l,c,v=vals
        if any(x is None for x in vals) or min(o,h,l,c)<=0 or v<0 or not l<=min(o,c)<=max(o,c)<=h:
            invalid=True;break
        if bars and ts-bars[-1]['time']!=300: invalid=True;break
        bars.append(dict(time=ts,open=o,high=h,low=l,close=c,volume=v))
    if invalid:
        stage('Data steward','blocked','Invalid, duplicated or missing session bars. No signal issued.');return out
    out['bars']=bars
    out['bar_close_time']=bars[-1]['time']+300 if bars else None
    freshness=bool(quote_time and price and price>0 and 0<=now-quote_time<=300 and bars and 0<=now-out['bar_close_time']<=600)
    enough=len(bars)>=21
    full_session=bool(bars and bars[0]['time']==start)
    stage('Data steward','pass' if freshness and enough and full_session else 'blocked',
          f'{len(bars)} closed five-minute bars. '+('Recent source timestamps.' if freshness else 'Source timestamps missing or stale.')+('' if full_session else ' Session opening bars unavailable.'))
    stage('Session guard','pass' if market_open else 'blocked','Inside provider-reported regular session.' if market_open else 'Market closed or regular session could not be verified.')
    if not enough:
        out['reason']='Wait for at least 21 closed five-minute bars.'
        stage('Trend analyst','blocked',out['reason']);return out
    closes=[b['close'] for b in bars]
    e9,e20=ema(closes,9),ema(closes,20)
    total_volume=sum(b['volume'] for b in bars)
    vwap=sum((b['high']+b['low']+b['close'])/3*b['volume'] for b in bars)/total_volume if total_volume>0 else None
    avgvol=sum(b['volume'] for b in bars[-21:-1])/20
    relvol=bars[-1]['volume']/avgvol if avgvol>0 else None
    trs=[max(b['high']-b['low'],abs(b['high']-bars[i-1]['close']),abs(b['low']-bars[i-1]['close'])) for i,b in enumerate(bars) if i>0]
    atr=sum(trs[-14:])/14
    direction='BULLISH' if vwap and closes[-1]>vwap and e9>e20 else ('BEARISH' if vwap and closes[-1]<vwap and e9<e20 else 'MIXED')
    out['bias']=direction
    last=bars[-1];prior_high=max(b['high'] for b in bars[-4:-1]);prior_low=min(b['low'] for b in bars[-4:-1])
    breakout=(direction=='BULLISH' and last['close']>prior_high) or (direction=='BEARISH' and last['close']<prior_low)
    volume_ok=relvol is not None and relvol>=1.2
    stretch=abs(last['close']-vwap)/atr if vwap and atr>0 else None
    not_extended=stretch is not None and stretch<=3
    out['metrics']=dict(ema9=e9,ema20=e20,vwap=vwap,relative_volume=relvol,atr14=atr,extension_atr=stretch)
    stage('Trend analyst','pass' if direction!='MIXED' and vwap else 'watch',f'{direction.title()} alignment of EMA 9/20 and volume-weighted price.' if vwap else 'No usable volume; VWAP and direction are unavailable.')
    stage('Setup analyst','pass' if breakout and volume_ok else 'watch','Closed-bar breakout and volume confirmed.' if breakout and volume_ok else 'Needs a close beyond the prior three bars and relative volume ≥ 1.2×.')
    stage('Risk critic','pass' if not_extended else 'blocked','Within three ATR of VWAP.' if not_extended else 'Extended entry or missing volatility evidence; wait for a better location.')
    eligible=all((freshness,enough,full_session,market_open,breakout,volume_ok,not_extended,atr>0))
    if eligible:
        out['verdict']='LONG_RESEARCH' if direction=='BULLISH' else 'BEARISH_RESEARCH'
        out['reason']='Conditions align for review. Verify prices and event risk before acting.'
        out['paper_eligible']=direction=='BULLISH' and meta.get('instrumentType') in ('EQUITY','ETF')
        # Only an underlying stock/ETF scenario. Never infer option prices from spot.
        entry=price
        stop=entry-1.5*atr if direction=='BULLISH' else entry+1.5*atr
        target=entry+3*atr if direction=='BULLISH' else entry-3*atr
        if min(entry,stop,target)<=0:
            out['paper_eligible']=False;out['verdict']='WAIT';out['reason']='Invalid underlying risk levels.'
        else: out['scenario']=dict(entry=entry,stop=stop,target=target,kind='UNDERLYING_ONLY')
    else:
        out['reason']='No candidate: '+('; '.join(s['name'] for s in stages if s['status']!='pass'))+'.'
    stage('Independent review','watch','Event calendar and executable options quotes are not verified. No call/put contract recommendation.')
    stage('Research coordinator','pass' if eligible else 'blocked',out['reason'])
    return out
