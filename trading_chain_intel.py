"""Server-side, fail-closed options evidence for the read-only Trading Desk.

The API returns a digest, not trade thresholds or proprietary scoring weights.
Snapshot time is not an executable quote timestamp.
"""
from datetime import date
from math import isfinite
from trading_research import number

def _sum(rows, kind, key):
    return sum(number((r.get(kind) or {}).get(key)) or 0 for r in rows)

def _wall(rows, kind):
    found=[r for r in rows if (number((r.get(kind) or {}).get('oi')) or 0)>0]
    return max(found,key=lambda r:number((r.get(kind) or {}).get('oi')) or 0).get('strike') if found else None

def evaluate(report, chain):
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
    return dict(status='WAIT',eligible=False,reason='No verified India CE/PE contract ticket. Do not enter based on a snapshot.',
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
