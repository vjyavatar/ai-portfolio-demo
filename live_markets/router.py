"""HTTP routes for the live market board. Mounted from start.py."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from live_markets import service

router = APIRouter()
_PAGE = Path(__file__).with_name("markets.html")


def attach_live_markets(app) -> None:
    app.include_router(router)


@router.get("/markets", response_class=HTMLResponse)
def markets_page():
    return HTMLResponse(_PAGE.read_text(encoding="utf-8"))


@router.get("/api/live/health")
def live_health():
    return service.health()


@router.get("/api/live/sessions")
def live_sessions():
    return service.sessions.describe()


@router.get("/api/live/overview")
def live_overview():
    return service.overview()


@router.get("/api/live/quote")
def live_quote(symbol: str = "", region: str = ""):
    try:
        return service.quote(symbol, region or None)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "disclaimer": service.DISCLAIMER}


@router.get("/api/live/quotes")
def live_quotes(symbols: str = "", region: str = ""):
    try:
        return service.quotes(symbols, region or None)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "quotes": [], "disclaimer": service.DISCLAIMER}


@router.get("/api/live/verdict")
def live_verdict(symbol: str = "", region: str = ""):
    try:
        return service.research(symbol, region or None)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "disclaimer": service.DISCLAIMER}


@router.get("/api/live/screen")
def live_screen(market: str = "US"):
    return service.screen(market)


@router.get("/api/live/options")
def live_options(symbol: str = "AAPL", region: str = ""):
    try:
        return service.options(symbol, region or None)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "disclaimer": service.DISCLAIMER}


@router.get("/api/live/ticker")
def live_ticker():
    return service.ticker_payload()
