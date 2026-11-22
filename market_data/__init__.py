"""Celesys canonical market-data layer.

Provider adapters are read-only. Signal engines must consume normalized,
timestamped records and must fail closed when required data is unavailable.
"""
from .contracts import DataQuality, MarketBar, MarketQuote, ProviderHealth

__all__ = ["DataQuality", "MarketBar", "MarketQuote", "ProviderHealth"]
