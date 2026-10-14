"""
ringscope.algorithms.goldberg
=============================
Goldberg's Exact Flow-Based Densest Subgraph Algorithm.

Formulates the densest subgraph decision and optimization problems using
a bipartite edge-node flow network solved by Dinic's maximum-flow algorithm.

Reference:
----------
Andrew V. Goldberg, "Finding a Maximum Density Subgraph",
Technical Report UCB/CSD-84-171, University of California, Berkeley, 1984.

Network Construction:
---------------------
Given an undirected simple graph G = (V, E) with n = |V| and m = |E|:
1. Source node `s`, Sink node `t`.
2. For each edge e = {u, v} in E, create an edge-node `e`:
   - Edge `s -> e` with capacity 1.0.
   - Edges `e -> u` and `e -> v` with capacity INF.
3. For each original vertex v in V:
   - Edge `v -> t` with capacity `g` (density candidate threshold).

Cut Cost Analysis:
------------------
For any source-side vertex subset S ⊆ V where no INF edge is cut:
- Every edge e = {u, v} with both u, v in S has e on the source side.
- Edges cut from s to edge-nodes: m - |E(S)|.
- Edges cut from vertex-nodes to sink: g * |S|.
- Total cut cost: C(S) = m - |E(S)| + g * |S|.
- The trivial cut (S = ∅) has cost m.
- A cut strictly cheaper than m exists (C(S) < m) if and only if:
  m - |E(S)| + g * |S| < m  <=>  |E(S)| / |S| > g.

INF Capacity Selection:
-----------------------
The maximum possible finite cut cost is bounded by m + g * n.
Since g <= (n - 1) / 2 <= m, any feasible cut has cost <= m + m * n.
Setting INF = 2.0 * m + n² + 10.0 guarantees that cutting even a single
INF edge exceeds any feasible cut cost, strictly preserving the closure.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Union

import networkx as nx

from ringscope.algorithms.dinic import Dinic
from ringscope.graph import TransactionGraph


@dataclass
class GoldbergDecisionResult:
    """Result of a single Goldberg density threshold decision query."""

    threshold_g: float
    """The queried density threshold g."""

    has_denser_subgraph: bool
    """True if a nonempty subgraph S with density > g exists."""

    cut_value: float
    """Capacity of the minimum (s, t)-cut in the bipartite flow network."""

    candidate_nodes: list[str]
    """Source-side original vertex subset S."""

    candidate_density: float
    """Actual recomputed density |E(S)| / |S| on the original graph."""

    theoretical_cut_bound: float
    """Trivial cut baseline m."""


@dataclass
class GoldbergDensestResult:
    """Result of Goldberg's flow-based densest subgraph binary search."""

    nodes: list[str]
    """Vertex identifiers belonging to the densest subgraph."""

    density: float
    """Actual density |E(S)| / |S| recomputed on the original graph."""

    edge_count: int
    """Number of internal undirected edges in the induced subgraph."""

    node_count: int
    """Number of vertices in the candidate subgraph."""

    threshold: float
    """Final converged threshold g."""

    stopping_tolerance: float
    """Binary search convergence epsilon."""

    flow_computations: int
    """Total number of Dinic max-flow invocations."""

    runtime_sec: float
    """Execution time in seconds."""

    is_mathematically_exact: bool = False
    """
    Whether the result is guaranteed mathematically exact.
    Note: Floating-point binary search is tolerance-based (epsilon-optimal).
    Exact rational convergence requires rational arithmetic or theoretical
    stopping threshold eps < 1 / (n * (n - 1)).
    """

    algorithm: str = "goldberg_flow_binary_search"

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "density": self.density,
            "edge_count": self.edge_count,
            "node_count": self.node_count,
            "threshold": self.threshold,
            "stopping_tolerance": self.stopping_tolerance,
            "flow_computations": self.flow_computations,
            "runtime_sec": self.runtime_sec,
            "is_mathematically_exact": self.is_mathematically_exact,
            "algorithm": self.algorithm,
        }


def _extract_graph_components(
    graph: Union[TransactionGraph, nx.Graph, nx.DiGraph],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Extract list of vertices and unique undirected edges from graph."""
    if isinstance(graph, TransactionGraph):
        nodes = [str(n) for n in graph.graph.nodes()]
        # Extract unique undirected edges
        edges = [(str(u), str(v)) for u, v in graph.graph.edges()]
    elif isinstance(graph, (nx.Graph, nx.DiGraph)):
        nodes = [str(n) for n in graph.nodes()]
        if graph.is_directed():
            # Treat as undirected simple edges
            seen = set()
            edges = []
            for u, v in graph.edges():
                su, sv = str(u), str(v)
                if su == sv:
                    continue
                pair = tuple(sorted([su, sv]))
                if pair not in seen:
                    seen.add(pair)
                    edges.append(pair)
        else:
            edges = [
                (str(u), str(v)) for u, v in graph.edges() if str(u) != str(v)
            ]
    else:
        raise TypeError(f"Unsupported graph type: {type(graph)}")

    return nodes, edges


def _compute_undirected_density(
    edges: Sequence[tuple[str, str]], nodes_subset: set[str]
) -> float:
    """Compute undirected density |E(S)| / |S|."""
    k = len(nodes_subset)
    if k == 0:
        return 0.0
    internal_edges = sum(
        1 for u, v in edges if u in nodes_subset and v in nodes_subset
    )
    return internal_edges / k


def goldberg_decision_threshold(
    graph: Union[TransactionGraph, nx.Graph, nx.DiGraph],
    g: float,
) -> GoldbergDecisionResult:
    """
    Goldberg threshold decision procedure.

    Determines whether there exists a nonempty vertex subset S with
    density |E(S)| / |S| > g by solving an (s, t)-min cut problem.

    Parameters
    ----------
    graph : TransactionGraph | nx.Graph
        The input graph.
    g : float
        Candidate density threshold.

    Returns
    -------
    GoldbergDecisionResult
    """
    if g < 0:
        raise ValueError(f"Density threshold g cannot be negative: {g}")

    nodes, edges = _extract_graph_components(graph)
    n = len(nodes)
    m = len(edges)

    if n == 0 or m == 0:
        return GoldbergDecisionResult(
            threshold_g=g,
            has_denser_subgraph=False,
            cut_value=0.0,
            candidate_nodes=[],
            candidate_density=0.0,
            theoretical_cut_bound=0.0,
        )

    # Rigorous INF capacity selection
    # Feasible cut cost <= m + g * n. INF strictly exceeds any feasible cut.
    inf_cap = float(2 * m + (n * n) + 10.0)

    s = "__source__"
    t = "__sink__"

    dinic = Dinic()

    # 1. Source to edge-nodes with capacity 1.0
    for idx, (u, v) in enumerate(edges):
        e_node = f"__e_{idx}__"
        dinic.add_edge(s, e_node, 1.0)
        # Edge-node to endpoint vertex-nodes with INF capacity
        dinic.add_edge(e_node, u, inf_cap)
        dinic.add_edge(e_node, v, inf_cap)

    # 2. Vertex-nodes to sink with capacity g
    for v in nodes:
        dinic.add_edge(v, t, float(g))

    cut_val = dinic.max_flow(s, t)
    source_side = dinic.min_cut_source_side(s)

    # Candidate original vertices in source cut
    candidate_vertices = [v for v in nodes if v in source_side]
    candidate_set = set(candidate_vertices)

    # Cut strictly cheaper than m indicates existence of subset with density > g
    # Tolerance 1e-9 avoids float imprecision
    has_denser = (cut_val < float(m) - 1e-9) and (len(candidate_vertices) > 0)
    actual_density = _compute_undirected_density(edges, candidate_set)

    return GoldbergDecisionResult(
        threshold_g=g,
        has_denser_subgraph=has_denser,
        cut_value=cut_val,
        candidate_nodes=candidate_vertices,
        candidate_density=actual_density,
        theoretical_cut_bound=float(m),
    )


def goldberg_densest_subgraph(
    graph: Union[TransactionGraph, nx.Graph, nx.DiGraph],
    tolerance: float = 1e-4,
    max_iter: Optional[int] = None,
) -> GoldbergDensestResult:
    """
    Binary search for densest subgraph using Goldberg's flow formulation.

    Parameters
    ----------
    graph : TransactionGraph | nx.Graph
        Input graph.
    tolerance : float
        Convergence stopping tolerance (epsilon). Default: 1e-4.
    max_iter : int | None
        Optional hard limit on binary search iterations.

    Returns
    -------
    GoldbergDensestResult
    """
    start_time = time.perf_counter()
    nodes, edges = _extract_graph_components(graph)
    n = len(nodes)
    m = len(edges)

    if n == 0:
        return GoldbergDensestResult(
            nodes=[],
            density=0.0,
            edge_count=0,
            node_count=0,
            threshold=0.0,
            stopping_tolerance=tolerance,
            flow_computations=0,
            runtime_sec=time.perf_counter() - start_time,
            is_mathematically_exact=True,
        )

    if m == 0:
        # Isolated vertices: any single vertex has density 0.0
        return GoldbergDensestResult(
            nodes=[nodes[0]],
            density=0.0,
            edge_count=0,
            node_count=1,
            threshold=0.0,
            stopping_tolerance=tolerance,
            flow_computations=0,
            runtime_sec=time.perf_counter() - start_time,
            is_mathematically_exact=True,
        )

    # Lower bound: 0. Upper bound: (n - 1) / 2 for simple graph or m
    lo = 0.0
    hi = float(min(m, (n - 1) / 2.0 if n > 1 else m))
    if hi <= lo:
        hi = float(m)

    best_nodes: list[str] = nodes[:]
    best_density: float = _compute_undirected_density(edges, set(nodes))
    flow_count = 0
    iteration = 0

    theoretical_exact_bound = 1.0 / (n * (n - 1)) if n > 1 else 1e-6
    is_exact = tolerance <= theoretical_exact_bound

    while (hi - lo) > tolerance:
        if max_iter is not None and iteration >= max_iter:
            break
        iteration += 1

        mid = (lo + hi) / 2.0
        dec = goldberg_decision_threshold(graph, mid)
        flow_count += 1

        if dec.has_denser_subgraph and dec.candidate_nodes:
            lo = mid
            cand_set = set(dec.candidate_nodes)
            cand_density = _compute_undirected_density(edges, cand_set)
            if cand_density > best_density:
                best_density = cand_density
                best_nodes = dec.candidate_nodes
        else:
            hi = mid

    elapsed = time.perf_counter() - start_time
    best_set = set(best_nodes)
    edge_count = sum(1 for u, v in edges if u in best_set and v in best_set)

    return GoldbergDensestResult(
        nodes=sorted(best_nodes),
        density=best_density,
        edge_count=edge_count,
        node_count=len(best_nodes),
        threshold=lo,
        stopping_tolerance=tolerance,
        flow_computations=flow_count,
        runtime_sec=elapsed,
        is_mathematically_exact=is_exact,
    )
