"""SmartAPI NFO snapshots and NSE LTP/OHLC quotes. Login and HTTP go through angel_session.
Sources: smartapi.angelone.in/docs (market quote modes LTP, OHLC, FULL), official
angel-one/smartapi-python SDK headers; official instrument master (NFO strikes in paise,
NSE equity symbols ending in -EQ, index symbols such as "Nifty 50").

chain() and nse_quotes() are read-only. They run when configured() is true.
CELESYS_LICENSED_OPTIONS_IN is not read here. The private desk still requires that
flag plus a verified session. The public live board does not.
"""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
import hashlib
import ipaddress
import json
import logging
import math
import os
import re
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler
from zoneinfo import ZoneInfo
import angel_session

MASTER_URL='https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
QUOTE_URL='https://apiconnect.angelone.in/rest/secure/angelbroking/market/v1/quote/'
IST=ZoneInfo('Asia/Kolkata')
INDEX_NAMES={'NIFTY':'Nifty 50','BANKNIFTY':'Nifty Bank'}
# Exact master symbols. "Nifty 50" must not match "Nifty 500" or the leveraged twins.
INDEX_QUOTES={'NIFTY':'Nifty 50','BANKNIFTY':'Nifty Bank','INDIAVIX':'India VIX'}
_QUOTE_ALIASES={'NIFTY50':'NIFTY','^NSEI':'NIFTY','NIFTYBANK':'BANKNIFTY','^NSEBANK':'BANKNIFTY','^INDIAVIX':'INDIAVIX'}
ENV=('CELESYS_ANGEL_API_KEY','CELESYS_ANGEL_JWT_TOKEN','CELESYS_ANGEL_CLIENT_LOCAL_IP',
     'CELESYS_ANGEL_CLIENT_PUBLIC_IP','CELESYS_ANGEL_MAC_ADDRESS')
_lock=threading.Lock();_master=None;_master_at=0.;_cache={};_retry_at=0.;_quote_next=0.
_nse_book=None;_nse_book_at=0.;_ltp_cache={}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Provider redirect rejected')

def configured():
    public=angel_session.public_ip()
    jwt=os.getenv(ENV[1],'').strip()
    use_login=angel_session.login_configured()
    if not use_login and (not jwt or '\r' in jwt or '\n' in jwt):return False
    values=[os.getenv(ENV[0],'').strip(), 'ready', os.getenv(ENV[2],'').strip(), public, os.getenv(ENV[4],'').strip()]
    if not all(values) or any('\r' in v or '\n' in v for v in values):return False
    try:
        ipaddress.ip_address(values[2]);ipaddress.ip_address(values[3])
        return bool(re.fullmatch(r'[0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5}',values[4]))
    except ValueError:return False

def _headers():
    token=angel_session.jwt_token()
    if not token:raise ValueError('Angel session unavailable')
    return {'Authorization':'Bearer '+token,'X-PrivateKey':os.environ[ENV[0]].strip(),
        'X-ClientLocalIP':os.environ[ENV[2]].strip(),'X-ClientPublicIP':angel_session.public_ip(),
        'X-MACAddress':os.environ[ENV[4]].strip(),'X-UserType':'USER','X-SourceID':'WEB',
        'Content-Type':'application/json','Accept':'application/json'}

_INDEX_MASTER_SCRIPT = r"""
import json, sys
names = {"NIFTY", "BANKNIFTY"}
master = json.load(sys.stdin)
if not isinstance(master, list) or len(master) > 400000:
    raise SystemExit(2)
kept = []
for row in master:
    if not isinstance(row, dict) or row.get("name") not in names:
        continue
    seg, kind = row.get("exch_seg"), row.get("instrumenttype")
    if (seg == "NFO" and kind == "OPTIDX") or (seg == "NSE" and kind == "AMXIDX"):
        kept.append(row)
json.dump(kept, sys.stdout)
"""


def _index_master_from_bytes(raw):
    """Filter the scrip master in another process. json.loads of the full file holds this process."""
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        raise ValueError('Invalid instrument master')
    try:
        proc = subprocess.run([sys.executable, '-c', _INDEX_MASTER_SCRIPT], input=bytes(raw), capture_output=True, timeout=12, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Instrument master parse timed out') from exc
    if proc.returncode != 0 or not proc.stdout:
        raise ValueError('Invalid instrument master')
    master = json.loads(proc.stdout.decode('utf-8'))
    if not isinstance(master, list):
        raise ValueError('Invalid instrument master')
    return master


def _request(url,payload=None,_auth_retry=True):
    if url not in (MASTER_URL,QUOTE_URL):raise ValueError('Unsupported provider resource')
    headers={'Accept':'application/json'} if url==MASTER_URL else _headers()
    try:
        if url==MASTER_URL and payload is None:
            raw = angel_session.request_bytes(url, headers=headers, timeout=12)
            return _index_master_from_bytes(raw)
        return angel_session.request_json(url,payload=payload,headers=headers)
    except angel_session.Unauthorized:
        if url==QUOTE_URL and _auth_retry and angel_session.login_configured():
            angel_session.jwt_token(force=True)
            return _request(url,payload,False)
        raise HTTPError(url,401,'provider',{},None)

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

def _quotes(exchange,tokens,mode='FULL'):
    global _quote_next
    if mode not in ('LTP','OHLC','FULL'):raise ValueError('Invalid quote mode')
    if exchange not in ('NSE','NFO') or not 1<=len(tokens)<=50 or len(set(tokens))!=len(tokens):raise ValueError('Invalid token batch')
    wait=_quote_next-time.monotonic()
    if wait>1.2:raise ValueError('Quote pacing busy')
    if wait>0:time.sleep(wait)
    _quote_next=time.monotonic()+1.1
    payload=_request(QUOTE_URL,{'mode':mode,'exchangeTokens':{exchange:tokens}})
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
    # The web process only waits. The one decision worker does the parse and quotes.
    if os.environ.get('CELESYS_DECISION_WORKER')!='1':
        import sys
        api=sys.modules.get('api')
        ready=getattr(api,'decision_worker_ready',None) if api is not None else None
        if callable(ready) and ready():
            return api.run_chain_in_worker(symbol,expiry)
    base=dict(symbol=symbol,region='IN',currency='INR',source='Angel One SmartAPI',rows=[],expiry=None,
        expiries=[],status='UNAVAILABLE',freshness='UNVERIFIED_OR_STALE',execution_enabled=False,
        message='Account-backed read-only feed requires authorized server configuration.')
    if symbol not in INDEX_NAMES:return dict(base,message='SmartAPI coverage currently supports NIFTY and BANKNIFTY only.')
    import web_background
    if web_background.budget_hit():return dict(base,message='Decision budget elapsed before the index chain.')
    if expiry and (not isinstance(expiry,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',expiry)):
        return dict(base,message='Choose an available ISO expiry.')
    if not configured():return base
    if not _lock.acquire(False):return dict(base,message='Provider request already in progress. Retry shortly.')
    try:
        now=time.time();today=datetime.fromtimestamp(now,IST).date()
        token=angel_session.jwt_token()
        auth_scope=hashlib.sha256((os.environ[ENV[0]].strip()+'\0'+token).encode()).hexdigest()
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
            _master=master;_master_at=now
            index,options=instruments(master,symbol,today)
        else:index,options=instruments(_master,symbol,today)
        if web_background.budget_hit():return dict(base,message='Decision budget elapsed before option quotes.')
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


def _nse_key(raw):
    text=str(raw or '').strip().upper().replace(' ','')
    if text.startswith('NSE:'):text=text[4:]
    if text.endswith('.NS'):text=text[:-3]
    if text.startswith('BSE:') or text.endswith('.BO'):return None
    text=_QUOTE_ALIASES.get(text,text)
    if not re.fullmatch(r'[A-Z][A-Z0-9]{0,19}',text):return None
    return text


_BOOK_SCRIPT = r"""
import json, re, sys
INDEX = {"NIFTY": "Nifty 50", "BANKNIFTY": "Nifty Bank", "INDIAVIX": "India VIX"}
master = json.load(sys.stdin)
if not isinstance(master, list) or len(master) > 400000:
    raise SystemExit(2)
book = {}
for raw in master:
    if not isinstance(raw, dict) or raw.get("exch_seg") != "NSE":
        continue
    token = str(raw.get("token", ""))
    if not re.fullmatch(r"[1-9][0-9]{0,11}", token):
        continue
    symbol = str(raw.get("symbol") or "")
    kind = raw.get("instrumenttype") or ""
    if kind == "AMXIDX":
        for key, trading in INDEX.items():
            if symbol == trading and key not in book:
                book[key] = {"token": token, "symbol": symbol}
        continue
    if kind not in ("", "EQ") or not symbol.endswith("-EQ"):
        continue
    key = symbol[:-3].upper()
    if key in INDEX or key in book or not re.fullmatch(r"[A-Z][A-Z0-9]{0,19}", key):
        continue
    listed = str(raw.get("name") or "").upper()
    if listed and listed != key:
        continue
    book[key] = {"token": token, "symbol": symbol}
if "NIFTY" not in book or "BANKNIFTY" not in book:
    raise SystemExit(3)
json.dump(book, sys.stdout)
"""


def _book_from_master_bytes(raw):
    """Build the NSE token book in another process.

    json.loads of the full instrument master holds this process's GIL for a long
    stretch. The decision request cannot answer while that lock is held.
    """
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        raise ValueError("Invalid instrument master")
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _BOOK_SCRIPT],
            input=bytes(raw),
            capture_output=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Instrument master parse timed out") from exc
    if proc.returncode != 0 or not proc.stdout:
        raise ValueError("Invalid instrument master")
    try:
        book = json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid instrument master") from exc
    if not isinstance(book, dict) or "NIFTY" not in book or "BANKNIFTY" not in book:
        raise ValueError("NSE index tokens unavailable")
    return book


def _load_nse_book(now):
    """NSE -EQ names and the three index symbols. The full master is not retained."""
    global _nse_book,_nse_book_at
    if _nse_book is not None and 0<=now-_nse_book_at<21600:return _nse_book
    raw = angel_session.request_bytes(MASTER_URL, headers={"Accept": "application/json"}, timeout=15)
    book = _book_from_master_bytes(raw)
    _nse_book=book;_nse_book_at=now
    return book


def _ltp_row(key,inst,quote,fetched):
    ltp=_num(quote.get('ltp'))
    if not ltp:return None
    # OHLC "close" is the previous close on the SmartAPI market quote.
    prev=_num(quote.get('close'))
    change=(ltp-prev) if prev else None
    change_pct=(change/prev*100) if prev and change is not None else None
    stamp=feed_time(quote.get('exchFeedTime'),fetched) if quote.get('exchFeedTime') else None
    return dict(symbol=key,price=ltp,prev_close=prev,change=change,change_pct=change_pct,
        open=_num(quote.get('open')),high=_num(quote.get('high')),low=_num(quote.get('low')),
        volume=_num(quote.get('tradeVolume')),as_of_epoch=stamp,provider='angel_one',source='angel_one',
        provider_mode='OHLC',quality='LIVE',delay_seconds=0,currency='INR',
        trading_symbol=inst['symbol'],fetched_at=fetched)


def nse_quotes(symbols):
    """LTP plus OHLC for NSE names. Empty when Angel is not configured or the call fails.

    Uses the market quote API (mode OHLC) through angel_session, so the static-IP
    proxy applies. Results are reused for 60 seconds. TradingView remains the caller's fallback.
    """
    if not configured():return {}
    keys=[]
    for raw in symbols or []:
        key=_nse_key(raw)
        if key and key not in keys:keys.append(key)
    if not keys:return {}
    if not _lock.acquire(False):return {}
    out={}
    try:
        now=time.time();missing=[]
        for key in keys:
            hit=_ltp_cache.get(key)
            if hit and 0<=now-hit['fetched_at']<60:out[key]=dict(hit)
            else:missing.append(key)
        if not missing:return out
        book=_load_nse_book(now)
        wanted=[key for key in missing if key in book]
        for offset in range(0,len(wanted),50):
            chunk=wanted[offset:offset+50]
            expected={book[key]['token']:book[key] for key in chunk}
            fetched=_quotes('NSE',[book[key]['token'] for key in chunk],mode='OHLC')
            by_token={}
            for quote in fetched:
                if not isinstance(quote,dict):continue
                token=str(quote.get('symbolToken',''))
                inst=expected.get(token)
                if not inst or quote.get('exchange')!='NSE' or token in by_token:continue
                if quote.get('tradingSymbol') and quote.get('tradingSymbol')!=inst['symbol']:continue
                by_token[token]=quote
            fetched_at=time.time()
            for key in chunk:
                quote=by_token.get(book[key]['token'])
                if not quote:continue
                row=_ltp_row(key,book[key],quote,fetched_at)
                if not row:continue
                if len(_ltp_cache)>=256:_ltp_cache.pop(next(iter(_ltp_cache)))
                _ltp_cache[key]=row
                out[key]=dict(row)
        return out
    except Exception as error:
        detail=angel_session._failure_text(error)
        logging.getLogger('angel_options').warning('Angel NSE quote failed: %s',detail)
        return out
    finally:_lock.release()


def _legacy_num(value):
    # The older options engine stores a missing quote as 0. Keep that contract here only.
    if isinstance(value,bool) or not isinstance(value,(int,float)):return 0
    return value if value>=0 else 0


def index_snapshot(symbol):
    """NIFTY/BANKNIFTY chain in the shape nse_options() returns. None if Angel cannot supply it."""
    sym=str(symbol or '').upper().strip()
    if sym not in INDEX_NAMES or not configured():return None
    snap=chain(sym)
    if not isinstance(snap,dict) or snap.get('status')!='SNAPSHOT' or not snap.get('rows'):return None
    spot=_num(snap.get('spot'))
    if not spot:return None
    chain_rows=[]
    for raw in snap.get('rows') or []:
        if not isinstance(raw,dict):continue
        call=raw.get('call') if isinstance(raw.get('call'),dict) else {}
        put=raw.get('put') if isinstance(raw.get('put'),dict) else {}
        strike=_num(raw.get('strike'))
        if not strike:continue
        chain_rows.append(dict(
            strike=strike,
            ce_oi=_legacy_num(call.get('oi')),pe_oi=_legacy_num(put.get('oi')),
            ce_iv=_legacy_num(call.get('iv_pct')),pe_iv=_legacy_num(put.get('iv_pct')),
            ce_ltp=_legacy_num(call.get('last')),pe_ltp=_legacy_num(put.get('last')),
            ce_bid=_legacy_num(call.get('bid')),pe_bid=_legacy_num(put.get('bid')),
            ce_ask=_legacy_num(call.get('ask')),pe_ask=_legacy_num(put.get('ask')),
            ce_volume=_legacy_num(call.get('volume')),pe_volume=_legacy_num(put.get('volume')),
            ce_chg=0,pe_chg=0,
        ))
    if not chain_rows:return None
    total_ce=sum(row['ce_oi'] for row in chain_rows)
    total_pe=sum(row['pe_oi'] for row in chain_rows)
    pcr=(total_pe/total_ce) if total_ce else None
    call_wall=max(chain_rows,key=lambda row:row['ce_oi'])
    put_wall=max(chain_rows,key=lambda row:row['pe_oi'])
    pain_strike=None;pain_value=None
    for settle in chain_rows:
        pain=0
        for row in chain_rows:
            pain+=max(settle['strike']-row['strike'],0)*row['ce_oi']
            pain+=max(row['strike']-settle['strike'],0)*row['pe_oi']
        if pain_value is None or pain<pain_value:
            pain_value=pain;pain_strike=settle['strike']
    atm=min(chain_rows,key=lambda row:abs(row['strike']-spot))
    atm_iv=(atm['ce_iv']+atm['pe_iv'])/2 if atm['ce_iv'] or atm['pe_iv'] else 0
    lot=0
    for raw in snap.get('rows') or []:
        leg=(raw.get('call') or raw.get('put') or {}) if isinstance(raw,dict) else {}
        if isinstance(leg,dict) and leg.get('lot_size'):
            lot=int(leg['lot_size']);break
    return dict(
        success=True,symbol=sym,spot=spot,lot_size=lot,expiry=snap.get('expiry'),
        expiry_dates=[snap.get('expiry')] if snap.get('expiry') else [],
        pcr=round(pcr,2) if pcr is not None else None,max_pain=pain_strike,
        atm_strike=atm['strike'],atm_iv=round(atm_iv,1),
        total_ce_oi=total_ce,total_pe_oi=total_pe,
        ce_resistance=[{'strike':row['strike'],'oi':row['ce_oi'],'chg':0} for row in sorted(chain_rows,key=lambda row:row['ce_oi'],reverse=True)[:5]],
        pe_support=[{'strike':row['strike'],'oi':row['pe_oi'],'chg':0} for row in sorted(chain_rows,key=lambda row:row['pe_oi'],reverse=True)[:5]],
        chain_near_atm=chain_rows,
        gex={'total':0,'regime':'POSITIVE' if (pcr or 0)>1 else 'NEGATIVE','implication':'','topStrikes':[],
             'flipPoint':0,'callWall':call_wall['strike'],'putWall':put_wall['strike']},
        ohlc_bars=[],source='angel_one',_chain_source='angel_one',
        message=snap.get('message'),
    )
