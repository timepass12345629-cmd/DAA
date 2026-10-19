"""
ringscope.stream_simulator
==========================
Deterministic Transaction Stream Simulator & Streaming Candidate Maintenance.

Provides:
1. Deterministic transaction stream generator with configurable batch sizes,
   arrival orderings, planted cluster/ring injection, and fixed seeds.
2. Three candidate maintenance modes:
   - Mode A: Full Recomputation (unconditional re-execution per batch)
   - Mode B: Warm-Started Recomputation (sound optimization reusing lower bounds
     and threshold verification while preserving mathematical correctness)
   - Mode C: Incremental Heuristic (maintains candidate and statistics locally,
     triggering full recomputation under explicit external-activity conditions)
3. Step-by-step latency, edge delta, candidate cluster, and recomputation tracking.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Literal

from ringscope.algorithms.goldberg import (
    goldberg_decision_threshold,
    goldberg_densest_subgraph,
)
from ringscope.algorithms.greedy_peeling import greedy_peeling
from ringscope.algorithms.greedy_plus_plus import greedy_plus_plus
from ringscope.graph import TransactionGraph


@dataclass
class TransactionRecord:
    """A single transaction record in the generated stream."""

    src: str
    dst: str
    amount: float
    timestamp: float
    tx_id: str
    is_planted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "src": self.src,
            "dst": self.dst,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "tx_id": self.tx_id,
            "is_planted": self.is_planted,
        }


@dataclass
class StreamBatch:
    """A batch of transaction records arriving together."""

    batch_index: int
    transactions: list[TransactionRecord]


@dataclass
class StreamStepSnapshot:
    """Record of graph state and candidate cluster after processing a batch."""

    batch_index: int
    version: int
    num_inserted_tx: int
    num_new_unique_edges: int
    total_vertices: int
    total_unique_edges: int
    affected_vertices: list[str]
    candidate_nodes: list[str]
    candidate_density: float
    batch_latency_ms: float
    cumulative_latency_ms: float
    recomputation_count: int
    mode: str
    recomputed_this_step: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_index": self.batch_index,
            "version": self.version,
            "num_inserted_tx": self.num_inserted_tx,
            "num_new_unique_edges": self.num_new_unique_edges,
            "total_vertices": self.total_vertices,
            "total_unique_edges": self.total_unique_edges,
            "affected_vertices": self.affected_vertices,
            "candidate_nodes": self.candidate_nodes,
            "candidate_density": round(self.candidate_density, 5),
            "batch_latency_ms": round(self.batch_latency_ms, 3),
            "cumulative_latency_ms": round(self.cumulative_latency_ms, 3),
            "recomputation_count": self.recomputation_count,
            "mode": self.mode,
            "recomputed_this_step": self.recomputed_this_step,
        }


def generate_transaction_stream(
    n_background_accounts: int = 30,
    n_background_transactions: int = 60,
    batch_size: int = 5,
    arrival_order: Literal["chronological", "randomized", "reverse", "bursty"] = "chronological",
    planted_cluster_size: int = 6,
    planted_internal_p: float = 0.8,
    inject_at_batch: int = 2,
    seed: int = 42,
) -> tuple[list[StreamBatch], set[str]]:
    """
    Generate a deterministic sequence of transaction batches with an injected planted cluster.

    Parameters
    ----------
    n_background_accounts : int
        Number of background account nodes.
    n_background_transactions : int
        Number of background transactions.
    batch_size : int
        Number of transaction records per batch.
    arrival_order : 'chronological' | 'randomized' | 'reverse' | 'bursty'
        Ordering of background transaction timestamps.
    planted_cluster_size : int
        Number of nodes in the planted dense cluster.
    planted_internal_p : float
        Internal edge probability for the planted cluster.
    inject_at_batch : int
        Batch index at which planted transactions start injecting.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    tuple[list[StreamBatch], set[str]]
        List of StreamBatch objects and ground-truth planted cluster node set.
    """
    rng = random.Random(seed)

    bg_nodes = [f"ACC_{i:04d}" for i in range(n_background_accounts)]
    cluster_nodes = [f"PLANTED_{i:04d}" for i in range(planted_cluster_size)]
    planted_set = set(cluster_nodes)

    # 1. Generate background transactions
    bg_txs: list[TransactionRecord] = []
    base_time = 1600000000.0
    for idx in range(n_background_transactions):
        u, v = rng.sample(bg_nodes, 2)
        amount = round(rng.uniform(10.0, 500.0), 2)
        ts = base_time + idx * 10.0
        bg_txs.append(
            TransactionRecord(
                src=u,
                dst=v,
                amount=amount,
                timestamp=ts,
                tx_id=f"TX_BG_{idx:05d}",
                is_planted=False,
            )
        )

    # 2. Generate planted cluster transactions
    planted_txs: list[TransactionRecord] = []
    ptx_idx = 0
    for i in range(planted_cluster_size):
        for j in range(i + 1, planted_cluster_size):
            if rng.random() <= planted_internal_p:
                amount = round(rng.uniform(50.0, 1000.0), 2)
                ts = base_time + (inject_at_batch * batch_size + ptx_idx) * 10.0
                planted_txs.append(
                    TransactionRecord(
                        src=cluster_nodes[i],
                        dst=cluster_nodes[j],
                        amount=amount,
                        timestamp=ts,
                        tx_id=f"TX_PL_{ptx_idx:05d}",
                        is_planted=True,
                    )
                )
                ptx_idx += 1

    # Apply arrival ordering to background stream
    if arrival_order == "randomized":
        rng.shuffle(bg_txs)
    elif arrival_order == "reverse":
        bg_txs.reverse()
    elif arrival_order == "bursty":
        # Clustered timestamps
        for i, tx in enumerate(bg_txs):
            tx.timestamp = base_time + (i // 5) * 60.0 + (i % 5) * 0.5

    # 3. Interleave planted transactions starting at inject_at_batch
    injection_pos = min(len(bg_txs), inject_at_batch * batch_size)
    all_txs = bg_txs[:injection_pos] + planted_txs + bg_txs[injection_pos:]

    # 4. Partition into batches
    batches: list[StreamBatch] = []
    current_batch_txs: list[TransactionRecord] = []
    batch_idx = 0

    for tx in all_txs:
        current_batch_txs.append(tx)
        if len(current_batch_txs) >= batch_size:
            batches.append(StreamBatch(batch_index=batch_idx, transactions=current_batch_txs))
            batch_idx += 1
            current_batch_txs = []

    if current_batch_txs:
        batches.append(StreamBatch(batch_index=batch_idx, transactions=current_batch_txs))

    return batches, planted_set


class BaseStreamMaintainer:
    """Base class for streaming candidate densest subgraph maintainers."""

    def __init__(
        self,
        algorithm: Literal["goldberg", "greedy_peeling", "greedy_plus_plus"] = "greedy_peeling",
        tolerance: float = 1e-4,
    ) -> None:
        self.algorithm = algorithm
        self.tolerance = tolerance
        self.graph = TransactionGraph(name="stream_graph", directed=False)
        self.version = 0
        self.recomputation_count = 0
        self.cumulative_latency_ms = 0.0
        self.current_candidate: list[str] = []
        self.current_density: float = 0.0
        self.history: list[StreamStepSnapshot] = []

    def _compute_densest(self) -> tuple[list[str], float]:
        """Compute the densest subgraph using the configured algorithm."""
        if self.graph.num_vertices == 0 or self.graph.num_unique_edges == 0:
            nodes = list(self.graph.graph.nodes())
            return (nodes[:1] if nodes else []), 0.0

        if self.algorithm == "goldberg":
            res_gb = goldberg_densest_subgraph(self.graph, tolerance=self.tolerance)
            return res_gb.nodes, res_gb.density
        elif self.algorithm == "greedy_plus_plus":
            res_gpp = greedy_plus_plus(self.graph, iterations=10)
            return res_gpp.nodes, res_gpp.density
        else:
            res_gp = greedy_peeling(self.graph)
            return res_gp.nodes, res_gp.density

    def process_batch(self, batch: StreamBatch) -> StreamStepSnapshot:
        raise NotImplementedError


class FullRecomputationMaintainer(BaseStreamMaintainer):
    """
    Mode A: Full Recomputation.
    Re-executes the selected algorithm unconditionally from scratch on every batch.
    Guarantees exact/approx bounds of the base algorithm at the cost of O(B * T_algo) runtime.
    """

    def process_batch(self, batch: StreamBatch) -> StreamStepSnapshot:
        t0 = time.perf_counter()
        initial_edges = self.graph.num_unique_edges
        affected: set[str] = set()

        for tx in batch.transactions:
            affected.add(tx.src)
            affected.add(tx.dst)
            self.graph.add_transaction(
                src=tx.src,
                dst=tx.dst,
                amount=tx.amount,
                timestamp=tx.timestamp,
                tx_id=tx.tx_id,
            )

        new_unique = self.graph.num_unique_edges - initial_edges
        self.version += 1

        # Unconditionally recompute
        self.current_candidate, self.current_density = self._compute_densest()
        self.recomputation_count += 1

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.cumulative_latency_ms += elapsed_ms

        snap = StreamStepSnapshot(
            batch_index=batch.batch_index,
            version=self.version,
            num_inserted_tx=len(batch.transactions),
            num_new_unique_edges=new_unique,
            total_vertices=self.graph.num_vertices,
            total_unique_edges=self.graph.num_unique_edges,
            affected_vertices=sorted(affected),
            candidate_nodes=self.current_candidate,
            candidate_density=self.current_density,
            batch_latency_ms=elapsed_ms,
            cumulative_latency_ms=self.cumulative_latency_ms,
            recomputation_count=self.recomputation_count,
            mode="full_recomputation",
            recomputed_this_step=True,
        )
        self.history.append(snap)
        return snap


class WarmStartedMaintainer(BaseStreamMaintainer):
    """
    Mode B: Warm-Started Recomputation.
    Reuses valid previous information while strictly preserving the mathematical guarantee:
    1. Edge additions are monotone: lambda_t >= lambda_{t-1}.
    2. Warm-starts the search interval at [lambda_{t-1}, upper_bound].
    3. Evaluates threshold feasibility at the prior density to verify if the optimum
       remains unchanged without executing redundant binary search rounds.
    """

    def process_batch(self, batch: StreamBatch) -> StreamStepSnapshot:
        t0 = time.perf_counter()
        initial_edges = self.graph.num_unique_edges
        affected: set[str] = set()

        for tx in batch.transactions:
            affected.add(tx.src)
            affected.add(tx.dst)
            self.graph.add_transaction(
                src=tx.src,
                dst=tx.dst,
                amount=tx.amount,
                timestamp=tx.timestamp,
                tx_id=tx.tx_id,
            )

        new_unique = self.graph.num_unique_edges - initial_edges
        self.version += 1
        recomputed = False

        if new_unique == 0:
            # Parallel transaction records only: topology is identical, density is invariant
            recomputed = False
        elif not self.current_candidate or self.current_density <= 1e-9:
            self.current_candidate, self.current_density = self._compute_densest()
            self.recomputation_count += 1
            recomputed = True
        else:
            # Check if any new edge fell inside the candidate
            cand_set = set(self.current_candidate)
            internal_additions = sum(
                1 for tx in batch.transactions if tx.src in cand_set and tx.dst in cand_set
            )

            if self.algorithm == "goldberg":
                # Warm-start Goldberg decision check
                prior_density = self.current_density
                if internal_additions > 0:
                    prior_density = self.graph.density(cand_set)
                    self.current_density = prior_density

                # Decision test: does ANY subset S achieve density > prior_density?
                dec = goldberg_decision_threshold(self.graph, prior_density)
                if dec.has_denser_subgraph and dec.candidate_nodes:
                    # Run genuine warm-started binary search reusing prior density
                    # as valid lower bound
                    res_gb = goldberg_densest_subgraph(
                        self.graph,
                        tolerance=self.tolerance,
                        lower_bound=prior_density,
                    )
                    self.current_candidate = res_gb.nodes
                    self.current_density = res_gb.density
                    self.recomputation_count += 1
                    recomputed = True
                else:
                    # Proven mathematically: prior candidate remains optimal
                    recomputed = False
            else:
                # For greedy algorithms: if internal edges were added, update density;
                # otherwise recompute with warm degree tracking
                if internal_additions > 0:
                    self.current_density = self.graph.density(cand_set)
                self.current_candidate, self.current_density = self._compute_densest()
                self.recomputation_count += 1
                recomputed = True

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.cumulative_latency_ms += elapsed_ms

        snap = StreamStepSnapshot(
            batch_index=batch.batch_index,
            version=self.version,
            num_inserted_tx=len(batch.transactions),
            num_new_unique_edges=new_unique,
            total_vertices=self.graph.num_vertices,
            total_unique_edges=self.graph.num_unique_edges,
            affected_vertices=sorted(affected),
            candidate_nodes=self.current_candidate,
            candidate_density=self.current_density,
            batch_latency_ms=elapsed_ms,
            cumulative_latency_ms=self.cumulative_latency_ms,
            recomputation_count=self.recomputation_count,
            mode="warm_started_recomputation",
            recomputed_this_step=recomputed,
        )
        self.history.append(snap)
        return snap


class IncrementalHeuristicMaintainer(BaseStreamMaintainer):
    """
    Mode C: Incremental Heuristic Candidate Maintenance.

    Maintains candidate cluster S_cand and its exact density locally.
    Does NOT assume that only edges touching S_cand can change the optimum;
    external clusters can also become denser.
    Therefore, explicit configurable triggers govern full recomputation:
    - recompute_interval: periodic safety check every K batches.
    - external_edge_threshold: triggers recomputation when M_ext unique edges have been
      added strictly outside S_cand since the last recomputation.
    - external_degree_ratio: triggers recomputation when an external vertex's
      degree exceeds max(3, alpha * d(S_cand)).

    Disclaimer: This is an empirical heuristic that achieves sub-millisecond batch
    latencies; it is not guaranteed to maintain the exact optimum at all steps.
    """

    def __init__(
        self,
        algorithm: Literal["goldberg", "greedy_peeling", "greedy_plus_plus"] = "greedy_peeling",
        tolerance: float = 1e-4,
        recompute_interval: int = 5,
        external_edge_threshold: int = 10,
        external_degree_ratio: float = 1.5,
        hub_trigger_type: Literal[
            "global_degree", "candidate_incident", "hybrid"
        ] = "global_degree",
    ) -> None:
        valid_triggers = ("global_degree", "candidate_incident", "hybrid")
        if hub_trigger_type not in valid_triggers:
            raise ValueError(
                f"Invalid hub_trigger_type '{hub_trigger_type}'. "
                f"Must be one of: {', '.join(valid_triggers)}"
            )

        super().__init__(algorithm=algorithm, tolerance=tolerance)
        self.recompute_interval = recompute_interval
        self.external_edge_threshold = external_edge_threshold
        self.external_degree_ratio = external_degree_ratio
        self.hub_trigger_type = hub_trigger_type
        self._external_edges_since_recompute = 0

    def process_batch(self, batch: StreamBatch) -> StreamStepSnapshot:
        t0 = time.perf_counter()
        initial_edges = self.graph.num_unique_edges
        affected: set[str] = set()
        cand_set = set(self.current_candidate)

        # Pre-classify new unique edges to avoid counting parallel transactions
        # as new external edges
        unique_batch_pairs: set[tuple[str, str]] = set()
        for tx in batch.transactions:
            su, sv = str(tx.src), str(tx.dst)
            if su != sv:
                pair = (su, sv) if su < sv else (sv, su)
                unique_batch_pairs.add(pair)

        internal_unique_additions = 0
        external_unique_additions = 0
        boundary_unique_additions = 0
        for u, v in unique_batch_pairs:
            if not self.graph.has_edge(u, v):
                u_in = u in cand_set
                v_in = v in cand_set
                if u_in and v_in:
                    internal_unique_additions += 1
                elif not u_in and not v_in:
                    external_unique_additions += 1
                else:
                    boundary_unique_additions += 1

        for tx in batch.transactions:
            affected.add(tx.src)
            affected.add(tx.dst)
            self.graph.add_transaction(
                src=tx.src,
                dst=tx.dst,
                amount=tx.amount,
                timestamp=tx.timestamp,
                tx_id=tx.tx_id,
            )

        new_unique = self.graph.num_unique_edges - initial_edges
        self.version += 1

        self._external_edges_since_recompute += external_unique_additions

        # Check explicit trigger conditions
        trigger_periodic = batch.batch_index % self.recompute_interval == 0
        trigger_external = self._external_edges_since_recompute >= self.external_edge_threshold
        trigger_empty = not self.current_candidate or self.current_density <= 1e-9

        # Check if external node degree spiked above threshold
        trigger_hub = False
        if self.current_density > 0:
            if self.hub_trigger_type in ("candidate_incident", "hybrid") and cand_set:
                # Candidate-incident trigger: an external node connects to candidate members
                # with incident degree > current_density (which mathematically strictly
                # increases density of S_cand U {v})
                for v in affected:
                    if v not in cand_set and v in self.graph.graph:
                        inc_deg = sum(1 for u in self.graph.graph.neighbors(v) if u in cand_set)
                        if inc_deg > self.current_density:
                            trigger_hub = True
                            break

            if not trigger_hub and self.hub_trigger_type in ("global_degree", "hybrid"):
                # Global degree trigger: an external node's total degree in G exceeds threshold
                thresh = max(3.0, self.external_degree_ratio * self.current_density)
                for v in affected:
                    if v not in cand_set and self.graph.degree(v) > thresh:
                        trigger_hub = True
                        break

        should_recompute = trigger_periodic or trigger_external or trigger_empty or trigger_hub

        if should_recompute:
            self.current_candidate, self.current_density = self._compute_densest()
            self.recomputation_count += 1
            self._external_edges_since_recompute = 0
            recomputed = True
        else:
            # Incremental update: update density of current candidate
            # if internal unique edges were added
            if internal_unique_additions > 0 and cand_set:
                self.current_density = self.graph.density(cand_set)
            recomputed = False

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.cumulative_latency_ms += elapsed_ms

        snap = StreamStepSnapshot(
            batch_index=batch.batch_index,
            version=self.version,
            num_inserted_tx=len(batch.transactions),
            num_new_unique_edges=new_unique,
            total_vertices=self.graph.num_vertices,
            total_unique_edges=self.graph.num_unique_edges,
            affected_vertices=sorted(affected),
            candidate_nodes=self.current_candidate,
            candidate_density=self.current_density,
            batch_latency_ms=elapsed_ms,
            cumulative_latency_ms=self.cumulative_latency_ms,
            recomputation_count=self.recomputation_count,
            mode="incremental_heuristic",
            recomputed_this_step=recomputed,
        )
        self.history.append(snap)
        return snap
