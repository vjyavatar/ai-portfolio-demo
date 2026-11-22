"""Authenticated read-only endpoints for US and India market data."""
from __future__ import annotations

import os
from dataclasses import asdict
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query

from secure_access import require_user
from .angel_provider import AngelOneMarketData
from .contracts import DataQuality
from .providers import AlpacaMarketData

router = APIRouter()


@lru_cache(maxsize=2)
def _provider(region: str):
    if region == "US":
        name = os.getenv("CELESYS_US_MARKET_DATA_PROVIDER", "disabled").strip().lower()
        return AlpacaMarketData() if name == "alpaca" else None
    if region == "IN":
        name = os.getenv("CELESYS_IN_MARKET_DATA_PROVIDER", "disabled").strip().lower()
        return AngelOneMarketData() if name == "angelone" else None
    return None


def _provider_name(region: str) -> str:
    key = "CELESYS_US_MARKET_DATA_PROVIDER" if region == "US" else "CELESYS_IN_MARKET_DATA_PROVIDER"
    return os.getenv(key, "disabled").strip().lower()


@router.get("/api/market-data/status")
def market_data_status():
    require_user()
    result = {}
    for region in ("US", "IN"):
        provider = _provider(region)
        name = _provider_name(region)
        if provider is None:
            result[region] = {"provider": name, "configured": False,
                              "connected": False, "authenticated": False,
                              "quality": DataQuality.INSUFFICIENT_DATA.value,
                              "execution_enabled": False}
            continue
        health = provider.health()
        if region == "US":
            configured = bool(provider.key and provider.secret)
        else:
            configured = provider.auth.configured
        result[region] = {"provider": name, "configured": configured,
                          **asdict(health), "execution_enabled": False}
    return result


@router.get("/api/market-data/quote/{symbol}")
def market_data_quote(symbol: str, region: str = Query("US")):
    require_user()
    if region not in ("US", "IN"):
        raise HTTPException(422, "region must be US or IN")
    provider = _provider(region)
    if provider is None:
        raise HTTPException(503, "Market-data provider is disabled; no live data is available.")
    try:
        quote = provider.get_quote(symbol)
    except Exception:
        raise HTTPException(503, "Provider request failed; live data is unavailable.")
    if quote is None:
        raise HTTPException(503, "No verified quote returned; data quality is INSUFFICIENT_DATA.")
    return asdict(quote)


@router.get("/api/market-data/bars/{symbol}")
def market_data_bars(symbol: str, region: str = Query("US"),
                     timeframe: str = Query("5m"),
                     limit: int = Query(100, ge=1, le=1000)):
    require_user()
    if region not in ("US", "IN"):
        raise HTTPException(422, "region must be US or IN")
    provider = _provider(region)
    if provider is None:
        raise HTTPException(503, "Market-data provider is disabled; no live data is available.")
    try:
        bars = provider.get_bars(symbol, timeframe, limit)
    except Exception:
        raise HTTPException(503, "Provider request failed; bars are unavailable.")
    return {"symbol": symbol.upper(), "region": region, "timeframe": timeframe,
            "bars": [asdict(bar) for bar in bars],
            "signal_eligible_count": sum(bar.signal_eligible for bar in bars),
            "execution_enabled": False}
