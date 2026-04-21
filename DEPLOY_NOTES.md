# Celesys deploy — April 21, 2026 (r13 HOTFIX)

Incremental over r12. Only `api.py` changed — one-line fix.

## The bug

Render logs after r12 deploy showed every single India ticker failing:

```
❌ NSE Options error: name 'sym' is not defined
[OPTIONS-QUICK] NIFTYBEES: NSE failed for India stock; Yahoo has no chain
[OPTIONS-QUICK] NIFTYBEES: NSE failed for India stock; Yahoo has no chain
...
[BOTTOM-NAV] ✅ IN: 0 scored in 6.5s, 0 buy
```

## The cause

`nse_options(symbol: str)` takes its parameter as `symbol`. At line 3954
the code used an undefined `sym` instead:

```python
_nse_lot = ALGO_INSTRUMENTS.get(sym, {}).get("lot", 1)  # NameError
```

This line is deep in the success path. **Before r10, only 5 indices
routed here (NIFTY/BANKNIFTY/SENSEX/FINNIFTY/MIDCPNIFTY). The code at
line 3954 for indices evaluates `ALGO_INSTRUMENTS.get(sym, {})` — if
`sym` is undefined Python raises NameError, BUT the outer try/except
at line 4081 swallows it silently and returns a result with
`"error": "name 'sym' is not defined"` AND empty fields. The indices
then fell through to the Yahoo fallback and that worked, so nobody
noticed the latent bug.**

r10 broadened India routing: every Indian stock+ETF (HDFCBANK, RELIANCE,
NIFTYBEES, etc.) now hits this code path. For stocks, the Yahoo fallback
doesn't exist — so the bug surfaces as "NSE failed → drop ticker" for
every single Indian symbol.

This is the same fracture pattern I've been flagging across this
project: two parts of code disagreeing about the same variable
(`symbol` vs `sym`) only kept working by accident because the failure
path happened to work elsewhere.

## The fix

Single-char change: `sym` → `symbol` at line 3954.

## What you'll see after deploy

India scans should start scoring real tickers again. Expected:
- NIFTY / BANKNIFTY / SENSEX: work via `option-chain-indices` endpoint
- HDFCBANK / RELIANCE / TCS / etc: work via `option-chain-equities` endpoint
- **ETFs (NIFTYBEES / BANKBEES / GOLDBEES / SILVERBEES / ITBEES / MOM50 /
  CPSE)**: may or may not work. NSE may not publish option chains for
  these — if they return empty from `option-chain-equities`, the r10
  India-stock short-circuit will still drop them (correct behavior).

If the India scan keeps showing 5-7 tickers instead of the full 47,
the difference is the ETFs that NSE doesn't list options for. That's
not a bug; it's honest "no option chain exists for this symbol". You
can either:
- Remove those ETF symbols from the `in_tickers` list in api.py (saves
  wasted scan time), or
- Leave them — they'll just silently drop and the scan stays correct.

## Everything else from r12 still applies

TradingView second-opinion integration, WhatsApp alerts, keep-last-good
cache, stuck-flag defense, NSE routing, everything.

## Deploy

Only `api.py` changed. Push one file. No new env vars, no rebuild
needed (nothing in requirements.txt changed).

## Honest flag

I'd been staring at this bug across multiple sessions without catching
it because the happy path for indices worked. It took the r10 broadening
+ live logs + your screenshot to expose it. This is exactly the kind
of fracture the recurring "contracts disagree between two pieces of
code" pattern produces. Adding a typedef-style docstring on
`nse_options` ("Param is `symbol` — do NOT shorten to `sym` inside
this function") would have prevented it. Worth a pass across the other
longer functions in api.py to inoculate against the same family of
bug.
