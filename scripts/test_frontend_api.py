"""Integration verification script testing frontend proxy against backend."""

import json
import urllib.request

BASE_URL = "http://localhost:5173/api/v1"


def post(url, data):
    req = urllib.request.Request(
        f"{BASE_URL}{url}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get(url):
    req = urllib.request.Request(f"{BASE_URL}{url}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    print("1. Testing Health...")
    health = get("/health")
    assert health["status"] == "ok"
    print(f"   Health OK: version={health['version']}")

    print("2. Generating Graph...")
    graph = post(
        "/graphs/generate",
        {
            "generator_type": "planted_cluster",
            "num_nodes": 30,
            "cluster_size": 6,
            "p_internal": 0.85,
            "p_external": 0.05,
            "seed": 42,
        },
    )
    graph_id = graph["graph_id"]
    print(f"   Graph generated: {graph_id}, N={graph['num_nodes']}, M={graph['num_edges']}")

    print("3. Fetching graph elements...")
    detailed = get(f"/graphs/{graph_id}?include_elements=true")
    assert len(detailed["nodes"]) == graph["num_nodes"]
    print(
        f"   Fetched {len(detailed['nodes'])} nodes and "
        f"{len(detailed['edges'])} edges for Cytoscape.js"
    )

    print("4. Running Goldberg Densest Subgraph...")
    res_gold = post("/analysis/run", {"graph_id": graph_id, "algorithm": "goldberg"})
    gold_data = res_gold["results"]["densest_subgraph"]["goldberg"]
    print(
        f"   Goldberg Density: {gold_data['density']:.4f}, "
        f"Nodes: {len(gold_data['nodes'])}, Time: {gold_data['time_ms']:.2f}ms"
    )

    print("5. Running Greedy Peeling...")
    res_peel = post("/analysis/run", {"graph_id": graph_id, "algorithm": "greedy_peeling"})
    peel_data = res_peel["results"]["densest_subgraph"]["greedy_peeling"]
    print(
        f"   Peeling Density: {peel_data['density']:.4f}, "
        f"Nodes: {len(peel_data['nodes'])}, Time: {peel_data['time_ms']:.2f}ms"
    )

    print("6. Running Greedy++...")
    res_gpp = post(
        "/analysis/run",
        {"graph_id": graph_id, "algorithm": "greedy_plus_plus", "params": {"iterations": 10}},
    )
    gpp_data = res_gpp["results"]["densest_subgraph"]["greedy_plus_plus"]
    print(
        f"   Greedy++ Density: {gpp_data['density']:.4f}, "
        f"Nodes: {len(gpp_data['nodes'])}, Time: {gpp_data['time_ms']:.2f}ms"
    )

    print("7. Testing Streaming Simulator...")
    stream = post(
        "/stream/start",
        {
            "graph_id": graph_id,
            "mode": "incremental_heuristic",
            "algorithm": "greedy_peeling",
            "batch_size": 5,
        },
    )
    stream_id = stream["stream_id"]
    print(f"   Stream started: {stream_id}")

    step = post("/stream/step", {"stream_id": stream_id, "num_synthetic_batches": 2})
    print(
        f"   Step executed: snapshots={len(step['snapshots'])}, "
        f"current_density={step['current_density']:.4f}"
    )

    inject = post(
        "/stream/inject-ring",
        {"stream_id": stream_id, "ring_size": 6, "complete_clique": True, "amount": 500.0},
    )
    print(
        f"   Ring injected: nodes={len(inject['current_candidate_nodes'])}, "
        f"density={inject['current_density']:.4f}"
    )

    stop = post("/stream/stop", {"stream_id": stream_id})
    print(f"   Stream stopped: status={stop['status']}")

    print("8. Running Empirical Experiment...")
    exp = post(
        "/experiments/run",
        {"experiment_name": "exp5_exact_vs_approx", "params": {"sizes": [8, 10]}},
    )
    exp_id = exp["experiment_id"]
    print(f"   Experiment job created: {exp_id}, status={exp['status']}")

    results = get(f"/experiments/{exp_id}/results")
    print(f"   Experiment results fetched: {len(results)} rows")

    print("9. Verifying Export Endpoint...")
    csv_url = f"{BASE_URL}/experiments/{exp_id}/export?format=csv"
    with urllib.request.urlopen(csv_url) as csv_resp:
        csv_data = csv_resp.read().decode("utf-8")
        assert len(csv_data) > 0
        print(f"   CSV export verified: {len(csv_data.splitlines())} lines")

    print("\nALL FRONTEND-TO-BACKEND INTEGRATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
