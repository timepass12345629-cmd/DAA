"""
ringscope.algorithms.brute_force
==================================
Brute-force exact densest-subgraph reference solver for small graph instances.

Mathematical Invariant:
For an undirected simple graph G = (V, E) and any non-empty vertex subset S ⊆ V:
    density(S) = |E(S)| / |S|
where E(S) = {{u, v} ∈ E : u ∈ S and v ∈ S}.

Complexity:
O(2^n · (n + m)), strictly exponential.
Documented limit: MAX_BRUTE_FORCE_NODES = 20.
Used strictly as a small-instance verification oracle and benchmark ground truth.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

import networkx as nx

from ringscope.graph import TransactionGraph

MAX_BRUTE_FORCE_NODES: int = 20


@dataclass
class BruteForceResult:
    """Result of an exhaustive densest-subgraph enumeration."""

    nodes: list[str]
    """Vertices in the optimal densest subgraph."""

    density: float
    """Maximum edge density achieved: |E(S*)| / |S*|."""

    edge_count: int
    """Number of internal edges inside the optimal subgraph."""

    node_count: int
    """Number of vertices in the optimal subgraph."""

    subsets_evaluated: int = 0
    """Total number of non-empty subsets evaluated."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "density": self.density,
            "edge_count": self.edge_count,
            "node_count": self.node_count,
            "subsets_evaluated": self.subsets_evaluated,
            "algorithm": "brute_force_exhaustive",
        }


def brute_force_densest_subgraph(
    graph: TransactionGraph | nx.Graph,
    max_nodes: int = MAX_BRUTE_FORCE_NODES,
) -> BruteForceResult:
    """
    Exhaustively evaluate all 2^n - 1 non-empty vertex subsets to find the
    globally optimal densest subgraph.

    Parameters
    ----------
    graph : TransactionGraph | nx.Graph
        Input graph.
    max_nodes : int
        Maximum permitted vertex count (default: 20).

    Returns
    -------
    BruteForceResult
        Optimal vertex set and density.

    Raises
    ------
    ValueError
        If the number of vertices exceeds `max_nodes`.
    """
    nx_graph = graph.graph if isinstance(graph, TransactionGraph) else graph

    nodes = list(nx_graph.nodes())
    n = len(nodes)

    if n > max_nodes:
        raise ValueError(
            f"Graph has {n} vertices, which exceeds the maximum brute-force limit "
            f"of {max_nodes} vertices. Exhaustive enumeration is O(2^n) and intended "
            "strictly as a small-instance verification oracle."
        )

    if n == 0:
        return BruteForceResult(
            nodes=[],
            density=0.0,
            edge_count=0,
            node_count=0,
            subsets_evaluated=0,
        )

    if n == 1:
        return BruteForceResult(
            nodes=[str(nodes[0])],
            density=0.0,
            edge_count=0,
            node_count=1,
            subsets_evaluated=1,
        )

    best_density: float = -1.0
    best_subset: list[str] = [str(nodes[0])]
    best_edges: int = 0
    subsets_evaluated: int = 0

    # Exhaustive enumeration across all subset sizes k in 1..n
    for k in range(1, n + 1):
        for combo in itertools.combinations(nodes, k):
            subsets_evaluated += 1
            combo_set = set(combo)
            subg = nx_graph.subgraph(combo_set)
            edge_count = subg.number_of_edges()
            d = edge_count / k

            # Prefer strictly higher density, or smaller subset on ties for compactness
            if d > best_density:
                best_density = d
                best_subset = sorted(str(v) for v in combo)
                best_edges = edge_count

    return BruteForceResult(
        nodes=best_subset,
        density=best_density,
        edge_count=best_edges,
        node_count=len(best_subset),
        subsets_evaluated=subsets_evaluated,
    )
