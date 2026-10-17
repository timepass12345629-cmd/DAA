# 03 — Algorithm Implementations and Technical Evidence

**Project:** RingScope  
**Document:** Deep-Dive into Algorithmic Mechanics, Formulations, Complexity, and Edge Cases  
**Verification Level:** `SOURCE-VERIFIED` / `TEST-VERIFIED`  

---

## 1. Dinic Maximum-Flow Algorithm

`SOURCE-VERIFIED` [ringscope/algorithms/dinic.py](file:///c:/VS%20code/DAA/ringscope/algorithms/dinic.py#L25-L165)

### 1.1 Implementation Architecture
Dinic's algorithm is implemented from scratch without third-party max-flow library calls.
- **Graph Representation:** Adjacency lists storing forward and backward residual edges. Edge records maintain `to`, `capacity`, `flow`, and `rev` (the index of the reverse edge).
- **Node Identifier Support:** Supports arbitrary hashable node IDs (strings, ints, and compound tuples such as `("__src__",)` or `("__e__", 0)`).
- **Level Graph (BFS):** `_bfs()` computes shortest path distances from source $s$ to all reachable vertices. Recomputes on each iteration; terminates when the sink $t$ is unreachable.
- **Blocking Flow (DFS):** `_dfs()` pushes flow along admissible edges where $\text{dist}[v] = \text{dist}[u] + 1$.
  - Uses a **work pointer array** (`work[u]`) to remember the current outgoing edge index at vertex $u$, preventing $O(V)$ re-scanning of saturated or dead-end paths within the same phase.
- **Source-Side Minimum Cut:** `min_cut_source_set()` runs a final BFS traversal on the residual network from source $s$. Any vertex reachable with positive residual capacity is placed in the source-side cut $S$.

### 1.2 Complexity & Guarantees
- **Theoretical Complexity:** $O(V^2 E)$ on general networks; $O(E \sqrt{V})$ on unit networks.
- **Empirical Runtime:** Typically sub-millisecond on graphs with $V \le 200, E \le 1000$.
- **Test Evidence:** `TEST-VERIFIED` [tests/test_dinic.py](file:///c:/VS%20code/DAA/tests/test_dinic.py) tests max-flow on classic textbook networks, disconnected networks, single edges, and multi-path graphs.

---

## 2. Goldberg Exact Densest Subgraph Solver

`SOURCE-VERIFIED` [ringscope/algorithms/goldberg.py](file:///c:/VS%20code/DAA/ringscope/algorithms/goldberg.py#L30-L245)

### 2.1 Problem Formulation & Reduction
Given an undirected graph $G = (V, E)$ with $n = |V|$ and $m = |E|$, the density of $S \subseteq V$ is $\rho(S) = \frac{|E(S)|}{|S|}$. Goldberg's method reduces the question *"Does there exist a subset $S \subseteq V$ with $\rho(S) > g$?"* to an $s$-$t$ minimum cut problem on a bipartite flow network $N(g)$.

#### Bipartite Flow Network Construction
- **Source $s$:** Node `("__src__",)`
- **Sink $t$:** Node `("__snk__",)`
- **Edge Nodes:** One node `("__e__", idx)` for each undirected edge $e = \{u, v\} \in E$.
  - Add directed edge $s \to ("__e__", idx)$ with capacity $c = 1$.
  - Add directed edges from `("__e__", idx)` to `("__v__", u)` and `("__v__", v)` with capacity $c = \infty$ (implemented as $c = 2m + n^2 + 10$).
- **Vertex Nodes:** One node `("__v__", u)` for each vertex $u \in V$.
  - Add directed edge `("__v__", u)` to $t$ with capacity $c = g$.

#### Cut Cost Analysis
For any finite-capacity cut separating $s$ and $t$, if an edge node `("__e__", idx)` is on the source side $S_{\text{cut}}$, both its endpoint vertex nodes must also be in $S_{\text{cut}}$ (otherwise an $\infty$-capacity edge would be severed).  
The capacity of the cut is:
$$C(S_{\text{cut}}) = (m - |E(S)|) + g |S|$$
where $S = S_{\text{cut}} \cap V$.  
Subtracting $m$ yields:
$$C(S_{\text{cut}}) < m \iff g |S| - |E(S)| < 0 \iff \frac{|E(S)|}{|S|} > g$$
Thus, a cut strictly cheaper than $m$ exists if and only if there is a subset $S$ with density strictly greater than $g$.

### 2.2 Binary Search & Stopping Conditions
- **Search Interval:** Initial bounds $[L, U] = [0, \frac{n-1}{2}]$ (or $[ \text{lower\_bound}, \frac{n-1}{2} ]$ when warm-started).
- **Threshold Decision:** On iteration with guess $g$, the network $N(g)$ is constructed. If Dinic returns $\text{max\_flow} < m - 10^{-9}$, a denser subgraph exists, so candidate $S$ is extracted from the source cut, density is updated, and $L \leftarrow g$. Otherwise, $U \leftarrow g$.
- **Stopping Rule:** Binary search terminates when $U - L \le \epsilon$.
- **Exactness Criterion:** In an undirected graph with $n$ vertices, the difference between any two distinct subgraph densities is at least:
  $$\Delta \rho \ge \frac{1}{n(n-1)}$$
  Therefore, if binary search is executed with tolerance $\epsilon \le \frac{1}{n(n-1)}$, the candidate extracted at $g = L$ is guaranteed to be mathematically exact.
  - In `goldberg.py`, `is_exact` is explicitly returned as `True` if and only if $\text{interval} \le \epsilon$ and $\epsilon \le \frac{1}{n(n-1)}$.
  - If a coarse $\epsilon$ (e.g. $0.05$) is used for speed, `is_exact` is returned as `False`.

### 2.3 Edge Cases & Empirical Evidence
- **Empty / Edge-less Graphs:** Returns density $0.0$ and empty vertex set.
- **Disconnected Graphs:** Correctly extracts the single densest component.
- **Brute-Force Oracle Testing:** `TEST-VERIFIED` [tests/test_goldberg_exactness.py](file:///c:/VS%20code/DAA/tests/test_goldberg_exactness.py) runs exponential $2^N$ exhaustive search on random graphs with $N \in [4, 14]$. Goldberg's solver achieved 100% agreement with the oracle across all seeds.

---

## 3. Charikar Greedy Degree-Peeling Algorithm

`SOURCE-VERIFIED` [ringscope/algorithms/greedy_peeling.py](file:///c:/VS%20code/DAA/ringscope/algorithms/greedy_peeling.py#L20-L95)

### 3.1 Mechanics
Charikar's peeling algorithm iteratively removes the vertex of minimum degree in the current induced subgraph:
1. Initialize active vertex set $H \leftarrow V$, with degree table $d[v] = \text{deg}_H(v)$.
2. Insert all vertices into a min-priority heap indexed by current degree.
3. In each step $i \in [1, n]$:
   - Compute current density $\rho(H) = \frac{|E(H)|}{|H|}$. If $\rho(H) > \rho_{\max}$, update best candidate $S^* \leftarrow H$.
   - Pop the minimum-degree vertex $v^*$ using lazy heap updates.
   - For all neighbors $u \in \text{Adj}(v^*) \cap H$: decrement $d[u] \leftarrow d[u] - 1$, push updated $(d[u], u)$ to heap, and decrement active edge count $|E(H)| \leftarrow |E(H)| - 1$.
   - Remove $v^*$ from $H$.
4. Return $S^*$ and $\rho(S^*)$.

### 3.2 Complexity & Approximation Guarantee
- **Theoretical Guarantee:** Proved 2-approximation: $\rho(S^*) \ge \frac{1}{2} \rho(S_{\text{opt}})$.
- **Time Complexity:** $O((m + n) \log n)$ using binary heap; $O(m + n)$ using bucket sort. RingScope implements heap-based peeling with lazy updates.
- **Runtime:** Sub-millisecond on all tested graphs up to $N = 1000$.

---

## 4. Multi-Pass Greedy++ Load-Peeling Algorithm

`SOURCE-VERIFIED` [ringscope/algorithms/greedy_plus_plus.py](file:///c:/VS%20code/DAA/ringscope/algorithms/greedy_plus_plus.py#L30-L140)

### 4.1 Mechanics and Source Realities
Greedy++ (Boob, Sawlani, Wang, 2020) runs $T$ passes of peeling. Rather than peeling by instantaneous degree alone, it maintains a cumulative vertex load $\ell(v)$:
1. Initialize loads $\ell(v) = 0$ for all $v \in V$.
2. For iteration $t = 1, \dots, T$:
   - Initialize induced graph $H \leftarrow V$.
   - In each peeling step, select vertex $v^*$ minimizing:
     $$\text{priority}(v) = \text{deg}_H(v) + \ell(v)$$
   - Update load of peeled vertex:
     $$\ell(v^*) \leftarrow \ell(v^*) + \text{deg}_H(v^*)$$
   - Remove $v^*$ from $H$ and decrement neighbor degrees in $H$.
   - Record density $\rho(H)$ and update global best candidate.
3. Return highest-density subgraph observed across all $T$ iterations.

### 4.2 Critical Honest Findings on Greedy++
1. **$T=1$ Equivalence:** When $T=1$, $\ell(v) \equiv 0$, so $\text{priority}(v) \equiv \text{deg}_H(v)$. The algorithm is mathematically and empirically identical to Charikar peeling (`TEST-VERIFIED` in `tests/test_greedy_plus_plus.py`).
2. **Asymptotic vs. Fixed Iterations:**  
   The published theorem proves that Greedy++ achieves a $(1-\epsilon)$ approximation when the number of iterations satisfies:
   $$T = \Omega\left(\frac{\Delta}{\lambda^*} \frac{\log n}{\epsilon^2}\right)$$
   where $\Delta$ is maximum degree and $\lambda^*$ is optimal density.  
   The RingScope source code sets a default parameter of $T = 10$. With fixed $T=10$, Greedy++ provides an empirical refinement over Charikar peeling that approaches exactness on many benchmark topologies, but **does not** provide an unconditional $(1-\epsilon)$ guarantee for arbitrary $\epsilon$.

---

## 5. Directed Cycle / Ring Detection

`SOURCE-VERIFIED` [ringscope/algorithms/cycle_detection.py](file:///c:/VS%20code/DAA/ringscope/algorithms/cycle_detection.py#L25-L115)

### 5.1 Mechanics
Detects circular wash-trading loops ($u_1 \to u_2 \to \dots \to u_k \to u_1$) in directed transaction graphs:
1. Operates on `TransactionGraph(is_directed=True)`.
2. Uses Johnson's elementary cycle algorithm via `networkx.simple_cycles`.
3. Applies domain-specific fraud filtering:
   - `min_length` (default 3) and `max_length` (default 8) to exclude trivial 2-node reciprocal swaps or intractable long chains.
   - `min_bottleneck_amount`: Filters for rings where the minimum transaction amount along the cycle exceeds a fraud threshold.
   - `max_cycles`: Limits cycle enumeration (default 1000) to prevent combinatorial explosion in dense topologies.
