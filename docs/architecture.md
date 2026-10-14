# RingScope — Architecture

## Overview

RingScope is a research platform for graph-based transaction-ring analysis. It consists of:

```
ringscope/
├── __init__.py          — package version
├── graph.py             — TransactionGraph (NetworkX DiGraph wrapper)
├── data.py              — Synthetic data generators
├── storage.py           — SQLite persistence and multi-session store
├── evaluation.py        — Research benchmark suite (recall, precision, approx ratio, TPS)
├── api.py               — FastAPI REST server
└── algorithms/
    ├── __init__.py
    ├── cycle_detection.py    — Johnson's algorithm (ring detection)
    ├── densest_subgraph.py   — Charikar greedy + Picard-Goldberg exact min-cut
    └── streaming.py          — Sliding-window detector with incremental ring cache

tests/
├── test_graph.py
├── test_cycle_detection.py
├── test_densest_subgraph.py
├── test_streaming.py
├── test_storage.py
├── test_evaluation.py
└── test_api.py

frontend/                — React + Vite dashboard
```

## Component Contracts

### TransactionGraph (`graph.py`)
- Wraps `nx.DiGraph`
- Edge attributes: `amount` (float), `timestamp` (float), `tx_id` (str), `tx_count` (int)
- Repeated edges are aggregated (amount summed, timestamp maxed)
- `to_dict()` / `from_dict()` provide JSON round-trip for graph serialization and topology export

### Ring Detection (`algorithms/cycle_detection.py`)
- Algorithm: Johnson 1975 via `nx.simple_cycles`
- Returns `Ring` objects sorted by `min_amount` descending
- Filters: `min_length`, `max_length`, `min_amount`, `max_rings`
- `Ring.min_amount` = bottleneck edge amount (flow proxy)

### Densest Subgraph (`algorithms/densest_subgraph.py`)
- **Greedy (Charikar)**: $O((n+e) \log n)$, 2-approximation peeling algorithm.
- **Exact (Picard-Goldberg Closure)**: Maximum weight closure min-cut formulation over directed graphs. Binary searches $\alpha$ such that min-cut $< |E|$ iff density $> \alpha$. Provably exact, guaranteeing `exact_density >= greedy_density`.
- Density = $|E(S)| / |S|$ (directed edge count / node count).

### Streaming Detector (`algorithms/streaming.py`)
- Sliding time window with configurable `window_size` (seconds).
- **Incremental Ring Cache**: When edge $u \to v$ arrives, explores bounded simple paths from $v$ to $u$ in $O(\text{paths})$, avoiding full graph recomputation. Evictions perform $O(1)$ hash-set cycle invalidations.
- Returns `WindowSnapshot` per ingestion (ring counts, density, latency in ms).

### Persistence & Storage (`storage.py`)
- SQLite-backed `GraphStore` supporting `:memory:` and disk-file storage (`ringscope.db`).
- Durable tables for graphs, accounts, and individual transactions.
- Preserves individual transaction records and metadata while maintaining aggregated graphs.

### REST API (`api.py`)
- Base URL: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs
- State: Active `TransactionGraph`, `StreamingRingDetector`, and `GraphStore`.

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Liveness probe |
| GET | /graph | Current graph stats |
| GET | /graph/export | Full node/edge list for interactive topology canvas |
| POST | /graph/load | Load synthetic graph |
| POST | /graph/transaction | Add single transaction |
| POST | /graph/transactions | Batch-add transactions |
| GET | /rings | Detect rings (with filters) |
| GET | /densest | Densest subgraph (greedy or exact) |
| POST | /stream/ingest | Ingest streaming transactions |
| GET | /stream/snapshot | Current stream window state |
| POST | /stream/reset | Reset stream state |
| GET | /graphs | List saved graph sessions |
| POST | /graphs/save | Save current graph to SQLite session store |
| POST | /graphs/{graph_id}/load | Load saved graph session |
| DELETE | /graphs/{graph_id} | Delete saved graph session |
| GET | /experiments/benchmark | Planted-ring recall and greedy vs exact benchmark |
| GET | /experiments/streaming-profile | Profiling incremental cache vs full recomputation TPS |
