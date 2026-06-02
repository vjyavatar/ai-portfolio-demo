"""
Celesys Cognitive Architecture — LAYER 2: DEPENDENCY GRAPH (Truth System)
=========================================================================

Defines HOW signals depend on each other. Encodes the institutional logic
that "high RVOL without catalyst = weaker signal" and "VWAP hold without
volume = fake strength".

Implements the doc spec line-by-line:

    GRAPH
    ├── Signal dependencies    → DAG of (upstream → downstream)
    ├── Weight adjustment      → propagate upstream score into downstream weight
    │
    Plus three properties the doc describes:
    ├── Signal weighting becomes dynamic     → propagate_weights()
    ├── Missing data explainability          → failure_trace()
    └── Detection of invalid setups          → detect_invalid_setups()

Design constraints addressed:
  - CYCLES — detected at register time via DFS-with-grey-marker
  - DIAMOND DEPENDENCIES — multiple upstream feeders combine additively
  - OPTIONAL EDGES — required=False; missing optional upstream degrades,
                     missing required upstream forces downstream NULL
  - REGIME OVERLAY — edge can carry regime-specific weight multipliers
  - PERFORMANCE — DAG traversal cached after first topological sort

The graph is REGISTERED ALONGSIDE the ontology but does NOT modify it.
Layer 1 stays clean; Layer 2 is a decorator over Layer 1 outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Iterable
from collections import defaultdict, deque

from celesys_ontology import (
    REGISTRY, SignalDef, ScoreResult, Verdict, score_to_verdict,
)


GRAPH_VERSION = "1.0.0"


@dataclass
class DependencyEdge:
    """One directed edge: upstream_signal → downstream_signal.

    `required`: if True, missing/NULL upstream forces downstream to NULL.
                If False, missing upstream only DEGRADES downstream weight.
    `weight_modifier`: how strongly the upstream affects downstream weight.
                       Default 1.0 = full influence.
    """
    upstream: str
    downstream: str
    required: bool = True
    weight_modifier: float = 1.0
    description: str = ""
    # Optional regime overlay: edge can be active only in certain regimes,
    # or carry regime-specific modifier. Empty = always active at default.
    regime_modifiers: Dict[str, float] = field(default_factory=dict)


class DependencyGraph:
    """Directed acyclic graph of signal dependencies."""

    def __init__(self):
        self._edges_out: Dict[str, List[DependencyEdge]] = defaultdict(list)
        self._edges_in: Dict[str, List[DependencyEdge]] = defaultdict(list)
        self._all_edges: List[DependencyEdge] = []
        self._topo_cache: Optional[List[str]] = None

    # ─── Registration ─────────────────────────────────────────────────────

    def add_edge(self, edge: DependencyEdge) -> None:
        """Add an edge. Raises if it would create a cycle."""
        # Both endpoints must reference known signals (Layer 1 contract)
        if REGISTRY.get_signal(edge.upstream) is None:
            raise ValueError(f"unknown upstream signal: {edge.upstream}")
        if REGISTRY.get_signal(edge.downstream) is None:
            raise ValueError(f"unknown downstream signal: {edge.downstream}")
        if edge.upstream == edge.downstream:
            raise ValueError(f"self-loop not allowed: {edge.upstream}")
        # Cycle check: BEFORE adding, would adding it create a path
        # downstream → ... → upstream? If yes, that's a cycle.
        if self._has_path(edge.downstream, edge.upstream):
            raise ValueError(
                f"adding edge {edge.upstream} → {edge.downstream} would create "
                f"a cycle (existing path {edge.downstream} → ... → {edge.upstream})"
            )
        self._edges_out[edge.upstream].append(edge)
        self._edges_in[edge.downstream].append(edge)
        self._all_edges.append(edge)
        self._topo_cache = None  # invalidate

    def _has_path(self, src: str, dst: str) -> bool:
        """BFS to check if a path exists src → dst in current graph."""
        if src == dst:
            return True
        seen: Set[str] = set()
        q = deque([src])
        while q:
            node = q.popleft()
            if node in seen:
                continue
            seen.add(node)
            for e in self._edges_out.get(node, []):
                if e.downstream == dst:
                    return True
                q.append(e.downstream)
        return False

    # ─── Topological order ────────────────────────────────────────────────

    def topo_sort(self) -> List[str]:
        """Return signals in topological order (upstream first).

        Signals with no edges are still included — they're independent.
        Uses Kahn's algorithm. Cached after first call.
        """
        if self._topo_cache is not None:
            return list(self._topo_cache)

        all_signals = set(REGISTRY.signals().keys())
        in_degree: Dict[str, int] = {s: 0 for s in all_signals}
        for e in self._all_edges:
            in_degree[e.downstream] = in_degree.get(e.downstream, 0) + 1

        ready = deque(sorted([s for s in all_signals if in_degree[s] == 0]))
        ordered: List[str] = []
        in_d = dict(in_degree)
        while ready:
            node = ready.popleft()
            ordered.append(node)
            for e in self._edges_out.get(node, []):
                in_d[e.downstream] -= 1
                if in_d[e.downstream] == 0:
                    ready.append(e.downstream)
        # If anything left with in_degree > 0, we have a cycle — should not
        # happen because add_edge prevents it, but guard anyway.
        if len(ordered) != len(all_signals):
            raise RuntimeError("graph has cycles (should not happen after add_edge guard)")
        self._topo_cache = ordered
        return list(ordered)

    # ─── Validation ───────────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """Structural validation. Returns list of issues (empty = healthy)."""
        issues = []
        # All edge endpoints must be in the ontology
        for e in self._all_edges:
            if REGISTRY.get_signal(e.upstream) is None:
                issues.append(f"edge references unknown upstream {e.upstream}")
            if REGISTRY.get_signal(e.downstream) is None:
                issues.append(f"edge references unknown downstream {e.downstream}")
            if not (0.0 <= e.weight_modifier <= 2.0):
                issues.append(f"edge {e.upstream}→{e.downstream}: weight_modifier "
                              f"{e.weight_modifier} outside [0,2]")
        # Try topo sort to surface cycles
        try:
            self.topo_sort()
        except RuntimeError as exc:
            issues.append(f"topo sort failed: {exc}")
        return issues

    # ─── Weight propagation ───────────────────────────────────────────────

    def propagate_weights(self,
                          signal_results: Dict[str, ScoreResult],
                          regime: Optional[str] = None
                          ) -> Dict[str, float]:
        """Compute effective weight for each signal given upstream strength.

        Algorithm (per downstream node, in topo order):
            base_weight = SignalDef.weight                       (from Layer 1)
            for each incoming edge:
                upstream_score = signal_results[e.upstream].score (or None)
                modifier = e.weight_modifier
                if regime and e.regime_modifiers.has(regime):
                    modifier *= e.regime_modifiers[regime]
                if upstream_score is None:
                    if e.required:
                        downstream_weight *= 0  → effectively muted
                    else:
                        downstream_weight *= 0.5  → degraded
                else:
                    # Map upstream score 0-100 → factor in [0.3, 1.2]:
                    #   100 → 1.2 (strong upstream amplifies)
                    #    50 → 0.75 (neutral upstream → neutral weight)
                    #     0 → 0.3 (weak upstream attenuates)
                    factor = 0.3 + (upstream_score / 100.0) * 0.9
                    downstream_weight *= factor * modifier
            effective_weights[downstream] = downstream_weight

        Returns: {signal_id: effective_weight}.
        """
        effective: Dict[str, float] = {}
        for sid in self.topo_sort():
            sdef = REGISTRY.get_signal(sid)
            if sdef is None:
                continue
            w = sdef.weight
            for e in self._edges_in.get(sid, []):
                up_score = (signal_results.get(e.upstream).score
                            if e.upstream in signal_results else None)
                mod = e.weight_modifier
                if regime and regime in e.regime_modifiers:
                    mod *= e.regime_modifiers[regime]
                if up_score is None:
                    if e.required:
                        w = 0.0
                    else:
                        w *= 0.5 * mod
                else:
                    factor = 0.3 + (max(0.0, min(100.0, up_score)) / 100.0) * 0.9
                    w *= factor * mod
            effective[sid] = round(max(0.0, w), 4)
        return effective

    # ─── Explainability ───────────────────────────────────────────────────

    def failure_trace(self,
                      signal_id: str,
                      signal_results: Dict[str, ScoreResult]
                      ) -> List[str]:
        """For a NULL or weak signal, walk upstream and list what failed.

        Produces lines like:
          "rvol_5m: missing upstream catalyst_present (required) → muted"
          "vwap_hold: upstream rvol_5m scored 28/100 (WEAK) → degraded"
        """
        trace = []
        for e in self._edges_in.get(signal_id, []):
            up = signal_results.get(e.upstream)
            up_score = up.score if up else None
            if up_score is None:
                req_label = "required" if e.required else "optional"
                trace.append(f"upstream {e.upstream} has no data ({req_label})"
                             f"{' → muted' if e.required else ' → degraded'}")
            elif up_score < 40:
                v = score_to_verdict(up_score).value
                trace.append(f"upstream {e.upstream} scored {up_score}/100 ({v}) "
                             f"→ attenuates downstream weight")
        return trace

    # ─── Invalid setup detection ──────────────────────────────────────────

    def detect_invalid_setups(self,
                              signal_results: Dict[str, ScoreResult]
                              ) -> List[Dict[str, str]]:
        """Flag combinations the institutional logic considers structurally invalid.

        Example: "breakout score is STRONG but rvol upstream is WEAK" → fake breakout.

        Returns a list of flag dicts:
            [{"signal": "breakout", "verdict": "STRONG",
              "issue": "missing volume confirmation",
              "fix": "reduce downstream weight or flag as low-quality setup"}]
        """
        flags = []
        for sid, sr in signal_results.items():
            if sr.score is None or sr.score < 60:
                continue  # only flag if signal claims strength
            for e in self._edges_in.get(sid, []):
                if not e.required:
                    continue
                up = signal_results.get(e.upstream)
                up_score = up.score if up else None
                if up_score is None:
                    flags.append({
                        "signal": sid, "verdict": score_to_verdict(sr.score).value,
                        "issue": f"upstream '{e.upstream}' missing (required)",
                        "fix": "data gap; do not trust this signal",
                    })
                elif up_score < 40:
                    flags.append({
                        "signal": sid, "verdict": score_to_verdict(sr.score).value,
                        "issue": f"upstream '{e.upstream}' is WEAK ({up_score}/100) "
                                 f"while downstream claims strength",
                        "fix": "structurally invalid setup — discount or skip",
                    })
        return flags

    # ─── Introspection ────────────────────────────────────────────────────

    def upstream_of(self, sid: str) -> List[str]:
        return [e.upstream for e in self._edges_in.get(sid, [])]

    def downstream_of(self, sid: str) -> List[str]:
        return [e.downstream for e in self._edges_out.get(sid, [])]

    def edges(self) -> List[DependencyEdge]:
        return list(self._all_edges)


# Module-level singleton
GRAPH = DependencyGraph()


def add_edge(upstream: str, downstream: str, required: bool = True,
             weight_modifier: float = 1.0, description: str = "",
             regime_modifiers: Optional[Dict[str, float]] = None) -> None:
    """Convenience: register an edge on the module-level graph."""
    GRAPH.add_edge(DependencyEdge(
        upstream=upstream, downstream=downstream,
        required=required, weight_modifier=weight_modifier,
        description=description,
        regime_modifiers=regime_modifiers or {},
    ))
