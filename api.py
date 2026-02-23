"""
Celesys AI - VERIFIED Real-Time Data
With built-in verification and ChatGPT comparison
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response, FileResponse
import os
import requests
from datetime import datetime, timedelta
import hashlib
import yfinance as yf
from functools import lru_cache
import time
import json
import random

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
            modules = 'summaryProfile,financialData,defaultKeyStatistics,summaryDetail,price'
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
                    price_d = r.get('price', {})
                    
                    def raw(d, key, default=0):
                        v = d.get(key, {})
                        return v.get('raw', v.get('fmt', default)) if isinstance(v, dict) else (v or default)
                    
                    # Always set margins/ROE/debt (these only come from v10)
                    updates = {
                        'sector': profile.get('sector', info.get('sector', 'N/A')),
                        'industry': profile.get('industry', info.get('industry', 'N/A')),
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

app = FastAPI(title="Celesys AI - Verified Live Data")

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

report_counter = {"count": 0}
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
                    stock_margins = yf.Ticker(ticker_symbol)
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
            "enterprise_to_ebitda": safe_get('enterpriseToEbitda') or 'N/A',
            "earnings_quarterly_growth": round(safe_get('earningsQuarterlyGrowth') * (100 if abs(safe_get('earningsQuarterlyGrowth')) < 1 else 1), 2) if safe_get('earningsQuarterlyGrowth') else 'N/A',
            "short_ratio": safe_get('shortRatio') or 'N/A',
            "payout_ratio": round(safe_get('payoutRatio') * (100 if safe_get('payoutRatio') and abs(safe_get('payoutRatio')) < 1 else 1), 2) if safe_get('payoutRatio') else 'N/A',
            "data_timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p UTC"),
            "data_source": data_source,
            "verification_url": f"https://www.google.com/finance/quote/{ticker_symbol.replace('.NS', ':NSE').replace('.BO', ':BOM')}",
        }
        
        # Fetch real 6-month price history for Price Trend chart
        try:
            hist_ticker = yf.Ticker(ticker_symbol)
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
        
        # ═══ TECHNICAL INDICATORS: SMA20, SMA200, EPS Growth, Sector PE ═══
        try:
            tk = yf.Ticker(ticker_symbol)
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
                    try:
                        pt = yf.Ticker(ptk)
                        pi = pt.info
                        if not pi or not pi.get('currentPrice'): return None
                        return {
                            "ticker": ptk,
                            "name": (pi.get('shortName') or pi.get('longName') or ptk)[:30],
                            "price": round(float(pi.get('currentPrice', 0)), 2),
                            "pe": round(float(pi.get('trailingPE', 0)), 1) if pi.get('trailingPE') else 'N/A',
                            "market_cap": float(pi.get('marketCap', 0)),
                            "profit_margin": round(float(pi.get('profitMargins', 0) or 0) * 100, 1),
                            "roe": round(float(pi.get('returnOnEquity', 0) or 0) * 100, 1),
                            "revenue_growth": round(float(pi.get('revenueGrowth', 0) or 0) * 100, 1),
                            "debt_to_equity": round(float(pi.get('debtToEquity', 0) or 0), 1),
                        }
                    except:
                        return None
                
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
TRADES_ALLOWED_EMAILS = ["vijy.dhulipala@gmail.com"]
_trades_cache = {"timestamp": None, "data": None}  # 30-min cache — live enough for trading, stable enough to not flip-flop

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

@app.get("/api/global-ticker")
async def global_ticker():
    """Lightweight global indices ticker — parallel fetch with 2-min cache."""
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime, timedelta
    
    # ═══ 2-MINUTE CACHE — prevents hammering yfinance ═══
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
    }
    
    results = []
    gold_price = None
    silver_price = None
    
    # ═══ PARALLEL FETCH — all 14 tickers at once (was sequential = 14-28s) ═══
    def _fetch_index(ticker, meta):
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
    result = {"success": True, "indices": results, "updated_at": IST.strftime("%I:%M %p IST")}
    
    _ticker_cache = result
    _ticker_cache_ts = now_utc
    print(f"📈 Global ticker: {len(results)} indices fetched (parallel)")
    return result

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


# ═══ BATCH PRICES — fetch live prices for stock picks (up to 30 tickers) ═══
_batch_cache = {}
_batch_cache_ts = None

@app.post("/api/batch-prices")
async def batch_prices(request: Request):
    """Fetch live prices for multiple tickers at once. Used by Picks tab."""
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime, timedelta
    
    global _batch_cache, _batch_cache_ts
    
    try:
        data = await request.json()
        tickers = data.get("tickers", [])
        if not tickers or not isinstance(tickers, list):
            return {"success": False, "error": "tickers array required"}
        
        # Limit to 30 tickers per request
        tickers = [t.strip().upper() for t in tickers[:30] if t.strip()]
        
        # Return cached prices if less than 2 min old
        now = datetime.utcnow()
        if _batch_cache_ts and (now - _batch_cache_ts).total_seconds() < 120:
            cached_results = {}
            missing = []
            for t in tickers:
                if t in _batch_cache:
                    cached_results[t] = _batch_cache[t]
                else:
                    missing.append(t)
            if not missing:
                return {"success": True, "prices": cached_results}
            tickers = missing  # Only fetch what's not cached
        else:
            cached_results = {}
        
        # Parallel fetch — 7 workers, 3s timeout per ticker
        results = {}
        def _fetch_price(tk):
            try:
                t = yf.Ticker(tk)
                info = t.info
                price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                if price:
                    chg = float(info.get('regularMarketChange', 0) or 0)
                    chg_pct = float(info.get('regularMarketChangePercent', 0) or 0)
                    if abs(chg_pct) < 0.001 and price:
                        prev = info.get('previousClose') or info.get('regularMarketPreviousClose')
                        if prev and prev > 0:
                            chg = round(price - prev, 2)
                            chg_pct = round(((price - prev) / prev) * 100, 2)
                    currency = info.get('currency', 'USD')
                    sym = '₹' if currency == 'INR' else '$'
                    return tk, {
                        "price": round(float(price), 2),
                        "change_pct": round(float(chg_pct), 2),
                        "symbol": sym,
                        "formatted": f"{sym}{round(float(price), 2):,.2f}"
                    }
            except:
                pass
            return tk, None
        
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {executor.submit(_fetch_price, t): t for t in tickers}
            for f in as_completed(futures, timeout=12):
                try:
                    tk, data = f.result(timeout=4)
                    if data:
                        results[tk] = data
                        _batch_cache[tk] = data
                except:
                    pass
        
        _batch_cache_ts = now
        
        # Merge with cached
        all_results = {**cached_results, **results}
        
        return {"success": True, "prices": all_results, "fetched": len(results), "cached": len(cached_results)}
    except Exception as e:
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
    for name, snap in global_snapshot.items():
        price, chg_pct = snap["price"], snap["change_pct"]
        if name == "Crude Oil" and abs(chg_pct) >= 1.5:
            direction = "spikes" if chg_pct > 0 else "crashes"
            events.append({"headline": f"Crude Oil {direction} {chg_pct:+.1f}% to ${price}", "impact": "BEARISH" if chg_pct > 0 else "BULLISH", "severity": "HIGH" if abs(chg_pct) >= 3 else "MEDIUM",
                "detail": "Higher crude raises input costs, inflation pressure on RBI." if chg_pct > 0 else "Lower crude benefits India. Positive for CAD and inflation.",
                "action": "Watch ONGC/Oil India. Negative for Nifty if sustained." if chg_pct > 0 else "Positive for Indian markets. Airlines, paint stocks benefit."})
        elif name == "Gold" and abs(chg_pct) >= 0.8:
            events.append({"headline": f"Gold {'surges' if chg_pct > 0 else 'drops'} {chg_pct:+.1f}% to ${price}", "impact": "VOLATILE", "severity": "MEDIUM",
                "detail": "Gold rally = risk-off sentiment globally." if chg_pct > 0 else "Gold decline = risk-on appetite returning.",
                "action": "Consider gold ETF hedge." if chg_pct > 0 else "Positive for equity markets."})
        elif name == "Silver" and abs(chg_pct) >= 1.2:
            events.append({"headline": f"Silver {'surges' if chg_pct > 0 else 'drops'} {chg_pct:+.1f}% to ${price}", "impact": "BULLISH" if chg_pct > 0 else "BEARISH", "severity": "HIGH" if abs(chg_pct) >= 3 else "MEDIUM",
                "detail": "Silver rally = industrial demand + safe-haven buying." if chg_pct > 0 else "Silver decline = weakening industrial demand.",
                "action": "Metals & mining stocks benefit. Watch Hindalco, Vedanta." if chg_pct > 0 else "Mining stocks under pressure."})
        elif name == "S&P 500" and abs(chg_pct) >= 0.5:
            events.append({"headline": f"US Markets {'rally' if chg_pct > 0 else 'sell-off'} {chg_pct:+.1f}%", "impact": "BULLISH" if chg_pct > 0 else "BEARISH", "severity": "HIGH" if abs(chg_pct) >= 1.5 else "MEDIUM",
                "detail": f"S&P 500 moved {abs(chg_pct):.1f}%. Indian markets follow with 0.5-0.8x correlation.",
                "action": "Expect gap-up for Nifty. IT stocks lead." if chg_pct > 0 else "Expect weak opening. Consider hedging."})
        elif name == "US Dollar" and abs(chg_pct) >= 0.3:
            events.append({"headline": f"Dollar {'strengthens' if chg_pct > 0 else 'weakens'} {chg_pct:+.1f}%", "impact": "BEARISH" if chg_pct > 0 else "BULLISH", "severity": "MEDIUM",
                "detail": "Stronger dollar pressures EM currencies, FII outflows." if chg_pct > 0 else "Weaker dollar supports EM inflows.",
                "action": "IT exporters benefit from weak INR." if chg_pct > 0 else "FII inflows likely. Banking stocks benefit."})
        elif name == "USD/INR" and abs(chg_pct) >= 0.15:
            events.append({"headline": f"Rupee {'weakens' if chg_pct > 0 else 'strengthens'} {chg_pct:+.1f}%", "impact": "BEARISH" if chg_pct > 0 else "BULLISH", "severity": "HIGH" if abs(chg_pct) >= 0.5 else "MEDIUM",
                "detail": "Rupee depreciation = capital outflows." if chg_pct > 0 else "Rupee strength attracts FII flows.",
                "action": "IT exporters benefit." if chg_pct > 0 else "Domestic consumption plays benefit."})
    
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
    
    # ═══ GEOPOLITICAL, TRADE, ECONOMIC & MACRO EVENTS ═══
    geo_events = [
        # ── GEOPOLITICAL & SOVEREIGN SHIFTS ──
        {"event": "US Supreme Court — Tariff Authority (IEEPA) Ruling", "month": 3, "day": 15, "year": 2026, "impact": "HIGH"},
        {"event": "Russia-Ukraine Ceasefire Review", "month": 3, "day": 1, "year": 2026, "impact": "HIGH"},
        {"event": "NATO Hybrid Warfare Summit — Europe Defense Posture", "month": 4, "day": 7, "year": 2026, "impact": "MEDIUM"},
        {"event": "Middle East De-escalation Talks (US-Iran)", "month": 3, "day": 20, "year": 2026, "impact": "HIGH"},
        {"event": "US Venezuela Sanctions Review", "month": 4, "day": 1, "year": 2026, "impact": "MEDIUM"},
        {"event": "Japan PM Takaichi — Corporate Reform Package (Sanaenomics)", "month": 3, "day": 28, "year": 2026, "impact": "MEDIUM"},
        {"event": "US Strategic Interest in Greenland — NATO Response", "month": 4, "day": 10, "year": 2026, "impact": "MEDIUM"},

        # ── TRADE & REGULATORY POLICY ──
        {"event": "US Reciprocal Tariff Review Deadline", "month": 4, "day": 2, "year": 2026, "impact": "HIGH"},
        {"event": "US-China Trade Talks Round", "month": 3, "day": 10, "year": 2026, "impact": "HIGH"},
        {"event": "EU Retaliatory Tariff Decision on US Goods", "month": 4, "day": 15, "year": 2026, "impact": "MEDIUM"},
        {"event": "USMCA Trade Pact Review — Mexico/Canada Manufacturing", "month": 5, "day": 1, "year": 2026, "impact": "MEDIUM"},
        {"event": "CLARITY Act — Crypto/Stablecoin Regulation Vote", "month": 4, "day": 20, "year": 2026, "impact": "MEDIUM"},
        {"event": "US-China Rare Earth Export Restrictions Review", "month": 3, "day": 25, "year": 2026, "impact": "HIGH"},

        # ── ECONOMIC & MONETARY DRIVERS ──
        {"event": "US CPI Inflation Data", "month": 3, "day": 12, "year": 2026, "impact": "HIGH"},
        {"event": "US Jobs Report (Non-Farm Payrolls)", "month": 3, "day": 6, "year": 2026, "impact": "HIGH"},
        {"event": "US GDP Q4 2025 (Final)", "month": 3, "day": 27, "year": 2026, "impact": "MEDIUM"},
        {"event": "Fed Chair Jerome Powell Term Ends — Warsh Transition", "month": 5, "day": 15, "year": 2026, "impact": "HIGH"},
        {"event": "One Big Beautiful Bill Act (OBBBA) — Fiscal Package Vote", "month": 4, "day": 30, "year": 2026, "impact": "HIGH"},
        {"event": "US Midterm Elections — Pre-Election Volatility Window", "month": 9, "day": 1, "year": 2026, "impact": "HIGH"},
        {"event": "US Midterm Elections", "month": 11, "day": 3, "year": 2026, "impact": "HIGH"},

        # ── INDIA SPECIFIC ──
        {"event": "India Parliament Budget Session Ends", "month": 3, "day": 21, "year": 2026, "impact": "MEDIUM"},
        {"event": "RBI FX Reserves Review", "month": 3, "day": 14, "year": 2026, "impact": "MEDIUM"},
        {"event": "India Q4 GDP Data Release", "month": 5, "day": 30, "year": 2026, "impact": "HIGH"},
        {"event": "India GST Council Meeting", "month": 3, "day": 22, "year": 2026, "impact": "MEDIUM"},

        # ── COMMODITY & TECH TRENDS ──
        {"event": "Big Tech AI Capex Earnings Review (MSFT/GOOG/META)", "month": 4, "day": 25, "year": 2026, "impact": "HIGH"},
        {"event": "OPEC+ Production Decision", "month": 3, "day": 3, "year": 2026, "impact": "HIGH"},
        {"event": "Gold Central Bank Purchases Report (WGC)", "month": 4, "day": 5, "year": 2026, "impact": "MEDIUM"},
        {"event": "US Strategic Minerals Executive Order Review", "month": 5, "day": 10, "year": 2026, "impact": "MEDIUM"},

        # ── ROLLING MONTHLY US DATA (auto-generate for next 6 months) ──
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
            if 0 < days_until <= 30:
                upcoming.append({"event": ge["event"], "date": ge_date.strftime("%b %d"), "days": days_until, "impact": ge["impact"]})
        except:
            pass
    
    # Sort upcoming by days
    upcoming.sort(key=lambda x: x["days"])
    
    # FII/DII Activity — non-blocking thread with 4s total timeout
    fii_dii = {}
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

    result = {
        "success": True,
        "date": date_str,
        "day": day_name,
        "ist_time": now.strftime("%I:%M %p IST"),
        "is_expiry": is_expiry,
        "expiry_today": expiry_today,
        "events": events[:8],
        "upcoming": upcoming[:8],
        "global_snapshot": global_snapshot,
        "fii_dii": fii_dii
    }
    
    # Store in cache
    _pulse_cache = result
    _pulse_cache_ts = datetime.utcnow()
    
    return result

@app.post("/api/index-trades")
async def index_trades(request: Request):
    """Generate AI-powered daily index trade ideas for Indian markets"""
    import json as json_mod
    
    body = await request.json()
    email = body.get("email", "").strip().lower()
    force_refresh = body.get("force_refresh", False)
    
    if email not in TRADES_ALLOWED_EMAILS:
        return {"success": False, "error": "Access restricted. This feature is exclusively available to authorized users."}
    
    # 30-minute cache — fresh enough for live trading, stable enough to avoid flip-flopping
    from datetime import timedelta
    IST_NOW = datetime.utcnow() + timedelta(hours=5, minutes=30)
    
    cache_valid = (
        not force_refresh
        and _trades_cache["timestamp"] is not None 
        and _trades_cache["data"] is not None
        and (IST_NOW - _trades_cache["timestamp"]).total_seconds() < 1800  # 30 minutes
    )
    
    if cache_valid:
        age_min = int((IST_NOW - _trades_cache["timestamp"]).total_seconds() / 60)
        print(f"📋 Returning cached trades ({age_min}min old, refreshes at 30min)")
        return _trades_cache["data"]
    
    if force_refresh:
        print(f"🔄 Force refresh requested by {email} — generating with latest market data")
    else:
        print(f"🔥 Index trades requested by {email} — generating fresh (cache expired or empty)")
    
    # Fetch Indian index data
    indices_data = []
    tickers = {
        "^NSEI": "NIFTY 50",
        "^NSEBANK": "BANK NIFTY",
        "^BSESN": "SENSEX",
        "^INDIAVIX": "INDIA VIX"
    }
    
    for ticker, name in tickers.items():
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            info = t.info or {}
            if not hist.empty:
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
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if not hist.empty:
                price = round(hist.iloc[-1]['Close'], 2)
                prev = hist.iloc[-2]['Close'] if len(hist) > 1 else price
                change_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
                global_data.append(f"{name}: {price} ({change_pct:+.2f}%)")
        except:
            pass
    
    # Fetch top Indian stock movers for stock option picks
    stock_data = []
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
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                latest = hist.iloc[-1]
                prev = hist.iloc[-2]
                price = round(latest['Close'], 2)
                change_pct = round(((price - prev['Close']) / prev['Close']) * 100, 2)
                vol_avg = int(hist['Volume'].mean())
                vol_today = int(latest['Volume'])
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
    
    # Fetch option chains for tradeable indices
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
    indices_text = "\n".join([
        f"- {d['name']}: ₹{d['price']:,.2f} (Change: {d['change']:+.2f}, {d['change_pct']:+.2f}%) | "
        f"Day Range: ₹{d['day_low']}-₹{d['day_high']} | 5D Range: ₹{d['low_5d']}-₹{d['high_5d']} | "
        f"Open: ₹{d['open']} | Volume: {d['volume']:,}"
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
    
    prompt = f"""You are a cold, ruthless, data-obsessed derivatives trader with 20 years of Indian market experience. You have ZERO tolerance for:
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
   - Crude oil (>2% move impacts Indian market, especially if India imports)
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
    "global_impact": "brief global cues impact on Indian market today"
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
    "impact": "BULLISH | BEARISH | VOLATILE — how it impacts Indian markets",
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

TIMING GUIDELINES (Indian market hours 9:15 AM - 3:30 PM IST):
- 9:15-9:30 AM: Opening volatility — avoid entries, observe gap direction
- 9:30-10:00 AM: Opening range establishment — good for momentum entries if gap sustains
- 10:00-11:30 AM: Trend development phase — best for directional trades
- 11:30 AM-1:00 PM: Consolidation/lunch lull — good for range-bound or mean-reversion setups
- 1:00-2:00 PM: Afternoon session starts — watch for breakout from consolidation
- 2:00-3:00 PM: Power hour — strongest moves, expiry-day gamma spikes here
- 3:00-3:30 PM: Final 30 min — high volatility, avoid new entries unless scalping
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
        
        response = requests.post(
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
        _trades_cache["timestamp"] = datetime.utcnow() + timedelta(hours=5, minutes=30)
        _trades_cache["data"] = response_data
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


@app.post("/api/generate-report")
async def generate_report(request: Request):
    try:
        data = await request.json()
        company = data.get("company_name", "").strip()
        email = data.get("email", "").strip()
        
        if not company or not email:
            raise HTTPException(400, "company_name and email required")
        
        # CHECK RATE LIMIT
        rate_check = check_rate_limit(email)
        if not rate_check["allowed"]:
            return JSONResponse(
                status_code=429,
                content=rate_check
            )
        
        # GET LIVE DATA
        live_data = get_live_stock_data(company)
        
        # Check if there was an error
        if "error" in live_data or not live_data.get("success"):
            error_msg = live_data.get("error", "Could not fetch market data for this ticker")
            raise HTTPException(400, error_msg)
        
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
        
        _ai_headers = {
            "x-api-key": ANTHROPIC_API_KEY or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        _ai_models = [
            ("claude-sonnet-4-20250514", 4096, 45, "sonnet"),
            ("claude-haiku-4-5-20251001", 4096, 30, "haiku"),
        ]
        
        if ANTHROPIC_API_KEY:
            for model_name, max_tok, timeout_s, label in _ai_models:
                try:
                    print(f"🤖 AI attempt: {label} (timeout={timeout_s}s)...")
                    _ai_resp = requests.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=_ai_headers,
                        json={
                            "model": model_name,
                            "max_tokens": max_tok,
                            "messages": [{"role": "user", "content": prompt}]
                        },
                        timeout=timeout_s
                    )
                    if _ai_resp.status_code == 200:
                        report = _ai_resp.json()["content"][0]["text"]
                        ai_model_used = label
                        print(f"✅ AI success: {label} ({len(report)} chars)")
                        break
                    elif _ai_resp.status_code in (429, 529, 503):
                        print(f"⚠️ {label} overloaded ({_ai_resp.status_code}), trying next...")
                        continue
                    elif _ai_resp.status_code == 401:
                        print(f"❌ API key invalid — skipping all AI models")
                        break
                    else:
                        print(f"⚠️ {label} error {_ai_resp.status_code}, trying next...")
                        continue
                except requests.exceptions.Timeout:
                    print(f"⏰ {label} timed out after {timeout_s}s, trying next...")
                    continue
                except requests.exceptions.ConnectionError:
                    print(f"🔌 {label} connection failed, trying next...")
                    continue
                except Exception as e:
                    print(f"⚠️ {label} unexpected error: {e}, trying next...")
                    continue
        
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

**⚠️ Note:** This is an auto-generated summary based on quantitative data. The AI narrative service was temporarily unavailable. All verdict scores, charts, entry/exit levels, risk analysis, and peer comparisons above are fully accurate and computed from live data. For educational purposes only — this is not investment advice.

---

## 📈 QUARTERLY FUNDAMENTALS

Revenue and earnings data is displayed in the charts and metrics above. Check the Key Numbers tab for the most current financial ratios and the Deep Analysis tab for margin trend details.

---

## 👔 MANAGEMENT & INSTITUTIONAL

Management and institutional holding data is available in the tabs above. The quantitative verdict and conviction scores are computed from 20 live data factors and do not depend on AI analysis.

---

## 🔮 WHAT'S NEXT — Catalysts & Timeline

**Next 30 Days:** Monitor upcoming earnings announcements and any sector-specific macro events. Check the Upcoming Events section in the What's Next tab for sector-specific catalysts.

**Next 90 Days:** Key factors to watch include quarterly earnings, sector rotation trends, and any regulatory or policy developments in the {_sector} space.

**Key Trigger:** Next quarterly earnings report will be the most important near-term catalyst.

**Bull Case:** Strong earnings beat + positive guidance could push toward 52-week highs at {_curr}{_w52h}.
**Bear Case:** Earnings miss or macro headwinds could test support near {_curr}{_w52l}.
**Most Likely:** Continued trading in current range with direction determined by next earnings.

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
        
        return {
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
                    # Try daily
                    hist = t.history(start=date_str, end=(trade_date + timedelta(days=3)).strftime('%Y-%m-%d'))
                
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
