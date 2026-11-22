"""Bounded option snapshots.

US: Yahoo option chain (delayed, crumb session). India: NSE public chain when
the exchange accepts the request. Angel One stays on the existing private desk.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from live_markets.providers import USER_AGENT

_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
_CRUMB: tuple[float, str] | None = None


def _read(url: str, timeout: int = 8) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return exc.code, body
    except Exception:
        return 0, b""


def _crumb() -> Optional[str]:
    global _CRUMB
    import time
    if _CRUMB and time.time() - _CRUMB[0] < 1500:
        return _CRUMB[1]
    try:
        _read("https://fc.yahoo.com", timeout=6)
    except Exception:
        pass
    status, raw = _read("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=6)
    text = raw.decode("utf-8", "replace").strip()
    if status == 200 and text and "<" not in text and len(text) < 40:
        _CRUMB = (time.time(), text)
        return text
    return None


def parse_yahoo_chain(payload: dict, strike_window: int = 6) -> Optional[dict]:
    result = (((payload or {}).get("optionChain") or {}).get("result") or [None])[0]
    if not isinstance(result, dict):
        return None
    quote = result.get("quote") or {}
    spot = _num(quote.get("regularMarketPrice"))
    options = result.get("options") or []
    if not options:
        return {
            "available": False,
            "provider": "yahoo",
            "reason": "Yahoo returned no listed contracts for this symbol.",
            "spot": spot,
        }
    chain = options[0]
    expiry = chain.get("expirationDate")
    calls = chain.get("calls") or []
    puts = chain.get("puts") or []
    strikes = sorted({_num(row.get("strike")) for row in calls + puts if _num(row.get("strike"))})
    if spot and strikes:
        nearest = sorted(strikes, key=lambda strike: abs(strike - spot))[: strike_window * 2 + 1]
        keep = set(nearest)
    else:
        keep = set(strikes[: strike_window * 2 + 1])

    def leg(row: dict) -> dict:
        return {
            "contract": row.get("contractSymbol"),
            "bid": _num(row.get("bid")),
            "ask": _num(row.get("ask")),
            "last": _num(row.get("lastPrice")),
            "volume": _num(row.get("volume")),
            "open_interest": _num(row.get("openInterest")),
            "iv": _num(row.get("impliedVolatility")),
            "last_trade_epoch": _num(row.get("lastTradeDate")),
        }

    rows = []
    by_strike: dict[float, dict] = {}
    for row in calls:
        strike = _num(row.get("strike"))
        if strike in keep:
            by_strike.setdefault(strike, {"strike": strike})["call"] = leg(row)
    for row in puts:
        strike = _num(row.get("strike"))
        if strike in keep:
            by_strike.setdefault(strike, {"strike": strike})["put"] = leg(row)
    for strike in sorted(by_strike):
        rows.append(by_strike[strike])
    return {
        "available": bool(rows),
        "provider": "yahoo",
        "quality": "DELAYED",
        "expiry_epoch": expiry,
        "expiry": datetime.fromtimestamp(expiry, timezone.utc).date().isoformat() if expiry else None,
        "spot": spot,
        "rows": rows,
        "truncated": True,
        "note": "Nearest expiry, strikes around spot. Yahoo options are a delayed public chain, not a broker NBBO.",
    }


def fetch_yahoo_chain(symbol: str) -> Optional[dict]:
    crumb = _crumb()
    if not crumb:
        return None
    url = (
        "https://query1.finance.yahoo.com/v7/finance/options/"
        + urllib.parse.quote(symbol, safe="")
        + "?crumb="
        + urllib.parse.quote(crumb)
    )
    status, raw = _read(url, timeout=10)
    if status != 200 or not raw:
        return None
    try:
        return parse_yahoo_chain(json.loads(raw.decode("utf-8", "replace")))
    except json.JSONDecodeError:
        return None


def parse_nse_chain(payload: dict, strike_window: int = 6) -> Optional[dict]:
    records = (payload or {}).get("records") if isinstance(payload, dict) else None
    if not isinstance(records, dict):
        return None
    spot = _num(records.get("underlyingValue"))
    data = records.get("data") or []
    expiries = records.get("expiryDates") or []
    expiry = expiries[0] if expiries else None
    filtered = [row for row in data if not expiry or row.get("expiryDate") == expiry]
    strikes = [_num(row.get("strikePrice")) for row in filtered]
    strikes = [s for s in strikes if s]
    if spot and strikes:
        nearest = set(sorted(strikes, key=lambda strike: abs(strike - spot))[: strike_window * 2 + 1])
    else:
        nearest = set(strikes[: strike_window * 2 + 1])

    def leg(block: dict) -> dict:
        return {
            "bid": _num(block.get("bidprice")),
            "ask": _num(block.get("askPrice")),
            "last": _num(block.get("lastPrice")),
            "volume": _num(block.get("totalTradedVolume")),
            "open_interest": _num(block.get("openInterest")),
            "iv": _num(block.get("impliedVolatility")),
        }

    rows = []
    for row in filtered:
        strike = _num(row.get("strikePrice"))
        if strike not in nearest:
            continue
        item = {"strike": strike}
        if isinstance(row.get("CE"), dict):
            item["call"] = leg(row["CE"])
        if isinstance(row.get("PE"), dict):
            item["put"] = leg(row["PE"])
        rows.append(item)
    rows.sort(key=lambda item: item["strike"])
    return {
        "available": bool(rows),
        "provider": "nse",
        "quality": "DELAYED",
        "expiry": expiry,
        "spot": spot,
        "rows": rows,
        "truncated": True,
        "note": "NSE public chain for the nearest listed expiry, strikes around spot. Datacenter IPs are often blocked.",
    }


def fetch_nse_chain(symbol: str) -> Optional[dict]:
    base = symbol.upper().replace(".NS", "").replace(".BO", "")
    index = base in {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}
    path = "option-chain-indices" if index else "option-chain-equities"
    url = f"https://www.nseindia.com/api/{path}?symbol={urllib.parse.quote(base)}"
    _read("https://www.nseindia.com", timeout=4)
    status, raw = _read(url, timeout=5)
    if status != 200 or not raw or raw[:1] not in (b"{", b"["):
        return None
    try:
        return parse_nse_chain(json.loads(raw.decode("utf-8", "replace")))
    except json.JSONDecodeError:
        return None


def _num(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number
