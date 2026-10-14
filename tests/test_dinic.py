"""
Tests for ringscope.algorithms.dinic (Dinic's Maximum Flow & Minimum Cut).
"""

import networkx as nx
import pytest

from ringscope.algorithms.dinic import Dinic


def test_dinic_single_edge():
    dinic = Dinic()
    dinic.add_edge("s", "t", 10.0)
    flow = dinic.max_flow("s", "t")
    assert flow == pytest.approx(10.0)
    cut = dinic.min_cut_source_side("s")
    assert cut == {"s"}


def test_dinic_diamond_network():
    # s -> a (10), s -> b (10), a -> t (10), b -> t (10), a -> b (1)
    dinic = Dinic()
    dinic.add_edge("s", "a", 10.0)
    dinic.add_edge("s", "b", 10.0)
    dinic.add_edge("a", "b", 1.0)
    dinic.add_edge("a", "t", 10.0)
    dinic.add_edge("b", "t", 10.0)

    flow = dinic.max_flow("s", "t")
    assert flow == pytest.approx(20.0)
    cut = dinic.min_cut_source_side("s")
    assert "s" in cut
    assert "t" not in cut


def test_dinic_classic_clrs_network():
    """
    Standard 6-node network from CLRS Chapter 26:
    s -> v1 (16), s -> v2 (13)
    v1 -> v3 (12), v1 -> v2 (10)
    v2 -> v1 (4), v2 -> v4 (14)
    v3 -> v2 (9), v3 -> t (20)
    v4 -> v3 (7), v4 -> t (4)
    Known max flow = 23.
    """
    dinic = Dinic()
    dinic.add_edge("s", "v1", 16.0)
    dinic.add_edge("s", "v2", 13.0)
    dinic.add_edge("v1", "v3", 12.0)
    dinic.add_edge("v1", "v2", 10.0)
    dinic.add_edge("v2", "v1", 4.0)
    dinic.add_edge("v2", "v4", 14.0)
    dinic.add_edge("v3", "v2", 9.0)
    dinic.add_edge("v3", "t", 20.0)
    dinic.add_edge("v4", "v3", 7.0)
    dinic.add_edge("v4", "t", 4.0)

    flow = dinic.max_flow("s", "t")
    assert flow == pytest.approx(23.0)

    cut = dinic.min_cut_source_side("s")
    assert cut == {"s", "v1", "v2", "v4"}


def test_dinic_residual_back_edge_routing():
    """
    Tests that Dinic properly uses reverse edges to undo earlier augmentations:
    s -> a (1), s -> b (1)
    a -> b (1)
    a -> t (1), b -> t (1)
    Max flow = 2.
    """
    dinic = Dinic()
    dinic.add_edge("s", "a", 1.0)
    dinic.add_edge("s", "b", 1.0)
    dinic.add_edge("a", "b", 1.0)
    dinic.add_edge("a", "t", 1.0)
    dinic.add_edge("b", "t", 1.0)

    flow = dinic.max_flow("s", "t")
    assert flow == pytest.approx(2.0)


def test_dinic_disconnected_sink():
    dinic = Dinic()
    dinic.add_edge("s", "a", 5.0)
    dinic.add_edge("b", "t", 5.0)
    flow = dinic.max_flow("s", "t")
    assert flow == pytest.approx(0.0)
    cut = dinic.min_cut_source_side("s")
    assert cut == {"s", "a"}


def test_dinic_validation_errors():
    dinic = Dinic()
    with pytest.raises(ValueError, match="negative"):
        dinic.add_edge("s", "t", -1.0)

    dinic.add_edge("s", "t", 5.0)
    with pytest.raises(ValueError, match="must be distinct"):
        dinic.max_flow("s", "s")

    with pytest.raises(KeyError, match="not in network"):
        dinic.max_flow("unknown", "t")


def test_dinic_matches_networkx_random_graphs():
    """Verify Dinic matches NetworkX max flow on random DAGs with capacities."""
    import random

    rng = random.Random(42)
    for _ in range(5):
        n = 15
        p = 0.3
        gnx = nx.gnp_random_graph(n, p, directed=True, seed=rng.randint(0, 10000))
        # Ensure DAG
        g_dag = nx.DiGraph()
        for u, v in gnx.edges():
            if u < v:
                cap = rng.randint(1, 20)
                g_dag.add_edge(u, v, capacity=cap)

        g_dag.add_node(0)
        g_dag.add_node(n - 1)

        dinic = Dinic()
        for u, v, data in g_dag.edges(data=True):
            dinic.add_edge(u, v, data["capacity"])

        nx_flow, _ = nx.maximum_flow(g_dag, 0, n - 1)
        dinic_flow = dinic.max_flow(0, n - 1)
        assert dinic_flow == pytest.approx(nx_flow, rel=1e-5)
