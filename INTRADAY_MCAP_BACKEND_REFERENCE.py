# ═══════════════════════════════════════════════════════════════════════════
# INTRADAY SETUPS — MARKET-CAP UNIVERSE WIRING
# Frontend (r63.85.0) now sends ?mcap=large|mid|small|micro to /api/intraday-setups.
# Update the endpoint to swap the scan universe based on this parameter.
# ═══════════════════════════════════════════════════════════════════════════

# ─── 1. Universe definitions ───
# Curate these as static lists (refresh quarterly, or load from a CSV/JSON file).
# Lists below are starter recommendations — adjust to your liquidity criteria.

US_UNIVERSES = {
    "large": [  # S&P 100 — the heaviest, most liquid US names
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "TSLA",
        "AVGO", "JPM", "WMT", "XOM", "V", "UNH", "MA", "PG", "JNJ", "HD", "COST",
        # ... full S&P 100 list (100 tickers)
    ],
    "mid": [  # S&P MidCap 400 — top 400 mid-caps
        # Source: download from S&P Global, or use a static list from
        # https://github.com/datasets/s-and-p-400-companies
        # Examples: "AAON", "ACM", "AGCO", "AIT", "AIZ", "ALK", "ALSN", ...
    ],
    "small": [  # S&P SmallCap 600
        # Examples: "AAOI", "AAON", "AAT", "ABCB", "ABG", "ABM", "ABR", ...
    ],
    "micro": [  # Russell Micro-Cap (top 1,000 micro-caps by liquidity)
        # WARNING: many have <$5M daily volume — filter for tradability.
        # Source: iShares IWC holdings export, or filter Russell 3000 by mcap < $300M.
    ],
}

INDIA_UNIVERSES = {
    "large": [  # NIFTY 50
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS",
        "INFY.NS", "SBIN.NS", "LT.NS", "ITC.NS", "HINDUNILVR.NS",
        # ... full NIFTY 50 list (50 tickers)
    ],
    "mid": [  # NIFTY MIDCAP 100
        # Examples: "PERSISTENT.NS", "POLYCAB.NS", "BHARATFORG.NS", "CUMMINSIND.NS", ...
    ],
    "small": [  # NIFTY SMALLCAP 100
        # Examples: "KPITTECH.NS", "AAVAS.NS", "HBLPOWER.NS", ...
    ],
    "micro": [  # NIFTY MICROCAP 250 — or "rest of NSE" as user described
        # Filter NIFTY 500 / NSE 1000 by mcap < ₹5,000 Cr.
    ],
}


# ─── 2. Endpoint update ───
# Replace the universe-resolution block in your existing /api/intraday-setups handler.

@app.get("/api/intraday-setups")
def intraday_setups(
    region: str = "US",
    timeframe: str = "intraday",  # was: default "all" — now "intraday" (matches frontend)
    mcap: str = "large",           # NEW — frontend sends one of: large/mid/small/micro
    email: str = "",
    limit: int = 30,
):
    # Validate mcap
    if mcap not in ("large", "mid", "small", "micro"):
        mcap = "large"

    # Validate timeframe (no more "all")
    if timeframe not in ("intraday", "swing"):
        timeframe = "intraday"

    # Resolve universe
    if region == "US":
        universe = US_UNIVERSES.get(mcap, US_UNIVERSES["large"])
    else:
        universe = INDIA_UNIVERSES.get(mcap, INDIA_UNIVERSES["large"])

    if not universe:
        return {
            "success": True,
            "universe_size": 0,
            "candidates": [],
            "scan_time_sec": 0,
            "honest_disclaimer": (
                f"{mcap.title()}-cap universe for {region} not yet populated in api.py. "
                "Add ticker list to INDIA_UNIVERSES/US_UNIVERSES dictionaries."
            ),
            "methodology": {},
        }

    # ... rest of existing scan logic (5-min bars, liquidity filter, setup detection)
    # The existing code should work as-is — only the universe variable changes.
    candidates = run_existing_scan_logic(universe, region, timeframe)

    return {
        "success": True,
        "universe_size": len(universe),
        "candidates": candidates,
        "scan_time_sec": <as before>,
        "honest_disclaimer": <as before>,
        "methodology": <as before>,
        "currency_symbol": "$" if region == "US" else "₹",
        # Optional: echo mcap back so frontend can log/cache by tier
        "mcap": mcap,
        "timeframe": timeframe,
    }


# ─── 3. Cache key update ───
# If you cache scan results (Redis or in-memory), include mcap in the key
# so large/mid/small/micro don't share cached candidates.

# OLD:  cache_key = f"intraday:{region}:{timeframe}"
# NEW:  cache_key = f"intraday:{region}:{timeframe}:{mcap}"


# ─── 4. Where to get the ticker lists ───
#
# US:
#   - S&P 100: https://en.wikipedia.org/wiki/S%26P_100 (right sidebar — components list)
#   - S&P 400/600: download from spglobal.com (free CSV) or use a maintained GitHub list
#   - Russell Micro: iShares IWC holdings export (CSV, refreshed daily)
#
# India:
#   - NIFTY 50: niftyindices.com → Indices → Broad Indices → NIFTY 50 → Constituents
#   - NIFTY MIDCAP 100: same path, MIDCAP 100
#   - NIFTY SMALLCAP 100: same path
#   - NIFTY MICROCAP 250: niftyindices.com → Indices → Thematic → MICROCAP 250
#
# All NSE lists update quarterly — set a calendar reminder to refresh in Jan/Apr/Jul/Oct.


# ─── 5. Liquidity filter (recommended for micro caps) ───
# Without this, your micro-cap scanner will surface untradable names with $50K daily volume.
def liquidity_filter(ticker_data, region):
    min_daily_vol_usd = {"large": 10_000_000, "mid": 2_000_000, "small": 500_000, "micro": 100_000}
    avg_vol_usd = ticker_data["avg_volume_30d"] * ticker_data["price"]
    return avg_vol_usd >= min_daily_vol_usd.get(ticker_data.get("mcap_tier", "large"), 100_000)
