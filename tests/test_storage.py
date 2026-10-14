"""
Tests for ringscope.storage (GraphStore SQLite persistence).
"""

import pytest

from ringscope.data import random_graph, ring_graph
from ringscope.graph import TransactionGraph
from ringscope.storage import GraphStore


def test_init_in_memory():
    store = GraphStore(":memory:")
    assert store.list_graphs() == []


def test_save_and_load_roundtrip():
    store = GraphStore(":memory:")
    tg = ring_graph(ring_sizes=[3, 4], seed=42)
    gid = store.save_graph(tg, "session_test")

    graphs = store.list_graphs()
    assert len(graphs) == 1
    assert graphs[0]["graph_id"] == "session_test"
    assert graphs[0]["num_nodes"] == tg.num_nodes
    assert graphs[0]["num_edges"] == tg.num_edges

    loaded = store.load_graph(gid)
    assert loaded.num_nodes == tg.num_nodes
    assert loaded.num_edges == tg.num_edges
    assert set(loaded.graph.nodes()) == set(tg.graph.nodes())
    assert set(loaded.graph.edges()) == set(tg.graph.edges())


def test_load_nonexistent_raises():
    store = GraphStore(":memory:")
    with pytest.raises(KeyError):
        store.load_graph("does_not_exist")


def test_delete_graph():
    store = GraphStore(":memory:")
    tg = random_graph(n_accounts=5, n_transactions=5, seed=1)
    gid = store.save_graph(tg, "del_test")
    assert len(store.list_graphs()) == 1

    deleted = store.delete_graph(gid)
    assert deleted is True
    assert len(store.list_graphs()) == 0

    assert store.delete_graph("unknown") is False


def test_transaction_history():
    store = GraphStore(":memory:")
    tg = TransactionGraph(name="tx_test")
    tg.add_account("U1")
    tg.add_account("U2")
    tg.add_transaction("U1", "U2", 50.0, 1000.0, tx_id="T001")
    gid = store.save_graph(tg, "tx_hist_test")

    history = store.get_transaction_history(gid)
    assert len(history) == 1
    assert history[0]["tx_id"] == "T001"
    assert history[0]["amount"] == 50.0
