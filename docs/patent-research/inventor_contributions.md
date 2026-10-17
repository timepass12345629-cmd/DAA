# Patent Research: Inventor Contributions & Development Chronology

**Internal Engineering & Legal Attribution Log**  
*Project: RingScope (Graph-Algorithms Research Platform for Transaction Ring Analysis)*  
*Date: October 2026*  

---

> [!NOTE]
> This document records the technical contributions, implementation chronology, and role demarcations between historical academic originators and the project engineering team. It serves to document inventorship provenance for any future patent or academic publications.

---

## 1. Technical Role & Attribution Summary

### 1.1 Academic & Theoretical Foundations (Public Domain Prior Art)
The mathematical algorithms implemented in RingScope were originally developed and published by the following researchers:
- **E. A. Dinic (1970)**: Conceived the blocking-flow and level-graph maximum flow algorithm ($O(V^2 E)$).
- **Andrew V. Goldberg (1984)**: Formulated the bipartite edge-node flow network reduction and minimum-cut decision procedure for exact maximum-density subgraphs.
- **Moses Charikar (2000)**: Formulated the minimum-degree peeling greedy algorithm and established the theoretical $2$-approximation proof.
- **Digvijay Boob, Yu Gao, Richard Peng, Saurabh Sawlani, Charalampos Tsourakakis, Di Wang, Junxing Wang (WWW 2020)**: Formulated the Greedy++ iterative load-accumulating multi-pass peeling framework and established the $(1 - \epsilon)$-approximation guarantee.

### 1.2 Human-Contribution & Inventorship Governance Policy
> [!IMPORTANT]
> **Legal Compliance on Inventorship (The Patents Act, 1970 & International Standards)**:
> Under the Indian Patents Act, 1970, US patent jurisprudence, and EPO guidelines, an artificial intelligence software system or automated coding agent **cannot** be listed as an inventor. Inventorship is restricted exclusively to natural human persons who made an inventive contribution to the **conception** of the technical solution. Automated implementation tools and execution assistants do not qualify as inventors.

### 1.3 Human-Contribution Review Checklist
Prior to formal patent consideration, the project entity must complete this review checklist to identify natural person inventors:

- [ ] **Criterion 1: Conception of Technical Problem & Solution**
  - Identify the specific human researcher(s) who formulated the research problem: streaming maintenance of graph structural density with non-local external activity triggers.
  - *Status*: Requires review and name identification by project leadership. (No artificial names invented).
- [ ] **Criterion 2: System Architecture & Novel Trigger Design**
  - Identify the human contributor(s) who conceived the specific threshold parameters ($\Theta_{\text{ext}}$, hub degree ratio $\alpha$, periodic intervals $K$) for governing non-local cluster drift.
  - *Status*: Pending project sponsor / author attestation.
- [ ] **Criterion 3: Exclusion of Prior Art Originators**
  - Confirm that academic originators (Goldberg, Charikar, Dinic, Boob et al.) are credited strictly as public domain prior art citations and NOT claimed as inventors of the platform integration.
  - *Status*: Verified and documented in prior art log.
- [ ] **Criterion 4: Exclusion of AI Tools as Inventors**
  - Confirm that DeepMind Antigravity IDE / LLM coding tools are recorded as software development instrumentation, not inventors.
  - *Status*: Compliant.
- [ ] **Criterion 5: Registered Indian Patent Agent Review**
  - Submit technical disclosure to a qualified Indian Patent Agent for statutory Section 3(k) analysis (tangible technical effect beyond software *per se*).
  - *Status*: Pending formal legal engagement.

---

## 2. Chronological Phase-by-Phase Technical Contributions

### Phase 1: Graph Model & Foundation Engineering
- **Engineering Deliverables**:
  - `ringscope/graph.py`: Designed `TransactionGraph` data model on an undirected simple graph representation.
  - Handled parallel transactions by aggregating edge counters and metadata without duplicating edges.
  - Designed self-loop suppression (`self_loops_skipped`) and preserved isolated singletons for accurate connected-component tracking.
  - `ringscope/data.py`: Developed reproducible synthetic planted cluster generator (`generate_planted_cluster_graph`).
  - `ringscope/importer.py`: Developed CSV edge-list ingestion with header auto-detection and row-level validation.
  - `ringscope/algorithms/brute_force.py`: Built exhaustive $2^n - 1$ subset verification oracle ($n \le 20$).
- **Test Evidence**: Unit tests validating graph statistics, isolated nodes, parallel edges, and oracle density.

---

### Phase 2: Flow Networks & Densest Subgraph Algorithms
- **Engineering Deliverables**:
  - `ringscope/algorithms/dinic.py`: Implemented Dinic's maximum flow algorithm from scratch (residual graph forward/backward edges, BFS level graph, DFS blocking flows with per-vertex work pointers, source-side cut reachability).
  - `ringscope/algorithms/goldberg.py`: Built Goldberg's bipartite edge-node flow network reduction, analytical tight finite bound $\text{INF} = 2m + n^2 + 10$, and binary search over density. Corrected in Phase 7 with tuple sentinels to eliminate vertex identifier collision risks.
  - `ringscope/algorithms/greedy_peeling.py`: Built Charikar's greedy peeling using a lazy min-heap with full `PeelingStep` history recording.
  - `ringscope/algorithms/greedy_plus_plus.py`: Built the Greedy++ multi-pass load peeling algorithm with clarified iteration requirements for theoretical approximation.
- **Test Evidence**: Unit tests validating max-flow on CLRS reference networks, cut costs, decision thresholds, and oracle comparisons across path, star, complete, triangle, and randomized graphs.

---

### Phase 3: Streaming Simulator & Reproducible Evaluation Harness
- **Engineering Deliverables**:
  - `ringscope/stream_simulator.py`: Built deterministic transaction streaming simulator supporting configurable batch sizes, arrival orders, and planted ring/clique injection.
  - Implemented three maintenance strategies:
    - **Mode A (Full Recomputation)**: Solves from scratch on every batch.
    - **Mode B (Warm-Started)**: Reuses prior density $\lambda_{t-1}$ as a valid lower bound in binary search; skips recomputation on parallel edges.
    - **Mode C (Incremental Heuristic)**: Updates local candidate density in $O(1)$; monitors non-local external activity triggers (unique external edge count and degree ratio) to trigger global recomputations. Corrected in Phase 7 to distinguish unique new edges from repeat transactions.
  - `ringscope/eval_harness.py`: Built evaluation metrics (Precision, Recall, F1, Jaccard, density gap, latency percentiles) and CSV/JSON export engine.
  - `ringscope/experiments.py` & `scripts/run_experiments.py`: Built 7 automated empirical benchmark suites.
- **Test Evidence**: Tests validating streaming replay determinism, snapshot fields, mode transitions, and benchmark execution.

---

### Phase 4: Production REST Backend & API
- **Engineering Deliverables**:
  - `ringscope/api.py` & `ringscope/api_v1.py`: Built production FastAPI v1 REST backend exposing endpoints under `/api/v1` for health, graphs, analysis, streaming, and experiments.
  - `ringscope/models_v1.py`: Structured strict Pydantic v2 schemas for all requests and responses.
  - `ringscope/service.py`: Implemented non-blocking worker engine offloading combinatorial algorithms via `asyncio.to_thread`.
- **Test Evidence**: Integration tests validating REST routes, error handling, background execution, and schema conformity.

---

### Phase 5: Research Dashboard & Interactive Visualizer
- **Engineering Deliverables**:
  - `frontend/`: Developed full-stack web dashboard using React 19, Vite, TypeScript, and Tailwind CSS v3.
  - `frontend/src/api/client.ts` & `frontend/src/api/types.ts`: Built typed API client with zero mock fallbacks.
  - `frontend/src/components/CytoscapeGraph.tsx`: Built interactive Cytoscape.js canvas with force-directed, concentric, and circular layouts, node selection, candidate cluster highlighting, and priority sampling display safeguard.
- **Test Evidence**: Vitest client unit tests passing, strict TypeScript typecheck passing, production build compiling cleanly.

---

### Phase 6 & 7: Final Full-System Validation & Technical Audit
- **Engineering Deliverables**:
  - Executed full-system verification across 168 backend pytest tests, frontend typechecks, linters, tests, and production build.
  - Conducted technical audit fixing Goldberg vertex naming collisions, self-loop normalization, Mode B lower-bound interval reuse, and Mode C unique edge accounting.
  - Re-ran empirical benchmarks reproducibly in `experiments_output/reproduced/`.
- **Test Evidence**: 168 / 168 pytest passing, 3 / 3 vitest passing, 0 ruff errors, 0 tsc errors.

---

## 3. Contribution Attribution Matrix

| Technical Capability | Conceptual Inception | Software Implementation | Empirical Validation |
| :--- | :--- | :--- | :--- |
| **Max-Flow Reduction Theorem** | Goldberg (1984) | RingScope Engineering | Validated vs Oracle (100% exact) |
| **2-Approximation Peeling Theorem** | Charikar (2000) | RingScope Engineering | Validated vs Oracle (100% within bound) |
| **Iterative Load Peeling Theorem** | Boob et al. (2020) | RingScope Engineering | Validated vs Oracle (100% ratio) |
| **Tight Safe INF Bound ($2m + n^2 + 10$)** | RingScope Engineering | RingScope Engineering | Verified zero cut leakage in Dinic |
| **Non-Local Streaming Trigger Engine** | Human Project Contributors | RingScope Engineering | Verified Mode C trigger control |
| **Parallel-Edge Recompute Bypassing** | Human Project Contributors | RingScope Engineering | Verified cycle conservation in Mode B/C |
| **Asynchronous Worker Thread Offloading** | RingScope Engineering | RingScope Engineering | Verified non-blocking FastAPI loop |
| **Priority Sampling Canvas Safeguard** | RingScope Engineering | RingScope Engineering | Verified 60 FPS UI performance |

