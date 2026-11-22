"""Cash-session clocks for NYSE/NASDAQ and NSE/BSE.

Regular hours only. Exchange holidays are not fully encoded; a weekday inside
the regular clock is reported as open on the regular schedule.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
IST = ZoneInfo("Asia/Kolkata")

NYSE_OPEN = time(9, 30)
NYSE_CLOSE = time(16, 0)
NYSE_PRE = time(4, 0)
NYSE_AFTER = time(20, 0)
NSE_OPEN = time(9, 15)
NSE_CLOSE = time(15, 30)


def _phase(local: datetime, open_at: time, close_at: time, pre: time | None = None, after: time | None = None) -> str:
    if local.weekday() >= 5:
        return "CLOSED"
    clock = local.time()
    if open_at <= clock < close_at:
        return "OPEN"
    if pre is not None and pre <= clock < open_at:
        return "PRE_MARKET"
    if after is not None and close_at <= clock < after:
        return "AFTER_HOURS"
    return "CLOSED"


def describe(now: datetime | None = None) -> dict:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    et = moment.astimezone(ET)
    ist = moment.astimezone(IST)
    us = _phase(et, NYSE_OPEN, NYSE_CLOSE, NYSE_PRE, NYSE_AFTER)
    india = _phase(ist, NSE_OPEN, NSE_CLOSE)
    return {
        "as_of": moment.isoformat(),
        "clocks": {
            "et": et.strftime("%Y-%m-%d %H:%M:%S ET"),
            "ist": ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        },
        "exchanges": {
            "US": {
                "venues": "NYSE / NASDAQ",
                "session": us,
                "regular_hours": "09:30–16:00 America/New_York",
                "holiday_calendar": "not fully encoded",
            },
            "IN": {
                "venues": "NSE / BSE",
                "session": india,
                "regular_hours": "09:15–15:30 Asia/Kolkata",
                "holiday_calendar": "not fully encoded",
            },
        },
        "note": "Weekends follow the clock above. A weekday holiday can still print as open on the regular schedule.",
    }


def session_for(region: str, now: datetime | None = None) -> str:
    board = describe(now)
    key = "IN" if (region or "").upper() == "IN" else "US"
    return board["exchanges"][key]["session"]
