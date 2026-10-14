"""
Tests for ringscope.stream_simulator (Deterministic replay and stream generation).
"""

from ringscope.stream_simulator import generate_transaction_stream


def test_deterministic_stream_replay():
    # Same seed must produce identical batches and transaction IDs
    batches1, planted1 = generate_transaction_stream(
        n_background_accounts=20,
        n_background_transactions=40,
        batch_size=5,
        seed=42,
    )
    batches2, planted2 = generate_transaction_stream(
        n_background_accounts=20,
        n_background_transactions=40,
        batch_size=5,
        seed=42,
    )

    assert planted1 == planted2
    assert len(batches1) == len(batches2)
    for b1, b2 in zip(batches1, batches2):
        assert b1.batch_index == b2.batch_index
        assert len(b1.transactions) == len(b2.transactions)
        for t1, t2 in zip(b1.transactions, b2.transactions):
            assert t1.tx_id == t2.tx_id
            assert t1.src == t2.src
            assert t1.dst == t2.dst
            assert t1.amount == t2.amount
            assert t1.timestamp == t2.timestamp
            assert t1.is_planted == t2.is_planted


def test_different_seeds_produce_different_streams():
    batches1, _ = generate_transaction_stream(seed=101)
    batches2, _ = generate_transaction_stream(seed=202)

    t1 = [tx.src for b in batches1 for tx in b.transactions]
    t2 = [tx.src for b in batches2 for tx in b.transactions]
    assert t1 != t2


def test_batch_sizing_and_injection():
    batch_size = 4
    inject_batch = 3
    batches, planted = generate_transaction_stream(
        n_background_accounts=15,
        n_background_transactions=30,
        batch_size=batch_size,
        planted_cluster_size=5,
        inject_at_batch=inject_batch,
        seed=77,
    )

    for b in batches[:-1]:
        assert len(b.transactions) == batch_size

    # Check that planted transactions appear at or after inject_batch
    seen_planted_before_injection = any(
        tx.is_planted for b in batches[:inject_batch] for tx in b.transactions
    )
    assert not seen_planted_before_injection

    seen_planted = any(tx.is_planted for b in batches for tx in b.transactions)
    assert seen_planted


def test_arrival_order_modes():
    for order in ("chronological", "randomized", "reverse", "bursty"):
        batches, _ = generate_transaction_stream(
            arrival_order=order,  # type: ignore
            seed=99,
        )
        assert len(batches) > 0
