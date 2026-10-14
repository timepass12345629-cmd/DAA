"""
Tests for ringscope.eval_harness (Evaluation harness metrics and exporter).
"""

import json
from pathlib import Path

import pytest

from ringscope.eval_harness import (
    calculate_density_gap,
    calculate_latency_percentiles,
    calculate_overlap_metrics,
    evaluate_streaming_modes,
    export_results_to_csv,
    export_results_to_json,
)
from ringscope.stream_simulator import generate_transaction_stream


def test_calculate_overlap_metrics():
    # Perfect match
    m_perf = calculate_overlap_metrics({"A", "B", "C"}, {"A", "B", "C"})
    assert m_perf["precision"] == 1.0
    assert m_perf["recall"] == 1.0
    assert m_perf["f1"] == 1.0
    assert m_perf["jaccard"] == 1.0

    # Partial match: pred={A, B}, gt={B, C} -> intersection={B} (1), union={A,B,C} (3)
    m_part = calculate_overlap_metrics({"A", "B"}, {"B", "C"})
    assert m_part["precision"] == pytest.approx(0.5)
    assert m_part["recall"] == pytest.approx(0.5)
    assert m_part["f1"] == pytest.approx(0.5)
    assert m_part["jaccard"] == pytest.approx(1.0 / 3.0, abs=1e-3)

    # Disjoint
    m_dis = calculate_overlap_metrics({"A"}, {"B"})
    assert m_dis["precision"] == 0.0
    assert m_dis["recall"] == 0.0
    assert m_dis["f1"] == 0.0
    assert m_dis["jaccard"] == 0.0

    # Empty
    m_empty = calculate_overlap_metrics(set(), set())
    assert m_empty["f1"] == 1.0


def test_calculate_density_gap():
    gap = calculate_density_gap(candidate_density=1.5, exact_density=2.0)
    assert gap["candidate_density"] == 1.5
    assert gap["exact_density"] == 2.0
    assert gap["absolute_gap"] == pytest.approx(0.5)
    assert gap["approximation_ratio"] == pytest.approx(0.75)


def test_calculate_latency_percentiles():
    lats = [1.0, 2.0, 3.0, 4.0, 5.0, 10.0]
    pct = calculate_latency_percentiles(lats)
    assert pct["mean"] == pytest.approx(4.167, abs=1e-2)
    assert pct["p50"] >= 1.0
    assert pct["p99"] >= pct["p95"] >= pct["p50"]


def test_evaluate_streaming_modes_integration():
    batches, planted = generate_transaction_stream(
        n_background_accounts=12,
        n_background_transactions=15,
        batch_size=3,
        planted_cluster_size=4,
        seed=10,
    )
    results = evaluate_streaming_modes(
        batches=batches,
        planted_cluster=planted,
        algorithm="greedy_peeling",
        exact_reference_solver=True,
    )

    assert len(results) == 3
    modes = {r.mode for r in results}
    assert modes == {
        "full_recomputation",
        "warm_started_recomputation",
        "incremental_heuristic",
    }

    for r in results:
        assert r.total_batches > 0
        assert r.final_density >= 0.0
        assert 0.0 <= r.precision <= 1.0
        assert 0.0 <= r.recall <= 1.0
        assert r.total_runtime_ms > 0.0
        assert not r.timed_out


def test_export_results_to_json_and_csv(tmp_path: Path):
    sample_records = [
        {"mode": "full", "density": 1.5, "runtime_ms": 12.3},
        {"mode": "warm", "density": 1.5, "runtime_ms": 4.5},
    ]
    json_path = tmp_path / "test_out.json"
    csv_path = tmp_path / "test_out.csv"

    export_results_to_json(sample_records, json_path)
    export_results_to_csv(sample_records, csv_path)

    assert json_path.is_file()
    assert csv_path.is_file()

    with open(json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert len(loaded) == 2
    assert loaded[0]["mode"] == "full"
