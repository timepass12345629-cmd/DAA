"""
Script to benchmark trigger strategies with repeated runs and fixed seeds.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ringscope.stream_simulator import (
    FullRecomputationMaintainer,
    IncrementalHeuristicMaintainer,
    StreamBatch,
    TransactionRecord,
    WarmStartedMaintainer,
    generate_transaction_stream,
)

NUM_RUNS = 10
SEEDS = [42, 888, 12345]


def run_benchmark():
    out_dir = Path("experiments_output/audit_mode_c_eval_20261017")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_seed_results = []

    for seed in SEEDS:
        print(f"\n=======================================================")
        print(f"Benchmarking Exp 6 Stream with Seed = {seed}")
        print(f"=======================================================")

        batches, planted = generate_transaction_stream(
            n_background_accounts=20,
            n_background_transactions=30,
            batch_size=3,
            planted_cluster_size=5,
            seed=seed,
        )

        modes = [
            ("Mode A (Full Recomputation)", lambda: FullRecomputationMaintainer(algorithm="greedy_peeling")),
            ("Mode B (Warm-Started)", lambda: WarmStartedMaintainer(algorithm="greedy_peeling")),
            ("Mode C (Global Degree)", lambda: IncrementalHeuristicMaintainer(algorithm="greedy_peeling", hub_trigger_type="global_degree")),
            ("Mode C (Candidate-Incident)", lambda: IncrementalHeuristicMaintainer(algorithm="greedy_peeling", hub_trigger_type="candidate_incident")),
            ("Mode C (Hybrid)", lambda: IncrementalHeuristicMaintainer(algorithm="greedy_peeling", hub_trigger_type="hybrid")),
        ]

        mode_stats = {}
        for mode_name, factory in modes:
            runtimes = []
            final_recomps = 0
            final_dens = 0.0
            final_cand = set()

            for _ in range(NUM_RUNS):
                maintainer = factory()
                t0 = time.perf_counter()
                for b in batches:
                    maintainer.process_batch(b)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                runtimes.append(elapsed_ms)
                final_recomps = maintainer.recomputation_count
                final_dens = maintainer.current_density
                final_cand = set(maintainer.current_candidate)

            mode_stats[mode_name] = {
                "runtimes": runtimes,
                "recomps": final_recomps,
                "density": final_dens,
                "cand": final_cand,
            }

        candA = mode_stats["Mode A (Full Recomputation)"]["cand"]

        seed_records = []
        for mode_name, _ in modes:
            st = mode_stats[mode_name]
            mean_lat = sum(st["runtimes"]) / len(st["runtimes"])
            candM = st["cand"]
            jaccard = len(candA & candM) / len(candA | candM) if (candA | candM) else 1.0

            rec = {
                "seed": seed,
                "mode": mode_name,
                "total_batches": len(batches),
                "total_recomputations": st["recomps"],
                "recomputation_rate": round(st["recomps"] / len(batches), 4),
                "mean_total_latency_ms": round(mean_lat, 3),
                "mean_batch_latency_ms": round(mean_lat / len(batches), 4),
                "min_latency_ms": round(min(st["runtimes"]), 3),
                "max_latency_ms": round(max(st["runtimes"]), 3),
                "final_density": round(st["density"], 5),
                "jaccard_overlap_mode_a": round(jaccard, 4),
                "candidate_nodes_count": len(candM),
            }
            seed_records.append(rec)
            print(
                f"{mode_name:28s} | Lat: {mean_lat:6.3f}ms | "
                f"Recomp: {st['recomps']:2d}/{len(batches)} | "
                f"Density: {st['density']:.5f} | "
                f"Jaccard: {jaccard:.4f}"
            )

        all_seed_results.extend(seed_records)

    # Save to disk
    json_path = out_dir / "exp6_multitrigger_benchmark.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_seed_results, f, indent=2)
    print(f"\nSaved benchmark results to {json_path.resolve()}")


if __name__ == "__main__":
    run_benchmark()
