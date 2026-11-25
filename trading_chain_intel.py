"""Server-side, fail-closed options evidence for the read-only Trading Desk.

The API returns a digest, not trade thresholds or proprietary scoring weights.
Snapshot time is not an executable quote timestamp.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import time
from math import isfinite
from trading_research import number

def _sum(rows, kind, key):
    return sum(number((r.get(kind) or {}).get(key)) or 0 for r in rows)

def _wall(rows, kind):
    found=[r for r in rows if (number((r.get(kind) or {}).get('oi')) or 0)>0]
    return max(found,key=lambda r:number((r.get(kind) or {}).get('oi')) or 0).get('strike') if found else None

def contract_review(report, chain, rows, now):
    """Read-only near-spot quote preview; never equate exchange snapshot with executable bid/ask."""
    symbol=report.get('symbol')
    if symbol not in ('NIFTY','BANKNIFTY','SENSEX') or report.get('region')!='IN' or chain.get('symbol')!=symbol or chain.get('region')!='IN':
        return None
    if report.get('stale_cache') or report.get('market_status')!='OPEN' or chain.get('status')!='SNAPSHOT':
        return None
    side={'LONG_RESEARCH':'call','BEARISH_RESEARCH':'put'}.get(report.get('verdict'))
    if not side:return None
    def recent(v,limit):
        t=number(v)
        return t is not None and 0<=now-t<=limit
    if not all(recent(report.get(k),300) for k in ('quote_time','bar_close_time')) or report['quote_time']<report['bar_close_time']:
        return None
    if chain.get('source')!='Angel One SmartAPI' or not recent(chain.get('spot_feed_time'),60) or not recent(chain.get('fetched_at'),60):
        return None
    try:
        if date.fromisoformat(chain['expiry'])<datetime.fromtimestamp(now,ZoneInfo('Asia/Kolkata')).date():return None
    except (KeyError,ValueError,TypeError):return None
    spot=number(chain.get('spot'))
    if not spot or spot<=0:return None
    choices=[]
    for row in rows:
        leg=row.get(side)
        strike=number(row.get('strike'))
        if not isinstance(leg,dict) or not strike or strike<=0:continue
        bid,ask,bsize,asize,lot,oi,vol=[number(leg.get(k)) for k in ('bid','ask','bid_size','ask_size','lot_size','oi','volume')]
        if not all(v is not None and v>0 for v in (bid,ask,bsize,asize,lot,oi,vol)) or ask<bid or lot!=int(lot) or asize<lot:continue
        spread=200*(ask-bid)/(ask+bid)
        if spread>5 or not recent(leg.get('feed_time'),60) or leg.get('feed_time_kind')!='EXCHANGE_FEED_SNAPSHOT_IST_NOT_SIDE_SPECIFIC':continue
        contract=leg.get('contract')
        if not isinstance(contract,str) or not contract.startswith(symbol) or not contract.endswith('CE' if side=='call' else 'PE'):continue
        choices.append((abs(strike-spot),spread,strike,dict(contract=contract,side='CE' if side=='call' else 'PE',strike=strike,expiry=chain['expiry'],bid=bid,ask=ask,lot_size=int(lot),premium_per_lot=round(ask*lot,2),feed_time=leg['feed_time'],expires_at=min(leg['feed_time'],chain['spot_feed_time'],chain['fetched_at'])+60,source=chain['source'])))
    return min(choices,key=lambda x:x[:3])[3] if choices else None

def evaluate(report, chain, now=None):
    now=time.time() if now is None else now
    chain=chain if isinstance(chain,dict) else {}

    rows=chain.get('rows') if isinstance(chain,dict) else None
    rows=[r for r in rows if isinstance(r,dict)] if isinstance(rows,list) else []
    actual=bool(chain.get('status')=='SNAPSHOT' and rows)
    expiry=chain.get('expiry')
    valid_expiry=False
    try:
        valid_expiry=bool(expiry and date.fromisoformat(expiry).isoformat()==expiry)
    except (ValueError,TypeError):
        pass
    call_oi=_sum(rows,'call','oi')
    put_oi=_sum(rows,'put','oi')
    changes=sum(1 for r in rows for k in ('call','put') if number((r.get(k) or {}).get('oi_change')) is not None)
    sides=[r[k] for r in rows for k in ('call','put') if isinstance(r.get(k),dict)]
    spreads=sum(1 for s in sides if number(s.get('bid')) and number(s.get('ask')) and
                number(s.get('ask'))>=number(s.get('bid')) and number(s.get('spread_pct')) is not None)
    # A chain snapshot cannot substitute a verified exchange quote timestamp.
    quote_times=sum(1 for s in sides if number(s.get('bid_time')) and number(s.get('ask_time')))
    ivs=[number(s.get('iv_pct')) for s in sides]
    ivs=[v for v in ivs if v is not None and 0<v<1000]
    greeks=sum(1 for s in sides if number(s.get('delta')) is not None)
    # Don't claim gamma / IV rank / event outcomes from a single chain snapshot.
    ready=bool(actual and valid_expiry and report.get('market_status')=='OPEN' and
               report.get('verdict') in ('LONG_RESEARCH','BEARISH_RESEARCH'))
    diagnostics=[
      dict(label='Price trend & risk',state='REVIEW' if ready else 'WAIT',detail='Underlying market checks are shown separately'),
      dict(label='Option open interest',state='CONTEXT' if actual and (call_oi or put_oi) else 'UNAVAILABLE',detail='OI and major strikes are contextual, not an entry trigger'),
      dict(label='OI changes',state='CONTEXT' if changes else 'UNAVAILABLE',detail='Changes do not prove fresh writing, covering or participant identity'),
      dict(label='Strike and expiry',state='CONTEXT' if actual and valid_expiry else 'UNAVAILABLE',detail='An expiry snapshot is available; the contract is not trade-verified'),
      dict(label='Bid / ask & liquidity',state='UNVERIFIED' if spreads else 'UNAVAILABLE',detail='Displayed spreads are not executable without timestamped quotes'),
      dict(label='IV / Greeks',state='CONTEXT' if ivs and greeks else 'INCOMPLETE',detail='Snapshot IV and delta are not IV rank or a live Greek feed'),
      dict(label='Gamma / gamma flip',state='UNAVAILABLE',detail='Requires complete timestamped strike-level gamma, OI and model assumptions'),
      dict(label='IV rank / crush risk',state='UNAVAILABLE',detail='Requires historical IV distribution and event-aware term structure'),
      dict(label='Event / volatility regime',state='UNAVAILABLE',detail='Validated exchange calendar and event feed are not connected here'),
      dict(label='Historical calibration',state='UNAVAILABLE',detail='No audited out-of-sample signal performance is available'),
    ]
    preview=contract_review(report,chain,rows,now)
    return dict(status='WAIT',eligible=False,contract_review=preview,
      reason='Recent contract snapshot available for broker review only; executable quote timestamps and risk evidence are still unverified.' if preview else 'No verified India CE/PE contract ticket. '+str(chain.get('message') or 'Do not enter based on a snapshot.'),
      summary='Underlying trend and chain context are separate from an executable options signal.',
      chain=dict(available=actual,expiry=expiry if valid_expiry else None,strikes=len(rows),
        pcr_oi=round(put_oi/call_oi,2) if call_oi else None,
        highest_call_oi_strike=_wall(rows,'call') if actual else None,
        highest_put_oi_strike=_wall(rows,'put') if actual else None,
        total_call_oi_change=_sum(rows,'call','oi_change') if changes else None,
        total_put_oi_change=_sum(rows,'put','oi_change') if changes else None,
        option_sides=len(sides),spreads_present=spreads,quote_timestamps_present=quote_times),
      checks=diagnostics,
      note='This is descriptive research only. Missing verified inputs always block options buy advice.')
