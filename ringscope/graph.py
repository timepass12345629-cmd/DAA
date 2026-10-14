"""
ringscope.graph — Core graph model for transaction networks.

Represents accounts as vertices and unique transaction relationships as edges
in an undirected, unweighted, simple graph by default. Parallel transaction
records are aggregated into edge metadata (count, amounts, timestamps), and
self-loops are preserved in metadata without creating internal self-loop edges.

Invariants & Correctness Rules
------------------------------
1. Simple Graph: At most one edge exists between any pair of vertices {u, v}.
   Parallel transaction records increment the edge's `tx_count` metadata and
   do not increase the unique edge count.
2. No Self-Loops as Edges: Self-loop transactions (u == v) do not create
   internal edges. They are tracked separately in graph and vertex metadata.
3. Isolated Vertices: Accounts with zero incident edges are fully supported
   as degree-0 vertices with independent connected components of size 1.
4. Input Validation: Endpoints must be non-empty, non-None string/hashable identifiers.
5. Subset Density: For any non-empty vertex subset S,
   density(S) = (number of unique internal edges in S) / |S|.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Iterable, Optional, TextIO

import networkx as nx


class TransactionGraph:
    """
    Graph representation for transaction networks.

    By default represents an undirected, unweighted, simple graph where
    vertices are account IDs and edges are unique transaction relationships.

    Parameters
    ----------
    name : str, optional
        Human-readable label for the graph.
    directed : bool, optional
        Whether the graph is directed (default: False, representing an undirected simple graph).
    """

    def __init__(self, name: str = "transaction_graph", directed: bool = False) -> None:
        self.name = name
        self.directed = directed
        self._g: nx.Graph = nx.DiGraph(name=name) if directed else nx.Graph(name=name)
        self._total_transaction_records: int = 0
        self._self_loops_skipped: int = 0
        self.metadata: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Graph access & Core Statistics (Requirement 7)
    # ------------------------------------------------------------------

    @property
    def graph(self) -> nx.Graph:
        """Underlying NetworkX Graph or DiGraph."""
        return self._g

    @property
    def num_vertices(self) -> int:
        """Number of vertices (accounts) in the graph."""
        return self._g.number_of_nodes()

    @property
    def num_nodes(self) -> int:
        """Alias for num_vertices."""
        return self._g.number_of_nodes()

    @property
    def num_unique_edges(self) -> int:
        """Number of unique edges in the simple graph."""
        return self._g.number_of_edges()

    @property
    def num_edges(self) -> int:
        """Alias for num_unique_edges."""
        return self._g.number_of_edges()

    @property
    def total_transaction_records(self) -> int:
        """Total number of transaction records ingested (including duplicates and self-loops)."""
        return self._total_transaction_records

    @property
    def self_loops_skipped(self) -> int:
        """Total number of self-loop transactions handled as metadata."""
        return self._self_loops_skipped

    def degrees(self) -> dict[str, int]:
        """Return a mapping from vertex ID to its degree in the simple graph."""
        return {str(node): int(self._g.degree(node)) for node in self._g.nodes}

    def degree(self, vertex: str) -> int:
        """Return the degree of a specific vertex."""
        if vertex not in self._g:
            raise KeyError(f"Vertex '{vertex}' does not exist in graph")
        return int(self._g.degree(vertex))

    def connected_components(self) -> list[set[str]]:
        """
        Return the connected components of the graph.
        For undirected graphs, returns standard connected components.
        For directed graphs, returns weakly connected components.
        Sorted by component size in descending order, with ties broken by node names.
        """
        if self.num_vertices == 0:
            return []

        if self.directed:
            comps = [set(c) for c in nx.weakly_connected_components(self._g)]
        else:
            comps = [set(c) for c in nx.connected_components(self._g)]

        comps.sort(key=lambda s: (-len(s), sorted(s)[0] if s else ""))
        return comps

    def density(self, subset: Optional[Iterable[str]] = None) -> float:
        """
        Compute the density of a vertex subset S:
            density(S) = (number of unique internal edges in S) / |S|

        Parameters
        ----------
        subset : Iterable[str] | None
            Non-empty subset of vertices. If None, computes density of the entire vertex set V.

        Returns
        -------
        float
            Edge density of the induced subgraph.

        Raises
        ------
        ValueError
            If the subset is empty or contains vertices not present in the graph.
        """
        if subset is None:
            nodes_set = set(self._g.nodes)
        else:
            nodes_set = set(subset)

        if len(nodes_set) == 0:
            raise ValueError("Density is undefined for an empty vertex subset.")

        missing = nodes_set - set(self._g.nodes)
        if missing:
            raise ValueError(
                f"Cannot compute density: vertices not in graph: {sorted(missing)}"
            )

        # In undirected simple graph, subgraph edges are the unique internal edges
        subg = self._g.subgraph(nodes_set)
        internal_edges = subg.number_of_edges()
        return float(internal_edges) / len(nodes_set)

    # ------------------------------------------------------------------
    # Mutation & Normalization (Requirements 4, 5, 6)
    # ------------------------------------------------------------------

    def add_account(self, account_id: str, **attrs: Any) -> None:
        """
        Add a vertex (account/wallet) with optional metadata.
        Explicitly supports isolated vertices.
        """
        if account_id is None:
            raise ValueError("Account ID cannot be None.")
        acc_str = str(account_id).strip()
        if not acc_str:
            raise ValueError("Account ID cannot be an empty or whitespace string.")
        self._g.add_node(acc_str, **attrs)

    def add_transaction(
        self,
        src: str,
        dst: str,
        amount: float = 1.0,
        timestamp: float = 0.0,
        tx_id: Optional[str] = None,
        **attrs: Any,
    ) -> str:
        """
        Add a transaction relationship between src and dst.

        Explicit Handling:
        -----------------
        - Missing/Malformed inputs: Raises ValueError if endpoints are None, empty, or whitespace.
        - Self-loops (src == dst): Handled as metadata. The vertex is ensured to exist,
          the self-loop counter is incremented, but no self-loop internal edge is added.
        - Duplicate transactions (parallel records): In an undirected simple graph,
          if {src, dst} already exists, amounts are accumulated, timestamps are updated,
          and `tx_count` is incremented. The unique edge count does not increase.
        """
        if src is None or dst is None:
            raise ValueError("Source and destination accounts must not be None.")

        src_str = str(src).strip()
        dst_str = str(dst).strip()

        if not src_str or not dst_str:
            raise ValueError(
                "Source and destination account IDs cannot be empty or whitespace strings."
            )

        tid = tx_id if tx_id is not None else str(uuid.uuid4())
        self._total_transaction_records += 1

        # Explicit handling: Self-loops
        if src_str == dst_str:
            self._g.add_node(src_str)
            self._self_loops_skipped += 1
            node_data = self._g.nodes[src_str]
            node_data["self_loop_count"] = node_data.get("self_loop_count", 0) + 1
            node_data["self_loop_amount"] = node_data.get("self_loop_amount", 0.0) + float(amount)
            return tid

        # Ensure both endpoints exist in the graph
        self._g.add_node(src_str)
        self._g.add_node(dst_str)

        # Explicit handling: Duplicate transactions (parallel edges)
        if self._g.has_edge(src_str, dst_str):
            edge_data = self._g[src_str][dst_str]
            edge_data["tx_count"] = edge_data.get("tx_count", 1) + 1
            edge_data["amount"] = edge_data.get("amount", 0.0) + float(amount)
            edge_data["timestamp"] = max(edge_data.get("timestamp", 0.0), float(timestamp))
            if "timestamps" in edge_data:
                edge_data["timestamps"].append(float(timestamp))
            else:
                edge_data["timestamps"] = [float(timestamp)]
        else:
            attrs_copy = dict(attrs)
            initial_ts = attrs_copy.pop("timestamps", [float(timestamp)])
            initial_count = attrs_copy.pop("tx_count", 1)
            self._g.add_edge(
                src_str,
                dst_str,
                amount=float(amount),
                timestamp=float(timestamp),
                timestamps=initial_ts,
                tx_id=tid,
                tx_count=initial_count,
                **attrs_copy,
            )

        return tid

    def remove_transaction(self, src: str, dst: str) -> None:
        """Remove the unique edge between src and dst if it exists. Preserves vertices."""
        if src is None or dst is None:
            return
        src_str = str(src).strip()
        dst_str = str(dst).strip()
        if self._g.has_edge(src_str, dst_str):
            self._g.remove_edge(src_str, dst_str)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict (node/edge lists and statistics)."""
        return {
            "name": self.name,
            "directed": self.directed,
            "num_vertices": self.num_vertices,
            "num_unique_edges": self.num_unique_edges,
            "total_transaction_records": self._total_transaction_records,
            "self_loops_skipped": self._self_loops_skipped,
            "nodes": [{"id": n, **self._g.nodes[n]} for n in self._g.nodes],
            "edges": [
                {
                    "source": u,
                    "target": v,
                    **{k: val for k, val in self._g[u][v].items() if k != "timestamps"},
                }
                for u, v in self._g.edges
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransactionGraph":
        """Reconstruct from dict produced by :meth:`to_dict`."""
        tg = cls(
            name=data.get("name", "transaction_graph"),
            directed=data.get("directed", False),
        )
        for node in data.get("nodes", []):
            node_copy = dict(node)
            nid = node_copy.pop("id")
            tg.add_account(nid, **node_copy)
        for edge in data.get("edges", []):
            edge_copy = dict(edge)
            src = edge_copy.pop("source")
            dst = edge_copy.pop("target")
            amount = edge_copy.pop("amount", 0.0)
            timestamp = edge_copy.pop("timestamp", 0.0)
            tx_id = edge_copy.pop("tx_id", None)
            edge_copy.pop("tx_count", None)
            tg.add_transaction(src, dst, amount, timestamp, tx_id, **edge_copy)
        tg.metadata = data.get("metadata", {})
        return tg

    @classmethod
    def from_csv(
        cls,
        filepath_or_buffer: str | Path | TextIO,
        source_col: str = "source",
        target_col: str = "target",
        timestamp_col: Optional[str] = None,
        amount_col: Optional[str] = None,
        delimiter: str = ",",
        directed: bool = False,
    ) -> "TransactionGraph":
        """Convenience method to import from a CSV edge-list."""
        from ringscope.importer import import_csv_edgelist

        return import_csv_edgelist(
            filepath_or_buffer=filepath_or_buffer,
            source_col=source_col,
            target_col=target_col,
            timestamp_col=timestamp_col,
            amount_col=amount_col,
            delimiter=delimiter,
            directed=directed,
        )

    @classmethod
    def from_snap(
        cls,
        filepath_or_buffer: Any,
        delimiter: Any = None,
        comment_char: str = "#",
        max_edges: Any = None,
        directed: bool = False,
    ) -> TransactionGraph:
        """Convenience method to import from a SNAP-format edge-list."""
        from ringscope.importer import import_snap_edgelist

        return import_snap_edgelist(
            filepath_or_buffer=filepath_or_buffer,
            delimiter=delimiter,
            comment_char=comment_char,
            max_edges=max_edges,
            directed=directed,
        )


# Backward-compatible alias
UndirectedTransactionGraph = TransactionGraph
