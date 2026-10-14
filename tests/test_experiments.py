"""
Tests for ringscope.experiments (All 7 experiment suites).
"""

from ringscope.experiments import (
    run_exp_background_connectivity,
    run_exp_cluster_size_vs_recovery,
    run_exp_cluster_sparsity_vs_recovery,
    run_exp_exact_vs_approx_density,
    run_exp_multiple_clusters_and_hubs,
    run_exp_runtime_vs_graph_size,
    run_exp_streaming_modes_comparison,
)


def test_exp_runtime_vs_graph_size():
    records = run_exp_runtime_vs_graph_size(sizes=(6, 10))
    assert len(records) == 2
    for r in records:
        assert r["num_nodes"] in (6, 10)
        assert r["greedy_peeling_ms"] >= 0.0
        assert r["greedy_plus_plus_ms"] >= 0.0


def test_exp_cluster_size_vs_recovery():
    records = run_exp_cluster_size_vs_recovery(n_total=16, cluster_sizes=(4, 6))
    assert len(records) == 2
    for r in records:
        assert 0.0 <= r["goldberg_f1"] <= 1.0


def test_exp_cluster_sparsity_vs_recovery():
    records = run_exp_cluster_sparsity_vs_recovery(
        n_total=16, cluster_size=4, p_in_values=(0.5, 0.9)
    )
    assert len(records) == 2
    for r in records:
        assert 0.0 <= r["recovery_f1"] <= 1.0


def test_exp_background_connectivity():
    records = run_exp_background_connectivity(
        n_total=16, cluster_size=4, p_out_values=(0.05, 0.2)
    )
    assert len(records) == 2
    for r in records:
        assert 0.0 <= r["f1"] <= 1.0


def test_exp_exact_vs_approx_density():
    records = run_exp_exact_vs_approx_density(sizes=(6, 8))
    assert len(records) == 2
    for r in records:
        assert r["optimal_density"] >= r["greedy_density"] - 1e-6
        assert r["greedy_approx_ratio"] >= 0.5 - 1e-6


def test_exp_streaming_modes_comparison():
    records = run_exp_streaming_modes_comparison(
        n_background_accounts=10,
        n_background_transactions=15,
        batch_size=3,
        planted_cluster_size=4,
    )
    assert len(records) == 3
    modes = {r["mode"] for r in records}
    assert modes == {
        "full_recomputation",
        "warm_started_recomputation",
        "incremental_heuristic",
    }


def test_exp_multiple_clusters_and_hubs():
    records = run_exp_multiple_clusters_and_hubs()
    assert len(records) == 1
    r = records[0]
    # Optimal cluster C1 has density 2.0; Goldberg and greedy should achieve density 2.0
    assert r["goldberg_density"] >= 1.99
    assert r["goldberg_c1_f1"] == 1.0
