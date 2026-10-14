"""
ringscope.data — Synthetic transaction dataset generators.

Generators
----------
1. random_graph(n, m, seed)          — Erdős–Rényi-style random transaction graph
2. ring_graph(ring_sizes, extras)    — Planted ring structure for benchmarking
3. transactions_stream(n, duration)  — Time-ordered transaction stream

All generators are deterministic given a fixed random seed.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass

from ringscope.algorithms.streaming import StreamEdge
from ringscope.graph import TransactionGraph

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _account_id(prefix: str, idx: int) -> str:
    return f"{prefix}{idx:04d}"


@dataclass
class PlantedClusterGraphResult:
    """Result of synthetic planted-cluster graph generation."""

    graph: TransactionGraph
    planted_cluster: set[str]
    background_nodes: set[str]
    p_internal: float
    p_external: float
    seed: int
    cluster_density: float
    background_density: float
    overall_density: float


def generate_planted_cluster_graph(
    n_total: int = 40,
    cluster_size: int = 10,
    p_internal: float = 0.7,
    p_external: float = 0.1,
    seed: int = 42,
    cluster_prefix: str = "C_",
    background_prefix: str = "B_",
) -> PlantedClusterGraphResult:
    """
    Generate an undirected, unweighted simple graph with a planted dense cluster.

    Parameters
    ----------
    n_total : int
        Total number of vertices in the graph.
    cluster_size : int
        Number of vertices in the planted dense cluster (must be <= n_total).
    p_internal : float
        Probability of an edge between any pair of vertices inside the cluster.
    p_external : float
        Probability of an edge between pairs outside the cluster, or between
        cluster and background vertices.
    seed : int
        Fixed random seed for deterministic reproducibility.
    cluster_prefix : str
        Prefix for cluster account IDs.
    background_prefix : str
        Prefix for background account IDs.

    Returns
    -------
    PlantedClusterGraphResult
        Contains the populated graph and ground-truth cluster membership.
    """
    if n_total < 1:
        raise ValueError("Total number of vertices n_total must be at least 1.")
    if not (0 <= cluster_size <= n_total):
        raise ValueError("cluster_size must satisfy 0 <= cluster_size <= n_total.")
    if not (0.0 <= p_internal <= 1.0) or not (0.0 <= p_external <= 1.0):
        raise ValueError("Connection probabilities must be between 0.0 and 1.0.")

    rng = random.Random(seed)
    tg = TransactionGraph(name=f"planted_cluster_seed_{seed}", directed=False)

    cluster_nodes = [f"{cluster_prefix}{i:03d}" for i in range(cluster_size)]
    bg_nodes = [f"{background_prefix}{i:03d}" for i in range(n_total - cluster_size)]

    # Add all vertices
    for u in cluster_nodes:
        tg.add_account(u, is_planted=True)
    for u in bg_nodes:
        tg.add_account(u, is_planted=False)

    # 1. Internal cluster edges
    for i in range(len(cluster_nodes)):
        for j in range(i + 1, len(cluster_nodes)):
            if rng.random() < p_internal:
                tg.add_transaction(cluster_nodes[i], cluster_nodes[j])

    # 2. Background internal edges
    for i in range(len(bg_nodes)):
        for j in range(i + 1, len(bg_nodes)):
            if rng.random() < p_external:
                tg.add_transaction(bg_nodes[i], bg_nodes[j])

    # 3. Cross edges between cluster and background
    for u in cluster_nodes:
        for v in bg_nodes:
            if rng.random() < p_external:
                tg.add_transaction(u, v)

    planted_set = set(cluster_nodes)
    bg_set = set(bg_nodes)

    tg.metadata["planted_cluster"] = planted_set
    tg.metadata["background_nodes"] = bg_set
    tg.metadata["p_internal"] = p_internal
    tg.metadata["p_external"] = p_external
    tg.metadata["seed"] = seed

    c_density = tg.density(cluster_nodes) if cluster_size > 0 else 0.0
    bg_density = tg.density(bg_nodes) if len(bg_nodes) > 0 else 0.0
    ov_density = tg.density() if n_total > 0 else 0.0

    return PlantedClusterGraphResult(
        graph=tg,
        planted_cluster=planted_set,
        background_nodes=bg_set,
        p_internal=p_internal,
        p_external=p_external,
        seed=seed,
        cluster_density=c_density,
        background_density=bg_density,
        overall_density=ov_density,
    )


# ---------------------------------------------------------------------------
# Static graph generators (Directed for cycle analysis)
# ---------------------------------------------------------------------------


def random_graph(
    n_accounts: int = 50,
    n_transactions: int = 100,
    min_amount: float = 1.0,
    max_amount: float = 10_000.0,
    seed: int = 42,
) -> TransactionGraph:
    """
    Generate a random directed transaction graph.
    """
    rng = random.Random(seed)
    tg = TransactionGraph(name="random_graph", directed=True)
    accounts = [_account_id("ACC", i) for i in range(n_accounts)]
    for acc in accounts:
        tg.add_account(acc)

    base_ts = 1_700_000_000.0  # ~ 2023-11-14 UTC
    for _ in range(n_transactions):
        src = rng.choice(accounts)
        dst = rng.choice(accounts)
        while dst == src:
            dst = rng.choice(accounts)
        amount = round(rng.uniform(min_amount, max_amount), 2)
        timestamp = base_ts + rng.uniform(0, 86_400)
        tg.add_transaction(src, dst, amount, timestamp)
    return tg


def ring_graph(
    ring_sizes: list[int] | None = None,
    n_extra_edges: int = 20,
    amount_per_edge: float = 1000.0,
    seed: int = 7,
) -> TransactionGraph:
    """
    Generate a graph with *planted* rings for controlled benchmarking.
    """
    if ring_sizes is None:
        ring_sizes = [3, 4, 5]

    rng = random.Random(seed)
    tg = TransactionGraph(name="ring_benchmark", directed=True)
    base_ts = 1_700_000_000.0
    planted: list[list[str]] = []
    node_counter = 0

    for size in ring_sizes:
        ring_nodes = [_account_id("R", node_counter + i) for i in range(size)]
        node_counter += size
        planted.append(ring_nodes)
        for acc in ring_nodes:
            tg.add_account(acc)
        for i in range(size):
            src = ring_nodes[i]
            dst = ring_nodes[(i + 1) % size]
            tg.add_transaction(
                src,
                dst,
                amount_per_edge,
                base_ts + i * 60,
                tx_id=str(uuid.uuid4()),
                ring_edge=True,
            )

    # Extra noise nodes
    noise_nodes = [_account_id("N", i) for i in range(n_extra_edges)]
    for acc in noise_nodes:
        tg.add_account(acc)

    all_nodes = [n for ring in planted for n in ring] + noise_nodes
    for _ in range(n_extra_edges):
        src = rng.choice(all_nodes)
        dst = rng.choice(all_nodes)
        if src != dst:
            tg.add_transaction(
                src,
                dst,
                round(rng.uniform(10.0, 500.0), 2),
                base_ts + rng.uniform(0, 3600),
            )

    tg.graph.graph["planted_rings"] = planted
    return tg


# ---------------------------------------------------------------------------
# Streaming generators
# ---------------------------------------------------------------------------


def transaction_stream(
    n_transactions: int = 200,
    n_accounts: int = 30,
    ring_probability: float = 0.3,
    ring_sizes: list[int] | None = None,
    window_size: float = 3600.0,
    seed: int = 99,
) -> list[StreamEdge]:
    """
    Generate a time-ordered list of StreamEdge objects.

    Some transactions are deliberately part of rings (planted by cycling
    through a ring account list) to provide ground-truth evaluation data.

    Parameters
    ----------
    ring_probability : float
        Fraction of transactions that belong to planted ring patterns.
    ring_sizes : list[int]
        Ring sizes to plant.
    window_size : float
        Total time span of the stream (seconds).

    Returns
    -------
    list[StreamEdge]  sorted by timestamp ascending.
    """
    if ring_sizes is None:
        ring_sizes = [3, 4]

    rng = random.Random(seed)
    accounts = [_account_id("S", i) for i in range(n_accounts)]
    ring_pools: list[list[str]] = [
        [_account_id("SR", i * sz + j) for j in range(sz)] for i, sz in enumerate(ring_sizes)
    ]

    edges: list[StreamEdge] = []
    start_ts = 1_700_000_000.0

    for idx in range(n_transactions):
        ts = start_ts + (idx / n_transactions) * window_size
        if rng.random() < ring_probability:
            pool = rng.choice(ring_pools)
            i = rng.randrange(len(pool))
            src = pool[i]
            dst = pool[(i + 1) % len(pool)]
        else:
            src = rng.choice(accounts)
            dst = rng.choice(accounts)
            while dst == src:
                dst = rng.choice(accounts)
        edges.append(
            StreamEdge(
                src=src,
                dst=dst,
                amount=round(rng.uniform(1.0, 5000.0), 2),
                timestamp=ts,
                tx_id=str(uuid.uuid4()),
            )
        )

    edges.sort(key=lambda e: e.timestamp)
    return edges
