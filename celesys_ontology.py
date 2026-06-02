"""
Celesys Cognitive Architecture — LAYER 1: ONTOLOGY (Meaning System)
====================================================================

Defines what "Signal / Dimension / Score / Verdict / Confidence" mean
across the entire Celesys platform. Every downstream system (scanner,
alerts, ML, dashboard) reads from this single source of truth.

Implements the doc spec line-by-line:

    ONTOLOGY
    ├── Dimensions          → DimensionDef registry
    ├── Signals             → SignalDef registry
    ├── Verdict rules       → VERDICT_BANDS (5-band 0-100 mapping)
    ├── Confidence rules    → ConfidenceModel (completeness × stability × source quality)
    └── Missing data rules  → NULL_PROPAGATION (no fake-neutral floor)

Design constraints surfaced during pre-build audit:
  - Cycles in dependency graph (handled in Layer 2)
  - Diamond dependencies — additive weight at convergence node
  - Optional vs required upstream — explicit `required: bool` per edge
  - Versioning — ontology version stamped on every output
  - Regime overlay — DimensionDef can declare regime-specific weight multipliers
  - Auditability — every Score carries a `provenance` list of every input + rule applied

Author: r63.100.0 Celesys Cognitive Architecture
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum

# ─────────────────────────────────────────────────────────────────────────────
# ONTOLOGY VERSION — bumped whenever the schema changes incompatibly
# ─────────────────────────────────────────────────────────────────────────────
ONTOLOGY_VERSION = "1.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# VERDICT BANDS — single source of truth for "what does a number MEAN"
# ─────────────────────────────────────────────────────────────────────────────
# Every Signal and every Dimension normalizes to a 0-100 score. The verdict
# is derived from this score using a single shared band scheme. This is the
# foundational rule that makes scoring consistent across markets/timeframes.
#
# Why 5 bands not 3: institutional setups distinguish "average" from "leans
# positive" from "very strong" — collapsing to 3 loses signal.

class Verdict(str, Enum):
    VERY_WEAK = "VERY_WEAK"
    WEAK = "WEAK"
    NEUTRAL = "NEUTRAL"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # special — not a band, a flag


VERDICT_BANDS: List[Tuple[float, float, Verdict]] = [
    # (lo_inclusive, hi_exclusive, verdict)
    (0.0,  20.0, Verdict.VERY_WEAK),
    (20.0, 40.0, Verdict.WEAK),
    (40.0, 60.0, Verdict.NEUTRAL),
    (60.0, 80.0, Verdict.STRONG),
    (80.0, 100.01, Verdict.VERY_STRONG),  # 100.01 so 100.0 falls in
]


def score_to_verdict(score: Optional[float]) -> Verdict:
    """Single rule converting normalized 0-100 score → Verdict.

    NULL score → INSUFFICIENT_DATA (never falls through to a band).
    This is the most important rule in the system. Do NOT bypass.
    """
    if score is None:
        return Verdict.INSUFFICIENT_DATA
    if not isinstance(score, (int, float)) or math.isnan(score):
        return Verdict.INSUFFICIENT_DATA
    s = max(0.0, min(100.0, float(score)))
    for lo, hi, v in VERDICT_BANDS:
        if lo <= s < hi:
            return v
    return Verdict.INSUFFICIENT_DATA  # should not reach (covers 100.0 edge)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIDENCE MODEL — completeness × stability × source_quality
# ─────────────────────────────────────────────────────────────────────────────
# Confidence is SEPARATE from score. A "STRONG" verdict on incomplete data is
# not the same as "STRONG" on complete data. Confidence captures this.

class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class SourceQuality(str, Enum):
    PRIMARY = "PRIMARY"        # exchange feeds, regulatory filings
    SECONDARY = "SECONDARY"    # yfinance, Google Finance
    HEURISTIC = "HEURISTIC"    # derived/proxied from imperfect inputs
    UNKNOWN = "UNKNOWN"


@dataclass
class ConfidenceComponents:
    """Inputs that determine final confidence."""
    completeness_pct: float = 0.0   # 0-100, what % of expected inputs are present
    stability_pct: float = 50.0     # 0-100, low variance across recent samples = high
    source_quality: SourceQuality = SourceQuality.SECONDARY

    def compute(self) -> Confidence:
        """Map components → final Confidence band.

        Rules (in order — first match wins):
          - completeness < 30  → NONE          (too sparse to claim anything)
          - completeness < 60  → LOW           (significant gaps)
          - completeness < 85  → MEDIUM        (partial — flag it)
          - source HEURISTIC   → cap at MEDIUM (no matter how complete)
          - source UNKNOWN     → cap at LOW
          - stability < 30     → drop one band (volatile sample = low trust)
          - else               → HIGH
        """
        if self.completeness_pct < 30:
            return Confidence.NONE
        if self.completeness_pct < 60:
            return Confidence.LOW
        if self.completeness_pct < 85:
            base = Confidence.MEDIUM
        else:
            base = Confidence.HIGH
        # Source quality cap
        if self.source_quality == SourceQuality.HEURISTIC and base == Confidence.HIGH:
            base = Confidence.MEDIUM
        if self.source_quality == SourceQuality.UNKNOWN:
            base = Confidence.LOW
        # Stability downgrade
        if self.stability_pct < 30:
            order = [Confidence.NONE, Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]
            idx = max(0, order.index(base) - 1)
            base = order[idx]
        return base


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL — the atomic unit. Every measurable thing is a Signal.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SignalDef:
    """Definition of an atomic Signal (RVOL, VWAP hold, breakout, PEG, etc).

    A SignalDef is REGISTERED ONCE at module load. It is metadata — it does
    NOT carry runtime data. Runtime data is a SignalReading.
    """
    id: str                          # canonical key e.g. "rvol_5m"
    name: str                        # human-readable e.g. "Relative Volume 5min"
    dimension: str                   # parent Dimension id (FK to DimensionDef)
    description: str                 # what it measures, in plain English
    # Required inputs from the upstream feature extractor.
    # Engine validates these before invoking the scorer.
    required_inputs: List[str] = field(default_factory=list)
    optional_inputs: List[str] = field(default_factory=list)
    # The scorer: takes a dict of inputs → returns ScoreResult.
    # Set by @register_signal decorator.
    scorer: Optional[Callable[[Dict[str, Any]], "ScoreResult"]] = None
    # Source quality declared at registration time. Engine uses this to
    # initialize the confidence component.
    source_quality: SourceQuality = SourceQuality.SECONDARY
    # Weight in the dimension. 0.0-1.0 within-dimension. Engine normalizes.
    weight: float = 1.0
    # Optional: regime multipliers. Example: {"bull": 1.0, "bear": 0.7}
    # If absent, no regime-based adjustment is applied.
    regime_multipliers: Dict[str, float] = field(default_factory=dict)
    # Version tag — bumped when scorer logic changes incompatibly.
    version: str = "1.0.0"


@dataclass
class ScoreResult:
    """What every Signal scorer returns.

    score: 0-100 normalized, OR None when the scorer cannot produce a score
           (missing required inputs, contradictory data, etc).
           NULL is honest — never substitute a "neutral" floor.

    raw: the underlying measurement (e.g. RVOL=2.3, PEG=0.85). For audit.
    verdict_override: rare cases where the verdict shouldn't follow the score
                      band (e.g. "stock split detected" → neutral but flagged).
    provenance: ordered list of strings explaining HOW the score was derived.
                Critical for explainability. Every rule applied gets a line.
    inputs_used: dict of the actual input values consumed. Audit trail.
    missing_required: list of required input keys that were absent → triggers NULL.
    """
    score: Optional[float] = None
    raw: Any = None
    verdict_override: Optional[Verdict] = None
    note: str = ""
    provenance: List[str] = field(default_factory=list)
    inputs_used: Dict[str, Any] = field(default_factory=dict)
    missing_required: List[str] = field(default_factory=list)
    source_quality_actual: Optional[SourceQuality] = None  # may downgrade from declared


# ─────────────────────────────────────────────────────────────────────────────
# DIMENSION — a thematic cluster of Signals (Fundamentals, Momentum, etc).
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DimensionDef:
    """A Dimension aggregates signals under one theme.

    Aggregation rule: weighted mean of non-NULL signal scores, with separate
    handling for >50% NULL → entire dimension becomes INSUFFICIENT_DATA.

    `weight` here is the dimension's contribution to the OVERALL composite
    score (sums to 1.0 across all dimensions registered for a profile).
    """
    id: str
    name: str
    description: str
    weight: float = 1.0
    # If at least this fraction of expected signals must be non-NULL or the
    # dimension reports INSUFFICIENT_DATA. Default 0.5 = need ≥50% coverage.
    min_coverage_for_score: float = 0.5
    # Optional regime weight multipliers at the dimension level too.
    regime_multipliers: Dict[str, float] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY — single source of truth for all Dimensions + Signals
# ─────────────────────────────────────────────────────────────────────────────

class OntologyRegistry:
    """Module-level registry. Singleton-by-import."""

    def __init__(self):
        self._dimensions: Dict[str, DimensionDef] = {}
        self._signals: Dict[str, SignalDef] = {}
        self._frozen = False  # once frozen, no more registrations

    def register_dimension(self, d: DimensionDef) -> None:
        if self._frozen:
            raise RuntimeError(f"Ontology frozen; cannot register dimension {d.id}")
        if d.id in self._dimensions:
            raise ValueError(f"Dimension already registered: {d.id}")
        if d.weight < 0:
            raise ValueError(f"Dimension {d.id}: weight must be >= 0")
        if not (0.0 <= d.min_coverage_for_score <= 1.0):
            raise ValueError(f"Dimension {d.id}: min_coverage_for_score must be in [0,1]")
        self._dimensions[d.id] = d

    def register_signal(self, s: SignalDef) -> None:
        if self._frozen:
            raise RuntimeError(f"Ontology frozen; cannot register signal {s.id}")
        if s.id in self._signals:
            raise ValueError(f"Signal already registered: {s.id}")
        if s.dimension not in self._dimensions:
            raise ValueError(
                f"Signal {s.id} declares unknown dimension '{s.dimension}'. "
                f"Register the DimensionDef first."
            )
        if s.weight < 0:
            raise ValueError(f"Signal {s.id}: weight must be >= 0")
        # Sanity: required_inputs and optional_inputs must not overlap
        rs = set(s.required_inputs); os_ = set(s.optional_inputs)
        if rs & os_:
            raise ValueError(
                f"Signal {s.id}: input keys cannot be both required and optional: {rs & os_}"
            )
        self._signals[s.id] = s

    def freeze(self):
        """Lock the registry — future registrations will error."""
        self._frozen = True

    def dimensions(self) -> Dict[str, DimensionDef]:
        return dict(self._dimensions)

    def signals(self) -> Dict[str, SignalDef]:
        return dict(self._signals)

    def signals_in_dimension(self, dim_id: str) -> List[SignalDef]:
        return [s for s in self._signals.values() if s.dimension == dim_id]

    def get_signal(self, sid: str) -> Optional[SignalDef]:
        return self._signals.get(sid)

    def get_dimension(self, did: str) -> Optional[DimensionDef]:
        return self._dimensions.get(did)

    def validate(self) -> List[str]:
        """Return a list of structural issues. Empty list = healthy."""
        issues = []
        # Every signal's dimension must exist
        for sid, s in self._signals.items():
            if s.dimension not in self._dimensions:
                issues.append(f"orphan signal {sid} → dim {s.dimension}")
            if s.scorer is None:
                issues.append(f"signal {sid} has no scorer attached")
        # Dimension weights should sum to ~1.0 (warn if not — not fatal)
        total_w = sum(d.weight for d in self._dimensions.values())
        if abs(total_w - 1.0) > 0.01:
            issues.append(f"dimension weights sum to {total_w:.3f}, not 1.0 (will be normalized)")
        return issues


# Module-level singleton
REGISTRY = OntologyRegistry()


# ─────────────────────────────────────────────────────────────────────────────
# DECORATORS — ergonomic registration
# ─────────────────────────────────────────────────────────────────────────────

def register_signal(sig_id: str, dimension: str, name: str, description: str = "",
                    required_inputs: Optional[List[str]] = None,
                    optional_inputs: Optional[List[str]] = None,
                    source_quality: SourceQuality = SourceQuality.SECONDARY,
                    weight: float = 1.0,
                    regime_multipliers: Optional[Dict[str, float]] = None,
                    version: str = "1.0.0"):
    """Decorator: wraps a scorer function and registers it as a Signal."""
    def deco(fn: Callable[[Dict[str, Any]], ScoreResult]):
        sdef = SignalDef(
            id=sig_id, name=name, dimension=dimension, description=description,
            required_inputs=required_inputs or [],
            optional_inputs=optional_inputs or [],
            scorer=fn, source_quality=source_quality, weight=weight,
            regime_multipliers=regime_multipliers or {}, version=version,
        )
        REGISTRY.register_signal(sdef)
        return fn
    return deco


# ─────────────────────────────────────────────────────────────────────────────
# AGGREGATION RULES — Dimension-level + Composite-level
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DimensionResult:
    dim_id: str
    name: str
    score: Optional[float]           # 0-100 normalized, NULL if INSUFFICIENT
    verdict: Verdict
    coverage_pct: float              # what % of signals contributed
    signal_results: List[Dict[str, Any]] = field(default_factory=list)
    confidence: Confidence = Confidence.NONE
    note: str = ""


@dataclass
class CompositeResult:
    score: Optional[float]
    verdict: Verdict
    confidence: Confidence
    coverage_pct: float              # overall data coverage 0-100
    dimensions: List[DimensionResult] = field(default_factory=list)
    ontology_version: str = ONTOLOGY_VERSION
    provenance_summary: str = ""
    forced_insufficient: bool = False  # True if coverage too low to recommend


def aggregate_dimension(dim: DimensionDef,
                        signal_results: List[Tuple[SignalDef, ScoreResult]]
                        ) -> DimensionResult:
    """Aggregate a dimension's signals into a single 0-100 score.

    Honest NULL rules:
      - Each signal returns either a number or NULL.
      - Weighted mean computed over NON-NULL signals only.
      - If non-NULL count / total < min_coverage_for_score → entire dimension
        becomes INSUFFICIENT_DATA (score=None). This is the rule that prevents
        4 missing components × 2/4 floor = 50% "FAIR" verdict on no data.

    Confidence:
      - completeness = real_signals / total_signals × 100
      - source_quality = worst across contributing signals
      - stability = placeholder 50.0 (no history yet; v1.1 will compute)
    """
    total = len(signal_results)
    if total == 0:
        return DimensionResult(dim_id=dim.id, name=dim.name,
                               score=None, verdict=Verdict.INSUFFICIENT_DATA,
                               coverage_pct=0.0, signal_results=[],
                               confidence=Confidence.NONE,
                               note="no signals registered for this dimension")

    non_null = [(sdef, sr) for sdef, sr in signal_results if sr.score is not None]
    coverage = len(non_null) / total

    # Render each signal for the response
    rendered = []
    for sdef, sr in signal_results:
        rendered.append({
            "id": sdef.id, "name": sdef.name,
            "score": sr.score, "max": 100,
            "verdict": (sr.verdict_override.value if sr.verdict_override
                        else score_to_verdict(sr.score).value),
            "raw": sr.raw, "note": sr.note,
            "missing_required": sr.missing_required,
            "provenance": sr.provenance,
            "weight": sdef.weight, "version": sdef.version,
        })

    if coverage < dim.min_coverage_for_score:
        return DimensionResult(
            dim_id=dim.id, name=dim.name, score=None,
            verdict=Verdict.INSUFFICIENT_DATA, coverage_pct=coverage * 100,
            signal_results=rendered, confidence=Confidence.NONE,
            note=f"only {len(non_null)}/{total} signals had data "
                 f"({coverage*100:.0f}%); below required {dim.min_coverage_for_score*100:.0f}%",
        )

    # Weighted mean
    total_w = sum(sdef.weight for sdef, _ in non_null)
    if total_w <= 0:
        return DimensionResult(
            dim_id=dim.id, name=dim.name, score=None,
            verdict=Verdict.INSUFFICIENT_DATA, coverage_pct=coverage * 100,
            signal_results=rendered, confidence=Confidence.NONE,
            note="non-null signals had zero total weight",
        )
    weighted = sum(sr.score * sdef.weight for sdef, sr in non_null) / total_w

    # Source quality = worst across contributors
    sq_order = [SourceQuality.PRIMARY, SourceQuality.SECONDARY,
                SourceQuality.HEURISTIC, SourceQuality.UNKNOWN]
    worst_sq = SourceQuality.PRIMARY
    for sdef, sr in non_null:
        actual = sr.source_quality_actual or sdef.source_quality
        if sq_order.index(actual) > sq_order.index(worst_sq):
            worst_sq = actual

    conf = ConfidenceComponents(
        completeness_pct=coverage * 100,
        stability_pct=50.0,  # v1.1: track stability over time
        source_quality=worst_sq,
    ).compute()

    return DimensionResult(
        dim_id=dim.id, name=dim.name, score=round(weighted, 2),
        verdict=score_to_verdict(weighted), coverage_pct=coverage * 100,
        signal_results=rendered, confidence=conf,
        note=f"weighted mean of {len(non_null)}/{total} signals",
    )


def aggregate_composite(dim_results: List[DimensionResult],
                        dim_defs: Dict[str, DimensionDef]) -> CompositeResult:
    """Aggregate dimensions into the overall composite score.

    Rules:
      - Composite = weighted mean of dimensions with score != None.
      - Weights from DimensionDef.weight, normalized over non-NULL dims.
      - If overall coverage < 60% → forced INSUFFICIENT_DATA (no recommendation).
      - Confidence = worst across contributing dimensions, with cap rules:
          * any dim INSUFFICIENT → composite confidence ≤ MEDIUM
          * coverage <70% → composite confidence ≤ LOW
    """
    non_null = [dr for dr in dim_results if dr.score is not None]
    total_dims = len(dim_results)
    if total_dims == 0:
        return CompositeResult(score=None, verdict=Verdict.INSUFFICIENT_DATA,
                               confidence=Confidence.NONE, coverage_pct=0.0)

    # Overall coverage = mean of dimension coverages
    overall_coverage = sum(dr.coverage_pct for dr in dim_results) / total_dims

    if len(non_null) == 0 or overall_coverage < 60.0:
        return CompositeResult(
            score=None, verdict=Verdict.INSUFFICIENT_DATA,
            confidence=Confidence.NONE,
            coverage_pct=round(overall_coverage, 2),
            dimensions=dim_results, forced_insufficient=True,
            provenance_summary=f"overall coverage {overall_coverage:.0f}% < 60% threshold; "
                               f"refusing to recommend",
        )

    weights = []
    scores = []
    for dr in non_null:
        ddef = dim_defs.get(dr.dim_id)
        w = ddef.weight if ddef else 1.0
        weights.append(w)
        scores.append(dr.score)
    total_w = sum(weights)
    if total_w <= 0:
        return CompositeResult(
            score=None, verdict=Verdict.INSUFFICIENT_DATA,
            confidence=Confidence.NONE,
            coverage_pct=round(overall_coverage, 2),
            dimensions=dim_results, forced_insufficient=True,
            provenance_summary="dimensions have zero total weight",
        )
    composite = sum(s * w for s, w in zip(scores, weights)) / total_w

    # Confidence caps
    any_insuf = any(dr.score is None for dr in dim_results)
    conf_order = [Confidence.NONE, Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]
    worst_conf = Confidence.HIGH
    for dr in non_null:
        if conf_order.index(dr.confidence) < conf_order.index(worst_conf):
            worst_conf = dr.confidence
    # Cap rules
    if any_insuf and conf_order.index(worst_conf) > conf_order.index(Confidence.MEDIUM):
        worst_conf = Confidence.MEDIUM
    if overall_coverage < 70 and conf_order.index(worst_conf) > conf_order.index(Confidence.LOW):
        worst_conf = Confidence.LOW

    return CompositeResult(
        score=round(composite, 2), verdict=score_to_verdict(composite),
        confidence=worst_conf, coverage_pct=round(overall_coverage, 2),
        dimensions=dim_results,
        provenance_summary=f"weighted mean of {len(non_null)}/{total_dims} dimensions; "
                           f"coverage {overall_coverage:.0f}%",
    )
