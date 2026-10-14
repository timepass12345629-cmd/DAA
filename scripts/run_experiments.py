"""
scripts/run_experiments.py — Automated research experiment runner for RingScope.

Executes Phase 3 empirical experiments:
1. Runtime vs Graph Size
2. Cluster Size vs Recovery
3. Cluster Sparsity vs Recovery
4. Background Connectivity vs Noise Overlap
5. Exact vs Approximate Density (against Brute-Force Oracle)
6. Streaming Modes Comparison (Mode A vs Mode B vs Mode C)
7. Multiple Clusters and High-Degree Hubs

Usage:
------
python scripts/run_experiments.py --experiments all --out-dir experiments_output
python scripts/run_experiments.py --experiments streaming --out-dir experiments_output
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure ringscope is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ringscope.eval_harness import export_results_to_csv, export_results_to_json
from ringscope.experiments import (
    run_exp_background_connectivity,
    run_exp_cluster_size_vs_recovery,
    run_exp_cluster_sparsity_vs_recovery,
    run_exp_exact_vs_approx_density,
    run_exp_multiple_clusters_and_hubs,
    run_exp_runtime_vs_graph_size,
    run_exp_streaming_modes_comparison,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RingScope — Research Experiment Runner"
    )
    parser.add_argument(
        "--experiments",
        type=str,
        default="all",
        help="Comma-separated experiment names to run, or 'all' (default: all)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="experiments_output",
        help="Directory to save CSV and JSON experiment exports (default: experiments_output)",
    )

    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    exp_choice = args.experiments.lower().split(",")
    run_all = "all" in exp_choice

    print("=" * 70)
    print("RingScope Phase 3 -- Research Experiment Suite")
    print(f"Output Directory: {out_dir.resolve()}")
    print("=" * 70)

    # 1. Runtime vs Graph Size
    if run_all or "runtime" in exp_choice:
        print("\n[1/7] Running: Runtime vs Graph Size...")
        t0 = time.perf_counter()
        res_runtime = run_exp_runtime_vs_graph_size(sizes=(10, 20, 40, 60))
        export_results_to_json(res_runtime, out_dir / "exp1_runtime_vs_size.json")
        export_results_to_csv(res_runtime, out_dir / "exp1_runtime_vs_size.csv")
        print(f"      Completed in {(time.perf_counter() - t0):.2f}s. Sample:")
        for r in res_runtime:
            print(f"      - N={r['num_nodes']:2d}, M={r['num_edges']:2d} | "
                  f"Greedy: {r['greedy_peeling_ms']:.2f}ms | "
                  f"Greedy++: {r['greedy_plus_plus_ms']:.2f}ms | "
                  f"Goldberg: {r['goldberg_ms']}ms")

    # 2. Cluster Size vs Recovery
    if run_all or "cluster_size" in exp_choice:
        print("\n[2/7] Running: Cluster Size vs Recovery...")
        t0 = time.perf_counter()
        res_csize = run_exp_cluster_size_vs_recovery(n_total=25, cluster_sizes=(4, 6, 8, 10))
        export_results_to_json(res_csize, out_dir / "exp2_cluster_size_recovery.json")
        export_results_to_csv(res_csize, out_dir / "exp2_cluster_size_recovery.csv")
        print(f"      Completed in {(time.perf_counter() - t0):.2f}s. Sample:")
        for r in res_csize:
            print(f"      - Size k={r['cluster_size']:2d} | "
                  f"Greedy F1={r['greedy_f1']:.3f} | "
                  f"Greedy++ F1={r['greedy_plus_plus_f1']:.3f} | "
                  f"Goldberg F1={r['goldberg_f1']:.3f}")

    # 3. Cluster Sparsity vs Recovery
    if run_all or "sparsity" in exp_choice:
        print("\n[3/7] Running: Cluster Sparsity vs Recovery...")
        t0 = time.perf_counter()
        res_sparsity = run_exp_cluster_sparsity_vs_recovery(n_total=25, cluster_size=6)
        export_results_to_json(res_sparsity, out_dir / "exp3_cluster_sparsity.json")
        export_results_to_csv(res_sparsity, out_dir / "exp3_cluster_sparsity.csv")
        print(f"      Completed in {(time.perf_counter() - t0):.2f}s.")

    # 4. Background Connectivity
    if run_all or "background" in exp_choice:
        print("\n[4/7] Running: Background Connectivity Noise...")
        t0 = time.perf_counter()
        res_bg = run_exp_background_connectivity(n_total=25, cluster_size=6)
        export_results_to_json(res_bg, out_dir / "exp4_background_connectivity.json")
        export_results_to_csv(res_bg, out_dir / "exp4_background_connectivity.csv")
        print(f"      Completed in {(time.perf_counter() - t0):.2f}s.")

    # 5. Exact vs Approximate Density against Brute Force Oracle
    if run_all or "exact" in exp_choice:
        print("\n[5/7] Running: Exact vs Approximate Density (Oracle Comparison)...")
        t0 = time.perf_counter()
        res_exact = run_exp_exact_vs_approx_density(sizes=(8, 12, 14))
        export_results_to_json(res_exact, out_dir / "exp5_exact_vs_approx.json")
        export_results_to_csv(res_exact, out_dir / "exp5_exact_vs_approx.csv")
        print(f"      Completed in {(time.perf_counter() - t0):.2f}s. Sample:")
        for r in res_exact:
            print(f"      - N={r['num_nodes']:2d} | OPT={r['optimal_density']:.4f} | "
                  f"Goldberg={r['goldberg_density']:.4f} | "
                  f"Greedy={r['greedy_density']:.4f} ({r['greedy_approx_ratio']:.3f}) | "
                  f"Greedy++={r['greedy_plus_plus_density']:.4f} "
                  f"({r['greedy_plus_plus_approx_ratio']:.3f})")

    # 6. Streaming Modes Comparison (Modes A, B, C)
    if run_all or "streaming" in exp_choice:
        print("\n[6/7] Running: Streaming Candidate Maintenance Modes (A vs B vs C)...")
        t0 = time.perf_counter()
        res_stream = run_exp_streaming_modes_comparison(
            n_background_accounts=20,
            n_background_transactions=30,
            batch_size=3,
            planted_cluster_size=5,
        )
        export_results_to_json(res_stream, out_dir / "exp6_streaming_modes.json")
        export_results_to_csv(res_stream, out_dir / "exp6_streaming_modes.csv")
        print(f"      Completed in {(time.perf_counter() - t0):.2f}s. Summary:")
        for r in res_stream:
            print(f"      - {r['mode']:28s} | Latency: {r['total_runtime_ms']:.2f}ms | "
                  f"Recomps: {r['total_recomputations']:2d}/{r['total_batches']:2d} | "
                  f"Density: {r['final_density']:.4f} | F1: {r['f1']:.3f}")

    # 7. Multiple Clusters and High-Degree Hubs
    if run_all or "hubs" in exp_choice:
        print("\n[7/7] Running: Multiple Competing Clusters and Hub Nodes...")
        t0 = time.perf_counter()
        res_hubs = run_exp_multiple_clusters_and_hubs()
        export_results_to_json(res_hubs, out_dir / "exp7_clusters_and_hubs.json")
        export_results_to_csv(res_hubs, out_dir / "exp7_clusters_and_hubs.csv")
        print(f"      Completed in {(time.perf_counter() - t0):.2f}s.")
        h0 = res_hubs[0]
        print(f"      - Goldberg density={h0['goldberg_density']}, C1 F1={h0['goldberg_c1_f1']}")

    print("\n" + "=" * 70)
    print(f"All experiments successfully executed and exported to: {out_dir.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
