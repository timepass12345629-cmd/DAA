"""
ringscope.algorithms.greedy_peeling
===================================
Charikar's Greedy Minimum-Degree Peeling Algorithm for Densest Subgraph.

Reference:
----------
Moses Charikar, "Greedy approximation algorithms for finding dense components
in a graph", APPROX 2000, pp. 84-95.

Mathematical Formulation & Guarantee:
--------------------------------------
For an undirected graph G = (V, E) and any nonempty vertex subset S ⊆ V:
- Density: density(S) = |E(S)| / |S|
- Average Degree: avg_deg(S) = (1 / |S|) * sum_{v in S} deg_S(v) = 2 * |E(S)| / |S|
- Relationship: avg_deg(S) = 2 * density(S)

Greedy Peeling Procedure:
-------------------------
1. Initialize S_0 = V.
2. For i = 1, ..., n - 1:
   - Identify vertex v* in S_{i-1} with minimum degree in G[S_{i-1}].
   - Set S_i = S_{i-1} \\ {v*}.
   - Recompute density(S_i).
3. Return S_k maximizing density(S_k) over k in {0, ..., n - 1}.

Complexity & Approximation:
---------------------------
- Time Complexity: O((n + m) log n) using a lazy min-heap.
  Each vertex is popped at most once; each edge removal decrements neighbor degree
  and adds an entry to the heap in O(log n).
- Space Complexity: O(n + m) for graph adjacency and heap.
- Theoretical Guarantee: 2-approximation under density |E(S)| / |S|.
  The returned density is guaranteed to be >= OPT / 2.
"""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass
from typing import Any, Union

import networkx as nx

from ringscope.graph import TransactionGraph


@dataclass
class PeelingStep:
    """Snapshot recorded after peeling a vertex."""

    step: int
    removed_node: str
    removed_degree: int
    remaining_node_count: int
    remaining_edge_count: int
    density: float


@dataclass
class GreedyPeelingResult:
    """Result of Charikar's greedy peeling densest subgraph algorithm."""

    nodes: list[str]
    """Vertices belonging to the densest snapshot found."""

    density: float
    """Actual density |E(S)| / |S| of the returned subgraph."""

    edge_count: int
    """Number of internal edges in the returned subgraph."""

    node_count: int
    """Number of vertices in the returned subgraph."""

    history: list[PeelingStep]
    """Chronological record of every peeling step."""

    runtime_sec: float
    """Total execution time in seconds."""

    approximation_factor: float = 2.0
    """Theoretical worst-case approximation ratio (2-approx)."""

    algorithm: str = "greedy_charikar_peeling"

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "density": self.density,
            "edge_count": self.edge_count,
            "node_count": self.node_count,
            "runtime_sec": self.runtime_sec,
            "approximation_factor": self.approximation_factor,
            "algorithm": self.algorithm,
            "history_length": len(self.history),
        }


def _extract_adjacency(
    graph: Union[TransactionGraph, nx.Graph, nx.DiGraph],
) -> tuple[list[str], dict[str, set[str]]]:
    """Extract node list and undirected adjacency dictionary."""
    if isinstance(graph, TransactionGraph):
        nodes = [str(n) for n in graph.graph.nodes()]
        adj: dict[str, set[str]] = {n: set() for n in nodes}
        for u, v in graph.graph.edges():
            su, sv = str(u), str(v)
            if su != sv:
                adj[su].add(sv)
                adj[sv].add(su)
    elif isinstance(graph, (nx.Graph, nx.DiGraph)):
        nodes = [str(n) for n in graph.nodes()]
        adj = {n: set() for n in nodes}
        for u, v in graph.edges():
            su, sv = str(u), str(v)
            if su != sv:
                adj[su].add(sv)
                adj[sv].add(su)
    else:
        raise TypeError(f"Unsupported graph type: {type(graph)}")

    return nodes, adj


def greedy_peeling(
    graph: Union[TransactionGraph, nx.Graph, nx.DiGraph],
) -> GreedyPeelingResult:
    """
    Execute Charikar's greedy minimum-degree peeling on an undirected graph.

    Parameters
    ----------
    graph : TransactionGraph | nx.Graph
        Input transaction graph.

    Returns
    -------
    GreedyPeelingResult
    """
    start_time = time.perf_counter()
    nodes, adj = _extract_adjacency(graph)
    n = len(nodes)

    if n == 0:
        return GreedyPeelingResult(
            nodes=[],
            density=0.0,
            edge_count=0,
            node_count=0,
            history=[],
            runtime_sec=time.perf_counter() - start_time,
        )

    # Initial degree calculation
    degree: dict[str, int] = {u: len(adj[u]) for u in nodes}
    total_edges = sum(degree.values()) // 2

    # Lazy min-heap with (degree, node)
    heap: list[tuple[int, str]] = [(degree[u], u) for u in nodes]
    heapq.heapify(heap)

    alive: set[str] = set(nodes)
    current_edges = total_edges

    # Snapshot 0: entire graph
    initial_density = total_edges / n if n > 0 else 0.0
    best_nodes: set[str] = set(alive)
    best_density: float = initial_density
    best_edge_count: int = total_edges

    history: list[PeelingStep] = []
    step_num = 0

    while len(alive) > 1:
        # Extract node with valid minimum degree
        while heap:
            deg, u = heapq.heappop(heap)
            if u not in alive:
                continue
            if deg > degree[u]:
                # Stale entry: degree decreased since push, re-insert with current degree
                heapq.heappush(heap, (degree[u], u))
                continue
            break
        else:
            break

        # Remove u
        alive.remove(u)
        removed_deg = degree[u]
        current_edges -= removed_deg

        # Decrement neighbors' degrees
        for neighbor in adj[u]:
            if neighbor in alive:
                degree[neighbor] -= 1
                heapq.heappush(heap, (degree[neighbor], neighbor))

        step_num += 1
        rem_count = len(alive)
        current_density = current_edges / rem_count if rem_count > 0 else 0.0

        history.append(
            PeelingStep(
                step=step_num,
                removed_node=u,
                removed_degree=removed_deg,
                remaining_node_count=rem_count,
                remaining_edge_count=current_edges,
                density=current_density,
            )
        )

        if current_density > best_density:
            best_density = current_density
            best_nodes = set(alive)
            best_edge_count = current_edges

    elapsed = time.perf_counter() - start_time

    return GreedyPeelingResult(
        nodes=sorted(best_nodes),
        density=best_density,
        edge_count=best_edge_count,
        node_count=len(best_nodes),
        history=history,
        runtime_sec=elapsed,
    )
