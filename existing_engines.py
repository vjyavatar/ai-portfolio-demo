"""Presentation adapters for Celesys's established, read-only engines."""
import asyncio
import json
import time
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from trading_site import market_symbol
from trading_research import number

router = APIRouter()
_trading = None
_options = None


def configure(trading=None, options=None):
    global _trading, _options
    _trading, _options = trading, options


async def fetch(supplier, symbol, region):
    if supplier is None:
        return {}
    try:
        result = await asyncio.wait_for(supplier(symbol=symbol, region=region), 55)
        if hasattr(result, 'body'):
            result = json.loads(result.body)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}  # Provider errors can contain credentials; never expose them.


def option_snapshot(data, symbol, region):
    source = 'NSE via existing Celesys options engine' if region == 'IN' else 'Yahoo Finance via existing Celesys options engine'
    expiry = data.get('expiry')
    rows = []
    valid_expiry = False
    for fmt in ('%Y-%m-%d', '%d-%b-%Y'):
        try:
            valid_expiry = datetime.strptime(str(expiry), fmt).date() >= datetime.now(timezone.utc).date()
            break
        except ValueError:
            pass
    # Existing feeds use zero both for missing and actual zero. Do not guess.
    def positive(value):
        n = number(value)
        return n if n is not None and n > 0 else None
    if data.get('success') and not data.get('_chain_unavailable') and valid_expiry:
        for raw in data.get('chain_near_atm') or []:
            strike = positive(raw.get('strike'))
            if strike is None:
                continue
            row = dict(strike=strike)
            for kind, prefix in (('call', 'ce'), ('put', 'pe')):
                values = {field: positive(raw.get(prefix+'_'+key)) for field, key in
                          (('bid','bid'),('ask','ask'),('last','ltp'),('oi','oi'),('iv_pct','iv'),('volume','volume'))}
                # Do not republish modelled Greeks or placeholder OI changes as feed facts.
                values.update(oi_change=None, delta=None, bid_time=None, ask_time=None,
                              greeks_time=None, spread_pct=None, contract=None)
                if values['bid'] and values['ask'] and values['ask'] >= values['bid']:
                    values['spread_pct'] = 200*(values['ask']-values['bid'])/(values['ask']+values['bid'])
                row[kind] = values if any(values[k] is not None for k in ('bid','ask','last','oi')) else None
            if row['call'] or row['put']:
                rows.append(row)
    return dict(status='SNAPSHOT' if rows else 'UNAVAILABLE', symbol=symbol, region=region,
                engine='options-quick', source=source, rows=rows, expiry=expiry if rows else None,
                expiries=[expiry] if rows else [], spot=positive(data.get('spot')),
                currency='INR' if region == 'IN' else 'USD', fetched_at=time.time(),
                freshness='UNVERIFIED_OR_STALE',
                message=('Existing Celesys option-chain snapshot. Quote times are not supplied; freshness is unverified. Zero/missing fields are shown as dashes.' if rows else
                         'The existing Celesys feed returned no usable option contracts. No substitute premiums are shown. Try again when the provider is available.'))


@router.get('/api/existing-option-chain')
async def existing_chain(symbol: str='SPY', region: str='US', expiry: str=''):
    region = region.upper()
    try:
        symbol, _ = market_symbol(symbol, region)
    except ValueError as error:
        raise HTTPException(422, str(error))
    from secure_access import identity
    from private_options import ready, chain
    user = identity.get()
    if user and user.get('full') and ready(region):
        from starlette.concurrency import run_in_threadpool
        return JSONResponse(await run_in_threadpool(chain, symbol, region, expiry), headers={'Cache-Control':'no-store'})
    data = option_snapshot(await fetch(_options, symbol, region), symbol, region)
    # The legacy engine only supplies the nearest expiry. Never mislabel another one.
    if expiry and data['expiry'] and expiry != data['expiry']:
        raise HTTPException(422, 'Reload the nearest available expiry.')
    return JSONResponse(data, headers={'Cache-Control':'no-store', 'X-Robots-Tag':'noindex'})
