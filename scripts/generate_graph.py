"""
scripts/generate_graph.py — CLI tool to generate a synthetic graph and display its statistics.

Usage
-----
python scripts/generate_graph.py --nodes 30 --cluster-size 10 --p-internal 0.8 \
    --p-external 0.1 --seed 42
python scripts/generate_graph.py --nodes 12 --cluster-size 5 --p-internal 0.9 \
    --p-external 0.05 --seed 7 --solve-densest
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure ringscope is on path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ringscope.algorithms.brute_force import MAX_BRUTE_FORCE_NODES, brute_force_densest_subgraph
from ringscope.algorithms.goldberg import goldberg_densest_subgraph
from ringscope.algorithms.greedy_peeling import greedy_peeling
from ringscope.algorithms.greedy_plus_plus import greedy_plus_plus
from ringscope.data import generate_planted_cluster_graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RingScope — Generate synthetic graph with planted dense cluster."
    )
    parser.add_argument(
        "--nodes", type=int, default=30, help="Total number of vertices (default: 30)"
    )
    parser.add_argument(
        "--cluster-size",
        type=int,
        default=10,
        help="Number of vertices in the planted dense cluster (default: 10)",
    )
    parser.add_argument(
        "--p-internal",
        type=float,
        default=0.7,
        help="Internal connection probability for planted cluster (default: 0.7)",
    )
    parser.add_argument(
        "--p-external",
        type=float,
        default=0.1,
        help="External / background connection probability (default: 0.1)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--solve-densest",
        action="store_true",
        help=f"Run brute-force densest solver (only for <= {MAX_BRUTE_FORCE_NODES} nodes)",
    )
    parser.add_argument(
        "--csv-out",
        type=str,
        default=None,
        help="Optional filepath to export the graph as a CSV edge-list",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("RingScope -- Synthetic Graph Generator & Statistics")
    print("=" * 60)
    print(f"Configuration: N={args.nodes}, Cluster={args.cluster_size}, "
          f"p_in={args.p_internal}, p_out={args.p_external}, seed={args.seed}")
    print("-" * 60)

    res = generate_planted_cluster_graph(
        n_total=args.nodes,
        cluster_size=args.cluster_size,
        p_internal=args.p_internal,
        p_external=args.p_external,
        seed=args.seed,
    )
    tg = res.graph

    # Compute graph statistics
    degrees = list(tg.degrees().values())
    min_deg = min(degrees) if degrees else 0
    max_deg = max(degrees) if degrees else 0
    avg_deg = (sum(degrees) / len(degrees)) if degrees else 0.0

    comps = tg.connected_components()
    comp_sizes = [len(c) for c in comps]

    print("GRAPH TOPOLOGY STATISTICS:")
    print(f"  * Vertices (Accounts)            : {tg.num_vertices}")
    print(f"  * Unique Edges                   : {tg.num_unique_edges}")
    print(f"  * Total Transaction Records      : {tg.total_transaction_records}")
    print(f"  * Self-loops Skipped             : {tg.self_loops_skipped}")
    print(f"  * Vertex Degree [min / avg / max]: {min_deg} / {avg_deg:.2f} / {max_deg}")
    print(f"  * Connected Components           : {len(comps)} (sizes: {comp_sizes})")
    print(f"  * Whole Graph Density            : {tg.density():.4f}")
    print("-" * 60)
    print("PLANTED CLUSTER GROUND TRUTH:")
    print(f"  * Planted Cluster Size           : {len(res.planted_cluster)}")
    print(f"  * Planted Cluster Density        : {res.cluster_density:.4f}")
    print(f"  * Background Vertices Density    : {res.background_density:.4f}")
    print(f"  * Planted Vertices               : {sorted(res.planted_cluster)}")

    if args.csv_out:
        out_path = Path(args.csv_out)
        import csv
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["source", "target", "tx_count", "amount", "timestamp"])
            for u, v, data in tg.graph.edges(data=True):
                writer.writerow([
                    u,
                    v,
                    data.get("tx_count", 1),
                    data.get("amount", 1.0),
                    data.get("timestamp", 0.0),
                ])
        print("-" * 60)
        print(f"Exported edge-list to: {out_path}")

    if args.solve_densest:
        print("-" * 60)
        print("DENSEST SUBGRAPH ALGORITHM COMPARISON:")
        # 1. Goldberg exact flow solver
        gb = goldberg_densest_subgraph(tg, tolerance=1e-4)
        print(f"  * Goldberg Flow Density          : {gb.density:.4f} "
              f"({gb.node_count} nodes, {gb.flow_computations} flows, {gb.runtime_sec*1000:.2f}ms)")

        # 2. Charikar Greedy Peeling (2-approx)
        gp = greedy_peeling(tg)
        print(f"  * Charikar Greedy Peeling Density: {gp.density:.4f} "
              f"({gp.node_count} nodes, {gp.runtime_sec*1000:.2f}ms)")

        # 3. Greedy++ (Iterative load-weighted peeling)
        gpp = greedy_plus_plus(tg, iterations=10)
        print(f"  * Greedy++ (T=10) Density        : {gpp.density:.4f} "
              f"({gpp.node_count} nodes, best iter {gpp.best_iteration}, "
              f"{gpp.runtime_sec*1000:.2f}ms)")

        # 4. Brute Force Oracle (if small)
        print("  * Brute-force Reference Oracle   : ", end="")
        if tg.num_vertices > MAX_BRUTE_FORCE_NODES:
            print(f"[SKIPPED] N={tg.num_vertices} > {MAX_BRUTE_FORCE_NODES}")
        else:
            t_bf = time.perf_counter()
            bf = brute_force_densest_subgraph(tg, max_nodes=MAX_BRUTE_FORCE_NODES)
            elapsed_bf = (time.perf_counter() - t_bf) * 1000
            print(f"{bf.density:.4f} ({bf.node_count} nodes, "
                  f"{bf.subsets_evaluated} subsets, {elapsed_bf:.2f}ms)")

    print("=" * 60)


if __name__ == "__main__":
    main()
