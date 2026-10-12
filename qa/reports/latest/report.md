# Celesys QA report

161 individual regressions passed. 19 page/document routes checked. Browser suite: 104 checks defined, execution unverified (no GitHub workflow run observed). Production application repair: e3c5a408.

Run timestamp: 2026-10-12T04:12:26.314287+00:00

Target: https://celesys.ai
Checks: {'UNVERIFIED': 7, 'PASS': 68}

PASS is scoped to each check. UNVERIFIED is not a pass.

| Check | Result | Evidence |
|---|---|---|
| Source INTRADAY_MCAP_BACKEND_REFERENCE.py | UNVERIFIED | Python syntax error; may be a non-runtime snippet |
| run build | PASS | Full results: suite-0.log |
| -m unittest discover -s tests -p test_existing_engines.py | PASS | Full results: suite-1.log |
| -m unittest discover -s tests -p test_workspace_backend.py | PASS | Full results: suite-2.log |
| -m unittest discover -s tests -p test_discovery.py | PASS | Full results: suite-3.log |
| -m unittest discover -s tests -p test_trading_*.py | PASS | Full results: suite-4.log |
| -m unittest discover -s tests -p test_qa_audit.py | PASS | Full results: suite-5.log |
| Page / | PASS | HTTP 200; HTML title True; 5.39s |
| Unique IDs / | PASS | No duplicate IDs |
| Original chart entry visible | PASS | Original report form must be exposed on homepage |
| Page /about | PASS | HTTP 200; HTML title True; 5.31s |
| Unique IDs /about | PASS | No duplicate IDs |
| Page /agents | PASS | HTTP 200; HTML title True; 5.3s |
| Unique IDs /agents | PASS | No duplicate IDs |
| Page /contact | PASS | HTTP 200; HTML title True; 4.05s |
| Unique IDs /contact | PASS | No duplicate IDs |
| Page /disclaimer | PASS | HTTP 200; HTML title True; 3.67s |
| Unique IDs /disclaimer | PASS | No duplicate IDs |
| Page /faq | PASS | HTTP 200; HTML title True; 3.6s |
| Unique IDs /faq | PASS | No duplicate IDs |
| Page /googleb6e1e80f88761fcc.html | PASS | HTTP 200; verified search-engine ownership resource; 4.09s |
| Unique IDs /googleb6e1e80f88761fcc.html | PASS | No duplicate IDs |
| Page /learn | PASS | HTTP 200; HTML title True; 4.1s |
| Unique IDs /learn | PASS | No duplicate IDs |
| Page /learn/how-to-read-option-chain | PASS | HTTP 200; HTML title True; 3.97s |
| Unique IDs /learn/how-to-read-option-chain | PASS | No duplicate IDs |
| Page /learn/open-interest-and-pcr | PASS | HTTP 200; HTML title True; 3.83s |
| Unique IDs /learn/open-interest-and-pcr | PASS | No duplicate IDs |
| Page /learn/paper-trading-checklist | PASS | HTTP 200; HTML title True; 3.77s |
| Unique IDs /learn/paper-trading-checklist | PASS | No duplicate IDs |
| Page /methodology | PASS | HTTP 200; HTML title True; 3.73s |
| Unique IDs /methodology | PASS | No duplicate IDs |
| Page /options/india | PASS | HTTP 200; HTML title True; 4.18s |
| Unique IDs /options/india | PASS | No duplicate IDs |
| Page /options/us | PASS | HTTP 200; HTML title True; 4.11s |
| Unique IDs /options/us | PASS | No duplicate IDs |
| Page /privacy | PASS | HTTP 200; HTML title True; 3.22s |
| Unique IDs /privacy | PASS | No duplicate IDs |
| Page /research | PASS | HTTP 200; HTML title True; 3.27s |
| Unique IDs /research | PASS | No duplicate IDs |
| Page /terms | PASS | HTTP 200; HTML title True; 5.63s |
| Unique IDs /terms | PASS | No duplicate IDs |
| Page /today | PASS | HTTP 200; HTML title True; 5.64s |
| Unique IDs /today | PASS | No duplicate IDs |
| Page /trading/ | PASS | HTTP 200; HTML title True; 3.68s |
| Unique IDs /trading/ | PASS | No duplicate IDs |
| Asset /discovery/agents.js | PASS | HTTP 200; 4977 bytes |
| Asset /discovery/analytics.js | PASS | HTTP 200; 850 bytes |
| Asset /discovery/options.js | PASS | HTTP 200; 5158 bytes |
| Asset /discovery/site.css | PASS | HTTP 200; 7694 bytes |
| Asset /static/active-trading.js?v=20261012-unified | PASS | HTTP 200; 568922 bytes |
| Asset /static/app.min.js?v=20261012-unified | PASS | HTTP 200; 3645242 bytes |
| Asset /static/celesys-ds.css?v=1778612666 | PASS | HTTP 200; 35163 bytes |
| Asset /static/options-engine.js?v=20261002-validation | PASS | HTTP 200; 745506 bytes |
| Asset /static/premium-override.js?v=1778612666 | PASS | HTTP 200; 615142 bytes |
| Asset /static/premium-theme.css?v=1775315896 | PASS | HTTP 200; 29518 bytes |
| Asset /static/workspace-core.js?v=20261012-unified | PASS | HTTP 200; 4018 bytes |
| Asset /static/workspace.css?v=20261012-unified | PASS | HTTP 200; 15172 bytes |
| Asset /static/workspace.js?v=20261012-unified | PASS | HTTP 200; 23118 bytes |
| Asset /trading/desk.css | PASS | HTTP 200; 15492 bytes |
| Asset /trading/desk.js | PASS | HTTP 200; 19992 bytes |
| Data /health | PASS | Service healthy |
| Data /api/research-brief?mode=stock&symbol=AAPL&region=US | PASS | 24 source-labelled facts; financial correctness and freshness require separate verification |
| Data /api/research-brief?mode=stock&symbol=RELIANCE&region=IN | PASS | 20 source-labelled facts; financial correctness and freshness require separate verification |
| Data /api/research-brief?mode=trading&symbol=SPY&region=US | PASS | 15 source-labelled facts; financial correctness and freshness require separate verification |
| Data /api/research-brief?mode=trading&symbol=NIFTY&region=IN | PASS | 15 source-labelled facts; financial correctness and freshness require separate verification |
| Data /api/existing-option-chain?symbol=SPY&region=US | PASS | 51 strikes; snapshot structure only, quote freshness not certified |
| Data /api/existing-option-chain?symbol=NIFTY&region=IN | UNVERIFIED | Feed unavailable; no working live option chain verified |
| Retired /api/upstox-login | PASS | HTTP 410, expected 410 |
| Retired /api/upstox-status | PASS | HTTP 410, expected 410 |
| Actual chart canvases rendered | UNVERIFIED | Requires browser/authorized fixtures or independent data; not certified by document/schema checks |
| All 50 menu output correctness | UNVERIFIED | Requires browser/authorized fixtures or independent data; not certified by document/schema checks |
| Authorized-user server identity | UNVERIFIED | Requires browser/authorized fixtures or independent data; not certified by document/schema checks |
| Voice microphone and audible playback | UNVERIFIED | Requires browser/authorized fixtures or independent data; not certified by document/schema checks |
| Independent financial calculation reconciliation | UNVERIFIED | Requires browser/authorized fixtures or independent data; not certified by document/schema checks |

## Every menu

| Tool | UI access profiles | Functional output |
|---|---|---|
| Summary | public, trading, full, premium, dream, admin | UNVERIFIED |
| AI Analysis | full, premium, dream, admin | UNVERIFIED |
| DCF Valuation | full, premium, dream, admin | UNVERIFIED |
| Research | full, premium, dream, admin | UNVERIFIED |
| Compare Stocks | public, trading, full, premium, dream, admin | UNVERIFIED |
| Analyze Stock | full, premium, dream, admin | UNVERIFIED |
| Tomorrow's Open | full, premium, dream, admin | UNVERIFIED |
| Dashboard | full, premium, dream, admin | UNVERIFIED |
| Engines | full, premium, dream, admin | UNVERIFIED |
| Top Trades | full, premium, dream, admin | UNVERIFIED |
| Top Investments | full, premium, dream, admin | UNVERIFIED |
| Smart Money v3 | full, premium, dream, admin | UNVERIFIED |
| Smart Money | full, premium, dream, admin | UNVERIFIED |
| Micro-Cap Hunter | full, premium, dream, admin | UNVERIFIED |
| Intraday Setups | full, premium, dream, admin | UNVERIFIED |
| Positioning | full, premium, dream, admin | UNVERIFIED |
| Diamond Hunter | full, premium, dream, admin | UNVERIFIED |
| Analyst Coverage | full, premium, dream, admin | UNVERIFIED |
| Pro Scan | premium, dream, admin | UNVERIFIED |
| ETF Scanner | full, premium, dream, admin | UNVERIFIED |
| Reports | full, premium, dream, admin | UNVERIFIED |
| PMS | premium, dream, admin | UNVERIFIED |
| Dream Portfolio | dream, admin | UNVERIFIED |
| Multibagger Hunter | dream, admin | UNVERIFIED |
| Momentum Radar | dream, admin | UNVERIFIED |
| High-Prob Setups | dream, admin | UNVERIFIED |
| Options Pulse | dream, admin | UNVERIFIED |
| Trade Ticket | dream, admin | UNVERIFIED |
| Micro-Cap Challenge | dream, admin | UNVERIFIED |
| Algo Trades | trading, full, premium, dream, admin | UNVERIFIED |
| Smart Trades | premium, dream, admin | UNVERIFIED |
| Stock Intel | premium, dream, admin | UNVERIFIED |
| Scanner | trading, full, premium, dream, admin | UNVERIFIED |
| Valuation | premium, dream, admin | UNVERIFIED |
| Backtest | premium, dream, admin | UNVERIFIED |
| Journal | premium, dream, admin | UNVERIFIED |
| AI Assistant | premium, dream, admin | UNVERIFIED |
| Top Performers | full, premium, dream, admin | UNVERIFIED |
| Market Daily | full, premium, dream, admin | UNVERIFIED |
| News Impact | full, premium, dream, admin | UNVERIFIED |
| Global Assets | full, premium, dream, admin | UNVERIFIED |
| Top Movers | full, premium, dream, admin | UNVERIFIED |
| Moat Analysis | full, premium, dream, admin | UNVERIFIED |
| Structural Change | full, premium, dream, admin | UNVERIFIED |
| Intraday Options | trading, full, premium, dream, admin | UNVERIFIED |
| 360° Scanner | full, premium, dream, admin | UNVERIFIED |
| Finance Tools | public, trading, full, premium, dream, admin | UNVERIFIED |
| Education | public, trading, full, premium, dream, admin | UNVERIFIED |
| Active Trading | full, premium, dream, admin | UNVERIFIED |
| Today’s Setups | dream, admin | UNVERIFIED |
