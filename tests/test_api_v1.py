"""
Comprehensive integration tests for RingScope REST API v1 (/api/v1).

Tests all endpoints:
- GET  /api/v1/health
- POST /api/v1/graphs/generate
- POST /api/v1/graphs/import
- GET  /api/v1/graphs/{graph_id}
- POST /api/v1/analysis/run
- GET  /api/v1/analysis/{analysis_id}
- POST /api/v1/stream/start
- POST /api/v1/stream/step
- POST /api/v1/stream/inject-ring
- POST /api/v1/stream/stop
- POST /api/v1/experiments/run
- GET  /api/v1/experiments/{experiment_id}
- GET  /api/v1/experiments/{experiment_id}/results
- GET  /api/v1/experiments/{experiment_id}/export
"""

import asyncio

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from ringscope.api import app


@pytest_asyncio.fixture
async def client():
    """Async test client using in-memory ASGI transport."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Health Probe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_v1_health(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.4.0"
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert "active_graphs" in data
    assert "active_streams" in data
    assert "active_jobs" in data


# ---------------------------------------------------------------------------
# Graph Generation & Import
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_v1_graph_generate_planted_cluster(client):
    payload = {
        "generator_type": "planted_cluster",
        "num_nodes": 15,
        "cluster_size": 5,
        "p_internal": 0.9,
        "p_external": 0.05,
        "seed": 42,
    }
    r = await client.post("/api/v1/graphs/generate", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["num_nodes"] == 15
    assert data["num_edges"] > 0
    assert data["generator_type"] == "planted_cluster"
    assert data["planted_cluster"] is not None
    assert data["planted_cluster"]["size"] == 5
    assert "graph_id" in data
    assert "degree_stats" in data


@pytest.mark.asyncio
async def test_api_v1_graph_generate_validation_error(client):
    # num_nodes below minimum (ge=2)
    payload = {
        "generator_type": "planted_cluster",
        "num_nodes": 1,
    }
    r = await client.post("/api/v1/graphs/generate", json=payload)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_api_v1_graph_import_csv(client):
    csv_data = (
        "source,target,amount,timestamp\n"
        "Alice,Bob,100,1000\n"
        "Bob,Charlie,200,1001\n"
        "Charlie,Alice,300,1002"
    )
    payload = {
        "content": csv_data,
        "format": "csv",
        "graph_id": "test_imported_csv",
    }
    r = await client.post("/api/v1/graphs/import", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["graph_id"] == "test_imported_csv"
    assert data["num_nodes"] == 3
    assert data["num_edges"] == 3


@pytest.mark.asyncio
async def test_api_v1_graph_import_snap(client):
    snap_data = "# Directed Node Graph\n# Nodes: 3 Edges: 3\n0 1\n1 2\n2 0\n"
    payload = {
        "content": snap_data,
        "format": "snap",
        "graph_id": "test_imported_snap",
    }
    r = await client.post("/api/v1/graphs/import", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["graph_id"] == "test_imported_snap"
    assert data["num_nodes"] == 3
    assert data["num_edges"] == 3


@pytest.mark.asyncio
async def test_api_v1_graph_import_empty_error(client):
    r = await client.post("/api/v1/graphs/import", json={"content": "  ", "format": "csv"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_api_v1_get_graph_and_elements(client):
    # Generate graph
    gen_r = await client.post(
        "/api/v1/graphs/generate",
        json={"generator_type": "random", "num_nodes": 6, "seed": 10},
    )
    gid = gen_r.json()["graph_id"]

    # Fetch without elements
    r1 = await client.get(f"/api/v1/graphs/{gid}")
    assert r1.status_code == 200
    assert r1.json()["nodes"] is None
    assert r1.json()["edges"] is None

    # Fetch with elements
    r2 = await client.get(f"/api/v1/graphs/{gid}?include_elements=true")
    assert r2.status_code == 200
    assert len(r2.json()["nodes"]) == 6
    assert isinstance(r2.json()["edges"], list)


@pytest.mark.asyncio
async def test_api_v1_get_graph_not_found(client):
    r = await client.get("/api/v1/graphs/non_existent_graph_xyz")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Analysis & Algorithms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_v1_analysis_goldberg_densest(client):
    # Create triangle + pendant
    csv_data = "src,dst\nA,B\nB,C\nC,A\nC,D"
    gen_r = await client.post(
        "/api/v1/graphs/import",
        json={"content": csv_data, "format": "csv"},
    )
    gid = gen_r.json()["graph_id"]

    run_r = await client.post(
        "/api/v1/analysis/run",
        json={
            "graph_id": gid,
            "analysis_type": "densest_subgraph",
            "algorithm": "goldberg",
        },
    )
    assert run_r.status_code == 200
    data = run_r.json()
    assert data["status"] == "COMPLETED"
    assert data["results"] is not None
    assert "densest_subgraph" in data["results"]
    gold = data["results"]["densest_subgraph"]["goldberg"]
    assert gold["density"] == 1.0  # Maximum density is 1.0
    assert set(gold["nodes"]).issuperset({"A", "B", "C"})


@pytest.mark.asyncio
async def test_api_v1_analysis_all_algorithms_and_cycle_detection(client):
    csv_data = "src,dst\n1,2\n2,3\n3,1"
    gen_r = await client.post(
        "/api/v1/graphs/import",
        json={"content": csv_data, "format": "csv"},
    )
    gid = gen_r.json()["graph_id"]

    run_r = await client.post(
        "/api/v1/analysis/run",
        json={
            "graph_id": gid,
            "analysis_type": "both",
            "algorithm": "all",
        },
    )
    assert run_r.status_code == 200
    data = run_r.json()
    assert data["status"] == "COMPLETED"
    res = data["results"]
    assert "goldberg" in res["densest_subgraph"]
    assert "greedy_peeling" in res["densest_subgraph"]
    assert "greedy_plus_plus" in res["densest_subgraph"]
    assert "cycle_detection" in res
    assert res["cycle_detection"]["summary"]["count"] >= 1


@pytest.mark.asyncio
async def test_api_v1_analysis_async_execution(client):
    csv_data = "src,dst\nX,Y\nY,Z\nZ,X"
    gen_r = await client.post(
        "/api/v1/graphs/import",
        json={"content": csv_data, "format": "csv"},
    )
    gid = gen_r.json()["graph_id"]

    run_r = await client.post(
        "/api/v1/analysis/run",
        json={
            "graph_id": gid,
            "analysis_type": "densest_subgraph",
            "algorithm": "greedy_peeling",
            "async_execution": True,
        },
    )
    assert run_r.status_code == 202
    aid = run_r.json()["analysis_id"]

    # Poll status
    for _ in range(10):
        await asyncio.sleep(0.05)
        poll_r = await client.get(f"/api/v1/analysis/{aid}")
        if poll_r.json()["status"] == "COMPLETED":
            break

    final_r = await client.get(f"/api/v1/analysis/{aid}")
    assert final_r.status_code == 200
    assert final_r.json()["status"] == "COMPLETED"
    assert "densest_subgraph" in final_r.json()["results"]


@pytest.mark.asyncio
async def test_api_v1_analysis_not_found(client):
    r = await client.get("/api/v1/analysis/non_existent_analysis_abc")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Streaming Simulation & Maintenance Modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_v1_stream_lifecycle_and_modes(client):
    # 1. Start stream in Mode A (full recomputation)
    start_r = await client.post(
        "/api/v1/stream/start",
        json={
            "mode": "full_recomputation",
            "algorithm": "greedy_peeling",
            "batch_size": 3,
        },
    )
    assert start_r.status_code == 201
    sid = start_r.json()["stream_id"]
    assert start_r.json()["status"] == "ACTIVE"

    # 2. Step with synthetic batch
    step1_r = await client.post(
        "/api/v1/stream/step",
        json={"stream_id": sid, "num_synthetic_batches": 1},
    )
    assert step1_r.status_code == 200
    assert len(step1_r.json()["snapshots"]) == 1
    assert step1_r.json()["total_transactions"] == 3

    # 3. Inject a ring of 4 vertices
    inj_r = await client.post(
        "/api/v1/stream/inject-ring",
        json={
            "stream_id": sid,
            "ring_size": 4,
            "ring_nodes": ["R0", "R1", "R2", "R3"],
            "amount": 250.0,
        },
    )
    assert inj_r.status_code == 200
    assert len(inj_r.json()["snapshots"]) == 1
    assert inj_r.json()["current_density"] >= 1.0

    # 4. Step with custom transactions
    custom_txs = [
        {"source": "R0", "target": "R2", "amount": 100.0},
        {"source": "R1", "target": "R3", "amount": 100.0},
    ]
    step2_r = await client.post(
        "/api/v1/stream/step",
        json={"stream_id": sid, "transactions": custom_txs},
    )
    assert step2_r.status_code == 200
    assert step2_r.json()["total_transactions"] == 9  # 3 + 4 + 2

    # 5. Stop stream
    stop_r = await client.post(
        "/api/v1/stream/stop",
        json={"stream_id": sid},
    )
    assert stop_r.status_code == 200
    assert stop_r.json()["status"] == "STOPPED"
    assert stop_r.json()["total_batches"] == 3
    assert stop_r.json()["total_transactions"] == 9

    # 6. Step on stopped stream raises 400
    err_r = await client.post(
        "/api/v1/stream/step",
        json={"stream_id": sid, "num_synthetic_batches": 1},
    )
    assert err_r.status_code == 400


@pytest.mark.asyncio
async def test_api_v1_stream_warm_started_and_heuristic_start(client):
    # Mode B
    r_b = await client.post(
        "/api/v1/stream/start",
        json={"mode": "warm_started_recomputation", "algorithm": "goldberg"},
    )
    assert r_b.status_code == 201
    assert r_b.json()["mode"] == "warm_started_recomputation"

    # Mode C
    r_c = await client.post(
        "/api/v1/stream/start",
        json={
            "mode": "incremental_heuristic",
            "algorithm": "greedy_peeling",
            "config": {"recompute_interval": 5, "external_edge_threshold": 3},
        },
    )
    assert r_c.status_code == 201
    assert r_c.json()["mode"] == "incremental_heuristic"


# ---------------------------------------------------------------------------
# Experiments & Benchmark Harness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_v1_experiment_run_and_results(client):
    # Execute small benchmark experiment synchronously
    run_r = await client.post(
        "/api/v1/experiments/run",
        json={
            "experiment_name": "exp1_runtime_vs_size",
            "params": {"sizes": [8, 12]},
            "seed": 99,
        },
    )
    assert run_r.status_code == 200
    data = run_r.json()
    eid = data["experiment_id"]
    assert data["status"] == "COMPLETED"
    assert len(data["output_files"]) == 2

    # Check job status
    job_r = await client.get(f"/api/v1/experiments/{eid}")
    assert job_r.status_code == 200
    assert job_r.json()["status"] == "COMPLETED"

    # Get results list
    res_r = await client.get(f"/api/v1/experiments/{eid}/results")
    assert res_r.status_code == 200
    results_list = res_r.json()
    assert isinstance(results_list, list)
    assert len(results_list) == 2
    assert results_list[0]["num_nodes"] == 8
    assert results_list[1]["num_nodes"] == 12

    # Export JSON
    exp_json = await client.get(f"/api/v1/experiments/{eid}/export?format=json")
    assert exp_json.status_code == 200
    assert "application/json" in exp_json.headers["content-type"]
    assert len(exp_json.content) > 0

    # Export CSV
    exp_csv = await client.get(f"/api/v1/experiments/{eid}/export?format=csv")
    assert exp_csv.status_code == 200
    assert "text/csv" in exp_csv.headers["content-type"]
    assert b"runtime_vs_graph_size" in exp_csv.content


@pytest.mark.asyncio
async def test_api_v1_experiment_not_found(client):
    r = await client.get("/api/v1/experiments/non_existent_exp_123")
    assert r.status_code == 404
