"""
Tests for ringscope.algorithms.streaming.

Invariants
----------
1. Empty detector has 0 nodes/edges.
2. Edges inserted within the window are visible.
3. Edges older than the window are evicted.
4. Rings planted inside the window are detected.
5. Reset clears all state.
6. Out-of-order edges are accepted.
"""

import pytest

from ringscope.algorithms.streaming import StreamEdge, StreamingRingDetector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_TS = 1_700_000_000.0
WINDOW = 600.0  # 10 minutes


def make_edge(src: str, dst: str, ts: float, amount: float = 100.0) -> StreamEdge:
    return StreamEdge(src=src, dst=dst, amount=amount, timestamp=ts)


def triangle_edges(base_ts: float) -> list[StreamEdge]:
    """Return three edges forming A→B→C→A."""
    return [
        make_edge("A", "B", base_ts),
        make_edge("B", "C", base_ts + 1),
        make_edge("C", "A", base_ts + 2),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_detector():
    det = StreamingRingDetector(window_size=WINDOW)
    snap = det.current_snapshot()
    assert snap.num_nodes == 0
    assert snap.num_edges == 0
    assert snap.ring_summary["count"] == 0


def test_single_edge_inserted():
    det = StreamingRingDetector(window_size=WINDOW)
    det.ingest(make_edge("X", "Y", BASE_TS))
    snap = det.current_snapshot()
    assert snap.num_edges == 1
    assert snap.num_nodes == 2


def test_ring_detected_in_window():
    det = StreamingRingDetector(window_size=WINDOW, max_cycle_length=5)
    for e in triangle_edges(BASE_TS):
        snap = det.ingest(e)
    assert snap.ring_summary["count"] >= 1
    ring_nodes = {n for r in snap.rings for n in r["nodes"]}
    assert {"A", "B", "C"}.issubset(ring_nodes)


def test_edge_evicted_after_window():
    det = StreamingRingDetector(window_size=WINDOW)
    # Add triangle at BASE_TS
    for e in triangle_edges(BASE_TS):
        det.ingest(e)
    # Advance clock beyond window
    late_edge = make_edge("P", "Q", BASE_TS + WINDOW + 100)
    snap = det.ingest(late_edge)
    # Triangle edges should be evicted
    assert snap.num_edges <= 1  # only the late P→Q edge


def test_reset_clears_state():
    det = StreamingRingDetector(window_size=WINDOW)
    for e in triangle_edges(BASE_TS):
        det.ingest(e)
    det.reset()
    snap = det.current_snapshot()
    assert snap.num_nodes == 0
    assert snap.num_edges == 0
    assert snap.ring_summary["count"] == 0


def test_out_of_order_edge_accepted():
    det = StreamingRingDetector(window_size=WINDOW)
    det.ingest(make_edge("A", "B", BASE_TS + 100))
    # Insert an older edge — should be accepted but clock stays at BASE_TS+100
    snap = det.ingest(make_edge("B", "C", BASE_TS + 50))
    assert snap.window_end == BASE_TS + 100
    assert snap.num_edges == 2


def test_bulk_ingest_returns_one_snapshot_per_edge():
    det = StreamingRingDetector(window_size=WINDOW)
    edges = triangle_edges(BASE_TS)
    snaps = det.bulk_ingest(edges)
    assert len(snaps) == 3


def test_processing_time_recorded():
    det = StreamingRingDetector(window_size=WINDOW)
    snap = det.ingest(make_edge("A", "B", BASE_TS))
    assert snap.processing_time_ms >= 0.0


def test_amount_accumulation():
    """Two edges on same pair should accumulate amount."""
    det = StreamingRingDetector(window_size=WINDOW)
    det.ingest(make_edge("A", "B", BASE_TS, amount=100.0))
    det.ingest(make_edge("A", "B", BASE_TS + 1, amount=200.0))
    snap = det.current_snapshot()
    assert snap.num_edges == 1  # one aggregated edge
    assert det.graph["A"]["B"]["amount"] == pytest.approx(300.0)


def test_incremental_vs_full_detection_equivalence():
    """Verify incremental ring cache exactly matches full Johnson recomputation."""
    det_inc = StreamingRingDetector(window_size=WINDOW, max_cycle_length=6, incremental=True)
    det_full = StreamingRingDetector(window_size=WINDOW, max_cycle_length=6, incremental=False)

    stream = [
        make_edge("A", "B", BASE_TS),
        make_edge("B", "C", BASE_TS + 1),
        make_edge("C", "A", BASE_TS + 2),
        make_edge("C", "D", BASE_TS + 3),
        make_edge("D", "A", BASE_TS + 4),
        make_edge("X", "Y", BASE_TS + 5),
        make_edge("Y", "Z", BASE_TS + 6),
        make_edge("Z", "X", BASE_TS + 7),
    ]

    for edge in stream:
        s_inc = det_inc.ingest(edge)
        s_full = det_full.ingest(edge)
        assert s_inc.ring_summary["count"] == s_full.ring_summary["count"]
        inc_sets = {frozenset(r["nodes"]) for r in s_inc.rings}
        full_sets = {frozenset(r["nodes"]) for r in s_full.rings}
        assert inc_sets == full_sets
