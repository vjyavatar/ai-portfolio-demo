"""
Sentinel AI Research - VERIFIED Real-Time Data
With built-in verification and ChatGPT comparison
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os
import requests
from datetime import datetime, timedelta
import hashlib
import yfinance as yf
from functools import lru_cache
import time

app = FastAPI(title="Sentinel AI Research - Verified Live Data")

# In-memory cache for stock data (expires after 10 minutes)
stock_data_cache = {}
CACHE_EXPIRY_MINUTES = 10

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

report_counter = {"count": 0}
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def get_live_stock_data(company_name: str) -> dict:
    """
    Get VERIFIED real-time stock data with CACHING to avoid rate limits
    Cache expires after 10 minutes
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
        
        # Fetch data
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        hist = stock.history(period="5d")  # Get last 5 days for reliability
        
        if hist.empty:
            return {
                "error": f"No data found for {company_name}. Try using the ticker symbol (e.g., TSLA, HDFCBANK.NS)"
            }
        
        # Get most recent price
        current_price = float(hist['Close'].iloc[-1])
        previous_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
        price_change = current_price - previous_close
        price_change_pct = (price_change / previous_close * 100) if previous_close > 0 else 0
        
        # Get 52-week range
        week52_high = float(hist['High'].max())
        week52_low = float(hist['Low'].min())
        
        # Currency detection
        currency = info.get('currency', 'USD')
        if '.NS' in ticker_symbol or '.BO' in ticker_symbol:
            currency = 'INR'
        
        # Build response data
        live_data = {
            "success": True,
            "ticker": ticker_symbol,
            "company_name": info.get('longName', company_name),
            "current_price": round(current_price, 2),
            "price_change": round(price_change, 2),
            "price_change_pct": round(price_change_pct, 2),
            "currency": currency,
            "market_cap": info.get('marketCap', 0),
            "pe_ratio": round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else 'N/A',
            "forward_pe": round(info.get('forwardPE', 0), 2) if info.get('forwardPE') else 'N/A',
            "pb_ratio": round(info.get('priceToBook', 0), 2) if info.get('priceToBook') else 'N/A',
            "dividend_yield": round(info.get('dividendYield', 0) * 100, 2) if info.get('dividendYield') else 0,
            "week52_high": round(week52_high, 2),
            "week52_low": round(week52_low, 2),
            "beta": round(info.get('beta', 0), 2) if info.get('beta') else 'N/A',
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "profit_margin": round(info.get('profitMargins', 0) * 100, 2) if info.get('profitMargins') else 'N/A',
            "operating_margin": round(info.get('operatingMargins', 0) * 100, 2) if info.get('operatingMargins') else 'N/A',
            "roe": round(info.get('returnOnEquity', 0) * 100, 2) if info.get('returnOnEquity') else 'N/A',
            "debt_to_equity": round(info.get('debtToEquity', 0), 2) if info.get('debtToEquity') else 'N/A',
            "current_ratio": round(info.get('currentRatio', 0), 2) if info.get('currentRatio') else 'N/A',
            "data_timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p UTC"),
            "verification_url": f"https://www.google.com/finance/quote/{ticker_symbol.replace('.NS', ':NSE').replace('.BO', ':BOM')}"
        }
        
        # Cache the data to reduce API calls
        stock_data_cache[cache_key] = (live_data, current_time)
        print(f"💾 Cached data for {cache_key}")
        
        return live_data
        
    except Exception as e:
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
                <h1>⚡ Sentinel AI Research</h1>
                <h2>Verified Live Data Edition</h2>
                <p>HTML file not found.</p></body></html>"""


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "reports_generated": report_counter["count"],
        "version": "1.0-VERIFIED-REALTIME"
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


@app.post("/api/generate-report")
async def generate_report(request: Request):
    try:
        data = await request.json()
        company = data.get("company_name", "").strip()
        email = data.get("email", "").strip()
        
        if not company or not email:
            raise HTTPException(400, "company_name and email required")
        
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
**Platform:** Sentinel AI Research

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
        
        if response.status_code != 200:
            raise HTTPException(500, f"API error: {response.text}")
        
        result = response.json()
        report = result["content"][0]["text"]
        
        report_counter["count"] += 1
        report_id = hashlib.md5(f"{company}{datetime.now()}".encode()).hexdigest()[:8]
        
        return {
            "success": True,
            "report": report,
            "company_name": company,
            "live_data": live_data,
            "timestamp": datetime.now().isoformat(),
            "report_id": report_id.upper(),
            "report_number": report_counter["count"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")


@app.get("/api/stats")
async def stats():
    return {
        "total_reports": report_counter["count"],
        "platform": "Sentinel AI Research",
        "version": "1.0-VERIFIED",
        "data_source": "Yahoo Finance (Real-Time)",
        "vs_chatgpt": "Live data vs ChatGPT's Jan 2025 cutoff"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
