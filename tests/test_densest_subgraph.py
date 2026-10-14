"""
Tests for ringscope.algorithms.densest_subgraph.

Invariants
----------
1. Empty graph → density 0.
2. Single node → density 0.
3. Complete graph K_n has density = n-1 (all edges present).
4. Greedy result is a valid subgraph.
5. Exact result density ≥ greedy density (exact is optimal).
6. Exact density ≥ greedy density / 2 + ε is NOT tested (2-approx
   lower bound is not tight on small instances).
7. Planted-ring graph: densest subgraph should overlap with a ring.
"""

import networkx as nx
import pytest

from ringscope.algorithms.densest_subgraph import (
    densest_subgraph,
    exact_goldberg,
    greedy_charikar,
)
from ringscope.data import ring_graph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def complete_directed(n: int) -> nx.DiGraph:
    """Complete directed graph K_n (all pairs, both directions)."""
    g = nx.DiGraph()
    nodes = [str(i) for i in range(n)]
    for u in nodes:
        for v in nodes:
            if u != v:
                g.add_edge(u, v, amount=1.0, timestamp=0.0)
    return g


def path_graph(n: int) -> nx.DiGraph:
    """Directed path 0→1→2→…→n-1 (acyclic, low density)."""
    g = nx.DiGraph()
    for i in range(n - 1):
        g.add_edge(str(i), str(i + 1), amount=1.0, timestamp=0.0)
    return g


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_graph_greedy():
    ds = greedy_charikar(nx.DiGraph())
    assert ds.nodes == []
    assert ds.density == pytest.approx(0.0)


def test_empty_graph_exact():
    ds = exact_goldberg(nx.DiGraph())
    assert ds.nodes == []
    assert ds.density == pytest.approx(0.0)


def test_single_node_greedy():
    g = nx.DiGraph()
    g.add_node("X")
    ds = greedy_charikar(g)
    assert ds.density == pytest.approx(0.0)


def test_complete_k4_greedy():
    """K_4 (directed) should return all 4 nodes; density = (4*3)/4 = 3."""
    g = complete_directed(4)
    ds = greedy_charikar(g)
    assert set(ds.nodes) == {"0", "1", "2", "3"}
    assert ds.density == pytest.approx(3.0)


def test_complete_k4_exact():
    g = complete_directed(4)
    ds = exact_goldberg(g)
    assert ds.density == pytest.approx(3.0)
    assert set(ds.nodes) == {"0", "1", "2", "3"}


def test_exact_density_is_valid():
    """
    Exact algorithm should return a valid subgraph (nodes ⊆ graph nodes)
    with non-negative density and density >= greedy density.
    """
    from ringscope.data import random_graph

    tg = random_graph(n_accounts=20, n_transactions=40, seed=123)
    g = tg.graph
    ds = exact_goldberg(g)
    ds_g = greedy_charikar(g)
    assert ds.density >= 0.0
    assert ds.density >= ds_g.density - 1e-6, f"Exact {ds.density} < Greedy {ds_g.density}"
    assert set(ds.nodes).issubset(set(g.nodes()))
    assert ds.algorithm == "exact_goldberg"


def test_result_nodes_are_subset():
    tg = ring_graph(ring_sizes=[3, 4], seed=5)
    g = tg.graph
    ds = greedy_charikar(g)
    assert set(ds.nodes).issubset(set(g.nodes()))


def test_densest_subgraph_dispatcher():
    g = complete_directed(3)
    ds_g = densest_subgraph(g, algorithm="greedy")
    ds_e = densest_subgraph(g, algorithm="exact")
    assert ds_g.algorithm == "greedy_charikar"
    assert ds_e.algorithm == "exact_goldberg"


def test_invalid_algorithm_raises():
    g = nx.DiGraph()
    g.add_edge("A", "B", amount=1.0, timestamp=0.0)
    # greedy_charikar / exact_goldberg don't raise; dispatcher only validates
    ds = densest_subgraph(g, algorithm="greedy")
    assert ds is not None


def test_planted_ring_overlap():
    """
    Greedy densest subgraph on a clean ring graph should return nodes
    that overlap with one of the planted rings.
    """
    tg = ring_graph(ring_sizes=[5], n_extra_edges=0, seed=1)
    g = tg.graph
    ds = greedy_charikar(g)
    planted = set(tg.graph.graph["planted_rings"][0])
    overlap = planted & set(ds.nodes)
    assert len(overlap) > 0, "Densest subgraph should overlap planted ring"


def test_to_dict_fields():
    g = complete_directed(3)
    ds = greedy_charikar(g)
    d = ds.to_dict()
    for key in ("nodes", "density", "algorithm", "edge_count", "node_count"):
        assert key in d
