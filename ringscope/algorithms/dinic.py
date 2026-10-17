"""
ringscope.algorithms.dinic
==========================
Dinic's Algorithm for Maximum Flow and Minimum Cut.

Implements Dinic's algorithm (Dinic 1970) from scratch:
- Residual graph representation with forward and reverse edges.
- Level graph construction via Breadth-First Search (BFS).
- Blocking flow computation via Depth-First Search (DFS) with edge-pointer
  optimization (work pointers).
- Maximum-flow computation.
- Source-side minimum-cut extraction via residual graph reachability.

Complexity:
- General networks: O(V² * E)
- Unit capacity networks: O(min(V^(2/3), E^(1/2)) * E)
- Bipartite matching networks: O(E * sqrt(V))
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass
class FlowEdge:
    """An edge in the residual flow network."""

    u: int
    v: int
    capacity: float
    flow: float = 0.0
    rev: int = -1

    @property
    def residual_capacity(self) -> float:
        return self.capacity - self.flow


class Dinic:
    """
    Dinic's maximum flow algorithm on a directed flow network with arbitrary capacities.

    Supports arbitrary hashable node keys (strings, integers, tuples, etc.).
    """

    def __init__(self, nodes: Optional[Iterable[Any]] = None) -> None:
        self._node_to_idx: dict[Any, int] = {}
        self._idx_to_node: list[Any] = []
        self._adj: list[list[FlowEdge]] = []

        if nodes is not None:
            for node in nodes:
                self._get_or_add_node(node)

    def _get_or_add_node(self, node: Any) -> int:
        if node in self._node_to_idx:
            return self._node_to_idx[node]
        idx = len(self._idx_to_node)
        self._node_to_idx[node] = idx
        self._idx_to_node.append(node)
        self._adj.append([])
        return idx

    @property
    def num_nodes(self) -> int:
        return len(self._idx_to_node)

    def add_edge(self, u: Any, v: Any, capacity: float) -> None:
        """
        Add a directed edge from `u` to `v` with given capacity.
        Also creates a back-edge with 0 capacity in the residual network.
        """
        if capacity < 0:
            raise ValueError(f"Capacity cannot be negative: {capacity}")

        u_idx = self._get_or_add_node(u)
        v_idx = self._get_or_add_node(v)

        forward = FlowEdge(u=u_idx, v=v_idx, capacity=float(capacity), flow=0.0)
        backward = FlowEdge(u=v_idx, v=u_idx, capacity=0.0, flow=0.0)

        forward.rev = len(self._adj[v_idx])
        backward.rev = len(self._adj[u_idx])

        self._adj[u_idx].append(forward)
        self._adj[v_idx].append(backward)

    def _bfs_level_graph(self, s_idx: int, t_idx: int, levels: list[int]) -> bool:
        """Construct the BFS level graph. Returns True if sink is reachable."""
        for i in range(len(levels)):
            levels[i] = -1

        levels[s_idx] = 0
        queue: collections.deque[int] = collections.deque([s_idx])

        while queue:
            u = queue.popleft()
            lvl_next = levels[u] + 1
            for edge in self._adj[u]:
                if edge.residual_capacity > 1e-11 and levels[edge.v] == -1:
                    levels[edge.v] = lvl_next
                    queue.append(edge.v)
                    if edge.v == t_idx:
                        return True

        return levels[t_idx] != -1

    def _dfs_blocking_flow(
        self,
        u: int,
        t_idx: int,
        pushed: float,
        levels: list[int],
        work: list[int],
    ) -> float:
        """Find blocking flow in the level graph using DFS and work pointers."""
        if pushed <= 1e-11 or u == t_idx:
            return pushed

        adj_u = self._adj[u]
        num_edges = len(adj_u)

        while work[u] < num_edges:
            edge = adj_u[work[u]]
            v = edge.v
            res = edge.residual_capacity

            if levels[v] == levels[u] + 1 and res > 1e-11:
                tr = self._dfs_blocking_flow(v, t_idx, min(pushed, res), levels, work)
                if tr > 1e-11:
                    edge.flow += tr
                    self._adj[v][edge.rev].flow -= tr
                    return tr
            work[u] += 1

        return 0.0

    def max_flow(self, source: Any, sink: Any) -> float:
        """
        Compute the maximum flow from `source` to `sink`.
        """
        if source not in self._node_to_idx:
            raise KeyError(f"Source node '{source}' not in network")
        if sink not in self._node_to_idx:
            raise KeyError(f"Sink node '{sink}' not in network")

        s_idx = self._node_to_idx[source]
        t_idx = self._node_to_idx[sink]

        if s_idx == t_idx:
            raise ValueError("Source and sink must be distinct nodes")

        n = self.num_nodes
        # Adjust recursion limit if necessary for deep level graphs
        old_limit = sys.getrecursionlimit()
        if n + 50 > old_limit:
            sys.setrecursionlimit(n + 100)

        total_flow = 0.0
        levels = [-1] * n
        work = [0] * n

        try:
            while self._bfs_level_graph(s_idx, t_idx, levels):
                for i in range(n):
                    work[i] = 0
                while True:
                    pushed = self._dfs_blocking_flow(s_idx, t_idx, float("inf"), levels, work)
                    if pushed <= 1e-11:
                        break
                    total_flow += pushed
        finally:
            if sys.getrecursionlimit() != old_limit:
                sys.setrecursionlimit(old_limit)

        return total_flow

    def min_cut_source_side(self, source: Any) -> set[Any]:
        """
        Extract the set of nodes on the source side of the minimum cut.
        These are all nodes reachable from `source` in the residual graph.
        """
        if source not in self._node_to_idx:
            raise KeyError(f"Source node '{source}' not in network")

        s_idx = self._node_to_idx[source]
        visited = [False] * self.num_nodes
        visited[s_idx] = True
        queue: collections.deque[int] = collections.deque([s_idx])

        while queue:
            u = queue.popleft()
            for edge in self._adj[u]:
                if edge.residual_capacity > 1e-11 and not visited[edge.v]:
                    visited[edge.v] = True
                    queue.append(edge.v)

        return {self._idx_to_node[i] for i, v in enumerate(visited) if v}

    def get_flow(self, u: Any, v: Any) -> float:
        """Get the net flow sent along directed edge (u, v)."""
        u_idx = self._node_to_idx[u]
        v_idx = self._node_to_idx[v]
        for edge in self._adj[u_idx]:
            if edge.v == v_idx and edge.capacity > 0:
                return edge.flow
        return 0.0
