# Known Issues and Limitations

## Resolved Issues

### KI-1 — Streaming ring detection O(cycles) recomputation (RESOLVED)
- **Status**: Resolved in Phase 2.
- **Resolution**: Implemented an incremental ring cache in `StreamingRingDetector`. When a new edge arrives, only newly created cycles passing through the new edge are discovered via bounded simple-path exploration. Evicted edges trigger instant hash-set cycle invalidation, yielding multi-fold speedups in streaming TPS.

### KI-2 & KI-6 — Exact Goldberg algorithm instability & under-performance on sparse graphs (RESOLVED)
- **Status**: Resolved in Phase 2.
- **Resolution**: Replaced the heuristic node-degree flow formulation with the Picard (1976) / Goldberg (1984) maximum weight closure min-cut network on directed graphs. For any candidate density $\alpha$, the $(s, t)$-cut capacity is $|E| - (|E(S)| - \alpha |S|)$, which is strictly $< |E|$ iff density $> \alpha$. This formulation is provably optimal on all directed graphs, guaranteeing `exact_density >= greedy_density`.

### KI-3 — DiGraph edge aggregation losing per-transaction history (RESOLVED)
- **Status**: Resolved in Phase 2.
- **Resolution**: Added `ringscope.storage.GraphStore` with a dedicated `transactions` table indexing individual transactions by `tx_id`, recording granular transaction events while maintaining aggregated DiGraph views for fast spectral/topological analytics.

### KI-4 — API state thread-safety under concurrent writes (RESOLVED)
- **Status**: Resolved in Phase 2.
- **Resolution**: Added SQLite database persistence with foreign keys and ACID transactions (`PRAGMA foreign_keys = ON; timeout = 10.0`), isolating database operations and session states.

### KI-5 — Frontend dashboard (RESOLVED)
- **Status**: Resolved in Phase 2.
- **Resolution**: Full React + Vite dashboard with interactive physics canvas topology (`GraphCanvas.jsx`), Johnson ring detection inspector, densest subgraph analyzer, live sliding-window stream simulator, and research benchmark suites.

## Current Limitations

### LIM-1 — Elementary cycle enumeration worst-case bound
- **Severity**: Low (by design).
- **Description**: Johnson's algorithm has exponential worst-case output complexity on complete/dense graphs.
- **Mitigation**: Protected by `max_cycle_length` (default 10) and `max_rings` (default 100) filters in `detect_rings`.
