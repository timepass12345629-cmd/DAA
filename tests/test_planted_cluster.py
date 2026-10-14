"""
Tests for ringscope.data (Synthetic planted cluster generator).
"""

import pytest

from ringscope.data import generate_planted_cluster_graph


def test_planted_cluster_determinism():
    """Identical seed must produce identical graph topology and membership."""
    res1 = generate_planted_cluster_graph(
        n_total=25, cluster_size=8, p_internal=0.8, p_external=0.1, seed=123
    )
    res2 = generate_planted_cluster_graph(
        n_total=25, cluster_size=8, p_internal=0.8, p_external=0.1, seed=123
    )

    assert res1.planted_cluster == res2.planted_cluster
    assert res1.graph.num_vertices == res2.graph.num_vertices
    assert res1.graph.num_unique_edges == res2.graph.num_unique_edges
    assert set(res1.graph.graph.edges()) == set(res2.graph.graph.edges())
    assert res1.cluster_density == pytest.approx(res2.cluster_density)


def test_planted_cluster_ground_truth_membership():
    res = generate_planted_cluster_graph(
        n_total=30, cluster_size=10, p_internal=0.7, p_external=0.1, seed=42
    )
    assert len(res.planted_cluster) == 10
    assert len(res.background_nodes) == 20
    assert res.graph.num_vertices == 30

    # Ensure metadata records ground truth
    assert res.graph.metadata["planted_cluster"] == res.planted_cluster
    assert res.graph.metadata["background_nodes"] == res.background_nodes

    for node in res.planted_cluster:
        assert res.graph.graph.nodes[node]["is_planted"] is True
    for node in res.background_nodes:
        assert res.graph.graph.nodes[node]["is_planted"] is False


def test_planted_cluster_density_contrast():
    """Planted cluster with p_in=1.0 and p_out=0.0 must be a pure clique with density (k-1)/2."""
    k = 6
    res = generate_planted_cluster_graph(
        n_total=20, cluster_size=k, p_internal=1.0, p_external=0.0, seed=7
    )
    # A complete graph K_6 has 6*5/2 = 15 edges -> density = 15 / 6 = 2.5
    assert res.cluster_density == pytest.approx(2.5)
    # Background has 0 edges
    assert res.background_density == pytest.approx(0.0)
    assert res.cluster_density > res.background_density


def test_planted_cluster_invalid_parameters_raise():
    with pytest.raises(ValueError, match="n_total must be at least 1"):
        generate_planted_cluster_graph(n_total=0)

    with pytest.raises(ValueError, match="0 <= cluster_size <= n_total"):
        generate_planted_cluster_graph(n_total=10, cluster_size=15)

    with pytest.raises(ValueError, match="probabilities must be between 0.0 and 1.0"):
        generate_planted_cluster_graph(n_total=10, cluster_size=5, p_internal=1.5)

    with pytest.raises(ValueError, match="probabilities must be between 0.0 and 1.0"):
        generate_planted_cluster_graph(n_total=10, cluster_size=5, p_external=-0.1)
