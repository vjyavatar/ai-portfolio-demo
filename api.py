"""
Celesys AI - VERIFIED Real-Time Data
With built-in verification and ChatGPT comparison
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
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


# In-memory cache for stock data (expires after 5 minutes - optimized for LinkedIn launch)
stock_data_cache = {}
CACHE_EXPIRY_MINUTES = 15  # 15 min cache to avoid Yahoo Finance rate limits
CACHE_STALE_OK_MINUTES = 120  # Serve stale cache up to 2 hours if Yahoo is down

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
            "data_timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p UTC"),
            "data_source": data_source,
            "verification_url": f"https://www.google.com/finance/quote/{ticker_symbol.replace('.NS', ':NSE').replace('.BO', ':BOM')}",
        }
        
        # Fetch real 6-month price history for Price Trend chart
        try:
            import yfinance as yf
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

def _page_shell(title: str, body: str) -> str:
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — Celesys AI</title>
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
<div class="wrap"><a href="/" class="back">← Back to Celesys AI</a>
<h1>{title}</h1><p class="sub">Last updated: February 2026</p>
{body}
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
    return _page_shell("Privacy Policy", """
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
    return _page_shell("Terms of Service", """
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
    return _page_shell("About Celesys AI", """
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
    return _page_shell("Contact Us", """
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
    return _page_shell("Disclaimer", """
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
    return _page_shell("Frequently Asked Questions", """
<h2>What is Celesys AI and how does it work?</h2>
<p>Celesys AI is a free, AI-powered stock analysis platform that generates institutional-grade research reports in 60 seconds. Enter any US (NYSE, NASDAQ) or Indian (NSE, BSE) stock ticker to receive real-time valuation metrics, intrinsic value estimates using the Graham Number and DCF model, 8-factor buy/sell verdicts, quarterly earnings analysis with QoQ and YoY trends, management tone assessment, and curated small-cap picks. No signup required.</p>

<h2>Is Celesys AI free to use?</h2>
<p>Yes — 5 deep-dive reports per email per hour, completely free. No credit card, no subscription, no hidden fees. Celesys AI is funded as an educational research tool to democratize access to institutional-quality financial analysis for retail investors worldwide.</p>

<h2>Which stock markets and tickers are supported?</h2>
<p>Celesys AI supports 100+ pre-loaded US stocks (AAPL, TSLA, NVDA, GOOGL, META, MSFT, AMZN, JPM) and Indian stocks (RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS, ICICIBANK.NS). You can also enter any valid Yahoo Finance ticker for global market coverage including European, Asian, and emerging market equities.</p>

<h2>How does the 8-factor stock verdict engine work?</h2>
<p>The verdict engine scores stocks across 8 quantitative factors: P/E valuation, profitability (profit margins and ROE), financial health (debt-to-equity and current ratio), 52-week price position, price-to-book value, dividend yield, beta/volatility risk, and operating efficiency. The combined score produces a deterministic verdict — Strong Buy, Buy, Hold, Sell, or Strong Sell — that remains consistent regardless of daily price fluctuations.</p>

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

@app.get("/api/global-ticker")
async def global_ticker():
    """Lightweight global indices ticker — loads on page visit. No auth required."""
    import yfinance as yf
    
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
    
    for ticker, meta in tickers_map.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if not hist.empty:
                price = round(hist.iloc[-1]['Close'], 2)
                prev = hist.iloc[-2]['Close'] if len(hist) > 1 else price
                chg = round(price - prev, 2)
                chg_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
                results.append({
                    "name": meta["name"], "flag": meta["flag"],
                    "price": price, "change": chg, "change_pct": chg_pct
                })
                if meta["name"] == "GOLD/OZ": gold_price = price
                if meta["name"] == "SILVER/OZ": silver_price = price
        except:
            pass
    
    # Calculate GSR (Gold/Silver Ratio)
    if gold_price and silver_price and silver_price > 0:
        gsr = round(gold_price / silver_price, 1)
        results.append({"name": "GSR", "flag": "⚖️", "price": gsr, "change": 0, "change_pct": 0})
    
    return {"success": True, "indices": results}

@app.get("/api/market-pulse")
async def market_pulse():
    """Lightweight market events — no AI, instant response. Called on every Analyze click."""
    import yfinance as yf
    from datetime import datetime, timedelta
    
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
    
    # Fetch key global data for event detection
    events = []
    global_snapshot = {}
    quick_tickers = {"CL=F": "Crude Oil", "GC=F": "Gold", "DX-Y.NYB": "US Dollar", "^GSPC": "S&P 500", "INR=X": "USD/INR"}
    
    for ticker, name in quick_tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if not hist.empty:
                price = round(hist.iloc[-1]['Close'], 2)
                prev = hist.iloc[-2]['Close'] if len(hist) > 1 else price
                chg_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
                global_snapshot[name] = {"price": price, "change_pct": chg_pct}
                
                # Auto-detect events from data
                if name == "Crude Oil" and abs(chg_pct) >= 2.5:
                    direction = "spikes" if chg_pct > 0 else "crashes"
                    impact = "BEARISH" if chg_pct > 0 else "BULLISH"
                    events.append({
                        "headline": f"Crude Oil {direction} {chg_pct:+.1f}% to ${price}",
                        "impact": impact, "severity": "HIGH" if abs(chg_pct) >= 4 else "MEDIUM",
                        "detail": f"{'Higher crude increases input costs for airlines, paint, chemicals, and boosts inflation pressure on RBI.' if chg_pct > 0 else 'Lower crude benefits India as net importer. Positive for current account deficit and inflation outlook.'}",
                        "action": f"{'Watch ONGC/Oil India for gains. Avoid IndianOil, BPCL on marketing margin pressure. Negative for Nifty if sustained.' if chg_pct > 0 else 'Positive for Indian markets. Airlines, paint stocks benefit. Bank Nifty could see inflows.'}"
                    })
                elif name == "Gold" and abs(chg_pct) >= 1.5:
                    events.append({
                        "headline": f"Gold {'surges' if chg_pct > 0 else 'drops'} {chg_pct:+.1f}% to ${price}",
                        "impact": "VOLATILE", "severity": "MEDIUM",
                        "detail": f"{'Gold rally signals risk-off sentiment globally. Investors moving to safe havens.' if chg_pct > 0 else 'Gold decline suggests risk-on appetite returning. Equities may benefit.'}",
                        "action": f"{'Consider gold ETF hedge. Watch for FII outflows from equities.' if chg_pct > 0 else 'Positive for equity markets. Growth stocks could benefit.'}"
                    })
                elif name == "S&P 500" and abs(chg_pct) >= 1.0:
                    events.append({
                        "headline": f"US Markets {'rally' if chg_pct > 0 else 'sell-off'} {chg_pct:+.1f}%",
                        "impact": "BULLISH" if chg_pct > 0 else "BEARISH",
                        "severity": "HIGH" if abs(chg_pct) >= 2 else "MEDIUM",
                        "detail": f"S&P 500 {'gained' if chg_pct > 0 else 'lost'} {abs(chg_pct):.1f}%. Indian markets typically follow with 0.5-0.8x correlation.",
                        "action": f"{'Expect gap-up opening for Nifty. IT stocks (TCS, Infosys) likely to lead.' if chg_pct > 0 else 'Expect weak opening. Consider hedging with Nifty puts.'}"
                    })
                elif name == "US Dollar" and abs(chg_pct) >= 0.5:
                    events.append({
                        "headline": f"Dollar Index {'strengthens' if chg_pct > 0 else 'weakens'} {chg_pct:+.1f}%",
                        "impact": "BEARISH" if chg_pct > 0 else "BULLISH",
                        "severity": "MEDIUM",
                        "detail": f"{'Stronger dollar pressures EM currencies and triggers FII outflows from India.' if chg_pct > 0 else 'Weaker dollar supports EM inflows. Positive for FII buying in India.'}",
                        "action": f"{'Watch for INR weakness. IT exporters benefit, but FII selling risk rises.' if chg_pct > 0 else 'FII inflows likely. Banking and consumption stocks benefit.'}"
                    })
                elif name == "USD/INR" and abs(chg_pct) >= 0.3:
                    events.append({
                        "headline": f"Rupee {'weakens' if chg_pct > 0 else 'strengthens'} {chg_pct:+.1f}% to ₹{price}",
                        "impact": "BEARISH" if chg_pct > 0 else "BULLISH",
                        "severity": "HIGH" if abs(chg_pct) >= 0.8 else "MEDIUM",
                        "detail": f"{'Rupee depreciation signals capital outflows. RBI may intervene.' if chg_pct > 0 else 'Rupee strength attracts FII flows. Positive for market sentiment.'}",
                        "action": f"{'IT exporters benefit. Import-heavy sectors (oil, electronics) under pressure.' if chg_pct > 0 else 'Domestic consumption plays benefit. Watch for FII buying.'}"
                    })
        except:
            pass
    
    # Expiry event
    if is_expiry:
        exp_list = ", ".join(expiry_today)
        sev = "HIGH" if is_last_tuesday or len(expiry_today) > 1 else "MEDIUM"
        events.append({
            "headline": f"Expiry Day — {exp_list}",
            "impact": "VOLATILE", "severity": sev,
            "detail": f"{'MEGA EXPIRY: Multiple indices expire today. Expect extreme volatility, heavy institutional activity, and pin risk.' if len(expiry_today) > 2 else 'Weekly expiry for '+exp_list+'. Theta decay accelerates after 1 PM. Max Pain becomes price magnet.'}",
            "action": f"{'Reduce position sizes. Use straddles/strangles. Gamma scalping opportunities after 2 PM.' if sev == 'HIGH' else 'Watch for gamma moves near max pain after 2 PM. Theta sellers collect premium decay.'}"
        })
    
    # Upcoming scheduled events (static calendar)
    upcoming = []
    # Known RBI meeting dates 2026 (approximate — first week of Apr, Jun, Aug, Oct, Dec, Feb)
    rbi_months = [2, 4, 6, 8, 10, 12]
    for rm in rbi_months:
        rbi_date = datetime(year if rm >= now.month else year + 1, rm, 7)
        days_until = (rbi_date - now).days
        if 0 < days_until <= 30:
            upcoming.append({"event": f"RBI Monetary Policy", "date": rbi_date.strftime("%b %d"), "days": days_until, "impact": "HIGH"})
    
    # Next expiry dates
    next_tue = now + timedelta(days=(1 - weekday) % 7 or 7)
    next_thu = now + timedelta(days=(3 - weekday) % 7 or 7)
    if not (weekday == 1):
        upcoming.append({"event": "Nifty Weekly Expiry", "date": next_tue.strftime("%b %d (%a)"), "days": (next_tue - now).days, "impact": "MEDIUM"})
    if not (weekday == 3):
        upcoming.append({"event": "Sensex Weekly Expiry", "date": next_thu.strftime("%b %d (%a)"), "days": (next_thu - now).days, "impact": "MEDIUM"})
    
    # US Fed (approx — Jan, Mar, May, Jun, Jul, Sep, Nov, Dec)
    fed_months = [1, 3, 5, 6, 7, 9, 11, 12]
    for fm in fed_months:
        fed_date = datetime(year if fm >= now.month else year + 1, fm, 18)
        days_until = (fed_date - now).days
        if 0 < days_until <= 30:
            upcoming.append({"event": "US Fed Rate Decision", "date": fed_date.strftime("%b %d"), "days": days_until, "impact": "HIGH"})
    
    # Sort upcoming by days
    upcoming.sort(key=lambda x: x["days"])
    
    return {
        "success": True,
        "date": date_str,
        "day": day_name,
        "ist_time": now.strftime("%I:%M %p IST"),
        "is_expiry": is_expiry,
        "expiry_today": expiry_today,
        "events": events[:3],  # Top 3 events
        "upcoming": upcoming[:5],  # Next 5 upcoming
        "global_snapshot": global_snapshot
    }

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
        price_arrow = '🔴 ↓' if live_data['price_change'] < 0 else '🟢 ↑'
        
        live_data_section = f"""
╔═══════════════════════════════════════════════════════════════╗
║  🔴 REAL-TIME MARKET DATA                                     ║
║  Data as of: {live_data['data_timestamp']}       ║
╚═══════════════════════════════════════════════════════════════╝

CURRENT MARKET SNAPSHOT:
• Ticker: {live_data['ticker']}
• Company: {live_data['company_name']}
• Current Price: {currency_symbol}{live_data['current_price']:,.2f}
• Change Today: {price_arrow} {currency_symbol}{abs(live_data['price_change']):.2f} ({live_data['price_change_pct']:+.2f}%)

VALUATION METRICS (CURRENT):
• P/E Ratio: {live_data['pe_ratio']}
• P/B Ratio: {live_data['pb_ratio']}
• Dividend Yield: {live_data['dividend_yield']}%
• 52-Week High: {currency_symbol}{live_data['week52_high']:,.2f}
• 52-Week Low: {currency_symbol}{live_data['week52_low']:,.2f}
• Market Cap: {currency_symbol}{live_data['market_cap']:,} if available

FINANCIAL HEALTH (LATEST):
• Profit Margin: {live_data['profit_margin']}%
• Operating Margin: {live_data['operating_margin']}%
• ROE: {live_data['roe']}%
• Debt/Equity: {live_data['debt_to_equity']}
• Current Ratio: {live_data['current_ratio']}
• EPS (TTM): {live_data['eps_ttm']}
• EPS (Forward): {live_data['eps_forward']}
• Book Value/Share: {live_data['book_value']}
• Free Cash Flow: {live_data.get('free_cash_flow', 'N/A')}
• Operating Cash Flow: {live_data.get('operating_cash_flow', 'N/A')}
• Revenue Growth: {live_data.get('revenue_growth', 'N/A')}%

COMPANY INFORMATION:
• Sector: {live_data['sector']}
• Industry: {live_data['industry']}
• Beta: {live_data['beta']}

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
Current Price: {currency_symbol}{live_data['current_price']:,.2f}
Price Change Today: {live_data['price_change_pct']:+.2f}%
P/E Ratio: {live_data['pe_ratio']}
Forward P/E: {live_data.get('forward_pe', 'N/A')}
P/B Ratio: {live_data['pb_ratio']}
Market Cap: {currency_symbol}{live_data['market_cap']:,}
Dividend Yield: {live_data['dividend_yield']}%
Beta: {live_data['beta']}
52-Week High: {currency_symbol}{live_data['week52_high']:,.2f}
52-Week Low: {currency_symbol}{live_data['week52_low']:,.2f}
Price vs 52W High: {((live_data['current_price']/live_data['week52_high'])*100) if live_data['week52_high'] > 0 else 0:.1f}%
Price vs 52W Low: {((live_data['current_price']/live_data['week52_low'])*100) if live_data['week52_low'] > 0 else 0:.1f}%
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
        v_price = live_data['current_price']
        v_hi = live_data['week52_high']
        v_lo = live_data['week52_low']
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
        
        # COMPUTE VERDICT
        if v_score >= 25: v_verdict = "STRONG BUY"; v_emoji = "🟢"
        elif v_score >= 12: v_verdict = "BUY"; v_emoji = "🟢"
        elif v_score >= -8: v_verdict = "HOLD"; v_emoji = "🟡"
        elif v_score >= -22: v_verdict = "SELL"; v_emoji = "🔴"
        else: v_verdict = "STRONG SELL"; v_emoji = "🔴"
        
        v_conviction = "High" if abs(v_score) > 30 else "Medium" if abs(v_score) > 15 else "Low"
        
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

CRITICAL INSTRUCTIONS:
1. Use ONLY the real-time data provided above
2. Current price is {currency_symbol}{live_data['current_price']:,.2f} - use THIS number
3. Base all analysis on current market conditions
4. Provide actionable, professional insights
5. Your Recommendation MUST be: {v_verdict} {v_emoji} — this is pre-computed from 8 quantitative factors and is NON-NEGOTIABLE
5. For Management Tone section, use analyst/earnings data if available, otherwise infer from P/E, margins, price position, beta, and dividend yield
6. For QoQ and YoY analysis: if quarterly data is provided, calculate actual changes. If NOT provided, use available metrics to INFER trends (e.g., forward PE vs trailing PE shows earnings growth/decline, profit margins indicate operational trends, price vs 52W range shows momentum)
7. Include specific growth predictions based on available data
8. ALWAYS provide a 12-month price prediction with specific bull/base/bear numbers
9. ABSOLUTE RULE — NEVER use these phrases in your report: "data corrupted", "HTML fragments", "insufficient data", "data limitation", "incomplete data", "cannot provide", "data unavailable", "technical website code", "UNKNOWN". Instead, ALWAYS analyze using whatever data IS available. Every metric (P/E, margins, price, 52W range) tells a story — use them.
10. If quarterly earnings numbers are missing, calculate implied growth from: (a) Forward PE vs Trailing PE gap = earnings growth expectation, (b) Price position in 52W range = momentum, (c) Profit margin level = operational health, (d) Dividend yield = cash flow confidence. Present these as "Implied QoQ/YoY Trends" with specific inferences.
11. The user is paying for a COMPLETE analysis. Every section must have substantive content with specific numbers and actionable insights. No empty sections, no disclaimers about missing data.

═══════════════════════════════════════════════════════════════
📊 COMPREHENSIVE INVESTMENT ANALYSIS: {company.upper()}
═══════════════════════════════════════════════════════════════
**Report Date:** {datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")}
**Data Source:** Real-Time Market Data + AI Analysis
**Platform:** Celesys AI

---

## 🎯 INVESTMENT THESIS

**Current Price:** {currency_symbol}{live_data['current_price']:,.2f} {live_data['currency']}  
**Recommendation:** {v_verdict} {v_emoji} (Score: {v_score:+d})  
**Conviction:** {v_conviction}  
**Time Horizon:** [Short/Long-term based on the data]

[Explain WHY this {v_verdict} verdict makes sense. Reference the factor breakdown. Do NOT contradict the verdict.]

---

## 💰 LIVE VALUATION ANALYSIS

```
┌──────────────────────────────────────────────────────┐
│ METRIC               LIVE VALUE     ASSESSMENT       │
├──────────────────────────────────────────────────────┤
│ Current Price        {currency_symbol}{live_data['current_price']:<10,.2f}  [Today's price] │
│ P/E Ratio            {str(live_data['pe_ratio']):<13}  [vs industry]  │
│ P/B Ratio            {str(live_data['pb_ratio']):<13}  [vs industry]  │
│ Price vs 52W High    [Calculate %]     [Position]    │
│ Price vs 52W Low     [Calculate %]     [Position]    │
└──────────────────────────────────────────────────────┘
```

---

## ⚠️ RISK ASSESSMENT

[Standard 5-category risk analysis using current data]

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

---

## 🏦 TOP FUND & INSTITUTIONAL HOLDINGS

**Smart Money Snapshot:** [If fund/institutional data is provided above, list the top 5 holders with % ownership. Comment on: Are big funds accumulating or reducing? Is institutional ownership high (>60%) = strong backing, or low = under the radar?]

**Top Holders:** [List top 5 institutional/mutual fund holders from the data. Format: "1. Vanguard (8.2%) 2. BlackRock (6.1%) etc." If data not available, note that institutional data was not available and skip this.]

**What Smart Money Tells Us:** [High institutional ownership = validation by professional analysts. Rising institutional % = accumulation phase. Declining = distribution/exit. Low institutional = either undiscovered gem or avoided for reasons.]

---

## 🔮 WHAT'S NEXT — Catalysts & Timeline

**Next 30 Days:** [What specific events/catalysts are coming? Earnings date, ex-dividend date, product launches, regulatory decisions, macro events]

**Next 90 Days:** [Medium-term catalysts — seasonal trends, industry events, guidance updates, competitive dynamics that will impact price]

**Next 12 Months:** [Big picture — growth trajectory, expansion plans, sector tailwinds/headwinds, regulatory changes, M&A potential]

**Key Trigger to Watch:** [The single most important catalyst that will determine if this stock goes up or down. Be specific — "Q3 earnings on [date]" or "Fed rate decision" or "New product launch in [month]"]

**Bull Case Scenario:** [If everything goes right — specific price target with reasoning]
**Bear Case Scenario:** [If things go wrong — specific downside target with reasoning]
**Most Likely Scenario:** [Your base case with probability assessment]

---

## 🎯 ENTRY & EXIT STRATEGY

**Based on LIVE Price: {currency_symbol}{live_data['current_price']:,.2f}**

```
Buy Below:        {currency_symbol}XXX  [Your target based on current price]
Current Price:    {currency_symbol}{live_data['current_price']:,.2f}  ◄── LIVE PRICE
Sell Above:       {currency_symbol}XXX  [Your target]
Stop Loss:        {currency_symbol}XXX  [Risk management]
```

---

## 🌟 10-YEAR SMALL-CAP RECOMMENDATIONS

[Include small-cap recommendations as before]

---

## 💡 BOTTOM LINE

**Current Assessment ({live_data['data_timestamp']}):**

**Verdict: {v_verdict} {v_emoji}** (Conviction: {v_conviction}, Score: {v_score:+d})

Based on real-time price of {currency_symbol}{live_data['current_price']:,.2f}:
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

        # CALL CLAUDE API
        if not ANTHROPIC_API_KEY:
            raise HTTPException(500, "AI analysis service is not configured. Please contact support at contact@celesys.ai.")
        
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=90
            )
        except requests.exceptions.Timeout:
            raise HTTPException(504, "AI analysis timed out. Please try again — the servers may be busy.")
        except requests.exceptions.ConnectionError:
            raise HTTPException(502, "Could not connect to AI service. Please try again in a moment.")
        
        if response.status_code == 429:
            raise HTTPException(503, "AI service is temporarily overloaded. Please wait 30 seconds and try again.")
        elif response.status_code == 401:
            raise HTTPException(500, "API key is invalid or expired. Please check your ANTHROPIC_API_KEY.")
        elif response.status_code == 529:
            raise HTTPException(503, "AI service is temporarily overloaded. Please wait a moment and try again.")
        elif response.status_code != 200:
            # Extract useful error info
            try:
                err_body = response.json()
                err_msg = err_body.get("error", {}).get("message", response.text[:200])
            except:
                err_msg = response.text[:200]
            raise HTTPException(500, f"AI service error ({response.status_code}): {err_msg}")
        
        result = response.json()
        report = result["content"][0]["text"]
        
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
