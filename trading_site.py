"""Isolated, read-only Trading Desk. Reuses the app's existing Yahoo chart source."""
from pathlib import Path
import json, re, threading, time, math
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from trading_research import analyze_chart, VERSION

ROOT=Path(__file__).resolve().parent/'trading'
router=APIRouter()
_cache={}
_failures={}
_lock=threading.Lock()
_slots=threading.BoundedSemaphore(1)
_provider_state={'retry_after':0,'checked_at':None,'code':'NOT_CHECKED','failures':0,'requests':0}
MIN_REQUEST_GAP=15
CACHE_TTL=60

def retry_delay(exc,now,default):
    value=(getattr(exc,'headers',None) or {}).get('Retry-After','')
    try:
        delay=float(value) if str(value).isdigit() else parsedate_to_datetime(value).timestamp()-now
        if math.isfinite(delay): return max(default,delay)
    except (ValueError,TypeError,OverflowError,AttributeError): pass
    return default

def provider_snapshot():
    with _lock:
        state=dict(_provider_state)
    state['scope']='Trading Desk / one server process'
    state['cooling_down']=time.time()<state['retry_after']
    return state
INDEX_MAP={'NIFTY':'^NSEI','BANKNIFTY':'^NSEBANK','SENSEX':'^BSESN','SPX':'^GSPC','NDX':'^NDX'}

def market_symbol(symbol,region):
    s=symbol.strip().upper()
    if region not in ('US','IN') or not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,19}',s):
        raise ValueError('Use a valid ticker and US or IN region.')
    if s in INDEX_MAP:
        if (s in ('NIFTY','BANKNIFTY','SENSEX')) != (region=='IN'):
            raise ValueError('Index does not match selected region.')
        return s,INDEX_MAP[s]
    if region=='US' and s.endswith(('.NS','.BO')):
        raise ValueError('Select India for .NS or .BO symbols.')
    return s,s if region=='US' or s.endswith(('.NS','.BO')) else s+'.NS'

@router.get('/api/trading-desk/status')
def status():
    return dict(version=VERSION,mode='research_and_local_paper',execution_enabled=False,source='Yahoo Finance chart',live_latency_guaranteed=False,provider=provider_snapshot())

def provider_failure(exc):
    if isinstance(exc,HTTPError):
        code='RATE_LIMITED' if exc.code==429 else ('ACCESS_DENIED' if exc.code in (401,403) else 'HTTP_ERROR')
        return dict(code=code,http_status=exc.code)
    if isinstance(exc,(TimeoutError,URLError)): return dict(code='CONNECTION_FAILURE')
    if isinstance(exc,(ValueError,KeyError,TypeError,IndexError)): return dict(code='INVALID_RESPONSE')
    return dict(code='PROVIDER_FAILURE')

def failed_report(clean,region,now,details):
    data=analyze_chart({},clean,region,now)
    data['provider_status']=details
    data['reason']='Market data unavailable ('+details['code']+'). No substitute prices or buy signal.'
    return data

@router.get('/api/trading-desk/research')
def research(symbol: str='SPY',region: str='US'):
    try: clean,provider_symbol=market_symbol(symbol,region)
    except ValueError as e: raise HTTPException(422,str(e))
    now=time.time();key=(clean,region)
    # A single provider request may run at once. Other callers receive cached
    # evidence or a bounded WAIT response, never start another upstream request.
    with _lock:
        hit=_cache.get(key)
    if hit and 0<=now-hit[0]<CACHE_TTL:
        try:
            data=analyze_chart(hit[1],clean,region,now);data['fetched_at']=hit[0]
            data['provider_status']=dict(code='RESPONSE_RECEIVED',cached=True,checked_at=hit[0])
            return JSONResponse(data,headers={'Cache-Control':'no-store'})
        except (ValueError,TypeError,KeyError,IndexError,AttributeError):
            with _lock: _cache.pop(key,None)
    if not _slots.acquire(blocking=False):
        return JSONResponse(failed_report(clean,region,now,dict(code='REQUEST_IN_PROGRESS',retry_after=now+15)),headers={'Cache-Control':'no-store'})
    try:
        # Recheck under the single-flight gate. Rate-limit cooldown spans symbols.
        with _lock:
            state=dict(_provider_state)
            failure=_failures.get(key)
        if now<state['retry_after']:
            return JSONResponse(failed_report(clean,region,now,state),headers={'Cache-Control':'no-store'})
        if failure and now<failure['retry_after']:
            return JSONResponse(failed_report(clean,region,now,failure),headers={'Cache-Control':'no-store'})
        with _lock: _provider_state['requests']+=1
        url='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(provider_symbol,safe='')+'?interval=5m&range=1d&includePrePost=false'
        req=Request(url,headers={'User-Agent':'CelesysResearch/1.0','Accept':'application/json'})
        with urlopen(req,timeout=10) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('Oversized source response')
        payload=json.loads(raw)
        fetched=time.time()
        # Validate before caching so malformed schemas cannot poison the cache path.
        data=analyze_chart(payload,clean,region,fetched);data['fetched_at']=fetched
        data['provider_status']=dict(code='RESPONSE_RECEIVED',cached=False,checked_at=fetched)
        with _lock:
            if len(_cache)>=100: _cache.pop(next(iter(_cache)))
            _cache[key]=(fetched,payload)
            _failures.pop(key,None)
            _provider_state.pop('http_status',None)
            _provider_state.update(retry_after=fetched+MIN_REQUEST_GAP,checked_at=fetched,code='LOCAL_PACING',failures=0)
    except Exception as exc:
        failed_at=time.time()
        info=provider_failure(exc)
        with _lock: previous=_provider_state['failures']
        rate_limited=info['code']=='RATE_LIMITED'
        delay=min(3600,300*2**min(previous,4)) if rate_limited else (900 if info['code']=='ACCESS_DENIED' else 60)
        delay=retry_delay(exc,failed_at,delay)
        details=dict(info,checked_at=failed_at,retry_after=failed_at+delay)
        with _lock:
            if len(_failures)>=100: _failures.pop(next(iter(_failures)))
            _failures[key]=details
            _provider_state.update(details,failures=previous+1 if rate_limited else 0)
        data=failed_report(clean,region,failed_at,details)
    finally: _slots.release()
    return JSONResponse(data,headers={'Cache-Control':'no-store'})

class DeskFiles(StaticFiles):
    async def get_response(self,path,scope):
        r=await super().get_response(path,scope)
        r.headers.update({'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff',
          'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
          'Referrer-Policy':'same-origin'})
        return r

def attach_trading_desk(app):
    if any(getattr(r,'path',None)=='/trading' for r in app.routes): return
    app.include_router(router)
    app.mount('/trading',DeskFiles(directory=str(ROOT),html=True),name='trading-desk')
