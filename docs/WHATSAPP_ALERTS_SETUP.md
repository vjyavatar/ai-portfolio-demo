# Celesys WhatsApp Alerts — Setup Guide

You're wiring up Meta WhatsApp Cloud API (free tier) to receive
Celesys A/A+ trade signals. This guide walks you through the Meta side.
The Celesys side is already coded in `api.py` — you just need to set
four environment variables.

## TL;DR

1. Create a Meta developer account + app
2. Add WhatsApp product to the app
3. Grab two credentials: `phone_number_id` and `access_token`
4. Add your phone `+919177577022` as a **verified test recipient**
5. Set 4 env vars on Render
6. Hit `GET /api/alert-test` to confirm it works
7. Real alerts now fire automatically

Time estimate: 30-45 minutes if Meta verification is smooth; can take
a few days if they ask for business documents.

## Step 1 — Create Meta app

1. Go to https://developers.facebook.com/
2. Log in with your personal Facebook account (you don't need a
   separate business account to START, but you'll need one later for
   production; the test mode works with personal account)
3. Click **My Apps** → **Create App**
4. Use case: select **Other**
5. App type: **Business**
6. Name the app something like "Celesys Alerts"
7. Contact email: your email

## Step 2 — Add WhatsApp product

1. On the app dashboard left sidebar, find **Add Product**
2. Locate **WhatsApp** → click **Set up**
3. You'll be asked to select or create a Meta Business Account
   (a MBA can be just a placeholder; you can set up a "personal use"
   one initially)

## Step 3 — Get credentials

In the WhatsApp product area you'll see a **Getting Started** tab.

**Phone number ID** (this is `META_WABA_PHONE_ID`):
- Under "From" there's a test phone number Meta gives you
- Below it, "Phone number ID" — copy that string of digits
- Example: `105954782173123`

**Access token** (this is `META_WABA_TOKEN`):
- On the same page, "Temporary access token" — this is valid 24 hours
- For production you need a **permanent system user token**, which
  requires going through Meta Business Suite → Business Settings →
  System Users → create a user, assign the app, generate token with
  `whatsapp_business_messaging` permission
- **For first test, the 24h token is fine**. Swap it later.

## Step 4 — Add your number as verified recipient

During test mode Meta will ONLY deliver messages to phone numbers
you've explicitly verified. Otherwise messages silently fail.

1. Same "Getting Started" page, section **To**
2. Click **Manage phone number list**
3. Add `+919177577022`
4. Meta sends a verification code to that WhatsApp number
5. Enter the code. Now your number is whitelisted.

This limit (5 verified numbers) disappears after you complete Meta
Business Verification, which requires submitting company documents.
For personal alerting you never need to graduate out of test mode.

## Step 5 — Set environment variables on Render

In your Render dashboard → your Celesys service → **Environment**:

| Variable | Value |
|---|---|
| `CELESYS_ALERTS_ENABLED` | `1` |
| `META_WABA_PHONE_ID` | (the phone_number_id from Step 3) |
| `META_WABA_TOKEN` | (the access token from Step 3) |
| `META_WABA_RECIPIENT` | `919177577022` (no `+`, no leading zeros) |

Click **Save, rebuild** and wait for the service to restart.

## Step 6 — Verify with the test endpoint

Open in browser:
```
https://celesys.ai/api/alert-test
```

Three possible responses:

**Success:**
```json
{
  "success": true,
  "config_check": {
    "CELESYS_ALERTS_ENABLED": true,
    "META_WABA_PHONE_ID": true,
    "META_WABA_TOKEN": true,
    "META_WABA_RECIPIENT": true
  },
  "send_result": "{'messaging_product': 'whatsapp', 'contacts': [...], 'messages': [...]}"
}
```
You should get a WhatsApp message within 5 seconds.

**Env vars missing:**
```json
{
  "success": false,
  "send_result": "env vars missing (META_WABA_PHONE_ID/TOKEN/RECIPIENT)"
}
```
→ Check Render env vars are saved and service rebuilt.

**Meta rejected the send:**
```json
{
  "success": false,
  "send_result": "HTTP 400: {\"error\":{\"message\":\"(#131030) Recipient phone number not in allowed list\"...}}"
}
```
→ Your recipient number isn't verified in Step 4, or token expired.

## Step 7 — Wait for real alerts

Once the test succeeds, alerts fire automatically. Conditions:
- Score ≥ 75 AND confidence ≥ 80
- Action is BUY CALL or BUY PUT (not HOLD/AVOID)
- Not blocked by any gate
- Not on stale/keep-last-good data
- Not in 30-min cooldown for same (symbol, strike, side)

Expected frequency: 5-15 alerts/day across IN+US combined during
market hours, less during quiet periods. If you get zero for an
entire day of active markets, something is misconfigured — check
Render logs for `[ALERT]` prefixed lines.

## Known limitations

1. **24h conversation window.** Meta's policy: you can freeform
   message a user only within 24 hours of THEIR last message to you.
   First time you hit the bot, reply "hi" from your WhatsApp to the
   Meta test number to open the window. For ongoing alerts, the
   `_alert_send_whatsapp()` function uses a plain text payload which
   works during the 24h window. Beyond 24h of silence, Meta requires
   a pre-approved **template message** — not built yet. Workaround:
   reply to any alert message to reset the 24h window.

2. **Temporary token = 24h.** If you only used the temp token from
   Step 3, after 24 hours alerts will silently fail with
   `HTTP 401: invalid access token`. Get a permanent token via
   System User (Step 3 note) before trusting this in production.

3. **Free tier rate limits.** Meta caps test mode at 250 messages per
   rolling 24h. Celesys at 5-15/day is fine. If you ever scale up,
   you'll hit the ceiling around 16-20 alerts/day factoring in the
   test message itself.

4. **No delivery confirmation.** The code checks HTTP 200 but doesn't
   track whether WhatsApp actually delivered to your phone. If your
   phone is offline for days, messages queue on Meta's side with no
   signal to us. Not a bug — a limitation.

## Turning alerts off

Either:
- Set `CELESYS_ALERTS_ENABLED=0` on Render (requires rebuild), or
- Remove the `META_WABA_TOKEN` env var (instant, no rebuild)

Both work. First is cleaner for pause/resume; second for permanent off.

## If something goes wrong

Check Render logs for lines starting with `[ALERT]`:
- `[ALERT] ✅ IN A+ NIFTY 24500 CE sent` — working
- `[ALERT] ❌ ... failed: HTTP 400 ...` — Meta rejected, read error
- `[ALERT] ❌ ... failed: env vars missing ...` — config issue
- `[ALERT] ⚠️ dispatch error ...` — bug in our code, send me the log

The `/api/alert-test` endpoint is your best friend for debugging —
it returns the raw Meta response so you can see their error codes
instead of digging through logs.
