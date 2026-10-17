"""
ringscope.algorithms.densest_subgraph
=======================================
Densest-subgraph algorithms for directed transaction graphs.

Two algorithms are provided:

1. **Charikar Greedy (2-approximation)**
   Greedy peeling: iteratively remove the node with minimum weighted degree.
   Guarantees density ≥ OPT / 2.
   Reference: Moses Charikar, "Greedy approximation algorithms for finding
   dense components in a graph", APPROX 2000.
   Complexity: O((n + e) log n)

2. **Flow-Based Exact (Goldberg 1984)**
   Binary search over candidate densities + max-flow feasibility test.
   Exact optimum, but slower: O(n² * e * log n) in the worst case.
   Reference: Andrew V. Goldberg, "Finding a Maximum Density Subgraph",
   UCB/CSD-84-171, 1984.
   We use NetworkX's max-flow (Dinic's algorithm internally).

Density definition (undirected view)
-------------------------------------
  density(S) = |E(S)| / |S|
where E(S) is the set of edges with both endpoints in S, and |S| = |V(S)|.

For directed graphs we use the *symmetric* edge count:
  |E(S)| = edges_in_subgraph(S, counting each direction separately)
which reduces to the standard undirected definition on the underlying
undirected graph.

Limitations
-----------
- Exact algorithm is practical up to ~500 nodes; use greedy for larger.
- Density is a size-normalised measure; it does not directly capture
  ring volume.  Use ring_detection for that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import networkx as nx
import numpy as np


@dataclass
class DenseSubgraph:
    """Result of a densest-subgraph query."""

    nodes: list[str]
    """Nodes in the densest subgraph found."""

    density: float
    """Edge density = |E(S)| / |S|."""

    algorithm: str
    """Algorithm name: 'greedy_charikar' or 'exact_goldberg'."""

    edge_count: int = 0
    """Number of directed edges inside the subgraph."""

    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "density": self.density,
            "algorithm": self.algorithm,
            "edge_count": self.edge_count,
            "node_count": len(self.nodes),
        }


def _directed_density(graph: nx.DiGraph, nodes: set) -> float:
    """Compute directed edge density of a node subset."""
    if len(nodes) <= 1:
        return 0.0
    edge_count = sum(1 for u, v in graph.edges() if u in nodes and v in nodes)
    return edge_count / len(nodes)


def greedy_charikar(
    graph: nx.DiGraph,
    weight_attr: Optional[str] = None,
) -> DenseSubgraph:
    """
    Charikar's 2-approximation greedy peeling for densest subgraph.

    The algorithm works on the *undirected* view of the graph:
      - Degree of a node = in-degree + out-degree in the subgraph.
      - At each step remove the node with minimum (weighted) degree.
      - Track the subgraph with the maximum density seen.

    Parameters
    ----------
    graph : nx.DiGraph
    weight_attr : str | None
        If provided, uses weighted degree instead of plain degree.

    Returns
    -------
    DenseSubgraph
    """
    if graph.number_of_nodes() == 0:
        return DenseSubgraph(nodes=[], density=0.0, algorithm="greedy_charikar")

    # Work on a mutable copy of the undirected graph for degree tracking
    ug: nx.Graph = graph.to_undirected()

    if weight_attr is not None:

        def degree_fn(g, n):
            return g.degree(n, weight=weight_attr)
    else:

        def degree_fn(g, n):
            return g.degree(n)

    current_nodes: set[str] = set(ug.nodes())
    best_nodes: set[str] = set(current_nodes)
    best_density: float = _directed_density(graph, current_nodes)

    while len(current_nodes) > 1:
        # Find node with minimum degree in the current induced subgraph
        subg = ug.subgraph(current_nodes)
        min_node = min(current_nodes, key=lambda n: degree_fn(subg, n))
        current_nodes.remove(min_node)

        d = _directed_density(graph, current_nodes)
        if d > best_density:
            best_density = d
            best_nodes = set(current_nodes)

    node_list = list(best_nodes)
    edge_count = sum(1 for u, v in graph.edges() if u in best_nodes and v in best_nodes)
    return DenseSubgraph(
        nodes=node_list,
        density=best_density,
        algorithm="greedy_charikar",
        edge_count=edge_count,
    )


def exact_goldberg(
    graph: nx.DiGraph,
    precision: float = 1e-6,
) -> DenseSubgraph:
    """
    Exact densest-subgraph via binary search + max-flow (Picard / Goldberg closure).

    Formulates the problem of finding a non-empty subset S of vertices
    maximizing directed edge density |E(S)| / |S| as a sequence of minimum cut
    computations on a closure network (Picard 1976, Goldberg 1984).

    For candidate density threshold alpha:
      Nodes: Source 's', Sink 't', an edge-node for each directed edge e=(u, v),
             and each vertex v in V.
      Edges:
        s -> e with capacity 1.0 (for each directed edge)
        e -> u and e -> v with infinite capacity
        v -> t with capacity alpha (for each vertex v in V)

    The capacity of an (s, t)-cut separating S from T is:
      |E| - (|E(S)| - alpha * |S|)
    which is strictly less than |E| if and only if |E(S)| / |S| > alpha.
    Binary search over alpha in [0, |E|] converges to the global maximum density.

    Complexity: O(iterations * max_flow(|V| + |E|, 3|E| + |V|)).
    Guaranteed: Exact density >= Greedy density for all graphs.

    Parameters
    ----------
    graph : nx.DiGraph
        Input directed transaction graph.
    precision : float
        Convergence tolerance for the binary search.

    Returns
    -------
    DenseSubgraph  (algorithm='exact_goldberg')
    """
    n = graph.number_of_nodes()
    if n == 0:
        return DenseSubgraph(nodes=[], density=0.0, algorithm="exact_goldberg", edge_count=0)
    if n == 1:
        node = list(graph.nodes())[0]
        return DenseSubgraph(nodes=[node], density=0.0, algorithm="exact_goldberg", edge_count=0)

    nodes = list(graph.nodes())
    edges = list(graph.edges())
    m = len(edges)
    if m == 0:
        return DenseSubgraph(nodes=nodes[:1], density=0.0, algorithm="exact_goldberg", edge_count=0)

    # Binary search bounds: density in [0, m]
    lo: float = 0.0
    hi: float = float(m)
    best_subgraph_nodes: list[str] = nodes[:]

    # Maximum iterations to guarantee precision
    max_iter = int(np.ceil(np.log2((hi - lo) / precision))) + 5

    s, t = "__source__", "__sink__"

    for _ in range(max_iter):
        if hi - lo < precision:
            break
        alpha = (lo + hi) / 2.0

        flow_g = nx.DiGraph()
        flow_g.add_node(s)
        flow_g.add_node(t)

        for i, (u, v) in enumerate(edges):
            e_node = f"__e_{i}__"
            flow_g.add_edge(s, e_node, capacity=1.0)
            flow_g.add_edge(e_node, u, capacity=float("inf"))
            flow_g.add_edge(e_node, v, capacity=float("inf"))

        for v in nodes:
            flow_g.add_edge(v, t, capacity=alpha)

        cut_value, partition = nx.minimum_cut(flow_g, s, t)
        reachable = partition[0]
        candidate = [v for v in nodes if v in reachable]

        if candidate and cut_value < float(m) - 1e-9:
            lo = alpha
            best_subgraph_nodes = candidate
        else:
            hi = alpha

    best_set = set(best_subgraph_nodes)
    final_density = _directed_density(graph, best_set)
    edge_count = sum(1 for u, v in graph.edges() if u in best_set and v in best_set)
    return DenseSubgraph(
        nodes=best_subgraph_nodes,
        density=final_density,
        algorithm="exact_goldberg",
        edge_count=edge_count,
    )


def densest_subgraph(
    graph: nx.DiGraph,
    algorithm: str = "greedy",
    **kwargs,
) -> DenseSubgraph:
    """
    Unified entry point.

    Parameters
    ----------
    graph : nx.DiGraph
    algorithm : str
        'greedy' / 'greedy_charikar' → Charikar 2-approximation (default, fast)
        'exact' / 'goldberg'         → Goldberg exact (slow, use only for n < 500)
        'greedy_peeling'             → Charikar lazy min-heap peeling with history
        'greedy++' / 'greedy_plus_plus' → Greedy++ iterative load-weighted peeling

    Returns
    -------
    DenseSubgraph
    """
    if algorithm in ("exact", "exact_goldberg", "goldberg"):
        return exact_goldberg(graph, **kwargs)
    if algorithm in ("greedy_peeling",):
        from ringscope.algorithms.greedy_peeling import greedy_peeling

        res = greedy_peeling(graph)
        return DenseSubgraph(
            nodes=res.nodes,
            density=res.density,
            algorithm="greedy_peeling",
            edge_count=res.edge_count,
        )
    if algorithm in ("greedy++", "greedy_plus_plus"):
        from ringscope.algorithms.greedy_plus_plus import greedy_plus_plus

        res_gpp = greedy_plus_plus(graph, **kwargs)
        return DenseSubgraph(
            nodes=res_gpp.nodes,
            density=res_gpp.density,
            algorithm="greedy_plus_plus",
            edge_count=res_gpp.edge_count,
        )
    return greedy_charikar(graph, **kwargs)
