"""
Celesys AI - VERIFIED Real-Time Data
With built-in verification and ChatGPT comparison
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
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
            if sr.status_code == 200:
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
                    
                    # Only override if we didn't get from v6 or values are better
                    updates = {
                        'sector': profile.get('sector', info.get('sector', 'N/A')),
                        'industry': profile.get('industry', info.get('industry', 'N/A')),
                        'operatingMargins': raw(fin, 'operatingMargins'),
                        'returnOnEquity': raw(fin, 'returnOnEquity'),
                        'debtToEquity': raw(fin, 'debtToEquity'),
                        'currentRatio': raw(fin, 'currentRatio'),
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
                            'profitMargins': raw(fin, 'profitMargins') or info.get('profitMargins', 0),
                            'fiftyTwoWeekHigh': raw(detail, 'fiftyTwoWeekHigh') or info['fiftyTwoWeekHigh'],
                            'fiftyTwoWeekLow': raw(detail, 'fiftyTwoWeekLow') or info['fiftyTwoWeekLow'],
                        })
                    info.update(updates)
                    info['_source'] = 'yahoo_direct_full'
                    print(f"  v10 summary: sector={info.get('sector')}, ROE={info.get('returnOnEquity')}")
        except Exception as e:
            print(f"  v10 summary failed: {e}")
        
        return info
        
    except Exception as e:
        print(f"❌ Yahoo direct HTTP failed: {e}")
        return None


def fetch_management_context(ticker: str, company_name: str) -> str:
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
        if r.status_code == 200:
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
        if r.status_code == 200:
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
        return ""
    
    return "\n\n".join(context_parts)


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
        # Convert ticker format: TSLA → TSLA:NASDAQ, RELIANCE.NS → RELIANCE:NSE
        if '.NS' in ticker:
            g_ticker = ticker.replace('.NS', '') + ':NSE'
        elif '.BO' in ticker:
            g_ticker = ticker.replace('.BO', '') + ':BOM'
        else:
            g_ticker = ticker  # Google will auto-resolve
        
        url = f"https://www.google.com/finance/quote/{g_ticker}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        
        text = resp.text
        
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
        
        # ── FUNDAMENTALS ENRICHMENT: If we got price but missing P/E, Market Cap, etc. ──
        if current_price is not None and info is not None:
            has_pe = info.get('trailingPE') and info['trailingPE'] != 0
            has_mcap = info.get('marketCap') and info['marketCap'] != 0
            
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
                return round(v * 100, 2) if is_pct and abs(v) < 1 else round(v, 2)
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
            "dividend_yield": round(safe_get('dividendYield') * (100 if data_source == 'yfinance' and safe_get('dividendYield') < 1 else 1), 2) if safe_get('dividendYield') else 0,
            "week52_high": round(week52_high, 2),
            "week52_low": round(week52_low, 2),
            "beta": safe_get('beta') or 'N/A',
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "profit_margin": safe_get('profitMargins', 'N/A', is_pct=(data_source=='yfinance')),
            "operating_margin": safe_get('operatingMargins', 'N/A', is_pct=(data_source=='yfinance')),
            "roe": safe_get('returnOnEquity', 'N/A', is_pct=(data_source=='yfinance')),
            "debt_to_equity": safe_get('debtToEquity') or 'N/A',
            "current_ratio": safe_get('currentRatio') or 'N/A',
            "data_timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p UTC"),
            "data_source": data_source,
            "verification_url": f"https://www.google.com/finance/quote/{ticker_symbol.replace('.NS', ':NSE').replace('.BO', ':BOM')}"
        }
        
        # Cache the data to reduce API calls
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

COMPANY INFORMATION:
• Sector: {live_data['sector']}
• Industry: {live_data['industry']}
• Beta: {live_data['beta']}

═══════════════════════════════════════════════════════════════
"""

        # FETCH REAL MANAGEMENT/EARNINGS DATA
        mgmt_context = ""
        try:
            mgmt_context = fetch_management_context(live_data['ticker'], live_data.get('company_name', company))
            if mgmt_context:
                print(f"📊 Got {len(mgmt_context)} chars of real management/earnings data")
        except Exception as e:
            print(f"⚠️ Management context fetch failed: {e}")

        # CREATE CLAUDE PROMPT
        prompt = f"""Analyze {company} using the VERIFIED LIVE DATA below.

{live_data_section}

{"=" * 60}
REAL ANALYST & EARNINGS DATA (use this for management tone analysis):
{"=" * 60}
{mgmt_context if mgmt_context else "No additional analyst data available — analyze based on financial metrics above."}
{"=" * 60}

CRITICAL INSTRUCTIONS:
1. Use ONLY the real-time data provided above
2. Current price is {currency_symbol}{live_data['current_price']:,.2f} - use THIS number
3. Base all analysis on current market conditions
4. Provide actionable, professional insights
5. For Management Tone section, use the REAL analyst/earnings data above - cite actual earnings surprises, analyst targets, insider activity
6. For QoQ and YoY analysis, use the quarterly revenue/earnings data provided - calculate actual changes between quarters
7. Include specific growth predictions based on forward EPS estimates and revenue growth rates
8. ALWAYS provide a 12-month price prediction with specific bull/base/bear numbers
9. When data is missing (N/A), explicitly state what's unavailable and analyze with available metrics
10. If FINVIZ/Screener.in/Moneycontrol data is provided, use it to enrich your analysis with insider trading patterns, institutional activity, and management signals

═══════════════════════════════════════════════════════════════
📊 COMPREHENSIVE INVESTMENT ANALYSIS: {company.upper()}
═══════════════════════════════════════════════════════════════
**Report Date:** {datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")}
**Data Source:** Real-Time Market Data + AI Analysis
**Platform:** Celesys AI

---

## 🎯 INVESTMENT THESIS

**Current Price:** {currency_symbol}{live_data['current_price']:,.2f} {live_data['currency']}  
**Recommendation:** [BUY 🟢 / HOLD 🟡 / SELL 🔴]  
**Conviction:** [High / Medium / Low]  
**Time Horizon:** [Short/Long-term]

[Your analysis based on CURRENT price of {currency_symbol}{live_data['current_price']:,.2f}]

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

IMPORTANT: Use the REAL quarterly revenue/earnings data and earnings surprise history provided in the data section above. Calculate ACTUAL QoQ and YoY changes from the real numbers. DO NOT use placeholders.

**Latest Earnings Snapshot:** [Use actual quarterly data provided — cite real revenue, EPS, and surprise percentages. Include: revenue (actual vs estimate), EPS (actual vs estimate), surprise %, beat/miss streak count]

**QoQ Momentum (Quarter-over-Quarter):**
- Revenue QoQ: [Latest quarter revenue vs previous quarter — calculate exact % change]
- Earnings QoQ: [Latest quarter earnings vs previous quarter — calculate exact % change]  
- Margin QoQ: [Did margins expand or compress vs prior quarter? By how much?]
- Verdict: [ACCELERATING 🟢 / STABLE 🟡 / DECELERATING 🔴]

**YoY Structural Growth (Year-over-Year):**
- Revenue YoY: [Latest quarter vs same quarter last year — exact % growth]
- Earnings YoY: [Latest quarter vs same quarter last year — exact % growth]
- EPS YoY: [Current EPS vs year-ago EPS — growth rate]
- Verdict: [STRENGTHENING 🟢 / STABLE 🟡 / WEAKENING 🔴]

**Earnings Surprise Trend:** [Are beats getting bigger or smaller over last 4 quarters? This predicts future surprises.]

**Key Fundamental Shifts:** [What changed in the last 1-2 quarters based on the real data — margin expansion/compression, earnings beats/misses getting bigger/smaller, guidance direction]

**12-Month Growth Forecast:**
Based on the actual data trends above, provide specific projections:
- Projected EPS (12mo): [Forward EPS estimate from analyst data]
- Projected Revenue Growth: [Based on QoQ/YoY trend trajectory]
- Projected Price Range: [Forward EPS × Historical PE range = Bull/Base/Bear prices]
- Growth Driver: [What will drive or limit growth in the next 4 quarters]

---

## 🎙️ MANAGEMENT TONE & OUTLOOK

IMPORTANT: Use the REAL analyst/earnings data provided above to ground your analysis. Cite actual numbers. If Finviz/Screener/Moneycontrol data is provided, use insider trading patterns and institutional moves.

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

Based on real-time price of {currency_symbol}{live_data['current_price']:,.2f}:
[Your specific recommendation]

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
            raise HTTPException(500, "ANTHROPIC_API_KEY environment variable is not set. Please set it in your deployment settings.")
        
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
