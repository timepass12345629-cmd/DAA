# 10 — Master File and Code Symbol Index

**Project:** RingScope  
**Document:** Exhaustive File Index, Component Mapping, and Handover Cross-Reference  
**Verification Level:** `SOURCE-VERIFIED`  

---

## 1. Master Source Code Index

| Absolute / Relative Path | Primary Language / Type | Key Classes & Functions | Relevant Handover Document |
| :--- | :--- | :--- | :--- |
| [`ringscope/__init__.py`](file:///c:/VS%20code/DAA/ringscope/__init__.py) | Python package | `__version__ = "0.1.0"` | [`00_EXECUTIVE_HANDOVER.md`](file:///c:/VS%20code/DAA/docs/handover/00_EXECUTIVE_HANDOVER.md), [`01_REPOSITORY_MAP.md`](file:///c:/VS%20code/DAA/docs/handover/01_REPOSITORY_MAP.md) |
| [`ringscope/graph.py`](file:///c:/VS%20code/DAA/ringscope/graph.py) | Python module | `TransactionGraph`, `Account`, `Transaction`, `add_transaction()`, `subgraph_density()` | [`01_REPOSITORY_MAP.md`](file:///c:/VS%20code/DAA/docs/handover/01_REPOSITORY_MAP.md), [`02_ARCHITECTURE_AND_DATA_FLOW.md`](file:///c:/VS%20code/DAA/docs/handover/02_ARCHITECTURE_AND_DATA_FLOW.md) |
| [`ringscope/storage.py`](file:///c:/VS%20code/DAA/ringscope/storage.py) | Python module | `GraphStore`, SQLite CRUD operations, `save_graph()`, `load_graph()` | [`02_ARCHITECTURE_AND_DATA_FLOW.md`](file:///c:/VS%20code/DAA/docs/handover/02_ARCHITECTURE_AND_DATA_FLOW.md) |
| [`ringscope/service.py`](file:///c:/VS%20code/DAA/ringscope/service.py) | Python module | `BackendService`, `run_analysis_async()`, `create_streaming_session()` | [`01_REPOSITORY_MAP.md`](file:///c:/VS%20code/DAA/docs/handover/01_REPOSITORY_MAP.md), [`02_ARCHITECTURE_AND_DATA_FLOW.md`](file:///c:/VS%20code/DAA/docs/handover/02_ARCHITECTURE_AND_DATA_FLOW.md) |
| [`ringscope/api_v1.py`](file:///c:/VS%20code/DAA/ringscope/api_v1.py) | Python FastAPI | Route handlers (`/health`, `/graphs/*`, `/analysis/*`, `/stream/*`, `/experiments/*`) | [`01_REPOSITORY_MAP.md`](file:///c:/VS%20code/DAA/docs/handover/01_REPOSITORY_MAP.md), [`02_ARCHITECTURE_AND_DATA_FLOW.md`](file:///c:/VS%20code/DAA/docs/handover/02_ARCHITECTURE_AND_DATA_FLOW.md) |
| [`ringscope/models_v1.py`](file:///c:/VS%20code/DAA/ringscope/models_v1.py) | Python Pydantic | `AnalysisRequest`, `AnalysisResponse`, `StreamStepResponse`, `GraphResponse` | [`02_ARCHITECTURE_AND_DATA_FLOW.md`](file:///c:/VS%20code/DAA/docs/handover/02_ARCHITECTURE_AND_DATA_FLOW.md) |
| [`ringscope/algorithms/dinic.py`](file:///c:/VS%20code/DAA/ringscope/algorithms/dinic.py) | Python algorithm | `Dinic`, `max_flow()`, `min_cut_source_set()`, `_bfs()`, `_dfs()` | [`03_ALGORITHM_IMPLEMENTATIONS.md`](file:///c:/VS%20code/DAA/docs/handover/03_ALGORITHM_IMPLEMENTATIONS.md) |
| [`ringscope/algorithms/goldberg.py`](file:///c:/VS%20code/DAA/ringscope/algorithms/goldberg.py) | Python algorithm | `goldberg_densest_subgraph()`, `goldberg_decision_threshold()`, exactness checks | [`03_ALGORITHM_IMPLEMENTATIONS.md`](file:///c:/VS%20code/DAA/docs/handover/03_ALGORITHM_IMPLEMENTATIONS.md), [`08_PATENT_CONTRIBUTION_EVIDENCE.md`](file:///c:/VS%20code/DAA/docs/handover/08_PATENT_CONTRIBUTION_EVIDENCE.md) |
| [`ringscope/algorithms/greedy_peeling.py`](file:///c:/VS%20code/DAA/ringscope/algorithms/greedy_peeling.py) | Python algorithm | `charikar_greedy_peeling()`, degree min-heap, lazy pop updates | [`03_ALGORITHM_IMPLEMENTATIONS.md`](file:///c:/VS%20code/DAA/docs/handover/03_ALGORITHM_IMPLEMENTATIONS.md) |
| [`ringscope/algorithms/greedy_plus_plus.py`](file:///c:/VS%20code/DAA/ringscope/algorithms/greedy_plus_plus.py) | Python algorithm | `greedy_plus_plus()`, cumulative vertex load updates, multi-pass peeling | [`03_ALGORITHM_IMPLEMENTATIONS.md`](file:///c:/VS%20code/DAA/docs/handover/03_ALGORITHM_IMPLEMENTATIONS.md) |
| [`ringscope/algorithms/cycle_detection.py`](file:///c:/VS%20code/DAA/ringscope/algorithms/cycle_detection.py) | Python algorithm | `find_transaction_rings()`, Johnson cycle enumeration, length/bottleneck filters | [`03_ALGORITHM_IMPLEMENTATIONS.md`](file:///c:/VS%20code/DAA/docs/handover/03_ALGORITHM_IMPLEMENTATIONS.md) |
| [`ringscope/streaming.py`](file:///c:/VS%20code/DAA/ringscope/streaming.py) | Python module | `TransactionStreamSimulator`, `StreamBatch`, `inject_planted_ring()` | [`04_STREAMING_MODES.md`](file:///c:/VS%20code/DAA/docs/handover/04_STREAMING_MODES.md) |
| [`ringscope/streaming_maintainer.py`](file:///c:/VS%20code/DAA/ringscope/streaming_maintainer.py) | Python module | `FullRecomputationMaintainer`, `WarmStartedMaintainer`, `IncrementalHeuristicMaintainer` | [`04_STREAMING_MODES.md`](file:///c:/VS%20code/DAA/docs/handover/04_STREAMING_MODES.md), [`08_PATENT_CONTRIBUTION_EVIDENCE.md`](file:///c:/VS%20code/DAA/docs/handover/08_PATENT_CONTRIBUTION_EVIDENCE.md) |
| [`ringscope/experiment_harness.py`](file:///c:/VS%20code/DAA/ringscope/experiment_harness.py) | Python module | `ExperimentHarness`, `run_experiment()`, `export_csv()`, `export_json()` | [`05_EXPERIMENTS_AND_RESULTS.md`](file:///c:/VS%20code/DAA/docs/handover/05_EXPERIMENTS_AND_RESULTS.md) |
| [`frontend/src/App.tsx`](file:///c:/VS%20code/DAA/frontend/src/App.tsx) | React / TSX | Root navigation, active tab container, shared state | [`01_REPOSITORY_MAP.md`](file:///c:/VS%20code/DAA/docs/handover/01_REPOSITORY_MAP.md), [`02_ARCHITECTURE_AND_DATA_FLOW.md`](file:///c:/VS%20code/DAA/docs/handover/02_ARCHITECTURE_AND_DATA_FLOW.md) |
| [`frontend/src/components/CytoscapeGraph.tsx`](file:///c:/VS%20code/DAA/frontend/src/components/CytoscapeGraph.tsx) | React / TSX | Cytoscape.js canvas, priority downsampling (200 nodes), color highlighting | [`02_ARCHITECTURE_AND_DATA_FLOW.md`](file:///c:/VS%20code/DAA/docs/handover/02_ARCHITECTURE_AND_DATA_FLOW.md) |
| [`frontend/src/api/client.ts`](file:///c:/VS%20code/DAA/frontend/src/api/client.ts) | TypeScript | Typed REST API client fetching data from FastAPI backend | [`02_ARCHITECTURE_AND_DATA_FLOW.md`](file:///c:/VS%20code/DAA/docs/handover/02_ARCHITECTURE_AND_DATA_FLOW.md) |
| [`scripts/run_experiments.py`](file:///c:/VS%20code/DAA/scripts/run_experiments.py) | Python CLI script | Main CLI runner for Exp 1 through Exp 7 | [`01_REPOSITORY_MAP.md`](file:///c:/VS%20code/DAA/docs/handover/01_REPOSITORY_MAP.md), [`05_EXPERIMENTS_AND_RESULTS.md`](file:///c:/VS%20code/DAA/docs/handover/05_EXPERIMENTS_AND_RESULTS.md) |

---

## 2. Handover Documentation Cross-Reference Matrix

All 11 handover documents are cross-referenced below with their direct links:

1. [`00_EXECUTIVE_HANDOVER.md`](file:///c:/VS%20code/DAA/docs/handover/00_EXECUTIVE_HANDOVER.md) — High-level executive summary, system boundaries, and verified operational state.
2. [`01_REPOSITORY_MAP.md`](file:///c:/VS%20code/DAA/docs/handover/01_REPOSITORY_MAP.md) — Directory layout, module purpose, system entry points, dependencies, and environment configuration.
3. [`02_ARCHITECTURE_AND_DATA_FLOW.md`](file:///c:/VS%20code/DAA/docs/handover/02_ARCHITECTURE_AND_DATA_FLOW.md) — End-to-end data flow, Mermaid architecture diagrams, graph representation invariants, and persistence model.
4. [`03_ALGORITHM_IMPLEMENTATIONS.md`](file:///c:/VS%20code/DAA/docs/handover/03_ALGORITHM_IMPLEMENTATIONS.md) — Detailed algorithm mechanics for Dinic, Goldberg, Charikar, Greedy++, and Cycle Detection.
5. [`04_STREAMING_MODES.md`](file:///c:/VS%20code/DAA/docs/handover/04_STREAMING_MODES.md) — In-depth analysis of streaming maintainers: Mode A (Full), Mode B (Warm-Start), and Mode C (Incremental Heuristic).
6. [`05_EXPERIMENTS_AND_RESULTS.md`](file:///c:/VS%20code/DAA/docs/handover/05_EXPERIMENTS_AND_RESULTS.md) — Full inventory of experimental scripts, baseline vs reproduced outputs, metrics, and limitations.
7. [`06_TESTS_AND_VERIFICATION.md`](file:///c:/VS%20code/DAA/docs/handover/06_TESTS_AND_VERIFICATION.md) — Complete test suite inventory, execution evidence, coverage gaps, and verification commands.
8. [`07_DEVELOPMENT_TIMELINE.md`](file:///c:/VS%20code/DAA/docs/handover/07_DEVELOPMENT_TIMELINE.md) — Phase-by-phase chronological history from Phase 1 to Phase 7.
9. [`08_PATENT_CONTRIBUTION_EVIDENCE.md`](file:///c:/VS%20code/DAA/docs/handover/08_PATENT_CONTRIBUTION_EVIDENCE.md) — Honest separation of prior art, engineering choices, and potential candidate contributions.
10. [`09_OPEN_ISSUES_AND_NEXT_STEPS.md`](file:///c:/VS%20code/DAA/docs/handover/09_OPEN_ISSUES_AND_NEXT_STEPS.md) — Prioritized technical defects, risk matrix, and actionable next steps.
11. [`10_FILE_INDEX.md`](file:///c:/VS%20code/DAA/docs/handover/10_FILE_INDEX.md) — Exhaustive index of all critical source files and their corresponding handover document mappings.
