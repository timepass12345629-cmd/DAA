# RingScope — Claim-Evidence Matrix & Patent Defensibility Audit

**Audit Date**: October 2026  
**Auditor**: Independent Algorithm & Verification Engine  
**Project**: RingScope (Graph-Algorithms Platform for Transaction Ring Analysis)  

---

## 1. Overview & Evaluation Methodology

This matrix audits every major technical, algorithmic, and patent claim articulated across the RingScope repository (`docs/research_report.md`, `docs/patent-research/`, `ringscope/algorithms/`, and test suites).

Claims are classified into four status categories:
- **Supported**: Supported by mathematically verified code, passing unit/oracle tests, and reproducible benchmark measurements.
- **Partially Supported**: Valid in core implementation but subject to unstated boundary conditions, asymptotic limitations, or heuristic trade-offs. Requires qualification.
- **Unsupported**: Inconsistent with code or empirical findings; must be removed or rewritten.
- **Requires External Prior-Art Review**: Candidate technical contribution that must be assessed by a registered Indian patent agent for Section 3(k) statutory compliance and prior art clearance.

---

## 2. Claim-Evidence Matrix

| # | Domain / Topic | Stated Claim in Previous Documents | Supporting Code / Evidence | Audit Status | Recommended Wording / Action |
| :-: | :--- | :--- | :--- | :--- | :--- |
| **1** | **Goldberg Exactness** | Goldberg's algorithm finds the exact maximum density subgraph on all graphs. | `ringscope/algorithms/goldberg.py`<br>`tests/test_goldberg.py`<br>`tests/test_brute_force.py` | **Partially Supported** | *Narrow Claim*: The flow-network reduction formulation is exact. In floating-point binary search, exactness is guaranteed when $\epsilon < \frac{1}{n(n-1)}$. Coarser tolerances or early `max_iter` stops yield $\epsilon$-optimal approximations. |
| **2** | **Greedy++ Guarantee** | Greedy++ universally guarantees a $(1 - \epsilon)$-approximation in a fixed 10 passes. | `ringscope/algorithms/greedy_plus_plus.py` | **Unsupported** *(for fixed $T$)* | *Correct Claim*: Theoretical $(1 - \epsilon)$ guarantee requires $T = \Omega\left(\frac{\Delta}{\lambda^*} \frac{\log n}{\epsilon^2}\right)$ (Boob et al., WWW 2020). For fixed $T=10$, it is an empirical heuristic that performs well in practice but lacks worst-case universal $(1-\epsilon)$ bounds. |
| **3** | **Greedy++ $T=1$ Equivalence** | When $T=1$, Greedy++ is identical to Charikar's peeling algorithm. | `ringscope/algorithms/greedy_plus_plus.py`<br>`tests/test_greedy_plus_plus.py` | **Supported** | *Retain Claim*: Proved and verified via regression test `test_greedy_plus_plus_iterations_1_matches_charikar()`. |
| **4** | **Warm-Started Binary Search** | Mode B prunes the binary search interval by reusing the prior density as a lower bound. | `ringscope/algorithms/goldberg.py`<br>`ringscope/stream_simulator.py` | **Supported** *(post Phase 7 fix)* | *Retain Claim*: By density monotonicity under edge insertions ($\lambda^*(G \cup \{e\}) \ge \lambda^*(G)$), prior density $\lambda_{t-1}$ is a mathematically valid lower bound, genuinely passed to the solver. |
| **5** | **Mode C Drift Control** | Incremental heuristic (Mode C) maintains candidate cluster while bounding drift via non-local triggers. | `ringscope/stream_simulator.py`<br>`tests/test_streaming_modes.py` | **Supported** *(as a heuristic)* | *Qualify Claim*: Mode C is an empirical heuristic that achieves sub-millisecond batch latencies and controlled drift on typical streams. It does NOT guarantee global optimality at all steps. |
| **6** | **Mode C 100% Density Parity** | Mode C achieved 100% density parity with exact ground truth in baseline streaming tests. | Baseline CSV: `candidate_density=1.3333`, `exact_reference=1.4167` | **Unsupported** *(factually inaccurate)* | *Remove Claim*: 1.3333 was the density of Greedy Peeling, while exact Goldberg was 1.4167. In corrected runs, Mode C achieved 1.3125 (a 1.5% heuristic variation while saving 66.7% of recomputations). |
| **7** | **Parallel Transaction Invariance** | Parallel transactions do not alter simple graph topology and skip recomputation. | `ringscope/graph.py`<br>`ringscope/stream_simulator.py` | **Supported** | *Retain Claim*: Parallel records update metadata without incrementing unique edges. Verified in `test_mode_b_warm_started_saves_recomputations()`. |
| **8** | **Planted Ring Recovery** | RingScope recovers planted collusive rings with high $F_1$ in noisy transaction graphs. | `ringscope/data.py`<br>`experiments_output/reproduced/exp2_*.csv` | **Supported** | *Retain Claim*: Validated across synthetic benchmarks ($F_1 \ge 0.80 - 1.00$ for $k \ge 6$). Explicitly label as synthetic evaluation. |
| **9** | **Asynchronous Worker Non-Blocking** | CPU-bound combinatorial algorithms are offloaded, preventing event loop blocking. | `ringscope/service.py`<br>`ringscope/api_v1.py` | **Supported** | *Retain Claim*: Implemented via `asyncio.to_thread` for all analysis, streaming, and experiment operations. |
| **10** | **Production Readiness** | The prototype is fully production-ready for live banking deployment. | In-memory graphs, SQLite fallback, single-process dev servers | **Unsupported** | *Narrow Claim*: The platform is a research prototype and benchmarking framework. Production deployment requires distributed graph databases (e.g. Neo4j/TigerGraph), Kafka stream connectors, and HA deployment. |
| **11** | **Patent Inventorship by AI** | DeepMind Antigravity IDE / AI coding assistant is an inventor of the technology. | Prior disclosure documents | **Unsupported** *(legally invalid)* | *Remove AI Inventor*: Under the Indian Patents Act, 1970, inventorship is restricted to natural human persons. Use the Human-Contribution Review Checklist. |
| **12** | **Novelty of Goldberg / Dinic / Peeling** | Goldberg flow reduction and Charikar peeling are novel inventions of the project. | `docs/patent-research/candidate_novelty.md` | **Unsupported** *(public domain prior art)* | *Retain Strict Prior-Art Demarcation*: Goldberg (1984), Charikar (2000), Dinic (1970), and Boob et al. (2020) are public domain prior art. |
| **13** | **Non-Local Streaming Triggers Patentability** | Non-local external activity triggers in streaming graph maintenance are patentable in India. | `ringscope/stream_simulator.py` | **Requires External Prior-Art Review** | *Action*: Submit technical disclosure to a registered Indian Patent Agent for Section 3(k) statutory review regarding tangible technical effect on processor starvation and cache drift. |
| **14** | **Warm-Started Flow Search Pruning Patentability** | Monotone lower-bound binary search pruning in streaming flow networks is patentable. | `ringscope/algorithms/goldberg.py` | **Requires External Prior-Art Review** | *Action*: Must be reviewed by patent counsel; claiming binary search lower bounds in isolation risks rejection as a mathematical method. |

---

## 3. Summary of Document Actions Required

1. **`docs/research_report.md`**:
   - Soften "universal $(1-\epsilon)$ in 10 passes" claim for Greedy++.
   - Clarify the $0.0833$ streaming gap in Section 9.6: greedy peeling (1.3333) vs exact Goldberg (1.4167).
   - Update Mode C recomputation counts to reflect corrected unique edge tracking (4/12 instead of 11/12).
2. **`docs/patent-research/candidate_novelty.md`**:
   - Remove "100% density parity with exact ground truth" for Mode C.
   - Retain honest demarcation of public domain prior art.
3. **`docs/patent-research/inventor_contributions.md`**:
   - Exclude AI agents from inventorship; mandate project human contributor identification.
