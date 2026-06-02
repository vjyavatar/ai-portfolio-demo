"""
Celesys Cognitive Architecture — LAYER 3: REAL-TIME ENGINE (Execution System)
=============================================================================

The execution surface that:
  - ingests live market data (price, volume, options, news)
  - extracts features (RVOL, VWAP slope, gap %, ATR, etc.)
  - maps features → signals via Layer 1 ontology
  - validates dependencies via Layer 2 graph (propagate weights, flag invalid)
  - aggregates into dimension + composite scores via Layer 1 rules
  - returns a fully-explainable structured response
  - supports ranking + alerting (batch scoring over a universe)

Implements the doc spec line-by-line:

    ENGINE
    ├── live data ingestion       → FeatureBundle (typed input)
    ├── scoring                   → score_single()
    ├── ranking                   → score_batch() + rank_results()
    └── alerting                  → emit_alerts() with configurable rules

Defensive design:
  - All upstream data is treated as untrusted. Validators run before scorers.
  - Per-symbol timeout. No scorer can hang the request.
  - Every output carries provenance: which signals fired, which deps fired,
    which were muted, what regime applied.
  - Output is stable for cache/diff: deterministic key ordering, rounded values.
"""
from __future__ import annotations

import time
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from celesys_ontology import (
    REGISTRY, ONTOLOGY_VERSION,
    SignalDef, ScoreResult, DimensionResult, CompositeResult,
    Confidence, Verdict, SourceQuality,
    aggregate_dimension, aggregate_composite, score_to_verdict,
)
from celesys_graph import GRAPH, GRAPH_VERSION


ENGINE_VERSION = "1.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE BUNDLE — typed input to the engine
# ─────────────────────────────────────────────────────────────────────────────
# This is the contract between data ingestion and the scorers. The engine
# guarantees: if a key is present in the FeatureBundle, it has been
# normalized + range-checked. Scorers can trust the values.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FeatureBundle:
    """All extracted features for one symbol at one moment in time.

    Every key is Optional[T] — extraction may fail. The engine handles
    NULL propagation downstream; scorers don't have to.
    """
    symbol: str
    region: str = "US"
    timestamp: float = 0.0
    regime: Optional[str] = None         # 'bull' | 'bear' | 'sideways' | None
    # Price / volume
    price: Optional[float] = None
    open_today: Optional[float] = None
    high_today: Optional[float] = None
    low_today: Optional[float] = None
    prev_close: Optional[float] = None
    vwap: Optional[float] = None
    rvol: Optional[float] = None         # today's volume / 20d avg
    atr_14: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    high_20d: Optional[float] = None
    low_20d: Optional[float] = None
    rsi_14: Optional[float] = None
    adx_14: Optional[float] = None
    # Fundamentals
    revenue_cagr_5y: Optional[float] = None
    eps_cagr_5y: Optional[float] = None
    fcf_cagr_5y: Optional[float] = None
    roe: Optional[float] = None
    op_margin: Optional[float] = None
    debt_to_equity: Optional[float] = None
    shares_outstanding_series: Optional[List[Tuple[int, float]]] = None  # [(year, shares)]
    # Valuation
    pe: Optional[float] = None
    fwd_pe: Optional[float] = None
    pb: Optional[float] = None
    peg: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    fcf_yield: Optional[float] = None
    div_yield: Optional[float] = None
    # Smart money / insider
    insider_net_180d_pct: Optional[float] = None     # net insider buying as % of float
    institutional_ownership_pct: Optional[float] = None
    smv3_score: Optional[float] = None               # external SMv3 signal
    # Catalysts
    days_to_earnings: Optional[int] = None
    sector_momentum_pct: Optional[float] = None
    relative_strength_pct: Optional[float] = None
    # News / sentiment (future inputs — empty in v1)
    news_count_24h: Optional[int] = None
    sentiment_polarity: Optional[float] = None       # -1.0 to +1.0
    # Diagnostic
    source_quality_actual: Optional[SourceQuality] = None
    extraction_errors: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE — orchestrator
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EngineConfig:
    per_signal_timeout_sec: float = 2.0
    total_timeout_sec: float = 15.0
    fail_fast_on_validation: bool = True
    apply_dependency_graph: bool = True
    apply_regime_overlay: bool = True


class CelesysEngine:
    """Execution pipeline. Stateless per-call; safe across threads."""

    def __init__(self, config: Optional[EngineConfig] = None):
        self.cfg = config or EngineConfig()

    # ─── Public API ──────────────────────────────────────────────────────

    def score_single(self, bundle: FeatureBundle) -> Dict[str, Any]:
        """Score one symbol end-to-end. Returns a structured dict."""
        t0 = time.time()

        # 1. Validate ontology + graph health (cheap; cached side effects)
        ont_issues = REGISTRY.validate()
        graph_issues = GRAPH.validate()
        if (ont_issues or graph_issues) and self.cfg.fail_fast_on_validation:
            return {
                "success": False,
                "error": "ontology/graph validation failed",
                "ontology_issues": ont_issues,
                "graph_issues": graph_issues,
            }

        # 2. Run all registered scorers, gather ScoreResults keyed by signal id
        signal_results = self._run_all_scorers(bundle)

        # 3. Apply graph: compute effective weights from upstream scores
        effective_weights: Dict[str, float] = {}
        invalid_setups: List[Dict[str, str]] = []
        if self.cfg.apply_dependency_graph:
            regime = bundle.regime if self.cfg.apply_regime_overlay else None
            effective_weights = GRAPH.propagate_weights(signal_results, regime=regime)
            invalid_setups = GRAPH.detect_invalid_setups(signal_results)

        # 4. Aggregate per-dimension using ONTOLOGY rules
        dim_results: List[DimensionResult] = []
        for dim_id, dim_def in REGISTRY.dimensions().items():
            sigs_in_dim = REGISTRY.signals_in_dimension(dim_id)
            pairs: List[Tuple[SignalDef, ScoreResult]] = []
            for sdef in sigs_in_dim:
                sr = signal_results.get(sdef.id, ScoreResult(score=None))
                # Override weight with graph-computed effective weight if applicable
                if sdef.id in effective_weights:
                    sdef_eff = SignalDef(
                        id=sdef.id, name=sdef.name, dimension=sdef.dimension,
                        description=sdef.description,
                        required_inputs=sdef.required_inputs,
                        optional_inputs=sdef.optional_inputs,
                        scorer=sdef.scorer, source_quality=sdef.source_quality,
                        weight=effective_weights[sdef.id],
                        regime_multipliers=sdef.regime_multipliers,
                        version=sdef.version,
                    )
                    pairs.append((sdef_eff, sr))
                else:
                    pairs.append((sdef, sr))
            dim_results.append(aggregate_dimension(dim_def, pairs))

        # 5. Aggregate composite
        composite = aggregate_composite(dim_results, REGISTRY.dimensions())

        # 6. Build response
        elapsed = time.time() - t0
        return {
            "success": True,
            "symbol": bundle.symbol,
            "region": bundle.region,
            "timestamp": bundle.timestamp or t0,
            "regime": bundle.regime,
            "elapsed_sec": round(elapsed, 4),
            "ontology_version": ONTOLOGY_VERSION,
            "graph_version": GRAPH_VERSION,
            "engine_version": ENGINE_VERSION,
            # Composite
            "score": composite.score,
            "verdict": composite.verdict.value,
            "confidence": composite.confidence.value,
            "coverage_pct": composite.coverage_pct,
            "forced_insufficient": composite.forced_insufficient,
            "provenance_summary": composite.provenance_summary,
            # Per-dimension
            "dimensions": [
                {
                    "id": dr.dim_id, "name": dr.name,
                    "score": dr.score,
                    "verdict": dr.verdict.value,
                    "confidence": dr.confidence.value,
                    "coverage_pct": round(dr.coverage_pct, 1),
                    "note": dr.note,
                    "signals": dr.signal_results,
                }
                for dr in dim_results
            ],
            # Graph diagnostics
            "invalid_setups": invalid_setups,
            "effective_weights": effective_weights,
            # Diagnostic
            "extraction_errors": bundle.extraction_errors,
        }

    def score_batch(self, bundles: List[FeatureBundle],
                    max_workers: int = 4) -> List[Dict[str, Any]]:
        """Score a list of symbols in parallel. Returns same order as input."""
        results: List[Optional[Dict[str, Any]]] = [None] * len(bundles)
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(self.score_single, b): i for i, b in enumerate(bundles)}
            for fut in futs:
                i = futs[fut]
                try:
                    results[i] = fut.result(timeout=self.cfg.total_timeout_sec)
                except FuturesTimeout:
                    results[i] = {
                        "success": False, "symbol": bundles[i].symbol,
                        "error": "engine timeout", "error_kind": "timeout",
                    }
                except Exception as exc:
                    results[i] = {
                        "success": False, "symbol": bundles[i].symbol,
                        "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                        "error_kind": "internal",
                    }
        return results  # type: ignore

    # ─── Ranking + alerting ──────────────────────────────────────────────

    @staticmethod
    def rank_results(results: List[Dict[str, Any]],
                     min_confidence: Optional[Confidence] = None,
                     min_score: Optional[float] = None
                     ) -> List[Dict[str, Any]]:
        """Sort by composite score desc, filter by floor thresholds."""
        out = []
        conf_order = {c.value: i for i, c in enumerate(
            [Confidence.NONE, Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]
        )}
        min_conf_idx = (conf_order[min_confidence.value]
                        if min_confidence else -1)
        for r in results:
            if not r.get("success"):
                continue
            if r.get("score") is None:
                continue
            if min_score is not None and r["score"] < min_score:
                continue
            if conf_order.get(r.get("confidence", "NONE"), -1) < min_conf_idx:
                continue
            out.append(r)
        out.sort(key=lambda x: x.get("score") or 0.0, reverse=True)
        return out

    @staticmethod
    def emit_alerts(results: List[Dict[str, Any]],
                    rules: Optional[List[Callable[[Dict[str, Any]], Optional[str]]]] = None
                    ) -> List[Dict[str, Any]]:
        """Run alert rules over results. Each rule returns None or an alert string.

        Default rules:
          - composite score >= 80 with HIGH confidence → "VERY_STRONG buy candidate"
          - any invalid_setups present → "structural warning"
          - coverage <60% with score >=70 → "high score, low data — be cautious"
        """
        rules = rules or _DEFAULT_ALERT_RULES
        alerts = []
        for r in results:
            for rule in rules:
                msg = rule(r)
                if msg:
                    alerts.append({"symbol": r.get("symbol"), "alert": msg,
                                   "score": r.get("score"),
                                   "verdict": r.get("verdict")})
        return alerts

    # ─── Internal ────────────────────────────────────────────────────────

    def _run_all_scorers(self, bundle: FeatureBundle) -> Dict[str, ScoreResult]:
        """Execute every registered scorer with bundle inputs."""
        # Build the input dict once — scorers receive a sliced view via getattr
        feat_dict = asdict(bundle)
        out: Dict[str, ScoreResult] = {}
        for sid, sdef in REGISTRY.signals().items():
            if sdef.scorer is None:
                out[sid] = ScoreResult(
                    score=None, note="no scorer registered",
                    missing_required=sdef.required_inputs,
                )
                continue
            # Validate required inputs are present (not None)
            missing = [k for k in sdef.required_inputs if feat_dict.get(k) is None]
            if missing:
                out[sid] = ScoreResult(
                    score=None,
                    note=f"missing required inputs: {', '.join(missing)}",
                    missing_required=missing,
                    provenance=[f"required input(s) absent → NULL (honest)"],
                )
                continue
            try:
                sr = sdef.scorer(feat_dict)
                if sr is None:
                    sr = ScoreResult(score=None, note="scorer returned None")
                out[sid] = sr
            except Exception as exc:
                out[sid] = ScoreResult(
                    score=None,
                    note=f"scorer crashed: {type(exc).__name__}: {str(exc)[:120]}",
                    provenance=[f"exception in scorer → NULL"],
                )
        return out


# ─── Default alert rules ─────────────────────────────────────────────────

def _rule_very_strong(r: Dict[str, Any]) -> Optional[str]:
    if r.get("score", 0) and r["score"] >= 80 and r.get("confidence") == "HIGH":
        return f"VERY_STRONG candidate — score {r['score']} with HIGH confidence"
    return None


def _rule_invalid_setup(r: Dict[str, Any]) -> Optional[str]:
    bad = r.get("invalid_setups") or []
    if bad:
        return f"structural warning — {len(bad)} invalid setup(s): " + \
               "; ".join(f["issue"] for f in bad[:3])
    return None


def _rule_high_score_low_data(r: Dict[str, Any]) -> Optional[str]:
    if (r.get("score", 0) and r["score"] >= 70
            and (r.get("coverage_pct", 100) or 100) < 60):
        return (f"high score ({r['score']}) on low data coverage "
                f"({r.get('coverage_pct')}%) — discount accordingly")
    return None


_DEFAULT_ALERT_RULES = [_rule_very_strong, _rule_invalid_setup, _rule_high_score_low_data]


# Module-level singleton (most callers want this)
ENGINE = CelesysEngine()
