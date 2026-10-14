"""
Tests for ringscope.algorithms.cycle_detection.

Key invariants tested
----------------------
1. No rings found in a DAG.
2. All planted rings are detected (recall = 1.0).
3. Filters (min_length, max_length, min_amount) are respected.
4. ring_summary statistics are correct.
5. Ring.edges() correctly closes the cycle.
"""

import networkx as nx
import pytest

from ringscope.algorithms.cycle_detection import detect_rings, ring_summary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def triangle_graph() -> nx.DiGraph:
    """A → B → C → A  (one 3-cycle)."""
    g = nx.DiGraph()
    g.add_edge("A", "B", amount=100.0, timestamp=1.0)
    g.add_edge("B", "C", amount=200.0, timestamp=2.0)
    g.add_edge("C", "A", amount=50.0, timestamp=3.0)
    return g


def dag_graph() -> nx.DiGraph:
    """A → B → C  (no cycle)."""
    g = nx.DiGraph()
    g.add_edge("A", "B", amount=10.0, timestamp=1.0)
    g.add_edge("B", "C", amount=20.0, timestamp=2.0)
    return g


def two_rings_graph() -> nx.DiGraph:
    """Two disjoint rings: [A,B,C] and [D,E,F,G]."""
    g = nx.DiGraph()
    for u, v in [("A", "B"), ("B", "C"), ("C", "A")]:
        g.add_edge(u, v, amount=500.0, timestamp=1.0)
    for u, v in [("D", "E"), ("E", "F"), ("F", "G"), ("G", "D")]:
        g.add_edge(u, v, amount=300.0, timestamp=2.0)
    return g


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_rings_in_dag():
    rings = detect_rings(dag_graph())
    assert rings == []


def test_triangle_detected():
    rings = detect_rings(triangle_graph())
    assert len(rings) == 1
    assert rings[0].length == 3
    node_set = set(rings[0].nodes)
    assert node_set == {"A", "B", "C"}


def test_triangle_min_amount():
    """Bottleneck of triangle is min(100, 200, 50) = 50."""
    rings = detect_rings(triangle_graph())
    assert rings[0].min_amount == pytest.approx(50.0)


def test_ring_edges_closes_cycle():
    rings = detect_rings(triangle_graph())
    edges = rings[0].edges()
    assert len(edges) == 3
    # Each edge must appear in the graph
    g = triangle_graph()
    for u, v in edges:
        assert g.has_edge(u, v)


def test_two_rings_both_detected():
    rings = detect_rings(two_rings_graph())
    lengths = sorted(r.length for r in rings)
    assert lengths == [3, 4]


def test_min_length_filter():
    """With min_length=4 only the 4-cycle should be returned."""
    rings = detect_rings(two_rings_graph(), min_length=4)
    assert len(rings) == 1
    assert rings[0].length == 4


def test_max_length_filter():
    """With max_length=3 only the 3-cycle should be returned."""
    rings = detect_rings(two_rings_graph(), max_length=3)
    assert len(rings) == 1
    assert rings[0].length == 3


def test_min_amount_filter():
    """3-cycle has bottleneck 500, 4-cycle has 300; filter removes 4-cycle."""
    rings = detect_rings(two_rings_graph(), min_amount=400.0)
    assert len(rings) == 1
    assert rings[0].length == 3


def test_max_rings_limit():
    rings = detect_rings(two_rings_graph(), max_rings=1)
    assert len(rings) == 1


def test_ring_summary_empty():
    s = ring_summary([])
    assert s["count"] == 0
    assert s["total_volume"] == 0.0


def test_ring_summary_correct():
    rings = detect_rings(two_rings_graph())
    s = ring_summary(rings)
    assert s["count"] == 2
    assert s["max_length"] == 4
    assert s["min_length"] == 3
    # Total volume = 500 + 300
    assert s["total_volume"] == pytest.approx(800.0)


def test_ring_to_dict():
    rings = detect_rings(triangle_graph())
    d = rings[0].to_dict()
    assert "nodes" in d
    assert "length" in d
    assert "min_amount" in d
    assert "edges" in d
    assert d["length"] == 3
