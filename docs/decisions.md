# Technical Decisions

## D1 — DiGraph vs MultiDiGraph
**Decision**: Use `nx.DiGraph` (single aggregated edge per pair).  
**Reason**: Simplifies density computation and cycle detection. Parallel transactions are aggregated (amounts summed).  
**Trade-off**: Cannot distinguish individual transactions on the same pair. Addressed in Phase 2 by `GraphStore` transaction logging.

## D2 — Johnson's algorithm via NetworkX
**Decision**: Delegate to `nx.simple_cycles` (Johnson 1975 implementation).  
**Reason**: NetworkX's implementation is well-tested and C-accelerated. Re-implementing from scratch would add risk without benefit.  
**Trade-off**: Exponential output size on dense graphs. Mitigated by `max_rings` and `max_length` filters.

## D3 — Greedy as default, Exact as opt-in
**Decision**: `densest_subgraph(algorithm="greedy")` is the default.  
**Reason**: Exact (Goldberg) has flow complexity and is slower for $n > 500$. Greedy has a 2-approximation guarantee and runs in $O((n+e) \log n)$.  
**Trade-off**: Greedy may return suboptimal density. User can opt in to exact for small-to-medium graphs.

## D4 — Incremental ring cache as streaming default
**Decision**: `StreamingRingDetector(incremental=True)` maintains an incremental ring cache.  
**Reason**: For sliding windows, a newly ingested edge $u \to v$ can only form simple cycles that pass through $u \to v$. Searching simple paths from $v$ to $u$ bounded by `max_cycle_length` discovers all new cycles in microseconds. Evicted edges directly invalidate participant rings via hash lookups.  
**Trade-off**: Requires cache state; can be toggled to `incremental=False` for validation.

## D5 — In-memory active graph with SQLite persistence
**Decision**: Fast in-memory active working graph with optional SQLite session store (`GraphStore`).  
**Reason**: Maximizes sub-millisecond graph query responsiveness while enabling multi-session persistence across server restarts.

## D6 — Amount aggregation for repeated edges
**Decision**: `add_transaction(src, dst, ...)` accumulates `amount` and increments `tx_count` for repeated src→dst pairs.  
**Reason**: Consistent with the aggregated-edge model (D1) and avoids multi-edge complexity.

## D7 — Fixed random seeds
**Decision**: All data generators default to fixed seeds (42, 7, 99, etc.).  
**Reason**: Reproducibility is a primary requirement. Tests pass deterministically.

## D8 — Maximum weight closure formulation for Exact Densest Subgraph
**Decision**: Formulate exact directed densest subgraph via Picard (1976) / Goldberg (1984) maximum weight closure min-cut.  
**Reason**: The undirected degree-offset formulation produced artifacts on sparse directed graphs. The closure formulation with edge-nodes of capacity 1, vertex-nodes of capacity $\alpha$, and infinite-capacity implications rigorously models directed density $|E(S)| / |S|$ and guarantees exact density $\ge$ greedy density across all instances.

## D9 — Interactive HTML5 Canvas physics renderer
**Decision**: Build custom spring-embedder force graph renderer in `GraphCanvas.jsx`.  
**Reason**: Zero external bundle bloat, zero SSR / Vite worker incompatibilities, high-DPI crisp rendering, direct glow rendering for detected ring nodes.
