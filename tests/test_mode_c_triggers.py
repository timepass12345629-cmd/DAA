"""
tests/test_mode_c_triggers.py — Regression and diagnostic tests for Mode C triggers.

Evaluates:
1. Disjoint dense cluster emerging outside the current candidate and its detection delay.
2. High-degree external star hub with no connections to candidate.
3. External node gaining connections to candidate members (density increase verified
   mathematically and algorithmically).
4. Parallel transactions not incorrectly inflating unique-edge counts.
"""

from __future__ import annotations

import pytest

from ringscope.stream_simulator import (
    FullRecomputationMaintainer,
    IncrementalHeuristicMaintainer,
    StreamBatch,
    TransactionRecord,
)


def test_disjoint_dense_cluster_detection_delay():
    """
    Test 1: A disjoint dense cluster (K4 clique, density 1.50) emerges outside
    the initial candidate C1 (4-cycle, density 1.00).

    Verifies the exact detection delay (in batches) under Mode C with default
    triggers (recompute_interval=5, external_edge_threshold=10, external_degree_ratio=1.5).
    """
    # Batch 0: C1 forms a 4-cycle {A, B, C, D}, density = 4/4 = 1.00
    b0 = StreamBatch(
        0,
        [
            TransactionRecord("A", "B", 10.0, 1.0, "tx_0"),
            TransactionRecord("B", "C", 10.0, 1.0, "tx_1"),
            TransactionRecord("C", "D", 10.0, 1.0, "tx_2"),
            TransactionRecord("D", "A", 10.0, 1.0, "tx_3"),
        ],
    )

    # Disjoint K4 edges: (X1, X2), (X2, X3), (X3, X4), (X4, X1), (X1, X3), (X2, X4)
    # Total 6 edges across 4 nodes -> density 6/4 = 1.50 > 1.00
    # Injected in 3 batches of 2 edges each:
    b1 = StreamBatch(
        1,
        [
            TransactionRecord("X1", "X2", 10.0, 2.0, "tx_4"),
            TransactionRecord("X2", "X3", 10.0, 2.0, "tx_5"),
        ],
    )
    b2 = StreamBatch(
        2,
        [
            TransactionRecord("X3", "X4", 10.0, 3.0, "tx_6"),
            TransactionRecord("X4", "X1", 10.0, 3.0, "tx_7"),
        ],
    )
    b3 = StreamBatch(
        3,
        [
            TransactionRecord("X1", "X3", 10.0, 4.0, "tx_8"),
            TransactionRecord("X2", "X4", 10.0, 4.0, "tx_9"),
        ],
    )
    # Batch 4: Unrelated neutral transaction
    b4 = StreamBatch(
        4,
        [
            TransactionRecord("Y1", "Y2", 10.0, 5.0, "tx_10"),
        ],
    )
    # Batch 5: Periodic trigger boundary (batch_index % 5 == 0)
    b5 = StreamBatch(
        5,
        [
            TransactionRecord("Y2", "Y3", 10.0, 6.0, "tx_11"),
        ],
    )

    m_full = FullRecomputationMaintainer(algorithm="greedy_peeling")
    m_inc = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=5,
        external_edge_threshold=10,
        external_degree_ratio=1.5,
    )

    # Batch 0
    s_f0 = m_full.process_batch(b0)
    s_i0 = m_inc.process_batch(b0)
    assert set(s_f0.candidate_nodes) == {"A", "B", "C", "D"}
    assert set(s_i0.candidate_nodes) == {"A", "B", "C", "D"}
    assert s_i0.candidate_density == pytest.approx(1.00)

    # Batches 1 and 2: K4 is building
    m_full.process_batch(b1)
    s_i1 = m_inc.process_batch(b1)
    assert s_i1.recomputed_this_step is False

    m_full.process_batch(b2)
    s_i2 = m_inc.process_batch(b2)
    assert s_i2.recomputed_this_step is False

    # Batch 3: K4 is complete. Mode A immediately finds {X1, X2, X3, X4} with density 1.50
    s_f3 = m_full.process_batch(b3)
    assert set(s_f3.candidate_nodes) == {"X1", "X2", "X3", "X4"}
    assert s_f3.candidate_density == pytest.approx(1.50)

    s_i3 = m_inc.process_batch(b3)
    # Document current baseline behavior:
    # Mode C has NOT recomputed because:
    # - batch_index 3 % 5 != 0
    # - external edges since recompute = 6 < 10
    # - max degree of X nodes is 3.0, which does NOT strictly exceed max(3.0, 1.5 * 1.0) = 3.0
    assert s_i3.recomputed_this_step is False
    assert set(s_i3.candidate_nodes) == {"A", "B", "C", "D"}
    assert s_i3.candidate_density == pytest.approx(1.00)

    # Batch 4: Still below triggers
    m_full.process_batch(b4)
    s_i4 = m_inc.process_batch(b4)
    assert s_i4.recomputed_this_step is False

    # Batch 5: Periodic trigger fires! Mode C catches up and finds K4
    m_full.process_batch(b5)
    s_i5 = m_inc.process_batch(b5)
    assert s_i5.recomputed_this_step is True
    assert set(s_i5.candidate_nodes) == {"X1", "X2", "X3", "X4"}
    assert s_i5.candidate_density == pytest.approx(1.50)


def test_high_degree_external_hub_without_candidate_edges():
    """
    Test 2: An external star hub H connects to 10 leaf accounts {L1..L10},
    with ZERO connections to the candidate C1 = {A, B, C} (density 1.0).

    A pure star hub has density 10/11 = 0.909, which is LESS dense than C1 (1.0).
    Examines whether the global degree trigger fires unnecessarily.
    """
    b0 = StreamBatch(
        0,
        [
            TransactionRecord("A", "B", 10.0, 1.0, "tx_0"),
            TransactionRecord("B", "C", 10.0, 1.0, "tx_1"),
            TransactionRecord("C", "A", 10.0, 1.0, "tx_2"),
        ],
    )

    # External hub H connects to 10 leaves in batch 1
    # Notice: batch_index 1 is NOT a periodic boundary (1 % 5 != 0)
    # external_edge_threshold = 15 (set high so only hub trigger can trip)
    b1 = StreamBatch(
        1,
        [TransactionRecord("HUB", f"LEAF_{i}", 10.0, 2.0, f"tx_hub_{i}") for i in range(10)],
    )

    m_inc = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=5,
        external_edge_threshold=15,
        external_degree_ratio=1.5,
    )

    s0 = m_inc.process_batch(b0)
    assert set(s0.candidate_nodes) == {"A", "B", "C"}
    assert s0.candidate_density == pytest.approx(1.0)

    s1 = m_inc.process_batch(b1)

    # 1. Under default global_degree trigger:
    # HUB has degree 10 > max(3.0, 1.5 * 1.0) = 3.0.
    # Therefore, trigger_hub = True and it executes an unnecessary full recomputation.
    assert s1.recomputed_this_step is True
    assert set(s1.candidate_nodes) == {"A", "B", "C"}
    assert s1.candidate_density == pytest.approx(1.0)

    # 2. Under candidate_incident trigger:
    # HUB has incident degree 0 into {A, B, C}. 0 > 1.0 is False!
    # Therefore, candidate_incident correctly bypasses recomputation!
    m_cand = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=5,
        external_edge_threshold=15,
        hub_trigger_type="candidate_incident",
    )
    m_cand.process_batch(b0)
    s1_cand = m_cand.process_batch(b1)
    assert s1_cand.recomputed_this_step is False
    assert set(s1_cand.candidate_nodes) == {"A", "B", "C"}
    assert s1_cand.candidate_density == pytest.approx(1.0)


def test_external_node_augmenting_candidate_density():
    """
    Test 3: An external node W connects to 3 members of candidate C1 = {A, B, C, D}.
    Candidate has 4 edges across 4 nodes (4-cycle, density 1.00).

    Mathematical verification:
    Augmented set C1 U {W} has:
    |V| = 4 + 1 = 5
    |E| = 4 + 3 = 7
    Density rho(C1 U {W}) = 7 / 5 = 1.40 > 1.00.

    Examines:
    1. Mathematical density of explicit set.
    2. Candidate and density returned by greedy peeling solver.
    3. Contrast behavior under global_degree vs candidate_incident triggering.
    """
    b0 = StreamBatch(
        0,
        [
            TransactionRecord("A", "B", 10.0, 1.0, "tx_0"),
            TransactionRecord("B", "C", 10.0, 1.0, "tx_1"),
            TransactionRecord("C", "D", 10.0, 1.0, "tx_2"),
            TransactionRecord("D", "A", 10.0, 1.0, "tx_3"),
        ],
    )

    # Node W connects to A, B, and C in batch 1
    # (batch_index=1 is not periodic, external edges=0 because edges touch candidate)
    b1 = StreamBatch(
        1,
        [
            TransactionRecord("W", "A", 10.0, 2.0, "tx_w1"),
            TransactionRecord("W", "B", 10.0, 2.0, "tx_w2"),
            TransactionRecord("W", "C", 10.0, 2.0, "tx_w3"),
        ],
    )

    # --- Part A: Default global_degree trigger ---
    m_global = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=5,
        external_edge_threshold=10,
        external_degree_ratio=1.5,
        hub_trigger_type="global_degree",
    )
    m_global.process_batch(b0)
    s1_g = m_global.process_batch(b1)

    # Math density check
    augmented_nodes = {"A", "B", "C", "D", "W"}
    math_density = m_global.graph.density(augmented_nodes)
    assert math_density == pytest.approx(7.0 / 5.0)  # 1.40

    # In global_degree mode: W degree 3 is NOT strictly > max(3.0, 1.5) = 3.0.
    # Therefore it misses the trigger!
    assert s1_g.recomputed_this_step is False
    assert set(s1_g.candidate_nodes) == {"A", "B", "C", "D"}
    assert s1_g.candidate_density == pytest.approx(1.00)

    # --- Part B: Candidate-incident trigger ---
    m_incident = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=5,
        external_edge_threshold=10,
        hub_trigger_type="candidate_incident",
    )
    m_incident.process_batch(b0)
    s1_inc = m_incident.process_batch(b1)

    # In candidate_incident mode: W has 3 incident edges into {A, B, C, D}.
    # 3 > current_density (1.00) is TRUE!
    # It triggers a recomputation!
    assert s1_inc.recomputed_this_step is True

    # Check greedy peeling's returned candidate and density:
    # Greedy peeling removes D (deg 2), leaving {A, B, C, W} with 5 edges (density 5/4 = 1.25)
    # or keeps {A, B, C, D, W} with 7 edges (density 7/5 = 1.40).
    # Since 1.40 > 1.25, greedy peeling picks {A, B, C, D, W} with density 1.40!
    assert set(s1_inc.candidate_nodes) == {"A", "B", "C", "D", "W"}
    assert s1_inc.candidate_density == pytest.approx(1.40)


def test_parallel_transactions_do_not_inflate_external_counter():
    """
    Test 4: In a single batch, 10 duplicate transactions for the exact same
    external edge (E1, E2) arrive.
    Verify that unique-edge count increases by 1, and the external edge counter
    is incremented by 1 (not 10).
    """
    b0 = StreamBatch(
        0,
        [
            TransactionRecord("A", "B", 10.0, 1.0, "tx_0"),
            TransactionRecord("B", "C", 10.0, 1.0, "tx_1"),
            TransactionRecord("C", "A", 10.0, 1.0, "tx_2"),
        ],
    )

    # Batch 1: 10 transactions between E1 and E2
    b1 = StreamBatch(
        1,
        [TransactionRecord("E1", "E2", 5.0, 2.0 + i * 0.1, f"dup_{i}") for i in range(10)],
    )

    m_inc = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=5,
        external_edge_threshold=5,  # Threshold is 5: if counted as 10, it would fire!
        external_degree_ratio=2.0,
    )

    m_inc.process_batch(b0)
    assert m_inc._external_edges_since_recompute == 0

    s1 = m_inc.process_batch(b1)

    # The external edge counter must be 1 (only 1 unique edge {E1, E2}), NOT 10!
    assert m_inc._external_edges_since_recompute == 1
    # Since 1 < 5, trigger_external should not fire
    assert s1.recomputed_this_step is False
    assert s1.num_new_unique_edges == 1
    assert s1.num_inserted_tx == 10


def test_hub_trigger_type_runtime_validation():
    """
    Test runtime validation of hub_trigger_type:
    Accepts: 'global_degree', 'candidate_incident', 'hybrid'.
    Rejects any invalid string with ValueError.
    """
    # Valid values should succeed
    for valid in ("global_degree", "candidate_incident", "hybrid"):
        m = IncrementalHeuristicMaintainer(hub_trigger_type=valid)
        assert m.hub_trigger_type == valid

    # Invalid values should raise ValueError
    with pytest.raises(ValueError, match="Invalid hub_trigger_type 'invalid_mode'"):
        IncrementalHeuristicMaintainer(hub_trigger_type="invalid_mode")

    with pytest.raises(ValueError, match="Invalid hub_trigger_type"):
        IncrementalHeuristicMaintainer(hub_trigger_type="")


def test_adversarial_disconnected_dense_cluster_delay_across_strategies():
    """
    Adversarial test: An initial candidate C1 of 4 nodes has density 1.0 (4-cycle).
    Between periodic refreshes (e.g., at batch index 1, 2, 3 where recompute_interval=8),
    a strictly denser disconnected cluster K5 (5 nodes, 10 edges, density 2.0) arrives.
    
    Measures the exact detection delay (in batches) for:
    - Mode A (Full Recomputation): 0 batches delay (detects immediately at batch 3).
    - Mode C (Global Degree): Detects at batch 3 because deg_G(K5 nodes) = 4 > max(3.0, 1.5).
    - Mode C (Hybrid): Detects at batch 3 because hybrid includes global degree check.
    - Mode C (Candidate-Incident): Lags until periodic refresh or external threshold!
    """
    # Batch 0: C1 forms 4-cycle {A, B, C, D}, density 1.00
    b0 = StreamBatch(
        0,
        [
            TransactionRecord("A", "B", 10.0, 1.0, "tx_0"),
            TransactionRecord("B", "C", 10.0, 1.0, "tx_1"),
            TransactionRecord("C", "D", 10.0, 1.0, "tx_2"),
            TransactionRecord("D", "A", 10.0, 1.0, "tx_3"),
        ],
    )

    # Disconnected K5 has 10 edges across 5 nodes {K0..K4}, density = 10/5 = 2.00
    # Injected across batches 1, 2, 3 (3 edges, 3 edges, 4 edges):
    k5_edges = [
        ("K0", "K1"), ("K0", "K2"), ("K0", "K3"),
        ("K0", "K4"), ("K1", "K2"), ("K1", "K3"),
        ("K1", "K4"), ("K2", "K3"), ("K2", "K4"), ("K3", "K4"),
    ]
    b1 = StreamBatch(
        1,
        [TransactionRecord(u, v, 10.0, 2.0, f"k5_{i}") for i, (u, v) in enumerate(k5_edges[:3])],
    )
    b2 = StreamBatch(
        2,
        [
            TransactionRecord(u, v, 10.0, 3.0, f"k5_{i}")
            for i, (u, v) in enumerate(k5_edges[3:6], 3)
        ],
    )
    b3 = StreamBatch(
        3,
        [
            TransactionRecord(u, v, 10.0, 4.0, f"k5_{i}")
            for i, (u, v) in enumerate(k5_edges[6:10], 6)
        ],
    )
    b4 = StreamBatch(4, [TransactionRecord("Z1", "Z2", 10.0, 5.0, "z1")])
    b5 = StreamBatch(5, [TransactionRecord("Z2", "Z3", 10.0, 6.0, "z2")])
    b6 = StreamBatch(6, [TransactionRecord("Z3", "Z4", 10.0, 7.0, "z3")])
    b7 = StreamBatch(7, [TransactionRecord("Z4", "Z5", 10.0, 8.0, "z4")])
    b8 = StreamBatch(8, [TransactionRecord("Z5", "Z1", 10.0, 9.0, "z5")])

    stream = [b0, b1, b2, b3, b4, b5, b6, b7, b8]

    # Mode A
    mA = FullRecomputationMaintainer(algorithm="greedy_peeling")
    # Mode C Global
    mC_glob = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=8,
        external_edge_threshold=20,  # high threshold so only hub trigger or periodic fires
        hub_trigger_type="global_degree",
    )
    # Mode C Candidate-Incident
    mC_cand = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=8,
        external_edge_threshold=20,
        hub_trigger_type="candidate_incident",
    )
    # Mode C Hybrid
    mC_hyb = IncrementalHeuristicMaintainer(
        algorithm="greedy_peeling",
        recompute_interval=8,
        external_edge_threshold=20,
        hub_trigger_type="hybrid",
    )

    delays = {"Mode A": None, "Global": None, "Candidate-Incident": None, "Hybrid": None}

    for b in stream:
        sA = mA.process_batch(b)
        sG = mC_glob.process_batch(b)
        sC = mC_cand.process_batch(b)
        sH = mC_hyb.process_batch(b)

        k5_nodes = {"K0", "K1", "K2", "K3", "K4"}
        if delays["Mode A"] is None and set(sA.candidate_nodes) == k5_nodes:
            delays["Mode A"] = b.batch_index
        if delays["Global"] is None and set(sG.candidate_nodes) == k5_nodes:
            delays["Global"] = b.batch_index
        if delays["Candidate-Incident"] is None and set(sC.candidate_nodes) == k5_nodes:
            delays["Candidate-Incident"] = b.batch_index
        if delays["Hybrid"] is None and set(sH.candidate_nodes) == k5_nodes:
            delays["Hybrid"] = b.batch_index

    # Mode A detects K5 at batch 3 (0 delay)
    assert delays["Mode A"] == 3
    # Global degree detects at batch 3 (degree 4 > 3.0) -> delay 0 vs Mode A
    assert delays["Global"] == 3
    # Hybrid detects at batch 3 -> delay 0 vs Mode A
    assert delays["Hybrid"] == 3
    # Candidate-Incident has NO connections to candidate, so it lags until batch 8 (periodic)!
    # Detection delay = 8 - 3 = 5 batches delay!
    assert delays["Candidate-Incident"] == 8


@pytest.mark.asyncio
async def test_api_stream_start_hub_trigger_passthrough():
    """
    Test API / BackendService layer passthrough of hub_trigger_type
    via StreamStartRequest.config.
    """
    from ringscope.service import BackendService

    service = BackendService()

    # 1. Default (no config provided) -> should be 'global_degree'
    service.start_stream(
        stream_id="stream_test_default",
        mode="incremental_heuristic",
        algorithm="greedy_peeling",
        batch_size=3,
        initial_graph_id=None,
        config={},
    )
    session_default = service.streams["stream_test_default"]
    assert session_default.maintainer.hub_trigger_type == "global_degree"

    # 2. Explicit 'candidate_incident' passed in config
    service.start_stream(
        stream_id="stream_test_cand",
        mode="incremental_heuristic",
        algorithm="greedy_peeling",
        batch_size=3,
        initial_graph_id=None,
        config={"hub_trigger_type": "candidate_incident"},
    )
    session_cand = service.streams["stream_test_cand"]
    assert session_cand.maintainer.hub_trigger_type == "candidate_incident"

    # 3. Explicit 'hybrid' passed in config
    service.start_stream(
        stream_id="stream_test_hyb",
        mode="incremental_heuristic",
        algorithm="greedy_peeling",
        batch_size=3,
        initial_graph_id=None,
        config={"hub_trigger_type": "hybrid"},
    )
    session_hyb = service.streams["stream_test_hyb"]
    assert session_hyb.maintainer.hub_trigger_type == "hybrid"

    # 4. Invalid trigger passed in config -> raises ValueError
    with pytest.raises(ValueError, match="Invalid hub_trigger_type"):
        service.start_stream(
            stream_id="stream_test_invalid",
            mode="incremental_heuristic",
            algorithm="greedy_peeling",
            batch_size=3,
            initial_graph_id=None,
            config={"hub_trigger_type": "invalid_type"},
        )

