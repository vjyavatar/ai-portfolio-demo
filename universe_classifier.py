"""
Celesys — Centralized Universe Classifier
==========================================
ONE service. Classifies any ticker into LARGE / MID / SMALL / MICRO / ETF.
Loaded once at boot. Memory-cached. Fast lookups.

Replace these duplicated lists across api.py:
  • Line 17215-17256 (/api/top-picks)
  • Line 23703-23720 (/api/multibagger-hunter)
  • Line 24750-24823 (/api/early-momentum-radar)
  • Line 26913-26935 (/api/microcap-challenge)

With:
  from universe_classifier import UC
  UC.classify(ticker, region)            → "LARGE" | "MID" | "SMALL" | "MICRO" | "ETF" | "UNKNOWN"
  UC.get(region, tier)                   → [tickers]
  UC.get_all(region)                     → {LARGE: [...], MID: [...], ...}
  UC.is_in_universe(ticker, region)      → bool
  UC.bucket_tickers(tickers, region)     → {LARGE: [...], MID: [...], ...}

Static classification by membership; covers ~600 tickers across both regions.
For unlisted names, falls back to dynamic market-cap classification when
market_cap_usd is provided.
"""

from __future__ import annotations
from typing import Optional


# ═════════════════════════════════════════════════════════════════════
# CANONICAL UNIVERSES
# Curate from authoritative sources in production:
#   • India: NSE NIFTY 100/Midcap 150/Smallcap 250 monthly index files
#   • US:    S&P 100/400/600 + Russell 2000 micro
# ═════════════════════════════════════════════════════════════════════

# ── INDIA — NIFTY 100 (large cap proxy) ─────────────────────────────
INDIA_LARGE = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC",
    "SBIN", "LT", "BHARTIARTL", "AXISBANK", "KOTAKBANK", "ASIANPAINT", "MARUTI",
    "BAJFINANCE", "HCLTECH", "WIPRO", "ULTRACEMCO", "TITAN", "SUNPHARMA",
    "NESTLEIND", "ONGC", "TATAMOTORS", "POWERGRID", "NTPC", "JSWSTEEL", "M&M",
    "TATASTEEL", "INDUSINDBK", "ADANIENT", "BAJAJFINSV", "GRASIM", "TECHM",
    "DRREDDY", "CIPLA", "DIVISLAB", "EICHERMOT", "BPCL", "BRITANNIA", "COALINDIA",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "SHREECEM", "SBILIFE", "TATACONSUM",
    "ADANIPORTS", "UPL", "BAJAJ-AUTO", "APOLLOHOSP",
    # Next 50
    "DMART", "PIDILITIND", "LICI", "AMBUJACEM", "GODREJCP", "DABUR", "GAIL",
    "BANKBARODA", "VEDL", "LTIM", "ICICIPRULI", "ICICIGI", "HAL", "BEL",
    "ZOMATO", "TRENT", "BOSCHLTD", "SIEMENS", "ABB", "HAVELLS", "INDIGO",
    "ADANIGREEN", "ADANIPOWER", "TATAPOWER", "DLF", "GODREJPROP", "OBEROIRLTY",
    "JINDALSTEL", "SAIL", "IRFC", "RECLTD", "PFC", "CANBK", "PNB", "MUTHOOTFIN",
    "CHOLAFIN", "BAJAJHLDNG", "SBICARD", "JIOFIN", "IOC", "MPHASIS", "MOTHERSON",
    "TVSMOTOR", "INDHOTEL", "VBL", "POLYCAB", "TATACOMM", "INDUSTOWER",
    "ZYDUSLIFE", "MARICO", "COLPAL",
]

# ── INDIA — NIFTY MIDCAP 150 ────────────────────────────────────────
INDIA_MID = [
    "PERSISTENT", "COFORGE", "PAYTM", "IRCTC", "PIIND", "LUPIN", "TORNTPHARM",
    "BIOCON", "AUROPHARMA", "ABBOTINDIA", "ALKEM", "IPCALAB", "GLENMARK",
    "BERGEPAINT", "PGHH", "MCDOWELL-N", "CUMMINSIND", "VOLTAS", "BLUESTARCO",
    "DIXON", "CDSL", "BSE", "ANGELONE", "MOTILALOFS", "ESCORTS", "ASHOKLEY",
    "MRF", "BALKRISIND", "APOLLOTYRE", "EXIDEIND", "AMARAJABAT", "NAUKRI",
    "INFOEDGE", "INDIAMART", "NMDC", "TATACHEM", "TATAELXSI", "LTTS", "OFSS",
    "MINDTREE", "SUZLON", "IDFCFIRSTB", "FEDERALBNK", "BANDHANBNK", "AUBANK",
    "RBLBANK", "YESBANK", "JUBLFOOD", "VARROC", "KEC", "FINOLEXIND",
    "JKCEMENT", "RAMCOCEM", "BHARATFORG", "CONCOR", "CROMPTON", "DEEPAKNTR",
    "DELHIVERY", "DEVYANI", "EMAMILTD", "ENDURANCE", "FORTIS", "GMRINFRA",
    "GODREJIND", "GRANULES", "GUJGASLTD", "HAPPSTMNDS", "HONAUT", "IDEA",
    "IGL", "L&TFH", "LALPATHLAB", "LICHSGFIN", "LINDEINDIA", "MASTEK",
    "MAXHEALTH", "METROPOLIS", "MINDACORP", "NATCOPHARM", "NETWORK18", "NH",
    "OIL", "OLECTRA", "PAGEIND", "PEL", "PETRONET", "POLYMED", "RADICO",
    "RAYMOND", "REDINGTON", "RELAXO", "RITES", "ROUTE", "RVNL", "SCHAEFFLER",
    "SCI", "SHRIRAMFIN", "SJVN", "SRF", "SUPREMEIND", "SYNGENE", "TANLA",
    "THERMAX", "TIINDIA", "TIMKEN", "TORNTPOWER", "TRIDENT", "TRIVENI",
    "UNIONBANK", "UNOMINDA", "UTIAMC", "VINATIORGA", "VTL", "WHIRLPOOL",
    "ZENSARTECH", "ASTRAL", "AARTI", "COROMANDEL",
]

# ── INDIA — NIFTY SMALLCAP 250 ──────────────────────────────────────
INDIA_SMALL = [
    "OLECTRA", "NETWEB", "TTML", "DATAMATICS", "RATEGAIN", "KPITTECH",
    "SONACOMS", "KAYNES", "LATENTVIEW", "COCHINSHIP", "MAZAGON", "BDL",
    "SOLARINDS", "CAMS", "MCX", "POONAWALLA", "GODREJPROP", "PRESTIGE",
    "PHOENIXLTD", "HDFCAMC", "RAILTEL", "GRINDWELL", "GRANULES", "AJANTPHARM",
    "STARHEALTH", "SUNTV", "EMAMILTD", "CLEAN", "FLUOROCHEM", "SUMICHEM",
    "CHAMBLFERT", "GNFC", "FACT", "GSFC", "MEDANTA", "BHEL", "CEAT",
    "GLENMARK", "GUJGASLTD", "HONAUT", "JBMA", "JKTYRE", "JSL", "JUBLPHARMA",
    "JYOTHYLAB", "KAJARIACER", "KALPATPOWR", "KANSAINER", "KARURVYSYA", "KEI",
    "KIMS", "KIRLOSENG", "KSB", "LXCHEM", "M&MFIN", "MAHINDCIE", "MANAPPURAM",
    "MAZAGAON", "MMTC", "NAVA", "NAVINFLUOR", "NAZARA", "NESCO", "NIITLTD",
    "NLCINDIA", "NUVOCO", "PFIZER", "PNBHOUSING", "PRINCEPIPE", "PRISMJOHNS",
    "PRSMJOHNSN", "PSPPROJECT", "PVR", "QUESS", "RAJESHEXPO", "RELINFRA",
    "SANOFI", "SPARC", "STAR", "SUNDARMFIN", "SUNDRMFAST", "SUNTECK",
    "SUPRAJIT", "TANLA", "TASTYBITE", "TATACOFFEE", "TATAINVEST", "TATAMETALI",
    "TATATECH", "TCNSBR", "TEAMLEASE", "THYROCARE", "TITAGARH", "TTKPRESTIG",
    "TVTODAY", "UCOBANK", "UFLEX", "VAIBHAVGBL", "VAKRANGEE", "VENKEYS",
    "VIPIND", "VMART", "WELCORP", "WELSPUNIND", "WOCKPHARMA", "ZEEL", "ZUARI",
    "PVRINOX", "SAPPHIRE", "BLUESTARLT", "MARKSANS", "ATUL", "DEEPAKNITRIT",
    "RAYMOND", "SCHAEFFLER", "EXIDEIND", "AMARARAJA",
]

# ── INDIA — Micro caps (volatile) ────────────────────────────────────
INDIA_MICRO = [
    "TANLA", "POONAWALLA", "OLECTRA", "RATEGAIN", "DATAMATICS", "HAPPSTMNDS",
    "PRINCEPIPE", "TIINDIA", "TVTODAY", "ZENSARTECH", "VINATIORGA", "RELAXO",
    "AARTI",
]

# ── INDIA — ETFs ────────────────────────────────────────────────────
INDIA_ETF = [
    "NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES", "CPSE", "MAFANG",
    "SILVERBEES", "ICICIB22", "ITBEES", "MOM50", "PSUBNKBEES",
]

# ── INDIA — Indices ─────────────────────────────────────────────────
INDIA_INDEX = ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY", "NIFTYIT"]


# ── US — S&P 100 (mega/large cap) ───────────────────────────────────
US_LARGE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "BRK-B", "TSLA",
    "AVGO", "JPM", "WMT", "V", "UNH", "XOM", "MA", "PG", "JNJ", "ORCL", "HD",
    "COST", "BAC", "MRK", "ABBV", "CVX", "KO", "ADBE", "PEP", "TMO", "CSCO",
    "ACN", "MCD", "AMD", "DHR", "ABT", "WFC", "INTC", "CRM", "NFLX", "VZ",
    "DIS", "NEE", "TXN", "UPS", "QCOM", "PM", "RTX", "T", "INTU", "LIN",
    "BMY", "AMGN", "LOW", "C", "BA", "HON", "PFE", "GS", "ELV", "BLK",
    "AXP", "DE", "MDT", "GE", "CAT", "SBUX", "BKNG", "AMT", "GILD",
    "ADI", "MMC", "ISRG", "VRTX", "TJX", "MO", "REGN", "ZTS", "ETN", "PLD",
    "SCHW", "PANW", "BSX", "FI", "CB", "CI", "DUK", "SO", "SLB", "BX",
    "MU", "EOG", "NKE", "ADP", "TMUS", "SHW", "ICE", "MDLZ", "ITW", "GD",
    "CME", "PGR", "LLY",
]

# ── US — S&P 400 (mid cap) ──────────────────────────────────────────
US_MID = [
    "PANW", "CRWD", "SNOW", "DDOG", "ZS", "NET", "MELI", "SHOP", "SQ", "COIN",
    "PLTR", "SOFI", "HOOD", "RBLX", "U", "USB", "MMM", "TGT", "FCX", "SYK",
    "AON", "NOC", "LMT", "EQIX", "APD", "WM", "BDX", "CL", "EMR", "FDX",
    "PSA", "DG", "MAR", "MET", "GM", "F", "HUM", "EW", "ROST", "SNPS",
    "CDNS", "MCK", "MNST", "GIS", "EL", "CTAS", "AEP", "DOW", "STZ", "OXY",
    "ATVI", "ROP", "PSX", "PRU", "AIG", "VLO", "AFL", "NSC", "TRV", "FERG",
    "CMI", "CMG", "AZO", "ORLY", "DLTR", "DLR", "WELL", "FTNT", "CSGP",
    "SRE", "WMB", "EXC", "MPC", "PCAR", "OKE", "MSI", "AME", "CTSH", "TT",
    "CHTR", "KMB", "DD", "AJG", "MCHP", "TFC", "CARR", "ECL", "ROK", "PCG",
    "CNC", "PPG", "ANSS", "STT", "ALL", "PWR", "WCN", "CPRT", "NUE", "OTIS",
    "EBAY", "URI", "FAST", "PAYX", "LRCX", "KLAC", "VICI", "EFX", "BIIB",
    "ON", "WBD", "FANG", "BR", "VRSK", "TYL", "DXCM", "WBA", "EQR", "CTRA",
    "PEG", "ED", "AVB", "ZBH", "AWK", "GLW", "MTB", "SPG", "RMD", "EIX",
    "TSN", "FTV", "ACGL", "DTE", "WTW", "CDW", "CINF", "RF", "GPN", "BAH",
    "TROW", "ETR", "GPC", "CMS", "HPE", "ARES", "BBY", "GRMN", "ADM",
]

# ── US — S&P 600 (small cap proxy) ──────────────────────────────────
US_SMALL = [
    "RIVN", "UPST", "AFRM", "DNA", "SMCI", "ARQQ", "PATH", "AI", "BBAI",
    "ASTS", "MARA", "RIOT", "MSTR", "JBHT", "DECK", "BAX", "AKAM", "POOL",
    "MOS", "EVRG", "STE", "IEX", "TECH", "PKG", "BG", "INCY", "AMCR",
    "EXPD", "UAL", "HSY", "VTR", "K", "OMC", "MTCH", "DOV", "STLD", "FITB",
    "PPL", "FE", "PHM", "WAT", "HOLX", "AVY", "LDOS", "BALL", "SBAC", "CAH",
    "WST", "FSLR", "MOH", "ULTA", "EXR", "ANET", "RJF", "TRGP", "KEYS",
    "WY", "INVH", "PFG", "DRI", "CNP", "SYF", "SWKS", "NTAP", "EXPE", "CFG",
    "LH", "HBAN", "EPAM", "TER", "DGX", "MGM", "ZBRA", "ATO", "WAB", "MAA",
    "ESS", "VTRS", "BRO", "TXT", "RKLB", "JOBY", "LUNR",
]

# ── US — Micro cap (high volatility) ────────────────────────────────
US_MICRO = [
    "IONQ", "SOUN", "QBTS", "QUBT", "DNA", "OKLO", "ARQQ", "BBAI", "ASTS",
    "RGTI", "ACHR", "EVTL", "POET", "VINP", "DRCT", "OPK", "INDI",
]

# ── US — ETFs ───────────────────────────────────────────────────────
US_ETF = [
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "SCHD", "SMH", "SOXX", "XLK",
    "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLU", "XLRE", "XLB", "ARKK",
    "ARKW", "ARKG", "ARKQ", "GLD", "SLV", "TLT", "IEF", "HYG", "LQD", "EEM",
    "EFA", "VEA", "VWO", "ACWI", "VT",
]

# ── US — Indices ────────────────────────────────────────────────────
US_INDEX = ["SPX", "NDX", "DJI", "RUT", "VIX"]


# ═════════════════════════════════════════════════════════════════════
# Build lookup tables (run once at import)
# ═════════════════════════════════════════════════════════════════════
def _build_lookup():
    lookup = {}  # {(symbol_uppercase, region): tier}
    for region, sets in (("IN", [
        ("LARGE", INDIA_LARGE), ("MID", INDIA_MID),
        ("SMALL", INDIA_SMALL), ("MICRO", INDIA_MICRO),
        ("ETF", INDIA_ETF), ("INDEX", INDIA_INDEX),
    ]), ("US", [
        ("LARGE", US_LARGE), ("MID", US_MID),
        ("SMALL", US_SMALL), ("MICRO", US_MICRO),
        ("ETF", US_ETF), ("INDEX", US_INDEX),
    ])):
        for tier, syms in sets:
            for s in syms:
                key = (s.upper().strip(), region)
                # First insertion wins (LARGE > MID > SMALL etc due to order)
                if key not in lookup:
                    lookup[key] = tier
    return lookup

_LOOKUP = _build_lookup()

_UNIVERSES = {
    "IN": {"LARGE": INDIA_LARGE, "MID": INDIA_MID, "SMALL": INDIA_SMALL,
           "MICRO": INDIA_MICRO, "ETF": INDIA_ETF, "INDEX": INDIA_INDEX},
    "US": {"LARGE": US_LARGE, "MID": US_MID, "SMALL": US_SMALL,
           "MICRO": US_MICRO, "ETF": US_ETF, "INDEX": US_INDEX},
}


# ═════════════════════════════════════════════════════════════════════
# Public API — UC = Universe Classifier
# ═════════════════════════════════════════════════════════════════════
class UC:
    @staticmethod
    def _norm(symbol: str) -> str:
        """Strip .NS / .BO suffix, uppercase, trim."""
        if not symbol: return ""
        s = symbol.upper().strip()
        if s.endswith(".NS"): s = s[:-3]
        elif s.endswith(".BO"): s = s[:-3]
        return s

    @staticmethod
    def classify(symbol: str, region: str = "US",
                 market_cap_usd: Optional[float] = None) -> str:
        """
        Classify a ticker. Returns: LARGE / MID / SMALL / MICRO / ETF / INDEX / UNKNOWN.

        1. Static lookup first (fast — covers ~600 tickers).
        2. Falls back to market_cap_usd thresholds if provided and ticker not found.
        """
        sym = UC._norm(symbol)
        reg = (region or "US").upper()
        if not sym: return "UNKNOWN"

        tier = _LOOKUP.get((sym, reg))
        if tier: return tier

        # Dynamic fallback by market cap if provided
        if market_cap_usd is not None and market_cap_usd > 0:
            if   market_cap_usd >= 200_000_000_000: return "LARGE"   # ≥ $200B mega/large
            elif market_cap_usd >=  10_000_000_000: return "LARGE"   # ≥ $10B large
            elif market_cap_usd >=   2_000_000_000: return "MID"     # $2-10B mid
            elif market_cap_usd >=     300_000_000: return "SMALL"   # $300M-2B small
            else:                                    return "MICRO"

        return "UNKNOWN"

    @staticmethod
    def get(region: str, tier: str) -> list:
        """Get the canonical list for one (region, tier)."""
        reg = (region or "US").upper()
        t = (tier or "").upper()
        return list(_UNIVERSES.get(reg, {}).get(t, []))

    @staticmethod
    def get_all(region: str) -> dict:
        """Get all tiers for a region. Returns {LARGE: [...], MID: [...], ...}."""
        reg = (region or "US").upper()
        return {k: list(v) for k, v in _UNIVERSES.get(reg, {}).items()}

    @staticmethod
    def is_in_universe(symbol: str, region: str) -> bool:
        return UC.classify(symbol, region) != "UNKNOWN"

    @staticmethod
    def bucket_tickers(symbols: list, region: str) -> dict:
        """
        Bucket a list of tickers by tier.
        Returns: {LARGE: [...], MID: [...], SMALL: [...], MICRO: [...], ETF: [...], INDEX: [...], UNKNOWN: [...]}
        """
        out = {"LARGE": [], "MID": [], "SMALL": [], "MICRO": [],
               "ETF": [], "INDEX": [], "UNKNOWN": []}
        for s in symbols or []:
            tier = UC.classify(s, region)
            out[tier].append(s)
        return out

    @staticmethod
    def stats() -> dict:
        """Universe size summary — for /api/universe-stats endpoint."""
        return {
            "IN": {tier: len(lst) for tier, lst in _UNIVERSES["IN"].items()},
            "US": {tier: len(lst) for tier, lst in _UNIVERSES["US"].items()},
            "total_in": sum(len(lst) for lst in _UNIVERSES["IN"].values()),
            "total_us": sum(len(lst) for lst in _UNIVERSES["US"].values()),
            "total":    sum(len(lst) for d in _UNIVERSES.values() for lst in d.values()),
        }
