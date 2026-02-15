"""
Investment Analysis API - Enhanced with Valuation & Graphics
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os
import requests
from datetime import datetime
import hashlib

# Initialize
app = FastAPI(title="AI Investment Analysis")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

report_counter = {"count": 0}
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the main HTML page"""
    try:
        with open("index.html", "r") as f:
            return f.read()
    except:
        return """
        <html>
            <body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1>📊 AI Investment Analysis</h1>
                <p>HTML file not found. Please add index.html to your repository.</p>
            </body>
        </html>
        """


@app.get("/health")
async def health():
    """API health check"""
    return {
        "status": "healthy",
        "reports_generated": report_counter["count"],
        "message": "AI Investment Analysis API"
    }


@app.post("/api/generate-report")
async def generate_report(request: Request):
    try:
        data = await request.json()
        company = data.get("company_name", "").strip()
        email = data.get("email", "").strip()
        
        if not company or not email:
            raise HTTPException(400, "company_name and email required")
        
        # Enhanced investment analysis prompt
        prompt = f"""You are a professional investment analyst. Analyze "{company}" and create a comprehensive investment report.

STRUCTURE YOUR REPORT EXACTLY AS FOLLOWS:

# 📊 INVESTMENT ANALYSIS: {company}
**Generated:** {datetime.now().strftime("%B %d, %Y")}

---

## 🎯 INVESTMENT THESIS

[In 2-3 sentences, state your clear recommendation: BUY / HOLD / SELL and why]

**Recommendation:** [BUY 🟢 / HOLD 🟡 / SELL 🔴]  
**Conviction Level:** [High / Medium / Low]  
**Time Horizon:** [Short-term (0-6 months) / Long-term (1-3 years)]

---

## 💰 VALUATION METRICS

```
Current Price:        $XXX.XX
Fair Value Estimate:  $XXX.XX (±X% from current)
Upside/Downside:     +/-XX%

P/E Ratio:           XX.X  [vs Industry Avg: XX.X]
P/B Ratio:           X.X   [vs Industry Avg: X.X]
EV/EBITDA:          XX.X  [vs Industry Avg: XX.X]
Price/Sales:         X.X   [vs Industry Avg: X.X]
Dividend Yield:      X.X%  [if applicable]

Market Cap:          $XXB
Enterprise Value:    $XXB
```

**Valuation Assessment:**  
🟢 Undervalued / 🟡 Fairly Valued / 🔴 Overvalued

---

## 📈 VISUAL PERFORMANCE ANALYSIS

### 5-Year Revenue Trend
```
2020: $XXB  ████████░░░░░░░░░░
2021: $XXB  ███████████░░░░░░░
2022: $XXB  ██████████████░░░░
2023: $XXB  ████████████████░░
2024: $XXB  ██████████████████
```
**Growth Rate:** XX% CAGR | Industry Avg: XX%

### Profit Margin Trend
```
2020: XX%  ████████░░░░░░░░░░
2021: XX%  ██████████░░░░░░░░
2022: XX%  ███████████░░░░░░░
2023: XX%  ████████████░░░░░░
2024: XX%  █████████████░░░░░
```
**Trend:** ↗ Improving / → Stable / ↘ Declining

### Debt Analysis
```
Debt/Equity Ratio:    X.X  ████████░░ [Target: <2.0]
Interest Coverage:    X.X  ██████████ [Target: >3.0]
Current Ratio:        X.X  ████████░░ [Target: >1.5]
```

---

## ⚠️ RISK ASSESSMENT DASHBOARD

```
┌─────────────────────────────────────────────┐
│  RISK CATEGORY         SCORE    SEVERITY    │
├─────────────────────────────────────────────┤
│  Financial Health      X/10     🟢🟡🔴      │
│  Market Position       X/10     🟢🟡🔴      │
│  Operational Risk      X/10     🟢🟡🔴      │
│  Regulatory Risk       X/10     🟢🟡🔴      │
│  Competition Risk      X/10     🟢🟡🔴      │
├─────────────────────────────────────────────┤
│  OVERALL RISK SCORE    X/10     🟢🟡🔴      │
└─────────────────────────────────────────────┘
```

**Risk Legend:**  
🟢 Low Risk (1-3) | 🟡 Moderate Risk (4-6) | 🔴 High Risk (7-10)

---

## 🎯 ENTRY & EXIT STRATEGY

### Price Targets
```
Buy Zone (Accumulate):     $XXX - $XXX  🟢
Hold Zone (Current):       $XXX - $XXX  🟡
Sell Zone (Take Profit):   $XXX+        🔴

Conservative Target:       $XXX (+XX%)
Base Case Target:          $XXX (+XX%)
Optimistic Target:         $XXX (+XX%)

Stop Loss:                 $XXX (-XX%)
```

### Position Sizing Recommendation
```
Conservative Investor:     X-X% of portfolio
Moderate Investor:        X-X% of portfolio
Aggressive Investor:      X-X% of portfolio
```

**Entry Timing:** [Now / Wait for dip / Wait for breakout]

---

## 🔍 PEER COMPARISON

```
┌────────────────────────────────────────────────────┐
│ Metric        │ {company} │ Competitor A │ Competitor B │
├────────────────────────────────────────────────────┤
│ P/E Ratio     │   XX.X   │    XX.X     │    XX.X     │
│ Revenue Growth│   XX%    │    XX%      │    XX%      │
│ Profit Margin │   XX%    │    XX%      │    XX%      │
│ Market Share  │   XX%    │    XX%      │    XX%      │
└────────────────────────────────────────────────────┘
```

**Competitive Position:** [Leader / Strong / Average / Weak]

---

## 🚀 KEY CATALYSTS (Bullish Factors)

1. **[Catalyst Name]:** [Brief explanation]
2. **[Catalyst Name]:** [Brief explanation]
3. **[Catalyst Name]:** [Brief explanation]

---

## ⚠️ KEY RISKS (Red Flags)

1. **[Risk Name]:** [Brief explanation]
2. **[Risk Name]:** [Brief explanation]
3. **[Risk Name]:** [Brief explanation]

---

## 📅 UPCOMING EVENTS TO WATCH

- **Earnings Date:** [Date or "TBD"]
- **Product Launches:** [Any upcoming releases]
- **Regulatory Decisions:** [Any pending approvals/decisions]
- **Industry Events:** [Conferences, reports, etc.]

---

## 💡 BOTTOM LINE

**For Short-Term Traders (0-6 months):**  
[Specific actionable advice]

**For Long-Term Investors (1-3 years):**  
[Specific actionable advice]

**Key Monitoring Points:**
- Watch for [metric/event]
- Re-evaluate if [condition occurs]
- Take profits if [target reached]

---

## 📌 DISCLAIMER

This is an AI-generated analysis for educational purposes only. Not financial advice. 
Always conduct your own research and consult a licensed financial advisor before investing.

**Report ID:** [Generate unique ID]  
**Analysis Date:** {datetime.now().strftime("%B %d, %Y at %I:%M %p")}

---

IMPORTANT: 
- Use ACTUAL data and reasonable estimates based on the company
- Fill in ALL the XXX placeholders with real numbers
- Make the visual charts proportional to actual data
- Be specific with price targets and percentages
- Use real competitor names
- Provide actionable insights, not generic advice"""

        # Call Anthropic API
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,  # Increased for comprehensive reports
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=90
        )
        
        if response.status_code != 200:
            raise HTTPException(500, f"API error: {response.text}")
        
        result = response.json()
        report = result["content"][0]["text"]
        
        report_counter["count"] += 1
        report_id = hashlib.md5(f"{company}{datetime.now()}".encode()).hexdigest()[:12]
        
        return {
            "success": True,
            "report": report,
            "company_name": company,
            "timestamp": datetime.now().isoformat(),
            "report_id": report_id,
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
        "portfolio_mode": True,
        "pricing": "FREE"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
