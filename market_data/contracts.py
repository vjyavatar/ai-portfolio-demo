"""Canonical, provider-neutral market-data contracts.

All timestamps are timezone-aware UTC. Missing values remain None; callers
must not infer or synthesize prices, quote times, volume, OI, or Greeks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Optional


class DataQuality(str, Enum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    STALE = "STALE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DISCONNECTED = "DISCONNECTED"
    INVALID = "INVALID"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _optional_nonnegative(value: Optional[float], field: str) -> Optional[float]:
    if value is None:
        return None
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return number


@dataclass(frozen=True, slots=True)
class MarketQuote:
    symbol: str
    provider: str
    asset_class: str
    currency: str
    received_at: datetime
    quality: DataQuality
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    bid_at: Optional[datetime] = None
    ask_at: Optional[datetime] = None
    last_at: Optional[datetime] = None
    volume: Optional[float] = None
    open_interest: Optional[float] = None
    source_sequence: Optional[str] = None

    def __post_init__(self) -> None:
        for field in ("symbol", "provider", "asset_class", "currency"):
            if not getattr(self, field) or not getattr(self, field).strip():
                raise ValueError(f"{field} is required")
        object.__setattr__(self, "received_at", _aware_utc(self.received_at, "received_at"))
        for field in ("bid_at", "ask_at", "last_at"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _aware_utc(value, field))
        for field in ("bid", "ask", "last", "volume", "open_interest"):
            object.__setattr__(self, field, _optional_nonnegative(getattr(self, field), field))
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError("crossed quote: bid exceeds ask")

    @property
    def has_two_sided_market(self) -> bool:
        return self.bid is not None and self.ask is not None

    @property
    def is_actionable_candidate(self) -> bool:
        return (
            self.quality == DataQuality.LIVE
            and self.has_two_sided_market
            and self.bid_at is not None
            and self.ask_at is not None
        )


@dataclass(frozen=True, slots=True)
class MarketBar:
    symbol: str
    provider: str
    timeframe: str
    start_at: datetime
    end_at: datetime
    received_at: datetime
    quality: DataQuality
    is_complete: bool
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    trade_count: Optional[int] = None

    def __post_init__(self) -> None:
        for field in ("start_at", "end_at", "received_at"):
            object.__setattr__(self, field, _aware_utc(getattr(self, field), field))
        if self.end_at <= self.start_at:
            raise ValueError("bar end_at must be after start_at")
        for field in ("open", "high", "low", "close", "volume"):
            object.__setattr__(self, field, _optional_nonnegative(getattr(self, field), field))
        prices = [v for v in (self.open, self.high, self.low, self.close) if v is not None]
        if prices and (self.high is None or self.low is None):
            raise ValueError("high and low are required when OHLC values are present")
        if prices and (self.high < max(prices) or self.low > min(prices)):
            raise ValueError("inconsistent OHLC range")
        if self.trade_count is not None and self.trade_count < 0:
            raise ValueError("trade_count must be non-negative")

    @property
    def signal_eligible(self) -> bool:
        return self.is_complete and self.quality == DataQuality.LIVE and self.close is not None


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    provider: str
    connected: bool
    authenticated: bool
    checked_at: datetime
    last_message_at: Optional[datetime] = None
    subscribed_symbols: int = 0
    reconnect_count: int = 0
    last_error_code: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "checked_at", _aware_utc(self.checked_at, "checked_at"))
        if self.last_message_at is not None:
            object.__setattr__(self, "last_message_at", _aware_utc(self.last_message_at, "last_message_at"))
        if self.subscribed_symbols < 0 or self.reconnect_count < 0:
            raise ValueError("health counters must be non-negative")
