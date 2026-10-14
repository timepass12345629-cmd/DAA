"""
ringscope.api — FastAPI server for RingScope.

Endpoints
---------
GET  /health                  — liveness probe
GET  /graph                   — current graph stats
POST /graph/load              — load a synthetic or supplied graph
POST /graph/transaction       — add a single transaction
POST /graph/transactions      — batch-add transactions
GET  /rings                   — detect rings in current graph
GET  /densest                 — densest-subgraph analysis
POST /stream/ingest           — ingest streaming transaction
GET  /stream/snapshot         — current streaming window snapshot
POST /stream/reset            — reset streaming window
GET  /experiments/benchmark   — run peeling-vs-exact benchmark on planted rings
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ringscope.algorithms.cycle_detection import detect_rings, ring_summary
from ringscope.algorithms.densest_subgraph import densest_subgraph
from ringscope.algorithms.streaming import StreamEdge, StreamingRingDetector
from ringscope.api_v1 import router as api_v1_router
from ringscope.data import random_graph, ring_graph
from ringscope.graph import TransactionGraph
from ringscope.storage import GraphStore

app = FastAPI(
    title="RingScope REST API",
    description=(
        "Financial transaction graph analysis platform — cycle/ring detection, "
        "densest subgraph discovery (Goldberg flow, Charikar greedy, Greedy++), "
        "streaming candidate maintenance, and reproducible experiment evaluation harness."
    ),
    version="0.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# State (active graph, streaming detector, SQLite session store)
# ---------------------------------------------------------------------------

_current_graph: TransactionGraph = TransactionGraph()
_streamer: StreamingRingDetector = StreamingRingDetector()
_store: GraphStore = GraphStore("ringscope.db")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TransactionIn(BaseModel):
    source: str = Field(..., description="Source account ID")
    target: str = Field(..., description="Target account ID")
    amount: float = Field(..., gt=0, description="Transaction amount (positive)")
    timestamp: Optional[float] = Field(None, description="Unix timestamp; defaults to now")
    tx_id: Optional[str] = Field(None, description="Optional transaction ID")


class GraphLoadRequest(BaseModel):
    dataset: str = Field("random", description="'random' | 'ring'")
    n_accounts: int = Field(30, ge=2, le=500)
    n_transactions: int = Field(80, ge=1, le=2000)
    seed: int = Field(42)
    ring_sizes: Optional[list[int]] = Field(None)


class StreamIngestRequest(BaseModel):
    transactions: list[TransactionIn]
    window_size: float = Field(3600.0, gt=0)


class GraphSaveRequest(BaseModel):
    graph_id: Optional[str] = Field(None, description="Optional custom session/graph ID")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _graph_stats(tg: TransactionGraph) -> dict:
    import networkx as nx

    g = tg.graph
    is_dir = g.is_directed()
    return {
        "name": tg.name,
        "num_nodes": tg.num_nodes,
        "num_edges": tg.num_edges,
        "is_strongly_connected": (
            nx.is_strongly_connected(g) if is_dir else nx.is_connected(g)
        )
        if tg.num_nodes > 0
        else False,
        "num_weakly_connected_components": (
            nx.number_weakly_connected_components(g)
            if is_dir
            else nx.number_connected_components(g)
        )
        if tg.num_nodes > 0
        else 0,
        "density": nx.density(g),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Meta"])
def health() -> dict:
    return {"status": "ok", "version": "0.1.0", "timestamp": time.time()}


@app.get("/graph", tags=["Graph"])
def get_graph_stats() -> dict:
    return _graph_stats(_current_graph)


@app.get("/graph/export", tags=["Graph"])
def export_graph() -> dict:
    """Return the full node and edge list for graph visualization."""
    return _current_graph.to_dict()


@app.post("/graph/load", tags=["Graph"])
def load_graph(req: GraphLoadRequest) -> dict:
    global _current_graph
    if req.dataset == "ring":
        sizes = req.ring_sizes or [3, 4, 5]
        _current_graph = ring_graph(ring_sizes=sizes, seed=req.seed)
    else:
        _current_graph = random_graph(
            n_accounts=req.n_accounts,
            n_transactions=req.n_transactions,
            seed=req.seed,
        )
    return {"loaded": req.dataset, **_graph_stats(_current_graph)}


@app.post("/graph/transaction", tags=["Graph"])
def add_transaction(tx: TransactionIn) -> dict:
    ts = tx.timestamp if tx.timestamp is not None else time.time()
    tx_id = _current_graph.add_transaction(tx.source, tx.target, tx.amount, ts, tx.tx_id)
    return {"tx_id": tx_id, **_graph_stats(_current_graph)}


@app.post("/graph/transactions", tags=["Graph"])
def add_transactions(txs: list[TransactionIn]) -> dict:
    for tx in txs:
        ts = tx.timestamp if tx.timestamp is not None else time.time()
        _current_graph.add_transaction(tx.source, tx.target, tx.amount, ts, tx.tx_id)
    return {"added": len(txs), **_graph_stats(_current_graph)}


@app.get("/rings", tags=["Analysis"])
def get_rings(
    min_length: int = Query(2, ge=2),
    max_length: Optional[int] = Query(None, ge=2),
    min_amount: float = Query(0.0, ge=0),
    max_rings: int = Query(50, ge=1, le=500),
) -> dict:
    t0 = time.perf_counter()
    rings = detect_rings(
        _current_graph.graph,
        min_length=min_length,
        max_length=max_length,
        min_amount=min_amount,
        max_rings=max_rings,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return {
        "rings": [r.to_dict() for r in rings],
        "summary": ring_summary(rings),
        "elapsed_ms": round(elapsed_ms, 3),
    }


@app.get("/densest", tags=["Analysis"])
def get_densest_subgraph(
    algorithm: str = Query(
        "greedy",
        description="'greedy' | 'exact' | 'greedy_peeling' | 'greedy_plus_plus'",
    ),
) -> dict:
    valid_algos = ("greedy", "exact", "greedy_peeling", "greedy_plus_plus", "greedy++")
    if algorithm not in valid_algos:
        raise HTTPException(status_code=400, detail=f"algorithm must be one of {valid_algos}")
    t0 = time.perf_counter()
    ds = densest_subgraph(_current_graph.graph, algorithm=algorithm)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return {**ds.to_dict(), "elapsed_ms": round(elapsed_ms, 3)}


@app.post("/stream/ingest", tags=["Streaming"])
def stream_ingest(req: StreamIngestRequest) -> dict:
    global _streamer
    if _streamer.window_size != req.window_size:
        _streamer = StreamingRingDetector(window_size=req.window_size)

    snapshots = []
    for tx in req.transactions:
        ts = tx.timestamp if tx.timestamp is not None else time.time()
        edge = StreamEdge(
            src=tx.source,
            dst=tx.target,
            amount=tx.amount,
            timestamp=ts,
            tx_id=tx.tx_id or "",
        )
        snap = _streamer.ingest(edge)
        snapshots.append(
            {
                "window_start": snap.window_start,
                "window_end": snap.window_end,
                "num_nodes": snap.num_nodes,
                "num_edges": snap.num_edges,
                "ring_count": snap.ring_summary.get("count", 0),
                "densest_density": snap.densest_subgraph.get("density", 0.0),
                "processing_time_ms": round(snap.processing_time_ms, 3),
            }
        )
    return {"snapshots": snapshots, "total_ingested": len(req.transactions)}


@app.get("/stream/snapshot", tags=["Streaming"])
def stream_snapshot() -> dict:
    snap = _streamer.current_snapshot()
    return {
        "window_start": snap.window_start,
        "window_end": snap.window_end,
        "num_nodes": snap.num_nodes,
        "num_edges": snap.num_edges,
        "rings": snap.rings,
        "ring_summary": snap.ring_summary,
        "densest_subgraph": snap.densest_subgraph,
    }


@app.post("/stream/reset", tags=["Streaming"])
def stream_reset() -> dict:
    _streamer.reset()
    return {"status": "reset"}


@app.get("/experiments/benchmark", tags=["Experiments"])
def benchmark_densest(
    ring_sizes: str = Query("3,4,5", description="Comma-separated ring sizes"),
    n_extra: int = Query(20, ge=0, le=200),
    seed: int = Query(7),
) -> dict:
    """
    Run greedy vs exact densest-subgraph on a planted-ring benchmark graph.
    Returns both results and timings for comparison.
    """
    sizes = [int(s.strip()) for s in ring_sizes.split(",") if s.strip().isdigit()]
    tg = ring_graph(ring_sizes=sizes, n_extra_edges=n_extra, seed=seed)
    g = tg.graph
    planted = g.graph.get("planted_rings", [])

    results = {}
    for algo in ("greedy", "exact"):
        t0 = time.perf_counter()
        ds = densest_subgraph(g, algorithm=algo)
        elapsed = (time.perf_counter() - t0) * 1000
        results[algo] = {**ds.to_dict(), "elapsed_ms": round(elapsed, 3)}

    rings = detect_rings(g, max_rings=50)
    detected_sets = [frozenset(r.nodes) for r in rings]
    planted_sets = [frozenset(p) for p in planted]
    recall = sum(1 for p in planted_sets if p in detected_sets) / max(len(planted_sets), 1)

    return {
        "graph_stats": _graph_stats(tg),
        "planted_rings": [list(p) for p in planted],
        "ring_detection": {
            "detected": len(rings),
            "recall_vs_planted": round(recall, 4),
        },
        "densest_subgraph": results,
    }


@app.get("/experiments/streaming-profile", tags=["Experiments"])
def profile_streaming(
    n_transactions: int = Query(200, ge=10, le=2000),
    window_size: float = Query(1800.0, ge=10.0),
    seed: int = Query(99),
) -> dict:
    """
    Profile streaming transaction ingestion throughput (TPS) and latency
    comparing incremental ring cache vs full recomputation.
    """
    from ringscope.evaluation import benchmark_streaming_throughput

    inc = benchmark_streaming_throughput(
        n_transactions=n_transactions,
        window_size=window_size,
        incremental=True,
        seed=seed,
    )
    full = benchmark_streaming_throughput(
        n_transactions=n_transactions,
        window_size=window_size,
        incremental=False,
        seed=seed,
    )
    return {
        "incremental": inc.to_dict(),
        "full": full.to_dict(),
        "speedup": round(full.total_time_ms / max(inc.total_time_ms, 0.001), 2),
    }


# ---------------------------------------------------------------------------
# Sessions & Persistence
# ---------------------------------------------------------------------------


@app.get("/graphs", tags=["Sessions"])
def list_saved_graphs() -> dict:
    return {"graphs": _store.list_graphs()}


@app.post("/graphs/save", tags=["Sessions"])
def save_current_graph(req: GraphSaveRequest = GraphSaveRequest()) -> dict:
    gid = _store.save_graph(_current_graph, graph_id=req.graph_id)
    return {"graph_id": gid, "saved": True, **_graph_stats(_current_graph)}


@app.post("/graphs/{graph_id}/load", tags=["Sessions"])
def load_saved_graph(graph_id: str) -> dict:
    global _current_graph
    try:
        _current_graph = _store.load_graph(graph_id)
        return {"loaded_graph_id": graph_id, **_graph_stats(_current_graph)}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Graph '{graph_id}' not found")


@app.delete("/graphs/{graph_id}", tags=["Sessions"])
def delete_saved_graph(graph_id: str) -> dict:
    success = _store.delete_graph(graph_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Graph '{graph_id}' not found")
    return {"deleted": True, "graph_id": graph_id}
