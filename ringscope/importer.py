"""
ringscope.importer — CSV edge-list import with robust validation.

Supports configurable source and destination columns, optional timestamp
and amount fields, and descriptive validation errors for missing files,
missing columns, empty endpoints, and malformed records.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional, TextIO, Union

from ringscope.graph import TransactionGraph


def import_csv_edgelist(
    filepath_or_buffer: Union[str, Path, TextIO],
    source_col: str = "source",
    target_col: str = "target",
    timestamp_col: Optional[str] = None,
    amount_col: Optional[str] = None,
    delimiter: str = ",",
    graph_name: str = "imported_csv_graph",
    directed: bool = False,
) -> TransactionGraph:
    """
    Import an edge list from a CSV file or file-like buffer into a TransactionGraph.

    Parameters
    ----------
    filepath_or_buffer : str | Path | TextIO
        Path to the CSV file on disk, or a text buffer (such as io.StringIO).
    source_col : str
        Name of the column containing the source account ID (default: 'source').
    target_col : str
        Name of the column containing the destination account ID (default: 'target').
    timestamp_col : str | None
        Optional column containing transaction timestamps.
    amount_col : str | None
        Optional column containing transaction amounts.
    delimiter : str
        Field delimiter character (default: ',').
    graph_name : str
        Name assigned to the created TransactionGraph.
    directed : bool
        Whether to construct a directed or undirected graph (default: False).

    Returns
    -------
    TransactionGraph
        Graph populated with unique edges and metadata.

    Raises
    ------
    FileNotFoundError
        If a file path is provided and does not exist.
    ValueError
        If the CSV header is missing required columns, or rows have empty endpoints.
    """
    # Open file or use provided stream
    close_file = False
    if isinstance(filepath_or_buffer, (str, Path)):
        p = Path(filepath_or_buffer)
        if not p.is_file():
            raise FileNotFoundError(f"CSV edge-list file not found: {p}")
        f: TextIO = open(p, "r", encoding="utf-8-sig", newline="")
        close_file = True
    elif hasattr(filepath_or_buffer, "read"):
        f = filepath_or_buffer
    else:
        raise TypeError(
            f"Expected str, Path, or file-like buffer, got {type(filepath_or_buffer).__name__}"
        )

    try:
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or missing a header line.")

        fieldnames = [col.strip() for col in reader.fieldnames if col is not None]

        # Validate required columns
        if source_col not in fieldnames:
            raise ValueError(
                f"Missing required source column '{source_col}'. "
                f"Available columns in CSV header: {fieldnames}"
            )
        if target_col not in fieldnames:
            raise ValueError(
                f"Missing required destination column '{target_col}'. "
                f"Available columns in CSV header: {fieldnames}"
            )

        tg = TransactionGraph(name=graph_name, directed=directed)

        # Auto-detect or use explicit amount and timestamp columns
        eff_amount_col = (
            amount_col if amount_col else ("amount" if "amount" in fieldnames else None)
        )
        eff_timestamp_col = (
            timestamp_col if timestamp_col else ("timestamp" if "timestamp" in fieldnames else None)
        )

        reserved_cols = {source_col, target_col}
        if eff_amount_col:
            reserved_cols.add(eff_amount_col)
        if eff_timestamp_col:
            reserved_cols.add(eff_timestamp_col)

        for row_idx, row in enumerate(reader, start=1):
            if not row or all(v is None or str(v).strip() == "" for v in row.values()):
                # Skip empty lines
                continue

            src_val = row.get(source_col)
            dst_val = row.get(target_col)

            if src_val is None or str(src_val).strip() == "":
                raise ValueError(
                    f"Row {row_idx}: Missing or empty source endpoint in column '{source_col}'."
                )
            if dst_val is None or str(dst_val).strip() == "":
                raise ValueError(
                    f"Row {row_idx}: Missing or empty destination endpoint in '{target_col}'."
                )

            src = str(src_val).strip()
            dst = str(dst_val).strip()

            # Parse optional amount
            amount = 1.0
            if eff_amount_col and row.get(eff_amount_col) is not None:
                val = str(row[eff_amount_col]).strip()
                if val:
                    try:
                        amount = float(val)
                    except ValueError:
                        raise ValueError(
                            f"Row {row_idx}: Invalid amount '{val}' in column '{eff_amount_col}'."
                        )

            # Parse optional timestamp
            timestamp = 0.0
            if eff_timestamp_col and row.get(eff_timestamp_col) is not None:
                val = str(row[eff_timestamp_col]).strip()
                if val:
                    try:
                        timestamp = float(val)
                    except ValueError:
                        raise ValueError(
                            f"Row {row_idx}: Invalid timestamp '{val}' in "
                            f"column '{eff_timestamp_col}'."
                        )

            # Extra metadata columns
            extras = {}
            for col_name, col_val in row.items():
                if col_name and col_name.strip() not in reserved_cols:
                    if col_val is not None:
                        extras[col_name.strip()] = col_val.strip()

            tg.add_transaction(
                src=src,
                dst=dst,
                amount=amount,
                timestamp=timestamp,
                **extras,
            )

        return tg

    finally:
        if close_file:
            f.close()


SAMPLE_SNAP_DATASET: str = """# Stanford Large Network Dataset Collection (SNAP) Style Format
# Provenance: Synthetic OTC transaction network modeled after soc-sign-bitcoinotc
# Nodes: 15 Edges: 24
# Directed/Undirected: Undirected financial relationships
# Format: FromNodeId ToNodeId [Weight] [Time]
# Dense fraudulent ring cluster: 1, 2, 3, 4, 5
1 2 10.0 1600000001
2 3 15.0 1600000002
3 4 12.0 1600000003
4 5 18.0 1600000004
5 1 20.0 1600000005
1 3 25.0 1600000006
2 4 14.0 1600000007
3 5 16.0 1600000008
1 4 22.0 1600000009
2 5 19.0 1600000010
# Background peripheral network
5 6 5.0 1600000011
6 7 4.0 1600000012
7 8 6.0 1600000013
8 9 3.0 1600000014
9 10 2.0 1600000015
10 11 1.0 1600000016
11 12 7.0 1600000017
12 13 8.0 1600000018
13 14 9.0 1600000019
14 15 5.0 1600000020
6 10 3.5 1600000021
8 12 4.5 1600000022
7 14 2.5 1600000023
9 15 1.5 1600000024
"""


def get_sample_snap_edgelist() -> str:
    """Return the bundled synthetic SNAP-style edge-list dataset string."""
    return SAMPLE_SNAP_DATASET.strip()


def import_snap_edgelist(
    filepath_or_buffer: Union[str, Path, TextIO],
    delimiter: Optional[str] = None,
    comment_char: str = "#",
    max_edges: Optional[int] = None,
    graph_name: str = "snap_imported_graph",
    directed: bool = False,
) -> TransactionGraph:
    """
    Import a SNAP-style edge list (Stanford Network Analysis Project format).

    Supports space-, tab-, or comma-separated edge lists with '#' comment lines.
    Automatically parses optional weight (amount) and timestamp columns when present.

    Parameters
    ----------
    filepath_or_buffer : str | Path | TextIO
        Filepath, path object, StringIO buffer, or raw multiline SNAP data string.
    delimiter : str | None
        Token delimiter. If None, splits on arbitrary whitespace (standard SNAP format).
    comment_char : str
        Character indicating a header or comment line (default: '#').
    max_edges : int | None
        Optional maximum number of edges to load (useful for large graph sampling).
    graph_name : str
        Name for the constructed TransactionGraph.
    directed : bool
        Whether to model as directed or undirected (default: False).

    Returns
    -------
    TransactionGraph
    """
    import io

    close_file = False
    comments: list[str] = []

    if isinstance(filepath_or_buffer, str):
        if "\n" in filepath_or_buffer or filepath_or_buffer.startswith(comment_char):
            f: TextIO = io.StringIO(filepath_or_buffer)
        else:
            p = Path(filepath_or_buffer)
            if not p.is_file():
                raise FileNotFoundError(f"SNAP edge-list file not found: {p}")
            f = open(p, "r", encoding="utf-8")
            close_file = True
    elif isinstance(filepath_or_buffer, Path):
        if not filepath_or_buffer.is_file():
            raise FileNotFoundError(f"SNAP edge-list file not found: {filepath_or_buffer}")
        f = open(filepath_or_buffer, "r", encoding="utf-8")
        close_file = True
    else:
        f = filepath_or_buffer

    try:
        tg = TransactionGraph(name=graph_name, directed=directed)
        edge_count = 0

        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue

            if line_str.startswith(comment_char):
                comments.append(line_str)
                continue

            tokens = line_str.split(delimiter) if delimiter else line_str.split()
            if len(tokens) < 2:
                raise ValueError(
                    f"Line {line_num}: Expected at least 2 endpoint tokens, found: '{line_str}'"
                )

            src = tokens[0].strip()
            dst = tokens[1].strip()

            amount = 1.0
            if len(tokens) >= 3:
                try:
                    amount = float(tokens[2])
                except ValueError:
                    amount = 1.0

            timestamp = 0.0
            if len(tokens) >= 4:
                try:
                    timestamp = float(tokens[3])
                except ValueError:
                    timestamp = 0.0

            tg.add_transaction(
                src=src,
                dst=dst,
                amount=amount,
                timestamp=timestamp,
            )
            edge_count += 1
            if max_edges is not None and edge_count >= max_edges:
                break

        tg.graph.graph["snap_metadata"] = {
            "comments": comments,
            "edges_loaded": edge_count,
        }
        return tg

    finally:
        if close_file:
            f.close()
