"""Live smoke for Research and Trading data after Yahoo removal.

Prints a markdown table of symbol, persona, source, latency and whether the
key fields arrived. Sunday sessions are closed, so last-close prices are expected.
"""
from __future__ import annotations

import json
import time

from market_data.layer import bundle, chart_payload
from trading_research import analyze_chart

SYMBOLS = [
    ("MU", "US"),
    ("AAPL", "US"),
    ("NVDA", "US"),
    ("RELIANCE", "IN"),
    ("TCS", "IN"),
    ("KAYNES", "IN"),
    ("NIFTY", "IN"),
]
FIELDS = ("trailingPE", "grossMargins", "profitMargins", "returnOnEquity")


def research_row(symbol: str, region: str) -> dict:
    started = time.perf_counter()
    token = symbol if region == "US" or symbol in {"NIFTY", "BANKNIFTY"} else f"{symbol}.NS"
    if symbol == "NIFTY":
        token = "NIFTY"
    payload = bundle(token, region)
    elapsed = time.perf_counter() - started
    fund = payload.get("fundamentals") or {}
    quote = payload.get("quote") or {}
    candles = payload.get("candles") or {}
    info = fund.get("data") or {}
    present = [name for name in FIELDS if info.get(name)]
    sources = info.get("_metric_sources") or {}
    source_names = sorted({item.get("source") for item in sources.values() if isinstance(item, dict) and item.get("source")})
    price = (quote.get("data") or {}).get("price")
    bars = candles.get("data") if isinstance(candles.get("data"), list) else []
    return {
        "endpoint": f"Research {symbol}",
        "before": "Yahoo Finance",
        "after": (", ".join(source_names) or fund.get("source") or "unavailable") + f" / candles {candles.get('source') or 'none'}",
        "latency_s": round(elapsed, 2),
        "price": price,
        "bars": len(bars),
        "fields": f"{len(present)}/{len(FIELDS)}",
        "stale": bool(fund.get("stale") or quote.get("stale")),
        "ok": bool(price) and len(bars) >= 50 and (symbol == "NIFTY" or len(present) >= 3),
    }


def trading_row(symbol: str, region: str) -> dict:
    started = time.perf_counter()
    provider_symbol = symbol if region == "US" else ("^NSEI" if symbol == "NIFTY" else f"{symbol}.NS")
    payload = chart_payload(provider_symbol, range="5d", interval="5m", region=region)
    report = analyze_chart(payload, symbol if symbol != "NIFTY" else "NIFTY", region, time.time())
    elapsed = time.perf_counter() - started
    meta = (((payload.get("chart") or {}).get("result") or [{}])[0].get("meta") or {})
    return {
        "endpoint": f"Trading {symbol}",
        "before": "Yahoo Finance chart",
        "after": (meta.get("source") or report.get("source") or "unavailable") + " quote",
        "latency_s": round(elapsed, 2),
        "price": report.get("price") or meta.get("regularMarketPrice"),
        "bars": len(report.get("bars") or []),
        "fields": report.get("verdict"),
        "stale": bool(meta.get("stale")),
        "ok": bool(report.get("price") or meta.get("regularMarketPrice")),
    }


def main() -> int:
    rows = []
    for symbol, region in SYMBOLS:
        rows.append(research_row(symbol, region))
        rows.append(trading_row(symbol, region))
    print("| endpoint | before | after source | latency | price | bars | check | stale |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    failed = 0
    for row in rows:
        if not row["ok"]:
            failed += 1
        print(
            f"| {row['endpoint']} | {row['before']} | {row['after']} | {row['latency_s']}s "
            f"| {row['price']} | {row['bars']} | {row['fields']} | {row['stale']} |"
        )
    print(json.dumps({"failed": failed, "rows": len(rows)}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
