# 08 — Research Claims, Prior Art, and Candidate Patent Contributions

**Project:** RingScope  
**Document:** Intellectual Property & Technical Contribution Analysis  
**Audience:** IP Counsel / Independent Research Reviewer  
**Verification Level:** `SOURCE-VERIFIED` / `DOCUMENTATION-ONLY`  

> [!IMPORTANT]
> This document records technical facts, implementation realities, and prior art distinctions. It does **not** assert legal patentability, patent novelty, or inventorship. In accordance with USPTO/EPO guidance, AI systems cannot be named as inventors; all inventorship inquiries remain subject to human legal review.

---

## 1. Categorization Taxonomy

To evaluate the technical contributions of the RingScope project objectively, all mechanisms are categorized into three distinct classes:
- **Category A: Established Prior Art:** Well-known, published academic algorithms and theoretical frameworks.
- **Category B: Standard Implementation Choices:** Common software engineering decisions that are competent but lack distinct novelty.
- **Category C: Candidate Technical Contributions:** Novel combinations, optimizations, or adaptive heuristics implemented in the codebase that may warrant prior art searching or patent consideration.

---

## 2. Category A: Established Prior Art

The core theoretical algorithms implemented in RingScope are established academic prior art:

1. **Dinic's Maximum Flow Algorithm:**
   - *Citation:* E. A. Dinic, "Algorithm for solution of a problem of maximum flow in a network with power estimation," *Soviet Math. Doklady*, 1970.
   - *Status:* Textbook prior art. RingScope's implementation in `dinic.py` is a clean from-scratch engineering implementation of BFS level graphs and DFS blocking flows.
2. **Goldberg's Exact Densest Subgraph Reduction:**
   - *Citation:* A. V. Goldberg, "Finding a maximum density subgraph," *Technical Report CSD-84-171*, UC Berkeley, 1984.
   - *Status:* Foundational prior art. The edge-node bipartite flow network, cut capacity $m - |E(S)| + g|S|$, and binary search framework are directly derived from Goldberg's paper.
3. **Charikar's Greedy Degree-Peeling Algorithm:**
   - *Citation:* M. Charikar, "Greedy approximation algorithms for finding dense subgraphs," *APPROX*, 2000.
   - *Status:* Foundational prior art. The iterative removal of the minimum-degree vertex achieving a 2-approximation is well-established.
4. **Greedy++ Multi-Pass Load Peeling:**
   - *Citation:* D. Boob, Y. Sawlani, C. Wang, "Greedy++: A Fast and Simple Approximation Algorithm for Densest Subgraph," *ICML*, 2020.
   - *Status:* Published prior art. The cumulative load update $\ell(v^*) \leftarrow \ell(v^*) + \text{deg}_H(v^*)$ and priority function $\text{deg}_H(v) + \ell(v)$ are published methods.
5. **Johnson's Elementary Cycle Detection:**
   - *Citation:* D. B. Johnson, "Finding all the elementary circuits of a directed graph," *SIAM Journal on Computing*, 1975.
   - *Status:* Textbook prior art.

---

## 3. Category B: Standard Implementation Choices

Engineering mechanisms implemented in RingScope that represent sound software engineering practice but are standard in the art:

1. **Simple Graph with Multi-Edge Metadata:**  
   Collapsing repeated transactions between accounts $u$ and $v$ into a single undirected edge while aggregating transaction count, volume, and timestamps in edge attributes. Standard technique in fraud surveillance.
2. **Priority Downsampling in Cytoscape.js:**  
   Limiting frontend rendering to 200 nodes by guaranteeing inclusion of candidate nodes while uniformly downsampling background nodes. Standard UI optimization for large graph visualization.
3. **Asynchronous Thread Pool Offloading:**  
   Dispatching CPU-intensive max-flow calculations via `asyncio.to_thread` to preserve FastAPI responsiveness. Standard asynchronous web architecture.

---

## 4. Category C: Candidate Technical Contributions

The following concrete mechanisms implemented in RingScope represent specific engineering innovations and adaptive heuristics that may warrant further prior-art search:

### Contribution 1: Adaptive Multi-Factor Triggered Streaming Candidate Maintenance (Mode C)
`SOURCE-VERIFIED` [ringscope/streaming_maintainer.py](file:///c:/VS%20code/DAA/ringscope/streaming_maintainer.py#L215-L380)

- **Technical Problem Addressed:** Full recomputation of densest subgraphs over streaming transaction batches incurs high latency, whereas purely localized tracking is blind to disjoint dense clusters emerging elsewhere in the network.
- **Specific Implementation in RingScope:**
  - Evaluates batch transactions into internal ($E \subseteq S^*$), incident ($E \cap S^* \neq \emptyset$), and external ($E \cap S^* = \emptyset$) sets.
  - Updates candidate density $\rho(S^*)$ locally in $O(1)$ time for internal edges without invoking flow algorithms.
  - Triggers a global recomputation if and only if one of four conditions is met:
    1. `trigger_periodic`: Periodic epoch boundary reached (default: every 5 batches).
    2. `trigger_external`: Unique external edge accumulation exceeds threshold (default: 10 edges).
    3. `trigger_hub`: An incident vertex exhibits degree $\text{deg}(v) > \max(3.0, 1.5 \cdot \rho(S^*))$.
    4. `trigger_empty`: Candidate set is empty.
- **Measured Empirical Evidence:** `OUTPUT-VERIFIED` In Experiment 6, Mode C reduced global recomputations from 12/12 down to 4/12 (66.7% reduction), reducing average latency by 46.3% while maintaining identical final candidate density on the evaluation stream.
- **Prior Art Comparison Needed:** Compare against dynamic densest subgraph algorithms by Bhattacharya et al. (STOC 2015), Henzinger et al., and Epasto et al. (KDD 2015).

### Contribution 2: Monotone Lower-Bound Pruning in Binary Search Goldberg Solver (Mode B)
`SOURCE-VERIFIED` [ringscope/streaming_maintainer.py](file:///c:/VS%20code/DAA/ringscope/streaming_maintainer.py#L130-L210), [ringscope/algorithms/goldberg.py](file:///c:/VS%20code/DAA/ringscope/algorithms/goldberg.py#L155-L180)

- **Technical Problem Addressed:** In an insertion-only transaction stream, maximum density is monotonically non-decreasing ($\rho_t \ge \rho_{t-1}$). Standard Goldberg solvers restart binary search from $[0, \frac{n-1}{2}]$ on every batch.
- **Specific Implementation in RingScope:**
  - Evaluates a single feasibility cut at $g = \rho_{t-1}$.
  - If no denser subgraph exists, the entire binary search is bypassed.
  - If a denser subgraph exists, the binary search interval is pruned to $[\rho_{t-1}, \frac{n-1}{2}]$, reducing the required number of Dinic max-flow invocations by $\log_2 \frac{1}{\rho_{t-1}}$.
- **Prior Art Comparison Needed:** Assess whether monotonic lower-bound initialization in flow-network binary search has been published in parametric max-flow literature (e.g., Gallo, Grigoriadis, Tarjan, 1989).

---

## 5. Unresolved Technical & IP Questions

1. **Worst-Case Delay of Disjoint Cluster Detection:**  
   What is the theoretical worst-case bound on the density gap between an un-triggered Mode C candidate and a newly emerging disjoint cluster before `trigger_external` or `trigger_periodic` fires?
2. **Dynamic Deletions / Aging Windows:**  
   RingScope currently assumes an **insertion-only** transaction stream. In real-world compliance, transactions expire outside a rolling window (e.g., 30-day window). How does lower-bound pruning adapt when density can decrease?
