# 05 — Experiments, Benchmarks, and Verification Evidence

**Project:** RingScope  
**Document:** Complete Inventory of Experiments, Output Artifacts, Reproducibility, and Evidence Limits  
**Verification Level:** `SOURCE-VERIFIED` / `TEST-VERIFIED` / `OUTPUT-VERIFIED`  

---

## 1. Experiment Inventory

`SOURCE-VERIFIED` [scripts/run_experiments.py](file:///c:/VS%20code/DAA/scripts/run_experiments.py#L40-L450), [ringscope/experiment_harness.py](file:///c:/VS%20code/DAA/ringscope/experiment_harness.py#L30-L280)

RingScope defines 7 core experimental protocols designed to evaluate algorithm scalability, cluster recovery accuracy, noise tolerance, oracle exactness, streaming latency, and competing topological structures.

| Exp ID | Experiment Name | Primary Objective / Hypothesis | Graph Generator & Parameters | Seed | Output Artifact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Exp 1** | Runtime vs Graph Size | Measure wall-clock scaling of Goldberg vs Peeling vs Greedy++ as $N$ grows. | ER Random Graph: $N \in \{10, 20, 40, 60\}$, $p=0.2$ | 42 | `exp1_runtime_vs_size.csv` / `.json` |
| **Exp 2** | Planted Cluster Recovery | Verify candidate recovery rate as planted clique size $k$ varies. | Background $N=25, p=0.08$; Planted clique $k \in \{4, 6, 8, 10\}$ | 42 | `exp2_planted_cluster.csv` / `.json` |
| **Exp 3** | Cluster Sparsity vs Recovery | Test whether algorithms can isolate diffuse, non-clique dense clusters. | Background $N=30, p=0.08$; Planted $k=8, p_{\text{in}} \in [0.4, 0.9]$ | 42 | `exp3_cluster_sparsity.csv` / `.json` |
| **Exp 4** | Background Noise Sweep | Evaluate degradation in recovery as random background density increases. | Planted $K_6$ in $N=30$; Background $p_{\text{out}} \in [0.02, 0.25]$ | 42 | `exp4_noise_sweep.csv` / `.json` |
| **Exp 5** | Exact vs Approx vs Oracle | Benchmark density and recovery against exhaustive $2^N$ brute-force oracle. | ER Random Graphs $N \in \{8, 12, 14\}, p \in \{0.2, 0.35, 0.5\}$ | 42 | `exp5_exact_vs_approx.csv` / `.json` |
| **Exp 6** | Streaming Modes Comparison | Measure recomputation counts and latency of Mode A vs Mode B vs Mode C. | Initial $N=20, p=0.08$; 12 streaming batches of 5 edges + planted ring | 42 | `exp6_streaming_modes.csv` / `.json` |
| **Exp 7** | Competing Clusters | Test resolution when multiple distinct dense structures co-exist. | $K_5$ clique vs $C_6$ cycle with cross-chords vs star hub | 42 | `exp7_competing_clusters.csv` / `.json` |

---

## 2. Artifact Directory Structure and File Verification

The directory `experiments_output/` contains both historical baseline runs and newly verified reproduction runs:

```
experiments_output/
├── baseline_phase6/                 # Archived Phase 6 benchmarks
│   ├── exp1_runtime_vs_size.csv    # 12 rows (4 sizes x 3 algorithms)
│   ├── exp2_planted_cluster.csv    # 12 rows (4 clique sizes x 3 algorithms)
│   ├── exp3_cluster_sparsity.csv   # 18 rows (6 sparsities x 3 algorithms)
│   ├── exp4_noise_sweep.csv        # 18 rows (6 noise levels x 3 algorithms)
│   ├── exp5_exact_vs_approx.csv    # 18 rows (6 graphs x 3 algorithms + oracle)
│   ├── exp6_streaming_modes.csv    # 36 rows (12 batches x 3 modes)
│   └── exp7_competing_clusters.csv # 3 rows (3 algorithms)
│
├── reproduced/                     # Phase 7 reproduction runs (identical seeds)
│   ├── exp1_runtime_vs_size.csv
│   ├── exp2_planted_cluster.csv
│   ├── exp3_cluster_sparsity.csv
│   ├── exp4_noise_sweep.csv
│   ├── exp5_exact_vs_approx.csv
│   ├── exp6_streaming_modes.csv    # Verified Mode C recomputation reduction
│   └── exp7_competing_clusters.csv
│
└── *.csv / *.json                  # Individual ad-hoc benchmark runs
```

---

## 3. Detailed Inspection of Critical Benchmark Results

### 3.1 Experiment 5: Exactness vs. Brute-Force Oracle
`OUTPUT-VERIFIED` [experiments_output/reproduced/exp5_exact_vs_approx.csv](file:///c:/VS%20code/DAA/experiments_output/reproduced/exp5_exact_vs_approx.csv)

Across all test graphs up to $N=14$:
- **Goldberg Exactness:** Goldberg's returned density matched the exponential brute-force oracle with **0.000000 error** in 100% of cases.
- **Charikar Peeling Approximation Ratio:** Observed approximation ratio $\frac{\rho_{\text{peeling}}}{\rho_{\text{oracle}}} \in [0.750, 1.000]$, strictly abiding by the theoretical 0.500 lower bound.
- **Greedy++ Refinement:** Observed ratio $\frac{\rho_{\text{greedy++}}}{\rho_{\text{oracle}}} \in [0.916, 1.000]$, narrowing the density gap over Charikar peeling on irregular topologies.

### 3.2 Experiment 6: Streaming Modes Latency and Recomputation
`OUTPUT-VERIFIED` [experiments_output/reproduced/exp6_streaming_modes.csv](file:///c:/VS%20code/DAA/experiments_output/reproduced/exp6_streaming_modes.csv)

Comparing Mode A, Mode B, and Mode C over 12 consecutive batches:

| Metric | Mode A (Full Recompute) | Mode B (Warm-Start) | Mode C (Incremental Heuristic) |
| :--- | :--- | :--- | :--- |
| **Total Batches Processed** | 12 | 12 | 12 |
| **Recomputations Executed** | 12 (100.0%) | 12 (100.0%) | **4 (33.3%)** |
| **Bypassed / Incremental Batches**| 0 (0.0%) | 0 (0.0%) | **8 (66.7%)** |
| **Cumulative Runtime (ms)** | 29.678 ms | 25.501 ms | **15.922 ms** |
| **Mean Latency per Batch (ms)** | 2.473 ms | 2.125 ms | **1.327 ms (-46.3%)** |
| **Final Candidate Density** | 1.3125 | 1.3125 | 1.3125 |

#### Baseline vs. Reproduced Anomaly Resolved
- In the initial Phase 6 baseline `experiments_output/baseline_phase6/exp6_streaming_modes.csv`, Mode C executed 11 recomputations out of 12 because unique edge counters were inflated due to the duplicate-edge checking bug.
- In the reproduced run under Phase 7, the bug fix ensured that Mode C executed only **4 recomputations** (at batches where the periodic refresh fired or a planted ring entered), delivering the intended **46.3% runtime reduction**.

---

## 4. Benchmark Limitations and Methodological Boundaries

The independent reviewer must note the following methodological constraints:
1. **Synthetic Nature:** All graphs were generated using Erdős–Rényi random models or synthetic planted cliques. No real-world interbank settlement (e.g., Fedwire, SWIFT) or blockchain transaction graphs (e.g., Ethereum) were benchmarked.
2. **Small Scale ($N \le 200$):** Due to the $O(V^2 E)$ worst-case complexity of Dinic max-flow, Goldberg's solver was not benchmarked on graphs exceeding $N=200$. On large production graphs, Charikar peeling or localized Ego-network extraction must be used.
3. **Single Core Execution:** All benchmarks were run single-threaded on a Windows workstation CPU; distributed or GPU acceleration was not implemented.
