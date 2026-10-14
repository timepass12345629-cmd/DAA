"""
Tests for ringscope.importer SNAP edge-list format support.
"""

import pytest

from ringscope.graph import TransactionGraph
from ringscope.importer import (
    SAMPLE_SNAP_DATASET,
    get_sample_snap_edgelist,
    import_snap_edgelist,
)


def test_get_sample_snap_dataset():
    sample = get_sample_snap_edgelist()
    assert isinstance(sample, str)
    assert "# Nodes: 15 Edges: 24" in sample


def test_import_snap_sample():
    tg = import_snap_edgelist(SAMPLE_SNAP_DATASET)
    assert tg.num_vertices == 15
    assert tg.num_unique_edges == 24
    assert tg.total_transaction_records == 24
    # Check snap metadata
    meta = tg.graph.graph.get("snap_metadata", {})
    assert len(meta.get("comments", [])) >= 5
    assert meta.get("edges_loaded") == 24


def test_import_snap_max_edges_limit():
    tg = import_snap_edgelist(SAMPLE_SNAP_DATASET, max_edges=10)
    assert tg.num_unique_edges == 10
    meta = tg.graph.graph.get("snap_metadata", {})
    assert meta.get("edges_loaded") == 10


def test_import_snap_from_snap_classmethod():
    sample = get_sample_snap_edgelist()
    tg = TransactionGraph.from_snap(sample)
    assert tg.num_vertices == 15
    assert tg.num_unique_edges == 24


def test_import_snap_file_not_found():
    with pytest.raises(FileNotFoundError):
        import_snap_edgelist("non_existent_snap_file.txt")


def test_import_snap_malformed_line():
    bad_snap = """# Comment
1 2 10.0
single_node_only
"""
    with pytest.raises(ValueError, match="at least 2 endpoint tokens"):
        import_snap_edgelist(bad_snap)
