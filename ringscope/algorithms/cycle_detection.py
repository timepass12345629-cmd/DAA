"""
ringscope.algorithms.cycle_detection
=====================================
Elementary cycle detection in directed transaction graphs.

Algorithm
---------
Johnson's algorithm (Donald B. Johnson, 1975):
  "Finding All the Elementary Circuits of a Directed Graph"
  SIAM Journal on Computing, 4(1), 77-84.

Complexity
----------
Time  : O((n + e)(c + 1))  where c = number of elementary cycles.
Space : O(n + e)

NetworkX exposes this as ``networkx.simple_cycles``, which we wrap with
transaction-domain filtering (length bounds, amount thresholds, etc.).

Limitations
-----------
- Exponential worst-case output size.
- For large, dense graphs use ``max_cycle_length`` to bound work.
- The algorithm operates on the *aggregated* edge view (one edge per
  src→dst pair); parallel transaction multi-edges are collapsed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

import networkx as nx


@dataclass
class Ring:
    """A detected transaction ring (elementary directed cycle)."""

    nodes: list[str]
    """Ordered list of account IDs forming the ring (last→first closes it)."""

    total_amount: float = 0.0
    """Sum of minimum edge amounts along the ring (flow bottleneck proxy)."""

    min_amount: float = 0.0
    """Bottleneck (minimum) edge amount — limits possible ring volume."""

    length: int = field(init=False)

    def __post_init__(self) -> None:
        self.length = len(self.nodes)

    def edges(self) -> list[tuple[str, str]]:
        """Return directed edges of the ring as (src, dst) pairs."""
        n = self.nodes
        return [(n[i], n[(i + 1) % len(n)]) for i in range(len(n))]

    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "length": self.length,
            "total_amount": self.total_amount,
            "min_amount": self.min_amount,
            "edges": [{"source": u, "target": v} for u, v in self.edges()],
        }


def detect_rings(
    graph: nx.DiGraph,
    min_length: int = 2,
    max_length: int | None = None,
    min_amount: float = 0.0,
    max_rings: int | None = None,
    weight_attr: str = "amount",
) -> list[Ring]:
    """
    Return all elementary cycles in *graph* that satisfy the filters.

    Parameters
    ----------
    graph : nx.DiGraph
        Directed transaction graph.
    min_length : int
        Minimum cycle length (number of nodes). Default 2 (self-loops
        through a single intermediary are length 2).
    max_length : int | None
        Maximum cycle length.  ``None`` = unbounded (use with caution on
        dense graphs).
    min_amount : float
        Exclude rings whose bottleneck edge amount is below this value.
    max_rings : int | None
        Stop after collecting this many rings (useful for large graphs).
    weight_attr : str
        Edge attribute used as the transaction amount.

    Returns
    -------
    list[Ring]
        Rings sorted by descending ``min_amount`` (highest-value rings first).
    """
    results: list[Ring] = []

    cycle_iter: Iterator[list] = nx.simple_cycles(graph, length_bound=max_length)

    for cycle in cycle_iter:
        if len(cycle) < min_length:
            continue

        # Compute ring amount statistics
        amounts: list[float] = []
        for i in range(len(cycle)):
            u = cycle[i]
            v = cycle[(i + 1) % len(cycle)]
            if graph.has_edge(u, v):
                amounts.append(graph[u][v].get(weight_attr, 0.0))
            else:
                amounts.append(0.0)

        bottleneck = min(amounts) if amounts else 0.0
        if bottleneck < min_amount:
            continue

        ring = Ring(
            nodes=cycle,
            total_amount=sum(amounts),
            min_amount=bottleneck,
        )
        results.append(ring)

        if max_rings is not None and len(results) >= max_rings:
            break

    results.sort(key=lambda r: r.min_amount, reverse=True)
    return results


def ring_summary(rings: list[Ring]) -> dict:
    """
    Aggregate statistics over a list of detected rings.

    Returns
    -------
    dict
        Keys: count, avg_length, max_length, min_length,
              total_volume, max_volume, min_volume.
    """
    if not rings:
        return {
            "count": 0,
            "avg_length": 0.0,
            "max_length": 0,
            "min_length": 0,
            "total_volume": 0.0,
            "max_volume": 0.0,
            "min_volume": 0.0,
        }
    lengths = [r.length for r in rings]
    volumes = [r.min_amount for r in rings]
    return {
        "count": len(rings),
        "avg_length": sum(lengths) / len(lengths),
        "max_length": max(lengths),
        "min_length": min(lengths),
        "total_volume": sum(volumes),
        "max_volume": max(volumes),
        "min_volume": min(volumes),
    }
