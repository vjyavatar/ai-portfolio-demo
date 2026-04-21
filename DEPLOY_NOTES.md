# Celesys deploy — April 21, 2026 (r14)

Incremental over r13. Only `api.py` changed. Three additions:

## 1. New endpoint: `/api/india-fundamentals?symbol=HDFCBANK`

Clean endpoint exposing the existing aggregated data from
`fetch_nse_stock_data()` — which already combines NSE + MoneyControl
+ Screener.in under the hood. This wasn't accessible as a standalone
endpoint; the Investor tab can now hit it directly to render a
fundamentals panel.

Response shape:
```json
{
  "success": true,
  "symbol": "HDFCBANK",
  "data": {
    "price": 1523.45, "companyName": "HDFC Bank Ltd",
    "sector": "Financial Services",
    "pe": 18.5, "pb": 2.8, "eps": 82.3, "bookValue": 545.2,
    "w52High": 1825.60, "w52Low": 1363.45,
    "mcap": 11500000000000, "dividendYield": 1.2,
    "roe": 17.8, "roce": 13.4, "debtToEquity": 5.2,
    "promoterHolding": 0, "fii": 52.3, "dii": 18.7,
    ...all fields aggregated from NSE + MoneyControl + Screener.in
  },
  "fetched_ts": 1729594823.5
}
```

Cache: 5min inside `fetch_nse_stock_data()` — fundamentals don't change
minute-to-minute, this is more than fast enough.

**What this is NOT for:** Active Trading. This endpoint is intended
for the Investor/Stock analysis tab. Call volume should be low (once
per stock the user examines), so there's no rate-limit exposure.

## 2. MoneyControl spot fallback for Indian stocks (Active Trading)

When NSE fails for an Indian stock (post-r13 we route all India stocks
through NSE; if NSE 429s or returns empty, the stock would drop).
Now we try MoneyControl's `priceapi.moneycontrol.com/pricefeed/nse/equitycash`
endpoint — which returns JSON spot/prev-close/52W for Indian stocks
reliably.

**What this gets you:** when NSE is briefly rate-limited, Indian stock
cards still show last-known spot instead of dropping. The card stays
**non-tradable** (`_chain_unavailable: true`) because MoneyControl
doesn't publish option chains — we do NOT fabricate a chain. This
matches the celesys "no fake assumptions" principle.

Side effect: Active Trading's `LAST-GOOD:` / `STALE:` state handling
works correctly because we're still returning `_chain_unavailable:
true` when chain data isn't real.

## 3. New endpoint: `/api/us-spot-fallback?symbol=NVDA`

Scrapes Google Finance's public HTML page for US spot + day range +
previous close. Used as a fallback when Yahoo returns 429 for a US
symbol. Does NOT return option chains (Google Finance has none).

Response shape:
```json
{
  "success": true,
  "symbol": "NVDA", "exchange": "NASDAQ",
  "spot": 128.45, "prev_close": 127.80,
  "day_high": 129.20, "day_low": 126.50,
  "source": "google_finance",
  "fetched_ts": 1729594823.5
}
```

**What this is for:** the NEXT session's US rate-limit work. With this
endpoint in place, we can later patch the US scanner to call it when
Yahoo returns 429 and keep showing "last-known price" on cards even
during Yahoo outages. Chains still require Yahoo — no alternative
exists for free — so cards during a Yahoo storm would show
`SPOT-ONLY` mode with the chain fields blank.

Not hooked into the scanner yet. Available as a standalone endpoint
so you can test it:
```
curl https://celesys.ai/api/us-spot-fallback?symbol=NVDA
```

## Architecture: what the data flow now looks like

### India options (Active Trading)
```
Request NIFTY / HDFCBANK / BANKBEES
  ↓
is_india? → try nse_options() [r10]
  ↓ (NSE success) → return real chain
  ↓ (NSE fail + is_india_index) → yfinance indices fallback for spot only
  ↓ (NSE fail + is_india stock) → MoneyControl spot fallback [r14 NEW]
    ↓ (MC success) → return spot only, _chain_unavailable:true
    ↓ (MC fail) → drop ticker honestly
```

### India fundamentals (Investor tab)
```
Request /api/india-fundamentals?symbol=X
  ↓
fetch_nse_stock_data(X) [unchanged, aggregates NSE+MC+Screener.in]
  ↓
Returns comprehensive {pe, pb, roe, roce, sector, financials...}
```

### US options (Active Trading)
```
Request NVDA / SPY / etc
  ↓
Not-India → Yahoo primary [existing]
  ↓ (Yahoo 429) → currently drops ticker
  
  [Next session] → call /api/us-spot-fallback (Google Finance)
  → return spot only, _chain_unavailable:true, card non-tradable
```

## Deploy

Only `api.py` changed. Push one file. No new dependencies.

## What to test after deploy

### India fundamentals endpoint
```
https://celesys.ai/api/india-fundamentals?symbol=HDFCBANK
https://celesys.ai/api/india-fundamentals?symbol=RELIANCE
https://celesys.ai/api/india-fundamentals?symbol=TCS
```
All three should return comprehensive data blobs. If a field is 0 or
null, that means all three sources (NSE + MC + Screener.in) couldn't
get it — not a bug, honest reflection of data availability.

### MoneyControl spot fallback
This only triggers when NSE fails for a stock. Hard to test directly
unless NSE rate-limits. You can verify the code path by watching
Render logs after r14 — look for `[OPTIONS-QUICK] ... NSE failed,
MoneyControl gave spot=...` lines if/when NSE has issues.

### Google Finance spot
```
https://celesys.ai/api/us-spot-fallback?symbol=NVDA
https://celesys.ai/api/us-spot-fallback?symbol=SPY
https://celesys.ai/api/us-spot-fallback?symbol=MU
```
Should return `{"success": true, "spot": 128.45, ...}`.

If any return `{"success": false, "error": "Google Finance scrape failed..."}`,
the HTML has changed — our regexes broke. Fix is one session of
re-reading their markup.

## Honest flags

1. **I didn't live-test any of this.** The MoneyControl endpoint shape
   I coded against is what the existing codebase already uses at line
   288 — that path has been working, so I'm confident the endpoint is
   real. Google Finance HTML scraping is the most fragile piece — their
   CSS class names (`YMlKec fxKbKc`, `P6K39c`) are minified and can
   change. First live hit will reveal whether my regexes work.

2. **MoneyControl and Screener.in are scrape targets** with no formal
   API. Screener.in specifically discourages scraping in their ToS.
   For personal research on a platform you own this is fine; if Celesys
   ever goes commercial you'd need licensed providers.

3. **`fetch_nse_stock_data()` already does the aggregation — I didn't
   audit every field it returns.** The `/api/india-fundamentals` endpoint
   exposes whatever that function produces. If a field is missing or
   wrongly-named, the fix is in `fetch_nse_stock_data` itself, which I
   didn't touch.

4. **The Google Finance spot fallback is NOT hooked into the Active
   Trading scanner yet.** It's available as a standalone endpoint so
   you can validate it works. Wiring it into the scanner so Yahoo
   429s automatically fall through to GF is the next session's work,
   along with the broader US rate-limit fix (aggressive pre-filter +
   chain caching).

5. **Rate limiting considerations for the new endpoints:**
   - `/api/india-fundamentals` — cached 5min per symbol, low volume
   - MoneyControl spot in options path — called only on NSE failure,
     cached inside nse_options normally; MC's own endpoint is quite
     tolerant
   - Google Finance spot — cached 60s per symbol, called only on Yahoo
     failure; GF is more tolerant than Yahoo but not infinite

## Known backlog (unchanged)

Scoring calibration, fair_value placeholder, score=50 default, ATR
default, 52W default. Plus the big open item: US Yahoo rate limits
— next session's focus.
