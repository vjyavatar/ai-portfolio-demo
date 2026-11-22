"""Compose quotes, sessions, verdicts and screeners. Fail soft."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from live_markets.cache import CACHE, FETCH_LOCK
from live_markets import options_chain, providers, sessions, symbols, verdict

QUOTE_TTL = float(os.getenv("CELESYS_LIVE_CACHE_SECONDS", "60") or 60)
STALE_TTL = 1800
SCREEN_TTL = 300

INDEX_BOOK = [
    {"name": "S&P 500", "flag": "🇺🇸", "tv": "SP:SPX", "yahoo": "^GSPC"},
    {"name": "NASDAQ", "flag": "🇺🇸", "tv": "NASDAQ:IXIC", "yahoo": "^IXIC"},
    {"name": "DOW", "flag": "🇺🇸", "tv": "DJ:DJI", "yahoo": "^DJI"},
    {"name": "US VIX", "flag": "🇺🇸", "tv": "CBOE:VIX", "yahoo": "^VIX"},
    {"name": "NIFTY 50", "flag": "🇮🇳", "tv": "NSE:NIFTY", "yahoo": "^NSEI"},
    {"name": "SENSEX", "flag": "🇮🇳", "tv": "BSE:SENSEX", "yahoo": "^BSESN"},
    {"name": "BANKNIFTY", "flag": "🇮🇳", "tv": "NSE:BANKNIFTY", "yahoo": "^NSEBANK"},
    {"name": "INDIA VIX", "flag": "🇮🇳", "tv": "NSE:INDIAVIX", "yahoo": "^INDIAVIX"},
    {"name": "USD/INR", "flag": "💱", "tv": "FX_IDC:USDINR", "yahoo": "INR=X", "calendar": "continuous"},
    {"name": "GOLD", "flag": "🥇", "tv": "TVC:GOLD", "yahoo": "GC=F", "calendar": "continuous"},
    {"name": "SILVER", "flag": "🥈", "tv": "TVC:SILVER", "yahoo": "SI=F", "calendar": "continuous"},
    {"name": "CRUDE", "flag": "🛢️", "tv": "TVC:USOIL", "yahoo": "CL=F", "calendar": "continuous"},
    {"name": "BTC", "flag": "₿", "tv": "BITSTAMP:BTCUSD", "yahoo": "BTC-USD", "calendar": "continuous"},
]

US_SCREEN = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "XOM", "LLY", "COST", "AMD", "NFLX"]
IN_SCREEN = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "BHARTIARTL", "SBIN", "ITC", "LT", "HINDUNILVR", "AXISBANK", "KOTAKBANK", "SUNPHARMA", "MARUTI"]

DISCLAIMER = (
    "Not financial advice. Figures are cached provider snapshots with the delay and session shown. "
    "A delayed or last-close print is not a broker quote. Orders are not placed here."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(epoch: Optional[float]) -> Optional[str]:
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(epoch, timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _present(raw: dict, resolved: dict, now: datetime | None = None) -> dict:
    moment = now or _now()
    tv_symbol = raw.get("tv_symbol") or (resolved.get("tv") or [""])[0]
    region = symbols.region_of(tv_symbol) if tv_symbol else (resolved.get("region_hint") or "US")
    quality = raw.get("quality") or "DELAYED"
    if raw.get("calendar") == "continuous":
        session = "CONTINUOUS"
        shown = "LIVE" if quality == "LIVE" else "DELAYED"
    else:
        session = sessions.session_for(region, moment)
        if session != "OPEN":
            shown = "LAST_CLOSE"
        elif quality == "LIVE":
            shown = "LIVE"
        else:
            shown = "DELAYED"
    clocks = sessions.describe(moment)
    features = dict(raw.get("features") or {})
    features["price"] = raw.get("price")
    features["volume"] = raw.get("volume")
    features["change_pct"] = raw.get("change_pct")
    return {
        "symbol": resolved.get("token") or tv_symbol,
        "provider_symbol": tv_symbol,
        "name": raw.get("name") or resolved.get("token"),
        "region": region,
        "currency": symbols.currency_of(tv_symbol, raw.get("currency")),
        "price": _round(raw.get("price")),
        "change": _round(raw.get("change")),
        "change_pct": _round(raw.get("change_pct")),
        "volume": int(raw["volume"]) if raw.get("volume") else None,
        "as_of": raw.get("as_of") or _iso(raw.get("as_of_epoch")),
        "as_of_estimated": raw.get("as_of") is None and raw.get("as_of_epoch") is None,
        "received_at": moment.isoformat(),
        "quality": shown,
        "provider_quality": quality,
        "delay_seconds": raw.get("delay_seconds"),
        "provider": raw.get("provider"),
        "provider_mode": raw.get("provider_mode"),
        "session": session,
        "clocks": clocks["clocks"],
        "features": features,
    }


def _yahoo_row(symbol: str, row: dict) -> dict:
    row = dict(row)
    row["tv_symbol"] = symbol
    if row.get("as_of_epoch"):
        row["as_of"] = _iso(row["as_of_epoch"])
    return row


def _merge_timestamp(primary: dict, yahoo: Optional[dict]) -> dict:
    if not yahoo or not yahoo.get("price"):
        if primary.get("delay_seconds"):
            primary["as_of_note"] = "Exchange timestamp was not supplied. Delay is the provider flag."
        return primary
    primary_price = primary.get("price") or 0
    yahoo_price = yahoo.get("price") or 0
    if primary_price and abs(primary_price - yahoo_price) / primary_price <= 0.005:
        primary["as_of"] = yahoo.get("as_of") or _iso(yahoo.get("as_of_epoch"))
        primary["as_of_estimated"] = False
        if not primary.get("volume") and yahoo.get("volume"):
            primary["volume"] = yahoo["volume"]
        primary["timestamp_provider"] = "yahoo"
    else:
        primary["cross_check"] = {"provider": "yahoo", "price": _round(yahoo_price)}
    return primary


def quote(symbol: str, region: str | None = None, now: datetime | None = None) -> dict:
    resolved = symbols.resolve(symbol, region)
    key = "q:" + ",".join(resolved["tv"]) + ":" + (region or "")
    cached = CACHE.get(key, QUOTE_TTL)
    if cached:
        return cached
    try:
        with FETCH_LOCK:
            cached = CACHE.get(key, QUOTE_TTL)
            if cached:
                return cached
            payload = _fetch_quote(resolved)
    except Exception as exc:
        stale = CACHE.get_stale(key, STALE_TTL)
        if stale:
            stale = dict(stale)
            stale["quality"] = "STALE"
            stale["warning"] = "Live fetch failed. Showing the last cached snapshot."
            return stale
        return _unavailable(resolved, str(exc)[:160])
    if payload is None:
        stale = CACHE.get_stale(key, STALE_TTL)
        if stale:
            stale = dict(stale)
            stale["quality"] = "STALE"
            stale["warning"] = "Providers returned nothing. Showing the last cached snapshot."
            return stale
        return _unavailable(resolved, "No provider returned a price.")
    presented = _present(payload, resolved, now)
    presented["success"] = True
    presented["disclaimer"] = DISCLAIMER
    CACHE.set(key, presented)
    return presented


def _yahoo_candidates(tv_symbol: str, fallbacks: list[str]) -> list[str]:
    mapped = symbols.YAHOO_BY_TV.get(tv_symbol)
    if mapped:
        return [mapped]
    if ":" in tv_symbol:
        prefix, base = tv_symbol.split(":", 1)
        if prefix == "NSE":
            return [f"{base}.NS"]
        if prefix == "BSE":
            return [f"{base}.BO"]
        if prefix in {"NASDAQ", "NYSE", "AMEX"}:
            return [base]
    return list(fallbacks)


def _fetch_quote(resolved: dict) -> Optional[dict]:
    tv_rows = providers.fetch_tradingview(resolved["tv"])
    chosen = None
    for ticker in resolved["tv"]:
        if ticker in tv_rows:
            chosen = dict(tv_rows[ticker])
            break
    yahoo_list = _yahoo_candidates(chosen["tv_symbol"], resolved["yahoo"]) if chosen else list(resolved["yahoo"])
    chosen_prefix = (chosen or {}).get("tv_symbol", "").split(":", 1)[0]
    us_equity = chosen_prefix in {"NASDAQ", "NYSE", "AMEX"} or (
        not chosen and resolved.get("region_hint") == "US" and resolved.get("kind") == "equity"
    )
    finnhub = None
    if us_equity and yahoo_list:
        finnhub = providers.fetch_finnhub(yahoo_list[0])
    if finnhub and finnhub.get("price"):
        base = chosen or {}
        merged = dict(base)
        merged.update({
            "price": finnhub["price"],
            "change": finnhub.get("change") if finnhub.get("change") is not None else merged.get("change"),
            "change_pct": finnhub.get("change_pct") if finnhub.get("change_pct") is not None else merged.get("change_pct"),
            "as_of": _iso(finnhub.get("as_of_epoch")),
            "provider": "finnhub" if not chosen else "finnhub+tradingview",
            "provider_mode": finnhub.get("provider_mode"),
            "quality": finnhub.get("quality") or "LIVE",
            "delay_seconds": 0,
            "currency": merged.get("currency") or finnhub.get("currency"),
            "tv_symbol": (chosen or {}).get("tv_symbol") or resolved["tv"][0],
            "name": (chosen or {}).get("name") or resolved["token"],
            "features": (chosen or {}).get("features") or {},
        })
        return merged
    if chosen:
        return chosen
    twelve_symbol = resolved["yahoo"][0] if resolved["yahoo"] else None
    twelve = providers.fetch_twelve(twelve_symbol) if twelve_symbol else None
    if twelve:
        twelve["tv_symbol"] = resolved["tv"][0]
        twelve["features"] = {}
        return twelve
    return None


def _unavailable(resolved: dict, reason: str) -> dict:
    clocks = sessions.describe()
    return {
        "success": False,
        "symbol": resolved.get("token"),
        "error": reason,
        "quality": "UNAVAILABLE",
        "clocks": clocks["clocks"],
        "disclaimer": DISCLAIMER,
    }


def quotes(raw_symbols: str, region: str | None = None) -> dict:
    parts = [part.strip() for part in (raw_symbols or "").split(",") if part.strip()]
    if not parts:
        return {"success": False, "error": "Add at least one symbol.", "quotes": [], "disclaimer": DISCLAIMER}
    if len(parts) > 20:
        parts = parts[:20]
    rows = [quote(part, region) for part in parts]
    return {
        "success": any(row.get("success") for row in rows),
        "quotes": rows,
        "sessions": sessions.describe(),
        "disclaimer": DISCLAIMER,
    }


def overview() -> dict:
    cached = CACHE.get("overview", QUOTE_TTL)
    if cached:
        return cached
    with FETCH_LOCK:
        cached = CACHE.get("overview", QUOTE_TTL)
        if cached:
            return cached
        payload = _overview()
    CACHE.set("overview", payload)
    return payload


def _overview() -> dict:
    moment = _now()
    tv = providers.fetch_tradingview([item["tv"] for item in INDEX_BOOK])
    rows = []
    warnings = []
    for item in INDEX_BOOK:
        raw = dict(tv.get(item["tv"]) or {})
        if item.get("calendar"):
            raw["calendar"] = item["calendar"]
        if not raw.get("price"):
            warnings.append(f"{item['name']} is unavailable from the current providers.")
            continue
        resolved = {"token": item["name"], "tv": [item["tv"]], "region_hint": symbols.region_of(item["tv"])}
        presented = _present(raw, resolved, moment)
        presented["name"] = item["name"]
        presented["flag"] = item["flag"]
        presented["success"] = True
        rows.append(presented)
    board = sessions.describe(moment)
    return {
        "success": bool(rows),
        "indices": rows,
        "sessions": board,
        "warnings": warnings,
        "source": "live_markets",
        "cache_seconds": QUOTE_TTL,
        "disclaimer": DISCLAIMER,
        "sources": _source_notes(),
    }


def index_rows() -> list[dict]:
    """Shape consumed by the existing /api/global-ticker."""
    board = overview()
    rows = []
    for item in board.get("indices") or []:
        if item.get("price") is None:
            continue
        rows.append({
            "name": item["name"],
            "flag": item.get("flag") or "",
            "price": item["price"],
            "change": item.get("change") or 0,
            "change_pct": item.get("change_pct") or 0,
        })
    return rows


def ticker_payload() -> dict:
    board = overview()
    ist = (board.get("sessions") or {}).get("clocks", {}).get("ist", "")
    return {
        "success": bool(board.get("indices")),
        "indices": [
            {
                "name": item["name"],
                "flag": item.get("flag") or "",
                "price": item.get("price") or 0,
                "change": item.get("change") or 0,
                "change_pct": item.get("change_pct") or 0,
            }
            for item in board.get("indices") or []
        ],
        "updated_at": ist,
        "source": "live_markets",
        "quality": "mixed",
        "disclaimer": DISCLAIMER,
    }


def research(symbol: str, region: str | None = None) -> dict:
    row = quote(symbol, region)
    if not row.get("success"):
        row["verdict"] = verdict.score({})
        return row
    scored = verdict.score(row.get("features") or {})
    row = dict(row)
    row["verdict"] = scored
    return row


def screen(market: str) -> dict:
    choice = "IN" if (market or "").upper() == "IN" else "US"
    key = "screen:" + choice
    cached = CACHE.get(key, SCREEN_TTL)
    if cached:
        return cached
    symbols_list = IN_SCREEN if choice == "IN" else US_SCREEN
    prefix = "NSE" if choice == "IN" else "NASDAQ"
    # US names can be NYSE. Ask both and keep the first hit per root.
    tv_symbols = []
    roots = []
    for root in symbols_list:
        roots.append(root)
        if choice == "IN":
            tv_symbols.append(f"NSE:{root}")
        else:
            tv_symbols.extend([f"NASDAQ:{root}", f"NYSE:{root}"])
    found = providers.fetch_tradingview(tv_symbols)
    ranked = []
    for root in roots:
        raw = found.get(f"{prefix}:{root}") or found.get(f"NYSE:{root}") or found.get(f"NASDAQ:{root}")
        if not raw:
            continue
        resolved = {"token": root, "tv": [raw["tv_symbol"]]}
        presented = _present(raw, resolved)
        presented["verdict"] = verdict.score(presented["features"])
        presented["success"] = True
        ranked.append(presented)
    ranked.sort(key=lambda item: (item["verdict"]["score"] is not None, item["verdict"]["score"] or -1), reverse=True)
    payload = {
        "success": bool(ranked),
        "market": choice,
        "universe": "A fixed liquid sample, not the full exchange.",
        "results": ranked,
        "sessions": sessions.describe(),
        "disclaimer": DISCLAIMER,
    }
    CACHE.set(key, payload)
    return payload


def options(symbol: str, region: str | None = None) -> dict:
    resolved = symbols.resolve(symbol, region)
    key = "opt:" + resolved["token"] + ":" + (resolved.get("region_hint") or "")
    cached = CACHE.get(key, 120)
    if cached:
        return cached
    region_hint = resolved.get("region_hint")
    chain = None
    try:
        from market_data.layer import option_chain as provider_chain
        chain = provider_chain(resolved["token"], region_hint)
    except Exception:
        chain = None
    if not chain or not chain.get("available"):
        if region_hint in (None, "IN"):
            nse_symbol = resolved["token"][:-3] if resolved["token"].endswith(".NS") else resolved["token"]
            nse = options_chain.fetch_nse_chain(nse_symbol)
            if nse and nse.get("available"):
                chain = nse
            elif chain is None:
                chain = nse
    if not chain:
        chain = {
            "available": False,
            "provider": None,
            "reason": "No option chain responded. US chains use Finnhub. India index chains use Angel One when that session is configured.",
        }
    underlying = quote(symbol, region)
    payload = {
        "success": bool(chain.get("available")),
        "symbol": resolved["token"],
        "underlying": {
            "price": underlying.get("price"),
            "quality": underlying.get("quality"),
            "session": underlying.get("session"),
            "as_of": underlying.get("as_of"),
        },
        "chain": chain,
        "angel_one_configured": _angel_configured(),
        "disclaimer": DISCLAIMER + " Option quotes can be wider than the underlying and are not an order ticket.",
    }
    if chain.get("available"):
        CACHE.set(key, payload)
    return payload


def _angel_configured() -> bool:
    try:
        import angel_options
        return bool(angel_options.configured())
    except Exception:
        return False


def price_tick_quote(symbol: str, region: str) -> Optional[dict]:
    row = quote(symbol, region)
    if not row.get("success") or not row.get("price"):
        return None
    price = row["price"]
    change = row.get("change") or 0
    return {
        "price": price,
        "prev_close": round(price - change, 2) if change else price,
        "volume": row.get("volume") or 0,
        "day_high": price,
        "day_low": price,
    }


def health() -> dict:
    return {
        "ok": True,
        "cache_seconds": QUOTE_TTL,
        "finnhub_configured": bool(os.getenv("FINNHUB_API_KEY", "").strip()),
        "twelve_data_configured": bool(os.getenv("TWELVE_DATA_API_KEY", "").strip()),
        "angel_one_configured": _angel_configured(),
        "providers": ["tradingview", "finnhub", "angel", "screener", "sec", "nasdaq", "twelvedata?"],
        "sources": _source_notes(),
        "sessions": sessions.describe(),
    }


def _source_notes() -> list[dict]:
    return [
        {
            "id": "tradingview",
            "role": "Primary quotes, indices, technical context",
            "auth": "none",
            "freshness": "Provider flag. Equities in checks were delayed_streaming_900 (15 minutes) or delayed_streaming_600.",
            "limit": "Unofficial scanner. Cached. Not a licensed real-time feed.",
            "cost": "free",
        },
        {
            "id": "finnhub",
            "role": "US quotes, candles, fundamentals, earnings, peers and news",
            "auth": "FINNHUB_API_KEY",
            "freshness": "Last trade when the key is set. Sunday and overnight prints are the last close.",
            "limit": "Free tier is about 60 calls a minute. Candles fall back to Nasdaq daily history when the candle route is unavailable.",
            "cost": "free tier",
        },
        {
            "id": "nse",
            "role": "India F&O chain when the exchange allows the request",
            "auth": "none",
            "freshness": "Exchange print during the session, otherwise the last chain NSE returns.",
            "limit": "Often HTTP 403 from datacenter and Render IPs.",
            "cost": "free",
        },
        {
            "id": "twelvedata",
            "role": "Optional last-resort quote when TWELVE_DATA_API_KEY is set",
            "auth": "TWELVE_DATA_API_KEY",
            "freshness": "Labeled delayed.",
            "limit": "Free tier is about 8 requests/minute and 800/day.",
            "cost": "free tier",
        },
    ]
