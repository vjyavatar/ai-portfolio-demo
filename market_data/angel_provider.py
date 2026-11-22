"""Angel One SmartAPI read-only quote/candle adapter using the session manager."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from .angel_session import AngelOneSession
from .base import MarketDataProvider
from .contracts import DataQuality, MarketBar, MarketQuote, ProviderHealth, utc_now


class AngelOneMarketData(MarketDataProvider):
    provider_name = "angelone"

    def __init__(self, session: Optional[AngelOneSession] = None):
        self.auth = session or AngelOneSession()
        raw = os.getenv("CELESYS_ANGEL_INSTRUMENTS_JSON", "{}")
        try:
            parsed = json.loads(raw)
            self.instruments = parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            self.instruments = {}
        self._last_message = None
        self._connected = False
        self._symbols: set[str] = set()
        self._last_error = None

    def _ensure_session(self):
        if not self.auth.jwt:
            self.auth.login()
        elif not self.auth.verify():
            self.auth.refresh()
            if not self.auth.verify():
                self.auth.close()
                self.auth.login()

    def _request(self, path: str, payload: dict) -> dict:
        self._ensure_session()
        headers = self.auth._headers()
        headers["Authorization"] = "Bearer " + str(self.auth.jwt)
        response = self.auth.http.post(
            "https://apiconnect.angelone.in/rest/secure/angelbroking/" + path,
            json=payload, headers=headers, timeout=(3.05, 12),
        )
        if response.status_code == 401:
            self.auth.refresh()
            headers["Authorization"] = "Bearer " + str(self.auth.jwt)
            response = self.auth.http.post(
                "https://apiconnect.angelone.in/rest/secure/angelbroking/" + path,
                json=payload, headers=headers, timeout=(3.05, 12),
            )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("status") is not True:
            raise RuntimeError("Angel One market-data request rejected")
        self._connected = True
        self._last_message = utc_now()
        self._last_error = None
        return data

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.provider_name, connected=self._connected,
            authenticated=bool(self.auth.jwt and self._connected),
            checked_at=utc_now(), last_message_at=self._last_message,
            subscribed_symbols=len(self._symbols), last_error_code=self._last_error,
        )

    def get_quote(self, symbol: str) -> Optional[MarketQuote]:
        symbol = symbol.strip().upper()
        instrument = self.instruments.get(symbol)
        if not isinstance(instrument, dict):
            return None
        exchange, token = instrument.get("exchange"), str(instrument.get("token", ""))
        if exchange not in {"NSE", "BSE", "NFO", "BFO"} or not token.isdigit():
            return None
        payload = self._request("market/v1/quote/", {
            "mode": "FULL", "exchangeTokens": {exchange: [token]},
        })
        data = payload.get("data") or {}
        rows = data.get("fetched") if isinstance(data, dict) else None
        if not isinstance(rows, list) or len(rows) != 1:
            return None
        row = rows[0]
        if str(row.get("symbolToken")) != token or row.get("exchange") != exchange:
            return None
        stamp_raw = row.get("exchFeedTime")
        if not isinstance(stamp_raw, str):
            return None
        try:
            stamp = datetime.strptime(stamp_raw, "%d-%b-%Y %H:%M:%S").replace(
                tzinfo=timezone(timedelta(hours=5, minutes=30))
            ).astimezone(timezone.utc)
        except ValueError:
            return None
        age = (utc_now() - stamp).total_seconds()
        quality = DataQuality.LIVE if 0 <= age <= 15 else DataQuality.STALE
        depth = row.get("depth") or {}
        def best(side, choose):
            levels = depth.get(side) if isinstance(depth, dict) else None
            vals = []
            for item in levels if isinstance(levels, list) else []:
                try:
                    price, qty = float(item["price"]), float(item["quantity"])
                    if price > 0 and qty > 0:
                        vals.append((price, qty))
                except (KeyError, TypeError, ValueError):
                    continue
            return choose(vals) if vals else (None, None)
        bid, _ = best("buy", max)
        ask, _ = best("sell", min)
        if bid is not None and ask is not None and bid > ask:
            bid = ask = None
        currency = str(instrument.get("currency", "INR")).upper()
        return MarketQuote(
            symbol=symbol, provider=self.provider_name, asset_class=str(instrument.get("asset_class", "equity")),
            currency=currency, received_at=utc_now(), quality=quality,
            bid=bid, ask=ask, last=row.get("ltp"),
            bid_at=stamp if bid is not None else None, ask_at=stamp if ask is not None else None,
            last_at=stamp, volume=row.get("tradeVolume"), open_interest=row.get("opnInterest"),
        )

    def get_bars(self, symbol: str, timeframe: str, limit: int = 100) -> list[MarketBar]:
        instrument = self.instruments.get(symbol.strip().upper())
        intervals = {"1m": "ONE_MINUTE", "5m": "FIVE_MINUTE", "15m": "FIFTEEN_MINUTE",
                     "1h": "ONE_HOUR", "1d": "ONE_DAY"}
        if not isinstance(instrument, dict) or timeframe not in intervals:
            return []
        if not 1 <= int(limit) <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        now = utc_now()
        start = now - timedelta(days=5 if timeframe != "1d" else 365)
        payload = self._request("historical/v1/getCandleData", {
            "exchange": instrument["exchange"], "symboltoken": str(instrument["token"]),
            "interval": intervals[timeframe],
            "fromdate": start.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M"),
            "todate": now.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M"),
        })
        rows = (payload.get("data") or [])
        seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}[timeframe]
        result = []
        for row in rows[-int(limit):]:
            if not isinstance(row, list) or len(row) < 6:
                continue
            stamp = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
            stamp = stamp.astimezone(timezone.utc)
            end = stamp + timedelta(seconds=seconds)
            complete = end <= now
            result.append(MarketBar(
                symbol=symbol.strip().upper(), provider=self.provider_name, timeframe=timeframe,
                start_at=stamp, end_at=end, received_at=now,
                quality=DataQuality.LIVE if complete else DataQuality.STALE,
                is_complete=complete, open=row[1], high=row[2], low=row[3],
                close=row[4], volume=row[5],
            ))
        return result

    def subscribe(self, symbols: Iterable[str]) -> None:
        normalized = {str(s).strip().upper() for s in symbols if str(s).strip()}
        if len(normalized) > 1000:
            raise ValueError("watchlist exceeds the 1000-symbol safety cap")
        self._symbols = normalized

    def close(self) -> None:
        self.auth.close()
        self.auth.http.close()
        self._connected = False
