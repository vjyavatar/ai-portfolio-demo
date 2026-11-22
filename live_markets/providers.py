"""Quote providers. Free sources first. Keys stay in the environment."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional

USER_AGENT = "Mozilla/5.0 (compatible; CelesysLiveBoard/1.0; +https://celesys.ai)"

TV_COLUMNS = [
    "close",
    "change",
    "change_abs",
    "volume",
    "description",
    "currency",
    "update_mode",
    "RSI",
    "SMA50",
    "SMA200",
    "price_52_week_high",
    "price_52_week_low",
    "price_earnings_ttm",
    "Recommend.All",
    "average_volume_10d_calc",
    "Perf.W",
    "Perf.1M",
]

HttpGet = Callable[[str, Optional[bytes], int], tuple[int, bytes]]


def _default_http(url: str, data: Optional[bytes], timeout: int) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
            "Content-Type": "application/json" if data else "text/plain",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return exc.code, body


def quality_from_mode(mode: str | None) -> tuple[str, int | None]:
    text = (mode or "").strip().lower()
    if not text:
        return "DELAYED", None
    if "delayed" in text:
        tail = text.split("_")[-1]
        delay = int(tail) if tail.isdigit() else None
        return "DELAYED", delay
    if text in {"streaming", "realtime", "real-time", "live"}:
        return "LIVE", 0
    return "DELAYED", None


def parse_tradingview(payload: dict) -> dict[str, dict]:
    rows = {}
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return rows
    for row in data:
        if not isinstance(row, dict):
            continue
        symbol = row.get("s")
        values = row.get("d")
        if not symbol or not isinstance(values, list) or len(values) < len(TV_COLUMNS):
            continue
        fields = dict(zip(TV_COLUMNS, values))
        price = _num(fields.get("close"))
        if price is None or price <= 0:
            continue
        quality, delay = quality_from_mode(fields.get("update_mode") if isinstance(fields.get("update_mode"), str) else None)
        rows[symbol] = {
            "tv_symbol": symbol,
            "price": price,
            "change": _num(fields.get("change_abs")),
            "change_pct": _num(fields.get("change")),
            "volume": _num(fields.get("volume")),
            "name": fields.get("description") or symbol,
            "currency": fields.get("currency") if isinstance(fields.get("currency"), str) else None,
            "provider": "tradingview",
            "provider_mode": fields.get("update_mode"),
            "quality": quality,
            "delay_seconds": delay,
            "features": {
                "rsi": _num(fields.get("RSI")),
                "sma50": _num(fields.get("SMA50")),
                "sma200": _num(fields.get("SMA200")),
                "high_52w": _num(fields.get("price_52_week_high")),
                "low_52w": _num(fields.get("price_52_week_low")),
                "pe": _num(fields.get("price_earnings_ttm")),
                "recommend": _num(fields.get("Recommend.All")),
                "avg_volume": _num(fields.get("average_volume_10d_calc")),
                "perf_w": _num(fields.get("Perf.W")),
                "perf_1m": _num(fields.get("Perf.1M")),
            },
        }
    return rows


def fetch_tradingview(tickers: list[str], http: HttpGet = _default_http, timeout: int = 8) -> dict[str, dict]:
    wanted = [t for t in tickers if t]
    if not wanted:
        return {}
    body = json.dumps({"symbols": {"tickers": wanted[:40]}, "columns": TV_COLUMNS}).encode()
    status, raw = http("https://scanner.tradingview.com/global/scan", body, timeout)
    if status != 200 or not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return {}
    found = parse_tradingview(payload)
    missing = [t for t in wanted if t not in found]
    if not missing:
        return found
    # Regional scanners sometimes carry a name the global scan skips.
    grouped: dict[str, list[str]] = {}
    for ticker in missing:
        prefix = ticker.split(":", 1)[0]
        market = "india" if prefix in {"NSE", "BSE"} else "america"
        grouped.setdefault(market, []).append(ticker)
    for market, symbols in grouped.items():
        body = json.dumps({"symbols": {"tickers": symbols[:40]}, "columns": TV_COLUMNS}).encode()
        status, raw = http(f"https://scanner.tradingview.com/{market}/scan", body, timeout)
        if status != 200 or not raw:
            continue
        try:
            found.update(parse_tradingview(json.loads(raw.decode("utf-8", "replace"))))
        except json.JSONDecodeError:
            continue
    return found


def parse_yahoo_chart(payload: dict) -> Optional[dict]:
    result = (((payload or {}).get("chart") or {}).get("result") or [None])[0]
    if not isinstance(result, dict):
        return None
    meta = result.get("meta") or {}
    price = _num(meta.get("regularMarketPrice"))
    if price is None or price <= 0:
        return None
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = [c for c in (quote.get("close") or []) if _num(c) is not None]
    prev = closes[-2] if len(closes) >= 2 else _num(meta.get("chartPreviousClose"))
    change_pct = _num(meta.get("regularMarketChangePercent"))
    change = None
    if prev and prev > 0:
        change = price - prev
        if change_pct is None:
            change_pct = (change / prev) * 100
    elif change_pct is not None:
        change = price - (price / (1 + change_pct / 100))
    volumes = [v for v in (quote.get("volume") or []) if _num(v) is not None]
    return {
        "price": price,
        "prev_close": prev,
        "change": change,
        "change_pct": change_pct,
        "volume": _num(meta.get("regularMarketVolume")) or (volumes[-1] if volumes else None),
        "day_high": _num(meta.get("regularMarketDayHigh")),
        "day_low": _num(meta.get("regularMarketDayLow")),
        "currency": meta.get("currency"),
        "name": meta.get("shortName") or meta.get("symbol"),
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "as_of_epoch": _num(meta.get("regularMarketTime")),
        "provider": "yahoo",
        "provider_mode": "chart_v8",
        "quality": "DELAYED",
        "delay_seconds": None,
    }


def fetch_yahoo(symbol: str, http: HttpGet = _default_http, timeout: int = 8) -> Optional[dict]:
    """Retired Yahoo chart entry. It does not call Yahoo. Tests assert it stays unused."""
    del symbol, http, timeout
    return None


def fetch_reference_quote(symbol: str, http: HttpGet = _default_http, timeout: int = 8) -> Optional[dict]:
    """Kept for older callers. Quotes are served by market_data.layer, not this HTTP helper."""
    del http, timeout
    if not symbol:
        return None
    try:
        from market_data.layer import quote
        env = quote(symbol)
    except Exception:
        return None
    data = env.get("data") if isinstance(env, dict) else None
    if not data or not data.get("price"):
        return None
    return {
        "price": data.get("price"),
        "prev_close": data.get("prev_close"),
        "change": data.get("change"),
        "change_pct": data.get("change_pct"),
        "volume": data.get("volume"),
        "currency": data.get("currency"),
        "name": data.get("name"),
        "provider": env.get("source") or "provider",
        "provider_mode": "quote",
        "quality": "LAST_CLOSE" if env.get("stale") else "DELAYED",
        "delay_seconds": None,
        "as_of": env.get("as_of"),
    }


def fetch_finnhub(symbol: str, http: HttpGet = _default_http, timeout: int = 8) -> Optional[dict]:
    key = os.getenv("FINNHUB_API_KEY", "").strip()
    if not key or not symbol or symbol.startswith("^"):
        return None
    url = "https://finnhub.io/api/v1/quote?" + urllib.parse.urlencode({"symbol": symbol, "token": key})
    status, raw = http(url, None, timeout)
    if status != 200 or not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None
    price = _num(data.get("c"))
    prev = _num(data.get("pc"))
    if price is None or price <= 0:
        return None
    change = price - prev if prev else _num(data.get("d"))
    change_pct = ((change / prev) * 100) if prev else _num(data.get("dp"))
    return {
        "price": price,
        "prev_close": prev,
        "change": change,
        "change_pct": change_pct,
        "volume": None,
        "as_of_epoch": _num(data.get("t")),
        "provider": "finnhub",
        "provider_mode": "quote",
        "quality": "LIVE",
        "delay_seconds": 0,
        "currency": "USD",
    }


def fetch_twelve(symbol: str, http: HttpGet = _default_http, timeout: int = 8) -> Optional[dict]:
    key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
    if not key or not symbol:
        return None
    url = "https://api.twelvedata.com/quote?" + urllib.parse.urlencode({"symbol": symbol, "apikey": key})
    status, raw = http(url, None, timeout)
    if status != 200 or not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None
    price = _num(data.get("close"))
    prev = _num(data.get("previous_close"))
    if price is None or price <= 0:
        return None
    change = price - prev if prev else None
    change_pct = ((change / prev) * 100) if prev else _num(data.get("percent_change"))
    return {
        "price": price,
        "prev_close": prev,
        "change": change,
        "change_pct": change_pct,
        "volume": _num(data.get("volume")),
        "name": data.get("name"),
        "currency": data.get("currency"),
        "provider": "twelvedata",
        "provider_mode": "quote",
        "quality": "DELAYED",
        "delay_seconds": None,
    }


def _num(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number
