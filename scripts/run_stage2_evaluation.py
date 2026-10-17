"""
scripts/run_stage2_evaluation.py — Comprehensive multi-seed evaluation across 10+ seeds.

Evaluates:
- Mode A (Full Recomputation)
- Mode B (Warm-Started)
- Mode C (Global Degree)
- Mode C (Candidate-Incident)
- Mode C (Hybrid)

Metrics collected:
- Recomputation count & rate
- Latency (mean, median, stdev, min, max, range over 10 repetitions)
- Final candidate density and density gap vs Mode A
- Jaccard overlap vs Mode A
- Disjoint-cluster detection delay
"""

from __future__ import annotations

import json
import statistics
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

SEEDS = [11, 22, 33, 42, 55, 77, 101, 202, 555, 777, 888, 12345]
NUM_REPETITIONS = 10


def run_stage2_eval():
    out_dir = Path("experiments_output/audit_stage2_eval_20261017")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_records = []
    timing_details = []

    print("================================================================================")
    print(f"Stage 2 Trigger Evaluation across {len(SEEDS)} Seeds ({NUM_REPETITIONS} runs per configuration)")
    print("================================================================================")

    for seed in SEEDS:
        batches, planted = generate_transaction_stream(
            n_background_accounts=20,
            n_background_transactions=30,
            batch_size=3,
            planted_cluster_size=5,
            seed=seed,
        )

        modes = [
            ("Mode A (Full)", lambda: FullRecomputationMaintainer(algorithm="greedy_peeling")),
            ("Mode B (Warm)", lambda: WarmStartedMaintainer(algorithm="greedy_peeling")),
            ("Mode C (Global)", lambda: IncrementalHeuristicMaintainer(algorithm="greedy_peeling", hub_trigger_type="global_degree")),
            ("Mode C (Candidate-Incident)", lambda: IncrementalHeuristicMaintainer(algorithm="greedy_peeling", hub_trigger_type="candidate_incident")),
            ("Mode C (Hybrid)", lambda: IncrementalHeuristicMaintainer(algorithm="greedy_peeling", hub_trigger_type="hybrid")),
        ]

        mode_data = {}
        for mode_name, factory in modes:
            runtimes = []
            final_recomps = 0
            final_dens = 0.0
            final_cand = set()
            history = []

            for _ in range(NUM_REPETITIONS):
                m = factory()
                t0 = time.perf_counter()
                for b in batches:
                    m.process_batch(b)
                elapsed = (time.perf_counter() - t0) * 1000.0
                runtimes.append(elapsed)
                final_recomps = m.recomputation_count
                final_dens = m.current_density
                final_cand = set(m.current_candidate)
                history = m.history

            mode_data[mode_name] = {
                "runtimes": runtimes,
                "recomps": final_recomps,
                "density": final_dens,
                "cand": final_cand,
                "history": history,
            }

        # Baseline reference: Mode A
        mA_cand = mode_data["Mode A (Full)"]["cand"]
        mA_dens = mode_data["Mode A (Full)"]["density"]
        mA_hist = mode_data["Mode A (Full)"]["history"]

        for mode_name, _ in modes:
            d = mode_data[mode_name]
            runtimes = d["runtimes"]
            m_cand = d["cand"]
            m_dens = d["density"]
            m_hist = d["history"]

            # Statistics
            mean_lat = statistics.mean(runtimes)
            median_lat = statistics.median(runtimes)
            stdev_lat = statistics.stdev(runtimes) if len(runtimes) > 1 else 0.0
            min_lat = min(runtimes)
            max_lat = max(runtimes)
            lat_range = max_lat - min_lat

            # Overlap & Gap
            jaccard = len(mA_cand & m_cand) / len(mA_cand | m_cand) if (mA_cand | m_cand) else 1.0
            dens_gap = abs(mA_dens - m_dens)

            # Measure detection delay for the optimal cluster
            # Find the batch where Mode A reaches its final optimal candidate
            opt_batch_A = None
            for step in mA_hist:
                if set(step.candidate_nodes) == mA_cand:
                    opt_batch_A = step.batch_index
                    break

            # Find the batch where this mode reaches mA_cand (if ever)
            opt_batch_mode = None
            for step in m_hist:
                if set(step.candidate_nodes) == mA_cand:
                    opt_batch_mode = step.batch_index
                    break

            if opt_batch_mode is not None and opt_batch_A is not None:
                delay = max(0, opt_batch_mode - opt_batch_A)
            elif opt_batch_mode is None:
                delay = -1  # Did not reach Mode A's candidate by stream end
            else:
                delay = 0

            summary_records.append({
                "seed": seed,
                "mode": mode_name,
                "total_batches": len(batches),
                "total_recomputations": d["recomps"],
                "recomputation_rate": round(d["recomps"] / len(batches), 4),
                "mean_latency_ms": round(mean_lat, 3),
                "median_latency_ms": round(median_lat, 3),
                "stdev_latency_ms": round(stdev_lat, 3),
                "min_latency_ms": round(min_lat, 3),
                "max_latency_ms": round(max_lat, 3),
                "latency_range_ms": round(lat_range, 3),
                "final_density": round(m_dens, 5),
                "density_gap_vs_mode_a": round(dens_gap, 5),
                "jaccard_overlap_mode_a": round(jaccard, 4),
                "detection_delay_batches": delay,
            })

            timing_details.append({
                "seed": seed,
                "mode": mode_name,
                "raw_runtimes_ms": [round(x, 3) for x in runtimes],
            })

        print(f"Seed {seed:5d} completed.")

    # Save summary and timing details
    with open(out_dir / "stage2_summary_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary_records, f, indent=2)

    with open(out_dir / "stage2_raw_timings.json", "w", encoding="utf-8") as f:
        json.dump(timing_details, f, indent=2)

    # Print aggregated cross-seed table
    print("\n" + "=" * 95)
    print(f"{'Strategy':26s} | {'Mean Recomps':12s} | {'Mean Latency':12s} | {'Mean Stdev':10s} | {'Mean Jaccard':12s} | {'Delayed / Missed':16s}")
    print("=" * 95)
    
    unique_modes = [m[0] for m in modes]
    for um in unique_modes:
        recs = [r for r in summary_records if r["mode"] == um]
        avg_recomp = statistics.mean([r["total_recomputations"] for r in recs])
        avg_lat = statistics.mean([r["mean_latency_ms"] for r in recs])
        avg_stdev = statistics.mean([r["stdev_latency_ms"] for r in recs])
        avg_jaccard = statistics.mean([r["jaccard_overlap_mode_a"] for r in recs])
        delays = [r["detection_delay_batches"] for r in recs]
        delayed_count = sum(1 for d in delays if d > 0)
        missed_count = sum(1 for d in delays if d == -1)

        print(f"{um:26s} | {avg_recomp:8.2f} / 12.8 | {avg_lat:8.3f} ms | {avg_stdev:7.3f} ms | {avg_jaccard:10.4f} | {delayed_count} delayed, {missed_count} missed")
    print("=" * 95)


if __name__ == "__main__":
    run_stage2_eval()
