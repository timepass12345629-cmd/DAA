# RingScope: Quantitative Analysis of Exact and Approximate Densest Subgraph Algorithms for Financial Transaction Ring Discovery

**Technical Research & Validation Report**  
*Project Phase: Phase 6 Final Validation & Research Documentation*  
*Date: October 2026*  

---

## Abstract

Coordinated financial crime—including circular money laundering schemes, bust-out fraud syndicates, and collusive merchant rings—frequently organizes transaction activity into dense subgraphs and closed directed cycles. While traditional rule-based transaction monitoring flags isolated anomalous events, it fundamentally struggles against distributed structural rings where individual transactions appear benign. In this research project, we present **RingScope**, a mathematically rigorous graph-algorithmic framework and interactive research platform designed to discover and evaluate dense transaction clusters and cyclic structures in both static and dynamic transaction networks.

RingScope implements and evaluates three distinct algorithmic paradigms:
1. **Goldberg's Exact Flow-Based Densest Subgraph Procedure** (Goldberg, 1984), reducing maximum-density subgraph discovery to a sequence of minimum $(s, t)$-cuts on a bipartite edge-node flow network solved via a scratch-built Dinic maximum-flow engine ($O(V^2 E)$).
2. **Charikar's Greedy Degree-Peeling Algorithm** (Charikar, 2000), achieving a provable $2$-approximation ($d \ge \text{OPT}/2$) in optimal $O((n + m) \log n)$ time using a lazy min-heap.
3. **The Greedy++ Iterative Peeling Framework** (Boob et al., WWW/KDD 2020), utilizing multi-pass load accumulation to yield a $(1 - \epsilon)$-approximation without constructing flow networks.

Furthermore, RingScope establishes a monotonically versioned streaming simulator evaluating three dynamic candidate maintenance strategies: **Full Recomputation (Mode A)**, **Warm-Started Recomputation (Mode B)**, and an **Incremental Heuristic with Non-Local External Activity Triggers (Mode C)**. Empirical evaluations across 7 reproducible benchmark suites against an exhaustive Brute-Force Oracle ($N \le 20$) demonstrate that Goldberg's reduction guarantees mathematical exactness across all tested topologies, while Greedy++ recovers the optimal density ($\text{ratio} = 1.000$) in all benchmark trials while executing in $0.23 - 3.22\text{ ms}$, compared to $4.88 - 186.26\text{ ms}$ for Goldberg.

---

## 1. Introduction & Motivation

Modern financial systems process hundreds of millions of inter-account transactions daily. Within this high-velocity traffic, financial criminals obscure audit trails through sophisticated topology manipulation:
- **Circular Layering (Smurfing / Loops)**: Funds cycle through shell entities ($A \to B \to C \to \dots \to A$) to fabricate legitimate commercial turnover or obscure the illicit origin of deposits.
- **Collusive Fraud Rings**: Rings of synthetic identities or collusive merchants execute dense webs of transactions between each other to artificially inflate credit ratings or extract transaction reward subsidies before defaulting simultaneously.

Standard relational databases and flat transaction monitoring systems evaluate transactions on a per-event basis using static thresholds (e.g., amount $> \$10,000$ or velocity $> 5 \text{ tx/hour}$). Consequently, organized fraud rings easily evade detection by splitting funds below thresholds and distributing transactions across dozens of accounts.

Graph algorithms offer an alternative by analyzing the **connectivity topology** of accounts (vertices $V$) and bilateral transaction relationships (edges $E$). Specifically, the **Densest Subgraph Problem (DSP)** seeks a subset of accounts $S \subseteq V$ that maximizes the ratio of internal transactions to participating accounts. Finding these dense components provides an objective, unsupervised filter for collusive clusters and fraudulent rings.

---

## 2. Problem Statement & Mathematical Formulation

Let $G = (V, E)$ be an undirected, unweighted simple graph representing a transaction network, where:
- $V$ is the set of accounts ($|V| = n$).
- $E \subseteq \binom{V}{2}$ is the set of unique bilateral transaction relationships ($|E| = m$).

### 2.1 Subgraph Density

For any nonempty subset of vertices $S \subseteq V$ ($S \ne \emptyset$), the induced subgraph $G[S] = (S, E(S))$ consists of vertex set $S$ and internal edge set:
$$E(S) = \{\{u, v\} \in E \mid u \in S \land v \in S\}$$

The **density** of $S$, denoted $\lambda(S)$, is defined as:
$$\lambda(S) = \frac{|E(S)|}{|S|}$$

The **maximum subgraph density** of graph $G$, denoted $\lambda^*(G)$, is:
$$\lambda^*(G) = \max_{S \subseteq V, S \ne \emptyset} \lambda(S) = \max_{S \subseteq V, S \ne \emptyset} \frac{|E(S)|}{|S|}$$

A subset $S^*$ achieving $\lambda(S^*) = \lambda^*(G)$ is an optimal densest subgraph.

### 2.2 Average Degree Identity

In any undirected graph, the sum of vertex degrees in an induced subgraph satisfies the Handshaking Lemma:
$$\sum_{v \in S} \text{deg}_{G[S]}(v) = 2 \cdot |E(S)|$$

Consequently, the average induced degree in $S$, denoted $\text{avg\_deg}(S)$, satisfies:
$$\text{avg\_deg}(S) = \frac{1}{|S|} \sum_{v \in S} \text{deg}_{G[S]}(v) = \frac{2 \cdot |E(S)|}{|S|} = 2 \cdot \lambda(S)$$

Thus, maximizing subgraph density $\lambda(S)$ is mathematically equivalent to maximizing the average degree of the induced subgraph.

### 2.3 Insertion Monotonicity

For any graph $G = (V, E)$ and newly inserted transaction edge $e = \{u, v\} \notin E$, the optimum density is monotonically non-decreasing:
$$\lambda^*(G \cup \{e\}) \ge \lambda^*(G)$$
*Proof*: Let $S^*$ be an optimal densest subgraph in $G$. Since $S^* \subseteq V(G \cup \{e\})$ remains a valid nonempty vertex subset in $G \cup \{e\}$, its density in $G \cup \{e\}$ satisfies:
$$\lambda_{G \cup \{e\}}(S^*) = \frac{|E_{G \cup \{e\}}(S^*)|}{|S^*|} \ge \frac{|E_G(S^*)|}{|S^*|} = \lambda^*(G)$$
Because $\lambda^*(G \cup \{e\}) = \max_{S} \lambda_{G \cup \{e\}}(S) \ge \lambda_{G \cup \{e\}}(S^*)$, monotonicity holds strictly.

---

## 3. Graph Data Model & Engineering Assumptions

RingScope structures financial transaction streams into an undirected simple graph model while preserving temporal and monetary metadata:

```mermaid
graph TD
    TX[Raw Transaction Ingestion] --> VAL[Input Validation & Sanitization]
    VAL --> AGG[Parallel Transaction Aggregator]
    AGG --> SL[Self-Loop Filter]
    SL --> TG[TransactionGraph Data Model]
    TG --> STATS[Graph Statistics & Degrees]
    TG --> SOLVERS[Exact & Approx Solvers]
    TG --> STREAM[Streaming Versioned Simulator]
```

### 3.1 Input Validation & Normalization
1. **Endpoint Validation**: Every transaction must supply valid source and target identifiers. Non-string, null, empty, or whitespace-only endpoints immediately raise structured `ValueError` exceptions.
2. **Direction Normalization**: While transactions have operational direction ($A \to B$), bilateral connectivity for collusive ring detection is modeled as undirected: $(u, v) \equiv (v, u)$. Edge keys are canonically stored as sorted tuples `(min(u, v), max(u, v))`.
3. **Parallel Edge Aggregation**: Multiple transactions between identical accounts do not duplicate physical edges. Instead, parallel transactions increment `tx_count` and accumulate financial metadata:
   $$\text{total\_volume}(u, v) = \sum_{i} \text{amount}_i, \quad \text{timestamps} = [t_1, t_2, \dots]$$
4. **Self-Loop Suppression**: Transactions where source equals destination ($u = u$) do not contribute to topological density ($\lambda = 0/1 = 0$) and are isolated into a `self_loops_skipped` audit log.
5. **Isolated Vertices**: Accounts with zero transactions are preserved as distinct singletons ($|S|=1, |E(S)|=0, \lambda=0.0$), maintaining correct connected-component metrics.

---

## 4. Exact Algorithm: Goldberg's Flow Reduction

Andrew V. Goldberg (1984) established that finding a maximum-density subgraph can be solved in polynomial time using a sequence of minimum $(s, t)$-cuts on an auxiliary flow network.

### 4.1 Bipartite Edge-Node Flow Construction

Given undirected graph $G = (V, E)$ with $n = |V|$ and $m = |E|$, and a queried density candidate threshold $g \ge 0$, Goldberg constructs a directed flow network $\mathcal{N}(g) = (V_{\mathcal{N}}, E_{\mathcal{N}}, c)$:

- **Network Vertices**:
  $$V_{\mathcal{N}} = \{s\} \cup \{t\} \cup \{v_e \mid e \in E\} \cup \{v \mid v \in V\}$$
  where $s$ is the source, $t$ is the sink, $v_e$ is an edge-node for each edge $e = \{u, v\} \in E$, and $v$ is a vertex-node for each account $v \in V$.
  Total vertices: $|V_{\mathcal{N}}| = m + n + 2$.

- **Capacities**:
  1. Source to Edge-Nodes: For every edge $e = \{u, v\} \in E$, add directed edge $(s, v_e)$ with capacity:
     $$c(s, v_e) = 1.0$$
  2. Edge-Nodes to Endpoint Vertex-Nodes: For every edge-node $v_e$ corresponding to $e = \{u, v\}$, add directed edges $(v_e, u)$ and $(v_e, v)$ with infinite capacity:
     $$c(v_e, u) = \text{INF}, \quad c(v_e, v) = \text{INF}$$
  3. Vertex-Nodes to Sink: For every vertex-node $v \in V$, add directed edge $(v, t)$ with capacity equal to candidate density $g$:
     $$c(v, t) = g$$

```
    [ s ] (Source)
      │
      ├──── cap = 1.0 ────> [ v_{e1} ] (Edge Node)
      │                       ├─── cap = INF ───> [ u ] (Vertex Node) ── cap = g ──> [ t ] (Sink)
      │                       └─── cap = INF ───> [ v ] (Vertex Node) ── cap = g ──> [ t ]
      └──── cap = 1.0 ────> [ v_{e2} ] ...
```

### 4.2 Cut Cost Theorem & Decision Correctness

Consider any finite-capacity $(s, t)$-cut $(S_{\mathcal{N}}, T_{\mathcal{N}})$ where $s \in S_{\mathcal{N}}$ and $t \in T_{\mathcal{N}}$. Let $S = S_{\mathcal{N}} \cap V$ denote the original graph vertices on the source side.

1. **Closure Property**: Because edges $(v_e, u)$ and $(v_e, v)$ carry capacity $\text{INF}$, any cut that cuts an $\text{INF}$ edge has capacity $\ge \text{INF}$. To achieve a finite cut cheaper than $\text{INF}$, whenever $v_e \in S_{\mathcal{N}}$, its endpoints $u, v$ must also reside in $S_{\mathcal{N}}$ ($u, v \in S$).
2. **Optimal Edge-Node Assignment**: For an edge $e = \{u, v\}$:
   - If both $u \in S$ and $v \in S$, assigning $v_e \in S_{\mathcal{N}}$ avoids cutting $(s, v_e)$, contributing $0$ to the cut.
   - If either $u \notin S$ or $v \notin S$, assigning $v_e \in S_{\mathcal{N}}$ would force cutting $(v_e, u)$ or $(v_e, v)$ of capacity $\text{INF}$. Hence, $v_e$ must be in $T_{\mathcal{N}}$, which cuts edge $(s, v_e)$ of capacity $1.0$.
3. **Finite Cut Cost Formula**:
   $$C(S) = \sum_{e \notin E(S)} c(s, v_e) + \sum_{v \in S} c(v, t) = (m - |E(S)|) + g \cdot |S|$$
4. **Decision Equivalence**:
   - For the trivial cut where $S = \emptyset$ (only $s \in S_{\mathcal{N}}$), no vertices are in $S$, all edges are cut from $s$: $C(\emptyset) = m$.
   - A cut strictly cheaper than $m$ exists if and only if there exists some non-empty $S \subseteq V$ such that:
     $$m - |E(S)| + g \cdot |S| < m \iff g \cdot |S| < |E(S)| \iff \frac{|E(S)|}{|S|} > g$$

Therefore, a minimum $(s, t)$-cut has capacity $< m$ if and only if the maximum subgraph density satisfies $\lambda^*(G) > g$.

### 4.3 Safe INF Capacity Selection

In floating-point implementations, using arbitrary values like $10^9$ can cause numerical instability or precision loss in Dinic flows. RingScope analytically derives a tight finite upper bound:
- Maximum possible cut cost for any valid subset $S$:
  $$C(S) \le m + g \cdot n$$
- In any simple graph, density $g \le (n - 1) / 2$. Therefore $g \cdot n \le n(n - 1)/2 = m \le \binom{n}{2} < n^2$.
- Hence, setting:
  $$\text{INF} = 2 \cdot m + n^2 + 10.0$$
  strictly exceeds any possible finite cut cost:
  $$\text{INF} > m + g \cdot n \ge \max_{S} C(S)$$
  guaranteeing that no INF edge is ever severed.

### 4.4 Dinic Maximum-Flow Implementation

To solve the minimum $(s, t)$-cut, RingScope implements Dinic's algorithm from scratch ([`ringscope/algorithms/dinic.py`](file:///c:/VS%20code/DAA/ringscope/algorithms/dinic.py)):
- **Forward & Reverse Residual Edges**: Every edge $(u, v)$ has a paired reverse edge $(v, u)$ with capacity $0$.
- **Breadth-First Search (BFS)**: Computes the level graph from source $s$, verifying if sink $t$ is reachable.
- **Depth-First Search (DFS) with Work Pointers**: Pushes blocking flow along admissible edges (`level[v] == level[u] + 1`). Per-vertex iterator pointers prevent redundant traversal of exhausted edges.
- **Source-Side Extraction**: After max-flow terminates, a BFS in the residual graph identifies all vertices reachable from $s$ via edges with remaining capacity $> 0$.

### 4.5 Binary Search Over Density

Because maximum density is bounded by $g \in [0, (n - 1) / 2]$, Goldberg performs binary search:
- Lower bound $L = 0.0$, Upper bound $U = (n - 1) / 2$.
- Iteration: Midpoint $g = (L + U) / 2$.
- Solve min-cut on $\mathcal{N}(g)$. If cut cost $< m - 10^{-11}$, a subgraph with density $> g$ exists $\implies L = g$. Otherwise, no such subgraph exists $\implies U = g$.
- Halts when $(U - L) \le \epsilon$ (default $\epsilon = 10^{-4}$).

---

## 5. Linear Approximation: Charikar's Greedy Peeling

While Goldberg provides exact solutions, flow networks require $O(V_{\mathcal{N}}^2 E_{\mathcal{N}}) \approx O((n + m)^3)$ time, becoming prohibitive on large networks. Moses Charikar (2000) introduced a linear-time greedy peeling algorithm.

### 5.1 Algorithm Description

1. Initialize $H_n = G = (V, E)$. Let $S_n = V$.
2. For $i = n, n-1, \dots, 2$:
   - Identify vertex $v^* \in V(H_i)$ with minimum degree in $H_i$:
     $$v^* = \arg\min_{v \in V(H_i)} \text{deg}_{H_i}(v)$$
   - Form $H_{i-1}$ by removing $v^*$ and its incident edges from $H_i$.
   - Record candidate subset $S_{i-1} = V(H_{i-1})$ and its density $\lambda(S_{i-1})$.
3. Return the subset $S^*$ that maximizes density across all recorded iterations:
   $$S^* = \arg\max_{S_i} \lambda(S_i)$$

### 5.2 Proof of 2-Approximation Guarantee

Let $S_{\text{opt}}$ be an optimal densest subgraph with maximum density $\lambda^* = |E(S_{\text{opt}})| / |S_{\text{opt}}|$.
By the average degree identity:
$$\text{avg\_deg}(S_{\text{opt}}) = 2 \cdot \lambda^*$$

Every vertex $u \in S_{\text{opt}}$ has induced degree in $S_{\text{opt}}$ that cannot all be strictly less than $\lambda^*$. In fact, by the optimality of $S_{\text{opt}}$, every vertex $u \in S_{\text{opt}}$ must satisfy:
$$\text{deg}_{S_{\text{opt}}}(u) \ge \lambda^*$$
*(If there existed $u \in S_{\text{opt}}$ with $\text{deg}_{S_{\text{opt}}}(u) < \lambda^*$, removing $u$ would produce $S' = S_{\text{opt}} \setminus \{u\}$ with $|E(S')| = |E(S_{\text{opt}})| - \text{deg}(u) > \lambda^* |S_{\text{opt}}| - \lambda^* = \lambda^*(|S_{\text{opt}}| - 1) = \lambda^* |S'|$, contradicting the maximality of $\lambda^*$).*

Now consider the first iteration $k$ in which Charikar's peeling removes any vertex $v \in S_{\text{opt}}$. At this step:
- All vertices of $S_{\text{opt}}$ are still present in $H_k \implies S_{\text{opt}} \subseteq V(H_k)$.
- For the peeled vertex $v$, its degree in $H_k$ satisfies:
  $$\text{deg}_{H_k}(v) \ge \text{deg}_{S_{\text{opt}}}(v) \ge \lambda^*$$
- Since $v$ was chosen as the vertex of minimum degree in $H_k$:
  $$\min_{u \in V(H_k)} \text{deg}_{H_k}(u) = \text{deg}_{H_k}(v) \ge \lambda^*$$
- The average degree of $H_k$ is at least its minimum degree:
  $$\text{avg\_deg}(H_k) \ge \min_{u \in V(H_k)} \text{deg}_{H_k}(u) \ge \lambda^*$$
- Rewriting in terms of density:
  $$\lambda(H_k) = \frac{\text{avg\_deg}(H_k)}{2} \ge \frac{\lambda^*}{2}$$

Because the algorithm inspects $H_k$ and selects the maximum density among all prefixes, the output subset $S^*$ satisfies:
$$\lambda(S^*) \ge \lambda(H_k) \ge \frac{\lambda^*}{2}$$
This guarantees a provable $2$-approximation ($50\%$ of optimum).

### 5.3 Implementation & Complexity

RingScope implements Charikar's peeling using a lazy min-heap ([`ringscope/algorithms/greedy_peeling.py`](file:///c:/VS%20code/DAA/ringscope/algorithms/greedy_peeling.py)):
- Vertices are inserted into a priority queue keyed by current induced degree.
- When degree drops due to neighbor removal, stale entries are lazily updated.
- Overall time complexity: $O((n + m) \log n)$.
- Space complexity: $O(n + m)$.

---

## 6. Greedy++: Multi-Pass Iterative Load Peeling

Published by Boob, Gao, Peng, Sawlani, Tsourakakis, Wang, and Wang (WWW 2020 / KDD 2020), **Greedy++** bridges the gap between Charikar's fast linear heuristic and Goldberg's exact flow computation.

### 6.1 Multiplicative Load Framework

Greedy++ recognizes that single-pass peeling often removes critical high-density vertices prematurely if they participate in external noise. To counteract this, Greedy++ runs $T$ peeling iterations while maintaining a cumulative load $\ell(v)$ for each vertex:

1. Initialize load $\ell(v) = 0$ for all $v \in V$.
2. For iteration $t = 1, 2, \dots, T$:
   - Execute a peeling pass on $G$, but select the minimum vertex guided by degree plus accumulated load:
     $$v^* = \arg\min_{v \in V(H)} \left( \text{deg}_H(v) + \ell(v) \right)$$
   - At the conclusion of pass $t$, update load for all vertices based on their degree in the pass:
     $$\ell(v) \leftarrow \ell(v) + \text{deg}_G(v)$$
3. Across all $T \times n$ subgraphs inspected, return the subset with the highest density $\lambda(S)$.

### 6.2 Theoretical Convergence

Boob et al. proved that for $T = O\left(\frac{\Delta \log n}{\lambda^* \epsilon^2}\right)$, Greedy++ achieves a provable $(1 - \epsilon)$-approximation to the exact densest subgraph:
$$\lambda(S^*) \ge (1 - \epsilon) \lambda^*$$
In practice, setting $T = 10$ iterations consistently achieves $> 98\%$ to $100\%$ of optimum density without constructing flow networks.

---

## 7. Streaming Simulator Architecture & Maintenance Modes

In live financial environments, transactions arrive as high-velocity streams. Recomputing exact maximum flow on every transaction edge insertion is computationally infeasible.

### 7.1 Monotonically Versioned Simulator

RingScope establishes a deterministic stream simulator ([`ringscope/stream_simulator.py`](file:///c:/VS%20code/DAA/ringscope/stream_simulator.py)) tracking:
- Monotonic graph version $V_t$.
- Transaction edge insertion count, unique edge delta, affected vertices.
- Processing latency percentiles ($p50, p95$) and total recomputation count.

### 7.2 Maintenance Modes Comparison

```
                  ┌────────────────────────────────────────┐
                  │        Incoming Transaction Batch      │
                  └───────────────────┬────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
      [ Mode A: Full ]        [ Mode B: Warm-Start ]  [ Mode C: Heuristic ]
      Solve from scratch      Reuse prior density     Track local bounds;
      O(n + m) peeling        as lower bound; skip    trigger full recompute
      every batch.            on parallel edges.      on external activity.
```

1. **Mode A (Full Recomputation)**: Runs solver from scratch on every incoming batch. Serves as exact ground truth baseline ($100\%$ recomputation rate).
2. **Mode B (Warm-Started Recomputation)**:
   - Reuses previous density $\lambda_{t-1}$ as the binary search lower bound ($L = \lambda_{t-1}$).
   - Bypasses recomputation entirely when incoming transactions consist solely of parallel edges between already connected vertices (topology unchanged).
3. **Mode C (Incremental Heuristic)**:
   - Tracks candidate cluster density locally. If an incoming edge falls entirely within the current candidate $S_t$, update density in $O(1)$ time:
     $$\lambda_{t+1}(S_t) = \frac{|E(S_t)| + 1}{|S_t|}$$
   - **Crucial Non-Local Trigger Guarantee**: RingScope does *not* make the false assumption that only edges touching the current candidate can change the optimum. Disjoint components can grow denser elsewhere in the graph. Mode C enforces explicit recomputations when:
     - Edge insertions occur outside $S_t$ exceeding `external_edge_threshold` ($k=10$).
     - External vertex degrees cross density threshold $\text{deg}(v) > 2 \lambda_{t-1}$.
     - Monotonic batch interval timer expires (`recompute_interval` $= 5$ batches).

---

## 8. Software Architecture & Implementation

RingScope is designed as a decoupled, asynchronous, research-grade full-stack platform:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          RingScope Architecture                        │
├───────────────────────────────────┬────────────────────────────────────┤
│           Backend (Python)        │         Frontend (React/Vite)      │
│  FastAPI + Pydantic v2 + NetworkX │ React 19 + TypeScript + Tailwind   │
│                                   │                                    │
│  [REST API: /api/v1]              │  [Interactive Research Views]      │
│  ├─ /health                       │  ├─ Overview (Live KPIs, Engine)   │
│  ├─ /graphs/generate & import     │  ├─ Graph Explorer (Cytoscape.js)  │
│  ├─ /analysis/run (Offloaded)     │  ├─ Algorithm Lab (Comparative)    │
│  ├─ /stream/start, step, inject   │  ├─ Streaming Simulator (Recharts) │
│  └─ /experiments/run & export     │  ├─ Empirical Experiments Runner   │
│                                   │  └─ Theoretical Documentation      │
│  [Worker Service Layer]           │                                    │
│  ├─ asyncio.to_thread Offloading  │  [Typed API Client: client.ts]     │
│  ├─ Thread-Safe Session Registry  │  ├─ Strict TypeScript Interfaces   │
│  └─ In-Memory / SQLite Storage    │  └─ Priority Sampling Safeguard    │
└───────────────────────────────────┴────────────────────────────────────┘
```

- **Asynchronous Loop Offloading**: Heavy combinatorial algorithms (Goldberg binary search, Dinic flows, Greedy++ passes) are offloaded from FastAPI's asyncio loop to worker threads using `asyncio.to_thread`, ensuring server responsiveness and zero HTTP request starvation.
- **Priority Sampling Safeguard**: Cytoscape.js force-directed layouts can degrade frame rate on graphs with $N > 300$ nodes. The frontend implements priority sampling: candidate cluster nodes and planted ground-truth nodes are unconditionally rendered, while peripheral nodes are sampled up to $N = 200$.

---

## 9. Experimental Methodology & Measured Results

All benchmark evaluations were executed on local hardware using the automated evaluation harness (`scripts/run_experiments.py`). Results were exported directly to CSV and JSON formats under `experiments_output/`.

### 9.1 Experiment 1: Runtime vs Graph Size Scaling

Evaluated scaling across graph orders $N \in \{10, 20, 40, 60\}$ with planted clusters ($p_{\text{in}} = 0.7, p_{\text{out}} = 0.1$):

| $N$ | $M$ | Charikar Peeling (ms) | Greedy++ ($T=10$) (ms) | Goldberg Flow (ms) | Peeling Density | Goldberg Density |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10** | 7 | 0.145 | 0.230 | 4.885 | 0.8571 | 0.8571 |
| **20** | 32 | 0.153 | 0.564 | 26.801 | 1.7647 | 1.7857 |
| **40** | 130 | 0.399 | 1.877 | 92.672 | 3.3243 | 3.3243 |
| **60** | 234 | 0.678 | 3.219 | 186.259 | 3.9153 | 3.9153 |

```mermaid
xychart-beta
    title "Algorithm Runtime Scaling (ms vs Number of Nodes N)"
    x-axis [N=10, N=20, N=40, N=60]
    y-axis "Runtime (ms)" 0 --> 200
    bar [0.145, 0.153, 0.399, 0.678]
    bar [0.230, 0.564, 1.877, 3.219]
    line [4.885, 26.801, 92.672, 186.259]
```
*(Blue bar: Charikar Peeling; Purple bar: Greedy++; Line: Goldberg Flow)*

**Finding**: Charikar peeling executes in $< 1 \text{ ms}$ across all sizes. Greedy++ ($T=10$) requires only $3.22\text{ ms}$ at $N=60$. In contrast, Goldberg flow scales polynomially to $186.26\text{ ms}$ at $N=60$ ($57\times$ slower than Greedy++), confirming the computational advantage of iterative peeling for rapid interactive screening.

---

### 9.2 Experiment 2: Cluster Size vs Recovery ($F_1$ & Jaccard)

Evaluated planted cluster recovery on $N = 30$ graphs as planted ring size $k$ varies from $4$ to $10$ ($p_{\text{in}} = 0.85, p_{\text{out}} = 0.05$):

| Cluster Size $k$ | Planted Nodes | Peeling $F_1$ | Peeling Jaccard | Greedy++ $F_1$ | Goldberg $F_1$ | Goldberg Jaccard | Measured Density |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **4** | 4 | 0.4000 | 0.2500 | 0.4000 | 0.4000 | 0.2500 | 1.5625 |
| **6** | 6 | 0.8000 | 0.6667 | 0.8000 | 0.8000 | 0.6667 | 2.3333 |
| **8** | 8 | 1.0000 | 1.0000 | 1.0000 | 0.9412 | 0.8889 | 3.0000 |
| **10** | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 3.7000 |

**Finding**: Small clusters ($k=4$) experience boundary bleed into adjacent background noise ($F_1 = 0.40$). At $k \ge 8$, cluster density ($\lambda \ge 3.0$) decisively separates from background noise ($\lambda_{\text{bg}} \approx 0.7$), achieving perfect ground-truth recovery ($F_1 = 1.000$, Jaccard $= 1.000$).

---

### 9.3 Experiment 3: Cluster Sparsity vs Boundary Recovery

Evaluated recovery on $N=30, k=6$ as internal cluster edge probability $p_{\text{in}}$ scales from $0.40$ (sparse) to $1.00$ (complete clique):

| $p_{\text{in}}$ | Internal Cluster Density | Background Density | Recovery $F_1$ | Recovery Jaccard | Detected Density |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **0.40** | 0.5000 | 0.4211 | 0.5882 | 0.4167 | 1.0909 |
| **0.60** | 1.1667 | 0.4211 | 0.7692 | 0.6250 | 1.4286 |
| **0.80** | 1.6667 | 0.4211 | 0.8571 | 0.7500 | 1.7500 |
| **1.00** | 2.5000 | 0.4211 | **1.0000** | **1.0000** | **2.5000** |

**Finding**: When internal density is close to background density ($p_{\text{in}} = 0.40$, density $0.50$ vs $0.42$), the densest subgraph absorbs surrounding noise nodes. When $p_{\text{in}} = 1.00$ (clique), the cluster exhibits sharp contrast and achieves exact $100\%$ recovery.

---

### 9.4 Experiment 4: Background Noise Tolerance

Evaluated cluster stability ($k=6, p_{\text{in}}=0.9$) as background noise $p_{\text{out}}$ scales from $0.02$ to $0.25$:

| $p_{\text{out}}$ | Total Edges | Planted Size | Detected Size | Precision | Recall | $F_1$ Score | Jaccard |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.02** | 20 | 6 | 6 | 1.0000 | 1.0000 | **1.0000** | 1.0000 |
| **0.08** | 29 | 6 | 6 | 1.0000 | 1.0000 | **1.0000** | 1.0000 |
| **0.15** | 45 | 6 | 8 | 0.7500 | 1.0000 | **0.8571** | 0.7500 |
| **0.25** | 69 | 6 | 21 | 0.2857 | 1.0000 | **0.4444** | 0.2857 |

**Finding**: High recall ($1.000$) is preserved across all noise levels: the true cluster is never lost. However, at $p_{\text{out}} = 0.25$, background connectivity becomes sufficiently dense that the optimal subgraph expands to include 21 nodes, lowering precision to $0.2857$.

---

### 9.5 Experiment 5: Exact vs Approximate Density (Brute-Force Oracle)

Validated against the exhaustive exponential Brute-Force Oracle ($2^n - 1$ subsets) across small instances:

| $N$ | $M$ | Exact OPT Density (Oracle) | Goldberg Density | Goldberg Gap | Greedy Peeling Ratio | Greedy++ Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **8** | 7 | **1.00000** | 1.00000 | **0.00000** | 1.00000 (100%) | 1.00000 (100%) |
| **12** | 21 | **1.75000** | 1.75000 | **0.00000** | 1.75000 (100%) | 1.75000 (100%) |
| **14** | 41 | **2.92857** | 2.92857 | **0.00000** | 2.92857 (100%) | 2.92857 (100%) |

**Finding**: Goldberg's max-flow reduction achieved a density gap of exactly $0.00000$ across all trials, verifying zero error against the mathematical oracle. Both Greedy Peeling and Greedy++ also discovered the exact optimal subset on these benchmark topologies.

---

### 9.6 Experiment 6: Streaming Maintenance Modes Comparison

Evaluated dynamic edge stream insertion across 12 synthetic batches (35 transactions total) comparing Modes A, B, and C under identical seed ($888$):

| Mode | Underlying Solver | Recomputations | Recomputation Rate | Final Density | Exact Ground Truth Density | Total Runtime | Mean Latency | p95 Latency | Recovery $F_1$ |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Mode A (Full Recompute)** | Greedy Peeling | 12 / 12 | 100.0% | 1.3333 | 1.4167 (Goldberg) | 2.47 ms | 0.206 ms | 0.281 ms | 0.261 |
| **Mode B (Warm-Started)** | Greedy Peeling | 12 / 12 | 100.0% | 1.3333 | 1.4167 (Goldberg) | 1.90 ms | 0.158 ms | 0.245 ms | 0.261 |
| **Mode C (Incremental Heuristic)** | Greedy Peeling | **4 / 12** | **33.3%** | 1.3125 | 1.4167 (Goldberg) | **1.33 ms** | **0.111 ms** | **0.252 ms** | 0.286 |

**Technical Audit Findings & Observations**:
1. **Explanation of the Reference Density Gap ($0.0833$)**:
   The candidate density ($1.3333$) differed from the exact reference density ($1.4167$) because the streaming maintainer was configured with Charikar's greedy peeling algorithm (a $2$-approximation), while the evaluation reference was calculated using Goldberg's exact max-flow reduction. The gap represents the natural approximation slack of greedy peeling on this graph topology, not candidate drift during streaming.
2. **Impact of Phase 7 Edge De-duplication**:
   In Phase 7, Mode C was corrected to track unique new edges rather than raw transaction counts, eliminating false triggers from repeat transactions between existing accounts. As a result, Mode C recomputations dropped from $11/12$ ($91.7\%$) to **$4/12$ ($33.3\%$)**, achieving a $46.2\%$ latency reduction ($1.33\text{ ms}$ vs $2.47\text{ ms}$) while maintaining candidate density within $1.5\%$ ($1.3125$ vs $1.3333$). Mode C is an empirical heuristic that provides excellent latency savings on typical streams, but does not guarantee global exactness at every intermediate step.

---

### 9.7 Experiment 7: Competing Dense Clusters & High-Degree Star Hubs

Evaluated graph containing two competing clusters and an artificial high-degree star hub:
- Cluster 1: Planted $K_5$ clique (theoretical density $= 10 / 5 = 2.00$).
- Cluster 2: $C_6$ ring with 2 internal chords (theoretical density $= 8 / 6 = 1.33$).
- Star Hub: Central hub node connected to 10 peripheral leaves (theoretical density $= 10 / 11 = 0.909$).

**Measured Results**:
- Goldberg: Density $= 2.0000$, Cluster 1 $F_1 = 1.0000$.
- Greedy Peeling: Density $= 2.0000$, Cluster 1 $F_1 = 1.0000$.
- Greedy++: Density $= 2.0000$, Cluster 1 $F_1 = 1.0000$.

**Finding**: High-degree hub nodes in financial networks (e.g., payroll disbursement or utility accounts with high degree but zero internal connectivity among payees) exhibit low density ($0.91$). All three algorithms correctly isolated the true fraudulent clique $K_5$ without being distracted by the star hub.

---

## 10. Limitations & Practical Constraints

1. **Floating-Point Binary Search vs Rational Stopping**:
   Goldberg's binary search halts when $(U - L) \le \epsilon$. While $\epsilon = 10^{-4}$ achieved exact answers across all test instances, absolute theoretical rational exactness requires stopping when $\epsilon < \frac{1}{n(n - 1)}$. On graphs with $n = 5000$, this requires $\epsilon < 4 \times 10^{-8}$ and $\approx 28$ binary search iterations.
2. **Streaming Non-Local Disjoint Components**:
   In incremental streaming (Mode C), if a disjoint clique forms entirely outside the candidate cluster without triggering external threshold bounds, candidate maintenance can temporarily lag behind the true global maximum until the periodic interval timer fires.
3. **Directed Cycle Length**:
   Densest subgraph finds dense clusters regardless of cycle orientation. For directed wash-trading cycles ($A \to B \to C \to A$), densest subgraph must be paired with Tarjan/Johnson cycle extraction (implemented in RingScope's cycle detection module).

---

## 11. Conclusion & Recommendations

RingScope demonstrates that combinatorial densest subgraph algorithms provide a rigorous, explainable foundation for transaction ring analysis:
- **For Real-Time Screening & Streaming**: Greedy++ with $T=10$ passes provides near-optimal density ($>99\%$) in $< 4\text{ ms}$, making it the recommended engine for high-velocity transaction streams.
- **For Regulatory Audits & Forensic Evidence**: Goldberg's flow reduction paired with Dinic's algorithm provides verifiable mathematical ground truth with zero heuristic approximation error.
- **For Production Architecture**: Decoupling the graph engine behind a non-blocking asynchronous REST API with client-side sampling safeguards enables interactive research exploration without server starvation.

---

## 12. References

1. **Goldberg, Andrew V.** (1984). *Finding a Maximum Density Subgraph*. Technical Report UCB/CSD-84-171, Computer Science Division, University of California, Berkeley.
2. **Charikar, Moses** (2000). *Greedy Approximation Algorithms for Finding Dense Components in a Graph*. International Workshop on Approximation Algorithms for Combinatorial Optimization (APPROX 2000), Lecture Notes in Computer Science, vol 1913, Springer, pp. 84–92.
3. **Boob, Digvijay; Gao, Yu; Peng, Richard; Sawlani, Saurabh; Tsourakakis, Charalampos; Wang, Di; Wang, Junxing** (2020). *Flowless: Extracting Densest Subgraphs Without Flow Computations*. In Proceedings of The Web Conference 2020 (WWW '20), ACM, pp. 573–583.
4. **Dinic, E. A.** (1970). *Algorithm for solution of a problem of maximal flow in a network with power estimation*. Soviet Mathematics Doklady, 11(5), pp. 1277–1280.
5. **Bhattacharya, Sayan; Henzinger, Monika; Nanongkai, Danupon; Tsourakakis, Charalampos** (2015). *Space- and Time-Efficient Algorithm for Maintaining Densest Subgraphs on Dynamic Graphs*. In Proceedings of the 47th Annual ACM Symposium on Theory of Computing (STOC '15), pp. 273–282.
6. **Epasto, Alessandro; Lattanzi, Silvio; Sozio, Mauro** (2015). *Efficient Densest Subgraph Computation in Dual-Memory Systems*. In Proceedings of the 21st ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (KDD '15), pp. 279–288.
7. **Kumar, Srijan; Spezzano, Francesca; Subrahmanian, V. S.; Faloutsos, Christos** (2018). *REV2: Fraudulent User Prediction in Rating Platforms*. In Proceedings of the Eleventh ACM International Conference on Web Search and Data Mining (WSDM '18), pp. 333–341.
8. **United States Patent and Trademark Office**. *US Patent No. 8,458,090: Detecting Fraudulent Mobile Money Transactions* (2013).
9. **Office of the Controller General of Patents, Designs and Trade Marks (India)**. *Guidelines for Examination of Computer Related Inventions (CRIs)*, CGPDTM, Government of India.
