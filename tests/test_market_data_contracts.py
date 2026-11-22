"""Regression tests for the provider-neutral market-data contracts."""
import unittest
from datetime import datetime, timedelta, timezone

from market_data.contracts import (
    DataQuality, MarketBar, MarketQuote, ProviderHealth,
)


class MarketQuoteTests(unittest.TestCase):
    def test_rejects_crossed_market(self):
        now = datetime.now(timezone.utc)
        with self.assertRaisesRegex(ValueError, "crossed quote"):
            MarketQuote(
                symbol="SPY", provider="alpaca", asset_class="equity",
                currency="USD", received_at=now, quality=DataQuality.LIVE,
                bid=101, ask=100,
            )

    def test_rejects_naive_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            MarketQuote(
                symbol="SPY", provider="alpaca", asset_class="equity",
                currency="USD", received_at=datetime.now(),
                quality=DataQuality.LIVE,
            )

    def test_missing_prices_are_not_synthesized(self):
        now = datetime.now(timezone.utc)
        quote = MarketQuote(
            symbol="SPY", provider="alpaca", asset_class="equity",
            currency="USD", received_at=now,
            quality=DataQuality.INSUFFICIENT_DATA,
        )
        self.assertIsNone(quote.last)
        self.assertFalse(quote.is_actionable_candidate)

    def test_actionable_requires_live_two_sided_timestamped_quote(self):
        now = datetime.now(timezone.utc)
        quote = MarketQuote(
            symbol="SPY", provider="alpaca", asset_class="equity",
            currency="USD", received_at=now, quality=DataQuality.LIVE,
            bid=100, ask=100.1, bid_at=now, ask_at=now,
        )
        self.assertTrue(quote.is_actionable_candidate)


class MarketBarTests(unittest.TestCase):
    def test_incomplete_bar_is_not_signal_eligible(self):
        now = datetime.now(timezone.utc)
        bar = MarketBar(
            symbol="SPY", provider="alpaca", timeframe="5m",
            start_at=now, end_at=now + timedelta(minutes=5),
            received_at=now, quality=DataQuality.LIVE,
            is_complete=False, open=100, high=102, low=99, close=101,
        )
        self.assertFalse(bar.signal_eligible)

    def test_rejects_inconsistent_ohlc(self):
        now = datetime.now(timezone.utc)
        with self.assertRaisesRegex(ValueError, "inconsistent OHLC"):
            MarketBar(
                symbol="SPY", provider="alpaca", timeframe="5m",
                start_at=now, end_at=now + timedelta(minutes=5),
                received_at=now, quality=DataQuality.LIVE,
                is_complete=True, open=100, high=99, low=98, close=100,
            )


class ProviderHealthTests(unittest.TestCase):
    def test_health_requires_aware_timestamps(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            ProviderHealth(
                provider="angelone", connected=False, authenticated=False,
                checked_at=datetime.now(),
            )


if __name__ == "__main__":
    unittest.main()
