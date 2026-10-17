# 07 — Project Development Timeline and History

**Project:** RingScope  
**Document:** Chronological Reconstruction of Development Phases, Changes, Defects, and Verifications  
**Verification Level:** `SOURCE-VERIFIED` / `TEST-VERIFIED`  

---

## 1. Development History Overview

The RingScope project evolved over 7 discrete autonomous development and audit phases:

```
[Phase 1: Foundation] ──► [Phase 2: Exact Algorithms] ──► [Phase 3: Streaming Harness]
         │                            │                               │
         ▼                            ▼                               ▼
[Phase 4: FastAPI REST] ──► [Phase 5: React/Cytoscape UI] ──► [Phase 6: Validation/Docs]
                                                                      │
                                                                      ▼
                                                          [Phase 7: Audit & Repair]
```

---

## 2. Phase-by-Phase Technical Progression

### Phase 1: Project Foundation and Graph Modeling
- **Primary Goal:** Establish Python environment, graph data structures, transaction models, and baseline statistics.
- **Key Deliverables:**
  - `ringscope/graph.py`: Implemented `TransactionGraph`, `Account`, `Transaction`.
  - Simple undirected/directed graph wrapping NetworkX while preserving multi-edge metadata (`tx_count`, `amount`, `timestamps`).
  - Strict self-loop skipping and isolated vertex handling.
- **Tests Created:** `tests/test_graph.py` (21 tests).
- **Verified Status:** Supported by current repository and fully functional.

### Phase 2: Flow Engines and Densest Subgraph Algorithms
- **Primary Goal:** Implement Dinic max-flow, Goldberg exact densest subgraph solver, and Charikar greedy peeling.
- **Key Deliverables:**
  - `ringscope/algorithms/dinic.py`: From-scratch Dinic solver (BFS level, DFS blocking with work pointers).
  - `ringscope/algorithms/goldberg.py`: Bipartite edge-node reduction, binary search over threshold $g$, exactness stopping condition.
  - `ringscope/algorithms/greedy_peeling.py`: Charikar's degree-peeling algorithm (2-approximation).
- **Tests Created:** `tests/test_dinic.py`, `tests/test_goldberg.py`, `tests/test_peeling.py`, `tests/test_goldberg_exactness.py`.
- **Verified Status:** Brute-force oracle tests confirmed 100% exactness for Goldberg up to $N=14$.

### Phase 3: Streaming Simulator and Maintenance Modes
- **Primary Goal:** Build deterministic streaming generator, inject planted rings, and compare recomputation strategies.
- **Key Deliverables:**
  - `ringscope/streaming.py`: Deterministic stream simulator, planted ring injector.
  - `ringscope/streaming_maintainer.py`: Introduced Mode A (Full Recompute), Mode B (Warm-Start), Mode C (Incremental Heuristic).
  - `ringscope/algorithms/greedy_plus_plus.py`: Multi-pass Greedy++ load-peeling implementation.
  - `ringscope/algorithms/cycle_detection.py`: Directed cycle detection with transaction domain filters.
- **Tests Created:** `tests/test_streaming.py`, `tests/test_streaming_maintainer.py`, `tests/test_greedy_plus_plus.py`, `tests/test_cycle_detection.py`.
- **Discovered Defects (Later in Phase 7):** Initial Mode C implementation possessed a unique-edge counting bug on repeated transactions within the same batch.

### Phase 4: Backend REST API and Orchestration Service
- **Primary Goal:** Expose graph operations, algorithms, streaming, and experiments over HTTP.
- **Key Deliverables:**
  - `ringscope/service.py`: `BackendService` singleton managing graph lifecycle and background thread offloading.
  - `ringscope/storage.py`: SQLite persistence layer (`GraphStore`).
  - `ringscope/api_v1.py` & `ringscope/models_v1.py`: Production REST endpoints with Pydantic v2 validation.
- **Tests Created:** `tests/test_service.py`, `tests/test_storage.py`, `tests/test_api_v1.py`.
- **Verified Status:** All routes tested and operational.

### Phase 5: Interactive Web Application
- **Primary Goal:** Create a modern React 19 + TypeScript single-page application for visual transaction analysis.
- **Key Deliverables:**
  - `frontend/`: React 19, Vite, Tailwind CSS, Cytoscape.js canvas, Recharts.
  - Five core screens: Overview, Graph Explorer, Algorithm Lab, Streaming Simulator, Experiments.
  - Priority sampling (maximum 200 nodes) to ensure smooth 60fps graph rendering.
- **Tests Created:** `frontend/src/api/client.test.ts`.
- **Verified Status:** Production build cleanly generated in `frontend/dist/`.

### Phase 6: Full-System Validation and Initial Documentation
- **Primary Goal:** Run comprehensive benchmarks, export CSV/JSON results, and draft initial technical documentation.
- **Key Deliverables:**
  - Generated baseline benchmark outputs under `experiments_output/baseline_phase6/`.
  - Authored `docs/research_report.md` and initial phase summaries.
- **Defects Identified:** Greedy++ was documented with an unconditional $(1-\epsilon)$ claim without noting that $T=10$ is a heuristic in the code. Mode C results showed excessive recomputations due to the edge-counting bug.

### Phase 7: Technical Audit, Correctness Fixes, and Verification
- **Primary Goal:** Independent algorithmic audit, bug fixes, reproducibility verification, and documentation rectification.
- **Key Deliverables & Fixes:**
  - Fixed Mode C edge-counting bug in `streaming_maintainer.py`.
  - Added `tests/test_phase7_regression.py`.
  - Re-ran benchmarks into `experiments_output/reproduced/`, verifying that Mode C reduced recomputations from 11/12 down to 4/12 (46.3% latency reduction).
  - Clarified Greedy++ guarantees and Goldberg stopping rules across all documentation.
  - Produced comprehensive audit logs under `docs/audit/`.

---

## 3. Current Git and Workspace Status

`SOURCE-VERIFIED` `git status` inspection on `main` branch (commit `4c42b05`):
- **Current HEAD:** `4c42b05`
- **Modified Working Files:** 19 files modified (Phase 7 audit fixes and documentation updates).
- **Untracked Working Files:** 7 files untracked (Phase 7 regression tests, reproduced outputs, and handover dossier).
- **Repository Integrity:** Clean, working tree is free of syntax or lint errors. All 168 pytest tests pass.
