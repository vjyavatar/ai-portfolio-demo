# Celesys AI

Stock research workspace for US and Indian markets. The site is a FastAPI app served by uvicorn. Render starts it with:

```bash
uvicorn start:app --host 0.0.0.0 --port $PORT
```

Python version is pinned in `runtime.txt`. Dependencies are in `requirements.txt`. There is no `render.yaml` in this repo; keep the service start command above.

## Live market board (v4.63.105)

`/markets` is a read-only board for NYSE/NASDAQ and NSE/BSE. The workspace overview also shows a short index strip. Existing research routes, analytics and AdSense tags are unchanged.

What it shows:

- Quotes, percent change and volume for stocks and for S&P 500, Nasdaq, Dow, Nifty 50, Sensex and Bank Nifty
- A research score (trend, valuation, momentum, risk) with the inputs written out
- A watchlist kept in the browser
- A liquid-name screener for a fixed US sample and a fixed India sample
- A bounded option chain when a feed answers (US via Yahoo, India via Angel One when configured, then NSE)
- Session clocks in US Eastern and India Standard Time, plus delayed vs last-close vs live

Not financial advice. A score is not a trade instruction.

### Data sources

| Source | Used for | Freshness seen in checks | Limit | Cost |
|---|---|---|---|---|
| Angel One SmartAPI | Primary NSE quotes (NIFTY, BANKNIFTY, RELIANCE and other NSE names) and the NIFTY/BANKNIFTY option chain when the session is configured | Broker LTP/OHLC and a near-spot chain, cached about 60 seconds. Labeled LIVE while the NSE cash session is open. | Read-only. Needs the Angel env block below. `CELESYS_LICENSED_OPTIONS_IN` is not required for this board. | Angel One account |
| TradingView public scanner | Fallback quotes and technicals when Angel has no price. Still the primary feed for US names and for BSE. | `delayed_streaming_900` (15 min) or `delayed_streaming_600` (10 min) on equities and indices. Some FX/CFD symbols report `streaming`. | Unofficial. No key. Cached. Not a licensed real-time feed and not a broker NBBO. | Free |
| Yahoo chart + option chain | Fallback price, exchange timestamp, US option chain | Delayed public chart. Options need a crumb cookie. India option chains are not listed. | Unofficial. Crumb can fail. | Free |
| NSE public chain | India F&O when the request is allowed | Exchange chain during the session | Often HTTP 403 from datacenter and Render IPs. | Free |
| Finnhub | Optional US stock price when `FINNHUB_API_KEY` is set | Labeled live only while that exchange is in its regular session | Free tier is about 60 calls/minute and is not an India feed. | Free tier |
| Twelve Data | Optional last resort when `TWELVE_DATA_API_KEY` is set | Labeled delayed | Free tier is about 8 calls/minute and 800/day. | Free tier |

Quotes are cached in the app process (default 60 seconds, `CELESYS_LIVE_CACHE_SECONDS`). A failed fetch serves the last cached snapshot as `STALE` for up to 30 minutes instead of breaking the page. Weekend and after-hours prints are labeled `LAST_CLOSE`. The holiday calendar is not fully encoded.

Angel One is used on the public board when the session is configured. The signed-in private desk is unchanged and still requires `CELESYS_LICENSED_OPTIONS_IN=true`. That flag is an operator switch in `private_options.ready`, not a statutory check, so the public read does not look at it. See `docs/FREE_CHAIN_SETUP.md`.

Upstox is not used.

### Environment

Copy `.env.example`. None of the keys are required for the public board. Set secrets in the Render dashboard, not in git.

Angel One only, all optional:

- `CELESYS_ANGEL_PROXY_URL` — forward proxy such as `http://user:pass@139.59.38.68:8888`. Login, quotes, the instrument master and Angel order routes use it. Other providers do not.
- `CELESYS_ANGEL_CLIENT_PUBLIC_IP` — when the proxy is set and this is blank, the header sent is `139.59.38.68`.
- `CELESYS_ANGEL_CLIENT_CODE`, `CELESYS_ANGEL_PIN`, `CELESYS_ANGEL_TOTP_SECRET` — together these log in through `loginByPassword`. The JWT stays in memory and refreshes after a 401 and around 08:30 IST. If any are blank, `CELESYS_ANGEL_JWT_TOKEN` is used.

### Local check

```bash
python -m unittest tests.test_live_markets
python -m live_markets.smoke
```

Then open `http://127.0.0.1:8000/markets` with `uvicorn start:app --host 0.0.0.0 --port 8000`.
