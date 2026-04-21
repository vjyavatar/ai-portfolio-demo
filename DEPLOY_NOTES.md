# Celesys deploy — April 21, 2026 (r12)

Incremental over r11. Three files changed: `api.py`, `requirements.txt`,
`static/active-trading.js`.

## What's new in r12: TradingView second-opinion integration

Every A/A+ signal Celesys produces now gets a silent background fetch from
TradingView's technical-analysis endpoint as a sanity check. If TV agrees,
fine. If TV disagrees — that's the signal worth paying attention to.

### Backend (`api.py`)

Self-contained TradingView module added between the alert module and
`_score_one_ticker`:

- `_tv_resolve_symbol(sym, reg)` — maps your scan universe to TV exchanges.
  India: `NSE:NIFTY`, `NSE:HDFCBANK`, etc. US has a full exchange table
  (NASDAQ/NYSE/AMEX) for the ~100 symbols we scan.
- `_tv_get_opinion(sym, reg, interval)` — fetches TV's technical analysis
  via the `tradingview-ta` PyPI library. 5-minute per-symbol cache.
  Returns normalized dict with verdict + oscillator breakdown + MA breakdown.
  Every failure returns None and logs; never crashes.
- `_tv_agreement_flag(action, verdict)` — compares Celesys BUY CALL vs TV's
  BUY/STRONG_BUY → AGREE, vs SELL → DISAGREE, vs NEUTRAL → PARTIAL.
- `_tv_enrich_results(results, reg)` — attaches `_tv_opinion` and
  `_tv_agreement` to each A/A+ ticker. Called inside `_run_bottom_nav_scan`
  BEFORE cache commit so frontend receives enriched data.

### Alert messages include TV opinion

WhatsApp alerts (r11) now append one of these lines when enrichment ran:
- `TV confirms: Strong Buy ✓`
- `⚠️ TV disagrees: Sell`
- `TV neutral (inconclusive)`

### New endpoint: `/api/tv-second-opinion`

On-demand fetch for the frontend button:
```
GET /api/tv-second-opinion?symbol=NIFTY&region=IN&interval=5m
```
Returns:
```json
{
  "success": true,
  "symbol": "NIFTY", "region": "IN", "interval": "5m",
  "tv_opinion": {
    "verdict": "BUY",
    "summary": {"buy": 14, "sell": 4, "neutral": 8},
    "oscillators": {...},
    "ma": {...},
    "exchange": "NSE", "interval": "5m",
    "fetched_ts": 1729594823.5
  }
}
```

### Frontend (`active-trading.js`)

New TV pill in each top-3 card's top bar, between confidence and button:
- **Green ✓ TV Buy** — TV agrees, setup looks clean from two angles
- **Red ✗ TV Sell** — TV disagrees, investigate before trading
- **Yellow ⁓ TV Neutral** — TV inconclusive, no confirmation
- **Gray `? TV`** — not yet enriched (ticker below A grade, or fetch failed).
  Click to force fetch via `/api/tv-second-opinion`.

Tooltip on hover shows full breakdown: summary B/S/N counts, oscillator
verdict, MA verdict.

Click any pill = fresh fetch, updates in place.

### requirements.txt

Added `tradingview-ta>=3.3.0`. This is the one dependency that matters —
Render must rebuild to pick it up.

## Timeframe choice: 5m

Per our prior decision: TV indicators use 5m to match your intraday
options horizon. If we ever add a swing-trading mode, that path would
pass `interval="1d"` instead. Daily indicators on a 5-minute-intent
card would always say "Strong Buy" on a trending stock and mislead you.

## Everything from r11 still applies

WhatsApp alerts, NSE stock routing, stuck-flag defense, keep-last-good
cache, `_stale` flag, light theme, big card typography, horizontal strip,
etc.

## Deploy

Three files changed. Deploy the whole zip. Render must rebuild to install
`tradingview-ta`.

## What to test after deploy

### 1. Does the library install?
Render build log should show `Collecting tradingview-ta` and
`Successfully installed tradingview-ta-3.3.0`. If it fails, the import
in api.py will log `[TV-OPINION] tradingview_ta not installed` and
all TV pills will stay gray with no data.

### 2. Does India work?
Open NIFTY in QT or wait for a top-3 card. Click the gray `? TV`
pill. Should flip to green/red/yellow with a real verdict within 3
seconds. If it stays gray, check logs for `[TV-OPINION] ❌ NIFTY`.

### 3. Does US work?
Same test on SPY / QQQ / NVDA.

### 4. Does an Indian stock work?
HDFCBANK or RELIANCE. My code assumes `NSE:HDFCBANK` works for TV.
If it fails, the exchange prefix may need to be `BSE:` for some
symbols — one-line fix.

### 5. Disagreement detection
Find a card where Celesys says BUY CALL but TV says SELL / STRONG_SELL.
Pill should be red ✗. Hover to see full breakdown. This is the case
r12 was built to surface.

## Honest flags

1. **`tradingview-ta` hits an undocumented endpoint.** TradingView can
   and does change this. When they do, the library usually gets patched
   within days. Meanwhile our code returns None gracefully — scans
   continue, cards just show gray TV pills. Not a fatal failure mode.

2. **I did not live-test any of this.** My sandbox has no network. The
   first real request will reveal whether:
   - `tradingview-ta` installs cleanly on Render (should)
   - NSE symbol routing works for Indian stocks (should)
   - 5m data is available from TV for all exchanges (might not during
     pre-market; falls back gracefully to None)

3. **TV rate limits are undocumented.** If we spam the endpoint, they
   may start returning 429s or block the IP. Our 5-minute per-symbol
   cache plus A-grade-only enrichment means realistic volume is ~5-15
   requests per scan × 1 scan per 3-5 min = low. If we start seeing
   429s in logs, first move is to raise `_TV_CACHE_TTL` from 300 to
   600 seconds.

4. **Only A/A+ tickers get enriched automatically.** Below-A signals
   don't fire TV calls. That's a cost-saving decision. If you want
   TV on every ticker the scanner sees, change `_tv_enrich_results`
   to drop the score/confidence check — but expect ~40-50 TV calls
   per scan instead of 3-5.

5. **Alert message length.** Adding the TV line grows the WhatsApp
   message by one line. Still well within Meta's 4096-char limit.

## Known backlog (unchanged)

Scoring calibration (OVERPRICED+WIDE+RANGING → BUY_SMALL),
`fair_value = price × 1.05`, score=50 default, ATR default, 52W default.
