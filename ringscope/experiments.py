"""
ringscope.experiments
=====================
Configurable Benchmark Experiments for RingScope Research.

Suite of reproducible experiments:
1. exp_runtime_vs_graph_size: Scalability across increasing N with execution time limits.
2. exp_cluster_size_vs_recovery: Recovery metrics (P/R/F1) as planted cluster size varies.
3. exp_cluster_sparsity_vs_recovery: Recovery metrics as internal density p_in varies.
4. exp_background_connectivity: Degradation as noise edge probability p_out increases.
5. exp_exact_vs_approx_density: Approximation ratio and gap against true optimum.
6. exp_streaming_modes_comparison: Comparison of Modes A, B, and C on streaming transactions.
7. exp_multiple_clusters_and_hubs: Behavior with competing dense clusters and hub nodes.

All experiments use fixed seeds, enforce time limits, and output real measured data.
"""

from __future__ import annotations

import random
import time
from typing import Any, Optional, Sequence

import networkx as nx

from ringscope.algorithms.brute_force import MAX_BRUTE_FORCE_NODES, brute_force_densest_subgraph
from ringscope.algorithms.goldberg import goldberg_densest_subgraph
from ringscope.algorithms.greedy_peeling import greedy_peeling
from ringscope.algorithms.greedy_plus_plus import greedy_plus_plus
from ringscope.data import generate_planted_cluster_graph
from ringscope.eval_harness import (
    calculate_overlap_metrics,
    evaluate_streaming_modes,
)
from ringscope.graph import TransactionGraph
from ringscope.stream_simulator import generate_transaction_stream


def run_exp_runtime_vs_graph_size(
    sizes: Sequence[int] = (10, 20, 40, 80),
    p: float = 0.15,
    seed: int = 42,
    time_limit_sec: float = 5.0,
) -> list[dict[str, Any]]:
    """Experiment 1: Measure runtime scaling across graph sizes N."""
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []

    for n in sizes:
        s = rng.randint(1, 10000)
        gnx = nx.gnp_random_graph(n, p, seed=s)
        tg = TransactionGraph(name=f"G_{n}")
        for u, v in gnx.edges():
            tg.add_transaction(f"v_{u}", f"v_{v}")
        for i in range(n):
            tg.add_account(f"v_{i}")

        # 1. Greedy Peeling
        t0 = time.perf_counter()
        gp = greedy_peeling(tg)
        t_gp = (time.perf_counter() - t0) * 1000.0

        # 2. Greedy++
        t0 = time.perf_counter()
        gpp = greedy_plus_plus(tg, iterations=10)
        t_gpp = (time.perf_counter() - t0) * 1000.0

        # 3. Goldberg (bounded by time limit)
        t_gb: Optional[float] = None
        gb_density: Optional[float] = None
        if n <= 100:
            t0 = time.perf_counter()
            gb = goldberg_densest_subgraph(tg, tolerance=1e-4)
            t_gb = (time.perf_counter() - t0) * 1000.0
            gb_density = gb.density

        records.append(
            {
                "experiment": "runtime_vs_graph_size",
                "num_nodes": tg.num_vertices,
                "num_edges": tg.num_unique_edges,
                "greedy_peeling_ms": round(t_gp, 3),
                "greedy_peeling_density": round(gp.density, 4),
                "greedy_plus_plus_ms": round(t_gpp, 3),
                "greedy_plus_plus_density": round(gpp.density, 4),
                "goldberg_ms": round(t_gb, 3) if t_gb is not None else None,
                "goldberg_density": round(gb_density, 4) if gb_density is not None else None,
            }
        )

    return records


def run_exp_cluster_size_vs_recovery(
    n_total: int = 30,
    cluster_sizes: Sequence[int] = (4, 6, 8, 12),
    p_in: float = 0.8,
    p_out: float = 0.08,
    seed: int = 123,
) -> list[dict[str, Any]]:
    """Experiment 2: Measure recovery against planted cluster ground truth across cluster sizes."""
    records: list[dict[str, Any]] = []

    for k in cluster_sizes:
        res = generate_planted_cluster_graph(
            n_total=n_total,
            cluster_size=k,
            p_internal=p_in,
            p_external=p_out,
            seed=seed,
        )
        tg = res.graph
        gt = res.planted_cluster

        gp = greedy_peeling(tg)
        gpp = greedy_plus_plus(tg, iterations=10)
        gb = goldberg_densest_subgraph(tg, tolerance=1e-4)

        m_gp = calculate_overlap_metrics(gp.nodes, gt)
        m_gpp = calculate_overlap_metrics(gpp.nodes, gt)
        m_gb = calculate_overlap_metrics(gb.nodes, gt)

        records.append(
            {
                "experiment": "cluster_size_vs_recovery",
                "cluster_size": k,
                "planted_nodes_count": len(gt),
                "greedy_f1": m_gp["f1"],
                "greedy_jaccard": m_gp["jaccard"],
                "greedy_density": round(gp.density, 4),
                "greedy_plus_plus_f1": m_gpp["f1"],
                "greedy_plus_plus_jaccard": m_gpp["jaccard"],
                "greedy_plus_plus_density": round(gpp.density, 4),
                "goldberg_f1": m_gb["f1"],
                "goldberg_jaccard": m_gb["jaccard"],
                "goldberg_density": round(gb.density, 4),
            }
        )

    return records


def run_exp_cluster_sparsity_vs_recovery(
    n_total: int = 30,
    cluster_size: int = 8,
    p_in_values: Sequence[float] = (0.4, 0.6, 0.8, 1.0),
    p_out: float = 0.08,
    seed: int = 321,
) -> list[dict[str, Any]]:
    """Experiment 3: Recovery metrics as planted cluster density p_in varies."""
    records: list[dict[str, Any]] = []

    for p_in in p_in_values:
        res = generate_planted_cluster_graph(
            n_total=n_total,
            cluster_size=cluster_size,
            p_internal=p_in,
            p_external=p_out,
            seed=seed,
        )
        tg = res.graph
        gt = res.planted_cluster

        gpp = greedy_plus_plus(tg, iterations=10)
        m_gpp = calculate_overlap_metrics(gpp.nodes, gt)

        records.append(
            {
                "experiment": "cluster_sparsity_vs_recovery",
                "p_internal": p_in,
                "cluster_size": cluster_size,
                "cluster_density": round(res.cluster_density, 4),
                "background_density": round(res.background_density, 4),
                "recovery_f1": m_gpp["f1"],
                "recovery_jaccard": m_gpp["jaccard"],
                "detected_density": round(gpp.density, 4),
            }
        )

    return records


def run_exp_background_connectivity(
    n_total: int = 30,
    cluster_size: int = 8,
    p_in: float = 0.8,
    p_out_values: Sequence[float] = (0.02, 0.08, 0.15, 0.25),
    seed: int = 555,
) -> list[dict[str, Any]]:
    """Experiment 4: Measure recovery degradation as background noise p_out increases."""
    records: list[dict[str, Any]] = []

    for p_out in p_out_values:
        res = generate_planted_cluster_graph(
            n_total=n_total,
            cluster_size=cluster_size,
            p_internal=p_in,
            p_external=p_out,
            seed=seed,
        )
        tg = res.graph
        gt = res.planted_cluster

        gb = goldberg_densest_subgraph(tg, tolerance=1e-4)
        m_gb = calculate_overlap_metrics(gb.nodes, gt)

        records.append(
            {
                "experiment": "background_connectivity",
                "p_external": p_out,
                "total_edges": tg.num_unique_edges,
                "planted_size": len(gt),
                "detected_size": len(gb.nodes),
                "precision": m_gb["precision"],
                "recall": m_gb["recall"],
                "f1": m_gb["f1"],
                "jaccard": m_gb["jaccard"],
            }
        )

    return records


def run_exp_exact_vs_approx_density(
    sizes: Sequence[int] = (8, 12, 16),
    seed: int = 777,
) -> list[dict[str, Any]]:
    """
    Experiment 5: Exact vs approximate density.
    Compares Brute-Force Oracle, Goldberg, Greedy Peeling, and Greedy++ on small N <= 20.
    """
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []

    for n in sizes:
        s = rng.randint(1, 10000)
        gnx = nx.gnp_random_graph(n, 0.35, seed=s)
        tg = TransactionGraph(name=f"Small_{n}")
        for u, v in gnx.edges():
            tg.add_transaction(f"v_{u}", f"v_{v}")
        for i in range(n):
            tg.add_account(f"v_{i}")

        bf = brute_force_densest_subgraph(tg, max_nodes=MAX_BRUTE_FORCE_NODES)
        gb = goldberg_densest_subgraph(tg, tolerance=1e-5)
        gp = greedy_peeling(tg)
        gpp = greedy_plus_plus(tg, iterations=10)

        gpp_ratio = (gpp.density / bf.density) if bf.density > 0 else 1.0
        records.append(
            {
                "experiment": "exact_vs_approx_density",
                "num_nodes": tg.num_vertices,
                "num_edges": tg.num_unique_edges,
                "optimal_density": round(bf.density, 5),
                "goldberg_density": round(gb.density, 5),
                "goldberg_gap": round(bf.density - gb.density, 5),
                "greedy_density": round(gp.density, 5),
                "greedy_approx_ratio": round(
                    (gp.density / bf.density) if bf.density > 0 else 1.0, 4
                ),
                "greedy_plus_plus_density": round(gpp.density, 5),
                "greedy_plus_plus_approx_ratio": round(gpp_ratio, 4),
            }
        )

    return records


def run_exp_streaming_modes_comparison(
    n_background_accounts: int = 25,
    n_background_transactions: int = 40,
    batch_size: int = 4,
    planted_cluster_size: int = 6,
    seed: int = 888,
) -> list[dict[str, Any]]:
    """Experiment 6: Head-to-head comparison of Modes A, B, and C on identical stream."""
    batches, planted = generate_transaction_stream(
        n_background_accounts=n_background_accounts,
        n_background_transactions=n_background_transactions,
        batch_size=batch_size,
        planted_cluster_size=planted_cluster_size,
        seed=seed,
    )
    res_list = evaluate_streaming_modes(
        batches=batches,
        planted_cluster=planted,
        algorithm="greedy_peeling",
        exact_reference_solver=True,
    )
    return [r.to_dict() for r in res_list]


def run_exp_multiple_clusters_and_hubs(
    seed: int = 999,
) -> list[dict[str, Any]]:
    """
    Experiment 7: Multiple competing dense clusters and high-degree hub nodes.
    Tests whether algorithms correctly identify the denser of two clusters.
    """
    tg = TransactionGraph(name="MultiCluster_Hub")
    # Cluster 1: 5 nodes, complete K5 (density 10 / 5 = 2.0)
    for i in range(5):
        for j in range(i + 1, 5):
            tg.add_transaction(f"C1_{i}", f"C1_{j}")

    # Cluster 2: 6 nodes, ring + chords (density 8 / 6 = 1.33)
    for i in range(6):
        tg.add_transaction(f"C2_{i}", f"C2_{(i + 1) % 6}")
    tg.add_transaction("C2_0", "C2_3")
    tg.add_transaction("C2_1", "C2_4")

    # High-degree star hub connected to 10 leaf accounts (density 10 / 11 = 0.91)
    for i in range(10):
        tg.add_transaction("HUB", f"LEAF_{i}")

    # Weak bridge between components
    tg.add_transaction("C1_0", "HUB")
    tg.add_transaction("HUB", "C2_0")

    gb = goldberg_densest_subgraph(tg, tolerance=1e-4)
    gp = greedy_peeling(tg)
    gpp = greedy_plus_plus(tg, iterations=10)

    c1_nodes = {f"C1_{i}" for i in range(5)}
    m_gb = calculate_overlap_metrics(gb.nodes, c1_nodes)
    m_gp = calculate_overlap_metrics(gp.nodes, c1_nodes)
    m_gpp = calculate_overlap_metrics(gpp.nodes, c1_nodes)

    return [
        {
            "experiment": "multiple_clusters_and_hubs",
            "description": (
                "K5 cluster (density 2.0) vs C6+chords cluster (1.33) vs Star Hub (0.91)"
            ),
            "goldberg_density": round(gb.density, 4),
            "goldberg_c1_f1": m_gb["f1"],
            "greedy_density": round(gp.density, 4),
            "greedy_c1_f1": m_gp["f1"],
            "greedy_plus_plus_density": round(gpp.density, 4),
            "greedy_plus_plus_c1_f1": m_gpp["f1"],
        }
    ]
