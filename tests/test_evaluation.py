"""
Tests for ringscope.evaluation benchmark suite.
"""

from ringscope.evaluation import (
    benchmark_streaming_throughput,
    evaluate_densest_subgraph,
    evaluate_ring_detection,
)


def test_evaluate_ring_detection():
    res = evaluate_ring_detection(ring_sizes=[3, 4], noise_edges=10, seed=7)
    assert res.planted_count == 2
    assert res.recall == 1.0  # all planted rings detected
    assert res.precision > 0.0
    assert res.f1 > 0.0
    assert res.elapsed_ms > 0.0
    d = res.to_dict()
    assert "recall" in d and "precision" in d and "f1" in d


def test_evaluate_densest_subgraph():
    res = evaluate_densest_subgraph(n_accounts=30, n_transactions=60, seed=42)
    assert res.greedy_density > 0.0
    assert res.exact_density >= res.greedy_density - 1e-6
    assert 0.5 <= res.approx_ratio <= 1.0001
    assert 0.0 <= res.jaccard_similarity <= 1.0
    assert res.greedy_time_ms >= 0.0
    assert res.exact_time_ms >= 0.0


def test_benchmark_streaming_throughput():
    res_inc = benchmark_streaming_throughput(
        n_transactions=50, window_size=600.0, incremental=True, seed=1
    )
    res_full = benchmark_streaming_throughput(
        n_transactions=50, window_size=600.0, incremental=False, seed=1
    )

    assert res_inc.throughput_tps > 0.0
    assert res_full.throughput_tps > 0.0
    assert res_inc.mean_latency_ms >= 0.0
    assert res_inc.p95_latency_ms >= res_inc.p50_latency_ms
    assert res_inc.final_ring_count == res_full.final_ring_count
