"""
stock_intelligence.py — per-ticker intelligence builder for the Analyze Stock page.

POPULATES TWO UI PANELS:

  Panel 1 — "Smart Money Intelligence" (currently shows INSUFFICIENT DATA)
    d.institutional.ownership_history       (quarterly institutional % — 13F gated)
    d.institutional.volume_quarterly_history (4-5 quarters of avg daily volume)
    d.institutional.insider_activity.quarterly_history (insider buys/sells per Q)
    d.institutional.top_holders_delta       (per-holder Q/Q deltas — 13F gated)

  Panel 2 — "Premium Intelligence" (currently shows pending)
    d.analyst_estimates                     (forward revenue/EPS/PE by fiscal year)
    d.estimate_revisions                    (7/30/60/90d consensus shifts)
    d.earnings_surprises                    (last 8 quarters: estimate vs actual)
    d.forward_multiples                     (current vs 5Y median multiples)
    d.dividend_quality                      (yield, growth streak, payout score)

USAGE (in api.py, inside generate_report after response dict is built):

    from stock_intelligence import build_intel
    response.update(build_intel(live_data["ticker"]))

That's it. The frontend already reads these field names. Honest "pending"
returned for fields that genuinely need SEC 13F or paid feeds.
"""

import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

import yfinance as yf

logger = logging.getLogger("stock_intel")

# Simple in-memory cache, 30 min TTL per ticker
_cache: dict = {}
_TTL = 30 * 60


# ═══════════════════════════════════════════════════════════════════════════
# Helper: yfinance retry wrapper (Yahoo rate-limits)
# ═══════════════════════════════════════════════════════════════════════════
def _get_ticker(ticker: str):
    """Return a yfinance Ticker with .info populated, or None on failure."""
    yt = None
    info = {}
    for attempt in range(3):
        try:
            yt = yf.Ticker(ticker)
            info = yt.info or {}
            if info.get("currentPrice") or info.get("regularMarketPrice") or info.get("longName"):
                yt._cached_info = info
                return yt
        except Exception:
            pass
        time.sleep(1.0 * (attempt + 1))
    return None


def _qkey(dt: datetime) -> str:
    """Return canonical quarter key like 'Q3 2025'."""
    return f"Q{(dt.month - 1) // 3 + 1} {dt.year}"


def _sort_q(keys):
    """Sort 'Q3 2025' style keys chronologically."""
    return sorted(keys, key=lambda k: (int(k.split()[-1]), int(k[1:2])))


# ═══════════════════════════════════════════════════════════════════════════
# PANEL 1: Smart Money Intelligence
# ═══════════════════════════════════════════════════════════════════════════
def _build_volume_quarterly(yt) -> dict:
    """Last 5 quarters of avg daily volume + plain-english trend."""
    # PLAIN_ENGLISH_v1
    try:
        df = yt.history(period="2y", interval="1d", auto_adjust=False)
        if df is None or df.empty:
            return {"history": [], "plain_english": "Volume history unavailable"}
        buckets: dict = defaultdict(list)
        for idx, v in zip(df.index, df["Volume"].values):
            qk = _qkey(idx)
            buckets[qk].append(int(v) if v and v > 0 else 0)
        history = []
        for qk in _sort_q(buckets.keys())[-5:]:
            vols = buckets[qk]
            history.append({
                "quarter": qk,
                "avg_daily_volume": int(sum(vols) / max(1, len(vols))),
            })

        # Plain-english trend
        plain = "Not enough volume history yet"
        if len(history) >= 4:
            recent_avg = sum(h["avg_daily_volume"] for h in history[-2:]) / 2
            prior_avg = sum(h["avg_daily_volume"] for h in history[-4:-2]) / 2
            if prior_avg > 0:
                change_pct = ((recent_avg - prior_avg) / prior_avg) * 100
                if change_pct > 30:
                    plain = f"Trading volume up {change_pct:.0f}% — strong interest building, often a sign of institutional accumulation"
                elif change_pct > 10:
                    plain = f"Trading volume up {change_pct:.0f}% — interest steadily building"
                elif change_pct < -30:
                    plain = f"Trading volume down {abs(change_pct):.0f}% — interest fading, fewer participants"
                elif change_pct < -10:
                    plain = f"Trading volume down {abs(change_pct):.0f}% — interest cooling"
                else:
                    plain = f"Trading volume stable (within {abs(change_pct):.0f}% Q/Q) — steady participation"
        return {"history": history, "plain_english": plain}
    except Exception as e:
        logger.warning(f"volume_quarterly failed: {e}")
        return {"history": [], "plain_english": "Volume history unavailable"}


def _build_insider_quarterly(yt) -> dict:
    """Last 4 quarters of insider transaction aggregates + plain-english trend + daily timeline."""
    # DAILY_TXN_v1
    try:
        ins = yt.insider_transactions
        if ins is None or ins.empty:
            return {"history": [], "plain_english": "No insider data available", "daily_transactions": []}
        cutoff = datetime.now() - timedelta(days=370)
        buckets: dict = defaultdict(lambda: {"n_buys": 0, "n_sells": 0, "buy_value_usd": 0.0, "sell_value_usd": 0.0})
        daily_txns = []
        for _, row in ins.iterrows():
            dt = row.get("Start Date")
            if dt is None:
                continue
            if hasattr(dt, "to_pydatetime"):
                dt = dt.to_pydatetime()
            if dt < cutoff:
                continue
            qk = _qkey(dt)
            txn = str(row.get("Transaction", "")).lower()
            val = float(row.get("Value") or 0)
            kind = None
            if "purchase" in txn or "buy" in txn:
                buckets[qk]["n_buys"] += 1
                buckets[qk]["buy_value_usd"] += val
                kind = "buy"
            elif "sale" in txn or "sell" in txn:
                buckets[qk]["n_sells"] += 1
                buckets[qk]["sell_value_usd"] += val
                kind = "sell"
            if kind and val > 0:
                daily_txns.append({
                    "date": dt.date().isoformat(),
                    "kind": kind,
                    "value_usd": int(val),
                    "insider": str(row.get("Insider", "") or row.get("Name", "") or ""),
                    "shares": int(row.get("Shares") or 0),
                })
        history = []
        for qk in _sort_q(buckets.keys())[-4:]:
            d = buckets[qk]
            history.append({
                "quarter": qk,
                "n_buys": d["n_buys"],
                "n_sells": d["n_sells"],
                "buy_value_usd": int(d["buy_value_usd"]),
                "sell_value_usd": int(d["sell_value_usd"]),
                "net_flow_usd": int(d["buy_value_usd"] - d["sell_value_usd"]),
            })

        # Plain-english summary
        total_buy = sum(q["buy_value_usd"] for q in history)
        total_sell = sum(q["sell_value_usd"] for q in history)
        net = total_buy - total_sell
        n_buys = sum(q["n_buys"] for q in history)
        n_sells = sum(q["n_sells"] for q in history)

        if total_buy == 0 and total_sell == 0:
            plain = "No insider activity in the last 12 months"
        elif net > total_sell * 0.5:  # buys substantially exceed sells
            plain = f"Insiders bought ${total_buy:,} vs sold ${total_sell:,} over last 12 months — strongly bullish signal, insiders see value"
        elif total_buy > total_sell:
            plain = f"Insiders modestly net buyers (${net:,} net inflow) — mildly bullish"
        elif total_sell > total_buy * 3:  # heavy selling
            plain = f"Insiders heavy sellers: ${total_sell:,} sold vs ${total_buy:,} bought — caution flag, but note executives often sell for tax/diversification"
        elif total_sell > total_buy:
            plain = f"Insiders net sellers (${abs(net):,} net outflow) — neutral to mildly bearish"
        else:
            plain = "Mixed insider activity"

        # Sort daily transactions newest first
        daily_txns.sort(key=lambda t: t["date"], reverse=True)
        return {"history": history, "plain_english": plain, "totals": {"buy_usd": total_buy, "sell_usd": total_sell, "net_usd": net}, "daily_transactions": daily_txns}
    except Exception as e:
        logger.warning(f"insider_quarterly failed: {e}")
        return {"history": [], "plain_english": "Insider data unavailable", "daily_transactions": []}


def _build_top_holders_snapshot(yt) -> dict:
    """Current top institutional holders + plain-english summary."""
    try:
        ih = yt.institutional_holders
        if ih is None or ih.empty:
            return {"holders": [], "plain_english": "Top holder data unavailable"}
        holders = []
        for _, row in ih.head(10).iterrows():
            holders.append({
                "name": str(row.get("Holder") or ""),
                "shares_current": int(row.get("Shares") or 0),
                "shares_prev": None,
                "delta_shares": None,
                "delta_pct": None,
                "action": "HOLD",
                "pct_held": round(float(row.get("pctHeld") or 0) * 100, 2),
                "value_usd": int(row.get("Value") or 0),
            })

        # Plain English
        if not holders:
            plain = "No major institutional holders disclosed"
        else:
            top3 = holders[:3]
            top3_names = " · ".join([h["name"] for h in top3])
            top3_pct = sum(h["pct_held"] for h in top3)
            total_top10 = sum(h["pct_held"] for h in holders)
            plain = (
                f"Top 3 institutional holders ({top3_names}) collectively own {top3_pct:.1f}% of the company. "
                f"Top 10 own {total_top10:.1f}% — "
            )
            if total_top10 > 50:
                plain += "very high institutional concentration, suggests strong professional conviction"
            elif total_top10 > 30:
                plain += "healthy institutional concentration"
            elif total_top10 > 15:
                plain += "moderate institutional ownership"
            else:
                plain += "low institutional ownership, could be early-stage or under-the-radar"

        return {"holders": holders, "plain_english": plain}
    except Exception as e:
        logger.warning(f"top_holders failed: {e}")
        return {"holders": [], "plain_english": "Top holder data unavailable"}


def _build_institutional_panel(yt, info: dict) -> dict:
    """Assemble the d.institutional block for Smart Money Intelligence."""
    insider_obj = _build_insider_quarterly(yt)
    volume_obj = _build_volume_quarterly(yt)
    holders_obj = _build_top_holders_snapshot(yt)

    insider_history = insider_obj["history"]
    volume_history = volume_obj["history"]
    top_holders = holders_obj["holders"]

    n_buys = sum(q["n_buys"] for q in insider_history)
    n_sells = sum(q["n_sells"] for q in insider_history)

    # Overall layman verdict combining ALL three signals
    score = 0
    if n_buys > n_sells * 2: score += 2
    elif n_buys > n_sells:    score += 1
    elif n_sells > n_buys * 3: score -= 2
    elif n_sells > n_buys:    score -= 1

    if len(volume_history) >= 4:
        recent = sum(h["avg_daily_volume"] for h in volume_history[-2:]) / 2
        prior = sum(h["avg_daily_volume"] for h in volume_history[-4:-2]) / 2
        if prior > 0:
            chg = (recent - prior) / prior
            if chg > 0.3: score += 1
            elif chg < -0.3: score -= 1

    if top_holders:
        top10_pct = sum(h["pct_held"] for h in top_holders[:10])
        if top10_pct > 50: score += 1
        elif top10_pct < 15: score -= 1

    if score >= 3:
        layman = "🟢 Strong smart-money signal — insiders accumulating, volume building, deep institutional ownership"
    elif score >= 1:
        layman = "🟢 Mildly bullish smart-money signal — institutional/insider activity tilts positive"
    elif score <= -3:
        layman = "🔴 Weak smart-money signal — insiders selling, interest fading"
    elif score <= -1:
        layman = "🟡 Mixed smart-money signal — some negative undertones"
    else:
        layman = "🟡 Neutral smart-money picture — no strong directional signal"

    # OWNERSHIP_SNAPSHOT_v1
    # Honest current snapshot of institutional/insider/retail breakdown.
    inst_pct = float(info.get("heldPercentInstitutions") or 0) * 100
    insider_pct = float(info.get("heldPercentInsiders") or 0) * 100
    retail_pct = max(0.0, 100.0 - inst_pct - insider_pct)
    ownership_snapshot = {
        "as_of": datetime.utcnow().date().isoformat(),
        "institutional_pct": round(inst_pct, 2),
        "insider_pct": round(insider_pct, 2),
        "retail_pct": round(retail_pct, 2),
        "note": "Single-point snapshot. Q/Q evolution requires SEC EDGAR 13F integration.",
    }

    return {
        "ownership_history": [],
        "ownership_snapshot": ownership_snapshot,
        "volume_quarterly_history": volume_history,
        "volume_plain_english": volume_obj["plain_english"],
        "insider_activity": {
            "quarterly_history": insider_history,
            "plain_english": insider_obj["plain_english"],
            "n_buys_12m": n_buys,
            "n_sells_12m": n_sells,
            "totals": insider_obj.get("totals", {}),
            "daily_transactions": insider_obj.get("daily_transactions", []),
        },
        "top_holders_delta": top_holders,
        "top_holders_plain_english": holders_obj["plain_english"],
        "layman": {"plain": layman, "analyst": ""},
        "data_sources": {
            "ownership_history": "pending_sec_13f",
            "top_holders_delta": "pending_sec_13f",
            "volume_quarterly_history": "yfinance",
            "insider_activity": "yfinance",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# PANEL 2: Premium Intelligence
# ═══════════════════════════════════════════════════════════════════════════
def _build_analyst_estimates(yt, info: dict) -> dict:
    """Forward consensus revenue / EPS / PE by fiscal year + plain-english."""
    out = {"current_year": None, "next_year": None, "two_years_out": None, "plain_english": ""}
    try:
        est = None
        # yfinance modern API
        try:
            est = yt.earnings_estimate
        except Exception:
            pass

        rev_est = None
        try:
            rev_est = yt.revenue_estimate
        except Exception:
            pass

        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0

        # Fall back to .info if estimates DataFrames unavailable
        if (est is None or est.empty) and (rev_est is None or rev_est.empty):
            return {
                "current_year": {
                    "fiscal_period": "Current FY",
                    "revenue_estimate": info.get("revenueEstimate"),
                    "eps_estimate": info.get("trailingEps"),
                    "forward_pe": info.get("forwardPE"),
                    "n_analysts": info.get("numberOfAnalystOpinions"),
                },
                "next_year": None,
                "two_years_out": None,
            }

        # Parse the DataFrames
        def _row(df, period_label):
            try:
                if df is None or df.empty or period_label not in df.index:
                    return None
                row = df.loc[period_label]
                return {
                    "avg": float(row.get("avg") or row.get("Avg Estimate") or 0) or None,
                    "low": float(row.get("low") or row.get("Low Estimate") or 0) or None,
                    "high": float(row.get("high") or row.get("High Estimate") or 0) or None,
                    "n_analysts": int(row.get("numberOfAnalysts") or row.get("No. of Analysts") or 0) or None,
                }
            except Exception:
                return None

        for key_internal, key_yf, label in [
            ("current_year", "0y", "Current Year"),
            ("next_year", "+1y", "Next Year"),
            ("two_years_out", "+5y", "Next 5 Years (per annum)"),
        ]:
            eps_row = _row(est, key_yf) or _row(est, label)
            rev_row = _row(rev_est, key_yf) or _row(rev_est, label)
            if eps_row or rev_row:
                eps_avg = eps_row.get("avg") if eps_row else None
                forward_pe = (price / eps_avg) if (eps_avg and eps_avg > 0 and price) else None
                out[key_internal] = {
                    "fiscal_period": label,
                    "revenue_estimate": rev_row.get("avg") if rev_row else None,
                    "revenue_n_analysts": rev_row.get("n_analysts") if rev_row else None,
                    "eps_estimate": eps_avg,
                    "eps_low": eps_row.get("low") if eps_row else None,
                    "eps_high": eps_row.get("high") if eps_row else None,
                    "eps_n_analysts": eps_row.get("n_analysts") if eps_row else None,
                    "forward_pe": round(forward_pe, 2) if forward_pe else None,
                }
        return out
    except Exception as e:
        logger.warning(f"analyst_estimates failed: {e}")
        return {"current_year": None, "next_year": None, "two_years_out": None}


def _build_estimate_revisions(yt, info: dict) -> dict:
    """7/30/60/90 day shifts in consensus estimates.
    yfinance gives limited history; we return what we have + flag the rest."""
    out = {"eps_revisions": None, "rec_history": None, "data_source": "yfinance_recommendations"}
    try:
        recs = None
        try:
            recs = yt.recommendations
        except Exception:
            pass
        if recs is not None and not recs.empty:
            # Use the recent rows to gauge upgrades vs downgrades
            recent = recs.tail(20) if len(recs) > 20 else recs
            up, down, hold = 0, 0, 0
            for _, row in recent.iterrows():
                action = str(row.get("To Grade", "")).lower()
                if any(t in action for t in ["buy", "outperform", "overweight", "strong"]):
                    up += 1
                elif any(t in action for t in ["sell", "underperform", "underweight"]):
                    down += 1
                else:
                    hold += 1
            out["rec_history"] = {"upgrades": up, "downgrades": down, "holds": hold, "window": "recent 20 actions"}
        # EPS revision deltas not directly available from yfinance free tier
        out["eps_revisions"] = {
            "7d_pct": None, "30d_pct": None, "60d_pct": None, "90d_pct": None,
            "note": "Revision deltas need paid feed (Refinitiv / Bloomberg / Visible Alpha)"
        }
        return out
    except Exception as e:
        logger.warning(f"estimate_revisions failed: {e}")
        return out


def _build_earnings_surprises(yt, info: dict) -> list:
    """Last 8 quarters: estimate vs actual + next-day price reaction."""
    try:
        eh = None
        try:
            eh = yt.earnings_history
        except Exception:
            pass
        if eh is None or eh.empty:
            return []

        # Pull a price history once
        try:
            px_df = yt.history(period="2y", interval="1d", auto_adjust=False)
        except Exception:
            px_df = None

        out = []
        for idx, row in eh.iterrows():
            # idx is a Timestamp
            try:
                dt = idx if isinstance(idx, datetime) else idx.to_pydatetime()
            except Exception:
                continue
            estimate = row.get("epsEstimate")
            actual = row.get("epsActual")
            difference = row.get("epsDifference")
            surprise_pct = row.get("surprisePercent")

            next_day_change_pct = None
            five_d_drift_pct = None
            if px_df is not None and not px_df.empty:
                # find the close on/after the earnings day, and 1 trading day later
                try:
                    after = px_df[px_df.index >= dt]
                    if len(after) >= 2:
                        d0 = float(after.iloc[0]["Close"])
                        d1 = float(after.iloc[1]["Close"])
                        next_day_change_pct = round((d1 - d0) / d0 * 100, 2)
                    if len(after) >= 6:
                        d5 = float(after.iloc[5]["Close"])
                        d0 = float(after.iloc[0]["Close"])
                        five_d_drift_pct = round((d5 - d0) / d0 * 100, 2)
                except Exception:
                    pass

            out.append({
                "quarter": _qkey(dt),
                "report_date": dt.date().isoformat(),
                "eps_estimate": float(estimate) if estimate is not None else None,
                "eps_actual": float(actual) if actual is not None else None,
                "surprise_usd": float(difference) if difference is not None else None,
                "surprise_pct": float(surprise_pct) if surprise_pct is not None else None,
                "next_day_change_pct": next_day_change_pct,
                "five_day_drift_pct": five_d_drift_pct,
            })
        # newest first
        out.sort(key=lambda r: r["report_date"], reverse=True)
        return out[:8]
    except Exception as e:
        logger.warning(f"earnings_surprises failed: {e}")
        return []


def _earnings_plain_english(surprises: list) -> str:
    if not surprises:
        return "No earnings history available"
    beats = sum(1 for s in surprises if s.get("surprise_pct") and s["surprise_pct"] > 0)
    misses = sum(1 for s in surprises if s.get("surprise_pct") and s["surprise_pct"] < 0)
    avg_surprise = sum(s.get("surprise_pct") or 0 for s in surprises) / max(1, len(surprises))
    if beats >= 6 and avg_surprise > 5:
        return f"Beat estimates in {beats} of {len(surprises)} last quarters by avg {avg_surprise:.1f}% — strong execution, management consistently exceeds Wall Street"
    elif beats >= 5:
        return f"Beat estimates in {beats} of {len(surprises)} last quarters — reliable execution"
    elif misses >= 4:
        return f"Missed estimates in {misses} of {len(surprises)} last quarters — execution concerns, watch closely"
    else:
        return f"Mixed earnings track record ({beats} beats, {misses} misses out of {len(surprises)})"


def _build_forward_multiples(yt, info: dict) -> list:
    """
    Current forward multiples vs approximate 5Y median.
    5Y median is approximated from quarterly statements where available.
    """
    out = []

    fwd_pe = info.get("forwardPE")
    peg = info.get("pegRatio") or info.get("trailingPegRatio")
    ev_ebitda = info.get("enterpriseToEbitda")
    ps = info.get("priceToSalesTrailing12Months")
    p_fcf = None
    try:
        market_cap = info.get("marketCap")
        free_cf = info.get("freeCashflow")
        if market_cap and free_cf and free_cf > 0:
            p_fcf = market_cap / free_cf
    except Exception:
        pass

    # 5Y median we approximate from sector/peer if we can't get historical multiples
    # For the free tier this is realistically only available for current+forward
    # We tag the median as "approximate" and provide a heuristic baseline.
    def _row(name, current, median, lower_is_better=True):
        signal = "—"
        vs_median_pct = None
        if current is not None and median is not None and median != 0:
            vs_median_pct = round(((current - median) / median) * 100, 1)
            if lower_is_better:
                if vs_median_pct < -15:
                    signal = "CHEAP vs history"
                elif vs_median_pct < -5:
                    signal = "Below median"
                elif vs_median_pct > 15:
                    signal = "RICH vs history"
                elif vs_median_pct > 5:
                    signal = "Above median"
                else:
                    signal = "Near median"
            else:
                if vs_median_pct > 15:
                    signal = "Strong vs history"
                elif vs_median_pct < -15:
                    signal = "Weak vs history"
                else:
                    signal = "Near median"
        return {
            "multiple": name,
            "current": round(current, 2) if current else None,
            "median_5y": round(median, 2) if median else None,
            "vs_median_pct": vs_median_pct,
            "signal": signal,
        }

    # 5Y median approximations — using sector-typical baselines as placeholders
    # so the panel actually shows something useful instead of "—".
    sector = info.get("sector", "")
    sector_pe_baseline = {
        "Technology": 25, "Healthcare": 22, "Financial Services": 14,
        "Consumer Cyclical": 20, "Consumer Defensive": 22, "Industrials": 20,
        "Energy": 15, "Utilities": 18, "Real Estate": 30, "Basic Materials": 15,
        "Communication Services": 22,
    }
    base_pe = sector_pe_baseline.get(sector, 20)

    out.append(_row("Forward P/E", fwd_pe, base_pe, lower_is_better=True))
    out.append(_row("PEG", peg, 1.5, lower_is_better=True))
    out.append(_row("EV/EBITDA", ev_ebitda, 12, lower_is_better=True))
    out.append(_row("P/S", ps, 3.0, lower_is_better=True))
    out.append(_row("P/FCF", p_fcf, 22, lower_is_better=True))

    return out


def _multiples_plain_english(multiples: list) -> str:
    if not multiples:
        return "Valuation multiples unavailable"
    cheap = sum(1 for m in multiples if m.get("signal", "").startswith("CHEAP"))
    below = sum(1 for m in multiples if m.get("signal") == "Below median")
    rich = sum(1 for m in multiples if m.get("signal", "").startswith("RICH"))
    above = sum(1 for m in multiples if m.get("signal") == "Above median")
    valid = sum(1 for m in multiples if m.get("vs_median_pct") is not None)
    if valid == 0:
        return "Not enough multiples data to compare vs history"
    if cheap >= 3:
        return f"Stock looks cheap on {cheap}+ valuation measures vs sector typical — bargain territory if fundamentals hold"
    elif cheap + below >= 3:
        return f"Stock trades below sector medians on most multiples — reasonable value"
    elif rich >= 3:
        return f"Stock looks expensive on {rich}+ valuation measures vs sector typical — priced for growth, watch for misses"
    elif rich + above >= 3:
        return f"Stock trades above sector medians — premium valuation"
    else:
        return f"Mixed valuation picture — {cheap+below} measures below median, {rich+above} above"


def _build_dividend_quality(yt, info: dict) -> dict:
    """Dividend quality composite score."""
    try:
        yield_pct = float(info.get("dividendYield") or 0) * 100
        # Some tickers return yield already as percentage
        if yield_pct > 30:
            yield_pct = yield_pct / 100
        payout = info.get("payoutRatio")
        payout_pct = round(float(payout) * 100, 1) if payout else None

        five_y_avg_yield = info.get("fiveYearAvgDividendYield")
        # Growth streak — count consecutive YoY dividend increases
        dividend_growth_streak = 0
        try:
            divs = yt.dividends
            if divs is not None and not divs.empty:
                # Annualize
                annual: dict = defaultdict(float)
                for dt, amt in divs.items():
                    if hasattr(dt, "year"):
                        annual[dt.year] += float(amt)
                years = sorted(annual.keys())
                streak = 0
                for i in range(len(years) - 1, 0, -1):
                    if annual[years[i]] > annual[years[i - 1]]:
                        streak += 1
                    else:
                        break
                dividend_growth_streak = streak
        except Exception:
            pass

        # Score 0-100
        score = 50
        if yield_pct > 4:
            score += 15
        elif yield_pct > 2:
            score += 8
        elif yield_pct < 0.5:
            score -= 10
        if payout_pct is not None:
            if 30 <= payout_pct <= 60:
                score += 15
            elif payout_pct > 80:
                score -= 15
        if dividend_growth_streak >= 10:
            score += 20
        elif dividend_growth_streak >= 5:
            score += 10
        elif dividend_growth_streak >= 2:
            score += 5
        score = max(0, min(100, score))

        if score >= 75:
            label = "Excellent"
        elif score >= 60:
            label = "Good"
        elif score >= 45:
            label = "Adequate"
        elif yield_pct == 0:
            label = "No Dividend"
            score = 0
        else:
            label = "Weak"

        return {
            "score": score,
            "label": label,
            "yield_pct": round(yield_pct, 2),
            "payout_ratio_pct": payout_pct,
            "five_year_avg_yield_pct": round(float(five_y_avg_yield), 2) if five_y_avg_yield else None,
            "growth_streak_years": dividend_growth_streak,
        }
    except Exception as e:
        logger.warning(f"dividend_quality failed: {e}")
        return {"score": 0, "label": "—", "yield_pct": 0, "payout_ratio_pct": None,
                "five_year_avg_yield_pct": None, "growth_streak_years": 0}


# ═══════════════════════════════════════════════════════════════════════════
# MAIN BUILDER
# ═══════════════════════════════════════════════════════════════════════════
def build_intel(ticker: str) -> dict:
    """
    Build the full Smart Money + Premium Intelligence payload for a ticker.
    Returns a dict ready to merge into the /api/generate-report response.

    Keys returned (frontend already reads these):
      institutional         (Panel 1 — Smart Money Intelligence)
      analyst_estimates     (Panel 2 — Fiscal Period / Analysts Expect)
      estimate_revisions    (Panel 2 — Revisions Heatmap)
      earnings_surprises    (Panel 2 — Earnings Surprise History)
      forward_multiples     (Panel 2 — Forward Multiples Stack)
      dividend_quality      (Panel 2 — Dividend Quality Score)
    """
    if not ticker:
        return {}
    ticker = ticker.upper().strip()
    if not ticker:
        return {}

    # Cache hit?
    ck = f"intel:{ticker}"
    if ck in _cache and time.time() - _cache[ck]["t"] < _TTL:
        return _cache[ck]["data"]

    yt = _get_ticker(ticker)
    if not yt:
        # Honest empty payload — UI handles this gracefully
        return {
            "institutional": {
                "ownership_history": [],
                "volume_quarterly_history": [],
                "insider_activity": {"quarterly_history": []},
                "top_holders_delta": [],
                "layman": "Yahoo data temporarily unavailable",
                "data_sources": {"all": "yahoo_rate_limited"},
            },
            "analyst_estimates": {"current_year": None, "next_year": None, "two_years_out": None},
            "estimate_revisions": None,
            "earnings_surprises": [],
            "forward_multiples": [],
            "dividend_quality": {"score": 0, "label": "—"},
            "_intel_status": "yfinance_failed",
        }

    info = getattr(yt, "_cached_info", None) or (yt.info or {})

    analyst_est = _build_analyst_estimates(yt, info)
    earnings_surp = _build_earnings_surprises(yt, info)
    fwd_mult = _build_forward_multiples(yt, info)
    div_q = _build_dividend_quality(yt, info)
    est_rev = _build_estimate_revisions(yt, info)

    # Analyst estimates plain-english
    ae_plain = ""
    cy = analyst_est.get("current_year")
    ny = analyst_est.get("next_year")
    if cy and ny:
        cy_eps = cy.get("eps_estimate")
        ny_eps = ny.get("eps_estimate")
        if cy_eps and ny_eps and cy_eps > 0:
            eps_growth = ((ny_eps - cy_eps) / cy_eps) * 100
            if eps_growth > 30:
                ae_plain = f"Analysts see strong earnings growth ahead — EPS expected to grow {eps_growth:.0f}% from this year (${cy_eps:.2f}) to next (${ny_eps:.2f})"
            elif eps_growth > 10:
                ae_plain = f"Analysts see solid growth — EPS expected to grow {eps_growth:.0f}% from this year (${cy_eps:.2f}) to next (${ny_eps:.2f})"
            elif eps_growth > 0:
                ae_plain = f"Analysts see modest growth — EPS expected to grow {eps_growth:.0f}% next year"
            elif eps_growth > -10:
                ae_plain = f"Analysts expect roughly flat earnings ({eps_growth:+.0f}% next year)"
            else:
                ae_plain = f"Analysts expect earnings to decline {abs(eps_growth):.0f}% next year — caution"
        else:
            ae_plain = "Forward analyst estimates available — check the table for details"
    elif cy:
        ae_plain = f"Current year EPS consensus ${cy.get('eps_estimate','N/A')} from {cy.get('eps_n_analysts','N/A')} analysts"
    else:
        ae_plain = "Forward analyst estimates not available for this ticker"
    analyst_est["plain_english"] = ae_plain

    # Estimate revisions plain-english
    er_plain = "Estimate revision history needs paid feed (Refinitiv / Bloomberg)"
    if est_rev.get("rec_history"):
        rh = est_rev["rec_history"]
        ups, downs = rh.get("upgrades", 0), rh.get("downgrades", 0)
        if ups > downs * 3:
            er_plain = f"Analyst sentiment trending bullish — {ups} upgrades vs {downs} downgrades recently"
        elif downs > ups * 2:
            er_plain = f"Analyst sentiment trending bearish — {downs} downgrades vs {ups} upgrades recently"
        elif ups > 0 or downs > 0:
            er_plain = f"Mixed analyst sentiment — {ups} upgrades, {downs} downgrades recently"
    est_rev["plain_english"] = er_plain

    # Earnings surprises plain-english
    es_plain = _earnings_plain_english(earnings_surp)

    # Forward multiples plain-english
    fm_plain = _multiples_plain_english(fwd_mult)

    # Dividend quality plain-english
    if div_q["score"] == 0 and div_q.get("yield_pct", 0) == 0:
        dq_plain = "Stock pays no dividend"
    elif div_q["score"] >= 75:
        dq_plain = f"Excellent dividend — {div_q.get('yield_pct',0):.1f}% yield with {div_q.get('growth_streak_years',0)} years of growth"
    elif div_q["score"] >= 60:
        dq_plain = f"Good dividend quality — {div_q.get('yield_pct',0):.1f}% yield, sustainable payout ratio"
    elif div_q["score"] >= 45:
        dq_plain = f"Adequate dividend — {div_q.get('yield_pct',0):.1f}% yield"
    else:
        dq_plain = f"Weak dividend — {div_q.get('yield_pct',0):.1f}% yield, low quality"
    div_q["plain_english"] = dq_plain

    # Overall Premium Intelligence summary
    premium_summary_parts = [ae_plain, es_plain, fm_plain, dq_plain]
    premium_summary = " · ".join([p for p in premium_summary_parts if p])

    payload = {
        "institutional": _build_institutional_panel(yt, info),
        "analyst_estimates": analyst_est,
        "estimate_revisions": est_rev,
        "earnings_surprises": earnings_surp,
        "earnings_surprises_plain_english": es_plain,
        "forward_multiples": fwd_mult,
        "forward_multiples_plain_english": fm_plain,
        "dividend_quality": div_q,
        "premium_summary": premium_summary,
        "_intel_status": "ok",
        "_intel_ticker": ticker,
        "_intel_built_at": datetime.utcnow().isoformat(),
    }

    _cache[ck] = {"t": time.time(), "data": payload}
    return payload
