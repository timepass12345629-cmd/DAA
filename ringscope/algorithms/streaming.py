"""
ringscope.algorithms.streaming
================================
Sliding-window streaming graph with incremental ring statistics.

Design
------
Transactions arrive in timestamp order.  A fixed-width time window
[now - window_size, now] is maintained.  Edges outside the window are
evicted on each update.

After every insertion / eviction the ring count and densest-subgraph
density are recomputed *incrementally* where possible:

- **Ring invalidation**: evicting an edge invalidates only cycles that
  pass through it.  Full recomputation is used for correctness
  (incremental Johnson is complex to implement correctly; we note this
  as a known limitation).

- **Density**: Charikar greedy is rerun on the current window graph.
  O((n + e) log n) per update.

All state is kept in memory (no persistence).  For production use,
persist the window graph to a database.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import networkx as nx

from ringscope.algorithms.cycle_detection import Ring, detect_rings, ring_summary
from ringscope.algorithms.densest_subgraph import greedy_charikar


@dataclass
class StreamEdge:
    """A single transaction arriving in the stream."""

    src: str
    dst: str
    amount: float
    timestamp: float
    tx_id: str = ""


@dataclass
class WindowSnapshot:
    """Current state of the streaming window."""

    window_start: float
    window_end: float
    num_nodes: int
    num_edges: int
    rings: list[dict]
    ring_summary: dict
    densest_subgraph: dict
    processing_time_ms: float


class StreamingRingDetector:
    """
    Sliding-window ring detector over a stream of transactions.

    Maintains an incremental ring cache: when a new edge (src, dst) arrives,
    only new cycles passing through (src, dst) are searched via simple path
    enumeration, avoiding full Johnson recomputation. Expired edges invalidate
    only their participant rings.

    Parameters
    ----------
    window_size : float
        Width of the time window in seconds.
    max_cycle_length : int | None
        Maximum ring length to track.
    max_rings : int
        Maximum number of rings to report per snapshot.
    incremental : bool
        If True (default), uses the incremental ring cache. If False,
        runs full Johnson detection on every snapshot.
    """

    def __init__(
        self,
        window_size: float = 3600.0,
        max_cycle_length: Optional[int] = 10,
        max_rings: int = 100,
        incremental: bool = True,
    ) -> None:
        self.window_size = window_size
        self.max_cycle_length = max_cycle_length
        self.max_rings = max_rings
        self.incremental = incremental

        self._graph: nx.DiGraph = nx.DiGraph()
        # Queue of (timestamp, src, dst) for eviction
        self._edge_queue: deque[StreamEdge] = deque()
        self._current_time: float = 0.0
        # Incremental ring cache: canonical node tuple -> Ring
        self._ring_cache: dict[tuple[str, ...], Ring] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def graph(self) -> nx.DiGraph:
        return self._graph

    @property
    def current_time(self) -> float:
        return self._current_time

    def ingest(self, edge: StreamEdge) -> WindowSnapshot:
        """
        Insert a new transaction into the window and return a snapshot.

        If ``edge.timestamp < current_time``, the edge is accepted but
        does not advance the clock (out-of-order tolerance).
        """
        t0 = time.perf_counter()

        self._current_time = max(self._current_time, edge.timestamp)
        self._add_edge(edge)
        self._evict_expired()

        snapshot = self._build_snapshot()
        snapshot.processing_time_ms = (time.perf_counter() - t0) * 1000
        return snapshot

    def bulk_ingest(self, edges: list[StreamEdge]) -> list[WindowSnapshot]:
        """
        Ingest a list of edges in order and return a snapshot per edge.
        """
        return [self.ingest(e) for e in edges]

    def current_snapshot(self) -> WindowSnapshot:
        """Return a snapshot of the current window without any insertion."""
        return self._build_snapshot()

    def reset(self) -> None:
        """Clear all state."""
        self._graph = nx.DiGraph()
        self._edge_queue.clear()
        self._current_time = 0.0
        self._ring_cache.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _canonical(cycle: list[str]) -> tuple[str, ...]:
        n = len(cycle)
        rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(n)]
        return min(rotations)

    def _compute_ring(self, cycle: list[str]) -> Ring:
        amounts: list[float] = []
        n = len(cycle)
        for i in range(n):
            u = cycle[i]
            v = cycle[(i + 1) % n]
            if self._graph.has_edge(u, v):
                amounts.append(self._graph[u][v].get("amount", 0.0))
            else:
                amounts.append(0.0)
        bottleneck = min(amounts) if amounts else 0.0
        return Ring(
            nodes=cycle,
            total_amount=sum(amounts),
            min_amount=bottleneck,
        )

    def _add_edge(self, edge: StreamEdge) -> None:
        self._edge_queue.append(edge)
        is_new = not self._graph.has_edge(edge.src, edge.dst)

        # Accumulate amount for repeated edges
        if not is_new:
            self._graph[edge.src][edge.dst]["amount"] += edge.amount
            self._graph[edge.src][edge.dst]["timestamp"] = max(
                self._graph[edge.src][edge.dst]["timestamp"], edge.timestamp
            )
            self._graph[edge.src][edge.dst]["tx_count"] = (
                self._graph[edge.src][edge.dst].get("tx_count", 1) + 1
            )
        else:
            self._graph.add_edge(
                edge.src,
                edge.dst,
                amount=edge.amount,
                timestamp=edge.timestamp,
                tx_id=edge.tx_id,
                tx_count=1,
            )

        if self.incremental and is_new:
            cutoff = (self.max_cycle_length - 1) if self.max_cycle_length is not None else 8
            try:
                for path in nx.all_simple_paths(self._graph, edge.dst, edge.src, cutoff=cutoff):
                    key = self._canonical(path)
                    if key not in self._ring_cache:
                        self._ring_cache[key] = self._compute_ring(list(key))
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pass

    def _evict_expired(self) -> None:
        cutoff = self._current_time - self.window_size
        evicted_pairs: set[tuple[str, str]] = set()

        while self._edge_queue and self._edge_queue[0].timestamp < cutoff:
            expired = self._edge_queue.popleft()
            if self._graph.has_edge(expired.src, expired.dst):
                data = self._graph[expired.src][expired.dst]
                tc = data.get("tx_count", 1) - 1
                if tc <= 0:
                    self._graph.remove_edge(expired.src, expired.dst)
                    evicted_pairs.add((expired.src, expired.dst))
                    # Remove isolated nodes
                    for n in [expired.src, expired.dst]:
                        if self._graph.degree(n) == 0:
                            self._graph.remove_node(n)
                else:
                    data["tx_count"] = tc
                    data["amount"] = max(0.0, data["amount"] - expired.amount)

        if self.incremental and evicted_pairs:
            to_remove = set()
            for key in self._ring_cache:
                n = len(key)
                for i in range(n):
                    if (key[i], key[(i + 1) % n]) in evicted_pairs:
                        to_remove.add(key)
                        break
            for key in to_remove:
                del self._ring_cache[key]

    def _build_snapshot(self) -> WindowSnapshot:
        if self.incremental:
            rings = [self._compute_ring(list(key)) for key in self._ring_cache.keys()]
            rings.sort(key=lambda r: r.min_amount, reverse=True)
            if self.max_rings is not None:
                rings = rings[: self.max_rings]
        else:
            rings = detect_rings(
                self._graph,
                max_length=self.max_cycle_length,
                max_rings=self.max_rings,
            )

        ds = greedy_charikar(self._graph)
        window_start = self._current_time - self.window_size

        return WindowSnapshot(
            window_start=window_start,
            window_end=self._current_time,
            num_nodes=self._graph.number_of_nodes(),
            num_edges=self._graph.number_of_edges(),
            rings=[r.to_dict() for r in rings],
            ring_summary=ring_summary(rings),
            densest_subgraph=ds.to_dict(),
            processing_time_ms=0.0,
        )
