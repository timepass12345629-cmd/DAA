"""
Tests for the FastAPI endpoints (ringscope.api).

Uses httpx.AsyncClient + ASGITransport for in-process async testing.
pytest-asyncio handles coroutine collection.
"""

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from ringscope.api import app

# ---------------------------------------------------------------------------
# Fixture — async client shared across tests in session scope
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    """Async test client using ASGITransport (no network I/O)."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Graph load
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_random_graph(client):
    r = await client.post(
        "/graph/load",
        json={
            "dataset": "random",
            "n_accounts": 10,
            "n_transactions": 20,
            "seed": 1,
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["num_nodes"] > 0
    assert d["num_edges"] > 0


@pytest.mark.asyncio
async def test_load_ring_graph(client):
    r = await client.post(
        "/graph/load",
        json={
            "dataset": "ring",
            "ring_sizes": [3, 4],
            "seed": 7,
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["num_nodes"] >= 7  # 3 + 4 ring nodes + extras


# ---------------------------------------------------------------------------
# Graph export
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_graph(client):
    await client.post(
        "/graph/load",
        json={
            "dataset": "ring",
            "ring_sizes": [3],
            "seed": 7,
        },
    )
    r = await client.get("/graph/export")
    assert r.status_code == 200
    d = r.json()
    assert "nodes" in d
    assert "edges" in d
    assert len(d["nodes"]) >= 3
    assert len(d["edges"]) >= 3


@pytest.mark.asyncio
async def test_add_single_transaction(client):
    await client.post(
        "/graph/load", json={"dataset": "random", "n_accounts": 5, "n_transactions": 5, "seed": 99}
    )
    r = await client.post(
        "/graph/transaction",
        json={
            "source": "NEW_A",
            "target": "NEW_B",
            "amount": 250.0,
            "timestamp": 1_700_000_000.0,
        },
    )
    assert r.status_code == 200
    assert "tx_id" in r.json()


@pytest.mark.asyncio
async def test_add_batch_transactions(client):
    await client.post(
        "/graph/load", json={"dataset": "random", "n_accounts": 5, "n_transactions": 5, "seed": 99}
    )
    r = await client.post(
        "/graph/transactions",
        json=[
            {"source": "AA", "target": "BB", "amount": 10.0},
            {"source": "BB", "target": "CC", "amount": 20.0},
            {"source": "CC", "target": "AA", "amount": 15.0},
        ],
    )
    assert r.status_code == 200
    assert r.json()["added"] == 3


# ---------------------------------------------------------------------------
# Ring detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rings_on_ring_graph(client):
    await client.post("/graph/load", json={"dataset": "ring", "ring_sizes": [3], "seed": 7})
    r = await client.get("/rings")
    assert r.status_code == 200
    d = r.json()
    assert d["summary"]["count"] >= 1


@pytest.mark.asyncio
async def test_rings_filter_min_length(client):
    await client.post("/graph/load", json={"dataset": "ring", "ring_sizes": [3, 5], "seed": 7})
    r = await client.get("/rings?min_length=5")
    assert r.status_code == 200
    for ring in r.json()["rings"]:
        assert ring["length"] >= 5


@pytest.mark.asyncio
async def test_rings_elapsed_ms_present(client):
    await client.post(
        "/graph/load", json={"dataset": "random", "n_accounts": 10, "n_transactions": 15, "seed": 5}
    )
    r = await client.get("/rings")
    assert "elapsed_ms" in r.json()


# ---------------------------------------------------------------------------
# Densest subgraph
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_densest_greedy(client):
    await client.post("/graph/load", json={"dataset": "ring", "ring_sizes": [4], "seed": 3})
    r = await client.get("/densest?algorithm=greedy")
    assert r.status_code == 200
    d = r.json()
    assert "density" in d
    assert d["density"] >= 0


@pytest.mark.asyncio
async def test_densest_exact(client):
    await client.post("/graph/load", json={"dataset": "ring", "ring_sizes": [3], "seed": 3})
    r = await client.get("/densest?algorithm=exact")
    assert r.status_code == 200
    assert r.json()["algorithm"] == "exact_goldberg"


@pytest.mark.asyncio
async def test_densest_invalid_algorithm(client):
    r = await client.get("/densest?algorithm=invalid")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_reset(client):
    r = await client.post("/stream/reset")
    assert r.status_code == 200
    assert r.json()["status"] == "reset"


@pytest.mark.asyncio
async def test_stream_ingest_and_snapshot(client):
    await client.post("/stream/reset")
    r = await client.post(
        "/stream/ingest",
        json={
            "transactions": [
                {"source": "A", "target": "B", "amount": 100.0, "timestamp": 1_700_000_000.0},
                {"source": "B", "target": "C", "amount": 200.0, "timestamp": 1_700_000_001.0},
                {"source": "C", "target": "A", "amount": 150.0, "timestamp": 1_700_000_002.0},
            ],
            "window_size": 3600.0,
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["total_ingested"] == 3
    assert len(d["snapshots"]) == 3

    snap_r = await client.get("/stream/snapshot")
    assert snap_r.status_code == 200
    snap = snap_r.json()
    assert snap["ring_summary"]["count"] >= 1


# ---------------------------------------------------------------------------
# Benchmark experiment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_benchmark_endpoint(client):
    r = await client.get("/experiments/benchmark?ring_sizes=3,4&n_extra=5&seed=42")
    assert r.status_code == 200
    d = r.json()
    assert "planted_rings" in d
    assert "densest_subgraph" in d
    assert d["ring_detection"]["recall_vs_planted"] >= 0


# ---------------------------------------------------------------------------
# Sessions & Persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_save_list_load_delete(client):
    # Load a distinct graph
    await client.post("/graph/load", json={"dataset": "ring", "ring_sizes": [3, 4], "seed": 10})
    # Save graph session
    save_r = await client.post("/graphs/save", json={"graph_id": "test_session_1"})
    assert save_r.status_code == 200
    assert save_r.json()["graph_id"] == "test_session_1"

    # List graphs
    list_r = await client.get("/graphs")
    assert list_r.status_code == 200
    gids = [g["graph_id"] for g in list_r.json()["graphs"]]
    assert "test_session_1" in gids

    # Load back the saved graph session
    load_r = await client.post("/graphs/test_session_1/load")
    assert load_r.status_code == 200
    assert load_r.json()["loaded_graph_id"] == "test_session_1"

    # Delete session
    del_r = await client.delete("/graphs/test_session_1")
    assert del_r.status_code == 200
    assert del_r.json()["deleted"] is True

    # 404 on re-load
    err_r = await client.post("/graphs/test_session_1/load")
    assert err_r.status_code == 404
