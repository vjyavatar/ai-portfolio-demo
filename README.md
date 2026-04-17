# Celesys — Institutional Analytics Platform

React + FastAPI trading analytics platform. Stock screening, options cockpit, portfolio construction.

## Deploy to Render in 5 minutes

### Option A — Blueprint deploy (1-click, recommended)

1. Create a new GitHub repo, push this folder to it
2. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**
3. Connect your repo → Render reads `render.yaml` and provisions everything
4. Wait for build (~3-5 min) — done

### Option B — Manual deploy

1. Push this folder to GitHub
2. Render dashboard → **New** → **Web Service** → connect repo
3. Configure:
   - **Runtime**: Python 3
   - **Build Command**: `npm install && npm run build && pip install -r requirements.txt`
   - **Start Command**: `uvicorn api:app --host 0.0.0.0 --port $PORT`
4. Deploy

## Local development

```bash
# Install everything
npm install
pip install -r requirements.txt

# Terminal 1 — backend
python api.py
# Runs on http://localhost:8000

# Terminal 2 — frontend (hot reload)
npm run dev
# Opens http://localhost:5173 with proxy to backend

# Or: build once and serve everything from FastAPI
npm run build
python api.py
# Visit http://localhost:8000
```

## Project structure

```
celesys/
├── api.py                    # FastAPI backend (endpoints + SPA serving)
├── requirements.txt          # Python deps
├── package.json              # Node deps
├── vite.config.js            # Build config
├── index.html                # React entry HTML
├── render.yaml               # Render Blueprint
│
├── src/
│   ├── main.jsx              # React bootstrap
│   └── celesys_app.jsx       # Entire app (7,272 lines)
│
└── static/dist/              # Built frontend (git-ignored, created by `npm run build`)
```

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/stock-quick?ticker=MU` | Stock analytics (primary) |
| `GET /api/options-quick?symbol=NIFTY` | Indian index options (synthesized from yfinance) |
| `GET /api/global-ticker` | Global indices snapshot |
| `GET /api/l0-scan` | Bulk scanner (fallback stub — frontend uses per-stock calls) |
| `GET /api/health` | Health check |

All endpoints return JSON. 60s in-memory cache on quotes.

## Features

- **Home** — hero + ticker search + live global ticker
- **Overview** — 5 subtabs (Overview · Valuation · Technical · Activity · Risk) with 20-factor engine + CDS v2.0 Unified Matrix
- **Stock** — 10 accordion deep-dive sections (Altman Z, DuPont ROE, Monte Carlo, etc.)
- **Decide** — Institutional Trading Cockpit (65/35 split, Top 3 ranked trades, Quick Trade panel with 30s tick, 220px Secondary Scanner, Voice announcements)
- **Trader** — L0 Scan Engine across 6 modes (Quality/Growth/Momentum/Value/Multibagger/Dividend), Watchlist (localStorage), Live A/A+ Signals bar
- **Markets** — Global indices + SPDR sector performance + market breadth regime
- **Tools** — Graham Calculator, DCF Modeler, Kelly Sizer, Options P&L
- **Dream Portfolio** — PMS-style 6-bucket construction (Growth Leaders / Quality Core / Momentum / Value / Defensive / Multibagger)

## Tech stack

- **Frontend**: React 18 + Vite + inline-styled components (no CSS framework)
- **Backend**: FastAPI + uvicorn + yfinance
- **Data**: yfinance (free, rate-limited — cache mitigates)
- **Deploy**: Render.com (single web service)

## Notes on data

Options data for Indian indices is **synthesized from yfinance daily bars** (real OI chains require NSE direct access or a paid data provider). The React frontend clearly flags this via a yellow warning banner on the Decide tab. If you have access to a real NSE options feed, replace `_synthesize_options_data()` in `api.py`.

### Yahoo Finance rate limiting

yfinance hits Yahoo's public API and Yahoo aggressively rate-limits datacenter IPs. If you see `403 Forbidden` errors in logs:

- Your existing production `api.py` (if you have one) likely has retry logic + yfinance-fallback chains for this. Use it instead of the simple `api.py` provided here — just keep the `/` + `/{path}` catchall block at the bottom for serving React.
- Render's free-tier IPs may be flagged. Upgrade to Starter or add proxy/retry logic.
- Alternatives: Alpha Vantage, Polygon.io, Tiingo, or NSE direct for Indian data.

The `api.py` provided here is a **minimal reference implementation** to prove the frontend works end-to-end. For real traffic, wire in your existing data pipeline.

## License

Private — see repo owner for terms.
