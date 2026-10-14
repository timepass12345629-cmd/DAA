"""
Tests for ringscope.algorithms.greedy_peeling (Charikar's greedy peeling).
"""

import pytest

from ringscope.algorithms.greedy_peeling import greedy_peeling
from ringscope.graph import TransactionGraph


def test_greedy_peeling_empty_and_isolated():
    # Empty
    tg_empty = TransactionGraph()
    res_empty = greedy_peeling(tg_empty)
    assert res_empty.density == pytest.approx(0.0)
    assert res_empty.nodes == []
    assert res_empty.history == []

    # Isolated
    tg_iso = TransactionGraph()
    tg_iso.add_account("A")
    tg_iso.add_account("B")
    res_iso = greedy_peeling(tg_iso)
    assert res_iso.density == pytest.approx(0.0)


def test_greedy_peeling_triangle():
    tg = TransactionGraph()
    tg.add_transaction("A", "B")
    tg.add_transaction("B", "C")
    tg.add_transaction("C", "A")

    res = greedy_peeling(tg)
    assert res.density == pytest.approx(1.0)
    assert set(res.nodes) == {"A", "B", "C"}
    assert res.edge_count == 3
    assert res.node_count == 3
    assert len(res.history) == 2  # n - 1 steps recorded


def test_greedy_peeling_complete_k4():
    tg = TransactionGraph()
    nodes = ["1", "2", "3", "4"]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            tg.add_transaction(nodes[i], nodes[j])

    res = greedy_peeling(tg)
    assert res.density == pytest.approx(1.5)
    assert set(res.nodes) == set(nodes)
    assert res.edge_count == 6
    assert res.node_count == 4


def test_greedy_peeling_peels_leaf_from_star():
    # Star graph: center C, leaves L1, L2, L3, L4
    # Max density is on any edge (1 edge / 2 nodes = 0.5) or entire star (4 edges / 5 nodes = 0.8)
    tg = TransactionGraph()
    for i in range(1, 5):
        tg.add_transaction("C", f"L{i}")

    res = greedy_peeling(tg)
    # The whole star has 4 edges and 5 nodes -> 4 / 5 = 0.8
    assert res.density == pytest.approx(0.8)
    assert set(res.nodes) == {"C", "L1", "L2", "L3", "L4"}

    # In peeling history, leaves with degree 1 are peeled first
    step1 = res.history[0]
    assert step1.removed_degree == 1
    assert step1.removed_node.startswith("L")


def test_greedy_peeling_history_consistency():
    tg = TransactionGraph()
    tg.add_transaction("1", "2")
    tg.add_transaction("2", "3")
    tg.add_transaction("3", "4")
    tg.add_transaction("4", "1")

    res = greedy_peeling(tg)
    assert len(res.history) == 3
    for step in res.history:
        assert step.remaining_node_count >= 1
        assert step.remaining_edge_count >= 0
        assert step.density >= 0.0

    d = res.to_dict()
    assert d["algorithm"] == "greedy_charikar_peeling"
    assert d["approximation_factor"] == 2.0
    assert d["history_length"] == 3
