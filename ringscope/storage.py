"""
ringscope.storage — SQLite persistence and session store for TransactionGraphs.

Provides durable multi-session persistence, transaction history recording,
and thread-safe database storage using the standard library sqlite3.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from ringscope.graph import TransactionGraph


class GraphStore:
    """
    SQLite-backed store for TransactionGraphs and transaction history.

    Parameters
    ----------
    db_path : str | Path
        Path to SQLite database file, or ':memory:' for in-memory store.
    """

    def __init__(self, db_path: str | Path = "ringscope.db") -> None:
        self.db_path = str(db_path)
        self._is_memory = self.db_path == ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self._is_memory:
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._is_memory and self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS graphs (
                    graph_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    num_nodes INTEGER DEFAULT 0,
                    num_edges INTEGER DEFAULT 0,
                    is_directed INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS accounts (
                    graph_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    attrs_json TEXT,
                    PRIMARY KEY (graph_id, account_id),
                    FOREIGN KEY (graph_id) REFERENCES graphs(graph_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    tx_id TEXT PRIMARY KEY,
                    graph_id TEXT NOT NULL,
                    src TEXT NOT NULL,
                    dst TEXT NOT NULL,
                    amount REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    attrs_json TEXT,
                    FOREIGN KEY (graph_id) REFERENCES graphs(graph_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_tx_graph ON transactions(graph_id);
                CREATE INDEX IF NOT EXISTS idx_tx_endpoints ON transactions(graph_id, src, dst);
            """)
            try:
                conn.execute("ALTER TABLE graphs ADD COLUMN is_directed INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass

    def save_graph(self, tg: TransactionGraph, graph_id: Optional[str] = None) -> str:
        """
        Save or overwrite a TransactionGraph into the database.
        Returns the graph_id.
        """
        gid = graph_id or tg.name or f"graph_{int(time.time())}"
        now = time.time()

        with self._get_connection() as conn:
            # Delete existing graph with this id if updating
            conn.execute("DELETE FROM graphs WHERE graph_id = ?", (gid,))

            conn.execute(
                """
                INSERT INTO graphs (graph_id, name, created_at, num_nodes, num_edges, is_directed)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (gid, tg.name, now, tg.num_nodes, tg.num_edges, 1 if tg.directed else 0),
            )

            # Insert accounts
            for node, attrs in tg.graph.nodes(data=True):
                conn.execute(
                    "INSERT INTO accounts (graph_id, account_id, attrs_json) VALUES (?, ?, ?)",
                    (gid, str(node), json.dumps(attrs)),
                )

            # Insert aggregated edges
            for u, v, data in tg.graph.edges(data=True):
                tx_id = data.get("tx_id", f"{gid}_{u}_{v}")
                amount = float(data.get("amount", 0.0))
                ts = float(data.get("timestamp", now))
                extra = {
                    k: v
                    for k, v in data.items()
                    if k not in ("tx_id", "amount", "timestamp", "tx_count", "timestamps")
                }
                conn.execute(
                    """
                    INSERT INTO transactions
                    (tx_id, graph_id, src, dst, amount, timestamp, attrs_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (tx_id, gid, str(u), str(v), amount, ts, json.dumps(extra)),
                )
        return gid

    def load_graph(self, graph_id: str) -> TransactionGraph:
        """
        Load a TransactionGraph by graph_id. Raises KeyError if not found.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT name, is_directed FROM graphs WHERE graph_id = ?", (graph_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"Graph '{graph_id}' not found")
            name = row["name"]
            is_directed = bool(row["is_directed"]) if "is_directed" in row.keys() else False

            tg = TransactionGraph(name=name, directed=is_directed)

            for acc in conn.execute(
                "SELECT account_id, attrs_json FROM accounts WHERE graph_id = ?", (graph_id,)
            ):
                attrs = json.loads(acc["attrs_json"]) if acc["attrs_json"] else {}
                tg.add_account(acc["account_id"], **attrs)

            query = (
                "SELECT tx_id, src, dst, amount, timestamp, attrs_json "
                "FROM transactions WHERE graph_id = ?"
            )
            for tx in conn.execute(query, (graph_id,)):
                extra = json.loads(tx["attrs_json"]) if tx["attrs_json"] else {}
                extra.pop("tx_count", None)
                extra.pop("timestamps", None)
                tg.add_transaction(
                    src=tx["src"],
                    dst=tx["dst"],
                    amount=tx["amount"],
                    timestamp=tx["timestamp"],
                    tx_id=tx["tx_id"],
                    **extra,
                )
        return tg

    def list_graphs(self) -> list[dict[str, Any]]:
        """List all saved graphs with summary stats."""
        with self._get_connection() as conn:
            query = (
                "SELECT graph_id, name, created_at, num_nodes, num_edges "
                "FROM graphs ORDER BY created_at DESC"
            )
            rows = conn.execute(query).fetchall()
            return [dict(r) for r in rows]

    def delete_graph(self, graph_id: str) -> bool:
        """Delete a graph and its associated records. Returns True if deleted."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM graphs WHERE graph_id = ?", (graph_id,))
            return cur.rowcount > 0

    def record_transaction(
        self,
        graph_id: str,
        src: str,
        dst: str,
        amount: float,
        timestamp: float,
        tx_id: Optional[str] = None,
        attrs: Optional[dict] = None,
    ) -> str:
        """
        Append a single transaction to history.
        """
        import uuid

        tid = tx_id or str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO transactions
                (tx_id, graph_id, src, dst, amount, timestamp, attrs_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (tid, graph_id, src, dst, amount, timestamp, json.dumps(attrs or {})),
            )
        return tid

    def get_transaction_history(self, graph_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieve recent transaction history for a graph session."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT tx_id, src, dst, amount, timestamp, attrs_json
                FROM transactions WHERE graph_id = ?
                ORDER BY timestamp DESC LIMIT ?
                """,
                (graph_id, limit),
            ).fetchall()
            res = []
            for r in rows:
                d = dict(r)
                if d.get("attrs_json"):
                    d["attrs"] = json.loads(d.pop("attrs_json"))
                res.append(d)
            return res
