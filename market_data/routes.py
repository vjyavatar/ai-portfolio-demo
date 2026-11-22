"""Authenticated read-only endpoints for the canonical market-data layer."""
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


@lru_cache(maxsize=1)
def _provider():
    name = os.getenv("CELESYS_MARKET_DATA_PROVIDER", "disabled").strip().lower()
    if name == "alpaca":
        return AlpacaMarketData()
    if name == "angelone":
        return AngelOneMarketData()
    return None


@router.get("/api/market-data/status")
def market_data_status():
    require_user()
    name = os.getenv("CELESYS_MARKET_DATA_PROVIDER", "disabled").strip().lower()
    provider = _provider()
    if provider is None:
        return {"provider": name, "configured": False, "connected": False,
                "authenticated": False, "quality": DataQuality.INSUFFICIENT_DATA.value,
                "execution_enabled": False}
    health = provider.health()
    return {"provider": name, "configured": True, **asdict(health),
            "execution_enabled": False}


@router.get("/api/market-data/quote/{symbol}")
def market_data_quote(symbol: str):
    require_user()
    provider = _provider()
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
def market_data_bars(symbol: str, timeframe: str = Query("5m"), limit: int = Query(100, ge=1, le=1000)):
    require_user()
    provider = _provider()
    if provider is None:
        raise HTTPException(503, "Market-data provider is disabled; no live data is available.")
    try:
        bars = provider.get_bars(symbol, timeframe, limit)
    except Exception:
        raise HTTPException(503, "Provider request failed; bars are unavailable.")
    return {"symbol": symbol.upper(), "timeframe": timeframe,
            "bars": [asdict(bar) for bar in bars],
            "signal_eligible_count": sum(bar.signal_eligible for bar in bars),
            "execution_enabled": False}
