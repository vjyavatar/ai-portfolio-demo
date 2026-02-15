"""
B2B Research Agent using LangGraph
Workflow: Search SEC/SEBI filings -> Analyze -> Generate Risk Report
"""

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
import os
from datetime import datetime


class AgentState(TypedDict):
    """State passed between nodes"""
    company_name: str
    search_results: str
    analysis: str
    final_report: str
    comparison_data: str  # NEW: For company comparisons
    historical_data: str  # NEW: Historical trends
    peer_data: str       # NEW: Peer benchmarking
    error: str | None


class B2BResearchAgent:
    def __init__(self, anthropic_api_key: str, tavily_api_key: str):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=anthropic_api_key,
            temperature=0
        )
        self.tavily_api_key = tavily_api_key
        self.graph = self._build_graph()
        self.cache = {}  # Cache for faster repeated queries
    
    def _build_graph(self):
        """Build the LangGraph state machine"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("search", self.search_node)
        workflow.add_node("analyze", self.analyze_node)
        workflow.add_node("report", self.report_node)
        
        # Define edges
        workflow.set_entry_point("search")
        workflow.add_edge("search", "analyze")
        workflow.add_edge("analyze", "report")
        workflow.add_edge("report", END)
        
        return workflow.compile()
    
    def search_node(self, state: AgentState) -> AgentState:
        """Node 1: Search for company data from premium financial platforms"""
        try:
            from tavily import TavilyClient
            
            client = TavilyClient(api_key=self.tavily_api_key)
            company = state["company_name"]
            
            all_results = []
            
            # ==========================================
            # INDIA - Premium Financial Platforms
            # ==========================================
            
            # 1. Moneycontrol - Financial results, press releases, corporate actions
            india_moneycontrol = [
                f"{company} financial results site:moneycontrol.com",
                f"{company} quarterly results site:moneycontrol.com",
                f"{company} annual report site:moneycontrol.com"
            ]
            
            for query in india_moneycontrol:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'India',
                            'source': 'Moneycontrol',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 2. Screener.in - Detailed financials, ratios, filings
            india_screener = [
                f"{company} financial ratios site:screener.in",
                f"{company} quarterly results site:screener.in",
                f"{company} annual report site:screener.in"
            ]
            
            for query in india_screener:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'India',
                            'source': 'Screener.in',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 3. BSE India - Official exchange disclosures
            india_bse = [
                f"{company} announcements site:bseindia.com",
                f"{company} corporate actions site:bseindia.com"
            ]
            
            for query in india_bse:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'India',
                            'source': 'BSE India',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 4. NSE India - Official exchange disclosures
            india_nse = [
                f"{company} announcements site:nseindia.com",
                f"{company} corporate actions site:nseindia.com"
            ]
            
            for query in india_nse:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'India',
                            'source': 'NSE India',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 5. Trendlyne - Analytics and insights
            india_trendlyne = [
                f"{company} analysis site:trendlyne.com",
                f"{company} financials site:trendlyne.com"
            ]
            
            for query in india_trendlyne:
                try:
                    results = client.search(query, max_results=1)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'India',
                            'source': 'Trendlyne',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # ==========================================
            # USA - Premium Financial Platforms
            # ==========================================
            
            # 1. Yahoo Finance - Earnings, analysis, filings
            usa_yahoo = [
                f"{company} earnings site:finance.yahoo.com",
                f"{company} financials site:finance.yahoo.com",
                f"{company} SEC filings site:finance.yahoo.com"
            ]
            
            for query in usa_yahoo:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'USA',
                            'source': 'Yahoo Finance',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 2. MarketWatch - Financial news and analysis
            usa_marketwatch = [
                f"{company} earnings site:marketwatch.com",
                f"{company} financial results site:marketwatch.com"
            ]
            
            for query in usa_marketwatch:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'USA',
                            'source': 'MarketWatch',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 3. SEC EDGAR - Official filings
            usa_sec = [
                f"{company} 10-K annual report site:sec.gov",
                f"{company} 10-Q quarterly report site:sec.gov"
            ]
            
            for query in usa_sec:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'USA',
                            'source': 'SEC EDGAR',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 4. Zacks - Earnings estimates and analysis
            usa_zacks = [
                f"{company} earnings estimates site:zacks.com",
                f"{company} analyst ratings site:zacks.com"
            ]
            
            for query in usa_zacks:
                try:
                    results = client.search(query, max_results=1)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'USA',
                            'source': 'Zacks',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 5. Bloomberg - Premium financial data (if available)
            usa_bloomberg = [
                f"{company} earnings site:bloomberg.com",
                f"{company} financial analysis site:bloomberg.com"
            ]
            
            for query in usa_bloomberg:
                try:
                    results = client.search(query, max_results=1)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'USA',
                            'source': 'Bloomberg',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # ==========================================
            # GLOBAL - Other Markets
            # ==========================================
            
            # 2. INDIA - SEBI/Stock Exchange Filings
            india_queries = [
                f"{company} annual report site:bseindia.com OR site:nseindia.com",
                f"{company} SEBI filing site:sebi.gov.in",
                f"{company} quarterly results BSE NSE"
            ]
            
            for query in india_queries:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'India',
                            'source': 'SEBI/Stock Exchange',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 3. UK - Companies House & FCA
            uk_queries = [
                f"{company} annual report site:companieshouse.gov.uk",
                f"{company} financial statements UK Companies House"
            ]
            
            for query in uk_queries:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'UK',
                            'source': 'Companies House',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 4. EUROPE - EU Regulatory Filings
            eu_queries = [
                f"{company} annual report ESMA filing",
                f"{company} financial statements European Securities"
            ]
            
            for query in eu_queries:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'EU',
                            'source': 'ESMA/European Regulators',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 5. CANADA - SEDAR
            canada_queries = [
                f"{company} SEDAR filing site:sedar.com",
                f"{company} annual information form Canada"
            ]
            
            for query in canada_queries:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'Canada',
                            'source': 'SEDAR',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 6. AUSTRALIA - ASX
            aus_queries = [
                f"{company} annual report site:asx.com.au",
                f"{company} ASX announcement Australia"
            ]
            
            for query in aus_queries:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'Australia',
                            'source': 'ASX',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 7. CHINA/HONG KONG - HKEX, CSRC
            china_queries = [
                f"{company} annual report site:hkexnews.hk",
                f"{company} Hong Kong Exchange filing"
            ]
            
            for query in china_queries:
                try:
                    results = client.search(query, max_results=2)
                    for result in results.get('results', []):
                        all_results.append({
                            'country': 'China/Hong Kong',
                            'source': 'HKEX',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
                except:
                    continue
            
            # 8. Generic company filings search (catch-all)
            generic_query = f'"{company}" annual report OR financial statements OR regulatory filing'
            try:
                results = client.search(generic_query, max_results=3)
                for result in results.get('results', []):
                    # Avoid duplicates
                    if not any(r['url'] == result['url'] for r in all_results):
                        all_results.append({
                            'country': 'Global',
                            'source': 'General Search',
                            'title': result['title'],
                            'url': result['url'],
                            'content': result['content']
                        })
            except:
                pass
            
            # Format results
            if all_results:
                formatted_results = []
                
                # Group by source for better organization
                sources_seen = {}
                for result in all_results[:20]:  # Limit to top 20
                    source_key = f"{result['country']}-{result['source']}"
                    
                    if source_key not in sources_seen:
                        sources_seen[source_key] = []
                    sources_seen[source_key].append(result)
                
                # Format grouped results
                idx = 1
                for source_key, results in sources_seen.items():
                    for result in results:
                        formatted_results.append(
                            f"[{idx}] {result['source']} ({result['country']})\n"
                            f"Title: {result['title']}\n"
                            f"URL: {result['url']}\n"
                            f"Content: {result['content'][:400]}...\n"
                        )
                        idx += 1
                
                search_summary = "\n---\n".join(formatted_results)
                
                # Add summary header
                unique_sources = len(sources_seen)
                total_results = len(all_results[:20])
                search_summary = f"Found {total_results} results from {unique_sources} premium sources:\n\n" + search_summary
                
            else:
                search_summary = f"No financial data found for '{company}'. This company may:\n- Not be publicly traded\n- File under a different legal name\n- Be a private company without public filings\n\nPlease verify the company name and try again."
            
            state["search_results"] = search_summary
            return state
            
        except Exception as e:
            state["error"] = f"Search failed: {str(e)}"
            state["search_results"] = f"Search unavailable for {state['company_name']}"
            return state
    
    def analyze_node(self, state: AgentState) -> AgentState:
        """Node 2: Analyze filings for risks"""
        try:
            system_prompt = """You are a financial analyst specializing in corporate risk assessment.
            Analyze the provided regulatory filings and identify key business risks across these categories:
            1. Financial risks (liquidity, debt, revenue concentration)
            2. Operational risks (supply chain, technology, workforce)
            3. Market risks (competition, market conditions, customer dependencies)
            4. Regulatory/Legal risks (compliance, litigation, regulatory changes)
            5. Strategic risks (business model, innovation, execution)
            
            Provide a structured analysis with specific evidence from the filings."""
            
            user_prompt = f"""Company: {state['company_name']}
            
Filing Information:
{state['search_results']}

Analyze these filings and identify the top 5 most material risks for this company. 
For each risk, provide:
- Risk category
- Specific evidence from filings
- Potential impact (High/Medium/Low)
- Brief explanation"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            state["analysis"] = response.content
            return state
            
        except Exception as e:
            state["error"] = f"Analysis failed: {str(e)}"
            state["analysis"] = "Analysis unavailable"
            return state
    
    def report_node(self, state: AgentState) -> AgentState:
        """Node 3: Generate professional, visual report with decision graphics"""
        try:
            system_prompt = """You are an elite business consultant creating investor-grade risk reports with VISUAL DECISION FRAMEWORKS.

CRITICAL: Include visual decision graphics showing SHORT-TERM vs LONG-TERM strategies.

REPORT STRUCTURE WITH VISUAL ELEMENTS:

# 📊 Company Risk Assessment: [Company Name]

**Report Date:** [Today's Date]  
**Analysis Coverage:** [Countries/Sources]  
**Overall Risk Rating:** [🔴 High / 🟡 Moderate / 🟢 Low] **({Score}/10)**

---

## 📋 Executive Summary

[3-4 sentences with KEY TAKEAWAY highlighted]

---

## 🎯 Risk Score Dashboard (VISUAL)

```
┌─────────────────────────────────────────────────────┐
│           RISK HEAT MAP                             │
├─────────────────────────────────────────────────────┤
│ Financial Health:      ████░░░░░░ 4/10 🟡 Moderate │
│ Market Position:       ███░░░░░░░ 3/10 🟢 Low      │
│ Operational Stability: ███████░░░ 7/10 🔴 High     │
│ Regulatory Compliance: ██████░░░░ 6/10 🟡 Moderate │
│ Strategic Execution:   ████████░░ 8/10 🔴 High     │
├─────────────────────────────────────────────────────┤
│ OVERALL RISK SCORE:    █████░░░░░ 5.6/10 🟡        │
└─────────────────────────────────────────────────────┘
```

---

## ⚠️ Top 5 Material Risks

### 1. [Risk Name] - 🔴/🟡/🟢 [Severity]

**What it is:** [One sentence]  
**Why it matters:** [Plain English impact]  
**Evidence:** [Specific data]  
**Likelihood:** █████░░░░░ High/Medium/Low  
**Financial Impact:** $X - $Y million

**Risk Timeline:**
```
Immediate (0-3 months):  🔴 Critical attention needed
Short-term (3-12 months): 🟡 Monitor closely  
Long-term (1-3 years):   🟢 Manageable with action
```

[Repeat for 5 risks]

---

## 🎯 VISUAL DECISION FRAMEWORK

### Investment Decision Matrix

```
                    HIGH RETURN POTENTIAL
                            ▲
                            │
                   ┌────────┼────────┐
                   │        │        │
    LOW RISK  ◄────┤  HOLD  │  BUY   │────► HIGH RISK
                   │        │        │
                   │  SELL  │ AVOID  │
                   └────────┼────────┘
                            │
                    LOW RETURN POTENTIAL

    Current Position: [Mark with ★]
```

### Short-Term vs Long-Term Strategy

```
╔═══════════════════════════════════════════════════════════════╗
║                   DECISION TIMELINE                           ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  SHORT-TERM (0-12 months)                                     ║
║  ═══════════════════════════                                  ║
║  Risk Level: 🔴🟡🟢                                            ║
║  Strategy:   [SPECIFIC ACTION]                                ║
║  Expected:   [OUTCOME]                                        ║
║  Monitor:    [KEY METRICS]                                    ║
║                                                               ║
║  ┌─────────────────────────────────────────┐                 ║
║  │ IF [Condition]:  DO [Action]            │                 ║
║  │ IF [Condition]:  DO [Action]            │                 ║
║  └─────────────────────────────────────────┘                 ║
║                                                               ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  LONG-TERM (1-3 years)                                        ║
║  ═══════════════════════                                      ║
║  Risk Level: 🔴🟡🟢                                            ║
║  Strategy:   [SPECIFIC ACTION]                                ║
║  Expected:   [OUTCOME]                                        ║
║  Watch For:  [CATALYSTS]                                      ║
║                                                               ║
║  ┌─────────────────────────────────────────┐                 ║
║  │ BULLISH IF:  [Conditions]               │                 ║
║  │ BEARISH IF:  [Conditions]               │                 ║
║  └─────────────────────────────────────────┘                 ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## 💡 Scenario Analysis (VISUAL)

### Best Case Scenario 📈
```
Risk Score: 2/10 🟢
Timeline: 12-24 months
Probability: 30%

Triggers:
▸ [Positive catalyst 1]
▸ [Positive catalyst 2]

Impact: +X% upside potential
```

### Base Case Scenario 📊
```
Risk Score: 5/10 🟡
Timeline: Current
Probability: 50%

Assumptions:
▸ [Current trend continues]
▸ [Market remains stable]

Impact: Status quo
```

### Worst Case Scenario 📉
```
Risk Score: 8/10 🔴
Timeline: 6-12 months
Probability: 20%

Triggers:
▸ [Negative catalyst 1]
▸ [Negative catalyst 2]

Impact: -X% downside risk
```

---

## ✅ Action Plan with Decision Tree

### For Investors

```
START HERE
    │
    ├─→ Short-term trader (0-6 months)?
    │   ├─→ YES → [Specific action + exit criteria]
    │   └─→ NO  → Continue
    │
    ├─→ Long-term investor (1-3 years)?
    │   ├─→ YES → [Specific action + milestones]
    │   └─→ NO  → Continue
    │
    └─→ Value/Growth investor?
        ├─→ VALUE  → [Value-specific strategy]
        └─→ GROWTH → [Growth-specific strategy]
```

**Immediate Actions (Next 30 days):**
1. 🔴 CRITICAL: [Action]
2. 🟡 IMPORTANT: [Action]
3. 🟢 MONITOR: [Metric]

**Quarterly Reviews (Every 3 months):**
- Check: [Metric 1]
- Verify: [Metric 2]
- Assess: [Trend]

**Annual Assessment:**
- Re-evaluate overall risk score
- Update long-term strategy
- Adjust position size

---

## 📊 Key Metrics Dashboard

```
┌────────────────────────────────────────┐
│  FINANCIAL HEALTH INDICATORS           │
├────────────────────────────────────────┤
│  Revenue Growth:     [XX]% ░░░░░░████ │
│  Profit Margin:      [XX]% ░░████████ │
│  Debt/Equity:        [X.X] ████░░░░░░ │
│  Cash Position:      $XXB  ████████░░ │
│  Return on Equity:   [XX]% ░░░░██████ │
└────────────────────────────────────────┘

Trend: ↗ Improving | → Stable | ↘ Declining
```

---

## 🎯 Quick Decision Guide

**Should I Invest NOW?**

```
╔════════════════════════════════════════╗
║  Risk Tolerance:                       ║
║  ○ Conservative  → [Recommendation]    ║
║  ○ Moderate      → [Recommendation]    ║
║  ○ Aggressive    → [Recommendation]    ║
╚════════════════════════════════════════╝
```

**What's the RIGHT price?**

```
Current Price:  $XXX
Fair Value:     $XXX (based on analysis)
Buy Below:      $XXX (10% margin of safety)
Sell Above:     $XXX (target upside)
```

---

## 📚 Data Sources
[List sources with confidence level]

---

**Disclaimer:** AI-generated report. Not financial advice. Consult professionals before investing.

---

TONE REQUIREMENTS:
- Use ASCII art for visual impact
- Include decision trees and flowcharts
- Provide specific numbers and thresholds
- Make it actionable for both short and long-term investors
- Use visual indicators (bars, arrows, symbols) liberally
- Translate everything to plain English
- Give specific "IF-THEN" decision rules"""
            
            user_prompt = f"""Create a VISUAL, decision-oriented risk report for: {state['company_name']}

ANALYSIS:
{state['analysis']}

DATA (first 1000 chars):
{state['search_results'][:1000]}

REQUIREMENTS:
1. Create visual ASCII risk dashboard with bars (████)
2. Include SHORT-TERM vs LONG-TERM decision framework
3. Add decision matrix showing investment position
4. Provide scenario analysis (best/base/worst case)
5. Include decision tree for different investor types
6. Use visual indicators throughout (🔴🟡🟢, ↗↘, ████)
7. Give specific entry/exit prices if applicable
8. Make it scannable with boxes and visual separators
9. Provide "IF-THEN" decision rules
10. Keep under 1000 words but maximally visual

Generate complete visual report now."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            state["final_report"] = response.content
            return state
            
        except Exception as e:
            state["error"] = f"Report generation failed: {str(e)}"
            state["final_report"] = "Report generation unavailable"
            return state
    
    def run(self, company_name: str) -> dict:
        """Execute the agent workflow"""
        initial_state = {
            "company_name": company_name,
            "search_results": "",
            "analysis": "",
            "final_report": "",
            "error": None
        }
        
        final_state = self.graph.invoke(initial_state)
        
        return {
            "company_name": final_state["company_name"],
            "report": final_state["final_report"],
            "search_results": final_state["search_results"],  # Include for debugging
            "error": final_state.get("error"),
            "timestamp": datetime.now().isoformat()
        }


# For local testing
if __name__ == "__main__":
    # Test the agent
    agent = B2BResearchAgent(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        tavily_api_key=os.getenv("TAVILY_API_KEY")
    )
    
    result = agent.run("Tesla Inc")
    print(result["report"])
