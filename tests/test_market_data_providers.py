from datetime import datetime, timedelta, timezone

import pytest

from market_data.contracts import DataQuality
from market_data.providers import AlpacaMarketData


class Response:
    status_code = 200
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): pass
    def json(self): return self.payload


class Session:
    def __init__(self, payload): self.payload = payload; self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.payload)
    def close(self): pass


def test_alpaca_rejects_unsupported_feed():
    with pytest.raises(ValueError):
        AlpacaMarketData(key="k", secret="s", feed="auto")


def test_alpaca_quote_is_timestamped_and_two_sided():
    stamp = datetime.now(timezone.utc).isoformat()
    session = Session({"quote": {"t": stamp, "bp": 100.0, "ap": 100.1}})
    provider = AlpacaMarketData("key", "secret", "iex", session)
    quote = provider.get_quote("aapl")
    assert quote.symbol == "AAPL"
    assert quote.quality == DataQuality.LIVE
    assert quote.is_actionable_candidate
    assert session.calls[0][1]["params"]["feed"] == "iex"


def test_alpaca_missing_timestamp_never_creates_quote():
    session = Session({"quote": {"bp": 100, "ap": 101}})
    provider = AlpacaMarketData("key", "secret", "iex", session)
    assert provider.get_quote("AAPL") is None


def test_alpaca_bars_are_only_eligible_after_close():
    now = datetime.now(timezone.utc)
    old = (now - timedelta(minutes=6)).isoformat()
    current = (now - timedelta(minutes=2)).isoformat()
    session = Session({"bars": [
        {"t": old, "o": 10, "h": 12, "l": 9, "c": 11, "v": 100, "n": 4},
        {"t": current, "o": 11, "h": 12, "l": 10, "c": 11.5, "v": 20, "n": 2},
    ]})
    provider = AlpacaMarketData("key", "secret", "iex", session)
    bars = provider.get_bars("AAPL", "5m", 2)
    assert bars[0].signal_eligible
    assert not bars[1].signal_eligible
