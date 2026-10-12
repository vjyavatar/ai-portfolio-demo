"""Read-only, opt-in public option-chain snapshots. Never used for order signals."""
import json
import os
import re
import threading
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from trading_research import number
from trading_site import retry_delay

router = APIRouter()
INDICES = {'NIFTY': 'NSE_INDEX|Nifty 50', 'BANKNIFTY': 'NSE_INDEX|Nifty Bank',
           'FINNIFTY': 'NSE_INDEX|Nifty Fin Service', 'SENSEX': 'BSE_INDEX|SENSEX'}
_cache = {}
_locks = {r: threading.Lock() for r in ('US', 'IN')}
_retry = {'US': 0, 'IN': 0}
_token_supplier = lambda: None


def configure_india_token(supplier):
    global _token_supplier
    _token_supplier = supplier


def nonnegative(v):
    n = number(v)
    return n if n is not None and n >= 0 else None


def side(raw, region):
    if not isinstance(raw, dict):
        return None
    market = raw.get('market_data') or {} if region == 'IN' else raw
    greeks = raw.get('option_greeks' if region == 'IN' else 'greeks') or {}
    bid = nonnegative(market.get('bid_price' if region == 'IN' else 'bid'))
    ask = nonnegative(market.get('ask_price' if region == 'IN' else 'ask'))
    oi = nonnegative(market.get('oi' if region == 'IN' else 'open_interest'))
    prev = nonnegative(market.get('prev_oi')) if region == 'IN' else None
    iv = nonnegative(greeks.get('iv' if region == 'IN' else 'mid_iv'))
    def stamp(k):
        t = number(market.get(k))
        return t / 1000 if region == 'US' and t and t > 0 else None
    return dict(contract=raw.get('instrument_key' if region == 'IN' else 'symbol'),
                bid=bid, ask=ask, last=nonnegative(market.get('ltp' if region == 'IN' else 'last')),
                oi=oi, oi_change=oi-prev if oi is not None and prev is not None else None,
                volume=nonnegative(market.get('volume')), iv_pct=iv if region == 'IN' or iv is None else iv*100,
                delta=number(greeks.get('delta')), bid_time=stamp('bid_date'), ask_time=stamp('ask_date'),
                greeks_time=greeks.get('updated_at') if region == 'US' else None,
                spread_pct=100*(ask-bid)/((ask+bid)/2) if bid and ask and ask >= bid else None)


def normalize(payload, region, symbol, expiry):
    rows = {}
    spot = None
    if region == 'IN':
        items = payload.get('data')
        if not isinstance(items, list):
            raise ValueError('Invalid chain')
        for q in items:
            if not isinstance(q, dict) or q.get('expiry') != expiry or q.get('underlying_key') != INDICES[symbol]:
                continue
            strike = number(q.get('strike_price'))
            if not strike or strike <= 0: continue
            if strike in rows: raise ValueError('Duplicate strike')
            value = number(q.get('underlying_spot_price'))
            if value and value > 0: spot = value
            rows[strike] = dict(strike=strike, call=side(q.get('call_options'), region), put=side(q.get('put_options'), region))
    else:
        items = (payload.get('options') or {}).get('option') or []
        if isinstance(items, dict): items = [items]
        if not isinstance(items, list): raise ValueError('Invalid chain')
        for q in items:
            if not isinstance(q, dict) or q.get('underlying') != symbol or q.get('expiration_date') != expiry:
                continue
            strike = number(q.get('strike'))
            kind = q.get('option_type')
            if not strike or strike <= 0 or kind not in ('call', 'put') or q.get('contract_size') != 100:
                continue
            expected = symbol + date.fromisoformat(expiry).strftime('%y%m%d') + kind[0].upper() + f'{round(strike*1000):08d}'
            if q.get('symbol') != expected or q.get('root_symbol') != symbol: continue
            row = rows.setdefault(strike, dict(strike=strike, call=None, put=None))
            if row[kind] is not None: raise ValueError('Duplicate contract')
            row[kind] = side(q, region)
    return sorted(rows.values(), key=lambda q: q['strike']), spot


def get_json(region, path, params, token):
    base = 'https://api.tradier.com/v1/markets/'
    req = Request(base + path + '?' + urlencode(params), headers={'Accept': 'application/json', 'Authorization': 'Bearer '+token})
    with urlopen(req, timeout=10) as response:
        raw = response.read(4_000_001)
    if len(raw) > 4_000_000: raise ValueError('Oversized response')
    result = json.loads(raw)
    if not isinstance(result, dict): raise ValueError('Invalid response')
    return result


def snapshot(data, now):
    # Never turn request or cache time into a quote timestamp.
    out = dict(data)
    times = [s.get(k) for row in out['rows'] for s in (row['call'], row['put']) if s for k in ('bid_time', 'ask_time')]
    out['freshness'] = 'RECENT_QUOTES' if times and all(t is not None and 0 <= now-t <= 300 for t in times) else 'UNVERIFIED_OR_STALE'
    out['age_seconds'] = max(0, int(now-out['fetched_at']))
    return out


@router.get('/api/option-chain')
def chain(region: str = 'IN', symbol: str = 'NIFTY', expiry: str = ''):
    region, symbol = region.upper(), symbol.strip().upper()
    if region not in ('IN', 'US') or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,9}', symbol):
        raise HTTPException(422, 'Select IN or US and a valid symbol.')
    if region == 'IN' and symbol not in INDICES:
        raise HTTPException(422, 'India currently supports NIFTY, BANKNIFTY, FINNIFTY and SENSEX.')
    if region == 'US' and symbol in INDICES:
        raise HTTPException(422, 'Select India for this index.')
    if expiry:
        try:
            if date.fromisoformat(expiry).isoformat() != expiry: raise ValueError()
        except ValueError: raise HTTPException(422, 'Expiry must be YYYY-MM-DD.')
    base = dict(region=region, symbol=symbol, source='NSE' if region == 'IN' else 'Tradier',
                currency='INR' if region == 'IN' else 'USD', rows=[], expiries=[], execution_enabled=False,
                message='', status='UNAVAILABLE', freshness='UNVERIFIED',
                limitations='Snapshot research only. OI and Greeks have separate update schedules. Quote recency does not verify market hours. No trade recommendation.')
    def response(data): return JSONResponse(data, headers={'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex'})
    if region == 'IN':
        return response(dict(base, message='Use Options in the main Celesys workspace for India exchange snapshots.'))
    # A brokerage token alone is not permission to redistribute its data publicly.
    if os.getenv('CELESYS_PUBLIC_OPTIONS_'+region) != 'true':
        return response(dict(base, message='This market feed is not enabled for public display. Explore the guide below while the operator connects an authorized feed.'))
    token = os.getenv('CELESYS_INDIA_OPTIONS_DATA_TOKEN') if region == 'IN' else os.getenv('CELESYS_OPTIONS_DATA_TOKEN')
    if region == 'IN' and not token: token = _token_supplier()
    if not token: return response(dict(base, message='The data connection is unavailable or needs renewal. No substitute prices are shown.'))
    now = time.time()
    key = (region, symbol, expiry)
    if not _locks[region].acquire(blocking=False): return response(dict(base, message='A provider request is already running. Try again shortly.'))
    try:
        cached = _cache.get(key)
        if cached and now-cached['fetched_at'] < 60:
            return response(snapshot(cached, now))
        if now < _retry[region]: return response(dict(base, message='Provider cooldown active. Please retry after the countdown.', retry_after=_retry[region]))
        _retry[region] = now + 15
        if region == 'IN':
            raw = get_json(region, 'option/contract', {'instrument_key': INDICES[symbol]}, token)
            expiries = {q.get('expiry') for q in raw.get('data', []) if isinstance(q, dict) and q.get('underlying_key') == INDICES[symbol]}
        else:
            dates = (get_json(region, 'options/expirations', {'symbol':symbol}, token).get('expirations') or {}).get('date') or []
            expiries = {dates} if isinstance(dates, str) else set(dates)
        today = datetime.fromtimestamp(now, ZoneInfo('Asia/Kolkata' if region == 'IN' else 'America/New_York')).date().isoformat()
        expiries = sorted(e for e in expiries if isinstance(e, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', e) and e >= today)
        if not expiries: return response(dict(base, message='No available expirations were returned.'))
        chosen = expiry or expiries[0]
        if chosen not in expiries: return response(dict(base, expiries=expiries, message='That expiry is unavailable. Select an available expiry.'))
        params = {'instrument_key':INDICES[symbol], 'expiry_date':chosen} if region == 'IN' else {'symbol':symbol, 'expiration':chosen, 'greeks':'true'}
        raw = get_json(region, 'option/chain' if region == 'IN' else 'options/chains', params, token)
        rows, spot = normalize(raw, region, symbol, chosen)
        if not rows: return response(dict(base, expiries=expiries, message='The provider returned no valid matching contracts.'))
        data = dict(base, rows=rows, spot=spot, expiry=chosen, expiries=expiries, status='SNAPSHOT', fetched_at=time.time(),
                    message='Provider snapshot. Check quote timestamps and liquidity before interpreting the chain.')
        if len(_cache) >= 64: _cache.pop(next(iter(_cache)))
        _cache[key] = data
        return response(snapshot(data, time.time()))
    except HTTPError as exc:
        _retry[region] = time.time()+retry_delay(exc,time.time(),300 if exc.code == 429 else 60)
        return response(dict(base, message='Provider access or rate limit prevented this request. The operator may need to renew the connection.', retry_after=_retry[region]))
    except Exception:
        _retry[region] = time.time()+60
        return response(dict(base, message='Provider data could not be verified. Retry later; no prices were substituted.'))
    finally:
        _locks[region].release()
