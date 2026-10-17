"""
Tests for ringscope.algorithms.greedy_plus_plus (Greedy++ iterative peeling).
"""

import pytest

from ringscope.algorithms.greedy_plus_plus import greedy_plus_plus
from ringscope.graph import TransactionGraph


def test_greedy_plus_plus_empty_and_isolated():
    tg_empty = TransactionGraph()
    res_empty = greedy_plus_plus(tg_empty, iterations=5)
    assert res_empty.density == pytest.approx(0.0)
    assert res_empty.nodes == []

    tg_iso = TransactionGraph()
    tg_iso.add_account("U")
    res_iso = greedy_plus_plus(tg_iso, iterations=3)
    assert res_iso.density == pytest.approx(0.0)


def test_greedy_plus_plus_invalid_iterations():
    tg = TransactionGraph()
    tg.add_transaction("A", "B")
    with pytest.raises(ValueError, match=">= 1"):
        greedy_plus_plus(tg, iterations=0)


def test_greedy_plus_plus_triangle_and_complete():
    # Triangle
    tg_tri = TransactionGraph()
    tg_tri.add_transaction("A", "B")
    tg_tri.add_transaction("B", "C")
    tg_tri.add_transaction("C", "A")

    res_tri = greedy_plus_plus(tg_tri, iterations=5)
    assert res_tri.density == pytest.approx(1.0)
    assert set(res_tri.nodes) == {"A", "B", "C"}
    assert res_tri.edge_count == 3

    # K4
    tg_k4 = TransactionGraph()
    nodes = ["1", "2", "3", "4"]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            tg_k4.add_transaction(nodes[i], nodes[j])

    res_k4 = greedy_plus_plus(tg_k4, iterations=5)
    assert res_k4.density == pytest.approx(1.5)
    assert set(res_k4.nodes) == set(nodes)
    assert res_k4.edge_count == 6


def test_greedy_plus_plus_planted_dense_component():
    # Planted K4 in a 12-node sparse graph
    tg = TransactionGraph()
    for i in range(12):
        tg.add_account(f"N{i}")
    for i in range(4):
        for j in range(i + 1, 4):
            tg.add_transaction(f"N{i}", f"N{j}")
    for i in range(4, 11):
        tg.add_transaction(f"N{i}", f"N{i + 1}")
    tg.add_transaction("N3", "N4")

    res = greedy_plus_plus(tg, iterations=10)
    assert res.density == pytest.approx(1.5)
    assert set(res.nodes) == {"N0", "N1", "N2", "N3"}
    assert res.iterations == 10
    assert 1 <= res.best_iteration <= 10


def test_greedy_plus_plus_reference_and_to_dict():
    tg = TransactionGraph()
    tg.add_transaction("A", "B")
    res = greedy_plus_plus(tg, iterations=3)
    d = res.to_dict()
    assert "Boob et al." in d["reference"]
    assert d["iterations"] == 3
    assert d["algorithm"] == "greedy_plus_plus"


def test_greedy_plus_plus_iterations_1_matches_charikar():
    """Verify that when iterations=1, Greedy++ exactly matches Charikar greedy peeling."""
    from ringscope.algorithms.greedy_peeling import greedy_peeling
    from ringscope.data import generate_planted_cluster_graph

    # Test on multiple graphs: random planted cluster
    res_graph = generate_planted_cluster_graph(
        n_total=25, cluster_size=6, p_internal=0.7, p_external=0.1, seed=123
    )
    tg = res_graph.graph

    res_peel = greedy_peeling(tg)
    res_gpp_1 = greedy_plus_plus(tg, iterations=1)

    assert res_gpp_1.density == pytest.approx(res_peel.density)
    assert res_gpp_1.edge_count == res_peel.edge_count
    assert res_gpp_1.node_count == res_peel.node_count
    assert set(res_gpp_1.nodes) == set(res_peel.nodes)


def test_greedy_plus_plus_heap_stale_handling_and_degree_updates():
    """
    Verify that multiple passes correctly update loads and handle
    degree changes via lazy heap.
    """
    tg = TransactionGraph()
    # Star graph connected to a cycle
    for i in range(1, 6):
        tg.add_transaction("HUB", f"LEAF_{i}")
    for i in range(1, 5):
        tg.add_transaction(f"C_{i}", f"C_{i + 1}")
    tg.add_transaction("C_5", "C_1")
    tg.add_transaction("HUB", "C_1")

    res = greedy_plus_plus(tg, iterations=5)
    assert res.density >= 1.0  # Cycle has density 5/5 = 1.0
    assert res.iterations == 5
    assert res.edge_count > 0
    assert len(res.nodes) > 0


def test_greedy_plus_plus_multi_pass_monotonicity():
    """Verify that multi-pass density is >= single-pass Charikar density."""
    from ringscope.algorithms.greedy_peeling import greedy_peeling
    from ringscope.data import generate_planted_cluster_graph

    res_graph = generate_planted_cluster_graph(
        n_total=30, cluster_size=8, p_internal=0.8, p_external=0.05, seed=456
    )
    tg = res_graph.graph

    res_peel = greedy_peeling(tg)
    res_gpp = greedy_plus_plus(tg, iterations=10)

    # Greedy++ can only achieve equal or higher density than pass 1
    assert res_gpp.density >= res_peel.density - 1e-9
