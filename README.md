# RingScope

A research and engineering platform for financial transaction graph analysis, cycle/ring detection, and densest subgraph discovery.

---

## Phase 1: Foundations & Graph Model

Phase 1 establishes the foundational graph data model, input validation, synthetic data generators, CSV import pipeline, graph statistics, and a brute-force densest-subgraph verification oracle.

### Core Foundations & Invariants

1. **Undirected Simple Graph Model (`TransactionGraph`)**:
   - Accounts are vertices; unique transaction relationships are edges.
   - Built on NetworkX `Graph` (undirected by default).
   - In an undirected simple graph, `(u, v)` and `(v, u)` represent the same physical edge.
   - **Parallel Transactions**: Parallel transactions between existing endpoints increment `tx_count` and accumulate amounts/timestamps without duplicating the edge.
   - **Self-Loops**: Self-loops `(u, u)` are filtered out and tracked in `self_loops_skipped` without forming internal edges.
   - **Isolated Vertices**: Accounts with 0 transactions are preserved as isolated vertices and distinct connected components.
   - **Input Validation**: `None`, empty, or whitespace-only account identifiers raise `ValueError`.

2. **Graph Statistics & Density**:
   - `num_vertices`: Count of unique accounts ($|V|$).
   - `num_unique_edges`: Count of unique edges ($|E|$).
   - `degrees()` / `degree(v)`: Degree per vertex.
   - `connected_components()`: Disjoint connected vertex sets.
   - `density(subset)`: For a nonempty vertex subset $S \subseteq V$:
     $$\text{density}(S) = \frac{|E(S)|}{|S|}$$
     where $|E(S)|$ is the number of unique undirected internal edges within $S$.

3. **Reproducible Planted Dense Cluster Generator (`generate_planted_cluster_graph`)**:
   - Generates a background Erdos-Renyi graph with probability $p_{\text{out}}$.
   - Plants a dense cluster of size $k$ with internal probability $p_{\text{in}}$.
   - Guarantees reproducibility via fixed random seeds.
   - Returns ground-truth cluster membership and baseline densities.

4. **Robust CSV Edge-List Importer (`import_csv_edgelist`)**:
   - Configurable source and target column headers (auto-detects `source`/`src`/`from` and `target`/`dst`/`to`).
   - Auto-detects or explicitly parses `amount` and `timestamp`.
   - Validates missing header columns, missing/empty endpoints, and malformed numeric fields with clear, row-indexed errors.
   - Preserves additional CSV columns in edge metadata.

5. **Brute-Force Densest Subgraph Reference Solver (`brute_force_densest_subgraph`)**:
   - Exhaustively enumerates all $2^n - 1$ nonempty subsets of vertices.
   - Small-instance oracle: strictly bounded to $n \le 20$ vertices (raises `ValueError` if $n > 20$).

---

## Phase 2: Flow Networks & Densest Subgraph Algorithms

Phase 2 implements exact and approximation algorithms for the Densest Subgraph Problem (DSP), starting from a scratch-built maximum flow engine.

### 1. Dinic's Maximum Flow Algorithm (`ringscope.algorithms.dinic`)
- Implemented from scratch with residual graph forward and backward edges.
- Breadth-First Search (BFS) constructs the level graph.
- Depth-First Search (DFS) with per-vertex work pointers pushes blocking flow.
- Extracts the source-side minimum cut via residual graph reachability.
- Complexity: $O(V^2 E)$ general, $O(E \sqrt{V})$ on unit/bipartite networks.

### 2. Goldberg's Flow-Based Densest Subgraph Solver (`ringscope.algorithms.goldberg`)
- Formulates the exact decision procedure using a bipartite edge-node flow network:
  - Source $s \to e$ with capacity 1.0 (for each edge $e = \{u, v\}$).
  - Edge-node $e \to u$ and $e \to v$ with capacity INF.
  - Vertex-node $v \to t$ with capacity $g$ (candidate density threshold).
- Cut Cost Analysis:
  $$C(S) = m - |E(S)| + g |S|$$
  A cut strictly cheaper than $m$ ($C(S) < m$) exists if and only if $\frac{|E(S)|}{|S|} > g$.
- Rigorous INF Capacity: $\text{INF} = 2m + n^2 + 10.0 > m + g \cdot n$, mathematically guaranteeing that no INF edge is ever cut.
- Binary search over $g \in [0, (n-1)/2]$ with tolerance $\epsilon$.

### 3. Charikar's Greedy Peeling Algorithm (`ringscope.algorithms.greedy_peeling`)
- Iteratively peels the vertex with minimum induced degree using a lazy min-heap.
- Time Complexity: $O((n + m) \log n)$ time and $O(n + m)$ space.
- Theoretical Guarantee: Provable 2-approximation ($d \ge \text{OPT} / 2$).
- Relationship between density and average degree:
  $$\text{average\_degree}(S) = \frac{2 |E(S)|}{|S|} = 2 \cdot \text{density}(S)$$
- Records full chronological peeling history (`PeelingStep`) with snapshot densities.

### 4. Greedy++ Iterative Peeling Framework (`ringscope.algorithms.greedy_plus_plus`)
- Published Reference: Boob, Gao, Peng, Sawlani, Tsourakakis, Wang, Wang (WWW 2020 / KDD 2020).
- Multi-pass peeling guided by accumulated load:
  $$v^* = \arg\min_{v \in V(H)} (\text{deg}_H(v) + \ell(v))$$
  $$\ell(v^*) \leftarrow \ell(v^*) + \text{deg}_H(v^*)$$
- Provably achieves a $(1 - \epsilon)$-approximation in $O(\Delta \log n / (\lambda^* \epsilon^2))$ iterations without expensive flow computations.

### 5. Multi-Algorithm Oracle Validation
Comprehensive unit tests validate Goldberg, Greedy Peeling, and Greedy++ against the Phase 1 Brute-Force oracle across:
- Path graphs ($P_n$)
- Star graphs ($S_n$)
- Triangles and pendant whiskers
- Complete graphs ($K_n$)
- Disconnected components and isolated vertices
- Random Erdos-Renyi graphs

---

## Phase 3: Streaming Simulator & Evaluation Harness

Phase 3 builds a streaming transaction simulator and a reproducible evaluation harness to compare static recomputation against warm-started and heuristic maintenance.

### 1. Transaction Stream Simulator (`ringscope.stream_simulator`)
- Generates deterministic batches of transaction edge insertions with monotonic version tracking.
- Configurable parameters:
  - Batch size (fixed or variable).
  - Arrival orderings (`chronological`, `reverse`, `random_shuffle`).
  - Planted dense ring/cluster injection at specified batch intervals.
  - Fixed seeds for exact reproducibility.
- Emits detailed per-step snapshots (`StreamStepSnapshot`):
  - Batch index, graph version, inserted transaction records, new unique edges.
  - Affected vertices.
  - Current candidate cluster and density.
  - Batch processing latency (ms) and cumulative latency.
  - Number of full recomputations triggered.

### 2. Three Candidate Maintenance Modes
- **Mode A: Full Recomputation (`FullRecomputationMaintainer`)**:
  - Re-executes the densest subgraph solver on the entire active graph after every batch.
  - Serves as the baseline ground truth across all stream steps.
- **Mode B: Warm-Started Recomputation (`WarmStartedMaintainer`)**:
  - Leverages graph monotonicity ($\lambda_t \ge \lambda_{t-1}$ under edge insertions).
  - Skips recomputation on parallel transactions that do not modify graph topology.
  - Warm-starts Goldberg's binary search lower bound at $\lambda_{t-1}$.
- **Mode C: Incremental Heuristic (`IncrementalHeuristicMaintainer`)**:
  - Locally updates candidate cluster membership and density when new edges connect to it.
  - Does *not* falsely assume candidate-adjacent edges are the only way density changes (a disjoint component can become denser).
  - Triggers full recomputations via explicit configurable criteria: periodic intervals, accumulated external edge counts, or sudden hub degree spikes.

### 3. SNAP-Style Real-World Edge-List Importer (`ringscope.importer`)
- Ingests standard Stanford Network Analysis Project (SNAP) edge lists.
- Parses `#` comments, extracted node/edge metadata counts, optional weights, and timestamps.
- Includes offline bundled sample dataset (`get_sample_snap_edgelist()`) with zero external network dependencies required for testing.

### 4. Reproducible Evaluation Suite (`scripts/run_experiments.py`)
Provides 7 automated, reproducible experiments exporting directly to CSV and JSON:
1. `exp1_runtime_vs_size`: Runtime scaling across graph sizes ($N \in [10, 60]$).
2. `exp2_cluster_size_recovery`: Planted cluster recovery metrics vs size ($k \in [3, 12]$).
3. `exp3_cluster_sparsity`: Recovery metrics vs internal edge density ($p_{\text{in}} \in [0.4, 1.0]$).
4. `exp4_background_connectivity`: False-positive candidate overlap vs background noise ($p_{\text{out}} \in [0.02, 0.2]$).
5. `exp5_exact_vs_approx`: Exact Goldberg density compared against Charikar Greedy and Greedy++ approximations, validated against the Brute-Force oracle on small instances.
6. `exp6_streaming_modes`: Detailed comparison of Mode A, Mode B, and Mode C across streaming metrics.
7. `exp7_clusters_and_hubs`: Performance and cluster recovery in graphs with multiple competing clusters and high-degree hubs.

---

## Phase 4: Production REST Backend (`/api/v1`)

Phase 4 delivers a real, high-performance REST backend built on FastAPI and Pydantic v2, exposing the graph engine, algorithms, streaming simulator, and evaluation harness.

### Key Architecture & Engineering Principles
1. **Pydantic v2 Models**: Strict typed schemas for all request payloads and responses with clear validation errors (`HTTP 422`).
2. **Non-Blocking Execution**: CPU-bound computations (Goldberg maximum flow, greedy peeling passes, cycle detection, and benchmark runs) are offloaded from the asyncio event loop using `asyncio.to_thread`.
3. **CORS Support**: Configured for local frontend development across all origins and headers.
4. **Interactive OpenAPI Documentation**: Auto-generated Swagger UI accessible at `/docs` and ReDoc at `/redoc`.
5. **Job Lifecycle Tracking**: Asynchronous and synchronous jobs track states (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`) with runtime and error details.
6. **Reproducible Experiment Storage**: Persists benchmark artifacts to disk in `experiments_output/` as JSON and CSV with download endpoints.

### API v1 Endpoints Summary
| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/api/v1/health` | System health probe, uptime, and active graph/stream/job metrics |
| `POST` | `/api/v1/graphs/generate` | Generate synthetic graphs (planted cluster, ring, random) |
| `POST` | `/api/v1/graphs/import` | Ingest CSV or SNAP formatted edge lists (max 10MB) |
| `GET` | `/api/v1/graphs/{graph_id}` | Retrieve topology statistics, degree metrics, and element lists |
| `POST` | `/api/v1/analysis/run` | Execute densest subgraph (Goldberg, Greedy, Greedy++) or cycle detection |
| `GET` | `/api/v1/analysis/{analysis_id}` | Retrieve status and computed results of an analysis job |
| `POST` | `/api/v1/stream/start` | Initialize streaming candidate maintenance session (Modes A, B, C) |
| `POST` | `/api/v1/stream/step` | Advance stream by ingesting custom or synthetic transaction batches |
| `POST` | `/api/v1/stream/inject-ring` | Ingest a dense cycle or clique into an active stream |
| `POST` | `/api/v1/stream/stop` | Conclude streaming session and retrieve cumulative latency metrics |
| `POST` | `/api/v1/experiments/run` | Trigger reproducible benchmark experiments |
| `GET` | `/api/v1/experiments/{experiment_id}` | Check experiment job status and output file paths |
| `GET` | `/api/v1/experiments/{experiment_id}/results` | Fetch experiment result records as JSON |
| `GET` | `/api/v1/experiments/{experiment_id}/export` | Download benchmark artifacts directly as JSON or CSV |

---

## Setup & Installation

### Prerequisites
- Python 3.12+
- Windows PowerShell or Unix Shell

### 1. Create and Activate Virtual Environment

```bash
# Create local virtual environment
python -m venv .venv

# Activate on Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Activate on Linux / macOS
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -e .
pip install pytest pytest-asyncio httpx ruff
```

#### Key Dependency Versions Recorded:
- `networkx`: 3.7
- `numpy`: 2.5.4
- `scipy`: 1.18.1
- `pandas`: 3.0.6
- `fastapi`: 0.143.0
- `uvicorn`: 0.54.0
- `pydantic`: 2.14.1
- `pytest`: 9.1.1
- `pytest-asyncio`: 1.4.0
- `httpx`: 0.28.1
- `ruff`: 0.17.0

---

## Running the Backend Server

Start the RingScope API backend locally with Uvicorn:

```bash
# Start server with live reload
.venv\Scripts\python -m uvicorn ringscope.api:app --reload --host 127.0.0.1 --port 8000
```

Once running:
- **Interactive OpenAPI Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check**: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## Running Benchmark Experiments

Execute the automated suite of 7 benchmark experiments and generate CSV/JSON artifacts:

```bash
# Run all 7 experiments and output to experiments_output/
.venv\Scripts\python scripts/run_experiments.py --experiments all --out-dir experiments_output

# Run a specific experiment with custom seed
.venv\Scripts\python scripts/run_experiments.py --experiments exp6_streaming_modes --seed 42
```

---

## CLI Usage: Synthetic Graph Generator & Algorithm Comparison

Generate synthetic transaction graphs and inspect topological statistics and densest-subgraph algorithm benchmarks:

```bash
# Basic run with 30 nodes and a planted cluster of 10 nodes
.venv\Scripts\python scripts/generate_graph.py --nodes 30 --cluster-size 10 --p-internal 0.7 --p-external 0.1 --seed 42

# Run side-by-side comparison across all algorithms (Goldberg, Greedy Peeling, Greedy++, and Brute-Force Oracle)
.venv\Scripts\python scripts/generate_graph.py --nodes 12 --cluster-size 5 --p-internal 0.9 --p-external 0.05 --seed 7 --solve-densest

# Export synthetic edge-list directly to CSV
.venv\Scripts\python scripts/generate_graph.py --nodes 25 --cluster-size 8 --csv-out graph_export.csv
```

---

## Phase 5: Interactive Research Dashboard (Frontend)

Phase 5 introduces a full-featured, research-grade web dashboard built with **React 19, Vite, TypeScript, Tailwind CSS v3, Cytoscape.js, and Recharts**, paired with a typed REST API client with zero mock data.

### Dashboard Screens

1. **Overview**: Live topological indicators (current graph nodes $N$, edges $M$, density $\lambda$, connected components), algorithm engine, last measured execution runtime, active streaming session pill, and data provenance badge.
2. **Graph Explorer**: Full interactive canvas powered by Cytoscape.js with zoom, pan, node drag, node selection with degree inspection, candidate cluster highlighting (crimson glow), and automatic sampling protection for graphs with $N > 200$. Supports synthetic graph generation and CSV/SNAP file import.
3. **Algorithm Lab**: Side-by-side solver comparisons running Goldberg's exact max-flow reduction, Charikar greedy peeling, and Greedy++ multi-pass peeling ($T=10$). Includes a comparative metric table, comparative density bar chart, and cluster JSON export/inspection.
4. **Streaming Simulator**: Real-time evaluation of dynamic transaction streams. Start, pause, step (1 or 5 batches), and stop streaming sessions. Supports injecting planted rings or cliques ($K_k$ vs $C_k$) with live candidate tracking across Mode A (Full Recomputation), Mode B (Warm-Started), and Mode C (Incremental Heuristic). Includes batch latency and density progression line charts.
5. **Experiments Suite**: Reproducible execution of 7 empirical benchmark suites directly against the backend harness. Visualizes trial outcomes via interactive Recharts bar charts, tabular results, and direct one-click CSV and JSON exports.
6. **Documentation & Theory**: Mathematical formulations of density $\frac{|E(S)|}{|S|}$, Goldberg's $(s, t)$-cut capacity reduction, Dinic's blocking flow mechanism, Charikar's 2-approximation theorem, Greedy++ load accumulation, and streaming maintenance tradeoffs.

---

## Launching RingScope Locally (PowerShell Commands)

To run the complete full-stack platform, open two PowerShell terminals:

### Terminal 1: Backend Server (FastAPI + Uvicorn)

```powershell
# Navigate to project root
cd "c:\VS code\DAA"

# Start the API server on 127.0.0.1:8000
.venv\Scripts\python -m uvicorn ringscope.api:app --host 127.0.0.1 --port 8000
```

Verify backend health:
```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health'
```

### Terminal 2: Frontend Dashboard (Vite Dev Server)

```powershell
# Navigate to frontend directory
cd "c:\VS code\DAA\frontend"

# (Optional) Install / verify dependencies
npm install

# Start Vite dev server on 127.0.0.1:5173
npm run dev -- --host 127.0.0.1 --port 5173
```

Open your browser to: **[http://127.0.0.1:5173](http://127.0.0.1:5173)**

All API calls (`/api/v1/...`) are automatically proxied from the Vite dev server (`http://127.0.0.1:5173`) directly to the backend (`http://127.0.0.1:8000`).

---

## Frontend Quality Assurance & Build Commands

Run the following commands inside `c:\VS code\DAA\frontend`:

```powershell
cd "c:\VS code\DAA\frontend"

# 1. TypeScript Strict Typecheck (0 errors)
npm run typecheck

# 2. Fast Linter Check (0 errors)
npm run lint

# 3. Vitest Unit Test Suite (100% pass)
npm test

# 4. Vite Production Bundle Build
npm run build
```

---

## Running Automated Tests

Run the full automated backend test suite (157 tests):

```powershell
.venv\Scripts\python -m pytest tests/ -v
```

Run code formatting and linting checks:

```powershell
.venv\Scripts\ruff check ringscope tests scripts
```


