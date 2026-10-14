"""
Tests for ringscope.importer (CSV edge-list importer).
"""

import io

import pytest

from ringscope.graph import TransactionGraph
from ringscope.importer import import_csv_edgelist


def test_import_valid_csv_buffer():
    csv_data = """source,target,amount,timestamp
ACC_A,ACC_B,100.5,1700000000
ACC_B,ACC_C,250.0,1700000010
ACC_C,ACC_A,300.0,1700000020
"""
    f = io.StringIO(csv_data)
    tg = import_csv_edgelist(f)
    assert tg.num_vertices == 3
    assert tg.num_unique_edges == 3
    assert tg.density() == pytest.approx(1.0)  # Triangle
    assert tg.total_transaction_records == 3


def test_import_custom_column_names():
    csv_data = """sender_id,receiver_id,tx_value,time_unix,notes
U100,U200,50.0,12345,payroll
U200,U300,75.0,12346,vendor
"""
    f = io.StringIO(csv_data)
    tg = import_csv_edgelist(
        f,
        source_col="sender_id",
        target_col="receiver_id",
        amount_col="tx_value",
        timestamp_col="time_unix",
    )
    assert tg.num_vertices == 3
    assert tg.num_unique_edges == 2
    assert tg.graph["U100"]["U200"]["amount"] == pytest.approx(50.0)


def test_import_missing_header_columns_raise_error():
    csv_data = """col_x,col_y,value
A,B,10
"""
    f = io.StringIO(csv_data)
    with pytest.raises(ValueError, match="Missing required source column 'source'"):
        import_csv_edgelist(f, source_col="source", target_col="col_y")

    f2 = io.StringIO(csv_data)
    with pytest.raises(ValueError, match="Missing required destination column 'target'"):
        import_csv_edgelist(f2, source_col="col_x", target_col="target")


def test_import_empty_endpoint_raises_row_error():
    csv_data = """source,target,amount
ACC_1,ACC_2,10
,ACC_3,20
"""
    f = io.StringIO(csv_data)
    with pytest.raises(ValueError, match="Row 2: Missing or empty source endpoint"):
        import_csv_edgelist(f)

    csv_data2 = """source,target,amount
ACC_1,ACC_2,10
ACC_2,   ,20
"""
    f2 = io.StringIO(csv_data2)
    with pytest.raises(ValueError, match="Row 2: Missing or empty destination endpoint"):
        import_csv_edgelist(f2)


def test_import_parallel_edges_and_self_loops():
    csv_data = """source,target,amount
A,B,100
B,A,200
A,A,50
"""
    f = io.StringIO(csv_data)
    tg = import_csv_edgelist(f)
    assert tg.num_vertices == 2
    assert tg.num_unique_edges == 1
    assert tg.total_transaction_records == 3
    assert tg.self_loops_skipped == 1
    assert tg.graph["A"]["B"]["tx_count"] == 2
    assert tg.graph["A"]["B"]["amount"] == pytest.approx(300.0)


def test_import_file_not_found():
    with pytest.raises(FileNotFoundError):
        import_csv_edgelist("non_existent_file_path_12345.csv")


def test_transaction_graph_from_csv_method():
    csv_data = """source,target
NODE_1,NODE_2
NODE_2,NODE_3
"""
    f = io.StringIO(csv_data)
    tg = TransactionGraph.from_csv(f)
    assert tg.num_vertices == 3
    assert tg.num_unique_edges == 2
