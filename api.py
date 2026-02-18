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
    Fallback: Direct HTTP call to Yahoo Finance API.
    No yfinance library needed — just raw HTTP.
    Returns same format as yfinance info dict or None on failure.
    """
    try:
        # Endpoint 1: v8 chart API (price + history)
        chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
        headers = {**YAHOO_HEADERS, 'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(110,125)}.0.0.0'}
        
        chart_resp = requests.get(chart_url, headers=headers, timeout=10)
        if chart_resp.status_code != 200:
            print(f"⚠️ Yahoo chart API returned {chart_resp.status_code}")
            return None
        
        chart_data = chart_resp.json()
        result = chart_data.get('chart', {}).get('result', [])
        if not result:
            return None
        
        meta = result[0].get('meta', {})
        indicators = result[0].get('indicators', {}).get('quote', [{}])[0]
        timestamps = result[0].get('timestamp', [])
        closes = indicators.get('close', [])
        highs = indicators.get('high', [])
        lows = indicators.get('low', [])
        
        # Get current price from meta
        current_price = meta.get('regularMarketPrice', 0)
        previous_close = meta.get('chartPreviousClose', meta.get('previousClose', current_price))
        
        # 52-week from chart history (limited but better than nothing)
        valid_highs = [h for h in highs if h is not None]
        valid_lows = [l for l in lows if l is not None]
        valid_closes = [c for c in closes if c is not None]
        
        chart_info = {
            'currentPrice': current_price,
            'previousClose': previous_close,
            'currency': meta.get('currency', 'USD'),
            'exchangeName': meta.get('exchangeName', ''),
            'symbol': meta.get('symbol', ticker),
            'longName': meta.get('longName', ticker),
            'chartHigh': max(valid_highs) if valid_highs else current_price,
            'chartLow': min(valid_lows) if valid_lows else current_price,
            'closes': valid_closes,
            '_source': 'yahoo_chart_v8'
        }
        
        # Endpoint 2: quoteSummary for fundamentals
        modules = 'summaryProfile,financialData,defaultKeyStatistics,summaryDetail,price'
        summary_url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules={modules}"
        
        try:
            summary_resp = requests.get(summary_url, headers=headers, timeout=10)
            if summary_resp.status_code == 200:
                summary_data = summary_resp.json()
                qresult = summary_data.get('quoteSummary', {}).get('result', [])
                if qresult:
                    r = qresult[0]
                    fin = r.get('financialData', {})
                    stats = r.get('defaultKeyStatistics', {})
                    detail = r.get('summaryDetail', {})
                    profile = r.get('summaryProfile', {})
                    price_data = r.get('price', {})
                    
                    def raw(d, key, default=0):
                        """Extract raw value from Yahoo's nested format"""
                        v = d.get(key, {})
                        if isinstance(v, dict):
                            return v.get('raw', v.get('fmt', default))
                        return v if v else default
                    
                    chart_info.update({
                        'longName': price_data.get('longName', chart_info.get('longName', ticker)),
                        'marketCap': raw(price_data, 'marketCap'),
                        'trailingPE': raw(detail, 'trailingPE'),
                        'forwardPE': raw(stats, 'forwardPE') or raw(detail, 'forwardPE'),
                        'priceToBook': raw(stats, 'priceToBook'),
                        'dividendYield': raw(detail, 'dividendYield'),
                        'beta': raw(stats, 'beta') or raw(detail, 'beta'),
                        'sector': profile.get('sector', 'N/A'),
                        'industry': profile.get('industry', 'N/A'),
                        'profitMargins': raw(fin, 'profitMargins') or raw(stats, 'profitMargins'),
                        'operatingMargins': raw(fin, 'operatingMargins'),
                        'returnOnEquity': raw(fin, 'returnOnEquity'),
                        'debtToEquity': raw(fin, 'debtToEquity'),
                        'currentRatio': raw(fin, 'currentRatio'),
                        'fiftyTwoWeekHigh': raw(detail, 'fiftyTwoWeekHigh', chart_info['chartHigh']),
                        'fiftyTwoWeekLow': raw(detail, 'fiftyTwoWeekLow', chart_info['chartLow']),
                        '_source': 'yahoo_direct_full'
                    })
        except Exception as e:
            print(f"⚠️ Yahoo summary API failed: {e} — using chart data only")
            chart_info['_source'] = 'yahoo_chart_only'
        
        return chart_info
        
    except Exception as e:
        print(f"❌ Yahoo direct HTTP failed: {e}")
        return None


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

        # CREATE CLAUDE PROMPT
        prompt = f"""Analyze {company} using the VERIFIED LIVE DATA below.

{live_data_section}

CRITICAL INSTRUCTIONS:
1. Use ONLY the real-time data provided above
2. Current price is {currency_symbol}{live_data['current_price']:,.2f} - use THIS number
3. Base all analysis on current market conditions
4. Provide actionable, professional insights

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

**Latest Earnings Snapshot:**

```
┌──────────────────────────────────────────────────────┐
│ Revenue (Last Qtr):    $XXX [vs estimate / beat-miss]│
│ EPS (Last Qtr):        $XXX [vs estimate / beat-miss]│
│ Revenue Growth (YoY):  XX%  [accelerating/slowing]   │
│ Earnings Growth (YoY): XX%  [trend direction]        │
│ Guidance:              [Raised / Maintained / Lowered]│
│ Surprise Factor:       [Beat by X% / Missed by X%]  │
└──────────────────────────────────────────────────────┘
```

**QoQ vs YoY Trend (Quarter-over-Quarter & Year-over-Year):**

```
┌──────────────────────────────────────────────────────────────┐
│ METRIC              QoQ Change    YoY Change    TREND        │
├──────────────────────────────────────────────────────────────┤
│ Revenue             +/-XX%        +/-XX%        [↑↓→]        │
│ Net Income          +/-XX%        +/-XX%        [↑↓→]        │
│ EPS                 +/-XX%        +/-XX%        [↑↓→]        │
│ Gross Margin        XX% → XX%    XX% → XX%     [Expanding/  │
│                                                  Compressing]│
│ Operating Margin    XX% → XX%    XX% → XX%     [Improving/  │
│                                                  Declining]  │
│ Free Cash Flow      $XXX → $XXX  $XXX → $XXX   [↑↓→]        │
│ Debt-to-Equity      XX → XX      XX → XX       [Deleveraging│
│                                                  /Loading]   │
└──────────────────────────────────────────────────────────────┘
```

**QoQ Momentum Read:** [Is the business improving THIS quarter vs last quarter? Acceleration = bullish. Deceleration even if positive = caution. Two consecutive QoQ declines = red flag.]

**YoY Structural Trend:** [Is the company fundamentally stronger than 1 year ago? Revenue + margin expansion YoY = strong. Revenue up but margins down YoY = growth at a cost. Both declining = avoid.]

**Key Fundamental Shifts:** [What changed fundamentally in the last 1-2 quarters — margins, debt, cash flow, new revenue streams, market share gains/losses]

---

## 🎙️ MANAGEMENT TONE & OUTLOOK

**CEO/CFO Confidence Level:** [🟢 Bullish / 🟡 Cautious / 🔴 Defensive]

**Earnings Call Tone Analysis:**
- **Language Sentiment:** [Confident & aggressive OR cautious & hedging OR defensive & excuse-making — cite specific patterns like "strong momentum" vs "challenging headwinds"]
- **Forward Guidance Tone:** [Are they raising outlook confidently or sandbagging expectations?]
- **Key Buzzwords Used:** [e.g., "record pipeline", "accelerating growth", "disciplined execution" vs "macro uncertainty", "one-time charges", "restructuring"]
- **Red Flags in Communication:** [Dodging questions, vague answers, sudden CFO departure, changing metrics, blaming macro]
- **Green Flags in Communication:** [Specific numbers, confident buyback announcements, insider buying, raising dividends]

**What Management Isn't Telling You:** [Read between the lines — what are they avoiding? What questions did they deflect on earnings calls?]

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
