"""Isolated, read-only Trading Desk. Reuses the app's existing Yahoo chart source."""
from pathlib import Path
import json, re, threading, time
from urllib.request import Request, urlopen
from urllib.parse import quote
from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from trading_research import analyze_chart, VERSION

ROOT=Path(__file__).resolve().parent/'trading'
router=APIRouter()
_cache={}
_lock=threading.Lock()
_slots=threading.BoundedSemaphore(2)
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
    return dict(version=VERSION,mode='research_and_local_paper',execution_enabled=False,source='Yahoo Finance chart',live_latency_guaranteed=False)

@router.get('/api/trading-desk/research')
def research(symbol: str='SPY',region: str='US'):
    try: clean,provider_symbol=market_symbol(symbol,region)
    except ValueError as e: raise HTTPException(422,str(e))
    now=time.time();key=(clean,region)
    with _lock:
        hit=_cache.get(key)
    if hit and now-hit[0]<60:
        # Re-run freshness/session gates at request time; cache fetch time is NOT quote time.
        data=analyze_chart(hit[1],clean,region,now);data['fetched_at']=hit[0]
        return JSONResponse(data,headers={'Cache-Control':'no-store'})
    if not _slots.acquire(blocking=False):
        raise HTTPException(429,'Research capacity busy. Retry in a minute.',headers={'Retry-After':'60'})
    try:
        url='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(provider_symbol,safe='')+'?interval=5m&range=1d&includePrePost=false'
        req=Request(url,headers={'User-Agent':'CelesysResearch/1.0','Accept':'application/json'})
        with urlopen(req,timeout=10) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('Oversized source response')
        payload=json.loads(raw)
        fetched=time.time()
        with _lock:
            if len(_cache)>=100: _cache.pop(next(iter(_cache)))
            _cache[key]=(fetched,payload)
        data=analyze_chart(payload,clean,region,fetched);data['fetched_at']=fetched
    except Exception:
        data=analyze_chart({},clean,region,time.time())
        data['reason']='Market-data provider unavailable. No substitute prices or buy signal.'
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
