# 04 — Streaming Modes and Dynamic Maintenance

**Project:** RingScope  
**Document:** In-Depth Analysis of Streaming Maintenance Modes A, B, and C  
**Verification Level:** `SOURCE-VERIFIED` / `TEST-VERIFIED` / `OUTPUT-VERIFIED`  

---

## 1. Overview of Streaming Objectives

In transaction surveillance, transactions arrive continuously as event streams. Repeatedly running full exact densest subgraph algorithms over the global graph introduces severe latency bottlenecks.

RingScope implements and evaluates three distinct streaming maintainer architectures:
1. **Mode A:** Full Recomputation (Naïve baseline)
2. **Mode B:** Warm-Started Recomputation (Monotone lower-bound pruning)
3. **Mode C:** Incremental Heuristic (Internal candidate tracking with multi-factor triggers)

All maintainers derive from `BaseStreamingMaintainer` in [ringscope/streaming_maintainer.py](file:///c:/VS%20code/DAA/ringscope/streaming_maintainer.py#L40-L380).

---

## 2. Mode A: Full Recomputation

`SOURCE-VERIFIED` [ringscope/streaming_maintainer.py](file:///c:/VS%20code/DAA/ringscope/streaming_maintainer.py#L85-L125)

### 2.1 Workflow
```
Incoming Edge Batch
        │
        ▼
Insert into Graph (TransactionGraph)
        │
        ▼
Run Solver unconditionally (Goldberg or Greedy Peeling)
        │
        ▼
Update Candidate Set S* and Density ρ*
```

### 2.2 Invariants and Characteristics
- **Batch Processing:** Inserts all batch transactions into the underlying `TransactionGraph`.
- **Recomputation Policy:** Unconditionally invokes `_compute_densest()` on **every single batch**, regardless of whether the batch added any new unique edges.
- **Optimality:** Yields the optimal global densest subgraph (exact if using Goldberg, 2-approx if using Peeling).
- **Complexity:** $O(B \cdot T_{\text{solver}})$, where $B$ is the number of batches.
- **Weakness:** Prohibitively expensive on high-throughput streams where many transactions are duplicates or isolated transfers.

---

## 3. Mode B: Warm-Started Recomputation

`SOURCE-VERIFIED` [ringscope/streaming_maintainer.py](file:///c:/VS%20code/DAA/ringscope/streaming_maintainer.py#L130-L210)

### 3.1 Workflow
```
Incoming Edge Batch
        │
        ▼
Insert into Graph & Count new unique edges
        │
        ├── If new_unique == 0 ──► Retain previous candidate (Latency: 0 ms)
        │
        ▼ (new_unique > 0)
Test Feasibility at current lower bound ρ_prev:
Is there any subgraph with density > ρ_prev?
(Run Goldberg decision test with g = ρ_prev)
        │
        ├── If NO ──► Candidate remains optimal! Retain S* (Saved flow iterations)
        │
        ▼ (If YES)
Run Goldberg binary search with pruned lower bound:
Interval = [ρ_prev, (n-1)/2]
        │
        ▼
Update S* and ρ*
```

### 3.2 Lower-Bound Pruning Mechanics
When the exact solver is Goldberg:
1. In an insertion-only stream, the global maximum density $\rho^*(G)$ is monotonically non-decreasing ($\rho_{t} \ge \rho_{t-1}$).
2. Therefore, any density value strictly below the previous optimal density $\rho_{t-1}$ is provably sub-optimal and does not need to be searched.
3. In `goldberg.py`, `lower_bound` is passed into `goldberg_densest_subgraph(..., lower_bound=self._current_density)`:
   - Setting $L \leftarrow \rho_{t-1}$ directly shrinks the initial binary search interval from $[0, \frac{n-1}{2}]$ to $[\rho_{t-1}, \frac{n-1}{2}]$.
   - This saves $\approx \log_2 \frac{1}{\rho_{t-1}}$ binary search iterations and their corresponding Dinic max-flow invocations.
4. **Feasibility Shortcut:** If the single decision check at $g = \rho_{t-1}$ confirms no denser subgraph exists, the entire binary search is bypassed.

---

## 4. Mode C: Incremental Heuristic Maintainer

`SOURCE-VERIFIED` [ringscope/streaming_maintainer.py](file:///c:/VS%20code/DAA/ringscope/streaming_maintainer.py#L215-L380)

### 4.1 Workflow and Candidate Tracking
Mode C avoids global recomputation by maintaining the current candidate cluster $S^*$ and updating its density locally in $O(1)$ time whenever new edges fall entirely within $S^*$.

```
Incoming Edge Batch
        │
        ▼
Pre-filter batch for unique new edges:
Split into:
  - E_internal: Both u, v ∈ S*
  - E_incident: Exactly one of u, v ∈ S*
  - E_external: Neither u nor v in S*
        │
        ▼
Update Internal Density in O(1):
|E(S*)| ← |E(S*)| + |E_internal|
ρ(S*)   ← |E(S*)| / |S*|
        │
        ▼
Evaluate Trigger Rules:
1. trigger_periodic: (batch_index % periodic_interval == 0)
2. trigger_external: (external_edge_count >= external_edge_threshold)
3. trigger_hub: (any incident node has deg(v) > max(3.0, 1.5 * ρ(S*)))
4. trigger_empty: (candidate S* is empty)
        │
        ├── Any trigger TRUE? ──► Execute Full Global Recompute & Reset counters
        │
        └── All triggers FALSE ──► Retain S* locally (Zero flow calls!)
```

### 4.2 Detailed Trigger Policies
1. **Periodic Refresh (`trigger_periodic`):**  
   - Default: Every 5 batches (`periodic_recompute_interval = 5`).
   - Guarantees that any slow-growing, disjoint dense cluster outside $S^*$ is eventually discovered.
2. **External Edge Activity (`trigger_external`):**  
   - Default threshold: 10 unique external edges (`external_edge_threshold = 10`).
   - Tracks unique edges formed entirely outside the current candidate: $\{u, v\} \cap S^* = \emptyset$.
   - Prevents an external cluster from accumulating substantial density without triggering a global solver run.
3. **High-Degree Incident Hub (`trigger_hub`):**  
   - Default ratio: $1.5 \times \rho(S^*)$ with a floor of $3.0$ (`hub_degree_ratio = 1.5`).
   - If an external vertex $v \notin S^*$ connects to many vertices in $S^*$ such that $\text{deg}(v) > 1.5 \rho(S^*)$, absorbing $v$ into $S^*$ would increase density. A recomputation is immediately triggered.
4. **Empty Candidate Trigger (`trigger_empty`):**  
   - Fires automatically if $S^*$ is empty or has zero density.

### 4.3 Phase 7 Bug Fix: Unique Edge Accounting
During the Phase 7 audit, a critical bug was identified and resolved:
- **Defect:** Mode C originally checked `if (u, v) not in graph.edges()` on the raw transaction stream. If a batch contained repeated transactions of the same new edge (e.g., `[(A, B), (A, B), (A, B)]`), the first transaction was inserted into the graph, causing subsequent transactions in the same batch to be evaluated as "already present," silently skewing the unique edge counter.
- **Fix:** `batch_unique_new_edges` pre-deduplicates edges within the batch and checks against the graph snapshot *prior* to batch insertion (`SOURCE-VERIFIED` in `ringscope/streaming_maintainer.py#L275-L290`).

---

## 5. Comparative Performance and Guarantees

| Characteristic | Mode A (Full) | Mode B (Warm-Start) | Mode C (Incremental) |
| :--- | :--- | :--- | :--- |
| **Global Exactness** | Guaranteed (with Goldberg) | Guaranteed (with Goldberg) | Heuristic (Exact only at refresh) |
| **Disjoint Cluster Discovery** | Immediate | Immediate | Delayed (until periodic/external trigger) |
| **Recomputations (Exp 6, 12 Batches)** | 12 / 12 (100%) | 12 / 12 (100%) | **4 / 12 (33.3%)** (`OUTPUT-VERIFIED`) |
| **Mean Latency (Exp 6)** | 2.473 ms | 2.125 ms | **1.327 ms (46.3% faster)** (`OUTPUT-VERIFIED`) |
| **End Density (Exp 6, Peeling)** | 1.3125 | 1.3125 | 1.3125 |
| **End Density (Exp 6, Goldberg)** | 1.4167 | 1.4167 | 1.4167 |
| **State Maintained** | None (Stateless) | Prior density $\rho_{t-1}$ | Candidate $S^*$, edge counters, degrees |
