"""
Tests for ringscope.stream_simulator maintenance modes (Modes A, B, and C).
"""

import pytest

from ringscope.stream_simulator import (
    FullRecomputationMaintainer,
    IncrementalHeuristicMaintainer,
    StreamBatch,
    TransactionRecord,
    WarmStartedMaintainer,
    generate_transaction_stream,
)


def test_mode_a_full_recomputation_increments_every_step():
    maintainer = FullRecomputationMaintainer(algorithm="greedy_peeling")
    batches, _ = generate_transaction_stream(
        n_background_accounts=10,
        n_background_transactions=15,
        batch_size=3,
        seed=1,
    )

    for idx, b in enumerate(batches):
        snap = maintainer.process_batch(b)
        assert snap.recomputed_this_step is True
        assert snap.recomputation_count == idx + 1
        assert snap.version == idx + 1
        assert snap.total_vertices > 0
        assert snap.candidate_density >= 0.0


def test_mode_b_warm_started_saves_recomputations():
    # In warm-started mode, parallel edges should skip or prune recomputations
    maintainer = WarmStartedMaintainer(algorithm="goldberg")

    # Batch 1: Triangle
    b1 = StreamBatch(
        batch_index=0,
        transactions=[
            TransactionRecord("A", "B", 10.0, 100.0, "T1"),
            TransactionRecord("B", "C", 10.0, 101.0, "T2"),
            TransactionRecord("C", "A", 10.0, 102.0, "T3"),
        ],
    )
    snap1 = maintainer.process_batch(b1)
    assert snap1.candidate_density == pytest.approx(1.0)
    assert maintainer.recomputation_count == 1

    # Batch 2: Parallel transaction records on existing triangle edges (no topology change)
    b2 = StreamBatch(
        batch_index=1,
        transactions=[
            TransactionRecord("A", "B", 20.0, 103.0, "T4"),
            TransactionRecord("B", "C", 20.0, 104.0, "T5"),
        ],
    )
    snap2 = maintainer.process_batch(b2)
    assert snap2.recomputed_this_step is False
    assert snap2.num_new_unique_edges == 0
    assert maintainer.recomputation_count == 1  # Recomputation was saved!
    assert snap2.candidate_density == pytest.approx(1.0)


def test_mode_c_incremental_triggers():
    maintainer = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=3,
        external_edge_threshold=4,
    )

    # Initial batch establishes candidate
    b0 = StreamBatch(
        batch_index=0,
        transactions=[
            TransactionRecord("C1", "C2", 10.0, 100.0, "T0"),
            TransactionRecord("C2", "C3", 10.0, 101.0, "T1"),
            TransactionRecord("C3", "C1", 10.0, 102.0, "T2"),
        ],
    )
    snap0 = maintainer.process_batch(b0)
    assert snap0.recomputed_this_step is True

    # Batch 1: Single external edge below threshold
    b1 = StreamBatch(
        batch_index=1,
        transactions=[
            TransactionRecord("Ext1", "Ext2", 5.0, 103.0, "T3"),
        ],
    )
    snap1 = maintainer.process_batch(b1)
    assert snap1.recomputed_this_step is False

    # Batch 2: 4 external edges triggering threshold
    b2 = StreamBatch(
        batch_index=2,
        transactions=[
            TransactionRecord("Ext2", "Ext3", 5.0, 104.0, "T4"),
            TransactionRecord("Ext3", "Ext4", 5.0, 105.0, "T5"),
            TransactionRecord("Ext4", "Ext2", 5.0, 106.0, "T6"),
            TransactionRecord("Ext4", "Ext5", 5.0, 107.0, "T7"),
        ],
    )
    snap2 = maintainer.process_batch(b2)
    # Triggered due to external_edge_threshold >= 4
    assert snap2.recomputed_this_step is True


def test_snapshot_to_dict_fields():
    maintainer = FullRecomputationMaintainer()
    b = StreamBatch(
        batch_index=0,
        transactions=[TransactionRecord("U1", "U2", 10.0, 100.0, "TX1")],
    )
    snap = maintainer.process_batch(b)
    d = snap.to_dict()
    for key in (
        "batch_index",
        "version",
        "num_inserted_tx",
        "num_new_unique_edges",
        "candidate_density",
        "batch_latency_ms",
        "cumulative_latency_ms",
        "recomputation_count",
    ):
        assert key in d


def test_mode_c_repeated_transactions_do_not_increment_external_count():
    """
    Verify that parallel/duplicate transactions between existing nodes
    do not trigger external edge threshold.
    """
    maintainer = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=100,  # disable periodic
        external_edge_threshold=5,
    )
    # Batch 0: candidate
    maintainer.process_batch(
        StreamBatch(
            batch_index=0,
            transactions=[
                TransactionRecord("C1", "C2", 10.0, 1.0, "T0"),
                TransactionRecord("C2", "C3", 10.0, 2.0, "T1"),
                TransactionRecord("C3", "C1", 10.0, 3.0, "T2"),
            ],
        )
    )
    # Batch 1: introduces one external edge
    snap1 = maintainer.process_batch(
        StreamBatch(
            batch_index=1,
            transactions=[TransactionRecord("X", "Y", 10.0, 4.0, "T3")],
        )
    )
    assert snap1.recomputed_this_step is False
    assert maintainer._external_edges_since_recompute == 1

    # Batch 2: sends 10 duplicate transactions for edge (X, Y)
    snap2 = maintainer.process_batch(
        StreamBatch(
            batch_index=2,
            transactions=[
                TransactionRecord("X", "Y", 10.0, float(5 + i), f"TD_{i}") for i in range(10)
            ],
        )
    )
    # Since (X, Y) was already an edge, no new unique edges were added
    assert snap2.recomputed_this_step is False
    assert snap2.num_new_unique_edges == 0
    assert maintainer._external_edges_since_recompute == 1  # Still 1, NOT 11!


def test_mode_c_internal_edge_addition_updates_density_locally():
    """
    Verify that adding an internal edge updates candidate density
    without full recomputation.
    """
    maintainer = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=100,
        external_edge_threshold=100,
    )
    # Batch 0: 4-cycle on C1, C2, C3, C4 -> density 4/4 = 1.0
    maintainer.process_batch(
        StreamBatch(
            batch_index=0,
            transactions=[
                TransactionRecord("C1", "C2", 1.0, 1.0, "T1"),
                TransactionRecord("C2", "C3", 1.0, 2.0, "T2"),
                TransactionRecord("C3", "C4", 1.0, 3.0, "T3"),
                TransactionRecord("C4", "C1", 1.0, 4.0, "T4"),
            ],
        )
    )
    initial_recomps = maintainer.recomputation_count

    # Batch 1: Add chord (C1, C3) inside candidate -> density becomes 5/4 = 1.25
    snap1 = maintainer.process_batch(
        StreamBatch(
            batch_index=1,
            transactions=[TransactionRecord("C1", "C3", 1.0, 5.0, "T5")],
        )
    )
    assert snap1.recomputed_this_step is False
    assert maintainer.recomputation_count == initial_recomps
    assert snap1.candidate_density == pytest.approx(1.25)


def test_mode_c_disjoint_cluster_recovery_on_trigger():
    """
    Verify that an external disjoint cluster that becomes denser
    is detected when trigger fires.
    """
    maintainer = IncrementalHeuristicMaintainer(
        algorithm="goldberg",
        recompute_interval=5,
        external_edge_threshold=6,
    )
    # Initial: Triangle on A, B, C (density 1.0)
    maintainer.process_batch(
        StreamBatch(
            batch_index=0,
            transactions=[
                TransactionRecord("A", "B", 1.0, 1.0, "T1"),
                TransactionRecord("B", "C", 1.0, 2.0, "T2"),
                TransactionRecord("C", "A", 1.0, 3.0, "T3"),
            ],
        )
    )
    assert maintainer.current_density == pytest.approx(1.0)

    # Inject disjoint K4 on D1..D4 (density 1.5, 6 unique edges) in one batch
    k4_txs = []
    nodes = ["D1", "D2", "D3", "D4"]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            k4_txs.append(TransactionRecord(nodes[i], nodes[j], 1.0, 10.0, f"TK_{i}_{j}"))

    snap_k4 = maintainer.process_batch(StreamBatch(batch_index=1, transactions=k4_txs))
    # 6 new unique external edges >= external_edge_threshold (6) -> triggers recomputation
    assert snap_k4.recomputed_this_step is True
    assert snap_k4.candidate_density == pytest.approx(1.5)
    assert set(snap_k4.candidate_nodes) == {"D1", "D2", "D3", "D4"}
