"""
ringscope.evaluation — Empirical research evaluation suite for RingScope.

Provides benchmark protocols for:
1. Ring Detection Recall & Precision against planted ground truth.
2. Densest Subgraph Empirical Approximation Ratio (Greedy vs Exact).
3. Streaming Window Ingestion Throughput & Latency (Incremental vs Full).

All benchmarks are deterministic with fixed seeds for reproducibility.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from ringscope.algorithms.cycle_detection import detect_rings
from ringscope.algorithms.densest_subgraph import exact_goldberg, greedy_charikar
from ringscope.algorithms.streaming import StreamingRingDetector
from ringscope.data import random_graph, ring_graph, transaction_stream


@dataclass
class RingEvalResult:
    """Result of ring detection evaluation on a single benchmark configuration."""

    ring_sizes: list[int]
    noise_edges: int
    seed: int
    num_nodes: int
    num_edges: int
    planted_count: int
    detected_count: int
    true_positives: int
    recall: float
    precision: float
    f1: float
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "ring_sizes": self.ring_sizes,
            "noise_edges": self.noise_edges,
            "seed": self.seed,
            "num_nodes": self.num_nodes,
            "num_edges": self.num_edges,
            "planted_count": self.planted_count,
            "detected_count": self.detected_count,
            "true_positives": self.true_positives,
            "recall": round(self.recall, 4),
            "precision": round(self.precision, 4),
            "f1": round(self.f1, 4),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclass
class DensityEvalResult:
    """Comparative evaluation of Charikar Greedy vs Picard-Goldberg Exact."""

    n_accounts: int
    n_transactions: int
    seed: int
    greedy_density: float
    exact_density: float
    approx_ratio: float
    jaccard_similarity: float
    greedy_time_ms: float
    exact_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_accounts": self.n_accounts,
            "n_transactions": self.n_transactions,
            "seed": self.seed,
            "greedy_density": round(self.greedy_density, 4),
            "exact_density": round(self.exact_density, 4),
            "approx_ratio": round(self.approx_ratio, 4),
            "jaccard_similarity": round(self.jaccard_similarity, 4),
            "greedy_time_ms": round(self.greedy_time_ms, 3),
            "exact_time_ms": round(self.exact_time_ms, 3),
        }


@dataclass
class StreamingThroughputResult:
    """Throughput and latency profiling for streaming transaction ingestion."""

    n_transactions: int
    mode: str  # 'incremental' or 'full'
    total_time_ms: float
    throughput_tps: float
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    final_ring_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_transactions": self.n_transactions,
            "mode": self.mode,
            "total_time_ms": round(self.total_time_ms, 2),
            "throughput_tps": round(self.throughput_tps, 1),
            "mean_latency_ms": round(self.mean_latency_ms, 4),
            "p50_latency_ms": round(self.p50_latency_ms, 4),
            "p95_latency_ms": round(self.p95_latency_ms, 4),
            "p99_latency_ms": round(self.p99_latency_ms, 4),
            "final_ring_count": self.final_ring_count,
        }


def evaluate_ring_detection(
    ring_sizes: Sequence[int] = (3, 4, 5),
    noise_edges: int = 30,
    seed: int = 42,
    max_rings: int = 100,
) -> RingEvalResult:
    """
    Evaluate ring detection recall, precision, and F1 on a planted-ring network.
    """
    tg = ring_graph(ring_sizes=list(ring_sizes), n_extra_edges=noise_edges, seed=seed)
    g = tg.graph
    planted = [frozenset(p) for p in g.graph.get("planted_rings", [])]

    t0 = time.perf_counter()
    detected_rings = detect_rings(g, max_rings=max_rings)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    detected_sets = [frozenset(r.nodes) for r in detected_rings]

    tp = sum(1 for p in planted if p in detected_sets)
    recall = tp / len(planted) if planted else 0.0
    precision = tp / len(detected_sets) if detected_sets else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return RingEvalResult(
        ring_sizes=list(ring_sizes),
        noise_edges=noise_edges,
        seed=seed,
        num_nodes=tg.num_nodes,
        num_edges=tg.num_edges,
        planted_count=len(planted),
        detected_count=len(detected_rings),
        true_positives=tp,
        recall=recall,
        precision=precision,
        f1=f1,
        elapsed_ms=elapsed_ms,
    )


def evaluate_densest_subgraph(
    n_accounts: int = 40,
    n_transactions: int = 80,
    seed: int = 42,
) -> DensityEvalResult:
    """
    Compare Charikar greedy vs Picard-Goldberg exact min-cut on a random graph.
    """
    tg = random_graph(n_accounts=n_accounts, n_transactions=n_transactions, seed=seed)
    g = tg.graph

    # Greedy
    t0 = time.perf_counter()
    ds_greedy = greedy_charikar(g)
    greedy_time = (time.perf_counter() - t0) * 1000

    # Exact
    t1 = time.perf_counter()
    ds_exact = exact_goldberg(g)
    exact_time = (time.perf_counter() - t1) * 1000

    greedy_set = set(ds_greedy.nodes)
    exact_set = set(ds_exact.nodes)

    jaccard = (
        len(greedy_set & exact_set) / len(greedy_set | exact_set)
        if (greedy_set or exact_set)
        else 1.0
    )

    ratio = (
        ds_greedy.density / ds_exact.density
        if ds_exact.density > 0
        else (1.0 if ds_greedy.density == 0 else 0.0)
    )

    return DensityEvalResult(
        n_accounts=n_accounts,
        n_transactions=n_transactions,
        seed=seed,
        greedy_density=ds_greedy.density,
        exact_density=ds_exact.density,
        approx_ratio=ratio,
        jaccard_similarity=jaccard,
        greedy_time_ms=greedy_time,
        exact_time_ms=exact_time,
    )


def benchmark_streaming_throughput(
    n_transactions: int = 300,
    window_size: float = 1800.0,
    incremental: bool = True,
    seed: int = 99,
) -> StreamingThroughputResult:
    """
    Profile ingestion throughput (transactions per second) and latency percentiles.
    """
    edges = transaction_stream(
        n_transactions=n_transactions,
        window_size=window_size,
        seed=seed,
    )

    detector = StreamingRingDetector(
        window_size=window_size,
        max_cycle_length=6,
        incremental=incremental,
    )

    latencies_ms: list[float] = []
    t_start = time.perf_counter()

    for edge in edges:
        snap = detector.ingest(edge)
        latencies_ms.append(snap.processing_time_ms)

    total_time_ms = (time.perf_counter() - t_start) * 1000
    throughput = (n_transactions / (total_time_ms / 1000.0)) if total_time_ms > 0 else 0.0

    arr = np.array(latencies_ms)
    return StreamingThroughputResult(
        n_transactions=n_transactions,
        mode="incremental" if incremental else "full",
        total_time_ms=total_time_ms,
        throughput_tps=throughput,
        mean_latency_ms=float(np.mean(arr)),
        p50_latency_ms=float(np.percentile(arr, 50)),
        p95_latency_ms=float(np.percentile(arr, 95)),
        p99_latency_ms=float(np.percentile(arr, 99)),
        final_ring_count=detector.current_snapshot().ring_summary.get("count", 0),
    )
