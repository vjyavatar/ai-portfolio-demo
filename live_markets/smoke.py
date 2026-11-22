"""Hit the public providers once. Prints AAPL, RELIANCE and the index board."""
from __future__ import annotations

from live_markets.service import options, overview, research


def main() -> int:
    board = overview()
    names = [row["name"] for row in board.get("indices") or []]
    print("indices", len(names), ",".join(names))
    if not board.get("success"):
        print("overview failed", board.get("warnings"))
        return 1
    needed = {"S&P 500", "NASDAQ", "DOW", "NIFTY 50", "SENSEX", "BANKNIFTY"}
    missing = needed - set(names)
    if missing:
        print("missing indices", sorted(missing))
        return 1
    for symbol, region in (("AAPL", "US"), ("RELIANCE.NS", "IN"), ("RELIANCE", "IN")):
        row = research(symbol, region)
        if not row.get("success") or not row.get("price"):
            print("quote failed", symbol, row.get("error"))
            return 1
        verdict = row.get("verdict") or {}
        print(
            symbol,
            row["price"],
            row.get("change_pct"),
            row.get("volume"),
            row.get("quality"),
            row.get("session"),
            row.get("provider"),
            verdict.get("label"),
            verdict.get("score"),
        )
    chain = options("AAPL", "US")
    available = (chain.get("chain") or {}).get("available")
    print("AAPL options", available, (chain.get("chain") or {}).get("provider"), (chain.get("chain") or {}).get("expiry"))
    if not available:
        print("US option chain did not load")
        return 1
    india = options("NIFTY", "IN")
    print("NIFTY options", (india.get("chain") or {}).get("available"), (india.get("chain") or {}).get("reason") or (india.get("chain") or {}).get("provider"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
