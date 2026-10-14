"""
Tests for ringscope.graph (TransactionGraph undirected simple graph model).
"""

import pytest

from ringscope.graph import TransactionGraph, UndirectedTransactionGraph

# ---------------------------------------------------------------------------
# Core Graph Construction & Normalization
# ---------------------------------------------------------------------------


def test_empty_graph():
    tg = TransactionGraph()
    assert tg.num_vertices == 0
    assert tg.num_nodes == 0
    assert tg.num_unique_edges == 0
    assert tg.num_edges == 0
    assert tg.total_transaction_records == 0
    assert tg.self_loops_skipped == 0
    assert tg.degrees() == {}
    assert tg.connected_components() == []


def test_add_account_and_isolated_vertices():
    tg = TransactionGraph()
    tg.add_account("ACC_1")
    tg.add_account("ACC_2", tier="premium")
    assert tg.num_vertices == 2
    assert tg.num_unique_edges == 0
    assert tg.degrees() == {"ACC_1": 0, "ACC_2": 0}

    # Isolated vertices form their own connected components of size 1
    comps = tg.connected_components()
    assert len(comps) == 2
    assert {"ACC_1"} in comps
    assert {"ACC_2"} in comps


def test_add_account_validation():
    tg = TransactionGraph()
    with pytest.raises(ValueError, match="cannot be None"):
        tg.add_account(None)  # type: ignore

    with pytest.raises(ValueError, match="empty or whitespace"):
        tg.add_account("   ")


def test_edge_normalization_undirected():
    """In an undirected simple graph, (A, B) and (B, A) represent the exact same edge."""
    tg = TransactionGraph()
    tid1 = tg.add_transaction("Alice", "Bob", amount=100.0, timestamp=1000.0)
    assert tg.num_vertices == 2
    assert tg.num_unique_edges == 1
    assert tg.total_transaction_records == 1
    assert isinstance(tid1, str)

    # Inverted direction is a parallel transaction on the same undirected edge
    tid2 = tg.add_transaction("Bob", "Alice", amount=50.0, timestamp=2000.0)
    assert isinstance(tid2, str)
    assert tg.num_unique_edges == 1  # Unique edge count does not increase
    assert tg.total_transaction_records == 2

    edge = tg.graph["Alice"]["Bob"]
    assert edge["tx_count"] == 2
    assert edge["amount"] == pytest.approx(150.0)
    assert edge["timestamp"] == pytest.approx(2000.0)


def test_self_loops_handling():
    """Self-loops must not create internal edges in the simple graph model."""
    tg = TransactionGraph()
    tid = tg.add_transaction("SelfAccount", "SelfAccount", amount=500.0, timestamp=1234.0)

    # Vertex is ensured to exist
    assert tg.num_vertices == 1
    # No self-loop edge is created
    assert tg.num_unique_edges == 0
    assert tg.self_loops_skipped == 1
    assert tg.total_transaction_records == 1
    assert tg.graph.nodes["SelfAccount"]["self_loop_count"] == 1
    assert tg.graph.nodes["SelfAccount"]["self_loop_amount"] == 500.0
    assert isinstance(tid, str)


def test_missing_endpoints_and_malformed_inputs():
    tg = TransactionGraph()
    with pytest.raises(ValueError, match="must not be None"):
        tg.add_transaction(None, "Bob")  # type: ignore

    with pytest.raises(ValueError, match="must not be None"):
        tg.add_transaction("Alice", None)  # type: ignore

    with pytest.raises(ValueError, match="empty or whitespace"):
        tg.add_transaction("", "Bob")

    with pytest.raises(ValueError, match="empty or whitespace"):
        tg.add_transaction("Alice", "   ")


def test_remove_transaction():
    tg = TransactionGraph()
    tg.add_transaction("A", "B", amount=50.0)
    assert tg.num_unique_edges == 1
    tg.remove_transaction("A", "B")
    assert tg.num_unique_edges == 0
    # Both vertices remain
    assert tg.num_vertices == 2


# ---------------------------------------------------------------------------
# Graph Statistics & Connected Components
# ---------------------------------------------------------------------------


def test_graph_statistics():
    tg = TransactionGraph()
    # Triangle: A-B, B-C, C-A
    tg.add_transaction("A", "B")
    tg.add_transaction("B", "C")
    tg.add_transaction("C", "A")
    # Isolated node D
    tg.add_account("D")

    assert tg.num_vertices == 4
    assert tg.num_unique_edges == 3
    assert tg.degree("A") == 2
    assert tg.degree("B") == 2
    assert tg.degree("C") == 2
    assert tg.degree("D") == 0

    with pytest.raises(KeyError):
        tg.degree("NonExistent")

    comps = tg.connected_components()
    assert len(comps) == 2
    assert comps[0] == {"A", "B", "C"}
    assert comps[1] == {"D"}


# ---------------------------------------------------------------------------
# Density Computations (Important Correctness Rule)
# density(S) = internal_edges / |S|
# ---------------------------------------------------------------------------


def test_density_subsets():
    tg = TransactionGraph()
    # Triangle: A-B, B-C, C-A
    tg.add_transaction("A", "B")
    tg.add_transaction("B", "C")
    tg.add_transaction("C", "A")
    tg.add_account("Isolated")

    # Triangle subset: 3 edges / 3 vertices = 1.0
    assert tg.density(["A", "B", "C"]) == pytest.approx(1.0)

    # Edge subset (A, B): 1 edge / 2 vertices = 0.5
    assert tg.density(["A", "B"]) == pytest.approx(0.5)

    # Single vertex: 0 edges / 1 vertex = 0.0
    assert tg.density(["Isolated"]) == pytest.approx(0.0)

    # Whole graph: 3 edges / 4 vertices = 0.75
    assert tg.density() == pytest.approx(0.75)


def test_density_complete_k4():
    """Complete graph K4 has 6 unique edges and 4 vertices -> density = 6 / 4 = 1.5."""
    tg = TransactionGraph()
    nodes = ["1", "2", "3", "4"]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            tg.add_transaction(nodes[i], nodes[j])

    assert tg.num_vertices == 4
    assert tg.num_unique_edges == 6
    assert tg.density() == pytest.approx(1.5)
    assert tg.density(["1", "2", "3"]) == pytest.approx(1.0)  # K3 sub-triangle


def test_density_validation_errors():
    tg = TransactionGraph()
    tg.add_transaction("X", "Y")

    # Empty subset error
    with pytest.raises(ValueError, match="undefined for an empty vertex subset"):
        tg.density([])

    # Unknown vertices error
    with pytest.raises(ValueError, match="vertices not in graph"):
        tg.density(["X", "GhostNode"])


# ---------------------------------------------------------------------------
# Serialization & Alias
# ---------------------------------------------------------------------------


def test_to_dict_and_from_dict_roundtrip():
    tg = TransactionGraph(name="test_serial")
    tg.add_transaction("A", "B", amount=75.0, timestamp=500.0)
    tg.add_account("IsolatedNode")

    d = tg.to_dict()
    assert d["name"] == "test_serial"
    assert d["num_vertices"] == 3
    assert d["num_unique_edges"] == 1

    tg2 = TransactionGraph.from_dict(d)
    assert tg2.name == "test_serial"
    assert tg2.num_vertices == 3
    assert tg2.num_unique_edges == 1
    assert tg2.graph.has_edge("A", "B")
    assert "IsolatedNode" in tg2.graph


def test_undirected_transaction_graph_alias():
    utg = UndirectedTransactionGraph()
    assert isinstance(utg, TransactionGraph)
    assert utg.directed is False
