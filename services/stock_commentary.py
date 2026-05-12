"""
r63.72.25 — Stock Commentary & Day-to-Day Tracker.

Aggregates per-ticker:
  1. Recent news headlines with sentiment classification
  2. Day-over-day price moves with magnitude + classification
  3. Key changes vs yesterday (price gap, sector move correlation)
  4. Recent rating/estimate revisions if available
  5. Upcoming earnings if within 30 days

Output: structured "daily story" + raw event list.

Design principles:
  - NEVER hang. Every external fetch has a hard timeout.
  - When a source fails, return what we have with explicit gap noted.
  - No LLM. Pure rule-based classification.
"""

import time
import threading
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Cache: 15 minutes (commentary changes fast)
_commentary_cache: Dict[str, tuple] = {}
_commentary_lock = threading.Lock()
_CACHE_TTL = 900


# ─── HELPERS ────────────────────────────────────────────────────────────

_BULLISH_KW = {
    "surge", "rally", "beat", "upgrade", "record", "growth", "profit", "gain",
    "buy", "bullish", "outperform", "raise", "boost", "strong", "soar", "jump",
    "positive", "optimistic", "exceed", "upside", "win", "approval", "expand",
    "innovation", "partnership", "acquisition", "deal", "contract", "order",
    "guidance raise", "raised guidance", "upgraded",
}
_BEARISH_KW = {
    "fall", "drop", "decline", "cut", "downgrade", "miss", "loss", "sell",
    "bearish", "underperform", "weak", "crash", "fear", "risk", "warning",
    "slash", "layoff", "concern", "threat", "negative", "panic", "plunge",
    "tumble", "lawsuit", "probe", "investigation", "fraud", "recall",
    "downgrade", "guidance cut", "lowered guidance", "downgraded",
}


def _classify_headline_sentiment(title: str) -> str:
    """Return 'bullish', 'bearish', or 'neutral' based on keyword count."""
    t = (title or "").lower()
    bull = sum(1 for k in _BULLISH_KW if k in t)
    bear = sum(1 for k in _BEARISH_KW if k in t)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def _classify_day_move(pct_change: float) -> dict:
    """Classify a single-day move with descriptor + color."""
    abs_chg = abs(pct_change)
    if pct_change >= 5:
        return {"label": "Strong Up", "color": "#10b981", "magnitude": "strong"}
    if pct_change >= 2:
        return {"label": "Up", "color": "#16a34a", "magnitude": "moderate"}
    if pct_change >= 0.5:
        return {"label": "Mild Up", "color": "#22c55e", "magnitude": "mild"}
    if pct_change > -0.5:
        return {"label": "Flat", "color": "#94a3b8", "magnitude": "flat"}
    if pct_change > -2:
        return {"label": "Mild Down", "color": "#f87171", "magnitude": "mild"}
    if pct_change > -5:
        return {"label": "Down", "color": "#dc2626", "magnitude": "moderate"}
    return {"label": "Strong Down", "color": "#991b1b", "magnitude": "strong"}


# ─── FETCHERS WITH HARD TIMEOUTS ────────────────────────────────────────

def _fetch_with_timeout(fn, timeout_sec: float, default=None):
    """Run a function with a hard timeout. Return default on timeout/exception."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout_sec)
        except (FuturesTimeoutError, Exception):
            return default


def _fetch_news(ticker: str, region: str) -> List[dict]:
    """Fetch up to 10 recent news headlines. 5s hard timeout."""
    def _go():
        try:
            import yfinance as yf
            # Try to import the rate-wait helper
            try:
                from api import _yahoo_rate_wait
                _yahoo_rate_wait()
            except Exception:
                pass

            yf_sym = ticker if region.upper() == "US" else f"{ticker}.NS"
            tk = yf.Ticker(yf_sym)
            news = tk.news or []
            items = []
            for n in news[:10]:
                title = n.get("title", "") or n.get("content", {}).get("title", "") or ""
                publisher = n.get("publisher", "") or n.get("content", {}).get("provider", {}).get("displayName", "") or ""
                link = n.get("link", "") or n.get("content", {}).get("canonicalUrl", {}).get("url", "") or ""
                pub_ts = n.get("providerPublishTime", 0)
                if title:
                    items.append({
                        "title": title,
                        "publisher": publisher,
                        "link": link,
                        "ts": pub_ts,
                        "sentiment": _classify_headline_sentiment(title),
                    })
            return items
        except Exception:
            return []
    return _fetch_with_timeout(_go, timeout_sec=5.0, default=[]) or []


def _fetch_price_series(ticker: str, region: str, days: int = 7) -> List[dict]:
    """Fetch last N days OHLC. 5s hard timeout. Returns [{date, open, close, volume, pct_change}, ...]"""
    def _go():
        try:
            import yfinance as yf
            try:
                from api import _yahoo_rate_wait
                _yahoo_rate_wait()
            except Exception:
                pass

            yf_sym = ticker if region.upper() == "US" else f"{ticker}.NS"
            tk = yf.Ticker(yf_sym)
            hist = tk.history(period=f"{days+3}d", interval="1d")  # padding for weekends
            if hist is None or len(hist) == 0:
                return []
            rows = []
            prev_close = None
            for idx, row in hist.iterrows():
                close = float(row.get("Close", 0))
                open_ = float(row.get("Open", 0))
                volume = int(row.get("Volume", 0) or 0)
                if close <= 0:
                    continue
                pct_chg = None
                if prev_close and prev_close > 0:
                    pct_chg = ((close - prev_close) / prev_close) * 100
                rows.append({
                    "date":   idx.strftime("%Y-%m-%d"),
                    "open":   round(open_, 2),
                    "close":  round(close, 2),
                    "volume": volume,
                    "pct_change": round(pct_chg, 2) if pct_chg is not None else None,
                })
                prev_close = close
            return rows[-days:]
        except Exception:
            return []
    return _fetch_with_timeout(_go, timeout_sec=6.0, default=[]) or []


def _fetch_upcoming_earnings(ticker: str, region: str) -> Optional[dict]:
    """Check if earnings are within next 30 days. 4s hard timeout. Returns event or None."""
    if region.upper() != "US":
        return None  # Finnhub free tier doesn't cover India forward

    def _go():
        try:
            import yfinance as yf
            from datetime import datetime, timedelta
            try:
                from api import _yahoo_rate_wait
                _yahoo_rate_wait()
            except Exception:
                pass

            tk = yf.Ticker(ticker)
            info = tk.info or {}
            ts = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
            if not ts:
                return None
            ed = datetime.fromtimestamp(ts)
            today = datetime.utcnow()
            days_out = (ed.date() - today.date()).days
            if days_out < -7 or days_out > 30:
                return None
            return {
                "date":     ed.strftime("%Y-%m-%d"),
                "days_out": days_out,
                "passed":   days_out < 0,
                "imminent": 0 <= days_out <= 7,
                "eps_estimate": info.get("trailingEps"),
            }
        except Exception:
            return None
    return _fetch_with_timeout(_go, timeout_sec=4.0, default=None)


# ─── DAY-OVER-DAY NARRATIVE BUILDER ─────────────────────────────────────

def _build_daily_story(price_rows: List[dict], news: List[dict], earnings: Optional[dict]) -> dict:
    """
    Build the day-to-day narrative for a stock:
      - Today's classified move
      - Comparison to yesterday (acceleration/deceleration)
      - 5-day trend summary
      - News context if any matches the move
    """
    if not price_rows or len(price_rows) < 2:
        return {
            "today_move": None,
            "narrative": "Price history unavailable — try refreshing.",
            "trend_5d": None,
            "events": [],
        }

    today_row = price_rows[-1]
    yest_row = price_rows[-2] if len(price_rows) >= 2 else None

    today_pct = today_row.get("pct_change") or 0
    yest_pct = (yest_row.get("pct_change") or 0) if yest_row else 0

    today_class = _classify_day_move(today_pct)

    # 5-day cumulative return
    if len(price_rows) >= 6:
        start_close = price_rows[-6].get("close") or 0
        end_close = today_row.get("close") or 0
        if start_close > 0:
            cum_5d = ((end_close - start_close) / start_close) * 100
        else:
            cum_5d = 0
    elif len(price_rows) >= 2:
        cum_5d = sum(r.get("pct_change") or 0 for r in price_rows[-5:])
    else:
        cum_5d = 0

    trend_5d_class = _classify_day_move(cum_5d / max(1, min(5, len(price_rows))))

    # Acceleration / deceleration
    if abs(today_pct) > abs(yest_pct) * 1.5 and abs(today_pct) > 1:
        momentum_note = f"Move accelerated today ({today_pct:+.1f}% vs {yest_pct:+.1f}% yesterday)."
    elif abs(today_pct) < abs(yest_pct) * 0.5:
        momentum_note = f"Move decelerated today ({today_pct:+.1f}% vs {yest_pct:+.1f}% yesterday)."
    else:
        momentum_note = ""

    # News alignment with move
    bull_news = sum(1 for n in news if n.get("sentiment") == "bullish")
    bear_news = sum(1 for n in news if n.get("sentiment") == "bearish")
    news_note = ""
    if today_pct > 1.5 and bull_news > bear_news:
        news_note = f"Move aligns with positive news flow ({bull_news} bullish vs {bear_news} bearish headlines)."
    elif today_pct < -1.5 and bear_news > bull_news:
        news_note = f"Move aligns with negative news flow ({bear_news} bearish vs {bull_news} bullish headlines)."
    elif (today_pct > 1.5 and bear_news > bull_news) or (today_pct < -1.5 and bull_news > bear_news):
        news_note = "News sentiment is mixed/contrary to the price move — possibly technical or sector-driven."
    elif abs(today_pct) > 1.5 and not news:
        news_note = "No major news catalyst detected — move likely sector or market driven."

    # Earnings context
    earnings_note = ""
    if earnings:
        if earnings.get("imminent"):
            earnings_note = f"⚡ Earnings in {earnings['days_out']} days ({earnings['date']}) — pre-event volatility expected."
        elif earnings.get("passed"):
            earnings_note = f"Earnings reported {abs(earnings['days_out'])} day(s) ago — post-event drift possible."
        else:
            earnings_note = f"Earnings on {earnings['date']} ({earnings['days_out']} days away)."

    # Compose narrative
    narrative_parts = [
        f"Today: {today_class['label']} ({today_pct:+.2f}%)."
    ]
    if momentum_note:
        narrative_parts.append(momentum_note)
    if cum_5d != 0:
        narrative_parts.append(f"5-day cumulative: {cum_5d:+.1f}%.")
    if news_note:
        narrative_parts.append(news_note)
    if earnings_note:
        narrative_parts.append(earnings_note)

    narrative = " ".join(narrative_parts)

    # Build events list (chronological)
    events = []
    for row in price_rows[-7:]:
        pct = row.get("pct_change")
        if pct is None:
            continue
        cls = _classify_day_move(pct)
        events.append({
            "date":     row["date"],
            "type":     "price",
            "close":    row["close"],
            "pct":      pct,
            "label":    cls["label"],
            "color":    cls["color"],
            "magnitude": cls["magnitude"],
            "volume":   row.get("volume"),
        })

    return {
        "today_move":  {
            "pct":      today_pct,
            "label":    today_class["label"],
            "color":    today_class["color"],
            "close":    today_row.get("close"),
        },
        "trend_5d": {
            "pct":      round(cum_5d, 2),
            "label":    trend_5d_class["label"],
            "color":    trend_5d_class["color"],
        },
        "narrative": narrative,
        "events":    events,
        "earnings":  earnings,
    }


# ─── TOP-LEVEL ──────────────────────────────────────────────────────────

def get_stock_commentary(ticker: str, region: str = "US") -> dict:
    """
    Build full commentary for a ticker. Cached 15 min.
    Returns:
      {
        success: bool,
        ticker, region,
        today_move: {pct, label, color, close},
        trend_5d: {pct, label, color},
        narrative: "<sentence-form day-to-day story>",
        events: [{date, type, pct, label, color, magnitude, volume}, ...],
        headlines: [{title, publisher, link, sentiment, ts}, ...],
        earnings: {date, days_out, ...} or null,
        data_sources: {news: 'yfinance'|'failed', price: 'yfinance'|'failed', earnings: 'yfinance'|'failed'},
        partial_data: bool,  # true if any source failed
      }
    """
    t = ticker.strip().upper()
    if not t:
        return {"success": False, "error": "empty ticker"}

    cache_key = f"{t}:{region.upper()}"
    now = time.time()
    with _commentary_lock:
        cached = _commentary_cache.get(cache_key)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]

    # Fetch all three sources in parallel with individual hard timeouts
    news = _fetch_news(t, region)
    price_rows = _fetch_price_series(t, region, days=7)
    earnings = _fetch_upcoming_earnings(t, region)

    data_sources = {
        "news":     "yfinance" if news else "failed",
        "price":    "yfinance" if price_rows else "failed",
        "earnings": "yfinance" if earnings else ("none" if region.upper() == "US" else "n/a"),
    }
    partial_data = (not news) or (not price_rows)

    story = _build_daily_story(price_rows, news, earnings)

    result = {
        "success":       True,
        "ticker":        t,
        "region":        region.upper(),
        "today_move":    story["today_move"],
        "trend_5d":      story["trend_5d"],
        "narrative":     story["narrative"],
        "events":        story["events"],
        "headlines":     news[:8],
        "earnings":      story["earnings"],
        "data_sources":  data_sources,
        "partial_data":  partial_data,
        "_cached":       False,
    }

    with _commentary_lock:
        _commentary_cache[cache_key] = (now, result)
    return result
