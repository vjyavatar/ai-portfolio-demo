"""Read-only US option candidates. Dedicated opt-in data credential; no orders."""
import json, os, re, threading, time
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from trading_research import number

_lock = threading.Lock()
_cache = {}
_retry_at = 0

def blocked(reason, direction=None):
    return dict(status='WAIT', direction=direction, reason=reason, candidate=None,
                execution_enabled=False, source='Tradier market data',
                limitations=['Rule-based candidate, not validated profitability.',
                  'Event risk is not automatically verified. Check the broker before acting.',
                  'Greeks/IV are provider estimates updated hourly, not live tick values.'])

def fresh_timestamp(value, now):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= now-value <= 300

def assess(report, quotes, now):
    """quotes must originate in the server adapter, never a client-supplied report."""
    direction = {'LONG_RESEARCH':'CALL', 'BEARISH_RESEARCH':'PUT'}.get(report.get('verdict'))
    out = blocked('Underlying setup not qualified.', direction)
    if report.get('region') != 'US' or report.get('symbol') not in ('SPY','QQQ'):
        out['reason']='Options candidates currently support SPY and QQQ only.'; return out
    if not direction or report.get('market_status') != 'OPEN': return out
    if not all(fresh_timestamp(report.get(k), now) for k in ('quote_time','bar_close_time')):
        out['reason']='Underlying quote or closed bar is stale.'; return out
    if not number(report.get('session_end')) or now >= report['session_end']: return out
    scenario=report.get('scenario') or {}
    if not all(number(scenario.get(k)) and scenario[k]>0 for k in ('entry','stop','target')): return out
    today=datetime.fromtimestamp(now,ZoneInfo('America/New_York')).date()
    accepted=[]
    for q in quotes if isinstance(quotes,list) else []:
        if not isinstance(q,dict): continue
        try:
            expiry=date.fromisoformat(q['expiration_date'])
            strike=number(q.get('strike'))
            if not strike or strike<=0: continue
            # Reject adjusted/non-standard contracts and mismatched identity.
            occ=report['symbol']+expiry.strftime('%y%m%d')+direction[0]+f'{round(strike*1000):08d}'
            if (q.get('symbol')!=occ or q.get('root_symbol')!=report['symbol'] or
                q.get('underlying')!=report['symbol'] or q.get('type')!='option' or
                q.get('option_type')!=direction.lower() or q.get('contract_size')!=100 or
                not 1 <= (expiry-today).days <= 14): continue
            bid,ask=number(q.get('bid')),number(q.get('ask'))
            bt,at=number(q.get('bid_date')),number(q.get('ask_date'))
            if not bt or not at or not all(fresh_timestamp(t/1000,now) for t in (bt,at)): continue
            if not bid or not ask or not 0<bid<=ask: continue
            spread=(ask-bid)/((ask+bid)/2)
            if spread>0.10 or ask-bid>0.50: continue
            if any(number(q.get(k)) is None or number(q[k])<v for k,v in [('volume',100),('open_interest',500),('bidsize',1),('asksize',1)]): continue
            g=q.get('greeks') or {}
            delta,iv=number(g.get('delta')),number(g.get('mid_iv'))
            # Provider documents hourly estimates. Retain raw timestamp; don't infer its timezone.
            if delta is None or iv is None or not 0<iv<=5 or not isinstance(g.get('updated_at'),str) or not g['updated_at'].startswith(today.isoformat()): continue
            if not (0.4<=delta<=0.65 if direction=='CALL' else -0.65<=delta<=-0.4): continue
            accepted.append(dict(contract=occ,expiry=expiry.isoformat(),strike=strike,bid=bid,ask=ask,
                bid_time=bt/1000,ask_time=at/1000,spread_pct=spread*100,volume=q['volume'],
                open_interest=q['open_interest'],delta=delta,iv=iv,greeks_updated_at=g['updated_at'],
                maximum_premium=ask,premium_at_risk=ask*100,expires_at=min(bt/1000+300,at/1000+300,
                    report['quote_time']+300,report['bar_close_time']+300,report['session_end']),
                underlying_invalidation=scenario['stop'],underlying_target=scenario['target']))
        except (KeyError,ValueError,TypeError,OverflowError): continue
    if not accepted:
        out['reason']='No contract passes identity, expiry, fresh bid/ask, spread, volume and Greek checks.';return out
    c=min(accepted,key=lambda c:(c['spread_pct'],abs(abs(c['delta'])-0.55),c['expiry'],c['contract']))
    out.update(status='BUY_'+direction+'_CANDIDATE',candidate=c,
        reason='Conditional review candidate. Reconfirm the setup and event risk; use no more than the displayed premium. Skip if quotes change or widen.')
    return out

def _get(path,params,token):
    req=Request('https://api.tradier.com/v1/markets/'+path+'?'+urlencode(params),
                headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
    with urlopen(req,timeout=8) as response: raw=response.read(2_000_001)
    if len(raw)>2_000_000: raise ValueError('Oversized options response')
    return json.loads(raw)

def option_research(report):
    global _retry_at
    direction={'LONG_RESEARCH':'CALL','BEARISH_RESEARCH':'PUT'}.get(report.get('verdict'))
    # Dedicated env name prevents accidental reuse of any existing broker secret.
    token=os.environ.get('CELESYS_OPTIONS_DATA_TOKEN','')
    if os.environ.get('CELESYS_OPTIONS_DATA_ENABLED')!='true' or not token:
        return blocked('Options feed not connected. An authorized real-time options data token is required; no CALL/PUT buy signal.',direction)
    if report.get('region')!='US' or report.get('symbol') not in ('SPY','QQQ') or not direction:
        return blocked('Waiting for a qualifying SPY/QQQ underlying setup.',direction)
    now=time.time(); symbol=report['symbol']
    if not _lock.acquire(blocking=False): return blocked('Options request already in progress.',direction)
    try:
        cached=_cache.get(symbol)
        if cached and 0<=now-cached[0]<60: return assess(report,cached[1],now)
        if now<_retry_at: return blocked('Options provider cooldown active; no buy signal.',direction)
        _retry_at=now+60
        expirations=_get('options/expirations',{'symbol':symbol},token)['expirations']['date']
        if isinstance(expirations,str): expirations=[expirations]
        today=datetime.fromtimestamp(now,ZoneInfo('America/New_York')).date()
        dates=sorted(d for d in expirations if 1<=(date.fromisoformat(d)-today).days<=14)
        if not dates: return blocked('No supported non-0DTE expiration available.',direction)
        # Bounded coverage: nearest non-0DTE expiry only; not a comprehensive chain scan.
        chain=_get('options/chains',{'symbol':symbol,'expiration':dates[0],'greeks':'true'},token)['options']['option']
        if isinstance(chain,dict): chain=[chain]
        _cache[symbol]=(time.time(),chain)
        return assess(report,chain,time.time())
    except Exception as exc:
        from urllib.error import HTTPError
        from trading_site import retry_delay
        delay=retry_delay(exc,time.time(),300) if isinstance(exc,HTTPError) else 60
        _retry_at=time.time()+delay
        return blocked('Options provider unavailable or response invalid; no buy signal.',direction)
    finally: _lock.release()
