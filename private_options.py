"""Credentialed read-only Angel One/Dhan/Tradier adapters for verified accounts.
Explicit licensed-display switches required. No broker order methods exist here.
"""
import json,os,threading,time
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from fastapi import APIRouter,HTTPException
from secure_access import require_user
from trading_site import market_symbol
from trading_research import number
from option_chain import normalize,snapshot
router=APIRouter();_lock=threading.Lock();_cache={};_next={'IN':0,'US':0}

def india_provider():
    # Preserve an existing configured Dhan installation; otherwise prefer the
    # account-backed free-API route. No silent fallback between credential sets.
    default='dhan' if os.getenv('CELESYS_DHAN_ACCESS_TOKEN') else 'angelone'
    return os.getenv('CELESYS_INDIA_OPTIONS_PROVIDER',default).strip().lower()

def provider_name(region):
    if region=='US':return 'Tradier'
    return {'angelone':'Angel One SmartAPI','dhan':'Dhan'}.get(india_provider(),'Unsupported provider')

def ready(region):
    if region not in ('IN','US'):return False
    if region=='IN' and india_provider()=='angelone':
        from angel_options import configured
        return os.getenv('CELESYS_LICENSED_OPTIONS_IN')=='true' and configured()
    if region=='IN' and india_provider()!='dhan':return False
    keys=('CELESYS_DHAN_ACCESS_TOKEN','CELESYS_DHAN_CLIENT_ID','CELESYS_DHAN_INSTRUMENTS_JSON') if region=='IN' else ('CELESYS_OPTIONS_DATA_TOKEN',)
    return os.getenv('CELESYS_LICENSED_OPTIONS_'+region)=='true' and all(os.getenv(k) for k in keys)

def request_json(url,headers,payload=None):
    req=Request(url,headers=headers,data=json.dumps(payload).encode() if payload is not None else None)
    with urlopen(req,timeout=12) as r:raw=r.read(4_000_001)
    if len(raw)>4_000_000:raise ValueError('Oversized response')
    result=json.loads(raw)
    if not isinstance(result,dict):raise ValueError('Invalid response')
    return result

def dhan_rows(payload):
    data=payload.get('data') or {};oc=data.get('oc');rows=[]
    if payload.get('status')!='success' or not isinstance(oc,dict):raise ValueError('Invalid chain')
    def nonnegative(x):
        x=number(x);return x if x is not None and x>=0 else None
    for strike,raw in oc.items():
        k=number(strike)
        if not k or k<=0 or not isinstance(raw,dict):continue
        row={'strike':k}
        for kind,key in [('call','ce'),('put','pe')]:
            q=raw.get(key)
            if not isinstance(q,dict):row[kind]=None;continue
            b,a=nonnegative(q.get('top_bid_price')),nonnegative(q.get('top_ask_price'));oi,prev=nonnegative(q.get('oi')),nonnegative(q.get('previous_oi'))
            row[kind]=dict(contract=str(q['security_id']) if q.get('security_id') else None,bid=b,ask=a,last=nonnegative(q.get('last_price')),oi=oi,oi_change=oi-prev if oi is not None and prev is not None else None,volume=nonnegative(q.get('volume')),iv_pct=nonnegative(q.get('implied_volatility')),delta=number((q.get('greeks') or {}).get('delta')),bid_time=None,ask_time=None,greeks_time=None,spread_pct=200*(a-b)/(a+b) if b and a and a>=b else None)
        if row['call'] or row['put']:rows.append(row)
    if len({r['strike'] for r in rows})!=len(rows):raise ValueError('Duplicate strikes')
    return sorted(rows,key=lambda r:r['strike']),number(data.get('last_price'))

@router.get('/api/private-options/status')
def status():
    require_user();return {'IN':ready('IN'),'US':ready('US'),'execution_enabled':False,
        'providers':{region:provider_name(region) for region in ('IN','US')},
        'connection_verified':False}

@router.get('/api/private-options/chain')
def chain(symbol:str='SPY',region:str='US',expiry:str=''):
    require_user()
    try:symbol,_=market_symbol(symbol,region)
    except ValueError as e:raise HTTPException(422,str(e))
    base=dict(symbol=symbol,region=region,currency='INR' if region=='IN' else 'USD',source=provider_name(region),rows=[],expiries=[],expiry=None,status='UNAVAILABLE',freshness='UNVERIFIED_OR_STALE',execution_enabled=False)
    if expiry:
        try:
            if date.fromisoformat(expiry).isoformat()!=expiry:raise ValueError()
        except ValueError:raise HTTPException(422,'Expiry must be YYYY-MM-DD.')
    if not ready(region):return dict(base,message='Authorized provider credentials and licensed-display setup required.')
    if region=='IN' and india_provider()=='angelone':
        from angel_options import chain as angel_chain
        return angel_chain(symbol,expiry)
    if not _lock.acquire(False):return dict(base,message='Provider request in progress. Try shortly.')
    try:
        now=time.time();key=(region,symbol,expiry);hit=_cache.get(key)
        if hit and now-hit['fetched_at']<60:return snapshot(hit,now)
        if now<_next[region]:return dict(base,message='Provider cooldown active.',retry_after=_next[region])
        _next[region]=now+15
        if region=='IN':
            instrument=json.loads(os.environ['CELESYS_DHAN_INSTRUMENTS_JSON']).get(symbol)
            if not instrument:return dict(base,message='No verified provider instrument mapping for this symbol.')
            payload={'UnderlyingScrip':int(instrument['id']),'UnderlyingSeg':instrument['segment']}
            if payload['UnderlyingScrip']<=0 or payload['UnderlyingSeg'] not in ('IDX_I','NSE_EQ','BSE_EQ'):raise ValueError('Invalid mapping')
            headers={'access-token':os.environ['CELESYS_DHAN_ACCESS_TOKEN'],'client-id':os.environ['CELESYS_DHAN_CLIENT_ID'],'Content-Type':'application/json'}
            result=request_json('https://api.dhan.co/v2/optionchain/expirylist',headers,payload)
            dates=result.get('data') or []
        else:
            headers={'Authorization':'Bearer '+os.environ['CELESYS_OPTIONS_DATA_TOKEN'],'Accept':'application/json'}
            result=request_json('https://api.tradier.com/v1/markets/options/expirations?'+urlencode({'symbol':symbol}),headers)
            dates=(result.get('expirations') or {}).get('date') or []
        if isinstance(dates,str):dates=[dates]
        today=datetime.fromtimestamp(now,ZoneInfo('Asia/Kolkata' if region=='IN' else 'America/New_York')).date()
        dates=sorted({x for x in dates if isinstance(x,str) and len(x)==10 and date.fromisoformat(x)>=today})
        if not dates:return dict(base,message='No available provider expiries.')
        selected=expiry or dates[0]
        if selected not in dates:raise HTTPException(422,'Choose an available expiry.')
        if region=='IN':
            time.sleep(3.1) # Respect Dhan's documented option-chain pacing.
            data=request_json('https://api.dhan.co/v2/optionchain',headers,dict(payload,Expiry=selected));rows,spot=dhan_rows(data)
        else:
            data=request_json('https://api.tradier.com/v1/markets/options/chains?'+urlencode({'symbol':symbol,'expiration':selected,'greeks':'true'}),headers);rows,spot=normalize(data,'US',symbol,selected)
        if not rows:return dict(base,message='No valid matching contracts from provider.')
        data=dict(base,rows=rows,spot=spot,expiry=selected,expiries=dates,status='SNAPSHOT',fetched_at=time.time(),message='Credentialed provider snapshot. Verify quote timestamps; no orders are sent.')
        if len(_cache)>=100:_cache.pop(next(iter(_cache)))
        _cache[key]=data;return snapshot(data,time.time())
    except HTTPException:raise
    except Exception:
        _next[region]=time.time()+300
        return dict(base,message='Provider request failed or data could not be verified. Retry after cooldown.',retry_after=_next[region])
    finally:_lock.release()
