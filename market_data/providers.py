"""Authenticated, read-only REST adapters for US and India market data.

REST snapshots are deliberately distinct from persistent websocket health.
No order, portfolio, or account-management methods are implemented here.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import requests

from .base import MarketDataProvider
from .contracts import DataQuality, MarketBar, MarketQuote, ProviderHealth, utc_now


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("provider timestamp missing timezone")
    return parsed.astimezone(timezone.utc)


class AlpacaMarketData(MarketDataProvider):
    """Alpaca Trading API key/secret market-data client (not Broker API OAuth)."""

    provider_name = "alpaca"

    def __init__(self, key: Optional[str] = None, secret: Optional[str] = None,
                 feed: Optional[str] = None, session: Optional[requests.Session] = None):
        self.key = (key if key is not None else os.getenv("APCA_API_KEY_ID", "")).strip()
        self.secret = (secret if secret is not None else os.getenv("APCA_API_SECRET_KEY", "")).strip()
        self.feed = (feed if feed is not None else os.getenv("CELESYS_ALPACA_STOCK_FEED", "iex")).strip().lower()
        if self.feed not in {"iex", "sip", "delayed_sip"}:
            raise ValueError("Alpaca stock feed must be iex, sip, or delayed_sip")
        self.base_url = "https://data.alpaca.markets"
        self.session = session or requests.Session()
        self._connected = False
        self._last_message: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._symbols: set[str] = set()

    def _get(self, path: str, params: dict) -> dict:
        if not self.key or not self.secret:
            raise RuntimeError("Alpaca credentials are not configured")
        response = self.session.get(
            self.base_url + path, params=params,
            headers={"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret},
            timeout=(3.05, 10),
        )
        if response.status_code in (401, 403):
            self._last_error = "AUTH_OR_FEED_ENTITLEMENT"
        elif response.status_code == 429:
            self._last_error = "RATE_LIMITED"
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Alpaca returned a non-object response")
        self._connected = True
        self._last_message = utc_now()
        self._last_error = None
        return payload

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.provider_name, connected=self._connected,
            authenticated=bool(self.key and self.secret and self._connected),
            checked_at=utc_now(), last_message_at=self._last_message,
            subscribed_symbols=len(self._symbols), last_error_code=self._last_error,
        )

    def get_quote(self, symbol: str) -> Optional[MarketQuote]:
        symbol = symbol.strip().upper()
        if not symbol:
            return None
        payload = self._get(f"/v2/stocks/{symbol}/quotes/latest", {"feed": self.feed})
        quote = payload.get("quote")
        if not isinstance(quote, dict) or not quote.get("t"):
            return None
        stamp = _dt(quote["t"])
        age = (utc_now() - stamp).total_seconds()
        quality = DataQuality.DELAYED if self.feed == "delayed_sip" else (
            DataQuality.LIVE if 0 <= age <= 15 else DataQuality.STALE
        )
        bid, ask = quote.get("bp"), quote.get("ap")
        return MarketQuote(
            symbol=symbol, provider=self.provider_name, asset_class="equity",
            currency="USD", received_at=utc_now(), quality=quality,
            bid=bid, ask=ask, bid_at=stamp if bid is not None else None,
            ask_at=stamp if ask is not None else None,
            source_sequence=str(quote.get("z") or quote.get("i") or "") or None,
        )

    def get_bars(self, symbol: str, timeframe: str, limit: int = 100) -> list[MarketBar]:
        symbol = symbol.strip().upper()
        intervals = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "1h": "1Hour", "1d": "1Day"}
        if timeframe not in intervals:
            raise ValueError("Unsupported Alpaca timeframe")
        if not 1 <= int(limit) <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        payload = self._get(f"/v2/stocks/{symbol}/bars", {
            "timeframe": intervals[timeframe], "limit": int(limit),
            "feed": self.feed, "adjustment": "raw",
        })
        rows = payload.get("bars")
        if not isinstance(rows, list):
            raise ValueError("Alpaca bars response is malformed")
        duration = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}[timeframe]
        now = utc_now()
        quality = DataQuality.DELAYED if self.feed == "delayed_sip" else DataQuality.LIVE
        bars = []
        for row in rows:
            start = _dt(row["t"])
            end = start + timedelta(seconds=duration)
            complete = end <= now
            bars.append(MarketBar(
                symbol=symbol, provider=self.provider_name, timeframe=timeframe,
                start_at=start, end_at=end, received_at=now,
                quality=quality if complete else DataQuality.STALE,
                is_complete=complete, open=row.get("o"), high=row.get("h"),
                low=row.get("l"), close=row.get("c"), volume=row.get("v"),
                trade_count=row.get("n"),
            ))
        return bars

    def subscribe(self, symbols: Iterable[str]) -> None:
        # REST adapter has no persistent subscriptions. This records a bounded
        # watchlist only; callers must not mistake it for websocket streaming.
        normalized = {str(s).strip().upper() for s in symbols if str(s).strip()}
        if len(normalized) > 1000:
            raise ValueError("watchlist exceeds the 1000-symbol safety cap")
        self._symbols = normalized

    def close(self) -> None:
        self.session.close()
        self._connected = False
