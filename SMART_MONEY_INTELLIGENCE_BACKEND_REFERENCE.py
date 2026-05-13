# ═══════════════════════════════════════════════════════════════════════════
# SMART MONEY INTELLIGENCE — Backend Reference
# Frontend (r63.86.0) reads three optional time-series fields from /api/investor-decide.
# Until you wire these, the SMI panel renders empty-state cards showing exactly
# what's missing. Wire them and the panel lights up with no frontend redeploy.
# ═══════════════════════════════════════════════════════════════════════════

# ─── Required additions to /api/investor-decide response ───
#
# Add these three keys under d.institutional:

response["institutional"]["ownership_history"] = [
    {"quarter": "Q1 2024", "filing_date": "2024-02-14", "total_pct_outstanding": 62.4, "n_holders": 1620},
    {"quarter": "Q2 2024", "filing_date": "2024-05-15", "total_pct_outstanding": 65.1, "n_holders": 1701},
    {"quarter": "Q3 2024", "filing_date": "2024-08-14", "total_pct_outstanding": 67.8, "n_holders": 1758},
    {"quarter": "Q4 2024", "filing_date": "2024-11-14", "total_pct_outstanding": 70.2, "n_holders": 1789},
    {"quarter": "Q1 2025", "filing_date": "2025-02-14", "total_pct_outstanding": 72.5, "n_holders": 1812},
    {"quarter": "Q2 2025", "filing_date": "2025-05-15", "total_pct_outstanding": 74.8, "n_holders": 1825},
    {"quarter": "Q3 2025", "filing_date": "2025-08-14", "total_pct_outstanding": 76.6, "n_holders": 1841},
    {"quarter": "Q4 2025", "filing_date": "2025-11-14", "total_pct_outstanding": 78.2, "n_holders": 1847},
    # 8-12 quarters recommended. Frontend handles any length >=2.
]

response["institutional"]["top_holders_delta"] = [
    {
        "name": "BlackRock Inc.",
        "shares_prev": 12_500_000,         # holdings as of the PREVIOUS quarter's filing
        "shares_current": 14_200_000,      # holdings as of the LATEST 13F filing
        "delta_shares": 1_700_000,         # shares_current - shares_prev (signed)
        "delta_pct": 13.6,                  # ((current - prev) / prev) * 100
        "action": "ADDING",                 # "ADDING" / "REDUCING" / "HOLDING" / "NEW POSITION" / "EXITED"
        "value_usd_current": 2.85e9,        # optional — for hover/click-through
    },
    {"name": "Vanguard Group", "shares_prev": 11_300_000, "shares_current": 12_100_000,
     "delta_shares": 800_000, "delta_pct": 7.1, "action": "ADDING"},
    {"name": "State Street",   "shares_prev": 5_800_000,  "shares_current": 5_900_000,
     "delta_shares": 100_000, "delta_pct": 1.7, "action": "HOLDING"},
    {"name": "Fidelity",       "shares_prev": 4_200_000,  "shares_current": 3_800_000,
     "delta_shares": -400_000, "delta_pct": -9.5, "action": "REDUCING"},
    # Top 10 by current holding recommended.
]

# Extend the existing insider_activity object with a quarterly time series:
response["institutional"]["insider_activity"]["quarterly_history"] = [
    {"quarter": "Q1 2024", "n_buys": 2, "n_sells": 1, "buy_value_usd": 0.4e6, "sell_value_usd": 0.1e6, "net_flow_usd":  0.3e6},
    {"quarter": "Q2 2024", "n_buys": 3, "n_sells": 1, "buy_value_usd": 1.1e6, "sell_value_usd": 0.2e6, "net_flow_usd":  0.9e6},
    {"quarter": "Q3 2024", "n_buys": 1, "n_sells": 2, "buy_value_usd": 0.3e6, "sell_value_usd": 0.6e6, "net_flow_usd": -0.3e6},
    {"quarter": "Q4 2024", "n_buys": 4, "n_sells": 0, "buy_value_usd": 2.4e6, "sell_value_usd": 0.0,    "net_flow_usd":  2.4e6},
    {"quarter": "Q1 2025", "n_buys": 5, "n_sells": 1, "buy_value_usd": 3.5e6, "sell_value_usd": 0.2e6, "net_flow_usd":  3.3e6},
    {"quarter": "Q2 2025", "n_buys": 6, "n_sells": 0, "buy_value_usd": 4.8e6, "sell_value_usd": 0.0,    "net_flow_usd":  4.8e6},
    {"quarter": "Q3 2025", "n_buys": 7, "n_sells": 1, "buy_value_usd": 6.5e6, "sell_value_usd": 0.3e6, "net_flow_usd":  6.2e6},
    {"quarter": "Q4 2025", "n_buys": 9, "n_sells": 0, "buy_value_usd": 8.2e6, "sell_value_usd": 0.0,    "net_flow_usd":  8.2e6},
]


# ═══════════════════════════════════════════════════════════════════════════
# Data sources
# ═══════════════════════════════════════════════════════════════════════════
#
# US tickers — institutional ownership (13F):
#   SEC EDGAR API — free, no key, public 13F filings
#   - Library: `python-edgar` (pip install edgar) or roll your own using
#     https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F-HR
#   - For each filing date, parse the holdings list, sum % outstanding
#   - Refresh quarterly (filings are 45 days post-quarter-end)
#
# US tickers — insider Form 4:
#   SEC EDGAR Form 4 filings (also free)
#   - https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=4
#   - Aggregate by transaction date → group by quarter → sum buy/sell value
#
# India tickers — institutional ownership:
#   BSE/NSE Shareholding Pattern disclosures (quarterly, free, public)
#   - NSE: https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern
#   - BSE: https://www.bseindia.com/corporates/shp.html
#   - Parse the XBRL filing — fields: FII %, DII %, top public holders %
#
# India tickers — insider trading:
#   BSE/NSE Insider Trading disclosures (mandatory under SEBI PIT regulations)
#   - NSE: https://www.nseindia.com/companies-listing/corporate-filings-insider-trading
#   - Quarterly aggregated buy/sell by promoter group + officers
#
# Caching:
#   13F data refreshes only quarterly — cache aggressively (4-week TTL is fine).
#   Insider Form 4 refreshes daily — cache 24h.

# ═══════════════════════════════════════════════════════════════════════════
# Minimal-viable implementation
# ═══════════════════════════════════════════════════════════════════════════
#
# If wiring all three at once is too much, ship them in this order of value:
#   1. top_holders_delta  — biggest insight per byte. Shows WHO is moving.
#   2. ownership_history  — visualizes the trend cleanly.
#   3. insider_activity.quarterly_history — refines the signal but lower priority.
#
# Each field renders independently with its own empty state, so partial deployment
# is fine — users see the panels that have data, empty cards for the ones that don't.
