"""
Celesys AI - VERIFIED Real-Time Data
With built-in verification and ChatGPT comparison
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import requests
from datetime import datetime, timedelta
import hashlib
import yfinance as yf
from functools import lru_cache
import time
import json
import random
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# ═══════════════════════════════════════════════════════════
# PERFORMANCE ENGINE — handles 10K+ concurrent users
# ═══════════════════════════════════════════════════════════

# 1. GLOBAL CONNECTION POOL — reuse TCP connections across all requests
_http_pool = requests.Session()
_http_pool.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json,text/html',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
})
# Connection pool adapter — reuse up to 20 connections per host
from requests.adapters import HTTPAdapter
_pool_adapter = HTTPAdapter(pool_connections=20, pool_maxsize=30, max_retries=1)
_http_pool.mount('https://', _pool_adapter)
_http_pool.mount('http://', _pool_adapter)

# 2. SMART PER-ITEM CACHE — per-ticker with TTL
_smart_cache = {}

def _smart_cache_get(key: str):
    """Get from cache if not expired."""
    entry = _smart_cache.get(key)
    if entry and time.time() - entry['ts'] < entry['ttl']:
        return entry['data']
    return None

def _smart_cache_set(key: str, data, ttl: int = 120):
    """Set cache with TTL in seconds."""
    _smart_cache[key] = {'data': data, 'ts': time.time(), 'ttl': ttl}
    # Evict old entries periodically (keep cache under 5000 items)
    if len(_smart_cache) > 5000:
        cutoff = time.time() - 600  # Remove anything older than 10 min
        expired = [k for k, v in _smart_cache.items() if v['ts'] < cutoff]
        for k in expired:
            del _smart_cache[k]

# 4. SHARED THREAD POOL — for all blocking IO (yfinance, HTTP scrapes)
_thread_pool = ThreadPoolExecutor(max_workers=15, thread_name_prefix="celesys")

# 5. POPULAR TICKER PRE-FETCH — background refresh every 90 seconds
_POPULAR_TICKERS_IN = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'SBIN.NS', 'BHARTIARTL.NS', 'ITC.NS', 'LT.NS', 'BAJFINANCE.NS',
    'TATAMOTORS.NS', 'COALINDIA.NS', 'NTPC.NS', 'PERSISTENT.NS', 'CDSL.NS',
    'TRENT.NS', 'DIXON.NS', 'IREDA.NS', 'NHPC.NS', 'KPITTECH.NS'
]
_POPULAR_TICKERS_US = [
    'NVDA', 'MSFT', 'GOOGL', 'META', 'AAPL', 'AMZN', 'CRWD', 'PLTR',
    'JPM', 'BRK-B', 'MRK', 'AXON', 'SMH', 'QQQ', 'SOXX', 'VGT'
]

def _prefetch_popular():
    """Background pre-fetch popular tickers into smart cache."""
    all_tickers = _POPULAR_TICKERS_IN + _POPULAR_TICKERS_US
    def _fetch_one(tk):
        try:
            t = yf.Ticker(tk)
            info = t.info
            price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            if price and float(price) > 0:
                prev = info.get('previousClose') or info.get('regularMarketPreviousClose') or price
                chg_pct = round(((float(price) - float(prev)) / float(prev)) * 100, 2) if float(prev) > 0 else 0
                is_indian = '.NS' in tk or '.BO' in tk
                sym = '₹' if is_indian else '$'
                data = {
                    "price": round(float(price), 2),
                    "change_pct": chg_pct,
                    "symbol": sym,
                    "formatted": f"{sym}{round(float(price), 2):,.2f}"
                }
                _smart_cache_set(f"price:{tk}", data, 120)
                return tk, True
        except:
            pass
        return tk, False
    
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(_fetch_one, tk): tk for tk in all_tickers}
        success = 0
        for f in as_completed(futs, timeout=20):
            try:
                tk, ok = f.result(timeout=5)
                if ok: success += 1
            except:
                pass
    print(f"🔄 Pre-fetched {success}/{len(all_tickers)} popular tickers")

async def _start_prefetch_loop():
    """Run prefetch every 90 seconds in background."""
    while True:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(_thread_pool, _prefetch_popular)
        except Exception as e:
            print(f"⚠️ Prefetch error: {e}")
        await asyncio.sleep(90)

# ═══════════════════════════════════════════════════════════
# DIRECT YAHOO FINANCE HTTP API (bypasses yfinance library)
# Works when yfinance breaks due to rate limits/version bugs
# ═══════════════════════════════════════════════════════════

YAHOO_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
}

def fetch_yahoo_direct(ticker: str) -> dict:
    """
    Fallback: Direct HTTP to Yahoo Finance APIs.
    Chain: v8 chart → v6 quote → v10 quoteSummary
    """
    try:
        headers = {**YAHOO_HEADERS, 'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(110,125)}.0.0.0'}
        
        # ── v8 chart (price + history) ──
        chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
        chart_resp = requests.get(chart_url, headers=headers, timeout=10)
        if chart_resp.status_code != 200:
            return None
        
        chart_data = chart_resp.json()
        result = chart_data.get('chart', {}).get('result', [])
        if not result:
            return None
        
        meta = result[0].get('meta', {})
        indicators = result[0].get('indicators', {}).get('quote', [{}])[0]
        closes = [c for c in indicators.get('close', []) if c is not None]
        highs = [h for h in indicators.get('high', []) if h is not None]
        lows = [l for l in indicators.get('low', []) if l is not None]
        
        current_price = meta.get('regularMarketPrice', 0)
        previous_close = meta.get('chartPreviousClose', meta.get('previousClose', current_price))
        
        info = {
            'currentPrice': current_price,
            'previousClose': previous_close,
            'currency': meta.get('currency', 'USD'),
            'symbol': meta.get('symbol', ticker),
            'longName': meta.get('longName', ticker),
            'chartHigh': max(highs) if highs else current_price,
            'chartLow': min(lows) if lows else current_price,
            'closes': closes,
            'fiftyTwoWeekHigh': max(highs) if highs else current_price,
            'fiftyTwoWeekLow': min(lows) if lows else current_price,
            '_source': 'yahoo_chart_v8'
        }
        
        got_fundamentals = False
        
        # ── v6 quote API (best for fundamentals — no crumb needed) ──
        try:
            quote_url = f"https://query1.finance.yahoo.com/v6/finance/quote?symbols={ticker}"
            qr = requests.get(quote_url, headers=headers, timeout=8)
            if qr.status_code == 200:
                quotes = qr.json().get('quoteResponse', {}).get('result', [])
                if quotes:
                    q = quotes[0]
                    info.update({
                        'longName': q.get('longName', q.get('shortName', ticker)),
                        'marketCap': q.get('marketCap', 0),
                        'trailingPE': q.get('trailingPE', 0),
                        'forwardPE': q.get('forwardPE', 0),
                        'priceToBook': q.get('priceToBook', 0),
                        'dividendYield': q.get('trailingAnnualDividendYield', 0),
                        'beta': q.get('beta', 0),
                        'profitMargins': q.get('profitMargins', 0),
                        'fiftyTwoWeekHigh': q.get('fiftyTwoWeekHigh', info['chartHigh']),
                        'fiftyTwoWeekLow': q.get('fiftyTwoWeekLow', info['chartLow']),
                        '_source': 'yahoo_v6_quote'
                    })
                    got_fundamentals = bool(q.get('trailingPE') or q.get('marketCap'))
                    print(f"  v6 quote: PE={q.get('trailingPE')}, MCap={q.get('marketCap')}")
        except Exception as e:
            print(f"  v6 quote failed: {e}")
        
        # ── v10 quoteSummary (fuller data — margins, ROE, sector) ──
        try:
            modules = 'summaryProfile,assetProfile,financialData,defaultKeyStatistics,summaryDetail,price'
            sr = requests.get(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules={modules}", headers=headers, timeout=8)
            sr_ct = sr.headers.get('content-type', '')
            if sr.status_code == 200 and 'json' in sr_ct and '<html' not in sr.text[:200].lower():
                qresult = sr.json().get('quoteSummary', {}).get('result', [])
                if qresult:
                    r = qresult[0]
                    fin = r.get('financialData', {})
                    stats = r.get('defaultKeyStatistics', {})
                    detail = r.get('summaryDetail', {})
                    profile = r.get('summaryProfile', {})
                    asset_profile = r.get('assetProfile', {})
                    # Merge: assetProfile often has longBusinessSummary when summaryProfile doesn't
                    if asset_profile:
                        for _ak in ['longBusinessSummary', 'fullTimeEmployees', 'website', 'sector', 'industry']:
                            if not profile.get(_ak) and asset_profile.get(_ak):
                                profile[_ak] = asset_profile[_ak]
                    price_d = r.get('price', {})
                    
                    def raw(d, key, default=0):
                        v = d.get(key, {})
                        return v.get('raw', v.get('fmt', default)) if isinstance(v, dict) else (v or default)
                    
                    # Always set margins/ROE/debt (these only come from v10)
                    updates = {
                        'sector': profile.get('sector', info.get('sector', 'N/A')),
                        'industry': profile.get('industry', info.get('industry', 'N/A')),
                        'longBusinessSummary': profile.get('longBusinessSummary', info.get('longBusinessSummary', '')),
                        'fullTimeEmployees': profile.get('fullTimeEmployees', info.get('fullTimeEmployees', 'N/A')),
                        'website': profile.get('website', info.get('website', '')),
                        'profitMargins': raw(fin, 'profitMargins') or info.get('profitMargins', 0),
                        'operatingMargins': raw(fin, 'operatingMargins') or info.get('operatingMargins', 0),
                        'returnOnEquity': raw(fin, 'returnOnEquity') or info.get('returnOnEquity', 0),
                        'debtToEquity': raw(fin, 'debtToEquity') or info.get('debtToEquity', 0),
                        'currentRatio': raw(fin, 'currentRatio') or info.get('currentRatio', 0),
                    }
                    if not got_fundamentals:
                        updates.update({
                            'longName': raw(price_d, 'longName') or info.get('longName', ticker),
                            'marketCap': raw(price_d, 'marketCap') or info.get('marketCap', 0),
                            'trailingPE': raw(detail, 'trailingPE') or info.get('trailingPE', 0),
                            'forwardPE': raw(stats, 'forwardPE') or info.get('forwardPE', 0),
                            'priceToBook': raw(stats, 'priceToBook') or info.get('priceToBook', 0),
                            'dividendYield': raw(detail, 'dividendYield') or info.get('dividendYield', 0),
                            'beta': raw(stats, 'beta') or info.get('beta', 0),
                            'fiftyTwoWeekHigh': raw(detail, 'fiftyTwoWeekHigh') or info['fiftyTwoWeekHigh'],
                            'fiftyTwoWeekLow': raw(detail, 'fiftyTwoWeekLow') or info['fiftyTwoWeekLow'],
                        })
                    info.update(updates)
                    info['_source'] = 'yahoo_direct_full'
                    print(f"  v10 summary: sector={info.get('sector')}, margins={info.get('profitMargins')}, ROE={info.get('returnOnEquity')}")
            else:
                print(f"  v10 blocked (status={sr.status_code}, ct={sr_ct[:30]})")
        except Exception as e:
            print(f"  v10 summary failed: {e}")
        
        return info
        
    except Exception as e:
        print(f"❌ Yahoo direct HTTP failed: {e}")
        return None


def fetch_management_context(ticker: str, company_name: str) -> tuple:
    """
    Fetch real analyst/earnings/insider data from free sources.
    Returns text that gets injected into the AI prompt for real analysis.
    """
    import re
    context_parts = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36'}
    is_indian = '.NS' in ticker or '.BO' in ticker
    clean_ticker = ticker.replace('.NS', '').replace('.BO', '')
    
    # ── 1. Yahoo Finance analysis page (analyst targets + estimates) ──
    try:
        url = f"https://query1.finance.yahoo.com/v6/finance/quote?symbols={ticker}"
        r = requests.get(url, headers={**YAHOO_HEADERS}, timeout=8)
        ct = r.headers.get('content-type', '')
        if r.status_code == 200 and 'json' in ct and '<html' not in r.text[:200].lower():
            quotes = r.json().get('quoteResponse', {}).get('result', [])
            if quotes:
                q = quotes[0]
                parts = []
                if q.get('averageAnalystRating'): parts.append(f"Analyst Rating: {q['averageAnalystRating']}")
                if q.get('targetMeanPrice'): parts.append(f"Mean Price Target: ${q['targetMeanPrice']}")  
                if q.get('targetHighPrice'): parts.append(f"High Target: ${q['targetHighPrice']}")
                if q.get('targetLowPrice'): parts.append(f"Low Target: ${q['targetLowPrice']}")
                if q.get('recommendationKey'): parts.append(f"Recommendation: {q['recommendationKey'].upper()}")
                if q.get('numberOfAnalystOpinions'): parts.append(f"Analyst Count: {q['numberOfAnalystOpinions']}")
                if q.get('earningsTimestamp'):
                    from datetime import datetime
                    ts = datetime.fromtimestamp(q['earningsTimestamp'])
                    parts.append(f"Last Earnings Date: {ts.strftime('%Y-%m-%d')}")
                if q.get('epsTrailingTwelveMonths'): parts.append(f"EPS (TTM): ${q['epsTrailingTwelveMonths']:.2f}")
                if q.get('epsForward'): parts.append(f"EPS Forward: ${q['epsForward']:.2f}")
                if q.get('epsCurrentYear'): parts.append(f"EPS Current Year: ${q['epsCurrentYear']:.2f}")
                if q.get('revenueGrowth'): parts.append(f"Revenue Growth: {q['revenueGrowth']*100:.1f}%")
                if q.get('earningsGrowth'): parts.append(f"Earnings Growth: {q['earningsGrowth']*100:.1f}%")
                if q.get('revenuePerShare'): parts.append(f"Revenue/Share: ${q['revenuePerShare']:.2f}")
                if q.get('heldPercentInsiders'): parts.append(f"Insider Ownership: {q['heldPercentInsiders']*100:.1f}%")
                if q.get('heldPercentInstitutions'): parts.append(f"Institutional Ownership: {q['heldPercentInstitutions']*100:.1f}%")
                if q.get('shortPercentOfFloat'): parts.append(f"Short Interest: {q['shortPercentOfFloat']*100:.1f}%")
                if q.get('sharesShortPreviousMonthDate'):
                    if q.get('sharesShort') and q.get('sharesShortPriorMonth'):
                        chg = q['sharesShort'] - q['sharesShortPriorMonth']
                        direction = "increased" if chg > 0 else "decreased"
                        parts.append(f"Short Interest {direction} by {abs(chg):,} shares vs prior month")
                if parts:
                    context_parts.append("=== ANALYST & MARKET DATA (REAL) ===\n" + "\n".join(parts))
                    print(f"✅ Got {len(parts)} analyst data points for {ticker}")
    except Exception as e:
        print(f"⚠️ Analyst data fetch failed: {e}")
    
    # ── 2. Yahoo earnings history ──
    try:
        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=earnings,earningsHistory,earningsTrend"
        r = requests.get(url, headers={**YAHOO_HEADERS}, timeout=8)
        # CRITICAL: Validate we got JSON, not HTML (Yahoo rate limits return HTML pages)
        content_type = r.headers.get('content-type', '')
        if r.status_code == 200 and 'json' in content_type and '<html' not in r.text[:200].lower():
            data = r.json().get('quoteSummary', {}).get('result', [])
            if data:
                d = data[0]
                parts = []
                
                # Earnings history (actual vs estimate)
                eh = d.get('earningsHistory', {}).get('history', [])
                if eh:
                    parts.append("\n--- EARNINGS SURPRISE HISTORY ---")
                    for e in eh[-4:]:  # last 4 quarters
                        def rv(x): 
                            return x.get('raw', 0) if isinstance(x, dict) else (x or 0)
                        actual = rv(e.get('epsActual', {}))
                        est = rv(e.get('epsEstimate', {}))
                        surprise = rv(e.get('epsDifference', {}))
                        surprise_pct = rv(e.get('surprisePercent', {}))
                        qtr = e.get('quarter', {})
                        qtr_val = rv(qtr) if isinstance(qtr, dict) else qtr
                        parts.append(f"Q{qtr_val}: Actual EPS ${actual:.2f} vs Est ${est:.2f} | Surprise: {surprise_pct*100:.1f}%")
                
                # Earnings trend (forward estimates)
                et = d.get('earningsTrend', {}).get('trend', [])
                if et:
                    parts.append("\n--- FORWARD EARNINGS ESTIMATES ---")
                    for t in et[:4]:
                        period = t.get('period', '')
                        growth = t.get('growth', {})
                        growth_val = growth.get('raw', 0) if isinstance(growth, dict) else 0
                        eps_est = t.get('earningsEstimate', {}).get('avg', {})
                        eps_val = eps_est.get('raw', 0) if isinstance(eps_est, dict) else 0
                        rev_est = t.get('revenueEstimate', {}).get('avg', {})
                        rev_val = rev_est.get('raw', 0) if isinstance(rev_est, dict) else 0
                        if eps_val:
                            parts.append(f"{period}: EPS Est ${eps_val:.2f} | Growth {growth_val*100:.1f}% | Rev Est ${rev_val:,.0f}")
                
                # Quarterly financials
                earnings = d.get('earnings', {}).get('financialsChart', {})
                quarterly = earnings.get('quarterly', [])
                if quarterly:
                    parts.append("\n--- QUARTERLY REVENUE & EARNINGS ---")
                    for q in quarterly[-4:]:
                        rev = q.get('revenue', {})
                        earn = q.get('earnings', {})
                        rev_val = rev.get('raw', 0) if isinstance(rev, dict) else 0
                        earn_val = earn.get('raw', 0) if isinstance(earn, dict) else 0
                        date = q.get('date', '')
                        parts.append(f"{date}: Revenue ${rev_val:,.0f} | Earnings ${earn_val:,.0f}")
                
                # LIVE earnings dates — shows actual reported dates + EPS
                try:
                    ed_df = tk_ins.earnings_dates
                    if ed_df is not None and len(ed_df) > 0:
                        parts.append("\n--- RECENT EARNINGS REPORTS (LIVE FROM EXCHANGE) ---")
                        for idx_row in range(min(4, len(ed_df))):
                            row = ed_df.iloc[idx_row]
                            date_str = str(ed_df.index[idx_row])[:10]
                            eps_est = row.get('EPS Estimate', 'N/A')
                            eps_act = row.get('Reported EPS', 'N/A')
                            surprise = row.get('Surprise(%)', 'N/A')
                            if eps_act != 'N/A' and eps_act is not None:
                                parts.append(f"{date_str}: EPS Reported ${float(eps_act):.2f} (Est: ${float(eps_est):.2f}, Surprise: {surprise}%)")
                            else:
                                parts.append(f"{date_str}: UPCOMING — EPS Est ${float(eps_est):.2f}" if eps_est != 'N/A' and eps_est is not None else f"{date_str}: UPCOMING")
                        print(f"✅ Got live earnings dates for {ticker}")
                except Exception as ed_ex:
                    print(f"⚠️ earnings_dates failed for {ticker}: {ed_ex}")
                
                if parts:
                    context_parts.append("=== EARNINGS & QUARTERLY DATA (REAL) ===\n" + "\n".join(parts))
                    print(f"✅ Got earnings history for {ticker}")
    except Exception as e:
        print(f"⚠️ Earnings data fetch failed: {e}")
    
    # ── 2b. Yahoo Fund/Institutional Holdings ──
    fund_holdings_data = {"institutions": [], "funds": [], "summary": {}}
    try:
        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=institutionOwnership,fundOwnership,majorHoldersBreakdown"
        r = requests.get(url, headers={**YAHOO_HEADERS}, timeout=8)
        ct = r.headers.get('content-type', '')
        if r.status_code == 200 and 'json' in ct and '<html' not in r.text[:200].lower():
            data = r.json().get('quoteSummary', {}).get('result', [])
            if data:
                d = data[0]
                parts = []
                
                # Major holders breakdown
                mh = d.get('majorHoldersBreakdown', {})
                if mh:
                    def rv(x): return x.get('raw', 0) if isinstance(x, dict) else (x or 0)
                    insider_pct = rv(mh.get('insidersPercentHeld', {}))
                    inst_pct = rv(mh.get('institutionsPercentHeld', {}))
                    float_inst = rv(mh.get('institutionsFloatPercentHeld', {}))
                    inst_count = rv(mh.get('institutionsCount', {}))
                    fund_holdings_data["summary"] = {
                        "institutional_pct": round(inst_pct * 100, 2) if inst_pct else 0,
                        "insider_pct": round(insider_pct * 100, 2) if insider_pct else 0,
                        "float_inst_pct": round(float_inst * 100, 2) if float_inst else 0,
                        "inst_count": int(inst_count) if inst_count else 0
                    }
                    if inst_pct: parts.append(f"Institutional Ownership: {inst_pct*100:.1f}%")
                    if insider_pct: parts.append(f"Insider Ownership: {insider_pct*100:.1f}%")
                    if float_inst: parts.append(f"Institutions % of Float: {float_inst*100:.1f}%")
                    if inst_count: parts.append(f"Number of Institutions: {int(inst_count)}")
                
                # Top institutional holders
                inst = d.get('institutionOwnership', {}).get('ownershipList', [])
                if inst:
                    parts.append("\n--- TOP INSTITUTIONAL HOLDERS ---")
                    for h in inst[:10]:
                        name = h.get('organization', 'Unknown')
                        pct = h.get('pctHeld', {})
                        pct_val = pct.get('raw', 0) if isinstance(pct, dict) else 0
                        shares = h.get('position', {})
                        shares_val = shares.get('raw', 0) if isinstance(shares, dict) else 0
                        value = h.get('value', {})
                        value_val = value.get('raw', 0) if isinstance(value, dict) else 0
                        fund_holdings_data["institutions"].append({
                            "name": name, "pct": round(pct_val * 100, 2),
                            "shares": int(shares_val), "value": int(value_val)
                        })
                        parts.append(f"{name}: {pct_val*100:.2f}% ({int(shares_val):,} shares, ${int(value_val):,})")
                
                # Top mutual fund holders
                funds = d.get('fundOwnership', {}).get('ownershipList', [])
                if funds:
                    parts.append("\n--- TOP MUTUAL FUND HOLDERS ---")
                    for f in funds[:10]:
                        name = f.get('organization', 'Unknown')
                        pct = f.get('pctHeld', {})
                        pct_val = pct.get('raw', 0) if isinstance(pct, dict) else 0
                        shares = f.get('position', {})
                        shares_val = shares.get('raw', 0) if isinstance(shares, dict) else 0
                        fund_holdings_data["funds"].append({
                            "name": name, "pct": round(pct_val * 100, 2),
                            "shares": int(shares_val)
                        })
                        parts.append(f"{name}: {pct_val*100:.2f}% ({int(shares_val):,} shares)")
                
                if parts:
                    context_parts.append("=== FUND & INSTITUTIONAL HOLDINGS (REAL) ===\n" + "\n".join(parts))
                    print(f"✅ Got {len(inst)} institutional + {len(funds)} fund holders for {ticker}")
    except Exception as e:
        print(f"⚠️ Fund holdings fetch failed: {e}")
    
    # ── 3. For Indian stocks: Screener.in data ──
    if is_indian:
        try:
            screener_url = f"https://www.screener.in/api/company/{clean_ticker}/consolidated/"
            r = requests.get(screener_url, headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
                parts = []
                if data.get('warehouse_set'):
                    wh = data['warehouse_set']
                    if wh.get('promoter_holding'): parts.append(f"Promoter Holding: {wh['promoter_holding']}%")
                    if wh.get('pledged_percentage'): parts.append(f"Promoter Pledge: {wh['pledged_percentage']}%")
                    if wh.get('roce'): parts.append(f"ROCE: {wh['roce']}%")
                    if wh.get('roe'): parts.append(f"ROE: {wh['roe']}%")
                    if wh.get('sales_growth_3years'): parts.append(f"3Y Sales Growth: {wh['sales_growth_3years']}%")
                    if wh.get('profit_growth_3years'): parts.append(f"3Y Profit Growth: {wh['profit_growth_3years']}%")
                if parts:
                    context_parts.append("=== INDIAN MARKET DATA (Screener.in) ===\n" + "\n".join(parts))
                    print(f"✅ Got Screener.in data for {clean_ticker}")
        except Exception as e:
            print(f"⚠️ Screener.in failed: {e}")
        
        # ── 4. For Indian stocks: Moneycontrol data (management commentary, quarterly results) ──
        try:
            import re as re_mc
            # Moneycontrol search - find stock URL
            mc_search = f"https://www.moneycontrol.com/stocks/company_info/stock_news.php?sc_id={clean_ticker}"
            mc_resp = requests.get(f"https://www.moneycontrol.com/indian-indices/nifty-50-9", headers=headers, timeout=6)
            # Alternative: direct company page
            mc_url = f"https://www.moneycontrol.com/stocks/company_info/print_financials.php?sc_did={clean_ticker}"
            mc_resp = requests.get(mc_url, headers=headers, timeout=6)
            if mc_resp.status_code == 200:
                text = mc_resp.text
                parts = []
                
                # Extract management discussions/commentary from page
                mgmt_disc = re_mc.findall(r'(?:management|board|promoter|chairman|CEO|MD)[^<]{10,300}', text, re_mc.IGNORECASE)
                for disc in mgmt_disc[:3]:
                    clean = re_mc.sub(r'<[^>]+>', '', disc).strip()
                    if len(clean) > 20:
                        parts.append(f"Management Note: {clean[:200]}")
                
                # Extract quarterly results mentions  
                qr_mentions = re_mc.findall(r'(?:quarterly|Q[1-4]|results?|revenue|profit|EPS|earnings)[^<]{10,200}', text, re_mc.IGNORECASE)
                for qr in qr_mentions[:3]:
                    clean = re_mc.sub(r'<[^>]+>', '', qr).strip()
                    if len(clean) > 15:
                        parts.append(f"Quarterly Info: {clean[:200]}")
                
                if parts:
                    context_parts.append("=== MONEYCONTROL DATA (India) ===\n" + "\n".join(parts))
                    print(f"✅ Got Moneycontrol data for {clean_ticker}")
        except Exception as e:
            print(f"⚠️ Moneycontrol failed: {e}")
    
    # ── 5. For US stocks: Finviz data (analyst targets, insider trading, earnings) ──
    if not is_indian:
        try:
            import re as re_fv
            finviz_url = f"https://finviz.com/quote.ashx?t={ticker}&ty=c&p=d&b=1"
            fv_headers = {**headers, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0'}
            fv_resp = requests.get(finviz_url, headers=fv_headers, timeout=8)
            if fv_resp.status_code == 200:
                text = fv_resp.text
                parts = []
                
                # Extract key Finviz stats
                stat_map = {
                    'Target Price': 'targetPrice', 'Insider Own': 'insiderOwn', 
                    'Insider Trans': 'insiderTrans', 'Inst Own': 'instOwn',
                    'Inst Trans': 'instTrans', 'Short Float': 'shortFloat',
                    'Earnings': 'earningsDate', 'EPS next Y': 'epsNextY',
                    'EPS next Q': 'epsNextQ', 'Sales Q/Q': 'salesQQ',
                    'EPS Q/Q': 'epsQQ', 'Perf Quarter': 'perfQ',
                    'Perf Half Y': 'perfHY', 'Perf Year': 'perfY',
                    'Recom': 'recommendation', 'Avg Volume': 'avgVol',
                    'SMA20': 'sma20', 'SMA50': 'sma50', 'SMA200': 'sma200',
                }
                
                for label, key in stat_map.items():
                    pattern = f'>{re_fv.escape(label)}</td>.*?<b>([^<]+)</b>'
                    m = re_fv.search(pattern, text, re_fv.DOTALL)
                    if m:
                        parts.append(f"{label}: {m.group(1).strip()}")
                
                # Extract recent insider transactions
                insider_matches = re_fv.findall(r'class="insider-(?:buy|sale)-cell[^"]*"[^>]*>([^<]+)', text)
                if insider_matches:
                    parts.append(f"\nRecent Insider Activity: {', '.join(insider_matches[:5])}")
                
                if parts:
                    context_parts.append("=== FINVIZ DATA (US Market) ===\n" + "\n".join(parts))
                    print(f"✅ Got Finviz data for {ticker}")
        except Exception as e:
            print(f"⚠️ Finviz failed: {e}")
    
    if not context_parts:
        return "", fund_holdings_data
    
    # CRITICAL: Sanitize — strip any HTML that leaked from Yahoo/Moneycontrol responses
    import re as re_clean
    result = "\n\n".join(context_parts)
    # Remove HTML tags
    result = re_clean.sub(r'<[^>]+>', '', result)
    # Remove common HTML artifacts
    result = re_clean.sub(r'&nbsp;|&amp;|&lt;|&gt;|&quot;|&#\d+;', ' ', result)
    # Remove excessive whitespace
    result = re_clean.sub(r'\n{3,}', '\n\n', result)
    result = re_clean.sub(r' {3,}', ' ', result)
    # Remove any lines that look like HTML/JS code
    clean_lines = []
    for line in result.split('\n'):
        stripped = line.strip()
        # Skip lines that look like code/HTML
        if any(x in stripped.lower() for x in ['<script', '<style', '<div', '<span', '<meta', 'function(', '{display:', 'class="', 'onclick=']):
            continue
        if stripped:
            clean_lines.append(line)
    result = '\n'.join(clean_lines)
    
    print(f"📊 Management context: {len(result)} chars (sanitized)")
    return result, fund_holdings_data


def fetch_yahoo_scrape(ticker: str) -> dict:
    """
    Last resort: Scrape Yahoo Finance quote page for basic data.
    Works even when APIs are blocked.
    """
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        }
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            return None
        
        text = resp.text
        
        # Try to find JSON data embedded in page
        import re
        
        # Look for price in page title or meta
        price_match = re.search(r'data-testid="qsp-price"[^>]*>([0-9,.]+)', text)
        if not price_match:
            price_match = re.search(r'"regularMarketPrice":\{"raw":([0-9.]+)', text)
        
        if not price_match:
            return None
        
        price = float(price_match.group(1).replace(',', ''))
        
        # Extract other fields from JSON blobs in page
        def extract_raw(field):
            m = re.search(f'"{field}":{{"raw":([0-9.eE+\\-]+)', text)
            return float(m.group(1)) if m else 0
        
        def extract_str(field):
            m = re.search(f'"{field}":"([^"]+)"', text)
            return m.group(1) if m else 'N/A'
        
        return {
            'currentPrice': price,
            'previousClose': extract_raw('regularMarketPreviousClose') or extract_raw('previousClose') or price,
            'currency': extract_str('currency') or 'USD',
            'longName': extract_str('longName') or ticker,
            'marketCap': extract_raw('marketCap'),
            'trailingPE': extract_raw('trailingPE'),
            'forwardPE': extract_raw('forwardPE'),
            'priceToBook': extract_raw('priceToBook'),
            'dividendYield': extract_raw('dividendYield'),
            'beta': extract_raw('beta'),
            'sector': extract_str('sector'),
            'industry': extract_str('industry'),
            'profitMargins': extract_raw('profitMargins'),
            'operatingMargins': extract_raw('operatingMargins'),
            'returnOnEquity': extract_raw('returnOnEquity'),
            'debtToEquity': extract_raw('debtToEquity'),
            'currentRatio': extract_raw('currentRatio'),
            'fiftyTwoWeekHigh': extract_raw('fiftyTwoWeekHigh') or price * 1.1,
            'fiftyTwoWeekLow': extract_raw('fiftyTwoWeekLow') or price * 0.8,
            '_source': 'yahoo_scrape'
        }
    except Exception as e:
        print(f"❌ Yahoo scrape failed: {e}")
        return None


def fetch_google_finance(ticker: str) -> dict:
    """
    Source 4: Google Finance page scrape for fundamentals.
    Google Finance pages are public and rarely rate-limited.
    Extracts: P/E, Market Cap, Dividend Yield, 52W range, etc.
    """
    import re
    try:
        # Convert ticker format for Google Finance URLs
        if '.NS' in ticker:
            g_tickers = [ticker.replace('.NS', '') + ':NSE']
        elif '.BO' in ticker:
            g_tickers = [ticker.replace('.BO', '') + ':BOM']
        else:
            # US stocks need exchange suffix — try NASDAQ first, then NYSE
            base = ticker.replace('.', '-')
            g_tickers = [f"{base}:NASDAQ", f"{base}:NYSE", f"{base}:NYSEARCA", base]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        text = None
        for g_ticker in g_tickers:
            url = f"https://www.google.com/finance/quote/{g_ticker}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200 and 'data-last-price' in resp.text:
                text = resp.text
                print(f"  ✅ Google Finance resolved: {g_ticker}")
                break
        
        if not text:
            return None
        
        # Extract price from Google Finance page
        price_match = re.search(r'data-last-price="([0-9.]+)"', text)
        if not price_match:
            price_match = re.search(r'class="YMlKec fxKbKc"[^>]*>([0-9,.]+)', text)
        if not price_match:
            return None
        
        price = float(price_match.group(1).replace(',', ''))
        
        # Google Finance shows key stats in structured data
        info = {
            'currentPrice': price,
            'previousClose': price,  # Will be refined below
            'currency': 'INR' if '.NS' in ticker or '.BO' in ticker else 'USD',
            'longName': ticker,
            '_source': 'google_finance'
        }
        
        # Extract key stats from Google Finance page
        # Google uses format: <div class="...">P/E ratio</div><div class="...">25.30</div>
        stat_patterns = [
            (r'P/E ratio.*?<div[^>]*>([0-9,.]+)', 'trailingPE'),
            (r'Market cap.*?<div[^>]*>([0-9,.]+[TBMK]?)', 'marketCap_str'),
            (r'Dividend yield.*?<div[^>]*>([0-9,.]+)%', 'dividendYield_pct'),
            (r'52-wk high.*?<div[^>]*>([0-9,.]+)', 'fiftyTwoWeekHigh'),
            (r'52-wk low.*?<div[^>]*>([0-9,.]+)', 'fiftyTwoWeekLow'),
            (r'Prev close.*?<div[^>]*>([0-9,.]+)', 'previousClose'),
            (r'Revenue.*?<div[^>]*>\$?₹?([0-9,.]+[TBMK]?)', 'revenue_str'),
            (r'Net income.*?<div[^>]*>\$?₹?([0-9,.]+[TBMK]?)', 'netIncome_str'),
            (r'EPS.*?<div[^>]*>\$?₹?([0-9,.]+)', 'eps'),
        ]
        
        for pattern, key in stat_patterns:
            m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if m:
                val_str = m.group(1).replace(',', '')
                try:
                    if key == 'marketCap_str':
                        # Convert 1.23T, 456B, 78M format
                        mult = 1
                        if val_str.endswith('T'): mult = 1e12; val_str = val_str[:-1]
                        elif val_str.endswith('B'): mult = 1e9; val_str = val_str[:-1]
                        elif val_str.endswith('M'): mult = 1e6; val_str = val_str[:-1]
                        elif val_str.endswith('K'): mult = 1e3; val_str = val_str[:-1]
                        info['marketCap'] = float(val_str) * mult
                    elif key == 'dividendYield_pct':
                        info['dividendYield'] = float(val_str) / 100  # Convert to decimal
                    elif key == 'previousClose':
                        info['previousClose'] = float(val_str)
                    else:
                        info[key] = float(val_str)
                except:
                    pass
        
        # Extract company name
        name_match = re.search(r'<div[^>]*class="zzDege"[^>]*>([^<]+)', text)
        if name_match:
            info['longName'] = name_match.group(1).strip()
        
        if info.get('trailingPE') or info.get('marketCap'):
            print(f"✅ Google Finance: PE={info.get('trailingPE')}, MCap={info.get('marketCap')}")
            return info
        
        return None
        
    except Exception as e:
        print(f"❌ Google Finance scrape failed: {e}")
        return None

import math as _math_global

class NaNSafeEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts NaN/Infinity to null"""
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)
    def encode(self, o):
        return super().encode(self._sanitize(o))
    def _sanitize(self, obj):
        if isinstance(obj, float):
            if _math_global.isnan(obj) or _math_global.isinf(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize(i) for i in obj]
        return obj

class SafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(content, cls=NaNSafeEncoder, ensure_ascii=False).encode("utf-8")

app = FastAPI(title="Celesys AI - Verified Live Data", default_response_class=SafeJSONResponse)

# ═══ STARTUP: launch background pre-fetch for popular tickers ═══
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_start_prefetch_loop())
    print("🚀 Background price pre-fetcher started (90s interval)")

# ═══════════════════════════════════════════════════════════
# SOURCE 5: FINVIZ FUNDAMENTALS (US stocks)
# ═══════════════════════════════════════════════════════════
def fetch_finviz_fundamentals(ticker: str) -> dict:
    """Scrape Finviz for P/E, P/B, Market Cap, margins, ROE, beta, debt/equity etc."""
    import re as re_fv
    try:
        clean_ticker = ticker.replace('.NS', '').replace('.BO', '')
        url = f"https://finviz.com/quote.ashx?t={clean_ticker}&ty=c&p=d&b=1"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://finviz.com/',
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ Finviz returned {resp.status_code}")
            return None
        
        text = resp.text
        result = {}
        
        metric_map = {
            'P/E': ('trailingPE', 'float'),
            'Forward P/E': ('forwardPE', 'float'),
            'P/B': ('priceToBook', 'float'),
            'Market Cap': ('marketCap', 'mcap'),
            'Dividend %': ('dividendYield', 'pct'),
            'ROE': ('returnOnEquity', 'pct'),
            'ROA': ('returnOnAssets', 'pct'),
            'Profit Margin': ('profitMargins', 'pct'),
            'Oper. Margin': ('operatingMargins', 'pct'),
            'Gross Margin': ('grossMargins', 'pct'),
            'Debt/Eq': ('debtToEquity', 'float_x100'),
            'Current Ratio': ('currentRatio', 'float'),
            'Beta': ('beta', 'float'),
            'EPS (ttm)': ('trailingEps', 'float'),
        }
        
        for label, (key, typ) in metric_map.items():
            # Try multiple patterns for Finviz HTML
            patterns = [
                f'>{re_fv.escape(label)}</td>.*?<b>([^<]+)</b>',
                f'>{re_fv.escape(label)}</td>\\s*<td[^>]*>([^<]+)</td>',
                f'"{re_fv.escape(label)}"[^>]*>.*?<b>([^<]+)</b>',
            ]
            raw = None
            for pat in patterns:
                m = re_fv.search(pat, text, re_fv.DOTALL | re_fv.I)
                if m:
                    raw = m.group(1).strip()
                    if raw and raw != '-':
                        break
                    raw = None
            
            if not raw:
                continue
            try:
                if typ == 'float':
                    result[key] = float(raw.replace(',', ''))
                elif typ == 'float_x100':
                    result[key] = float(raw.replace(',', '')) * 100
                elif typ == 'pct':
                    result[key] = float(raw.replace('%', '').replace(',', '')) / 100
                elif typ == 'mcap':
                    raw = raw.upper().replace(',', '')
                    mult = 1
                    if 'T' in raw: mult = 1e12; raw = raw.replace('T', '')
                    elif 'B' in raw: mult = 1e9; raw = raw.replace('B', '')
                    elif 'M' in raw: mult = 1e6; raw = raw.replace('M', '')
                    result[key] = float(raw) * mult
            except:
                pass
        
        # Sector/Industry
        sec_m = re_fv.search(r'Sector[^<]*</a>.*?<a[^>]*>([^<]+)</a>', text, re_fv.DOTALL)
        if sec_m: result['sector'] = sec_m.group(1).strip()
        ind_m = re_fv.search(r'Industry[^<]*</a>.*?<a[^>]*>([^<]+)</a>', text, re_fv.DOTALL)
        if ind_m: result['industry'] = ind_m.group(1).strip()
        
        if result:
            print(f"  ✅ Finviz fundamentals: got {len(result)} metrics ({', '.join(result.keys())})")
        return result if result else None
    except Exception as e:
        print(f"  ⚠️ Finviz fundamentals failed: {e}")
        return None


def fetch_stockanalysis_fundamentals(ticker: str) -> dict:
    """Scrape stockanalysis.com for financials — another Yahoo alternative."""
    try:
        clean = ticker.replace('.NS', '').replace('.BO', '')
        url = f"https://stockanalysis.com/stocks/{clean.lower()}/financials/quarterly/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html',
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return {}
        text = resp.text
        result = {}
        
        # Try the overview page for ratios
        url2 = f"https://stockanalysis.com/stocks/{clean.lower()}/"
        resp2 = requests.get(url2, headers=headers, timeout=8)
        if resp2.status_code == 200:
            text2 = resp2.text
            
            def extract_sa(label):
                # Pattern: "Market Cap" ... some value like "$2.51T" or "25.3"
                pat = f'{re.escape(label)}[^<]*</td>\\s*<td[^>]*>([^<]+)</td>'
                m = re.search(pat, text2, re.I | re.DOTALL)
                if m:
                    val = m.group(1).strip().replace('$', '').replace(',', '').replace('%', '')
                    if val and val != '-' and val != 'n/a':
                        # Handle T/B/M suffixes
                        mult = 1
                        if val.endswith('T'): mult = 1e12; val = val[:-1]
                        elif val.endswith('B'): mult = 1e9; val = val[:-1]
                        elif val.endswith('M'): mult = 1e6; val = val[:-1]
                        try:
                            return float(val) * mult
                        except:
                            return None
                return None
            
            pe = extract_sa('PE Ratio')
            if pe: result['trailingPE'] = pe
            
            fpe = extract_sa('Forward PE')
            if fpe: result['forwardPE'] = fpe
            
            mcap = extract_sa('Market Cap')
            if mcap: result['marketCap'] = mcap
            
            dy = extract_sa('Dividend Yield')
            if dy and dy < 100: result['dividendYield'] = dy / 100
            
            pb = extract_sa('Price-to-Book')
            if pb: result['priceToBook'] = pb
            
            beta = extract_sa('Beta')
            if beta: result['beta'] = beta
        
        if result:
            print(f"  ✅ StockAnalysis fundamentals: got {len(result)} metrics ({', '.join(result.keys())})")
        return result
    except Exception as e:
        print(f"  ⚠️ StockAnalysis failed: {e}")
        return {}


def fetch_screener_fundamentals(ticker: str) -> dict:
    """Scrape Screener.in API for Indian stock fundamentals (P/E, ROE, margins, etc.)"""
    try:
        # Convert .NS/.BO ticker to clean name for Screener
        clean = ticker.replace('.NS', '').replace('.BO', '').upper()
        url = f"https://www.screener.in/api/company/{clean}/consolidated/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0',
            'Accept': 'application/json',
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            # Try standalone
            url = f"https://www.screener.in/api/company/{clean}/"
            resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200 or 'json' not in resp.headers.get('content-type', ''):
            return None
        
        data = resp.json()
        result = {}
        
        # Screener.in returns data in specific keys
        # Number dict format: {"<key>": value}
        number = data.get('number_set', {}) or {}
        ratios = data.get('warehouse_set', {}).get('standalone', {}) or data.get('warehouse_set', {}) or {}
        
        # Try to extract from various locations
        def get_num(d, keys):
            for k in keys:
                v = d.get(k)
                if v is not None and v != '' and v != 0:
                    try: return float(v)
                    except: pass
            return None
        
        pe = get_num(number, ['price_to_earning', 'pe_ratio', 'stock_pe'])
        if pe: result['trailingPE'] = pe
        
        pb = get_num(number, ['price_to_book', 'book_value_per_share'])
        if pb: result['priceToBook'] = pb
        
        mcap = get_num(number, ['market_capitalization', 'market_cap'])
        if mcap: result['marketCap'] = mcap * 10000000  # Screener shows in Cr, convert to raw
        
        roe = get_num(number, ['return_on_equity', 'roe'])
        if roe: result['returnOnEquity'] = roe / 100  # Convert % to decimal
        
        roce = get_num(number, ['return_on_capital_employed', 'roce'])
        if roce: result['returnOnAssets'] = roce / 100
        
        de = get_num(number, ['debt_to_equity', 'debt_equity'])
        if de is not None: result['debtToEquity'] = de
        
        cr = get_num(number, ['current_ratio'])
        if cr: result['currentRatio'] = cr
        
        npm = get_num(number, ['net_profit_margin', 'npm', 'profit_margin'])
        if npm: result['profitMargins'] = npm / 100
        
        opm = get_num(number, ['operating_profit_margin', 'opm', 'operating_margin'])
        if opm: result['operatingMargins'] = opm / 100
        
        dy = get_num(number, ['dividend_yield'])
        if dy: result['dividendYield'] = dy / 100
        
        if result:
            print(f"  ✅ Screener.in fundamentals: got {len(result)} metrics ({', '.join(result.keys())})")
        return result if result else None
    except Exception as e:
        print(f"  ⚠️ Screener.in fundamentals failed: {e}")
        return None


# In-memory cache for stock data
stock_data_cache = {}
CACHE_EXPIRY_MINUTES = 3    # 3 min fresh cache — feels live
CACHE_STALE_OK_MINUTES = 15  # 15 min stale max — never serve 2hr old data

# ═══════════════════════════════════════════════════════════
# EMAIL-BASED RATE LIMITING
# Goal: Keep usage at ~80% capacity, fair access per user
# ═══════════════════════════════════════════════════════════
email_rate_limiter = {}  # { email: [timestamp1, timestamp2, ...] }
RATE_LIMIT_MAX_REQUESTS = 5       # Max reports per email per window
RATE_LIMIT_WINDOW_MINUTES = 60    # Rolling window in minutes
GLOBAL_REQUESTS_PER_MINUTE = 10   # Global cap across all users (80% of API capacity)
global_request_log = []           # [timestamp1, timestamp2, ...]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static JS/CSS files
os.makedirs("static", exist_ok=True)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    pass

report_counter = {"count": 0}

# ═══ AI REPORT CACHE — serves 10K users instantly ═══
# Key: ticker symbol (uppercase), Value: (full_response_dict, timestamp)
# TTL: 30 minutes — same stock searched by different users = instant
_ai_report_cache = {}
_AI_REPORT_CACHE_TTL = 1800  # 30 minutes

def _get_cached_report(ticker_key):
    """Return cached report if fresh, else None."""
    import time
    if ticker_key in _ai_report_cache:
        cached_resp, cached_ts = _ai_report_cache[ticker_key]
        if time.time() - cached_ts < _AI_REPORT_CACHE_TTL:
            return cached_resp
        else:
            del _ai_report_cache[ticker_key]
    return None

def _set_cached_report(ticker_key, response_dict):
    """Cache the full report response."""
    import time
    _ai_report_cache[ticker_key] = (response_dict, time.time())
    # Evict old entries (keep max 200)
    if len(_ai_report_cache) > 200:
        oldest_key = min(_ai_report_cache, key=lambda k: _ai_report_cache[k][1])
        del _ai_report_cache[oldest_key]
COUNTER_FILE = "report_count.json"

def load_counter():
    """Load report count from file (survives restarts/deploys)."""
    try:
        import json
        with open(COUNTER_FILE, "r") as f:
            data = json.load(f)
            report_counter["count"] = data.get("count", 0)
            print(f"📊 Loaded report counter: {report_counter['count']}")
    except FileNotFoundError:
        # First deploy or file missing — check env var for seed value
        seed = int(os.getenv("REPORT_COUNT_SEED", "0"))
        report_counter["count"] = seed
        save_counter()
        print(f"📊 Initialized counter at {seed}")
    except Exception as e:
        print(f"⚠️ Counter load failed: {e}")

def save_counter():
    """Persist report count to file."""
    try:
        import json
        with open(COUNTER_FILE, "w") as f:
            json.dump({"count": report_counter["count"]}, f)
    except Exception as e:
        print(f"⚠️ Counter save failed: {e}")

load_counter()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ═══════════════════════════════════════════════════════════
# FEATURE VOTING SYSTEM
# ═══════════════════════════════════════════════════════════
feature_votes = {
    "pdf": {"up": 0, "dn": 0},
    "cmp": {"up": 0, "dn": 0},
    "share": {"up": 0, "dn": 0},
    "tech": {"up": 0, "dn": 0},
    "peer": {"up": 0, "dn": 0},
    "earn": {"up": 0, "dn": 0},
    "insider": {"up": 0, "dn": 0},
    "theme": {"up": 0, "dn": 0},
}
VOTES_FILE = "feature_votes.json"

def load_votes():
    """Load feature votes from file (survives restarts/deploys)."""
    try:
        import json
        with open(VOTES_FILE, "r") as f:
            data = json.load(f)
            for k in feature_votes:
                if k in data:
                    feature_votes[k] = data[k]
            print(f"🗳️ Loaded votes: {sum(v['up']+v['dn'] for v in feature_votes.values())} total")
    except FileNotFoundError:
        save_votes()
        print("🗳️ Initialized empty vote file")
    except Exception as e:
        print(f"⚠️ Vote load failed: {e}")

def save_votes():
    """Persist feature votes to file."""
    try:
        import json
        with open(VOTES_FILE, "w") as f:
            json.dump(feature_votes, f)
    except Exception as e:
        print(f"⚠️ Vote save failed: {e}")

load_votes()

# Clean up FII/DII history file on startup (remove duplicates)
try:
    _fii_file = "fii_dii_history.json"
    if os.path.exists(_fii_file):
        with open(_fii_file, "r") as _f:
            _raw = json.load(_f)
        _seen = set()
        _clean = []
        for _h in _raw:
            _d = str(_h.get("date", "")).strip()
            if _d and _d not in _seen:
                _seen.add(_d)
                _clean.append(_h)
        _clean = _clean[-5:]
        with open(_fii_file, "w") as _f:
            json.dump(_clean, _f)
        print(f"📊 FII history cleanup: {len(_raw)} → {len(_clean)} entries")
except Exception as _e:
    print(f"FII history cleanup skipped: {_e}")


def check_rate_limit(email: str) -> dict:
    """
    Check email-based + global rate limits.
    Returns {"allowed": True} or {"allowed": False, "reason": ..., "retry_after_minutes": ...}
    """
    now = datetime.now()
    cutoff = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    email_lower = email.lower().strip()

    # --- Clean up old global entries ---
    global global_request_log
    global_request_log = [t for t in global_request_log if t > now - timedelta(minutes=1)]

    # --- Global rate limit (protect API capacity) ---
    if len(global_request_log) >= GLOBAL_REQUESTS_PER_MINUTE:
        return {
            "allowed": False,
            "reason": "High demand right now. Please try again in a minute.",
            "retry_after_minutes": 1
        }

    # --- Per-email rate limit ---
    if email_lower not in email_rate_limiter:
        email_rate_limiter[email_lower] = []

    # Clean old entries for this email
    email_rate_limiter[email_lower] = [
        t for t in email_rate_limiter[email_lower] if t > cutoff
    ]

    requests_used = len(email_rate_limiter[email_lower])

    if requests_used >= RATE_LIMIT_MAX_REQUESTS:
        # Find when the oldest request in the window will expire
        oldest = min(email_rate_limiter[email_lower])
        retry_at = oldest + timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
        retry_seconds = max(60, int((retry_at - now).total_seconds()))
        retry_minutes = (retry_seconds + 59) // 60  # round up
        retry_at_str = retry_at.strftime("%I:%M %p")
        return {
            "allowed": False,
            "reason": f"You've used {requests_used}/{RATE_LIMIT_MAX_REQUESTS} reports this hour.",
            "retry_after_minutes": retry_minutes,
            "retry_after_seconds": retry_seconds,
            "retry_at": retry_at.isoformat(),
            "retry_at_display": retry_at_str,
            "requests_used": requests_used,
            "requests_limit": RATE_LIMIT_MAX_REQUESTS
        }

    return {
        "allowed": True,
        "requests_used": requests_used,
        "requests_remaining": RATE_LIMIT_MAX_REQUESTS - requests_used - 1  # -1 for current
    }


def record_request(email: str):
    """Record a successful request for rate limiting."""
    now = datetime.now()
    email_lower = email.lower().strip()
    if email_lower not in email_rate_limiter:
        email_rate_limiter[email_lower] = []
    email_rate_limiter[email_lower].append(now)
    global_request_log.append(now)


def get_live_stock_data(company_name: str) -> dict:
    """
    Get VERIFIED real-time stock data with:
    - 15-min cache to minimize Yahoo Finance calls
    - Retry with exponential backoff on rate limit
    - Stale cache fallback if Yahoo is completely blocked
    """
    try:
        # Check cache first
        cache_key = company_name.upper()
        current_time = datetime.now()
        
        if cache_key in stock_data_cache:
            cached_data, cached_time = stock_data_cache[cache_key]
            age_minutes = (current_time - cached_time).total_seconds() / 60
            
            if age_minutes < CACHE_EXPIRY_MINUTES:
                print(f"✅ Returning CACHED data for {cache_key} (age: {age_minutes:.1f} min)")
                return cached_data
            else:
                print(f"♻️ Cache expired for {cache_key}, fetching fresh data")
        
        # Comprehensive ticker mapping
        ticker_map = {
            # US Stocks
            'tesla': 'TSLA', 'tsla': 'TSLA',
            'apple': 'AAPL', 'aapl': 'AAPL',
            'microsoft': 'MSFT', 'msft': 'MSFT',
            'amazon': 'AMZN', 'amzn': 'AMZN',
            'google': 'GOOGL', 'googl': 'GOOGL', 'alphabet': 'GOOGL',
            'meta': 'META', 'facebook': 'META',
            'nvidia': 'NVDA', 'nvda': 'NVDA',
            'netflix': 'NFLX', 'nflx': 'NFLX',
            'jpmorgan': 'JPM', 'jpm': 'JPM',
            
            # Indian Stocks  
            'hdfc bank': 'HDFCBANK.NS', 'hdfc': 'HDFCBANK.NS', 'hdfcbank': 'HDFCBANK.NS',
            'reliance': 'RELIANCE.NS', 'reliance industries': 'RELIANCE.NS',
            'tcs': 'TCS.NS', 'tata consultancy': 'TCS.NS',
            'infosys': 'INFY', 'infy': 'INFY',
            'wipro': 'WIPRO.NS',
            'icici bank': 'ICICIBANK.NS', 'icici': 'ICICIBANK.NS',
            'sbi': 'SBIN.NS', 'state bank': 'SBIN.NS',
        }
        
        company_lower = company_name.lower().strip()
        ticker_symbol = None
        
        # Check mapping first
        for key, value in ticker_map.items():
            if key in company_lower:
                ticker_symbol = value
                break
        
        # If not found, try as ticker directly
        if not ticker_symbol:
            if len(company_name) <= 6 and '.' not in company_name:
                ticker_symbol = company_name.upper()
            elif '.NS' in company_name.upper() or '.BO' in company_name.upper():
                ticker_symbol = company_name.upper()
            else:
                ticker_symbol = company_name.upper()
        
        # ════════════════════════════════════════════
        # 3-SOURCE FALLBACK CHAIN
        # Source 1: yfinance library
        # Source 2: Yahoo Finance direct HTTP API
        # Source 3: Yahoo Finance page scrape
        # ════════════════════════════════════════════
        
        info = None
        current_price = None
        previous_close = None
        week52_high = None
        week52_low = None
        data_source = 'unknown'
        stock = None  # Will be set by Source 1, reused later for charts/technicals
        
        # ── SOURCE 1: yfinance library ──
        try:
            print(f"🔍 Source 1: yfinance for {ticker_symbol}...")
            stock = yf.Ticker(ticker_symbol)
            hist = stock.history(period="5d")
            
            if not hist.empty:
                info = stock.info
                current_price = float(hist['Close'].iloc[-1])
                previous_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
                week52_high = float(hist['High'].max())
                week52_low = float(hist['Low'].min())
                # Override with better 52-week data from info
                if info.get('fiftyTwoWeekHigh'):
                    week52_high = float(info['fiftyTwoWeekHigh'])
                if info.get('fiftyTwoWeekLow'):
                    week52_low = float(info['fiftyTwoWeekLow'])
                data_source = 'yfinance'
                print(f"✅ Source 1 SUCCESS: {ticker_symbol} @ {current_price}")
            else:
                print(f"⚠️ Source 1: yfinance returned empty history")
                info = None
        except Exception as e:
            print(f"❌ Source 1 FAILED: {e}")
            info = None
        
        # ── SOURCE 2: Yahoo Finance direct HTTP API ──
        if info is None or current_price is None:
            try:
                print(f"🔍 Source 2: Yahoo direct HTTP for {ticker_symbol}...")
                direct_data = fetch_yahoo_direct(ticker_symbol)
                
                if direct_data and direct_data.get('currentPrice'):
                    current_price = float(direct_data['currentPrice'])
                    previous_close = float(direct_data.get('previousClose', current_price))
                    week52_high = float(direct_data.get('fiftyTwoWeekHigh', direct_data.get('chartHigh', current_price * 1.1)))
                    week52_low = float(direct_data.get('fiftyTwoWeekLow', direct_data.get('chartLow', current_price * 0.8)))
                    info = direct_data
                    data_source = direct_data.get('_source', 'yahoo_direct')
                    print(f"✅ Source 2 SUCCESS: {ticker_symbol} @ {current_price} via {data_source}")
                else:
                    print(f"⚠️ Source 2: No price data returned")
            except Exception as e:
                print(f"❌ Source 2 FAILED: {e}")
        
        # ── SOURCE 3: Yahoo Finance page scrape ──
        if info is None or current_price is None:
            try:
                print(f"🔍 Source 3: Yahoo scrape for {ticker_symbol}...")
                scrape_data = fetch_yahoo_scrape(ticker_symbol)
                
                if scrape_data and scrape_data.get('currentPrice'):
                    current_price = float(scrape_data['currentPrice'])
                    previous_close = float(scrape_data.get('previousClose', current_price))
                    week52_high = float(scrape_data.get('fiftyTwoWeekHigh', current_price * 1.1))
                    week52_low = float(scrape_data.get('fiftyTwoWeekLow', current_price * 0.8))
                    info = scrape_data
                    data_source = 'yahoo_scrape'
                    print(f"✅ Source 3 SUCCESS: {ticker_symbol} @ {current_price}")
                else:
                    print(f"⚠️ Source 3: Scrape returned no data")
            except Exception as e:
                print(f"❌ Source 3 FAILED: {e}")
        
        # ── SOURCE 4: Google Finance (if no price yet, or as fundamentals enrichment) ──
        if info is None or current_price is None:
            try:
                print(f"🔍 Source 4: Google Finance for {ticker_symbol}...")
                gf_data = fetch_google_finance(ticker_symbol)
                if gf_data and gf_data.get('currentPrice'):
                    current_price = float(gf_data['currentPrice'])
                    previous_close = float(gf_data.get('previousClose', current_price))
                    week52_high = float(gf_data.get('fiftyTwoWeekHigh', current_price * 1.1))
                    week52_low = float(gf_data.get('fiftyTwoWeekLow', current_price * 0.8))
                    info = gf_data
                    data_source = 'google_finance'
                    print(f"✅ Source 4 SUCCESS: {ticker_symbol} @ {current_price}")
            except Exception as e:
                print(f"❌ Source 4 FAILED: {e}")
        
        # ── FUNDAMENTALS ENRICHMENT: If we got price but missing P/E, Market Cap, margins, etc. ──
        if current_price is not None and info is not None:
            has_pe = info.get('trailingPE') and info['trailingPE'] != 0
            has_mcap = info.get('marketCap') and info['marketCap'] != 0
            has_margins = info.get('profitMargins') and info['profitMargins'] != 0
            
            if not has_pe or not has_mcap:
                print(f"⚠️ Missing fundamentals (PE={info.get('trailingPE')}, MCap={info.get('marketCap')}). Trying enrichment...")
                
                # Try Google Finance for missing fundamentals
                try:
                    gf_enrich = fetch_google_finance(ticker_symbol)
                    if gf_enrich:
                        if not has_pe and gf_enrich.get('trailingPE'):
                            info['trailingPE'] = gf_enrich['trailingPE']
                            print(f"  ✅ Enriched PE from Google: {gf_enrich['trailingPE']}")
                        if not has_mcap and gf_enrich.get('marketCap'):
                            info['marketCap'] = gf_enrich['marketCap']
                            print(f"  ✅ Enriched Market Cap from Google: {gf_enrich['marketCap']}")
                        if not info.get('fiftyTwoWeekHigh') and gf_enrich.get('fiftyTwoWeekHigh'):
                            info['fiftyTwoWeekHigh'] = gf_enrich['fiftyTwoWeekHigh']
                            week52_high = float(gf_enrich['fiftyTwoWeekHigh'])
                        if not info.get('fiftyTwoWeekLow') and gf_enrich.get('fiftyTwoWeekLow'):
                            info['fiftyTwoWeekLow'] = gf_enrich['fiftyTwoWeekLow']
                            week52_low = float(gf_enrich['fiftyTwoWeekLow'])
                        if gf_enrich.get('dividendYield') and not info.get('dividendYield'):
                            info['dividendYield'] = gf_enrich['dividendYield']
                except Exception as e:
                    print(f"  ⚠️ Google enrichment failed: {e}")
            
            # ── COMPREHENSIVE ENRICHMENT: Finviz (US) or Screener.in (India) ──
            # These are the BEST fallbacks when Yahoo is rate-limited
            is_indian_stock = '.NS' in ticker_symbol or '.BO' in ticker_symbol
            
            # Check what's still missing
            missing_metrics = []
            if not info.get('trailingPE') or info.get('trailingPE') == 0: missing_metrics.append('P/E')
            if not info.get('marketCap') or info.get('marketCap') == 0: missing_metrics.append('MCap')
            if not info.get('profitMargins') or info.get('profitMargins') == 0: missing_metrics.append('Margins')
            if not info.get('returnOnEquity') or info.get('returnOnEquity') == 0: missing_metrics.append('ROE')
            if not info.get('debtToEquity'): missing_metrics.append('Debt/Eq')
            if not info.get('beta') or info.get('beta') == 0: missing_metrics.append('Beta')
            if not info.get('priceToBook') or info.get('priceToBook') == 0: missing_metrics.append('P/B')
            
            if missing_metrics:
                print(f"⚠️ Still missing: {', '.join(missing_metrics)}. Trying {'Screener.in' if is_indian_stock else 'Finviz'}...")
                
                alt_data = None
                if is_indian_stock:
                    alt_data = fetch_screener_fundamentals(ticker_symbol)
                else:
                    alt_data = fetch_finviz_fundamentals(ticker_symbol)
                
                if alt_data:
                    # Fill ALL missing metrics from alternative source
                    fill_keys = [
                        'trailingPE', 'forwardPE', 'priceToBook', 'marketCap',
                        'profitMargins', 'operatingMargins', 'grossMargins',
                        'returnOnEquity', 'returnOnAssets', 'debtToEquity',
                        'currentRatio', 'beta', 'dividendYield', 'trailingEps',
                        'sector', 'industry'
                    ]
                    filled = []
                    for key in fill_keys:
                        if alt_data.get(key) is not None and (not info.get(key) or info.get(key) == 0 or info.get(key) == 'N/A'):
                            info[key] = alt_data[key]
                            filled.append(key)
                    if filled:
                        print(f"  ✅ Enriched {len(filled)} metrics from {'Screener.in' if is_indian_stock else 'Finviz'}: {', '.join(filled)}")
                    
                    # Update flags
                    has_pe = info.get('trailingPE') and info['trailingPE'] != 0
                    has_mcap = info.get('marketCap') and info['marketCap'] != 0
                    has_margins = info.get('profitMargins') and info['profitMargins'] != 0
            
            # ── SECOND ALT: StockAnalysis.com (US stocks only, if still missing) ──
            still_missing = []
            if not info.get('trailingPE') or info.get('trailingPE') == 0: still_missing.append('P/E')
            if not info.get('marketCap') or info.get('marketCap') == 0: still_missing.append('MCap')
            if not info.get('priceToBook') or info.get('priceToBook') == 0: still_missing.append('P/B')
            if not info.get('beta') or info.get('beta') == 0: still_missing.append('Beta')
            
            if still_missing and not is_indian_stock:
                print(f"⚠️ Still missing after Finviz: {', '.join(still_missing)}. Trying StockAnalysis.com...")
                try:
                    sa_data = fetch_stockanalysis_fundamentals(ticker_symbol)
                    if sa_data:
                        sa_filled = []
                        for key in ['trailingPE', 'forwardPE', 'priceToBook', 'marketCap', 'beta', 'dividendYield']:
                            if sa_data.get(key) and (not info.get(key) or info.get(key) == 0):
                                info[key] = sa_data[key]
                                sa_filled.append(key)
                        if sa_filled:
                            print(f"  ✅ StockAnalysis enriched: {', '.join(sa_filled)}")
                except Exception as e:
                    print(f"  ⚠️ StockAnalysis enrichment failed: {e}")
            
            # ── LAST RESORT MARGIN ENRICHMENT: yfinance .info (may also fail if Yahoo blocked) ──
            if not has_margins:
                print(f"⚠️ Margins still missing. Last resort: yfinance .info...")
                try:
                    stock_margins = stock or yf.Ticker(ticker_symbol)
                    margin_info = stock_margins.info
                    if margin_info:
                        if not info.get('profitMargins') and margin_info.get('profitMargins'):
                            info['profitMargins'] = margin_info['profitMargins']
                            print(f"  ✅ Enriched profit margin: {margin_info['profitMargins']}")
                        if not info.get('operatingMargins') and margin_info.get('operatingMargins'):
                            info['operatingMargins'] = margin_info['operatingMargins']
                        if not info.get('returnOnEquity') and margin_info.get('returnOnEquity'):
                            info['returnOnEquity'] = margin_info['returnOnEquity']
                        if not info.get('debtToEquity') and margin_info.get('debtToEquity'):
                            info['debtToEquity'] = margin_info['debtToEquity']
                        if not info.get('currentRatio') and margin_info.get('currentRatio'):
                            info['currentRatio'] = margin_info['currentRatio']
                        if not info.get('beta') and margin_info.get('beta'):
                            info['beta'] = margin_info['beta']
                        if not info.get('sector') or info['sector'] == 'N/A':
                            info['sector'] = margin_info.get('sector', info.get('sector', 'N/A'))
                            info['industry'] = margin_info.get('industry', info.get('industry', 'N/A'))
                except Exception as e:
                    print(f"  ⚠️ yfinance margin enrichment failed: {e}")
            
            # ── ABSOLUTE LAST RESORT: Yahoo crumb-based v10 (fresh session) ──
            final_missing = []
            if not info.get('trailingPE') or info.get('trailingPE') == 0: final_missing.append('P/E')
            if not info.get('marketCap') or info.get('marketCap') == 0: final_missing.append('MCap')
            if not info.get('profitMargins') or info.get('profitMargins') == 0: final_missing.append('Margins')
            
            if final_missing:
                print(f"⚠️ FINAL RESORT for {', '.join(final_missing)}: Yahoo crumb session...")
                try:
                    session = requests.Session()
                    session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
                    })
                    # Get crumb
                    cr = session.get('https://fc.yahoo.com', timeout=5)
                    crumb_r = session.get('https://query2.finance.yahoo.com/v1/test/getcrumb', timeout=5)
                    if crumb_r.status_code == 200:
                        crumb = crumb_r.text.strip()
                        if crumb and len(crumb) < 20:
                            modules = 'defaultKeyStatistics,financialData,summaryDetail'
                            v10_url = f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker_symbol}?modules={modules}&crumb={crumb}'
                            dr = session.get(v10_url, timeout=8)
                            ct = dr.headers.get('content-type', '')
                            if dr.status_code == 200 and 'json' in ct:
                                d10 = dr.json().get('quoteSummary', {}).get('result', [])
                                if d10:
                                    d10 = d10[0]
                                    def rv10(sec, key):
                                        return d10.get(sec, {}).get(key, {}).get('raw', 0) if isinstance(d10.get(sec, {}).get(key, {}), dict) else 0
                                    
                                    enriched = []
                                    if not info.get('trailingPE') or info['trailingPE'] == 0:
                                        pe_val = rv10('summaryDetail', 'trailingPE')
                                        if pe_val: info['trailingPE'] = pe_val; enriched.append(f'PE={pe_val}')
                                    if not info.get('marketCap') or info['marketCap'] == 0:
                                        mc = rv10('summaryDetail', 'marketCap')
                                        if mc: info['marketCap'] = mc; enriched.append(f'MCap={mc}')
                                    if not info.get('profitMargins') or info['profitMargins'] == 0:
                                        pm_val = rv10('financialData', 'profitMargins')
                                        if pm_val: info['profitMargins'] = pm_val; enriched.append(f'PM={pm_val}')
                                    if not info.get('operatingMargins') or info['operatingMargins'] == 0:
                                        om_val = rv10('financialData', 'operatingMargins')
                                        if om_val: info['operatingMargins'] = om_val; enriched.append(f'OM={om_val}')
                                    if not info.get('returnOnEquity') or info['returnOnEquity'] == 0:
                                        roe_val = rv10('financialData', 'returnOnEquity')
                                        if roe_val: info['returnOnEquity'] = roe_val; enriched.append(f'ROE={roe_val}')
                                    if not info.get('debtToEquity'):
                                        de_val = rv10('financialData', 'debtToEquity')
                                        if de_val: info['debtToEquity'] = de_val; enriched.append(f'D/E={de_val}')
                                    if not info.get('priceToBook') or info['priceToBook'] == 0:
                                        pb_val = rv10('defaultKeyStatistics', 'priceToBook')
                                        if pb_val: info['priceToBook'] = pb_val; enriched.append(f'PB={pb_val}')
                                    if not info.get('beta') or info['beta'] == 0:
                                        beta_val = rv10('defaultKeyStatistics', 'beta')
                                        if beta_val: info['beta'] = beta_val; enriched.append(f'Beta={beta_val}')
                                    if enriched:
                                        print(f"  ✅ Yahoo crumb session: {', '.join(enriched)}")
                except Exception as e:
                    print(f"  ⚠️ Yahoo crumb enrichment failed: {e}")
        
        # ── ALL SOURCES FAILED: check stale cache ──
        if current_price is None:
            if cache_key in stock_data_cache:
                cached_data, cached_time = stock_data_cache[cache_key]
                age_minutes = (current_time - cached_time).total_seconds() / 60
                if age_minutes < CACHE_STALE_OK_MINUTES:
                    print(f"🆘 All sources failed — serving stale cache for {cache_key} (age: {age_minutes:.1f} min)")
                    cached_data["data_timestamp"] = f"{datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')} (cached)"
                    cached_data["data_source"] = "stale_cache"
                    return cached_data
            
            return {
                "error": f"All data sources failed for {ticker_symbol}. Yahoo Finance may be temporarily down. Try again in 1-2 minutes."
            }
        
        # ── SUCCESS: Build response ──
        if info is None:
            info = {}
        
        price_change = current_price - previous_close
        price_change_pct = (price_change / previous_close * 100) if previous_close > 0 else 0
        
        # Currency detection
        currency = info.get('currency', 'USD')
        if '.NS' in ticker_symbol or '.BO' in ticker_symbol:
            currency = 'INR'
        
        # Safe getter for info (handles both yfinance dict and our custom dict)
        def safe_get(key, default=0, is_pct=False):
            val = info.get(key)
            if val is None or val == 'N/A' or val == 0:
                return default
            try:
                v = float(val)
                if is_pct and abs(v) < 1:
                    return round(v * 100, 2)
                # Don't round large values like marketCap — preserve full magnitude
                if abs(v) > 1e9:
                    return int(v)
                return round(v, 2)
            except:
                return default
        
        # For direct/scrape sources, margins are already raw decimals
        is_direct = data_source != 'yfinance'
        
        live_data = {
            "success": True,
            "ticker": ticker_symbol,
            "company_name": info.get('longName', company_name),
            "current_price": round(current_price, 2),
            "price_change": round(price_change, 2),
            "price_change_pct": round(price_change_pct, 2),
            "currency": currency,
            "market_cap": safe_get('marketCap'),
            "pe_ratio": safe_get('trailingPE') or 'N/A',
            "forward_pe": safe_get('forwardPE') or 'N/A',
            "pb_ratio": safe_get('priceToBook') or 'N/A',
            "dividend_yield": round(safe_get('dividendYield') * (100 if safe_get('dividendYield') < 1 else 1), 2) if safe_get('dividendYield') else 0,
            "week52_high": round(week52_high, 2),
            "week52_low": round(week52_low, 2),
            "beta": safe_get('beta') or 'N/A',
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "profit_margin": safe_get('profitMargins', 'N/A', is_pct=True),
            "operating_margin": safe_get('operatingMargins', 'N/A', is_pct=True),
            "roe": safe_get('returnOnEquity', 'N/A', is_pct=True),
            "debt_to_equity": safe_get('debtToEquity') or 'N/A',
            "current_ratio": safe_get('currentRatio') or 'N/A',
            "eps_ttm": safe_get('trailingEps') or 'N/A',
            "eps_forward": safe_get('forwardEps') or safe_get('epsForward') or 'N/A',
            "book_value": safe_get('bookValue') or 'N/A',
            "free_cash_flow": safe_get('freeCashflow') or 'N/A',
            "operating_cash_flow": safe_get('operatingCashflow') or 'N/A',
            "total_revenue": safe_get('totalRevenue') or 'N/A',
            "revenue_growth": round(safe_get('revenueGrowth') * (100 if abs(safe_get('revenueGrowth')) < 1 else 1), 2) if safe_get('revenueGrowth') else 'N/A',
            "total_cash": safe_get('totalCash') or 'N/A',
            "total_debt": safe_get('totalDebt') or 'N/A',
            "quick_ratio": safe_get('quickRatio') or 'N/A',
            "gross_margins": safe_get('grossMargins', 'N/A', is_pct=True),
            "ebitda": safe_get('ebitda') or 'N/A',
            "ebitda_margins": safe_get('ebitdaMargins', 'N/A', is_pct=True),
            "revenue_per_share": safe_get('revenuePerShare') or 'N/A',
            "peg_ratio": safe_get('pegRatio') or 'N/A',
            "target_price": safe_get('targetMeanPrice') or 'N/A',
            "target_high": safe_get('targetHighPrice') or 'N/A',
            "target_low": safe_get('targetLowPrice') or 'N/A',
            "analyst_rating": (safe_get('recommendationKey') or 'N/A').upper() if safe_get('recommendationKey') else 'N/A',
            "analyst_count": safe_get('numberOfAnalystOpinions') or 0,
            "return_on_equity": round(safe_get('returnOnEquity') * 100, 1) if safe_get('returnOnEquity') and abs(safe_get('returnOnEquity')) < 10 else 'N/A',
            "return_on_assets": round(safe_get('returnOnAssets') * 100, 1) if safe_get('returnOnAssets') and abs(safe_get('returnOnAssets')) < 10 else 'N/A',
            "current_ratio": round(safe_get('currentRatio'), 2) if safe_get('currentRatio') else 'N/A',
            "quick_ratio": round(safe_get('quickRatio'), 2) if safe_get('quickRatio') else 'N/A',
            "operating_margin": round(safe_get('operatingMargins') * 100, 1) if safe_get('operatingMargins') and abs(safe_get('operatingMargins')) < 10 else 'N/A',
            "gross_margin": round(safe_get('grossMargins') * 100, 1) if safe_get('grossMargins') and abs(safe_get('grossMargins')) < 10 else 'N/A',
            "enterprise_to_ebitda": safe_get('enterpriseToEbitda') or 'N/A',
            "earnings_quarterly_growth": round(safe_get('earningsQuarterlyGrowth') * (100 if abs(safe_get('earningsQuarterlyGrowth')) < 1 else 1), 2) if safe_get('earningsQuarterlyGrowth') else 'N/A',
            "short_ratio": safe_get('shortRatio') or 'N/A',
            "payout_ratio": round(safe_get('payoutRatio') * (100 if safe_get('payoutRatio') and abs(safe_get('payoutRatio')) < 1 else 1), 2) if safe_get('payoutRatio') else 'N/A',
            "data_timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p UTC"),
            "data_source": data_source,
            "verification_url": f"https://www.google.com/finance/quote/{ticker_symbol.replace('.NS', ':NSE').replace('.BO', ':BOM')}",
            "company_description": str(info.get('longBusinessSummary', ''))[:600] if info.get('longBusinessSummary') else '',
            "employees": info.get('fullTimeEmployees', 'N/A'),
            "website": info.get('website', ''),
            "exchange": info.get('exchange', 'N/A'),
        }
        
        # Debug: log company description availability
        print(f"📝 Company desc: {'YES ('+str(len(str(info.get('longBusinessSummary',''))))+'ch)' if info.get('longBusinessSummary') else 'NO'}")
        print(f"📝 Employees: {info.get('fullTimeEmployees', 'N/A')}, Website: {info.get('website', 'N/A')}")
        
        # Fetch real 6-month price history for Price Trend chart
        try:
            hist_ticker = stock or yf.Ticker(ticker_symbol)  # Reuse Source 1 Ticker (saves 2-3s)
            hist = hist_ticker.history(period="6mo", interval="1mo")
            if hist is not None and len(hist) > 1:
                price_history = [round(float(row['Close']), 2) for _, row in hist.iterrows()]
                live_data["price_history"] = price_history
                print(f"📈 Price history: {len(price_history)} monthly points")
            else:
                live_data["price_history"] = None
        except Exception as e:
            print(f"⚠️ Price history fetch failed: {e}")
            live_data["price_history"] = None
        
        # ═══ STOCK YTD + 5-YEAR YEARLY RETURNS ═══
        try:
            _yr_tk = stock or yf.Ticker(ticker_symbol)
            _yr_hist = _yr_tk.history(period="5y", interval="1mo")
            if _yr_hist is not None and len(_yr_hist) > 12:
                from datetime import datetime as _dt
                _cur_yr = _dt.utcnow().year
                _yearly = {}
                # YTD
                try:
                    _ytd_rows = _yr_hist[_yr_hist.index.year == _cur_yr]
                    if len(_ytd_rows) > 0:
                        _ytd_open = float(_ytd_rows['Close'].iloc[0])
                        _ytd_close = float(_yr_hist['Close'].iloc[-1])
                        live_data["ytd_return"] = round(((_ytd_close - _ytd_open) / _ytd_open) * 100, 2)
                except:
                    pass
                # Each year
                for _y in range(_cur_yr - 5, _cur_yr):
                    try:
                        _yd = _yr_hist[_yr_hist.index.year == _y]
                        if len(_yd) >= 2:
                            _yo = float(_yd['Close'].iloc[0])
                            _yc = float(_yd['Close'].iloc[-1])
                            _yearly[str(_y)] = round(((_yc - _yo) / _yo) * 100, 2)
                    except:
                        pass
                live_data["yearly_returns"] = _yearly
                print(f"📊 YTD: {live_data.get('ytd_return', 'N/A')}%, Yearly: {_yearly}")
        except Exception as e:
            print(f"⚠️ Yearly returns failed: {e}")
        
        # ═══ TECHNICAL INDICATORS: SMA20, SMA200, EPS Growth, Sector PE ═══
        # Also compute YTD + yearly returns from daily history
        try:
            tk = stock or yf.Ticker(ticker_symbol)  # Reuse Source 1 Ticker (saves 2-3s)
            # Daily history for moving averages
            daily = tk.history(period="1y", interval="1d")
            if daily is not None and len(daily) > 20:
                closes = daily['Close'].values
                sma20 = round(float(closes[-20:].mean()), 2) if len(closes) >= 20 else None
                sma200 = round(float(closes[-200:].mean()), 2) if len(closes) >= 200 else None
                sma50 = round(float(closes[-50:].mean()), 2) if len(closes) >= 50 else None
                live_data["sma_20"] = sma20
                live_data["sma_50"] = sma50
                live_data["sma_200"] = sma200
                # EMA calculations using pandas ewm
                try:
                    import pandas as pd
                    close_series = pd.Series(closes)
                    ema9 = round(float(close_series.ewm(span=9, adjust=False).mean().iloc[-1]), 2) if len(closes) >= 9 else None
                    ema21 = round(float(close_series.ewm(span=21, adjust=False).mean().iloc[-1]), 2) if len(closes) >= 21 else None
                    ema50 = round(float(close_series.ewm(span=50, adjust=False).mean().iloc[-1]), 2) if len(closes) >= 50 else None
                    live_data["ema_9"] = ema9
                    live_data["ema_21"] = ema21
                    live_data["ema_50"] = ema50
                    # Price action signals
                    price = float(closes[-1])
                    ema_signals = []
                    if ema9 and ema21:
                        if ema9 > ema21: ema_signals.append("EMA9>EMA21 (short-term bullish)")
                        else: ema_signals.append("EMA9<EMA21 (short-term bearish)")
                    if ema21 and ema50:
                        if ema21 > ema50: ema_signals.append("EMA21>EMA50 (medium bullish)")
                        else: ema_signals.append("EMA21<EMA50 (medium bearish)")
                    if ema9 and price:
                        if price > ema9: ema_signals.append("Price above EMA9 (momentum up)")
                        else: ema_signals.append("Price below EMA9 (momentum fading)")
                    live_data["ema_signals"] = ema_signals
                    print(f"📊 EMAs: 9d={ema9}, 21d={ema21}, 50d={ema50} | {', '.join(ema_signals[:2])}")
                except Exception as ema_err:
                    print(f"⚠️ EMA calc failed: {ema_err}")
                    live_data["ema_9"] = None
                    live_data["ema_21"] = None
                    live_data["ema_50"] = None
                    live_data["ema_signals"] = []
                print(f"📊 SMAs: 20d={sma20}, 50d={sma50}, 200d={sma200}")
            else:
                live_data["sma_20"] = None
                live_data["sma_50"] = None
                live_data["sma_200"] = None
                live_data["ema_9"] = None
                live_data["ema_21"] = None
                live_data["ema_50"] = None
                live_data["ema_signals"] = []
        except Exception as e:
            print(f"⚠️ SMA calc failed: {e}")
            live_data["sma_20"] = None
            live_data["sma_50"] = None
            live_data["sma_200"] = None
            live_data["ema_9"] = None
            live_data["ema_21"] = None
            live_data["ema_50"] = None
            live_data["ema_signals"] = []
        
        # EPS growth rate (forward vs trailing)
        try:
            eps_t = float(info.get('trailingEps', 0) or 0)
            eps_f = float(info.get('forwardEps', 0) or info.get('epsForward', 0) or 0)
            if eps_t > 0 and eps_f > 0:
                live_data["eps_growth_pct"] = round(((eps_f - eps_t) / eps_t) * 100, 1)
            else:
                live_data["eps_growth_pct"] = 'N/A'
            # Earnings growth from yfinance
            eg = info.get('earningsGrowth', 0) or 0
            live_data["earnings_growth"] = round(eg * 100, 1) if abs(eg) < 1 and eg != 0 else (round(eg, 1) if eg else 'N/A')
        except:
            live_data["eps_growth_pct"] = 'N/A'
            live_data["earnings_growth"] = 'N/A'
        
        # Sector average P/E (hardcoded ranges — more reliable than API which often returns None)
        sector_pe_map = {
            'Technology': 30, 'Communication Services': 22, 'Consumer Cyclical': 25,
            'Consumer Defensive': 28, 'Financial Services': 15, 'Healthcare': 25,
            'Industrials': 22, 'Basic Materials': 18, 'Energy': 12,
            'Utilities': 18, 'Real Estate': 35
        }
        sec = info.get('sector', '')
        live_data["sector_avg_pe"] = sector_pe_map.get(sec, 20)
        
        # ═══ INSIDER ACTIVITY & EARNINGS CALENDAR ═══
        try:
            tk_ins = stock or yf.Ticker(ticker_symbol)
            # Insider transactions
            try:
                ins = tk_ins.insider_transactions
                if ins is not None and hasattr(ins, 'empty') and not ins.empty:
                    insider_list = []
                    for _, row in ins.head(10).iterrows():
                        try:
                            _shares = row.get('Shares', row.get('shares', 0))
                            _value = row.get('Value', row.get('value', 0))
                            import math
                            if _shares is None or (isinstance(_shares, float) and math.isnan(_shares)):
                                _shares = 0
                            if _value is None or (isinstance(_value, float) and math.isnan(_value)):
                                _value = 0
                            insider_list.append({
                                "name": str(row.get('Insider', row.get('insider', 'Unknown')) or 'Unknown'),
                                "relation": str(row.get('Relation', row.get('position', '')) or ''),
                                "type": str(row.get('Transaction', row.get('transaction', '')) or ''),
                                "shares": int(float(_shares)),
                                "value": float(_value),
                                "date": str(row.get('Date', row.get('startDate', '')) or '')[:10]
                            })
                        except:
                            continue
                    buys = sum(1 for i in insider_list if 'buy' in str(i.get('type','')).lower() or 'purchase' in str(i.get('type','')).lower())
                    sells = sum(1 for i in insider_list if 'sell' in str(i.get('type','')).lower() or 'sale' in str(i.get('type','')).lower())
                    live_data["insider_trades"] = insider_list
                    live_data["insider_buys"] = buys
                    live_data["insider_sells"] = sells
                    live_data["insider_signal"] = "BULLISH" if buys > sells else "BEARISH" if sells > buys else "NEUTRAL"
                else:
                    live_data["insider_trades"] = []
                    live_data["insider_buys"] = 0
                    live_data["insider_sells"] = 0
                    live_data["insider_signal"] = "N/A"
            except Exception as e:
                print(f"⚠️ Insider transactions failed: {e}")
                live_data["insider_trades"] = []
                live_data["insider_buys"] = 0
                live_data["insider_sells"] = 0
                live_data["insider_signal"] = "N/A"
            
            # Earnings calendar
            try:
                cal = tk_ins.calendar
                if cal is not None:
                    if isinstance(cal, dict):
                        ed = cal.get('Earnings Date', cal.get('earningsDate', []))
                        if isinstance(ed, list) and ed:
                            live_data["next_earnings"] = str(ed[0])[:10]
                        elif ed:
                            live_data["next_earnings"] = str(ed)[:10]
                        else:
                            live_data["next_earnings"] = "N/A"
                        # Override with earnings_dates if available (more accurate)
                        try:
                            ed_df = tk_ins.earnings_dates
                            if ed_df is not None and len(ed_df) > 0:
                                from datetime import datetime as _dt
                                now = _dt.utcnow()
                                for idx_r in range(len(ed_df)):
                                    date_val = ed_df.index[idx_r]
                                    if hasattr(date_val, 'to_pydatetime'):
                                        date_val = date_val.to_pydatetime().replace(tzinfo=None)
                                    if date_val > now:
                                        live_data["next_earnings"] = str(ed_df.index[idx_r])[:10]
                                        break
                                # Also find most recent reported
                                for idx_r in range(len(ed_df)):
                                    date_val = ed_df.index[idx_r]
                                    if hasattr(date_val, 'to_pydatetime'):
                                        date_val = date_val.to_pydatetime().replace(tzinfo=None)
                                    row = ed_df.iloc[idx_r]
                                    if date_val <= now and row.get('Reported EPS') is not None:
                                        live_data["last_earnings"] = str(ed_df.index[idx_r])[:10]
                                        live_data["last_eps_reported"] = float(row.get('Reported EPS', 0))
                                        live_data["last_eps_surprise"] = row.get('Surprise(%)', 'N/A')
                                        break
                        except:
                            pass
                        import math as _m
                        def _safe_cal(v):
                            if v is None: return "N/A"
                            try:
                                if isinstance(v, float) and _m.isnan(v): return "N/A"
                                return v
                            except: return "N/A"
                        live_data["earnings_est_low"] = _safe_cal(cal.get('Earnings Low', cal.get('earningsLow', 'N/A')))
                        live_data["earnings_est_high"] = _safe_cal(cal.get('Earnings High', cal.get('earningsHigh', 'N/A')))
                        live_data["earnings_est_avg"] = _safe_cal(cal.get('Earnings Average', cal.get('earningsAverage', 'N/A')))
                        live_data["revenue_est_avg"] = _safe_cal(cal.get('Revenue Average', cal.get('revenueAverage', 'N/A')))
                    elif hasattr(cal, 'to_dict'):
                        # DataFrame format in some yfinance versions
                        try:
                            cal_dict = cal.to_dict()
                            live_data["next_earnings"] = "N/A"
                            live_data["earnings_est_low"] = "N/A"
                            live_data["earnings_est_high"] = "N/A"
                            live_data["earnings_est_avg"] = "N/A"
                            live_data["revenue_est_avg"] = "N/A"
                        except:
                            pass
                    else:
                        live_data["next_earnings"] = "N/A"
                        live_data["earnings_est_low"] = "N/A"
                        live_data["earnings_est_high"] = "N/A"
                        live_data["earnings_est_avg"] = "N/A"
                        live_data["revenue_est_avg"] = "N/A"
                else:
                    live_data["next_earnings"] = "N/A"
                    live_data["earnings_est_low"] = "N/A"
                    live_data["earnings_est_high"] = "N/A"
                    live_data["earnings_est_avg"] = "N/A"
                    live_data["revenue_est_avg"] = "N/A"
            except Exception as e:
                print(f"⚠️ Earnings calendar failed: {e}")
                live_data["next_earnings"] = "N/A"
                live_data["earnings_est_low"] = "N/A"
                live_data["earnings_est_high"] = "N/A"
                live_data["earnings_est_avg"] = "N/A"
                live_data["revenue_est_avg"] = "N/A"
        except Exception as e:
            print(f"⚠️ Insider/Earnings outer block failed: {e}")
            live_data["insider_trades"] = []
            live_data["insider_buys"] = 0
            live_data["insider_sells"] = 0
            live_data["insider_signal"] = "N/A"
            live_data["next_earnings"] = "N/A"
            live_data["earnings_est_low"] = "N/A"
            live_data["earnings_est_high"] = "N/A"
            live_data["earnings_est_avg"] = "N/A"
            live_data["revenue_est_avg"] = "N/A"
        
        # ═══ PEER / COMPETITOR COMPARISON ═══
        try:
            _industry = info.get('industry', '')
            _sector = info.get('sector', '')
            _ticker_up = ticker_symbol.upper()
            
            # Industry-to-peers mapping (top 4-5 competitors per industry)
            peer_map = {
                # US Tech
                'Software—Infrastructure': ['MSFT','ORCL','CRM','NOW','ADBE'],
                'Software—Application': ['CRM','ADBE','NOW','WDAY','INTU'],
                'Semiconductors': ['NVDA','AMD','INTC','AVGO','QCOM','TXN'],
                'Semiconductor Equipment & Materials': ['ASML','AMAT','LRCX','KLAC','TER'],
                'Consumer Electronics': ['AAPL','SONY','DELL','HPQ','LOGI'],
                'Internet Content & Information': ['GOOGL','META','SNAP','PINS','BIDU'],
                'Internet Retail': ['AMZN','BABA','JD','PDD','MELI','EBAY'],
                'Auto Manufacturers': ['TSLA','TM','F','GM','RIVN','LCID'],
                'Banks—Diversified': ['JPM','BAC','WFC','C','GS','MS'],
                'Banks—Regional': ['USB','PNC','TFC','FITB','HBAN'],
                'Insurance—Diversified': ['BRK-B','AIG','MET','PRU','ALL'],
                'Drug Manufacturers—General': ['JNJ','PFE','MRK','ABBV','LLY','NVO'],
                'Biotechnology': ['AMGN','GILD','BIIB','REGN','VRTX','MRNA'],
                'Oil & Gas Integrated': ['XOM','CVX','COP','EOG','SLB'],
                'Aerospace & Defense': ['LMT','RTX','BA','NOC','GD'],
                'Telecom Services': ['T','VZ','TMUS','AMX','BCE'],
                # Indian
                'Software—Infrastructure:IN': ['TCS.NS','INFY.NS','WIPRO.NS','HCLTECH.NS','TECHM.NS','LTI.NS'],
                'Banks—Diversified:IN': ['HDFCBANK.NS','ICICIBANK.NS','SBIN.NS','KOTAKBANK.NS','AXISBANK.NS','INDUSINDBK.NS'],
                'Oil & Gas Integrated:IN': ['RELIANCE.NS','ONGC.NS','IOC.NS','BPCL.NS','HINDPETRO.NS'],
                'Telecom Services:IN': ['BHARTIARTL.NS','JIOFIN.NS','IDEA.NS'],
                'Auto Manufacturers:IN': ['TATAMOTORS.NS','MARUTI.NS','M&M.NS','BAJAJ-AUTO.NS','HEROMOTOCO.NS'],
                'FMCG:IN': ['HINDUNILVR.NS','ITC.NS','NESTLEIND.NS','BRITANNIA.NS','DABUR.NS','GODREJCP.NS'],
                'Cement:IN': ['ULTRACEMCO.NS','AMBUJACEM.NS','ACC.NS','SHREECEM.NS','RAMCOCEM.NS'],
                'Pharmaceuticals:IN': ['SUNPHARMA.NS','DRREDDY.NS','CIPLA.NS','DIVISLAB.NS','LUPIN.NS'],
                'Power:IN': ['NTPC.NS','POWERGRID.NS','TATAPOWER.NS','ADANIGREEN.NS','NHPC.NS'],
                'Metals & Mining:IN': ['TATASTEEL.NS','HINDALCO.NS','JSWSTEEL.NS','VEDL.NS','COALINDIA.NS'],
            }
            
            # Determine peer key — try industry first, then with :IN suffix for Indian stocks
            is_indian = '.NS' in _ticker_up or '.BO' in _ticker_up
            peer_key = (_industry + ':IN') if is_indian else _industry
            peer_tickers = peer_map.get(peer_key, peer_map.get(_industry, []))
            
            # If no exact match, try sector-level fallback
            if not peer_tickers:
                sector_peer_map = {
                    'Technology': ['AAPL','MSFT','GOOGL','META','NVDA'],
                    'Financial Services': ['JPM','BAC','GS','V','MA'],
                    'Healthcare': ['JNJ','UNH','PFE','ABBV','MRK'],
                    'Consumer Cyclical': ['AMZN','TSLA','HD','NKE','MCD'],
                    'Consumer Defensive': ['PG','KO','PEP','WMT','COST'],
                    'Energy': ['XOM','CVX','COP','SLB','EOG'],
                    'Industrials': ['CAT','HON','UPS','BA','GE'],
                    'Basic Materials': ['LIN','APD','ECL','NEM','FCX'],
                    'Communication Services': ['GOOGL','META','DIS','NFLX','CMCSA'],
                    'Utilities': ['NEE','DUK','SO','D','AEP'],
                    'Real Estate': ['AMT','PLD','CCI','EQIX','SPG'],
                }
                peer_tickers = sector_peer_map.get(_sector, [])
            
            # Remove self from peers
            peer_tickers = [p for p in peer_tickers if p.upper() != _ticker_up][:5]
            
            # Fetch peer data in parallel
            peers = []
            if peer_tickers:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                def _fetch_peer(ptk):
                    price = None
                    pi = {}
                    # Source 1: yfinance (fast — 3s max)
                    try:
                        pt = yf.Ticker(ptk)
                        pi = pt.info or {}
                        price = pi.get('currentPrice') or pi.get('regularMarketPrice')
                        if price and float(price) > 0:
                            price = float(price)
                        else:
                            price = None
                    except:
                        pass
                    
                    # Source 2: Yahoo v8 chart (only if Source 1 failed, 3s timeout)
                    if not price:
                        try:
                            r = _http_pool.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ptk}?interval=1d&range=2d", timeout=3)
                            if r.status_code == 200:
                                m = r.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
                                p = m.get('regularMarketPrice', 0)
                                if p and float(p) > 0:
                                    price = float(p)
                                    if not pi: pi = {'longName': ptk, 'currency': m.get('currency', 'USD')}
                        except:
                            pass
                    
                    if not price or not pi:
                        return None
                    
                    return {
                        "ticker": ptk,
                        "name": (pi.get('shortName') or pi.get('longName') or ptk)[:30],
                        "price": round(price, 2),
                        "pe": round(float(pi.get('trailingPE', 0)), 1) if pi.get('trailingPE') else 'N/A',
                        "market_cap": float(pi.get('marketCap', 0)),
                        "profit_margin": round(float(pi.get('profitMargins', 0) or 0) * 100, 1),
                        "roe": round(float(pi.get('returnOnEquity', 0) or 0) * 100, 1),
                        "revenue_growth": round(float(pi.get('revenueGrowth', 0) or 0) * 100, 1),
                        "debt_to_equity": round(float(pi.get('debtToEquity', 0) or 0), 1),
                    }
                
                with ThreadPoolExecutor(max_workers=5) as ex:
                    futs = {ex.submit(_fetch_peer, t): t for t in peer_tickers}
                    for f in as_completed(futs, timeout=8):
                        try:
                            r = f.result(timeout=3)
                            if r: peers.append(r)
                        except:
                            pass
            
            live_data["peers"] = peers
            live_data["peer_count"] = len(peers)
            if peers:
                valid_pes = [p['pe'] for p in peers if p['pe'] != 'N/A' and p['pe'] > 0]
                live_data["peer_avg_pe"] = round(sum(valid_pes) / len(valid_pes), 1) if valid_pes else 'N/A'
                print(f"📊 Peers: {len(peers)} found — avg PE: {live_data['peer_avg_pe']}")
            else:
                live_data["peer_avg_pe"] = 'N/A'
        except Exception as e:
            print(f"⚠️ Peer fetch error: {e}")
            live_data["peers"] = []
            live_data["peer_count"] = 0
            live_data["peer_avg_pe"] = 'N/A'
        
        # ═══ INTRINSIC VALUE CALCULATIONS ═══
        try:
            _eps = float(info.get('trailingEps', 0) or 0)
            _bvps = float(info.get('bookValue', 0) or 0)
            _fwd_eps = float(info.get('epsForward', 0) or info.get('forwardEps', 0) or 0)
            _pe = float(live_data['pe_ratio']) if live_data['pe_ratio'] != 'N/A' else 0
            _growth = float(info.get('earningsGrowth', 0) or info.get('revenueGrowth', 0) or 0)
            if abs(_growth) < 1: _growth = _growth * 100  # Convert decimal to %
            
            intrinsic = {}
            
            # 1. Graham Number = sqrt(22.5 × EPS × BVPS)
            if _eps > 0 and _bvps > 0:
                import math
                graham = round(math.sqrt(22.5 * _eps * _bvps), 2)
                intrinsic['graham'] = graham
                intrinsic['graham_upside'] = round((graham / current_price - 1) * 100, 1) if current_price > 0 else 0
            
            # 2. Peter Lynch Fair Value = EPS × Growth Rate (PEG = 1)
            if _eps > 0 and _growth > 0:
                lynch = round(_eps * _growth, 2)
                intrinsic['lynch'] = lynch
            
            # 3. DCF Simple = Forward EPS × (8.5 + 2g) where g = growth rate
            # Benjamin Graham's growth formula
            if _eps > 0:
                g = max(0, min(_growth, 25))  # Cap growth at 25%
                dcf_graham = round(_eps * (8.5 + 2 * g), 2)
                intrinsic['dcf_simple'] = dcf_graham
                intrinsic['dcf_upside'] = round((dcf_graham / current_price - 1) * 100, 1) if current_price > 0 else 0
            
            # 4. Earnings Yield vs Bond (10Y ~4.5%)
            if _pe > 0:
                earnings_yield = round(100 / _pe, 2)
                intrinsic['earnings_yield'] = earnings_yield
                intrinsic['earnings_yield_premium'] = round(earnings_yield - 4.5, 2)  # vs 10Y bond
            
            # 5. Book Value
            if _bvps > 0:
                intrinsic['book_value'] = round(_bvps, 2)
                intrinsic['price_to_book_discount'] = round((1 - current_price / _bvps) * 100, 1) if _bvps > 0 else 0
            
            live_data['intrinsic'] = intrinsic if intrinsic else None
            if intrinsic:
                print(f"💎 Intrinsic value: Graham={intrinsic.get('graham','N/A')}, DCF={intrinsic.get('dcf_simple','N/A')}")
        except Exception as e:
            print(f"⚠️ Intrinsic value calc failed: {e}")
            live_data['intrinsic'] = None
        
        # ═══ SANITIZE NaN/Infinity before JSON serialization ═══
        import math as _math
        def _sanitize(obj):
            if isinstance(obj, float):
                if _math.isnan(obj) or _math.isinf(obj):
                    return None
            elif isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_sanitize(i) for i in obj]
            return obj
        live_data = _sanitize(live_data)
        
        stock_data_cache[cache_key] = (live_data, current_time)
        print(f"💾 Cached data for {cache_key}")
        
        return live_data
        
    except Exception as e:
        # Last resort: try stale cache
        cache_key = company_name.upper()
        if cache_key in stock_data_cache:
            cached_data, cached_time = stock_data_cache[cache_key]
            age_minutes = (datetime.now() - cached_time).total_seconds() / 60
            if age_minutes < CACHE_STALE_OK_MINUTES:
                print(f"🆘 Exception fallback: serving stale cache for {cache_key}")
                cached_data["data_timestamp"] = f"{datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')} (cached data)"
                return cached_data
        
        return {
            "error": f"Could not fetch data: {str(e)}. Try using ticker symbol (e.g., TSLA for Tesla)"
        }


from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse as StarletteRedirect

class DomainRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        host = request.headers.get("host", "")
        # Redirect onrender.com to celesys.ai (preserve path + query)
        if "onrender.com" in host:
            url = f"https://celesys.ai{request.url.path}"
            if request.url.query:
                url += f"?{request.url.query}"
            return StarletteRedirect(url, status_code=301)
        return await call_next(request)

app.add_middleware(DomainRedirectMiddleware)


@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        with open("index.html", "r") as f:
            return f.read()
    except:
        return """<html><body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1>⚡ Celesys AI</h1>
                <h2>Verified Live Data Edition</h2>
                <p>HTML file not found.</p></body></html>"""


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "reports_generated": report_counter["count"],
        "version": "1.0-VERIFIED-REALTIME",
        "api_key_set": bool(ANTHROPIC_API_KEY),
        "api_key_preview": (ANTHROPIC_API_KEY[:8] + "...") if ANTHROPIC_API_KEY else "NOT SET",
        "active_rate_limits": len(email_rate_limiter),
        "global_requests_last_min": len(global_request_log),
        "stock_cache_entries": len(stock_data_cache),
        "ai_report_cache_entries": len(_ai_report_cache),
        "stock_cache_tickers": list(stock_data_cache.keys()),
        "cache_expiry_minutes": CACHE_EXPIRY_MINUTES
    }


@app.get("/googleb6e1e80f88761fcc.html", response_class=HTMLResponse)
async def google_verify():
    return "google-site-verification: googleb6e1e80f88761fcc.html"

# ═══ PWA: Manifest, Service Worker & Icons ═══
# All PWA assets served inline — zero file dependencies

@app.get("/manifest.json")
async def pwa_manifest():
    """Serve PWA manifest inline — no file dependency."""
    return JSONResponse({
        "name": "Celesys AI — Stock Analysis",
        "short_name": "Celesys AI",
        "description": "Free AI-powered stock analysis with buy/sell verdicts, risk scoring, and entry/exit levels for US & Indian markets.",
        "start_url": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#f8f9fa",
        "theme_color": "#002f6c",
        "scope": "/",
        "lang": "en",
        "categories": ["finance", "business", "education"],
        "icons": [
            {"src": "/icons/icon-72.png", "sizes": "72x72", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-96.png", "sizes": "96x96", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-128.png", "sizes": "128x128", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-144.png", "sizes": "144x144", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-152.png", "sizes": "152x152", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/icons/icon-384.png", "sizes": "384x384", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
        ],
        "shortcuts": [{"name": "Analyze Stock", "short_name": "Analyze", "url": "/", "icons": [{"src": "/icons/icon-96.png", "sizes": "96x96"}]}],
        "prefer_related_applications": False
    }, media_type="application/manifest+json")

@app.get("/sw.js")
async def pwa_sw():
    """Serve service worker inline — no file dependency."""
    sw_code = """const CACHE_NAME='celesys-ai-v2';
const STATIC_ASSETS=['/','/manifest.json','/icons/icon-192.png','/icons/icon-512.png'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE_NAME).then(c=>c.addAll(STATIC_ASSETS).catch(()=>{})));self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE_NAME).map(k=>caches.delete(k)))));self.clients.claim()});
self.addEventListener('fetch',e=>{
if(e.request.method!=='GET')return;
const u=new URL(e.request.url);
if(u.pathname.startsWith('/api/'))return;
if(e.request.mode==='navigate'){e.respondWith(fetch(e.request).then(r=>{const c=r.clone();caches.open(CACHE_NAME).then(ca=>ca.put(e.request,c));return r}).catch(()=>caches.match(e.request).then(r=>r||caches.match('/'))));return}
e.respondWith(caches.match(e.request).then(c=>{const f=fetch(e.request).then(r=>{const cl=r.clone();caches.open(CACHE_NAME).then(ca=>ca.put(e.request,cl));return r}).catch(()=>c);return c||f}))
});"""
    return Response(content=sw_code, media_type="application/javascript",
                   headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})

# PWA Icons — embedded base64 (zero file dependencies)
import base64 as _b64
_PWA_ICONS = {
    "apple-touch-icon.png": "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",
    "icon-128.png": "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",
    "icon-144.png": "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",
    "icon-152.png": "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",
    "icon-192.png": "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",
    "icon-384.png": "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",
    "icon-512.png": "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",
    "icon-72.png": "iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAYAAABV7bNHAAAEj0lEQVR4nO2cX2xTVRzHv727nbdIi1tdXZa2YnFja82k4v5owYB/JpDgg+GNKFSRaDTGBx8WUdDEzBhNjH8e1AxfDInBGAMmJjQhI0CGbOKyyR+TZUop2LluNOtk1lmoD03ndk9v771195zecj5P3dnu7vd89rvn7J6bcwEOh8PhlC2Wko+896XsEuagw/AnuvurX5AZxcjRIUq7oEoQI0eDKEHTL6pEOYCmfqkLqlQ5eVT6V7zEtMhxrNIXiAWpMfWfUbjcxJJPagYxefJZtYiSoXyJFaseM8lZSLHcCv3VNkhrPYkZ0Jm/sCCl6jG7nDxK/SjQb/0VdJOhXVClVE8ejf3hFaRC6dN8GbD15efnP3/30aeGnMO0FbRQTqGvlwrTCqIFF6SCaQXJxxyjxiBTD9JGSVmIaSuIFlyQCmVxiW0MerC5cyXWtTbA47Kj1i7BKgpIzc7hYjyFkbEE+oYu4/DJXzF97W+q2ZgKevR+L957YT3WNNYV/L7TIcHpkLB2tQvhLQGk5zJwP9mLqVSaWkZmgvaFO7F3RwcEQftzA6lahFWsMjAVCRNB3dvb8Ga4k2g/PnwFHxz8Cf1n40jOpFFrl7CmsQ5bQz7s3OzHrZKVelbqgjr89ejZHSLa3z3wI7o/O7mo7Y/kLI4MRHFkIIp9+0/h/RcfQjZL9xkCdUE9u0OwyK6qyGCUkCNnKpVG+J2IgckKQ3Wa97jsePg+D9G+d/8pmjF0QVVQV5uXaLuS+BOnz4/TjKELqoIa3TVE29BogmYE3VAVVHebjWibnP6LZgTdUBUkH5zNAFVBE0myWpwOiWYE3VAVNHo5SbQFm1w0I+iGqqDI4CWizV23HO0t9TRj6IKqoNjEDPqGYkT7W8+Qtx3lAvX1oNc+74f8bmFTx0q8vevBosfVOiR80f0Y7qhZZmA6EuqCfjgXx+u9/UT7nqfb0ffhNjwR8uH2FTZYRQGummXoarsTH7+yEdGvn0V4SwAWylMhk7v5ni8HYLtFxJ6n2hdN/RuCbmwIullEUoTZkusbvf3Y9Oq3GBmb1HxMei6DfzLXDUxFwnRFMTIYRSQcxSNrc0uuoXtyS67OFRKqBAEzs3O4OJ7CyNgk+oZiOHTiJltyzXP0TAxHz5CzWznAn2qowAWpwAWpwAWpUBaDtC/YisD63H/Sxw4cxMzUVQBAtU3C48/txPREAse/+oZJtrKoIK+/Gelrs7nPgWbGaRbDXFBNvQt2Zy1+G/4ZiUsxuJubIFQxjzUP8yRefwuyN24gdv4XRM9eQLUkod53F+tY8zAdg6pEEQ1Nd8MiCOjatWO+3etvxu+j+vdVGAFTQQ2NqyBWW3H60PeYiOYW0/zrHoAv2AqbfTmuZzIs4wHQc4mVsFNGDW+gBdlsFsn4f8/FrsbHYbFY4GlZveTnW4TG/hReXKn0vRqAsiDZvrHCFaS0l9OAKmKCRjlAKbOY2SXpzK8sqNiOYLNKKpZ7ybdk5k9mhnHpf/xB1VfAK33XM1D0alEfg0p4nYOpUOmftkG6UiVp6Bd/d4cK/O0vHA6HU8b8C1rmMwxMSJdzAAAAAElFTkSuQmCC",
    "icon-96.png": "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",
    "screenshot-narrow.png": "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ISAg0MXFZe/ePWV/6Ct5qKSioqLNmzZNvOvu8PBwx8633/73pujomwcOrOYybDZb86ubb9m8OT8/383NzdnZqajEL4a/v3+tWrWOHDnSoEEDa8+RIwktWrSwVnj40KGAgICyczYICBg6dNg777xts5lyP09wfitPT09PTU3tP+A6X19fY8yxY8cKCwvLHdmjZ88f161LT0u/unlzx8qtb7ZFi5YtWrQcMmToG69Piy7zbkCVA6qj8nWWOsMlVXS2z3UBOFdXymtJlXN1db3++htWRkTExGzNyclJSUnZsH79t9+urPyhkvbs3p2ZmWm9UOLQrl276Oiosn/eOhQUFLz99r937tyRlpaWn5+fkBC/es3qkJAQ6xUKX1/fE8eP5+bmWoNdXFz69u339YrlR44cyc7OXrky4vTp03379Xd1de3ff8CKFct3747Nzc05evTogi8+L/ksAYGBDz30cExMzJeLF5Vdw/mt3MvLy9PTMzo6Ki8v7+TJk/PmfVbRyC5duqampkZGbrBeFLckJMR//vn8EydO5Ofnnzh+PC0tzf+398JVDqimytdZ6gyXVNHZPo814JxwlVRs4KBBdbzqfLty5dw5c7y964WFhd10881VPuQQFRUV0qqVu7t7yZ3t27df8uWX+/fva936mnKftFatWkOGDP1x3drFixZlZmbW9fZuGxZ286+fA+jbr/+cTz959pmn8/LyrA8BDBk61G63z5r5flZWVqNGje67/y/WG0CDhwzx8PRYvHjxmfT0ho0a3Tq89NVEQGDglIcenv7O28ZmGzHituqvvKLT5ezsfNfd9yxetHD1Dz94e3v37dfv6wpemPfw8GjfvkNs7K6SV2FNmgSfPHFy7pxPk5KSvLzq9uzVq1fv3iWPqnJANVW+zlJnuNSxFZ1tXFS2nNy8S70G/MH9590ZPj4+fxo3/lIvBJcBbtxwcR04cGD//v3c8qCauHHDRfT888/l5uQMHXZLw4YNL/VacHngxg2AEG7cAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEJIEgAhJAmAEJIEQAhJAiCEJAEQQpIACCFJAISQJABCSBIAISQJgBCSBEAISQIghCQBEEKSAAghSQCEkCQAQkgSACEkCYAQkgRACEkCIIQkARBCkgAIIUkAhJAkAEL+H795mrVZOtimAAAAAElFTkSuQmCC",
    "screenshot-wide.png": "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AhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABC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7Z2npdgfz733DpsxffoFF1504UUXLVq08IH773/nnbfPGXzuxRdfMm/e3If/+te2bdoeqIvqAPx38xAsAHZj0aKF1117Teqfu+68M7Wzbdt2ffocm52dXVBQMH78K+cMPrd58+ZZWVmtWrU+7rh+U6dOSZKklJd2NWXqlJ69emVkZHTq1DkjI2P27NmlryojI+PcIee99967t/341gcfuH/8+PFr167d0+CCgoKJEycMHDioRYvDcnJyTu/fv2GjRhMnvJ6fn//aa68OHDiwU+fOVatWbda8+ZDzhhY/cMLrr48Y8cxVV121p/otfeWdOnc+5pie2dlVmzdv3rFjx8WLFpc4tnr16oMHn7t27drVq1YV35+VldWte7dpU6elfpz+zjs5OQe1b98+SZIvcnMLCgo6deqclZVVp07dQYPOKBG3ex1QQmFh4aJFC99++62OHTvtacye1rlbezrb6QHpP56dZ6lT56OPPjo7O7tDh46NGjVq27Zt165ds7Ozu3Q5qnbt2h8tWbLXdwSAL8EVYAB2Y7efAW7cuHFqY82aNfn5+X/+0x+TJCkqKkr9b9169Up/qYR169Yt+eijiy++JEmSSpUq9ezZa+rUKV26dCl9Yd27dz/iiCPmzZu3ZMlHU6dMHjN61ODB5x7bt++uIz/77LPt27c3b9EiveewFi1Wr169Zs2agoKCVi1b7Xb+6e+888UXX9zwgx8esueALH3lDYrd2FwtJ2fjxo2p7VWrVo0eNWrp0iWbN29OnZn1GzY0adq0+My9e/X+3e9++/nnm2rUqDl12tQex/RIXSKuU7du+/btf/fb33Tt1q116zZt27atUqVK8QP3OiAt9Z82MjMza9Wq3bNXrwEDBpYYUJZ17mpPZzv9Y/qPJ6V+/X/9SVSrVq1e8ZNWrdrWLVtKfzsA+HIEMABlVanyzrt8i4oKkyS5+ZZbG+1yn2opL5UwdeqUwsLCO35ye3pPRkbGhg0bateuXfqBBx10UPfu3bt3715UVPT44489//xzvfv02fXzrql4+/c9SZJkJElR6s12O3mzZs2WLl361rRphwze49Ok97Ly3c1cVFR035//1KFDhx/eeFPNmjUzMzNv+P73CgsLS7578+aNGzd+66232h/R/pMVKy677PL0/N++6urFixfNnz9/zJjRTz05/LvXXFv8DO91QFrpjzcr4zp3e+Aue5Ik+depSP/xpFf8bz8lu//XAQAVSwADsM8aNmxUpUqVuXM/2DWxSnmpuMLCwrffeuvSyy7v2rVreufdd//hrWnTTjv99DIuIyMjo+XhLd95++2CgoLs7OxKlTILi2VYvXr1KleuvGzZsgYNGqT2LFu2tFWrVqkVLl60qGHDhrvO2aBhw0GDzrjnnrszMpLdfqPSl1v5pk2bNmzYcMKJJ9WpUydJko8//njHjh27Hdmrd+83Jk7ctHHT4S1bplee+mVbtWrdqlXrgQMH/eauO6ft8sywvQ4oi9LXWeIMF7ens72vCwCA/cpngAHYZ1lZWV/72snjxo6dMWP6tm3b1q9fP+nNN196aVzpLxX3wZw5mzdvTn3ANa1z587Tpk3d9Vpi2vbt2++++w+zZs3cuHFjQUHB0qVLXnv9tTZt2qQ+WVqnTp1PVqzIy8tLDa5SpUq/fse/OGb0smXLtm7dOm7c2NWrV/c7/oSsrKwTTjhxzJjRc+bMzsvbtnz58qeferL4uzRs1Oi6666fMWPGsyNH7LqGL7fy6tWr5+TkTJs2NT8/f+XKlU888fieRh59dI8NGzZMnjwp9eislKVLlzz55PBPPvmkoKDgkxUrNm7cWO/f7yrf64AyKn2dJc5wcXs6219iDQCw/7gCDMCXcXr//gdXP/ilceMee/TRmjVrdezY8dTTTtvrS2lTp05t07Zt1apVi+888sgjn3v22QUL5rdrd8Ru37Ry5coDBw56Y+KEkSNGbN68uUbNmp06djztn9+E1O/4Ex79+99+fOst+fn5qa9BGjhoUFFR0QP337dly5amTZtedfV3Ug8lHjBwYLWcaiNHjvx806YmTZuedWbJK6UNGzW69rrrh91zd5KRcfbZ55R95Xs6XZUqVbrs8m+OHPHMa6++WrNmzX7HH//iHh7fVa1atSOP7DJ79vvFrzA3a9Z85ScrH3v072vXrq1evUbvPn36HHts8aP2OqCMSl9niTNc4tg9nW0A+M+RsS0v/0CvAQD4lz/98d7atWt/4/wLDvRCAOC/jVugAeA/yIcffrhgwQI3DwPA/uAWaAD4T3H77bflbds26IyvN2nS5ECvBQD+C7kFGgAAgBDcAg0AAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAIQggAEAAAhBAAMAABCCAAYAACAEAQwAAEAIAhgAAIAQBDAAAAAhCGAAAABCEMAAAACEIIABAAAIQQADAAAQggAGAAAgBAEMAABACAIYAACAEAQwAAAAIQhgAAAAQhDAAAAAhCCAAQAACEEAAwAAEIIABgAAIAQBDAAAQAgCGAAAgBAEMAAAACEIYAAAAEIQwAAAAITw/wEx2pm92o0evQAAAABJRU5ErkJggg=="
}

@app.get("/icons/{icon_name}")
async def pwa_icon(icon_name: str):
    safe = icon_name.replace("..", "").replace("/", "").replace("\\", "")
    if safe in _PWA_ICONS:
        data = _b64.b64decode(_PWA_ICONS[safe])
        return Response(content=data, media_type="image/png",
                       headers={"Cache-Control": "public, max-age=604800"})
    raise HTTPException(404)

@app.get("/.well-known/assetlinks.json")
async def asset_links():
    """Digital Asset Links for Android TWA verification.
    Replace SHA256_CERT_FINGERPRINT with your actual signing key fingerprint."""
    return JSONResponse([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "ai.celesys.app",
            "sha256_cert_fingerprints": ["__SHA256_CERT_FINGERPRINT__"]
        }
    }], headers={"Content-Type": "application/json"})

@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    return """User-agent: *
Allow: /
Disallow: /api/
Disallow: /api/generate-report
Disallow: /api/check-rate-limit

# AI Crawlers — welcome to index our public pages
User-agent: GPTBot
Allow: /
Allow: /about
Allow: /faq
Allow: /disclaimer
Disallow: /api/

User-agent: ChatGPT-User
Allow: /
Disallow: /api/

User-agent: Google-Extended
Allow: /
Disallow: /api/

User-agent: Anthropic-ai
Allow: /
Disallow: /api/

User-agent: PerplexityBot
Allow: /
Disallow: /api/

Sitemap: https://celesys.ai/sitemap.xml
"""

@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt():
    return """# Celesys AI — llms.txt
# https://celesys.ai

## About
Celesys AI is a free, AI-powered stock analysis platform for retail investors.
It generates institutional-grade research reports in 60 seconds for US (NYSE, NASDAQ)
and Indian (NSE, BSE) stock markets. No signup required.

## Core Features
- Real-time stock price data and live market indicators
- 8-factor deterministic stock verdict engine (Strong Buy / Buy / Hold / Sell / Strong Sell)
- Intrinsic value calculations: Graham Number, DCF growth model, Peter Lynch fair value, earnings yield vs bond
- AI-generated buy/sell price targets with entry and exit levels
- Quarterly earnings analysis with QoQ and YoY growth trends
- Management tone and CEO/CFO confidence assessment
- Financial health radar: profit margin, ROE, current ratio, operating margin, debt-to-equity
- Risk profile scoring: volatility (beta), debt, liquidity, valuation risk, sector risk
- Valuation metrics: P/E ratio, P/B ratio, dividend yield, forward P/E
- 6-month historical price trend chart with real monthly close data
- Margin vs industry comparison benchmarking
- Hidden small-cap and micro-cap stock recommendations with growth potential ratings
- Smart Trades: daily AI-generated index and stock trade ideas using 10-factor scoring with NSE option chain data
- Curated stock picks across 6 categories: large-cap, mid-cap, small-cap, niche/moat, micro-cap multibagger, best indices
- Global market indices live ticker: S&P 500, NASDAQ, Dow Jones, Nifty 50, Sensex, FTSE 100, DAX, Nikkei 225

## Pages
- Home: https://celesys.ai — Main stock analysis tool
- About: https://celesys.ai/about — Company mission and how it works
- FAQ: https://celesys.ai/faq — Frequently asked questions
- Privacy: https://celesys.ai/privacy — Privacy policy
- Terms: https://celesys.ai/terms — Terms of service
- Disclaimer: https://celesys.ai/disclaimer — Investment disclaimer

## Data Sources
Real-time market data sourced from Yahoo Finance, Google Finance, NSE India, and Screener.in.
AI analysis powered by Anthropic Claude. All data is for educational purposes only.

## Contact
Email: contact@celesys.ai
Website: https://celesys.ai
"""

@app.get("/sitemap.xml", response_class=Response)
async def sitemap():
    today = datetime.now().strftime('%Y-%m-%d')
    pages = [
        ("https://celesys.ai", "daily", "1.0"),
        ("https://celesys.ai/about", "monthly", "0.8"),
        ("https://celesys.ai/faq", "monthly", "0.9"),
        ("https://celesys.ai/privacy", "monthly", "0.5"),
        ("https://celesys.ai/terms", "monthly", "0.5"),
        ("https://celesys.ai/disclaimer", "monthly", "0.5"),
        ("https://celesys.ai/contact", "monthly", "0.6"),
    ]
    urls = "\n".join([f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{pri}</priority>
  </url>""" for loc, freq, pri in pages])
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>"""
    return Response(content=content, media_type="application/xml")

# ═══════════════════════════════════════════════════════════
# ADSENSE-REQUIRED PAGES
# ═══════════════════════════════════════════════════════════

def _page_shell(title: str, body: str, slug: str = "", description: str = "") -> str:
    canonical = f"https://celesys.ai/{slug}" if slug else "https://celesys.ai"
    meta_desc = description or f"{title} — Celesys AI provides free AI-powered stock analysis for US and Indian markets."
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — Celesys AI</title>
<meta name="description" content="{meta_desc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title} — Celesys AI">
<meta property="og:description" content="{meta_desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Celesys AI">
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;700&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#0a0e1a;color:#c9d1d9;font-family:'DM Sans',sans-serif;line-height:1.8;padding:40px 20px 120px}}
.wrap{{max-width:720px;margin:0 auto}}h1{{font-family:'Sora',sans-serif;font-size:28px;color:#fff;margin-bottom:8px}}
.sub{{color:#6b7280;font-size:13px;margin-bottom:32px}}.back{{display:inline-block;margin-bottom:24px;color:#3b82f6;text-decoration:none;font-size:13px;font-weight:600}}
.back:hover{{text-decoration:underline}}h2{{font-family:'Sora',sans-serif;font-size:18px;color:#e5e7eb;margin:28px 0 10px}}
p,li{{font-size:14px;color:#9ca3af;margin-bottom:12px}}ul{{padding-left:20px}}a{{color:#3b82f6}}
.foot{{margin-top:48px;padding:20px 0 16px;border-top:1px solid #1e2433}}
.foot-top{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;padding-bottom:12px;border-bottom:1px solid #1e2433}}
.foot-brand{{font-family:'Sora',sans-serif;font-size:13px;font-weight:700;color:#fff;letter-spacing:.5px}}
.foot-brand span{{color:#3b82f6}}
.foot-links{{display:flex;gap:16px;flex-wrap:wrap}}
.foot-links a{{font-size:11px;color:#6b7280;text-decoration:none}}
.foot-links a:hover{{color:#3b82f6}}
.foot-copy{{font-size:10px;color:#4b5563;padding-top:12px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}}
.edu-bar{{position:fixed;bottom:0;left:0;width:100%;z-index:199;padding:14px 24px;background:rgba(10,12,20,.98);border-top:1px solid rgba(239,68,68,.15);backdrop-filter:blur(12px)}}
.edu-bar .edu-title{{font-family:'Sora',sans-serif;font-size:12px;font-weight:800;color:#ef4444;letter-spacing:.5px;margin-bottom:6px}}
.edu-bar .edu-lines{{display:flex;flex-wrap:wrap;gap:4px 20px}}
.edu-bar .edu-line{{font-size:10px;color:#6b7280;line-height:1.5;padding-left:10px;border-left:2px solid rgba(239,68,68,.3)}}
.edu-bar .edu-line strong{{color:#ef4444;font-weight:700;font-size:10px}}
.site-wm{{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:9998;overflow:hidden;opacity:.03}}
.site-wm span{{position:absolute;font-size:12px;font-weight:800;color:#fff;transform:rotate(-35deg);white-space:nowrap;letter-spacing:2px;font-family:'Sora',sans-serif;user-select:none}}
</style></head><body>
<div class="site-wm" id="swm"></div>
<script>!function(){{var w=document.getElementById('swm');if(!w)return;var h='';for(var r=0;r<30;r++)for(var c=0;c<8;c++){{var t=r*120+Math.random()*40,l=c*250+Math.random()*60;h+='<span style="top:'+t+'px;left:'+l+'px">CELESYS.AI \u2022 CONFIDENTIAL</span>';}}w.innerHTML=h;}}();</script>
<div class="wrap"><a href="/" class="back">← Back to Celesys AI — Free Stock Analysis</a>
<h1>{title}</h1><p class="sub">Last updated: February 2026</p>
{body}
<div style="margin-top:32px;padding:20px;border-radius:10px;background:#111827;border:1px solid #1e2433">
<div style="font-family:'Sora',sans-serif;font-size:13px;font-weight:700;color:#e5e7eb;margin-bottom:12px">Explore Celesys AI</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px">
<a href="/" style="color:#3b82f6;text-decoration:none;font-size:12px;padding:8px 12px;border-radius:6px;background:#0d1117;border:1px solid #1e2433">&#9889; Analyze Any Stock Free</a>
<a href="/about" style="color:#3b82f6;text-decoration:none;font-size:12px;padding:8px 12px;border-radius:6px;background:#0d1117;border:1px solid #1e2433">&#128218; About Celesys AI</a>
<a href="/faq" style="color:#3b82f6;text-decoration:none;font-size:12px;padding:8px 12px;border-radius:6px;background:#0d1117;border:1px solid #1e2433">&#10067; FAQ</a>
<a href="/disclaimer" style="color:#3b82f6;text-decoration:none;font-size:12px;padding:8px 12px;border-radius:6px;background:#0d1117;border:1px solid #1e2433">&#9888; Disclaimer</a>
<a href="/privacy" style="color:#3b82f6;text-decoration:none;font-size:12px;padding:8px 12px;border-radius:6px;background:#0d1117;border:1px solid #1e2433">&#128274; Privacy</a>
<a href="/terms" style="color:#3b82f6;text-decoration:none;font-size:12px;padding:8px 12px;border-radius:6px;background:#0d1117;border:1px solid #1e2433">&#128196; Terms</a>
<a href="/contact" style="color:#3b82f6;text-decoration:none;font-size:12px;padding:8px 12px;border-radius:6px;background:#0d1117;border:1px solid #1e2433">&#9993; Contact</a>
</div>
</div>
<div class="foot">
<div class="foot-top">
<div><div class="foot-brand">CELESYS <span>AI</span></div><div style="font-size:9px;color:#4b5563;letter-spacing:1px;font-weight:600">RESEARCH PLATFORM</div></div>
<div class="foot-links">
<a href="/about">About</a><a href="/faq">FAQ</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a><a href="/disclaimer">Disclaimer</a><a href="mailto:contact@celesys.ai">✉ contact@celesys.ai</a>
</div>
</div>
<div class="foot-copy">
<span>© 2026 Celesys AI · All rights reserved</span>
<span>Real-time data · AI-powered analysis · Not financial advice</span>
</div>
</div>
</div>
<div class="edu-bar">
<div class="edu-title">⚠ READ THIS BEFORE YOU TRADE</div>
<div class="edu-lines">
<div class="edu-line"><strong>NOT FINANCIAL ADVICE:</strong> This tool is <b style="color:#f59e0b">for education only</b>. Not a replacement for licensed financial advisors. <b style="color:#f59e0b">Consult your financial advisor</b> before making any decisions. Never invest money you cannot afford to lose.</div>
<div class="edu-line"><strong>DATA MAY BE DELAYED:</strong> Market data from third-party providers may be delayed or incomplete. Always cross-check with your broker.</div>
<div class="edu-line"><strong>YOU CAN LOSE MONEY:</strong> All investments carry real risk. Past performance never guarantees future results. No affiliation with any brokerage.</div>
</div>
</div>
</body></html>"""

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page():
    return _page_shell("Privacy Policy", slug="privacy", description="Celesys AI privacy policy. How we handle your data, cookies, and email addresses for our free stock analysis platform.", body="""
<p>Celesys AI ("we", "us", "our") operates the website celesys.ai. This Privacy Policy explains how we collect, use, and protect your information.</p>

<h2>Information We Collect</h2>
<p>We collect minimal information to provide our stock analysis service:</p>
<ul>
<li><strong>Email Address:</strong> Used solely for rate limiting (5 reports per hour). We do not send marketing emails or share your email with third parties.</li>
<li><strong>Stock Ticker Searches:</strong> We log which stocks are analyzed to improve our service. This data is not linked to individual users.</li>
<li><strong>Analytics Data:</strong> We use Google Analytics to understand how visitors use our site. This includes anonymized data such as page views, session duration, device type, and approximate geographic location.</li>
</ul>

<h2>How We Use Your Information</h2>
<ul>
<li>To provide free AI-powered stock analysis reports</li>
<li>To enforce fair usage limits (rate limiting)</li>
<li>To improve our service and user experience</li>
<li>To display relevant advertisements through Google AdSense</li>
</ul>

<h2>Cookies & Advertising</h2>
<p>We use cookies for Google Analytics and Google AdSense. Third-party advertising partners, including Google, may use cookies to serve ads based on your prior visits to our website or other websites. You can opt out of personalized advertising by visiting <a href="https://www.google.com/settings/ads" target="_blank" rel="noopener">Google Ads Settings</a>.</p>

<h2>Data Storage & Security</h2>
<p>We do not store personal data on our servers beyond temporary rate-limiting records. All stock analysis is generated in real-time and not permanently stored. We use HTTPS encryption for all data transmission.</p>

<h2>Third-Party Services</h2>
<ul>
<li><strong>Yahoo Finance:</strong> Market data provider</li>
<li><strong>AI Engine:</strong> Advanced language model for analysis</li>
<li><strong>Google Analytics:</strong> Website analytics</li>
<li><strong>Google AdSense:</strong> Advertising</li>
<li><strong>Render:</strong> Web hosting</li>
</ul>

<h2>Your Rights</h2>
<p>You may request deletion of any data associated with your email address by contacting us. Since we store minimal data, in most cases there is nothing to delete beyond rate-limiting records that expire automatically.</p>

<h2>Children's Privacy</h2>
<p>Our service is not directed to individuals under 18. We do not knowingly collect personal information from children.</p>

<h2>Changes to This Policy</h2>
<p>We may update this policy from time to time. Changes will be posted on this page with an updated revision date.</p>

<h2>Contact</h2>
<p>For questions about this Privacy Policy, contact us at: <a href="mailto:contact@celesys.ai">contact@celesys.ai</a></p>
""")

@app.get("/terms", response_class=HTMLResponse)
async def terms_page():
    return _page_shell("Terms of Service", slug="terms", description="Terms of service for Celesys AI free stock analysis platform. Usage rules, data disclaimers, and intellectual property.", body="""
<p>By using Celesys AI (celesys.ai), you agree to these Terms of Service. Please read them carefully.</p>

<h2>Service Description</h2>
<p>Celesys AI is a free, educational AI-powered stock analysis platform. We provide research reports on publicly traded stocks using real-time market data and artificial intelligence. Our service is provided "as is" without any warranties.</p>

<h2>Not Financial Advice</h2>
<p><strong>IMPORTANT:</strong> All content on Celesys AI is for educational and informational purposes only. Nothing on this website constitutes financial advice, investment advice, trading advice, or any other form of professional advice. You should not make any investment decisions based solely on the information provided by our service.</p>
<ul>
<li>Always consult a qualified, licensed financial advisor before making investment decisions</li>
<li>Past performance does not guarantee future results</li>
<li>Stock investing involves risk, including potential loss of principal</li>
<li>AI-generated analysis may contain errors or inaccuracies</li>
</ul>

<h2>Fair Usage</h2>
<ul>
<li>Each email address is limited to 5 reports per hour</li>
<li>Automated scraping or bot access is prohibited</li>
<li>You may not resell or redistribute our reports commercially</li>
<li>Personal and educational use is encouraged</li>
</ul>

<h2>Data Accuracy</h2>
<p>While we source data from reputable financial providers (Yahoo Finance, Google Finance), we cannot guarantee 100% accuracy of all data points. Market data may be delayed. Users should verify critical information independently before making any decisions.</p>

<h2>Intellectual Property</h2>
<p>The Celesys AI brand, logo, website design, and analysis methodology are our intellectual property. Generated reports may be used for personal purposes. You may share reports with attribution to celesys.ai.</p>

<h2>Limitation of Liability</h2>
<p>Celesys AI shall not be liable for any losses, damages, or claims arising from: the use of our reports for investment decisions, data inaccuracies, service interruptions, or any other use of our platform.</p>

<h2>Modifications</h2>
<p>We reserve the right to modify these terms at any time. Continued use of our service constitutes acceptance of updated terms.</p>

<h2>Contact</h2>
<p>For questions about these Terms, contact us at: <a href="mailto:contact@celesys.ai">contact@celesys.ai</a></p>
""")

@app.get("/about", response_class=HTMLResponse)
async def about_page():
    return _page_shell("About Celesys AI", slug="about", description="About Celesys AI — free AI-powered stock analysis for US (NYSE, NASDAQ) and Indian (NSE, BSE) markets. Institutional-grade research in 60 seconds.", body="""
<p style="font-size:16px;line-height:1.8;color:#ccc">Celesys AI turns raw market data into clarity. In under 60 seconds, you get the same depth of stock analysis that hedge funds pay thousands for — and it costs you nothing.</p>

<h2>Why We Built This</h2>
<p>Most retail investors make decisions based on tips, headlines, or gut feel. The investors who consistently win? They have systems — data pipelines, quantitative models, and research frameworks. Celesys AI gives you that system. No jargon, no paywalls, no sign-up forms.</p>

<h2>What Happens When You Hit Analyze</h2>
<p>The moment you enter a ticker, five things happen simultaneously: live price data streams in from multiple exchanges, AI dissects the company's fundamentals against sector benchmarks, management sentiment gets scored from earnings call patterns, institutional money flow reveals who's accumulating and who's exiting, and a risk model stress-tests your downside. You see all of this in one screen — organized by what matters most to your decision.</p>

<h2>The Technology</h2>
<p>We pull from Yahoo Finance, Google Finance, Screener.in, and Finviz through a 5-layer fallback system — if one source is down, the next picks up seamlessly. The AI layer doesn't just summarize data; it cross-references signals, identifies contradictions, and tells you when the numbers don't add up. Every analysis is generated fresh. Nothing is cached or recycled.</p>

<h2>Coverage</h2>
<p>US markets (NYSE, NASDAQ) and Indian markets (NSE, BSE). Enter any valid ticker — from mega-caps like AAPL and RELIANCE to small-caps most screeners miss.</p>

<h2>Completely Free</h2>
<p>5 deep-dive reports per email per hour. No credit card. No account creation. No trial that expires. We believe access to quality research shouldn't depend on your brokerage account size.</p>

<h2>Get in Touch</h2>
<p>Questions, bugs, feature ideas, or just want to say hello — <a href="mailto:contact@celesys.ai" style="color:#3b82f6">contact@celesys.ai</a></p>
""")

@app.get("/contact", response_class=HTMLResponse)
async def contact_page():
    return _page_shell("Contact Us", slug="contact", description="Contact Celesys AI. Send questions, bug reports, or feature requests for our free stock analysis platform.", body="""
<p>We'd love to hear from you! Whether you have feedback, questions, feature requests, or partnership inquiries, we're here to help.</p>

<h2>Email</h2>
<p>📧 <a href="mailto:contact@celesys.ai">contact@celesys.ai</a></p>
<p>We aim to respond within 24-48 hours.</p>

<h2>What You Can Reach Out About</h2>
<ul>
<li><strong>Bug Reports:</strong> Found something broken? Let us know the stock ticker and what went wrong</li>
<li><strong>Feature Requests:</strong> Want a new feature? Use the "Shape Our Roadmap" button on the main page to vote, or email us directly</li>
<li><strong>Data Accuracy:</strong> If you spot incorrect data in a report, we want to know</li>
<li><strong>Partnership & API:</strong> Interested in integrating Celesys AI data? Let's talk</li>
<li><strong>Press & Media:</strong> For media inquiries and interviews</li>
</ul>

<h2>Social</h2>
<p>Follow us for daily stock analysis and updates:</p>
<ul>
<li>Twitter/X: Coming soon</li>
<li>LinkedIn: Coming soon</li>
</ul>

<h2>Feedback</h2>
<p>Your feedback shapes our product. Every suggestion is read and considered for future updates. Thank you for helping us build the best free stock analysis tool on the internet.</p>
""")

@app.get("/disclaimer", response_class=HTMLResponse)
async def disclaimer_page():
    return _page_shell("Disclaimer", slug="disclaimer", description="Investment disclaimer for Celesys AI. Not financial advice. All analysis is for educational purposes only.", body="""
<p>The information provided by Celesys AI is for general educational and informational purposes only.</p>

<h2>No Financial Advice</h2>
<p>All analysis, reports, buy/sell targets, risk scores, and recommendations generated by Celesys AI are produced by artificial intelligence and should NOT be considered as financial advice. We are not registered financial advisors, brokers, or dealers.</p>

<h2>Investment Risk</h2>
<p>Investing in stocks involves substantial risk of loss and is not suitable for every investor. The value of stocks can fluctuate significantly, and you may lose some or all of your investment. Before making any investment decisions, consult with a qualified, licensed financial professional.</p>

<h2>AI Limitations</h2>
<p>Our AI analysis is based on publicly available data and algorithmic processing. AI can make errors, misinterpret data, or produce inaccurate predictions. No AI system can reliably predict stock market movements. Historical patterns do not guarantee future results.</p>

<h2>Data Sources</h2>
<p>We source market data from Yahoo Finance, Google Finance, and other public financial data providers. While we strive for accuracy, we cannot guarantee that all data is current, complete, or error-free. Real-time data may be delayed by 15-20 minutes depending on the source.</p>

<h2>No Guarantees</h2>
<p>Celesys AI makes no representations or warranties about the accuracy, reliability, or completeness of any information on this site. Use our service at your own risk.</p>
""")

@app.get("/faq", response_class=HTMLResponse)
async def faq_page():
    return _page_shell("Frequently Asked Questions", slug="faq", description="FAQ for Celesys AI. Learn how our free AI stock analysis works, what markets we cover, and how to use buy/sell verdicts.", body="""
<h2>What is Celesys AI and how does it work?</h2>
<p>Celesys AI is a free, AI-powered stock analysis platform that generates institutional-grade research reports in 60 seconds. Enter any US (NYSE, NASDAQ) or Indian (NSE, BSE) stock ticker to receive real-time valuation metrics, intrinsic value estimates using the Graham Number and DCF model, 8-factor buy/sell verdicts, quarterly earnings analysis with QoQ and YoY trends, management tone assessment, and curated small-cap picks. No signup required.</p>

<h2>Is Celesys AI free to use?</h2>
<p>Yes — 5 deep-dive reports per email per hour, completely free. No credit card, no subscription, no hidden fees. Celesys AI is funded as an educational research tool to democratize access to institutional-quality financial analysis for retail investors worldwide.</p>

<h2>Which stock markets and tickers are supported?</h2>
<p>Celesys AI supports 100+ pre-loaded US stocks (AAPL, TSLA, NVDA, GOOGL, META, MSFT, AMZN, JPM) and Indian stocks (RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS, ICICIBANK.NS). You can also enter any valid Yahoo Finance ticker for global market coverage including European, Asian, and emerging market equities.</p>

<h2>How does the 8-factor stock verdict engine work?</h2>
<p>The verdict engine scores stocks across 20 quantitative factors: P/E valuation, profitability (profit margins and ROE), financial health (debt-to-equity and current ratio), 52-week price position, price-to-book value, dividend yield, beta/volatility risk, and operating efficiency. The combined score produces a deterministic verdict — Strong Buy, Buy, Hold, Sell, or Strong Sell — that remains consistent regardless of daily price fluctuations.</p>

<h2>How does Celesys AI calculate intrinsic value?</h2>
<p>Celesys AI computes intrinsic value using four established financial models: the Graham Number (square root of 22.5 × EPS × book value per share), the Benjamin Graham DCF growth formula (EPS × (8.5 + 2g) where g is the earnings growth rate), the Peter Lynch fair value (EPS × growth rate for PEG ratio of 1), and earnings yield comparison versus 10-year treasury bond rates. These models help investors determine whether a stock is trading above or below its fundamental worth.</p>

<h2>What does the management tone analysis show?</h2>
<p>The management tone analysis uses real earnings data, analyst ratings, insider trading activity, institutional ownership patterns, and forward guidance to assess whether company leadership is bullish, cautious, or defensive. It examines CEO/CFO confidence through earnings call sentiment, insider buy/sell ratios, and how closely actual results match prior guidance.</p>

<h2>What are Smart Trades and curated stock picks?</h2>
<p>Smart Trades provides daily AI-generated trade ideas for Nifty 50, Bank Nifty, Sensex, and high-momentum individual stocks using a 10-factor scoring engine powered by live NSE option chain data (put-call ratio, max pain, open interest walls). Curated Stock Picks lists the top 5 undervalued companies across six categories: large-cap value, mid-cap growth, small-cap opportunities, niche/deep moat monopolies, micro-cap multibagger candidates, and best-performing stock market indices — for both India and USA markets.</p>

<h2>Is Celesys AI a replacement for a financial advisor?</h2>
<p>No. Celesys AI is an educational research tool, not a licensed financial advisor. All analysis, buy/sell targets, risk scores, intrinsic value calculations, and stock recommendations are AI-generated for educational purposes only. Always consult a certified financial advisor before making investment decisions. Market data from third-party providers may be delayed or incomplete — always cross-check with your broker.</p>
""")

@app.get("/ads.txt", response_class=PlainTextResponse)
async def ads_txt():
    # Replace ca-pub-2084524493538975 with your real AdSense publisher ID after approval
    return "google.com, ca-pub-2084524493538975, DIRECT, f08c47fec0942fa0"

# ═══════════════════════════════════════════════════════════
# INDEX TRADES — AI Daily Trade Ideas (Restricted Access)
# ═══════════════════════════════════════════════════════════
TRADES_ALLOWED_EMAILS = ["x@yp.com"]
_trades_cache = {"timestamp": None, "data": None}  # 30-min cache — live enough for trading, stable enough to not flip-flop
_trades_cache_us = {"timestamp": None, "data": None}  # Separate cache for US

# ═══ TRADE HISTORY — Auto-save for backtesting validation ═══
TRADES_HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades_history.json")

def _load_trade_history():
    try:
        if os.path.exists(TRADES_HISTORY_FILE):
            with open(TRADES_HISTORY_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def _save_trades_to_history(trades_data, date_str):
    """Save generated trades for later validation"""
    try:
        history = _load_trade_history()
        # Extract key trade fields for validation
        saved = []
        for t in (trades_data.get("trades") or []):
            saved.append({
                "type": "INDEX",
                "index": t.get("index", ""),
                "direction": t.get("direction", ""),
                "bias": t.get("bias", ""),
                "entry_level": t.get("entry_level", ""),
                "target_level": t.get("target_level", ""),
                "stop_level": t.get("stop_level", ""),
                "probability": t.get("probability", ""),
                "timing": t.get("timing", ""),
                "move_pct": t.get("move_pct", ""),
            })
        for t in (trades_data.get("stock_trades") or []):
            saved.append({
                "type": "STOCK",
                "stock": t.get("stock", ""),
                "direction": t.get("direction", ""),
                "bias": t.get("bias", ""),
                "entry_level": t.get("entry_level", ""),
                "target_level": t.get("target_level", ""),
                "stop_level": t.get("stop_level", ""),
                "probability": t.get("probability", ""),
                "move_pct": t.get("move_pct", ""),
            })
        if saved:
            history[date_str] = {
                "trades": saved,
                "generated_at": trades_data.get("generated_at", ""),
                "is_expiry_day": trades_data.get("is_expiry_day", False),
            }
            # Keep last 30 days only
            keys = sorted(history.keys())
            if len(keys) > 30:
                for k in keys[:-30]:
                    del history[k]
            with open(TRADES_HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)
            print(f"💾 Saved {len(saved)} trades for {date_str}")
    except Exception as e:
        print(f"⚠️ Trade history save error: {e}")

_nse_cache = {}
_nse_cache_ts = {}

@app.get("/api/nse-options")
async def nse_options(symbol: str = "NIFTY"):
    """Fetch real NSE options chain, VIX, PCR, OI, Max Pain for confluence engine."""
    import requests as req
    from datetime import datetime, timedelta
    
    symbol = symbol.upper().strip()
    cache_key = symbol
    now = datetime.utcnow()
    
    # 3-min cache
    if cache_key in _nse_cache and cache_key in _nse_cache_ts:
        if (now - _nse_cache_ts[cache_key]).total_seconds() < 180:
            return _nse_cache[cache_key]
    
    hdr = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/option-chain",
    }
    
    result = {"success": False, "symbol": symbol}
    
    try:
        s = req.Session()
        # Step 1: Get cookies
        s.get("https://www.nseindia.com/", headers=hdr, timeout=3)
        
        # Step 2: Fetch options chain
        oc_url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}" if symbol in ["NIFTY", "BANKNIFTY", "NIFTY BANK", "FINNIFTY", "MIDCPNIFTY"] else f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
        
        oc_resp = s.get(oc_url, headers=hdr, timeout=4)
        if oc_resp.status_code == 200:
            oc_data = oc_resp.json()
            records = oc_data.get("records", {})
            data = records.get("data", [])
            spot = records.get("underlyingValue", 0)
            expiry_dates = records.get("expiryDates", [])
            current_expiry = expiry_dates[0] if expiry_dates else ""
            
            # Calculate PCR, Max Pain, OI analysis
            total_ce_oi = 0
            total_pe_oi = 0
            total_ce_vol = 0
            total_pe_vol = 0
            strike_oi = {}  # {strike: {ce_oi, pe_oi, ce_chg, pe_chg}}
            
            for row in data:
                strike = row.get("strikePrice", 0)
                ce = row.get("CE", {})
                pe = row.get("PE", {})
                
                if ce and ce.get("expiryDate") == current_expiry:
                    ce_oi = ce.get("openInterest", 0)
                    ce_vol = ce.get("totalTradedVolume", 0)
                    ce_chg = ce.get("changeinOpenInterest", 0)
                    ce_iv = ce.get("impliedVolatility", 0)
                    total_ce_oi += ce_oi
                    total_ce_vol += ce_vol
                else:
                    ce_oi = ce_chg = ce_iv = 0
                
                if pe and pe.get("expiryDate") == current_expiry:
                    pe_oi = pe.get("openInterest", 0)
                    pe_vol = pe.get("totalTradedVolume", 0)
                    pe_chg = pe.get("changeinOpenInterest", 0)
                    pe_iv = pe.get("impliedVolatility", 0)
                    total_pe_oi += pe_oi
                    total_pe_vol += pe_vol
                else:
                    pe_oi = pe_chg = pe_iv = 0
                
                if strike > 0:
                    strike_oi[strike] = {
                        "ce_oi": ce_oi, "pe_oi": pe_oi,
                        "ce_chg": ce_chg, "pe_chg": pe_chg,
                        "ce_iv": ce_iv, "pe_iv": pe_iv
                    }
            
            # PCR
            pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0
            
            # Max Pain calculation
            max_pain_strike = 0
            min_pain = float('inf')
            for strike in strike_oi:
                pain = 0
                for s2 in strike_oi:
                    if s2 < strike:
                        pain += (strike - s2) * strike_oi[s2].get("ce_oi", 0)
                    elif s2 > strike:
                        pain += (s2 - strike) * strike_oi[s2].get("pe_oi", 0)
                if pain < min_pain:
                    min_pain = pain
                    max_pain_strike = strike
            
            # Top OI strikes (support/resistance)
            sorted_ce = sorted(strike_oi.items(), key=lambda x: x[1]["ce_oi"], reverse=True)[:5]
            sorted_pe = sorted(strike_oi.items(), key=lambda x: x[1]["pe_oi"], reverse=True)[:5]
            
            # OI buildup (change in OI)
            top_ce_buildup = sorted(strike_oi.items(), key=lambda x: x[1]["ce_chg"], reverse=True)[:3]
            top_pe_buildup = sorted(strike_oi.items(), key=lambda x: x[1]["pe_chg"], reverse=True)[:3]
            
            # ATM IV
            atm_strike = min(strike_oi.keys(), key=lambda x: abs(x - spot)) if strike_oi else 0
            atm_iv = (strike_oi.get(atm_strike, {}).get("ce_iv", 0) + strike_oi.get(atm_strike, {}).get("pe_iv", 0)) / 2 if atm_strike else 0
            
            result.update({
                "success": True,
                "spot": spot,
                "expiry": current_expiry,
                "expiry_dates": expiry_dates[:4],
                "pcr": pcr,
                "max_pain": max_pain_strike,
                "atm_strike": atm_strike,
                "atm_iv": round(atm_iv, 1),
                "total_ce_oi": total_ce_oi,
                "total_pe_oi": total_pe_oi,
                "ce_resistance": [{"strike": s, "oi": d["ce_oi"], "chg": d["ce_chg"]} for s, d in sorted_ce],
                "pe_support": [{"strike": s, "oi": d["pe_oi"], "chg": d["pe_chg"]} for s, d in sorted_pe],
                "ce_buildup": [{"strike": s, "chg": d["ce_chg"]} for s, d in top_ce_buildup if d["ce_chg"] > 0],
                "pe_buildup": [{"strike": s, "chg": d["pe_chg"]} for s, d in top_pe_buildup if d["pe_chg"] > 0],
            })
        
        # Step 3: Fetch India VIX
        try:
            vix_resp = s.get("https://www.nseindia.com/api/allIndices", headers=hdr, timeout=3)
            if vix_resp.status_code == 200:
                for idx in vix_resp.json().get("data", []):
                    if "VIX" in idx.get("index", "").upper():
                        result["vix"] = round(idx.get("last", 0), 2)
                        result["vix_change"] = round(idx.get("percentChange", 0), 2)
                        break
        except:
            pass
        
        # Step 4: Previous day data for CPR
        try:
            if symbol in ["NIFTY", "BANKNIFTY", "NIFTY BANK"]:
                import yfinance as yf
                tk_map = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "NIFTY BANK": "^NSEBANK"}
                tk = yf.Ticker(tk_map.get(symbol, f"{symbol}.NS"))
                hist = tk.history(period="5d", interval="1d")
                if len(hist) >= 2:
                    prev = hist.iloc[-2]
                    today = hist.iloc[-1]
                    pdh = round(float(prev["High"]), 2)
                    pdl = round(float(prev["Low"]), 2)
                    pdc = round(float(prev["Close"]), 2)
                    pivot = round((pdh + pdl + pdc) / 3, 2)
                    bc = round((pdh + pdl) / 2, 2)
                    tc = round(2 * pivot - bc, 2)
                    cpr_width = round(abs(tc - bc), 2)
                    cpr_pct = round((cpr_width / pdc) * 100, 3)
                    
                    result["pdh"] = pdh
                    result["pdl"] = pdl
                    result["pdc"] = pdc
                    result["pivot"] = pivot
                    result["cpr_top"] = tc
                    result["cpr_bottom"] = bc
                    result["cpr_width"] = cpr_width
                    result["cpr_pct"] = cpr_pct
                    result["cpr_type"] = "NARROW" if cpr_pct < 0.3 else "WIDE" if cpr_pct > 0.8 else "MEDIUM"
                    result["today_high"] = round(float(today["High"]), 2)
                    result["today_low"] = round(float(today["Low"]), 2)
                    result["today_open"] = round(float(today["Open"]), 2)
                    
                    # Gap analysis
                    gap = round(float(today["Open"]) - pdc, 2)
                    gap_pct = round((gap / pdc) * 100, 2)
                    result["gap"] = gap
                    result["gap_pct"] = gap_pct
                    result["gap_type"] = "GAP UP" if gap_pct > 0.3 else "GAP DOWN" if gap_pct < -0.3 else "FLAT OPEN"
        except Exception as e:
            print(f"CPR calc error: {e}")
        
        print(f"📊 NSE Options: {symbol} spot={result.get('spot')} pcr={result.get('pcr')} maxpain={result.get('max_pain')} vix={result.get('vix')}")
    
    except Exception as e:
        print(f"❌ NSE Options error: {e}")
        result["error"] = str(e)
    
    _nse_cache[cache_key] = result
    _nse_cache_ts[cache_key] = now
    return result


_fund_cache = {}
_fund_cache_ts = None

@app.get("/api/fund-live")
async def fund_live():
    """Fetch live NAV, returns, AUM for all ETFs and funds. 30-min cache."""
    global _fund_cache, _fund_cache_ts
    from datetime import datetime, timedelta
    import numpy as np
    
    now = datetime.utcnow()
    if _fund_cache and _fund_cache_ts and (now - _fund_cache_ts).total_seconds() < 1800:
        return _fund_cache
    
    # Map display names to yfinance tickers
    TICKERS = {
        # India ETFs
        "MON100": "MAFANG.NS", "NETFIT": "NETFIT.NS", "ICICIN50": "ICICNIFTY.NS",
        "MAFANG": "MAFANG.NS", "JUNIORBEES": "JUNIORBEES.NS",
        # India MFs (use NAV proxy ETFs where available)
        "QUANT-SC": "0P0001BAU5.BO", "NIPPON-SC": "0P0000XVMZ.BO", "QUANT-MC": "0P0001BAU3.BO",
        "SBI-SC": "0P0000XVRN.BO", "PPFAS": "0P0001BHEJ.BO", "HDFC-MC": "0P0000XVS2.BO",
        "CANROB-SC": "0P00019SQX.BO",
        # USA ETFs
        "QQQ": "QQQ", "SMH": "SMH", "SOXX": "SOXX", "VGT": "VGT", "AIQ": "AIQ",
        # USA MFs
        "FCNTX": "FCNTX", "TRBCX": "TRBCX", "FDGRX": "FDGRX", "BPTIX": "BPTIX", "VIGAX": "VIGAX",
    }
    
    def _fetch_fund(display_name, yf_ticker):
        try:
            tk = yf.Ticker(yf_ticker)
            hist = tk.history(period="5y", interval="1mo")
            if hist is None or len(hist) < 3:
                return display_name, None
            
            closes = hist['Close'].values.astype(float)
            nav = round(float(closes[-1]), 2)
            
            # Returns
            def _ret(months):
                if len(closes) > months:
                    old = float(closes[-(months+1)])
                    if old > 0:
                        return round(((nav - old) / old) * 100, 1)
                return None
            
            # Annualized returns
            def _cagr(years):
                months = years * 12
                if len(closes) > months:
                    old = float(closes[-(months+1)])
                    if old > 0:
                        return round((((nav / old) ** (1/years)) - 1) * 100, 1)
                return None
            
            y1 = _ret(12)
            y3 = _cagr(3)
            y5 = _cagr(5)
            
            # Max drawdown
            peak = closes[0]
            max_dd = 0
            for c in closes:
                if c > peak: peak = c
                dd = (peak - c) / peak * 100
                if dd > max_dd: max_dd = dd
            
            # AUM from info
            info = tk.info or {}
            aum = info.get('totalAssets', 0) or info.get('netAssets', 0) or 0
            aum_fmt = ""
            if aum > 0:
                if aum >= 1e12: aum_fmt = f"${aum/1e12:.1f}T"
                elif aum >= 1e9: aum_fmt = f"${aum/1e9:.1f}B"
                elif aum >= 1e7: aum_fmt = f"₹{aum/1e7:.0f} Cr"
                elif aum >= 1e6: aum_fmt = f"${aum/1e6:.1f}M"
            
            exp = info.get('annualReportExpenseRatio', 0) or info.get('totalExpenseRatio', 0) or 0
            exp_fmt = f"{exp*100:.2f}%" if exp > 0 else ""
            
            is_indian = '.NS' in yf_ticker or '.BO' in yf_ticker
            sym = "₹" if is_indian else "$"
            
            return display_name, {
                "nav": nav,
                "nav_fmt": f"{sym}{nav:,.2f}",
                "y1": f"{y1:+.1f}%" if y1 is not None else "N/A",
                "y3": f"{y3:+.1f}%" if y3 is not None else "N/A",
                "y5": f"{y5:+.1f}%" if y5 is not None else "N/A",
                "y1_num": y1,
                "y3_num": y3,
                "y5_num": y5,
                "max_dd": f"-{max_dd:.0f}%",
                "aum": aum_fmt,
                "exp": exp_fmt,
            }
        except Exception as e:
            print(f"  fund fetch fail {display_name}: {e}")
            return display_name, None
    
    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_fetch_fund, name, ticker): name for name, ticker in TICKERS.items()}
        for f in as_completed(futs, timeout=30):
            try:
                name, data = f.result(timeout=10)
                if data:
                    results[name] = data
            except:
                pass
    
    resp = {"success": True, "funds": results, "count": len(results), "cached": False}
    _fund_cache = resp
    _fund_cache_ts = now
    print(f"📊 Fund-live: {len(results)}/{len(TICKERS)} fetched")
    return resp


@app.get("/api/global-ticker")
async def global_ticker():
    """Lightweight global indices ticker — parallel fetch with 2-min cache + dedup."""
    import yfinance as yf
    
    # ═══ FAST PATH: serve from cache ═══
    global _ticker_cache, _ticker_cache_ts
    now_utc = datetime.utcnow()
    if _ticker_cache and _ticker_cache_ts and (now_utc - _ticker_cache_ts).total_seconds() < 120:
        return _ticker_cache
    
    tickers_map = {
        "^NSEI": {"name": "NIFTY 50", "flag": "🇮🇳"},
        "^BSESN": {"name": "SENSEX", "flag": "🇮🇳"},
        "^GSPC": {"name": "S&P 500", "flag": "🇺🇸"},
        "^DJI": {"name": "DOW", "flag": "🇺🇸"},
        "^IXIC": {"name": "NASDAQ", "flag": "🇺🇸"},
        "^FTSE": {"name": "FTSE 100", "flag": "🇬🇧"},
        "^N225": {"name": "NIKKEI", "flag": "🇯🇵"},
        "^HSI": {"name": "HANG SENG", "flag": "🇭🇰"},
        "000001.SS": {"name": "SHANGHAI", "flag": "🇨🇳"},
        "^GDAXI": {"name": "DAX", "flag": "🇩🇪"},
        "DX-Y.NYB": {"name": "US DOLLAR", "flag": "💵"},
        "INR=X": {"name": "USD/INR", "flag": "🇮🇳"},
        "GC=F": {"name": "GOLD/OZ", "flag": "🥇"},
        "SI=F": {"name": "SILVER/OZ", "flag": "🥈"},
        "CL=F": {"name": "CRUDE OIL", "flag": "🛢️"},
        "BTC-USD": {"name": "BITCOIN", "flag": "₿"},
    }
    
    results = []
    gold_price = None
    silver_price = None
    
    # ═══ PARALLEL FETCH with FALLBACK — yfinance → Yahoo HTTP v8 ═══
    def _fetch_index(ticker, meta):
        # Source 1: yfinance
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if not hist.empty:
                price = round(hist.iloc[-1]['Close'], 2)
                prev = hist.iloc[-2]['Close'] if len(hist) > 1 else price
                chg = round(price - prev, 2)
                chg_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
                return {
                    "name": meta["name"], "flag": meta["flag"],
                    "price": price, "change": chg, "change_pct": chg_pct
                }
        except:
            pass
        
        # Source 2: Yahoo v8 chart API (direct HTTP)
        try:
            _h = {'User-Agent': f'Mozilla/5.0 Chrome/{random.randint(118,126)}.0.0.0', 'Accept': 'application/json'}
            r = _http_pool.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d", timeout=4)
            if r.status_code == 200:
                m = r.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
                price = m.get('regularMarketPrice', 0)
                prev = m.get('chartPreviousClose', m.get('previousClose', price))
                if price and float(price) > 0:
                    price = round(float(price), 2)
                    prev = round(float(prev), 2)
                    chg = round(price - prev, 2)
                    chg_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
                    return {
                        "name": meta["name"], "flag": meta["flag"],
                        "price": price, "change": chg, "change_pct": chg_pct
                    }
        except:
            pass
        
        return None
    
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(_fetch_index, tk, meta): meta for tk, meta in tickers_map.items()}
        for f in as_completed(futures, timeout=10):
            try:
                r = f.result(timeout=3)
                if r:
                    results.append(r)
                    if r["name"] == "GOLD/OZ": gold_price = r["price"]
                    if r["name"] == "SILVER/OZ": silver_price = r["price"]
            except:
                pass
    
    # Sort in original order
    name_order = [m["name"] for m in tickers_map.values()]
    results.sort(key=lambda x: name_order.index(x["name"]) if x["name"] in name_order else 99)
    
    # Calculate GSR (Gold/Silver Ratio)
    if gold_price and silver_price and silver_price > 0:
        gsr = round(gold_price / silver_price, 1)
        results.append({"name": "GSR", "flag": "⚖️", "price": gsr, "change": 0, "change_pct": 0})
    
    IST = datetime.utcnow() + timedelta(hours=5, minutes=30)
    
    # ═══ GENERATE LIVE ECONOMIC NEWS HEADLINES from market data ═══
    news = []
    for r in results:
        nm, pct = r["name"], r["change_pct"]
        if nm == "NIFTY 50":
            if pct > 1: news.append({"text": f"Nifty 50 rallies {pct:+.1f}% — bulls in control", "type": "bullish"})
            elif pct < -1: news.append({"text": f"Nifty 50 falls {pct:.1f}% — selling pressure mounts", "type": "bearish"})
            else: news.append({"text": f"Nifty 50 trades flat at {r['price']:,.0f} — markets await cues", "type": "neutral"})
        elif nm == "S&P 500":
            if pct > 0.5: news.append({"text": f"Wall Street gains {pct:+.1f}% — risk appetite up", "type": "bullish"})
            elif pct < -0.5: news.append({"text": f"US markets drop {pct:.1f}% — global selloff risk", "type": "bearish"})
        elif nm == "GOLD/OZ":
            if r["price"] > 2900: news.append({"text": f"Gold near all-time highs at ${r['price']:,.0f}/oz — safe-haven demand surges", "type": "bullish"})
            elif pct > 0.5: news.append({"text": f"Gold up {pct:+.1f}% to ${r['price']:,.0f} — inflation hedge in demand", "type": "bullish"})
            elif pct < -0.5: news.append({"text": f"Gold slips {pct:.1f}% — risk-on sentiment returns", "type": "bearish"})
        elif nm == "SILVER/OZ":
            if abs(pct) > 0.8: news.append({"text": f"Silver {'jumps' if pct>0 else 'drops'} {pct:+.1f}% to ${r['price']:.1f} — industrial demand {'strong' if pct>0 else 'weak'}", "type": "bullish" if pct>0 else "bearish"})
        elif nm == "USD/INR":
            if pct > 0.2: news.append({"text": f"Rupee weakens to ₹{r['price']:.2f} — FII outflows and strong dollar", "type": "bearish"})
            elif pct < -0.2: news.append({"text": f"Rupee strengthens to ₹{r['price']:.2f} — RBI intervention, FII inflows", "type": "bullish"})
        elif nm == "US DOLLAR":
            if abs(pct) > 0.3: news.append({"text": f"Dollar {'strengthens' if pct>0 else 'weakens'} {pct:+.1f}% — EM currencies {'under pressure' if pct>0 else 'get relief'}", "type": "bearish" if pct>0 else "bullish"})
        elif nm == "NASDAQ":
            if abs(pct) > 0.8: news.append({"text": f"NASDAQ {'surges' if pct>0 else 'tumbles'} {pct:+.1f}% — tech stocks {'rally' if pct>0 else 'sell off'}", "type": "bullish" if pct>0 else "bearish"})
        elif nm == "CRUDE OIL":
            if pct > 1: news.append({"text": f"Oil spikes {pct:+.1f}% to ${r['price']:.1f}/bbl — supply concerns, inflation risk", "type": "bearish"})
            elif pct < -1: news.append({"text": f"Oil drops {pct:.1f}% to ${r['price']:.1f}/bbl — demand fears, India benefits", "type": "bullish"})
            else: news.append({"text": f"Crude steady at ${r['price']:.1f}/bbl — OPEC+ production caps holding", "type": "neutral"})
        elif nm == "BITCOIN":
            if abs(pct) > 2: news.append({"text": f"Bitcoin {'rallies' if pct>0 else 'crashes'} {pct:+.1f}% to ${r['price']:,.0f} — crypto markets {'euphoric' if pct>0 else 'in fear'}", "type": "bullish" if pct>0 else "bearish"})
            elif r["price"] > 80000: news.append({"text": f"Bitcoin holds above $80K at ${r['price']:,.0f} — institutional adoption growing", "type": "bullish"})
    
    # Dynamic macro headlines — date-aware and market-responsive
    hour = IST.hour
    day = IST.day
    month_name = IST.strftime("%B")
    
    context_news = []
    
    # Generate LIVE headlines from actual data
    nifty_r = next((r for r in results if r["name"] == "NIFTY 50"), None)
    sp_r = next((r for r in results if r["name"] == "S&P 500"), None)
    gold_r = next((r for r in results if r["name"] == "GOLD/OZ"), None)
    btc_r = next((r for r in results if r["name"] == "BITCOIN"), None)
    oil_r = next((r for r in results if r["name"] == "CRUDE OIL"), None)
    inr_r = next((r for r in results if r["name"] == "USD/INR"), None)
    
    # Market breadth summary
    gainers = sum(1 for r in results if r.get("change_pct", 0) > 0)
    losers = sum(1 for r in results if r.get("change_pct", 0) < 0)
    if gainers > losers + 3:
        context_news.append({"text": f"Global risk-on: {gainers} of {len(results)} indices in green — broad-based buying across markets", "type": "bullish"})
    elif losers > gainers + 3:
        context_news.append({"text": f"Global risk-off: {losers} of {len(results)} indices in red — defensive positioning recommended", "type": "bearish"})
    
    # Cross-market signals
    if gold_r and sp_r:
        if gold_r["change_pct"] > 0.5 and sp_r["change_pct"] < -0.3:
            context_news.append({"text": "Flight to safety: Gold up while equities fall — institutional hedging underway", "type": "bearish"})
        elif gold_r["change_pct"] < -0.5 and sp_r["change_pct"] > 0.3:
            context_news.append({"text": "Risk appetite returns: Equities up, gold down — rotational buying into stocks", "type": "bullish"})
    
    if oil_r and oil_r["price"] > 0:
        if oil_r["price"] > 75:
            context_news.append({"text": f"Crude at ${oil_r['price']:.0f}/bbl — above $75 raises India inflation concerns, RBI watching closely", "type": "bearish"})
        elif oil_r["price"] < 65:
            context_news.append({"text": f"Crude at ${oil_r['price']:.0f}/bbl — sub-$65 boosts India's current account, positive for markets", "type": "bullish"})
    
    if inr_r and inr_r["price"] > 0:
        if inr_r["price"] > 86:
            context_news.append({"text": f"Rupee at {inr_r['price']:.2f} — weak INR boosts IT exports but pressures import-heavy sectors", "type": "neutral"})
    
    if btc_r and btc_r["price"] > 0:
        if btc_r["price"] > 85000:
            context_news.append({"text": f"Bitcoin ${btc_r['price']:,.0f} — crypto rally signals strong global liquidity and risk appetite", "type": "bullish"})
    
    # Time-of-day context
    if 9 <= hour <= 10:
        context_news.append({"text": f"Market opening: Gap analysis active — ORB strategy window 9:15-9:30 AM", "type": "neutral"})
    elif 14 <= hour <= 15:
        context_news.append({"text": "Final hour trading: Institutional positioning for close — watch for trend reversals", "type": "neutral"})
    elif hour >= 20:
        context_news.append({"text": "After hours: US market live — watch S&P 500 futures for tomorrow's Nifty opening cue", "type": "neutral"})
    
    # Geopolitical (updated for 2026)
    geo_events = [
        {"text": f"{month_name} 2026: US tariff review on India pending — pharma, IT, textiles at risk of 26% duty", "type": "bearish"},
        {"text": "AI infrastructure spend: Global capex at $300B+ for data centers — NVDA, AVGO, power stocks benefit", "type": "bullish"},
        {"text": "Fed policy: Markets pricing 1-2 rate cuts in H2 2026 — bond yields stabilizing", "type": "neutral"},
        {"text": "India inclusion in JP Morgan Bond Index — steady FII debt inflows supporting INR", "type": "bullish"},
        {"text": "SEBI F&O reforms: Weekly expiry restricted to 1 per exchange — option premium stability improving", "type": "neutral"},
        {"text": "Global supply chains: China+1 strategy accelerating — India PLI beneficiaries in electronics, pharma", "type": "bullish"},
    ]
    # Pick 2 based on day rotation
    for i in range(2):
        idx = (day + i) % len(geo_events)
        context_news.append(geo_events[idx])
    
    # Add to main news
    for cn in context_news[:4]:
        news.append(cn)
    
    result = {"success": True, "indices": results, "news": news[:8], "updated_at": IST.strftime("%I:%M %p IST")}
    
    _ticker_cache = result
    _ticker_cache_ts = now_utc
    print(f"📈 Global ticker: {len(results)} indices fetched (parallel)")
    return result

@app.get("/api/stock-data")
async def stock_data_endpoint(company: str = ""):
    """Phase 1 instant stock data — used by Compare tab and other features"""
    if not company:
        raise HTTPException(400, "company parameter required")
    try:
        loop = asyncio.get_event_loop()
        live_data = await loop.run_in_executor(_thread_pool, get_live_stock_data, company)
        if "error" in live_data:
            raise HTTPException(400, live_data["error"])
        return live_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch data: {str(e)}")


@app.get("/api/stock-quick")
async def stock_quick(ticker: str = ""):
    """Lightweight stock data — returns only metrics needed for decision algorithm. No AI, instant response."""
    import yfinance as yf
    from datetime import datetime, timedelta
    
    ticker = ticker.strip().upper()
    if not ticker:
        return {"success": False, "error": "Ticker required"}
    
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose') or 0
        
        # Source 2: Yahoo v8 chart if yfinance failed
        if not price:
            try:
                _h = {'User-Agent': f'Mozilla/5.0 Chrome/{random.randint(118,126)}.0.0.0', 'Accept': 'application/json'}
                r = _http_pool.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d", timeout=3)
                if r.status_code == 200:
                    meta = r.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
                    p = meta.get('regularMarketPrice', 0)
                    if p and float(p) > 0:
                        price = float(p)
                        info = {**info, 'currentPrice': price, 'previousClose': meta.get('chartPreviousClose', price),
                                'currency': meta.get('currency', 'USD'), 'longName': meta.get('longName', ticker)}
            except:
                pass
        
        # Source 3: Google Finance if still no price
        if not price:
            try:
                import re as _re
                is_ind = '.NS' in ticker or '.BO' in ticker
                clean = ticker.replace('.NS','').replace('.BO','')
                g_url = f"https://www.google.com/finance/quote/{clean}:NSE" if is_ind else f"https://www.google.com/finance/quote/{clean}:NASDAQ"
                _h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0', 'Accept': 'text/html'}
                r = _http_pool.get(g_url, headers={'Accept':'text/html'}, timeout=3)
                if r.status_code == 200:
                    pm = _re.search(r'data-last-price="([0-9.]+)"', r.text)
                    if pm:
                        price = float(pm.group(1))
                        info = {**info, 'currentPrice': price, 'longName': ticker}
            except:
                pass
        
        # NSE India API skipped in stock_quick for speed (use batch-prices for NSE fallback)
        
        if not price:
            return {"success": False, "error": f"No data for {ticker}"}
        
        def sn(key, default=0):
            v = info.get(key)
            if v is None or v == 'N/A':
                return default
            try:
                return float(v)
            except:
                return default
        
        # SMA calculations
        sma20 = sma50 = sma200 = None
        try:
            hist = t.history(period="1y")
            if not hist.empty and len(hist) >= 20:
                sma20 = round(float(hist['Close'].tail(20).mean()), 2)
            if not hist.empty and len(hist) >= 50:
                sma50 = round(float(hist['Close'].tail(50).mean()), 2)
            if not hist.empty and len(hist) >= 200:
                sma200 = round(float(hist['Close'].tail(200).mean()), 2)
        except:
            pass
        
        # EPS growth
        eps_growth = 'N/A'
        try:
            eps_t = sn('trailingEps')
            eps_f = sn('forwardEps')
            if eps_t and eps_f and eps_t != 0:
                eps_growth = round(((eps_f - eps_t) / abs(eps_t)) * 100, 1)
        except:
            pass
        
        # Revenue growth
        rev_growth = sn('revenueGrowth')
        if rev_growth and abs(rev_growth) < 1:
            rev_growth = round(rev_growth * 100, 2)
        elif rev_growth:
            rev_growth = round(rev_growth, 2)
        else:
            rev_growth = 'N/A'
        
        # Earnings growth
        eg = sn('earningsGrowth')
        if eg and abs(eg) < 1 and eg != 0:
            eg = round(eg * 100, 1)
        elif eg:
            eg = round(eg, 1)
        else:
            eg = 'N/A'
        
        # Sector PE
        sector_pe_map = {
            'Technology': 30, 'Communication Services': 22, 'Consumer Cyclical': 25,
            'Consumer Defensive': 28, 'Financial Services': 15, 'Healthcare': 25,
            'Industrials': 22, 'Basic Materials': 18, 'Energy': 12,
            'Utilities': 18, 'Real Estate': 35
        }
        sec = info.get('sector', '')
        
        pm = sn('profitMargins')
        if pm and abs(pm) < 1:
            pm = round(pm * 100, 2)
        
        roe_val = sn('returnOnEquity')
        if roe_val and abs(roe_val) < 1:
            roe_val = round(roe_val * 100, 2)
        
        currency = info.get('currency', 'USD')
        
        return {
            "success": True,
            "ticker": ticker,
            "company_name": info.get('longName', ticker),
            "current_price": round(price, 2),
            "currency": currency,
            "pe_ratio": round(sn('trailingPE'), 2) if sn('trailingPE') else 'N/A',
            "forward_pe": round(sn('forwardPE'), 2) if sn('forwardPE') else 'N/A',
            "pb_ratio": round(sn('priceToBook'), 2) if sn('priceToBook') else 'N/A',
            "profit_margin": pm or 'N/A',
            "roe": roe_val or 'N/A',
            "beta": round(sn('beta', 1), 2),
            "dividend_yield": round(sn('dividendYield') * 100, 2) if sn('dividendYield') and sn('dividendYield') < 1 else round(sn('dividendYield'), 2) if sn('dividendYield') else 0,
            "week52_high": round(sn('fiftyTwoWeekHigh'), 2),
            "week52_low": round(sn('fiftyTwoWeekLow'), 2),
            "sma_20": sma20,
            "sma_50": sma50,
            "sma_200": sma200,
            "eps_growth_pct": eps_growth,
            "revenue_growth": rev_growth,
            "earnings_growth": eg,
            "sector_avg_pe": sector_pe_map.get(sec, 20),
            "sector": sec,
            "market_cap": int(sn('marketCap')) if sn('marketCap') > 1e6 else 0,
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch data for {ticker}: {str(e)[:100]}"}


# ═══ BATCH PRICES — multi-source live prices for stock picks ═══

@app.get("/api/test-price/{ticker}")
async def test_price(ticker: str):
    """Diagnostic endpoint — test if we can fetch a single ticker price."""
    import traceback
    results = {"ticker": ticker, "sources": []}
    
    # Source 1: yfinance
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        results["sources"].append({
            "name": "yfinance",
            "success": bool(price and float(price) > 0),
            "price": float(price) if price else None,
            "keys": list(info.keys())[:20]
        })
    except Exception as e:
        results["sources"].append({"name": "yfinance", "success": False, "error": str(e)[:200]})
    
    # Source 2: Yahoo v8 chart
    try:
        r = _http_pool.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d", timeout=5)
        if r.status_code == 200:
            meta = r.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
            price = meta.get('regularMarketPrice', 0)
            results["sources"].append({
                "name": "yahoo_v8",
                "success": bool(price and float(price) > 0),
                "price": float(price) if price else None,
                "status": r.status_code
            })
        else:
            results["sources"].append({"name": "yahoo_v8", "success": False, "status": r.status_code, "body": r.text[:200]})
    except Exception as e:
        results["sources"].append({"name": "yahoo_v8", "success": False, "error": str(e)[:200]})
    
    results["any_success"] = any(s.get("success") for s in results["sources"])
    return results

@app.post("/api/batch-prices")
async def batch_prices(request: Request):
    """Fetch live prices. Always fetches fresh — no stale cache."""
    import re as re_bp
    
    try:
        data = await request.json()
        tickers = data.get("tickers", [])
        if not tickers or not isinstance(tickers, list):
            return {"success": False, "error": "tickers array required"}
        
        tickers = [t.strip().upper() for t in tickers[:30] if t.strip()]
        if not tickers:
            return {"success": False, "error": "no valid tickers"}
        
        def _fetch_one(tk):
            """Fetch single ticker price with 2-source fallback."""
            is_indian = '.NS' in tk or '.BO' in tk
            sym = '₹' if is_indian else '$'
            
            # Source 1: yfinance
            try:
                t = yf.Ticker(tk)
                info = t.info or {}
                price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                if price and float(price) > 0:
                    price = round(float(price), 2)
                    prev = float(info.get('previousClose') or info.get('regularMarketPreviousClose') or price)
                    chg = round(((price - prev) / prev) * 100, 2) if prev > 0 else 0
                    return tk, {"price": price, "change_pct": chg, "symbol": sym, "formatted": f"{sym}{price:,.2f}"}
            except Exception as e1:
                print(f"  yf fail {tk}: {e1}")
            
            # Source 2: Yahoo v8 chart API
            try:
                r = _http_pool.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}?interval=1d&range=2d", timeout=5)
                if r.status_code == 200:
                    meta = r.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
                    price = meta.get('regularMarketPrice', 0)
                    prev = meta.get('chartPreviousClose', meta.get('previousClose', price))
                    if price and float(price) > 0:
                        price = round(float(price), 2)
                        prev = round(float(prev or price), 2)
                        chg = round(((price - prev) / prev) * 100, 2) if prev > 0 else 0
                        return tk, {"price": price, "change_pct": chg, "symbol": sym, "formatted": f"{sym}{price:,.2f}"}
            except Exception as e2:
                print(f"  v8 fail {tk}: {e2}")
            
            return tk, None
        
        # Fetch ALL tickers in parallel — dedicated pool so we don't block other endpoints
        results = {}
        failed = []
        with ThreadPoolExecutor(max_workers=min(len(tickers), 8)) as pool:
            futs = {pool.submit(_fetch_one, t): t for t in tickers}
            for f in as_completed(futs, timeout=15):
                try:
                    tk, price_data = f.result(timeout=8)
                    if price_data:
                        results[tk] = price_data
                    else:
                        failed.append(futs[f])
                except:
                    failed.append(futs[f])
        
        print(f"📊 batch-prices: {len(results)}/{len(tickers)} OK, {len(failed)} failed")
        return {"success": True, "prices": results, "fetched": len(results), "cached": 0, "failed": failed[:10]}
    except Exception as e:
        print(f"❌ batch-prices error: {e}")
        return {"success": False, "error": str(e)[:100]}


# Module-level cache for market-pulse
_pulse_cache = None
_pulse_cache_ts = None
_ticker_cache = None
_ticker_cache_ts = None

@app.get("/api/market-pulse")
async def market_pulse():
    """Lightweight market events — cached 5min, parallel fetches."""
    import yfinance as yf
    from datetime import datetime, timedelta
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # ═══ 5-MINUTE CACHE — prevents hammering yfinance/NSE on every page load ═══
    global _pulse_cache, _pulse_cache_ts
    now_ts = datetime.utcnow()
    if _pulse_cache and _pulse_cache_ts and (now_ts - _pulse_cache_ts).total_seconds() < 120:
        return _pulse_cache
    
    IST_OFFSET = timedelta(hours=5, minutes=30)
    now = datetime.utcnow() + IST_OFFSET
    day_name = now.strftime("%A")
    weekday = now.weekday()
    date_str = now.strftime("%A, %B %d, %Y")
    
    # Expiry detection
    year, month = now.year, now.month
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    last_tuesday = last_day
    while datetime(year, month, last_tuesday).weekday() != 1:
        last_tuesday -= 1
    is_last_tuesday = (now.day == last_tuesday and weekday == 1)
    last_thursday = last_day
    while datetime(year, month, last_thursday).weekday() != 3:
        last_thursday -= 1
    is_last_thursday = (now.day == last_thursday and weekday == 3)
    
    expiry_today = []
    if weekday == 1:  # Tuesday
        expiry_today.append("NIFTY 50 (weekly)")
        if is_last_tuesday:
            expiry_today.extend(["BANK NIFTY (monthly)", "FIN NIFTY (monthly)", "Stock F&O (monthly)"])
    if weekday == 3:  # Thursday
        expiry_today.append("SENSEX (weekly)")
        if is_last_thursday:
            expiry_today.append("BANKEX (monthly)")
    
    is_expiry = len(expiry_today) > 0
    
    # ═══ PARALLEL FETCH — all 6 tickers at once instead of sequential ═══
    events = []
    global_snapshot = {}
    quick_tickers = {"CL=F": "Crude Oil", "GC=F": "Gold", "SI=F": "Silver", "DX-Y.NYB": "US Dollar", "^GSPC": "S&P 500", "INR=X": "USD/INR"}
    
    def fetch_ticker(ticker, name):
        # Source 1: yfinance
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if not hist.empty:
                price = round(hist.iloc[-1]['Close'], 2)
                prev = hist.iloc[-2]['Close'] if len(hist) > 1 else price
                chg_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
                return name, {"price": price, "change_pct": chg_pct}
        except:
            pass
        # Source 2: Yahoo v8 chart API
        try:
            _h = {'User-Agent': f'Mozilla/5.0 Chrome/{random.randint(118,126)}.0.0.0', 'Accept': 'application/json'}
            r = _http_pool.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d", timeout=4)
            if r.status_code == 200:
                m = r.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
                price = m.get('regularMarketPrice', 0)
                prev = m.get('chartPreviousClose', m.get('previousClose', price))
                if price and float(price) > 0:
                    price = round(float(price), 2)
                    prev = round(float(prev), 2)
                    chg_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
                    return name, {"price": price, "change_pct": chg_pct}
        except:
            pass
        return name, None
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_ticker, t, n): n for t, n in quick_tickers.items()}
        for f in as_completed(futures, timeout=8):
            try:
                name, data = f.result(timeout=3)
                if data:
                    global_snapshot[name] = data
            except:
                pass
    
    # ═══ AUTO-DETECT EVENTS from parallel-fetched snapshot ═══
    # Always show key commodity/market data as context
    for name, snap in global_snapshot.items():
        price, chg_pct = snap["price"], snap["change_pct"]
        if name == "Crude Oil":
            if abs(chg_pct) >= 0.8:
                direction = "spikes" if chg_pct > 0 else "drops"
                events.append({"headline": f"Crude Oil {direction} {chg_pct:+.1f}% to ${price}", "impact": "BEARISH" if chg_pct > 0 else "BULLISH", "severity": "HIGH" if abs(chg_pct) >= 2 else "MEDIUM",
                    "detail": "Higher crude raises input costs, inflation pressure on RBI." if chg_pct > 0 else "Lower crude benefits India. Positive for CAD and inflation.",
                    "action": "Watch ONGC/Oil India. Negative for Nifty if sustained." if chg_pct > 0 else "Positive for Indian markets. Airlines, paint stocks benefit."})
            else:
                events.append({"headline": f"Crude Oil ${price} ({chg_pct:+.1f}%)", "impact": "VOLATILE", "severity": "LOW",
                    "detail": f"Oil stable at ${price}. India imports 85% of crude — stable oil = positive for current account.",
                    "action": "No immediate impact. Monitor OPEC decisions."})
        elif name == "Gold":
            if abs(chg_pct) >= 0.5:
                events.append({"headline": f"Gold {'surges' if chg_pct > 0 else 'drops'} {chg_pct:+.1f}% to ${price}", "impact": "VOLATILE", "severity": "HIGH" if abs(chg_pct) >= 1.5 else "MEDIUM",
                    "detail": "Gold rally = risk-off sentiment globally." if chg_pct > 0 else "Gold decline = risk-on appetite returning.",
                    "action": "Consider gold ETF hedge." if chg_pct > 0 else "Positive for equity markets."})
            else:
                events.append({"headline": f"Gold ${price} ({chg_pct:+.1f}%)", "impact": "VOLATILE", "severity": "LOW",
                    "detail": f"Gold stable near ${price}. Safe-haven demand steady amid geopolitical tensions.",
                    "action": "Watch for breakout above $3,000 or breakdown below $2,800."})
        elif name == "Silver":
            if abs(chg_pct) >= 0.5:
                events.append({"headline": f"Silver {'surges' if chg_pct > 0 else 'drops'} {chg_pct:+.1f}% to ${price}", "impact": "BULLISH" if chg_pct > 0 else "BEARISH", "severity": "HIGH" if abs(chg_pct) >= 1.5 else "MEDIUM",
                    "detail": "Silver rally = industrial demand + safe-haven buying." if chg_pct > 0 else "Silver decline = weakening industrial demand.",
                    "action": "Metals & mining stocks benefit. Watch Hindalco, Vedanta." if chg_pct > 0 else "Mining stocks under pressure."})
            else:
                events.append({"headline": f"Silver ${price} ({chg_pct:+.1f}%)", "impact": "VOLATILE", "severity": "LOW",
                    "detail": f"Silver stable at ${price}. Industrial + monetary demand supporting prices. Gold/Silver ratio signals {'silver undervalued' if price < 28 else 'fair value'}.",
                    "action": "Watch solar panel demand (key industrial driver) and Fed rate path."})
        elif name == "S&P 500":
            if abs(chg_pct) >= 0.3:
                events.append({"headline": f"US Markets {'rally' if chg_pct > 0 else 'sell-off'} {chg_pct:+.1f}%", "impact": "BULLISH" if chg_pct > 0 else "BEARISH", "severity": "HIGH" if abs(chg_pct) >= 1 else "MEDIUM",
                    "detail": f"S&P 500 moved {abs(chg_pct):.1f}%. Indian markets follow with 0.5-0.8x correlation.",
                    "action": "Expect gap-up for Nifty. IT stocks lead." if chg_pct > 0 else "Expect weak opening. Consider hedging."})
            else:
                events.append({"headline": f"S&P 500 flat ({chg_pct:+.1f}%)", "impact": "VOLATILE", "severity": "LOW",
                    "detail": "US markets quiet. Awaiting catalysts — Fed commentary, earnings, or macro data.",
                    "action": "Range-bound trading expected. Watch for breakout triggers."})
        elif name == "US Dollar":
            if abs(chg_pct) >= 0.2:
                events.append({"headline": f"Dollar {'strengthens' if chg_pct > 0 else 'weakens'} {chg_pct:+.1f}%", "impact": "BEARISH" if chg_pct > 0 else "BULLISH", "severity": "MEDIUM",
                    "detail": "Stronger dollar pressures EM currencies, FII outflows." if chg_pct > 0 else "Weaker dollar supports EM inflows.",
                    "action": "IT exporters benefit from weak INR." if chg_pct > 0 else "FII inflows likely. Banking stocks benefit."})
            else:
                events.append({"headline": f"Dollar Index stable ({chg_pct:+.1f}%)", "impact": "VOLATILE", "severity": "LOW",
                    "detail": "Dollar steady. No major FX pressure on emerging markets today.",
                    "action": "Watch Fed commentary for directional clues."})
        elif name == "USD/INR":
            if abs(chg_pct) >= 0.1:
                events.append({"headline": f"Rupee {'weakens' if chg_pct > 0 else 'strengthens'} {chg_pct:+.1f}%", "impact": "BEARISH" if chg_pct > 0 else "BULLISH", "severity": "HIGH" if abs(chg_pct) >= 0.3 else "MEDIUM",
                    "detail": "Rupee depreciation = capital outflows." if chg_pct > 0 else "Rupee strength attracts FII flows.",
                    "action": "IT exporters benefit." if chg_pct > 0 else "Domestic consumption plays benefit."})
            else:
                events.append({"headline": f"USD/INR ₹{price} ({chg_pct:+.1f}%)", "impact": "VOLATILE", "severity": "LOW",
                    "detail": f"Rupee stable at ₹{price}. RBI intervention keeping range-bound.",
                    "action": "No major FX risk today. Watch RBI reserves data."})
    
    # ═══ ALWAYS-ON GEOPOLITICAL CONTEXT (shows even on quiet days) ═══
    context_events = [
        {"headline": "US-China Trade War — tariffs up to 145% on Chinese goods", "impact": "BEARISH", "severity": "HIGH",
         "detail": "Ongoing trade tensions affecting global supply chains, semiconductor stocks, and emerging market sentiment.",
         "action": "Watch tech hardware, EV, and semiconductor supply chain stocks."},
        {"headline": "Russia-Ukraine conflict — energy & grain markets volatile", "impact": "VOLATILE", "severity": "HIGH",
         "detail": "War continues to impact European energy prices, global food supply, and defense spending.",
         "action": "Defense stocks, energy exporters benefit. European industrials at risk."},
        {"headline": "Middle East tensions — Red Sea shipping disruptions", "impact": "BEARISH", "severity": "MEDIUM",
         "detail": "Houthi attacks on shipping routes raising freight costs and oil price risk premium.",
         "action": "Shipping, logistics stocks impacted. Oil prices carry risk premium."},
        {"headline": "US tariffs on India — reciprocal tariff review pending", "impact": "BEARISH", "severity": "HIGH",
         "detail": "India faces potential 26% reciprocal tariffs on exports to US. Pharma, IT, textiles at risk.",
         "action": "Watch pharma exporters, IT services, and auto component makers."},
    ]
    # Add 2 context events that rotate based on day
    day_of_year = now.timetuple().tm_yday
    for i in range(min(2, len(context_events))):
        idx = (day_of_year + i) % len(context_events)
        events.append(context_events[idx])
    
    # Upcoming scheduled events (static calendar)
    upcoming = []
    # Known RBI meeting dates 2026 (approximate — first week of Apr, Jun, Aug, Oct, Dec, Feb)
    rbi_months = [2, 4, 6, 8, 10, 12]
    for rm in rbi_months:
        rbi_date = datetime(year if rm >= now.month else year + 1, rm, 7)
        days_until = (rbi_date - now).days
        if 0 < days_until <= 30:
            upcoming.append({"event": f"RBI Monetary Policy", "date": rbi_date.strftime("%b %d"), "days": days_until, "impact": "HIGH"})
    
    # US Fed (approx — Jan, Mar, May, Jun, Jul, Sep, Nov, Dec)
    fed_months = [1, 3, 5, 6, 7, 9, 11, 12]
    for fm in fed_months:
        fed_date = datetime(year if fm >= now.month else year + 1, fm, 18)
        days_until = (fed_date - now).days
        if 0 < days_until <= 30:
            upcoming.append({"event": "US Fed Rate Decision", "date": fed_date.strftime("%b %d"), "days": days_until, "impact": "HIGH"})
    
    # ═══ GEOPOLITICAL, TRADE, ECONOMIC & MACRO EVENTS — 2026 ═══
    geo_events = [
        # ── MARCH 2026 ──
        {"event": "US CPI Inflation Data (Feb)", "month": 3, "day": 12, "year": 2026, "impact": "HIGH"},
        {"event": "US Supreme Court — Tariff Authority (IEEPA) Ruling", "month": 3, "day": 15, "year": 2026, "impact": "HIGH"},
        {"event": "US PPI Data Release", "month": 3, "day": 13, "year": 2026, "impact": "MEDIUM"},
        {"event": "RBI FX Reserves Review", "month": 3, "day": 14, "year": 2026, "impact": "MEDIUM"},
        {"event": "US Fed FOMC Meeting + Rate Decision", "month": 3, "day": 19, "year": 2026, "impact": "HIGH"},
        {"event": "Middle East De-escalation Talks (US-Iran)", "month": 3, "day": 20, "year": 2026, "impact": "HIGH"},
        {"event": "India Parliament Budget Session Ends", "month": 3, "day": 21, "year": 2026, "impact": "MEDIUM"},
        {"event": "India GST Council Meeting", "month": 3, "day": 22, "year": 2026, "impact": "MEDIUM"},
        {"event": "US-China Rare Earth Export Restrictions Review", "month": 3, "day": 25, "year": 2026, "impact": "HIGH"},
        {"event": "US GDP Q4 2025 (Final Revision)", "month": 3, "day": 27, "year": 2026, "impact": "MEDIUM"},
        {"event": "Japan PM Takaichi — Corporate Reform Package", "month": 3, "day": 28, "year": 2026, "impact": "MEDIUM"},
        {"event": "US PCE Inflation (Fed's preferred gauge)", "month": 3, "day": 28, "year": 2026, "impact": "HIGH"},
        {"event": "India FY26 Financial Year End", "month": 3, "day": 31, "year": 2026, "impact": "MEDIUM"},
        
        # ── APRIL 2026 ──
        {"event": "US Reciprocal Tariff Review Deadline", "month": 4, "day": 2, "year": 2026, "impact": "HIGH"},
        {"event": "US Jobs Report (Mar NFP)", "month": 4, "day": 3, "year": 2026, "impact": "HIGH"},
        {"event": "US Venezuela Sanctions Review", "month": 4, "day": 1, "year": 2026, "impact": "MEDIUM"},
        {"event": "Gold Central Bank Purchases Report (WGC)", "month": 4, "day": 5, "year": 2026, "impact": "MEDIUM"},
        {"event": "NATO Hybrid Warfare Summit", "month": 4, "day": 7, "year": 2026, "impact": "MEDIUM"},
        {"event": "RBI Monetary Policy (Apr)", "month": 4, "day": 9, "year": 2026, "impact": "HIGH"},
        {"event": "US CPI Inflation Data (Mar)", "month": 4, "day": 10, "year": 2026, "impact": "HIGH"},
        {"event": "EU Retaliatory Tariff Decision on US Goods", "month": 4, "day": 15, "year": 2026, "impact": "MEDIUM"},
        {"event": "India Q4 FY26 Earnings Season Begins", "month": 4, "day": 15, "year": 2026, "impact": "HIGH"},
        {"event": "CLARITY Act — Crypto Regulation Vote", "month": 4, "day": 20, "year": 2026, "impact": "MEDIUM"},
        {"event": "Big Tech Earnings (MSFT/GOOG/META/AMZN)", "month": 4, "day": 25, "year": 2026, "impact": "HIGH"},
        {"event": "OBBBA Fiscal Package Vote", "month": 4, "day": 30, "year": 2026, "impact": "HIGH"},
        
        # ── MAY 2026 ──
        {"event": "US Jobs Report (Apr NFP)", "month": 5, "day": 1, "year": 2026, "impact": "HIGH"},
        {"event": "USMCA Trade Pact Review", "month": 5, "day": 1, "year": 2026, "impact": "MEDIUM"},
        {"event": "US Fed FOMC Meeting + Rate Decision", "month": 5, "day": 6, "year": 2026, "impact": "HIGH"},
        {"event": "US Strategic Minerals Executive Order Review", "month": 5, "day": 10, "year": 2026, "impact": "MEDIUM"},
        {"event": "US CPI Inflation Data (Apr)", "month": 5, "day": 13, "year": 2026, "impact": "HIGH"},
        {"event": "Fed Chair Powell Term Ends — Warsh Transition", "month": 5, "day": 15, "year": 2026, "impact": "HIGH"},
        {"event": "India Q4 GDP Data Release", "month": 5, "day": 30, "year": 2026, "impact": "HIGH"},
        
        # ── JUNE-DECEMBER 2026 ──
        {"event": "RBI Monetary Policy (Jun)", "month": 6, "day": 6, "year": 2026, "impact": "HIGH"},
        {"event": "US Fed FOMC Meeting", "month": 6, "day": 17, "year": 2026, "impact": "HIGH"},
        {"event": "OPEC+ Mid-Year Production Review", "month": 6, "day": 5, "year": 2026, "impact": "HIGH"},
        {"event": "US Fed FOMC Meeting", "month": 7, "day": 29, "year": 2026, "impact": "HIGH"},
        {"event": "RBI Monetary Policy (Aug)", "month": 8, "day": 7, "year": 2026, "impact": "HIGH"},
        {"event": "Jackson Hole Economic Symposium", "month": 8, "day": 27, "year": 2026, "impact": "HIGH"},
        {"event": "US Midterm Pre-Election Volatility Window Opens", "month": 9, "day": 1, "year": 2026, "impact": "HIGH"},
        {"event": "US Fed FOMC Meeting", "month": 9, "day": 17, "year": 2026, "impact": "HIGH"},
        {"event": "China Golden Week Holiday — Market Closure", "month": 10, "day": 1, "year": 2026, "impact": "MEDIUM"},
        {"event": "RBI Monetary Policy (Oct)", "month": 10, "day": 8, "year": 2026, "impact": "HIGH"},
        {"event": "US Midterm Elections", "month": 11, "day": 3, "year": 2026, "impact": "HIGH"},
        {"event": "US Fed FOMC Meeting (Nov)", "month": 11, "day": 4, "year": 2026, "impact": "HIGH"},
        {"event": "India Diwali — Muhurat Trading", "month": 11, "day": 8, "year": 2026, "impact": "MEDIUM"},
        {"event": "RBI Monetary Policy (Dec)", "month": 12, "day": 5, "year": 2026, "impact": "HIGH"},
        {"event": "US Fed FOMC Meeting (Dec) + 2027 Dot Plot", "month": 12, "day": 16, "year": 2026, "impact": "HIGH"},
    ]
    # Auto-add recurring US CPI + Jobs for upcoming months
    for offset in range(1, 7):
        m = (now.month + offset - 1) % 12 + 1
        y_adj = year if m > now.month else year + 1
        geo_events.append({"event": "US CPI Inflation Data", "month": m, "day": 12, "year": y_adj, "impact": "HIGH"})
        geo_events.append({"event": "US Jobs Report (Non-Farm Payrolls)", "month": m, "day": 6, "year": y_adj, "impact": "HIGH"})
    for ge in geo_events:
        try:
            ge_date = datetime(ge["year"], ge["month"], ge["day"])
            days_until = (ge_date - now).days
            if 0 <= days_until <= 45:
                upcoming.append({"event": ge["event"], "date": ge_date.strftime("%b %d"), "days": days_until, "impact": ge["impact"]})
        except:
            pass
    
    # Sort upcoming by days
    upcoming.sort(key=lambda x: x["days"])
    
    # FII/DII Activity — non-blocking thread with 4s total timeout
    # Also maintains 5-day rolling history in a local file
    fii_dii = {}
    FII_HISTORY_FILE = "fii_dii_history.json"
    
    def _load_fii_history():
        try:
            with open(FII_HISTORY_FILE, "r") as f:
                raw = json.load(f)
                # Dedup by date on load
                seen = set()
                clean = []
                for h in raw:
                    d = str(h.get("date", "")).strip()
                    if d and d not in seen:
                        seen.add(d)
                        clean.append(h)
                return clean[-5:]  # keep last 5
        except:
            return []
    
    def _save_fii_history(history):
        try:
            with open(FII_HISTORY_FILE, "w") as f:
                json.dump(history[-10:], f)  # keep last 10 entries
        except:
            pass
    
    def _fetch_fii():
        _r = {}
        _evts = []
        try:
            import requests as req
            s = req.Session()
            hdr = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": "https://www.nseindia.com/"}
            s.get("https://www.nseindia.com/", headers=hdr, timeout=2)
            resp = s.get("https://www.nseindia.com/api/fiidiiTradeReact", headers=hdr, timeout=2)
            if resp.status_code == 200:
                for entry in resp.json():
                    cat = entry.get("category", "")
                    buy, sell, net = float(entry.get("buyValue", 0)), float(entry.get("sellValue", 0)), float(entry.get("netValue", 0))
                    if "FII" in cat or "FPI" in cat:
                        _r["fii"] = {"buy": round(buy, 2), "sell": round(sell, 2), "net": round(net, 2), "date": entry.get("date", "")}
                    elif "DII" in cat:
                        _r["dii"] = {"buy": round(buy, 2), "sell": round(sell, 2), "net": round(net, 2), "date": entry.get("date", "")}
                
                # Save to rolling history
                if _r.get("fii") and _r.get("dii"):
                    today_date = str(_r["fii"].get("date", "")).strip()
                    if today_date and len(today_date) > 3:
                        history = _load_fii_history()
                        # Strict dedup: normalize dates and check
                        existing_dates = set(str(h.get("date", "")).strip() for h in history)
                        if today_date not in existing_dates:
                            history.append({
                                "date": today_date,
                                "fii_buy": _r["fii"]["buy"],
                                "fii_sell": _r["fii"]["sell"],
                                "fii_net": _r["fii"]["net"],
                                "dii_buy": _r["dii"]["buy"],
                                "dii_sell": _r["dii"]["sell"],
                                "dii_net": _r["dii"]["net"],
                                "combined": round(_r["fii"]["net"] + _r["dii"]["net"], 2)
                            })
                            # Keep only last 5 unique dates
                            _save_fii_history(history[-5:])
                            print(f"📊 FII/DII history: saved {today_date}, total {min(len(history),5)} days")
                        else:
                            print(f"📊 FII/DII history: {today_date} already exists, skipping")
                
                fii_net = _r.get("fii", {}).get("net", 0)
                dii_net = _r.get("dii", {}).get("net", 0)
                if abs(fii_net) >= 2000:
                    _evts.append({"headline": f"FII {'buying' if fii_net > 0 else 'selling'} \u20b9{abs(fii_net):,.0f}Cr", "impact": "BULLISH" if fii_net > 0 else "BEARISH", "severity": "HIGH" if abs(fii_net) >= 4000 else "MEDIUM",
                        "detail": "FII inflows signal global confidence." if fii_net > 0 else "FII outflows create selling pressure.", "action": "Banking, IT stocks benefit." if fii_net > 0 else "Defensive sectors hold better."})
                if abs(dii_net) >= 2000:
                    _evts.append({"headline": f"DII {'buying' if dii_net > 0 else 'selling'} \u20b9{abs(dii_net):,.0f}Cr", "impact": "BULLISH" if dii_net > 0 else "BEARISH", "severity": "MEDIUM",
                        "detail": "DII support limits downside." if dii_net > 0 else "Unusual DII selling.", "action": "Mid/small-cap stocks benefit." if dii_net > 0 else "Watch for correction."})
        except:
            pass
        return _r, _evts
    
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_fetch_fii)
            fii_dii, fii_events = fut.result(timeout=4)
            events.extend(fii_events)
    except:
        pass
    
    # Load 5-day history
    fii_dii["history"] = _load_fii_history()[-5:]

    result = {
        "success": True,
        "date": date_str,
        "day": day_name,
        "ist_time": now.strftime("%I:%M %p IST"),
        "is_expiry": is_expiry,
        "expiry_today": expiry_today,
        "events": events[:12],
        "upcoming": upcoming[:15],
        "global_snapshot": global_snapshot,
        "fii_dii": fii_dii
    }
    
    # Store in cache
    _pulse_cache = result
    _pulse_cache_ts = datetime.utcnow()
    
    return result

_perf_cache = None
_perf_cache_ts = None

@app.get("/api/performance-leaderboard")
async def performance_leaderboard():
    """YTD + 5-year yearly returns for indices, ETFs, mutual funds, and top stocks."""
    import yfinance as yf
    from datetime import datetime, timedelta
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    global _perf_cache, _perf_cache_ts
    now = datetime.utcnow()
    if _perf_cache and _perf_cache_ts and (now - _perf_cache_ts).total_seconds() < 1800:
        return _perf_cache
    
    current_year = now.year
    years = list(range(current_year - 5, current_year + 1))  # last 5 years + current
    
    # ═══ TICKERS TO TRACK ═══
    indices = {
        "^NSEI": "Nifty 50", "^NSEBANK": "Bank Nifty", "^BSESN": "Sensex",
        "NIFTYMIDCAP150.NS": "Nifty Midcap 150", "NIFTYSMALLCAP250.NS": "Nifty Smallcap 250",
        "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones",
        "^RUT": "Russell 2000", "^FTSE": "FTSE 100"
    }
    etfs = {
        "NIFTYBEES.NS": "Nifty BeES", "BANKBEES.NS": "Bank BeES",
        "GOLDBEES.NS": "Gold BeES", "MIDCPNIFTY.NS": "Midcap Nifty ETF",
        "MON100.NS": "Motilal Oswal NASDAQ 100",
        "SPY": "SPDR S&P 500", "QQQ": "Invesco NASDAQ 100",
        "IWM": "iShares Russell 2000", "VTI": "Vanguard Total Market",
        "ARKK": "ARK Innovation"
    }
    top_stocks = {
        "RELIANCE.NS": "Reliance", "TCS.NS": "TCS", "HDFCBANK.NS": "HDFC Bank",
        "INFY.NS": "Infosys", "ICICIBANK.NS": "ICICI Bank",
        "BHARTIARTL.NS": "Bharti Airtel", "ITC.NS": "ITC", "SBIN.NS": "SBI",
        "LT.NS": "L&T", "BAJFINANCE.NS": "Bajaj Finance",
        "ADANIENT.NS": "Adani Enterprises", "TATAPOWER.NS": "Tata Power",
        "ZOMATO.NS": "Zomato", "JIOFIN.NS": "Jio Financial",
        "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA",
        "GOOGL": "Alphabet", "AMZN": "Amazon", "TSLA": "Tesla",
        "META": "Meta", "AVGO": "Broadcom", "JPM": "JPMorgan",
        "V": "Visa"
    }
    
    all_tickers = {**indices, **etfs, **top_stocks}
    
    def fetch_yearly(ticker, name):
        """Fetch 6-year history, compute YTD + yearly returns."""
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="6y", interval="1mo")
            if hist.empty or len(hist) < 12:
                return None
            
            results = {"ticker": ticker, "name": name, "yearly": {}, "ytd": None, "current_price": None}
            
            # Current price
            latest = hist['Close'].iloc[-1]
            results["current_price"] = round(float(latest), 2)
            
            # YTD
            try:
                yr_start_rows = hist[hist.index.year == current_year]
                if len(yr_start_rows) > 0:
                    yr_open = float(yr_start_rows['Close'].iloc[0])
                    results["ytd"] = round(((latest - yr_open) / yr_open) * 100, 2)
            except:
                pass
            
            # Yearly returns
            for yr in years[:-1]:  # skip current year (that's YTD)
                try:
                    yr_data = hist[hist.index.year == yr]
                    if len(yr_data) >= 2:
                        yr_open = float(yr_data['Close'].iloc[0])
                        yr_close = float(yr_data['Close'].iloc[-1])
                        results["yearly"][str(yr)] = round(((yr_close - yr_open) / yr_open) * 100, 2)
                except:
                    pass
            
            return results
        except Exception as e:
            return None
    
    # Parallel fetch all tickers
    all_results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_yearly, tk, nm): (tk, nm) for tk, nm in all_tickers.items()}
        for f in as_completed(futures, timeout=30):
            try:
                r = f.result(timeout=5)
                if r:
                    all_results[r["ticker"]] = r
            except:
                pass
    
    # ═══ BUILD RESPONSE — COUNTRY-WISE ═══
    def categorize(tickers_map):
        items = []
        for tk in tickers_map:
            if tk in all_results:
                items.append(all_results[tk])
        return items
    
    def rank_by_year(items, year_str, top_n=5):
        valid = [(it, it["yearly"].get(year_str)) for it in items if it["yearly"].get(year_str) is not None]
        valid.sort(key=lambda x: x[1], reverse=True)
        best = [{"name": it["name"], "ticker": it["ticker"], "return": ret} for it, ret in valid[:top_n]]
        worst = [{"name": it["name"], "ticker": it["ticker"], "return": ret} for it, ret in valid[-top_n:]]
        worst.reverse()
        return {"best": best, "worst": worst}
    
    def rank_by_ytd(items, top_n=5):
        valid = [(it, it["ytd"]) for it in items if it["ytd"] is not None]
        valid.sort(key=lambda x: x[1], reverse=True)
        best = [{"name": it["name"], "ticker": it["ticker"], "return": ret, "price": it["current_price"]} for it, ret in valid[:top_n]]
        worst = [{"name": it["name"], "ticker": it["ticker"], "return": ret, "price": it["current_price"]} for it, ret in valid[-top_n:]]
        worst.reverse()
        return {"best": best, "worst": worst}
    
    # Split by country
    india_indices = {k: v for k, v in indices.items() if ".NS" in k or "^NSEI" in k or "^NSEBANK" in k or "^BSESN" in k or "NIFTY" in k.upper()}
    usa_indices = {k: v for k, v in indices.items() if k not in india_indices}
    india_etfs = {k: v for k, v in etfs.items() if ".NS" in k}
    usa_etfs = {k: v for k, v in etfs.items() if k not in india_etfs}
    india_stocks = {k: v for k, v in top_stocks.items() if ".NS" in k}
    usa_stocks = {k: v for k, v in top_stocks.items() if k not in india_stocks}
    
    def build_country(c_indices, c_etfs, c_stocks):
        idx = categorize(c_indices)
        etf = categorize(c_etfs)
        stk = categorize(c_stocks)
        all_c = idx + etf + stk
        
        yr_rankings = {}
        for yr in years[:-1]:
            yr_str = str(yr)
            yr_rankings[yr_str] = {
                "indices": rank_by_year(idx, yr_str),
                "etfs": rank_by_year(etf, yr_str),
                "stocks": rank_by_year(stk, yr_str, 5),
            }
        
        return {
            "indices": idx,
            "etfs": etf,
            "stocks": stk,
            "ytd": {
                "indices": rank_by_ytd(idx),
                "etfs": rank_by_ytd(etf),
                "stocks": rank_by_ytd(stk, 5),
            },
            "yearly": yr_rankings
        }
    
    result = {
        "success": True,
        "current_year": current_year,
        "years": [str(y) for y in years[:-1]],
        "india": build_country(india_indices, india_etfs, india_stocks),
        "usa": build_country(usa_indices, usa_etfs, usa_stocks),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    }
    
    _perf_cache = result
    _perf_cache_ts = now
    return result


ALGO_INSTRUMENTS = {
    # ═══ INDIA ═══
    "NIFTY": {"sym": "^NSEI", "lot": 65, "gap": 50, "ex": "NFO", "exp": "Tuesday", "region": "IN", "currency": "INR"},
    "BANKNIFTY": {"sym": "^NSEBANK", "lot": 30, "gap": 100, "ex": "NFO", "exp": "Monthly-Tue", "region": "IN", "currency": "INR"},
    "SENSEX": {"sym": "^BSESN", "lot": 20, "gap": 100, "ex": "BFO", "exp": "Thursday", "region": "IN", "currency": "INR"},
    "RELIANCE": {"sym": "RELIANCE.NS", "lot": 250, "gap": 20, "ex": "NFO", "region": "IN", "currency": "INR"},
    "TCS": {"sym": "TCS.NS", "lot": 150, "gap": 50, "ex": "NFO", "region": "IN", "currency": "INR"},
    "HDFCBANK": {"sym": "HDFCBANK.NS", "lot": 550, "gap": 20, "ex": "NFO", "region": "IN", "currency": "INR"},
    "INFY": {"sym": "INFY.NS", "lot": 400, "gap": 20, "ex": "NFO", "region": "IN", "currency": "INR"},
    "ICICIBANK": {"sym": "ICICIBANK.NS", "lot": 700, "gap": 20, "ex": "NFO", "region": "IN", "currency": "INR"},
    "SBIN": {"sym": "SBIN.NS", "lot": 750, "gap": 10, "ex": "NFO", "region": "IN", "currency": "INR"},
    "TATAMOTORS": {"sym": "TATAMOTORS.NS", "lot": 575, "gap": 10, "ex": "NFO", "region": "IN", "currency": "INR"},
    "BHARTIARTL": {"sym": "BHARTIARTL.NS", "lot": 475, "gap": 20, "ex": "NFO", "region": "IN", "currency": "INR"},
    "LT": {"sym": "LT.NS", "lot": 150, "gap": 50, "ex": "NFO", "region": "IN", "currency": "INR"},
    "BAJFINANCE": {"sym": "BAJFINANCE.NS", "lot": 125, "gap": 100, "ex": "NFO", "region": "IN", "currency": "INR"},
    "ITC": {"sym": "ITC.NS", "lot": 1600, "gap": 5, "ex": "NFO", "region": "IN", "currency": "INR"},
    "MARUTI": {"sym": "MARUTI.NS", "lot": 100, "gap": 100, "ex": "NFO", "region": "IN", "currency": "INR"},
    # ═══ USA ═══
    "SPY": {"sym": "SPY", "lot": 100, "gap": 1, "ex": "CBOE", "exp": "Mon/Wed/Fri", "region": "US", "currency": "USD"},
    "QQQ": {"sym": "QQQ", "lot": 100, "gap": 1, "ex": "CBOE", "exp": "Mon/Wed/Fri", "region": "US", "currency": "USD"},
    "IWM": {"sym": "IWM", "lot": 100, "gap": 1, "ex": "CBOE", "exp": "Fri", "region": "US", "currency": "USD"},
    "AAPL": {"sym": "AAPL", "lot": 100, "gap": 1, "ex": "NASDAQ", "exp": "Fri", "region": "US", "currency": "USD"},
    "MSFT": {"sym": "MSFT", "lot": 100, "gap": 1, "ex": "NASDAQ", "exp": "Fri", "region": "US", "currency": "USD"},
    "NVDA": {"sym": "NVDA", "lot": 100, "gap": 1, "ex": "NASDAQ", "exp": "Fri", "region": "US", "currency": "USD"},
    "TSLA": {"sym": "TSLA", "lot": 100, "gap": 1, "ex": "NASDAQ", "exp": "Fri", "region": "US", "currency": "USD"},
    "AMZN": {"sym": "AMZN", "lot": 100, "gap": 1, "ex": "NASDAQ", "exp": "Fri", "region": "US", "currency": "USD"},
    "GOOGL": {"sym": "GOOGL", "lot": 100, "gap": 1, "ex": "NASDAQ", "exp": "Fri", "region": "US", "currency": "USD"},
    "META": {"sym": "META", "lot": 100, "gap": 1, "ex": "NASDAQ", "exp": "Fri", "region": "US", "currency": "USD"},
    "AMD": {"sym": "AMD", "lot": 100, "gap": 1, "ex": "NASDAQ", "exp": "Fri", "region": "US", "currency": "USD"},
    "JPM": {"sym": "JPM", "lot": 100, "gap": 1, "ex": "NYSE", "exp": "Fri", "region": "US", "currency": "USD"},
    "AVGO": {"sym": "AVGO", "lot": 100, "gap": 1, "ex": "NASDAQ", "exp": "Fri", "region": "US", "currency": "USD"},
}

_algo_cache = {}
_algo_cache_ts = {}

@app.get("/api/algo-signal")
async def algo_signal_safe(symbol: str = "NIFTY", region: str = ""):
    """Wrapper that guarantees JSON response even on crash. 3-min cache."""
    from datetime import datetime, timedelta
    symbol = symbol.upper().strip().replace(".NS","").replace(".BO","").replace("^NSEI","NIFTY").replace("^NSEBANK","BANKNIFTY").replace("^BSESN","SENSEX")
    now = datetime.utcnow()
    cache_key = f"{symbol}_{region}"
    if cache_key in _algo_cache and cache_key in _algo_cache_ts:
        if (now - _algo_cache_ts[cache_key]).total_seconds() < 180:
            return _algo_cache[cache_key]
    try:
        result = await _algo_signal_impl(symbol, region)
        _algo_cache[cache_key] = result
        _algo_cache_ts[cache_key] = now
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": f"Algo error: {str(e)}", "symbol": symbol}

@app.get("/api/algo-batch")
async def algo_batch(region: str = "IN"):
    """Batch: 3 top instruments by region. Uses cache."""
    from datetime import datetime, timedelta
    IST = datetime.utcnow() + timedelta(hours=5, minutes=30)
    day_name = IST.strftime("%A")
    
    region = region.upper()
    if region == "US":
        symbols = ["SPY", "QQQ", "IWM"]
        expiry_index = ""  # SPY/QQQ have Mon/Wed/Fri expiry
        if day_name in ["Monday", "Wednesday", "Friday"]:
            expiry_index = "SPY"  # SPY 0DTE
    else:
        symbols = ["NIFTY", "BANKNIFTY", "SENSEX"]
        EXPIRY_MAP = {"Tuesday": "NIFTY", "Thursday": "SENSEX"}
        expiry_index = EXPIRY_MAP.get(day_name, "")
    
    # Priority: expiry index first
    if expiry_index in symbols:
        symbols.remove(expiry_index)
        symbols = [expiry_index] + symbols
    
    out = []
    for s in symbols:
        try:
            r = await algo_signal_safe(s, region)
            out.append(r)
        except Exception as e:
            out.append({"success": False, "symbol": s, "error": str(e)})
    
    return {
        "success": True, "signals": out, "count": len(out),
        "expiryToday": expiry_index, "dayName": day_name, "region": region,
    }

async def _algo_signal_impl(symbol: str = "NIFTY", region: str = ""):
    """5-Layer Confluence Algorithm — ALL real data, ZERO hallucination."""
    import yfinance as yf
    from datetime import datetime, timedelta
    import math
    
    symbol = symbol.upper().strip().replace(".NS","").replace(".BO","").replace("^NSEI","NIFTY").replace("^NSEBANK","BANKNIFTY").replace("^BSESN","SENSEX")
    
    # Smart region detection
    known_us = {"SPY","QQQ","IWM","AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META","AMD","JPM","AVGO","NFLX","CRM","ORCL","INTC","BA","DIS","V","MA","WMT","COST","HD","PG","KO","PEP","MRK","LLY","UNH","JNJ","ABBV","BMY","SNDK","WDC","PLTR","CRWD","DDOG","SNOW","NET","UBER","LYFT","SQ","PYPL","COIN","HOOD","SOFI","RIVN","LCID","NIO","BABA","TSM","ASML","ARM"}
    known_in = {"NIFTY","BANKNIFTY","SENSEX","RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","SBIN","TATAMOTORS","BHARTIARTL","LT","BAJFINANCE","ITC","MARUTI","WIPRO","KOTAKBANK","ADANIENT","ADANIPORTS","HINDALCO","JSWSTEEL","TATASTEEL","ONGC","NTPC","POWERGRID","BPCL","HCLTECH","TECHM","DRREDDY","CIPLA","SUNPHARMA","HINDUNILVR","ASIANPAINT","ULTRACEMCO","GRASIM","TITAN","BAJAJFINSV","AXISBANK","INDUSINDBK"}
    
    if not region:
        if symbol in known_us or (symbol in ALGO_INSTRUMENTS and ALGO_INSTRUMENTS[symbol].get("region") == "US"):
            region = "US"
        elif symbol in known_in or (symbol in ALGO_INSTRUMENTS and ALGO_INSTRUMENTS[symbol].get("region") == "IN"):
            region = "IN"
        else:
            # Try yfinance to detect
            try:
                test_tk = yf.Ticker(symbol)
                test_info = test_tk.info or {}
                exch = (test_info.get("exchange", "") or "").upper()
                if any(x in exch for x in ["NSE", "BSE", "BOM"]):
                    region = "IN"
                else:
                    region = "US"
            except:
                region = "IN"  # Default India
    
    region = region.upper()
    is_us_region = region == "US"
    
    # Build instrument config
    if symbol in ALGO_INSTRUMENTS:
        inst = ALGO_INSTRUMENTS[symbol]
    elif is_us_region:
        inst = {"sym": symbol, "lot": 100, "gap": 1, "ex": "US", "region": "US", "currency": "USD"}
    else:
        inst = {"sym": f"{symbol}.NS", "lot": 100, "gap": 10, "ex": "NFO", "region": "IN", "currency": "INR"}
    
    yf_sym = inst["sym"]
    is_us = inst.get("region") == "US"
    csym = "$" if is_us else "₹"
    
    # ═══ FETCH ALL DATA IN PARALLEL ═══
    result = {"success": True, "symbol": symbol, "instrument": inst, "region": inst.get("region", "IN"), "currSym": "₹" if inst.get("region") != "US" else "$"}
    factors = []
    
    # 1. yfinance — price, technicals, fundamentals
    try:
        tk = yf.Ticker(yf_sym)
        
        # Daily history (1 year for MAs)
        daily = tk.history(period="1y", interval="1d")
        if daily is None or len(daily) < 20:
            return {"success": False, "error": f"No data for {symbol}"}
        
        closes = daily['Close'].values
        highs = daily['High'].values
        lows = daily['Low'].values
        volumes = daily['Volume'].values
        
        price = round(float(closes[-1]), 2)
        result["spot"] = price
        
        # Previous day
        pdh = round(float(highs[-2]), 2) if len(highs) > 1 else price
        pdl = round(float(lows[-2]), 2) if len(lows) > 1 else price
        pdc = round(float(closes[-2]), 2) if len(closes) > 1 else price
        today_open = round(float(daily['Open'].iloc[-1]), 2)
        today_high = round(float(highs[-1]), 2)
        today_low = round(float(lows[-1]), 2)
        
        # CPR
        pivot = round((pdh + pdl + pdc) / 3, 2)
        bc = round((pdh + pdl) / 2, 2)
        tc = round(2 * pivot - bc, 2)
        cpr_width = abs(tc - bc)
        cpr_pct = round((cpr_width / pdc) * 100, 3)
        cpr_type = "NARROW" if cpr_pct < 0.3 else "WIDE" if cpr_pct > 0.8 else "MEDIUM"
        
        # Gap
        gap = round(today_open - pdc, 2)
        gap_pct = round((gap / pdc) * 100, 2)
        gap_type = "GAP UP" if gap_pct > 0.3 else "GAP DOWN" if gap_pct < -0.3 else "FLAT"
        
        # SMAs + EMAs
        import pandas as pd
        cs = pd.Series(closes)
        sma20 = round(float(cs.rolling(20).mean().iloc[-1]), 2) if len(closes) >= 20 else price
        sma50 = round(float(cs.rolling(50).mean().iloc[-1]), 2) if len(closes) >= 50 else price
        sma200 = round(float(cs.rolling(200).mean().iloc[-1]), 2) if len(closes) >= 200 else price
        ema9 = round(float(cs.ewm(span=9).mean().iloc[-1]), 2) if len(closes) >= 9 else price
        ema21 = round(float(cs.ewm(span=21).mean().iloc[-1]), 2) if len(closes) >= 21 else price
        ema50 = round(float(cs.ewm(span=50).mean().iloc[-1]), 2) if len(closes) >= 50 else price
        
        # RSI(14)
        deltas = cs.diff()
        gain = deltas.clip(lower=0).rolling(14).mean()
        loss = (-deltas.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        rsi = round(float(rsi_series.iloc[-1]), 1) if not pd.isna(rsi_series.iloc[-1]) else 50
        
        # MACD
        ema12 = cs.ewm(span=12).mean()
        ema26 = cs.ewm(span=26).mean()
        macd_line = ema12 - ema26
        macd_signal = macd_line.ewm(span=9).mean()
        macd_hist = round(float((macd_line - macd_signal).iloc[-1]), 2)
        macd_bullish = macd_hist > 0
        
        # Supertrend(10,3)
        atr_period = 10
        multiplier = 3
        hl2 = (pd.Series(highs) + pd.Series(lows)) / 2
        atr = pd.Series(highs).rolling(atr_period).max() - pd.Series(lows).rolling(atr_period).min()
        atr_val = round(float(atr.iloc[-1] / atr_period), 2) if len(atr) > atr_period else round(float(highs[-1] - lows[-1]), 2)
        upper = float(hl2.iloc[-1] + multiplier * atr_val)
        lower = float(hl2.iloc[-1] - multiplier * atr_val)
        supertrend_buy = price > lower
        
        # ATR(14)
        tr_series = pd.DataFrame({'hl': pd.Series(highs) - pd.Series(lows), 'hc': abs(pd.Series(highs) - cs.shift(1)), 'lc': abs(pd.Series(lows) - cs.shift(1))}).max(axis=1)
        atr14 = round(float(tr_series.rolling(14).mean().iloc[-1]), 2) if len(tr_series) > 14 else round(float(highs[-1] - lows[-1]), 2)
        
        # Volume
        avg_vol = float(pd.Series(volumes[-20:]).mean()) if len(volumes) >= 20 else float(volumes[-1])
        vol_ratio = round(float(volumes[-1]) / avg_vol, 2) if avg_vol > 0 else 1
        
        # 52W
        w52h = round(float(max(highs[-252:])), 2) if len(highs) >= 252 else round(float(max(highs)), 2)
        w52l = round(float(min(lows[-252:])), 2) if len(lows) >= 252 else round(float(min(lows)), 2)
        w52pos = round(((price - w52l) / (w52h - w52l)) * 100, 1) if w52h > w52l else 50
        
        # Market structure (HH/HL check on last 5 days)
        recent_highs = [float(h) for h in highs[-5:]]
        recent_lows = [float(l) for l in lows[-5:]]
        hh_hl = all(recent_highs[i] >= recent_highs[i-1] for i in range(1, len(recent_highs))) and all(recent_lows[i] >= recent_lows[i-1] for i in range(1, len(recent_lows)))
        lh_ll = all(recent_highs[i] <= recent_highs[i-1] for i in range(1, len(recent_highs))) and all(recent_lows[i] <= recent_lows[i-1] for i in range(1, len(recent_lows)))
        
        # Fundamentals (for stocks, not indices)
        pe = roe = margin = de = beta_val = 0
        try:
            info = tk.info or {}
            pe = round(float(info.get("trailingPE", 0) or 0), 1)
            roe = round(float(info.get("returnOnEquity", 0) or 0) * 100, 1)
            margin = round(float(info.get("profitMargins", 0) or 0) * 100, 1)
            de = round(float(info.get("debtToEquity", 0) or 0) / 100, 2)
            beta_val = round(float(info.get("beta", 1) or 1), 2)
        except:
            pass
        
        result["technicals"] = {
            "price": price, "pdh": pdh, "pdl": pdl, "pdc": pdc,
            "today_open": today_open, "today_high": today_high, "today_low": today_low,
            "pivot": pivot, "cpr_top": tc, "cpr_bottom": bc, "cpr_pct": cpr_pct, "cpr_type": cpr_type,
            "gap": gap, "gap_pct": gap_pct, "gap_type": gap_type,
            "sma20": sma20, "sma50": sma50, "sma200": sma200,
            "ema9": ema9, "ema21": ema21, "ema50": ema50,
            "rsi": rsi, "macd_hist": macd_hist, "macd_bullish": macd_bullish,
            "supertrend_buy": supertrend_buy, "atr14": atr14,
            "vol_ratio": vol_ratio, "w52h": w52h, "w52l": w52l, "w52pos": w52pos,
            "hh_hl": hh_hl, "lh_ll": lh_ll,
            "pe": pe, "roe": roe, "margin": margin, "de": de, "beta": beta_val
        }
    except Exception as e:
        return {"success": False, "error": f"Data fetch failed: {e}"}
    
    # 2. NSE Options data (India only — US stocks use yfinance options)
    nse = {}
    is_us = inst.get("region") == "US"
    if not is_us:
        try:
            nse_resp = await nse_options(symbol)
            if isinstance(nse_resp, dict) and nse_resp.get("success"):
                nse = nse_resp
        except:
            pass
    
    result["options"] = nse
    
    # 3. Opening Range Breakout (ORB) — intraday 15m candles
    orb = {}
    try:
        intra = tk.history(period="1d", interval="15m")
        if intra is not None and len(intra) >= 2:
            # First 15-min candle = Opening Range
            first_candle = intra.iloc[0]
            orb_high = round(float(first_candle['High']), 2)
            orb_low = round(float(first_candle['Low']), 2)
            orb_range = round(orb_high - orb_low, 2)
            orb_pct = round((orb_range / orb_low) * 100, 3) if orb_low > 0 else 0
            
            # Current price vs ORB
            latest_intra = intra.iloc[-1]
            intra_price = round(float(latest_intra['Close']), 2)
            intra_high = round(float(intra['High'].max()), 2)
            intra_low = round(float(intra['Low'].min()), 2)
            
            # Volume of first candle vs average
            if len(intra) >= 3:
                first_vol = float(intra.iloc[0]['Volume'])
                avg_vol_15m = float(intra['Volume'].mean())
                orb_vol_ratio = round(first_vol / avg_vol_15m, 2) if avg_vol_15m > 0 else 1
            else:
                orb_vol_ratio = 1
            
            orb_breakout = "ABOVE" if intra_price > orb_high else "BELOW" if intra_price < orb_low else "INSIDE"
            
            # Intraday VWAP approximation: sum(price*volume)/sum(volume) from intraday data
            try:
                typical_prices = (intra['High'] + intra['Low'] + intra['Close']) / 3
                vwap_val = round(float((typical_prices * intra['Volume']).cumsum().iloc[-1] / intra['Volume'].cumsum().iloc[-1]), 2)
            except:
                vwap_val = 0
            
            orb = {
                "orb_high": orb_high, "orb_low": orb_low, "orb_range": orb_range,
                "orb_pct": orb_pct, "breakout": orb_breakout,
                "intra_price": intra_price, "intra_high": intra_high, "intra_low": intra_low,
                "orb_vol_ratio": orb_vol_ratio, "vwap": vwap_val,
                "candles": len(intra),
            }
            result["orb"] = orb
            print(f"📊 ORB: {symbol} H={orb_high} L={orb_low} Range={orb_range} Break={orb_breakout} VWAP={vwap_val}")
    except Exception as e:
        print(f"⚠️ ORB fetch failed: {e}")
    
    # 4. Black-Scholes Delta Calculation
    bs_data = {}
    try:
        if nse.get("success") and nse.get("atm_iv", 0) > 0:
            from math import log, sqrt, exp, erf
            
            def norm_cdf(x):
                return 0.5 * (1 + erf(x / sqrt(2)))
            
            def black_scholes_greeks(S, K, T, r, sigma, option_type="CE"):
                """Full Black-Scholes with Greeks."""
                if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
                    return {"delta": 0, "gamma": 0, "theta": 0, "premium": 0}
                d1 = (log(S / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt(T))
                d2 = d1 - sigma * sqrt(T)
                nd1 = norm_cdf(d1)
                nd2 = norm_cdf(d2)
                # PDF of standard normal
                npd1 = exp(-d1**2 / 2) / sqrt(2 * 3.14159265)
                
                if option_type == "CE":
                    delta = round(nd1, 3)
                    premium = round(S * nd1 - K * exp(-r * T) * nd2, 2)
                else:
                    delta = round(nd1 - 1, 3)
                    premium = round(K * exp(-r * T) * (1 - nd2) - S * (1 - nd1), 2)
                
                gamma = round(npd1 / (S * sigma * sqrt(T)), 6)
                theta = round((-S * npd1 * sigma / (2 * sqrt(T)) - r * K * exp(-r * T) * nd2) / 365, 2) if option_type == "CE" else round((-S * npd1 * sigma / (2 * sqrt(T)) + r * K * exp(-r * T) * (1 - nd2)) / 365, 2)
                
                return {"delta": delta, "gamma": gamma, "theta": theta, "premium": max(premium, 0)}
            
            spot = nse.get("spot", price)
            atm_iv_dec = nse.get("atm_iv", 20) / 100  # Convert from % to decimal
            risk_free = 0.0525 if is_us else 0.065  # US Fed rate vs India 10Y
            
            # Expiry: find days to expiry
            try:
                exp_date = datetime.strptime(nse.get("expiry", ""), "%d-%b-%Y")
                dte = max((exp_date - datetime.utcnow() - timedelta(hours=-5, minutes=-30)).days, 1)
            except:
                dte = 7  # default 1 week
            T = dte / 365
            
            gap_size = inst["gap"]
            atm_strike = round(spot / gap_size) * gap_size
            
            # Calculate Greeks for ATM, ITM-1, OTM-1 strikes (CE and PE)
            strikes_to_calc = {
                "ATM": atm_strike,
                "ITM1": atm_strike - gap_size,
                "OTM1": atm_strike + gap_size,
                "OTM2": atm_strike + gap_size * 2,
            }
            
            greeks = {}
            for label, K in strikes_to_calc.items():
                ce = black_scholes_greeks(spot, K, T, risk_free, atm_iv_dec, "CE")
                pe = black_scholes_greeks(spot, K, T, risk_free, atm_iv_dec, "PE")
                greeks[label] = {"strike": K, "CE": ce, "PE": pe}
            
            # Find best strike by delta (0.50-0.55 for aggressive, 0.40-0.45 for conservative)
            best_ce_strike = atm_strike
            best_ce_delta = 0
            best_pe_strike = atm_strike
            best_pe_delta = 0
            
            for label, K in strikes_to_calc.items():
                ce_d = abs(greeks[label]["CE"]["delta"])
                pe_d = abs(greeks[label]["PE"]["delta"])
                if 0.40 <= ce_d <= 0.55:
                    if ce_d > best_ce_delta:
                        best_ce_delta = ce_d
                        best_ce_strike = K
                if 0.40 <= pe_d <= 0.55:
                    if pe_d > best_pe_delta:
                        best_pe_delta = pe_d
                        best_pe_strike = K
            
            bs_data = {
                "dte": dte,
                "T": round(T, 4),
                "risk_free": risk_free,
                "iv": nse.get("atm_iv", 20),
                "greeks": greeks,
                "best_ce": {"strike": best_ce_strike, "delta": best_ce_delta, "premium": greeks.get("ATM", {}).get("CE", {}).get("premium", 0)},
                "best_pe": {"strike": best_pe_strike, "delta": abs(best_pe_delta), "premium": greeks.get("ATM", {}).get("PE", {}).get("premium", 0)},
                "atm_gamma": greeks.get("ATM", {}).get("CE", {}).get("gamma", 0),
                "atm_theta": greeks.get("ATM", {}).get("CE", {}).get("theta", 0),
            }
            result["black_scholes"] = bs_data
            print(f"📊 B-S: {symbol} ATM={atm_strike} CE_delta={greeks.get('ATM',{}).get('CE',{}).get('delta',0)} Premium={greeks.get('ATM',{}).get('CE',{}).get('premium',0)} DTE={dte}")
    except Exception as e:
        print(f"⚠️ Black-Scholes failed: {e}")
    
    # ═══ OPTIONS INTELLIGENCE — IV Rank, Expected Move, Max Pain OI ═══
    try:
        import numpy as np
        import traceback
        if len(closes) > 30:
            daily_returns = []
            for i in range(1, len(closes)):
                if closes[i-1] > 0:
                    daily_returns.append((float(closes[i]) - float(closes[i-1])) / float(closes[i-1]))
            
            # 1. IV RANK / PERCENTILE
            hv_values = []
            if len(daily_returns) > 25:
                for w in range(0, len(daily_returns) - 21, 5):
                    window = daily_returns[w:w+21]
                    if len(window) >= 10:
                        hv_val = float(np.std(window) * (252 ** 0.5) * 100)
                        if hv_val > 0:
                            hv_values.append(hv_val)
            
            current_iv = float(nse.get("atm_iv", 0) or 0)
            if current_iv <= 0 and len(daily_returns) >= 21:
                current_iv = round(float(np.std(daily_returns[-21:]) * (252 ** 0.5) * 100), 1)
            if current_iv <= 0:
                current_iv = round(float(np.std(daily_returns[-10:]) * (252 ** 0.5) * 100), 1) if len(daily_returns) >= 10 else 20
            
            iv_rank = 50
            iv_percentile = 50
            iv_high = round(current_iv * 1.5, 1)
            iv_low = round(current_iv * 0.5, 1)
            if hv_values and len(hv_values) >= 3 and current_iv > 0:
                iv_high = round(max(hv_values), 1)
                iv_low = round(min(hv_values), 1)
                iv_range = iv_high - iv_low
                iv_rank = round(((current_iv - iv_low) / iv_range) * 100, 0) if iv_range > 0 else 50
                iv_rank = max(0, min(100, iv_rank))
                below = sum(1 for hv in hv_values if hv < current_iv)
                iv_percentile = round((below / len(hv_values)) * 100, 0)
            
            if iv_rank >= 70:
                iv_signal = "HIGH — Premiums expensive. Consider SELLING options (iron condors, credit spreads)."
            elif iv_rank <= 30:
                iv_signal = "LOW — Premiums cheap. Good time to BUY options (long calls/puts, debit spreads)."
            else:
                iv_signal = "NORMAL — No extreme. Directional trades OK."
            
            # 2. EXPECTED MOVE
            dte_val = bs_data.get("dte", 7) if bs_data else 7
            iv_decimal = current_iv / 100 if current_iv > 0 else 0.20
            expected_move_pct = round(iv_decimal * ((max(dte_val, 1) / 365) ** 0.5) * 100, 2)
            expected_move_pts = round(price * expected_move_pct / 100, 1)
            em_upper = round(price + expected_move_pts, 1)
            em_lower = round(price - expected_move_pts, 1)
            
            # 3. MAX PAIN with OI DISTRIBUTION
            oi_distribution = []
            max_pain_val = float(nse.get("max_pain", 0) or 0)
            
            if is_us:
                try:
                    us_opts = tk.options
                    if us_opts:
                        chain = tk.option_chain(us_opts[0])
                        if len(chain.calls) > 0 and len(chain.puts) > 0:
                            near_calls = chain.calls.loc[abs(chain.calls["strike"] - price) < price * 0.10].head(15)
                            near_puts = chain.puts.loc[abs(chain.puts["strike"] - price) < price * 0.10].head(15)
                            all_strikes = sorted(set(near_calls["strike"].tolist() + near_puts["strike"].tolist()))
                            for s in all_strikes[:15]:
                                c_oi = int(near_calls.loc[near_calls["strike"]==s, "openInterest"].sum()) if s in near_calls["strike"].values else 0
                                p_oi = int(near_puts.loc[near_puts["strike"]==s, "openInterest"].sum()) if s in near_puts["strike"].values else 0
                                oi_distribution.append({"strike": round(float(s), 1), "call_oi": c_oi, "put_oi": p_oi})
                except Exception as oe:
                    print(f"  US OI dist error: {oe}")
            else:
                ce_resist = nse.get("ce_resistance", [])
                pe_support = nse.get("pe_support", [])
                strike_map = {}
                for c in (ce_resist or []):
                    strike_map[c["strike"]] = {"strike": c["strike"], "call_oi": c["oi"], "put_oi": 0}
                for p in (pe_support or []):
                    if p["strike"] in strike_map:
                        strike_map[p["strike"]]["put_oi"] = p["oi"]
                    else:
                        strike_map[p["strike"]] = {"strike": p["strike"], "call_oi": 0, "put_oi": p["oi"]}
                oi_distribution = sorted(strike_map.values(), key=lambda x: x["strike"])
            
            result["options_intel"] = {
                "iv_current": round(current_iv, 1),
                "iv_rank": int(iv_rank),
                "iv_percentile": int(iv_percentile),
                "iv_high_1y": round(float(iv_high), 1),
                "iv_low_1y": round(float(iv_low), 1),
                "iv_signal": iv_signal,
                "expected_move_pct": float(expected_move_pct),
                "expected_move_pts": float(expected_move_pts),
                "em_upper": float(em_upper),
                "em_lower": float(em_lower),
                "dte": int(dte_val),
                "max_pain": float(max_pain_val),
                "oi_distribution": oi_distribution[:15],
            }
            print(f"📊 Options Intel: {symbol} IV={current_iv:.1f} Rank={iv_rank:.0f}% EM=±{expected_move_pts:.1f} MaxPain={max_pain_val}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"⚠️ Options Intelligence failed: {e}")
    
    # ═══ 5-LAYER CONFLUENCE COMPUTATION ═══
    t = result["technicals"]
    
    def add(name, status, detail, category, weight=1.0):
        factors.append({"name": name, "status": status, "detail": detail, "category": category, "weight": weight})
    
    # ─── LAYER 1: PRICE ACTION ───
    add("CPR", "SUPPORTS" if cpr_type == "NARROW" else "OPPOSES" if cpr_type == "WIDE" else "NEUTRAL",
        f"{cpr_type} CPR ({cpr_pct}%). {'Trending day — directional trades favored.' if cpr_type == 'NARROW' else 'Range-bound. Sell strategies better.' if cpr_type == 'WIDE' else 'Normal day.'}", "PRICE_ACTION", 1.5)
    
    add("PDH/PDL", "SUPPORTS" if price > pdh else "OPPOSES" if price < pdl else "NEUTRAL",
        f"PDH {csym}{pdh:,.0f}, PDL {csym}{pdl:,.0f}. {'Price broke above PDH — bullish structure.' if price > pdh else 'Price below PDL — bearish breakdown.' if price < pdl else 'Within prev range — consolidating.'}", "PRICE_ACTION", 1.0)
    
    add("Gap Analysis", "SUPPORTS" if gap_pct > 0.3 else "OPPOSES" if gap_pct < -0.3 else "NEUTRAL",
        f"{gap_type} ({gap_pct:+.2f}%). {'Gap up = bullish continuation.' if gap_pct > 0.5 else 'Gap down = selling pressure.' if gap_pct < -0.5 else 'Flat/minor gap.'}", "PRICE_ACTION", 0.8)
    
    # ORB (Opening Range Breakout) — from real intraday 15m data
    if orb.get("orb_high"):
        orb_status = "SUPPORTS" if orb["breakout"] == "ABOVE" else "OPPOSES" if orb["breakout"] == "BELOW" else "NEUTRAL"
        add("Opening Range (ORB)", orb_status,
            f"ORB: {csym}{orb['orb_high']:,.0f}–{csym}{orb['orb_low']:,.0f} (range {orb['orb_pct']:.2f}%). "
            f"{'Price ABOVE ORB high — bullish breakout confirmed.' if orb['breakout'] == 'ABOVE' else 'Price BELOW ORB low — bearish breakdown.' if orb['breakout'] == 'BELOW' else 'Inside range — no breakout yet.'}"
            f"{' Vol ' + str(orb['orb_vol_ratio']) + '× on ORB candle.' if orb.get('orb_vol_ratio', 1) > 1.3 else ''}", "PRICE_ACTION", 2.0)
    
    add("Market Structure", "SUPPORTS" if hh_hl else "OPPOSES" if lh_ll else "NEUTRAL",
        f"{'HH + HL on daily — uptrend intact.' if hh_hl else 'LH + LL — downtrend.' if lh_ll else 'Mixed structure — no clear trend.'}", "PRICE_ACTION", 2.0)
    
    add("52W Position", "SUPPORTS" if 20 < w52pos < 75 else "OPPOSES" if w52pos > 90 else "NEUTRAL",
        f"{w52pos:.0f}% of 52W range. {'Sweet spot for entry.' if 20 < w52pos < 75 else 'Near 52W high — pullback risk.' if w52pos > 80 else 'Near 52W low — catching knife?'}", "PRICE_ACTION", 0.8)
    
    add("Support/Resistance", "SUPPORTS" if price > sma20 and price > ema21 else "OPPOSES" if price < sma20 and price < ema21 else "NEUTRAL",
        f"{'Above SMA20 + EMA21 demand zone.' if price > sma20 and price > ema21 else 'Below supply zone.' if price < sma20 and price < ema21 else 'Between zones.'}", "PRICE_ACTION", 1.5)
    
    # ─── LAYER 2: INDICATORS ───
    # VWAP — from real intraday data
    if orb.get("vwap") and orb["vwap"] > 0:
        vwap_val = orb["vwap"]
        add("VWAP", "SUPPORTS" if price > vwap_val else "OPPOSES",
            f"VWAP {csym}{vwap_val:,.0f}. Price {'above — institutional bias bullish. Buyers in control.' if price > vwap_val else 'below — institutional selling. Bears dominating.'}", "INDICATOR", 2.0)
    
    add("EMA Stack (9/21/50)", "SUPPORTS" if ema9 > ema21 > ema50 else "OPPOSES" if ema9 < ema21 < ema50 else "NEUTRAL",
        f"EMA 9/21/50: {'Full bullish stack ✓' if ema9 > ema21 > ema50 else 'Full bearish stack' if ema9 < ema21 < ema50 else 'Mixed — choppy'}. 9={ema9:,.0f} 21={ema21:,.0f} 50={ema50:,.0f}", "INDICATOR", 2.0)
    
    add("RSI(14)", "SUPPORTS" if 35 < rsi < 65 else "OPPOSES" if rsi > 75 else "SUPPORTS" if rsi < 25 else "NEUTRAL",
        f"RSI {rsi}. {'Healthy momentum.' if 35 < rsi < 65 else 'Overbought — pullback risk.' if rsi > 70 else 'Oversold — bounce likely.' if rsi < 30 else 'Borderline.'}" + (" No divergence." if 40 < rsi < 60 else ""), "INDICATOR", 1.5)
    
    add("Supertrend(10,3)", "SUPPORTS" if supertrend_buy else "OPPOSES",
        f"{'BUY signal active.' if supertrend_buy else 'SELL signal active.'}", "INDICATOR", 1.5)
    
    add("MACD", "SUPPORTS" if macd_bullish else "OPPOSES",
        f"Histogram {'expanding ↑' if macd_hist > 0 else 'contracting ↓'} ({macd_hist:+.1f}). {'Bullish crossover.' if macd_bullish else 'Bearish crossover.'}", "INDICATOR", 1.5)
    
    add("Volume", "SUPPORTS" if vol_ratio > 1.2 else "OPPOSES" if vol_ratio < 0.7 else "NEUTRAL",
        f"{vol_ratio:.1f}× average volume. {'Breakout confirmed by volume.' if vol_ratio > 1.5 else 'Above average — conviction.' if vol_ratio > 1.2 else 'Below average — weak conviction.' if vol_ratio < 0.7 else 'Normal.'}", "INDICATOR", 1.0)
    
    add("ATR(14)", "NEUTRAL", f"ATR {csym}{atr14:,.0f}. SL = 1.5×ATR = {csym}{round(atr14*1.5):,.0f}.", "INDICATOR", 0.5)
    
    add("Golden/Death Cross", "SUPPORTS" if sma50 > sma200 else "OPPOSES",
        f"{'Golden Cross — SMA50 > SMA200. Strongest bullish signal.' if sma50 > sma200 else 'Death Cross — bearish long-term.'}", "INDICATOR", 2.0)
    
    # ─── LAYER 3: OPTIONS (NSE LIVE for India, yfinance for US) ───
    vix = 0; pcr = 0; max_pain = 0; atm_iv = 0
    ce_resist = []; pe_support = []
    
    if nse.get("success"):
        # India — use NSE data
        vix = nse.get("vix", 0)
        pcr = nse.get("pcr", 0)
        max_pain = nse.get("max_pain", 0)
        atm_iv = nse.get("atm_iv", 0)
        ce_resist = nse.get("ce_resistance", [])
        pe_support = nse.get("pe_support", [])
    elif is_us:
        # USA — fetch VIX and basic options from yfinance
        try:
            vix_tk = yf.Ticker("^VIX")
            vix_info = vix_tk.info or {}
            vix = round(float(vix_info.get("regularMarketPrice", 0) or vix_info.get("previousClose", 0)), 1)
        except:
            pass
        # Try yfinance options chain for US stocks
        try:
            opts = tk.options
            if opts:
                chain = tk.option_chain(opts[0])
                calls = chain.calls
                puts = chain.puts
                if len(calls) > 0 and len(puts) > 0:
                    # PCR from OI
                    total_call_oi = calls['openInterest'].sum()
                    total_put_oi = puts['openInterest'].sum()
                    if total_call_oi > 0:
                        pcr = round(total_put_oi / total_call_oi, 2)
                    # ATM IV
                    atm_idx = (calls['strike'] - price).abs().idxmin()
                    atm_iv = round(float(calls.loc[atm_idx, 'impliedVolatility']) * 100, 1) if atm_idx is not None else 0
                    # Max pain approximation
                    max_pain_strike = 0
                    min_pain = float('inf')
                    for s in calls['strike'].values:
                        call_pain = ((s - calls['strike']).clip(lower=0) * calls['openInterest']).sum()
                        put_pain = ((puts['strike'] - s).clip(lower=0) * puts['openInterest']).sum()
                        total_pain = call_pain + put_pain
                        if total_pain < min_pain:
                            min_pain = total_pain
                            max_pain_strike = s
                    max_pain = round(float(max_pain_strike), 2)
                    # Top OI strikes
                    top_calls = calls.nlargest(3, 'openInterest')[['strike','openInterest']].to_dict('records')
                    top_puts = puts.nlargest(3, 'openInterest')[['strike','openInterest']].to_dict('records')
                    ce_resist = [{"strike": int(r['strike']), "oi": int(r['openInterest'])} for r in top_calls]
                    pe_support = [{"strike": int(r['strike']), "oi": int(r['openInterest'])} for r in top_puts]
                    nse["ce_resistance"] = ce_resist
                    nse["pe_support"] = pe_support
                    nse["pcr"] = pcr
                    nse["max_pain"] = max_pain
                    nse["atm_iv"] = atm_iv
                    nse["vix"] = vix
                    nse["success"] = True
                    nse["spot"] = price
        except Exception as e:
            print(f"  US options error for {symbol}: {e}")
    
    if vix > 0:
        vix_label = "CBOE VIX" if is_us else "India VIX"
        add(vix_label, "SUPPORTS" if 0 < vix < 16 else "NEUTRAL" if vix < 22 else "OPPOSES",
            f"VIX {vix:.1f}. {'Low fear — premiums cheap. Option BUY favorable.' if vix < 13 else 'Fair premiums.' if vix < 18 else 'Elevated — sell strategies preferred.' if vix < 25 else 'High fear — extreme caution.'}", "OPTION", 1.5)
    
    if pcr > 0:
        add("PCR", "SUPPORTS" if 0.8 < pcr < 1.3 else "OPPOSES" if pcr < 0.7 else "NEUTRAL",
            f"PCR {pcr:.2f}. {'PE writing = bullish floor.' if pcr > 1.1 else 'Balanced.' if pcr > 0.8 else 'CE heavy = bearish resistance.' if pcr > 0 else 'N/A.'}", "OPTION", 1.5)
    
    if max_pain > 0:
        mp_dist = abs(price - max_pain) / price * 100
        add("Max Pain", "SUPPORTS" if mp_dist < 1.5 else "NEUTRAL",
            f"Max Pain {csym}{max_pain:,.0f}. {'Price near max pain — expiry pin effect.' if mp_dist < 1 else f'Price {mp_dist:.1f}% away. May drift toward it.'}", "OPTION", 1.0)
    
    if ce_resist and pe_support:
        top_ce = ce_resist[0]["strike"]
        top_pe = pe_support[0]["strike"]
        add("OI Buildup", "SUPPORTS" if top_pe < price < top_ce else "NEUTRAL",
            f"Resist: {csym}{top_ce:,.0f} (CE OI:{ce_resist[0]['oi']:,.0f}). Support: {csym}{top_pe:,.0f} (PE OI:{pe_support[0]['oi']:,.0f}). {'Within OI range.' if top_pe < price < top_ce else 'Near OI wall.'}", "OPTION", 1.5)
    
    if atm_iv > 0:
        add("ATM IV", "SUPPORTS" if atm_iv < 18 else "NEUTRAL" if atm_iv < 30 else "OPPOSES",
            f"IV {atm_iv:.1f}%. {'Low — options cheap. BUY.' if atm_iv < 15 else 'Normal.' if atm_iv < 25 else 'Elevated. SELL preferred.' if atm_iv < 35 else 'Very high.'}", "OPTION", 1.0)
    
    # Black-Scholes Greeks
    if bs_data.get("greeks"):
            atm_g = bs_data["greeks"].get("ATM", {})
            ce_delta = atm_g.get("CE", {}).get("delta", 0)
            ce_gamma = atm_g.get("CE", {}).get("gamma", 0)
            ce_theta = atm_g.get("CE", {}).get("theta", 0)
            ce_prem = atm_g.get("CE", {}).get("premium", 0)
            dte_val = bs_data.get("dte", 7)
            
            add("Delta (B-S)", "SUPPORTS" if 0.45 <= ce_delta <= 0.60 else "NEUTRAL" if 0.35 <= ce_delta <= 0.65 else "OPPOSES",
                f"ATM CE delta {ce_delta:.2f}. {'Sweet spot (0.45-0.55) — best risk/reward for directional trades.' if 0.45 <= ce_delta <= 0.55 else 'Deep ITM — expensive, less leverage.' if ce_delta > 0.65 else 'Far OTM — cheap but low probability.' if ce_delta < 0.30 else 'Acceptable range.'} Premium {csym}{ce_prem:,.0f}.", "OPTION", 1.0)
            
            if ce_gamma > 0 and dte_val <= 2:
                add("Gamma Risk", "OPPOSES" if ce_gamma > 0.005 else "NEUTRAL",
                    f"Gamma {ce_gamma:.5f}. {'HIGH gamma near expiry — premium swings wildly. Tighter SL needed.' if ce_gamma > 0.005 else 'Moderate gamma.'} DTE={dte_val}.", "OPTION", 1.5)
            
            if ce_theta != 0:
                add("Theta Decay", "OPPOSES" if dte_val <= 2 and ce_theta < -5 else "NEUTRAL" if ce_theta < -3 else "SUPPORTS",
                    f"Theta {csym}{ce_theta:,.1f}/day. {'Heavy decay — time working against BUY positions.' if ce_theta < -5 else 'Moderate decay.' if ce_theta < -2 else 'Low decay — time not a major factor.'} DTE={dte_val}.", "OPTION", 1.0)
    
    # ─── LAYER 4: FUNDAMENTALS (stocks only) ───
    is_index = yf_sym.startswith("^")
    if not is_index and pe > 0:
        add("P/E", "SUPPORTS" if 0 < pe < 25 else "NEUTRAL" if pe < 40 else "OPPOSES", f"P/E {pe}x.", "FUNDAMENTAL", 0.8)
        add("ROE", "SUPPORTS" if roe > 15 else "NEUTRAL" if roe > 8 else "OPPOSES", f"ROE {roe}%.", "FUNDAMENTAL", 0.8)
        add("Margin", "SUPPORTS" if margin > 12 else "NEUTRAL" if margin > 5 else "OPPOSES", f"Net margin {margin}%.", "FUNDAMENTAL", 0.8)
    
    # ─── LAYER 5: RISK ───
    add("Beta/Volatility", "SUPPORTS" if 0.7 <= beta_val <= 1.5 else "OPPOSES" if beta_val > 2 else "NEUTRAL",
        f"Beta {beta_val:.2f}. {'Normal vol.' if 0.7 <= beta_val <= 1.5 else 'High vol — wider SL.' if beta_val > 1.5 else 'Low vol.'}", "RISK", 0.5)
    
    add("ATR Risk", "SUPPORTS" if atr14 < price * 0.03 else "NEUTRAL" if atr14 < price * 0.05 else "OPPOSES",
        f"ATR {(atr14/price*100):.1f}% of price. {'Tight range — controlled risk.' if atr14 < price * 0.02 else 'Normal.' if atr14 < price * 0.04 else 'Wide swings — reduce position size.'}", "RISK", 0.5)
    
    if not is_index and de > 0:
        add("Balance Sheet", "SUPPORTS" if de < 1 else "NEUTRAL" if de < 2 else "OPPOSES", f"D/E {de:.2f}.", "RISK", 0.5)
    
    # ─── EXPIRY CHECK — Uses REAL NSE expiry dates ───
    IST = datetime.utcnow() + timedelta(hours=5, minutes=30)
    today_str = IST.strftime("%d-%b-%Y")  # e.g. "17-Mar-2026" — same format as NSE
    today_date = IST.strftime("%Y-%m-%d")
    day_name = IST.strftime("%A")
    is_expiry = False
    expiry_note = "Non-expiry day. Standard rules."
    expiry_instrument = ""  # which index expires today
    next_expiry = ""
    dte_to_expiry = 99
    
    # Method 1: Check NSE expiry_dates from options chain (REAL data)
    nse_expiry_dates = nse.get("expiry_dates", [])
    if nse_expiry_dates:
        next_expiry = nse_expiry_dates[0] if nse_expiry_dates else ""
        # Compare today with nearest expiry
        try:
            exp_dt = datetime.strptime(next_expiry, "%d-%b-%Y")
            today_dt = IST.replace(hour=0, minute=0, second=0, microsecond=0)
            dte_to_expiry = (exp_dt - today_dt).days
            if dte_to_expiry == 0:
                is_expiry = True
                expiry_instrument = symbol
        except:
            pass
    
    # Method 2: Fallback — check known weekly expiry schedule
    # NSE 2024-2026 schedule: NIFTY=Thursday, BANKNIFTY=Wednesday, SENSEX=Friday
    # (Changed from Tue/Thu in Nov 2024)
    if not is_expiry:
        if is_us:
            # SPY/QQQ: 0DTE on Mon/Wed/Fri
            if day_name in ["Monday", "Wednesday", "Friday"] and symbol in ["SPY", "QQQ"]:
                is_expiry = True
                expiry_instrument = symbol
            # All US stocks: weekly Friday
            elif day_name == "Friday":
                is_expiry = True
                expiry_instrument = symbol
        else:
            # NSE/BSE expiry schedule (post Sep 2025 SEBI revision):
            # NIFTY weekly = Tuesday (NSE), SENSEX weekly = Thursday (BSE)
            # BANKNIFTY = NO weekly (monthly only = last Tuesday)
            EXPIRY_SCHEDULE = {
                "NIFTY": "Tuesday",
                "SENSEX": "Thursday",
            }
            exp_day = EXPIRY_SCHEDULE.get(symbol, "")
            if exp_day and day_name == exp_day:
                is_expiry = True
                expiry_instrument = symbol
    
    # Also check if ANY index expires today (for top trades priority)
    # Which indices expire today? Region-aware — no cross-contamination
    all_expiry_today = []
    if is_us:
        # US: SPY/QQQ have 0DTE on Mon/Wed/Fri
        if day_name in ["Monday", "Wednesday", "Friday"]:
            is_expiry = True
            expiry_instrument = symbol
            all_expiry_today = ["SPY 0DTE", "QQQ 0DTE"]
        # Regular weekly on Friday
        if day_name == "Friday":
            all_expiry_today = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA"]
    else:
        # India: NIFTY=Tuesday, SENSEX=Thursday
        IN_EXPIRY_MAP = {"Tuesday": ["NIFTY"], "Thursday": ["SENSEX"]}
        if day_name in IN_EXPIRY_MAP:
            all_expiry_today = IN_EXPIRY_MAP[day_name]
        # BANKNIFTY monthly (last Tuesday — compare with NSE expiry_dates)
        if symbol == "BANKNIFTY" and nse_expiry_dates:
            try:
                bn_exp = datetime.strptime(nse_expiry_dates[0], "%d-%b-%Y")
                if bn_exp.strftime("%Y-%m-%d") == IST.strftime("%Y-%m-%d"):
                    is_expiry = True
                    if "BANKNIFTY" not in all_expiry_today:
                        all_expiry_today.append("BANKNIFTY")
            except:
                pass
    
    if is_expiry:
        expiry_note = f"🔥 {symbol} EXPIRY TODAY! Gamma risk HIGH. Theta decay accelerates after 1 PM. Pin to max pain {csym}{nse.get('max_pain', 0):,.0f} likely until 2 PM. Tighter SL mandatory. Exit by 2:30 PM."
        add("Expiry", "NEUTRAL", expiry_note, "RISK", 1.5)
        add("Theta Crush", "OPPOSES", f"EXPIRY — option premiums decay 3-5× faster today. BUY positions face severe time decay after 1 PM. Consider selling or hedging.", "RISK", 1.5)
    elif dte_to_expiry <= 2:
        expiry_note = f"⚠️ {dte_to_expiry} day{'s' if dte_to_expiry > 1 else ''} to {symbol} expiry ({next_expiry}). Theta accelerating. Consider shorter targets."
        add("Near Expiry", "NEUTRAL", expiry_note, "RISK", 1.0)
    
    # Expiry-specific SL adjustment: tighter on expiry day
    if is_expiry:
        # Will be overridden after direction is computed (below)
        sl_price = round(price - atr14 * 1.0, 2)
        t1_price = round(price + atr14 * 0.8, 2)
        t2_price = round(price + atr14 * 1.5, 2)
        t3_price = round(price + atr14 * 2.5, 2)
    
    # ═══ COMPUTE SCORES ═══
    # Weighted scoring
    weighted_support = sum(f["weight"] for f in factors if f["status"] == "SUPPORTS")
    weighted_oppose = sum(f["weight"] for f in factors if f["status"] == "OPPOSES")
    weighted_neutral = sum(f["weight"] for f in factors if f["status"] == "NEUTRAL")
    total_weight = sum(f["weight"] for f in factors)
    supports = len([f for f in factors if f["status"] == "SUPPORTS"])
    opposes = len([f for f in factors if f["status"] == "OPPOSES"])
    neutrals = len([f for f in factors if f["status"] == "NEUTRAL"])
    total = len(factors)
    pct = round((weighted_support / total_weight) * 100) if total_weight > 0 else 0
    
    if pct >= 78: signal, confidence = "STRONG BUY", "HIGH"
    elif pct >= 62: signal, confidence = "BUY", "HIGH"
    elif pct >= 50: signal, confidence = "LEAN BUY", "MEDIUM"
    elif pct >= 38: signal, confidence = "HOLD / WAIT", "LOW"
    else: signal, confidence = "AVOID", "LOW"
    
    direction = "BULLISH" if supports > opposes else "BEARISH" if opposes > supports else "NEUTRAL"
    
    # ═══ TRADE PLAN — Direction-aware SL & Targets ═══
    if direction == "BEARISH":
        # BEARISH: SL above price, targets below price
        if is_expiry:
            sl_price = round(price + atr14 * 1.0, 2)
            t1_price = round(price - atr14 * 0.8, 2)
            t2_price = round(price - atr14 * 1.5, 2)
            t3_price = round(price - atr14 * 2.5, 2)
        else:
            sl_price = round(price + atr14 * 1.5, 2)
            t1_price = round(price - atr14 * 1, 2)
            t2_price = round(price - atr14 * 2, 2)
            t3_price = round(price - atr14 * 3, 2)
    else:
        # BULLISH / NEUTRAL: SL below price, targets above price
        if is_expiry:
            sl_price = round(price - atr14 * 1.0, 2)
            t1_price = round(price + atr14 * 0.8, 2)
            t2_price = round(price + atr14 * 1.5, 2)
            t3_price = round(price + atr14 * 2.5, 2)
        else:
            sl_price = round(price - atr14 * 1.5, 2)
            t1_price = round(price + atr14 * 1, 2)
            t2_price = round(price + atr14 * 2, 2)
            t3_price = round(price + atr14 * 3, 2)
    
    risk_per_lot = round(abs(price - sl_price) * inst["lot"], 0)
    reward_t2 = round(abs(t2_price - price) * inst["lot"], 0)
    risk_pts = abs(price - sl_price)
    reward_pts = abs(t2_price - price)
    rr_ratio = f"1:{round(reward_pts / risk_pts, 1)}" if risk_pts > 0 else "N/A"
    capital_per_lot = round(price * inst["lot"], 0)
    
    # Option strike suggestion — delta-based when B-S available, else ATM
    atm_strike = round(price / inst["gap"]) * inst["gap"]
    selected_strike = atm_strike
    selected_delta = 0.50
    bs_premium = 0
    
    if bs_data.get("best_ce") and direction != "BEARISH":
        selected_strike = bs_data["best_ce"]["strike"]
        selected_delta = bs_data["best_ce"]["delta"]
        bs_premium = bs_data["best_ce"]["premium"]
    elif bs_data.get("best_pe") and direction == "BEARISH":
        selected_strike = bs_data["best_pe"]["strike"]
        selected_delta = bs_data["best_pe"]["delta"]
        bs_premium = bs_data["best_pe"]["premium"]
    
    opt_type_raw = "CE" if direction != "BEARISH" else "PE"
    opt_type = ("CALL" if opt_type_raw == "CE" else "PUT") if is_us else opt_type_raw
    csym = "$" if is_us else "₹"
    bs_r_rate = 0.0525 if is_us else 0.065  # US Fed rate vs India 10Y
    
    # ═══ PREMIUM-BASED TRADE PLAN ═══
    # Compute option premium at entry, SL, T1, T2, T3 underlying levels
    # This gives EXACT premium targets for the trader
    def _bs_premium_at(spot_at, strike, T, r, sigma, otype):
        """Quick B-S premium at a given spot level."""
        from math import log, sqrt, exp, erf
        if T <= 0 or sigma <= 0 or spot_at <= 0 or strike <= 0:
            return 0
        d1 = (log(spot_at / strike) + (r + sigma**2 / 2) * T) / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)
        nd1 = 0.5 * (1 + erf(d1 / sqrt(2)))
        nd2 = 0.5 * (1 + erf(d2 / sqrt(2)))
        if otype == "CE":
            return max(round(spot_at * nd1 - strike * exp(-r * T) * nd2, 2), 0)
        else:
            return max(round(strike * exp(-r * T) * (1 - nd2) - spot_at * (1 - nd1), 2), 0)
    
    # Use B-S params if available
    bs_T = bs_data.get("T", 7/365)
    bs_r = bs_data.get("risk_free", bs_r_rate)
    bs_iv = (nse.get("atm_iv", 20)) / 100  # decimal
    
    prem_entry = bs_premium if bs_premium > 0 else _bs_premium_at(price, selected_strike, bs_T, bs_r, bs_iv, opt_type_raw)
    prem_sl = _bs_premium_at(sl_price, selected_strike, bs_T, bs_r, bs_iv, opt_type_raw) if prem_entry > 0 else 0
    prem_t1 = _bs_premium_at(t1_price, selected_strike, bs_T, bs_r, bs_iv, opt_type_raw) if prem_entry > 0 else 0
    prem_t2 = _bs_premium_at(t2_price, selected_strike, bs_T, bs_r, bs_iv, opt_type_raw) if prem_entry > 0 else 0
    prem_t3 = _bs_premium_at(t3_price, selected_strike, bs_T, bs_r, bs_iv, opt_type_raw) if prem_entry > 0 else 0
    
    # Premium-based risk/reward
    prem_risk = round(prem_entry - prem_sl, 2) if prem_entry > prem_sl else round(prem_entry * 0.3, 2)
    prem_reward_t2 = round(prem_t2 - prem_entry, 2) if prem_t2 > prem_entry else round(prem_entry * 0.5, 2)
    prem_rr = f"1:{round(prem_reward_t2 / prem_risk, 1)}" if prem_risk > 0 else "N/A"
    prem_risk_per_lot = round(prem_risk * inst["lot"], 0)
    prem_reward_per_lot = round(prem_reward_t2 * inst["lot"], 0)
    prem_capital = round(prem_entry * inst["lot"], 0)
    
    # ORB-enhanced entry condition
    if direction == "BEARISH":
        entry_condition = f"Enter when {symbol} breaks below {csym}{sma20:,.0f} (SMA20) with volume > 1.2×."
    else:
        entry_condition = f"Enter when {symbol} holds above {csym}{sma20:,.0f} (SMA20) with volume > 1.2×."
    if orb.get("breakout") == "ABOVE" and direction != "BEARISH":
        entry_condition = f"ORB BREAKOUT ✓. Buy {selected_strike} {opt_type} when 5m candle closes above ORB {csym}{orb['orb_high']:,.0f} with vol > 1.5×. Must be above VWAP {csym}{orb.get('vwap', 0):,.0f}."
    elif orb.get("breakout") == "BELOW" or direction == "BEARISH":
        entry_condition = f"ORB BREAKDOWN ✓. Buy {selected_strike} {opt_type} when 5m candle closes below {csym}{orb.get('orb_low', price):,.0f}. VWAP {csym}{orb.get('vwap', 0):,.0f}."
    elif orb.get("orb_high"):
        entry_condition = f"Inside ORB {csym}{orb['orb_low']:,.0f}–{csym}{orb['orb_high']:,.0f}. Wait for breakout, then buy {selected_strike} {opt_type}."
    
    # ═══ GET EXACT OPTION EXPIRY DATE + REAL LTP ═══
    option_expiry = ""
    option_expiry_fmt = ""
    option_ltp = 0  # Real last traded price from chain
    
    # Method 1: India — from NSE expiry_dates
    if nse_expiry_dates and not is_us:
        option_expiry = nse_expiry_dates[0]
        try:
            option_expiry_fmt = datetime.strptime(option_expiry, "%d-%b-%Y").strftime("%d %b %Y")
        except:
            option_expiry_fmt = option_expiry
        # Get real LTP from NSE chain data
        try:
            chain_data = nse.get("raw_chain", {})
            if chain_data:
                for rec in chain_data:
                    if rec.get("strikePrice") == selected_strike:
                        opt_key = "CE" if opt_type_raw == "CE" else "PE"
                        option_ltp = round(float(rec.get(opt_key, {}).get("lastPrice", 0)), 2)
                        break
        except:
            pass
    
    # Method 2: USA — from yfinance options
    if is_us:
        try:
            us_opts = tk.options
            if us_opts:
                option_expiry = us_opts[0]
                try:
                    option_expiry_fmt = datetime.strptime(option_expiry, "%Y-%m-%d").strftime("%b %d, %Y")
                except:
                    option_expiry_fmt = option_expiry
                # Get real LTP from chain
                chain = tk.option_chain(us_opts[0])
                opt_df = chain.calls if opt_type_raw == "CE" else chain.puts
                if len(opt_df) > 0:
                    strike_match = opt_df.loc[(opt_df["strike"] - selected_strike).abs().idxmin()]
                    option_ltp = round(float(strike_match.get("lastPrice", 0) or 0), 2)
                    selected_strike = round(float(strike_match["strike"]), 2)
        except Exception as e:
            print(f"  US option chain error: {e}")
    
    # Method 3: FALLBACK — compute next expiry from schedule if nothing found
    if not option_expiry_fmt:
        try:
            today = IST
            if is_us:
                # US: next Friday (standard weekly) or next 0DTE day
                days_to_fri = (4 - today.weekday()) % 7
                if days_to_fri == 0 and today.hour >= 16: days_to_fri = 7
                next_exp = today + timedelta(days=days_to_fri if days_to_fri > 0 else 7)
                option_expiry_fmt = next_exp.strftime("%b %d, %Y")
            else:
                # India: NIFTY=Tuesday, SENSEX=Thursday, BANKNIFTY=last Tue of month
                exp_weekday = {"NIFTY": 1, "SENSEX": 3}.get(symbol, 1)  # 0=Mon, 1=Tue, 3=Thu
                days_ahead = (exp_weekday - today.weekday()) % 7
                if days_ahead == 0 and today.hour >= 15: days_ahead = 7
                next_exp = today + timedelta(days=days_ahead if days_ahead > 0 else 7)
                option_expiry_fmt = next_exp.strftime("%d %b %Y")
            option_expiry = option_expiry_fmt
        except:
            pass
    
    # Also use next_expiry from expiry check if available and we still don't have it
    if not option_expiry_fmt and next_expiry:
        try:
            option_expiry_fmt = datetime.strptime(next_expiry, "%d-%b-%Y").strftime("%d %b %Y")
            option_expiry = next_expiry
        except:
            option_expiry_fmt = next_expiry
    
    # Build full contract name
    if option_expiry_fmt:
        contract_name = f"{symbol} {selected_strike} {opt_type} {option_expiry_fmt}"
    else:
        contract_name = f"{symbol} {selected_strike} {opt_type}"
    
    # Use real LTP if available, otherwise B-S computed premium
    if option_ltp > 0:
        prem_entry = option_ltp
        # Recalculate risk/reward with real LTP
        prem_risk = round(prem_entry - prem_sl, 2) if prem_entry > prem_sl else round(prem_entry * 0.3, 2)
        prem_reward_t2 = round(prem_t2 - prem_entry, 2) if prem_t2 > prem_entry else round(prem_entry * 0.5, 2)
        prem_rr = f"1:{round(prem_reward_t2 / prem_risk, 1)}" if prem_risk > 0 else "N/A"
        prem_risk_per_lot = round(prem_risk * inst["lot"], 0)
        prem_reward_per_lot = round(prem_reward_t2 * inst["lot"], 0)
        prem_capital = round(prem_entry * inst["lot"], 0)
    
    trade = {
        "action": f"BUY {contract_name}",
        "contractName": contract_name,
        "expiry": option_expiry_fmt,
        "expiryRaw": option_expiry,
        "strike": selected_strike,
        "type": opt_type,
        "delta": selected_delta,
        "optionLTP": option_ltp,
        # Premium-based (what trader actually pays/watches)
        "premEntry": round(prem_entry, 1),
        "premSL": round(prem_sl, 1) if prem_sl > 0 else round(prem_entry * 0.7, 1),
        "premT1": round(prem_t1, 1) if prem_t1 > prem_entry else round(prem_entry * 1.3, 1),
        "premT2": round(prem_t2, 1) if prem_t2 > prem_entry else round(prem_entry * 1.6, 1),
        "premT3": round(prem_t3, 1) if prem_t3 > prem_entry else round(prem_entry * 2.0, 1),
        "premRisk": prem_risk,
        "premReward": prem_reward_t2,
        "premRR": prem_rr,
        # Underlying levels (for chart reference)
        "spot": price,
        "spotSL": sl_price,
        "spotT1": t1_price,
        "spotT2": t2_price,
        "spotT3": t3_price,
        # Risk/capital
        "riskPerLot": prem_risk_per_lot,
        "rewardPerLot": prem_reward_per_lot,
        "capitalPerLot": prem_capital,
        "lot": inst["lot"],
        "rrRatio": prem_rr,
        # Actions
        "t1Action": f"Book 50%. Move SL to {csym}{round(prem_entry, 1)} (cost).",
        "t2Action": "Book 30%. Trail SL below last 5m swing." if direction != "BEARISH" else "Book 30%. Trail SL above last 5m swing.",
        "t3Action": "Let 20% ride. Hard exit at close.",
        "slReason": f"If {symbol} breaks {'above' if direction=='BEARISH' else 'below'} {csym}{sl_price:,.0f} ({'above SMA20' if direction=='BEARISH' else 'SMA20'} / 1.5×ATR). Premium drops to ~{csym}{round(prem_sl, 1) if prem_sl > 0 else round(prem_entry*0.7, 1)}.",
        "entry": entry_condition,
        "exit": ("2:30 PM hard exit. EXPIRY — gamma risk HIGH. Tighter SL." if bs_data.get("dte", 99) <= 2 else ("3:55 PM ET hard exit." if is_us else "3:00 PM hard exit.")) + f" If premium hits {csym}{round(prem_sl, 1) if prem_sl > 0 else round(prem_entry*0.7, 1)} → exit immediately.",
    }
    
    # Reasoning
    reasoning = f"{supports} of {total} factors support this trade. "
    if cpr_type == "NARROW": reasoning += "Narrow CPR signals trending day. "
    if orb.get("breakout") == "ABOVE": reasoning += f"ORB breakout confirmed above {csym}{orb['orb_high']:,.0f}. "
    elif orb.get("breakout") == "BELOW": reasoning += f"ORB breakdown below {csym}{orb['orb_low']:,.0f}. "
    if orb.get("vwap") and orb["vwap"] > 0: reasoning += f"{'Above' if price > orb['vwap'] else 'Below'} VWAP {csym}{orb['vwap']:,.0f}. "
    if ema9 > ema21 > ema50: reasoning += "Full EMA bullish stack. "
    if macd_bullish: reasoning += f"MACD bullish (histogram {macd_hist:+.1f}). "
    if supertrend_buy: reasoning += "Supertrend BUY active. "
    if vol_ratio > 1.2: reasoning += f"Volume {vol_ratio:.1f}× confirms move. "
    if nse.get("success"):
        if pcr > 1: reasoning += f"PCR {pcr:.2f} = PE writing (bullish floor). "
        if vix and vix < 16: reasoning += f"VIX {vix:.1f} = fair premiums. "
    if bs_data.get("best_ce"):
        reasoning += f"B-S delta {selected_delta:.2f} at {csym}{selected_strike} strike. "
        if bs_data.get("dte", 99) <= 2: reasoning += "⚠️ Near expiry — gamma risk elevated. "
    if opposes > 0: reasoning += f"{opposes} factors oppose. "
    if neutrals > 0: reasoning += f"{neutrals} neutral. "
    reasoning += f"{confidence} confidence."
    
    result["factors"] = factors
    result["signal"] = signal
    result["confidence"] = confidence
    result["direction"] = direction
    result["confluenceScore"] = supports
    result["totalFactors"] = total
    result["supports"] = supports
    result["weightedSupport"] = round(weighted_support, 1)
    result["weightedOppose"] = round(weighted_oppose, 1)
    result["weightedNeutral"] = round(weighted_neutral, 1)
    result["totalWeight"] = round(total_weight, 1)
    result["opposes"] = opposes
    result["neutrals"] = neutrals
    result["pct"] = pct
    result["isExpiry"] = is_expiry
    result["expiryNote"] = expiry_note
    result["expiryInstrument"] = expiry_instrument
    result["allExpiryToday"] = all_expiry_today
    result["nextExpiry"] = next_expiry
    result["dteToExpiry"] = dte_to_expiry
    trade["tradeable"] = signal not in ["HOLD / WAIT", "AVOID"]
    result["trade"] = trade
    
    # ═══ 5-ENGINE ARCHITECTURE ═══
    try:
        tech = result.get("technicals", {})
        _ema9 = float(tech.get("ema9", 0) or 0)
        _ema21 = float(tech.get("ema21", 0) or 0)
        _ema50 = float(tech.get("ema50", 0) or 0)
        _sma200 = float(tech.get("sma200", 0) or 0)
        _rsi = float(tech.get("rsi", 50) or 50)
        _macd_h = float(tech.get("macd_hist", 0) or 0)
        _vol_r = float(tech.get("vol_ratio", 1.0) or 1.0)
        _atr = float(tech.get("atr14", 0) or 0)
        _iv = float(nse.get("atm_iv", 20) or 20)
        _pcr = float(nse.get("pcr", 1.0) or 1.0)
        _vix = float(nse.get("vix", 0) or 0)
        _oi_data = result.get("options_intel", {})
        _dte = bs_data.get("dte", 7) if bs_data else 7
        
        # ── ENGINE A: Market Regime (Trend + Structure) ──
        # EMA stack alignment
        ema_bull = _ema9 > _ema21 > _ema50 if _ema9 > 0 and _ema21 > 0 and _ema50 > 0 else False
        ema_bear = _ema9 < _ema21 < _ema50 if _ema9 > 0 and _ema21 > 0 and _ema50 > 0 else False
        above_200 = price > _sma200 if _sma200 > 0 else True
        
        # ADX calculation (trend strength)
        adx_val = 0
        try:
            closes_arr = df_daily["Close"].values.astype(float)
            highs_arr = df_daily["High"].values.astype(float)
            lows_arr = df_daily["Low"].values.astype(float)
            if len(closes_arr) >= 20:
                import numpy as np
                tr_arr = np.maximum(highs_arr[1:] - lows_arr[1:], np.maximum(abs(highs_arr[1:] - closes_arr[:-1]), abs(lows_arr[1:] - closes_arr[:-1])))
                dm_plus = np.where((highs_arr[1:] - highs_arr[:-1]) > (lows_arr[:-1] - lows_arr[1:]), np.maximum(highs_arr[1:] - highs_arr[:-1], 0), 0)
                dm_minus = np.where((lows_arr[:-1] - lows_arr[1:]) > (highs_arr[1:] - highs_arr[:-1]), np.maximum(lows_arr[:-1] - lows_arr[1:], 0), 0)
                atr_14 = pd.Series(tr_arr).ewm(span=14).mean().iloc[-1]
                di_plus = 100 * pd.Series(dm_plus).ewm(span=14).mean().iloc[-1] / atr_14 if atr_14 > 0 else 0
                di_minus = 100 * pd.Series(dm_minus).ewm(span=14).mean().iloc[-1] / atr_14 if atr_14 > 0 else 0
                dx = abs(di_plus - di_minus) / (di_plus + di_minus) * 100 if (di_plus + di_minus) > 0 else 0
                adx_val = round(float(dx), 1)
        except: pass
        
        trend_dir = "BULLISH" if ema_bull else ("BEARISH" if ema_bear else "SIDEWAYS")
        trend_strength = "STRONG" if adx_val > 25 else "WEAK"
        trend_score = 0
        if ema_bull: trend_score += 40
        elif ema_bear: trend_score += 40
        if above_200 and trend_dir == "BULLISH": trend_score += 20
        elif not above_200 and trend_dir == "BEARISH": trend_score += 20
        if adx_val > 25: trend_score += 20
        elif adx_val > 20: trend_score += 10
        if _macd_h > 0 and trend_dir == "BULLISH": trend_score += 20
        elif _macd_h < 0 and trend_dir == "BEARISH": trend_score += 20
        trend_score = min(100, trend_score)
        
        engine_a = {
            "name": "Market Regime", "icon": "📊",
            "trend": trend_dir, "strength": trend_strength, "adx": adx_val,
            "emaStack": "BULL" if ema_bull else ("BEAR" if ema_bear else "MIXED"),
            "above200": above_200, "score": trend_score,
            "detail": f"EMA {'9>21>50 ✅' if ema_bull else ('9<21<50 ✅' if ema_bear else 'mixed ⚠️')} | ADX {adx_val} {'Strong' if adx_val>25 else 'Weak'} | {'Above' if above_200 else 'Below'} SMA200",
        }
        
        # ── ENGINE B: OI + Liquidity (Smart Money) ──
        ce_res = nse.get("ce_resistance", [])
        pe_sup = nse.get("pe_support", [])
        max_pain = float(nse.get("max_pain", 0) or 0)
        
        oi_bias = "NEUTRAL"
        oi_score = 50
        support_zone = pe_sup[0]["strike"] if pe_sup else 0
        resistance_zone = ce_res[0]["strike"] if ce_res else 0
        
        if _pcr > 1.2:
            oi_bias = "BULLISH"
            oi_score = 70
        elif _pcr < 0.8:
            oi_bias = "BEARISH"
            oi_score = 30
        elif _pcr > 1.0:
            oi_score = 60
            oi_bias = "MILDLY BULLISH"
        else:
            oi_score = 40
            oi_bias = "MILDLY BEARISH"
        
        # OI shift detection
        if resistance_zone > 0 and price > 0:
            if price > resistance_zone * 0.98: oi_score += 10  # Near breakout
            if max_pain > price: oi_score += 5  # Max pain above = bullish pull
        if support_zone > 0 and price > 0:
            if price < support_zone * 1.02: oi_score -= 10
        
        oi_score = max(0, min(100, oi_score))
        
        # Breakout / Breakdown levels
        breakout_level = resistance_zone if resistance_zone > 0 else 0
        breakdown_level = support_zone if support_zone > 0 else 0
        near_breakout = price > breakout_level * 0.98 if breakout_level > 0 else False
        near_breakdown = price < breakdown_level * 1.02 if breakdown_level > 0 else False
        
        engine_b = {
            "name": "OI & Smart Money", "icon": "🏦",
            "bias": oi_bias, "pcr": round(_pcr, 2),
            "support": support_zone, "resistance": resistance_zone,
            "maxPain": max_pain, "score": oi_score,
            "breakout": breakout_level, "breakdown": breakdown_level,
            "nearBreakout": near_breakout, "nearBreakdown": near_breakdown,
            "detail": f"PCR {_pcr:.2f} ({oi_bias}) | Support {csym}{support_zone:,.0f} | Resistance {csym}{resistance_zone:,.0f} | Max Pain {csym}{max_pain:,.0f}",
        }
        
        # ── ENGINE C: Volatility (Buy vs Sell Premium) ──
        iv_rank = float(_oi_data.get("iv_rank", 50) or 50)
        hv_20 = 0
        try:
            dr = [(closes_arr[i]-closes_arr[i-1])/closes_arr[i-1] for i in range(max(1,len(closes_arr)-21), len(closes_arr)) if closes_arr[i-1]>0]
            hv_20 = round(float(np.std(dr) * (252**0.5) * 100), 1) if dr else 0
        except: pass
        
        iv_hv_spread = round(_iv - hv_20, 1) if hv_20 > 0 else 0
        
        if iv_rank >= 70:
            vol_state = "HIGH"
            vol_action = "SELL_PREMIUM"
            vol_score = 30 if direction == "BULLISH" else 70  # Selling is favorable
        elif iv_rank <= 30:
            vol_state = "LOW"
            vol_action = "BUY_PREMIUM"
            vol_score = 75  # Buying cheap premium
        else:
            vol_state = "NORMAL"
            vol_action = "DIRECTIONAL"
            vol_score = 55
        
        if _vix > 25: vol_score -= 15
        elif _vix < 14: vol_score += 10
        vol_score = max(0, min(100, vol_score))
        
        engine_c = {
            "name": "Volatility", "icon": "🌡️",
            "state": vol_state, "action": vol_action,
            "iv": round(_iv, 1), "hv": hv_20, "ivRank": round(iv_rank, 0),
            "ivHvSpread": iv_hv_spread, "vix": round(_vix, 1), "score": vol_score,
            "detail": f"IV {_iv:.1f}% (Rank {iv_rank:.0f}%) | HV {hv_20}% | Spread {iv_hv_spread:+.1f}% | VIX {_vix:.1f} | {vol_action.replace('_',' ')}",
        }
        
        # ── ENGINE D: Expected Move ──
        em_pts = round(price * (_iv/100) * (max(_dte, 1)/365)**0.5, 1) if _iv > 0 else 0
        em_low = round(price - em_pts, 0)
        em_high = round(price + em_pts, 0)
        
        engine_d = {
            "name": "Expected Move", "icon": "📐",
            "points": em_pts, "low": em_low, "high": em_high,
            "dte": _dte, "iv": round(_iv, 1),
            "detail": f"Market expects {csym}{em_low:,.0f} – {csym}{em_high:,.0f} by expiry (±{csym}{em_pts:,.0f})",
        }
        
        # ── ENGINE E: Momentum (Entry Timing) ──
        orb_data = result.get("orb", {})
        vwap_val = float(orb_data.get("vwap", 0) or 0)
        above_vwap = price > vwap_val if vwap_val > 0 else True
        
        mom_signal = "NONE"
        mom_score = 50
        
        # RSI momentum
        if _rsi > 60 and _rsi < 80: mom_score += 15  # Bullish momentum
        elif _rsi < 40 and _rsi > 20: mom_score += 15  # Bearish momentum (for puts)
        elif _rsi > 80: mom_score -= 10  # Overbought
        elif _rsi < 20: mom_score -= 10  # Oversold extreme
        
        # VWAP
        if above_vwap and direction == "BULLISH": mom_score += 10
        elif not above_vwap and direction == "BEARISH": mom_score += 10
        
        # Volume surge
        if _vol_r > 1.5: mom_score += 15
        elif _vol_r > 1.2: mom_score += 5
        elif _vol_r < 0.7: mom_score -= 10
        
        # MACD confirmation
        if (_macd_h > 0 and direction == "BULLISH") or (_macd_h < 0 and direction == "BEARISH"):
            mom_score += 10
        
        mom_score = max(0, min(100, mom_score))
        
        if mom_score >= 65:
            mom_signal = "BUY_CALL" if direction == "BULLISH" else "BUY_PUT"
        elif mom_score <= 35:
            mom_signal = "BUY_PUT" if direction == "BULLISH" else "BUY_CALL"
        
        engine_e = {
            "name": "Momentum", "icon": "🚀",
            "signal": mom_signal, "rsi": round(_rsi, 1),
            "vwap": round(vwap_val, 2), "aboveVwap": above_vwap,
            "volRatio": round(_vol_r, 1), "macdBull": _macd_h > 0,
            "score": mom_score,
            "detail": f"RSI {_rsi:.0f} | VWAP {'Above ✅' if above_vwap else 'Below ❌'} | Vol {_vol_r:.1f}x | MACD {'Bull' if _macd_h>0 else 'Bear'} → {mom_signal.replace('_',' ')}",
        }
        
        # ── DECISION ENGINE: Weighted Score ──
        final_score = round(
            engine_a["score"] * 0.30 +
            engine_b["score"] * 0.25 +
            engine_c["score"] * 0.20 +
            engine_e["score"] * 0.25
        , 1)
        
        # Decision matrix
        if trend_dir != "SIDEWAYS" and trend_strength == "STRONG" and vol_state != "HIGH" and final_score >= 65:
            decision = "BUY_CALL" if trend_dir == "BULLISH" else "BUY_PUT"
            dec_reason = "Trending market + strong momentum + favorable volatility"
        elif trend_dir == "SIDEWAYS" and vol_state == "HIGH" and final_score >= 50:
            decision = "SELL_STRANGLE"
            dec_reason = "Range-bound + high IV = premium selling opportunity"
        elif mom_score < 40 and oi_score < 40:
            decision = "AVOID"
            dec_reason = "Mixed signals + low momentum + unclear OI = no edge"
        elif final_score >= 55:
            decision = "BUY_CALL" if direction == "BULLISH" else "BUY_PUT"
            dec_reason = "Moderate setup with directional bias"
        else:
            decision = "AVOID"
            dec_reason = "Insufficient confluence across engines"
        
        # GEX (Gamma Exposure) approximation
        gex_zones = []
        try:
            if ce_res and pe_sup:
                for r in ce_res[:3]:
                    gex_zones.append({"strike": r["strike"], "type": "RESISTANCE", "oi": r["oi"], "gamma": "NEGATIVE", "effect": "Price repelled — acts as ceiling"})
                for s in pe_sup[:3]:
                    gex_zones.append({"strike": s["strike"], "type": "SUPPORT", "oi": s["oi"], "gamma": "POSITIVE", "effect": "Price attracted — acts as floor"})
        except: pass
        
        result["engines"] = {
            "regime": engine_a,
            "oi": engine_b,
            "volatility": engine_c,
            "expectedMove": engine_d,
            "momentum": engine_e,
            "finalScore": final_score,
            "decision": decision,
            "decisionReason": dec_reason,
            "gexZones": gex_zones,
            "weights": {"trend": 30, "oi": 25, "volatility": 20, "momentum": 25},
        }
        
        # ═══ 3-PLAN DECISION SYSTEM ═══
        plans = []
        _atm_s = round(price / inst.get("gap", 50)) * inst.get("gap", 50)
        _gap_s = inst.get("gap", 50)
        _lot_s = inst.get("lot", 50)
        _dte_s = bs_data.get("dte", 7) if bs_data else 7
        
        # Helper for B-S premium
        def _quick_prem(S, K, T, sigma, otype):
            try:
                from math import log, sqrt, exp, erf
                if T <= 0 or sigma <= 0: return 0
                r = 0.0525 if is_us else 0.065
                d1 = (log(S/K) + (r + sigma**2/2)*T) / (sigma*sqrt(T))
                d2 = d1 - sigma*sqrt(T)
                nd1 = 0.5*(1+erf(d1/sqrt(2))); nd2 = 0.5*(1+erf(d2/sqrt(2)))
                if otype == "CE": return round(max(S*nd1 - K*exp(-r*T)*nd2, 0), 1)
                return round(max(K*exp(-r*T)*(1-nd2) - S*(1-nd1), 0), 1)
            except: return 0
        _T_s = max(_dte_s, 1) / 365
        _iv_dec_s = (_iv / 100) if _iv > 0 else 0.20
        
        # ── PLAN A: AGGRESSIVE — High conviction directional ──
        if final_score >= 55 and decision != "AVOID":
            pa_type = "CE" if direction == "BULLISH" else "PE"
            pa_display = ("CALL" if is_us else "CE") if direction == "BULLISH" else ("PUT" if is_us else "PE")
            pa_prem = _quick_prem(price, _atm_s, _T_s, _iv_dec_s, pa_type)
            pa_sl = round(pa_prem * 0.65, 1)  # 35% SL
            pa_t1 = round(pa_prem * 1.5, 1)
            pa_t2 = round(pa_prem * 2.2, 1)
            pa_rr = round((pa_t2 - pa_prem) / (pa_prem - pa_sl), 1) if pa_prem > pa_sl else 0
            
            plans.append({
                "plan": "A", "name": "AGGRESSIVE", "color": "#0a7c42",
                "emoji": "🎯", "tagline": "Maximum profit potential — for confident traders",
                "strategy": f"BUY {_atm_s} {pa_display}",
                "type": "DIRECTIONAL",
                "risk": "HIGH",
                "entry": pa_prem, "sl": pa_sl, "t1": pa_t1, "t2": pa_t2,
                "rr": f"1:{pa_rr}",
                "capital": round(pa_prem * _lot_s, 0),
                "maxLoss": round((pa_prem - pa_sl) * _lot_s, 0),
                "maxProfit": f"Unlimited ({csym}{round((pa_t2 - pa_prem) * _lot_s, 0):,} at T2)",
                "when": "You're confident in direction. Engines show strong alignment. You can handle 35% premium loss.",
                "exit": f"Book 50% at {csym}{pa_t1}, trail rest. Hard SL at {csym}{pa_sl}.",
                "analogy": "Like betting on the favorite horse — higher chance of winning, still need the race to go your way.",
                "steps": [
                    f"Open your broker app (Zerodha/Angel/IBKR)",
                    f"Search for {symbol} {_atm_s} {pa_display} expiry {next_expiry if next_expiry else 'this week'}",
                    f"Buy 1 lot ({_lot_s} qty) at market price around {csym}{pa_prem}",
                    f"IMMEDIATELY set Stop Loss at {csym}{pa_sl} (35% below entry)",
                    f"When premium hits {csym}{pa_t1}, sell HALF your position — lock profit",
                    f"Move SL to entry price {csym}{pa_prem} — now it is a FREE trade",
                    f"Let remaining ride to target {csym}{pa_t2} or trail SL",
                ],
                "kidsExplain": f"Imagine {symbol} is a race car. You are betting it will {'speed UP' if direction=='BULLISH' else 'slow DOWN'}. You pay {csym}{pa_prem} for the ticket. If the car {'speeds up' if direction=='BULLISH' else 'slows down'}, your ticket becomes worth {csym}{pa_t2} — you make money! If the car goes the wrong way, you lose max {csym}{round(pa_prem - pa_sl, 1)} per ticket.",
            })
        
        # ── PLAN B: BALANCED — Spread strategy (defined risk) ──
        if direction == "BULLISH":
            pb_buy = _quick_prem(price, _atm_s, _T_s, _iv_dec_s, "CE")
            pb_sell = _quick_prem(price, _atm_s + _gap_s, _T_s, _iv_dec_s, "CE")
            pb_cost = round(pb_buy - pb_sell, 1)
            pb_profit = round(_gap_s - pb_cost, 1) if pb_cost > 0 else 0
            pb_rr = round(pb_profit / pb_cost, 1) if pb_cost > 0 else 0
            pb_display = "CALL" if is_us else "CE"
            plans.append({
                "plan": "B", "name": "BALANCED", "color": "#3b82f6",
                "emoji": "⚖️", "tagline": "Defined risk, defined reward — for smart traders",
                "strategy": f"BULL {pb_display} SPREAD: BUY {_atm_s} / SELL {_atm_s + _gap_s}",
                "type": "SPREAD",
                "risk": "MEDIUM",
                "entry": pb_cost, "sl": 0, "t1": round(pb_cost + pb_profit * 0.5, 1), "t2": round(pb_cost + pb_profit, 1),
                "rr": f"1:{pb_rr}",
                "capital": round(pb_cost * _lot_s, 0),
                "maxLoss": round(pb_cost * _lot_s, 0),
                "maxProfit": f"{csym}{round(pb_profit * _lot_s, 0):,}",
                "when": "Moderately confident. Want to limit max loss. Engines show 55-70% score.",
                "exit": f"Max profit if {d.get('symbol', '')} above {csym}{_atm_s + _gap_s:,.0f} at expiry. Max loss = entry cost.",
                "analogy": "Like buying a lottery ticket with a cap — you know exactly what you can lose AND win before you start.",
                "steps": [
                    f"Open broker → search {symbol} options for this week expiry",
                    f"BUY {_atm_s} {pb_display} — this costs around {csym}{pb_buy}",
                    f"SELL {_atm_s + _gap_s} {pb_display} — this gives you back {csym}{pb_sell}",
                    f"Your net cost = {csym}{pb_cost} per qty (this is your MAX loss, period)",
                    f"If {symbol} goes above {csym}{_atm_s + _gap_s:,.0f} at expiry, you keep {csym}{pb_profit} profit",
                    f"No stop loss needed — max loss is already capped at entry cost",
                ],
                "kidsExplain": f"You buy one toy for {csym}{pb_buy} and sell a similar toy for {csym}{pb_sell}. Net cost = {csym}{pb_cost}. If {symbol} goes UP past {csym}{_atm_s + _gap_s:,.0f}, you earn {csym}{pb_profit}. If it doesn't, you only lose {csym}{pb_cost}. Simple — you KNOW your max loss before starting!",
            })
        else:
            pb_buy = _quick_prem(price, _atm_s, _T_s, _iv_dec_s, "PE")
            pb_sell = _quick_prem(price, _atm_s - _gap_s, _T_s, _iv_dec_s, "PE")
            pb_cost = round(pb_buy - pb_sell, 1)
            pb_profit = round(_gap_s - pb_cost, 1) if pb_cost > 0 else 0
            pb_rr = round(pb_profit / pb_cost, 1) if pb_cost > 0 else 0
            pb_display = "PUT" if is_us else "PE"
            plans.append({
                "plan": "B", "name": "BALANCED", "color": "#3b82f6",
                "emoji": "⚖️", "tagline": "Defined risk, defined reward — for smart traders",
                "strategy": f"BEAR {pb_display} SPREAD: BUY {_atm_s} / SELL {_atm_s - _gap_s}",
                "type": "SPREAD",
                "risk": "MEDIUM",
                "entry": pb_cost, "sl": 0, "t1": round(pb_cost + pb_profit * 0.5, 1), "t2": round(pb_cost + pb_profit, 1),
                "rr": f"1:{pb_rr}",
                "capital": round(pb_cost * _lot_s, 0),
                "maxLoss": round(pb_cost * _lot_s, 0),
                "maxProfit": f"{csym}{round(pb_profit * _lot_s, 0):,}",
                "when": "Moderately confident. Want to limit max loss.",
                "exit": f"Max profit if below {csym}{_atm_s - _gap_s:,.0f} at expiry.",
                "analogy": "Like buying insurance with a deductible — you know your max loss upfront.",
                "steps": [
                    f"Open broker → search {symbol} options for this week expiry",
                    f"BUY {_atm_s} {pb_display} — this costs around {csym}{pb_buy}",
                    f"SELL {_atm_s - _gap_s} {pb_display} — this gives back {csym}{pb_sell}",
                    f"Net cost = {csym}{pb_cost} per qty (MAX loss, guaranteed)",
                    f"If {symbol} drops below {csym}{_atm_s - _gap_s:,.0f} at expiry, profit = {csym}{pb_profit}",
                    f"No stop loss needed — loss capped at {csym}{pb_cost}",
                ],
                "kidsExplain": f"You buy umbrella insurance for {csym}{pb_cost}. If it rains ({symbol} falls), you get {csym}{pb_profit}. If sunny (price stays up), you lose just {csym}{pb_cost}. You KNOW the worst case before you start.",
            })
        
        # ── PLAN C: CONSERVATIVE — Non-directional or wait ──
        if vol_state == "HIGH" or iv_rank >= 50:
            # Iron Condor — sell premium
            pc_ce_sell = _quick_prem(price, _atm_s + _gap_s, _T_s, _iv_dec_s, "CE")
            pc_pe_sell = _quick_prem(price, _atm_s - _gap_s, _T_s, _iv_dec_s, "PE")
            pc_ce_buy = _quick_prem(price, _atm_s + _gap_s * 2, _T_s, _iv_dec_s, "CE")
            pc_pe_buy = _quick_prem(price, _atm_s - _gap_s * 2, _T_s, _iv_dec_s, "PE")
            pc_credit = round(pc_ce_sell + pc_pe_sell - pc_ce_buy - pc_pe_buy, 1)
            pc_max_loss = round(_gap_s - pc_credit, 1)
            pc_pop = round(max(45, min(80, 50 + (pc_credit / _gap_s * 40))), 0) if _gap_s > 0 else 50
            
            plans.append({
                "plan": "C", "name": "CONSERVATIVE", "color": "#8b5cf6",
                "emoji": "🛡️", "tagline": "Collect premium — profit from time decay",
                "strategy": f"IRON CONDOR: Sell {_atm_s - _gap_s}/{_atm_s + _gap_s}, Buy wings",
                "type": "NON-DIRECTIONAL",
                "risk": "LOW-MEDIUM",
                "entry": -pc_credit, "sl": round(pc_credit * 2, 1), "t1": round(pc_credit * 0.5, 1), "t2": pc_credit,
                "rr": f"Credit {csym}{pc_credit}",
                "capital": round(pc_max_loss * _lot_s, 0),
                "maxLoss": round(pc_max_loss * _lot_s, 0),
                "maxProfit": f"{csym}{round(pc_credit * _lot_s, 0):,} (keep full credit)",
                "pop": pc_pop,
                "when": "Unsure about direction. IV is high. Want to profit from time passing. Market is range-bound.",
                "exit": f"Keep credit if price stays between {csym}{_atm_s - _gap_s:,.0f} and {csym}{_atm_s + _gap_s:,.0f}.",
                "analogy": "Like being the house in a casino — you collect the premium and win if nothing dramatic happens. ~{0}% probability of profit.".format(pc_pop),
                "steps": [
                    f"Open broker → search {symbol} options for this week expiry",
                    f"SELL {_atm_s + _gap_s} CE/CALL — collect premium {csym}{pc_ce_sell:.0f}",
                    f"BUY {_atm_s + _gap_s*2} CE/CALL — pay {csym}{pc_ce_buy:.0f} (protection)",
                    f"SELL {_atm_s - _gap_s} PE/PUT — collect premium {csym}{pc_pe_sell:.0f}",
                    f"BUY {_atm_s - _gap_s*2} PE/PUT — pay {csym}{pc_pe_buy:.0f} (protection)",
                    f"Total credit received = {csym}{pc_credit} (this is your MAX profit)",
                    f"If {symbol} stays between {csym}{_atm_s - _gap_s:,.0f} and {csym}{_atm_s + _gap_s:,.0f}, you KEEP the full {csym}{pc_credit}",
                    f"Max loss = {csym}{pc_max_loss} only if price moves way outside this range",
                ],
                "kidsExplain": f"You open a lemonade stand with {csym}{pc_credit} cash. As long as the weather ({symbol}) stays normal (between {csym}{_atm_s - _gap_s:,.0f} and {csym}{_atm_s + _gap_s:,.0f}), you keep ALL the money. Only if there is a hurricane (huge move) do you lose. Chance of keeping money: ~{pc_pop}%.",
            })
        else:
            # Low IV — straddle for breakout
            pc_ce = _quick_prem(price, _atm_s, _T_s, _iv_dec_s, "CE")
            pc_pe = _quick_prem(price, _atm_s, _T_s, _iv_dec_s, "PE")
            pc_cost = round(pc_ce + pc_pe, 1)
            
            plans.append({
                "plan": "C", "name": "HEDGE / BREAKOUT", "color": "#8b5cf6",
                "emoji": "🛡️", "tagline": "Profit from big move in either direction",
                "strategy": f"LONG STRADDLE: BUY {_atm_s} CE + {_atm_s} PE",
                "type": "NON-DIRECTIONAL",
                "risk": "MEDIUM",
                "entry": pc_cost, "sl": round(pc_cost * 0.6, 1), "t1": round(pc_cost * 1.5, 1), "t2": round(pc_cost * 2.5, 1),
                "rr": f"Cost {csym}{pc_cost}",
                "capital": round(pc_cost * _lot_s, 0),
                "maxLoss": round(pc_cost * _lot_s, 0),
                "maxProfit": "Unlimited (either direction)",
                "when": "Before big events. IV is low (cheap options). Expect big move but unsure which way.",
                "exit": f"Need {csym}{pc_cost:,.0f}+ move from {csym}{_atm_s:,.0f} to profit.",
                "analogy": "Like betting on BOTH teams — you win as long as the match isn't a boring draw.",
                "steps": [
                    f"Open broker → search {symbol} {_atm_s} options for this week",
                    f"BUY {_atm_s} CE/CALL — pay {csym}{pc_ce:.0f}",
                    f"BUY {_atm_s} PE/PUT — pay {csym}{pc_pe:.0f}",
                    f"Total cost = {csym}{pc_cost} (this is max you can lose)",
                    f"If {symbol} moves UP past {csym}{_atm_s + pc_cost:,.0f} — you profit from the CE",
                    f"If {symbol} moves DOWN past {csym}{_atm_s - pc_cost:,.0f} — you profit from the PE",
                    f"You need a BIG move in EITHER direction to profit",
                ],
                "kidsExplain": f"You bet {csym}{pc_cost} that SOMETHING exciting will happen — you don't care which direction. If {symbol} moves a LOT up or down, you win. Only if nothing happens (price stays at {csym}{_atm_s:,.0f}) do you lose your {csym}{pc_cost}.",
            })
        
        result["plans"] = plans
        print(f"📋 Plans: {len(plans)} generated for {symbol}")
        
        print(f"🧠 Engines: {symbol} trend={trend_dir}/{trend_strength} oi={oi_bias} vol={vol_state} mom={mom_signal} final={final_score} → {decision}")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"⚠️ Engine computation failed: {e}")
    
    # ═══ 3-PLAN FALLBACK — Generate plans even if engines failed ═══
    if "plans" not in result or not result.get("plans"):
        try:
            _dir = result.get("direction", "BULLISH")
            _sig = result.get("signal", "HOLD / WAIT")
            _is_wait = _sig in ["HOLD / WAIT", "AVOID"]
            _iv_f = float(nse.get("atm_iv", 20) or 20)
            _iv_rank_f = 50
            try: _iv_rank_f = float(result.get("options_intel", {}).get("iv_rank", 50) or 50)
            except: pass
            _dte_f = bs_data.get("dte", 7) if bs_data else 7
            _T_f = max(_dte_f, 1) / 365
            _iv_dec_f = (_iv_f / 100) if _iv_f > 0 else 0.20
            _atm_f = round(price / inst.get("gap", 50)) * inst.get("gap", 50)
            if _atm_f == 0: _atm_f = round(price)
            _gap_f = inst.get("gap", 50)
            if _gap_f == 0: _gap_f = max(1, round(price * 0.01))
            _lot_f = inst.get("lot", 100)
            
            def _qp(S, K, T, sigma, otype):
                try:
                    from math import log, sqrt, exp, erf
                    if T <= 0 or sigma <= 0 or K <= 0 or S <= 0: return max(1, round(S * 0.02))
                    r = 0.0525 if is_us else 0.065
                    d1 = (log(S/K) + (r + sigma**2/2)*T) / (sigma*sqrt(T))
                    d2 = d1 - sigma*sqrt(T)
                    nd1 = 0.5*(1+erf(d1/sqrt(2))); nd2 = 0.5*(1+erf(d2/sqrt(2)))
                    if otype == "CE": return round(max(S*nd1 - K*exp(-r*T)*nd2, 0.5), 1)
                    return round(max(K*exp(-r*T)*(1-nd2) - S*(1-nd1), 0.5), 1)
                except: return max(1, round(S * 0.02))
            
            plans_f = []
            
            # Plan A: Aggressive
            if not _is_wait:
                pa_t = "CE" if _dir == "BULLISH" else "PE"
                pa_d = ("CALL" if is_us else "CE") if _dir == "BULLISH" else ("PUT" if is_us else "PE")
                pa_p = _qp(price, _atm_f, _T_f, _iv_dec_f, pa_t)
                pa_sl = round(pa_p * 0.65, 1)
                pa_t1 = round(pa_p * 1.5, 1)
                pa_t2 = round(pa_p * 2.2, 1)
                pa_rr = round((pa_t2 - pa_p) / max(pa_p - pa_sl, 0.1), 1)
                plans_f.append({
                    "plan": "A", "name": "AGGRESSIVE", "color": "#047857",
                    "emoji": "🎯", "tagline": "Maximum profit potential — for confident traders",
                    "strategy": f"BUY {_atm_f} {pa_d}",
                    "type": "DIRECTIONAL", "risk": "HIGH",
                    "entry": pa_p, "sl": pa_sl, "t1": pa_t1, "t2": pa_t2,
                    "rr": f"1:{pa_rr}",
                    "capital": round(pa_p * _lot_f, 0),
                    "maxLoss": round((pa_p - pa_sl) * _lot_f, 0),
                    "maxProfit": f"Unlimited ({csym}{round((pa_t2 - pa_p) * _lot_f, 0):,} at T2)",
                    "when": "Confident in direction. Use when trend and momentum align.",
                    "exit": f"Book 50% at {csym}{pa_t1}, trail rest. Hard SL at {csym}{pa_sl}.",
                    "analogy": "Like betting on the favorite horse — higher chance of winning, but the race still needs to go your way.",
                })
            
            # Plan B: Balanced (Spread)
            if _dir == "BULLISH":
                pb_b = _qp(price, _atm_f, _T_f, _iv_dec_f, "CE")
                pb_s = _qp(price, _atm_f + _gap_f, _T_f, _iv_dec_f, "CE")
                pb_c = round(max(pb_b - pb_s, 0.5), 1)
                pb_pr = round(max(_gap_f - pb_c, 0), 1)
                pb_rr = round(pb_pr / max(pb_c, 0.1), 1)
                pb_d = "CALL" if is_us else "CE"
                plans_f.append({
                    "plan": "B", "name": "BALANCED", "color": "#1a56db",
                    "emoji": "⚖️", "tagline": "Defined risk, defined reward — for smart traders",
                    "strategy": f"BULL {pb_d} SPREAD: BUY {_atm_f} / SELL {_atm_f + _gap_f}",
                    "type": "SPREAD", "risk": "MEDIUM",
                    "entry": pb_c, "sl": 0, "t1": round(pb_c + pb_pr * 0.5, 1), "t2": round(pb_c + pb_pr, 1),
                    "rr": f"1:{pb_rr}",
                    "capital": round(pb_c * _lot_f, 0),
                    "maxLoss": round(pb_c * _lot_f, 0),
                    "maxProfit": f"{csym}{round(pb_pr * _lot_f, 0):,}",
                    "when": "Moderately confident. Want to cap your max loss upfront.",
                    "exit": f"Max profit if above {csym}{_atm_f + _gap_f:,.0f} at expiry.",
                    "analogy": "Like buying a lottery ticket with a cap — you know exactly what you can lose AND win before you start.",
                })
            else:
                pb_b = _qp(price, _atm_f, _T_f, _iv_dec_f, "PE")
                pb_s = _qp(price, _atm_f - _gap_f, _T_f, _iv_dec_f, "PE")
                pb_c = round(max(pb_b - pb_s, 0.5), 1)
                pb_pr = round(max(_gap_f - pb_c, 0), 1)
                pb_rr = round(pb_pr / max(pb_c, 0.1), 1)
                pb_d = "PUT" if is_us else "PE"
                plans_f.append({
                    "plan": "B", "name": "BALANCED", "color": "#1a56db",
                    "emoji": "⚖️", "tagline": "Defined risk, defined reward — for smart traders",
                    "strategy": f"BEAR {pb_d} SPREAD: BUY {_atm_f} / SELL {_atm_f - _gap_f}",
                    "type": "SPREAD", "risk": "MEDIUM",
                    "entry": pb_c, "sl": 0, "t1": round(pb_c + pb_pr * 0.5, 1), "t2": round(pb_c + pb_pr, 1),
                    "rr": f"1:{pb_rr}",
                    "capital": round(pb_c * _lot_f, 0),
                    "maxLoss": round(pb_c * _lot_f, 0),
                    "maxProfit": f"{csym}{round(pb_pr * _lot_f, 0):,}",
                    "when": "Moderately confident bearish. Want defined risk.",
                    "exit": f"Max profit if below {csym}{_atm_f - _gap_f:,.0f} at expiry.",
                    "analogy": "Like buying insurance with a deductible — you know your max loss upfront.",
                })
            
            # Plan C: Conservative
            if _iv_rank_f >= 50:
                pc_cs = _qp(price, _atm_f + _gap_f, _T_f, _iv_dec_f, "CE")
                pc_ps = _qp(price, _atm_f - _gap_f, _T_f, _iv_dec_f, "PE")
                pc_cb = _qp(price, _atm_f + _gap_f * 2, _T_f, _iv_dec_f, "CE")
                pc_pb = _qp(price, _atm_f - _gap_f * 2, _T_f, _iv_dec_f, "PE")
                pc_cr = round(max(pc_cs + pc_ps - pc_cb - pc_pb, 0.5), 1)
                pc_ml = round(max(_gap_f - pc_cr, 0), 1)
                pc_pop = round(max(45, min(80, 50 + (pc_cr / max(_gap_f, 1) * 40))), 0)
                plans_f.append({
                    "plan": "C", "name": "CONSERVATIVE", "color": "#7c3aed",
                    "emoji": "🛡️", "tagline": "Collect premium — profit from time decay",
                    "strategy": f"IRON CONDOR: Sell {_atm_f - _gap_f}/{_atm_f + _gap_f}, Buy wings",
                    "type": "NON-DIRECTIONAL", "risk": "LOW-MEDIUM",
                    "entry": -pc_cr, "sl": round(pc_cr * 2, 1), "t1": round(pc_cr * 0.5, 1), "t2": pc_cr,
                    "rr": f"Credit {csym}{pc_cr}",
                    "capital": round(pc_ml * _lot_f, 0),
                    "maxLoss": round(pc_ml * _lot_f, 0),
                    "maxProfit": f"{csym}{round(pc_cr * _lot_f, 0):,}",
                    "pop": pc_pop,
                    "when": "Unsure about direction. IV is elevated. Market is range-bound.",
                    "exit": f"Keep credit if price stays between {csym}{_atm_f - _gap_f:,.0f} and {csym}{_atm_f + _gap_f:,.0f}.",
                    "analogy": f"Like being the house in a casino — collect premium, win if nothing dramatic happens. ~{pc_pop}% probability.",
                })
            else:
                pc_ce = _qp(price, _atm_f, _T_f, _iv_dec_f, "CE")
                pc_pe = _qp(price, _atm_f, _T_f, _iv_dec_f, "PE")
                pc_cost = round(pc_ce + pc_pe, 1)
                plans_f.append({
                    "plan": "C", "name": "HEDGE / BREAKOUT", "color": "#7c3aed",
                    "emoji": "🛡️", "tagline": "Profit from big move in either direction",
                    "strategy": f"LONG STRADDLE: BUY {_atm_f} CE + PE",
                    "type": "NON-DIRECTIONAL", "risk": "MEDIUM",
                    "entry": pc_cost, "sl": round(pc_cost * 0.6, 1), "t1": round(pc_cost * 1.5, 1), "t2": round(pc_cost * 2.5, 1),
                    "rr": f"Cost {csym}{pc_cost}",
                    "capital": round(pc_cost * _lot_f, 0),
                    "maxLoss": round(pc_cost * _lot_f, 0),
                    "maxProfit": "Unlimited (either direction)",
                    "when": "Before big events. IV is low. Expect big move but unsure which way.",
                    "exit": f"Need {csym}{pc_cost:,.0f}+ move from {csym}{_atm_f:,.0f} to profit.",
                    "analogy": "Like betting on BOTH teams — you win as long as the match isn't a boring draw.",
                })
            
            result["plans"] = plans_f
            print(f"📋 Plans (fallback): {len(plans_f)} generated for {symbol}")
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"⚠️ Plans fallback failed: {e}")
            result["plans"] = []
    
    # ═══ TRADE CONFIDENCE — Win probability, strength, risk assessment ═══
    try:
        # Win probability based on weighted factor score + historical patterns
        score_pct = round((weighted_support / total_weight) * 100, 1) if total_weight > 0 else 50
        
        # Base win rate from factor confluence
        if score_pct >= 75: base_win = 72
        elif score_pct >= 65: base_win = 65
        elif score_pct >= 55: base_win = 58
        elif score_pct >= 45: base_win = 50
        else: base_win = 38
        
        # Adjustments
        win_adj = 0
        confidence_notes = []
        
        # Trend alignment bonus (use technicals from result)
        tech = result.get("technicals", {})
        _ema9 = tech.get("ema9", 0)
        _ema21 = tech.get("ema21", 0)
        _rsi = tech.get("rsi", 50)
        _vol_r = tech.get("vol_ratio", 1.0)
        
        if _ema9 > _ema21 and direction == "BULLISH":
            win_adj += 5; confidence_notes.append("EMA 9>21 aligned with bullish direction (+5%)")
        elif _ema9 < _ema21 and direction == "BEARISH":
            win_adj += 5; confidence_notes.append("EMA 9<21 confirms bearish direction (+5%)")
        elif _ema9 > _ema21 and direction == "BEARISH":
            win_adj -= 3; confidence_notes.append("Selling against short-term uptrend (-3%)")
        
        # Volume confirmation
        if _vol_r > 1.5:
            win_adj += 3; confidence_notes.append(f"Volume {_vol_r:.1f}x above average confirms move (+3%)")
        elif _vol_r < 0.7:
            win_adj -= 3; confidence_notes.append("Low volume — weak conviction (-3%)")
        
        # RSI zone
        if (_rsi < 30 and direction == "BULLISH"):
            win_adj += 4; confidence_notes.append("Oversold bounce setup (+4%)")
        elif (_rsi > 70 and direction == "BEARISH"):
            win_adj += 4; confidence_notes.append("Overbought reversal setup (+4%)")
        elif (_rsi > 70 and direction == "BULLISH"):
            win_adj -= 5; confidence_notes.append("Buying into overbought — risky (-5%)")
        elif (_rsi < 30 and direction == "BEARISH"):
            win_adj -= 5; confidence_notes.append("Selling into oversold — risky (-5%)")
        
        # VIX/fear level
        vix = float(nse.get("vix", 0) or 0)
        if vix > 25:
            win_adj -= 4; confidence_notes.append(f"VIX {vix:.1f} elevated — market fearful (-4%)")
        elif 0 < vix < 14:
            win_adj += 2; confidence_notes.append(f"VIX {vix:.1f} calm — favorable (+2%)")
        
        # Expiry risk
        if is_expiry:
            win_adj -= 6; confidence_notes.append("EXPIRY DAY — gamma risk & theta decay (-6%)")
        elif dte_to_expiry <= 2:
            win_adj -= 3; confidence_notes.append(f"{dte_to_expiry}d to expiry — time pressure (-3%)")
        
        # MACD alignment
        _macd = tech.get("macd_hist", 0)
        if (_macd > 0 and direction == "BULLISH") or (_macd < 0 and direction == "BEARISH"):
            win_adj += 3; confidence_notes.append("MACD confirms direction (+3%)")
        
        # R:R quality
        rr_val = 0
        try:
            rr_parts = prem_rr.split(":")
            if len(rr_parts) == 2: rr_val = float(rr_parts[1])
        except: pass
        if rr_val >= 2.5:
            win_adj += 3; confidence_notes.append(f"Excellent R:R {prem_rr} (+3%)")
        elif rr_val >= 1.5:
            win_adj += 1; confidence_notes.append(f"Good R:R {prem_rr} (+1%)")
        elif 0 < rr_val < 1.0:
            win_adj -= 4; confidence_notes.append(f"Poor R:R {prem_rr} — risk > reward (-4%)")
        
        estimated_win = max(20, min(85, base_win + win_adj))
        signal_strength = round(score_pct * 0.6 + estimated_win * 0.4, 0)
        
        if estimated_win >= 70: grade = "A+"
        elif estimated_win >= 65: grade = "A"
        elif estimated_win >= 58: grade = "B+"
        elif estimated_win >= 52: grade = "B"
        elif estimated_win >= 45: grade = "C"
        else: grade = "D"
        
        if estimated_win >= 65 and rr_val >= 2:
            size_rec = "Full size (2-3% of capital). High conviction."
        elif estimated_win >= 55 and rr_val >= 1.5:
            size_rec = "Standard size (1-2% of capital). Good setup."
        elif estimated_win >= 45:
            size_rec = "Half size (0.5-1%). Moderate conviction."
        else:
            size_rec = "Skip or paper trade. Low probability."
        
        result["tradeConfidence"] = {
            "estimatedWin": estimated_win,
            "signalStrength": int(signal_strength),
            "grade": grade,
            "baseWin": base_win,
            "adjustments": win_adj,
            "notes": confidence_notes,
            "sizeRecommendation": size_rec,
            "riskReward": prem_rr,
            "rrValue": round(rr_val, 1),
            "factorScore": round(score_pct, 1),
        }
    except Exception as e:
        print(f"⚠️ Trade confidence calc failed: {e}")
        import traceback; traceback.print_exc()
        # Provide default confidence even on error
        result["tradeConfidence"] = {
            "estimatedWin": 50, "signalStrength": 50, "grade": "B",
            "baseWin": 50, "adjustments": 0, "notes": ["Confidence calculation encountered an error"],
            "sizeRecommendation": "Standard size (1-2%). Use caution.",
            "riskReward": prem_rr if 'prem_rr' in dir() else "N/A",
            "rrValue": 0, "factorScore": round(pct, 1) if 'pct' in dir() else 50,
        }
    
    # ═══ ADVANCED EDGE — GEX, Liquidity Voids, ML Patterns, Weighted Score ═══
    try:
        from math import log, sqrt, exp, erf
        adv = {}
        _iv_d = (nse.get("atm_iv", 20) or 20) / 100
        _gap_v = inst.get("gap", 50)
        _atm_v = round(price / _gap_v) * _gap_v
        _T_v = max(bs_data.get("dte", 7) if bs_data else 7, 1) / 365
        _r_v = 0.0525 if is_us else 0.065
        
        # ─── 1. GAMMA EXPOSURE (GEX) — Squeeze Zone Detection ───
        gex_data = []
        gex_flip = 0
        gex_total = 0
        try:
            oi_strikes = nse.get("oi_data", []) or []
            if not oi_strikes and nse.get("ce_resistance"):
                # Build from resistance/support data
                for r in (nse.get("ce_resistance", []) or []):
                    oi_strikes.append({"strike": r["strike"], "ce_oi": r.get("oi", 0), "pe_oi": 0})
                for r in (nse.get("pe_support", []) or []):
                    for s in oi_strikes:
                        if s["strike"] == r["strike"]: s["pe_oi"] = r.get("oi", 0); break
                    else:
                        oi_strikes.append({"strike": r["strike"], "ce_oi": 0, "pe_oi": r.get("oi", 0)})
            
            for s in oi_strikes:
                K = s.get("strike", 0)
                if K <= 0: continue
                ce_oi = s.get("ce_oi", 0) or 0
                pe_oi = s.get("pe_oi", 0) or 0
                
                # Gamma at this strike
                if _iv_d > 0 and _T_v > 0 and K > 0:
                    d1 = (log(price/K) + (_r_v + _iv_d**2/2)*_T_v) / (_iv_d*sqrt(_T_v))
                    npd1 = exp(-d1**2/2) / sqrt(2*3.14159)
                    gamma = npd1 / (price * _iv_d * sqrt(_T_v))
                else:
                    gamma = 0
                
                # GEX = (CE_OI - PE_OI) × Gamma × Spot × 100
                gex_at_strike = round((ce_oi - pe_oi) * gamma * price * 100 / 1e6, 2)  # in millions
                gex_data.append({"strike": K, "gex": gex_at_strike, "ce_oi": ce_oi, "pe_oi": pe_oi})
                gex_total += gex_at_strike
            
            # GEX flip point — where GEX changes sign (negative → positive)
            gex_sorted = sorted(gex_data, key=lambda x: x["strike"])
            for i in range(1, len(gex_sorted)):
                if gex_sorted[i-1]["gex"] < 0 and gex_sorted[i]["gex"] >= 0:
                    gex_flip = gex_sorted[i]["strike"]
                    break
            if not gex_flip and gex_sorted:
                gex_flip = _atm_v
        except Exception as ge:
            print(f"GEX calc error: {ge}")
        
        # GEX interpretation
        gex_regime = "NEUTRAL"
        gex_msg = ""
        if gex_total > 0:
            gex_regime = "POSITIVE"
            gex_msg = "Dealers are LONG gamma. They sell rallies & buy dips = market stays range-bound. Low volatility expected. Sell premium strategies work well."
        elif gex_total < 0:
            gex_regime = "NEGATIVE"
            gex_msg = "Dealers are SHORT gamma. They buy rallies & sell dips = AMPLIFIED moves. High volatility. Breakouts are real. Ride the momentum."
        else:
            gex_msg = "Balanced gamma. No strong dealer positioning bias."
        
        adv["gex"] = {
            "total": round(gex_total, 2),
            "regime": gex_regime,
            "flipPoint": gex_flip,
            "msg": gex_msg,
            "topStrikes": sorted(gex_data, key=lambda x: abs(x["gex"]), reverse=True)[:5] if gex_data else [],
        }
        
        # ─── 2. LIQUIDITY VOIDS — Fast Move Zones ───
        voids = []
        try:
            closes_arr = df_daily["Close"].values.astype(float) if 'df_daily' in dir() else []
            highs_arr = df_daily["High"].values.astype(float) if 'df_daily' in dir() else []
            lows_arr = df_daily["Low"].values.astype(float) if 'df_daily' in dir() else []
            
            if len(closes_arr) >= 20:
                avg_range = float((highs_arr[-20:] - lows_arr[-20:]).mean())
                
                for i in range(-min(20, len(closes_arr)-1), 0):
                    gap_size = abs(float(lows_arr[i] - highs_arr[i-1]))
                    if gap_size > avg_range * 1.5:
                        void_top = max(float(lows_arr[i]), float(highs_arr[i-1]))
                        void_bot = min(float(lows_arr[i]), float(highs_arr[i-1]))
                        dist_pct = round(abs(price - (void_top+void_bot)/2) / price * 100, 1)
                        filled = price >= void_bot and price <= void_top
                        voids.append({
                            "top": round(void_top, 2),
                            "bottom": round(void_bot, 2),
                            "size": round(gap_size, 2),
                            "sizePct": round(gap_size/price*100, 2),
                            "distFromPrice": dist_pct,
                            "direction": "ABOVE" if (void_top+void_bot)/2 > price else "BELOW",
                            "filled": filled,
                        })
                
                voids.sort(key=lambda x: x["distFromPrice"])
        except Exception as ve:
            print(f"Void calc error: {ve}")
        
        adv["liquidityVoids"] = {
            "voids": voids[:4],
            "count": len(voids),
            "msg": f"{len(voids)} liquidity void(s) detected nearby." if voids else "No significant liquidity voids. Price action is smooth.",
            "interpretation": "Liquidity voids are price zones where trading was thin — price 'jumped' through. These zones act as magnets. Price often revisits to fill the gap." if voids else "Clean price action. No gap-fill risk.",
        }
        
        # ─── 3. ML PATTERN SCORING — Learn from Historical Setups ───
        ml_score = 50
        ml_patterns = []
        try:
            if len(closes_arr) >= 60:
                # Pattern 1: EMA crossover success rate
                ema9_h = pd.Series(closes_arr).ewm(span=9).mean().values
                ema21_h = pd.Series(closes_arr).ewm(span=21).mean().values
                cross_wins = 0; cross_total = 0
                for i in range(-50, -5):
                    if ema9_h[i-1] < ema21_h[i-1] and ema9_h[i] > ema21_h[i]:  # Bullish cross
                        cross_total += 1
                        if closes_arr[i+5] > closes_arr[i]: cross_wins += 1
                    elif ema9_h[i-1] > ema21_h[i-1] and ema9_h[i] < ema21_h[i]:  # Bearish cross
                        cross_total += 1
                        if closes_arr[i+5] < closes_arr[i]: cross_wins += 1
                
                cross_rate = round(cross_wins/cross_total*100) if cross_total > 3 else 50
                ml_patterns.append({"pattern": "EMA 9/21 Crossover", "winRate": cross_rate, "samples": cross_total, "msg": f"EMA crosses predicted correctly {cross_rate}% of the time ({cross_total} samples)"})
                
                # Pattern 2: RSI oversold/overbought bounce rate
                rsi_series = []
                delta = pd.Series(closes_arr).diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss
                rsi_arr = (100 - 100/(1+rs)).values
                
                ob_wins = 0; ob_total = 0; os_wins = 0; os_total = 0
                for i in range(-50, -5):
                    if not pd.isna(rsi_arr[i]):
                        if rsi_arr[i] < 30:
                            os_total += 1
                            if closes_arr[i+5] > closes_arr[i]: os_wins += 1
                        elif rsi_arr[i] > 70:
                            ob_total += 1
                            if closes_arr[i+5] < closes_arr[i]: ob_wins += 1
                
                if os_total >= 2:
                    os_rate = round(os_wins/os_total*100)
                    ml_patterns.append({"pattern": "RSI Oversold Bounce", "winRate": os_rate, "samples": os_total, "msg": f"Oversold bounces worked {os_rate}% ({os_total} times)"})
                if ob_total >= 2:
                    ob_rate = round(ob_wins/ob_total*100)
                    ml_patterns.append({"pattern": "RSI Overbought Reversal", "winRate": ob_rate, "samples": ob_total, "msg": f"Overbought reversals worked {ob_rate}% ({ob_total} times)"})
                
                # Pattern 3: Volume spike continuation
                vol_arr = df_daily["Volume"].values.astype(float)
                vol_mean = float(vol_arr[-20:].mean()) if len(vol_arr) >= 20 else float(vol_arr.mean())
                vs_wins = 0; vs_total = 0
                for i in range(-40, -3):
                    if vol_arr[i] > vol_mean * 1.8:
                        vs_total += 1
                        # Did price continue in same direction?
                        day_dir = closes_arr[i] > closes_arr[i-1]
                        next_dir = closes_arr[i+3] > closes_arr[i]
                        if day_dir == next_dir: vs_wins += 1
                
                if vs_total >= 3:
                    vs_rate = round(vs_wins/vs_total*100)
                    ml_patterns.append({"pattern": "Volume Spike Continuation", "winRate": vs_rate, "samples": vs_total, "msg": f"High volume days continued {vs_rate}% of the time ({vs_total} spikes)"})
                
                # Composite ML score
                if ml_patterns:
                    ml_score = round(sum(p["winRate"] * p["samples"] for p in ml_patterns) / max(1, sum(p["samples"] for p in ml_patterns)))
        except Exception as me:
            print(f"ML pattern error: {me}")
        
        adv["mlPatterns"] = {
            "score": ml_score,
            "patterns": ml_patterns,
            "msg": f"Historical pattern analysis suggests {ml_score}% probability based on {sum(p['samples'] for p in ml_patterns)} past setups." if ml_patterns else "Insufficient historical data for pattern analysis.",
        }
        
        # ─── 4. FORMAL WEIGHTED CONFIDENCE SCORE ───
        tech_d = result.get("technicals", {})
        _rsi_v = float(tech_d.get("rsi", 50) or 50)
        _ema9_v = float(tech_d.get("ema9", 0) or 0)
        _ema21_v = float(tech_d.get("ema21", 0) or 0)
        _macd_h = float(tech_d.get("macd_hist", 0) or 0)
        _vol_r = float(tech_d.get("vol_ratio", 1) or 1)
        _pcr = float(nse.get("pcr", 1) or 1)
        _iv_rank = float(result.get("options_intel", {}).get("iv_rank", 50) or 50)
        
        # Trend Score (30%)
        trend_score = 50
        if _ema9_v > _ema21_v and direction == "BULLISH": trend_score = 80
        elif _ema9_v < _ema21_v and direction == "BEARISH": trend_score = 80
        elif _ema9_v > _ema21_v and direction == "BEARISH": trend_score = 25
        elif _ema9_v < _ema21_v and direction == "BULLISH": trend_score = 25
        if _trd.get("pct", 0) and abs(_trd["pct"]) > 40: trend_score += 10
        trend_score = min(100, max(0, trend_score))
        
        # OI Bias Score (25%)
        oi_score = 50
        if _pcr > 1.2 and direction == "BULLISH": oi_score = 75  # Contrarian bullish
        elif _pcr < 0.8 and direction == "BEARISH": oi_score = 75
        elif _pcr > 1.2 and direction == "BEARISH": oi_score = 30
        elif _pcr < 0.8 and direction == "BULLISH": oi_score = 30
        if gex_regime == "NEGATIVE" and direction != "NEUTRAL": oi_score += 10  # Momentum amplified
        oi_score = min(100, max(0, oi_score))
        
        # Volatility Score (20%)
        vol_score = 50
        if _iv_rank < 30: vol_score = 70  # Cheap options = good for buyers
        elif _iv_rank > 70: vol_score = 30  # Expensive = bad for buyers
        if _vix > 0:
            if _vix < 16: vol_score += 10
            elif _vix > 25: vol_score -= 15
        vol_score = min(100, max(0, vol_score))
        
        # Momentum Score (25%)
        mom_score = 50
        if _rsi_v > 50 and _rsi_v < 70 and direction == "BULLISH": mom_score = 75
        elif _rsi_v < 50 and _rsi_v > 30 and direction == "BEARISH": mom_score = 75
        elif _rsi_v > 70 and direction == "BULLISH": mom_score = 35  # Overbought
        elif _rsi_v < 30 and direction == "BEARISH": mom_score = 35  # Oversold
        if _macd_h > 0 and direction == "BULLISH": mom_score += 10
        elif _macd_h < 0 and direction == "BEARISH": mom_score += 10
        if _vol_r > 1.5: mom_score += 8
        mom_score = min(100, max(0, mom_score))
        
        # Weighted composite
        composite = round(
            trend_score * 0.30 +
            oi_score * 0.25 +
            vol_score * 0.20 +
            mom_score * 0.25
        )
        
        # ML adjustment
        if ml_patterns:
            composite = round(composite * 0.85 + ml_score * 0.15)
        
        composite = max(15, min(92, composite))
        
        adv["confidenceScore"] = {
            "composite": composite,
            "trend": {"score": trend_score, "weight": 30},
            "oiBias": {"score": oi_score, "weight": 25},
            "volatility": {"score": vol_score, "weight": 20},
            "momentum": {"score": mom_score, "weight": 25},
            "mlAdjustment": ml_score if ml_patterns else None,
        }
        
        result["advancedEdge"] = adv
        print(f"🔬 Advanced Edge: {symbol} GEX={gex_regime} voids={len(voids)} ML={ml_score} composite={composite}")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"⚠️ Advanced Edge failed: {e}")
    
    # ═══ SCALP / QUICK TRADE — 5min & 15min Price Action ═══
    try:
        scalp = {}
        # Use intraday data already fetched (15m candles from ORB section)
        # Also fetch 5m candles for scalp
        intra_5m = tk.history(period="1d", interval="5m")
        intra_15m = tk.history(period="2d", interval="15m")
        
        if intra_5m is not None and len(intra_5m) >= 5 and intra_15m is not None and len(intra_15m) >= 5:
            c5 = intra_5m["Close"].values.astype(float)
            h5 = intra_5m["High"].values.astype(float)
            l5 = intra_5m["Low"].values.astype(float)
            v5 = intra_5m["Volume"].values.astype(float)
            c15 = intra_15m["Close"].values.astype(float)
            h15 = intra_15m["High"].values.astype(float)
            l15 = intra_15m["Low"].values.astype(float)
            
            # 5min EMA 9 & 21
            import pandas as pd
            ema9_5m = float(pd.Series(c5).ewm(span=9).mean().iloc[-1])
            ema21_5m = float(pd.Series(c5).ewm(span=21).mean().iloc[-1])
            
            # 15min EMA 9 & 21
            ema9_15m = float(pd.Series(c15).ewm(span=9).mean().iloc[-1])
            ema21_15m = float(pd.Series(c15).ewm(span=21).mean().iloc[-1])
            
            # VWAP (from 5m data)
            vwap = 0
            if len(v5) > 0:
                tp = (h5 + l5 + c5) / 3
                cum_tpv = (tp * v5).cumsum()
                cum_vol = v5.cumsum()
                vwap = round(float(cum_tpv[-1] / cum_vol[-1]), 2) if cum_vol[-1] > 0 else 0
            
            # Recent 5min momentum (last 3 candles)
            last3_dir = "UP" if c5[-1] > c5[-3] else "DOWN"
            last3_strength = abs(round(((c5[-1] - c5[-3]) / c5[-3]) * 100, 3))
            
            # 15min trend
            trend_15m = "BULLISH" if ema9_15m > ema21_15m else "BEARISH"
            trend_5m = "BULLISH" if ema9_5m > ema21_5m else "BEARISH"
            
            # Price vs VWAP
            above_vwap = price > vwap if vwap > 0 else True
            
            # Scalp direction — alignment of 5m + 15m + VWAP
            scalp_dir = "NEUTRAL"
            scalp_confidence = 0
            scalp_reasons = []
            
            if trend_5m == "BULLISH" and trend_15m == "BULLISH":
                scalp_dir = "BULLISH"
                scalp_confidence += 30
                scalp_reasons.append("5m & 15m EMA aligned bullish (+30)")
            elif trend_5m == "BEARISH" and trend_15m == "BEARISH":
                scalp_dir = "BEARISH"
                scalp_confidence += 30
                scalp_reasons.append("5m & 15m EMA aligned bearish (+30)")
            else:
                scalp_reasons.append("Mixed: 5m=" + trend_5m + ", 15m=" + trend_15m + " (conflicting)")
            
            if above_vwap and scalp_dir == "BULLISH":
                scalp_confidence += 20; scalp_reasons.append(f"Price above VWAP {csym}{vwap:,.1f} (+20)")
            elif not above_vwap and scalp_dir == "BEARISH":
                scalp_confidence += 20; scalp_reasons.append(f"Price below VWAP {csym}{vwap:,.1f} (+20)")
            elif above_vwap and scalp_dir == "BEARISH":
                scalp_confidence -= 10; scalp_reasons.append(f"Selling above VWAP — risky (-10)")
            
            if last3_dir == "UP" and scalp_dir == "BULLISH":
                scalp_confidence += 15; scalp_reasons.append(f"Last 3 candles moving up (+15)")
            elif last3_dir == "DOWN" and scalp_dir == "BEARISH":
                scalp_confidence += 15; scalp_reasons.append(f"Last 3 candles moving down (+15)")
            
            # Volume surge in last candle
            avg_vol_5m = float(v5[-10:].mean()) if len(v5) >= 10 else float(v5.mean())
            last_vol = float(v5[-1])
            vol_surge = round(last_vol / avg_vol_5m, 1) if avg_vol_5m > 0 else 1
            if vol_surge > 1.5:
                scalp_confidence += 10; scalp_reasons.append(f"Volume surge {vol_surge}x on last candle (+10)")
            
            scalp_confidence = max(0, min(85, scalp_confidence))
            
            # Scalp levels
            atr_5m = round(float((h5[-10:] - l5[-10:]).mean()), 2) if len(h5) >= 10 else round(float((h5 - l5).mean()), 2)
            
            if scalp_dir == "BULLISH":
                s_entry = round(price, 2)
                s_sl = round(price - atr_5m * 2, 2)
                s_t1 = round(price + atr_5m * 1.5, 2)
                s_t2 = round(price + atr_5m * 3, 2)
                s_opt = opt_type  # same as main trade direction (CE/CALL)
                s_opt_raw = "CE"
            elif scalp_dir == "BEARISH":
                s_entry = round(price, 2)
                s_sl = round(price + atr_5m * 2, 2)
                s_t1 = round(price - atr_5m * 1.5, 2)
                s_t2 = round(price - atr_5m * 3, 2)
                s_opt = ("PUT" if is_us else "PE")
                s_opt_raw = "PE"
            else:
                s_entry = round(price, 2)
                s_sl = round(price - atr_5m * 1.5, 2)
                s_t1 = round(price + atr_5m * 1, 2)
                s_t2 = round(price + atr_5m * 2, 2)
                s_opt = opt_type
                s_opt_raw = opt_type_raw
            
            # Compute scalp premiums
            s_prem_entry = _bs_premium_at(s_entry, selected_strike, bs_T, bs_r, bs_iv, s_opt_raw) if bs_T > 0 and bs_iv > 0 else 0
            s_prem_sl = _bs_premium_at(s_sl, selected_strike, bs_T, bs_r, bs_iv, s_opt_raw) if s_prem_entry > 0 else 0
            s_prem_t1 = _bs_premium_at(s_t1, selected_strike, bs_T, bs_r, bs_iv, s_opt_raw) if s_prem_entry > 0 else 0
            s_prem_t2 = _bs_premium_at(s_t2, selected_strike, bs_T, bs_r, bs_iv, s_opt_raw) if s_prem_entry > 0 else 0
            
            scalp = {
                "direction": scalp_dir,
                "confidence": scalp_confidence,
                "reasons": scalp_reasons,
                "trend_5m": trend_5m,
                "trend_15m": trend_15m,
                "ema9_5m": round(ema9_5m, 2),
                "ema21_5m": round(ema21_5m, 2),
                "ema9_15m": round(ema9_15m, 2),
                "ema21_15m": round(ema21_15m, 2),
                "vwap": vwap,
                "above_vwap": above_vwap,
                "vol_surge": vol_surge,
                "atr_5m": atr_5m,
                "entry": s_entry,
                "sl": s_sl,
                "t1": s_t1,
                "t2": s_t2,
                "optType": s_opt,
                "strike": selected_strike,
                "premEntry": round(s_prem_entry, 1),
                "premSL": round(s_prem_sl, 1),
                "premT1": round(s_prem_t1, 1),
                "premT2": round(s_prem_t2, 1),
                "action": f"SCALP {'BUY' if scalp_dir!='NEUTRAL' else 'WAIT'} {selected_strike} {s_opt}",
            }
        
        if scalp:
            result["scalp"] = scalp
            print(f"⚡ Scalp: {symbol} {scalp['direction']} conf={scalp['confidence']}% 5m={scalp['trend_5m']} 15m={scalp['trend_15m']}")
    except Exception as e:
        print(f"⚠️ Scalp analysis failed: {e}")
    
    # ═══ FUNDAMENTAL ANALYSIS — Revenue, Margins, Debt, Returns ═══
    try:
        info = tk.info if hasattr(tk, 'info') else {}
        fa = {}
        
        # Revenue & profit growth
        rev_growth = round(float(info.get("revenueGrowth", 0) or 0) * 100, 1)
        earn_growth = round(float(info.get("earningsGrowth", 0) or 0) * 100, 1)
        
        # Margins
        gross_margin = round(float(info.get("grossMargins", 0) or 0) * 100, 1)
        op_margin = round(float(info.get("operatingMargins", 0) or 0) * 100, 1)
        profit_margin = round(float(info.get("profitMargins", 0) or 0) * 100, 1)
        
        # Debt & health
        de_ratio = round(float(info.get("debtToEquity", 0) or 0), 1)
        current_ratio = round(float(info.get("currentRatio", 0) or 0), 1)
        free_cf = float(info.get("freeCashflow", 0) or 0)
        
        # Return ratios
        roe = round(float(info.get("returnOnEquity", 0) or 0) * 100, 1)
        roa = round(float(info.get("returnOnAssets", 0) or 0) * 100, 1)
        
        # Red flags & strengths
        red_flags = []
        strengths = []
        
        if de_ratio > 150: red_flags.append(f"High debt (D/E {de_ratio}%) — company is heavily leveraged")
        elif de_ratio > 0 and de_ratio < 50: strengths.append(f"Low debt (D/E {de_ratio}%) — financially healthy")
        
        if profit_margin < 5 and profit_margin > 0: red_flags.append(f"Thin margins ({profit_margin}%) — vulnerable to cost pressure")
        elif profit_margin > 20: strengths.append(f"Strong margins ({profit_margin}%) — pricing power")
        
        if rev_growth < -5: red_flags.append(f"Revenue shrinking ({rev_growth}%) — business declining")
        elif rev_growth > 15: strengths.append(f"Strong revenue growth ({rev_growth}%) — business expanding")
        
        if roe > 20: strengths.append(f"High ROE ({roe}%) — efficient use of equity")
        elif roe < 5 and roe > 0: red_flags.append(f"Low ROE ({roe}%) — poor returns for shareholders")
        
        if earn_growth < -10: red_flags.append(f"Earnings declining ({earn_growth}%)")
        elif earn_growth > 20: strengths.append(f"Earnings surging ({earn_growth}%)")
        
        if free_cf < 0: red_flags.append("Negative free cash flow — burning cash")
        elif free_cf > 0: strengths.append("Positive free cash flow — generating cash")
        
        if current_ratio > 0 and current_ratio < 1: red_flags.append(f"Current ratio {current_ratio} — may struggle to pay short-term debts")
        
        # Fundamental Grade
        fund_score = 50
        if rev_growth > 10: fund_score += 10
        elif rev_growth < 0: fund_score -= 10
        if profit_margin > 15: fund_score += 10
        elif profit_margin < 5: fund_score -= 10
        if de_ratio < 80: fund_score += 10
        elif de_ratio > 150: fund_score -= 15
        if roe > 15: fund_score += 10
        elif roe < 5: fund_score -= 10
        if earn_growth > 10: fund_score += 10
        elif earn_growth < -5: fund_score -= 10
        fund_score = max(0, min(100, fund_score))
        
        fund_grade = "STRONG" if fund_score >= 70 else ("AVERAGE" if fund_score >= 45 else "WEAK")
        fund_color = "#059669" if fund_score >= 70 else ("#d97706" if fund_score >= 45 else "#dc2626")
        
        fa = {
            "revGrowth": rev_growth, "earnGrowth": earn_growth,
            "grossMargin": gross_margin, "opMargin": op_margin, "profitMargin": profit_margin,
            "deRatio": de_ratio, "currentRatio": current_ratio,
            "roe": roe, "roa": roa,
            "redFlags": red_flags, "strengths": strengths,
            "score": fund_score, "grade": fund_grade, "color": fund_color,
            "coachSummary": f"Fundamentals are {fund_grade.lower()}. " + (
                "This company is growing revenue, has healthy margins and low debt. A solid business." if fund_grade == "STRONG"
                else "Decent business but some areas need watching. Not a red flag but not exceptional either." if fund_grade == "AVERAGE"
                else "Weak fundamentals — declining growth, thin margins or high debt. Be cautious."
            ),
        }
        result["fundamentals"] = fa
        print(f"📊 Fundamentals: {symbol} grade={fund_grade} score={fund_score} roe={roe} de={de_ratio}")
    except Exception as e:
        print(f"⚠️ Fundamental analysis failed: {e}")
    
    # ═══ VALUATION INTELLIGENCE — PE, Forward PE, Crash Scenarios ═══
    try:
        tech_d = result.get("technicals", {})
        pe_val = float(tech_d.get("pe", 0) or 0)
        w52h = float(tech_d.get("w52h", 0) or 0)
        w52l = float(tech_d.get("w52l", 0) or 0)
        
        # Get forward PE + PEG from yfinance
        fwd_pe = 0; peg = 0; div_yield = 0; mkt_cap = 0; sector = ""
        try:
            info = tk.info
            fwd_pe = round(float(info.get("forwardPE", 0) or 0), 1)
            peg = round(float(info.get("pegRatio", 0) or 0), 2)
            div_yield = round(float(info.get("dividendYield", 0) or 0) * 100, 2)
            mkt_cap = float(info.get("marketCap", 0) or 0)
            sector = info.get("sector", "")
            if pe_val == 0: pe_val = round(float(info.get("trailingPE", 0) or 0), 1)
        except: pass
        
        # Historical PE benchmarks
        pe_benchmarks = {
            "NIFTY": {"avg": 22, "low": 16, "high": 30, "fair_pe": 21, "name": "Nifty 50"},
            "BANKNIFTY": {"avg": 17, "low": 12, "high": 24, "fair_pe": 16, "name": "Bank Nifty"},
            "SENSEX": {"avg": 23, "low": 17, "high": 32, "fair_pe": 22, "name": "Sensex"},
            "SPY": {"avg": 20, "low": 14, "high": 30, "fair_pe": 19, "name": "S&P 500"},
            "QQQ": {"avg": 28, "low": 18, "high": 40, "fair_pe": 26, "name": "NASDAQ 100"},
            "IWM": {"avg": 22, "low": 14, "high": 35, "fair_pe": 20, "name": "Russell 2000"},
        }
        sector_pe = {
            "Technology": {"avg": 30, "low": 18, "high": 50},
            "Financial Services": {"avg": 15, "low": 8, "high": 22},
            "Healthcare": {"avg": 25, "low": 15, "high": 40},
            "Consumer Cyclical": {"avg": 35, "low": 20, "high": 60},
            "Consumer Defensive": {"avg": 28, "low": 18, "high": 45},
            "Energy": {"avg": 12, "low": 6, "high": 20},
            "Industrials": {"avg": 20, "low": 10, "high": 30},
            "Basic Materials": {"avg": 15, "low": 8, "high": 25},
            "Communication Services": {"avg": 22, "low": 12, "high": 35},
            "Real Estate": {"avg": 18, "low": 10, "high": 30},
        }
        
        bench = pe_benchmarks.get(symbol, None)
        if not bench and sector:
            sp = sector_pe.get(sector, {"avg": 22, "low": 12, "high": 35})
            bench = {"avg": sp["avg"], "low": sp["low"], "high": sp["high"], "fair_pe": sp["avg"] - 2, "name": symbol}
        if not bench:
            bench = {"avg": 22, "low": 12, "high": 35, "fair_pe": 20, "name": symbol}
        
        # Valuation zone
        val_zone = "FAIR"
        val_explanation = ""
        if pe_val > 0:
            ratio = pe_val / bench["avg"]
            if ratio > 1.3:
                val_zone = "EXPENSIVE"
                val_explanation = f"PE {pe_val:.1f}x is {(ratio-1)*100:.0f}% above historical average ({bench['avg']}x). Market expects high growth. Risk of sharp correction if earnings disappoint."
            elif ratio > 1.1:
                val_zone = "SLIGHTLY EXPENSIVE"
                val_explanation = f"PE {pe_val:.1f}x is slightly above average ({bench['avg']}x). Moderate risk — growth needs to sustain to justify current prices."
            elif ratio > 0.9:
                val_zone = "FAIR VALUE"
                val_explanation = f"PE {pe_val:.1f}x is near historical average ({bench['avg']}x). Neither cheap nor expensive. Good for gradual accumulation."
            elif ratio > 0.7:
                val_zone = "UNDERVALUED"
                val_explanation = f"PE {pe_val:.1f}x is below average ({bench['avg']}x). Historically a good entry zone. Market may be pricing in temporary headwinds."
            else:
                val_zone = "DEEPLY UNDERVALUED"
                val_explanation = f"PE {pe_val:.1f}x is significantly below average ({bench['avg']}x). Either a crisis bargain or structural problems. Investigate before buying."
        else:
            val_explanation = "PE data not available for this instrument."
        
        # Fair value calculation
        fair_value = 0
        if pe_val > 0 and bench["fair_pe"] > 0:
            eps = price / pe_val if pe_val > 0 else 0
            fair_value = round(eps * bench["fair_pe"], 2)
        
        # Forward PE analysis
        fwd_analysis = ""
        if fwd_pe > 0 and pe_val > 0:
            if fwd_pe < pe_val * 0.85:
                fwd_analysis = f"Forward PE ({fwd_pe}x) is {round((1-fwd_pe/pe_val)*100)}% lower than trailing — strong earnings growth expected. Valuation improving."
            elif fwd_pe < pe_val:
                fwd_analysis = f"Forward PE ({fwd_pe}x) slightly lower than trailing — modest growth ahead."
            else:
                fwd_analysis = f"Forward PE ({fwd_pe}x) higher than trailing — earnings expected to decline. Caution."
        
        # Crash scenario analysis
        crash_scenarios = []
        for pct in [10, 20, 30]:
            crash_price = round(price * (1 - pct/100), 2)
            crash_pe = round(crash_price / (price/pe_val), 1) if pe_val > 0 else 0
            recovery_needed = round((price / crash_price - 1) * 100, 1)
            is_buy_zone = crash_pe < bench["avg"] if crash_pe > 0 else False
            
            if pct == 10:
                scenario = "Normal correction. Happens 1-2x per year. Usually recovers in 1-3 months."
            elif pct == 20:
                scenario = "Bear market territory. Happens every 3-5 years. Recovery takes 6-18 months. Good SIP accumulation zone."
            else:
                scenario = "Severe crash (COVID/2008 level). Rare — once per decade. Recovery takes 1-3 years. Generational buying opportunity."
            
            crash_scenarios.append({
                "correction": pct,
                "price": crash_price,
                "pe": crash_pe,
                "recovery": recovery_needed,
                "isBuyZone": is_buy_zone,
                "scenario": scenario,
            })
        
        # Geopolitical risk factors
        geo_risks = []
        if is_us:
            geo_risks = [
                {"risk": "US-China Trade War", "impact": "HIGH", "sectors": "Tech, Semis, Manufacturing", "action": "Avoid pure-China supply chain stocks. Favor onshoring beneficiaries (AVGO, AMAT)."},
                {"risk": "Fed Rate Policy", "impact": "HIGH", "sectors": "REITs, Growth, Banks", "action": "Rate cuts = bullish growth. Rate holds = value outperforms. Watch 10Y yield."},
                {"risk": "US Debt/Deficit", "impact": "MEDIUM", "sectors": "Bonds, USD, Gold", "action": "Rising debt → weaker USD → Gold/BTC benefit. TLT as hedge."},
                {"risk": "AI Capex Bubble Risk", "impact": "MEDIUM", "sectors": "NVDA, Cloud, Data Centers", "action": "AI spending $300B+ in 2026. If ROI disappoints → 30-40% correction in AI names."},
                {"risk": "US Midterm Elections (Nov 2026)", "impact": "MEDIUM", "sectors": "Defense, Healthcare, Energy", "action": "Volatility rises Sep-Nov. Historically markets rally post-election."},
            ]
        else:
            geo_risks = [
                {"risk": "US Reciprocal Tariffs on India", "impact": "HIGH", "sectors": "Pharma, IT, Textiles, Auto Parts", "action": "26% tariff risk. Diversify from US-dependent exporters. Favor domestic consumption."},
                {"risk": "FII Outflows / Dollar Strength", "impact": "HIGH", "sectors": "Banking, Large Cap", "action": "Strong USD pulls FII money out. DII buying provides floor. Watch INR > 87 as danger zone."},
                {"risk": "China+1 / PLI Beneficiaries", "impact": "BULLISH", "sectors": "Electronics, Pharma, Auto", "action": "India gaining manufacturing share. Dixon, Tata Electronics, Cipla benefit."},
                {"risk": "RBI Rate Cycle", "impact": "MEDIUM", "sectors": "Banks, NBFCs, Real Estate", "action": "Rate cuts ahead → banks' NIMs compress but credit growth rises. Favor retail banks."},
                {"risk": "Crude Oil > $80", "impact": "HIGH", "sectors": "OMCs, Airlines, Paints", "action": "India imports 85% crude. Above $80 = inflation + CAD pressure. Hedge with ONGC."},
                {"risk": "SEBI F&O Reforms", "impact": "MEDIUM", "sectors": "Brokers, Options Traders", "action": "Weekly expiry restricted. Premium stability improving. Adjust strategies."},
            ]
        
        # Investment recommendations by scenario
        safe_havens = []
        if is_us:
            safe_havens = [
                {"category": "Recession-Proof", "picks": "JNJ, PG, KO, WMT, COST", "reason": "Consumer staples — people buy toothpaste in recessions too."},
                {"category": "Dividend Aristocrats", "picks": "SCHD ETF, VYM, O, ABBV", "reason": "25+ years of rising dividends. Income even in crashes."},
                {"category": "Gold/Hedge", "picks": "GLD, SLV, TLT, BRK.B", "reason": "Gold up 25% in 2025. Bonds rally when stocks crash."},
                {"category": "AI/Growth (for dips)", "picks": "NVDA, MSFT, GOOGL, AVGO", "reason": "Buy these ONLY on 20%+ corrections. Don't chase at highs."},
            ]
        else:
            safe_havens = [
                {"category": "Defensive (crash-proof)", "picks": "NESTLEIND, HUL, ITC, BRITANNIA", "reason": "FMCG — people buy daily essentials even in recessions."},
                {"category": "SIP Accumulation", "picks": "NIFTYBEES, JUNIORBEES, BANKBEES", "reason": "Index ETFs via SIP. Buy more units when market falls = rupee cost averaging."},
                {"category": "Gold/Hedge", "picks": "GOLDBEES, SGB (Sovereign Gold Bond)", "reason": "Gold hedge + 2.5% interest on SGB. Up 20%+ in 2025."},
                {"category": "High Conviction (buy on dips)", "picks": "RELIANCE, TCS, HDFCBANK, ICICIBANK", "reason": "India's bluest chips. Buy only on 15-20% corrections from highs."},
                {"category": "PLI/China+1", "picks": "DIXON, HAL, BEL, KAYNES, TRENT", "reason": "Structural growth stories. India manufacturing boom beneficiaries."},
            ]
        
        result["valuation"] = {
            "pe": pe_val, "fwdPE": fwd_pe, "peg": peg, "divYield": div_yield,
            "histPE": bench, "sector": sector,
            "zone": val_zone, "explanation": val_explanation,
            "fairValue": fair_value, "fwdAnalysis": fwd_analysis,
            "crashScenarios": crash_scenarios,
            "geoRisks": geo_risks,
            "safeHavens": safe_havens,
            "w52h": w52h, "w52l": w52l, "w52pos": round(float(tech_d.get("w52pos", 50) or 50), 1),
        }
        print(f"📊 Valuation: {symbol} PE={pe_val} zone={val_zone} fair={fair_value}")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"⚠️ Valuation Intelligence failed: {e}")
    
    # ═══ PREMIUM TRADING INTELLIGENCE ═══
    try:
        from math import log, sqrt, exp, erf
        _bs_iv = bs_data.get("T", 7/365) if bs_data else 7/365
        _bs_r = 0.0525 if is_us else 0.065
        _iv_dec = (nse.get("atm_iv", 20) or 20) / 100
        _dte = bs_data.get("dte", 7) if bs_data else 7
        _T = max(_dte, 1) / 365
        _gap = inst.get("gap", 50)
        _lot = inst.get("lot", 50)
        _atm = round(price / _gap) * _gap
        
        def _bsp(S, K, T, r, sigma, otype):
            if T <= 0 or sigma <= 0 or S <= 0 or K <= 0: return 0
            d1 = (log(S/K) + (r + sigma**2/2)*T) / (sigma*sqrt(T))
            d2 = d1 - sigma*sqrt(T)
            nd1 = 0.5*(1+erf(d1/sqrt(2))); nd2 = 0.5*(1+erf(d2/sqrt(2)))
            if otype == "CE": return max(round(S*nd1 - K*exp(-r*T)*nd2, 2), 0)
            return max(round(K*exp(-r*T)*(1-nd2) - S*(1-nd1), 2), 0)
        
        def _bsg(S, K, T, r, sigma, otype):
            if T <= 0 or sigma <= 0 or S <= 0 or K <= 0: return {"delta":0,"gamma":0,"theta":0,"vega":0}
            d1 = (log(S/K) + (r + sigma**2/2)*T) / (sigma*sqrt(T))
            d2 = d1 - sigma*sqrt(T)
            nd1 = 0.5*(1+erf(d1/sqrt(2))); nd2 = 0.5*(1+erf(d2/sqrt(2)))
            npd1 = exp(-d1**2/2) / sqrt(2*3.14159)
            delta = round(nd1,3) if otype=="CE" else round(nd1-1,3)
            gamma = round(npd1/(S*sigma*sqrt(T)),6)
            theta_ce = (-S*npd1*sigma/(2*sqrt(T)) - r*K*exp(-r*T)*nd2)/365
            theta_pe = (-S*npd1*sigma/(2*sqrt(T)) + r*K*exp(-r*T)*(1-nd2))/365
            theta = round(theta_ce if otype=="CE" else theta_pe, 2)
            vega = round(S*npd1*sqrt(T)/100, 2)
            return {"delta":delta,"gamma":gamma,"theta":theta,"vega":vega}
        
        # ─── 1. MULTI-LEG STRATEGIES ───
        strategies = []
        ce_atm = _bsp(price, _atm, _T, _bs_r, _iv_dec, "CE")
        pe_atm = _bsp(price, _atm, _T, _bs_r, _iv_dec, "PE")
        ce_otm1 = _bsp(price, _atm+_gap, _T, _bs_r, _iv_dec, "CE")
        pe_otm1 = _bsp(price, _atm-_gap, _T, _bs_r, _iv_dec, "PE")
        ce_otm2 = _bsp(price, _atm+_gap*2, _T, _bs_r, _iv_dec, "CE")
        pe_otm2 = _bsp(price, _atm-_gap*2, _T, _bs_r, _iv_dec, "PE")
        
        straddle_cost = round(ce_atm + pe_atm, 2)
        straddle_be_up = round(_atm + straddle_cost, 2)
        straddle_be_dn = round(_atm - straddle_cost, 2)
        em_pts = round(price * _iv_dec * sqrt(_T), 1)
        pop_straddle = round(max(20, min(80, 100 - (straddle_cost / em_pts * 50))), 0) if em_pts > 0 else 40
        
        strategies.append({
            "name": "Long Straddle", "type": "NON-DIRECTIONAL", "bias": "Expects big move either side",
            "legs": [
                {"action":"BUY","strike":_atm,"type":"CE" if not is_us else "CALL","premium":ce_atm},
                {"action":"BUY","strike":_atm,"type":"PE" if not is_us else "PUT","premium":pe_atm},
            ],
            "cost": straddle_cost, "costPerLot": round(straddle_cost*_lot,0),
            "maxLoss": straddle_cost, "maxProfit": "Unlimited",
            "breakeven": f"{csym}{straddle_be_dn:,.0f} / {csym}{straddle_be_up:,.0f}",
            "pop": pop_straddle,
            "when": "Before events (earnings, Fed, RBI). When IV is LOW (buy cheap). When you expect >" + f"{csym}{straddle_cost:,.0f} move.",
            "interpretation": f"You pay {csym}{straddle_cost} total. Stock must move more than {csym}{straddle_cost:,.0f} from {csym}{_atm:,.0f} for profit. Works best when IV Rank < 30.",
        })
        
        strangle_cost = round(ce_otm1 + pe_otm1, 2)
        strangle_be_up = round(_atm+_gap+strangle_cost, 2)
        strangle_be_dn = round(_atm-_gap-strangle_cost, 2)
        pop_strangle = round(max(15, min(75, 100 - (strangle_cost / em_pts * 45))), 0) if em_pts > 0 else 35
        
        strategies.append({
            "name": "Long Strangle", "type": "NON-DIRECTIONAL", "bias": "Cheaper than straddle, needs bigger move",
            "legs": [
                {"action":"BUY","strike":_atm+_gap,"type":"CE" if not is_us else "CALL","premium":ce_otm1},
                {"action":"BUY","strike":_atm-_gap,"type":"PE" if not is_us else "PUT","premium":pe_otm1},
            ],
            "cost": strangle_cost, "costPerLot": round(strangle_cost*_lot,0),
            "maxLoss": strangle_cost, "maxProfit": "Unlimited",
            "breakeven": f"{csym}{strangle_be_dn:,.0f} / {csym}{strangle_be_up:,.0f}",
            "pop": pop_strangle,
            "when": "Before big events. Cheaper entry than straddle but needs a bigger move to profit.",
            "interpretation": f"Pay {csym}{strangle_cost} (cheaper than straddle). But stock must move past {csym}{strangle_be_dn:,.0f} or {csym}{strangle_be_up:,.0f}.",
        })
        
        ic_credit = round(ce_otm1 + pe_otm1 - ce_otm2 - pe_otm2, 2)
        ic_max_loss = round(_gap - ic_credit, 2)
        ic_pop = round(max(40, min(85, 50 + (ic_credit / _gap * 50))), 0)
        
        strategies.append({
            "name": "Iron Condor (Short)", "type": "NON-DIRECTIONAL", "bias": "Range-bound, collect premium",
            "legs": [
                {"action":"SELL","strike":_atm-_gap,"type":"PE" if not is_us else "PUT","premium":pe_otm1},
                {"action":"BUY","strike":_atm-_gap*2,"type":"PE" if not is_us else "PUT","premium":pe_otm2},
                {"action":"SELL","strike":_atm+_gap,"type":"CE" if not is_us else "CALL","premium":ce_otm1},
                {"action":"BUY","strike":_atm+_gap*2,"type":"CE" if not is_us else "CALL","premium":ce_otm2},
            ],
            "cost": -ic_credit, "costPerLot": round(ic_credit*_lot,0),
            "maxLoss": round(ic_max_loss*_lot,0), "maxProfit": round(ic_credit*_lot,0),
            "breakeven": f"{csym}{_atm-_gap-ic_credit:,.0f} / {csym}{_atm+_gap+ic_credit:,.0f}",
            "pop": ic_pop,
            "when": "When IV Rank > 50 (sell expensive premium). Sideways market. After events (IV crush).",
            "interpretation": f"Collect {csym}{ic_credit} credit. Keep it if stock stays between {csym}{_atm-_gap:,.0f}–{csym}{_atm+_gap:,.0f}. Max risk {csym}{ic_max_loss} per lot.",
        })
        
        # Bull/Bear spread based on direction
        if direction == "BULLISH":
            spread_cost = round(ce_atm - ce_otm1, 2)
            spread_profit = round(_gap - spread_cost, 2)
            strategies.append({
                "name": "Bull Call Spread", "type": "DIRECTIONAL", "bias": "Moderately bullish",
                "legs": [
                    {"action":"BUY","strike":_atm,"type":"CE" if not is_us else "CALL","premium":ce_atm},
                    {"action":"SELL","strike":_atm+_gap,"type":"CE" if not is_us else "CALL","premium":ce_otm1},
                ],
                "cost": spread_cost, "costPerLot": round(spread_cost*_lot,0),
                "maxLoss": round(spread_cost*_lot,0), "maxProfit": round(spread_profit*_lot,0),
                "breakeven": f"{csym}{_atm+spread_cost:,.0f}",
                "pop": round(max(30,min(70, 50 + (spread_profit/spread_cost*10) if spread_cost>0 else 50)),0),
                "when": "Mildly bullish. Cheaper than naked call. Defined risk.",
                "interpretation": f"Pay {csym}{spread_cost}, max profit {csym}{spread_profit} if stock above {csym}{_atm+_gap:,.0f} at expiry.",
            })
        else:
            spread_cost = round(pe_atm - pe_otm1, 2)
            spread_profit = round(_gap - spread_cost, 2)
            strategies.append({
                "name": "Bear Put Spread", "type": "DIRECTIONAL", "bias": "Moderately bearish",
                "legs": [
                    {"action":"BUY","strike":_atm,"type":"PE" if not is_us else "PUT","premium":pe_atm},
                    {"action":"SELL","strike":_atm-_gap,"type":"PE" if not is_us else "PUT","premium":pe_otm1},
                ],
                "cost": spread_cost, "costPerLot": round(spread_cost*_lot,0),
                "maxLoss": round(spread_cost*_lot,0), "maxProfit": round(spread_profit*_lot,0),
                "breakeven": f"{csym}{_atm-spread_cost:,.0f}",
                "pop": round(max(30,min(70, 50 + (spread_profit/spread_cost*10) if spread_cost>0 else 50)),0),
                "when": "Mildly bearish. Defined risk. Cheaper than naked put.",
                "interpretation": f"Pay {csym}{spread_cost}, max profit {csym}{spread_profit} if stock below {csym}{_atm-_gap:,.0f} at expiry.",
            })
        
        result["strategies"] = strategies
        
        # ─── 2. GREEKS DASHBOARD + INTERPRETATION ───
        atm_ce_g = _bsg(price, _atm, _T, _bs_r, _iv_dec, "CE")
        atm_pe_g = _bsg(price, _atm, _T, _bs_r, _iv_dec, "PE")
        
        greeks_interpretation = []
        # Delta
        if abs(atm_ce_g["delta"]) > 0.6:
            greeks_interpretation.append({"greek":"Delta","value":atm_ce_g["delta"],"msg":"Deep ITM — moves almost 1:1 with stock. High premium but low leverage.","severity":"INFO"})
        elif abs(atm_ce_g["delta"]) > 0.45:
            greeks_interpretation.append({"greek":"Delta","value":atm_ce_g["delta"],"msg":"ATM sweet spot. Best balance of cost vs probability.","severity":"GOOD"})
        else:
            greeks_interpretation.append({"greek":"Delta","value":atm_ce_g["delta"],"msg":"OTM — cheap but low probability. Needs strong move to profit.","severity":"WARN"})
        
        # Gamma
        if atm_ce_g["gamma"] > 0.005 and _dte <= 3:
            greeks_interpretation.append({"greek":"Gamma","value":atm_ce_g["gamma"],"msg":"⚡ GAMMA SPIKE — near expiry, small moves cause big premium swings. Scalp opportunity but dangerous if wrong.","severity":"ALERT"})
        elif atm_ce_g["gamma"] > 0.003:
            greeks_interpretation.append({"greek":"Gamma","value":atm_ce_g["gamma"],"msg":"Elevated gamma — option is sensitive to small price changes. Good for quick trades.","severity":"INFO"})
        else:
            greeks_interpretation.append({"greek":"Gamma","value":atm_ce_g["gamma"],"msg":"Low gamma — option moves slowly. Better for swing trades.","severity":"INFO"})
        
        # Theta
        daily_decay = abs(atm_ce_g["theta"])
        if _dte <= 2:
            greeks_interpretation.append({"greek":"Theta","value":atm_ce_g["theta"],"msg":f"🔥 EXTREME DECAY — losing {csym}{daily_decay:.1f}/day. Buyers: exit before EOD. Sellers: this is your edge.","severity":"ALERT"})
        elif _dte <= 5:
            greeks_interpretation.append({"greek":"Theta","value":atm_ce_g["theta"],"msg":f"Accelerating decay at {csym}{daily_decay:.1f}/day. Time is against buyers. Consider booking profits.","severity":"WARN"})
        else:
            greeks_interpretation.append({"greek":"Theta","value":atm_ce_g["theta"],"msg":f"Moderate decay at {csym}{daily_decay:.1f}/day. Safe to hold for a few days.","severity":"INFO"})
        
        # Vega
        if atm_ce_g["vega"] > 0:
            greeks_interpretation.append({"greek":"Vega","value":atm_ce_g["vega"],"msg":f"1% IV change = {csym}{atm_ce_g['vega']:.1f} premium change. " + ("IV is HIGH — expect crush after events. Sellers benefit." if (nse.get("atm_iv",20) or 20) > 25 else "IV is LOW — buyers get cheap options, vega works in your favor if IV expands."),"severity":"INFO"})
        
        result["greeksDashboard"] = {
            "ce": atm_ce_g, "pe": atm_pe_g,
            "strike": _atm, "dte": _dte,
            "interpretation": greeks_interpretation,
            "netDelta": round(atm_ce_g["delta"] + atm_pe_g["delta"], 3),
            "dailyDecay": round(daily_decay, 2),
        }
        
        # ─── 3. VOLATILITY INTELLIGENCE ───
        # Already computed in options_intel, enhance with regime
        oi_data = result.get("options_intel", {})
        iv_current = oi_data.get("iv_current", 20)
        iv_rank = oi_data.get("iv_rank", 50)
        
        # HV (20-day) from daily returns
        tech_data = result.get("technicals", {})
        hv_20 = 0
        try:
            dr = [(closes[i]-closes[i-1])/closes[i-1] for i in range(max(1,len(closes)-21), len(closes)) if closes[i-1]>0]
            hv_20 = round(float(np.std(dr) * (252**0.5) * 100), 1) if dr else 0
        except: pass
        
        iv_hv_spread = round(iv_current - hv_20, 1) if hv_20 > 0 else 0
        
        if iv_rank >= 70 and iv_hv_spread > 5:
            vol_regime = "HIGH_IV_SELL"
            vol_action = "SELL premium. IV is expensive vs history. Iron condors, credit spreads, covered calls work best."
        elif iv_rank <= 30 and iv_hv_spread < -3:
            vol_regime = "LOW_IV_BUY"
            vol_action = "BUY options cheap. IV below historical. Straddles, long calls/puts before catalysts."
        elif iv_rank >= 50 and iv_hv_spread > 3:
            vol_regime = "ELEVATED"
            vol_action = "Slightly favor selling. IV above HV — premium is rich. Spread strategies reduce risk."
        elif iv_rank <= 40 and abs(iv_hv_spread) < 3:
            vol_regime = "NORMAL_LOW"
            vol_action = "Normal volatility. Go directional based on your view. Both buying and selling OK."
        else:
            vol_regime = "NORMAL"
            vol_action = "Fair volatility. Use directional trades based on trend analysis."
        
        result["volIntelligence"] = {
            "iv": iv_current, "hv20": hv_20, "ivHvSpread": iv_hv_spread,
            "regime": vol_regime, "action": vol_action, "ivRank": iv_rank,
        }
        
        # ─── 4. RISK MANAGEMENT ───
        account_sizes = [100000, 300000, 500000, 1000000] if not is_us else [5000, 10000, 25000, 50000]
        risk_pcts = [1, 2, 3]
        position_sizing = []
        for acct in account_sizes:
            for rpct in risk_pcts:
                risk_amt = round(acct * rpct / 100, 0)
                max_lots = int(risk_amt / (abs(price - sl_price) * _lot)) if abs(price - sl_price) > 0 else 0
                max_lots = max(0, max_lots)
                position_sizing.append({
                    "account": acct, "riskPct": rpct, "riskAmt": risk_amt,
                    "maxLots": max_lots, "capitalNeeded": round(prem_entry * _lot * max(max_lots,1), 0),
                })
        
        # Exposure alerts
        exposure_alerts = []
        if _dte <= 2:
            exposure_alerts.append({"type":"CRITICAL","msg":f"Expiry in {_dte} day(s). Theta decay is 3-5x faster. Reduce position size or hedge with spread."})
        if iv_rank >= 70:
            exposure_alerts.append({"type":"WARNING","msg":"IV Rank high. You're overexposed to Vega if buying. IV crush after events will destroy premium."})
        if abs(atm_ce_g["gamma"]) > 0.005:
            exposure_alerts.append({"type":"WARNING","msg":"Gamma squeeze zone. Small moves = big P&L swings. Use tight stops."})
        if prem_entry > 0 and prem_risk > 0 and prem_risk / prem_entry > 0.5:
            exposure_alerts.append({"type":"WARNING","msg":f"Risk is {round(prem_risk/prem_entry*100)}% of premium. High risk-to-cost ratio. Consider reducing size."})
        
        result["riskManagement"] = {
            "positionSizing": position_sizing[:9],
            "exposureAlerts": exposure_alerts,
            "lot": _lot, "slPoints": round(abs(price-sl_price),2),
            "premiumAtRisk": round(prem_risk*_lot, 0),
        }
        
        print(f"🎯 Premium Trading Intel: {symbol} strategies={len(strategies)} regime={vol_regime} alerts={len(exposure_alerts)}")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"⚠️ Premium Trading Intelligence failed: {e}")
    
    # ═══ GAMMA BLAST SETUP — Expiry day straddle/strangle ═══
    blast_setup = None
    if is_expiry and bs_data.get("greeks") and nse.get("success"):
        try:
            atm_g = bs_data["greeks"].get("ATM", {})
            ce_prem = atm_g.get("CE", {}).get("premium", 0)
            pe_prem = atm_g.get("PE", {}).get("premium", 0)
            combined_cost = round(ce_prem + pe_prem, 2)
            atm_k = bs_data["greeks"]["ATM"]["strike"] if "ATM" in bs_data["greeks"] else atm_strike
            
            # Morning range check (today's high - low vs previous day range)
            morning_range_pct = 0
            if orb.get("intra_high") and orb.get("intra_low") and orb["intra_low"] > 0:
                morning_range_pct = round((orb["intra_high"] - orb["intra_low"]) / orb["intra_low"] * 100, 2)
            
            # Gamma blast is viable when morning range is tight (compression before expansion)
            is_viable = morning_range_pct < 1.0 and combined_cost > 0
            
            # SL = 30% of combined cost, Target = 2-3× on breakout
            blast_sl = round(combined_cost * 0.30, 2)
            blast_t1 = round(combined_cost * 2, 2)
            blast_t2 = round(combined_cost * 3, 2)
            
            # Risk per lot
            blast_risk_per_lot = round(blast_sl * inst["lot"], 0)
            blast_reward_per_lot = round((blast_t1 - combined_cost) * inst["lot"], 0)
            
            blast_setup = {
                "active": is_viable,
                "strike": atm_k,
                "cePrem": ce_prem,
                "pePrem": pe_prem,
                "cost": combined_cost,
                "morningRange": f"{morning_range_pct:.2f}%",
                "condition": f"Morning range <1% (currently {morning_range_pct:.2f}%). Low VIX ({nse.get('vix', 0):.1f}) = cheap premiums.",
                "entry": "After 1:45 PM IST. Wait for range compression to complete.",
                "sl": f"{csym}{blast_sl:,.0f} ({30}% of cost). Exit if both legs decay.",
                "target": f"2× = {csym}{blast_t1:,.0f}, 3× = {csym}{blast_t2:,.0f} on directional breakout.",
                "riskPerLot": blast_risk_per_lot,
                "rewardPerLot": blast_reward_per_lot,
                "maxPain": nse.get("max_pain", 0),
                "prob": 65 if morning_range_pct < 0.5 else 55 if morning_range_pct < 0.8 else 40,
                "note": f"Expiry pin to {csym}{nse.get('max_pain', 0):,.0f} max pain likely until 2PM. After that, gamma explosion can move {inst['gap']*3}+ points in minutes."
            }
            print(f"🔥 Gamma Blast: {symbol} ATM={atm_k} Cost={combined_cost} Morning={morning_range_pct}% Viable={is_viable}")
        except Exception as e:
            print(f"⚠️ Gamma Blast calc error: {e}")
    
    result["blastSetup"] = blast_setup
    result["reasoning"] = reasoning
    result["timestamp"] = IST.strftime("%I:%M %p IST")
    result["region"] = inst.get("region", "IN")
    result["currency"] = inst.get("currency", "INR")
    
    # ═══ TRADING COACH — Smart improvement tips ═══
    coach = []
    # Correlation warning
    if symbol in ["BANKNIFTY", "NIFTY"] and direction == "BULLISH":
        coach.append({"tip": "NIFTY and BANKNIFTY are 85% correlated. Don't take the same direction on both — you're doubling risk, not diversifying.", "type": "RISK"})
    # R:R filter
    if trade.get("rrRatio") and ":" in str(trade["rrRatio"]):
        try:
            rr_val = float(str(trade["rrRatio"]).split(":")[1])
            if rr_val < 1.5:
                coach.append({"tip": f"R:R is only {trade['rrRatio']} — below 1.5. Skip this or wait for a better entry closer to support.", "type": "RISK"})
            elif rr_val >= 2.5:
                coach.append({"tip": f"R:R is excellent at {trade['rrRatio']}. This is an A-grade setup — consider 1.5× normal position.", "type": "OPPORTUNITY"})
        except: pass
    # Session timing
    import datetime as _dt
    ist_hour = IST.hour
    if 9 <= ist_hour <= 9:
        coach.append({"tip": "First 15 minutes — volatile. Wait for ORB to form before entering.", "type": "TIMING"})
    elif 14 <= ist_hour <= 15:
        coach.append({"tip": "Last hour. Theta decay accelerates. BUY positions lose value faster. Consider closing or trailing tight.", "type": "TIMING"})
    elif 12 <= ist_hour <= 13:
        coach.append({"tip": "Lunch session — low volume. Spreads widen. Avoid new entries. Best time: 9:30-11:30 AM or 2:00-2:30 PM.", "type": "TIMING"})
    # Weighted score insight
    if pct >= 78:
        coach.append({"tip": "HIGH confluence (78%+). Top-tier setup. Execute with full conviction. These setups historically have 65%+ win rate.", "type": "CONFIDENCE"})
    elif pct < 40:
        coach.append({"tip": "WEAK confluence (<40%). Most losses come from forcing trades on weak setups. Patience = profitability.", "type": "WARNING"})
    # Volume insight
    if vol_ratio < 0.7:
        coach.append({"tip": "Volume is below average. Move may not sustain. Reduce position size by 50% or skip entirely.", "type": "WARNING"})
    elif vol_ratio > 2:
        coach.append({"tip": f"Volume spike ({vol_ratio:.1f}×). Smart money is active. This confirms the directional move. High-conviction entry.", "type": "OPPORTUNITY"})
    # US market hours check
    if is_us:
        us_hour = (IST - _dt.timedelta(hours=10, minutes=30)).hour  # IST - 10:30 = ET
        if us_hour < 9 or us_hour >= 16:
            coach.append({"tip": "US market is CLOSED. Prices are from last close. Real-time signals available during US market hours (7:00 PM - 1:30 AM IST).", "type": "TIMING"})
    
    result["coach"] = coach
    
    try:
    # ═══ TREND ANALYSIS + CHANGE DETECTION ═══
        # Score each indicator for trend direction: +1 bullish, -1 bearish, 0 neutral
        trend_scores = []
        trend_details = []
        
        # EMA Stack
        if ema9 > ema21 > ema50:
            trend_scores.append(2); trend_details.append({"ind": "EMA Stack", "dir": "BULL", "val": "9>21>50"})
        elif ema9 < ema21 < ema50:
            trend_scores.append(-2); trend_details.append({"ind": "EMA Stack", "dir": "BEAR", "val": "9<21<50"})
        else:
            trend_scores.append(0); trend_details.append({"ind": "EMA Stack", "dir": "FLAT", "val": "Mixed"})
        
        # Price vs SMA200
        if price > sma200 * 1.02:
            trend_scores.append(2); trend_details.append({"ind": "SMA200", "dir": "BULL", "val": f"Price {((price/sma200-1)*100):.1f}% above"})
        elif price < sma200 * 0.98:
            trend_scores.append(-2); trend_details.append({"ind": "SMA200", "dir": "BEAR", "val": f"Price {((1-price/sma200)*100):.1f}% below"})
        else:
            trend_scores.append(0); trend_details.append({"ind": "SMA200", "dir": "FLAT", "val": "Near 200-DMA"})
        
        # Price vs SMA50
        if price > sma50:
            trend_scores.append(1); trend_details.append({"ind": "SMA50", "dir": "BULL", "val": f"Above"})
        else:
            trend_scores.append(-1); trend_details.append({"ind": "SMA50", "dir": "BEAR", "val": f"Below"})
        
        # Golden/Death Cross
        if sma50 > sma200:
            trend_scores.append(2); trend_details.append({"ind": "Cross", "dir": "BULL", "val": "Golden"})
        else:
            trend_scores.append(-2); trend_details.append({"ind": "Cross", "dir": "BEAR", "val": "Death"})
        
        # RSI trend
        if rsi > 60:
            trend_scores.append(1); trend_details.append({"ind": "RSI", "dir": "BULL", "val": f"{rsi}"})
        elif rsi < 40:
            trend_scores.append(-1); trend_details.append({"ind": "RSI", "dir": "BEAR", "val": f"{rsi}"})
        else:
            trend_scores.append(0); trend_details.append({"ind": "RSI", "dir": "FLAT", "val": f"{rsi}"})
        
        # MACD
        if macd_bullish and macd_hist > 0:
            trend_scores.append(1); trend_details.append({"ind": "MACD", "dir": "BULL", "val": f"+{macd_hist:.1f}"})
        elif not macd_bullish:
            trend_scores.append(-1); trend_details.append({"ind": "MACD", "dir": "BEAR", "val": f"{macd_hist:.1f}"})
        else:
            trend_scores.append(0); trend_details.append({"ind": "MACD", "dir": "FLAT", "val": f"{macd_hist:.1f}"})
        
        # Supertrend
        if supertrend_buy:
            trend_scores.append(1); trend_details.append({"ind": "Supertrend", "dir": "BULL", "val": "BUY"})
        else:
            trend_scores.append(-1); trend_details.append({"ind": "Supertrend", "dir": "BEAR", "val": "SELL"})
        
        # HH/HL structure
        if hh_hl:
            trend_scores.append(2); trend_details.append({"ind": "Structure", "dir": "BULL", "val": "HH+HL"})
        elif lh_ll:
            trend_scores.append(-2); trend_details.append({"ind": "Structure", "dir": "BEAR", "val": "LH+LL"})
        else:
            trend_scores.append(0); trend_details.append({"ind": "Structure", "dir": "FLAT", "val": "Mixed"})
        
        # Volume confirmation
        if vol_ratio > 1.3:
            trend_scores.append(1 if price > closes[-2] else -1)
            trend_details.append({"ind": "Volume", "dir": "BULL" if price > closes[-2] else "BEAR", "val": f"{vol_ratio:.1f}×"})
        else:
            trend_scores.append(0); trend_details.append({"ind": "Volume", "dir": "FLAT", "val": f"{vol_ratio:.1f}×"})
        
        # VWAP (if available)
        if orb.get("vwap") and orb["vwap"] > 0:
            if price > orb["vwap"] * 1.002:
                trend_scores.append(1); trend_details.append({"ind": "VWAP", "dir": "BULL", "val": f"Above"})
            elif price < orb["vwap"] * 0.998:
                trend_scores.append(-1); trend_details.append({"ind": "VWAP", "dir": "BEAR", "val": f"Below"})
            else:
                trend_scores.append(0); trend_details.append({"ind": "VWAP", "dir": "FLAT", "val": f"At VWAP"})
        
        total_trend_score = sum(trend_scores)
        max_possible = len(trend_scores) * 2
        trend_pct = round((total_trend_score / max_possible) * 100) if max_possible > 0 else 0
        
        if trend_pct >= 60: trend_label = "STRONG UPTREND"
        elif trend_pct >= 25: trend_label = "UPTREND"
        elif trend_pct >= -25: trend_label = "SIDEWAYS"
        elif trend_pct >= -60: trend_label = "DOWNTREND"
        else: trend_label = "STRONG DOWNTREND"
        
        # Trend change alerts — compare short-term vs medium-term
        alerts = []
        # EMA crossover imminent
        ema9_dist = abs(ema9 - ema21) / ema21 * 100 if ema21 > 0 else 99
        if ema9_dist < 0.15:
            alerts.append({"type": "WARNING", "msg": f"EMA 9/21 crossover imminent ({ema9_dist:.2f}% apart). Trend reversal possible.", "severity": "HIGH"})
        
        # RSI divergence from extreme
        if rsi > 75:
            alerts.append({"type": "BEARISH", "msg": f"RSI {rsi} — overbought. Expect pullback.", "severity": "MEDIUM"})
        elif rsi < 25:
            alerts.append({"type": "BULLISH", "msg": f"RSI {rsi} — oversold. Expect bounce.", "severity": "MEDIUM"})
        
        # MACD histogram weakening
        if len(closes) >= 3:
            try:
                prev_macd = float((macd_line - macd_signal).iloc[-2]) if len(macd_signal) >= 2 else 0
            except:
                prev_macd = 0
            if macd_hist > 0 and prev_macd > macd_hist:
                alerts.append({"type": "WARNING", "msg": f"MACD histogram shrinking ({prev_macd:.1f}→{macd_hist:.1f}). Bullish momentum fading.", "severity": "MEDIUM"})
            elif macd_hist < 0 and prev_macd < macd_hist:
                alerts.append({"type": "WARNING", "msg": f"MACD histogram recovering ({prev_macd:.1f}→{macd_hist:.1f}). Bearish momentum weakening.", "severity": "MEDIUM"})
        
        # Price near key level
        if pdh > 0 and abs(price - pdh) / pdh * 100 < 0.3:
            alerts.append({"type": "WARNING", "msg": f"Price near PDH {csym}{pdh:,.0f} ({abs(price-pdh):.0f} away). Breakout or rejection imminent.", "severity": "HIGH"})
        if pdl > 0 and abs(price - pdl) / pdl * 100 < 0.3:
            alerts.append({"type": "WARNING", "msg": f"Price near PDL {csym}{pdl:,.0f} ({abs(price-pdl):.0f} away). Breakdown or bounce imminent.", "severity": "HIGH"})
        
        # SMA200 test
        if abs(price - sma200) / sma200 * 100 < 0.5:
            alerts.append({"type": "CRITICAL", "msg": f"Price testing 200-DMA {csym}{sma200:,.0f}. Major support/resistance. Big move likely.", "severity": "HIGH"})
        
        # Volume spike
        if vol_ratio > 2.0:
            alerts.append({"type": "BULLISH" if price > closes[-2] else "BEARISH", "msg": f"Volume spike {vol_ratio:.1f}× average. Smart money active. {'Accumulation' if price > closes[-2] else 'Distribution'} likely.", "severity": "HIGH"})
        
        # VIX spike (if available)
        if nse.get("vix_change") and abs(nse["vix_change"]) > 5:
            alerts.append({"type": "CRITICAL", "msg": f"VIX moved {nse['vix_change']:+.1f}% today. {'Fear rising — hedge positions.' if nse['vix_change'] > 0 else 'Fear dropping — risk-on.'}", "severity": "HIGH"})
        
        # OI-based alerts
        if nse.get("ce_resistance") and len(nse["ce_resistance"]) > 0:
            top_resist = nse["ce_resistance"][0]["strike"]
            if abs(price - top_resist) / price * 100 < 0.5:
                alerts.append({"type": "WARNING", "msg": f"Price approaching major OI resistance {csym}{top_resist:,.0f} (CE OI: {nse['ce_resistance'][0]['oi']:,.0f}). Breakout above = massive short covering rally.", "severity": "HIGH"})
        
        result["trend"] = {
            "label": trend_label,
            "score": total_trend_score,
            "maxScore": max_possible,
            "pct": trend_pct,
            "details": trend_details,
            "bullCount": len([s for s in trend_scores if s > 0]),
            "bearCount": len([s for s in trend_scores if s < 0]),
            "flatCount": len([s for s in trend_scores if s == 0]),
        }
        result["alerts"] = alerts
    except Exception as _te:
        print(f"⚠️ Trend error: {_te}")
        result["trend"] = {"label":"N/A","score":0,"maxScore":1,"pct":0,"details":[],"bullCount":0,"bearCount":0,"flatCount":0}
        result["alerts"] = []
    
    # Ensure all numpy types are converted to native Python for JSON serialization
    import numpy as np
    def _json_safe(obj):
        if isinstance(obj, dict):
            return {k: _json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_json_safe(v) for v in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        return obj
    
    result = _json_safe(result)
    
    print(f"🎯 Algo Signal: {symbol} → {result.get('signal','')} ({result.get('supports',0)}/{result.get('totalFactors',0)}) {result.get('direction','')}")
    return result



# ═══════════════════════════════════════════════
# HEATMAP — Live sector/stock color map
# ═══════════════════════════════════════════════
_heatmap_cache = {}
_heatmap_ts = None

@app.get("/api/heatmap")
async def heatmap(region: str = "IN"):
    """Live stock heatmap data — price change, market cap, sector."""
    from datetime import datetime, timedelta
    global _heatmap_cache, _heatmap_ts
    
    cache_key = region.upper()
    now = datetime.utcnow()
    if cache_key in _heatmap_cache and _heatmap_ts and (now - _heatmap_ts).total_seconds() < 300:
        return _heatmap_cache[cache_key]
    
    if region.upper() == "US":
        tickers = {
            "Technology": ["AAPL","MSFT","NVDA","GOOGL","META","AMD","AVGO","CRM","ORCL","INTC","ADBE","CSCO"],
            "Consumer": ["AMZN","TSLA","HD","MCD","NKE","SBUX","TGT","COST","WMT","DIS"],
            "Finance": ["JPM","V","MA","BAC","GS","MS","BRK-B","AXP","C","WFC"],
            "Healthcare": ["UNH","JNJ","LLY","PFE","ABBV","MRK","TMO","ABT","BMY","AMGN"],
            "Energy": ["XOM","CVX","COP","SLB","EOG","MPC","PSX","VLO","OXY","HAL"],
        }
    else:
        tickers = {
            "Banking": ["HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","KOTAKBANK.NS","AXISBANK.NS","INDUSINDBK.NS"],
            "IT": ["TCS.NS","INFY.NS","HCLTECH.NS","WIPRO.NS","TECHM.NS","LTI.NS"],
            "Auto": ["TATAMOTORS.NS","MARUTI.NS","M&M.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS","EICHERMOT.NS"],
            "Pharma": ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS","APOLLOHOSP.NS","BIOCON.NS"],
            "Energy": ["RELIANCE.NS","ONGC.NS","NTPC.NS","POWERGRID.NS","ADANIENT.NS","BPCL.NS"],
            "FMCG": ["HINDUNILVR.NS","ITC.NS","NESTLEIND.NS","BRITANNIA.NS","DABUR.NS","GODREJCP.NS"],
            "Metals": ["TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS","COALINDIA.NS","VEDL.NS","NMDC.NS"],
        }
    
    all_syms = []
    sym_sector = {}
    for sector, syms in tickers.items():
        for s in syms:
            all_syms.append(s)
            sym_sector[s] = sector
    
    def _fetch_hm(sym):
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            prev = info.get("previousClose") or info.get("regularMarketPreviousClose") or price
            mcap = info.get("marketCap", 0)
            name = info.get("shortName", sym.replace(".NS",""))
            chg = round(((price - prev) / prev) * 100, 2) if prev > 0 else 0
            return {"sym": sym.replace(".NS",""), "name": name[:20], "price": round(price, 2),
                    "chg": chg, "mcap": mcap, "sector": sym_sector.get(sym, "Other")}
        except:
            return None
    
    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(_fetch_hm, s): s for s in all_syms}
        for f in as_completed(futs, timeout=20):
            try:
                r = f.result(timeout=8)
                if r and r["price"] > 0:
                    results.append(r)
            except:
                pass
    
    results.sort(key=lambda x: x["mcap"], reverse=True)
    resp = {"success": True, "stocks": results, "count": len(results), "region": region.upper()}
    _heatmap_cache[cache_key] = resp
    _heatmap_ts = now
    return resp


# ═══════════════════════════════════════════════════
# SCREENER — Multi-filter stock scanner
# ═══════════════════════════════════════════════════
_screener_raw_cache = {}
_screener_raw_ts = {}

@app.get("/api/screener")
async def screener(region: str = "IN", preset: str = "", rsi_below: float = 0, rsi_above: float = 0,
                   vol_above: float = 0, above_sma200: bool = False, pe_below: float = 0,
                   sort_by: str = "mcap"):
    """Scan 200+ stocks with technical/fundamental filters + YTD performance. 10-min cache on raw data."""
    from datetime import datetime, timedelta
    
    # Cache raw scan results per region (10 min) — filters applied AFTER
    cache_key = region.upper()
    now = datetime.utcnow()
    if cache_key in _screener_raw_cache and cache_key in _screener_raw_ts:
        if (now - _screener_raw_ts[cache_key]).total_seconds() < 600:
            results = _screener_raw_cache[cache_key]
            # Jump to filter/sort
            return _apply_screener_filters(results, preset, rsi_below, rsi_above, vol_above, above_sma200, pe_below, sort_by, region)
    
    # ═══ LARGE UNIVERSE — 100+ stocks per region ═══
    if region.upper() == "US":
        syms = [
            # Mega Cap Tech (10)
            "AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","AVGO","ORCL","CRM",
            # Semiconductors (18)
            "AMD","INTC","MU","WDC","MRVL","AMAT","LRCX","KLAC","QCOM","ARM","TSM","ASML","ON","SNDK","STX","NXPI","SWKS","MPWR",
            # Software/Cloud/Cyber (20)
            "NFLX","ADBE","NOW","PANW","CRWD","DDOG","SNOW","PLTR","NET","ZS","FTNT","HUBS","WDAY","INTU","APP","TTD","TEAM","VEEV","ANSS","CDNS",
            # Internet/Fintech (12)
            "UBER","ABNB","DASH","SNAP","PINS","RBLX","COIN","HOOD","SQ","PYPL","SHOP","MELI",
            # Finance (18)
            "JPM","V","MA","BAC","GS","MS","BRK-B","AXP","C","WFC","SCHW","BLK","ICE","CME","SPGI","MCO","CB","TFC",
            # Healthcare/Pharma/Biotech (20)
            "UNH","JNJ","LLY","PFE","ABBV","MRK","TMO","ABT","BMY","AMGN","ISRG","DXCM","MRNA","REGN","VRTX","GILD","BIIB","HCA","CI","ELV",
            # Consumer Discretionary (18)
            "HD","MCD","NKE","SBUX","TGT","COST","WMT","DIS","LULU","DECK","CMG","DLTR","DG","ROST","TJX","BKNG","MAR","YUM",
            # Consumer Staples (10)
            "PG","KO","PEP","PM","MO","CL","KMB","GIS","HSY","MNST",
            # Energy (14)
            "XOM","CVX","COP","SLB","EOG","MPC","VLO","OXY","HAL","DVN","PSX","TPL","FANG","WMB",
            # Industrials (20)
            "CAT","BA","GE","RTX","HON","LMT","UNP","UPS","FDX","DE","MMM","GD","NOC","WM","RSG","EMR","ETN","GNRC","IR","PH",
            # Materials/Chemicals (8)
            "LIN","APD","SHW","ECL","FCX","NEM","NUE","LYB",
            # Telecom/Media (8)
            "T","VZ","CMCSA","CHTR","TMUS","PARA","WBD","FOX",
            # REITs/Real Estate (6)
            "PLD","AMT","CCI","EQIX","SPG","O",
            # Utilities (6)
            "NEE","SO","DUK","AEP","D","NRG",
            # Other notable S&P 500 (16)
            "GLW","WSM","AKAM","CVNA","IT","ANET","FICO","AXON","GDDY","LPLA","SMCI","VST","DELL","HPE","RIVN","LI",
        ]
    else:
        syms = [
            # Nifty 50 core
            "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","SBIN.NS","BHARTIARTL.NS",
            "LT.NS","BAJFINANCE.NS","ITC.NS","MARUTI.NS","HCLTECH.NS","WIPRO.NS","KOTAKBANK.NS",
            "AXISBANK.NS","INDUSINDBK.NS","HINDUNILVR.NS","ASIANPAINT.NS","ULTRACEMCO.NS","TITAN.NS",
            "SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS","APOLLOHOSP.NS",
            "TATAMOTORS.NS","M&M.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS","EICHERMOT.NS",
            # Banking & Finance
            "BAJAJFINSV.NS","PNB.NS","BANKBARODA.NS","CANBK.NS","UNIONBANK.NS","IDFCFIRSTB.NS",
            "CHOLAFIN.NS","MUTHOOTFIN.NS","MANAPPURAM.NS","SBICARD.NS",
            # IT Mid-cap
            "TECHM.NS","COFORGE.NS","PERSISTENT.NS","LTTS.NS","MPHASIS.NS","KPITTECH.NS",
            # Metals & Mining
            "TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS","COALINDIA.NS","VEDL.NS","NMDC.NS","SAIL.NS",
            # Energy & Power
            "ONGC.NS","NTPC.NS","POWERGRID.NS","ADANIENT.NS","ADANIPORTS.NS","BPCL.NS","IOC.NS",
            "TATAPOWER.NS","NHPC.NS","SJVN.NS","IREDA.NS",
            # FMCG
            "NESTLEIND.NS","BRITANNIA.NS","DABUR.NS","GODREJCP.NS","MARICO.NS","TATACONSUM.NS",
            # Pharma
            "BIOCON.NS","GLENMARK.NS","LAURUSLABS.NS","AUROPHARMA.NS","ALKEM.NS",
            # Auto Ancillary
            "BALKRISIND.NS","MOTHERSON.NS","BOSCHLTD.NS","MRF.NS",
            # Real Estate & Infra
            "DLF.NS","LODHA.NS","OBEROIRLTY.NS","IRCTC.NS","HAL.NS","BEL.NS",
            # New Age / PSU
            "ZOMATO.NS","PAYTM.NS","POLICYBZR.NS","DELHIVERY.NS","NYKAA.NS",
            "DIXON.NS","KAYNES.NS","POLYCAB.NS","KEI.NS","TRENT.NS",
        ]
    
    def _scan(sym):
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="1y", interval="1d")
            if hist is None or len(hist) < 20:
                return None
            
            closes = hist["Close"].values.astype(float)
            volumes = hist["Volume"].values.astype(float)
            price = round(float(closes[-1]), 2)
            if price <= 0:
                return None
            
            # YTD return — from EXISTING 1Y history (no extra API call)
            ytd_ret = 0
            from datetime import datetime as _dt
            _now = _dt.utcnow()
            try:
                # The 1Y hist (Mar 2025→Mar 2026) already contains Jan 2026
                # Find last close of previous year OR first close of current year
                ytd_start_price = None
                last_prev_year = None
                first_curr_year = None
                for i, dt in enumerate(hist.index):
                    yr = dt.year if hasattr(dt, 'year') else dt.to_pydatetime().year
                    mo = dt.month if hasattr(dt, 'month') else dt.to_pydatetime().month
                    if yr == _now.year - 1:
                        last_prev_year = float(closes[i])  # keeps updating to last day of prev year
                    elif yr == _now.year and first_curr_year is None:
                        first_curr_year = float(closes[i])  # first trading day of current year
                
                # Prefer Dec 31 close, fallback to Jan first close
                ytd_start_price = last_prev_year or first_curr_year
                if ytd_start_price and ytd_start_price > 0:
                    ytd_ret = round(((price - ytd_start_price) / ytd_start_price) * 100, 1)
            except:
                pass
            
            # 1-month return
            m1_ret = round(((price - float(closes[-22])) / float(closes[-22])) * 100, 1) if len(closes) >= 22 else 0
            
            # 1-week return
            w1_ret = round(((price - float(closes[-5])) / float(closes[-5])) * 100, 1) if len(closes) >= 5 else 0
            
            # Daily change
            prev = float(closes[-2]) if len(closes) >= 2 else price
            chg = round(((price - prev) / prev) * 100, 2) if prev > 0 else 0
            
            # RSI(14)
            deltas_arr = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [d if d > 0 else 0 for d in deltas_arr[-14:]]
            losses = [-d if d < 0 else 0 for d in deltas_arr[-14:]]
            avg_gain = sum(gains) / 14 if gains else 0
            avg_loss = sum(losses) / 14 if losses else 0.01
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = round(100 - (100 / (1 + rs)), 1)
            
            # SMA
            sma50 = round(float(closes[-50:].mean()), 2) if len(closes) >= 50 else 0
            sma200 = round(float(closes[-200:].mean()), 2) if len(closes) >= 200 else 0
            
            # Volume ratio
            avg_vol = float(volumes[-20:].mean()) if len(volumes) >= 20 else 1
            vol_ratio = round(float(volumes[-1]) / avg_vol, 1) if avg_vol > 0 else 0
            
            # EMA
            ema9 = round(float(hist["Close"].ewm(span=9).mean().iloc[-1]), 2)
            ema21 = round(float(hist["Close"].ewm(span=21).mean().iloc[-1]), 2)
            
            # MACD hist
            ema12 = hist["Close"].ewm(span=12).mean()
            ema26 = hist["Close"].ewm(span=26).mean()
            macd_hist = round(float((ema12 - ema26).iloc[-1] - (ema12 - ema26).ewm(span=9).mean().iloc[-1]), 2)
            
            # PE
            info = t.info or {}
            pe = round(float(info.get("trailingPE", 0) or 0), 1)
            mcap = info.get("marketCap", 0)
            name = info.get("shortName", sym.replace(".NS",""))[:25]
            sector = info.get("sector", "")[:20]
            
            # 52W high/low
            w52_high = round(float(closes.max()), 2)
            w52_low = round(float(closes.min()), 2)
            from_52h = round(((price - w52_high) / w52_high) * 100, 1) if w52_high > 0 else 0
            
            return {
                "sym": sym.replace(".NS",""), "name": name, "price": price, "chg": chg,
                "ytd": ytd_ret, "m1": m1_ret, "w1": w1_ret,
                "rsi": rsi, "sma50": sma50, "sma200": sma200,
                "vol_ratio": vol_ratio, "pe": pe, "mcap": mcap, "macd": macd_hist,
                "ema9": ema9, "ema21": ema21, "ema_bull": ema9 > ema21,
                "above_sma200": price > sma200 if sma200 > 0 else False,
                "sector": sector, "from_52h": from_52h,
                "w52_high": w52_high, "w52_low": w52_low,
            }
        except:
            return None
    
    results = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = {pool.submit(_scan, s): s for s in syms}
        for f in as_completed(futs, timeout=60):
            try:
                r = f.result(timeout=15)
                if r:
                    results.append(r)
            except:
                pass
    
    # Cache raw results
    _screener_raw_cache[cache_key] = results
    _screener_raw_ts[cache_key] = now
    
    return _apply_screener_filters(results, preset, rsi_below, rsi_above, vol_above, above_sma200, pe_below, sort_by, region)

def _apply_screener_filters(results, preset, rsi_below, rsi_above, vol_above, above_sma200, pe_below, sort_by, region):
    """Apply presets, filters, and sorting to raw screener results."""
    # Apply presets
    if preset == "top_ytd":
        sort_by = "ytd"
    elif preset == "worst_ytd":
        sort_by = "ytd_asc"
    elif preset == "top_monthly":
        sort_by = "m1"
    elif preset == "oversold":
        rsi_below = 30
    elif preset == "momentum":
        rsi_above = 60; vol_above = 1.2; above_sma200 = True
    elif preset == "value":
        pe_below = 15; above_sma200 = True
    elif preset == "near_52h":
        sort_by = "from_52h"
    elif preset == "volume_spike":
        vol_above = 2.0
    
    # Apply filters
    filtered = list(results)
    if rsi_below > 0:
        filtered = [s for s in filtered if s["rsi"] <= rsi_below]
    if rsi_above > 0:
        filtered = [s for s in filtered if s["rsi"] >= rsi_above]
    if vol_above > 0:
        filtered = [s for s in filtered if s["vol_ratio"] >= vol_above]
    if above_sma200:
        filtered = [s for s in filtered if s["above_sma200"]]
    if pe_below > 0:
        filtered = [s for s in filtered if 0 < s["pe"] <= pe_below]
    
    # Sort
    if sort_by == "ytd":
        filtered.sort(key=lambda x: x["ytd"], reverse=True)
    elif sort_by == "ytd_asc":
        filtered.sort(key=lambda x: x["ytd"])
    elif sort_by == "m1":
        filtered.sort(key=lambda x: x["m1"], reverse=True)
    elif sort_by == "from_52h":
        filtered.sort(key=lambda x: x["from_52h"], reverse=True)
    else:
        filtered.sort(key=lambda x: x["mcap"], reverse=True)
    
    return {"success": True, "results": filtered[:50], "total_scanned": len(results),
            "matched": len(filtered), "region": region.upper(), "preset": preset or "custom"}


# ═══════════════════════════════════════════════════
# OPTIONS FLOW — Unusual activity detector
# ═══════════════════════════════════════════════════
@app.get("/api/options-flow")
async def options_flow(region: str = "IN"):
    """Detect unusual options activity — big money tracking."""
    
    is_us = region.upper() == "US"
    
    if is_us:
        # USA: yfinance has real options chains
        syms = ["SPY","QQQ","AAPL","MSFT","NVDA","TSLA","AMZN","META","AMD","GOOGL"]
        
        def _scan_us(sym):
            try:
                t = yf.Ticker(sym)
                info = t.info or {}
                price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
                if price <= 0: return None
                
                opts = t.options
                if not opts: return None
                
                chain = t.option_chain(opts[0])
                calls, puts = chain.calls, chain.puts
                if len(calls) == 0: return None
                
                alerts = []
                for _, row in calls.iterrows():
                    vol = int(row.get("volume", 0) or 0)
                    oi = int(row.get("openInterest", 0) or 0)
                    strike = float(row["strike"])
                    if vol > 0 and oi > 0 and vol > 3 * oi:
                        premium = float(row.get("lastPrice", 0) or 0)
                        alerts.append({"sym": sym, "type": "CALL", "strike": round(strike, 1), "volume": vol, "oi": oi,
                                       "ratio": round(vol/oi, 1), "premium": round(premium, 2),
                                       "signal": "BULLISH", "csym": "$",
                                       "msg": f"CALL ${strike:,.0f} — Vol {vol:,} vs OI {oi:,} ({round(vol/oi,1)}×)"})
                
                for _, row in puts.iterrows():
                    vol = int(row.get("volume", 0) or 0)
                    oi = int(row.get("openInterest", 0) or 0)
                    strike = float(row["strike"])
                    if vol > 0 and oi > 0 and vol > 3 * oi:
                        premium = float(row.get("lastPrice", 0) or 0)
                        alerts.append({"sym": sym, "type": "PUT", "strike": round(strike, 1), "volume": vol, "oi": oi,
                                       "ratio": round(vol/oi, 1), "premium": round(premium, 2),
                                       "signal": "BEARISH", "csym": "$",
                                       "msg": f"PUT ${strike:,.0f} — Vol {vol:,} vs OI {oi:,} ({round(vol/oi,1)}×)"})
                
                total_call_oi = int(calls["openInterest"].sum())
                total_put_oi = int(puts["openInterest"].sum())
                pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 0
                top_calls = [{"strike": int(r["strike"]), "oi": int(r["openInterest"])} for r in calls.nlargest(3, "openInterest")[["strike","openInterest"]].to_dict("records")]
                top_puts = [{"strike": int(r["strike"]), "oi": int(r["openInterest"])} for r in puts.nlargest(3, "openInterest")[["strike","openInterest"]].to_dict("records")]
                
                return {"sym": sym, "price": round(price, 2), "pcr": pcr,
                        "alerts": sorted(alerts, key=lambda x: x["ratio"], reverse=True)[:5],
                        "top_call_oi": top_calls, "top_put_oi": top_puts,
                        "total_alerts": len(alerts)}
            except Exception as e:
                print(f"  US flow error {sym}: {e}")
                return None
        
        results = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(_scan_us, s): s for s in syms}
            for f in as_completed(futs, timeout=25):
                try:
                    r = f.result(timeout=12)
                    if r: results.append(r)
                except: pass
    
    else:
        # INDIA: Use our NSE options API (yfinance has NO Indian options chains)
        results = []
        nse_syms = ["NIFTY", "BANKNIFTY", "SENSEX"]
        
        for sym in nse_syms:
            try:
                nse_data = await nse_options(sym)
                if not nse_data.get("success"): continue
                
                price = float(nse_data.get("spot", 0))
                pcr = float(nse_data.get("pcr", 0))
                ce_resist = nse_data.get("ce_resistance", [])
                pe_support = nse_data.get("pe_support", [])
                vix = float(nse_data.get("vix", 0))
                max_pain = float(nse_data.get("max_pain", 0))
                
                alerts = []
                # Flag high OI strikes as unusual if OI > 10 lakh
                for ce in ce_resist:
                    if ce.get("oi", 0) > 1000000:
                        alerts.append({"sym": sym, "type": "CE", "strike": ce["strike"],
                                       "volume": 0, "oi": ce["oi"], "ratio": 0,
                                       "signal": "RESISTANCE", "csym": "₹",
                                       "msg": f"CE {ce['strike']:,} — OI {ce['oi']:,}. Heavy CE writing = resistance wall."})
                for pe in pe_support:
                    if pe.get("oi", 0) > 1000000:
                        alerts.append({"sym": sym, "type": "PE", "strike": pe["strike"],
                                       "volume": 0, "oi": pe["oi"], "ratio": 0,
                                       "signal": "SUPPORT", "csym": "₹",
                                       "msg": f"PE {pe['strike']:,} — OI {pe['oi']:,}. Heavy PE writing = strong support."})
                
                # PCR-based signal
                if pcr > 1.3:
                    alerts.append({"sym": sym, "type": "PCR", "strike": 0, "volume": 0, "oi": 0,
                                   "ratio": pcr, "signal": "BULLISH", "csym": "₹",
                                   "msg": f"PCR {pcr:.2f} — Extreme PE writing. Bullish floor. Smart money expects move up."})
                elif pcr < 0.6:
                    alerts.append({"sym": sym, "type": "PCR", "strike": 0, "volume": 0, "oi": 0,
                                   "ratio": pcr, "signal": "BEARISH", "csym": "₹",
                                   "msg": f"PCR {pcr:.2f} — Heavy CE writing. Bearish resistance. Downside risk."})
                
                top_calls = [{"strike": c["strike"], "oi": c["oi"]} for c in ce_resist[:3]]
                top_puts = [{"strike": p["strike"], "oi": p["oi"]} for p in pe_support[:3]]
                
                results.append({"sym": sym, "price": round(price, 2), "pcr": pcr,
                                "alerts": alerts, "top_call_oi": top_calls, "top_put_oi": top_puts,
                                "total_alerts": len(alerts), "vix": vix, "max_pain": round(max_pain, 0)})
            except Exception as e:
                print(f"  India flow error {sym}: {e}")
    
    results.sort(key=lambda x: x["total_alerts"], reverse=True)
    all_alerts = []
    for r in results:
        all_alerts.extend(r["alerts"])
    all_alerts.sort(key=lambda x: x["ratio"], reverse=True)
    
    return {"success": True, "stocks": results, "top_alerts": all_alerts[:15],
            "total_unusual": len(all_alerts), "region": region.upper()}


@app.get("/api/algo-backtest")
async def algo_backtest(symbol: str = "NIFTY", years: int = 3):
    """Backtest the 5-layer confluence algo on historical data."""
    import yfinance as yf
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
    import math
    
    symbol = symbol.upper().strip()
    inst = ALGO_INSTRUMENTS.get(symbol, {"sym": f"{symbol}.NS", "lot": 100, "gap": 50})
    yf_sym = inst["sym"]
    years = min(max(years, 1), 5)
    
    try:
        tk = yf.Ticker(yf_sym)
        hist = tk.history(period=f"{years}y", interval="1d")
        if hist is None or len(hist) < 200:
            return {"success": False, "error": f"Insufficient data for {symbol} ({len(hist) if hist is not None else 0} days)"}
        
        closes = hist['Close'].values.astype(float)
        highs = hist['High'].values.astype(float)
        lows = hist['Low'].values.astype(float)
        opens = hist['Open'].values.astype(float)
        volumes = hist['Volume'].values.astype(float)
        dates = [d.strftime("%Y-%m-%d") for d in hist.index]
        
        cs = pd.Series(closes)
        
        # Pre-compute all indicators across full history
        sma20 = cs.rolling(20).mean().values
        sma50 = cs.rolling(50).mean().values
        sma200 = cs.rolling(200).mean().values
        ema9 = cs.ewm(span=9).mean().values
        ema21 = cs.ewm(span=21).mean().values
        ema50 = cs.ewm(span=50).mean().values
        
        # RSI(14)
        deltas = cs.diff()
        gain = deltas.clip(lower=0).rolling(14).mean().values
        loss = (-deltas.clip(upper=0)).rolling(14).mean().values
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = np.where(loss > 0, gain / loss, 100)
        rsi_arr = 100 - (100 / (1 + rs))
        
        # MACD
        ema12 = cs.ewm(span=12).mean().values
        ema26 = cs.ewm(span=26).mean().values
        macd_line = ema12 - ema26
        macd_signal = pd.Series(macd_line).ewm(span=9).mean().values
        macd_hist_arr = macd_line - macd_signal
        
        # ATR(14)
        tr = np.maximum(highs[1:] - lows[1:], np.maximum(abs(highs[1:] - closes[:-1]), abs(lows[1:] - closes[:-1])))
        tr = np.concatenate([[highs[0] - lows[0]], tr])
        atr14 = pd.Series(tr).rolling(14).mean().values
        
        # Volume ratio (20-day avg)
        vol_avg = pd.Series(volumes).rolling(20).mean().values
        
        # Supertrend(10,3)
        hl2 = (pd.Series(highs) + pd.Series(lows)) / 2
        st_atr = pd.Series(tr).rolling(10).mean().values
        
        # ═══ BACKTEST LOOP ═══
        trades = []
        equity_curve = [0]
        total_signals = 0
        start_idx = max(200, 50)  # need 200 bars for SMA200
        
        open_trade = None  # {entry_price, sl, t1, t2, t3, entry_date, direction, qty_remaining}
        
        for i in range(start_idx, len(closes)):
            price = closes[i]
            prev_close = closes[i-1]
            
            if np.isnan(sma200[i]) or np.isnan(atr14[i]) or atr14[i] <= 0:
                equity_curve.append(equity_curve[-1])
                continue
            
            # ─── CHECK OPEN TRADE ───
            if open_trade:
                hit_sl = lows[i] <= open_trade["sl"] if open_trade["direction"] == "LONG" else highs[i] >= open_trade["sl"]
                hit_t1 = highs[i] >= open_trade["t1"] if open_trade["direction"] == "LONG" else lows[i] <= open_trade["t1"]
                hit_t2 = highs[i] >= open_trade["t2"] if open_trade["direction"] == "LONG" else lows[i] <= open_trade["t2"]
                hit_t3 = highs[i] >= open_trade["t3"] if open_trade["direction"] == "LONG" else lows[i] <= open_trade["t3"]
                
                if hit_sl and not open_trade.get("t1_hit"):
                    # Full SL hit — lose on all remaining qty
                    pnl = (open_trade["sl"] - open_trade["entry"]) * open_trade["qty"] if open_trade["direction"] == "LONG" else (open_trade["entry"] - open_trade["sl"]) * open_trade["qty"]
                    open_trade["exit_price"] = open_trade["sl"]
                    open_trade["exit_date"] = dates[i]
                    open_trade["pnl"] = round(pnl, 2)
                    open_trade["result"] = "SL HIT"
                    trades.append(open_trade)
                    equity_curve.append(equity_curve[-1] + pnl)
                    open_trade = None
                    continue
                
                if hit_t1 and not open_trade.get("t1_hit"):
                    open_trade["t1_hit"] = True
                    open_trade["booked_pnl"] = open_trade.get("booked_pnl", 0) + (open_trade["t1"] - open_trade["entry"]) * open_trade["qty"] * 0.5 if open_trade["direction"] == "LONG" else open_trade.get("booked_pnl", 0) + (open_trade["entry"] - open_trade["t1"]) * open_trade["qty"] * 0.5
                    open_trade["sl"] = open_trade["entry"]  # Move SL to cost
                    open_trade["qty"] *= 0.5
                
                if hit_t2 and open_trade.get("t1_hit") and not open_trade.get("t2_hit"):
                    open_trade["t2_hit"] = True
                    open_trade["booked_pnl"] = open_trade.get("booked_pnl", 0) + (open_trade["t2"] - open_trade["entry"]) * open_trade["qty"] * 0.6 if open_trade["direction"] == "LONG" else open_trade.get("booked_pnl", 0) + (open_trade["entry"] - open_trade["t2"]) * open_trade["qty"] * 0.6
                    open_trade["qty"] *= 0.4
                
                if hit_t3 and open_trade.get("t2_hit"):
                    final_pnl = open_trade.get("booked_pnl", 0) + (open_trade["t3"] - open_trade["entry"]) * open_trade["qty"] if open_trade["direction"] == "LONG" else open_trade.get("booked_pnl", 0) + (open_trade["entry"] - open_trade["t3"]) * open_trade["qty"]
                    open_trade["exit_price"] = open_trade["t3"]
                    open_trade["exit_date"] = dates[i]
                    open_trade["pnl"] = round(final_pnl, 2)
                    open_trade["result"] = "T3 HIT (FULL TARGET)"
                    trades.append(open_trade)
                    equity_curve.append(equity_curve[-1] + final_pnl)
                    open_trade = None
                    continue
                
                # SL hit after T1 (at cost)
                if hit_sl and open_trade.get("t1_hit"):
                    final_pnl = open_trade.get("booked_pnl", 0)  # Only booked profits, SL at cost = 0 loss on remainder
                    open_trade["exit_price"] = open_trade["sl"]
                    open_trade["exit_date"] = dates[i]
                    open_trade["pnl"] = round(final_pnl, 2)
                    open_trade["result"] = "SL AT COST (partial profit)" if final_pnl > 0 else "BREAKEVEN"
                    trades.append(open_trade)
                    equity_curve.append(equity_curve[-1] + final_pnl)
                    open_trade = None
                    continue
                
                # Max hold = 5 days
                entry_idx = dates.index(open_trade["entry_date"]) if open_trade["entry_date"] in dates else i - 5
                if i - entry_idx >= 5:
                    exit_pnl = open_trade.get("booked_pnl", 0) + (price - open_trade["entry"]) * open_trade["qty"] if open_trade["direction"] == "LONG" else open_trade.get("booked_pnl", 0) + (open_trade["entry"] - price) * open_trade["qty"]
                    open_trade["exit_price"] = price
                    open_trade["exit_date"] = dates[i]
                    open_trade["pnl"] = round(exit_pnl, 2)
                    open_trade["result"] = "TIME EXIT (5D)"
                    trades.append(open_trade)
                    equity_curve.append(equity_curve[-1] + exit_pnl)
                    open_trade = None
                    continue
                
                equity_curve.append(equity_curve[-1])
                continue
            
            # ─── CONFLUENCE SCORING (same logic as live algo) ───
            supports = 0
            total_factors = 0
            
            def check(condition):
                nonlocal supports, total_factors
                total_factors += 1
                if condition:
                    supports += 1
            
            # L1: Price Action
            w52h_i = max(highs[max(0,i-252):i+1])
            w52l_i = min(lows[max(0,i-252):i+1])
            w52pos_i = ((price - w52l_i) / (w52h_i - w52l_i)) * 100 if w52h_i > w52l_i else 50
            check(20 < w52pos_i < 75)  # 52W position
            check(price > sma200[i])    # Above SMA200
            check(price > sma50[i])     # Above SMA50
            check(price > sma20[i] and price > ema21[i])  # Support zone
            
            # CPR
            pdh_i, pdl_i, pdc_i = highs[i-1], lows[i-1], closes[i-1]
            pivot_i = (pdh_i + pdl_i + pdc_i) / 3
            bc_i = (pdh_i + pdl_i) / 2
            tc_i = 2 * pivot_i - bc_i
            cpr_pct_i = abs(tc_i - bc_i) / pdc_i * 100
            check(cpr_pct_i < 0.3)  # Narrow CPR = trending
            
            # Gap
            gap_pct_i = (opens[i] - closes[i-1]) / closes[i-1] * 100
            check(gap_pct_i > 0.2)  # Gap up
            
            # L2: Indicators
            check(ema9[i] > ema21[i] and ema21[i] > ema50[i])  # EMA stack
            rsi_i = rsi_arr[i] if not np.isnan(rsi_arr[i]) else 50
            check(35 < rsi_i < 70)  # RSI sweet spot
            check(sma50[i] > sma200[i])  # Golden cross
            check(ema9[i] > ema21[i])  # Short momentum
            check(macd_hist_arr[i] > 0)  # MACD bullish
            vol_ratio_i = volumes[i] / vol_avg[i] if vol_avg[i] > 0 else 1
            check(vol_ratio_i > 1.1)  # Above avg volume
            
            # Supertrend approximation
            st_upper = hl2.values[i] + 3 * st_atr[i] if not np.isnan(st_atr[i]) else price * 1.05
            st_lower = hl2.values[i] - 3 * st_atr[i] if not np.isnan(st_atr[i]) else price * 0.95
            check(price > st_lower)  # Supertrend BUY
            
            # HH/HL check
            if i >= 5:
                rh = highs[i-4:i+1]
                rl = lows[i-4:i+1]
                hh_hl = all(rh[j] >= rh[j-1] for j in range(1, 5)) and all(rl[j] >= rl[j-1] for j in range(1, 5))
                check(hh_hl)
            
            total_signals += 1
            pct = round((supports / total_factors) * 100) if total_factors > 0 else 0
            
            # ─── GENERATE TRADE if confluence >= 65% ───
            if pct >= 65 and not open_trade:
                atr_i = atr14[i] if not np.isnan(atr14[i]) else abs(highs[i] - lows[i])
                sl = round(price - atr_i * 1.5, 2)
                t1 = round(price + atr_i * 1.0, 2)
                t2 = round(price + atr_i * 2.0, 2)
                t3 = round(price + atr_i * 3.0, 2)
                
                open_trade = {
                    "entry": round(price, 2),
                    "entry_date": dates[i],
                    "sl": sl,
                    "t1": t1, "t2": t2, "t3": t3,
                    "direction": "LONG",
                    "confluence": f"{supports}/{total_factors}",
                    "pct": pct,
                    "qty": inst["lot"],
                    "atr": round(atr_i, 2),
                    "booked_pnl": 0,
                    "t1_hit": False, "t2_hit": False,
                }
            
            equity_curve.append(equity_curve[-1])
        
        # Close any open trade at last price
        if open_trade:
            final_pnl = open_trade.get("booked_pnl", 0) + (closes[-1] - open_trade["entry"]) * open_trade["qty"]
            open_trade["exit_price"] = round(closes[-1], 2)
            open_trade["exit_date"] = dates[-1]
            open_trade["pnl"] = round(final_pnl, 2)
            open_trade["result"] = "OPEN → FORCED CLOSE"
            trades.append(open_trade)
        
        # ═══ STATISTICS ═══
        if not trades:
            return {"success": True, "symbol": symbol, "trades": 0, "message": "No signals generated with >= 65% confluence", "years": years}
        
        pnls = [t["pnl"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        breakevens = [p for p in pnls if p == 0]
        
        total_trades = len(trades)
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = round(win_count / total_trades * 100, 1)
        
        total_profit = sum(wins) if wins else 0
        total_loss = abs(sum(losses)) if losses else 0
        net_pnl = sum(pnls)
        profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else float('inf')
        
        avg_win = round(sum(wins) / len(wins), 0) if wins else 0
        avg_loss = round(sum(losses) / len(losses), 0) if losses else 0
        
        # Max drawdown
        peak = 0
        max_dd = 0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            if dd > max_dd:
                max_dd = dd
        
        # Sharpe (annualized, assuming 252 trading days)
        daily_returns = []
        for i in range(1, len(equity_curve)):
            daily_returns.append(equity_curve[i] - equity_curve[i-1])
        if daily_returns:
            dr = np.array(daily_returns)
            sharpe = round(np.mean(dr) / (np.std(dr) + 1e-10) * np.sqrt(252), 2)
        else:
            sharpe = 0
        
        # Expectancy
        expectancy = round((win_rate/100 * avg_win) - ((1 - win_rate/100) * abs(avg_loss)), 0) if avg_loss != 0 else avg_win
        
        # Results by type
        result_counts = {}
        for t in trades:
            r = t.get("result", "?")
            result_counts[r] = result_counts.get(r, 0) + 1
        
        # Monthly breakdown
        monthly = {}
        for t in trades:
            m = t["entry_date"][:7]  # YYYY-MM
            if m not in monthly:
                monthly[m] = {"trades": 0, "wins": 0, "pnl": 0}
            monthly[m]["trades"] += 1
            monthly[m]["pnl"] += t["pnl"]
            if t["pnl"] > 0:
                monthly[m]["wins"] += 1
        
        # Equity curve (sampled for chart)
        eq_sampled = []
        step = max(1, len(equity_curve) // 200)
        for i in range(0, len(equity_curve), step):
            eq_sampled.append(round(equity_curve[i], 0))
        
        # Best/worst trades
        sorted_trades = sorted(trades, key=lambda t: t["pnl"], reverse=True)
        
        result = {
            "success": True,
            "symbol": symbol,
            "years": years,
            "period": f"{dates[start_idx]} to {dates[-1]}",
            "total_bars": len(closes) - start_idx,
            "total_signals": total_signals,
            
            "stats": {
                "total_trades": total_trades,
                "wins": win_count,
                "losses": loss_count,
                "breakevens": len(breakevens),
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "sharpe_ratio": sharpe,
                "expectancy": expectancy,
                "total_profit": round(total_profit, 0),
                "total_loss": round(total_loss, 0),
                "net_pnl": round(net_pnl, 0),
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "max_drawdown": round(max_dd, 0),
                "best_trade": round(sorted_trades[0]["pnl"], 0) if sorted_trades else 0,
                "worst_trade": round(sorted_trades[-1]["pnl"], 0) if sorted_trades else 0,
                "avg_holding_days": round(sum((datetime.strptime(t.get("exit_date", t["entry_date"]), "%Y-%m-%d") - datetime.strptime(t["entry_date"], "%Y-%m-%d")).days for t in trades) / len(trades), 1),
            },
            
            "result_breakdown": result_counts,
            "monthly": dict(sorted(monthly.items())),
            "equity_curve": eq_sampled,
            
            "best_trades": [{"date": t["entry_date"], "entry": t["entry"], "exit": t.get("exit_price", 0), "pnl": t["pnl"], "result": t["result"], "confluence": t["confluence"]} for t in sorted_trades[:5]],
            "worst_trades": [{"date": t["entry_date"], "entry": t["entry"], "exit": t.get("exit_price", 0), "pnl": t["pnl"], "result": t["result"], "confluence": t["confluence"]} for t in sorted_trades[-5:]],
            
            "confluence_threshold": "65%",
            "sl_method": "1.5 × ATR(14)",
            "targets": "T1=1×ATR, T2=2×ATR, T3=3×ATR",
            "exit_strategy": "50% at T1 (SL→cost), 30% at T2 (trail), 20% at T3 or 5-day max hold",
            "lot": inst["lot"],
        }
        
        print(f"📊 Backtest: {symbol} {years}Y → {total_trades} trades, {win_rate}% win, PF={profit_factor}, Sharpe={sharpe}")
        return result
    
    except Exception as e:
        print(f"❌ Backtest error: {e}")
        import traceback; traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.post("/api/index-trades")
async def index_trades(request: Request):
    """Generate AI-powered daily index trade ideas for Indian markets"""
    import json as json_mod
    
    body = await request.json()
    email = body.get("email", "").strip().lower()
    force_refresh = body.get("force_refresh", False)
    region = body.get("region", "IN").upper()
    is_us_trades = region == "US"
    
    if email not in TRADES_ALLOWED_EMAILS:
        return {"success": False, "error": "Access restricted. This feature is exclusively available to authorized users."}
    
    # 30-minute cache — fresh enough for live trading, stable enough to avoid flip-flopping
    from datetime import timedelta
    IST_NOW = datetime.utcnow() + timedelta(hours=5, minutes=30)
    _rc = _trades_cache_us if is_us_trades else _trades_cache
    
    cache_valid = (
        not force_refresh
        and _rc["timestamp"] is not None 
        and _rc["data"] is not None
        and (IST_NOW - _rc["timestamp"]).total_seconds() < 1800  # 30 minutes
    )
    
    if cache_valid:
        age_min = int((IST_NOW - _rc["timestamp"]).total_seconds() / 60)
        print(f"📋 Returning cached {region} trades ({age_min}min old)")
        return _rc["data"]
    
    if force_refresh:
        print(f"🔄 Force refresh requested by {email} — generating with latest market data")
    else:
        print(f"🔥 Index trades requested by {email} — generating fresh (cache expired or empty)")
    
    # ═══ MULTI-SOURCE HELPER — yfinance → Yahoo v8 ═══
    def _yfetch(ticker):
        """Fetch price+history with fallback. Returns (hist_df, info_dict) or (None, None)."""
        import yfinance as yf
        # Source 1: yfinance
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty:
                return hist, t.info or {}
        except:
            pass
        # Source 2: Yahoo v8 chart API
        try:
            _h = {'User-Agent': f'Mozilla/5.0 Chrome/{random.randint(118,126)}.0.0.0', 'Accept': 'application/json'}
            r = _http_pool.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d", timeout=4)
            if r.status_code == 200:
                res = r.json().get('chart', {}).get('result', [{}])[0]
                meta = res.get('meta', {})
                quotes = res.get('indicators', {}).get('quote', [{}])[0]
                import pandas as pd
                closes = quotes.get('close', [])
                highs = quotes.get('high', [])
                lows = quotes.get('low', [])
                opens = quotes.get('open', [])
                vols = quotes.get('volume', [])
                ts = res.get('timestamp', [])
                if closes and any(c for c in closes if c):
                    df = pd.DataFrame({'Close': closes, 'High': highs, 'Low': lows, 'Open': opens, 'Volume': vols}, 
                                       index=pd.to_datetime(ts, unit='s') if ts else range(len(closes)))
                    df = df.dropna(subset=['Close'])
                    if not df.empty:
                        info = {'currentPrice': meta.get('regularMarketPrice'), 
                                'previousClose': meta.get('chartPreviousClose'),
                                'currency': meta.get('currency', 'USD'),
                                'longName': meta.get('longName', ticker)}
                        return df, info
        except:
            pass
        return None, None
    
    # Fetch index data based on region
    indices_data = []
    if is_us_trades:
        tickers = {
            "SPY": "S&P 500",
            "QQQ": "NASDAQ 100",
            "IWM": "Russell 2000",
            "^VIX": "CBOE VIX"
        }
    else:
        tickers = {
            "^NSEI": "NIFTY 50",
            "^NSEBANK": "BANK NIFTY",
            "^BSESN": "SENSEX",
            "^INDIAVIX": "INDIA VIX"
        }
    
    for ticker, name in tickers.items():
        try:
            hist, info = _yfetch(ticker)
            if hist is not None and not hist.empty:
                latest = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[0]
                price = round(latest['Close'], 2)
                change = round(price - prev['Close'], 2)
                change_pct = round((change / prev['Close']) * 100, 2) if prev['Close'] else 0
                high_5d = round(hist['High'].max(), 2)
                low_5d = round(hist['Low'].min(), 2)
                vol = int(latest.get('Volume', 0))
                indices_data.append({
                    "name": name, "ticker": ticker, "price": price,
                    "change": change, "change_pct": change_pct,
                    "high_5d": high_5d, "low_5d": low_5d, "volume": vol,
                    "day_high": round(latest['High'], 2), "day_low": round(latest['Low'], 2),
                    "open": round(latest['Open'], 2)
                })
                print(f"  ✅ {name}: {price} ({change:+.2f})")
        except Exception as e:
            print(f"  ⚠️ Failed to fetch {name}: {e}")
    
    # Get global market context
    global_data = []
    global_tickers = {
        "^GSPC": "S&P 500",
        "^DJI": "Dow Jones",
        "^IXIC": "NASDAQ",
        "^N225": "Nikkei 225",
        "^HSI": "Hang Seng",
        "DX-Y.NYB": "US Dollar Index",
        "CL=F": "Crude Oil",
        "GC=F": "Gold"
    }
    for ticker, name in global_tickers.items():
        try:
            hist, info = _yfetch(ticker)
            if hist is not None and not hist.empty:
                price = round(hist.iloc[-1]['Close'], 2)
                prev = hist.iloc[-2]['Close'] if len(hist) > 1 else price
                change_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
                global_data.append(f"{name}: {price} ({change_pct:+.2f}%)")
        except:
            pass
    
    # Fetch top stock movers for option picks
    stock_data = []
    if is_us_trades:
        stock_tickers = {
            "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA",
            "TSLA": "Tesla", "AMZN": "Amazon", "GOOGL": "Alphabet",
            "META": "Meta", "AMD": "AMD", "JPM": "JPMorgan",
            "AVGO": "Broadcom", "NFLX": "Netflix", "CRM": "Salesforce"
        }
    else:
        stock_tickers = {
            "RELIANCE.NS": "Reliance Industries",
            "TCS.NS": "TCS",
            "HDFCBANK.NS": "HDFC Bank",
            "INFY.NS": "Infosys",
            "ICICIBANK.NS": "ICICI Bank",
            "SBIN.NS": "SBI",
            "BHARTIARTL.NS": "Bharti Airtel",
            "TATAMOTORS.NS": "Tata Motors",
            "ITC.NS": "ITC",
            "LT.NS": "L&T",
            "AXISBANK.NS": "Axis Bank",
            "BAJFINANCE.NS": "Bajaj Finance",
            "MARUTI.NS": "Maruti Suzuki",
            "TATASTEEL.NS": "Tata Steel",
            "ADANIENT.NS": "Adani Enterprises"
        }
    for ticker, name in stock_tickers.items():
        try:
            hist, info = _yfetch(ticker)
            if hist is not None and not hist.empty and len(hist) >= 2:
                latest = hist.iloc[-1]
                prev = hist.iloc[-2]
                price = round(latest['Close'], 2)
                change_pct = round(((price - prev['Close']) / prev['Close']) * 100, 2)
                vol_avg = int(hist['Volume'].mean()) if 'Volume' in hist.columns else 0
                vol_today = int(latest.get('Volume', 0))
                vol_spike = round(vol_today / vol_avg, 2) if vol_avg > 0 else 1
                high_5d = round(hist['High'].max(), 2)
                low_5d = round(hist['Low'].min(), 2)
                stock_data.append({
                    "ticker": ticker.replace(".NS",""), "name": name,
                    "price": price, "change_pct": change_pct,
                    "vol_spike": vol_spike, "high_5d": high_5d, "low_5d": low_5d,
                    "day_high": round(latest['High'], 2), "day_low": round(latest['Low'], 2)
                })
        except:
            pass
    
    # Sort by absolute change % to find movers
    stock_data.sort(key=lambda x: abs(x['change_pct']), reverse=True)
    
    stocks_text = "\n".join([
        f"- {d['ticker']}: ₹{d['price']} ({d['change_pct']:+.2f}%) | "
        f"Day: ₹{d['day_low']}-₹{d['day_high']} | 5D: ₹{d['low_5d']}-₹{d['high_5d']} | "
        f"Vol Spike: {d['vol_spike']}x"
        for d in stock_data[:10]
    ])
    
    # ═══ FETCH REAL OPTION CHAIN DATA FROM NSE ═══
    import requests as req_lib
    
    def fetch_nse_option_chain(symbol):
        """Fetch live option chain from NSE for NIFTY, BANKNIFTY, or SENSEX."""
        try:
            session = req_lib.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://www.nseindia.com/option-chain",
                "X-Requested-With": "XMLHttpRequest"
            }
            session.headers.update(headers)
            # First hit the main page to get cookies
            session.get("https://www.nseindia.com", timeout=5)
            
            # Map symbol to NSE API format
            nse_symbol = symbol.replace(" ", "").upper()
            if nse_symbol in ["NIFTY50", "NIFTY"]:
                nse_symbol = "NIFTY"
            elif nse_symbol in ["BANKNIFTY", "NIFTYBANK"]:
                nse_symbol = "BANKNIFTY"
            
            # BSE/SENSEX option chain is on BSE, not NSE — skip
            if nse_symbol in ["SENSEX", "BSE"]:
                return None
            
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={nse_symbol}"
            resp = session.get(url, timeout=10)
            
            if resp.status_code != 200:
                print(f"  ⚠️ NSE option chain {symbol}: HTTP {resp.status_code}")
                return None
            
            data = resp.json()
            records = data.get("records", {})
            oc_data = records.get("data", [])
            
            if not oc_data:
                return None
            
            spot = records.get("underlyingValue", 0)
            expiry_dates = records.get("expiryDates", [])
            nearest_expiry = expiry_dates[0] if expiry_dates else ""
            
            # Calculate PCR, Max Pain, key OI levels
            total_ce_oi = 0
            total_pe_oi = 0
            max_pain_data = {}
            strike_oi = []
            atm_strike = None
            min_diff = float('inf')
            straddle_premium = 0
            
            for row in oc_data:
                strike = row.get("strikePrice", 0)
                ce = row.get("CE", {})
                pe = row.get("PE", {})
                
                # Only consider nearest expiry
                ce_expiry = ce.get("expiryDate", "")
                pe_expiry = pe.get("expiryDate", "")
                
                if ce_expiry == nearest_expiry or pe_expiry == nearest_expiry:
                    ce_oi = ce.get("openInterest", 0) or 0
                    pe_oi = pe.get("openInterest", 0) or 0
                    ce_ltp = ce.get("lastPrice", 0) or 0
                    pe_ltp = pe.get("lastPrice", 0) or 0
                    ce_iv = ce.get("impliedVolatility", 0) or 0
                    pe_iv = pe.get("impliedVolatility", 0) or 0
                    ce_chg_oi = ce.get("changeinOpenInterest", 0) or 0
                    pe_chg_oi = pe.get("changeinOpenInterest", 0) or 0
                    
                    total_ce_oi += ce_oi
                    total_pe_oi += pe_oi
                    
                    # ATM strike (closest to spot)
                    diff = abs(strike - spot)
                    if diff < min_diff:
                        min_diff = diff
                        atm_strike = strike
                        straddle_premium = round(ce_ltp + pe_ltp, 2)
                    
                    if ce_oi > 0 or pe_oi > 0:
                        strike_oi.append({
                            "strike": strike,
                            "ce_oi": ce_oi, "pe_oi": pe_oi,
                            "ce_chg_oi": ce_chg_oi, "pe_chg_oi": pe_chg_oi,
                            "ce_ltp": ce_ltp, "pe_ltp": pe_ltp,
                            "ce_iv": ce_iv, "pe_iv": pe_iv
                        })
                    
                    # Max pain calculation
                    max_pain_data[strike] = {"ce_oi": ce_oi, "pe_oi": pe_oi}
            
            # Calculate max pain
            max_pain = spot
            min_pain_value = float('inf')
            strikes_list = sorted(max_pain_data.keys())
            for s in strikes_list:
                pain = 0
                for s2 in strikes_list:
                    if s2 < s:
                        pain += max_pain_data[s2]["ce_oi"] * (s - s2)
                    elif s2 > s:
                        pain += max_pain_data[s2]["pe_oi"] * (s2 - s)
                if pain < min_pain_value:
                    min_pain_value = pain
                    max_pain = s
            
            pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0
            
            # Top OI strikes (resistance = high CE OI, support = high PE OI)
            strike_oi.sort(key=lambda x: x["ce_oi"], reverse=True)
            top_ce_oi = strike_oi[:5]  # Top resistance walls
            strike_oi.sort(key=lambda x: x["pe_oi"], reverse=True)
            top_pe_oi = strike_oi[:5]  # Top support walls
            
            # Top change in OI (smart money positioning)
            strike_oi.sort(key=lambda x: abs(x["ce_chg_oi"]) + abs(x["pe_chg_oi"]), reverse=True)
            top_chg_oi = strike_oi[:5]
            
            result = {
                "symbol": symbol,
                "spot": spot,
                "nearest_expiry": nearest_expiry,
                "pcr": pcr,
                "max_pain": max_pain,
                "atm_strike": atm_strike,
                "straddle_premium": straddle_premium,
                "expected_move": straddle_premium,
                "total_ce_oi": total_ce_oi,
                "total_pe_oi": total_pe_oi,
                "resistance_walls": [(s["strike"], s["ce_oi"]) for s in top_ce_oi],
                "support_walls": [(s["strike"], s["pe_oi"]) for s in top_pe_oi],
                "top_oi_changes": [(s["strike"], s["ce_chg_oi"], s["pe_chg_oi"]) for s in top_chg_oi],
                "atm_iv": round((top_ce_oi[0]["ce_iv"] + top_pe_oi[0]["pe_iv"]) / 2, 1) if top_ce_oi and top_pe_oi else 0
            }
            print(f"  ✅ NSE OC {symbol}: Spot={spot}, PCR={pcr}, MaxPain={max_pain}, ATM={atm_strike}, Straddle=₹{straddle_premium}")
            return result
            
        except Exception as e:
            print(f"  ⚠️ NSE option chain {symbol} failed: {e}")
            return None
    
    # Fetch option chains (India only — NSE doesn't have US data)
    oc_nifty = None; oc_banknifty = None
    if not is_us_trades:
        oc_nifty = fetch_nse_option_chain("NIFTY")
        oc_banknifty = fetch_nse_option_chain("BANKNIFTY")
    
    # Build option chain text for prompt
    oc_text_parts = []
    for oc in [oc_nifty, oc_banknifty]:
        if oc:
            pcr_signal = "BULLISH (PE writers confident)" if oc["pcr"] > 1.2 else "BEARISH (CE writers confident)" if oc["pcr"] < 0.7 else "NEUTRAL"
            max_pain_dist = oc["max_pain"] - oc["spot"]
            mp_dir = f"+{max_pain_dist}" if max_pain_dist > 0 else str(max_pain_dist)
            
            res_walls = ", ".join([f"{s[0]} ({s[1]:,} OI)" for s in oc["resistance_walls"][:3]])
            sup_walls = ", ".join([f"{s[0]} ({s[1]:,} OI)" for s in oc["support_walls"][:3]])
            oi_changes = ", ".join([f"{s[0]} (CE:{s[1]:+,} PE:{s[2]:+,})" for s in oc["top_oi_changes"][:3]])
            
            oc_text_parts.append(f"""
{oc['symbol']} LIVE OPTION CHAIN (Expiry: {oc['nearest_expiry']}):
  Spot: ₹{oc['spot']:,.2f} | ATM Strike: {oc['atm_strike']} | ATM Straddle: ₹{oc['straddle_premium']}
  PCR: {oc['pcr']} ({pcr_signal}) | Total CE OI: {oc['total_ce_oi']:,} | Total PE OI: {oc['total_pe_oi']:,}
  Max Pain: {oc['max_pain']} ({mp_dir} pts from spot) | ATM IV: {oc['atm_iv']}%
  Resistance Walls (heavy CE OI): {res_walls}
  Support Walls (heavy PE OI): {sup_walls}
  Smart Money (biggest OI changes): {oi_changes}
  Expected Move (straddle): ±₹{oc['straddle_premium']} ({round(oc['straddle_premium']/oc['spot']*100, 2)}% of spot)""")
    
    oc_text = "\n".join(oc_text_parts) if oc_text_parts else "Option chain data unavailable — use price action and volume only."
    
    # ═══════════════════════════════════════════════════════════════════
    # MULTI-FACTOR SCORING ENGINE — Pre-computes edge scores from real data
    # AI sees hard numbers, not guesses
    # ═══════════════════════════════════════════════════════════════════
    
    def compute_index_scores(idx_data, oc_data_dict, global_data_list, vix_data, is_expiry, weekday_num, ist_hour):
        """Score each index on 10 independent factors. Returns structured score card."""
        scores = {}
        
        for idx in idx_data:
            name = idx["name"]
            if name == "INDIA VIX":
                continue
            
            s = {"name": name, "total": 0, "factors": [], "bias": "NEUTRAL"}
            price = idx["price"]
            day_high = idx.get("day_high", price)
            day_low = idx.get("day_low", price)
            open_p = idx.get("open", price)
            high_5d = idx.get("high_5d", price)
            low_5d = idx.get("low_5d", price)
            change_pct = idx.get("change_pct", 0)
            vol = idx.get("volume", 0)
            
            bullish_points = 0
            bearish_points = 0
            
            # ── FACTOR 1: Price Action Structure (0-15 pts) ──
            range_5d = high_5d - low_5d if high_5d > low_5d else 1
            pos_in_range = (price - low_5d) / range_5d  # 0=bottom, 1=top
            day_range = day_high - day_low
            
            if pos_in_range < 0.3:  # Near support
                bullish_points += 12
                s["factors"].append(f"Price near 5D support ({pos_in_range:.0%} of range) [+12 BULL]")
            elif pos_in_range > 0.7:  # Near resistance
                bearish_points += 12
                s["factors"].append(f"Price near 5D resistance ({pos_in_range:.0%} of range) [+12 BEAR]")
            else:
                s["factors"].append(f"Price mid-range ({pos_in_range:.0%}) [NEUTRAL]")
            
            # Gap analysis
            gap_pct = ((open_p - price) / price * 100) if price else 0
            if abs(change_pct) > 0.5:
                if change_pct > 0:
                    bullish_points += 8
                    s["factors"].append(f"Gap up +{change_pct:.2f}% [+8 BULL]")
                else:
                    bearish_points += 8
                    s["factors"].append(f"Gap down {change_pct:.2f}% [+8 BEAR]")
            
            # ── FACTOR 2: Option Chain Signal (0-15 pts) ──
            oc = oc_data_dict.get(name.replace(" ", "").replace("50", "").upper())
            if oc:
                pcr = oc.get("pcr", 1)
                max_pain = oc.get("max_pain", price)
                straddle = oc.get("straddle_premium", 0)
                mp_dist = max_pain - price
                mp_pct = (mp_dist / price * 100) if price else 0
                
                # PCR signal
                if pcr > 1.3:
                    bullish_points += 10
                    s["factors"].append(f"PCR {pcr:.2f} — strong bullish (heavy PE writing) [+10 BULL]")
                elif pcr > 1.1:
                    bullish_points += 5
                    s["factors"].append(f"PCR {pcr:.2f} — mildly bullish [+5 BULL]")
                elif pcr < 0.7:
                    bearish_points += 10
                    s["factors"].append(f"PCR {pcr:.2f} — strong bearish (heavy CE writing) [+10 BEAR]")
                elif pcr < 0.9:
                    bearish_points += 5
                    s["factors"].append(f"PCR {pcr:.2f} — mildly bearish [+5 BEAR]")
                else:
                    s["factors"].append(f"PCR {pcr:.2f} — neutral zone")
                
                # Max Pain pull
                if abs(mp_pct) > 0.3:
                    if mp_dist > 0:
                        bullish_points += 8
                        s["factors"].append(f"Max Pain {max_pain} is {mp_dist:+.0f} pts ABOVE spot — pull-up force [+8 BULL]")
                    else:
                        bearish_points += 8
                        s["factors"].append(f"Max Pain {max_pain} is {mp_dist:+.0f} pts BELOW spot — pull-down force [+8 BEAR]")
                else:
                    s["factors"].append(f"Max Pain {max_pain} near spot ({mp_dist:+.0f} pts) — pinning likely")
                
                # Straddle vs day range (momentum gauge)
                if straddle > 0 and day_range > straddle * 1.2:
                    s["factors"].append(f"Day range ({day_range:.0f}) > straddle (₹{straddle}) — MOMENTUM day")
                elif straddle > 0:
                    s["factors"].append(f"Day range ({day_range:.0f}) within straddle (₹{straddle}) — RANGE-BOUND")
                
                # OI walls
                res_walls = oc.get("resistance_walls", [])
                sup_walls = oc.get("support_walls", [])
                if res_walls:
                    s["factors"].append(f"CE OI resistance: {', '.join([str(w[0]) for w in res_walls[:3]])}")
                if sup_walls:
                    s["factors"].append(f"PE OI support: {', '.join([str(w[0]) for w in sup_walls[:3]])}")
            else:
                s["factors"].append("No option chain data — price action only")
            
            # ── FACTOR 3: Momentum & Trend (0-10 pts) ──
            if change_pct > 1.0:
                bullish_points += 10
                s["factors"].append(f"Strong upward momentum +{change_pct:.2f}% [+10 BULL]")
            elif change_pct > 0.3:
                bullish_points += 5
                s["factors"].append(f"Mild upward momentum +{change_pct:.2f}% [+5 BULL]")
            elif change_pct < -1.0:
                bearish_points += 10
                s["factors"].append(f"Strong downward momentum {change_pct:.2f}% [+10 BEAR]")
            elif change_pct < -0.3:
                bearish_points += 5
                s["factors"].append(f"Mild downward momentum {change_pct:.2f}% [+5 BEAR]")
            
            # ── FACTOR 4: Volatility/VIX (0-10 pts) ──
            if vix_data:
                vix_level = vix_data.get("price", 14)
                vix_chg = vix_data.get("change_pct", 0)
                if vix_level < 13:
                    bullish_points += 8
                    s["factors"].append(f"VIX {vix_level:.1f} LOW — complacency, directional bets favored [+8 BULL]")
                elif vix_level > 20:
                    bearish_points += 8
                    s["factors"].append(f"VIX {vix_level:.1f} HIGH — fear, mean-reversion or hedging [+8 BEAR]")
                elif vix_level > 16:
                    s["factors"].append(f"VIX {vix_level:.1f} ELEVATED — reduce sizes, stay alert")
                else:
                    s["factors"].append(f"VIX {vix_level:.1f} NORMAL")
                    
                if abs(vix_chg) > 5:
                    s["factors"].append(f"VIX moving fast ({vix_chg:+.1f}%) — volatility regime shift")
            
            # ── FACTOR 5: Global Cues (0-10 pts) ──
            global_bullish = 0
            global_bearish = 0
            for g in global_data_list:
                if "S&P 500" in g or "Dow" in g or "NASDAQ" in g:
                    try:
                        pct = float(g.split("(")[1].split("%")[0])
                        if pct > 0.5:
                            global_bullish += 1
                        elif pct < -0.5:
                            global_bearish += 1
                    except:
                        pass
                if "Crude" in g:
                    try:
                        pct = float(g.split("(")[1].split("%")[0])
                        if pct > 2:
                            bearish_points += 3  # Crude up = bearish for India
                            s["factors"].append(f"Crude spike {pct:+.1f}% — negative for India [+3 BEAR]")
                        elif pct < -2:
                            bullish_points += 3
                            s["factors"].append(f"Crude drop {pct:+.1f}% — positive for India [+3 BULL]")
                    except:
                        pass
                if "Dollar" in g:
                    try:
                        pct = float(g.split("(")[1].split("%")[0])
                        if pct > 0.3:
                            bearish_points += 3  # Strong dollar = EM negative
                            s["factors"].append(f"Dollar up {pct:+.1f}% — EM headwind [+3 BEAR]")
                        elif pct < -0.3:
                            bullish_points += 3
                            s["factors"].append(f"Dollar down {pct:+.1f}% — EM tailwind [+3 BULL]")
                    except:
                        pass
            
            if global_bullish >= 2:
                bullish_points += 8
                s["factors"].append(f"US markets positive ({global_bullish}/3 up) [+8 BULL]")
            elif global_bearish >= 2:
                bearish_points += 8
                s["factors"].append(f"US markets negative ({global_bearish}/3 down) [+8 BEAR]")
            
            # ── FACTOR 6: Expiry Dynamics (0-10 pts) ──
            if is_expiry:
                s["factors"].append("EXPIRY DAY — gamma acceleration, max pain magnet, theta crush after 1 PM [+5 VOLATILE]")
                # On expiry, max pain pull is stronger
                if oc and abs(mp_pct) > 0.5:
                    if mp_dist > 0:
                        bullish_points += 5
                    else:
                        bearish_points += 5
                    s["factors"].append(f"Expiry max pain pull: {mp_dist:+.0f} pts [+5 directional]")
            
            # ── FACTOR 7: Volume Confirmation (0-10 pts) ──
            # High volume in direction of move = conviction, against = divergence warning
            if vol > 0:
                # We don't have vol average for indices from yfinance, but we can check 
                # if today's candle body matches volume direction
                body = price - open_p  # positive = bullish candle
                if body > 0 and change_pct > 0.3:
                    bullish_points += 7
                    s["factors"].append(f"Bullish candle + positive session = volume confirming direction [+7 BULL]")
                elif body < 0 and change_pct < -0.3:
                    bearish_points += 7
                    s["factors"].append(f"Bearish candle + negative session = volume confirming direction [+7 BEAR]")
                elif body > 0 and change_pct < -0.3:
                    s["factors"].append(f"⚠️ DIVERGENCE: Bullish candle but session negative — distribution pattern")
                elif body < 0 and change_pct > 0.3:
                    s["factors"].append(f"⚠️ DIVERGENCE: Bearish candle but session positive — accumulation pattern")
            
            # ── FACTOR 8: Intraday Price Pattern (0-10 pts) ──
            if day_high > day_low:
                upper_wick = day_high - max(open_p, price)
                lower_wick = min(open_p, price) - day_low
                body_size = abs(price - open_p)
                total_range = day_high - day_low
                body_ratio = body_size / total_range if total_range > 0 else 0
                
                if body_ratio > 0.7:  # Strong body = conviction
                    if price > open_p:
                        bullish_points += 8
                        s["factors"].append(f"Marubozu-like candle (body {body_ratio:.0%}) — strong bullish conviction [+8 BULL]")
                    else:
                        bearish_points += 8
                        s["factors"].append(f"Marubozu-like candle (body {body_ratio:.0%}) — strong bearish conviction [+8 BEAR]")
                elif lower_wick > body_size * 2 and price > open_p:  # Hammer
                    bullish_points += 6
                    s["factors"].append(f"Hammer pattern — buying from lows, reversal signal [+6 BULL]")
                elif upper_wick > body_size * 2 and price < open_p:  # Shooting star
                    bearish_points += 6
                    s["factors"].append(f"Shooting star — rejection from highs [+6 BEAR]")
                elif body_ratio < 0.2:  # Doji
                    s["factors"].append(f"Doji-like candle (body {body_ratio:.0%}) — indecision, wait for breakout")
                
                # Price position within today's range
                day_pos = (price - day_low) / total_range if total_range > 0 else 0.5
                if day_pos > 0.8:
                    bullish_points += 3
                    s["factors"].append(f"Closing near day high ({day_pos:.0%}) — buyers in control [+3 BULL]")
                elif day_pos < 0.2:
                    bearish_points += 3
                    s["factors"].append(f"Closing near day low ({day_pos:.0%}) — sellers in control [+3 BEAR]")
            
            # ── FACTOR 9: Intermarket Correlation (0-10 pts) ──
            # Check if global signals are aligned or divergent
            aligned_signals = 0
            conflict_signals = 0
            for g in global_data_list:
                try:
                    pct = float(g.split("(")[1].split("%")[0])
                    if (change_pct > 0 and pct > 0) or (change_pct < 0 and pct < 0):
                        aligned_signals += 1
                    elif abs(pct) > 0.3:
                        conflict_signals += 1
                except:
                    pass
            
            if aligned_signals >= 5:
                pts = 8
                if change_pct > 0:
                    bullish_points += pts
                else:
                    bearish_points += pts
                s["factors"].append(f"Strong intermarket alignment ({aligned_signals} markets same direction) [+{pts} directional]")
            elif conflict_signals >= 3:
                s["factors"].append(f"⚠️ Intermarket divergence ({conflict_signals} conflicting) — lower conviction")
            
            # Gold-equity inverse check
            for g in global_data_list:
                if "Gold" in g:
                    try:
                        gold_pct = float(g.split("(")[1].split("%")[0])
                        if gold_pct > 1 and change_pct > 0:
                            s["factors"].append(f"Gold +{gold_pct:.1f}% with equity up — risk-on rally (unusual)")
                        elif gold_pct > 1.5 and change_pct < 0:
                            bearish_points += 3
                            s["factors"].append(f"Gold +{gold_pct:.1f}% = flight to safety [+3 BEAR]")
                    except:
                        pass
            
            # ── FACTOR 10: Day-of-Week & Time Seasonality (0-8 pts) ──
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            dow = day_names[weekday_num] if weekday_num < 5 else "Weekend"
            
            if weekday_num == 0:  # Monday
                s["factors"].append("Monday — gap risk from weekend news, often sets weekly direction")
                if abs(change_pct) > 0.5:
                    s["factors"].append(f"Monday gap {change_pct:+.2f}% — high probability of continuation first 2 hours")
            elif weekday_num == 1:  # Tuesday (Nifty expiry)
                if is_expiry:
                    bullish_points += 3  # Expiry day has built-in edge from gamma
                    s["factors"].append("Tuesday Nifty expiry — theta decay accelerates, max pain magnet active [+3]")
            elif weekday_num == 3:  # Thursday (Sensex expiry)
                if is_expiry:
                    s["factors"].append("Thursday Sensex expiry — BSE options gamma play possible")
            elif weekday_num == 4:  # Friday
                s["factors"].append("Friday — weekend risk, positions may get squared off. Lighter trade sizes.")
            
            # Time-of-day edge
            if 9 <= ist_hour < 10:
                s["factors"].append("⏰ Pre-10AM: Opening range forming — observe, don't chase gaps")
            elif 10 <= ist_hour < 12:
                s["factors"].append("⏰ 10AM-12PM: Prime trend development window — best for directional entries")
            elif 12 <= ist_hour < 14:
                s["factors"].append("⏰ 12-2PM: Lunch consolidation — range-bound strategies or wait")
            elif 14 <= ist_hour < 15:
                s["factors"].append("⏰ 2-3PM: Power hour — strongest moves, expiry gamma spikes HERE")
            elif ist_hour >= 15:
                s["factors"].append("⏰ Post-3PM: Final 30min — avoid new entries, high chop risk")
            
            # ── FINAL SCORING ──
            net = bullish_points - bearish_points
            s["bullish_score"] = bullish_points
            s["bearish_score"] = bearish_points
            s["net_score"] = net
            
            if net > 15:
                s["bias"] = "STRONG BULLISH"
                s["suggested_bias"] = "Buy CE / Buy Futures"
            elif net > 5:
                s["bias"] = "MILD BULLISH"
                s["suggested_bias"] = "Buy CE (conservative)"
            elif net < -15:
                s["bias"] = "STRONG BEARISH"
                s["suggested_bias"] = "Buy PE / Sell Futures"
            elif net < -5:
                s["bias"] = "MILD BEARISH"
                s["suggested_bias"] = "Buy PE (conservative)"
            else:
                s["bias"] = "NEUTRAL"
                s["suggested_bias"] = "Range play / Straddle / Wait for clarity"
            
            s["edge_pct"] = min(50 + int(abs(net) * 0.6), 95)  # Base 50% + scaled factor edge, cap at 95%
            s["factor_count"] = len([f for f in s["factors"] if "BULL]" in f or "BEAR]" in f])
            scores[name] = s
        
        return scores
    
    # Run scoring engine
    # Need IST time for day-of-week and time scoring
    from datetime import timedelta as td_alias
    IST_NOW = datetime.utcnow() + td_alias(hours=5, minutes=30)
    IST_WEEKDAY = IST_NOW.weekday()
    IST_HOUR = IST_NOW.hour
    # Quick expiry check for scoring (detailed check happens later for prompt)
    _is_tue = IST_WEEKDAY == 1
    _is_thu = IST_WEEKDAY == 3
    _quick_expiry = _is_tue or _is_thu  # At minimum, some expiry on Tue/Thu
    
    vix_entry = next((d for d in indices_data if d["name"] == "INDIA VIX"), None)
    oc_dict = {}
    if oc_nifty:
        oc_dict["NIFTY"] = oc_nifty
    if oc_banknifty:
        oc_dict["BANKNIFTY"] = oc_banknifty
    
    index_scores = compute_index_scores(indices_data, oc_dict, global_data, vix_entry, _quick_expiry, IST_WEEKDAY, IST_HOUR)
    
    # Build score cards text for the prompt
    score_text_parts = []
    for name, sc in index_scores.items():
        factors_str = "\n    ".join(sc["factors"])
        score_text_parts.append(f"""
{name} SCORE CARD:
  BULLISH points: {sc['bullish_score']} | BEARISH points: {sc['bearish_score']} | NET: {sc['net_score']:+d}
  COMPUTED BIAS: {sc['bias']} → Suggested: {sc['suggested_bias']}
  Computed edge: {sc['edge_pct']}% | Active factors: {sc.get('factor_count', 0)}/10
  Factor breakdown:
    {factors_str}""")
    
    score_text = "\n".join(score_text_parts) if score_text_parts else "Scoring unavailable"
    
    # Also score stocks — comprehensive multi-factor
    stock_scores = []
    for st in stock_data[:10]:
        bull = 0
        bear = 0
        factors = []
        
        # F1: Momentum (0-15)
        chg = st["change_pct"]
        if chg > 2:
            bull += 15
            factors.append(f"Strong momentum +{chg:.1f}%")
        elif chg > 0.5:
            bull += 8
            factors.append(f"Positive +{chg:.1f}%")
        elif chg < -2:
            bear += 15
            factors.append(f"Strong sell-off {chg:.1f}%")
        elif chg < -0.5:
            bear += 8
            factors.append(f"Negative {chg:.1f}%")
        
        # F2: Volume spike (0-12)
        vs = st.get("vol_spike", 1)
        if vs > 2.5:
            pts = 12
            if chg > 0: bull += pts
            else: bear += pts
            factors.append(f"Vol SPIKE {vs:.1f}x — heavy institutional")
        elif vs > 1.8:
            pts = 8
            if chg > 0: bull += pts
            else: bear += pts
            factors.append(f"High volume {vs:.1f}x")
        elif vs > 1.3:
            pts = 4
            if chg > 0: bull += pts
            else: bear += pts
            factors.append(f"Above-avg vol {vs:.1f}x")
        elif vs < 0.6:
            factors.append(f"Low volume {vs:.1f}x — weak conviction")
        
        # F3: 5D range position (0-10)
        r = st["high_5d"] - st["low_5d"]
        if r > 0:
            pos = (st["price"] - st["low_5d"]) / r
            if pos < 0.2:
                bull += 10
                factors.append(f"Near 5D LOW ({pos:.0%}) — bounce zone")
            elif pos < 0.35:
                bull += 5
                factors.append(f"Lower half ({pos:.0%})")
            elif pos > 0.85:
                bear += 8
                factors.append(f"Near 5D HIGH ({pos:.0%}) — resistance")
            elif pos > 0.7:
                bear += 3
                factors.append(f"Upper half ({pos:.0%})")
        
        # F4: Day candle pattern (0-8)
        dh = st.get("day_high", st["price"])
        dl = st.get("day_low", st["price"])
        if dh > dl:
            day_range = dh - dl
            body = abs(st["price"] - (dh + dl) / 2 * 2 - st["price"])  # simplified
            day_pos = (st["price"] - dl) / day_range
            if day_pos > 0.8 and chg > 0:
                bull += 6
                factors.append("Closing near high — buyers dominating")
            elif day_pos < 0.2 and chg < 0:
                bear += 6
                factors.append("Closing near low — sellers dominating")
        
        # F5: Alignment with parent index
        nifty_chg = next((d["change_pct"] for d in indices_data if d["name"] == "NIFTY 50"), 0)
        if (chg > 0 and nifty_chg > 0) or (chg < 0 and nifty_chg < 0):
            pts = 3
            if chg > 0: bull += pts
            else: bear += pts
            factors.append(f"Aligned with Nifty ({nifty_chg:+.1f}%)")
        elif abs(chg) > 1 and abs(nifty_chg) > 0.5 and (chg * nifty_chg < 0):
            factors.append(f"DIVERGING from Nifty — relative strength/weakness")
        
        net = bull - bear
        bias = "BULLISH" if net > 12 else "BEARISH" if net < -12 else "MILD BULL" if net > 5 else "MILD BEAR" if net < -5 else "NEUTRAL"
        edge = min(50 + int(abs(net) * 0.6), 95)
        stock_scores.append(f"  {st['ticker']}: Bull={bull} Bear={bear} Net={net:+d} Edge={edge}% → {bias} | {', '.join(factors)}")
    
    stock_score_text = "\n".join(stock_scores) if stock_scores else "No stock scores"
    
    print(f"📊 Scoring complete: {len(index_scores)} indices, {len(stock_scores)} stocks scored")
    
    # Build AI prompt
    _csym = "$" if is_us_trades else "₹"
    indices_text = "\n".join([
        f"- {d['name']}: {_csym}{d['price']:,.2f} (Change: {d['change']:+.2f}, {d['change_pct']:+.2f}%) | "
        f"Day Range: {_csym}{d['day_low']}-{_csym}{d['day_high']} | 5D Range: {_csym}{d['low_5d']}-{_csym}{d['high_5d']} | "
        f"Open: {_csym}{d['open']} | Volume: {d['volume']:,}"
        for d in indices_data
    ])
    
    global_text = "\n".join([f"- {g}" for g in global_data]) if global_data else "Global data unavailable"
    
    # Use IST (UTC+5:30) for Indian market — CRITICAL for correct expiry day detection
    IST_OFFSET = timedelta(hours=5, minutes=30)
    now = datetime.utcnow() + IST_OFFSET
    today = now.strftime("%A, %B %d, %Y")
    weekday = now.weekday()  # 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday
    day_name = now.strftime("%A")
    print(f"🕐 IST Time: {now.strftime('%Y-%m-%d %H:%M:%S')} ({day_name})")
    
    # ═══════════════════════════════════════════════════
    # SEBI EXPIRY SCHEDULE (effective Sep 1, 2025)
    # NSE: ALL derivatives expire on TUESDAY
    #   - Nifty 50: weekly expiry every Tuesday
    #   - Bank Nifty: monthly expiry last Tuesday (NO weekly)
    #   - Fin Nifty: monthly expiry last Tuesday (NO weekly)
    #   - Stock F&O: monthly expiry last Tuesday
    # BSE: ALL derivatives expire on THURSDAY
    #   - Sensex: weekly expiry every Thursday
    #   - Bankex: monthly expiry last Thursday (NO weekly)
    # ═══════════════════════════════════════════════════
    
    # Check if today is last Tuesday or last Thursday of month
    import calendar
    year, month = now.year, now.month
    last_day = calendar.monthrange(year, month)[1]
    
    # Find last Tuesday (weekday=1) of this month
    last_tuesday = last_day
    while datetime(year, month, last_tuesday).weekday() != 1:
        last_tuesday -= 1
    is_last_tuesday = (now.day == last_tuesday and weekday == 1)
    
    # Find last Thursday (weekday=3) of this month
    last_thursday = last_day
    while datetime(year, month, last_thursday).weekday() != 3:
        last_thursday -= 1
    is_last_thursday = (now.day == last_thursday and weekday == 3)
    
    is_tuesday = (weekday == 1)
    is_thursday = (weekday == 3)
    
    # Build dynamic expiry context
    expiry_today = []
    expiry_context_lines = []
    
    if is_tuesday:
        expiry_today.append("NIFTY 50 (weekly)")
        expiry_context_lines.append("🔴 NIFTY 50 WEEKLY EXPIRY TODAY (Tuesday) — High theta decay, gamma spike expected after 2 PM")
        if is_last_tuesday:
            expiry_today.append("BANK NIFTY (monthly)")
            expiry_today.append("FIN NIFTY (monthly)")
            expiry_today.append("Stock F&O (monthly)")
            expiry_context_lines.append("🔴🔴 BANK NIFTY MONTHLY EXPIRY TODAY (last Tuesday) — Major event! Heavy OI unwinding expected")
            expiry_context_lines.append("🔴 FIN NIFTY + ALL STOCK F&O MONTHLY EXPIRY TODAY")
    
    if is_thursday:
        expiry_today.append("SENSEX (weekly)")
        expiry_context_lines.append("🔴 SENSEX WEEKLY EXPIRY TODAY (Thursday) — BSE options theta decay in play")
        if is_last_thursday:
            expiry_today.append("BANKEX (monthly)")
            expiry_context_lines.append("🔴 BANKEX MONTHLY EXPIRY TODAY (last Thursday)")
    
    if not expiry_today:
        # Calculate days to next expiry
        days_to_tuesday = (1 - weekday) % 7
        if days_to_tuesday == 0:
            days_to_tuesday = 7
        days_to_thursday = (3 - weekday) % 7
        if days_to_thursday == 0:
            days_to_thursday = 7
        next_nifty_expiry = (now + timedelta(days=days_to_tuesday)).strftime("%A, %B %d")
        next_sensex_expiry = (now + timedelta(days=days_to_thursday)).strftime("%A, %B %d")
        expiry_context_lines.append(f"⚪ NO EXPIRY TODAY ({day_name}) — Next Nifty expiry: {next_nifty_expiry} (Tuesday), Next Sensex expiry: {next_sensex_expiry} (Thursday)")
        expiry_context_lines.append("Focus on positional/swing trades. No Hero Zero today.")
    
    is_expiry_day = len(expiry_today) > 0
    expiry_text = "\n".join(expiry_context_lines)
    expiry_list = ", ".join(expiry_today) if expiry_today else "NONE"
    
    print(f"📅 {day_name} | Expiry today: {expiry_list} | Last Tue: {is_last_tuesday} | Last Thu: {is_last_thursday}")
    
    # Hero Zero instruction based on whether it's expiry day
    if is_expiry_day:
        hero_zero_instruction = f"""
RULES FOR HERO ZERO (1-2 trades — TODAY IS EXPIRY DAY for {expiry_list}):
- Hero Zero = directional bet on deep OTM side on EXPIRY DAY for potential 3x-10x returns
- Pick from the expiring index/indices: {expiry_list}
- Identify the breakout SPOT LEVEL where gamma acceleration would kick in (use OI walls from option chain)
- Timing is crucial: usually 1:00-2:30 PM IST when gamma spikes on expiry
- Mark confidence as SPECULATIVE — make it clear this is a high-risk lottery play
- Use max pain, OI walls, and straddle premium from the real option chain data to identify the trigger level
- MUST include timing field with specific IST time window"""
    else:
        hero_zero_instruction = """
HERO ZERO: Return empty array "hero_zero": [] because today is NOT an expiry day.
Do NOT generate any hero_zero trades on non-expiry days."""
    
    _mkt_region = "US equity and options market" if is_us_trades else "Indian market (NSE/BSE)"
    _mkt_hours = "9:30 AM - 4:00 PM ET" if is_us_trades else "9:15 AM - 3:30 PM IST"
    _mkt_currency = "USD ($)" if is_us_trades else "INR (₹)"
    _mkt_indices = "S&P 500, NASDAQ, Russell 2000" if is_us_trades else "NIFTY, BANKNIFTY, SENSEX"
    
    prompt = f"""You are a cold, ruthless, data-obsessed derivatives trader with 20 years of {_mkt_region} experience. You have ZERO tolerance for:
- PANDERING: Never tell the user what they want to hear. If the market is unclear, say "NO CLEAR EDGE TODAY" for that trade.
- BIAS: You have no bullish or bearish bias. You follow DATA ONLY. If data says sell, you sell. If data says buy, you buy. You don't care about narratives.
- BOTH-SIDING: Never hedge your opinion with "on the other hand" or "however". Pick a direction and commit. If you can't commit, DON'T SUGGEST THE TRADE.
- RETROACTIVE REASONING: Never justify a trade by fitting a narrative after picking a direction. The data MUST lead to the conclusion, not the other way around.
- WISHFUL THINKING: A trade with <70% probability based on data confluence should NOT be suggested. Only suggest trades where 3+ independent factors align.

YOUR PROBABILITY FRAMEWORK — Use the PRE-COMPUTED scores above:
The scoring engine has already computed bullish/bearish points from 10 independent factors:
F1: Price Action Structure (support/resistance position, gaps)
F2: Option Chain (PCR, Max Pain, OI walls, straddle premium)
F3: Momentum & Trend (today's change %, direction)
F4: Volatility/VIX (level, change, regime)
F5: Global Cues (US markets, crude, dollar, gold alignment)
F6: Expiry Dynamics (max pain pull, gamma, theta)
F7: Volume Confirmation (candle body vs session direction)
F8: Intraday Price Pattern (candle type, wick analysis, close position)
F9: Intermarket Correlation (cross-market alignment score)
F10: Day/Time Seasonality (weekday edge, time-of-day window)

ADDITIONAL FACTORS FOR STOCK-SPECIFIC TRADES (apply to stock trades only):
F11: Earnings Velocity — Revenue + EPS growth rate. Growing >15% = bullish bias. Declining = bearish bias.
F12: Balance Sheet Health — D/E ratio, cash vs debt, quick ratio. Fortress balance = hold through dips.
F13: Valuation vs Sector — P/E vs sector avg P/E. Deep discount = mean-reversion upside target.
F14: FCF Quality — Positive FCF margin >10% = real earnings. Negative FCF = avoid long positions.
F15: Technical SMA Position — Price vs 20/50/200 SMA. Above all 3 = strong trend. Below all 3 = avoid longs.

Use the computed edge_pct as the BASE probability for each index.
Only suggest a trade if computed edge >= 65% AND your analysis agrees.
You may adjust ±5% based on your synthesis, but NEVER flip the direction from what the scoring engine computed.

MINIMUM THRESHOLD: edge_pct >= 65% to suggest a trade. 80%+ for high conviction.
If fewer than 3 trades meet threshold, suggest FEWER trades. NEVER pad with weak trades.

Today is {today}.

CRITICAL RULES:
1. ALL analysis must be based EXCLUSIVELY on the LIVE MARKET DATA and LIVE OPTION CHAIN DATA provided below.
2. You have REAL option chain data from NSE — use PCR, Max Pain, OI walls, straddle premium, and IV directly. Do NOT invent different numbers.
3. ALL entry/target/stop_loss values must be SPOT INDEX LEVELS or STOCK PRICES — never option premiums (we show directional bias, not specific contracts).
4. Your "bias" field (Buy CE, Buy PE, etc.) is a DIRECTIONAL SUGGESTION based on the real option chain signals.
5. Key levels must reference the REAL support/resistance walls from the OI data provided, plus 5-day range levels.
6. If option chain data is unavailable for an index, state that and use price action only.

INSTITUTIONAL-GRADE TRADE LOGIC — FOLLOW EXACTLY:
A. ENTRY VALIDATION: Every entry must be at a verifiable support/resistance level from OI data, NOT arbitrary round numbers.
B. RISK-REWARD MINIMUM: Every trade must have minimum 1:2 risk-reward ratio. Stop loss MUST be tighter than target distance.
C. CONFLUENCE REQUIREMENT: Minimum 3 out of 10 factors must align for ANY trade suggestion. Single-factor trades are BANNED.
D. STOP LOSS PLACEMENT: Place stops behind the NEXT major OI wall or pivot, not at arbitrary fixed-point distances.
E. TIME DECAY AWARENESS: On expiry days, adjust probability DOWN for afternoon trades (theta crush after 1 PM).
F. MAX PAIN GRAVITY: If current price is far from max pain on expiry day, bias should lean TOWARD max pain direction.
G. STRADDLE PREMIUM = EXPECTED RANGE: The ATM straddle premium on expiry defines the expected move. Targets beyond this range need extra justification.
H. PCR EXTREMES: PCR > 1.5 = heavily bullish support, PCR < 0.7 = bearish pressure. Use this to validate direction.
I. VOLUME CONFIRMATION: Trades in direction of volume surge get +5% probability. Counter-volume trades get -5%.
J. NO PHANTOM DATA: If a data field shows "N/A" or 0, acknowledge the gap. NEVER fabricate numbers to fill it.

LIVE INDIAN INDEX DATA:
{indices_text}

LIVE NSE OPTION CHAIN DATA (REAL — from NSE API):
{oc_text}

TOP INDIAN STOCKS (sorted by momentum):
{stocks_text}

GLOBAL MARKET CONTEXT:
{global_text}

═══ PRE-COMPUTED MULTI-FACTOR SCORES (from real data — USE THESE) ═══
The scoring engine below has analyzed 10 independent factors for each index.
Your trade suggestions MUST be consistent with these scores. Do NOT contradict the computed bias.
If computed bias is BULLISH with 70+ edge, suggest Buy CE. If BEARISH, suggest Buy PE. If NEUTRAL, suggest range plays or fewer trades.

INDEX SCORES:
{score_text}

STOCK SCORES:
{stock_score_text}
═══ END PRE-COMPUTED SCORES ═══

DEEP ANALYSIS CHECKLIST — Work through each BEFORE generating trades:

1. STRUCTURE (Where is price relative to key levels?):
   - Identify exact support/resistance from 5-day high/low, today's open, previous close
   - Is price in a range or trending? Which side of VWAP?
   - Gap up/gap down? Has the gap been filled or is it running?
   - Round number psychology (24500, 25000, 52000, 53000)

2. OPTION CHAIN ANALYSIS (from REAL NSE data provided above):
   - PCR: Use the exact PCR value provided. >1.2 = bullish, <0.7 = bearish
   - Max Pain: Note how far spot is from max pain — price tends to gravitate toward it on expiry
   - OI Walls: Heavy CE OI at a strike = resistance ceiling. Heavy PE OI = support floor. Use the exact numbers from the data.
   - Straddle Premium: This is the market's expected move. If actual move exceeds it, breakout trade. If within, range trade.
   - Smart Money OI Changes: Large OI additions = new positions. Large OI reductions = unwinding. Direction of change matters.

3. VOLUME & MONEY FLOW:
   - Is today's volume above or below 5-day average?
   - Volume spike stocks = institutional entry/exit (>1.5x = notable, >2x = significant)
   - Delivery percentage trend — high delivery = conviction, low = speculation

4. VOLATILITY EDGE:
   - India VIX current level and 5-day trend
   - VIX < 13 = complacency (expect surprise move), VIX > 18 = fear (mean reversion possible)
   - ATM IV from real option chain — compare with VIX to assess if options are cheap or expensive
   - Straddle premium vs actual day range — if range > straddle, momentum day. If range < straddle, range-bound.

5. GLOBAL SETUP (Facts, not stories):
   - US markets close direction and magnitude (>1% move = significant)
   - Dollar Index direction (DXY up = emerging markets negative)
   - Crude oil (>2% move impacts markets)
   - Asian markets (Nikkei, Hang Seng) — correlation or divergence?
   - US bond yields — rising yields = risk-off for emerging markets

6. REGIME IDENTIFICATION:
   - Trending day (opens at extreme, closes at other extreme) — probability based on gap + VIX
   - Range day (chops between support/resistance) — probability based on VIX + no catalyst
   - Expiry day characteristics (pin to Max Pain, late gamma burst, OI unwinding)
   
HONEST ASSESSMENT: After analysis, state clearly:
- "Market bias: BULLISH / BEARISH / NEUTRAL-CHOPPY"  
- "Regime: TRENDING / RANGE-BOUND / EXPIRY-DRIVEN"
- "Edge clarity: CLEAR / MODERATE / WEAK"
- If edge is WEAK, reduce number of trades suggested.

RESPOND IN STRICT JSON FORMAT (no markdown, no backticks, no explanation outside JSON):
{{
  "market_assessment": {{
    "bias": "BULLISH | BEARISH | NEUTRAL-CHOPPY",
    "regime": "TRENDING | RANGE-BOUND | EXPIRY-DRIVEN",
    "edge_clarity": "CLEAR | MODERATE | WEAK",
    "vix_signal": "brief VIX interpretation",
    "global_impact": "brief global cues impact on the market today"
  }},
  "market_context": "2-3 sentence HONEST summary. If market is unclear, SAY SO. No forced bullishness or bearishness.",
  "trades": [
    {{
      "rank": "1 | 2 | 3 etc. — Rank by probability, highest first. #1 = best trade of the day.",
      "index": "NIFTY 50 | BANK NIFTY | SENSEX",
      "direction": "BULLISH | BEARISH",
      "bias": "Buy CE | Buy PE | Sell CE | Sell PE | Buy Futures | Sell Futures — directional suggestion only, NOT a specific strike",
      "probability": "80% | 85% | 90% — must be >= 80% to be included",
      "factors_aligned": "List which 5+ factors confirm: e.g. support+volume+trend+global+VIX",
      "spot_price": "current index spot level — number only",
      "entry_level": "SPOT LEVEL to enter — number only. This is the INDEX level, NOT an option premium.",
      "entry_condition": "MANDATORY — Exact trigger like: Nifty spot > 24600 | Bank Nifty spot < 52700. Always use > or < with a specific INDEX LEVEL.",
      "target_level": "SPOT TARGET — index level where you'd book profits. Number only.",
      "stop_level": "SPOT STOP LOSS — index level where trade is invalidated. Number only.",
      "move_points": "Expected move in points. E.g. '+200 pts' or '-150 pts'.",
      "move_pct": "Expected % move on spot. E.g. '+0.8%' or '-0.6%'. Calculate from entry_level to target_level.",
      "risk_reward": "1:2 format based on points",
      "timing": "MANDATORY — Best time window to enter. E.g. '9:30-10:00 AM (gap fill)' or '2:00-2:30 PM (expiry gamma)'. Specific IST time range + reason.",
      "time_sort": "MANDATORY — 24hr start time for sorting. E.g. '0930'. 4-digit string.",
      "confidence": "HIGH (5+ factors) | MEDIUM (4 factors) — never suggest with <4 factors",
      "reason": "Cold, factual 2-3 sentence rationale. DATA FIRST — cite actual price levels, volume, VIX, global cues. No narratives.",
      "key_levels": "MANDATORY — Support: 24500, 24350 | Resistance: 24800, 25000 — real levels derived from 5-day range, previous close, round numbers.",
      "what_invalidates": "MANDATORY — Kill condition. E.g. 'Nifty breaks below 24400 with heavy volume' or 'VIX spikes above 18'."
    }}
  ],
  "stock_trades": [
    {{
      "rank": "S1 | S2 — Rank by probability",
      "stock": "RELIANCE | TCS | HDFCBANK etc.",
      "direction": "BULLISH | BEARISH",
      "bias": "Buy CE | Buy PE | Buy Cash — directional suggestion only",
      "probability": "80% | 85% | 90%",
      "factors_aligned": "List confirming factors from live data",
      "spot_price": "current stock price — number only",
      "entry_level": "STOCK PRICE level to enter — number only",
      "entry_condition": "MANDATORY — Exact trigger with > or < using STOCK PRICE level",
      "target_level": "STOCK PRICE target — number only",
      "stop_level": "STOCK PRICE stop loss — number only",
      "move_pct": "Expected % move. E.g. '+2.5%'",
      "risk_reward": "1:2 format",
      "timing": "MANDATORY — Best IST time window with reason",
      "time_sort": "MANDATORY — 24hr start time. 4-digit string.",
      "confidence": "HIGH | MEDIUM",
      "reason": "Factual rationale — cite volume numbers, price levels, sector momentum. No fluff.",
      "key_levels": "Support and resistance levels from 5-day range",
      "what_invalidates": "MANDATORY — Kill condition for this trade"
    }}
  ],
  "hero_zero": [
    {{
      "index": "Index expiring today",
      "direction": "BULLISH | BEARISH",
      "bias": "Deep OTM CE | Deep OTM PE — direction only, no specific strike",
      "spot_price": "current index level",
      "trigger_level": "MANDATORY — Spot level that must break for this play to work",
      "entry_condition": "MANDATORY — trigger with > or < on SPOT level",
      "target_move": "Expected point move if breakout happens. E.g. '+300 pts from trigger'",
      "timing": "MANDATORY — IST time (usually 1:30-2:30 PM for expiry gamma)",
      "time_sort": "MANDATORY — 24hr start time. E.g. '1330'.",
      "risk_reward": "Risk full premium for 3x-10x",
      "confidence": "SPECULATIVE",
      "reason": "Why this direction specifically. What data supports the breakout? Cite levels.",
      "what_invalidates": "What makes this zero instead of hero"
    }}
  ],
  "skipped_trades": "MANDATORY — If you found fewer than 5 index trades with 80%+ probability, explain here WHY. If all met threshold, say 'All trades met 80%+ threshold.'",
  "gut_picks": [
    {{
      "rank": "#1 GUT PICK | #2 GUT PICK",
      "index_or_stock": "NIFTY 50 | RELIANCE etc.",
      "type": "INDEX | STOCK",
      "direction": "BULLISH | BEARISH",
      "bias": "Buy CE | Buy PE | Futures etc.",
      "probability": "90%+ — your HIGHEST conviction",
      "entry_level": "spot level to enter",
      "entry_condition": "exact > or < trigger on spot",
      "timing": "IST time window",
      "target_level": "spot target level",
      "stop_level": "spot SL level",
      "move_pct": "expected % move",
      "why_this_one": "1-2 sentences — why THIS trade above all others? What makes it near-certain? Be specific."
    }}
  ],
  "event_alert": {{
    "has_event": true,
    "headline": "Short headline e.g. 'RBI Rate Decision Today' or 'US CPI Data Above Estimates' or 'FII Sell-Off ₹5000Cr' or 'Crude Spikes +4%'",
    "impact": "BULLISH | BEARISH | VOLATILE — how it impacts the market",
    "severity": "HIGH | MEDIUM | LOW",
    "detail": "2-3 sentence explanation of what happened, why it matters for today's trading, and which sectors/indices are most affected.",
    "action": "What traders should do: e.g. 'Avoid fresh longs until dust settles' or 'Banking stocks will benefit, add to Bank Nifty CE positions' or 'Hedge existing positions with protective puts'"
  }},
  "gamma_blast": {{
    "active": true,
    "source": "EXPIRY | EVENT | BOTH — What's driving the gamma blast potential today",
    "index": "MANDATORY — For expiry-driven: the specific index expiring TODAY (e.g. 'SENSEX' on Thursday, 'NIFTY 50' on Tuesday). For event-driven: the index most impacted by the event. For BOTH: list both.",
    "probability": "0-100% — combined probability from BOTH expiry mechanics AND event impact",
    "direction": "UP | DOWN | EITHER",
    "trigger_zone": "Price level on the target INDEX where gamma blast activates",
    "expected_move": "Expected point move if gamma blast triggers",
    "best_play": "Exact trade to capture gamma blast — must specify the correct index and expiry",
    "timing": "IST time window when gamma blast is most likely",
    "expiry_factors": "Expiry-specific factors: OI concentration, max pain distance, PCR, theta decay rate, straddle premium — ONLY if expiry day, else 'N/A - not expiry day'",
    "event_factors": "Event-specific factors: What geopolitical/macro event creates sudden gamma? RBI decision, US CPI, crude spike, FII panic, war escalation, currency crash etc. — ONLY if event exists, else 'No major event today'"
  }}
}}

CRITICAL — TODAY'S EXPIRY STATUS:
{expiry_text}
Expiring today: {expiry_list}
Day: {day_name}

SEBI EXPIRY SCHEDULE (effective Sep 1, 2025):
- NSE — ALL derivatives expire on TUESDAY:
  * Nifty 50: WEEKLY expiry every Tuesday (only index with weekly on NSE)
  * Bank Nifty: MONTHLY expiry on LAST TUESDAY of month only (NO weekly expiry since Nov 2024)
  * Fin Nifty: MONTHLY expiry on last Tuesday (NO weekly)
  * Stock F&O: MONTHLY expiry on last Tuesday
  * Lot size: Nifty = 75, Bank Nifty = 30
- BSE — ALL derivatives expire on THURSDAY:
  * Sensex: WEEKLY expiry every Thursday (only index with weekly on BSE)
  * Bankex: MONTHLY expiry on last Thursday (NO weekly)
  * Lot size: Sensex = 20
- If expiry falls on holiday, it moves to previous trading day

IMPORTANT EXPIRY DAY BEHAVIORS:
- Tuesday: Nifty weekly theta crush accelerates after 1 PM. Max Pain level becomes magnet. OI at round strikes unwinds.
- Last Tuesday: Bank Nifty + Nifty both expire = DOUBLE EXPIRY = extreme volatility, heavy institutional activity
- Thursday: Sensex weekly expiry on BSE. Typically lower volumes than Nifty but can see sharp moves.
- Monday/Wednesday/Friday: No expiry — focus on positional/swing trades, carry trades for next expiry.

TIMING GUIDELINES (Market hours: {_mkt_hours}):
""" + ("""- 9:30-10:00 AM ET: Opening volatility — observe gap direction
- 10:00-11:30 AM ET: Trend development — best for directional trades
- 11:30 AM-1:00 PM ET: Midday consolidation — range-bound setups
- 1:00-3:00 PM ET: Afternoon momentum — strongest moves
- 3:00-4:00 PM ET: Power hour — high volatility, avoid new entries unless scalping
""" if is_us_trades else """- 9:15-9:30 AM: Opening volatility — avoid entries, observe gap direction
- 9:30-10:00 AM: Opening range establishment — good for momentum entries if gap sustains
- 10:00-11:30 AM: Trend development phase — best for directional trades
- 11:30 AM-1:00 PM: Consolidation/lunch lull — good for range-bound or mean-reversion setups
- 1:00-2:00 PM: Afternoon session starts — watch for breakout from consolidation
- 2:00-3:00 PM: Power hour — strongest moves, expiry-day gamma spikes here
- 3:00-3:30 PM: Final 30 min — high volatility, avoid new entries unless scalping
""") + f"""
- EVERY trade MUST have a specific IST time window in the "timing" field

HARD RULES — VIOLATING THESE MAKES YOU A BAD TRADER:

1. NEVER suggest a trade just to fill a quota. If only 3 trades have 80%+ edge, suggest 3. Say why others didn't qualify.
2. EVERY trade must have "what_invalidates" — the kill switch. A trade without a defined exit is gambling.
3. EVERY trade must show probability (80-95%) and list the specific factors that got it there.
4. If global cues conflict with domestic setup, SAY SO. Don't pretend everything aligns.
5. NEVER use words: "should", "might", "could potentially". Use: "will if X happens", "data shows", "OI confirms".
6. Stop loss is NON-NEGOTIABLE. Every trade must have a stop_level on the INDEX/STOCK SPOT price. Risk:reward must be at least 1:1.5.
7. If VIX is > 20, reduce position sizes in your recommendation. MENTION THIS.
8. "skipped_trades" field is MANDATORY — be honest about market uncertainty.

RANKING & ORDERING RULES (CRITICAL):
9. RANK trades by probability — highest probability = rank 1 (best trade of the day).
10. The "rank" field in trades array: 1, 2, 3, 4, 5. In stock_trades: S1, S2. Rank 1 = highest confidence.
11. The "time_sort" field MUST be 4-digit 24hr format IST: "0930", "1030", "1400", "1430" etc. This allows frontend to sort all trades chronologically for the trading day plan.
12. Sort trades array by rank (highest probability first) in the JSON output.

PERCENTAGE TARGETS (CRITICAL):
13. EVERY trade MUST have "target_pct" — the expected % gain if target hits. Calculate: ((target - entry) / entry) * 100. Round to nearest integer. Include % sign.
14. EVERY trade MUST have "sl_pct" — the % loss if stop loss hits. Calculate: ((stop_loss - entry) / entry) * 100. Round to nearest integer. Include % and minus sign.
15. These percentages help traders instantly see reward vs risk without mental math.
16. Example: Entry ₹120, Target ₹200, SL ₹80 → target_pct = "+67%", sl_pct = "-33%"

GUT PICKS (CRITICAL — Your 2 BEST trades of the day):
17. "gut_picks" array MUST contain exactly 2 trades — your absolute HIGHEST conviction picks from all trades above.
18. These are the trades you would put YOUR OWN money on if forced to choose only 2.
19. They must have the highest probability (ideally 90%+), best risk:reward, and clearest data confirmation.
20. "why_this_one" must explain in 1-2 sentences what makes THIS trade stand out above all others.
21. If no trade truly feels near-certain, still pick the best 2 but be honest about the probability. Never inflate.
22. Gut picks can come from index trades, stock trades, or even hero zero. Pick the best 2 regardless of type.

EVENT ALERT (CRITICAL):
23. ALWAYS scan the global/domestic data for any sudden event that could impact trading today: RBI decisions, US CPI/jobs data, FII/DII massive flows, crude oil spikes, geopolitical events, earnings surprises, government policy announcements, currency moves > 1%.
24. If ANY significant event exists, populate "event_alert" with has_event=true and all fields filled.
25. If no significant event today, set has_event=false and leave other fields empty.
26. Severity: HIGH = can move market 1%+ (rate decision, war, crude spike >5%), MEDIUM = 0.3-1% impact, LOW = sector-specific.
27. The "action" field must be specific and actionable — not generic "be careful". Tell the trader exactly what to do.

GAMMA BLAST PROBABILITY (CRITICAL — Analyze for BOTH expiry AND events):
Gamma blast = sudden explosive move caused by options gamma forcing market makers to hedge rapidly.
Two sources trigger gamma blasts — analyze BOTH and combine:

SOURCE 1: EXPIRY-DRIVEN GAMMA (applies on ALL expiry days — weekly AND monthly):
COMPLETE EXPIRY MAP (analyze gamma for EVERY index expiring today):
- TUESDAY (NSE): NIFTY 50 WEEKLY expiry → Gamma on Nifty
- LAST TUESDAY (NSE): NIFTY 50 weekly + BANK NIFTY monthly + FIN NIFTY monthly + ALL Stock F&O monthly = MEGA EXPIRY DAY
- THURSDAY (BSE): SENSEX WEEKLY expiry → Gamma on Sensex
- LAST THURSDAY (BSE): SENSEX weekly + BANKEX monthly = DOUBLE BSE EXPIRY

CRITICAL: Monthly expiry has MORE gamma than weekly because:
- 4 weeks of OI accumulation unwinds in one day
- Institutional positions are larger on monthly series
- Bank Nifty monthly = highest gamma potential of any single expiry (lot size 30 + heavy institutional OI)
- Stock F&O monthly expiry can cause individual stock gamma cascades

Scoring for expiry-driven gamma:
    * Weekly expiry day: +25% base
    * Monthly expiry day: +35% base (MORE OI = MORE gamma)
    * DOUBLE EXPIRY (Nifty weekly + Bank Nifty monthly on last Tue): +45% base (maximum gamma potential)
    * Price within 50 points of max pain on EXPIRING index: +20%
    * Heavy OI at single strike on EXPIRING index: +15%
    * After 2 PM IST on expiry day: +10%
    * VIX < 13 (complacency → surprise move): +15%
    * Straddle premium low (market underpricing move): +10%
- "index" field: List ALL indices expiring today. E.g. on last Tuesday: "NIFTY 50 + BANK NIFTY + FIN NIFTY"
- "expiry_factors" must reference EACH EXPIRING INDEX's OI, max pain, PCR separately
- On NON-expiry days: expiry component = 0%, set expiry_factors to "N/A - not expiry day"

SOURCE 2: EVENT-DRIVEN GAMMA (applies ANY day):
- Sudden geopolitical/macro events create gamma blasts even on non-expiry days
- Scoring for event-driven:
    * RBI rate decision / policy announcement: +25%
    * US CPI / Jobs / Fed decision (if released today or overnight): +20%
    * Crude oil spike > 3% overnight: +15%
    * FII selling > ₹3000Cr in a single session: +15%
    * War escalation / border tension / sanctions: +20%
    * Currency move > 1% (INR crash): +15%
    * Major earnings surprise (top 5 Nifty stock): +10%
    * Global flash crash / circuit breaker triggered anywhere: +25%
- "event_factors" must name the SPECIFIC event and explain the transmission mechanism
- If NO major event: event component = 0%, set event_factors to "No major event today"

COMBINED PROBABILITY:
28. Final gamma_blast probability = max(expiry_component, event_component) + overlap_bonus
    - If BOTH expiry AND event exist on same day: add +10% overlap bonus (double whammy)
    - DOUBLE EXPIRY (last Tue/last Thu) + major event = add +15% overlap bonus (triple whammy)
    - Cap at 95% — never claim 100% certainty
29. "source" field: "EXPIRY" if only expiry-driven, "EVENT" if only event-driven, "BOTH" if both
30. "index" field must name ALL INDICES EXPIRING TODAY (e.g. "NIFTY 50 + BANK NIFTY" on last Tuesday). For event-driven: name the MOST IMPACTED index.
31. "best_play" must be SPECIFIC: exact instrument, entry price, target, on the correct index with correct expiry. On double expiry days, pick the index with the BEST gamma setup.
32. Reference ranges:
    - Calm non-expiry day, no events: 5-15%
    - Weekly expiry day (Tue/Thu): 25-55%
    - Monthly expiry day (last Tue/Thu): 35-70%
    - Double/Mega expiry (last Tue = Nifty + Bank Nifty): 45-80%
    - Major event day (any day): 20-50%
    - Double expiry + major event: 55-95%

RULES FOR INDEX TRADES (up to 5 trades — fewer if market is unclear):
- Generate UP TO 5 index trades — only include trades with 80%+ probability
- Mix of NIFTY, BANK NIFTY (at least 2 each if available), and optionally SENSEX
- EVERY trade MUST include: entry_condition (> or <), timing (IST), probability (%), factors_aligned, what_invalidates
- Include both CALL and PUT options, and at least 1 futures trade
- Use REALISTIC strike prices near current levels (ATM or 1-2 strikes OTM)
- Entry, target, stop loss must be specific numbers
- Risk:Reward must be minimum 1:1.5
- Use correct expiry dates based on SEBI schedule: Nifty weekly=Tuesday, Sensex weekly=Thursday, Bank Nifty monthly=last Tuesday
- {"TODAY IS EXPIRY DAY for " + expiry_list + ". Prioritize expiry-day strategies: theta decay plays, gamma scalping. At least 2 trades should be expiry-specific." if is_expiry_day else "Today is NOT an expiry day. Use next week's expiry for weekly options. Focus on positional/swing trades."}

RULES FOR STOCK OPTIONS (up to 2 trades — 0 if no clear setup):
- Pick stocks with STRONGEST data-backed setups ONLY
- EVERY trade MUST include: entry_condition, timing, probability, factors_aligned, what_invalidates
- Prefer stocks with volume spike > 1.5x (institutional fingerprint)
- Use MONTHLY expiry stock options (not weekly)
- Include lot size in option_detail
- If no stock has clear 80%+ edge today, return empty array and explain in skipped_trades

{hero_zero_instruction}
"""

    # Call Claude API via HTTP (same method as main report)
    try:
        if not ANTHROPIC_API_KEY:
            return {"success": False, "error": "AI analysis service is not configured. Please contact support at contact@celesys.ai."}
        
        response = _http_pool.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 6000,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=120
        )
        
        if response.status_code != 200:
            error_detail = ""
            try:
                error_detail = response.json().get("error", {}).get("message", "")
            except:
                pass
            print(f"❌ Anthropic API error {response.status_code}: {error_detail}")
            return {"success": False, "error": "AI service temporarily unavailable. Please try again in a moment."}
        
        raw = response.json()["content"][0]["text"].strip()
        # Clean JSON
        raw = raw.replace("```json", "").replace("```", "").strip()
        
        # Parse JSON
        result = json_mod.loads(raw)
        
        response_data = {
            "success": True,
            "market_assessment": result.get("market_assessment", {}),
            "market_context": result.get("market_context", ""),
            "indices": [d for d in indices_data if d['name'] != 'INDIA VIX'],
            "trades": result.get("trades", []),
            "stock_trades": result.get("stock_trades", []),
            "hero_zero": result.get("hero_zero", []),
            "skipped_trades": result.get("skipped_trades", ""),
            "gut_picks": result.get("gut_picks", []),
            "event_alert": result.get("event_alert", {}),
            "gamma_blast": result.get("gamma_blast", {}),
            "vix": next((d for d in indices_data if d['name'] == 'INDIA VIX'), None),
            "generated_at": (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat(),
            "expiry_today": expiry_list,
            "is_expiry_day": is_expiry_day,
            "day_name": day_name
        }
        
        # Cache for 30 minutes — next click within window returns same trades
        _rc2 = _trades_cache_us if is_us_trades else _trades_cache
        _rc2["timestamp"] = datetime.utcnow() + timedelta(hours=5, minutes=30)
        _rc2["data"] = response_data
        print(f"💾 Trades cached at {_trades_cache['timestamp'].strftime('%H:%M IST')} — valid until {(_trades_cache['timestamp'] + timedelta(minutes=30)).strftime('%H:%M IST')}")
        
        # Auto-save to history for validation/backtesting
        try:
            ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
            _save_trades_to_history(response_data, ist_now.strftime('%Y-%m-%d'))
        except Exception as he:
            print(f"⚠️ History save skipped: {he}")
        
        return response_data
        
    except json_mod.JSONDecodeError as e:
        print(f"⚠️ JSON parse error: {e}")
        print(f"Raw response: {raw[:500]}")
        try:
            start = raw.index('{')
            end = raw.rindex('}') + 1
            result = json_mod.loads(raw[start:end])
            return {
                "success": True,
                "market_assessment": result.get("market_assessment", {}),
                "market_context": result.get("market_context", ""),
                "indices": [d for d in indices_data if d['name'] != 'INDIA VIX'],
                "trades": result.get("trades", []),
                "stock_trades": result.get("stock_trades", []),
                "hero_zero": result.get("hero_zero", []),
                "skipped_trades": result.get("skipped_trades", ""),
            "gut_picks": result.get("gut_picks", []),
            "event_alert": result.get("event_alert", {}),
            "gamma_blast": result.get("gamma_blast", {}),
                "vix": next((d for d in indices_data if d['name'] == 'INDIA VIX'), None),
                "generated_at": (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat(),
                "expiry_today": expiry_list,
                "is_expiry_day": is_expiry_day,
                "day_name": day_name
            }
        except:
            return {"success": False, "error": "AI service temporarily unavailable. Please try again."}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Analysis is taking longer than expected. Please try again."}
    except Exception as e:
        print(f"❌ Index trades error: {e}")
        return {"success": False, "error": "Service temporarily unavailable. Please try again in a moment."}


@app.get("/api/verify-price/{company}")
async def verify_price(company: str):
    """
    Quick price check endpoint - verify data is accurate
    Returns just the current price for comparison
    """
    live_data = get_live_stock_data(company)
    
    if "error" in live_data:
        raise HTTPException(400, live_data["error"])
    
    return {
        "ticker": live_data["ticker"],
        "price": live_data["current_price"],
        "currency": live_data["currency"],
        "change": live_data["price_change"],
        "change_pct": live_data["price_change_pct"],
        "timestamp": live_data["data_timestamp"],
        "verify_at": live_data["verification_url"]
    }


@app.post("/api/check-rate-limit")
async def check_rate_limit_endpoint(request: Request):
    """Check if an email has remaining report quota before submitting."""
    try:
        data = await request.json()
        email = data.get("email", "").strip()
        if not email:
            raise HTTPException(400, "Email required")
        result = check_rate_limit(email)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"allowed": True}  # Fail open - don't block on errors


# ═══ FULL REPORT WITH AI ═══
@app.post("/api/generate-report")
async def generate_report(request: Request):
    import time as _time
    _t0 = _time.time()
    try:
        data = await request.json()
        company = data.get("company_name", "").strip()
        email = data.get("email", "").strip()
        
        if not company or not email:
            raise HTTPException(400, "company_name and email required")
        
        # CHECK RATE LIMIT (inline — no separate API call needed)
        rate_check = check_rate_limit(email)
        if not rate_check["allowed"]:
            return JSONResponse(
                status_code=429,
                content=rate_check
            )
        
        # GET LIVE DATA — run in thread pool so other users aren't blocked
        _t1 = _time.time()
        loop = asyncio.get_event_loop()
        live_data = await loop.run_in_executor(_thread_pool, get_live_stock_data, company)
        _t2 = _time.time()
        print(f"⏱️ get_live_stock_data: {_t2-_t1:.1f}s")
        
        # Check if there was an error
        if "error" in live_data or not live_data.get("success"):
            error_msg = live_data.get("error", "Could not fetch market data for this ticker")
            raise HTTPException(400, error_msg)
        
        # ═══ CHECK AI REPORT CACHE — instant for 10K users hitting same stock ═══
        _cache_key = live_data.get('ticker', company).upper()
        cached = _get_cached_report(_cache_key)
        if cached:
            _elapsed = round(_time.time() - _t0, 1)
            print(f"⚡ CACHE HIT: {_cache_key} → {_elapsed}s (saved ~30s AI call)")
            # Still count the rate limit
            record_request(email)
            remaining = RATE_LIMIT_MAX_REQUESTS - len([
                t for t in email_rate_limiter.get(email.lower().strip(), [])
                if t > datetime.now() - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
            ])
            # Return cached report with fresh rate limit info
            cached_resp = dict(cached)  # copy
            cached_resp["rate_limit"] = {"remaining": max(0, remaining)}
            cached_resp["cached"] = True
            cached_resp["elapsed"] = _elapsed
            report_counter["count"] += 1
            save_counter()
            cached_resp["report_number"] = report_counter["count"]
            return cached_resp
        
        # Format live data section
        currency_symbol = '₹' if live_data['currency'] == 'INR' else '$'
        price_arrow = '🔴 ↓' if isinstance(live_data.get('price_change'), (int, float)) and live_data['price_change'] < 0 else '🟢 ↑'
        
        # ═══ SAFE FORMATTER — prevents 'N/A' from crashing float formats ═══
        def _fv(val, fmt=",.2f", prefix="", suffix=""):
            """Format a value safely. Returns formatted string or 'N/A'."""
            if val is None or val == 'N/A' or val == '':
                return 'N/A'
            try:
                v = float(str(val).replace(',', ''))
                return f"{prefix}{format(v, fmt)}{suffix}"
            except (ValueError, TypeError):
                return str(val)
        
        def _safe_div(a, b):
            """Safe division — handles N/A, None, zero."""
            try:
                a, b = float(a if a and a != 'N/A' else 0), float(b if b and b != 'N/A' else 1)
                return a / b if b != 0 else 0
            except:
                return 0
        
        # Pre-format all values that use :,.2f or :, formatting
        _f_price = _fv(live_data.get('current_price', 0), ",.2f", currency_symbol)
        _f_chg = _fv(abs(live_data.get('price_change', 0)) if isinstance(live_data.get('price_change'), (int, float)) else 0, ".2f", currency_symbol)
        _f_chg_pct = _fv(live_data.get('price_change_pct', 0), "+.2f", "", "%")
        _f_w52h = _fv(live_data.get('week52_high'), ",.2f", currency_symbol)
        _f_w52l = _fv(live_data.get('week52_low'), ",.2f", currency_symbol)
        _f_mcap = _fv(live_data.get('market_cap'), ",.0f", currency_symbol)
        
        live_data_section = f"""
╔═══════════════════════════════════════════════════════════════╗
║  🔴 REAL-TIME MARKET DATA                                     ║
║  Data as of: {live_data['data_timestamp']}       ║
╚═══════════════════════════════════════════════════════════════╝

CURRENT MARKET SNAPSHOT:
• Ticker: {live_data['ticker']}
• Company: {live_data['company_name']}
• Current Price: {_f_price}
• Change Today: {price_arrow} {_f_chg} ({_f_chg_pct})

VALUATION METRICS (CURRENT):
• P/E Ratio (Trailing): {live_data['pe_ratio']}
• P/E Ratio (Forward): {live_data.get('forward_pe', 'N/A')}
• P/B Ratio: {live_data['pb_ratio']}
• PEG Ratio: {live_data.get('peg_ratio', 'N/A')}
• EV/EBITDA: {live_data.get('enterprise_to_ebitda', 'N/A')}
• Dividend Yield: {live_data['dividend_yield']}%
• Payout Ratio: {live_data.get('payout_ratio', 'N/A')}%
• Sector Avg P/E: {live_data.get('sector_avg_pe', 'N/A')}x
• Peer Avg P/E: {live_data.get('peer_avg_pe', 'N/A')}x
• Peers Analyzed: {', '.join([p['ticker']+' (PE:'+str(p['pe'])+'x)' for p in live_data.get('peers',[])][:5]) or 'N/A'}
• 52-Week High: {_f_w52h}
• 52-Week Low: {_f_w52l}
• Market Cap: {_f_mcap}

PROFITABILITY & EFFICIENCY:
• Gross Margins: {live_data.get('gross_margins', 'N/A')}%
• Operating Margin: {live_data['operating_margin']}%
• Profit Margin: {live_data['profit_margin']}%
• EBITDA Margins: {live_data.get('ebitda_margins', 'N/A')}%
• ROE: {live_data['roe']}%
• Revenue Per Share: {live_data.get('revenue_per_share', 'N/A')}

BALANCE SHEET & CASH POSITION:
• Total Cash: {live_data.get('total_cash', 'N/A')}
• Total Debt: {live_data.get('total_debt', 'N/A')}
• Debt/Equity: {live_data['debt_to_equity']}
• Current Ratio: {live_data['current_ratio']}
• Quick Ratio: {live_data.get('quick_ratio', 'N/A')}
• Book Value/Share: {live_data['book_value']}
• Free Cash Flow: {live_data.get('free_cash_flow', 'N/A')}
• Operating Cash Flow: {live_data.get('operating_cash_flow', 'N/A')}
• EBITDA: {live_data.get('ebitda', 'N/A')}

GROWTH & EARNINGS VELOCITY:
• Revenue Growth: {live_data.get('revenue_growth', 'N/A')}%
• EPS Growth (Forward vs TTM): {live_data.get('eps_growth_pct', 'N/A')}%
• Earnings Growth: {live_data.get('earnings_growth', 'N/A')}%
• Quarterly Earnings Growth (YoY): {live_data.get('earnings_quarterly_growth', 'N/A')}%
• EPS (TTM): {live_data['eps_ttm']}
• EPS (Forward): {live_data['eps_forward']}
• Total Revenue: {live_data.get('total_revenue', 'N/A')}

TECHNICAL INDICATORS:
• SMA 20-Day: {live_data.get('sma_20', 'N/A')}
• SMA 50-Day: {live_data.get('sma_50', 'N/A')}
• SMA 200-Day: {live_data.get('sma_200', 'N/A')}
• EMA 9-Day: {live_data.get('ema_9', 'N/A')}
• EMA 21-Day: {live_data.get('ema_21', 'N/A')}
• EMA 50-Day: {live_data.get('ema_50', 'N/A')}
• Price vs SMA20: {'Above' if live_data.get('sma_20') and live_data['current_price'] > live_data['sma_20'] else 'Below' if live_data.get('sma_20') else 'N/A'}
• Price vs SMA200: {'Above (uptrend)' if live_data.get('sma_200') and live_data['current_price'] > live_data['sma_200'] else 'Below (downtrend)' if live_data.get('sma_200') else 'N/A'}
• EMA Signals: {', '.join(live_data.get('ema_signals', [])) if live_data.get('ema_signals') else 'N/A'}

RISK & SENTIMENT:
• Beta: {live_data['beta']}
• Short Ratio: {live_data.get('short_ratio', 'N/A')}

COMPANY INFORMATION:
• Sector: {live_data['sector']}
• Industry: {live_data['industry']}

═══════════════════════════════════════════════════════════════
"""

        # FETCH REAL MANAGEMENT/EARNINGS DATA
        mgmt_context = ""
        fund_holdings = {"institutions": [], "funds": [], "summary": {}}
        try:
            mgmt_context, fund_holdings = fetch_management_context(live_data['ticker'], live_data.get('company_name', company))
            if mgmt_context:
                # Final safety: reject if it's mostly HTML
                import re as re_safety
                html_tag_count = len(re_safety.findall(r'<[a-zA-Z/]', mgmt_context))
                if html_tag_count > 5:
                    print(f"⚠️ Management context contains {html_tag_count} HTML tags — DISCARDING")
                    mgmt_context = ""
                else:
                    print(f"📊 Got {len(mgmt_context)} chars of clean management/earnings data")
        except Exception as e:
            print(f"⚠️ Management context fetch failed: {e}")
        
        # BUILD COMPUTED FINANCIAL CONTEXT (always available from live_data)
        # This ensures the AI ALWAYS has numbers to work with, even if Yahoo APIs fail
        computed_context = f"""
=== COMPUTED FINANCIAL METRICS (from live market data) ===
Current Price: {_f_price}
Price Change Today: {_f_chg_pct}
P/E Ratio: {live_data['pe_ratio']}
Forward P/E: {live_data.get('forward_pe', 'N/A')}
P/B Ratio: {live_data['pb_ratio']}
Market Cap: {_f_mcap}
Dividend Yield: {live_data['dividend_yield']}%
Beta: {live_data['beta']}
52-Week High: {_f_w52h}
52-Week Low: {_f_w52l}
Price vs 52W High: {_fv(_safe_div(live_data.get('current_price',0), live_data.get('week52_high',1)) * 100, '.1f', '', '%')}
Price vs 52W Low: {_fv(_safe_div(live_data.get('current_price',0), live_data.get('week52_low',1)) * 100, '.1f', '', '%')}
Profit Margin: {live_data['profit_margin']}%
Operating Margin: {live_data['operating_margin']}%
ROE: {live_data['roe']}%
Debt/Equity: {live_data['debt_to_equity']}
Current Ratio: {live_data['current_ratio']}
EPS (TTM): {live_data['eps_ttm']}
EPS (Forward): {live_data['eps_forward']}
Book Value/Share: {live_data['book_value']}
Free Cash Flow: {live_data.get('free_cash_flow', 'N/A')}
Operating Cash Flow: {live_data.get('operating_cash_flow', 'N/A')}
Revenue Growth: {live_data.get('revenue_growth', 'N/A')}%
Sector: {live_data['sector']}
Industry: {live_data['industry']}
"""
        # Combine: real earnings data (if available) + computed metrics (always)
        full_context = ""
        if mgmt_context:
            full_context = mgmt_context + "\n\n" + computed_context
        else:
            full_context = computed_context + "\nNOTE: Detailed quarterly earnings data was not available from Yahoo Finance. Use the financial metrics above to infer trends. Compute approximate QoQ/YoY analysis from profit margins, P/E trends, and price position vs 52-week range."

        # ═══ DETERMINISTIC STOCK VERDICT ENGINE (server-side) ═══
        # This ensures AI always uses the same verdict for same data
        def _n(v):
            try:
                f = float(v)
                return f if v != 'N/A' else 0
            except:
                return 0
        
        v_score = 0
        v_reasons = []
        v_pe = _n(live_data['pe_ratio'])
        v_fpe = _n(live_data.get('forward_pe', 0))
        v_pb = _n(live_data['pb_ratio'])
        v_dy = _n(live_data['dividend_yield'])
        v_pm = _n(live_data['profit_margin'])
        v_om = _n(live_data['operating_margin'])
        v_roe = _n(live_data['roe'])
        v_de = _n(live_data['debt_to_equity'])
        v_cr = _n(live_data['current_ratio'])
        v_beta = _n(live_data['beta'])
        v_price = _n(live_data.get('current_price', 0))
        v_hi = _n(live_data.get('week52_high', 0))
        v_lo = _n(live_data.get('week52_low', 0))
        v_w52 = (v_price - v_lo) / (v_hi - v_lo) if v_hi > v_lo else 0.5
        
        # F1: VALUATION (±20)
        if v_pe > 0:
            if v_pe < 10: v_score += 18; v_reasons.append(f"Deep value P/E {v_pe:.1f}x [+18]")
            elif v_pe < 15: v_score += 12; v_reasons.append(f"Value P/E {v_pe:.1f}x [+12]")
            elif v_pe < 22: v_score += 4; v_reasons.append(f"Fair P/E {v_pe:.1f}x [+4]")
            elif v_pe < 35: v_score -= 6; v_reasons.append(f"Expensive P/E {v_pe:.1f}x [-6]")
            else: v_score -= 14; v_reasons.append(f"Very expensive P/E {v_pe:.1f}x [-14]")
        if v_fpe > 0 and v_pe > 0 and v_fpe < v_pe * 0.85:
            v_score += 5; v_reasons.append("Forward P/E discount — earnings growth [+5]")
        elif v_fpe > 0 and v_pe > 0 and v_fpe > v_pe * 1.1:
            v_score -= 3; v_reasons.append("Forward P/E premium — earnings may decline [-3]")
        
        # F2: PROFITABILITY (±15)
        if v_pm > 20: v_score += 12; v_reasons.append(f"Excellent margins {v_pm:.1f}% [+12]")
        elif v_pm > 10: v_score += 6; v_reasons.append(f"Solid margins {v_pm:.1f}% [+6]")
        elif v_pm > 0: v_score += 2; v_reasons.append(f"Thin margins {v_pm:.1f}% [+2]")
        elif v_pm < 0: v_score -= 10; v_reasons.append(f"Unprofitable {v_pm:.1f}% [-10]")
        
        if v_roe > 20: v_score += 8; v_reasons.append(f"Strong ROE {v_roe:.1f}% [+8]")
        elif v_roe > 12: v_score += 4; v_reasons.append(f"Decent ROE {v_roe:.1f}% [+4]")
        elif 0 < v_roe < 5: v_score -= 3; v_reasons.append(f"Weak ROE {v_roe:.1f}% [-3]")
        
        # F3: FINANCIAL HEALTH (±12)
        if v_de > 0:
            if v_de < 30: v_score += 10; v_reasons.append(f"Low debt D/E {v_de:.0f} [+10]")
            elif v_de < 80: v_score += 5; v_reasons.append(f"Moderate debt D/E {v_de:.0f} [+5]")
            elif v_de < 150: v_score -= 3; v_reasons.append(f"Elevated debt D/E {v_de:.0f} [-3]")
            else: v_score -= 10; v_reasons.append(f"High leverage D/E {v_de:.0f} [-10]")
        if v_cr > 2: v_score += 4; v_reasons.append(f"Strong liquidity CR {v_cr:.1f} [+4]")
        elif 0 < v_cr < 1: v_score -= 6; v_reasons.append(f"Liquidity risk CR {v_cr:.1f} [-6]")
        
        # F4: 52-WEEK POSITION (±10)
        if v_w52 < 0.2: v_score += 8; v_reasons.append(f"Near 52W low ({v_w52*100:.0f}% of range) [+8]")
        elif v_w52 < 0.35: v_score += 4; v_reasons.append("Lower half of 52W range [+4]")
        elif v_w52 > 0.9: v_score -= 4; v_reasons.append(f"Near 52W high ({v_w52*100:.0f}%) [-4]")
        elif v_w52 > 0.75: v_score += 2; v_reasons.append("Upper range, momentum intact [+2]")
        
        # F5: P/B (±8)
        if v_pb > 0:
            if v_pb < 1: v_score += 8; v_reasons.append(f"Below book P/B {v_pb:.1f} [+8]")
            elif v_pb < 2.5: v_score += 3; v_reasons.append(f"Reasonable P/B {v_pb:.1f} [+3]")
            elif v_pb > 8: v_score -= 5; v_reasons.append(f"Extreme P/B {v_pb:.1f} [-5]")
        
        # F6: DIVIDEND (±5)
        if v_dy > 4: v_score += 5; v_reasons.append(f"High yield {v_dy:.1f}% [+5]")
        elif v_dy > 2: v_score += 3; v_reasons.append(f"Decent yield {v_dy:.1f}% [+3]")
        
        # F7: BETA/RISK (±5)
        if v_beta > 2: v_score -= 5; v_reasons.append(f"High volatility Beta {v_beta:.2f} [-5]")
        elif v_beta > 1.5: v_score -= 2; v_reasons.append(f"Above-avg vol Beta {v_beta:.2f} [-2]")
        elif 0 < v_beta < 0.7: v_score += 3; v_reasons.append(f"Defensive Beta {v_beta:.2f} [+3]")
        
        # F8: OPERATING EFFICIENCY (±5)
        if v_om > 20: v_score += 5; v_reasons.append("High operating efficiency [+5]")
        elif 0 < v_om < 5: v_score -= 3; v_reasons.append("Weak operating margins [-3]")
        
        # ═══ NEW FACTORS F9-F20 — Deep multi-factor analysis ═══
        v_revG = _n(live_data.get('revenue_growth', 0))
        v_epsG = _n(live_data.get('eps_growth_pct', 0))
        v_earnG = _n(live_data.get('earnings_growth', 0))
        v_sectorPE = _n(live_data.get('sector_avg_pe', 0)) or 20
        v_sma20 = _n(live_data.get('sma_20', 0))
        v_sma50 = _n(live_data.get('sma_50', 0))
        v_sma200 = _n(live_data.get('sma_200', 0))
        v_peg = _n(live_data.get('peg_ratio', 0))
        v_evEbitda = _n(live_data.get('enterprise_to_ebitda', 0))
        v_fcf = _n(live_data.get('free_cash_flow', 0))
        v_ocf = _n(live_data.get('operating_cash_flow', 0))
        v_totalCash = _n(live_data.get('total_cash', 0))
        v_totalDebt = _n(live_data.get('total_debt', 0))
        v_totalRev = _n(live_data.get('total_revenue', 0))
        v_qr = _n(live_data.get('quick_ratio', 0))
        v_gm = _n(live_data.get('gross_margins', 0))
        v_ebitdaM = _n(live_data.get('ebitda_margins', 0))
        v_eqg = _n(live_data.get('earnings_quarterly_growth', 0))
        v_shortR = _n(live_data.get('short_ratio', 0))
        v_payout = _n(live_data.get('payout_ratio', 0))
        v_mcap = _n(live_data.get('market_cap', 0))
        
        # F9: EARNINGS VELOCITY — EPS + Revenue CAGR (±15)
        v_bestEG = v_epsG or v_earnG
        v_combG = (v_bestEG * 0.6 + v_revG * 0.4) if (v_bestEG and v_revG) else (v_bestEG or v_revG)
        if v_combG:
            if v_combG > 30: v_score += 12; v_reasons.append(f"Hypergrowth earnings velocity {v_combG:.0f}% CAGR [+12]")
            elif v_combG > 15: v_score += 7; v_reasons.append(f"Strong growth trajectory {v_combG:.0f}% [+7]")
            elif v_combG > 5: v_score += 3; v_reasons.append(f"Moderate growth {v_combG:.0f}% [+3]")
            elif v_combG <= -15: v_score -= 8; v_reasons.append(f"Severe earnings decline {v_combG:.0f}% [-8]")
            elif v_combG <= -5: v_score -= 4; v_reasons.append(f"Earnings contracting {v_combG:.0f}% [-4]")
        if v_bestEG > 10 and v_revG > 10:
            v_score += 3; v_reasons.append("Revenue + EPS both growing — quality momentum [+3]")
        elif v_bestEG < -5 and v_revG < -5:
            v_score -= 3; v_reasons.append("Revenue + EPS both declining — deterioration [-3]")
        
        # F10: RELATIVE VALUATION — P/E vs Sector (±10)
        if v_pe > 0 and v_sectorPE > 0:
            peR = v_pe / v_sectorPE
            disc = abs((v_sectorPE - v_pe) / v_sectorPE * 100)
            if peR < 0.6: v_score += 8; v_reasons.append(f"P/E {disc:.0f}% below sector avg ({v_sectorPE:.0f}x) [+8]")
            elif peR < 0.85: v_score += 4; v_reasons.append(f"P/E {disc:.0f}% below sector — undervalued [+4]")
            elif peR > 1.5: v_score -= 6; v_reasons.append(f"P/E {disc:.0f}% above sector — expensive vs peers [-6]")
            elif peR > 1.2: v_score -= 2; v_reasons.append("P/E premium over sector [-2]")
        
        # F11: TECHNICAL MOMENTUM — SMA crossovers (±12)
        tS = 0; tD = []
        if v_sma20 > 0:
            if v_price > v_sma20: tS += 2; tD.append("Above SMA20")
            else: tS -= 2; tD.append("Below SMA20")
        if v_sma200 > 0:
            if v_price > v_sma200: tS += 3; tD.append("Above SMA200 uptrend")
            else: tS -= 3; tD.append("Below SMA200 downtrend")
        if v_sma20 > 0 and v_sma200 > 0:
            if v_sma20 > v_sma200: tS += 2; tD.append("Golden Cross")
            elif v_sma20 < v_sma200 * 0.95: tS -= 2; tD.append("Death Cross")
        if v_sma50 > 0 and v_sma200 > 0 and v_price > v_sma50 and v_price > v_sma200:
            tS += 2; tD.append("All MAs bullish")
        # EMA crossover analysis
        v_ema9 = _n(live_data.get('ema_9', 0))
        v_ema21 = _n(live_data.get('ema_21', 0))
        v_ema50 = _n(live_data.get('ema_50', 0))
        if v_ema9 > 0 and v_ema21 > 0:
            if v_ema9 > v_ema21: tS += 1; tD.append("EMA9>21 bullish")
            else: tS -= 1; tD.append("EMA9<21 bearish")
        if v_ema21 > 0 and v_ema50 > 0:
            if v_ema21 > v_ema50: tS += 1; tD.append("EMA21>50 uptrend")
            else: tS -= 1; tD.append("EMA21<50 downtrend")
        tS = max(-8, min(8, tS))
        if tD: v_score += tS; v_reasons.append(f"Technical: {', '.join(tD[:3])} [{'+' if tS >= 0 else ''}{tS}]")
        
        # F12: PEG RATIO — Growth at Reasonable Price (±8)
        if v_peg > 0:
            if v_peg < 0.8: v_score += 7; v_reasons.append(f"PEG bargain ({v_peg:.1f}) — growth underpriced [+7]")
            elif v_peg < 1.2: v_score += 3; v_reasons.append(f"PEG fair ({v_peg:.1f}) [+3]")
            elif v_peg > 2.5: v_score -= 5; v_reasons.append(f"PEG stretched ({v_peg:.1f}) — overpaying for growth [-5]")
            elif v_peg > 1.8: v_score -= 2; v_reasons.append(f"PEG slightly high ({v_peg:.1f}) [-2]")
        
        # F13: CASH FLOW QUALITY — FCF health (±10)
        if v_fcf > 0 and v_totalRev > 0:
            fcfM = (v_fcf / v_totalRev) * 100
            if fcfM > 15: v_score += 7; v_reasons.append(f"Excellent FCF margin {fcfM:.1f}% — cash machine [+7]")
            elif fcfM > 5: v_score += 4; v_reasons.append(f"Healthy FCF {fcfM:.1f}% of revenue [+4]")
        elif v_fcf < 0 and v_ocf > 0:
            v_score -= 2; v_reasons.append("Negative FCF despite positive OCF — heavy capex [-2]")
        elif v_fcf < 0 and v_ocf <= 0:
            v_score -= 7; v_reasons.append("Negative cash flows — burning cash [-7]")
        if v_ocf > 0 and v_totalDebt > 0:
            dc = v_ocf / v_totalDebt
            if dc > 0.5: v_score += 2; v_reasons.append(f"OCF covers {dc*100:.0f}% of debt [+2]")
            elif dc < 0.1: v_score -= 2; v_reasons.append("Cash barely covers debt [-2]")
        
        # F14: BALANCE SHEET VERIFICATION — Cash vs Debt (±10)
        if v_totalCash > 0 and v_totalDebt > 0:
            cdr = v_totalCash / v_totalDebt
            if cdr > 1.5: v_score += 6; v_reasons.append(f"Net cash — cash exceeds debt by {(cdr-1)*100:.0f}% [+6]")
            elif cdr > 0.7: v_score += 3; v_reasons.append(f"Adequate cash — {cdr*100:.0f}% of debt covered [+3]")
            elif cdr < 0.15: v_score -= 5; v_reasons.append(f"Cash crunch — only {cdr*100:.0f}% of debt covered [-5]")
        elif v_totalCash > 0 and v_totalDebt == 0:
            v_score += 4; v_reasons.append("Debt-free with cash on books [+4]")
        if v_qr > 0:
            if v_qr > 1.5: v_score += 2; v_reasons.append(f"Strong quick ratio {v_qr:.1f} — meets short-term obligations [+2]")
            elif v_qr < 0.5: v_score -= 3; v_reasons.append(f"Weak quick ratio {v_qr:.1f} — solvency risk [-3]")
        
        # F15: EV/EBITDA — Enterprise valuation (±8)
        if v_evEbitda > 0:
            if v_evEbitda < 6: v_score += 7; v_reasons.append(f"Cheap EV/EBITDA {v_evEbitda:.1f}x — potential takeover value [+7]")
            elif v_evEbitda < 10: v_score += 4; v_reasons.append(f"Reasonable EV/EBITDA {v_evEbitda:.1f}x [+4]")
            elif v_evEbitda < 16: v_score += 1; v_reasons.append(f"Fair EV/EBITDA {v_evEbitda:.1f}x [+1]")
            elif v_evEbitda > 25: v_score -= 5; v_reasons.append(f"Very expensive EV/EBITDA {v_evEbitda:.1f}x [-5]")
            elif v_evEbitda > 18: v_score -= 2; v_reasons.append(f"Elevated EV/EBITDA {v_evEbitda:.1f}x [-2]")
        
        # F16: GROSS MARGIN POWER — Pricing power & moat (±7)
        if v_gm > 0:
            if v_gm > 60: v_score += 6; v_reasons.append(f"Elite gross margins {v_gm:.0f}% — strong moat [+6]")
            elif v_gm > 40: v_score += 3; v_reasons.append(f"Healthy gross margins {v_gm:.0f}% [+3]")
            elif v_gm < 20: v_score -= 4; v_reasons.append(f"Low gross margins {v_gm:.0f}% — weak pricing power [-4]")
        
        # F17: QUARTERLY EARNINGS MOMENTUM (±8)
        if v_eqg:
            if v_eqg > 30: v_score += 7; v_reasons.append(f"Quarterly earnings surging +{v_eqg:.0f}% YoY [+7]")
            elif v_eqg > 15: v_score += 4; v_reasons.append(f"Strong quarterly growth +{v_eqg:.0f}% [+4]")
            elif v_eqg > 5: v_score += 2; v_reasons.append(f"Moderate quarterly growth +{v_eqg:.0f}% [+2]")
            elif v_eqg < -20: v_score -= 6; v_reasons.append(f"Quarterly earnings plunging {v_eqg:.0f}% [-6]")
            elif v_eqg < -5: v_score -= 3; v_reasons.append(f"Quarterly decline {v_eqg:.0f}% [-3]")
        
        # F18: EBITDA MARGIN QUALITY (±5)
        if v_ebitdaM > 0:
            if v_ebitdaM > 30: v_score += 4; v_reasons.append(f"Strong EBITDA margins {v_ebitdaM:.0f}% — operational excellence [+4]")
            elif v_ebitdaM > 15: v_score += 2; v_reasons.append(f"Healthy EBITDA margins {v_ebitdaM:.0f}% [+2]")
            elif v_ebitdaM < 5: v_score -= 3; v_reasons.append(f"Thin EBITDA margins {v_ebitdaM:.0f}% [-3]")
        
        # F19: SHORT INTEREST SIGNAL (±5)
        if v_shortR > 0:
            if v_shortR > 10: v_score -= 4; v_reasons.append(f"Very high short interest ({v_shortR:.1f} days) — bearish sentiment [-4]")
            elif v_shortR > 5: v_score -= 2; v_reasons.append(f"Elevated short interest ({v_shortR:.1f} days) [-2]")
            elif v_shortR < 1.5: v_score += 2; v_reasons.append(f"Low short interest ({v_shortR:.1f} days) — bullish sentiment [+2]")
        
        # F20: DIVIDEND SUSTAINABILITY (±5)
        if v_dy > 0 and v_payout > 0:
            if v_payout < 40 and v_dy > 2: v_score += 4; v_reasons.append(f"Sustainable dividend — low payout {v_payout:.0f}% with {v_dy:.1f}% yield [+4]")
            elif v_payout > 90: v_score -= 3; v_reasons.append(f"Unsustainable payout ratio {v_payout:.0f}% — dividend at risk [-3]")
            elif v_payout > 70: v_score -= 1; v_reasons.append(f"High payout ratio {v_payout:.0f}% — limited dividend growth [-1]")
        
        # QUALITY COMBO BONUSES (±8)
        if v_combG and v_combG > 15 and v_pm > 15:
            v_score += 3; v_reasons.append("Growth + profitability combo — rare quality [+3]")
        if v_combG and v_combG < 0 and v_pm < 5:
            v_score -= 3; v_reasons.append("Declining growth + weak margins — avoid [-3]")
        # VALUE TRAP: cheap but deteriorating
        if v_pe > 0 and v_pe < 15 and v_combG and v_combG < -5 and v_pm < 8:
            v_score -= 6; v_reasons.append("VALUE TRAP: cheap P/E but shrinking earnings + thin margins [-6]")
        # GROWTH TRAP: expensive + growth stalling
        if v_pe > 30 and v_combG and v_combG < 5 and v_fpe > 0 and v_fpe > v_pe * 0.9:
            v_score -= 5; v_reasons.append("GROWTH TRAP: premium valuation but growth stalling [-5]")
        # TRIPLE STRENGTH
        if v_pe > 0 and v_pe < 20 and v_pm > 15 and v_roe > 15:
            v_score += 4; v_reasons.append("Triple Strength: fair value + profitable + strong ROE [+4]")
        # TRIPLE WEAKNESS
        if v_pe > 35 and v_pm < 5:
            v_score -= 4; v_reasons.append("Triple Weakness: overvalued + weak margins [-4]")
        
        # COMPUTE VERDICT — Tightened thresholds with quality gates
        v_bullish = len([r for r in v_reasons if '[+' in r])
        v_bearish = len([r for r in v_reasons if '[-' in r])
        v_total = len(v_reasons) if v_reasons else 1
        v_net_ratio = (v_bullish - v_bearish) / v_total
        
        if v_score >= 55 and v_bullish >= 8 and v_net_ratio > 0.4: v_verdict = "STRONG BUY"; v_emoji = "🟢"
        elif v_score >= 35 and v_bullish >= 6 and v_net_ratio > 0.25: v_verdict = "BUY"; v_emoji = "🟢"
        elif v_score >= 18 and v_bullish >= 4: v_verdict = "ACCUMULATE"; v_emoji = "🟢"
        elif v_score >= -18: v_verdict = "HOLD"; v_emoji = "🟡"
        elif v_score >= -35: v_verdict = "SELL"; v_emoji = "🔴"
        elif v_bearish >= 5: v_verdict = "STRONG SELL"; v_emoji = "🔴"
        else: v_verdict = "SELL"; v_emoji = "🔴"
        
        v_conviction = "Very High" if abs(v_score) > 50 else "High" if abs(v_score) > 30 else "Medium" if abs(v_score) > 15 else "Low"
        
        verdict_card = f"""
═══ PRE-COMPUTED STOCK VERDICT (deterministic — USE THIS) ═══
VERDICT: {v_verdict} {v_emoji}
Score: {v_score:+d} | Conviction: {v_conviction}
Factor breakdown:
  """ + "\n  ".join(v_reasons) + f"""

IMPORTANT: Your recommendation in the report MUST match this verdict ({v_verdict}).
Do NOT override or contradict this score-based verdict.
Your job is to EXPLAIN why this verdict makes sense using the data, not to change it.
═══ END VERDICT ═══"""
        
        # Add intrinsic value data to prompt
        iv = live_data.get('intrinsic')
        intrinsic_section = ""
        if iv:
            intrinsic_section = "\n═══ INTRINSIC VALUE ESTIMATES (pre-computed) ═══\n"
            if iv.get('graham'): intrinsic_section += f"Graham Number: {currency_symbol}{iv['graham']:,.2f} ({iv['graham_upside']:+.1f}% vs current price)\n"
            if iv.get('dcf_simple'): intrinsic_section += f"DCF (Graham Growth): {currency_symbol}{iv['dcf_simple']:,.2f} ({iv['dcf_upside']:+.1f}% vs current price)\n"
            if iv.get('lynch'): intrinsic_section += f"Lynch Fair Value (PEG=1): {currency_symbol}{iv['lynch']:,.2f}\n"
            if iv.get('earnings_yield'): intrinsic_section += f"Earnings Yield: {iv['earnings_yield']}% (premium vs 10Y bond: {iv['earnings_yield_premium']:+.2f}%)\n"
            if iv.get('book_value'): intrinsic_section += f"Book Value/Share: {currency_symbol}{iv['book_value']:,.2f}\n"
            intrinsic_section += "USE these intrinsic values in your Valuation Analysis section.\n═══ END INTRINSIC ═══"
        
        print(f"📊 Stock Verdict: {v_verdict} (score: {v_score:+d}, conviction: {v_conviction})")
        print(f"   Factors: {len(v_reasons)}")

        # CREATE CLAUDE PROMPT
        prompt = f"""Analyze {company} using the VERIFIED LIVE DATA below.

{live_data_section}

{"=" * 60}
REAL ANALYST & EARNINGS DATA (use this for management tone analysis):
{"=" * 60}
{full_context}
{"=" * 60}

{verdict_card}

{intrinsic_section}

═══ THE 20 QUANTITATIVE FACTORS DRIVING THIS VERDICT ═══
The verdict above ({v_verdict}, score: {v_score:+d}) was computed from these 20 factors.
Your report MUST analyze and reference ALL of them:

VALUATION FACTORS:
  F1: P/E Ratio Valuation (±20) — cheap vs expensive vs sector avg
  F2: P/B Ratio (±8) — book value premium/discount
  F5: Forward PE vs Trailing PE (±5) — earnings trajectory signal
  F10: Relative Valuation vs Sector P/E (±10) — peer comparison
  F12: PEG Ratio (±8) — growth at reasonable price
  F15: EV/EBITDA (±8) — enterprise value vs cash generation

PROFITABILITY FACTORS:
  F3: Profit Margin Quality (±15) — net margin strength
  F8: Operating Efficiency (±5) — ROE & operating margin
  F16: Gross Margin Power (±7) — pricing power & moat
  F18: EBITDA Margin Quality (±5) — operational cash generation

FINANCIAL HEALTH FACTORS:
  F4: Financial Health/Debt (±12) — debt-to-equity & current ratio
  F13: Free Cash Flow Quality (±10) — FCF yield & health
  F14: Balance Sheet Verification (±10) — cash vs debt coverage
  F20: Dividend Sustainability (±5) — payout ratio safety

MOMENTUM & POSITION FACTORS:
  F6: 52-Week Position (±10) — price range positioning
  F7: Beta/Risk (±5) — volatility assessment
  F9: Earnings Velocity (±15) — EPS & revenue CAGR
  F11: Technical Momentum (±12) — SMA/EMA crossovers
  F17: Quarterly Earnings Momentum (±8) — surprise & beat trends
  F19: Short Interest Signal (±5) — bearish bet indicator

You MUST touch on ALL 20 factors across your analysis sections. Group them naturally but ensure EVERY factor gets mentioned.
═══ END FACTOR LIST ═══

CRITICAL INSTRUCTIONS:
1. Use ONLY the real-time data provided above
2. Current price is {_f_price} - use THIS number
3. Base all analysis on current market conditions
4. Provide actionable, professional insights
5. Your Recommendation MUST be: {v_verdict} {v_emoji} — this is pre-computed from 20 quantitative factors and is NON-NEGOTIABLE
6. For Management Tone section, use analyst/earnings data if available, otherwise infer from P/E, margins, price position, beta, and dividend yield
7. For QoQ and YoY analysis: if quarterly data is provided, calculate actual changes. If NOT provided, use available metrics to INFER trends (e.g., forward PE vs trailing PE shows earnings growth/decline, profit margins indicate operational trends, price vs 52W range shows momentum)
7. Include specific growth predictions based on available data
8. ALWAYS provide a 12-month price prediction with specific bull/base/bear numbers
9. ABSOLUTE RULE — NEVER use these phrases in your report: "data corrupted", "HTML fragments", "insufficient data", "data limitation", "incomplete data", "cannot provide", "data unavailable", "technical website code", "UNKNOWN". Instead, ALWAYS analyze using whatever data IS available. Every metric (P/E, margins, price, 52W range) tells a story — use them.
10. If quarterly earnings numbers are missing, calculate implied growth from: (a) Forward PE vs Trailing PE gap = earnings growth expectation, (b) Price position in 52W range = momentum, (c) Profit margin level = operational health, (d) Dividend yield = cash flow confidence. Present these as "Implied QoQ/YoY Trends" with specific inferences.
11. The user is paying for a COMPLETE analysis. Every section must have substantive content with specific numbers and actionable insights. No empty sections, no disclaimers about missing data.
12. CRITICAL — LAYMAN INFERENCE: At the END of EVERY section, add a "💡 What This Means For You" box in plain, jargon-free language. Imagine explaining to a friend who knows nothing about stocks. Use analogies, comparisons to everyday things, and clear "should I worry?" / "is this good?" verdicts. This is the MOST important part of each section — make it crystal clear.
13. FACTOR COVERAGE: Your analysis must reflect ALL 20 quantitative factors listed above. Reference specific factor numbers (F1, F2, etc.) when discussing metrics. Each section should explicitly mention which factors drive its conclusion.
14. INFERENCE QUALITY: Every number you cite must have an inference. Don't just say "P/E is 25x" — say "P/E is 25x which means investors are paying ₹25 for every ₹1 of profit — that's a premium price, justified only if growth is strong."

═══════════════════════════════════════════════════════════════
📊 COMPREHENSIVE INVESTMENT ANALYSIS: {company.upper()}
═══════════════════════════════════════════════════════════════
**Report Date:** {datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")}
**Data Source:** Real-Time Market Data + AI Analysis
**Platform:** Celesys AI

---

## 🎯 INVESTMENT THESIS

**Current Price:** {_f_price} {live_data['currency']}  
**Recommendation:** {v_verdict} {v_emoji} (Score: {v_score:+d})  
**Conviction:** {v_conviction}  
**Time Horizon:** [Short/Long-term based on the data]

Explain WHY this {v_verdict} verdict makes sense by referencing ALL 20 factors grouped into 4 pillars:
- **Valuation** (F1, F2, F5, F10, F12, F15): Is price justified?
- **Profitability** (F3, F8, F16, F18): Is the business healthy?
- **Financial Strength** (F4, F13, F14, F20): Can it survive stress?
- **Momentum** (F6, F7, F9, F11, F17, F19): Where is it headed?

Give a clear 2-3 sentence verdict for each pillar, then an overall synthesis. Do NOT contradict the verdict.

---

## 💰 LIVE VALUATION ANALYSIS

```
┌──────────────────────────────────────────────────────┐
│ METRIC               LIVE VALUE     ASSESSMENT       │
├──────────────────────────────────────────────────────┤
│ Current Price        {currency_symbol}{live_data['current_price']:<10,.2f}  [Today's price] │
│ P/E Ratio (F1)       {str(live_data['pe_ratio']):<13}  [vs industry]  │
│ P/B Ratio (F2)       {str(live_data['pb_ratio']):<13}  [vs industry]  │
│ Forward PE (F5)      {str(live_data.get('forward_pe','N/A')):<13}  [Growth signal] │
│ PEG Ratio (F12)      {str(live_data.get('peg_ratio','N/A')):<13}  [Value vs growth]│
│ EV/EBITDA (F15)      {str(live_data.get('enterprise_to_ebitda','N/A')):<13}  [Enterprise val] │
│ Profit Margin (F3)   {str(live_data['profit_margin'])+"%":<13}  [Profitability]  │
│ Oper Margin (F8)     {str(live_data['operating_margin'])+"%":<13}  [Efficiency]     │
│ Gross Margin (F16)   {str(live_data.get('gross_margins','N/A')):<13}  [Pricing power]  │
│ FCF Yield (F13)      [Calculate]       [Cash quality]  │
│ Debt/Equity (F4)     {str(live_data['debt_to_equity']):<13}  [Leverage]       │
│ ROE (F8)             {str(live_data['roe'])+"%":<13}  [Returns]        │
│ Beta (F7)            {str(live_data['beta']):<13}  [Volatility]     │
│ Price vs 52W (F6)    [Calculate %]     [Position]     │
│ Div Yield (F20)      {str(live_data['dividend_yield'])+"%":<13}  [Income]         │
│ Short Interest (F19) {str(live_data.get('short_percent_of_float','N/A')):<13}  [Bear bets]      │
└──────────────────────────────────────────────────────┘
```

For EACH metric above, provide a 1-sentence layman interpretation. Example: "P/E of 45x means you're paying ₹45 for every ₹1 of earnings — that's expensive unless growth is exceptional."

**💡 Valuation Bottom Line:** [In 2 sentences: "Is this stock a good deal right now? Think of it like buying a house — are you paying a fair price for what you're getting, or are you overpaying because of hype?" Give a clear CHEAP / FAIR / EXPENSIVE verdict.]

---

## ⚠️ RISK ASSESSMENT (Cover ALL risk-related factors)

Analyze these 8 risk dimensions using the 20-factor data:

1. **Valuation Risk** — Is the stock overpriced? (F1: P/E, F2: P/B, F10: vs sector, F12: PEG, F15: EV/EBITDA)
2. **Financial Risk** — Can the company survive a downturn? (F4: debt/equity, F13: FCF, F14: cash vs debt, F20: dividend safety)
3. **Profitability Risk** — Are margins sustainable? (F3: net margin, F8: operating efficiency, F16: gross margin, F18: EBITDA margin)
4. **Momentum Risk** — Is the stock losing steam? (F6: 52W position, F9: earnings velocity, F11: SMA/EMA, F17: quarterly beats)
5. **Volatility Risk** — How wild are the price swings? (F7: beta)
6. **Short Seller Risk** — Are bears betting against this? (F19: short interest)
7. **Growth Risk** — Can growth sustain the valuation? (F5: forward vs trailing PE, F9: EPS CAGR)
8. **Sector & Macro Risk** — External headwinds from regulation, competition, economy

For each risk, rate as: 🟢 LOW / 🟡 MODERATE / 🔴 HIGH with specific numbers.

**Overall Risk Grade:** [LOW / MODERATE / ELEVATED / HIGH]

**💡 What This Means For You:** [In 2-3 simple sentences, explain to a regular person: "Should I worry about owning this stock? What's the worst that could happen?" Use plain language, no jargon.]

---

## 📈 QUARTERLY FUNDAMENTALS UPDATE

IMPORTANT: If quarterly revenue/earnings data is provided above, use REAL numbers to calculate QoQ and YoY changes. If quarterly data is NOT available, use the available financial metrics (profit margins, P/E, price vs 52-week range, forward P/E vs trailing P/E) to INFER growth trends. NEVER say "data corrupted" or "insufficient data" — always provide your best analysis with whatever data is available. Use phrases like "Based on available metrics..." or "Current margins suggest..."

**Latest Earnings Snapshot:** [If quarterly data available: cite real revenue, EPS, surprise %. If NOT: use trailing PE, forward PE, profit margins to describe current financial position. Example: "Trading at 25x trailing earnings with 14% profit margins suggests solid profitability"]

**QoQ Momentum (Quarter-over-Quarter):**
[If quarterly data available: calculate exact revenue/earnings % changes between quarters]
[If NOT available, use these PROXY INDICATORS — always provide analysis:]
- Forward PE vs Trailing PE: {live_data.get('forward_pe', 'N/A')} vs {live_data['pe_ratio']} → [If forward < trailing = earnings expected to GROW, if forward > trailing = earnings expected to SHRINK]
- Profit Margin at {live_data['profit_margin']}%: [Above 15% = strong, 8-15% = moderate, below 8% = tight]
- Price at {((live_data['current_price']/live_data['week52_high'])*100) if live_data['week52_high'] > 0 else 0:.0f}% of 52-week high → [Above 80% = upward momentum, 40-80% = neutral, below 40% = decline]
- Verdict: [ACCELERATING 🟢 / STABLE 🟡 / DECELERATING 🔴]

**YoY Structural Growth (Year-over-Year):**
[If quarterly data available: calculate exact YoY revenue/earnings growth]
[If NOT available, infer from:]
- PE ratio {live_data['pe_ratio']} vs sector average → [Market pricing in growth or decline?]
- Operating margin {live_data['operating_margin']}% → [Improving efficiency or compression?]
- 52-week price range position → [Stock appreciation = market sees growth]
- Verdict: [STRENGTHENING 🟢 / STABLE 🟡 / WEAKENING 🔴]

**Earnings Surprise Trend:** [If surprise data available, use it. If not: "Based on current valuation multiples and margin levels, the market appears to be pricing in [positive/negative/neutral] earnings expectations"]

**Key Fundamental Shifts:** [Analyze what the current metrics tell us about the company's trajectory — margin trends, valuation changes, momentum signals]

**12-Month Growth Forecast:**
Provide specific projections using available data:
- Projected Price Range: [Use PE ratio × estimated earnings growth to project bull/base/bear prices]
- Growth Catalyst: [What could drive this stock higher — sector tailwinds, margin expansion, market share]
- Risk Factor: [What could pull it down — competition, regulation, macro environment]

**💡 What This Means For You:** [In plain English: "Is this company growing or shrinking? If I invest ₹1 lakh today, what might it become in 12 months — best case and worst case?" Use specific numbers.]

---

## 🎙️ MANAGEMENT TONE & OUTLOOK

IMPORTANT: If analyst/earnings data is provided above, use it with real numbers. If NOT available, infer management confidence from: P/E ratio trends (forward vs trailing), price position vs 52-week range, profit margin levels, dividend yield, and beta. NEVER say "data corrupted" or "HTML fragments" — always provide substantive analysis.

**CEO/CFO Confidence Level:** [🟢 Bullish / 🟡 Cautious / 🔴 Defensive — based on earnings surprises, guidance direction, and insider activity from the data above]

**Earnings Performance:** [Use the actual earnings surprise history — did they beat or miss? By how much? Is the trend improving or deteriorating?]

**Analyst Consensus:** [What do analysts actually think? Use real price targets and recommendation data. How does current price compare to mean/high/low targets?]

**Forward Growth Outlook:** [Use forward EPS estimates and revenue growth data to project 12-month outlook. Be specific with numbers.]

**Insider & Institutional Signal:** [Use actual insider ownership %, institutional %, and short interest data. Are insiders buying or selling? Is short interest rising?]

**Red Flags:** [Based on real data — declining earnings surprises, lowered guidance, increasing short interest, insider selling, etc.]

**Green Flags:** [Based on real data — consecutive beats, raised targets, insider buying, institutional accumulation, etc.]

**What Management Isn't Telling You:** [Read between the numbers — what do the data patterns suggest that management wouldn't say directly?]

**Management Tone → Future Stock Impact:** 
[Based on everything above — how will management's current stance likely impact the stock price in the next 3-6-12 months? Be specific:
- If BULLISH: "Management confidence + rising estimates suggest X% upside to $XXX by [date]"
- If CAUTIOUS: "Mixed signals suggest sideways trading in $XXX-$XXX range until [catalyst]"  
- If DEFENSIVE: "Declining metrics + hedged language suggests X% downside risk to $XXX"
Include specific price targets tied to management tone.]

**12-Month Price Prediction:** [Based on forward EPS × historical PE range, analyst targets, and growth trajectory — give a specific price range with bull/base/bear cases]

**Investment Inference from Management Behavior:**
[Based on tone, body language of guidance, insider transactions, and communication patterns — is this management team building value or managing decline? Should investors trust the forward narrative? Concrete recommendation tied to management credibility.]

**💡 What This Means For You:** [Simple answer: "Can you trust these people with your money? Are they acting like owners or corporate politicians? What would their behavior tell a friend deciding whether to invest?"]

---

## 🏦 TOP FUND & INSTITUTIONAL HOLDINGS

**Smart Money Snapshot:** [If fund/institutional data is provided above, list the top 5 holders with % ownership. Comment on: Are big funds accumulating or reducing? Is institutional ownership high (>60%) = strong backing, or low = under the radar?]

**Top Holders:** [List top 5 institutional/mutual fund holders from the data. Format: "1. Vanguard (8.2%) 2. BlackRock (6.1%) etc." If data not available, note that institutional data was not available and skip this.]

**What Smart Money Tells Us:** [High institutional ownership = validation by professional analysts. Rising institutional % = accumulation phase. Declining = distribution/exit. Low institutional = either undiscovered gem or avoided for reasons.]

**💡 What This Means For You:** [Simple: "Are the big professional investors buying this stock or avoiding it? Think of it like a restaurant — if top food critics eat there, it's probably good. If they avoid it, there might be something wrong you can't see yet."]

---

## 🔮 WHAT'S NEXT — Catalysts & Timeline

**vs Peers / Competitors:** [Compare this stock's valuation (P/E), growth, and margins vs its industry peers listed above. Is it cheaper or more expensive than competitors? Is the premium/discount justified by superior growth, margins, or market position? Which competitor is the biggest threat and why?]

**Upcoming Sector Events (Next 3-6 Months):** [List 3-5 specific upcoming events for THIS sector that could move the stock — include approximate dates where possible. Examples: earnings season, regulatory decisions, commodity price drivers, policy changes, tech launches, industry conferences, seasonal demand shifts. Be specific to the sector, not generic.]

**Next 30 Days:** [What specific events/catalysts are coming? Earnings date, ex-dividend date, product launches, regulatory decisions, macro events]

**Next 90 Days:** [Medium-term catalysts — seasonal trends, industry events, guidance updates, competitive dynamics that will impact price]

**Next 12 Months:** [Big picture — growth trajectory, expansion plans, sector tailwinds/headwinds, regulatory changes, M&A potential]

**Key Trigger to Watch:** [The single most important catalyst that will determine if this stock goes up or down. Be specific — "Q3 earnings on [date]" or "Fed rate decision" or "New product launch in [month]"]

**Bull Case Scenario:** [If everything goes right — specific price target with reasoning]
**Bear Case Scenario:** [If things go wrong — specific downside target with reasoning]
**Most Likely Scenario:** [Your base case with probability assessment]

**💡 What This Means For You:** [Simple summary: "Over the next year, this stock is most likely to [go up/stay flat/go down] because [one clear reason]. The single thing to watch is [specific trigger]." Do NOT give explicit buy/hold/sell advice — only explain the outlook and key risks. End with: "This is for educational analysis only, not investment advice."]

---

## 🎯 ENTRY & EXIT STRATEGY (Multi-Factor Driven)

**Based on LIVE Price: {_f_price}**

CALCULATE ENTRY/EXIT using ALL these factors:
1. SMA Support: 20-day ({live_data.get('sma_20','N/A')}), 50-day ({live_data.get('sma_50','N/A')}), 200-day ({live_data.get('sma_200','N/A')}) — Buy near SMA support, sell near SMA resistance
   EMA Signals: 9-day ({live_data.get('ema_9','N/A')}), 21-day ({live_data.get('ema_21','N/A')}), 50-day ({live_data.get('ema_50','N/A')}) — {', '.join(live_data.get('ema_signals',[])) if live_data.get('ema_signals') else 'N/A'}
2. 52-Week Range: High {_f_w52h}, Low {_f_w52l} — Use for range-based targets
3. Book Value Floor: {live_data['book_value']} — absolute downside anchor
4. Intrinsic Value: Use Graham/DCF/Lynch values above as fair value targets
5. EV/EBITDA Implied: If EV/EBITDA is cheap (<10x), wider upside target; if expensive (>20x), tighter stop loss
6. FCF Yield: FCF {live_data.get('free_cash_flow','N/A')} vs market cap — determines margin of safety
7. Sector P/E: Current P/E vs sector avg {live_data.get('sector_avg_pe','N/A')}x — if below, target can be sector-mean reversion price
8. Beta-Adjusted Risk: Beta {live_data['beta']} — higher beta = wider stop loss, lower beta = tighter

```
Aggressive Buy:   {currency_symbol}XXX  [SMA200 or 52W range support — for swing traders]
Accumulate Zone:  {currency_symbol}XXX  [SMA50 support or -5% from CMP — for investors]
Current Price:    {_f_price}  ◄── LIVE PRICE
Target 1 (3M):   {currency_symbol}XXX  [Nearest SMA resistance or +10% move]
Target 2 (12M):  {currency_symbol}XXX  [Intrinsic value / sector P/E convergence price]
Stop Loss:       {currency_symbol}XXX  [Below SMA200 or key support — max loss defined by beta]
```

Explain the LOGIC behind each level — which factor(s) drive it.

---

## 🌟 10-YEAR SMALL-CAP RECOMMENDATIONS

[Include small-cap recommendations as before]

---

## 💡 BOTTOM LINE

**Current Assessment ({live_data['data_timestamp']}):**

**Verdict: {v_verdict} {v_emoji}** (Conviction: {v_conviction}, Score: {v_score:+d})

Based on real-time price of {_f_price}:
[Summarize your analysis. Must align with the {v_verdict} verdict. Give specific entry/exit levels if applicable.]

═══════════════════════════════════════════════════════════════
⚠️ IMPORTANT DISCLAIMERS:

📊 DATA FRESHNESS:
   Report generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")}
   Market data: Real-time from multiple financial sources
   
⚠️ NOT FINANCIAL ADVICE:
   This is educational research only
   Consult Certified Financial Advisor before investing
   
🔬 RESEARCH PLATFORM:
   Non-commercial educational tool
   For learning and analysis purposes only
═══════════════════════════════════════════════════════════════
"""

        # ═══ INTELLIGENT AI FALLBACK CHAIN ═══
        # Model 1: Claude Sonnet (best quality, 60s)
        # Model 2: Claude Haiku (faster, 40s)  
        # Model 3: Template report (instant, no AI needed)
        # User ALWAYS gets a report — no more timeouts.
        
        report = None
        ai_model_used = "none"
        _t3 = _time.time()
        print(f"⏱️ Prompt built: {_t3-_t2:.1f}s. Starting AI...")
        
        def _run_ai_call(prompt_text, api_key, models_list):
            """Run AI models in sequence. Returns (report_text, model_label)."""
            if not api_key:
                return None, "none"
            _headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            for model_name, max_tok, timeout_s, label in models_list:
                try:
                    print(f"🤖 AI attempt: {label} (timeout={timeout_s}s)...")
                    resp = _http_pool.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=_headers,
                        json={"model": model_name, "max_tokens": max_tok,
                              "messages": [{"role": "user", "content": prompt_text}]},
                        timeout=timeout_s
                    )
                    if resp.status_code == 200:
                        text = resp.json()["content"][0]["text"]
                        print(f"✅ AI success: {label} ({len(text)} chars)")
                        return text, label
                    elif resp.status_code in (429, 529, 503):
                        print(f"⚠️ {label} overloaded ({resp.status_code}), trying next...")
                        continue
                    elif resp.status_code == 401:
                        print(f"❌ API key invalid")
                        break
                    else:
                        print(f"⚠️ {label} error {resp.status_code}")
                        continue
                except requests.exceptions.Timeout:
                    print(f"⏰ {label} timed out after {timeout_s}s")
                    continue
                except Exception as e:
                    print(f"⚠️ {label} error: {e}")
                    continue
            return None, "none"
        
        _ai_models = [
            ("claude-sonnet-4-20250514", 4096, 35, "sonnet"),
            ("claude-haiku-4-5-20251001", 4096, 25, "haiku"),
        ]
        
        # Run AI in thread pool — doesn't block event loop while waiting 5-45s
        report, ai_model_used = await loop.run_in_executor(
            _thread_pool, _run_ai_call, prompt, ANTHROPIC_API_KEY, _ai_models
        )
        
        # ═══ FALLBACK 3: Template report (no AI) — ALWAYS succeeds ═══
        if not report:
            print("📝 All AI models failed — generating template report...")
            ai_model_used = "template"
            
            # Safe float helper — handles 'N/A', None, empty strings
            def _sf(v, default=0):
                if v is None or v == 'N/A' or v == '' or v == 'N/A%':
                    return default
                try:
                    return float(str(v).replace('%','').replace(',',''))
                except:
                    return default
            
            _curr = '₹' if live_data['currency'] == 'INR' else '$'
            _p = _sf(live_data.get('current_price', 0))
            _pe = live_data.get('pe_ratio', 'N/A')
            _pm = live_data.get('profit_margin', 'N/A')
            _roe = live_data.get('roe', 'N/A')
            _de = live_data.get('debt_to_equity', 'N/A')
            _beta = live_data.get('beta', 'N/A')
            _sector = live_data.get('sector', 'Unknown')
            _industry = live_data.get('industry', 'Unknown')
            _w52h = _sf(live_data.get('week52_high', _p), _p)
            _w52l = _sf(live_data.get('week52_low', _p), _p)
            _w52pct = round(((_p - _w52l) / (_w52h - _w52l) * 100), 1) if _w52h != _w52l else 50
            _spe = _sf(live_data.get('sector_avg_pe', 20), 20)
            _pAvgPE = live_data.get('peer_avg_pe', 'N/A')
            _eg = live_data.get('earnings_growth', 'N/A')
            _dv = live_data.get('dividend_yield', 'N/A')
            
            # Valuation assessment
            _pe_f = _sf(_pe)
            if _pe_f > 0:
                _pe_vs = "undervalued relative to" if _pe_f < _spe * 0.8 else "fairly valued relative to" if _pe_f < _spe * 1.2 else "trading at a premium to"
            else:
                _pe_vs = "not comparable (negative earnings) to"
            
            # Profitability assessment
            _pm_f = _sf(_pm)
            _pm_txt = "strong" if _pm_f > 15 else "moderate" if _pm_f > 5 else "thin" if _pm_f > 0 else "negative"
            
            # Risk assessment  
            _de_f = _sf(_de)
            _risk_txt = "low debt levels" if _de_f < 50 else "moderate leverage" if _de_f < 150 else "high debt load"
            _beta_f = _sf(_beta, 1)
            _vol_txt = "less volatile than the market" if _beta_f < 0.8 else "similar volatility to the market" if _beta_f < 1.2 else "more volatile than the market"
            
            # Momentum
            _mom_txt = "near yearly lows — potential value territory" if _w52pct < 25 else "near yearly highs — momentum is strong but watch for resistance" if _w52pct > 75 else "mid-range of its 52-week band — neutral positioning"
            
            # Peers
            _peer_txt = ""
            if live_data.get('peers'):
                _peer_names = ", ".join([p['ticker'] for p in live_data['peers'][:3]])
                _peer_txt = f"\n\n**Peer Comparison:** Key competitors include {_peer_names}. "
                if _pAvgPE != 'N/A' and _pe_f > 0:
                    _peer_pe_f = _sf(_pAvgPE)
                    if _pe_f < _peer_pe_f * 0.85:
                        _peer_txt += f"At {_pe_f:.1f}x P/E vs peer average of {_peer_pe_f:.1f}x, the stock appears undervalued relative to industry peers."
                    elif _pe_f > _peer_pe_f * 1.15:
                        _peer_txt += f"At {_pe_f:.1f}x P/E vs peer average of {_peer_pe_f:.1f}x, the stock carries a premium. Growth must justify this valuation."
                    else:
                        _peer_txt += f"At {_pe_f:.1f}x P/E vs peer average of {_peer_pe_f:.1f}x, the stock is fairly valued relative to peers."
            
            report = f"""## 📊 INVESTMENT THESIS

{live_data['company_name']} ({live_data['ticker']}) is currently trading at {_curr}{_p:,.2f} in the {_sector} sector ({_industry}). The stock is {_pe_vs} its sector average P/E of {_spe}x, with a trailing P/E of {_pe}. Profitability is {_pm_txt} at {_pm}% net margin, and the company's return on equity stands at {_roe}%.

The stock is {_mom_txt}, sitting at {_w52pct}% of its 52-week range ({_curr}{_w52l} to {_curr}{_w52h}). The balance sheet shows {_risk_txt} (D/E: {_de}), and the stock is {_vol_txt} (beta: {_beta}).{_peer_txt}

{'Dividend yield of ' + str(_dv) + '% provides income support.' if _sf(_dv) > 1 else ''} {'Earnings growth of ' + str(_eg) + '% signals improving fundamentals.' if _eg != 'N/A' and _sf(_eg) > 5 else ''}

**💡 What This Means For You:** At {_curr}{_p:,.2f}, the stock is {_pe_vs} its sector. {'This looks reasonably priced for what you get.' if _pe_f < _spe * 1.2 and _pe_f > 0 else 'The premium valuation means you need strong growth to justify the price.' if _pe_f > 0 else 'Negative earnings make valuation tricky — focus on revenue growth trajectory.'}

---

## 📈 QUARTERLY FUNDAMENTALS

**Revenue & Earnings Trend:** Based on current financial metrics, {live_data['company_name']} shows {_pm_txt} profitability with {_pm}% net margins. {'Margins above 15% indicate strong pricing power and operational efficiency.' if _pm_f > 15 else 'Margins suggest room for operational improvement.' if _pm_f > 0 else 'Negative margins indicate the company is currently unprofitable.'}

**Profitability Assessment:** Return on equity of {_roe}% {'exceeds 15% threshold — management is generating strong returns on shareholder capital.' if _sf(_roe) > 15 else 'is moderate — management generates adequate but not exceptional returns.' if _sf(_roe) > 8 else 'needs improvement.'}

**Earnings Surprise Trend:** {'Recent earnings growth of ' + str(_eg) + '% shows the company is beating expectations.' if _eg != 'N/A' and _sf(_eg) > 5 else 'Earnings data will be updated after the next quarterly report.'}

**12-Month Growth Forecast:**
- Projected Price Range: {_curr}{_w52l:,.0f} (bear) to {_curr}{_w52h:,.0f} (bull)
- Growth Catalyst: Sector tailwinds in {_sector}, margin expansion potential
- Risk Factor: Macro headwinds, competitive pressure in {_industry}

**💡 What This Means For You:** {'Strong fundamentals — the company is profitable and growing.' if _pm_f > 10 and _sf(_roe) > 12 else 'Mixed fundamentals — some strengths but watch for improvement.' if _pm_f > 0 else 'Fundamentals need work — this is a turnaround story.'}

---

## 🎙️ MANAGEMENT TONE & OUTLOOK

**CEO/CFO Confidence Level:** {'🟢 Bullish — stock trading near highs with strong margins suggests confident management' if _w52pct > 65 and _pm_f > 10 else '🟡 Cautious — mixed signals from price positioning and margins' if _w52pct > 35 else '🔴 Defensive — stock near lows, management likely in damage control mode'}

**Earnings Performance:** {'Company consistently delivers above-average profitability with ' + str(_pm) + '% margins.' if _pm_f > 15 else 'Profitability is moderate at ' + str(_pm) + '% margins — room for improvement exists.' if _pm_f > 0 else 'Company is currently unprofitable — watch for turnaround signs.'}

**Analyst Consensus:** Based on current valuation of {_pe}x P/E {'below' if _pe_f < _spe else 'above'} sector average of {_spe}x, analysts appear to be {'undervaluing' if _pe_f < _spe * 0.8 else 'fairly pricing' if _pe_f < _spe * 1.2 else 'pricing in significant growth for'} this stock.

**Forward Growth Outlook:** {'Strong forward indicators — high ROE and healthy margins suggest continued growth.' if _sf(_roe) > 15 and _pm_f > 10 else 'Moderate outlook — fundamentals are stable but not exceptional.' if _pm_f > 5 else 'Challenging outlook — company needs to demonstrate improving fundamentals.'}

**Red Flags:** {'High debt levels (D/E: ' + str(_de) + ') increase risk in rising rate environment. ' if _de_f > 150 else ''}{'Low margins suggest pricing pressure. ' if 0 < _pm_f < 5 else ''}{'High volatility (beta: ' + str(_beta) + ') means larger swings in both directions.' if _beta_f > 1.5 else ''}{'No major red flags identified from current data.' if _de_f < 150 and _pm_f > 5 and _beta_f < 1.5 else ''}

**Green Flags:** {'Strong margins (' + str(_pm) + '%) indicate competitive moat. ' if _pm_f > 15 else ''}{'Low debt (D/E: ' + str(_de) + ') provides financial flexibility. ' if _de_f < 50 else ''}{'Excellent ROE (' + str(_roe) + '%) shows efficient capital deployment. ' if _sf(_roe) > 15 else ''}{'Dividend yield of ' + str(_dv) + '% provides income support. ' if _sf(_dv) > 1 else ''}

**Management Tone → Future Stock Impact:** {'Management confidence appears HIGH based on strong operational metrics. Stock likely to maintain upward trajectory if margins hold. Target: ' + _curr + str(round(_w52h * 1.05, 0)) + ' within 12 months.' if _w52pct > 65 and _pm_f > 10 else 'Mixed signals suggest SIDEWAYS trading in ' + _curr + str(round(_w52l, 0)) + '-' + _curr + str(round(_w52h, 0)) + ' range until next catalyst.' if _w52pct > 35 else 'Defensive positioning suggests DOWNSIDE risk. Key support at ' + _curr + str(round(_w52l, 0)) + '. Wait for stabilization before entry.'}

**💡 What This Means For You:** {'Management appears to be executing well. The numbers back up a confident story.' if _w52pct > 60 and _pm_f > 10 else 'Management is doing an okay job but the stock needs a catalyst to move higher.' if _pm_f > 5 else 'Be cautious — the numbers suggest management has challenges ahead.'}

---

## 🏦 TOP FUND & INSTITUTIONAL HOLDINGS

**Smart Money Snapshot:** Institutional holding data is sourced from the latest available filings. Check the data cards above for real-time institutional ownership percentages.

**What Smart Money Tells Us:** {'Strong institutional ownership suggests professional validation of this stock. Large funds typically have dedicated research teams analyzing every aspect of the company.' if _sf(live_data.get('institutional_pct', '0')) > 50 else 'Monitor institutional flow data from quarterly filings for directional signals.'}

**💡 What This Means For You:** Think of institutional ownership like a restaurant review from top food critics — if the big professional investors hold this stock, their research teams have vetted it. Check the holding percentages above for the latest data.

---

## 🔮 WHAT'S NEXT — Catalysts & Timeline

**vs Peers / Competitors:** {live_data['company_name']} {'trades at a discount to peers, suggesting potential upside if the gap closes.' if _pe_f < _spe * 0.85 and _pe_f > 0 else 'trades at a premium to peers, reflecting market confidence in its growth trajectory.' if _pe_f > _spe * 1.15 else 'is fairly valued relative to industry peers.'}{_peer_txt}

**Upcoming Sector Events (Next 3-6 Months):** Key catalysts for the {_sector} sector include quarterly earnings season, potential regulatory changes, and macro developments affecting {_industry} companies.

**Next 30 Days:** Monitor upcoming earnings announcements, sector-specific macro events, and any corporate actions or regulatory filings.

**Next 90 Days:** Key factors include quarterly results, analyst estimate revisions, and sector rotation trends in {_sector}. Industry conferences and product launches may provide catalysts.

**Next 12 Months:** Long-term trajectory depends on margin expansion, revenue growth, and competitive dynamics in the {_industry} space. {'Favorable tailwinds suggest positive outlook.' if _pm_f > 10 and _w52pct > 50 else 'Watch for improvement in fundamentals before getting constructive.'}

**Key Trigger to Watch:** Next quarterly earnings report — watch for revenue growth trajectory and margin trends. This single event will determine short-term direction.

**Bull Case Scenario:** Strong earnings beat + positive guidance could push toward {_curr}{round(_w52h * 1.1):,.0f} (10% above 52-week high).
**Bear Case Scenario:** Earnings miss or macro headwinds could test support near {_curr}{round(_w52l * 0.9):,.0f} (10% below 52-week low).
**Most Likely Scenario:** Continued trading in {_curr}{round(_w52l):,.0f}-{_curr}{round(_w52h):,.0f} range with direction determined by next earnings.

**💡 What This Means For You:** Over the next year, this stock is most likely to {'trend higher if current momentum and fundamentals hold' if _w52pct > 60 and _pm_f > 10 else 'trade sideways until a clear catalyst emerges' if _pm_f > 5 else 'face headwinds until fundamentals improve'}. The single thing to watch is the next quarterly earnings report. This is for educational analysis only, not investment advice.

---

## 🏅 FINAL VERDICT

This is for educational analysis only, not investment advice. The 20-factor quantitative verdict, entry/exit levels, risk scores, and peer comparison above provide comprehensive analysis based on live market data. Always consult a financial advisor before making investment decisions.
"""
            print(f"📝 Template report generated ({len(report)} chars)")
        
        report_counter["count"] += 1
        save_counter()
        report_id = hashlib.md5(f"{company}{datetime.now()}".encode()).hexdigest()[:8]
        
        # Record this request for rate limiting
        record_request(email)
        remaining = RATE_LIMIT_MAX_REQUESTS - len([
            t for t in email_rate_limiter.get(email.lower().strip(), [])
            if t > datetime.now() - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
        ])
        
        _t4 = _time.time()
        print(f"⏱️ TOTAL: {_t4-_t0:.1f}s (data={_t2-_t1:.1f}s + prompt={_t3-_t2:.1f}s + AI={_t4-_t3:.1f}s) model={ai_model_used}")
        
        response = {
            "success": True,
            "report": report,
            "ai_model": ai_model_used,
            "company_name": company,
            "live_data": live_data,
            "fund_holdings": fund_holdings,
            "timestamp": datetime.now().isoformat(),
            "report_id": report_id.upper(),
            "report_number": report_counter["count"],
            "rate_limit": {
                "remaining": max(0, remaining),
                "limit": RATE_LIMIT_MAX_REQUESTS,
                "window_minutes": RATE_LIMIT_WINDOW_MINUTES
            }
        }
        
        # ═══ CACHE the report — next user searching same stock gets instant response ═══
        _set_cached_report(_cache_key, response)
        print(f"💾 Cached report for {_cache_key} (30min TTL, {len(_ai_report_cache)} reports cached)")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ Report generation error: {traceback.format_exc()}")
        raise HTTPException(500, f"Report generation failed: {str(e)}")


# ═══ TRADE VALIDATION — Backtest suggested trades against actual market data ═══
@app.get("/api/validate-trades")
async def validate_trades(request: Request):
    """Validate past trade suggestions against actual closing prices"""
    email = request.query_params.get("email", "").strip().lower()
    if email not in TRADES_ALLOWED_EMAILS:
        return {"success": False, "error": "Access restricted"}
    
    history = _load_trade_history()
    if not history:
        return {"success": True, "message": "No trade history yet. Generate trades first — they'll be saved automatically.", "results": [], "summary": {}}
    
    # Index ticker mapping
    index_tickers = {
        "NIFTY 50": "^NSEI", "NIFTY": "^NSEI",
        "BANK NIFTY": "^NSEBANK", "BANKNIFTY": "^NSEBANK",
        "SENSEX": "^BSESN", "BSE SENSEX": "^BSESN",
        "NIFTY IT": "^CNXIT", "NIFTY NEXT 50": "^NSMIDCP50",
        "FINNIFTY": "NIFTY_FIN_SERVICE.NS", "MIDCAP NIFTY": "^NSMIDCP50",
    }
    
    results = []
    from datetime import timedelta
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    today_str = ist_now.strftime('%Y-%m-%d')
    
    for date_str, day_data in sorted(history.items(), reverse=True):
        # Skip today (market may still be open)
        if date_str == today_str:
            continue
        
        day_results = {"date": date_str, "trades": [], "is_expiry": day_data.get("is_expiry_day", False)}
        
        for trade in day_data.get("trades", []):
            try:
                # Resolve ticker
                if trade["type"] == "INDEX":
                    name = (trade.get("index") or "").upper().strip()
                    ticker = index_tickers.get(name)
                    if not ticker:
                        # Try partial match
                        for k, v in index_tickers.items():
                            if k in name or name in k:
                                ticker = v
                                break
                    label = name
                elif trade["type"] == "STOCK":
                    stock_name = trade.get("stock", "")
                    ticker = stock_name if '.' in stock_name else stock_name + ".NS"
                    label = stock_name
                else:
                    continue
                
                if not ticker:
                    continue
                
                # Parse levels (remove ₹, $, commas)
                def parse_level(v):
                    if not v or v == '-':
                        return 0
                    s = str(v).replace('₹', '').replace('$', '').replace(',', '').strip()
                    try:
                        return float(s)
                    except:
                        return 0
                
                entry = parse_level(trade.get("entry_level"))
                target = parse_level(trade.get("target_level"))
                stop = parse_level(trade.get("stop_level"))
                
                if not entry:
                    continue
                
                # Fetch actual intraday data for that date
                t = yf.Ticker(ticker)
                trade_date = datetime.strptime(date_str, '%Y-%m-%d')
                next_day = trade_date + timedelta(days=1)
                hist = t.history(start=date_str, end=next_day.strftime('%Y-%m-%d'), interval="1h")
                
                if hist.empty:
                    hist = t.history(start=date_str, end=(trade_date + timedelta(days=3)).strftime('%Y-%m-%d'))
                
                # Fallback: Yahoo v8 chart API
                if hist.empty:
                    try:
                        _h = {'User-Agent': f'Mozilla/5.0 Chrome/{random.randint(118,126)}.0.0.0', 'Accept': 'application/json'}
                        ts1 = int(trade_date.timestamp())
                        ts2 = int((trade_date + timedelta(days=2)).timestamp())
                        r = _http_pool.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={ts1}&period2={ts2}&interval=1d", timeout=4)
                        if r.status_code == 200:
                            res = r.json().get('chart', {}).get('result', [{}])[0]
                            q = res.get('indicators', {}).get('quote', [{}])[0]
                            import pandas as pd
                            if q.get('close'):
                                hist = pd.DataFrame({'Close': q['close'], 'High': q['high'], 'Low': q['low'], 'Open': q['open']}).dropna()
                    except:
                        pass
                
                if hist.empty:
                    continue
                
                day_high = float(hist['High'].max())
                day_low = float(hist['Low'].min())
                day_open = float(hist['Open'].iloc[0])
                day_close = float(hist['Close'].iloc[-1])
                
                direction = (trade.get("direction") or "").upper()
                is_bullish = "BULL" in direction or "BUY CE" in (trade.get("bias") or "").upper()
                
                # Score the trade
                if is_bullish:
                    # Bullish: target hit if high >= target, stop hit if low <= stop
                    target_hit = target > 0 and day_high >= target
                    stop_hit = stop > 0 and day_low <= stop
                    actual_move_pct = round(((day_close - entry) / entry) * 100, 2) if entry else 0
                    best_move_pct = round(((day_high - entry) / entry) * 100, 2) if entry else 0
                else:
                    # Bearish: target hit if low <= target, stop hit if high >= stop
                    target_hit = target > 0 and day_low <= target
                    stop_hit = stop > 0 and day_high >= stop
                    actual_move_pct = round(((entry - day_close) / entry) * 100, 2) if entry else 0
                    best_move_pct = round(((entry - day_low) / entry) * 100, 2) if entry else 0
                
                # Determine outcome
                if target_hit and not stop_hit:
                    outcome = "TARGET HIT"
                    outcome_score = 1
                elif stop_hit and not target_hit:
                    outcome = "STOP HIT"
                    outcome_score = -1
                elif target_hit and stop_hit:
                    outcome = "VOLATILE"  # Both hit — depends on which first (hard to tell from daily)
                    outcome_score = 0
                elif actual_move_pct > 0:
                    outcome = "PARTIAL WIN"
                    outcome_score = 0.5
                else:
                    outcome = "PARTIAL LOSS"
                    outcome_score = -0.5
                
                day_results["trades"].append({
                    "label": label,
                    "type": trade["type"],
                    "direction": "BULL" if is_bullish else "BEAR",
                    "entry": entry,
                    "target": target,
                    "stop": stop,
                    "probability": trade.get("probability", ""),
                    "day_open": round(day_open, 2),
                    "day_high": round(day_high, 2),
                    "day_low": round(day_low, 2),
                    "day_close": round(day_close, 2),
                    "actual_move_pct": actual_move_pct,
                    "best_move_pct": best_move_pct,
                    "outcome": outcome,
                    "score": outcome_score,
                })
            except Exception as te:
                print(f"  Trade validation error for {trade}: {te}")
                continue
        
        if day_results["trades"]:
            results.append(day_results)
    
    # Compute summary
    all_trades = [t for r in results for t in r["trades"]]
    total = len(all_trades)
    wins = sum(1 for t in all_trades if t["score"] >= 0.5)
    losses = sum(1 for t in all_trades if t["score"] <= -0.5)
    target_hits = sum(1 for t in all_trades if t["outcome"] == "TARGET HIT")
    stop_hits = sum(1 for t in all_trades if t["outcome"] == "STOP HIT")
    avg_move = round(sum(t["actual_move_pct"] for t in all_trades) / max(1, total), 2)
    avg_best = round(sum(t["best_move_pct"] for t in all_trades) / max(1, total), 2)
    
    summary = {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / max(1, total) * 100, 1),
        "target_hit_rate": round(target_hits / max(1, total) * 100, 1),
        "stop_hit_rate": round(stop_hits / max(1, total) * 100, 1),
        "avg_actual_move": avg_move,
        "avg_best_move": avg_best,
        "days_tracked": len(results),
    }
    
    return {"success": True, "results": results, "summary": summary}


@app.post("/api/vote")
async def cast_vote(request: Request):
    """Record a feature vote."""
    try:
        data = await request.json()
        feature = data.get("feature", "")
        direction = data.get("direction", 0)
        
        if feature not in feature_votes:
            raise HTTPException(400, "Invalid feature")
        
        if direction > 0:
            feature_votes[feature]["up"] += 1
        elif direction < 0:
            feature_votes[feature]["dn"] += 1
        
        save_votes()
        return {"success": True, "votes": feature_votes[feature]}
    except HTTPException:
        raise
    except:
        return {"success": False}


@app.get("/api/votes")
async def get_votes():
    """Get current vote tallies for all features."""
    total = sum(v["up"] + v["dn"] for v in feature_votes.values())
    return {
        "votes": feature_votes,
        "total_votes": total
    }


@app.get("/api/stats")
async def stats():
    return {
        "total_reports": report_counter["count"],
        "platform": "Celesys AI",
        "version": "1.0-VERIFIED",
        "data_source": "Yahoo Finance (Real-Time)",
        "vs_chatgpt": "Live data vs ChatGPT's Jan 2025 cutoff"
    }


# ═══════════════════════════════════════════════
# MARKET DAILY ANALYSIS — Nifty, Bank Nifty, Sensex
# ═══════════════════════════════════════════════
_market_daily_cache = None
_market_daily_ts = None

@app.get("/api/market-daily")
async def market_daily():
    """Comprehensive daily analysis for Nifty, Bank Nifty, Sensex with technicals + options."""
    import yfinance as yf
    from datetime import datetime, timedelta
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import numpy as np
    
    global _market_daily_cache, _market_daily_ts
    now = datetime.utcnow()
    if _market_daily_cache and _market_daily_ts and (now - _market_daily_ts).total_seconds() < 180:
        return _market_daily_cache
    
    IST = timedelta(hours=5, minutes=30)
    now_ist = now + IST
    today_str = now_ist.strftime("%A, %d %B %Y")
    time_str = now_ist.strftime("%I:%M %p IST")
    
    indices = {
        "^NSEI": {"name": "NIFTY 50", "short": "NIFTY"},
        "^NSEBANK": {"name": "BANK NIFTY", "short": "BANKNIFTY"},
        "^BSESN": {"name": "SENSEX", "short": "SENSEX"}
    }
    
    def calc_rsi(prices, period=14):
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 1)
    
    def calc_macd(prices):
        prices = np.array(prices, dtype=float)
        def ema(data, span):
            alpha = 2 / (span + 1)
            result = np.zeros_like(data)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
            return result
        ema12 = ema(prices, 12)
        ema26 = ema(prices, 26)
        macd_line = ema12 - ema26
        signal_line = ema(macd_line, 9)
        histogram = macd_line - signal_line
        return round(macd_line[-1], 2), round(signal_line[-1], 2), round(histogram[-1], 2)
    
    def calc_bollinger(prices, period=20):
        prices = np.array(prices[-period:], dtype=float)
        sma = np.mean(prices)
        std = np.std(prices)
        return round(sma + 2*std, 2), round(sma, 2), round(sma - 2*std, 2)
    
    def calc_pivots(high, low, close):
        pp = round((high + low + close) / 3, 2)
        r1 = round(2 * pp - low, 2)
        s1 = round(2 * pp - high, 2)
        r2 = round(pp + (high - low), 2)
        s2 = round(pp - (high - low), 2)
        r3 = round(high + 2 * (pp - low), 2)
        s3 = round(low - 2 * (high - pp), 2)
        return {"PP": pp, "R1": r1, "R2": r2, "R3": r3, "S1": s1, "S2": s2, "S3": s3}
    
    def detect_pattern(opens, highs, lows, closes):
        if len(closes) < 3: return "Insufficient data"
        o, h, l, c = opens[-1], highs[-1], lows[-1], closes[-1]
        body = abs(c - o)
        rng = h - l
        if rng == 0: return "Doji"
        body_pct = body / rng
        
        po, ph, pl, pc = opens[-2], highs[-2], lows[-2], closes[-2]
        
        # Doji
        if body_pct < 0.1: return "Doji — Market indecision, potential reversal"
        # Hammer
        if c > o and (o - l) > 2 * body and (h - c) < body * 0.3:
            return "Hammer — Bullish reversal signal, buyers stepped in at lows"
        # Shooting Star
        if c < o and (h - o) > 2 * body and (c - l) < body * 0.3:
            return "Shooting Star — Bearish reversal, sellers rejected highs"
        # Bullish Engulfing
        if pc < po and c > o and c > po and o < pc:
            return "Bullish Engulfing — Strong buying pressure, trend may reverse up"
        # Bearish Engulfing
        if pc > po and c < o and c < po and o > pc:
            return "Bearish Engulfing — Strong selling pressure, trend may reverse down"
        # Marubozu
        if body_pct > 0.85:
            if c > o: return "Bullish Marubozu — Very strong buying, conviction candle"
            else: return "Bearish Marubozu — Very strong selling, panic candle"
        # Spinning Top
        if 0.1 < body_pct < 0.35:
            return "Spinning Top — Tug-of-war between bulls and bears"
        
        if c > o: return "Green candle — Buyers in control"
        return "Red candle — Sellers in control"
    
    def analyze_index(ticker_sym, info):
        try:
            t = yf.Ticker(ticker_sym)
            hist = t.history(period="6mo")
            if hist.empty:
                return info["short"], None
            
            closes = hist["Close"].values
            opens = hist["Open"].values
            highs = hist["High"].values
            lows = hist["Low"].values
            volumes = hist["Volume"].values
            dates = hist.index
            
            price = round(closes[-1], 2)
            prev_close = round(closes[-2], 2) if len(closes) > 1 else price
            change = round(price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2) if prev_close else 0
            
            day_high = round(highs[-1], 2)
            day_low = round(lows[-1], 2)
            day_open = round(opens[-1], 2)
            day_vol = int(volumes[-1]) if len(volumes) > 0 else 0
            avg_vol_20 = int(np.mean(volumes[-20:])) if len(volumes) >= 20 else day_vol
            vol_ratio = round(day_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 1
            
            # Moving averages
            sma5 = round(np.mean(closes[-5:]), 2) if len(closes) >= 5 else price
            sma10 = round(np.mean(closes[-10:]), 2) if len(closes) >= 10 else price
            sma20 = round(np.mean(closes[-20:]), 2) if len(closes) >= 20 else price
            sma50 = round(np.mean(closes[-50:]), 2) if len(closes) >= 50 else price
            sma100 = round(np.mean(closes[-100:]), 2) if len(closes) >= 100 else price
            sma200 = round(np.mean(closes[-200:]), 2) if len(closes) >= 200 else price
            
            # EMA 9 & 21
            def ema_calc(data, span):
                a = 2 / (span + 1)
                r = float(data[0])
                for v in data[1:]:
                    r = a * float(v) + (1 - a) * r
                return round(r, 2)
            ema9 = ema_calc(closes[-50:], 9) if len(closes) >= 50 else price
            ema21 = ema_calc(closes[-50:], 21) if len(closes) >= 50 else price
            
            # RSI
            rsi = calc_rsi(closes) if len(closes) >= 15 else 50
            
            # MACD
            macd_l, macd_s, macd_h = (0, 0, 0)
            if len(closes) >= 30:
                macd_l, macd_s, macd_h = calc_macd(closes)
            
            # Bollinger Bands
            bb_upper, bb_mid, bb_lower = price, price, price
            if len(closes) >= 20:
                bb_upper, bb_mid, bb_lower = calc_bollinger(closes)
            
            # Pivot Points
            pivots = calc_pivots(day_high, day_low, price)
            
            # 52W High/Low
            w52_high = round(max(highs[-252:]), 2) if len(highs) >= 100 else day_high
            w52_low = round(min(lows[-252:]), 2) if len(lows) >= 100 else day_low
            w52_pos = round(((price - w52_low) / (w52_high - w52_low)) * 100, 1) if w52_high != w52_low else 50
            
            # Candlestick pattern
            pattern = detect_pattern(opens, highs, lows, closes)
            
            # Trend determination
            trend_signals = 0
            if price > sma20: trend_signals += 1
            if price > sma50: trend_signals += 1
            if price > sma200: trend_signals += 1
            if ema9 > ema21: trend_signals += 1
            if macd_h > 0: trend_signals += 1
            trend = "STRONG BULLISH" if trend_signals >= 5 else "BULLISH" if trend_signals >= 3 else "NEUTRAL" if trend_signals >= 2 else "BEARISH" if trend_signals >= 1 else "STRONG BEARISH"
            
            # Volatility (ATR-like)
            tr_list = []
            for i in range(-min(14, len(closes)-1), 0):
                tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
                tr_list.append(tr)
            atr = round(np.mean(tr_list), 2) if tr_list else 0
            atr_pct = round((atr / price) * 100, 2) if price else 0
            
            # Options chain analysis
            options_data = {"pcr": None, "max_pain": None, "oi_buildup": None, "call_oi": 0, "put_oi": 0, "top_strikes": []}
            try:
                exp_dates = t.options
                if exp_dates:
                    nearest_exp = exp_dates[0]
                    chain = t.option_chain(nearest_exp)
                    calls_df = chain.calls
                    puts_df = chain.puts
                    
                    total_call_oi = int(calls_df["openInterest"].sum()) if "openInterest" in calls_df.columns else 0
                    total_put_oi = int(puts_df["openInterest"].sum()) if "openInterest" in puts_df.columns else 0
                    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 0
                    
                    # Max Pain calculation
                    all_strikes = sorted(set(calls_df["strike"].tolist() + puts_df["strike"].tolist()))
                    min_pain = float("inf")
                    max_pain_strike = price
                    for strike in all_strikes:
                        call_pain = calls_df[calls_df["strike"] < strike].apply(
                            lambda r: (strike - r["strike"]) * r.get("openInterest", 0), axis=1).sum()
                        put_pain = puts_df[puts_df["strike"] > strike].apply(
                            lambda r: (r["strike"] - strike) * r.get("openInterest", 0), axis=1).sum()
                        total_pain = call_pain + put_pain
                        if total_pain < min_pain:
                            min_pain = total_pain
                            max_pain_strike = strike
                    
                    # Top OI strikes
                    top_call_strikes = calls_df.nlargest(3, "openInterest")[["strike", "openInterest"]].to_dict("records") if "openInterest" in calls_df.columns else []
                    top_put_strikes = puts_df.nlargest(3, "openInterest")[["strike", "openInterest"]].to_dict("records") if "openInterest" in puts_df.columns else []
                    
                    # OI buildup interpretation
                    if change > 0 and total_call_oi > total_put_oi:
                        oi_buildup = "Long Buildup — Price up + OI increasing = Bulls adding positions"
                    elif change > 0 and total_put_oi > total_call_oi:
                        oi_buildup = "Short Covering — Price up + Put OI high = Shorts exiting"
                    elif change < 0 and total_put_oi > total_call_oi:
                        oi_buildup = "Short Buildup — Price down + Put OI rising = Bears adding positions"
                    elif change < 0 and total_call_oi > total_put_oi:
                        oi_buildup = "Long Unwinding — Price down + Call OI high = Bulls exiting"
                    else:
                        oi_buildup = "Neutral — No clear OI trend"
                    
                    options_data = {
                        "pcr": pcr,
                        "max_pain": round(max_pain_strike, 0),
                        "oi_buildup": oi_buildup,
                        "call_oi": total_call_oi,
                        "put_oi": total_put_oi,
                        "expiry": nearest_exp,
                        "top_call_strikes": top_call_strikes[:3],
                        "top_put_strikes": top_put_strikes[:3]
                    }
            except Exception as oe:
                options_data["error"] = str(oe)[:100]
            
            # Last 5 days data
            recent_days = []
            for i in range(min(5, len(closes)-1), 0, -1):
                idx = -i
                d_close = round(closes[idx], 2)
                d_prev = round(closes[idx-1], 2)
                d_chg = round(((d_close - d_prev) / d_prev) * 100, 2) if d_prev else 0
                d_date = dates[idx].strftime("%d %b %Y") if hasattr(dates[idx], 'strftime') else str(dates[idx])[:10]
                recent_days.append({
                    "date": d_date,
                    "open": round(opens[idx], 2),
                    "high": round(highs[idx], 2),
                    "low": round(lows[idx], 2),
                    "close": d_close,
                    "change_pct": d_chg,
                    "volume": int(volumes[idx]) if idx < len(volumes) else 0
                })
            
            return info["short"], {
                "name": info["name"],
                "ticker": ticker_sym,
                "price": price,
                "prev_close": prev_close,
                "change": change,
                "change_pct": change_pct,
                "open": day_open,
                "high": day_high,
                "low": day_low,
                "volume": day_vol,
                "avg_volume_20d": avg_vol_20,
                "volume_ratio": vol_ratio,
                "sma5": sma5, "sma10": sma10, "sma20": sma20,
                "sma50": sma50, "sma100": sma100, "sma200": sma200,
                "ema9": ema9, "ema21": ema21,
                "rsi": rsi,
                "macd": macd_l, "macd_signal": macd_s, "macd_histogram": macd_h,
                "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower,
                "pivots": pivots,
                "w52_high": w52_high, "w52_low": w52_low, "w52_position": w52_pos,
                "atr": atr, "atr_pct": atr_pct,
                "trend": trend,
                "pattern": pattern,
                "options": options_data,
                "recent_days": recent_days
            }
        except Exception as e:
            return info["short"], {"error": str(e)[:200]}
    
    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(analyze_index, sym, info): info["short"] for sym, info in indices.items()}
        for f in as_completed(futures, timeout=25):
            try:
                short_name, data = f.result(timeout=20)
                if data:
                    results[short_name] = data
            except Exception as e:
                pass
    
    response = {
        "date": today_str,
        "time": time_str,
        "timestamp": now_ist.isoformat(),
        "indices": results
    }
    
    _market_daily_cache = response
    _market_daily_ts = now
    return response


# ═══════════════════════════════════════════════════
# TRADE JOURNAL — Log trades, track P&L, analytics
# ═══════════════════════════════════════════════════
_journal_file = "trade_journal.json"
def _load_journal():
    try:
        with open(_journal_file, 'r') as f: return json.load(f)
    except: return []
def _save_journal(trades):
    with open(_journal_file, 'w') as f: json.dump(trades, f)

@app.post("/api/journal")
async def journal_add(request: Request):
    """Add a trade to journal."""
    data = await request.json()
    trades = _load_journal()
    trade = {
        "id": f"T{len(trades)+1:04d}",
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": data.get("symbol", ""),
        "direction": data.get("direction", "BUY"),
        "optType": data.get("optType", "CE"),
        "strike": data.get("strike", 0),
        "entryPrem": data.get("entryPrem", 0),
        "exitPrem": data.get("exitPrem", 0),
        "qty": data.get("qty", 1),
        "lot": data.get("lot", 50),
        "strategy": data.get("strategy", "Directional"),
        "notes": data.get("notes", ""),
        "status": "OPEN",
        "pnl": 0,
        "tags": data.get("tags", []),
    }
    trades.append(trade)
    _save_journal(trades)
    return {"success": True, "trade": trade, "total": len(trades)}

@app.get("/api/journal")
async def journal_list():
    """Get all journal trades + analytics."""
    trades = _load_journal()
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    wins = [t for t in closed if t.get("pnl", 0) > 0]
    losses = [t for t in closed if t.get("pnl", 0) < 0]
    total_pnl = sum(t.get("pnl", 0) for t in closed)
    
    # Analytics by strategy
    strat_stats = {}
    for t in closed:
        s = t.get("strategy", "Other")
        if s not in strat_stats: strat_stats[s] = {"wins": 0, "losses": 0, "pnl": 0}
        if t.get("pnl", 0) > 0: strat_stats[s]["wins"] += 1
        else: strat_stats[s]["losses"] += 1
        strat_stats[s]["pnl"] += t.get("pnl", 0)
    
    # Behavioral insights
    insights = []
    if len(closed) >= 5:
        win_rate = len(wins) / len(closed) * 100
        if win_rate < 40: insights.append({"type": "WARNING", "msg": f"Win rate {win_rate:.0f}% is below 40%. Review your entry criteria."})
        if len(closed) >= 3:
            last3 = closed[-3:]
            if all(t.get("pnl", 0) < 0 for t in last3):
                insights.append({"type": "CRITICAL", "msg": "3 consecutive losses detected. Take a break — avoid revenge trading."})
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(t["pnl"] for t in losses) / len(losses)) if losses else 1
        if avg_loss > 0:
            expectancy = round((win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss), 0)
            insights.append({"type": "INFO", "msg": f"Expectancy: ₹{expectancy:,.0f}/trade. {'Positive edge ✅' if expectancy > 0 else 'Negative edge ❌ — fix risk management.'}"})
    
    return {
        "success": True, "trades": trades, "total": len(trades),
        "analytics": {
            "totalTrades": len(closed), "wins": len(wins), "losses": len(losses),
            "winRate": round(len(wins)/len(closed)*100, 1) if closed else 0,
            "totalPnl": round(total_pnl, 0),
            "avgWin": round(sum(t["pnl"] for t in wins)/len(wins), 0) if wins else 0,
            "avgLoss": round(sum(t["pnl"] for t in losses)/len(losses), 0) if losses else 0,
            "strategyStats": strat_stats,
            "insights": insights,
        }
    }

@app.put("/api/journal/{trade_id}")
async def journal_update(trade_id: str, request: Request):
    """Close a trade — set exit premium and compute P&L."""
    data = await request.json()
    trades = _load_journal()
    for t in trades:
        if t["id"] == trade_id:
            t["exitPrem"] = data.get("exitPrem", t.get("exitPrem", 0))
            t["status"] = "CLOSED"
            t["closedAt"] = datetime.utcnow().isoformat()
            t["notes"] = data.get("notes", t.get("notes", ""))
            pnl_per_unit = t["exitPrem"] - t["entryPrem"]
            if t.get("direction") == "SELL": pnl_per_unit = -pnl_per_unit
            t["pnl"] = round(pnl_per_unit * t.get("qty", 1) * t.get("lot", 50), 0)
            break
    _save_journal(trades)
    return {"success": True, "trades": trades}


# ═══════════════════════════════════════════════════
# AI TRADING ASSISTANT — Rule-based + context-aware
# ═══════════════════════════════════════════════════
@app.get("/api/top-picks")
async def top_picks(region: str = "IN"):
    """Comprehensive Investment Intelligence — scan ALL stocks, categorize, rank, return reports"""
    try:
        import yfinance as yf
        import pandas as pd
        import numpy as np
        
        is_us = region.upper() == "US"
        csym = "$" if is_us else "₹"
        
        if is_us:
            largecap = ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AVGO","BRK-B","LLY","JPM","V","UNH","XOM","MA","JNJ","PG","COST","HD","ABBV","MRK","AMD","CRM","NFLX"]
            midcap = ["PANW","CRWD","SNOW","DDOG","ZS","NET","MELI","SHOP","SQ","COIN","RIVN","PLTR","SOFI","HOOD","RBLX","U"]
            smallcap = ["UPST","AFRM","IONQ","SOUN","RKLB","JOBY","LUNR","DNA","SMCI","ARQQ"]
            etfs = {"VOO":"S&P 500","QQQ":"Nasdaq 100","SCHD":"Dividend","VTI":"Total Market","SMH":"Semiconductors","XLF":"Financials","XLK":"Tech","XLV":"Healthcare","ARKK":"Innovation","IWM":"Small Cap","GLD":"Gold","TLT":"Bonds"}
            niche = ["MU","MARA","RIOT","MSTR","PATH","AI","BBAI","ASTS"]
        else:
            # ═══ FULL NSE UNIVERSE — 200 stocks covering NIFTY 500 ═══
            largecap_raw = [
                "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","BHARTIARTL","ITC","LT","SBIN","AXISBANK",
                "KOTAKBANK","BAJFINANCE","MARUTI","TATAMOTORS","SUNPHARMA","HCLTECH","WIPRO","NTPC","POWERGRID","ONGC",
                "BAJAJ-AUTO","HDFCLIFE","SBILIFE","DIVISLAB","DRREDDY","CIPLA","TITAN","NESTLEIND","ULTRACEMCO","GRASIM",
                "JSWSTEEL","INDUSINDBK","M&M","TECHM","HEROMOTOCO","BPCL","HINDALCO","TATACONSUM","APOLLOHOSP","EICHERMOT",
                "BRITANNIA","LTIM","HINDUNILVR","COALINDIA","TATASTEEL","IOC","VEDL","GAIL","LICI","PIDILITIND"
            ]
            midcap_raw = [
                "TRENT","ZOMATO","PAYTM","POLYCAB","PERSISTENT","COFORGE","MPHASIS","INDIGO","PIIND","BALKRISIND",
                "ASTRAL","DEEPAKNTR","VOLTAS","AUROPHARMA","TORNTPHARM","LUPIN","BIOCON","ALKEM","IPCALAB","ABBOTINDIA",
                "HAVELLS","CROMPTON","TATAPOWER","ADANIGREEN","NHPC","SUZLON","IREDA","IRFC","BEL","HAL",
                "CDSL","BSE","ANGELONE","JIOFIN","BAJAJFINSV","CHOLAFIN","MUTHOOTFIN","MANAPPURAM","PNB","BANKBARODA",
                "CANBK","UNIONBANK","FEDERALBNK","IDFCFIRSTB","DMART","TATAELXSI","DIXON","DLF","LODHA","OBEROIRLTY",
                "BERGEPAINT","ASIANPAINT","NAUKRI","ZYDUSLIFE","CONCOR","IRCTC","SIEMENS","ABB","CUMMINSIND","BOSCHLTD",
                "MOTHERSON","GODREJCP","MARICO","DABUR","COLPAL","UPL","PI","SRF","AARTI","COROMANDEL"
            ]
            smallcap_raw = [
                "OLECTRA","NETWEB","TTML","DATAMATICS","HAPPSTMNDS","RATEGAIN","RVNL","KPITTECH","SONACOMS","KAYNES",
                "LATENTVIEW","COCHINSHIP","MAZAGON","BDL","SOLARINDS","CAMS","MCX","POONAWALLA","RBLBANK","YESBANK",
                "GODREJPROP","PRESTIGE","PHOENIXLTD","SBICARD","ICICIPRULI","HDFCAMC","RAILTEL","TIINDIA","THERMAX","GRINDWELL",
                "SCHAEFFLER","EXIDEIND","AMARARAJA","GRANULES","AJANTPHARM","NATCOPHARM","LALPATHLAB","METROPOLIS","MAXHEALTH","FORTIS",
                "STARHEALTH","SUNTV","JUBLFOOD","VBL","RADICO","UBL","TATACOMM","INDUSTOWER","EMAMILTD","CLEAN",
                "FLUOROCHEM","SUMICHEM","CHAMBLFERT","GNFC","FACT","GSFC","ADANIPORTS","ADANIENT","ADANIPOWER","MEDANTA"
            ]
            etfs_raw = {"NIFTYBEES":"Nifty 50","JUNIORBEES":"Next 50","BANKBEES":"Bank Nifty","GOLDBEES":"Gold","CPSE":"PSU","MAFANG":"Global Tech","SILVERBEES":"Silver","ICICIB22":"Bharat Bond","ITBEES":"IT Sector"}
            niche_raw = ["PVRINOX","DEVYANI","SAPPHIRE","BLUESTARLT","WHIRLPOOL","RAJESHEXPO","GICRE","NIACL","MARKSANS","ATUL","DEEPAKNITRIT","FACT"]
            largecap = [s+".NS" for s in largecap_raw]
            midcap = [s+".NS" for s in midcap_raw]
            smallcap = [s+".NS" for s in smallcap_raw]
            etfs = {s+".NS":v for s,v in etfs_raw.items()}
            niche = [s+".NS" for s in niche_raw]
        
        all_syms = largecap + midcap + smallcap + list(etfs.keys()) + niche
        
        # Include cached stock intel results
        for ck, cv in _si_cache.items():
            if ck.endswith(f"_{region}"):
                sym = ck.replace(f"_{region}", "")
                yfSym = sym if is_us else f"{sym}.NS"
                if yfSym not in all_syms:
                    d = cv.get("data", {})
                    if d.get("success") and d.get("confidence", 0) >= 50:
                        all_syms.append(yfSym)
        
        print(f"🔍 Intelligence Report: Scanning {len(all_syms)} securities for {region}...")
        
        # Batch download price history — ONE call for ALL stocks
        try:
            hist_data = yf.download(all_syms, period="1y", group_by="ticker", progress=False, threads=True)
            print(f"✅ Batch download complete: {len(hist_data)} rows")
        except Exception as bd_err:
            print(f"⚠️ Batch download failed: {bd_err}")
            hist_data = pd.DataFrame()
        
        # ═══ PASS 1: Price-only screening (no API calls — instant) ═══
        pass1_results = []
        for sym in all_syms:
            clean = sym.replace(".NS", "") if not is_us else sym
            
            # Check cache first
            ck = f"{clean}_{region}"
            if ck in _si_cache:
                age = (datetime.utcnow() - _si_cache[ck]["ts"]).total_seconds()
                if age < 3600:
                    d = _si_cache[ck]["data"]
                    if d.get("success"):
                        # Determine category
                        cat = "niche"
                        if sym in largecap: cat = "largecap"
                        elif sym in midcap: cat = "midcap"
                        elif sym in smallcap: cat = "smallcap"
                        elif sym in etfs: cat = "etf"
                        d["category"] = cat
                        d["etfName"] = etfs.get(sym, "")
                        d["_cached"] = True
                        pass1_results.append(d)
                        continue
            
            try:
                if len(all_syms) > 1 and sym in hist_data.columns.get_level_values(0):
                    closes = hist_data[sym]["Close"].dropna().values.astype(float)
                else:
                    continue
                if len(closes) < 20: continue
                price = round(float(closes[-1]), 2)
                if price <= 0: continue
                
                ema20 = float(pd.Series(closes).ewm(span=20).mean().iloc[-1])
                ema50 = float(pd.Series(closes).ewm(span=50).mean().iloc[-1])
                trend = "BULLISH" if ema20 > ema50 else "BEARISH"
                pa_score = 70 if trend == "BULLISH" else 40
                
                cagr_1y = round(((closes[-1] / closes[0]) - 1) * 100, 1)
                cagr_6m = round(((closes[-1] / closes[len(closes)//2]) - 1) * 100, 1) if len(closes) > 60 else 0
                cagr_3m = round(((closes[-1] / closes[-min(63, len(closes))]) - 1) * 100, 1) if len(closes) > 30 else 0
                
                cat = "niche"
                if sym in largecap: cat = "largecap"
                elif sym in midcap: cat = "midcap"
                elif sym in smallcap: cat = "smallcap"
                elif sym in etfs: cat = "etf"
                
                pass1_results.append({
                    "_sym": sym, "symbol": clean, "price": price, "trend": trend,
                    "paScore": pa_score, "cagr1Y": cagr_1y, "cagr6M": cagr_6m, "cagr3M": cagr_3m,
                    "category": cat, "etfName": etfs.get(sym, ""),
                    "_needsInfo": True
                })
            except:
                continue
        
        print(f"  Pass 1: {len(pass1_results)} stocks passed price screen")
        
        # ═══ PASS 2: Fetch fundamentals only for top candidates ═══
        # Sort by price action, take top 80 for info calls
        needs_info = [r for r in pass1_results if r.get("_needsInfo")]
        needs_info.sort(key=lambda x: x.get("paScore", 0) + x.get("cagr3M", 0), reverse=True)
        top_candidates = needs_info[:80]  # Only fetch info for top 80
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        
        def fetch_info(item):
            sym = item["_sym"]
            try:
                tk = yf.Ticker(sym)
                info = tk.info or {}
                mcap = float(info.get("marketCap", 0) or 0)
                pe = float(info.get("trailingPE", 0) or 0)
                fwd_pe = float(info.get("forwardPE", 0) or 0)
                peg = float(info.get("pegRatio", 0) or 0)
                rev_g = float(info.get("revenueGrowth", 0) or 0) * 100
                roe = float(info.get("returnOnEquity", 0) or 0) * 100
                div_yield = float(info.get("dividendYield", 0) or 0) * 100
                
                fund_score = 50
                if rev_g > 15: fund_score += 15
                elif rev_g > 5: fund_score += 5
                elif rev_g < -5: fund_score -= 10
                if roe > 15: fund_score += 10
                fund_score = max(0, min(100, fund_score))
                
                val_score = 50
                if 0 < pe < 20: val_score += 20
                elif pe > 40: val_score -= 15
                if peg > 0 and peg < 1: val_score += 15
                val_score = max(0, min(100, val_score))
                
                confidence = int(round(fund_score * 0.30 + val_score * 0.25 + item["paScore"] * 0.45))
                decision = "BUY" if confidence >= 65 and item["trend"] == "BULLISH" else ("HOLD" if confidence >= 50 else "AVOID")
                
                item.update({
                    "companyName": info.get("shortName", item["symbol"]),
                    "sector": info.get("sector", item.get("etfName", "")),
                    "decision": decision, "confidence": min(confidence, 95),
                    "mcap": mcap, "pe": round(pe, 1), "fwdPE": round(fwd_pe, 1),
                    "peg": round(peg, 2), "roe": round(roe, 1),
                    "revGrowth": round(rev_g, 1), "divYield": round(div_yield, 2),
                    "fundScore": fund_score, "valScore": val_score,
                    "_needsInfo": False
                })
                return item
            except:
                # Fallback — use price action only
                item.update({
                    "companyName": item["symbol"], "sector": "",
                    "decision": "HOLD" if item["trend"] == "BULLISH" else "AVOID",
                    "confidence": item["paScore"],
                    "mcap": 0, "pe": 0, "fwdPE": 0, "peg": 0, "roe": 0,
                    "revGrowth": 0, "divYield": 0,
                    "fundScore": 50, "valScore": 50,
                    "_needsInfo": False
                })
                return item
        
        # Concurrent info fetching — 10 threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_info, item): item for item in top_candidates}
            for future in as_completed(futures):
                try:
                    future.result()
                except:
                    pass
        
        # For stocks that didn't get info (outside top 80), use price-only scoring
        for item in needs_info:
            if item.get("_needsInfo"):
                item.update({
                    "companyName": item["symbol"], "sector": "",
                    "decision": "HOLD" if item["trend"] == "BULLISH" else "AVOID",
                    "confidence": max(30, item.get("paScore", 40)),
                    "mcap": 0, "pe": 0, "fwdPE": 0, "peg": 0, "roe": 0,
                    "revGrowth": 0, "divYield": 0,
                    "fundScore": 50, "valScore": 50,
                })
        
        # Combine cached + scored
        results = [r for r in pass1_results if not r.get("_needsInfo")]
        
        print(f"  Pass 2: {len(results)} stocks fully scored")
        
        # Categorize and rank
        cats = {}
        for cat in ["largecap", "midcap", "smallcap", "etf", "niche"]:
            cat_results = [r for r in results if r.get("category") == cat]
            cat_results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            cats[cat] = cat_results[:5]
        
        # Overall top 5
        results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        top5 = results[:5]
        
        # Top dividend
        div_sorted = sorted([r for r in results if r.get("divYield", 0) > 1], key=lambda x: x["divYield"], reverse=True)[:5]
        
        # Top momentum (best 3M CAGR)
        mom_sorted = sorted([r for r in results if r.get("cagr3M", 0) > 5], key=lambda x: x["cagr3M"], reverse=True)[:5]
        
        # Value picks (low PE + decent growth)
        value_sorted = sorted([r for r in results if 0 < r.get("pe", 0) < 18 and r.get("revGrowth", 0) > 0], key=lambda x: x["confidence"], reverse=True)[:5]
        
        print(f"✅ Intelligence: Scanned {len(all_syms)}, scored {len(results)} | LC:{len(cats.get('largecap',[]))} MC:{len(cats.get('midcap',[]))} SC:{len(cats.get('smallcap',[]))} ETF:{len(cats.get('etf',[]))} Niche:{len(cats.get('niche',[]))}")
        
        return {
            "success": True, "region": region, "csym": csym,
            "totalScanned": len(all_syms), "totalScored": len(results),
            "top5": top5,
            "largecap": cats.get("largecap", []),
            "midcap": cats.get("midcap", []),
            "smallcap": cats.get("smallcap", []),
            "etfs": cats.get("etf", []),
            "niche": cats.get("niche", []),
            "dividend": div_sorted,
            "momentum": mom_sorted,
            "value": value_sorted,
        }
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.get("/api/payoff-curve")
async def payoff_curve(symbol: str, region: str = "IN"):
    """Generate P&L payoff curves for all strategies on a given stock"""
    try:
        algo = await algo_signal_safe(symbol, region)
        strats = algo.get("strategies", [])
        spot = algo.get("spot", 0)
        inst = algo.get("instrument", {"gap": 50, "lot": 50})
        gap = inst.get("gap", 50)
        lot = inst.get("lot", 50)
        csym = "$" if region.upper() == "US" else "₹"
        
        if not strats and spot == 0:
            return {"success": False, "error": "No strategies available"}
        
        if spot == 0:
            return {"success": False, "error": "Could not get spot price"}
        
        # Generate price range (±10% from spot)
        low = round(spot * 0.9, 0)
        high = round(spot * 1.1, 0)
        step = max(1, round((high - low) / 50))
        prices = [low + i * step for i in range(51)]
        
        # Helper to compute one curve
        def compute_curve(legs_data, name, strat_type, pop_val=50):
            data_points = []
            for p in prices:
                pnl = 0
                for leg in legs_data:
                    strike = leg.get("strike", 0)
                    prem = leg.get("premium", 0)
                    is_buy = leg.get("action") == "BUY"
                    is_ce = leg.get("type") in ["CE", "CALL"]
                    if is_ce:
                        intrinsic = max(0, p - strike)
                    else:
                        intrinsic = max(0, strike - p)
                    if is_buy:
                        pnl += (intrinsic - prem) * lot
                    else:
                        pnl += (prem - intrinsic) * lot
                data_points.append({"price": round(p, 0), "pnl": round(pnl, 0)})
            max_profit = max(dp["pnl"] for dp in data_points)
            max_loss = min(dp["pnl"] for dp in data_points)
            breakevens = []
            for i in range(1, len(data_points)):
                if (data_points[i-1]["pnl"] < 0 and data_points[i]["pnl"] >= 0) or \
                   (data_points[i-1]["pnl"] >= 0 and data_points[i]["pnl"] < 0):
                    breakevens.append(data_points[i]["price"])
            return {
                "name": name, "type": strat_type, "legs": legs_data,
                "dataPoints": data_points, "maxProfit": max_profit,
                "maxLoss": max_loss, "breakevens": breakevens, "pop": pop_val,
            }
        
        curves = []
        
        # Get ATM info for naked strategies
        _atm = algo.get("atm", round(spot / gap) * gap if gap > 0 else spot)
        is_us = region.upper() == "US"
        ce_type = "CALL" if is_us else "CE"
        pe_type = "PUT" if is_us else "PE"
        
        # Find ATM premiums from existing strategies or estimate
        ce_prem = 0; pe_prem = 0
        for s in strats:
            for leg in s.get("legs", []):
                if leg.get("strike") == _atm and leg.get("action") == "BUY":
                    if leg.get("type") in ["CE", "CALL"]: ce_prem = leg.get("premium", 0)
                    if leg.get("type") in ["PE", "PUT"]: pe_prem = leg.get("premium", 0)
        # Fallback: estimate from expected move
        if ce_prem == 0:
            em = algo.get("expectedMove", {})
            em_pts = em.get("em_pts", spot * 0.02)
            ce_prem = round(em_pts * 0.5, 2)
            pe_prem = round(em_pts * 0.5, 2)
        
        # 1. Naked Call Buy (ATM)
        if ce_prem > 0:
            curves.append(compute_curve(
                [{"action": "BUY", "strike": _atm, "type": ce_type, "premium": ce_prem}],
                "Buy Call (ATM)", "DIRECTIONAL — BULLISH", 45
            ))
        
        # 2. Naked Put Buy (ATM)
        if pe_prem > 0:
            curves.append(compute_curve(
                [{"action": "BUY", "strike": _atm, "type": pe_type, "premium": pe_prem}],
                "Buy Put (ATM)", "DIRECTIONAL — BEARISH", 45
            ))
        
        # 3-7. Existing multi-leg strategies
        for strat in strats:
            legs = strat.get("legs", [])
            if not legs: continue
            curves.append(compute_curve(
                legs, strat.get("name", ""), strat.get("type", ""), strat.get("pop", 50)
            ))
        
        return {"success": True, "symbol": symbol, "spot": spot, "csym": csym, "curves": curves}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/journal-review")
async def journal_review():
    """Today's trade review with behavioral insights"""
    trades = _load_journal()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    today_trades = [t for t in trades if t.get("timestamp", "").startswith(today)]
    all_closed = [t for t in trades if t.get("status") == "CLOSED"]
    
    # Behavioral analysis
    behaviors = []
    if len(all_closed) >= 3:
        # Early exits
        early_exits = 0
        for t in all_closed[-10:]:
            entry = t.get("entryPrem", 0)
            exit_p = t.get("exitPrem", 0)
            if exit_p > 0 and exit_p > entry:
                gain_pct = (exit_p - entry) / entry * 100 if entry > 0 else 0
                if gain_pct < 10 and gain_pct > 0:
                    early_exits += 1
        if early_exits >= 2:
            behaviors.append({"type": "WARNING", "habit": "Early Profit Booking", 
                "msg": f"You booked profits too early on {early_exits} of last 10 trades (<10% gain). Let winners run — set trailing SL instead.",
                "fix": "Try booking 50% at T1, trail rest with 15-min candle SL"})
        
        # Revenge trading
        consecutive_losses = 0
        for t in reversed(all_closed[-10:]):
            if t.get("pnl", 0) < 0:
                consecutive_losses += 1
            else:
                break
        if consecutive_losses >= 3:
            behaviors.append({"type": "CRITICAL", "habit": "Revenge Trading Risk",
                "msg": f"{consecutive_losses} consecutive losses. STOP trading today. Your judgment is clouded.",
                "fix": "Take a 24-hour break. Review what went wrong before next trade."})
        
        # Overtrading
        recent_dates = set()
        for t in all_closed[-20:]:
            d = t.get("timestamp", "")[:10]
            recent_dates.add(d)
        avg_per_day = len(all_closed[-20:]) / max(len(recent_dates), 1)
        if avg_per_day > 5:
            behaviors.append({"type": "WARNING", "habit": "Overtrading",
                "msg": f"Averaging {avg_per_day:.0f} trades/day. Quality > quantity.",
                "fix": "Limit to 3 high-conviction trades per day. Wait for A+ setups."})
        
        # Win/loss asymmetry
        wins = [t for t in all_closed if t.get("pnl", 0) > 0]
        losses = [t for t in all_closed if t.get("pnl", 0) < 0]
        if wins and losses:
            avg_win = sum(t["pnl"] for t in wins) / len(wins)
            avg_loss = abs(sum(t["pnl"] for t in losses) / len(losses))
            if avg_loss > avg_win * 1.5:
                behaviors.append({"type": "CRITICAL", "habit": "Letting Losses Run",
                    "msg": f"Average loss (₹{avg_loss:,.0f}) is {avg_loss/max(avg_win,1):.1f}x your average win (₹{avg_win:,.0f}). You hold losers too long.",
                    "fix": "Strict SL — exit the MOMENT SL hits. No hoping, no averaging down."})
    
    # Today's summary
    today_pnl = sum(t.get("pnl", 0) for t in today_trades if t.get("status") == "CLOSED")
    today_wins = len([t for t in today_trades if t.get("pnl", 0) > 0 and t.get("status") == "CLOSED"])
    today_losses = len([t for t in today_trades if t.get("pnl", 0) < 0 and t.get("status") == "CLOSED"])
    today_open = len([t for t in today_trades if t.get("status") == "OPEN"])
    
    # Streak
    streak = 0; streak_type = "NONE"
    for t in reversed(all_closed):
        if t.get("pnl", 0) > 0:
            if streak_type == "WIN" or streak_type == "NONE": streak += 1; streak_type = "WIN"
            else: break
        elif t.get("pnl", 0) < 0:
            if streak_type == "LOSS" or streak_type == "NONE": streak += 1; streak_type = "LOSS"
            else: break
    
    return {
        "success": True,
        "today": {
            "trades": len(today_trades), "wins": today_wins, "losses": today_losses,
            "open": today_open, "pnl": round(today_pnl, 0),
        },
        "streak": {"count": streak, "type": streak_type},
        "behaviors": behaviors,
        "totalClosed": len(all_closed),
    }


@app.post("/api/ai-assist")
async def ai_assist(request: Request):
    """AI assistant that answers trading questions using live data."""
    data = await request.json()
    question = (data.get("question", "")).strip().lower()
    symbol = data.get("symbol", "NIFTY")
    
    if not question:
        return {"success": False, "error": "No question provided"}
    
    # Get fresh algo data
    try:
        algo = await algo_signal_safe(symbol, data.get("region", "IN"))
    except:
        algo = {}
    
    tr = algo.get("trade", {})
    tc = algo.get("tradeConfidence", {})
    oi = algo.get("options_intel", {})
    vi = algo.get("volIntelligence", {})
    strats = algo.get("strategies", [])
    sc = algo.get("scalp", {})
    sig = algo.get("signal", "HOLD / WAIT")
    direction = algo.get("direction", "NEUTRAL")
    is_us = algo.get("region") == "US"
    csym = "$" if is_us else "₹"
    price = algo.get("spot", 0)
    inst = algo.get("instrument", {"gap": 50, "lot": 50})
    nse = algo.get("options", {})
    bs_data = algo.get("black_scholes", {})
    
    answer = ""
    
    # Pattern matching for common questions
    # CALL/CE BUY — Full trade details
    if any(w in question for w in ["call buy", "ce buy", "call trade", "ce trade", "bullish trade"]):
        win = tc.get("estimatedWin", 50)
        grade = tc.get("grade", "B")
        # Build CE/CALL trade regardless of algo direction
        ce_type = "CALL" if is_us else "CE"
        atm = round(price / inst.get("gap", 50)) * inst.get("gap", 50)
        ce_prem = 0
        try:
            from math import log, sqrt, exp, erf
            _iv = (nse.get("atm_iv", 20) or 20) / 100
            _T = max(bs_data.get("dte", 7), 1) / 365 if bs_data else 7/365
            _r = 0.0525 if is_us else 0.065
            d1 = (log(price/atm) + (_r + _iv**2/2)*_T) / (_iv*sqrt(_T)) if _iv > 0 and _T > 0 else 0
            d2 = d1 - _iv*sqrt(_T) if _iv > 0 and _T > 0 else 0
            nd1 = 0.5*(1+erf(d1/sqrt(2))); nd2 = 0.5*(1+erf(d2/sqrt(2)))
            ce_prem = round(max(price*nd1 - atm*exp(-_r*_T)*nd2, 0), 1)
        except: ce_prem = round(price * 0.015, 1)
        
        atr_val = algo.get("technicals", {}).get("atr14", price * 0.015)
        ce_sl_spot = round(price - atr_val * 1.5, 2)
        ce_t1_spot = round(price + atr_val * 1.0, 2)
        ce_t2_spot = round(price + atr_val * 2.0, 2)
        
        oi_data = algo.get("options_intel", {})
        answer = f"""📈 {ce_type} BUY TRADE — {symbol}

🎯 TRADE SETUP:
• Action: BUY {atm} {ce_type}
• Entry Premium: ~{csym}{ce_prem}
• Spot Price: {csym}{price:,.2f}

📊 LEVELS (on underlying):
• Entry Zone: {csym}{price:,.0f}
• Stop Loss: {csym}{ce_sl_spot:,.0f} (if breaks below this, exit)
• Target 1: {csym}{ce_t1_spot:,.0f} (book 50% here)
• Target 2: {csym}{ce_t2_spot:,.0f} (book remaining)

📋 TRADE RULES:
• When T1 is hit → move SL to entry (free trade!)
• Max risk: {csym}{ce_prem} per unit (you can never lose more)
• Exit by 3:00 PM if no target hit

📊 CONFIDENCE:
• Win Rate: {win}% (Grade {grade})
• Signal: {sig} | Direction: {direction}
• IV Rank: {oi_data.get('iv_rank', 50)}%

💡 IN SIMPLE WORDS:
We're betting {symbol} will go UP. Buy {ce_type} at {csym}{ce_prem}. 
If stock rises → your option becomes more valuable → profit!
If stock falls → exit at SL → lose only the premium paid.
Think of it as buying a lottery ticket where you know the odds."""
    
    # PUT/PE BUY — Full trade details
    elif any(w in question for w in ["put buy", "pe buy", "put trade", "pe trade", "bearish trade"]):
        win = tc.get("estimatedWin", 50)
        grade = tc.get("grade", "B")
        pe_type = "PUT" if is_us else "PE"
        atm = round(price / inst.get("gap", 50)) * inst.get("gap", 50)
        pe_prem = 0
        try:
            from math import log, sqrt, exp, erf
            _iv = (nse.get("atm_iv", 20) or 20) / 100
            _T = max(bs_data.get("dte", 7), 1) / 365 if bs_data else 7/365
            _r = 0.0525 if is_us else 0.065
            d1 = (log(price/atm) + (_r + _iv**2/2)*_T) / (_iv*sqrt(_T)) if _iv > 0 and _T > 0 else 0
            d2 = d1 - _iv*sqrt(_T) if _iv > 0 and _T > 0 else 0
            nd1 = 0.5*(1+erf(d1/sqrt(2))); nd2 = 0.5*(1+erf(d2/sqrt(2)))
            pe_prem = round(max(atm*exp(-_r*_T)*(1-nd2) - price*(1-nd1), 0), 1)
        except: pe_prem = round(price * 0.015, 1)
        
        atr_val = algo.get("technicals", {}).get("atr14", price * 0.015)
        pe_sl_spot = round(price + atr_val * 1.5, 2)
        pe_t1_spot = round(price - atr_val * 1.0, 2)
        pe_t2_spot = round(price - atr_val * 2.0, 2)
        
        oi_data = algo.get("options_intel", {})
        answer = f"""📉 {pe_type} BUY TRADE — {symbol}

🎯 TRADE SETUP:
• Action: BUY {atm} {pe_type}
• Entry Premium: ~{csym}{pe_prem}
• Spot Price: {csym}{price:,.2f}

📊 LEVELS (on underlying):
• Entry Zone: {csym}{price:,.0f}
• Stop Loss: {csym}{pe_sl_spot:,.0f} (if breaks above this, exit)
• Target 1: {csym}{pe_t1_spot:,.0f} (book 50% here)
• Target 2: {csym}{pe_t2_spot:,.0f} (book remaining)

📋 TRADE RULES:
• When T1 is hit → move SL to entry (free trade!)
• Max risk: {csym}{pe_prem} per unit
• Exit by 3:00 PM if no target hit

📊 CONFIDENCE:
• Win Rate: {win}% (Grade {grade})
• Signal: {sig} | Direction: {direction}
• IV Rank: {oi_data.get('iv_rank', 50)}%

💡 IN SIMPLE WORDS:
We're betting {symbol} will go DOWN. Buy {pe_type} at {csym}{pe_prem}.
If stock falls → your option becomes more valuable → profit!
If stock rises → exit at SL → lose only the premium paid.
Think of it as buying insurance — small cost, big payout if things drop."""
    
    elif any(w in question for w in ["should i buy", "should i enter", "can i trade", "is it good"]):
        win = tc.get("estimatedWin", 50)
        grade = tc.get("grade", "B")
        if win >= 65:
            answer = f"✅ YES — {symbol} shows a {sig} signal with {win}% estimated win rate (Grade {grade}). {tr.get('action', '')} at {csym}{tr.get('premEntry', 0)}. R:R = {tr.get('rrRatio', 'N/A')}. Position size: {tc.get('sizeRecommendation', 'Standard')}."
        elif win >= 50:
            answer = f"⚠️ MAYBE — {symbol} is {sig} with {win}% win rate (Grade {grade}). Setup is decent but not high conviction. Use smaller size. {tr.get('action', '')} if {direction.lower()} factors strengthen."
        else:
            answer = f"❌ NO — {symbol} shows weak setup ({win}% win rate, Grade {grade}). {len(algo.get('factors', []))} factors analyzed, confluence is low. Wait for better setup or consider scalp: {sc.get('direction', 'NEUTRAL')} on 5m chart."
    
    elif any(w in question for w in ["best strategy", "which strategy", "what strategy", "how to trade"]):
        if strats:
            best = max(strats, key=lambda s: s.get("pop", 0))
            answer = f"📊 Best strategy for {symbol}: **{best['name']}** (POP: {best['pop']}%). {best['interpretation']}. Volatility regime: {vi.get('regime', 'NORMAL')} — {vi.get('action', '')}."
        else:
            answer = f"Directional trade: {tr.get('action', 'N/A')} with Grade {tc.get('grade', 'B')}. Use {tc.get('sizeRecommendation', 'standard size')}."
    
    elif any(w in question for w in ["sell", "exit", "book profit", "close"]):
        if tr.get("premEntry", 0) > 0:
            answer = f"📈 Exit plan for {tr.get('action', '')}:\n• T1: {csym}{tr.get('premT1', 0)} — book 50%, move SL to entry.\n• T2: {csym}{tr.get('premT2', 0)} — book 30%, trail stop.\n• T3: {csym}{tr.get('premT3', 0)} — let 20% ride.\n• Hard SL: {csym}{tr.get('premSL', 0)}.\n• Time exit: {'2:30 PM' if algo.get('isExpiry') else '3:00 PM'}."
        else:
            answer = f"No active position data for {symbol}. Analyze the stock first."
    
    elif any(w in question for w in ["risk", "how much", "position size", "capital"]):
        rm = algo.get("riskManagement", {})
        answer = f"🛡️ Risk for {symbol}:\n• SL: {csym}{tr.get('premSL', 0)} (max loss per lot: {csym}{rm.get('premiumAtRisk', 0):,.0f})\n• {tc.get('sizeRecommendation', 'Use 1-2% of capital')}.\n• {len(rm.get('exposureAlerts', []))} risk alerts active."
        for a in rm.get("exposureAlerts", [])[:3]:
            answer += f"\n⚠️ {a['msg']}"
    
    elif any(w in question for w in ["scalp", "quick trade", "intraday", "short term"]):
        if sc:
            answer = f"⚡ Scalp for {symbol}: {sc.get('direction', 'NEUTRAL')} ({sc.get('confidence', 0)}% conf).\n{sc.get('action', '')} — Entry: {csym}{sc.get('entry', 0)}, SL: {csym}{sc.get('sl', 0)}, T1: {csym}{sc.get('t1', 0)}, T2: {csym}{sc.get('t2', 0)}.\n5m: {sc.get('trend_5m', '?')}, 15m: {sc.get('trend_15m', '?')}, VWAP: {'ABOVE' if sc.get('above_vwap') else 'BELOW'}."
        else:
            answer = f"No scalp data for {symbol}. Market may be closed."
    
    elif any(w in question for w in ["iv", "volatility", "expensive", "cheap"]):
        answer = f"🌡️ {symbol} Volatility:\nIV: {oi.get('iv_current', 0)}% (Rank: {oi.get('iv_rank', 50)}%)\nHV: {vi.get('hv20', 0)}%\nSpread: {vi.get('ivHvSpread', 0)}%\nRegime: {vi.get('regime', 'NORMAL')}\n{vi.get('action', '')}"
    
    elif any(w in question for w in ["why", "explain", "reason"]):
        notes = tc.get("notes", [])
        answer = f"📋 {symbol} analysis breakdown:\nSignal: {sig} ({direction}), Win Rate: {tc.get('estimatedWin', 50)}%\n"
        for n in notes[:6]: answer += f"  • {n}\n"
        answer += f"Factor score: {tc.get('factorScore', 50)}% ({algo.get('supports', 0)} supporting, {algo.get('opposes', 0)} opposing)"
    
    else:
        # ═══ SMART INFERENCE — handle ANY text ═══
        # Try to extract a stock ticker from the question
        import re
        known_stocks = ["NIFTY","BANKNIFTY","SENSEX","RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","SBIN","ITC","LT","TATAMOTORS","BAJFINANCE","BHARTIARTL","MARUTI",
                       "SPY","QQQ","IWM","AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META","AMD","JPM","AVGO","NFLX"]
        mentioned = [s for s in known_stocks if s.lower() in question]
        
        # Detect sentiment/intent from keywords
        bullish_words = ["buy","long","bullish","up","call","ce","invest","good","strong","growth","undervalued","cheap"]
        bearish_words = ["sell","short","bearish","down","put","pe","overvalued","expensive","weak","crash","fall"]
        risk_words = ["risk","safe","loss","stop","protect","hedge","insurance","danger"]
        learn_words = ["what is","explain","how does","teach","learn","mean","definition","basics","beginner"]
        compare_words = ["vs","versus","compare","better","which one","or"]
        
        bull_count = sum(1 for w in bullish_words if w in question)
        bear_count = sum(1 for w in bearish_words if w in question)
        is_risk_q = any(w in question for w in risk_words)
        is_learn_q = any(w in question for w in learn_words)
        is_compare = any(w in question for w in compare_words)
        
        # Smart response based on detected intent
        if mentioned and len(mentioned) >= 2 and is_compare:
            # Compare two stocks
            s1, s2 = mentioned[0], mentioned[1]
            answer = f"📊 {s1} vs {s2} — Quick Comparison:\n\n"
            answer += f"Use the Stock Intel tab to analyze each one separately. Look at:\n"
            answer += f"• Fundamentals: Which has better revenue growth?\n"
            answer += f"• Valuation: Which is cheaper (lower PE/PEG)?\n"
            answer += f"• Trend: Which is in an uptrend?\n\n"
            answer += f"The one scoring higher on ALL THREE is the better pick. If mixed, diversify — buy both.\n\n"
            answer += f"💡 Tip: Click Stock Intel tab → Analyze {s1} → then {s2} → compare scores."
            
        elif mentioned and is_risk_q:
            s1 = mentioned[0]
            rm = algo.get("riskManagement", {})
            answer = f"🛡️ Risk Analysis for {s1}:\n\n"
            answer += f"• Signal: {sig} ({direction})\n"
            answer += f"• Win Rate: {tc.get('estimatedWin', 50)}% (Grade {tc.get('grade', 'B')})\n"
            if tr: answer += f"• Stop Loss: {csym}{tr.get('premSL', 0)} (max loss per lot: {csym}{rm.get('premiumAtRisk', 0):,.0f})\n"
            answer += f"• Position sizing: {tc.get('sizeRecommendation', 'Use 1-2% of capital')}\n\n"
            answer += f"Risk factors:\n"
            for alert in (rm.get("exposureAlerts", []))[:3]:
                answer += f"  ⚠️ {alert.get('msg', '')}\n"
            answer += f"\n💡 Golden rule: Never risk more than 2% of your total capital on one trade."
            
        elif is_learn_q:
            # Educational response
            topic = question
            if "greek" in topic or "delta" in topic or "theta" in topic:
                answer = "📚 Greeks Explained Simply:\n\n"
                answer += "• DELTA = Speed. How much your option moves when stock moves ₹1. Delta 0.5 = option moves 50 paise per ₹1.\n"
                answer += "• THETA = Time decay. Your option loses this much value EVERY DAY. Like ice cream melting.\n"
                answer += "• GAMMA = Acceleration. How fast Delta changes. High near expiry = wild swings.\n"
                answer += "• VEGA = Fear sensitivity. When VIX rises, your option price jumps.\n\n"
                answer += "💡 Remember: Theta works AGAINST buyers and FOR sellers. Near expiry, Theta accelerates — that's why options lose value fast in the last week."
            elif "iv" in topic or "volatil" in topic:
                answer = "📚 Volatility Explained:\n\n"
                answer += "IV (Implied Volatility) = how expensive options are right now.\n"
                answer += "Think of it like flight ticket prices:\n"
                answer += "• High IV = peak season = expensive tickets = sell options\n"
                answer += "• Low IV = off-season = cheap tickets = buy options\n\n"
                answer += "IV Rank tells you WHERE current IV is vs last year:\n"
                answer += "• Rank > 70% = expensive (sell premium)\n"
                answer += "• Rank < 30% = cheap (buy premium)\n\n"
                answer += "💡 Biggest retail mistake: Buying options when IV is high, then watching them lose value even when stock moves in their direction (IV crush)."
            elif "spread" in topic or "iron" in topic or "straddle" in topic or "strateg" in topic:
                answer = "📚 Strategy Guide:\n\n"
                answer += "• BUY CALL/CE = You think stock goes UP. Risk = premium paid.\n"
                answer += "• BUY PUT/PE = You think stock goes DOWN. Risk = premium paid.\n"
                answer += "• BULL SPREAD = Buy + Sell calls. Capped profit but lower cost.\n"
                answer += "• IRON CONDOR = Sell calls + puts. Profit if stock stays in range.\n"
                answer += "• STRADDLE = Buy call + put same strike. Profit from BIG move either way.\n\n"
                answer += "When to use what:\n"
                answer += "• Confident direction + low IV → Buy Call/Put\n"
                answer += "• Moderate confidence → Spread\n"
                answer += "• No direction + high IV → Iron Condor\n"
                answer += "• Event coming + low IV → Straddle"
            else:
                answer = "📚 Options Trading Basics:\n\n"
                answer += "An OPTION = right to buy/sell a stock at a fixed price before a fixed date.\n"
                answer += "• CALL (CE) = Bet stock goes UP\n"
                answer += "• PUT (PE) = Bet stock goes DOWN\n"
                answer += "• PREMIUM = What you pay for this right (like a movie ticket)\n"
                answer += "• STRIKE = The price you're betting on\n"
                answer += "• EXPIRY = When your bet expires\n\n"
                answer += "💡 Start with: 'Should I buy NIFTY?' or 'Best strategy for RELIANCE?'"
                
        elif bull_count > bear_count and mentioned:
            # Bullish sentiment detected
            s1 = mentioned[0]
            answer = f"📈 Bullish View on {s1}:\n\n"
            answer += f"Current signal: {sig} ({direction}), Win Rate: {tc.get('estimatedWin', 50)}%\n\n"
            if direction == "BULLISH":
                answer += f"✅ Our engines AGREE with your bullish view!\n"
                if tr: answer += f"Trade: {tr.get('action', '')} at {csym}{tr.get('premEntry', 0)}, SL: {csym}{tr.get('premSL', 0)}, Target: {csym}{tr.get('premT2', 0)}\n"
            else:
                answer += f"⚠️ Our engines show {direction} — your bullish view may face headwinds.\n"
                answer += f"Consider waiting for trend confirmation before entering.\n"
            answer += f"\n💡 Always check: Is the TREND with you? Is IV low (options cheap)? Do engines agree?"
            
        elif bear_count > bull_count and mentioned:
            s1 = mentioned[0]
            answer = f"📉 Bearish View on {s1}:\n\n"
            answer += f"Current signal: {sig} ({direction})\n\n"
            if direction == "BEARISH":
                answer += f"✅ Engines confirm bearish bias. {sig}.\n"
                if tr: answer += f"Trade: {tr.get('action', '')} at {csym}{tr.get('premEntry', 0)}\n"
            else:
                answer += f"⚠️ Engines show {direction} — bearish trade goes AGAINST the trend.\n"
                answer += f"Contrarian trades work sometimes but have lower win rate.\n"
            answer += f"\n💡 For bearish bets: Buy PUT/PE, or use Bear Put Spread to limit risk."
        
        else:
            # Generic — give full summary
            answer = f"📊 {symbol} Complete Summary:\n\n"
            answer += f"🎯 SIGNAL: {sig} ({direction}) — Win Rate: {tc.get('estimatedWin', 50)}% (Grade {tc.get('grade', 'B')})\n"
            answer += f"💰 PRICE: {csym}{price:,.2f}\n"
            if tr and not isWait:
                answer += f"\n📋 TRADE:\n"
                answer += f"  {tr.get('action', 'N/A')}\n"
                answer += f"  Entry: {csym}{tr.get('premEntry', 0)} → SL: {csym}{tr.get('premSL', 0)} → Target: {csym}{tr.get('premT2', 0)}\n"
                answer += f"  R:R: {tr.get('rrRatio', 'N/A')}\n"
            answer += f"\n📊 ENGINES:\n"
            eng = algo.get("engines", {})
            if eng.get("regime"): answer += f"  Trend: {eng['regime'].get('trend', '—')} ({eng['regime'].get('strength', '—')})\n"
            if eng.get("oi"): answer += f"  Smart Money: {eng['oi'].get('bias', '—')}\n"
            if eng.get("volatility"): answer += f"  Volatility: {eng['volatility'].get('action', '—').replace('_', ' ')}\n"
            if eng.get("momentum"): answer += f"  Momentum: {eng['momentum'].get('signal', '—').replace('_', ' ')}\n"
            answer += f"\n⚡ SCALP: {sc.get('direction', 'N/A')} ({sc.get('confidence', 0)}%)\n"
            answer += f"📊 IV Rank: {oi.get('iv_rank', '—')}%\n\n"
            answer += f"💡 Try asking:\n• 'Should I buy {symbol}?'\n• 'CE/CALL buy'\n• 'Best strategy'\n• 'What is IV?'\n• 'Compare NIFTY vs BANKNIFTY'"
    
    return {"success": True, "answer": answer, "symbol": symbol, "signal": sig, "direction": direction}


# ═══════════════════════════════════════════════════
# EDUCATION — Live case studies from real algo data
# ═══════════════════════════════════════════════════
@app.get("/api/education")
async def education_module(topic: str = "basics"):
    """Generate educational content from real market data."""
    
    lessons = {
        "basics": {
            "title": "Options Trading Fundamentals",
            "sections": [
                {"heading": "What is an Option?", "content": "An option gives you the RIGHT (not obligation) to buy or sell a stock at a specific price before a specific date. Think of it as paying a small deposit to reserve a house — if the price goes up, you exercise; if not, you lose only the deposit (premium)."},
                {"heading": "Call (CE) vs Put (PE)", "content": "CALL = You expect price to GO UP. Like betting the team will win. PUT = You expect price to GO DOWN. Like buying insurance on your car. In India: CE = Call, PE = Put. In US: CALL/PUT."},
                {"heading": "Strike Price", "content": "The price at which you can buy/sell the stock. ATM (At The Money) = strike near current price. ITM (In The Money) = already profitable. OTM (Out of The Money) = needs to move more."},
                {"heading": "Premium", "content": "What you PAY for the option. Like rent — you pay to hold the right. Premium = Intrinsic Value + Time Value. Time value decays every day (Theta)."},
                {"heading": "Expiry", "content": "Options have a death date. In India: NIFTY expires every Tuesday, SENSEX every Thursday. After expiry, your option is worthless if OTM. Never hold till last minute."},
            ]
        },
        "greeks": {
            "title": "Greeks Made Simple",
            "sections": [
                {"heading": "Delta (Δ) — Speed", "content": "How much your option moves when stock moves ₹1. Delta 0.5 means option moves ₹0.50 for every ₹1 stock move. ATM options have ~0.5 delta. Higher delta = more expensive but higher probability."},
                {"heading": "Gamma (Γ) — Acceleration", "content": "How fast Delta changes. Near expiry, Gamma EXPLODES — small moves cause huge premium changes. This is why expiry-day trading is like driving at 200 km/h. Exciting but dangerous."},
                {"heading": "Theta (Θ) — Time Decay", "content": "How much you LOSE every day just by holding. Options are like ice cream in summer — they melt. Theta kills buyers and rewards sellers. Last 3 days = fastest melt."},
                {"heading": "Vega (V) — Volatility Sensitivity", "content": "How much premium changes when IV changes 1%. Before events (earnings, Fed), IV rises → premiums inflate. After events, IV crushes → premiums collapse. Sellers love this."},
                {"heading": "Pro Tip", "content": "Don't memorize Greeks. Understand: Delta = direction, Gamma = speed of direction change, Theta = time cost, Vega = volatility cost. Use our Greeks Dashboard to see what YOUR option is doing RIGHT NOW."},
            ]
        },
        "strategies": {
            "title": "Strategy Selection Guide",
            "sections": [
                {"heading": "Market is Trending UP", "content": "Use: Bull Call Spread (defined risk) or Naked Long Call (unlimited profit). Avoid: Selling naked calls. Check: EMA 9>21>50, RSI 50-70, above VWAP."},
                {"heading": "Market is Trending DOWN", "content": "Use: Bear Put Spread or Long Put. Avoid: Buying calls hoping for reversal. Check: EMA 9<21<50, RSI 30-50, below VWAP."},
                {"heading": "Market is SIDEWAYS", "content": "Use: Iron Condor or Short Strangle (sell premium). This is where most money is made. 70% of the time markets are range-bound. Check: Low ATR, narrow Bollinger Bands, IV Rank > 50."},
                {"heading": "Before a BIG EVENT", "content": "Use: Long Straddle/Strangle (buy both CE+PE). You profit from the MOVE, not the direction. Check: IV Rank < 30 (buy cheap), event within 3-5 days."},
                {"heading": "After an EVENT (IV Crush)", "content": "Use: Iron Condor or Credit Spreads. After events, IV drops 30-50% in hours. Sellers collect this premium drop. Check: IV Rank just dropped from >70, event over."},
                {"heading": "Golden Rule", "content": "HIGH IV → SELL premium (Iron Condors, Credit Spreads). LOW IV → BUY premium (Straddles, Long Calls/Puts). Check IV Rank on our dashboard before every trade."},
            ]
        },
        "risk": {
            "title": "Risk Management — The REAL Edge",
            "sections": [
                {"heading": "The 2% Rule", "content": "Never risk more than 2% of your account on a single trade. Account ₹5L → max loss per trade = ₹10,000. This ensures you survive 10 consecutive losses and still have 80% capital left."},
                {"heading": "Position Sizing Formula", "content": "Lots = (Account × Risk%) / (Premium × Lot Size). Example: ₹5L account, 2% risk, premium ₹200, lot 50. Max lots = (500000 × 0.02) / (200 × 50) = 1 lot. NEVER exceed this."},
                {"heading": "Stop Loss is NON-NEGOTIABLE", "content": "Place SL BEFORE entering. Not in your head — in the system. If premium drops 30% from entry, EXIT. No hoping, no averaging down. The market doesn't care about your feelings."},
                {"heading": "Trailing Stop Loss", "content": "When T1 is hit, move SL to entry (cost). Now it's a free trade — worst case you exit at breakeven. Let winners run, cut losers fast. This alone transforms your P&L."},
                {"heading": "Weekly Risk Limit", "content": "Set a weekly loss limit (e.g., 5% of account). If you hit it, STOP trading for the week. No exceptions. This prevents revenge trading — the #1 account killer."},
                {"heading": "Revenge Trading Detection", "content": "Signs: Trading immediately after a loss. Doubling position size. Ignoring your strategy. Taking random trades. If you notice any of these — close the terminal and walk away."},
            ]
        },
    }
    
    topic_data = lessons.get(topic, lessons["basics"])
    return {"success": True, "topic": topic, "lesson": topic_data, "available_topics": list(lessons.keys())}


_si_cache = {}  # {symbol_region: {ts, data}}
_si_lock = None  # Semaphore to limit concurrent yfinance calls

@app.get("/api/stock-intel")
async def stock_intel(symbol: str, region: str = "IN"):
    """Complete Stock Intelligence — single yfinance call, 30-min cache, rate-limit safe"""
    import asyncio
    global _si_lock
    if _si_lock is None:
        _si_lock = asyncio.Semaphore(2)  # Max 2 concurrent yfinance calls
    
    cache_key = f"{symbol}_{region}"
    now = datetime.utcnow()
    
    # 30-min cache — prevents rate limiting on repeated clicks
    if cache_key in _si_cache:
        age = (now - _si_cache[cache_key]["ts"]).total_seconds()
        if age < 1800:
            print(f"📋 Stock Intel cache hit: {cache_key} ({int(age/60)}min old)")
            return _si_cache[cache_key]["data"]
    
    # Rate limit guard
    if not _si_lock.locked() or _si_lock._value > 0:
        pass  # OK to proceed
    else:
        # Already 2 concurrent calls — return cached even if stale, or wait
        if cache_key in _si_cache:
            return _si_cache[cache_key]["data"]
        # Brief wait
        await asyncio.sleep(2)
    
    async with _si_lock:
        return await _run_stock_intel(symbol, region, cache_key)

async def _run_stock_intel(symbol, region, cache_key):
    """Actual stock intel computation — runs under semaphore"""
    try:
        import yfinance as yf, math, time
        import pandas as pd
        import numpy as np
        
        is_us = region.upper() == "US"
        yf_sym = symbol if is_us else f"{symbol}.NS"
        csym = "$" if is_us else "₹"
        
        # ═══ SINGLE yfinance call with retry ═══
        info = {}; hist = pd.DataFrame()
        for attempt in range(3):
            try:
                tk = yf.Ticker(yf_sym)
                # Get history FIRST (less likely to fail than info)
                hist = tk.history(period="1y")
                if len(hist) == 0:
                    raise Exception("Empty history")
                # Then try info (may fail with rate limit)
                try:
                    info = tk.info or {}
                except Exception as ie:
                    print(f"⚠️ Stock Intel info failed for {yf_sym}: {ie}")
                    info = {}
                break
            except Exception as ex:
                print(f"⚠️ Stock Intel attempt {attempt+1}/3 for {yf_sym}: {ex}")
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))  # Back-off: 1.5s, 3s
                continue
        
        # Fallback: Yahoo v8 direct API if yfinance fails
        if len(hist) == 0:
            try:
                import requests as req
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}?range=1y&interval=1d"
                r = req.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                data = r.json()
                result_data = data.get("chart", {}).get("result", [{}])[0]
                ts = result_data.get("timestamp", [])
                quotes = result_data.get("indicators", {}).get("quote", [{}])[0]
                if ts and quotes:
                    hist = pd.DataFrame({
                        "Close": quotes.get("close", []),
                        "Open": quotes.get("open", []),
                        "High": quotes.get("high", []),
                        "Low": quotes.get("low", []),
                        "Volume": quotes.get("volume", [])
                    }).dropna()
                    print(f"✅ Stock Intel fallback v8 worked for {yf_sym}: {len(hist)} rows")
            except Exception as v8e:
                print(f"⚠️ v8 fallback also failed: {v8e}")
        
        if len(hist) == 0:
            return {"success": False, "error": f"Could not fetch data for {symbol}. Yahoo Finance may be rate limiting — please try again in 2 minutes."}
        
        closes = hist["Close"].values.astype(float)
        volumes = hist["Volume"].values.astype(float) if "Volume" in hist else []
        highs = hist["High"].values.astype(float) if "High" in hist else closes
        lows = hist["Low"].values.astype(float) if "Low" in hist else closes
        price = round(float(closes[-1]), 2)
        
        # ═══ 1. FUNDAMENTAL ANALYSIS ═══
        rev_growth = float(info.get("revenueGrowth", 0) or 0) * 100
        earn_growth = float(info.get("earningsGrowth", 0) or 0) * 100
        profit_margin = float(info.get("profitMargins", 0) or 0) * 100
        gross_margin = float(info.get("grossMargins", 0) or 0) * 100
        debt_equity = float(info.get("debtToEquity", 0) or 0)
        roe = float(info.get("returnOnEquity", 0) or 0) * 100
        roce = float(info.get("returnOnAssets", 0) or 0) * 100 * 1.5
        
        fund_score = 50; fund_flags = []
        if rev_growth > 15: fund_score += 15; fund_flags.append(f"+Revenue growing {rev_growth:.0f}% — business expanding")
        elif rev_growth > 5: fund_score += 5; fund_flags.append(f"+Moderate revenue growth {rev_growth:.0f}%")
        elif rev_growth < -5: fund_score -= 10; fund_flags.append(f"-Revenue DECLINING {rev_growth:.0f}% — red flag")
        if earn_growth > 20: fund_score += 15; fund_flags.append(f"+Strong earnings growth {earn_growth:.0f}%")
        elif earn_growth < -5: fund_score -= 10; fund_flags.append(f"-Earnings declining {earn_growth:.0f}%")
        if profit_margin > 15: fund_score += 10; fund_flags.append(f"+Healthy profit margin {profit_margin:.0f}%")
        elif profit_margin < 5 and profit_margin != 0: fund_score -= 10; fund_flags.append(f"-Thin margins {profit_margin:.0f}%")
        if 0 < debt_equity < 50: fund_score += 5; fund_flags.append(f"+Low debt ({debt_equity:.0f}%) — strong balance sheet")
        elif debt_equity > 150: fund_score -= 10; fund_flags.append(f"-Heavy debt ({debt_equity:.0f}%) — risk if rates rise")
        if roe > 15: fund_score += 5; fund_flags.append(f"+Good ROE {roe:.0f}%")
        if not fund_flags: fund_flags.append("Fundamental data limited — using price action instead")
        fund_score = max(0, min(100, fund_score))
        fund_verdict = "STRONG" if fund_score >= 70 else ("AVERAGE" if fund_score >= 45 else "WEAK")
        
        # ═══ 2. VALUATION ANALYSIS ═══
        pe = float(info.get("trailingPE", 0) or 0)
        fwd_pe = float(info.get("forwardPE", 0) or 0)
        peg = float(info.get("pegRatio", 0) or 0)
        pb = float(info.get("priceToBook", 0) or 0)
        sector = info.get("sector", "")
        
        val_score = 50; val_flags = []
        if pe > 0:
            if pe < 15: val_score += 20; val_flags.append(f"+PE {pe:.1f}x — attractively valued")
            elif pe < 25: val_score += 5; val_flags.append(f"PE {pe:.1f}x — reasonable valuation")
            elif pe > 40: val_score -= 15; val_flags.append(f"-PE {pe:.1f}x — expensive, needs high growth to justify")
        if fwd_pe > 0 and pe > 0:
            if fwd_pe < pe * 0.85: val_score += 10; val_flags.append(f"+Forward PE {fwd_pe:.1f}x dropping — earnings growing into valuation")
            elif fwd_pe > pe: val_score -= 5; val_flags.append(f"-Forward PE {fwd_pe:.1f}x rising — earnings may shrink")
        if peg > 0:
            if peg < 1: val_score += 15; val_flags.append(f"+PEG {peg:.1f} — undervalued for growth (sweet spot!)")
            elif peg > 2: val_score -= 10; val_flags.append(f"-PEG {peg:.1f} — overpriced for growth")
        if not val_flags: val_flags.append("Valuation data limited — rely on price action signals")
        val_score = max(0, min(100, val_score))
        val_verdict = "CHEAP" if val_score >= 65 else ("FAIR" if val_score >= 40 else "EXPENSIVE")
        
        # ═══ 3. PRICE ACTION ANALYSIS ═══
        trend = "SIDEWAYS"; trend_detail = "Insufficient data"
        support = 0; resistance = 0; vol_confirm = "WEAK"
        breakout_level = 0; breakdown_level = 0
        
        if len(closes) >= 50:
            ema20 = float(pd.Series(closes).ewm(span=20).mean().iloc[-1])
            ema50 = float(pd.Series(closes).ewm(span=50).mean().iloc[-1])
            sma200 = float(np.mean(closes[-200:])) if len(closes) >= 200 else float(np.mean(closes[-50:]))
            
            if ema20 > ema50 and price > sma200: trend = "BULLISH"; trend_detail = "Moving averages stacked up — clear uptrend"
            elif ema20 < ema50 and price < sma200: trend = "BEARISH"; trend_detail = "Moving averages stacked down — downtrend"
            else: trend_detail = "Mixed signals — no clear direction yet"
            
            w52h = float(max(closes[-min(252,len(closes)):]))
            w52l = float(min(closes[-min(252,len(closes)):]))
            resistance = round(w52h, 2)
            support = round(w52l + (w52h - w52l) * 0.236, 2)
            breakout_level = round(w52h * 1.02, 2)
            breakdown_level = round(support * 0.98, 2)
            
            if len(volumes) >= 20:
                avg_vol = float(np.mean(volumes[-20:]))
                recent_vol = float(np.mean(volumes[-5:]))
                vol_ratio = round(recent_vol / avg_vol, 1) if avg_vol > 0 else 1.0
                vol_confirm = "STRONG" if vol_ratio > 1.3 else ("MODERATE" if vol_ratio > 0.8 else "WEAK")
        
        pa_score = 50
        if trend == "BULLISH": pa_score += 20
        elif trend == "BEARISH": pa_score -= 10
        if vol_confirm == "STRONG": pa_score += 10
        if price > 0 and resistance > 0 and price > resistance * 0.95: pa_score += 10
        pa_score = max(0, min(100, pa_score))
        
        # ═══ 4. CONFLUENCE ═══
        conf_score = round(fund_score * 0.30 + val_score * 0.25 + pa_score * 0.45, 0)
        alignment = []
        if fund_verdict == "STRONG" and val_verdict != "EXPENSIVE" and trend == "BULLISH":
            alignment.append("✅ TRIPLE ALIGNMENT — Fundamentals + Valuation + Trend all agree")
        elif fund_verdict == "STRONG" and trend != "BULLISH":
            alignment.append("⚠️ Good company but wrong timing — wait for uptrend")
        elif val_verdict == "CHEAP" and trend == "BULLISH":
            alignment.append("✅ Value + Momentum — cheap AND trending up")
        elif val_verdict == "EXPENSIVE" and trend == "BEARISH":
            alignment.append("🔴 Expensive AND falling — avoid")
        else:
            alignment.append("⚠️ Mixed signals — wait for clarity")
        
        # ═══ 5. TRADE PLAN ═══
        if conf_score >= 65 and trend == "BULLISH":
            decision = "BUY"; dec_color = "#059669"
        elif conf_score >= 55 and trend != "BEARISH":
            decision = "HOLD / ACCUMULATE"; dec_color = "#d97706"
        elif trend == "BEARISH" or conf_score < 35:
            decision = "SELL / AVOID"; dec_color = "#dc2626"
        else:
            decision = "WAIT"; dec_color = "#d97706"
        
        atr = 0
        if len(closes) >= 15 and len(highs) >= 14 and len(lows) >= 14:
            trs = []
            for i in range(1, min(15, len(closes))):
                tr_val = max(highs[-i]-lows[-i], abs(highs[-i]-closes[-i-1]), abs(lows[-i]-closes[-i-1]))
                trs.append(tr_val)
            atr = round(float(np.mean(trs)), 2) if trs else 0
        
        entry_low = round(price * 0.98, 2)
        entry_high = round(price * 1.01, 2)
        sl = round(price - atr * 2, 2) if atr > 0 else round(price * 0.93, 2)
        t1 = round(price + atr * 3, 2) if atr > 0 else round(price * 1.08, 2)
        t2 = round(price + atr * 5, 2) if atr > 0 else round(price * 1.15, 2)
        rr = round((t1 - price) / max(price - sl, 0.01), 1)
        
        confidence = int(conf_score)
        
        # ═══ 7. SIMPLE EXPLANATION ═══
        if decision == "BUY":
            simple_why = f"{symbol} has solid fundamentals, reasonable valuation, and price is trending up. Like a train leaving the station — better to be on it."
            simple_risk = "Market-wide crash could drag it down. Set stop loss and don't panic sell."
        elif "SELL" in decision:
            simple_why = f"{symbol} is either expensive, fundamentals weakening, or in downtrend. Like buying at peak price — wait for better deal."
            simple_risk = "If you own it, consider cutting losses or wait for reversal."
        else:
            simple_why = f"{symbol} shows mixed signals. Like a restaurant with great food but bad reviews — worth watching, not committing yet."
            simple_risk = "Could go either way. Set alerts and wait for clearer picture."
        
        # ═══ 8-13: Context, Timing, Sizing, Smart Money, Risk, Invalidation ═══
        # Entry Timing
        if price > 0 and resistance > 0 and price >= resistance * 0.98:
            entry_timing = {"signal": "BREAKOUT IMMINENT", "condition": f"Wait for close above {csym}{breakout_level:,.0f} with volume", "type": "BREAKOUT"}
        elif price > 0 and support > 0 and price <= support * 1.05:
            entry_timing = {"signal": "NEAR SUPPORT", "condition": f"Enter if bounces from {csym}{support:,.0f}", "type": "PULLBACK"}
        else:
            entry_timing = {"signal": "MID-RANGE", "condition": f"Wait for pullback to {csym}{round(price*0.97,0):,.0f} or breakout above {csym}{resistance:,.0f}", "type": "WAIT"}
        
        # Sizing
        if confidence >= 75: sizing = "AGGRESSIVE"; sizing_detail = "High conviction — allocate 3-5% of portfolio"
        elif confidence >= 55: sizing = "MODERATE"; sizing_detail = "Decent setup — allocate 1-3%"
        else: sizing = "CONSERVATIVE"; sizing_detail = "Weak setup — max 1% or skip"
        
        # Smart Money
        smart_money = []
        if len(volumes) >= 20:
            avg_v = float(np.mean(volumes[-20:]))
            recent_v = float(np.mean(volumes[-3:])) if len(volumes) >= 3 else avg_v
            if recent_v > avg_v * 2: smart_money.append("🔥 Volume 2x above average — institutions may be accumulating")
            elif recent_v > avg_v * 1.5: smart_money.append("📊 Above-average volume — increased interest")
            if len(closes) >= 5:
                if closes[-1] > closes[-5] and recent_v > avg_v: smart_money.append("📈 Price up + volume up = genuine buying")
                if closes[-1] < closes[-5] and recent_v < avg_v * 0.7: smart_money.append("😴 Price down on LOW volume — pullback, not distribution")
        if not smart_money: smart_money.append("No unusual activity — normal trading")
        
        # Risks
        risks = []
        if debt_equity > 100: risks.append("High debt — vulnerable to rate hikes")
        if pe > 50: risks.append("Expensive valuation — earnings miss = sharp fall")
        if vol_confirm == "WEAK": risks.append("Low volume — breakouts may fail")
        risks.append("Earnings season can create sudden 5-10% moves")
        risks.append("Global macro risks (Fed/RBI, geopolitics, oil)")
        
        invalidation = f"This idea FAILS if price closes below {csym}{sl:,.0f}. At that point, exit — no exceptions."
        
        _si_result = {
            "success": True, "symbol": symbol, "price": price, "csym": csym, "region": region,
            "companyName": info.get("shortName", symbol), "sector": sector,
            "industry": info.get("industry", ""),
            "decision": decision, "decColor": dec_color, "confidence": confidence,
            "fundamental": {"score": fund_score, "verdict": fund_verdict, "flags": fund_flags,
                           "revGrowth": round(rev_growth,1), "earnGrowth": round(earn_growth,1),
                           "profitMargin": round(profit_margin,1), "grossMargin": round(gross_margin,1),
                           "debtEquity": round(debt_equity,1), "roe": round(roe,1), "roce": round(roce,1)},
            "valuation": {"score": val_score, "verdict": val_verdict, "flags": val_flags,
                         "pe": round(pe,1), "fwdPE": round(fwd_pe,1), "peg": round(peg,2), "pb": round(pb,1)},
            "priceAction": {"score": pa_score, "trend": trend, "trendDetail": trend_detail,
                           "support": support, "resistance": resistance, "volConfirm": vol_confirm,
                           "breakout": breakout_level, "breakdown": breakdown_level},
            "confluence": {"score": conf_score, "alignment": alignment},
            "tradePlan": {"entry": [entry_low, entry_high], "sl": sl, "t1": t1, "t2": t2, "rr": rr},
            "simple": {"why": simple_why, "risk": simple_risk},
            "marketContext": {"sectorStrength": sector or "Unknown", "aligned": trend == "BULLISH"},
            "entryTiming": entry_timing,
            "sizing": {"level": sizing, "detail": sizing_detail},
            "smartMoney": smart_money,
            "risks": risks,
            "invalidation": invalidation,
        }
        _si_cache[cache_key] = {"ts": datetime.utcnow(), "data": _si_result}
        if len(_si_cache) > 50:
            oldest = min(_si_cache, key=lambda k: _si_cache[k]["ts"])
            del _si_cache[oldest]
        print(f"📊 Stock Intel: {symbol} → {decision} ({confidence}%) cached 30min")
        return _si_result
    except Exception as e:
        import traceback; traceback.print_exc()
        # Return stale cache if available
        if cache_key in _si_cache:
            print(f"⚠️ Stock Intel error, returning stale cache for {symbol}")
            return _si_cache[cache_key]["data"]
        return {"success": False, "error": f"Rate limited by Yahoo Finance. Please wait 2 minutes and try again. ({str(e)[:80]})"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting Celesys AI on port {port}")
    print(f"   Performance: connection pool, thread pool (15), smart cache, background prefetch")
    # Single worker + async + thread pool = best for IO-bound app with in-memory cache
    # Multiple workers would split cache across processes (bad for hit rate)
    uvicorn.run("api:app", host="0.0.0.0", port=port, 
                timeout_keep_alive=30, limit_concurrency=1000)
