# Trading and access upgrade — 12 October 2026

## Delivered without replacing existing features

The original reports, charts, 50-menu directory and voice integration remain. The homepage now includes a collapsible trading watchlist: up to six India or US symbols, paced requests, five-minute scan boundaries, source timestamps, real closed-bar sparklines, explicit WAIT results and a direct path to the existing option-chain controls. It stops when hidden, on logout, on market/watchlist changes or when access is denied. It does not run with the browser closed or place orders.

Voice is opt-in. It announces changed research candidates and invalidations, not every refresh. Stop clears pending speech; the global voice toggle remains authoritative. The scanner uses the existing closed-bar research engine; it does not assign invented win probabilities or choose random trades.

## Strategy review

Existing criteria: 21 completed five-minute bars; verified session; EMA 9/20 and session VWAP; a close beyond the previous three bars; relative volume at least 1.2; distance from VWAP at most three ATR; and a current quote still consistent with the setup. Freshness, gaps and invalid bar checks are retained. This is a specific research rule set, not evidence of profitability. The 21-bar warm-up excludes the first 105 minutes. Event-calendar verification and independent out-of-sample performance remain absent. An opening-range strategy should be separately backtested, including costs, before activation.

Critical correction: removed five synthetic-history fallback blocks in the existing algorithm and stock-intelligence engines. A current NSE/Google spot quote no longer becomes 60 invented historical price/volume bars. Genuine-history failure returns insufficient data. Labelled Monte Carlo simulations are unaffected.

## Security changes and limits

- Removed cross-account session fallback from `check_premium_gate`: an unrelated caller cannot inherit another member's active session.
- Restricted credentialed CORS origins to the owned HTTPS domain and www host.
- Added no-sniff, same-origin framing/referrer headers and no-store responses for protected/account paths.
- Added verified-email OTP flow, origin checks, bounded attempts, single-use expiring challenges, signed Secure/HttpOnly/SameSite cookies, two-hour sessions, logout revocation and server-side tier enforcement.
- Private provider adapters require a verified authorized session even when legacy compatibility mode is active.
- Existing email-only access remains **compatibility mode** until SMTP delivery is configured and verified enforcement is enabled. Email strings and hidden menus alone are not authentication. This release does not claim complete production authentication or an exhaustive security audit.
- Enforcement discovers existing tier-gated API routes and evaluates them before the handler. A complete independent authorization review of every route and data object remains outstanding.
- OTP/session/rate-limit state is in memory for one server process. Restart invalidates sessions. Multiple workers/replicas require a shared session/rate-limit store before use.

## Operator setup (credentials belong in Render secrets, never source or chat)

Verified sign-in:

| Environment variable | Purpose |
|---|---|
| CELESYS_AUTH_SECRET | Random secret, at least 32 characters |
| CELESYS_SMTP_HOST | SMTP-over-TLS service hostname |
| CELESYS_SMTP_PORT | TLS port; default 465 |
| CELESYS_SMTP_USER / CELESYS_SMTP_PASSWORD | Email-service credentials |
| CELESYS_SMTP_FROM | Verified sender address |
| CELESYS_SITE_ORIGIN | Default https://celesys.ai |
| CELESYS_AUTH_ENFORCE | Set true after testing owner sign-in and tier access |

First configure delivery and secret; use the homepage code flow to verify access, then enable enforcement and retest public, trading and dream profiles. No email was sent and no provider token was accessed during this implementation.

India feed: `CELESYS_DHAN_ACCESS_TOKEN`, `CELESYS_DHAN_CLIENT_ID`, `CELESYS_DHAN_INSTRUMENTS_JSON`, and `CELESYS_LICENSED_OPTIONS_IN=true`. The mapping is an object keyed by symbol with `id` (verified positive underlying security ID) and `segment` (`IDX_I`, `NSE_EQ` or `BSE_EQ`). Obtain mappings from the current Dhan instrument master. Do not guess index or contract IDs/lot sizes.

US feed: `CELESYS_OPTIONS_DATA_TOKEN` (Tradier brokerage token) and `CELESYS_LICENSED_OPTIONS_US=true`.

The licensed-display switches are an operator confirmation that the configured feed may be shown to the authorized audience. They are not entitlement checks performed by Celesys. Credentials and entitlement activation are still required; real-time connectivity has not been verified. When a verified session and configured feed exist, the existing homepage chain automatically uses the private adapter. Other users retain the prior public snapshot path. Fetch time is never substituted for quote time. Dhan responses without per-quote timestamps remain freshness-unverified; Tradier Greeks may be older than quotes.

## Primary documentation reviewed

- [Dhan option-chain API and pacing](https://dhanhq.co/docs/v2/option-chain/)
- [Dhan instrument master and security IDs](https://dhanhq.co/docs/v2/instruments/)
- [Tradier market-data account requirements, delayed data and Greek frequency](https://docs.tradier.com/docs/market-data)
- [OWASP authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

## Validation

181 focused regressions, including 12 new security/provider checks and eight scanner checks. These test OTP replay/attempt limits, cookie tampering, logout, wrong-origin requests, supplied-email bypass under enforcement, cross-user session isolation, missing-versus-zero data, removal of synthetic history, sequential scans, five-minute cadence, hidden-tab cancellation and voice opt-in/freshness.

Browser visual/audio execution, actual email delivery, credentialed provider calls and independent reconciliation/backtesting remain unverified. This is targeted source review and regression coverage, not a claim that every line or financial output has been certified.
