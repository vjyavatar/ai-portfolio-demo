"""Single market-data provider for Celesys.

US quotes and fundamentals come from Finnhub when FINNHUB_API_KEY is set,
with TradingView scanner fields and SEC EDGAR companyfacts filling gaps.
US daily candles are TradingView, then Nasdaq, then Stooq, then Finnhub.
India candles are Angel
getCandleData through the static-IP proxy, then Screener.in, TradingView,
and the Nifty index graph. Each candle step gives up after about 5 seconds
and the next source runs. The whole chain stays inside an 8 second budget.

India quotes come from Angel One SmartAPI when a session is configured, then
the TradingView India scanner. India fundamentals come from the TradingView
scanner and Screener.in company pages.

Nothing in this module calls Yahoo Finance. Quote and fundamentals calls keep
an 8 second timeout and one retry. Candle calls do not retry. An in-memory
TTL cache plus a single in-flight load serve concurrent readers. A failed
refresh returns the last cached payload labelled stale, with its source and
timestamp.
"""
from __future__ import annotations

import base64
import json
import os
import re
import socket
import ssl
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable, Optional

import pandas as pd

# One list per region and data type. Edit a tuple here to change a source.
SOURCES = {
    "US": {
        "price": ("tradingview", "finnhub"),
        "candle": ("tradingview", "nasdaq", "stooq", "finnhub"),
        "fundamental": ("tradingview", "finnhub", "sec"),
        "growth": ("sec", "finnhub", "tradingview"),
    },
    "IN": {
        "price": ("angel", "tradingview"),
        "candle": ("angel", "screener", "tradingview"),
        "fundamental": ("screener", "tradingview"),
        "growth": ("screener", "tradingview"),
    },
}
FINANCIALS = {
    "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "BAJFINANCE",
    "BAJAJFINSV", "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB",
    "JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "AXP",
}

TIMEOUT = 8
RETRIES = 1
CANDLE_TIMEOUT = 5
CANDLE_BUDGET = 8
ANGEL_CANDLE_TIMEOUT = 2
TTL_QUOTE = 20
TTL_CANDLE = 5 * 60
TTL_FUND = 18 * 3600

_USER_AGENT = "Celesys Research/4.63 (+https://celesys.ai)"
_TV = "https://scanner.tradingview.com/global/scan"
_NASDAQ = "https://api.nasdaq.com/api/quote/{symbol}/historical"
_SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
_SEC_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_SCREENER_PAGE = "https://www.screener.in/company/{symbol}/consolidated/"
_SCREENER_CHART = "https://www.screener.in/api/company/{cid}/chart/?q=Price-Volume&days=420"
_MC_INDEX_URL = "https://appfeeds.moneycontrol.com/jsonapi/market/graph&format=json&ind_id={ind}&range=1yr"
_ANGEL_CANDLE = "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getCandleData"
_ANGEL_LTP = "https://apiconnect.angelone.in/rest/secure/angelbroking/order/v1/getLtpData"

_YAHOO_HOSTS = (
    "query1.finance.yahoo.com",
    "query2.finance.yahoo.com",
    "finance.yahoo.com",
    "fc.yahoo.com",
    "feeds.finance.yahoo.com",
)

_TV_COLUMNS = [
    "close", "change", "change_abs", "volume", "description", "currency",
    "update_mode", "price_earnings_ttm", "price_book_fq", "return_on_equity",
    "gross_margin", "net_margin", "operating_margin", "market_cap_basic",
    "beta_1_year", "price_52_week_high", "price_52_week_low",
    "book_value_per_share_fq", "earnings_per_share_basic_ttm", "current_ratio",
    "Recommend.All", "average_volume_10d_calc", "last_bar_update_time",
]

QUOTE_MAX_AGE = 5 * 24 * 3600

_INDIA_EQUITY = {
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "TATAMOTORS",
    "BHARTIARTL", "LT", "BAJFINANCE", "ITC", "MARUTI", "WIPRO", "KOTAKBANK",
    "ADANIENT", "ADANIPORTS", "HINDALCO", "JSWSTEEL", "TATASTEEL", "ONGC",
    "NTPC", "POWERGRID", "BPCL", "HCLTECH", "TECHM", "DRREDDY", "CIPLA",
    "SUNPHARMA", "HINDUNILVR", "ASIANPAINT", "ULTRACEMCO", "GRASIM", "TITAN",
    "BAJAJFINSV", "AXISBANK", "INDUSINDBK", "KAYNES",
}
_INDIA_INDEX = {
    "NIFTY": "NSE:NIFTY",
    "^NSEI": "NSE:NIFTY",
    "BANKNIFTY": "NSE:BANKNIFTY",
    "^NSEBANK": "NSE:BANKNIFTY",
    "SENSEX": "BSE:SENSEX",
    "^BSESN": "BSE:SENSEX",
    "FINNIFTY": "NSE:CNXFINANCE",
}
_MC_INDEX = {"NIFTY": 9, "^NSEI": 9, "BANKNIFTY": 23, "^NSEBANK": 23}
_US_INDEX = {
    "^GSPC": "SP:SPX", "SPX": "SP:SPX", "^IXIC": "NASDAQ:IXIC",
    "NASDAQ": "NASDAQ:IXIC", "IXIC": "NASDAQ:IXIC",
    "^DJI": "DJ:DJI", "^VIX": "CBOE:VIX", "VIX": "CBOE:VIX",
    "GOLD": "TVC:GOLD", "GC=F": "TVC:GOLD",
    "USDINR": "FX_IDC:USDINR", "INR=X": "FX_IDC:USDINR",
}

_lock = threading.Lock()
_cache: dict[str, dict] = {}
_inflight: dict[str, threading.Event] = {}
_cik_map: dict[str, int] | None = None
_orig_urlopen = urllib.request.urlopen


def _blocked(url: str) -> bool:
    text = url.lower()
    return any(host in text for host in _YAHOO_HOSTS)


def _guarded_urlopen(req, *args, **kwargs):
    url = getattr(req, "full_url", None) or str(req)
    if _blocked(url):
        raise RuntimeError("Yahoo Finance is disabled")
    return _orig_urlopen(req, *args, **kwargs)


urllib.request.urlopen = _guarded_urlopen


def _now() -> float:
    return time.time()


def _iso(epoch: Optional[float] = None) -> str:
    moment = datetime.fromtimestamp(epoch or _now(), timezone.utc)
    return moment.replace(microsecond=0).isoformat()


def _num(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.replace(",", "").replace("$", "").replace("₹", "").replace("%", "").strip()
        if not value or value in {"-", "—", "NA", "N/A"}:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _cache_get(key: str, ttl: float) -> Optional[dict]:
    with _lock:
        row = _cache.get(key)
        if not row:
            return None
        if _now() - row["stored_at"] <= ttl:
            hit = deepcopy(row["value"])
            hit["stale"] = False
            return hit
    return None


def _cache_stale(key: str) -> Optional[dict]:
    with _lock:
        row = _cache.get(key)
        if not row:
            return None
        hit = deepcopy(row["value"])
    hit["stale"] = True
    hit["cached_at"] = row["stored_at"]
    return hit


def _cache_put(key: str, value: dict) -> dict:
    # A miss is not stored. The next call must try the providers again.
    if not value.get("ok"):
        return deepcopy(value)
    stored = deepcopy(value)
    stored.setdefault("as_of", _iso())
    stored["stale"] = False
    with _lock:
        _cache[key] = {"stored_at": _now(), "value": stored}
        if len(_cache) > 800:
            oldest = min(_cache, key=lambda item: _cache[item]["stored_at"])
            _cache.pop(oldest, None)
    return deepcopy(stored)


def _unavailable() -> dict:
    return {
        "ok": False,
        "data": None,
        "source": None,
        "as_of": None,
        "stale": False,
        "error": "Market data is temporarily unavailable.",
        "metric_sources": {},
    }


def _remember(key: str, ttl: float, loader: Callable[[], Optional[dict]]) -> dict:
    """One load per key. A failed load is not cached, and a waiter may try again."""
    for _attempt in range(2):
        fresh = _cache_get(key, ttl)
        if fresh and fresh.get("ok"):
            return fresh
        with _lock:
            event = _inflight.get(key)
            owner = event is None
            if owner:
                event = threading.Event()
                _inflight[key] = event
        if not owner:
            event.wait(20)
            continue
        try:
            loaded = None
            try:
                loaded = loader()
            except Exception:
                loaded = None
            if loaded and loaded.get("ok"):
                return _cache_put(key, loaded)
            stale = _cache_stale(key)
            if stale and stale.get("ok"):
                return stale
            return _unavailable()
        finally:
            event.set()
            with _lock:
                if _inflight.get(key) is event:
                    _inflight.pop(key, None)
    return _unavailable()


def _request(url: str, *, data: Optional[bytes] = None, headers: Optional[dict] = None, timeout: int = TIMEOUT, retries: Optional[int] = None) -> tuple[int, bytes]:
    if _blocked(url):
        raise RuntimeError("Yahoo Finance is disabled")
    hdrs = {"User-Agent": _USER_AGENT, "Accept": "application/json,text/plain,*/*"}
    if headers:
        hdrs.update(headers)
    attempts = RETRIES if retries is None else max(0, int(retries))
    last_error = None
    for attempt in range(attempts + 1):
        req = urllib.request.Request(url, data=data, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read() if exc.fp else b""
            if exc.code in (429, 500, 502, 503, 504) and attempt < attempts:
                time.sleep(0.4)
                continue
            return exc.code, body
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.4)
                continue
    raise TimeoutError("provider timed out") from last_error


def _json(url: str, **kwargs) -> Optional[Any]:
    try:
        status, raw = _request(url, **kwargs)
    except Exception:
        return None
    if status != 200 or not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None


def classify(symbol: str, region: Optional[str] = None) -> dict:
    raw = (symbol or "").strip().upper()
    hint = (region or "").strip().upper()
    root = raw[:-3] if raw.endswith(".NS") or raw.endswith(".BO") else raw
    if hint in {"US", "IN"}:
        market = hint
    elif raw.endswith((".NS", ".BO")) or root in _INDIA_INDEX or root in _INDIA_EQUITY:
        market = "IN"
    elif raw in _US_INDEX or raw.startswith("^"):
        market = "US"
    else:
        market = "US"
    kind = "index" if root in _INDIA_INDEX or raw in _US_INDEX or root in _US_INDEX else "equity"
    if market == "IN":
        tv = [_INDIA_INDEX.get(root) or _INDIA_INDEX.get(raw) or f"NSE:{root}"]
    else:
        tv = [_US_INDEX[raw]] if raw in _US_INDEX else [f"NASDAQ:{root}", f"NYSE:{root}", f"AMEX:{root}"]
    return {
        "raw": raw,
        "root": root,
        "region": market,
        "kind": kind,
        "currency": "INR" if market == "IN" else "USD",
        "tv": tv,
        "finnhub": root if market == "US" and kind == "equity" else None,
    }


def _stamp(source: str, stale: bool = False) -> dict:
    return {"source": source, "as_of": _iso(), "stale": stale}


def _tv_row(symbol: str, region: Optional[str] = None) -> Optional[dict]:
    meta = classify(symbol, region)
    key = "tv:" + ",".join(meta["tv"])

    def load():
        body = json.dumps({"symbols": {"tickers": meta["tv"][:8]}, "columns": _TV_COLUMNS}).encode()
        payload = _json(_TV, data=body, headers={"Content-Type": "application/json", "Origin": "https://www.tradingview.com"})
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return None
        found = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            values = row.get("d")
            if not isinstance(values, list) or len(values) < len(_TV_COLUMNS):
                continue
            fields = dict(zip(_TV_COLUMNS, values))
            price = _num(fields.get("close"))
            if price is None or price <= 0:
                continue
            found = {"tv_symbol": row.get("s"), "fields": fields, "price": price}
            break
        if not found:
            return None
        return {"ok": True, "data": found, "source": "tradingview", "as_of": _iso(), "metric_sources": {}}

    env = _remember(key, TTL_QUOTE, load)
    return env.get("data") if env.get("ok") else None


def _finnhub(path: str, params: dict, timeout: int = TIMEOUT, retries: int = RETRIES) -> Optional[Any]:
    key = os.getenv("FINNHUB_API_KEY", "").strip()
    if not key:
        return None
    query = dict(params)
    query["token"] = key
    url = "https://finnhub.io/api/v1" + path + "?" + urllib.parse.urlencode(query)
    try:
        return _json(url, timeout=timeout, retries=retries)
    except Exception:
        return None


def _put_metric(info: dict, sources: dict, field: str, value, source: str, as_of: str) -> None:
    number = _num(value)
    if number is None:
        return
    if info.get(field) not in (None, 0, 0.0, ""):
        return
    info[field] = number
    sources[field] = {"source": source, "as_of": as_of, "value": number}


def _apply_tv_fundamentals(info: dict, sources: dict, row: dict, as_of: str) -> None:
    fields = row.get("fields") or {}
    price = _num(row.get("price"))
    change = _num(fields.get("change_abs"))
    _put_metric(info, sources, "currentPrice", price, "tradingview", as_of)
    _put_metric(info, sources, "regularMarketPrice", price, "tradingview", as_of)
    if price is not None and change is not None:
        _put_metric(info, sources, "previousClose", price - change, "tradingview", as_of)
    _put_metric(info, sources, "trailingPE", fields.get("price_earnings_ttm"), "tradingview", as_of)
    _put_metric(info, sources, "priceToBook", fields.get("price_book_fq"), "tradingview", as_of)
    roe = _num(fields.get("return_on_equity"))
    if roe is not None:
        _put_metric(info, sources, "returnOnEquity", roe / 100.0, "tradingview", as_of)
    for src_key, dest in (
        ("gross_margin", "grossMargins"),
        ("net_margin", "profitMargins"),
        ("operating_margin", "operatingMargins"),
    ):
        margin = _num(fields.get(src_key))
        if margin is not None:
            _put_metric(info, sources, dest, margin / 100.0, "tradingview", as_of)
    _put_metric(info, sources, "marketCap", fields.get("market_cap_basic"), "tradingview", as_of)
    _put_metric(info, sources, "beta", fields.get("beta_1_year"), "tradingview", as_of)
    _put_metric(info, sources, "fiftyTwoWeekHigh", fields.get("price_52_week_high"), "tradingview", as_of)
    _put_metric(info, sources, "fiftyTwoWeekLow", fields.get("price_52_week_low"), "tradingview", as_of)
    _put_metric(info, sources, "bookValue", fields.get("book_value_per_share_fq"), "tradingview", as_of)
    _put_metric(info, sources, "trailingEps", fields.get("earnings_per_share_basic_ttm"), "tradingview", as_of)
    _put_metric(info, sources, "currentRatio", fields.get("current_ratio"), "tradingview", as_of)
    volume = _num(fields.get("volume")) or _num(fields.get("average_volume_10d_calc"))
    _put_metric(info, sources, "averageVolume", volume, "tradingview", as_of)
    _put_metric(info, sources, "volume", fields.get("volume"), "tradingview", as_of)
    name = fields.get("description")
    if isinstance(name, str) and name and not info.get("shortName"):
        info["shortName"] = name
        info["longName"] = name
        sources["shortName"] = {"source": "tradingview", "as_of": as_of, "value": name}
    currency = fields.get("currency")
    if isinstance(currency, str) and currency:
        info["currency"] = currency


def _apply_finnhub(info: dict, sources: dict, symbol: str, as_of: str) -> dict:
    """Fill quote, profile, ratios, targets and earnings. Returns the parallel payload."""
    root = classify(symbol)["finnhub"]
    if not root:
        return {}
    jobs = {
        "quote": ("/quote", {"symbol": root}),
        "profile": ("/stock/profile2", {"symbol": root}),
        "metric": ("/stock/metric", {"symbol": root, "metric": "all"}),
        "target": ("/stock/price-target", {"symbol": root}),
        "recs": ("/stock/recommendation", {"symbol": root}),
        "earnings": ("/calendar/earnings", {"symbol": root, "from": (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat(), "to": (datetime.now(timezone.utc) + timedelta(days=120)).date().isoformat()}),
        "peers": ("/stock/peers", {"symbol": root}),
    }
    found: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=7) as pool:
        future_map = {pool.submit(_finnhub, path, params): name for name, (path, params) in jobs.items()}
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                found[name] = future.result()
            except Exception:
                found[name] = None
    quote = found.get("quote") if isinstance(found.get("quote"), dict) else {}
    price = _num(quote.get("c"))
    if price and price > 0:
        _put_metric(info, sources, "currentPrice", price, "finnhub", as_of)
        _put_metric(info, sources, "regularMarketPrice", price, "finnhub", as_of)
        _put_metric(info, sources, "previousClose", quote.get("pc"), "finnhub", as_of)
        _put_metric(info, sources, "open", quote.get("o"), "finnhub", as_of)
        _put_metric(info, sources, "dayHigh", quote.get("h"), "finnhub", as_of)
        _put_metric(info, sources, "dayLow", quote.get("l"), "finnhub", as_of)
    profile = found.get("profile") if isinstance(found.get("profile"), dict) else {}
    if profile.get("name"):
        info.setdefault("shortName", profile.get("name"))
        info.setdefault("longName", profile.get("name"))
        sources.setdefault("shortName", {"source": "finnhub", "as_of": as_of, "value": profile.get("name")})
    if profile.get("finnhubIndustry"):
        info.setdefault("sector", profile.get("finnhubIndustry"))
        info.setdefault("industry", profile.get("finnhubIndustry"))
        sources.setdefault("sector", {"source": "finnhub", "as_of": as_of, "value": profile.get("finnhubIndustry")})
    mcap_m = _num(profile.get("marketCapitalization"))
    if mcap_m and mcap_m > 0:
        _put_metric(info, sources, "marketCap", mcap_m * 1_000_000, "finnhub", as_of)
    shares_m = _num(profile.get("shareOutstanding"))
    if shares_m and shares_m > 0:
        _put_metric(info, sources, "sharesOutstanding", shares_m * 1_000_000, "finnhub", as_of)
    metric = found.get("metric") if isinstance(found.get("metric"), dict) else {}
    ratios = metric.get("metric") if isinstance(metric.get("metric"), dict) else {}
    def pct(key):
        value = _num(ratios.get(key))
        return None if value is None else value / 100.0
    _put_metric(info, sources, "trailingPE", ratios.get("peBasicExclExtraTTM") or ratios.get("peTTM") or ratios.get("peNormalizedAnnual") or ratios.get("peExclExtraAnnual"), "finnhub", as_of)
    _put_metric(info, sources, "forwardPE", ratios.get("peInclExtraTTM"), "finnhub", as_of)
    _put_metric(info, sources, "priceToBook", ratios.get("pbQuarterly") or ratios.get("pbAnnual"), "finnhub", as_of)
    _put_metric(info, sources, "grossMargins", pct("grossMarginTTM") if ratios.get("grossMarginTTM") is not None else pct("grossMarginAnnual"), "finnhub", as_of)
    _put_metric(info, sources, "profitMargins", pct("netProfitMarginTTM") if ratios.get("netProfitMarginTTM") is not None else pct("netProfitMarginAnnual"), "finnhub", as_of)
    _put_metric(info, sources, "operatingMargins", pct("operatingMarginTTM") if ratios.get("operatingMarginTTM") is not None else pct("operatingMarginAnnual"), "finnhub", as_of)
    _put_metric(info, sources, "returnOnEquity", pct("roeTTM") if ratios.get("roeTTM") is not None else pct("roeRfy"), "finnhub", as_of)
    _put_metric(info, sources, "returnOnAssets", pct("roaTTM"), "finnhub", as_of)
    _put_metric(info, sources, "revenueGrowth", pct("revenueGrowthTTMYoy"), "finnhub", as_of)
    _put_metric(info, sources, "earningsGrowth", pct("epsGrowthTTMYoy"), "finnhub", as_of)
    _put_metric(info, sources, "beta", ratios.get("beta"), "finnhub", as_of)
    _put_metric(info, sources, "currentRatio", ratios.get("currentRatioQuarterly") or ratios.get("currentRatioAnnual"), "finnhub", as_of)
    _put_metric(info, sources, "fiftyTwoWeekHigh", ratios.get("52WeekHigh"), "finnhub", as_of)
    _put_metric(info, sources, "fiftyTwoWeekLow", ratios.get("52WeekLow"), "finnhub", as_of)
    _put_metric(info, sources, "bookValue", ratios.get("bookValuePerShareQuarterly") or ratios.get("bookValuePerShareAnnual"), "finnhub", as_of)
    debt = _num(ratios.get("totalDebt/totalEquityQuarterly") or ratios.get("totalDebt/totalEquityAnnual"))
    if debt is not None:
        _put_metric(info, sources, "debtToEquity", debt if debt > 5 else debt * 100.0, "finnhub", as_of)
    target = found.get("target") if isinstance(found.get("target"), dict) else {}
    _put_metric(info, sources, "targetMeanPrice", target.get("targetMean"), "finnhub", as_of)
    _put_metric(info, sources, "targetHighPrice", target.get("targetHigh"), "finnhub", as_of)
    _put_metric(info, sources, "targetLowPrice", target.get("targetLow"), "finnhub", as_of)
    recs = found.get("recs") if isinstance(found.get("recs"), list) else []
    if recs and isinstance(recs[0], dict):
        latest = recs[0]
        count = sum(_num(latest.get(key)) or 0 for key in ("strongBuy", "buy", "hold", "sell", "strongSell"))
        if count:
            _put_metric(info, sources, "numberOfAnalystOpinions", count, "finnhub", as_of)
        info["_recommendations"] = recs
    earnings = found.get("earnings") if isinstance(found.get("earnings"), dict) else {}
    calendar = earnings.get("earningsCalendar") if isinstance(earnings.get("earningsCalendar"), list) else []
    if calendar:
        info["_earnings_calendar"] = calendar
        upcoming = [row for row in calendar if isinstance(row, dict) and row.get("date")]
        if upcoming:
            info["earningsDate"] = upcoming[0].get("date")
            sources["earningsDate"] = {"source": "finnhub", "as_of": as_of, "value": upcoming[0].get("date")}
    peers = found.get("peers")
    if isinstance(peers, list):
        info["_peers"] = [item for item in peers if isinstance(item, str)]
    elif isinstance(peers, dict) and isinstance(peers.get("peers"), list):
        info["_peers"] = peers["peers"]
    return found


def _sec_user_agent() -> str:
    return os.getenv("SEC_USER_AGENT", "").strip() or "Celesys Research research@celesys.ai"


def _cik_for(symbol: str) -> Optional[str]:
    global _cik_map
    root = classify(symbol)["root"]
    if _cik_map is None:
        payload = _json(_SEC_TICKERS, headers={"User-Agent": _sec_user_agent(), "Accept": "application/json"})
        mapping = {}
        rows = payload.values() if isinstance(payload, dict) else payload if isinstance(payload, list) else []
        for row in rows:
            if isinstance(row, dict) and row.get("ticker") and row.get("cik_str") is not None:
                mapping[str(row["ticker"]).upper()] = int(row["cik_str"])
        _cik_map = mapping
    cik = (_cik_map or {}).get(root)
    return f"{cik:010d}" if cik else None


def _annual_values(facts: dict, concepts: tuple[str, ...]) -> list[float]:
    """Last annual values for a US-GAAP concept, oldest to newest."""
    usgaap = ((facts.get("facts") or {}).get("us-gaap") or {}) if isinstance(facts, dict) else {}
    for concept in concepts:
        node = usgaap.get(concept) or {}
        units = node.get("units") if isinstance(node, dict) else None
        if not isinstance(units, dict):
            continue
        series = units.get("USD") or units.get("USD/shares") or units.get("shares") or []
        annual = [row for row in series if isinstance(row, dict) and row.get("fp") == "FY" and row.get("form") in ("10-K", "10-K/A", "20-F")]
        chosen = annual or [row for row in series if isinstance(row, dict)]
        if not chosen:
            continue
        chosen.sort(key=lambda row: (str(row.get("end") or ""), str(row.get("filed") or "")))
        by_end = {}
        for row in chosen:
            end = str(row.get("end") or "")
            start = str(row.get("start") or "")
            if start and end:
                try:
                    span = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
                except ValueError:
                    span = 365
                if span < 300 or span > 380:
                    continue
            if end:
                by_end[end] = row
        values = [_num(by_end[end].get("val")) for end in sorted(by_end)]
        values = [value for value in values if value is not None]
        if values:
            return values
    return []


def _yoy(values: list[float]) -> Optional[float]:
    if len(values) < 2 or values[-2] == 0:
        return None
    return (values[-1] - values[-2]) / abs(values[-2])


def _latest_fact(facts: dict, concepts: tuple[str, ...]) -> Optional[float]:
    usgaap = ((facts.get("facts") or {}).get("us-gaap") or {}) if isinstance(facts, dict) else {}
    for concept in concepts:
        node = usgaap.get(concept) or {}
        units = node.get("units") if isinstance(node, dict) else None
        if not isinstance(units, dict):
            continue
        series = units.get("USD") or units.get("USD/shares") or units.get("shares") or []
        annual = [row for row in series if isinstance(row, dict) and row.get("fp") == "FY" and row.get("form") in ("10-K", "10-K/A", "20-F")]
        chosen = annual or [row for row in series if isinstance(row, dict)]
        if not chosen:
            continue
        chosen.sort(key=lambda row: str(row.get("end") or ""))
        value = _num(chosen[-1].get("val"))
        if value is not None:
            return value
    return None


def _apply_sec(info: dict, sources: dict, symbol: str, as_of: str) -> None:
    meta = classify(symbol)
    if meta["region"] != "US" or meta["kind"] != "equity":
        return
    need = any(not info.get(field) for field in (
        "grossMargins", "profitMargins", "trailingPE", "returnOnEquity",
        "revenueGrowth", "earningsGrowth", "debtToEquity",
    ))
    if not need:
        return
    cik = _cik_for(symbol)
    if not cik:
        return
    facts = _json(_SEC_FACTS.format(cik=cik), headers={"User-Agent": _sec_user_agent(), "Accept": "application/json"})
    if not isinstance(facts, dict):
        return
    revenue_series = _annual_values(facts, ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "InterestAndDividendIncomeOperating", "InterestIncomeExpenseNet"))
    income_series = _annual_values(facts, ("NetIncomeLoss",))
    revenue = revenue_series[-1] if revenue_series else None
    income = income_series[-1] if income_series else None
    gross = _latest_fact(facts, ("GrossProfit",))
    equity = _latest_fact(facts, ("StockholdersEquity",))
    debt = _latest_fact(facts, ("LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"))
    eps = _latest_fact(facts, ("EarningsPerShareDiluted", "EarningsPerShareBasic"))
    price = _num(info.get("currentPrice") or info.get("regularMarketPrice"))
    rev_yoy = _yoy(revenue_series)
    earn_yoy = _yoy(income_series)
    if rev_yoy is not None:
        _put_metric(info, sources, "revenueGrowth", rev_yoy, "sec", as_of)
    if earn_yoy is not None:
        _put_metric(info, sources, "earningsGrowth", earn_yoy, "sec", as_of)
    if gross is not None and revenue:
        _put_metric(info, sources, "grossMargins", gross / revenue, "sec", as_of)
    if income is not None and revenue:
        _put_metric(info, sources, "profitMargins", income / revenue, "sec", as_of)
    if income is not None and equity:
        _put_metric(info, sources, "returnOnEquity", income / equity, "sec", as_of)
    if debt is not None and equity:
        _put_metric(info, sources, "debtToEquity", debt / equity * 100.0, "sec", as_of)
    if eps and price and eps > 0:
        _put_metric(info, sources, "trailingPE", price / eps, "sec", as_of)
        _put_metric(info, sources, "trailingEps", eps, "sec", as_of)


def _screener_page(symbol: str) -> Optional[str]:
    root = classify(symbol)["root"]
    key = "screener-html:" + root

    def load():
        status, raw = _request(_SCREENER_PAGE.format(symbol=urllib.parse.quote(root)), headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"}, timeout=TIMEOUT)
        if status != 200 or not raw or b"Stock P/E" not in raw and b"company" not in raw:
            return None
        return {"ok": True, "data": raw.decode("utf-8", "replace"), "source": "screener", "as_of": _iso(), "metric_sources": {}}

    env = _remember(key, TTL_FUND, load)
    return env.get("data") if env.get("ok") and isinstance(env.get("data"), str) else None


def _screener_ratios(html: str) -> dict[str, float]:
    # RELIANCE's page is large. A DOTALL scan of the whole document holds the GIL.
    start = html.find('id="top-ratios"')
    if start < 0:
        start = 0
    chunk = html[start:start + 12000]
    pairs = re.findall(r'class="name">\s*([^<]+?)\s*</span>.*?class="number">\s*([^<]+?)\s*</span>', chunk, flags=re.S)
    out = {}
    for name, raw in pairs:
        label = re.sub(r"\s+", " ", name).strip()
        value = _num(raw)
        if label and value is not None:
            out[label] = value
    return out


def _apply_screener_html(info: dict, sources: dict, html: str, as_of: str) -> None:
    ratios = _screener_ratios(html)
    pe = ratios.get("Stock P/E")
    _put_metric(info, sources, "trailingPE", pe, "screener", as_of)
    roe = ratios.get("ROE")
    if roe is not None:
        _put_metric(info, sources, "returnOnEquity", roe / 100.0, "screener", as_of)
    roce = ratios.get("ROCE")
    if roce is not None:
        _put_metric(info, sources, "returnOnAssets", roce / 100.0, "screener", as_of)
    for label, value in ratios.items():
        low = label.lower()
        if "debt" in low and "equity" in low:
            _put_metric(info, sources, "debtToEquity", value, "screener", as_of)
    _put_metric(info, sources, "currentPrice", ratios.get("Current Price"), "screener", as_of)
    _put_metric(info, sources, "bookValue", ratios.get("Book Value"), "screener", as_of)
    dividend = ratios.get("Dividend Yield")
    if dividend is not None:
        _put_metric(info, sources, "dividendYield", dividend / 100.0, "screener", as_of)
    high_low = None
    for label, value in ratios.items():
        if label.lower().startswith("high"):
            _put_metric(info, sources, "fiftyTwoWeekHigh", value, "screener", as_of)
        if label.lower().startswith("low"):
            _put_metric(info, sources, "fiftyTwoWeekLow", value, "screener", as_of)
        if "Market Cap" in label:
            high_low = value
    if high_low is not None:
        # Screener prints market cap in crores. Prefer this over the scanner's India scale.
        info["marketCap"] = high_low * 10_000_000
        sources["marketCap"] = {"source": "screener", "as_of": as_of, "value": info["marketCap"]}
    company = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.S)
    if company and not info.get("longName"):
        name = re.sub(r"<[^>]+>", "", company.group(1))
        name = re.sub(r"\s+", " ", name).strip()
        if name:
            info["longName"] = name
            info["shortName"] = name
            sources["shortName"] = {"source": "screener", "as_of": as_of, "value": name}


def _screener_rows(html: str, section_id: str) -> list[tuple[str, list[float]]]:
    start = html.find(f'id="{section_id}"')
    if start < 0:
        return []
    end = html.find("<section", start + 20)
    chunk = html[start:end if 0 < end - start < 30000 else start + 30000]
    rows = []
    for match in re.finditer(r"<tr[^>]*>(.*?)</tr>", chunk, flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", match.group(1), flags=re.S)
        if len(cells) < 2:
            continue
        label = re.sub(r"<[^>]+>", " ", cells[0])
        label = re.sub(r"&nbsp;", " ", label)
        label = re.sub(r"\s+", " ", label).strip()
        values = []
        for cell in cells[1:]:
            text = re.sub(r"<[^>]+>", " ", cell).replace(",", "").replace("%", "")
            found = re.search(r"[+\-]?\d+(?:\.\d+)?", text)
            values.append(float(found.group()) if found else None)
        if label:
            rows.append((label, [value for value in values if value is not None]))
    return rows


def _last_two_growth(values: list[float]) -> Optional[float]:
    usable = [value for value in values if value is not None]
    if len(usable) < 2 or usable[-2] == 0:
        return None
    return round((usable[-1] - usable[-2]) / abs(usable[-2]) * 100, 1)


def _row_label(label: str) -> str:
    text = label.lower().replace("&nbsp;", " ")
    text = re.sub(r"[^a-z% ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _screener_statement_metrics(html: str) -> dict:
    """Growth and margins from Screener's P&L table, in percent."""
    out = {}
    annual = _screener_rows(html, "profit-loss")
    for label, values in annual:
        low = _row_label(label)
        if low in {"sales", "revenue", "interest earned"} and "revenueGrowth" not in out:
            growth = _last_two_growth(values)
            if growth is not None:
                out["revenueGrowth"] = growth
        if values and (low in {"sales growth", "revenue growth"} or (low.startswith("yoy") and "growth" in low and ("sales" in low or "revenue" in low))):
            out["revenueGrowth"] = round(values[-1], 1)
        if "net profit" in low and "growth" not in low:
            growth = _last_two_growth(values)
            if growth is not None:
                out["earningsGrowth"] = growth
        if values and (low in {"profit growth", "net profit growth"} or (low.startswith("yoy") and "profit" in low)):
            out["earningsGrowth"] = round(values[-1], 1)
        if low.startswith("opm") and values:
            out["operatingMargin"] = round(values[-1], 1)
        if "financing margin" in low:
            out["financial"] = True
            # A bank NIM sits around 2-5%. Screener's financing-margin row is a
            # different ratio and turns negative after some mergers, so only a
            # value in that band is kept.
            if values and 1 <= values[-1] <= 8:
                out["nim"] = round(values[-1], 1)
        if low in {"gross margin", "gross margin %"} and values:
            out["grossMargin"] = round(values[-1], 1)
    borrow = equity = reserves = None
    for label, values in _screener_rows(html, "balance-sheet"):
        low = _row_label(label)
        if not values:
            continue
        if low.startswith("borrowing"):
            borrow = values[-1]
        elif low.startswith("equity capital"):
            equity = values[-1]
        elif low.startswith("reserve"):
            reserves = values[-1]
    base = (equity or 0) + (reserves or 0)
    if borrow is not None and base:
        out["debtToEquity"] = round(borrow / base * 100.0, 1)
    return out


def screener_decide_from_html(html: str) -> dict:
    """Book value and the annual profit series from one Screener page.

    The page is already cached for fundamentals. Decide uses this so a
    one-year dip is not treated as the whole earnings history, and so a
    missing gross margin on a bank is not a missing series.
    """
    if not html:
        return {}
    ratios = _screener_ratios(html)
    sector_match = re.search(r'title="Broad Sector">([^<]+)', html)
    sector = re.sub(r"\s+", " ", sector_match.group(1)).strip() if sector_match else ""
    sales = profit = operating = None
    for label, values in _screener_rows(html, "profit-loss"):
        low = _row_label(label)
        if sales is None and low in {"sales", "revenue"}:
            sales = values
        elif profit is None and "net profit" in low and "growth" not in low:
            profit = values
        elif operating is None and low.startswith("opm") and values and values[-1] > 0:
            operating = values
    sales = sales or []
    profit = profit or []
    count = max(len(sales), len(profit))
    history = []
    for index in range(count):
        revenue = sales[index] if index < len(sales) else 0
        earnings = profit[index] if index < len(profit) else 0
        if operating and index < len(operating) and operating[index] > 0:
            margin = operating[index]
        elif revenue:
            margin = round(earnings / revenue * 100, 1)
        else:
            margin = 0
        if revenue or earnings:
            history.append({
                "year": str(index + 1),
                "revenue": revenue,
                "profit": earnings,
                "margin": round(margin, 1) if margin else 0,
                "fcf": 0,
                "roe": 0,
            })
    cagr = None
    if len(history) >= 4 and history[0]["profit"] > 0 and history[-1]["profit"] > 0:
        years = len(history) - 1
        cagr = round((history[-1]["profit"] / history[0]["profit"]) ** (1 / years) - 1, 4) * 100
        cagr = round(cagr, 1)
    latest_revenue = history[-1]["revenue"] if history else 0
    latest_profit = history[-1]["profit"] if history else 0
    net_margin = round(latest_profit / latest_revenue * 100, 1) if latest_revenue else None
    return {
        "bookValue": ratios.get("Book Value"),
        "sector": sector,
        "profitCagr": cagr,
        "profitMargin": net_margin,
        "dividendYield": ratios.get("Dividend Yield"),
        "annualHistory": history,
    }


def screener_decide_pack(symbol: str) -> dict:
    """Decide inputs from the Screener page cached by the fundamentals read."""
    return screener_decide_from_html(_screener_page(symbol) or "")


def _apply_screener_statements(info: dict, sources: dict, html: str, as_of: str) -> None:
    metrics = _screener_statement_metrics(html)
    if metrics.get("revenueGrowth") is not None:
        _put_metric(info, sources, "revenueGrowth", metrics["revenueGrowth"] / 100.0, "screener", as_of)
    if metrics.get("earningsGrowth") is not None:
        _put_metric(info, sources, "earningsGrowth", metrics["earningsGrowth"] / 100.0, "screener", as_of)
    if metrics.get("operatingMargin") is not None:
        _put_metric(info, sources, "operatingMargins", metrics["operatingMargin"] / 100.0, "screener", as_of)
    if metrics.get("grossMargin") is not None:
        _put_metric(info, sources, "grossMargins", metrics["grossMargin"] / 100.0, "screener", as_of)
    if metrics.get("debtToEquity") is not None:
        _put_metric(info, sources, "debtToEquity", metrics["debtToEquity"], "screener", as_of)
    if metrics.get("nim") is not None:
        info["nim"] = metrics["nim"]
        sources["nim"] = {"source": "screener", "as_of": as_of, "value": metrics["nim"]}
    if metrics.get("financial"):
        info["financial"] = True


def _apply_screener(info: dict, sources: dict, symbol: str, as_of: str) -> None:
    if classify(symbol)["region"] != "IN" or classify(symbol)["kind"] != "equity":
        return
    html = _screener_page(symbol)
    if html:
        _apply_screener_html(info, sources, html, as_of)


def _angel_configured() -> bool:
    try:
        import angel_session
        return bool(angel_session.login_configured() or os.getenv("CELESYS_ANGEL_JWT_TOKEN", "").strip())
    except Exception:
        return False


def _angel_token(symbol: str) -> Optional[str]:
    """Best-effort NSE token. Skips the instrument master unless Angel is configured."""
    if not _angel_configured():
        return None
    meta = classify(symbol)
    if meta["region"] != "IN":
        return None
    root = meta["root"]
    key = "angel-token:" + root

    def load():
        try:
            import angel_options
            book = angel_options._load_nse_book(time.time())
        except Exception:
            return None
        token = book.get(root, {}).get("token") if isinstance(book, dict) else None
        if not token:
            return None
        return {"ok": True, "data": str(token), "source": "angel", "as_of": _iso(), "metric_sources": {}}

    env = _remember(key, TTL_FUND, load)
    data = env.get("data") if env.get("ok") else None
    return str(data) if data else None


def _angel_headers() -> Optional[dict]:
    try:
        import angel_options
        if not angel_options.configured():
            return None
        return angel_options._headers()
    except Exception:
        return None


def _quote_from_tv_fields(symbol: str, fields: dict, price: float) -> dict:
    change = _num(fields.get("change_abs"))
    prev = price - change if change is not None else price
    pct = ((price - prev) / prev * 100.0) if prev else _num(fields.get("change"))
    return {
        "symbol": symbol,
        "price": price,
        "prev_close": prev,
        "change_pct": round(pct, 2) if pct is not None else 0,
        "name": fields.get("description") or symbol,
        "pe": _num(fields.get("price_earnings_ttm")) or 0,
        "mcap": _num(fields.get("market_cap_basic")) or 0,
        "roe": _num(fields.get("return_on_equity")) or 0,
        "volume": _num(fields.get("volume")) or 0,
        "high52": _num(fields.get("price_52_week_high")) or 0,
        "low52": _num(fields.get("price_52_week_low")) or 0,
        "as_of": _quote_time_text(fields.get("last_bar_update_time")),
    }


def _quote_time_text(raw) -> Optional[str]:
    """Exchange clock from the scanner. Missing or unreadable stays missing."""
    try:
        moment = datetime.fromtimestamp(float(raw), timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    return moment.isoformat()


def _parse_quote_time(text) -> Optional[datetime]:
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def quote_batch_clock(book: dict) -> dict:
    """Newest exchange time in a quote batch. Empty or old batches are a refusal."""
    newest = None
    priced = 0
    for row in (book or {}).values():
        if not isinstance(row, dict) or not row.get("price"):
            continue
        priced += 1
        moment = _parse_quote_time(row.get("as_of"))
        if moment and (newest is None or moment > newest):
            newest = moment
    if priced == 0 or newest is None:
        return {"ok": False, "as_of": None, "error": "No current quote. Refusing to serve a saved snapshot."}
    age = (datetime.now(timezone.utc) - newest).total_seconds()
    day = newest.date().isoformat()
    if age > QUOTE_MAX_AGE:
        return {
            "ok": False,
            "as_of": day,
            "error": "Quotes are from %s, %d days old. Refusing to serve them." % (day, int(age // 86400)),
        }
    return {"ok": True, "as_of": day, "error": None}


def quote_date_ok(text) -> bool:
    moment = _parse_quote_time(str(text)[:10] if text else None)
    if moment is None:
        return False
    return (datetime.now(timezone.utc) - moment).total_seconds() <= QUOTE_MAX_AGE


def scan_quotes(symbols: list, region: Optional[str] = None) -> dict[str, dict]:
    """Prices for a scan. One scanner request per chunk, never the candle chain.

    Two requests run at a time on a pool the home strip does not use.
    """
    ordered: list[tuple[str, str]] = []
    seen = set()
    for symbol in symbols or []:
        text = str(symbol or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        for tv in classify(text, region).get("tv") or []:
            if tv:
                ordered.append((text, tv))
    if not ordered:
        return {}
    chunks = [ordered[index:index + 40] for index in range(0, len(ordered), 40)]

    def one(chunk: list[tuple[str, str]]) -> dict[str, dict]:
        if not _scan_slots.acquire(timeout=0.4):
            return {}
        try:
            body = json.dumps({
                "symbols": {"tickers": [tv for _symbol, tv in chunk]},
                "columns": _TV_COLUMNS,
            }).encode()
            payload = _json(
                _TV,
                data=body,
                headers={"Content-Type": "application/json", "Origin": "https://www.tradingview.com"},
                timeout=3,
                retries=0,
            )
            rows = payload.get("data") if isinstance(payload, dict) else None
            by_tv = {}
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    values = row.get("d")
                    if not isinstance(values, list) or len(values) < 5:
                        continue
                    fields = dict(zip(_TV_COLUMNS, values))
                    price = _num(fields.get("close"))
                    if price and price > 0:
                        by_tv[row.get("s")] = fields | {"_price": price}
            found = {}
            for symbol, tv in chunk:
                if symbol in found:
                    continue
                fields = by_tv.get(tv)
                if not fields:
                    continue
                found[symbol] = _quote_from_tv_fields(symbol, fields, fields["_price"])
            return found
        finally:
            _scan_slots.release()

    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as _FuturesTimeout
    found: dict[str, dict] = {}
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        jobs = [pool.submit(one, chunk) for chunk in chunks]
        try:
            for job in as_completed(jobs, timeout=4):
                try:
                    for symbol, row in job.result().items():
                        found.setdefault(symbol, row)
                except Exception:
                    pass
        except _FuturesTimeout:
            pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return found


def quote(symbol: str, region: Optional[str] = None) -> dict:
    meta = classify(symbol, region)
    key = f"quote:{meta['region']}:{meta['root']}"

    def load():
        as_of = _iso()
        if meta["region"] == "IN" and (meta["kind"] == "equity" or meta["root"] in {"NIFTY", "BANKNIFTY"}):
            token = _angel_token(symbol)
            headers = _angel_headers()
            if token and headers:
                tradingsymbol = "Nifty 50" if meta["root"] == "NIFTY" else "Nifty Bank" if meta["root"] == "BANKNIFTY" else meta["root"] + "-EQ"
                payload = _json(
                    _ANGEL_LTP,
                    data=json.dumps({"exchange": "NSE", "tradingsymbol": tradingsymbol, "symboltoken": token}).encode(),
                    headers=headers,
                )
                data = payload.get("data") if isinstance(payload, dict) else None
                price = _num((data or {}).get("ltp") if isinstance(data, dict) else None)
                if price and price > 0:
                    close = _num(data.get("close")) if isinstance(data, dict) else None
                    change_pct = None
                    if close and close > 0 and abs(close - price) / price > 0.0001:
                        change_pct = (price - close) / close * 100.0
                    return {
                        "ok": True,
                        "data": {
                            "price": price,
                            "prev_close": close or price,
                            "change_pct": change_pct,
                            "currency": "INR",
                            "symbol": meta["root"],
                        },
                        "source": "angel",
                        "as_of": as_of,
                        "stale": False,
                        "metric_sources": {"price": {"source": "angel", "as_of": as_of, "value": price}},
                    }
        row = _tv_row(symbol, meta["region"])
        if not row:
            fh = _finnhub("/quote", {"symbol": meta["root"]}) if meta["finnhub"] else None
            price = _num((fh or {}).get("c")) if isinstance(fh, dict) else None
            if not price or price <= 0:
                return None
            prev = _num(fh.get("pc")) or price
            return {
                "ok": True,
                "data": {"price": price, "prev_close": prev, "currency": meta["currency"], "symbol": meta["root"]},
                "source": "finnhub",
                "as_of": as_of,
                "stale": False,
                "metric_sources": {"price": {"source": "finnhub", "as_of": as_of, "value": price}},
            }
        fields = row["fields"]
        change = _num(fields.get("change_abs"))
        price = row["price"]
        prev = price - change if change is not None else price
        source = "finnhub" if meta["finnhub"] and os.getenv("FINNHUB_API_KEY", "").strip() else "tradingview"
        if source == "finnhub":
            fh = _finnhub("/quote", {"symbol": meta["root"]})
            fh_price = _num((fh or {}).get("c")) if isinstance(fh, dict) else None
            if fh_price and fh_price > 0:
                price = fh_price
                prev = _num(fh.get("pc")) or prev
            else:
                source = "tradingview"
        return {
            "ok": True,
            "data": {
                "price": price,
                "prev_close": prev,
                "change": price - prev if prev else None,
                "change_pct": ((price - prev) / prev * 100) if prev else _num(fields.get("change")),
                "volume": _num(fields.get("volume")),
                "currency": fields.get("currency") or meta["currency"],
                "name": fields.get("description") or meta["root"],
                "symbol": meta["root"],
                "tv_symbol": row.get("tv_symbol"),
            },
            "source": source,
            "as_of": as_of,
            "stale": False,
            "metric_sources": {"price": {"source": source, "as_of": as_of, "value": price}},
        }

    return _remember(key, TTL_QUOTE, load)


def _bars_from_pairs(pairs: list[tuple], source: str) -> Optional[dict]:
    bars = []
    for item in pairs:
        if len(item) < 5:
            continue
        moment, open_, high, low, close = item[:5]
        volume = item[5] if len(item) > 5 else 0
        close_n = _num(close)
        if close_n is None or close_n <= 0:
            continue
        bars.append({
            "time": moment,
            "open": _num(open_) or close_n,
            "high": _num(high) or close_n,
            "low": _num(low) or close_n,
            "close": close_n,
            "volume": _num(volume) or 0,
        })
    if not bars:
        return None
    bars.sort(key=lambda row: row["time"])
    return {"ok": True, "data": bars, "source": source, "as_of": _iso(), "stale": False, "metric_sources": {"close": {"source": source, "as_of": _iso()}}}


def _nasdaq_bars(symbol: str) -> Optional[dict]:
    meta = classify(symbol)
    if meta["region"] != "US" or meta["kind"] != "equity":
        return None
    start = (datetime.now(timezone.utc) - timedelta(days=420)).date().isoformat()
    url = _NASDAQ.format(symbol=urllib.parse.quote(meta["root"])) + "?" + urllib.parse.urlencode({
        "assetclass": "stocks", "fromdate": start, "limit": "500",
    })
    status = None
    try:
        status, raw = _request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/",
        }, timeout=CANDLE_TIMEOUT, retries=0)
        payload = json.loads(raw.decode("utf-8", "replace")) if status == 200 and raw else None
    except Exception as exc:
        print(f"  candle {meta['root']}: nasdaq request failed ({type(exc).__name__})")
        return None
    if not isinstance(payload, dict):
        print(f"  candle {meta['root']}: nasdaq HTTP {status}")
        return None
    table = ((payload or {}).get("data") or {}).get("tradesTable") if isinstance(payload, dict) else None
    rows = (table or {}).get("rows") if isinstance(table, dict) else None
    if not isinstance(rows, list):
        return None
    pairs = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            moment = datetime.strptime(row.get("date") or "", "%m/%d/%Y").date().isoformat()
        except ValueError:
            continue
        pairs.append((moment, row.get("open"), row.get("high"), row.get("low"), row.get("close"), row.get("volume")))
    return _bars_from_pairs(pairs, "nasdaq")


def _stooq_bars(symbol: str) -> Optional[dict]:
    """Daily bars from Stooq. Used when Nasdaq and TradingView both miss."""
    meta = classify(symbol)
    if meta["region"] != "US" or meta["kind"] != "equity":
        return None
    url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(meta['root'].lower())}.us&i=d"
    try:
        status, raw = _request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/csv"}, timeout=CANDLE_TIMEOUT, retries=0)
    except Exception as exc:
        print(f"  candle {meta['root']}: stooq request failed ({type(exc).__name__})")
        return None
    if status != 200 or not raw or raw[:1] == b"<":
        print(f"  candle {meta['root']}: stooq HTTP {status}")
        return None
    pairs = []
    for line in raw.decode("utf-8", "replace").splitlines()[1:]:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 5 or parts[0].lower() == "date":
            continue
        pairs.append((parts[0], parts[1], parts[2], parts[3], parts[4], parts[5] if len(parts) > 5 else 0))
    return _bars_from_pairs(pairs[-400:], "stooq")


def _finnhub_bars(symbol: str, interval: str) -> Optional[dict]:
    meta = classify(symbol)
    if not meta["finnhub"]:
        return None
    resolution = {"1d": "D", "1wk": "W", "60m": "60", "15m": "15", "5m": "5", "1m": "1"}.get(interval, "D")
    days = 10 if resolution in {"1", "5", "15", "60"} else 420
    end = int(_now())
    start = end - days * 86400
    payload = _finnhub("/stock/candle", {"symbol": meta["root"], "resolution": resolution, "from": start, "to": end}, timeout=CANDLE_TIMEOUT, retries=0)
    if not isinstance(payload, dict) or payload.get("s") != "ok":
        reason = payload.get("s") or payload.get("error") if isinstance(payload, dict) else "no response"
        print(f"  candle {meta['root']}: finnhub {reason}")
        return None
    stamps = payload.get("t") or []
    opens = payload.get("o") or []
    highs = payload.get("h") or []
    lows = payload.get("l") or []
    closes = payload.get("c") or []
    volumes = payload.get("v") or []
    pairs = []
    for index, stamp in enumerate(stamps):
        if index >= len(closes):
            break
        moment = datetime.fromtimestamp(int(stamp), timezone.utc).isoformat()
        pairs.append((
            moment,
            opens[index] if index < len(opens) else None,
            highs[index] if index < len(highs) else None,
            lows[index] if index < len(lows) else None,
            closes[index],
            volumes[index] if index < len(volumes) else 0,
        ))
    return _bars_from_pairs(pairs, "finnhub")


def _screener_html_quick(symbol: str) -> Optional[str]:
    """Candle-path page fetch. Five seconds, no retry, and the fundamentals cache when it is warm."""
    root = classify(symbol)["root"]
    cached = _cache_get("screener-html:" + root, TTL_FUND)
    if cached and isinstance(cached.get("data"), str):
        return cached["data"]
    try:
        status, raw = _request(
            _SCREENER_PAGE.format(symbol=urllib.parse.quote(root)),
            headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"},
            timeout=CANDLE_TIMEOUT,
            retries=0,
        )
    except Exception:
        return None
    if status != 200 or not raw:
        return None
    html = raw.decode("utf-8", "replace")
    _cache_put("screener-html:" + root, {"ok": True, "data": html, "source": "screener", "as_of": _iso(), "metric_sources": {}})
    return html


def _screener_bars(symbol: str) -> Optional[dict]:
    meta = classify(symbol)
    if meta["region"] != "IN" or meta["kind"] != "equity":
        return None
    html = _screener_html_quick(symbol)
    if not html:
        return None
    match = re.search(r"/api/company/(\d+)/", html)
    if not match:
        return None
    payload = _json(
        _SCREENER_CHART.format(cid=match.group(1)),
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.screener.in/"},
        timeout=CANDLE_TIMEOUT,
        retries=0,
    )
    datasets = payload.get("datasets") if isinstance(payload, dict) else None
    if not isinstance(datasets, list):
        return None
    prices = []
    volumes = {}
    for dataset in datasets:
        if not isinstance(dataset, dict):
            continue
        label = (dataset.get("metric") or dataset.get("label") or "").lower()
        values = dataset.get("values") or []
        if "price" in label and not prices:
            prices = values
        elif "volume" in label:
            volumes = {row[0]: row[1] for row in values if isinstance(row, list) and len(row) >= 2}
    pairs = []
    for row in prices:
        if not isinstance(row, list) or len(row) < 2:
            continue
        pairs.append((row[0], row[1], row[1], row[1], row[1], volumes.get(row[0], 0)))
    return _bars_from_pairs(pairs, "screener")


def _moneycontrol_index_bars(symbol: str) -> Optional[dict]:
    meta = classify(symbol)
    ind = _MC_INDEX.get(meta["root"]) or _MC_INDEX.get(meta["raw"])
    if not ind:
        return None
    payload = _json(
        _MC_INDEX_URL.format(ind=ind),
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.moneycontrol.com/"},
        timeout=CANDLE_TIMEOUT,
        retries=0,
    )
    values = ((payload or {}).get("graph") or {}).get("values") if isinstance(payload, dict) else None
    if not isinstance(values, list):
        return None
    pairs = []
    for row in values:
        if not isinstance(row, dict):
            continue
        label = row.get("_time") or ""
        try:
            moment = datetime.strptime(label, "%d %b %Y").date().isoformat()
        except ValueError:
            continue
        pairs.append((moment, row.get("_open"), row.get("_high"), row.get("_low"), row.get("_close") or row.get("_value"), row.get("_volume")))
    return _bars_from_pairs(pairs, "moneycontrol")


def _angel_bars(symbol: str, interval: str) -> Optional[dict]:
    """Historical candles through the Angel proxy. A direct call from Render is rejected."""
    try:
        import angel_options
        import angel_session
        if not angel_options.configured():
            return None
        key = angel_options._nse_key(symbol)
        if not key:
            return None
        # The instrument master is large. A cold download must not hold Screener or TradingView.
        book = getattr(angel_options, "_nse_book", None)
        if not isinstance(book, dict):
            threading.Thread(target=lambda: angel_options._load_nse_book(time.time()), name="angel-book", daemon=True).start()
            return None
        inst = book.get(key) if isinstance(book, dict) else None
        token = inst.get("token") if isinstance(inst, dict) else None
        if not token:
            return None
        headers = angel_options._headers()
    except Exception:
        return None
    interval_name = {"1d": "ONE_DAY", "5m": "FIVE_MINUTE", "15m": "FIFTEEN_MINUTE", "60m": "ONE_HOUR", "1m": "ONE_MINUTE"}.get(interval, "ONE_DAY")
    end = datetime.now().strftime("%Y-%m-%d %H:%M")
    start = (datetime.now() - timedelta(days=10 if interval != "1d" else 400)).strftime("%Y-%m-%d %H:%M")
    try:
        payload = angel_session.request_json(
            _ANGEL_CANDLE,
            payload={"exchange": "NSE", "symboltoken": str(token), "interval": interval_name, "fromdate": start, "todate": end},
            headers=headers,
            timeout=ANGEL_CANDLE_TIMEOUT,
        )
    except Exception:
        return None
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return None
    pairs = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 5:
            continue
        pairs.append((row[0], row[1], row[2], row[3], row[4], row[5] if len(row) > 5 else 0))
    return _bars_from_pairs(pairs, "angel")


def _try_bars(loader) -> tuple:
    """One candle provider cannot cancel the next. Returns bars and a short failure reason."""
    try:
        bars = loader()
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"[:160]
    if isinstance(bars, dict) and bars.get("ok") and isinstance(bars.get("data"), list) and bars["data"]:
        return bars, None
    return None, "no bars"


def _within(loader, seconds: float) -> tuple:
    """Give one candle step a hard stop. The socket keeps its own timeout too."""
    box: dict[str, Any] = {}

    def run():
        box["value"] = _try_bars(loader)

    thread = threading.Thread(target=run, name="candle-step", daemon=True)
    thread.start()
    thread.join(max(0.1, seconds))
    if "value" not in box:
        return None, "timeout"
    return box["value"]


def _run_chain(symbol: str, steps: list, budget: Optional[float] = None) -> Optional[dict]:
    """Try every source. A timeout or a fast failure cannot skip the rest.

    When budget is set, a later source does not start after the clock runs out.
    """
    deadline = time.perf_counter() + budget if budget else None
    for name, step in steps:
        if deadline is not None and time.perf_counter() >= deadline:
            print(f"  candle {symbol}: budget spent before {name}")
            break
        limit = CANDLE_TIMEOUT
        if deadline is not None:
            limit = min(CANDLE_TIMEOUT, max(0.2, deadline - time.perf_counter()))
        started = time.perf_counter()
        bars, reason = _within(step, limit)
        elapsed = time.perf_counter() - started
        if bars:
            print(f"  candle {symbol}: {name} ok {len(bars['data'])} bars in {elapsed:.2f}s")
            return bars
        print(f"  candle {symbol}: {name} failed in {elapsed:.2f}s ({reason})")
    return None


def _ws_send(sock, text: str) -> None:
    payload = text.encode()
    mask = os.urandom(4)
    size = len(payload)
    header = bytearray([0x81])
    if size < 126:
        header.append(0x80 | size)
    elif size < 65536:
        header.append(0x80 | 126)
        header += struct.pack("!H", size)
    else:
        header.append(0x80 | 127)
        header += struct.pack("!Q", size)
    header += mask
    sock.sendall(bytes(header) + bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload)))


def _ws_recv(sock) -> str:
    def exact(count: int) -> bytes:
        buf = b""
        while len(buf) < count:
            chunk = sock.recv(count - len(buf))
            if not chunk:
                raise ConnectionError("closed")
            buf += chunk
        return buf

    parts = []
    while True:
        first, second = exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", exact(8))[0]
        if second & 0x80:
            mask = exact(4)
            data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(exact(length)))
        else:
            data = exact(length)
        if opcode == 0x8:
            raise ConnectionError("closed")
        if opcode == 0x9:
            continue
        if opcode in (0x1, 0x0):
            parts.append(data)
            if first & 0x80:
                return b"".join(parts).decode("utf-8", "replace")
            continue
        if first & 0x80:
            return ""


def _tv_connect(timeout: float):
    host = "data.tradingview.com"
    key = base64.b64encode(os.urandom(16)).decode()
    raw = socket.create_connection((host, 443), timeout=timeout)
    sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
    sock.settimeout(timeout)
    request = (
        "GET /socket.io/websocket?from=chart%2F&type=chart HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Origin: https://www.tradingview.com\r\n"
        "User-Agent: Mozilla/5.0\r\n"
        "\r\n"
    )
    sock.sendall(request.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
    status = buf.split(b"\r\n", 1)[0]
    if b" 101 " not in status:
        sock.close()
        raise ConnectionError("TradingView handshake failed")
    return sock


def _tv_packets(blob: str) -> list:
    out = []
    cursor = 0
    while True:
        mark = blob.find("~m~", cursor)
        if mark < 0:
            break
        start = mark + 3
        end = blob.find("~m~", start)
        if end < 0:
            break
        try:
            length = int(blob[start:end])
        except ValueError:
            break
        body_at = end + 3
        body = blob[body_at:body_at + length]
        cursor = body_at + length
        if body.startswith("~h~"):
            out.append({"_heartbeat": body})
            continue
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def _tv_wrap(payload: dict) -> str:
    message = json.dumps(payload, separators=(",", ":"))
    return f"~m~{len(message)}~m~{message}"


def _tv_symbol_bars(tv_symbol: str, resolution: str, count: int, timeout: float) -> list:
    """One TradingView chart session. Returns (time, o, h, l, c, v) rows or []."""
    sock = _tv_connect(max(0.5, timeout))
    try:
        _ws_recv(sock)
        session = "cs_" + os.urandom(3).hex()
        spec = json.dumps({"symbol": tv_symbol, "adjustment": "splits"}, separators=(",", ":"))
        for payload in (
            {"m": "set_auth_token", "p": ["unauthorized_user_token"]},
            {"m": "chart_create_session", "p": [session, ""]},
            {"m": "resolve_symbol", "p": [session, "sds_sym_1", "=" + spec]},
            {"m": "create_series", "p": [session, "s1", "s1", "sds_sym_1", resolution, count, ""]},
        ):
            _ws_send(sock, _tv_wrap(payload))
        deadline = time.time() + timeout
        while time.time() < deadline:
            sock.settimeout(max(0.2, deadline - time.time()))
            text = _ws_recv(sock)
            if text.startswith("~h~") and "~m~" not in text:
                _ws_send(sock, text)
                continue
            for packet in _tv_packets(text):
                beat = packet.get("_heartbeat")
                if beat:
                    _ws_send(sock, f"~m~{len(beat)}~m~{beat}")
                    continue
                if packet.get("m") == "timescale_update":
                    node = (packet.get("p") or [None, {}])[1] or {}
                    rows = ((node.get("s1") or {}).get("s")) or []
                    pairs = []
                    for row in rows:
                        values = row.get("v") if isinstance(row, dict) else None
                        if not isinstance(values, list) or len(values) < 5:
                            continue
                        moment = datetime.fromtimestamp(float(values[0]), timezone.utc).isoformat()
                        volume = values[5] if len(values) > 5 else 0
                        pairs.append((moment, values[1], values[2], values[3], values[4], volume))
                    if pairs:
                        return pairs
                if packet.get("m") in {"series_error", "symbol_error"}:
                    return []
        return []
    finally:
        try:
            sock.close()
        except Exception:
            pass


_tv_slots = threading.Semaphore(2)


def _tradingview_bars(symbol: str, interval: str = "1d") -> Optional[dict]:
    meta = classify(symbol)
    if not _tv_slots.acquire(timeout=1):
        print(f"  candle {meta['root']}: tradingview busy")
        return None
    try:
        return _tradingview_bars_unlocked(symbol, interval, meta)
    finally:
        _tv_slots.release()


def _tradingview_bars_unlocked(symbol: str, interval: str, meta: dict) -> Optional[dict]:
    resolution = {"1d": "D", "1wk": "W", "60m": "60", "15m": "15", "5m": "5", "1m": "1"}.get(interval, "D")
    count = 120 if resolution in {"1", "5", "15", "60"} else 400
    deadline = time.time() + CANDLE_TIMEOUT
    for tv_symbol in meta["tv"][:4]:
        left = deadline - time.time()
        if left < 0.4:
            break
        try:
            pairs = _tv_symbol_bars(tv_symbol, resolution, count, min(left, 4))
        except Exception:
            pairs = []
        bars = _bars_from_pairs(pairs, "tradingview") if pairs else None
        if bars:
            return bars
    return None


def _candle_steps(symbol: str, meta: dict, interval_name: str) -> list:
    intraday = interval_name in {"5m", "1m", "15m", "60m"}
    fetch_interval = interval_name if intraday else "1d"
    if meta["region"] == "IN":
        # Angel first, and only Angel uses the proxy. Screener, TradingView and the Nifty graph follow.
        steps = [("angel", lambda interval=fetch_interval: _angel_bars(symbol, interval))]
        if not intraday:
            steps.append(("screener", lambda: _screener_bars(symbol)))
        steps.append(("tradingview", lambda interval=fetch_interval: _tradingview_bars(symbol, interval)))
        if not intraday:
            steps.append(("nifty", lambda: _moneycontrol_index_bars(symbol)))
        return steps
    # TradingView is the source that actually returns bars from this host.
    # Finnhub's candle call is often empty on the current plan, and Nasdaq
    # rejects a bare request, so those follow instead of going first.
    steps = [("tradingview", lambda interval=fetch_interval: _tradingview_bars(symbol, interval))]
    if not intraday and meta["kind"] == "equity":
        steps.append(("nasdaq", lambda: _nasdaq_bars(symbol)))
        steps.append(("stooq", lambda: _stooq_bars(symbol)))
    steps.append(("finnhub", lambda interval=fetch_interval: _finnhub_bars(symbol, interval)))
    return steps


_candle_inflight = 0
_candle_inflight_lock = threading.Lock()
_scan_slots = threading.Semaphore(2)


def candles(symbol: str, period: str = "1y", interval: str = "1d", region: Optional[str] = None, retry: bool = True, budget: Optional[float] = None) -> dict:
    meta = classify(symbol, region)
    interval_name = "60m" if interval in {"60m", "1h"} else (interval or "1d")
    # Period does not change the fetch window, so 3mo and 1y share one cache entry.
    key = f"candles:{meta['region']}:{meta['root']}:{interval_name}"
    del period

    def load():
        global _candle_inflight
        with _candle_inflight_lock:
            _candle_inflight += 1
            crowded = _candle_inflight > 2
        try:
            steps = _candle_steps(symbol, meta, interval_name)
            bars = _run_chain(meta["root"], steps, budget)
            if bars or not retry or crowded or budget:
                if not bars and (not retry or crowded or budget):
                    print(f"  candle {meta['root']}: no chain retry")
                return bars
            print(f"  candle {meta['root']}: no source returned bars, retrying the chain once")
            time.sleep(0.25)
            return _run_chain(meta["root"], steps, budget)
        finally:
            with _candle_inflight_lock:
                _candle_inflight -= 1

    env = _remember(key, TTL_CANDLE, load)
    if env.get("ok") and isinstance(env.get("data"), list):
        env["metric_sources"] = {"close": {"source": env.get("source"), "as_of": env.get("as_of"), "stale": bool(env.get("stale"))}}
    return env


def fundamentals(symbol: str, region: Optional[str] = None) -> dict:
    meta = classify(symbol, region)
    key = f"fund:{meta['region']}:{meta['root']}"

    def load():
        as_of = _iso()
        info: dict[str, Any] = {"symbol": meta["root"], "currency": meta["currency"], "quoteType": "EQUITY" if meta["kind"] == "equity" else "INDEX"}
        sources: dict[str, dict] = {}
        # Finnhub's own calls are concurrent. TradingView and Screener run beside that fetch.
        with ThreadPoolExecutor(max_workers=2) as pool:
            tv_future = pool.submit(_tv_row, symbol, meta["region"])
            screen_future = pool.submit(_screener_page, symbol) if meta["region"] == "IN" and meta["kind"] == "equity" else None
            if meta["finnhub"]:
                try:
                    _apply_finnhub(info, sources, symbol, as_of)
                except Exception:
                    pass
            try:
                row = tv_future.result()
            except Exception:
                row = None
            html = None
            if screen_future:
                try:
                    html = screen_future.result()
                except Exception:
                    html = None
        if row:
            _apply_tv_fundamentals(info, sources, row, as_of)
        if html:
            _apply_screener_html(info, sources, html, as_of)
            try:
                _apply_screener_statements(info, sources, html, as_of)
            except Exception:
                pass
        try:
            _apply_sec(info, sources, symbol, as_of)
        except Exception:
            pass
        if not (info.get("currentPrice") or info.get("regularMarketPrice") or info.get("trailingPE")):
            return None
        primary = "finnhub" if any(item.get("source") == "finnhub" for item in sources.values()) else (
            "screener" if any(item.get("source") == "screener" for item in sources.values()) else "tradingview"
        )
        info["_metric_sources"] = sources
        info["_source"] = primary
        return {"ok": True, "data": info, "source": primary, "as_of": as_of, "stale": False, "metric_sources": sources}

    return _remember(key, TTL_FUND, load)


def _as_percent(value) -> Optional[float]:
    """Layer ratios are decimals: 0.15 is 15 percent, and 2.5 is 250 percent."""
    number = _num(value)
    if number is None:
        return None
    return round(number * 100.0, 1)


def is_financial(symbol: str, info: Optional[dict] = None) -> bool:
    """Banks and other lenders do not publish a product gross margin."""
    info = info or {}
    root = classify(symbol)["root"]
    if root in FINANCIALS or info.get("financial") or info.get("nim") is not None:
        return True
    blob = " ".join(str(info.get(key) or "") for key in ("sector", "industry", "longName", "shortName")).lower()
    return any(word in blob for word in ("bank", "financial", "nbfc", "lender", "insurance"))


def investor_fundamentals(symbol: str, region: Optional[str] = None) -> dict:
    """Margins, growth, PE, ROE and debt for the Decide page.

    Percent fields are already in percent. A bank returns NIM, ROA and ROE
    instead of a product gross margin. A failed load is not cached.
    """
    meta = classify(symbol, region)
    env = fundamentals(symbol, region)
    info = env.get("data") if isinstance(env, dict) else None
    if not isinstance(info, dict):
        return {"ok": False, "symbol": meta["root"], "region": meta["region"], "financial": meta["root"] in FINANCIALS}
    financial = is_financial(symbol, info)
    gross = _as_percent(info.get("grossMargins"))
    roa = _as_percent(info.get("returnOnAssets"))
    roe = _as_percent(info.get("returnOnEquity"))
    nim = _num(info.get("nim"))
    if nim is not None:
        nim = round(nim, 1)
    if financial:
        # Bank ROA is only a couple of percent. A larger figure is a ROCE that
        # was stored in the same field, so the verdict uses ROE instead.
        if nim is not None:
            quality = nim
        elif roa is not None and roa < 4:
            quality = roa
        else:
            quality = roe
    else:
        quality = gross
    return {
        "ok": True,
        "symbol": meta["root"],
        "region": meta["region"],
        "source": env.get("source"),
        "as_of": env.get("as_of"),
        "financial": financial,
        "grossMargin": gross,
        "operatingMargin": _as_percent(info.get("operatingMargins")),
        "profitMargin": _as_percent(info.get("profitMargins")),
        "revenueGrowth": _as_percent(info.get("revenueGrowth")),
        "earningsGrowth": _as_percent(info.get("earningsGrowth")),
        "pe": _num(info.get("trailingPE")),
        "roe": roe,
        "roa": roa,
        "debt": _num(info.get("debtToEquity")),
        "nim": nim,
        "quality": quality,
        "marketCap": _num(info.get("marketCap")),
    }


_HOME_STRIP = (
    ("NIFTY", "NIFTY", "IN"),
    ("SENSEX", "SENSEX", "IN"),
    ("S&P 500", "SPX", "US"),
    ("NASDAQ", "NASDAQ", "US"),
    ("USD/INR", "USDINR", "US"),
    ("GOLD", "GOLD", "US"),
)


_STRIP_TV = {
    "NIFTY": "NSE:NIFTY",
    "SENSEX": "BSE:SENSEX",
    "S&P 500": "SP:SPX",
    "NASDAQ": "NASDAQ:IXIC",
    "USD/INR": "FX_IDC:USDINR",
    "GOLD": "TVC:GOLD",
}


def _strip_scan() -> dict[str, dict]:
    """One TradingView scan for every home tile. India does not wait on the Angel book."""
    tickers = [_STRIP_TV[label] for label, _symbol, _region in _HOME_STRIP]
    body = json.dumps({"symbols": {"tickers": tickers}, "columns": ["close", "change", "change_abs"]}).encode()
    payload = _json(_TV, data=body, headers={"Content-Type": "application/json", "Origin": "https://www.tradingview.com"})
    rows = payload.get("data") if isinstance(payload, dict) else None
    by_symbol = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            values = row.get("d")
            price = _num(values[0]) if isinstance(values, list) and values else None
            if not price or price <= 0:
                continue
            reported = _num(values[1]) if len(values) > 1 else None
            by_symbol[row.get("s")] = {"price": price, "change_pct": reported, "source": "tradingview"}
    found = {}
    for label, _symbol, _region in _HOME_STRIP:
        hit = by_symbol.get(_STRIP_TV[label])
        if hit:
            found[label] = dict(hit)
    return found


def _session_move(price: Optional[float], closes: list, reported: Optional[float]) -> Optional[float]:
    """Percent versus the prior daily close. A move the bars do not support is omitted."""
    if price and price > 0 and len(closes) >= 2:
        prev = closes[-2]
        last = closes[-1]
        if prev and prev > 0 and last and last > 0:
            if abs(price - last) / last <= 0.002:
                pct = (last - prev) / prev * 100.0
            elif abs(price - last) / last < 0.04:
                pct = (price - prev) / prev * 100.0
            else:
                pct = (price - last) / last * 100.0
            if abs(pct) > 15:
                return None
            if reported is not None and abs(reported - pct) > 1.0:
                return round(pct, 2)
            return round(pct, 2)
    if reported is None or abs(reported) > 8:
        return None
    return round(reported, 2)


def home_strip() -> dict:
    """Six home tiles. TradingView fills the strip; Angel can replace the NIFTY price."""
    def load():
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as _FuturesTimeout
        found = _strip_scan()
        pool = ThreadPoolExecutor(max_workers=6)
        try:
            angel = pool.submit(quote, "NIFTY", "IN")
            # Sparks are optional. A 4 second wait on six sockets was the 3 second strip.
            bars = {pool.submit(_tv_symbol_bars, _STRIP_TV[label], "D", 24, 0.6): label for label, _s, _r in _HOME_STRIP}
            closes: dict[str, list] = {}
            try:
                for job in as_completed(list(bars), timeout=0.7):
                    label = bars[job]
                    try:
                        rows = job.result()
                    except Exception:
                        rows = []
                    series = []
                    for row in rows or []:
                        close = _num(row[4]) if len(row) > 4 else None
                        if close and close > 0:
                            series.append(close)
                    if series:
                        closes[label] = series[-16:]
            except _FuturesTimeout:
                pass
            try:
                env = angel.result(timeout=0.4)
            except Exception:
                env = None
            angel_data = env.get("data") if isinstance(env, dict) and env.get("ok") else None
            if isinstance(angel_data, dict) and angel_data.get("price"):
                spot = found.setdefault("NIFTY", {"source": "angel"})
                tv_price = spot.get("price")
                angel_price = angel_data["price"]
                if not tv_price or abs(angel_price - tv_price) / tv_price <= 0.03:
                    spot["price"] = angel_price
                    spot["source"] = "angel"
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        for label, symbol, region in _HOME_STRIP:
            if label in found and found[label].get("price"):
                continue
            try:
                env = quote(symbol, region)
            except Exception:
                env = None
            data = env.get("data") if isinstance(env, dict) else None
            if isinstance(data, dict) and data.get("price"):
                found[label] = {"price": data["price"], "change_pct": data.get("change_pct"), "source": env.get("source") or "tradingview"}
        indices = []
        for label, _symbol, _region in _HOME_STRIP:
            row = found.get(label)
            if not row or not row.get("price"):
                continue
            series = closes.get(label) or []
            pct = _session_move(row.get("price"), series, row.get("change_pct"))
            indices.append({
                "name": label,
                "symbol": label,
                "price": row.get("price"),
                "change_pct": pct,
                "spark": series,
                "provider": row.get("source"),
                "source": row.get("source"),
                "as_of": _iso(),
            })
        providers = []
        for row in indices:
            if row.get("provider") and row["provider"] not in providers:
                providers.append(row["provider"])
        nifty = next((row for row in indices if row["name"] == "NIFTY"), None)
        payload = {
            "ok": len(indices) == 6,
            "success": bool(indices),
            "indices": indices,
            "source": ", ".join(providers),
            "as_of": nifty.get("as_of") if nifty else (indices[0]["as_of"] if indices else None),
            "nifty": nifty.get("price") if nifty else None,
        }
        return payload if payload["ok"] else None

    cached = _remember("home-strip", 30, load)
    if cached.get("ok") and cached.get("indices"):
        return cached
    return {"success": False, "indices": [], "source": "", "as_of": None, "nifty": None}


def bundle(symbol: str, region: Optional[str] = None, period: str = "1y", interval: str = "1d") -> dict:
    """Quote, candles and fundamentals in parallel."""
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {
            "quote": pool.submit(quote, symbol, region),
            "candles": pool.submit(candles, symbol, period, interval, region),
            "fundamentals": pool.submit(fundamentals, symbol, region),
        }
        out = {name: job.result() for name, job in jobs.items()}
    out["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    out["symbol"] = symbol
    out["region"] = classify(symbol, region)["region"]
    return out


def news(symbol: str, region: Optional[str] = None) -> dict:
    meta = classify(symbol, region)
    if not meta["finnhub"]:
        return {"ok": True, "data": [], "source": "tradingview", "as_of": _iso(), "stale": False, "metric_sources": {}}
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=14)
    payload = _finnhub("/company-news", {"symbol": meta["root"], "from": start.isoformat(), "to": end.isoformat()})
    rows = payload if isinstance(payload, list) else []
    clean = []
    for row in rows[:12]:
        if not isinstance(row, dict):
            continue
        clean.append({
            "headline": row.get("headline") or "",
            "source": row.get("source") or "finnhub",
            "url": row.get("url") or "",
            "summary": row.get("summary") or "",
            "datetime": row.get("datetime"),
        })
    return {"ok": True, "data": clean, "source": "finnhub" if clean else None, "as_of": _iso(), "stale": False, "metric_sources": {"news": {"source": "finnhub", "as_of": _iso()}}}


def peers(symbol: str, region: Optional[str] = None) -> dict:
    fund = fundamentals(symbol, region)
    data = fund.get("data") or {}
    rows = data.get("_peers") or []
    return {"ok": bool(rows), "data": rows, "source": "finnhub" if rows else fund.get("source"), "as_of": fund.get("as_of"), "stale": fund.get("stale", False), "metric_sources": {}}


def option_chain(symbol: str, region: Optional[str] = None) -> dict:
    meta = classify(symbol, region)
    if meta["region"] == "IN" and meta["root"] in {"NIFTY", "BANKNIFTY"}:
        try:
            import angel_options
            if angel_options.configured():
                chain = angel_options.chain(meta["root"])
                rows = chain.get("rows") if isinstance(chain, dict) else None
                return {
                    "available": bool(rows),
                    "provider": "angel",
                    "quality": "LIVE" if rows else "UNAVAILABLE",
                    "rows": rows or [],
                    "spot": chain.get("spot") if isinstance(chain, dict) else None,
                    "expiry": chain.get("expiry") if isinstance(chain, dict) else None,
                    "reason": None if rows else (chain.get("message") if isinstance(chain, dict) else "Angel option chain is unavailable."),
                }
        except Exception:
            pass
        return {"available": False, "provider": "angel", "rows": [], "reason": "Angel One session is not configured for the India option chain."}
    if meta["finnhub"]:
        payload = _finnhub("/stock/option-chain", {"symbol": meta["root"]})
        if isinstance(payload, dict) and payload.get("data"):
            return {"available": True, "provider": "finnhub", "quality": "DELAYED", "rows": payload.get("data"), "raw": False, "reason": None}
        return {"available": False, "provider": "finnhub", "rows": [], "reason": "Finnhub did not return an option chain for this symbol on the current plan."}
    return {"available": False, "provider": None, "rows": [], "reason": "No option chain source is configured for this symbol."}


class HTTPResult:
    """Small response object so older call sites can read status, JSON and text."""

    def __init__(self, payload: dict, status: int = 200):
        self.status_code = status
        self._payload = payload if isinstance(payload, dict) else {}
        self.headers = {"content-type": "application/json"}
        self.ok = status == 200
        self.text = json.dumps(self._payload)
        self.content = self.text.encode()

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("provider response was not usable")


def chart_payload(symbol: str, range: str = "5d", interval: str = "1d", period1: Optional[int] = None, period2: Optional[int] = None, region: Optional[str] = None) -> dict:
    meta = classify(symbol, region)
    interval_name = interval or "1d"
    if interval_name in {"5m", "1m", "15m", "60m"}:
        candle_env = candles(symbol, period="5d", interval=interval_name, region=region)
    else:
        period = "1y" if range in {"1y", "2y", "5y", "10y", "max"} else "6mo"
        candle_env = candles(symbol, period=period, interval="1d", region=region)
    bars = candle_env.get("data") if candle_env.get("ok") and isinstance(candle_env.get("data"), list) else []
    if period1 or period2:
        def _keep(bar):
            stamp = bar.get("time")
            try:
                epoch = datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
            except ValueError:
                return True
            if period1 and epoch < period1:
                return False
            if period2 and epoch > period2:
                return False
            return True
        bars = [bar for bar in bars if _keep(bar)]
    quote_env = quote(symbol, region)
    quote_data = quote_env.get("data") or {}
    price = _num(quote_data.get("price")) or (_num(bars[-1]["close"]) if bars else None)
    prev = _num(quote_data.get("prev_close")) or (_num(bars[-2]["close"]) if len(bars) > 1 else price)
    as_of = quote_env.get("as_of") or candle_env.get("as_of") or _iso()
    try:
        epoch = int(datetime.fromisoformat(as_of.replace("Z", "+00:00")).timestamp())
    except ValueError:
        epoch = int(_now())
    timestamps = []
    opens, highs, lows, closes, volumes = [], [], [], [], []
    for bar in bars:
        stamp = bar.get("time")
        try:
            if isinstance(stamp, (int, float)):
                timestamps.append(int(stamp))
            else:
                text = str(stamp)
                if len(text) == 10:
                    timestamps.append(int(datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()))
                else:
                    timestamps.append(int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()))
        except (ValueError, TypeError):
            continue
        opens.append(bar.get("open"))
        highs.append(bar.get("high"))
        lows.append(bar.get("low"))
        closes.append(bar.get("close"))
        volumes.append(bar.get("volume") or 0)
    provider_symbol = symbol if meta["region"] == "US" else (meta["root"] + ".NS" if not str(symbol).upper().endswith((".NS", ".BO")) and meta["kind"] == "equity" else symbol)
    if meta["root"] in {"NIFTY", "^NSEI"}:
        provider_symbol = "^NSEI"
    elif meta["root"] in {"BANKNIFTY", "^NSEBANK"}:
        provider_symbol = "^NSEBANK"
    elif meta["root"] in {"SENSEX", "^BSESN"}:
        provider_symbol = "^BSESN"
    session_start = timestamps[0] if timestamps else epoch - 6 * 3600
    session_end = (timestamps[-1] + 300) if timestamps else epoch
    return {
        "chart": {
            "result": [{
                "meta": {
                    "symbol": provider_symbol if interval_name == "5m" else (quote_data.get("symbol") or meta["root"]),
                    "currency": quote_data.get("currency") or meta["currency"],
                    "regularMarketPrice": price or 0,
                    "chartPreviousClose": prev or price or 0,
                    "previousClose": prev or price or 0,
                    "regularMarketTime": epoch,
                    "instrumentType": "EQUITY" if meta["kind"] == "equity" else "INDEX",
                    "dataGranularity": interval_name,
                    "exchangeName": "NSE" if meta["region"] == "IN" else "NASDAQ",
                    "shortName": quote_data.get("name") or meta["root"],
                    "longName": quote_data.get("name") or meta["root"],
                    "fullExchangeName": "NSE" if meta["region"] == "IN" else "NASDAQ",
                    "currentTradingPeriod": {"regular": {"start": session_start, "end": session_end}},
                    "source": candle_env.get("source") or quote_env.get("source"),
                    "sourceAsOf": as_of,
                    "stale": bool(candle_env.get("stale") or quote_env.get("stale")),
                },
                "timestamp": timestamps,
                "indicators": {"quote": [{"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}]},
            }],
        }
    }


def chart_http(symbol: str, range: str = "5d", interval: str = "1d", period1: Optional[int] = None, period2: Optional[int] = None) -> HTTPResult:
    payload = chart_payload(symbol, range=range, interval=interval, period1=period1, period2=period2)
    result = (payload.get("chart") or {}).get("result") or []
    meta = (result[0].get("meta") if result else {}) or {}
    if not meta.get("regularMarketPrice") and not (result and result[0].get("timestamp")):
        return HTTPResult(payload, status=204)
    return HTTPResult(payload, status=200)


def summary_http(symbol: str) -> HTTPResult:
    """Quote-summary shaped JSON built from the provider, for older parsers."""
    env = fundamentals(symbol)
    info = env.get("data") or {}

    def raw(field):
        value = info.get(field)
        return {"raw": value if value is not None else 0}

    payload = {
        "quoteSummary": {
            "result": [{
                "financialData": {
                    "currentPrice": raw("currentPrice"),
                    "profitMargins": raw("profitMargins"),
                    "operatingMargins": raw("operatingMargins"),
                    "grossMargins": raw("grossMargins"),
                    "returnOnEquity": raw("returnOnEquity"),
                    "returnOnAssets": raw("returnOnAssets"),
                    "revenueGrowth": raw("revenueGrowth"),
                    "earningsGrowth": raw("earningsGrowth"),
                    "debtToEquity": raw("debtToEquity"),
                    "currentRatio": raw("currentRatio"),
                    "targetMeanPrice": raw("targetMeanPrice"),
                    "numberOfAnalystOpinions": raw("numberOfAnalystOpinions"),
                    "freeCashflow": raw("freeCashflow"),
                },
                "defaultKeyStatistics": {
                    "trailingEps": raw("trailingEps"),
                    "bookValue": raw("bookValue"),
                    "beta": raw("beta"),
                    "pegRatio": raw("pegRatio"),
                    "forwardPE": raw("forwardPE"),
                    "priceToBook": raw("priceToBook"),
                    "enterpriseToEbitda": raw("enterpriseToEbitda"),
                },
                "summaryDetail": {
                    "trailingPE": raw("trailingPE"),
                    "forwardPE": raw("forwardPE"),
                    "marketCap": raw("marketCap"),
                    "dividendYield": raw("dividendYield"),
                    "fiftyTwoWeekHigh": raw("fiftyTwoWeekHigh"),
                    "fiftyTwoWeekLow": raw("fiftyTwoWeekLow"),
                    "previousClose": raw("previousClose"),
                    "beta": raw("beta"),
                    "priceToBook": raw("priceToBook"),
                },
                "summaryProfile": {"sector": info.get("sector") or "", "industry": info.get("industry") or "", "longBusinessSummary": info.get("longBusinessSummary") or ""},
                "assetProfile": {"sector": info.get("sector") or "", "industry": info.get("industry") or "", "longBusinessSummary": info.get("longBusinessSummary") or ""},
                "price": {"shortName": info.get("shortName") or symbol, "longName": {"raw": info.get("longName") or symbol}, "marketCap": raw("marketCap"), "regularMarketPrice": raw("currentPrice")},
                "earnings": {"earningsChart": {"quarterly": info.get("_earnings_calendar") or []}},
            }]
        },
        "_source": env.get("source"),
        "_as_of": env.get("as_of"),
        "_stale": env.get("stale"),
    }
    return HTTPResult(payload, status=200 if info else 204)


def cache_snapshot() -> dict:
    with _lock:
        return {"entries": len(_cache)}


# Quote-shaped helpers that used to live beside this module. History still
# reads candles for one symbol. download() is the quote batch.
_OHLCV = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
_EMPTY_INSIDER = ["Insider", "Transaction", "Start Date", "Shares", "Value"]


def _empty(columns=_OHLCV) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _frame(bars: list) -> pd.DataFrame:
    if not bars:
        return _empty()
    rows = []
    index = []
    for bar in bars:
        stamp = bar.get("time")
        try:
            if isinstance(stamp, (int, float)):
                moment = datetime.fromtimestamp(float(stamp), timezone.utc)
            elif isinstance(stamp, str) and len(stamp) == 10:
                moment = datetime.strptime(stamp, "%Y-%m-%d")
            else:
                moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        close = bar.get("close")
        rows.append({
            "Open": bar.get("open") if bar.get("open") is not None else close,
            "High": bar.get("high") if bar.get("high") is not None else close,
            "Low": bar.get("low") if bar.get("low") is not None else close,
            "Close": close,
            "Adj Close": close,
            "Volume": bar.get("volume") or 0,
        })
        index.append(pd.Timestamp(moment))
    if not rows:
        return _empty()
    frame = pd.DataFrame(rows, index=pd.DatetimeIndex(index))
    frame.index.name = "Date"
    return frame.sort_index()


def _period_interval(period: str, interval: str) -> tuple[str, str]:
    interval_name = interval or "1d"
    if interval_name in {"1m", "5m", "15m", "60m", "1h"}:
        mapped = "60m" if interval_name == "1h" else interval_name
        return "5d", mapped
    return period or "1y", "1d"


def _roll_up(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    indexed = frame.sort_index()
    if getattr(indexed.index, "tz", None) is not None:
        indexed = indexed.tz_localize(None)
    aggregations = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Adj Close": "last",
        "Volume": "sum",
    }
    try:
        rolled = indexed.resample(rule).agg(aggregations).dropna(subset=["Close"])
    except ValueError:
        rolled = indexed.resample("M" if rule == "ME" else rule).agg(aggregations).dropna(subset=["Close"])
    try:
        rolled.attrs = dict(frame.attrs)
    except Exception:
        pass
    return rolled


class Ticker:
    def __init__(self, ticker, *args, **kwargs):
        self.ticker = str(ticker or "").strip()

    def _fund(self) -> dict:
        env = fundamentals(self.ticker)
        data = env.get("data") if isinstance(env, dict) else None
        return data if isinstance(data, dict) else {}

    def history(self, period="1mo", interval="1d", start=None, end=None, **kwargs) -> pd.DataFrame:
        requested = str(interval or "1d")
        period_name, interval_name = _period_interval(str(period or "1y"), requested)
        region = kwargs.get("region")
        env = candles(self.ticker, period=period_name, interval=interval_name, region=region)
        bars = env.get("data") if isinstance(env, dict) and isinstance(env.get("data"), list) else []
        frame = _frame(bars)
        if requested in {"1wk", "1w"}:
            frame = _roll_up(frame, "W-FRI")
        elif requested in {"1mo", "1month"}:
            frame = _roll_up(frame, "ME")
        try:
            frame.attrs["source"] = (env or {}).get("source")
            frame.attrs["as_of"] = (env or {}).get("as_of")
            frame.attrs["stale"] = bool((env or {}).get("stale"))
        except Exception:
            pass
        if start is not None or end is not None:
            try:
                frame = frame.loc[start:end]
            except Exception:
                pass
        return frame if isinstance(frame, pd.DataFrame) else _empty()

    @property
    def info(self) -> dict:
        return self._fund()

    @property
    def fast_info(self) -> dict:
        env = quote(self.ticker)
        data = env.get("data") if isinstance(env, dict) else {}
        data = data or {}
        price = data.get("price") or 0
        prev = data.get("prev_close") or price
        return {
            "last_price": price,
            "lastPrice": price,
            "previous_close": prev,
            "previousClose": prev,
            "regularMarketPrice": price,
            "currency": data.get("currency"),
            "source": env.get("source") if isinstance(env, dict) else None,
        }

    def _statement(self) -> pd.DataFrame:
        return _empty(["2024"])

    @property
    def income_stmt(self):
        return self._statement()

    @property
    def quarterly_income_stmt(self):
        return self._statement()

    @property
    def balance_sheet(self):
        return self._statement()

    @property
    def quarterly_balance_sheet(self):
        return self._statement()

    @property
    def cashflow(self):
        return self._statement()

    @property
    def quarterly_cashflow(self):
        return self._statement()

    @property
    def financials(self):
        return self.income_stmt

    @property
    def quarterly_financials(self):
        return self.quarterly_income_stmt

    @property
    def earnings(self):
        return _empty()

    @property
    def quarterly_earnings(self):
        return _empty()

    @property
    def earnings_dates(self):
        info = self._fund()
        rows = info.get("_earnings_calendar") or []
        records = []
        index = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("date"):
                continue
            try:
                index.append(pd.Timestamp(row["date"]))
            except (TypeError, ValueError):
                continue
            records.append({"EPS Estimate": row.get("epsEstimate"), "Reported EPS": row.get("epsActual")})
        if not records:
            return _empty(["EPS Estimate", "Reported EPS"])
        return pd.DataFrame(records, index=pd.DatetimeIndex(index))

    @property
    def earnings_history(self):
        return self.earnings_dates

    @property
    def calendar(self) -> dict:
        info = self._fund()
        date = info.get("earningsDate")
        if not date:
            return {}
        try:
            parsed = datetime.strptime(str(date)[:10], "%Y-%m-%d")
        except ValueError:
            return {}
        return {"Earnings Date": [parsed]}

    @property
    def recommendations(self):
        info = self._fund()
        rows = info.get("_recommendations") or []
        if not rows:
            return _empty(["strongBuy", "buy", "hold", "sell", "strongSell"])
        return pd.DataFrame(rows)

    @property
    def analyst_price_targets(self) -> dict:
        info = self._fund()
        return {
            "current": info.get("currentPrice"),
            "mean": info.get("targetMeanPrice"),
            "high": info.get("targetHighPrice"),
            "low": info.get("targetLowPrice"),
        }

    @property
    def insider_transactions(self):
        return _empty(_EMPTY_INSIDER)

    @property
    def insider_purchases(self):
        return _empty()

    @property
    def institutional_holders(self):
        return _empty()

    @property
    def major_holders(self):
        return _empty()

    @property
    def mutualfund_holders(self):
        return _empty()

    @property
    def options(self):
        return ()

    def option_chain(self, date=None):
        return SimpleNamespace(calls=_empty(), puts=_empty())

    @property
    def news(self):
        env = news(self.ticker)
        rows = env.get("data") if isinstance(env, dict) else []
        return rows if isinstance(rows, list) else []

    @property
    def dividends(self):
        return pd.Series(dtype=float)

    @property
    def splits(self):
        return pd.Series(dtype=float)

    @property
    def actions(self):
        return _empty()

    def get_news(self, *args, **kwargs):
        return self.news

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return _empty()


class Tickers:
    def __init__(self, tickers, *args, **kwargs):
        if isinstance(tickers, str):
            symbols = [part for part in tickers.replace(",", " ").split() if part]
        else:
            symbols = [str(part) for part in tickers]
        self.symbols = symbols
        self.tickers = {symbol: Ticker(symbol) for symbol in symbols}

    def history(self, **kwargs):
        return download(self.symbols, group_by="ticker", **kwargs)

    def __getattr__(self, name):
        return self.tickers.get(name)


def history_frame(symbol: str, period: str = "1y", interval: str = "1d", region: str | None = None) -> pd.DataFrame:
    """The one candle entry analysis routes use. Always a DataFrame, never None."""
    frame = Ticker(symbol).history(period=period, interval=interval, region=region)
    return frame if isinstance(frame, pd.DataFrame) else _empty()


def history_many(symbol: str, specs, region: str | None = None) -> dict:
    """Fetch several (period, interval) frames at once. They share the candle cache."""
    wanted = [(str(period or "1y"), str(interval or "1d")) for period, interval in list(specs or [])]
    if not wanted:
        return {}

    def one(spec):
        period, interval = spec
        return history_frame(symbol, period=period, interval=interval, region=region)

    if len(wanted) == 1:
        return {wanted[0]: one(wanted[0])}
    from concurrent.futures import ThreadPoolExecutor
    out = {}
    with ThreadPoolExecutor(max_workers=min(4, len(wanted))) as pool:
        jobs = {pool.submit(one, spec): spec for spec in wanted}
        for job, spec in jobs.items():
            try:
                out[spec] = job.result()
            except Exception:
                out[spec] = _empty()
    return out


def download(tickers="AAPL", period="1mo", interval="1d", group_by="column", threads=True, progress=False, start=None, end=None, region=None, **kwargs) -> pd.DataFrame:
    if region is None:
        region = kwargs.get("region")
    if isinstance(tickers, str):
        symbols = [part for part in tickers.replace(",", " ").split() if part]
    else:
        symbols = [str(part) for part in tickers if str(part).strip()]
    if not symbols:
        return _empty()
    # Scans share this helper. A candle chain per symbol filled the home strip's slots.
    book = scan_quotes(symbols, region)
    frames = {}
    for symbol in symbols:
        row = book.get(symbol) or {}
        price = row.get("price") or 0
        if not price:
            continue
        prev = row.get("prev_close") or price
        volume = row.get("volume") or 0
        stamp = pd.Timestamp.now().normalize()
        frames[symbol] = pd.DataFrame(
            {
                "Open": [prev, price],
                "High": [max(prev, price), max(prev, price)],
                "Low": [min(prev, price), min(prev, price)],
                "Close": [prev, price],
                "Adj Close": [prev, price],
                "Volume": [volume, volume],
            },
            index=pd.DatetimeIndex([stamp - pd.Timedelta(days=1), stamp]),
        )
    usable = {symbol: frame for symbol, frame in frames.items() if isinstance(frame, pd.DataFrame) and not frame.empty}
    if not usable:
        return _empty()
    if len(symbols) == 1:
        return usable.get(symbols[0], _empty())
    if group_by == "ticker":
        pieces = []
        for symbol, frame in usable.items():
            copied = frame.copy()
            copied.columns = pd.MultiIndex.from_product([[symbol], copied.columns])
            pieces.append(copied)
        return pd.concat(pieces, axis=1).sort_index()
    pieces = []
    for symbol, frame in usable.items():
        copied = frame.copy()
        copied.columns = pd.MultiIndex.from_product([copied.columns, [symbol]])
        pieces.append(copied)
    return pd.concat(pieces, axis=1).sort_index()


def set_tz_cache_location(*args, **kwargs):
    return None
