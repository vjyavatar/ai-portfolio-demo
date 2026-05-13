# ═══════════════════════════════════════════════════════════════════════════
# SMART MONEY SCANNER — Backend Reference
# Frontend (r63.87.0) calls /api/smart-money-scanner?region=US&mcap=large&limit=50
# Until you wire this endpoint, the scanner shows a friendly empty state.
# ═══════════════════════════════════════════════════════════════════════════

# This endpoint reuses the same universes you (will) populate for the intraday
# scanner — see INTRADAY_MCAP_BACKEND_REFERENCE.py for the four mcap-tier
# ticker lists. You can share the same US_UNIVERSES / INDIA_UNIVERSES dictionaries.

# ─── Endpoint handler ───
@app.get("/api/smart-money-scanner")
def smart_money_scanner(
    region: str = "US",
    mcap: str = "large",        # large / mid / small / micro
    email: str = "",
    limit: int = 50,
):
    if mcap not in ("large", "mid", "small", "micro"):
        mcap = "large"

    universe = (US_UNIVERSES if region == "US" else INDIA_UNIVERSES).get(mcap, [])
    if not universe:
        return {
            "success": False,
            "universe_size": 0,
            "results": [],
            "scan_time_sec": 0,
            "error": f"{mcap.title()}-cap universe for {region} not yet populated.",
        }

    # Cache key includes mcap so tiers don't share results
    cache_key = f"smartmoney:{region}:{mcap}"
    cached = redis_get(cache_key)
    if cached:
        return {**cached, "_cached": True, "_cache_age_sec": cache_age(cache_key)}

    t0 = time.time()
    results = []
    for ticker in universe[:limit]:
        sig = compute_smi_signals(ticker, region)
        if sig:
            results.append(sig)

    payload = {
        "success": True,
        "universe_size": len(universe),
        "results": results,
        "scan_time_sec": round(time.time() - t0, 1),
        "region": region,
        "mcap": mcap,
    }
    redis_set(cache_key, payload, ttl_sec=4 * 3600)   # 4-hour TTL — 13F doesn't change often
    return payload


# ─── Per-stock signal aggregator ───
def compute_smi_signals(ticker: str, region: str) -> dict | None:
    """
    Returns one row of the scanner. Fields:
      ticker, issuer_name, price, change_pct
      smi_verdict        — ACCUMULATING / DISTRIBUTING / HOLDING / INSUFFICIENT
      smi_score          — 0-100 composite
      ownership_history  — same shape as per-stock SMI panel (8 quarters of {quarter, total_pct_outstanding})
      ownership_delta_8q — float, percentage-point change over last 8 quarters
      top_holders_action — NET ADDING / NET REDUCING / MIXED / HOLDING
      insider_trend      — ACCELERATING / STEADY / DECELERATING / NONE
    """
    # 1) Pull the 8-quarter ownership history (reuse the same code path your
    #    per-stock SMI panel uses — both should hit the same SEC EDGAR 13F /
    #    BSE-NSE shareholding pattern data source).
    ownership_history = fetch_ownership_history(ticker, region, n_quarters=8)
    if len(ownership_history) < 4:
        return None  # skip stocks with too little history

    # 2) Compute delta + verdict from the trend
    last = ownership_history[-1].get("total_pct_outstanding", 0)
    first = ownership_history[max(0, len(ownership_history) - 4)].get("total_pct_outstanding", 0)
    delta = last - first
    if delta >= 3:
        verdict = "ACCUMULATING"
    elif delta <= -3:
        verdict = "DISTRIBUTING"
    else:
        verdict = "HOLDING"

    # 3) Top-holder action this quarter
    holders_delta = fetch_top_holders_delta(ticker, region)
    adding = sum(1 for h in holders_delta if h.get("action") == "ADDING")
    reducing = sum(1 for h in holders_delta if h.get("action") == "REDUCING")
    total = len(holders_delta)
    if total == 0:
        top_holders_action = None
    elif adding / total > 0.6:
        top_holders_action = "NET ADDING"
    elif reducing / total > 0.6:
        top_holders_action = "NET REDUCING"
    elif adding == 0 and reducing == 0:
        top_holders_action = "HOLDING"
    else:
        top_holders_action = "MIXED"

    # 4) Insider trend — accel/decel comparison
    insider_q = fetch_insider_quarterly_history(ticker, region, n_quarters=8)
    if len(insider_q) >= 4:
        recent = sum(q.get("buy_value_usd", 0) for q in insider_q[-2:])
        prior  = sum(q.get("buy_value_usd", 0) for q in insider_q[-4:-2])
        if recent == 0 and prior == 0:
            insider_trend = "NONE"
        elif prior == 0 or recent > prior * 1.5:
            insider_trend = "ACCELERATING"
        elif recent < prior * 0.5:
            insider_trend = "DECELERATING"
        else:
            insider_trend = "STEADY"
    else:
        insider_trend = None

    # 5) Composite score (0-100). Weight ownership trend the heaviest.
    # Tune these weights based on backtest performance.
    score = 50  # neutral baseline
    score += delta * 4                             # ownership trend (~ +/- 20 pts max)
    score += (15 if top_holders_action == "NET ADDING" else
              -15 if top_holders_action == "NET REDUCING" else 0)
    score += (10 if insider_trend == "ACCELERATING" else
              -10 if insider_trend == "DECELERATING" else 0)
    score = max(0, min(100, score))

    # 6) Live price (reuse your existing price fetch)
    px = fetch_live_price(ticker, region)

    return {
        "ticker": ticker,
        "issuer_name": fetch_issuer_name(ticker, region),
        "price": px.get("price"),
        "change_pct": px.get("change_pct"),

        "smi_verdict": verdict,
        "smi_score": round(score, 1),
        "ownership_history": ownership_history,    # 8 quarters — drives OWN LAST 4Q + sparkline + verdict
        "ownership_delta_8q": round(delta, 2),

        # r63.88.0: 5 quarters of trading volume so frontend can compute 4 Q-over-Q deltas
        # Each entry: {"quarter": "Q3 2025", "avg_daily_volume": 12_500_000}
        "volume_quarterly_history": fetch_volume_quarterly_history(ticker, region, n_quarters=5),

        "top_holders_action": top_holders_action,
        "insider_trend": insider_trend,
    }


# ─── Volume fetcher (NEW in r63.88.0) ───
def fetch_volume_quarterly_history(ticker: str, region: str, n_quarters: int = 5) -> list:
    """
    Returns 5 quarters of average daily volume so the frontend can derive
    4 Q-over-Q deltas (green/red cells in VOL LAST 4Q column).

    Implementation: pull daily OHLCV bars for the last ~24 months from yfinance
    (US) or NSE bhavcopy archives (India), bucket by calendar quarter, average
    the daily volume.

    [
      {"quarter": "Q4 2023", "avg_daily_volume": 11_800_000},
      {"quarter": "Q1 2024", "avg_daily_volume": 12_500_000},
      {"quarter": "Q2 2024", "avg_daily_volume": 14_200_000},
      {"quarter": "Q3 2024", "avg_daily_volume": 13_100_000},
      {"quarter": "Q4 2024", "avg_daily_volume": 18_500_000},
    ]

    Cache by (ticker, quarter) — historical quarters never change. Only the
    most recent (in-progress) quarter needs fresh fetches.
    """
    bars = fetch_daily_ohlcv(ticker, region, lookback_days=730)
    if not bars:
        return []
    from collections import defaultdict
    by_quarter = defaultdict(list)
    for bar in bars:
        dt = bar["date"]  # datetime
        q = f"Q{(dt.month - 1) // 3 + 1} {dt.year}"
        by_quarter[q].append(bar["volume"])
    sorted_quarters = sorted(by_quarter.keys(), key=lambda q: (int(q.split()[-1]), int(q[1:2])))
    return [
        {"quarter": q, "avg_daily_volume": int(sum(by_quarter[q]) / max(1, len(by_quarter[q])))}
        for q in sorted_quarters[-n_quarters:]
    ]


# ─── Data sources (same as per-stock SMI panel — share the code) ───
#
# US:
#   fetch_ownership_history(ticker, "US", 8):
#     - Loop through last 8 quarterly 13F filing dates for the ticker
#     - For each, sum institutional holdings as % of shares outstanding
#     - SEC EDGAR full-text search: https://efts.sec.gov/LATEST/search-index?q=%22{cik}%22&forms=13F-HR
#     - Cache by (ticker, quarter) — historical data never changes
#
#   fetch_top_holders_delta(ticker, "US"):
#     - Compare current quarter's 13F holdings vs. prior quarter's
#     - For each top-10 holder, compute delta_shares + delta_pct + action
#
#   fetch_insider_quarterly_history(ticker, "US", 8):
#     - SEC Form 4 filings grouped by quarter
#     - https://efts.sec.gov/LATEST/search-index?q=%22{cik}%22&forms=4
#
# India:
#   fetch_ownership_history(ticker, "IN", 8):
#     - BSE: https://www.bseindia.com/corporates/shp.html
#     - NSE: https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern
#     - Parse the XBRL shareholding pattern — FII + DII + Mutual Funds %
#
#   fetch_insider_quarterly_history(ticker, "IN", 8):
#     - NSE Insider Trading disclosures (SEBI PIT regulation)
#     - https://www.nseindia.com/companies-listing/corporate-filings-insider-trading
#
# All sources are free and public. NSE rate-limits NSE-direct calls from
# datacenters (Render's outbound IP 72.180.65.28 is banned), so route through
# nseindia.com archives.


# ─── Performance / batching notes ───
#
# A full scan of NIFTY 50 (50 tickers × 8 quarters of 13F + 8 quarters of insider)
# takes 30-90 seconds without parallelism. Recommendations:
#
# 1. Use a ThreadPoolExecutor with max_workers=10 for the per-ticker compute loop
#    (each compute_smi_signals call is mostly I/O-bound).
#
# 2. Cache the per-ticker ownership_history and insider_quarterly_history
#    by (ticker, quarter) — historical quarters never change, so TTL can be
#    months. Only the LATEST quarter needs fresh fetches.
#
# 3. For the micro-cap universe (250+ tickers), set limit=50 by default and
#    let users page through. Or pre-warm in a background job every 24h.
#
# 4. Cache the FULL scanner response by (region, mcap) with a 4-hour TTL.
#    The frontend sends Cache-Control: no-store so users get fresh data on
#    refresh, but the backend serves the cached copy unless explicitly refreshed.
