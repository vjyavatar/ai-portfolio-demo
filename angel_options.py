"""Read-only SmartAPI NFO snapshots; no login, refresh, TOTP or order operations.
Sources: smartapi.angelone.in/docs (FULL market data), official angel-one/smartapi-python
SDK headers; official SmartAPI instrument-master interpretation (NFO strikes in paise).
Caller must enforce verified identity and licensed-display permission before chain().
"""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
import hashlib
import ipaddress
import json
import math
import os
import re
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, HTTPRedirectHandler, build_opener
from zoneinfo import ZoneInfo

MASTER_URL='https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
QUOTE_URL='https://apiconnect.angelone.in/rest/secure/angelbroking/market/v1/quote/'
IST=ZoneInfo('Asia/Kolkata')
INDEX_NAMES={'NIFTY':'Nifty 50','BANKNIFTY':'Nifty Bank'}
ENV=('CELESYS_ANGEL_API_KEY','CELESYS_ANGEL_JWT_TOKEN','CELESYS_ANGEL_CLIENT_LOCAL_IP',
     'CELESYS_ANGEL_CLIENT_PUBLIC_IP','CELESYS_ANGEL_MAC_ADDRESS')
_lock=threading.Lock();_master=None;_master_at=0.;_cache={};_retry_at=0.;_quote_next=0.

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Provider redirect rejected')

def configured():
    values=[os.getenv(key,'').strip() for key in ENV]
    if not all(values) or any('\r' in v or '\n' in v for v in values):return False
    try:
        ipaddress.ip_address(values[2]);ipaddress.ip_address(values[3])
        return bool(re.fullmatch(r'[0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5}',values[4]))
    except ValueError:return False

def _headers():
    return {'Authorization':'Bearer '+os.environ[ENV[1]].strip(),'X-PrivateKey':os.environ[ENV[0]].strip(),
        'X-ClientLocalIP':os.environ[ENV[2]].strip(),'X-ClientPublicIP':os.environ[ENV[3]].strip(),
        'X-MACAddress':os.environ[ENV[4]].strip(),'X-UserType':'USER','X-SourceID':'WEB',
        'Content-Type':'application/json','Accept':'application/json'}

def _request(url,payload=None):
    if url not in (MASTER_URL,QUOTE_URL):raise ValueError('Unsupported provider resource')
    cap=64_000_000 if url==MASTER_URL else 2_000_000
    headers={'Accept':'application/json'} if url==MASTER_URL else _headers()
    request=Request(url,headers=headers,data=json.dumps(payload).encode() if payload is not None else None)
    with build_opener(NoRedirect()).open(request,timeout=15) as response:raw=response.read(cap+1)
    if len(raw)>cap:raise ValueError('Oversized provider response')
    return json.loads(raw)

def _num(value):
    if isinstance(value,bool):return None
    try:
        d=Decimal(str(value))
        return float(d) if d.is_finite() and d>=0 and math.isfinite(float(d)) else None
    except (InvalidOperation,ValueError,TypeError):return None

def feed_time(value,now):
    # FULL reports exchange-local timestamps; NFO/NSE exchange time is IST.
    if not isinstance(value,str):return None
    try:
        stamp=datetime.strptime(value,'%d-%b-%Y %H:%M:%S').replace(tzinfo=IST).timestamp()
        return stamp if 0<=now-stamp<=7*86400 else None
    except (ValueError,OverflowError):return None

def instruments(master,symbol,today):
    if not isinstance(master,list) or len(master)>400000:raise ValueError('Invalid instrument master')
    options=[];indices=[];tokens=set();contracts=set()
    for raw in master:
        if not isinstance(raw,dict) or raw.get('name')!=symbol:continue
        token=str(raw.get('token',''))
        if not re.fullmatch(r'[1-9][0-9]{0,11}',token):continue
        if raw.get('exch_seg')=='NSE' and raw.get('instrumenttype')=='AMXIDX' and raw.get('symbol')==INDEX_NAMES[symbol]:
            indices.append(dict(token=token,symbol=raw['symbol']));continue
        if raw.get('exch_seg')!='NFO' or raw.get('instrumenttype')!='OPTIDX':continue
        try:
            expiry=datetime.strptime(raw['expiry'],'%d%b%Y').date()
            strike=Decimal(str(raw['strike']))/100
            lot=Decimal(str(raw['lotsize']))
            if not strike.is_finite() or not 0<strike<=10000000 or not lot.is_finite() or not 0<lot<=1000000 or lot!=int(lot):continue
            if expiry<today:continue
            suffix=raw['symbol'][-2:]
            if suffix not in ('CE','PE'):continue
            strike_text=format(strike,'f').rstrip('0').rstrip('.') if '.' in format(strike,'f') else format(strike,'f')
            expected=symbol+expiry.strftime('%d%b%y').upper()+strike_text+suffix
            if raw['symbol']!=expected:continue
            identity=(expiry.isoformat(),float(strike),suffix)
            if token in tokens or identity in contracts:raise RuntimeError('Ambiguous instrument identity')
            tokens.add(token);contracts.add(identity)
            options.append(dict(token=token,symbol=expected,expiry=expiry.isoformat(),strike=float(strike),
                side='call' if suffix=='CE' else 'put',lot_size=int(lot)))
        except (KeyError,ValueError,TypeError,InvalidOperation,OverflowError):continue
    if len(indices)!=1 or indices[0]['token'] in tokens:raise ValueError('Index instrument identity unavailable or ambiguous')
    return indices[0],options

def _quotes(exchange,tokens):
    global _quote_next
    if exchange not in ('NSE','NFO') or not 1<=len(tokens)<=50 or len(set(tokens))!=len(tokens):raise ValueError('Invalid token batch')
    wait=_quote_next-time.monotonic()
    if wait>1.2:raise ValueError('Quote pacing busy')
    if wait>0:time.sleep(wait)
    _quote_next=time.monotonic()+1.1
    payload=_request(QUOTE_URL,{'mode':'FULL','exchangeTokens':{exchange:tokens}})
    if not isinstance(payload,dict) or payload.get('status') is not True or not isinstance(payload.get('data'),dict):raise ValueError('Provider response unavailable')
    fetched=payload['data'].get('fetched')
    if not isinstance(fetched,list) or len(fetched)>len(tokens):raise ValueError('Invalid quote batch')
    return fetched

def _identify(quotes,expected,exchange):
    found={}
    for q in quotes:
        if not isinstance(q,dict):raise ValueError('Malformed quote')
        token=str(q.get('symbolToken',''));inst=expected.get(token)
        if not inst or q.get('exchange')!=exchange or q.get('tradingSymbol')!=inst['symbol'] or token in found:
            raise ValueError('Quote identity mismatch')
        found[token]=q
    return found

def _leg(q,inst,now):
    depth=q.get('depth') or {}
    def best(side):
        levels=depth.get(side) if isinstance(depth,dict) else None
        pairs=[]
        for level in levels if isinstance(levels,list) else []:
            if not isinstance(level,dict):continue
            p,qty=_num(level.get('price')),_num(level.get('quantity'))
            if p is not None and p>0 and qty is not None and qty>0:pairs.append((p,qty))
        return (max(pairs) if side=='buy' else min(pairs)) if pairs else (None,None)
    bid,bsize=best('buy');ask,asize=best('sell')
    if bid is not None and ask is not None and bid>ask:bid=ask=bsize=asize=None
    return dict(contract=inst['symbol'],token=inst['token'],lot_size=inst['lot_size'],bid=bid,ask=ask,
        bid_size=bsize,ask_size=asize,last=_num(q.get('ltp')),oi=_num(q.get('opnInterest')),
        volume=_num(q.get('tradeVolume')),oi_change=None,delta=None,iv_pct=None,
        bid_time=None,ask_time=None,greeks_time=None,feed_time=feed_time(q.get('exchFeedTime'),now),
        feed_time_kind='EXCHANGE_FEED_SNAPSHOT_IST_NOT_SIDE_SPECIFIC',
        spread_pct=200*(ask-bid)/(ask+bid) if bid and ask and ask>=bid else None)

def _snapshot(data,now):
    out=deepcopy(data);legs=[row[side] for row in out['rows'] for side in ('call','put') if row.get(side)]
    times=[leg.get('feed_time') for leg in legs]+[out.get('spot_feed_time')]
    recent=bool(legs) and all(isinstance(t,(int,float)) and 0<=now-t<300 for t in times)
    out['freshness']='RECENT_FEED_SNAPSHOT' if recent else 'UNVERIFIED_OR_STALE'
    out['cache_age_seconds']=max(0,now-out['fetched_at'])
    return out

def chain(symbol,expiry=''):
    global _master,_master_at,_retry_at
    base=dict(symbol=symbol,region='IN',currency='INR',source='Angel One SmartAPI',rows=[],expiry=None,
        expiries=[],status='UNAVAILABLE',freshness='UNVERIFIED_OR_STALE',execution_enabled=False,
        message='Account-backed read-only feed requires authorized server configuration.')
    if symbol not in INDEX_NAMES:return dict(base,message='SmartAPI coverage currently supports NIFTY and BANKNIFTY only.')
    if expiry and (not isinstance(expiry,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',expiry)):
        return dict(base,message='Choose an available ISO expiry.')
    if not configured():return base
    if not _lock.acquire(False):return dict(base,message='Provider request already in progress. Retry shortly.')
    try:
        now=time.time();today=datetime.fromtimestamp(now,IST).date()
        auth_scope=hashlib.sha256((os.environ[ENV[0]]+'\0'+os.environ[ENV[1]]).encode()).hexdigest()
        key=(symbol,expiry,auth_scope);hit=_cache.get(key)
        if hit and 0<=now-hit['fetched_at']<60:return _snapshot(hit,now)
        if now<_retry_at:return dict(base,message='Provider cooldown active.',retry_after=_retry_at)
        _retry_at=now+5
        if _master is None or not 0<=now-_master_at<21600:
            master=_request(MASTER_URL)
            if not isinstance(master,list) or len(master)>400000:raise ValueError('Invalid instrument master')
            # Retain only the supported indices/options; discard the much larger all-market dump.
            master=[row for row in master if isinstance(row,dict) and row.get('name') in INDEX_NAMES
                and ((row.get('exch_seg')=='NFO' and row.get('instrumenttype')=='OPTIDX')
                     or (row.get('exch_seg')=='NSE' and row.get('instrumenttype')=='AMXIDX'))]
            index,options=instruments(master,symbol,today)
            _master=master;_master_at=now
        else:index,options=instruments(_master,symbol,today)
        dates=sorted({item['expiry'] for item in options});selected=expiry or (dates[0] if dates else '')
        if not selected or selected not in dates:return dict(base,expiries=dates,message='No matching available expiry in the current instrument master.')
        indexq=_identify(_quotes('NSE',[index['token']]),{index['token']:index},'NSE').get(index['token'])
        spot=_num(indexq.get('ltp')) if indexq else None
        stamp=feed_time(indexq.get('exchFeedTime'),time.time()) if indexq else None
        if not spot or stamp is None:return dict(base,expiries=dates,message='Underlying index quote identity or timestamp unavailable; no arbitrary strike window selected.')
        candidates=[item for item in options if item['expiry']==selected]
        grouped={}
        for item in candidates:grouped.setdefault(item['strike'],{})[item['side']]=item
        paired=[strike for strike,pair in grouped.items() if set(pair)=={'call','put'} and pair['call']['lot_size']==pair['put']['lot_size']]
        strikes=sorted(sorted(paired,key=lambda strike:(abs(strike-spot),strike))[:25])
        contracts=[grouped[strike][side] for strike in strikes for side in ('call','put')]
        if not contracts:return dict(base,expiries=dates,message='No complete call/put pairs in the instrument master.')
        expected={item['token']:item for item in contracts};quotes=_identify(_quotes('NFO',list(expected)),expected,'NFO')
        rows=[];fetched=time.time()
        for strike in strikes:
            row={'strike':strike}
            for side in ('call','put'):
                inst=grouped[strike][side];q=quotes.get(inst['token'])
                row[side]=_leg(q,inst,fetched) if q else None
            if row['call'] or row['put']:rows.append(row)
        if not rows:return dict(base,expiries=dates,message='No matching option quotes returned by the provider.')
        data=dict(base,rows=rows,status='SNAPSHOT',expiry=selected,expiries=dates,spot=spot,
            spot_feed_time=stamp,fetched_at=fetched,
            coverage=dict(scope='BOUNDED_NEAR_SPOT_WINDOW_NOT_FULL_CHAIN',requested_contracts=len(contracts),
                returned_contracts=len(quotes),available_paired_strikes=len(paired),returned_strikes=len(rows),maximum_contracts=50),
            message=f'Account-backed bounded snapshot: {len(quotes)} of {len(contracts)} requested contracts across up to 25 near-spot strikes, not the full chain. Exchange feed time is not a separate bid/ask timestamp. Greeks and IV are unavailable; no orders or contract recommendations.')
        if len(_cache)>=32:_cache.pop(next(iter(_cache)))
        _cache[key]=data
        return _snapshot(data,fetched)
    except Exception as error:
        delay=300
        if isinstance(error,HTTPError):
            raw=(error.headers or {}).get('Retry-After','')
            try:
                extra=float(raw) if str(raw).isdigit() else parsedate_to_datetime(raw).timestamp()-time.time()
                if extra>delay:delay=min(extra,86400)
            except (ValueError,TypeError,OverflowError):pass
        _retry_at=time.time()+delay
        return dict(base,message='Provider request failed or response could not be verified. Check server configuration and retry after cooldown.',retry_after=_retry_at)
    finally:_lock.release()
