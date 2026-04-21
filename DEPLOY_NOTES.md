# Celesys deploy — April 21, 2026 (r11)

Incremental over r10. Only `api.py` changed. Adds WhatsApp alerts via
Meta Cloud API, plus a new doc `docs/WHATSAPP_ALERTS_SETUP.md` with the
step-by-step Meta onboarding guide.

## What's new in r11

### WhatsApp alert system

Fires a Meta Cloud API WhatsApp message to your configured recipient
when a bottom-nav scan produces A-grade or A+ signals. Gated by:

1. Score ≥ 75 AND confidence ≥ 80 (A threshold) or ≥ 85/85 (A+)
2. Action is `BUY CALL` or `BUY PUT` — not HOLD or AVOID
3. Scan is fresh (not on `_last_scan_empty` keep-last-good branch)
4. Per-symbol 30-minute cooldown (bypassed when grade upgrades A → A+)
5. `CELESYS_ALERTS_ENABLED=1` env var is set

Expected frequency: 5-15 alerts/day across IN+US during market hours.

### New env vars (all 4 required)

| Variable | Purpose |
|---|---|
| `CELESYS_ALERTS_ENABLED` | Master switch. Set to `1` to enable. |
| `META_WABA_PHONE_ID` | Meta WABA phone number ID (digits, from app dashboard) |
| `META_WABA_TOKEN` | Access token (temp 24h for test, system-user for prod) |
| `META_WABA_RECIPIENT` | Your WhatsApp number — `919177577022` (no `+`) |

Without all 4 set, the `_alert_send_whatsapp` function returns
`(False, "env vars missing...")` and does nothing. Scan pipeline
continues normally.

### New endpoint: `/api/alert-test`

Fires a diagnostic "🧪 Celesys alert test" message that bypasses
grade and cooldown gates. Returns JSON with:
- `config_check`: which env vars are present
- `send_result`: raw Meta API response (or error string)
- `success`: true/false

Use this to verify Meta Cloud API setup BEFORE waiting for real signals.

### Docs

`docs/WHATSAPP_ALERTS_SETUP.md` has the full Meta onboarding walkthrough
including screenshots references, token types, and common error codes.

## Everything from r10 still applies

NSE routing for Indian stocks, stuck-flag defense, keep-last-good cache,
longer TTLs, `_stale` flag in response, light theme, horizontal TOP
TRADES strip, big card typography, everything from r9 and below.

## Deploy

Only `api.py` changed vs r10. If r10 is live, push just that file.
Then set the 4 new env vars in Render and rebuild.

## What to test

**Order of operations:**

1. Deploy api.py (no env vars yet — alerts stay off)
2. Hit `https://celesys.ai/api/alert-test` → should return
   `success: false, send_result: "env vars missing..."`
   (confirms the endpoint works and CELESYS_ALERTS_ENABLED is off)
3. Follow `docs/WHATSAPP_ALERTS_SETUP.md` to provision Meta app +
   verify your number
4. Set 4 env vars on Render, rebuild
5. Hit `/api/alert-test` again → should return `success: true` AND
   you receive a WhatsApp message
6. Wait for real alerts to fire during market hours

## Honest flags

1. **I cannot test this end-to-end.** My sandbox has no access to
   Meta's API. The HTTP call path is coded defensively (8s timeout,
   all errors swallowed and logged) but if Meta's API shape has
   changed from what I coded against, you'll see the mismatch in the
   `/api/alert-test` response. Fix would be one small session once
   we see the actual error string.

2. **24-hour window rule.** Meta's policy: freeform messages work
   only within 24h of the recipient's last message. First time you
   wire this up, send "hi" from your WhatsApp to the Meta test number
   to open the window. For sustained alerting beyond 24h of silence,
   you'd need to implement template messages (not built yet). Easy
   workaround: reply to any alert to reset the window.

3. **Temporary token expiry.** If you use the 24h temp token from
   Meta's getting-started page, alerts will silently fail 24 hours
   later with `HTTP 401`. For production reliability, get a permanent
   system-user token. Doc explains the steps.

4. **No delivery confirmation.** We check HTTP 200 from Meta, but if
   your phone is offline for days, messages queue server-side with no
   signal back to us. Acceptable for this use case; worth knowing.

5. **Grade detection uses `ticker.get("score")` with a
   `confidence_score` fallback.** If your scanner's output schema
   differs slightly per region (e.g. US returns `score`, IN returns
   `confidence_score`), the primary `score` field should work. If
   zero alerts fire on a day with known A-grade signals, dump one
   response from `/api/bottom-nav-scan?region=IN` and check the
   actual field names vs what `_alert_should_send` expects.

6. **Message format uses the trigger formula `spot * 1.002` for CE /
   `spot * 0.998` for PE.** This matches the spot-based trigger
   redesign from earlier sessions. If the scanner ever sends an
   explicit `trigger_spot` field, I should prefer that over
   recalculating — didn't see it in the current response shape so
   left the local calc. Verify on first real alert that the entry
   price matches what the UI card shows for the same trade.

## Known backlog (unchanged)

Scoring calibration, fair_value placeholder, score=50 default, ATR
default, 52W default.
