# Mode C Hub-Trigger Audit & Evaluation Report (Stage 2)

**Date of Audit:** October 17, 2026  
**Auditor:** Senior Software Architect & Verification Engineer  
**Working Branch:** `audit/mode-c-hub-trigger` (unmerged, working copy cleanly isolated from `main`)  
**Target Modules:**  
- [`ringscope/stream_simulator.py`](file:///c:/VS%20code/DAA/ringscope/stream_simulator.py) (`IncrementalHeuristicMaintainer`)  
- [`ringscope/service.py`](file:///c:/VS%20code/DAA/ringscope/service.py) (`StreamSession`)  
**Stage 1 Output Directory:** `experiments_output/audit_mode_c_eval_20261017/`  
**Stage 2 Output Directory:** `experiments_output/audit_stage2_eval_20261017/`  
**Test Suite:** [`tests/test_mode_c_triggers.py`](file:///c:/VS%20code/DAA/tests/test_mode_c_triggers.py)  

---

## 1. Executive Summary & Core Insights

In streaming densest-subgraph maintenance, Mode C achieves sub-millisecond batch throughput by maintaining the current candidate cluster $S_{\text{cand}}$ and updating its density locally in $O(1)$ time. However, to remain aware of topology changes beyond $S_{\text{cand}}$, it relies on trigger rules to initiate full recomputations.

This audit evaluated three hub-trigger strategies:
1. **The Existing Global-Degree Trigger (`global_degree`):**  
   Evaluates $\text{deg}_G(v) > \max(3.0, 1.5 \cdot \rho(S_{\text{cand}}))$ for affected vertices $v \notin S_{\text{cand}}$.
2. **The Candidate-Aware Incident-Degree Trigger (`candidate_incident`):**  
   Evaluates whether an external vertex has incident connections into the candidate strictly exceeding current density: $\text{deg}_{S_{\text{cand}}}(v) > \rho(S_{\text{cand}})$.
3. **The Combined Hybrid Trigger (`hybrid`):**  
   Fires if *either* the candidate-incident condition is met *or* the external global degree threshold is breached.

### Key Audit Findings:
- **Strict Decoupling of Local Expansion vs. Disjoint Discovery:**  
  - The **Candidate-Aware trigger** is mathematically sound for *local candidate expansion* ($\rho(S \cup \{v\}) > \rho(S) \iff \text{deg}_S(v) > \rho(S)$) and avoids false-positive recomputations on isolated external star hubs.
  - However, **candidate-aware triggering cannot detect disjoint global densification by itself**. If diffuse background edges connect external nodes together without touching $S_{\text{cand}}$, candidate-incident triggering remains blind until the periodic modulo timer fires.
  - In adversarial benchmarks with disconnected dense clusters ($K_5$), Candidate-Incident suffers a **5-batch detection delay**, while Global Degree and Hybrid trigger recomputation with **0 delay**.
  - The **Hybrid trigger** successfully bridges this gap: it captures candidate-adjacent expansion immediately while preserving the global safeguard for external cluster growth. Across 12 seeds, Hybrid achieved a **0.9907 mean Jaccard overlap** against Mode A, while executing 27% fewer recomputations than Mode A.
- **Mathematical Bound Disclaimer:**  
  Mode C remains an **empirical heuristic**. In the interval between trigger activations, there is no universal worst-case approximation guarantee.

---

## 2. Source Code Changes & Runtime Validation

### 2.1 Runtime Validation in `IncrementalHeuristicMaintainer`
In [`ringscope/stream_simulator.py`](file:///c:/VS%20code/DAA/ringscope/stream_simulator.py):
```python
valid_triggers = ("global_degree", "candidate_incident", "hybrid")
if hub_trigger_type not in valid_triggers:
    raise ValueError(
        f"Invalid hub_trigger_type '{hub_trigger_type}'. "
        f"Must be one of: {', '.join(valid_triggers)}"
    )
```
- Restricts `hub_trigger_type` strictly to the three evaluated options.
- Any empty string or unrecognized trigger name immediately raises a descriptive `ValueError`.

### 2.2 API & Service Passthrough
In [`ringscope/service.py`](file:///c:/VS%20code/DAA/ringscope/service.py):
```python
elif mode == "incremental_heuristic":
    self.maintainer = IncrementalHeuristicMaintainer(
        algorithm=algorithm,
        recompute_interval=cfg.get("recompute_interval", 5),
        external_edge_threshold=cfg.get("external_edge_threshold", 10),
        external_degree_ratio=cfg.get(
            "external_degree_ratio",
            cfg.get("hub_degree_ratio", 1.5),
        ),
        hub_trigger_type=cfg.get("hub_trigger_type", "global_degree"),
    )
```
- Exposes `hub_trigger_type` to all callers of `StreamStartRequest` / `service.start_stream`.
- Defaults safely to `"global_degree"`, completely preserving backward compatibility.

---

## 3. Test Suite & Verification Results

Full backend test suite status:
```powershell
.\.venv\Scripts\pytest.exe tests/ -v
# Result: 175 passed in 23.44s (100% pass rate)
```

The dedicated test suite [`tests/test_mode_c_triggers.py`](file:///c:/VS%20code/DAA/tests/test_mode_c_triggers.py) provides 7 targeted tests:
1. `test_disjoint_dense_cluster_detection_delay`: Baseline 2-batch lag demonstration when periodic interval is 5.
2. `test_high_degree_external_hub_without_candidate_edges`: Star hub with 10 leaves correctly ignored by candidate-incident (0 recomp) vs unnecessary recomputation under global-degree.
3. `test_external_node_augmenting_candidate_density`: Mathematical verification that adding a node with 3 incident edges strictly increases density from $\rho=1.00$ to $\rho=1.40$, correctly identified by greedy peeling.
4. `test_parallel_transactions_do_not_inflate_external_counter`: Verifies that duplicate transactions on the same external edge increment the counter by 1, not 10.
5. `test_hub_trigger_type_runtime_validation`: Asserts valid trigger strings succeed and invalid types raise `ValueError`.
6. `test_adversarial_disconnected_dense_cluster_delay_across_strategies`: Injects a disconnected $K_5$ ($\rho=2.0$) across batches 1–3 when candidate is a 4-cycle ($\rho=1.0$) and `recompute_interval=8`.
   - **Mode A (Full)**: Detection delay = **0 batches** (batch 3).
   - **Mode C (Global Degree)**: Detection delay = **0 batches** (batch 3, degree $4 > 3.0$).
   - **Mode C (Hybrid)**: Detection delay = **0 batches** (batch 3).
   - **Mode C (Candidate-Incident)**: Detection delay = **5 batches** (delayed until batch 8 periodic refresh).
7. `test_api_stream_start_hub_trigger_passthrough`: Tests `BackendService.start_stream` configuration handling, defaulting to `"global_degree"` and raising `ValueError` on invalid inputs.

---

## 4. Benchmark Calculations & Latency Statistics

### 4.1 Statistical Methodology (Correct Aggregation)
In multi-seed streaming benchmarks, two distinct sources of variation exist:
1. **Microsecond execution jitter (within-seed repetitions):** Operating system context switching, scheduling noise, and CPU frequency variations.
2. **Structural graph variation (cross-seed differences):** Variations in stream density, arrival order, and graph topology.

To prevent conflation, we report:
- **Pooled Trial Statistics ($N=120$ per strategy):** Combining all 12 seeds $\times$ 10 repetitions.
- **Cross-Seed Variation:** Mean and standard deviation of per-seed averages ($K=12$ seeds).

> [!IMPORTANT]
> **Avoid Claims of Statistical Significance:** Differences between Mode A, Hybrid, and Global degree ($\Delta \approx 0.03\text{ ms} - 0.28\text{ ms}$) fall within typical OS scheduler jitter ($\sigma \approx 0.58\text{ ms} - 0.77\text{ ms}$). Claims of statistical significance are omitted because micro-benchmarking on small graphs ($N \le 25$) exhibits overlapping confidence bands. Candidate-Incident, however, shows a substantial reduction in both recomputation count (39.4% vs 100%) and mean runtime (1.718 ms vs 2.612 ms).

### 4.2 Latency Statistics Summary (12 Seeds, 10 Repetitions Each)

| Strategy | Recomputation Rate | Pooled Mean Latency | Pooled Median | Pooled Stdev | Pooled Min–Max Range | Cross-Seed Mean | Cross-Seed Stdev |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Mode A (Full)** | 100.0% (12.92 / 12.8) | 2.612 ms | 2.380 ms | 0.716 ms | [1.624, 4.870] ms | 2.612 ms | 0.506 ms |
| **Mode B (Warm)** | 100.0% (12.92 / 12.8) | 3.036 ms | 2.790 ms | 0.773 ms | [1.932, 5.403] ms | 3.036 ms | 0.505 ms |
| **Mode C (Global)** | 61.3% (7.92 / 12.8) | 2.332 ms | 2.173 ms | 0.586 ms | [1.661, 4.349] ms | 2.332 ms | 0.366 ms |
| **Mode C (Candidate-Incident)** | **39.4% (5.08 / 12.8)** | **1.718 ms** | **1.540 ms** | **0.507 ms** | **[1.136, 3.566] ms** | **1.718 ms** | **0.360 ms** |
| **Mode C (Hybrid)** | 73.0% (9.42 / 12.8) | 2.584 ms | 2.372 ms | 0.764 ms | [1.633, 6.816] ms | 2.584 ms | 0.492 ms |

### 4.3 Quality & Detection Accuracy

| Strategy | Mean Jaccard (vs Mode A) | Delayed Epochs (Across 12 Seeds) | Missed by Stream End |
| :--- | :---: | :---: | :---: |
| **Mode A (Full)** | 1.0000 | 0 | 0 |
| **Mode B (Warm)** | 1.0000 | 0 | 0 |
| **Mode C (Global)** | 0.9827 | 6 | 3 |
| **Mode C (Candidate-Incident)** | 0.7419 | 5 | 5 |
| **Mode C (Hybrid)** | **0.9907** | **2** | **1** |

---

## 5. Limitations & Caveats

1. **No Universal Approximation Bound:**  
   Mode C remains a heuristic. While periodic recomputations provide safety bounds at defined intervals, between recomputations the candidate density may drift arbitrarily from the true densest subgraph if background edges form dense disconnected clusters that do not trigger threshold conditions.
2. **Trade-off Profile:**  
   - `candidate_incident`: Ideal when the fraud ring is known to expand locally through adjacent accounts. Slashes recomputations by ~60%, but blind to disjoint clusters.
   - `hybrid`: Recommended compromise for streaming production. Retains 99.07% Jaccard fidelity with Mode A while reducing recomputations by 27%.
   - `global_degree`: Conservative and robust, but susceptible to false-positive recomputations on isolated star hubs.

---

## 6. Exact Reproduction Commands

```powershell
# 1. Run target Mode C unit and regression tests
.\.venv\Scripts\pytest.exe tests/test_mode_c_triggers.py -v

# 2. Run full backend verification test suite
.\.venv\Scripts\pytest.exe tests/ -v

# 3. Execute multi-seed evaluation benchmark
python scripts/run_stage2_evaluation.py
```
