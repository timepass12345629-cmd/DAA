"""
Comprehensive validation of densest subgraph algorithms against the Phase 1 brute-force oracle.

Tests Goldberg exact solver, Charikar greedy peeling, and Greedy++ against the
brute-force reference solver on small graph families (N <= 20):
1. Paths
2. Stars
3. Triangles
4. Complete graphs (K_n)
5. Disconnected graphs / multiple components
6. Isolated vertices
7. Randomized graphs (Erdos-Renyi)
"""

import networkx as nx
import pytest

from ringscope.algorithms.brute_force import brute_force_densest_subgraph
from ringscope.algorithms.goldberg import goldberg_densest_subgraph
from ringscope.algorithms.greedy_peeling import greedy_peeling
from ringscope.algorithms.greedy_plus_plus import greedy_plus_plus
from ringscope.graph import TransactionGraph


def _validate_subgraph_solution(tg: TransactionGraph, nodes: list[str], reported_density: float):
    """Verify that candidate nodes form a valid subset and density is accurately computed."""
    all_nodes = set(tg.graph.nodes())
    subset = set(nodes)
    assert subset.issubset(all_nodes), "Returned nodes must be a subset of graph vertices"

    if len(subset) == 0:
        assert reported_density == pytest.approx(0.0)
        return

    # Count internal undirected edges in graph
    internal_edges = 0
    for u, v in tg.graph.edges():
        if u in subset and v in subset:
            internal_edges += 1

    actual_density = internal_edges / len(subset)
    assert reported_density == pytest.approx(actual_density, abs=1e-5), (
        f"Reported density {reported_density} does not match recomputed {actual_density}"
    )


def _check_algorithms_against_oracle(tg: TransactionGraph):
    """
    Run Brute Force oracle, Goldberg, Greedy Peeling, and Greedy++ on tg.
    Verifies:
      1. Solution validity (subset is valid and reported density is correct).
      2. Goldberg achieves exact optimal density within tolerance.
      3. Greedy peeling achieves >= OPT / 2 and <= OPT.
      4. Greedy++ achieves >= Greedy peeling and <= OPT.
    """
    bf = brute_force_densest_subgraph(tg, max_nodes=20)
    gb = goldberg_densest_subgraph(tg, tolerance=1e-5)
    gp = greedy_peeling(tg)
    gpp = greedy_plus_plus(tg, iterations=10)

    # 1. Solution validity
    _validate_subgraph_solution(tg, bf.nodes, bf.density)
    _validate_subgraph_solution(tg, gb.nodes, gb.density)
    _validate_subgraph_solution(tg, gp.nodes, gp.density)
    _validate_subgraph_solution(tg, gpp.nodes, gpp.density)

    # 2. Goldberg exactness
    assert gb.density == pytest.approx(bf.density, abs=1e-4), (
        f"Goldberg density {gb.density} failed to match Brute-force OPT {bf.density}"
    )

    # 3. Greedy 2-approximation bounds
    if bf.density > 0:
        assert gp.density >= (bf.density / 2.0) - 1e-6, (
            f"Greedy density {gp.density} violated 2-approx bound: OPT is {bf.density}"
        )
    assert gp.density <= bf.density + 1e-6, "Greedy density cannot exceed OPT"

    # 4. Greedy++ bounds
    assert gpp.density >= gp.density - 1e-6, "Greedy++ should be >= standard greedy"
    assert gpp.density <= bf.density + 1e-6, "Greedy++ density cannot exceed OPT"


def test_oracle_validation_path_graphs():
    """Paths P_2, P_4, P_6."""
    for n in (2, 4, 6):
        tg = TransactionGraph(name=f"Path_{n}")
        for i in range(n - 1):
            tg.add_transaction(f"v_{i}", f"v_{i+1}")
        _check_algorithms_against_oracle(tg)


def test_oracle_validation_star_graphs():
    """Star graphs S_4, S_6 (1 center, k leaves)."""
    for leaves in (3, 5):
        tg = TransactionGraph(name=f"Star_{leaves}")
        for i in range(leaves):
            tg.add_transaction("Center", f"Leaf_{i}")
        _check_algorithms_against_oracle(tg)


def test_oracle_validation_triangles():
    """Simple triangle and triangle with pendant edges."""
    tg = TransactionGraph(name="Triangle_Pendant")
    tg.add_transaction("T1", "T2")
    tg.add_transaction("T2", "T3")
    tg.add_transaction("T3", "T1")
    # Pendant whiskers
    tg.add_transaction("T1", "W1")
    tg.add_transaction("T2", "W2")
    _check_algorithms_against_oracle(tg)


def test_oracle_validation_complete_graphs():
    """Complete graphs K_3, K_4, K_5."""
    for n in (3, 4, 5):
        tg = TransactionGraph(name=f"K_{n}")
        nodes = [f"u_{i}" for i in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                tg.add_transaction(nodes[i], nodes[j])
        _check_algorithms_against_oracle(tg)


def test_oracle_validation_disconnected_and_isolated():
    """Graph with two disconnected components and isolated vertices."""
    tg = TransactionGraph(name="Disconnected_Complex")
    # Component 1: K4 (density 1.5)
    for i in range(4):
        for j in range(i + 1, 4):
            tg.add_transaction(f"C1_{i}", f"C1_{j}")

    # Component 2: Triangle (density 1.0)
    tg.add_transaction("C2_0", "C2_1")
    tg.add_transaction("C2_1", "C2_2")
    tg.add_transaction("C2_2", "C2_0")

    # Isolated nodes
    tg.add_account("Iso_1")
    tg.add_account("Iso_2")

    _check_algorithms_against_oracle(tg)


def test_oracle_validation_randomized_graphs():
    """Random graphs generated across different seeds and edge densities."""
    import random

    rng = random.Random(999)
    for trial in range(4):
        n = 8
        p = 0.25 + 0.15 * trial
        gnx = nx.gnp_random_graph(n, p, seed=rng.randint(0, 10000))
        tg = TransactionGraph(name=f"Random_{trial}")
        for u, v in gnx.edges():
            tg.add_transaction(f"r_{u}", f"r_{v}")
        for i in range(n):
            tg.add_account(f"r_{i}")

        _check_algorithms_against_oracle(tg)
