# RingScope — Algorithm Correctness & Oracle Verification Report

**Audit Date**: October 2026  
**Auditor**: Independent Algorithm & Verification Engine  
**Project**: RingScope (Graph-Algorithms Platform for Transaction Ring Analysis)  

---

## 1. Algorithmic Overview & Invariants

RingScope implements three core densest subgraph paradigms and an incremental streaming framework. This report documents the mathematical foundations, independent oracle comparisons, implementation corrections, and theoretical limitations for each algorithm.

| Algorithm | Paradigm | Mathematical Guarantee | Verified Complexity |
| :--- | :--- | :--- | :--- |
| **Goldberg Flow Binary Search** | Exact Flow-Cut Reduction | Exact optimal density $\lambda^*$ | $O(\text{Dinic}(V', E') \cdot \log(m/\epsilon))$ |
| **Dinic Maximum Flow** | Blocking Flow via BFS/DFS | Exact maximum $(s, t)$-flow | $O(V^2 E)$ general, $O(E \sqrt{V})$ unit networks |
| **Charikar Greedy Peeling** | Iterative Minimum-Degree Peeling | Provable $2$-approximation ($\lambda \ge \lambda^*/2$) | $O((n + m) \log n)$ with lazy min-heap |
| **Greedy++ (Boob et al.)** | Multi-Pass Load Peeling | $(1 - \epsilon)$ when $T = \Omega\left(\frac{\Delta}{\lambda^*} \frac{\log n}{\epsilon^2}\right)$ | $O(T \cdot (n + m) \log n)$ |
| **Mode B (Warm-Started)** | Monotone Search Pruning | Identical to base solver | $O(\text{Dinic} \cdot \log((m - \lambda_{t-1})/\epsilon))$ |
| **Mode C (Incremental Heuristic)** | Bounded Non-Local Drift Tracking | Empirical heuristic | $O(1)$ per internal edge + periodic recomputes |

---

## 2. Goldberg Densest Subgraph Formulation & Audited Corrections

### 2.1 Reduction Formulation
Given an undirected simple graph $G = (V, E)$ with $n = |V|$ and $m = |E|$, Goldberg constructs a bipartite directed flow network $N = (V_N, E_N)$:
- Terminals: Source $s$, Sink $t$.
- For each edge $e = \{u, v\} \in E$, an edge-node $e$:
  - Directed edge $(s, e)$ with capacity $c(s, e) = 1.0$.
  - Directed edges $(e, u)$ and $(e, v)$ with capacity $c(e, u) = c(e, v) = \text{INF}$.
- For each vertex $v \in V$:
  - Directed edge $(v, t)$ with capacity $c(v, t) = g$ (the density threshold).

### 2.2 Cut Cost Theorem
For any subset of vertices $S \subseteq V$:
- If no INF edge is cut, every edge $e = \{u, v\}$ with both endpoints in $S$ must have $e$ on the source side.
- Edges cut from $s$ to edge-nodes: $m - |E(S)|$.
- Edges cut from vertex-nodes to sink: $g \cdot |S|$.
- Finite cut cost: $C(S) = m - |E(S)| + g \cdot |S|$.
- The trivial cut ($S = \emptyset$) has capacity $m$.
- A cut strictly cheaper than $m$ exists if and only if:
  $$m - |E(S)| + g \cdot |S| < m \iff \frac{|E(S)|}{|S|} > g$$

### 2.3 Tight Analytical INF Bound
The maximum feasible finite cut cost satisfies $C(S) \le m + g \cdot n$. Since $g \le (n-1)/2 \le m$, setting:
$$\text{INF} = 2m + n^2 + 10$$
guarantees that cutting even a single INF edge strictly exceeds any feasible cut, preserving the closure condition without using arbitrary large floats that could cause numerical cancellation in Dinic.

### 2.4 Audited Correctness Fixes
1. **Network Key Disjointness**: Replaced literal string sentinels with typed tuple keys (`s = ("__src__",)`, `t = ("__snk__",)`, `e_node = ("__e__", idx)`, `v_node = ("__v__", v)`). This eliminates key collisions with user accounts named `"__source__"`, `"__sink__"`, etc.
2. **Tie-Breaking Compactness**: In `goldberg_densest_subgraph()`, if a tested threshold returns a candidate with density equal to the best density seen so far, the candidate is updated if it contains fewer nodes (`len(dec.candidate_nodes) < len(best_nodes)`). This prevents isolated singletons or non-dense peripherals from being retained when a compact dense core exists.
3. **Valid Lower-Bound Warm-Starting**: Added parameter `lower_bound: Optional[float] = None`, initializing `lo = max(0.0, float(lower_bound))`. By density monotonicity ($\lambda^*(G \cup \{e\}) \ge \lambda^*(G)$), any previous candidate density is a valid lower bound.
4. **Exactness Flag Validity**: `is_mathematically_exact` is now set to `True` only when `(hi - lo) <= tolerance` and `tolerance <= 1.0 / (n * (n - 1))`. If binary search was halted early by `max_iter` or tolerance is too coarse, it correctly reports `False`.

---

## 3. Dinic Max-Flow Correctness & Reachability

Dinic's algorithm was verified on reference flow networks (CLRS networks, unit networks, random networks):
1. **BFS Level Graph**: Correctly clears level array to $-1$, sets $\text{level}[s] = 0$, and traverses residual edges with residual capacity $> 10^{-11}$.
2. **DFS Blocking Flow**: Utilizes per-vertex edge work pointers (`work[u]`), preventing repeated exploration of saturated edges and achieving $O(V^2 E)$ worst-case time complexity.
3. **Reverse Residual Edges**: Properly pairs forward edge index with backward edge `rev` pointer.
4. **Source-Side Cut Extraction**: Uses BFS on residual network from $s$. Original vertices reachable via residual capacity $> 10^{-11}$ form the source-side cut $S$.

---

## 4. Greedy++ Peeling vs Published Boob et al. Specification

### 4.1 Theoretical Guarantee vs Fixed Pass Heuristic
Boob et al. (WWW 2020) proved:
$$\text{For any } \epsilon \in (0, 1), \text{ Greedy++ achieves a } (1 - \epsilon)\text{-approximation in } T = O\left(\frac{\Delta}{\lambda^*} \cdot \frac{\log n}{\epsilon^2}\right) \text{ iterations.}$$
- **Audit Clarification**: A fixed pass count (such as $T = 10$) is an **empirical heuristic**. In practice, it converges rapidly and recovers OPT on all tested benchmarks, but does NOT theoretically guarantee $(1 - \epsilon)$ on arbitrary graphs unless $T$ scales with graph parameters.
- **Code & Documentation Attribution**: Updated docstrings in `greedy_plus_plus.py` and research reports to explicitly reflect this distinction.

### 4.2 Behavior at $T = 1$
At $T = 1$, the accumulated load vector $\ell(v) = 0$ for all $v$. The selection metric $\text{deg}_H(v) + \ell(v)$ reduces strictly to $\text{deg}_H(v)$, which is identical to Charikar's greedy peeling. Added regression test `test_greedy_plus_plus_iterations_1_matches_charikar()` to verify that $T=1$ candidate density, node set, and edge count are identical to Charikar.

---

## 5. Streaming Maintenance Modes (A, B, and C)

### 5.1 Mode A (Full Recomputation)
Unconditionally executes solver from scratch on each batch. Guarantees zero candidate drift at $O(B \cdot T_{\text{algo}})$ total cost.

### 5.2 Mode B (Warm-Started Recomputation)
1. Checks for parallel transactions (`new_unique == 0`). If no new unique edges were added, topology is identical and recomputation is bypassed.
2. If internal edges were added, updates density of current candidate.
3. Solves Goldberg threshold decision at prior density: does any subset achieve density $> \lambda_{t-1}$?
   - If False: proven that prior candidate remains optimal.
   - If True: invokes `goldberg_densest_subgraph(..., lower_bound=prior_density)`, reducing search interval by up to $50\%$.

### 5.3 Mode C (Incremental Heuristic)
1. Maintains current candidate $S_{\text{cand}}$ and updates internal density in $O(1)$.
2. Pre-filters transactions to track only genuine *new unique* external edges, eliminating spurious triggers from repeated transactions on existing edges.
3. Hub trigger requires degree to exceed `max(3.0, alpha * density)`, preventing spurious triggers in sparse graphs.
4. Documented explicitly as an empirical heuristic without global optimality guarantees.

---

## 6. Brute-Force Oracle Comparison Evidence

To establish empirical ground truth, an independent exponential Brute-Force Oracle (`brute_force_densest_subgraph`) was executed across all $2^n - 1$ nonempty vertex subsets on small graphs ($n \le 16$):

| Graph Topology | $N$ | $M$ | Oracle OPT Density | Goldberg Density | Goldberg Error | Greedy Peeling | Greedy++ ($T=10$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Path Graph $P_5$** | 5 | 4 | 0.80000 | 0.80000 | 0.00000 | 0.80000 | 0.80000 |
| **Star Graph $S_6$** | 6 | 5 | 0.83333 | 0.83333 | 0.00000 | 0.83333 | 0.83333 |
| **Triangle $K_3$** | 3 | 3 | 1.00000 | 1.00000 | 0.00000 | 1.00000 | 1.00000 |
| **Complete $K_4$** | 4 | 6 | 1.50000 | 1.50000 | 0.00000 | 1.50000 | 1.50000 |
| **Complete $K_5$** | 5 | 10 | 2.00000 | 2.00000 | 0.00000 | 2.00000 | 2.00000 |
| **Random GNP $(8, 0.35)$** | 8 | 7 | 1.00000 | 1.00000 | 0.00000 | 1.00000 | 1.00000 |
| **Random GNP $(12, 0.35)$** | 12 | 21 | 1.75000 | 1.75000 | 0.00000 | 1.75000 | 1.75000 |
| **Random GNP $(14, 0.35)$** | 14 | 41 | 2.92857 | 2.92857 | 0.00000 | 2.92857 | 2.92857 |
| **Disconnected Components** | 10 | 6 | 1.00000 | 1.00000 | 0.00000 | 1.00000 | 1.00000 |

**Conclusion**: Across all tested topologies, Goldberg max-flow achieved zero error ($0.00000$ density gap) against the exhaustive brute-force oracle.
