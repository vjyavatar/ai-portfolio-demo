"""Provider adapter interface. Implementations must be read-only."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Optional

from .contracts import MarketBar, MarketQuote, ProviderHealth


class MarketDataProvider(ABC):
    provider_name: str

    @abstractmethod
    def health(self) -> ProviderHealth:
        """Return current connection/authentication health without leaking secrets."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Return a normalized quote, or None when no verified quote is available."""

    @abstractmethod
    def get_bars(self, symbol: str, timeframe: str, limit: int) -> list[MarketBar]:
        """Return normalized bars; incomplete bars must remain explicitly incomplete."""

    @abstractmethod
    def subscribe(self, symbols: Iterable[str]) -> None:
        """Subscribe to a bounded symbol set; must be idempotent."""

    @abstractmethod
    def close(self) -> None:
        """Close streams and release provider resources."""
