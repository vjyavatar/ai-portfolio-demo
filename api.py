"""
Sentinel AI Research - Comprehensive Investment Analysis API
Combines risk assessment + valuation + visual analytics
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os
import requests
from datetime import datetime
import hashlib

# Initialize
app = FastAPI(title="Sentinel AI Research - Agentic Investment Intelligence")

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
                <h1>⚡ Sentinel AI Research</h1>
                <h2>Agentic Investment Intelligence</h2>
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
        "platform": "Sentinel AI Research",
        "version": "1.0-Agentic"
    }


@app.post("/api/generate-report")
async def generate_report(request: Request):
    try:
        data = await request.json()
        company = data.get("company_name", "").strip()
        email = data.get("email", "").strip()
        
        if not company or not email:
            raise HTTPException(400, "company_name and email required")
        
        # Comprehensive analysis prompt combining risk + valuation + visuals
        prompt = f"""You are an advanced agentic AI investment analyst. Create a COMPREHENSIVE analysis for "{company}" that combines risk assessment with investment metrics and visual analytics.

Generate a professional report with the following structure. Use TABLES, CHARTS, and VISUAL formatting to make it easy to scan and understand.

═══════════════════════════════════════════════════════════════
📊 COMPREHENSIVE INVESTMENT ANALYSIS: {company.upper()}
═══════════════════════════════════════════════════════════════
Generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}
Platform: Sentinel AI Research | Agentic Investment Intelligence
Report ID: [Generate unique 8-char ID]

---

## 🎯 EXECUTIVE SUMMARY & INVESTMENT THESIS

**Investment Recommendation:** [BUY 🟢 / HOLD 🟡 / SELL 🔴]  
**Conviction Level:** [High / Medium / Low]  
**Price Action:** [Value Play / Growth Story / Turnaround / Avoid]  
**Time Horizon:** [Short-term (0-6mo) / Medium-term (6-18mo) / Long-term (1-3yr)]

**One-Line Summary:**  
[Write a single compelling sentence summarizing the investment case]

**Key Thesis:**  
[2-3 sentences explaining why this is a buy/hold/sell]

---

## 💰 VALUATION METRICS TABLE

```
┌──────────────────────────────────────────────────────────┐
│ METRIC              │ CURRENT │ INDUSTRY │ ASSESSMENT │
├──────────────────────────────────────────────────────────┤
│ Current Price       │  $XXX   │    -     │     -      │
│ Fair Value Est.     │  $XXX   │    -     │  ±XX%      │
│ Upside/Downside     │  +XX%   │    -     │  🟢🟡🔴    │
├──────────────────────────────────────────────────────────┤
│ P/E Ratio           │  XX.X   │   XX.X   │  🟢🟡🔴    │
│ P/B Ratio           │  X.XX   │   X.XX   │  🟢🟡🔴    │
│ EV/EBITDA           │  XX.X   │   XX.X   │  🟢🟡🔴    │
│ Price/Sales         │  X.XX   │   X.XX   │  🟢🟡🔴    │
│ Dividend Yield      │  X.X%   │   X.X%   │  🟢🟡🔴    │
├──────────────────────────────────────────────────────────┤
│ Market Cap          │  $XXB   │    -     │     -      │
│ Enterprise Value    │  $XXB   │    -     │     -      │
└──────────────────────────────────────────────────────────┘
```

**Overall Valuation:** 🟢 Undervalued / 🟡 Fair / 🔴 Overvalued

---

## 📈 VISUAL PERFORMANCE TRENDS (5-Year Analysis)

### Revenue Growth Trajectory
```
2020:  $XX.XB  ████████████░░░░░░░░ (Base Year)
2021:  $XX.XB  ██████████████░░░░░░ (+XX%)
2022:  $XX.XB  ████████████████░░░░ (+XX%)
2023:  $XX.XB  ███████████████████░ (+XX%)
2024:  $XX.XB  ████████████████████ (+XX%)
───────────────────────────────────────────
5-Year CAGR: XX% | Industry Avg: XX% | Trend: ↗↘→
```

### Profit Margin Evolution
```
Operating Margin:
2020: XX% ████████░░░░░░░░░░
2021: XX% ██████████░░░░░░░░
2022: XX% ████████████░░░░░░
2023: XX% ████████████░░░░░░
2024: XX% ██████████████░░░░
───────────────────────────────────
Net Margin:
2020: XX% ██████░░░░░░░░░░░░
2021: XX% ████████░░░░░░░░░░
2022: XX% ████████░░░░░░░░░░
2023: XX% ██████████░░░░░░░░
2024: XX% ██████████░░░░░░░░

Margin Trend: ↗ Expanding / → Stable / ↘ Contracting
```

### Financial Health Metrics
```
┌─────────────────────────────────────────────┐
│ METRIC               VALUE    VISUAL  TARGET│
├─────────────────────────────────────────────┤
│ Debt/Equity          X.XX  ██████░░░░  <2.0 │
│ Current Ratio        X.XX  ████████░░  >1.5 │
│ Interest Coverage    XX.X  ██████████  >3.0 │
│ Cash Position        $XXB  ████████░░   -   │
│ Free Cash Flow       $XXB  ████████░░   -   │
└─────────────────────────────────────────────┘

Financial Strength: 🟢 Strong / 🟡 Adequate / 🔴 Weak
```

---

## ⚠️ COMPREHENSIVE RISK ASSESSMENT DASHBOARD

```
╔═══════════════════════════════════════════════════════════╗
║ RISK CATEGORY           SCORE    VISUAL      SEVERITY     ║
╠═══════════════════════════════════════════════════════════╣
║ Financial Health        X/10   ████████░░   🟢🟡🔴        ║
║ Market Position         X/10   ████████░░   🟢🟡🔴        ║
║ Operational Risks       X/10   ████████░░   🟢🟡🔴        ║
║ Regulatory/Legal        X/10   ████████░░   🟢🟡🔴        ║
║ Competition Risk        X/10   ████████░░   🟢🟡🔴        ║
╠═══════════════════════════════════════════════════════════╣
║ OVERALL RISK SCORE      X/10   ████████░░   🟢🟡🔴        ║
╚═══════════════════════════════════════════════════════════╝

Risk Legend: 🟢 Low (1-3) | 🟡 Moderate (4-6) | 🔴 High (7-10)
```

### Top 5 Material Risks (Detailed)

**1. [Risk Name] - [🔴/🟡/🟢 Severity]**
   - **Impact:** [High/Medium/Low]
   - **Likelihood:** [High/Medium/Low]
   - **Description:** [2-3 sentences]
   - **Mitigation:** [What could reduce this risk]

**2. [Risk Name] - [🔴/🟡/🟢 Severity]**
   - **Impact:** [High/Medium/Low]
   - **Likelihood:** [High/Medium/Low]
   - **Description:** [2-3 sentences]
   - **Mitigation:** [What could reduce this risk]

[Repeat for risks 3-5]

---

## 🎯 ENTRY & EXIT STRATEGY

### Price Target Matrix
```
┌─────────────────────────────────────────────────┐
│ ZONE               PRICE RANGE    ACTION        │
├─────────────────────────────────────────────────┤
│ Strong Buy Zone    $XXX - $XXX   🟢 Accumulate │
│ Buy Zone           $XXX - $XXX   🟢 Add         │
│ Current Price      $XXX.XX       ▶ HERE        │
│ Hold Zone          $XXX - $XXX   🟡 Monitor     │
│ Take Profit Zone   $XXX - $XXX   🔴 Trim        │
│ Full Exit Zone     $XXX+          🔴 Sell       │
├─────────────────────────────────────────────────┤
│ Stop Loss          $XXX (-XX%)    ⛔ HARD STOP  │
└─────────────────────────────────────────────────┘
```

### Price Targets (12-Month Horizon)
- **Conservative Target:** $XXX (+XX% upside)
- **Base Case Target:** $XXX (+XX% upside)
- **Optimistic Target:** $XXX (+XX% upside)
- **Downside Risk:** $XXX (-XX% downside)

### Position Sizing Recommendations
```
Portfolio Risk Profile:
  Conservative Investor:   X-X%  of portfolio
  Moderate Investor:       X-X%  of portfolio
  Aggressive Investor:     X-X%  of portfolio
  
Suggested Entry: [Lump sum / Dollar-cost average over X weeks]
```

---

## 📊 PEER COMPARISON TABLE

```
┌──────────────────────────────────────────────────────────────┐
│ METRIC          │ {company} │ Competitor A │ Competitor B  │
├──────────────────────────────────────────────────────────────┤
│ P/E Ratio       │   XX.X   │     XX.X    │     XX.X      │
│ Revenue Growth  │   XX%    │     XX%     │     XX%       │
│ Profit Margin   │   XX%    │     XX%     │     XX%       │
│ Market Share    │   XX%    │     XX%     │     XX%       │
│ ROE             │   XX%    │     XX%     │     XX%       │
│ Debt/Equity     │   X.X    │     X.X     │     X.X       │
└──────────────────────────────────────────────────────────────┘

Competitive Position: [Industry Leader / Strong Player / Average / Weak]
Relative Valuation: [Premium / In-line / Discount] to peers
```

---

## 🚀 KEY CATALYSTS (Bullish Drivers)

**Near-Term (0-6 months):**
1. **[Catalyst Name]:** [Specific trigger and potential impact]
2. **[Catalyst Name]:** [Specific trigger and potential impact]
3. **[Catalyst Name]:** [Specific trigger and potential impact]

**Medium-Term (6-18 months):**
1. **[Catalyst Name]:** [Specific trigger and potential impact]
2. **[Catalyst Name]:** [Specific trigger and potential impact]

---

## ⚠️ KEY RED FLAGS (Risk Factors)

**Immediate Concerns:**
1. **[Red Flag]:** [Why this matters and potential impact]
2. **[Red Flag]:** [Why this matters and potential impact]
3. **[Red Flag]:** [Why this matters and potential impact]

**Watch Items:**
- [Item to monitor]
- [Item to monitor]
- [Item to monitor]

---

## 📅 UPCOMING EVENTS TO MONITOR

```
┌────────────────────────────────────────────┐
│ EVENT              DATE        IMPORTANCE  │
├────────────────────────────────────────────┤
│ Earnings Report    MMM DD      ⭐⭐⭐      │
│ Product Launch     MMM DD      ⭐⭐        │
│ FDA Decision       MMM DD      ⭐⭐⭐      │
│ Conference Call    MMM DD      ⭐          │
└────────────────────────────────────────────┘
```

---

## 💡 ACTIONABLE RECOMMENDATIONS

### For Short-Term Traders (0-6 months):
**Strategy:** [Specific actionable advice]
**Entry:** [When and how to enter]
**Exit:** [When to take profits]
**Risk Management:** [Stop loss and position sizing]

### For Long-Term Investors (1-3 years):
**Strategy:** [Specific actionable advice]
**Accumulation Plan:** [How to build position]
**Hold Criteria:** [What would make you continue holding]
**Sell Triggers:** [What would make you exit]

### Key Monitoring Points:
- ✓ Watch for: [Specific metric or event]
- ✓ Re-evaluate if: [Specific condition]
- ✓ Take profits if: [Specific target or trigger]
- ✓ Cut losses if: [Specific red flag]

---

## 📌 BOTTOM LINE SUMMARY

**In One Sentence:**  
[Final verdict in plain English]

**Action Steps:**
1. [Immediate action to take]
2. [Second step]
3. [Third step]

**Expected Outcome (12 months):**  
[Realistic expectation for return and volatility]

═══════════════════════════════════════════════════════════════
⚠️ DISCLAIMER: Educational research only. NOT financial advice.
Consult a Certified Financial Advisor before investing.
Sentinel AI Research is not responsible for investment outcomes.
═══════════════════════════════════════════════════════════════

**Report Generated:** {datetime.now().strftime("%B %d, %Y at %I:%M %p")} UTC
**Analysis Platform:** Sentinel AI Research - Agentic Investment Intelligence
**Contact:** research@sentinelai-research.org

═══════════════════════════════════════════════════════════════

CRITICAL INSTRUCTIONS:
- Fill in ALL placeholders (XXX, XXXX, etc.) with REAL estimates based on the company
- Use actual competitor names
- Make visual bars proportional to actual values
- Provide specific, actionable insights
- Be realistic with price targets and timeframes
- Use tables and visual formatting extensively
- Make it scannable and easy to understand
- Combine detailed analysis with visual clarity"""

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
                "max_tokens": 4096,
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
        report_id = hashlib.md5(f"{company}{datetime.now()}".encode()).hexdigest()[:8]
        
        return {
            "success": True,
            "report": report,
            "company_name": company,
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
        "type": "Agentic Investment Intelligence"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
