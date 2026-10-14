"""
Tests for ringscope.algorithms.brute_force (Brute-force densest-subgraph reference solver).
"""

import networkx as nx
import pytest

from ringscope.algorithms.brute_force import (
    MAX_BRUTE_FORCE_NODES,
    brute_force_densest_subgraph,
)
from ringscope.graph import TransactionGraph


def test_brute_force_empty_and_single_node():
    empty_g = TransactionGraph()
    res_empty = brute_force_densest_subgraph(empty_g)
    assert res_empty.nodes == []
    assert res_empty.density == pytest.approx(0.0)

    single_g = TransactionGraph()
    single_g.add_account("Single")
    res_single = brute_force_densest_subgraph(single_g)
    assert res_single.nodes == ["Single"]
    assert res_single.density == pytest.approx(0.0)


def test_brute_force_triangle():
    """Triangle (K3) has density = 3 edges / 3 nodes = 1.0."""
    tg = TransactionGraph()
    tg.add_transaction("A", "B")
    tg.add_transaction("B", "C")
    tg.add_transaction("C", "A")

    res = brute_force_densest_subgraph(tg)
    assert set(res.nodes) == {"A", "B", "C"}
    assert res.density == pytest.approx(1.0)
    assert res.edge_count == 3
    assert res.node_count == 3
    # 2^3 - 1 = 7 subsets evaluated
    assert res.subsets_evaluated == 7


def test_brute_force_complete_k4():
    """Complete graph K4 has density = 6 edges / 4 nodes = 1.5."""
    tg = TransactionGraph()
    for u in ["1", "2", "3", "4"]:
        for v in ["1", "2", "3", "4"]:
            if u < v:
                tg.add_transaction(u, v)

    res = brute_force_densest_subgraph(tg)
    assert set(res.nodes) == {"1", "2", "3", "4"}
    assert res.density == pytest.approx(1.5)
    assert res.edge_count == 6
    assert res.node_count == 4
    # 2^4 - 1 = 15 subsets evaluated
    assert res.subsets_evaluated == 15


def test_brute_force_finds_dense_component_in_sparse_graph():
    """Triangle component with attached isolated nodes: oracle must identify the triangle."""
    tg = TransactionGraph()
    # Triangle
    tg.add_transaction("T1", "T2")
    tg.add_transaction("T2", "T3")
    tg.add_transaction("T3", "T1")
    # Isolated nodes and pendant edge
    tg.add_account("ISO_1")
    tg.add_account("ISO_2")
    tg.add_transaction("P1", "P2")

    res = brute_force_densest_subgraph(tg)
    assert set(res.nodes) == {"T1", "T2", "T3"}
    assert res.density == pytest.approx(1.0)


def test_brute_force_exceeding_max_nodes_raises():
    """Graph with > MAX_BRUTE_FORCE_NODES nodes must raise ValueError."""
    g = nx.path_graph(MAX_BRUTE_FORCE_NODES + 1)
    with pytest.raises(ValueError, match="exceeds the maximum brute-force limit"):
        brute_force_densest_subgraph(g)
