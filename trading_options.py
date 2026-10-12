"""Read-only US option candidates. Dedicated opt-in data credential; no orders."""
import json, os, re, threading, time
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
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
                confidence=dict(status='UNCALIBRATED',success_probability=None,
                    basis=['Deterministic data and liquidity filters; no independently validated win probability.']),
                coverage=dict(supported_symbols=['SPY','QQQ'],
                    expiry_policy='NEAREST_NON_0DTE_1_TO_14_CALENDAR_DAYS',
                    scope='RETURNED_PROVIDER_CHAIN_ONLY_NOT_MARKET_WIDE'),
                limitations=['Rule-based candidate, not validated profitability.',
                  'Event risk is not automatically verified. Check the broker before acting.',
                  'Greeks/IV are provider estimates updated hourly, not live tick values.'])

def fresh_timestamp(value, now):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= now-value <= 300

def greek_timestamp(value, now):
    """Require an explicit source timezone; never guess a naive timestamp's zone."""
    if not isinstance(value, str): return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None: return None
        stamp = parsed.timestamp()
        return stamp if 0 <= now-stamp <= 3600 else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None

def assess(report, quotes, now, expected_expiry=None):
    """quotes must originate in the server adapter, never a client-supplied report."""
    direction = {'LONG_RESEARCH':'CALL', 'BEARISH_RESEARCH':'PUT'}.get(report.get('verdict'))
    out = blocked('Underlying setup not qualified.', direction)
    if report.get('region') != 'US' or report.get('symbol') not in ('SPY','QQQ'):
        out['reason']='Options candidates currently support SPY and QQQ only.'; return out
    if not direction or report.get('market_status') != 'OPEN': return out
    stages=report.get('stages')
    if (report.get('stale_cache') or not isinstance(stages,list) or
            any(not isinstance(stage,dict) or stage.get('status')=='blocked' for stage in stages)):
        out['reason']='Underlying evidence is cached stale, blocked or incomplete.'; return out
    gates={stage.get('name'):stage.get('status') for stage in stages}
    if any(gates.get(name)!='pass' for name in (
            'Data steward','Session guard','Trend analyst','Setup analyst','Risk critic','Quote guard')):
        out['reason']='Underlying research guards are not all verified.'; return out
    if not all(fresh_timestamp(report.get(k), now) for k in ('quote_time','bar_close_time')):
        out['reason']='Underlying quote or closed bar is stale.'; return out
    start,end=number(report.get('session_start')),number(report.get('session_end'))
    if start is None or end is None or not start<=now<end or not 0<end-start<=86400:
        out['reason']='Underlying regular session times are not verified.'; return out
    if not start<=report['bar_close_time']<=report['quote_time']:
        out['reason']='Underlying quote predates the signal close or session.'; return out
    scenario=report.get('scenario') or {}
    if not isinstance(scenario,dict) or scenario.get('kind')!='UNDERLYING_ONLY':
        out['reason']='Underlying-only risk scenario is not verified.'; return out
    entry,stop,target=(number(scenario.get(k)) for k in ('entry','stop','target'))
    if any(v is None or v<=0 for v in (entry,stop,target)) or not (
        stop<entry<target if direction=='CALL' else target<entry<stop):
        out['reason']='Underlying entry/stop/target ordering is invalid.'; return out
    out['coverage'].update(requested_expiry=expected_expiry,
        contracts_received=len(quotes) if isinstance(quotes,list) else 0,contracts_passed=0)
    today=datetime.fromtimestamp(now,ZoneInfo('America/New_York')).date()
    accepted=[]
    for q in quotes if isinstance(quotes,list) else []:
        if not isinstance(q,dict): continue
        try:
            expiry=date.fromisoformat(q['expiration_date'])
            strike=number(q.get('strike'))
            if not strike or strike<=0 or abs(strike*1000-round(strike*1000))>1e-6: continue
            if expected_expiry is not None and expiry.isoformat()!=expected_expiry: continue
            # Reject adjusted/non-standard contracts and mismatched identity.
            occ=report['symbol']+expiry.strftime('%y%m%d')+direction[0]+f'{round(strike*1000):08d}'
            if (q.get('symbol')!=occ or q.get('root_symbol')!=report['symbol'] or
                q.get('underlying')!=report['symbol'] or q.get('type')!='option' or
                q.get('option_type')!=direction.lower() or q.get('contract_size')!=100 or
                not 1 <= (expiry-today).days <= 14): continue
            bid,ask=number(q.get('bid')),number(q.get('ask'))
            bt,at=number(q.get('bid_date')),number(q.get('ask_date'))
            if not bt or not at or not all(fresh_timestamp(t/1000,now) and t/1000>=report['bar_close_time'] for t in (bt,at)): continue
            if not bid or not ask or not 0<bid<=ask: continue
            spread=(ask-bid)/((ask+bid)/2)
            if spread>0.10 or ask-bid>0.50: continue
            if any(number(q.get(k)) is None or number(q[k])<v for k,v in [('volume',100),('open_interest',500),('bidsize',1),('asksize',1)]): continue
            g=q.get('greeks') or {}
            if not isinstance(g,dict): continue
            delta,iv=number(g.get('delta')),number(g.get('mid_iv'))
            # Hourly provider estimates are not live Greeks. Ambiguous timing blocks candidates.
            gt=greek_timestamp(g.get('updated_at'),now)
            if delta is None or iv is None or not 0<iv<=5 or gt is None: continue
            if not (0.4<=delta<=0.65 if direction=='CALL' else -0.65<=delta<=-0.4): continue
            expires=min(bt/1000+300,at/1000+300,report['quote_time']+300,
                report['bar_close_time']+300,end,gt+3600)
            if expires<=now: continue
            accepted.append(dict(contract=occ,expiry=expiry.isoformat(),strike=strike,bid=bid,ask=ask,
                bid_time=bt/1000,ask_time=at/1000,spread_pct=spread*100,volume=q['volume'],
                open_interest=q['open_interest'],delta=delta,iv=iv,greeks_updated_at=g['updated_at'],
                greeks_source_time=gt,greeks_kind='HOURLY_PROVIDER_ESTIMATE_NOT_LIVE',
                maximum_premium=ask,premium_at_risk=ask*100,expires_at=expires,
                contract_multiplier=100,underlying_invalidation=stop,underlying_target=target,
                underlying_risk_kind='UNDERLYING_PRICE_NOT_OPTION_PREMIUM'))
        except (KeyError,ValueError,TypeError,OverflowError): continue
    out['coverage']['contracts_passed']=len(accepted)
    if not accepted:
        out['reason']='No contract passes identity, expiry, fresh bid/ask, spread, volume and Greek checks.';return out
    c=min(accepted,key=lambda c:(c['spread_pct'],abs(abs(c['delta'])-0.55),c['expiry'],c['contract']))
    # Bid/ask are source quotes; exit levels below are a disclosed risk policy,
    # never inferred option forecasts or guaranteed stop fills.
    c['entry']=dict(kind='QUOTED_BID_ASK_RANGE',low=c['bid'],high=c['ask'],limit_cap=c['ask'],
        currency='USD',unit='PREMIUM_PER_SHARE',fill_guaranteed=False,
        note='Displayed bid/ask range, not a promised entry. Recheck the executable quote; do not chase above this snapshot cap.')
    c['premium_risk']=dict(maximum_loss_per_contract=c['premium_at_risk'],currency='USD',
        scope='LONG_OPTION_PREMIUM_ONLY',excludes_fees=True,
        note='Premium exposure at the displayed cap for one standard long option, plus costs. Exercise can create a separate underlying position and additional risk.')
    premium=Decimal(str(c['ask']))
    policy_stop=float((premium*Decimal('0.75')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))
    policy_target=float((premium*Decimal('1.50')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))
    c['exit_policy']=None
    if 0<policy_stop<c['ask']<policy_target:
        c['exit_policy']=dict(kind='ILLUSTRATIVE_POLICY_NOT_FORECAST',basis='ASK_CAP_NOT_ACTUAL_FILL',
            stop_pct=25,target_pct=50,stop_premium=policy_stop,target_premium=policy_target,
            stop_loss_guaranteed=False,
            note='Optional 25% stop / 50% target policy based on the ask cap. Recalculate from the actual fill and check permitted price ticks. Stops can gap; these levels do not cap losses or predict returns.')
    c['confidence']=dict(status='UNCALIBRATED',success_probability=None,
        basis=['Underlying directional scenario and fresh source timing passed.',
               'Standard contract identity, expiry, spread, size, volume, OI and hourly Greek filters passed.'])
    c['ranking']=dict(position=1,eligible_contracts=len(accepted),
        method='Lowest relative spread, then absolute delta closest to 0.55, then expiry and contract identifier.',
        note='Ranks execution-related filters within returned coverage, not expected profit or probability of success.')
    out.update(status='BUY_'+direction+'_CANDIDATE',candidate=c,confidence=c['confidence'],
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
        if cached and 0<=now-cached[0]<60: return assess(report,cached[1],now,expected_expiry=cached[2])
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
        _cache[symbol]=(time.time(),chain,dates[0])
        return assess(report,chain,time.time(),expected_expiry=dates[0])
    except Exception as exc:
        from urllib.error import HTTPError
        from trading_site import retry_delay
        delay=retry_delay(exc,time.time(),300) if isinstance(exc,HTTPError) else 60
        _retry_at=time.time()+delay
        return blocked('Options provider unavailable or response invalid; no buy signal.',direction)
    finally: _lock.release()
