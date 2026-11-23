"""Drop-in replacement for the yfinance module.

Callers keep using Ticker.info, Ticker.history and download(). Every read goes
through market_data.layer, so a missing provider returns an empty dict or an
empty DataFrame instead of None.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

from market_data import layer

_OHLCV = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
_EMPTY_INSIDER = ["Insider", "Transaction", "Start Date", "Shares", "Value"]


def _empty(columns=_OHLCV) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _frame(bars: list) -> pd.DataFrame:
    if not bars:
        return _empty()
    rows = []
    index = []
    for bar in bars:
        stamp = bar.get("time")
        try:
            if isinstance(stamp, (int, float)):
                moment = datetime.fromtimestamp(float(stamp), timezone.utc)
            elif isinstance(stamp, str) and len(stamp) == 10:
                moment = datetime.strptime(stamp, "%Y-%m-%d")
            else:
                moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        close = bar.get("close")
        rows.append({
            "Open": bar.get("open") if bar.get("open") is not None else close,
            "High": bar.get("high") if bar.get("high") is not None else close,
            "Low": bar.get("low") if bar.get("low") is not None else close,
            "Close": close,
            "Adj Close": close,
            "Volume": bar.get("volume") or 0,
        })
        index.append(pd.Timestamp(moment))
    if not rows:
        return _empty()
    frame = pd.DataFrame(rows, index=pd.DatetimeIndex(index))
    frame.index.name = "Date"
    return frame.sort_index()


def _period_interval(period: str, interval: str) -> tuple[str, str]:
    interval_name = interval or "1d"
    if interval_name in {"1m", "5m", "15m", "60m", "1h"}:
        mapped = "60m" if interval_name == "1h" else interval_name
        return "5d", mapped
    return period or "1y", "1d"


def _roll_up(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    indexed = frame.sort_index()
    if getattr(indexed.index, "tz", None) is not None:
        indexed = indexed.tz_localize(None)
    aggregations = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Adj Close": "last",
        "Volume": "sum",
    }
    try:
        rolled = indexed.resample(rule).agg(aggregations).dropna(subset=["Close"])
    except ValueError:
        rolled = indexed.resample("M" if rule == "ME" else rule).agg(aggregations).dropna(subset=["Close"])
    try:
        rolled.attrs = dict(frame.attrs)
    except Exception:
        pass
    return rolled


class Ticker:
    def __init__(self, ticker, *args, **kwargs):
        self.ticker = str(ticker or "").strip()

    def _fund(self) -> dict:
        env = layer.fundamentals(self.ticker)
        data = env.get("data") if isinstance(env, dict) else None
        return data if isinstance(data, dict) else {}

    def history(self, period="1mo", interval="1d", start=None, end=None, **kwargs) -> pd.DataFrame:
        requested = str(interval or "1d")
        period_name, interval_name = _period_interval(str(period or "1y"), requested)
        region = kwargs.get("region")
        env = layer.candles(self.ticker, period=period_name, interval=interval_name, region=region)
        bars = env.get("data") if isinstance(env, dict) and isinstance(env.get("data"), list) else []
        frame = _frame(bars)
        if requested in {"1wk", "1w"}:
            frame = _roll_up(frame, "W-FRI")
        elif requested in {"1mo", "1month"}:
            frame = _roll_up(frame, "ME")
        try:
            frame.attrs["source"] = (env or {}).get("source")
            frame.attrs["as_of"] = (env or {}).get("as_of")
            frame.attrs["stale"] = bool((env or {}).get("stale"))
        except Exception:
            pass
        if start is not None or end is not None:
            try:
                frame = frame.loc[start:end]
            except Exception:
                pass
        return frame if isinstance(frame, pd.DataFrame) else _empty()

    @property
    def info(self) -> dict:
        return self._fund()

    @property
    def fast_info(self) -> dict:
        env = layer.quote(self.ticker)
        data = env.get("data") if isinstance(env, dict) else {}
        data = data or {}
        price = data.get("price") or 0
        prev = data.get("prev_close") or price
        return {
            "last_price": price,
            "lastPrice": price,
            "previous_close": prev,
            "previousClose": prev,
            "regularMarketPrice": price,
            "currency": data.get("currency"),
            "source": env.get("source") if isinstance(env, dict) else None,
        }

    def _statement(self) -> pd.DataFrame:
        return _empty(["2024"])

    @property
    def income_stmt(self):
        return self._statement()

    @property
    def quarterly_income_stmt(self):
        return self._statement()

    @property
    def balance_sheet(self):
        return self._statement()

    @property
    def quarterly_balance_sheet(self):
        return self._statement()

    @property
    def cashflow(self):
        return self._statement()

    @property
    def quarterly_cashflow(self):
        return self._statement()

    @property
    def financials(self):
        return self.income_stmt

    @property
    def quarterly_financials(self):
        return self.quarterly_income_stmt

    @property
    def earnings(self):
        return _empty()

    @property
    def quarterly_earnings(self):
        return _empty()

    @property
    def earnings_dates(self):
        info = self._fund()
        rows = info.get("_earnings_calendar") or []
        records = []
        index = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("date"):
                continue
            try:
                index.append(pd.Timestamp(row["date"]))
            except (TypeError, ValueError):
                continue
            records.append({"EPS Estimate": row.get("epsEstimate"), "Reported EPS": row.get("epsActual")})
        if not records:
            return _empty(["EPS Estimate", "Reported EPS"])
        return pd.DataFrame(records, index=pd.DatetimeIndex(index))

    @property
    def earnings_history(self):
        return self.earnings_dates

    @property
    def calendar(self) -> dict:
        info = self._fund()
        date = info.get("earningsDate")
        if not date:
            return {}
        try:
            parsed = datetime.strptime(str(date)[:10], "%Y-%m-%d")
        except ValueError:
            return {}
        return {"Earnings Date": [parsed]}

    @property
    def recommendations(self):
        info = self._fund()
        rows = info.get("_recommendations") or []
        if not rows:
            return _empty(["strongBuy", "buy", "hold", "sell", "strongSell"])
        return pd.DataFrame(rows)

    @property
    def analyst_price_targets(self) -> dict:
        info = self._fund()
        return {
            "current": info.get("currentPrice"),
            "mean": info.get("targetMeanPrice"),
            "high": info.get("targetHighPrice"),
            "low": info.get("targetLowPrice"),
        }

    @property
    def insider_transactions(self):
        return _empty(_EMPTY_INSIDER)

    @property
    def insider_purchases(self):
        return _empty()

    @property
    def institutional_holders(self):
        return _empty()

    @property
    def major_holders(self):
        return _empty()

    @property
    def mutualfund_holders(self):
        return _empty()

    @property
    def options(self):
        return ()

    def option_chain(self, date=None):
        return SimpleNamespace(calls=_empty(), puts=_empty())

    @property
    def news(self):
        env = layer.news(self.ticker)
        rows = env.get("data") if isinstance(env, dict) else []
        return rows if isinstance(rows, list) else []

    @property
    def dividends(self):
        return pd.Series(dtype=float)

    @property
    def splits(self):
        return pd.Series(dtype=float)

    @property
    def actions(self):
        return _empty()

    def get_news(self, *args, **kwargs):
        return self.news

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return _empty()


class Tickers:
    def __init__(self, tickers, *args, **kwargs):
        if isinstance(tickers, str):
            symbols = [part for part in tickers.replace(",", " ").split() if part]
        else:
            symbols = [str(part) for part in tickers]
        self.symbols = symbols
        self.tickers = {symbol: Ticker(symbol) for symbol in symbols}

    def history(self, **kwargs):
        return download(self.symbols, group_by="ticker", **kwargs)

    def __getattr__(self, name):
        return self.tickers.get(name)


def history_frame(symbol: str, period: str = "1y", interval: str = "1d", region: str | None = None) -> pd.DataFrame:
    """The one candle entry analysis routes use. Always a DataFrame, never None."""
    frame = Ticker(symbol).history(period=period, interval=interval, region=region)
    return frame if isinstance(frame, pd.DataFrame) else _empty()


def history_many(symbol: str, specs, region: str | None = None) -> dict:
    """Fetch several (period, interval) frames at once. They share the candle cache."""
    wanted = [(str(period or "1y"), str(interval or "1d")) for period, interval in list(specs or [])]
    if not wanted:
        return {}

    def one(spec):
        period, interval = spec
        return history_frame(symbol, period=period, interval=interval, region=region)

    if len(wanted) == 1:
        return {wanted[0]: one(wanted[0])}
    from concurrent.futures import ThreadPoolExecutor
    out = {}
    with ThreadPoolExecutor(max_workers=min(4, len(wanted))) as pool:
        jobs = {pool.submit(one, spec): spec for spec in wanted}
        for job, spec in jobs.items():
            try:
                out[spec] = job.result()
            except Exception:
                out[spec] = _empty()
    return out


def download(tickers="AAPL", period="1mo", interval="1d", group_by="column", threads=True, progress=False, start=None, end=None, region=None, **kwargs) -> pd.DataFrame:
    if region is None:
        region = kwargs.get("region")
    if isinstance(tickers, str):
        symbols = [part for part in tickers.replace(",", " ").split() if part]
    else:
        symbols = [str(part) for part in tickers if str(part).strip()]
    if not symbols:
        return _empty()
    # Scans share this helper. A candle chain per symbol filled the home strip's slots.
    book = layer.scan_quotes(symbols, region)
    frames = {}
    for symbol in symbols:
        row = book.get(symbol) or {}
        price = row.get("price") or 0
        if not price:
            continue
        prev = row.get("prev_close") or price
        volume = row.get("volume") or 0
        stamp = pd.Timestamp.now().normalize()
        frames[symbol] = pd.DataFrame(
            {
                "Open": [prev, price],
                "High": [max(prev, price), max(prev, price)],
                "Low": [min(prev, price), min(prev, price)],
                "Close": [prev, price],
                "Adj Close": [prev, price],
                "Volume": [volume, volume],
            },
            index=pd.DatetimeIndex([stamp - pd.Timedelta(days=1), stamp]),
        )
    usable = {symbol: frame for symbol, frame in frames.items() if isinstance(frame, pd.DataFrame) and not frame.empty}
    if not usable:
        return _empty()
    if len(symbols) == 1:
        return usable.get(symbols[0], _empty())
    if group_by == "ticker":
        pieces = []
        for symbol, frame in usable.items():
            copied = frame.copy()
            copied.columns = pd.MultiIndex.from_product([[symbol], copied.columns])
            pieces.append(copied)
        return pd.concat(pieces, axis=1).sort_index()
    pieces = []
    for symbol, frame in usable.items():
        copied = frame.copy()
        copied.columns = pd.MultiIndex.from_product([copied.columns, [symbol]])
        pieces.append(copied)
    return pd.concat(pieces, axis=1).sort_index()


def set_tz_cache_location(*args, **kwargs):
    return None
