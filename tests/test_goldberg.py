"""
Tests for ringscope.algorithms.goldberg (Goldberg's flow-based densest subgraph).
"""

import pytest

from ringscope.algorithms.goldberg import (
    goldberg_decision_threshold,
    goldberg_densest_subgraph,
)
from ringscope.graph import TransactionGraph


def test_goldberg_decision_triangle():
    # Triangle: 3 nodes, 3 edges -> density = 3 / 3 = 1.0
    tg = TransactionGraph()
    tg.add_transaction("A", "B")
    tg.add_transaction("B", "C")
    tg.add_transaction("C", "A")

    # For g = 0.5, density 1.0 > 0.5 -> True
    res_below = goldberg_decision_threshold(tg, g=0.5)
    assert res_below.has_denser_subgraph is True
    assert set(res_below.candidate_nodes) == {"A", "B", "C"}
    assert res_below.candidate_density == pytest.approx(1.0)
    assert res_below.cut_value < res_below.theoretical_cut_bound

    # For g = 1.2, max density 1.0 < 1.2 -> False
    res_above = goldberg_decision_threshold(tg, g=1.2)
    assert res_above.has_denser_subgraph is False


def test_goldberg_decision_negative_g_raises():
    tg = TransactionGraph()
    tg.add_transaction("A", "B")
    with pytest.raises(ValueError, match="negative"):
        goldberg_decision_threshold(tg, g=-0.1)


def test_goldberg_densest_empty_and_isolated():
    # Empty
    tg_empty = TransactionGraph()
    res_empty = goldberg_densest_subgraph(tg_empty)
    assert res_empty.density == pytest.approx(0.0)
    assert res_empty.nodes == []

    # Isolated
    tg_iso = TransactionGraph()
    tg_iso.add_account("X")
    tg_iso.add_account("Y")
    res_iso = goldberg_densest_subgraph(tg_iso)
    assert res_iso.density == pytest.approx(0.0)
    assert len(res_iso.nodes) == 1


def test_goldberg_densest_triangle():
    tg = TransactionGraph()
    tg.add_transaction("A", "B")
    tg.add_transaction("B", "C")
    tg.add_transaction("C", "A")

    res = goldberg_densest_subgraph(tg, tolerance=1e-4)
    assert res.density == pytest.approx(1.0)
    assert set(res.nodes) == {"A", "B", "C"}
    assert res.edge_count == 3
    assert res.node_count == 3
    assert res.flow_computations > 0
    assert res.runtime_sec >= 0.0


def test_goldberg_densest_complete_k4():
    # K4 has 4 nodes, 6 edges -> density 6 / 4 = 1.5
    tg = TransactionGraph()
    nodes = ["1", "2", "3", "4"]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            tg.add_transaction(nodes[i], nodes[j])

    res = goldberg_densest_subgraph(tg, tolerance=1e-4)
    assert res.density == pytest.approx(1.5)
    assert set(res.nodes) == set(nodes)
    assert res.edge_count == 6


def test_goldberg_densest_planted_dense_component():
    # K4 planted in a sparse 10-node graph
    tg = TransactionGraph()
    for i in range(10):
        tg.add_account(f"N{i}")
    # Dense K4 on N0..N3
    for i in range(4):
        for j in range(i + 1, 4):
            tg.add_transaction(f"N{i}", f"N{j}")
    # Sparse tail
    tg.add_transaction("N3", "N4")
    tg.add_transaction("N4", "N5")

    res = goldberg_densest_subgraph(tg, tolerance=1e-4)
    assert res.density == pytest.approx(1.5)
    assert set(res.nodes) == {"N0", "N1", "N2", "N3"}


def test_goldberg_reserved_node_names_collision():
    """
    Verify that node names like '__source__', '__sink__', '__e_0__'
    do not collide with internal network keys.
    """
    tg = TransactionGraph()
    tg.add_transaction("__source__", "__sink__")
    tg.add_transaction("__sink__", "__e_0__")
    tg.add_transaction("__e_0__", "__source__")

    dec = goldberg_decision_threshold(tg, g=0.5)
    assert dec.has_denser_subgraph is True
    assert set(dec.candidate_nodes) == {"__source__", "__sink__", "__e_0__"}
    assert dec.candidate_density == pytest.approx(1.0)

    res = goldberg_densest_subgraph(tg, tolerance=1e-4)
    assert res.density == pytest.approx(1.0)
    assert set(res.nodes) == {"__source__", "__sink__", "__e_0__"}


def test_goldberg_self_loop_and_duplicate_edges():
    """Verify that self-loops and duplicate edges in raw networkx graphs do not distort density."""
    import networkx as nx

    g = nx.Graph()
    g.add_edge("A", "B")
    g.add_edge("B", "C")
    g.add_edge("C", "A")
    g.add_edge("A", "A")  # Self loop

    res = goldberg_densest_subgraph(g, tolerance=1e-4)
    assert res.density == pytest.approx(1.0)
    assert set(res.nodes) == {"A", "B", "C"}
    assert res.edge_count == 3


def test_goldberg_warm_started_lower_bound():
    """Verify that lower_bound reduces flow computations while preserving the optimal density."""
    tg = TransactionGraph()
    for i in range(5):
        for j in range(i + 1, 5):
            tg.add_transaction(f"v_{i}", f"v_{j}")

    # Standard run
    res_cold = goldberg_densest_subgraph(tg, tolerance=1e-4)
    # Warm-started run with lower_bound = 1.0
    res_warm = goldberg_densest_subgraph(tg, tolerance=1e-4, lower_bound=1.0)

    assert res_cold.density == pytest.approx(2.0)
    assert res_warm.density == pytest.approx(2.0)
    assert set(res_warm.nodes) == set(res_cold.nodes)
    assert res_warm.flow_computations <= res_cold.flow_computations


def test_goldberg_tie_breaking_compactness():
    """Verify that tie-breaking prefers the smaller candidate subset when densities are equal."""
    tg = TransactionGraph()
    # K4 has density 6 / 4 = 1.5
    for i in range(4):
        for j in range(i + 1, 4):
            tg.add_transaction(f"C_{i}", f"C_{j}")
    # Isolated nodes with zero density
    for i in range(10):
        tg.add_account(f"ISO_{i}")

    res = goldberg_densest_subgraph(tg, tolerance=1e-4)
    assert res.density == pytest.approx(1.5)
    assert len(res.nodes) == 4
    assert set(res.nodes) == {"C_0", "C_1", "C_2", "C_3"}


def test_goldberg_mathematical_exactness_flag():
    """Verify is_mathematically_exact flag logic."""
    tg = TransactionGraph()
    for i in range(4):
        for j in range(i + 1, 4):
            tg.add_transaction(f"n_{i}", f"n_{j}")

    # For n=4, theoretical bound = 1 / (4 * 3) = 1/12 ≈ 0.0833
    # Tolerance 0.05 <= 0.0833 -> exact
    res_exact = goldberg_densest_subgraph(tg, tolerance=0.05)
    assert res_exact.is_mathematically_exact is True

    # Tolerance 0.5 > 0.0833 -> not exact
    res_approx = goldberg_densest_subgraph(tg, tolerance=0.5)
    assert res_approx.is_mathematically_exact is False

    # Hard max_iter stop -> not exact
    res_stopped = goldberg_densest_subgraph(tg, tolerance=0.01, max_iter=1)
    assert res_stopped.is_mathematically_exact is False
