"""
ringscope.eval_harness
======================
Evaluation Harness for Benchmark Protocols & Streaming Maintenance Modes.

Provides:
1. Reusable metric calculations (precision, recall, F1, Jaccard overlap, density gap,
   latency percentiles).
2. Streaming evaluation runner comparing Mode A (Full Recomputation), Mode B
   (Warm-Started), and Mode C (Incremental Heuristic) on identical streams.
3. CSV and JSON export facilities with complete provenance recording.
4. Time limit enforcement to prevent long-running exact flow solvers from hanging.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional, Sequence, Union

import numpy as np

from ringscope.algorithms.brute_force import MAX_BRUTE_FORCE_NODES, brute_force_densest_subgraph
from ringscope.algorithms.goldberg import goldberg_densest_subgraph
from ringscope.stream_simulator import (
    FullRecomputationMaintainer,
    IncrementalHeuristicMaintainer,
    StreamBatch,
    WarmStartedMaintainer,
)


def calculate_overlap_metrics(
    predicted: Union[set[str], list[str]],
    ground_truth: Union[set[str], list[str]],
) -> dict[str, float]:
    """
    Calculate precision, recall, F1 score, and Jaccard overlap.

    Parameters
    ----------
    predicted : set[str] | list[str]
        Detected vertex cluster.
    ground_truth : set[str] | list[str]
        Planted ground-truth vertex cluster.

    Returns
    -------
    dict[str, float]
    """
    s_pred = set(predicted)
    s_gt = set(ground_truth)

    if not s_gt and not s_pred:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "jaccard": 1.0}
    if not s_pred or not s_gt:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "jaccard": 0.0}

    intersection = len(s_pred & s_gt)
    union = len(s_pred | s_gt)

    precision = intersection / len(s_pred)
    recall = intersection / len(s_gt)
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    jaccard = intersection / union if union > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "jaccard": round(jaccard, 4),
    }


def calculate_density_gap(candidate_density: float, exact_density: float) -> dict[str, float]:
    """Calculate absolute and relative density gap against an exact reference."""
    abs_gap = max(0.0, exact_density - candidate_density)
    ratio = (candidate_density / exact_density) if exact_density > 1e-9 else 1.0
    return {
        "candidate_density": round(candidate_density, 5),
        "exact_density": round(exact_density, 5),
        "absolute_gap": round(abs_gap, 5),
        "approximation_ratio": round(ratio, 4),
    }


def calculate_latency_percentiles(latencies_ms: Sequence[float]) -> dict[str, float]:
    """Compute mean, p50, p95, and p99 from a sequence of latencies in ms."""
    if not latencies_ms:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

    arr = np.array(latencies_ms)
    return {
        "mean": round(float(np.mean(arr)), 3),
        "p50": round(float(np.percentile(arr, 50)), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
        "p99": round(float(np.percentile(arr, 99)), 3),
    }


@dataclass
class StreamingModeComparisonResult:
    """Evaluation summary for a single streaming maintenance mode."""

    mode: str
    algorithm: str
    total_batches: int
    total_transactions: int
    final_num_nodes: int
    final_num_edges: int
    final_density: float
    exact_reference_density: Optional[float]
    density_gap: Optional[float]
    approx_ratio: Optional[float]
    precision: float
    recall: float
    f1: float
    jaccard: float
    total_runtime_ms: float
    mean_batch_latency_ms: float
    p95_batch_latency_ms: float
    total_recomputations: int
    recomputation_rate: float
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "algorithm": self.algorithm,
            "total_batches": self.total_batches,
            "total_transactions": self.total_transactions,
            "final_num_nodes": self.final_num_nodes,
            "final_num_edges": self.final_num_edges,
            "final_density": round(self.final_density, 5),
            "exact_reference_density": (
                round(self.exact_reference_density, 5)
                if self.exact_reference_density is not None
                else None
            ),
            "density_gap": (round(self.density_gap, 5) if self.density_gap is not None else None),
            "approx_ratio": (
                round(self.approx_ratio, 4) if self.approx_ratio is not None else None
            ),
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "jaccard": self.jaccard,
            "total_runtime_ms": round(self.total_runtime_ms, 3),
            "mean_batch_latency_ms": round(self.mean_batch_latency_ms, 3),
            "p95_batch_latency_ms": round(self.p95_batch_latency_ms, 3),
            "total_recomputations": self.total_recomputations,
            "recomputation_rate": round(self.recomputation_rate, 4),
            "timed_out": self.timed_out,
        }


def evaluate_streaming_modes(
    batches: list[StreamBatch],
    planted_cluster: set[str],
    algorithm: str = "greedy_peeling",
    exact_reference_solver: bool = True,
    time_limit_sec: float = 10.0,
) -> list[StreamingModeComparisonResult]:
    """
    Run identical streaming batches across all three maintenance modes:
      Mode A: Full Recomputation
      Mode B: Warm-Started Recomputation
      Mode C: Incremental Heuristic
    """
    results: list[StreamingModeComparisonResult] = []

    modes = [
        ("full_recomputation", FullRecomputationMaintainer(algorithm=algorithm)),
        ("warm_started_recomputation", WarmStartedMaintainer(algorithm=algorithm)),
        ("incremental_heuristic", IncrementalHeuristicMaintainer(algorithm=algorithm)),
    ]

    total_tx = sum(len(b.transactions) for b in batches)

    for mode_name, maintainer in modes:
        start_time = time.perf_counter()
        timed_out = False
        batch_latencies = []

        for b in batches:
            if (time.perf_counter() - start_time) > time_limit_sec:
                timed_out = True
                break
            snap = maintainer.process_batch(b)
            batch_latencies.append(snap.batch_latency_ms)

        total_elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Exact reference density on the final graph
        exact_dens: Optional[float] = None
        dens_gap: Optional[float] = None
        approx_rat: Optional[float] = None

        if exact_reference_solver and maintainer.graph.num_vertices > 0:
            if maintainer.graph.num_vertices <= MAX_BRUTE_FORCE_NODES:
                bf = brute_force_densest_subgraph(maintainer.graph)
                exact_dens = bf.density
            else:
                gb = goldberg_densest_subgraph(maintainer.graph, tolerance=1e-4)
                exact_dens = gb.density

            if exact_dens is not None:
                gap_info = calculate_density_gap(maintainer.current_density, exact_dens)
                dens_gap = gap_info["absolute_gap"]
                approx_rat = gap_info["approximation_ratio"]

        # Recovery metrics against planted ground truth
        overlap_info = calculate_overlap_metrics(maintainer.current_candidate, planted_cluster)

        lat_pct = calculate_latency_percentiles(batch_latencies)
        num_batches_processed = len(maintainer.history)
        recomp_rate = (
            maintainer.recomputation_count / num_batches_processed
            if num_batches_processed > 0
            else 0.0
        )

        results.append(
            StreamingModeComparisonResult(
                mode=mode_name,
                algorithm=algorithm,
                total_batches=num_batches_processed,
                total_transactions=total_tx,
                final_num_nodes=maintainer.graph.num_vertices,
                final_num_edges=maintainer.graph.num_unique_edges,
                final_density=maintainer.current_density,
                exact_reference_density=exact_dens,
                density_gap=dens_gap,
                approx_ratio=approx_rat,
                precision=overlap_info["precision"],
                recall=overlap_info["recall"],
                f1=overlap_info["f1"],
                jaccard=overlap_info["jaccard"],
                total_runtime_ms=total_elapsed_ms,
                mean_batch_latency_ms=lat_pct["mean"],
                p95_batch_latency_ms=lat_pct["p95"],
                total_recomputations=maintainer.recomputation_count,
                recomputation_rate=recomp_rate,
                timed_out=timed_out,
            )
        )

    return results


def _normalize_to_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "to_dict"):
        return item.to_dict()
    if hasattr(item, "__dataclass_fields__"):
        return asdict(item)
    if isinstance(item, dict):
        return item
    return dict(item)


def export_results_to_json(results: list[Any], filepath: Union[str, Path]) -> None:
    """Export benchmark result dataclasses or dicts to formatted JSON."""
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    dict_list = [_normalize_to_dict(r) for r in results]
    with open(p, "w", encoding="utf-8") as f:
        json.dump(dict_list, f, indent=2)


def export_results_to_csv(results: list[Any], filepath: Union[str, Path]) -> None:
    """Export benchmark result dataclasses or dicts to CSV."""
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    dict_list = [_normalize_to_dict(r) for r in results]
    if not dict_list:
        return

    fieldnames = list(dict_list[0].keys())
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in dict_list:
            writer.writerow(row)
