# 360 Decision Engine — Engineering Validation Report

**Build:** r63.110.8 · **Engine:** `decision_360_v2` (`/api/decision-360`)
**Date:** 2026-06-07 · **Method:** execution-based (real shipped code extracted from `api.py` / `static/app.js`)
**Scope:** backend math + helpers, endpoint control flow, frontend decision helpers + render.

---

## 1. Final Verdict

**APPROVED WITH CONDITIONS.**

All logic within the execution boundary passed (39/39 checks after fix). One genuine defect
was found and fixed during this review (RSI dead-flat → see Risk Register R-1). The single
condition is the **live network path**, which cannot be executed in the validation
environment and must be confirmed in the runtime (see §6).

---

## 2. Test Matrix (executed)

| # | Category | Case | Result |
|---|----------|------|--------|
| F-1 | Functional | Uptrend (n=200): trend=Up, RSI=100, finite | PASS |
| F-2 | Functional | Downtrend (n=200): trend=Down, RSI=0 | PASS |
| F-3 | Functional | Sideways (n=120) | PASS |
| F-4 | Functional | Minimum length (n=60): no sma200, no 6-mo return | PASS |
| F-5 | Functional | High-volatility series | PASS |
| F-6 | Functional | V-shape reversal | PASS |
| E-1 | Edge | Dead-flat (all identical) — no exception, finite | PASS |
| E-2 | Edge | Monotonic up (zero losses) | PASS |
| E-3 | Edge | Monotonic down (zero gains) | PASS |
| C-1 | Correctness | RSI of Wilder reference seq ≈ 70.5 | PASS |
| C-2 | Correctness | RSI dead-flat = 50 (neutral) — *after fix* | PASS |
| C-3 | Correctness | RSI monotonic up=100 / down=0 | PASS |
| C-4 | Correctness | RSI too-short (n<15) = None | PASS |
| C-5 | Correctness | FVG fires on constructed unfilled bullish gap | PASS |
| C-6 | Correctness | FVG returns None on flat (no gap) | PASS |
| N-1 | Negative/FE | `_dec360TechDec({})` empty → NEUTRAL, no crash | PASS |
| N-2 | Negative/FE | TechDec all-undefined fields → NEUTRAL | PASS |
| N-3 | Negative/FE | MacroDec null / undefined regime → UNKNOWN | PASS |
| N-4 | Negative/FE | FundDec null / partial / risky | PASS |
| N-5 | Negative/FE | StratDec empty / undefined → SET TOGGLES | PASS |
| M-1 | Functional/FE | Combined matrix: pos+pos → LEAN CONSTRUCTIVE (+pending note) | PASS |
| M-2 | Functional/FE | Combined: weak-tech override → WAIT/AVOID | PASS |
| M-3 | Functional/FE | Combined: caution×4 → LEAN CAUTIOUS | PASS |
| M-4 | Functional/FE | Combined: pos + full data → LEAN CONSTRUCTIVE | PASS |
| R-1..6 | Render | `_renderDec360` × 6 edge states (±fundamentals, null RSI, no FVG, downtrend, IN region): 15 plain-English lines, 4 group decisions, no `undefined` | PASS |
| INT-1 | Integration | Fetch None → clean `success:false` error | PASS |
| INT-2 | Integration | <60 bars → guard error | PASS |
| INT-3 | Integration | Valid 200 bars → `success:true` | PASS |
| INT-4 | Integration | Engine tag = `decision_360_v2` | PASS |
| INT-5 | Integration | technical/macro/fundamentals keys present | PASS |
| INT-6 | Integration | Fundamentals honest-NULL when feed silent | PASS |
| INT-7 | Integration | region `in` → `IN` + `.NS` symbol | PASS |
| INT-8 | Integration | Invalid region coerced to US | PASS |
| INT-9 | Integration | Empty symbol → error | PASS |
| REL-1 | Reliability | Idempotent (same input → identical output) | PASS |
| REL-2 | Reliability | No non-finite numbers in response | PASS |
| REL-3 | Reliability | Full response JSON-serializable | PASS |
| SEC-1 | Security | Render escapes symbol + backend strings (no raw `<script>`/`<img>`) | PASS |
| SEC-2 | Security | Malicious symbol does not crash endpoint | PASS |

**Totals:** 39 executed checks · 39 PASS · 0 open FAIL · 1 defect found & fixed in-cycle.

---

## 3. Traceability Matrix

| Requirement | Implementation | Verified by |
|-------------|----------------|-------------|
| Technical lens computed from price | endpoint sma/trend/zone/ATR/returns/rsi/fvg | F-1..F-6, C-1..C-6 |
| RSI correctness & bounds [0,100] | `_d360_rsi` | C-1..C-4 |
| FVG detection (ICT 3-candle) | `_d360_fvg` | C-5, C-6 |
| Fundamentals honest-NULL (never faked) | `_d360_fundamentals` + endpoint | INT-6 |
| Macro/region read from VIX regime | `_dec360MacroDec` + endpoint | N-3 |
| Per-lens group decisions + combined | `_dec360*Dec`, `_dec360Combined` | M-1..M-4, R-1..6 |
| Weak technicals override to WAIT/AVOID | `_dec360Combined` | M-2 |
| Incomplete lenses flagged pending | `_dec360Combined` | M-1, M-3 |
| Plain-English line per question | `_renderDec360` | R-1..6 (15 lines) |
| Insufficient-data guard (<60 bars) | endpoint | INT-2 |
| Graceful failure on feed outage | endpoint try/except | INT-1 |

---

## 4. Audit Review

- **Concurrency:** endpoint is async; uses `run_in_executor` + `asyncio.gather`; no shared mutable state → safe under parallel requests.
- **Idempotency:** deterministic pure math; verified identical output on repeat (REL-1).
- **Timeouts/Retry:** fetch bounded 12s; vix+fundamentals bounded 9s each via `wait_for`; failures fall back to defaults, not exceptions.
- **Failure handling:** None / <60-bar / network-error paths all return structured `success:false` (INT-1,2).
- **Memory/Scalability:** O(n) over ≤~252 bars; no accumulation across calls.
- **Observability:** response carries `_engine`, `data_note`, `asof`.
- **Security:** symbol is `.upper().strip()`, used only in yfinance ticker + f-string (no SQL/shell); all rendered values escaped via `_esc` (SEC-1); no XSS sink (SEC-2).
- **Honest-NULL:** fundamentals absent → `None`, excluded from claims; no fabricated defaults.

---

## 5. Production Readiness Checklist

- [x] Compiles (`py_compile`, `node --check`)
- [x] Deterministic / idempotent
- [x] Bounded timeouts on every network call
- [x] Graceful degradation on feed outage / thin data
- [x] No non-finite values in output; JSON-serializable
- [x] Input escaped at render (no XSS)
- [x] Honest-NULL for unavailable fundamentals
- [x] Versioned + cache-busted (r63.110.8 / v=63110801)
- [ ] **Live network path confirmed in runtime** — *pending (see Conditions §6)*

---

## 6. Risk Register

| ID | Severity | Risk | Status / Mitigation |
|----|----------|------|---------------------|
| R-1 | Medium | RSI returned 100 for a dead-flat (no-movement) window → mislabels neutral as overbought | **FIXED** r63.110.8: no-movement → 50; re-verified C-2 |
| R-2 | Low (condition) | Live yfinance fetch reachability / timeout behaviour not executable in validation env | Confirm in runtime; failure path already returns clean error (INT-1) |
| R-3 | Low | Fundamentals depend on `.info` (unreliable on host) | By design: honest-NULL; lens marked guided, excluded from combined (INT-6) |
| R-4 | Low | Stage/zone read uses ≤9-mo window; 200-DMA absent under 200 bars | Handled: `sma200=None`, trend label adapts (F-4) |
| R-5 | Informational | RS/FVG are price proxies, not true IBD RS-rating / exact institutional zones | Documented in `data_note`; not a defect |

---

## 7. Conditions for full APPROVED

1. Hard-refresh to r63.110.8 and run `/api/decision-360` against a live symbol (e.g. NVDA, MU) to confirm the fetch path and rendered output in the browser.
2. If the host's yfinance feed is blocked at runtime, the engine will return the INT-1 error path (verified) rather than fail — acceptable, but the technical lens will be empty until the feed is reachable.
