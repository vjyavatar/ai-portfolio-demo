"""Map user input onto provider symbols. No network."""
from __future__ import annotations

import re

_TOKEN = re.compile(r"^[A-Z0-9.^=-]{1,24}$")

INDEX_ALIASES = {
    "NIFTY": "NSE:NIFTY",
    "NIFTY50": "NSE:NIFTY",
    "NIFTY 50": "NSE:NIFTY",
    "^NSEI": "NSE:NIFTY",
    "BANKNIFTY": "NSE:BANKNIFTY",
    "BANK NIFTY": "NSE:BANKNIFTY",
    "NIFTYBANK": "NSE:BANKNIFTY",
    "^NSEBANK": "NSE:BANKNIFTY",
    "SENSEX": "BSE:SENSEX",
    "^BSESN": "BSE:SENSEX",
    "SPX": "SP:SPX",
    "^GSPC": "SP:SPX",
    "GSPC": "SP:SPX",
    "SP500": "SP:SPX",
    "DJI": "DJ:DJI",
    "^DJI": "DJ:DJI",
    "DJIA": "DJ:DJI",
    "DOW": "DJ:DJI",
    "IXIC": "NASDAQ:IXIC",
    "^IXIC": "NASDAQ:IXIC",
    "NASDAQ": "NASDAQ:IXIC",
    "NDX": "NASDAQ:NDX",
    "^NDX": "NASDAQ:NDX",
    "VIX": "CBOE:VIX",
    "^VIX": "CBOE:VIX",
    "INDIAVIX": "NSE:INDIAVIX",
    "^INDIAVIX": "NSE:INDIAVIX",
}

YAHOO_BY_TV = {
    "NSE:NIFTY": "^NSEI",
    "NSE:BANKNIFTY": "^NSEBANK",
    "BSE:SENSEX": "^BSESN",
    "NSE:INDIAVIX": "^INDIAVIX",
    "SP:SPX": "^GSPC",
    "DJ:DJI": "^DJI",
    "NASDAQ:IXIC": "^IXIC",
    "NASDAQ:NDX": "^NDX",
    "CBOE:VIX": "^VIX",
    "FX_IDC:USDINR": "INR=X",
    "TVC:GOLD": "GC=F",
    "TVC:SILVER": "SI=F",
    "TVC:USOIL": "CL=F",
    "BITSTAMP:BTCUSD": "BTC-USD",
}


def _clean(raw: str) -> str:
    return (raw or "").strip().upper().replace(" ", "")


def validate(raw: str) -> str:
    token = _clean(raw)
    if not token or not _TOKEN.match(token):
        raise ValueError("Enter a ticker such as AAPL or RELIANCE.NS")
    return token


def _pack(raw: str, tv: list[str], yahoo: list[str], kind: str, region: str | None) -> dict:
    return {
        "input": raw.strip(),
        "token": _clean(raw),
        "tv": tv,
        "yahoo": yahoo,
        "kind": kind,
        "region_hint": region,
    }


def resolve(raw: str, region: str | None = None) -> dict:
    token = validate(raw)
    hinted = (region or "").upper() or None
    if hinted not in (None, "US", "IN"):
        hinted = None
    alias = INDEX_ALIASES.get(token) or INDEX_ALIASES.get(raw.strip().upper())
    if alias:
        region_hint = "IN" if alias.startswith(("NSE:", "BSE:")) else "US"
        yahoo = [YAHOO_BY_TV[alias]] if alias in YAHOO_BY_TV else []
        return _pack(raw, [alias], yahoo, "index", region_hint)

    if token.endswith(".NS"):
        base = token[:-3]
        return _pack(raw, [f"NSE:{base}"], [token], "equity", "IN")
    if token.endswith(".BO"):
        base = token[:-3]
        return _pack(raw, [f"BSE:{base}"], [token], "equity", "IN")

    if hinted == "IN":
        return _pack(raw, [f"NSE:{token}", f"BSE:{token}"], [f"{token}.NS", f"{token}.BO"], "equity", "IN")
    if hinted == "US":
        return _pack(raw, [f"NASDAQ:{token}", f"NYSE:{token}", f"AMEX:{token}"], [token], "equity", "US")
    return _pack(
        raw,
        [f"NASDAQ:{token}", f"NYSE:{token}", f"AMEX:{token}", f"NSE:{token}", f"BSE:{token}"],
        [token, f"{token}.NS", f"{token}.BO"],
        "equity",
        None,
    )


def region_of(tv_symbol: str) -> str:
    prefix = (tv_symbol or "").split(":", 1)[0]
    if prefix in {"NSE", "BSE"}:
        return "IN"
    return "US"


def currency_of(tv_symbol: str, provider_currency: str | None) -> str:
    if provider_currency:
        return provider_currency
    return "INR" if region_of(tv_symbol) == "IN" else "USD"
