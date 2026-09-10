"""SQLite-backed knowledge graph store with ontology enforcement."""

import json
import sqlite3
from pathlib import Path

from factory.knowledge.graph.ontology import EdgeType, NodeType, validate_edge
from factory.models.graph import GraphEdge, GraphNode

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    authority TEXT NOT NULL DEFAULT 'informative',
    version TEXT NOT NULL DEFAULT 'v1',
    effective_from TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS edges (
    edge_id TEXT PRIMARY KEY,
    from_id TEXT NOT NULL REFERENCES nodes(node_id),
    to_id TEXT NOT NULL REFERENCES nodes(node_id),
    edge_type TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
"""


def _node_row(row: sqlite3.Row) -> GraphNode:
    return GraphNode(
        node_id=row["node_id"], node_type=row["node_type"], label=row["label"],
        source=row["source"], authority=row["authority"], version=row["version"],
        effective_from=row["effective_from"], status=row["status"],
        metadata=json.loads(row["metadata"]),
    )


def _edge_row(row: sqlite3.Row) -> GraphEdge:
    return GraphEdge(
        edge_id=row["edge_id"], from_id=row["from_id"], to_id=row["to_id"],
        edge_type=row["edge_type"], source=row["source"], created_by=row["created_by"],
        metadata=json.loads(row["metadata"]),
    )


class SqliteGraphStore:
    def __init__(self, path: Path | str) -> None:
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def add_node(self, node: GraphNode) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                node.node_id, node.node_type, node.label, node.source, node.authority,
                node.version,
                node.effective_from.isoformat() if node.effective_from else None,
                node.status, json.dumps(node.metadata),
            ),
        )
        self.conn.commit()

    def add_edge(self, edge: GraphEdge) -> None:
        from_node = self.get_node(edge.from_id)
        to_node = self.get_node(edge.to_id)
        if from_node is None or to_node is None:
            raise ValueError(f"Edge {edge.edge_id} references unknown node(s)")
        validate_edge(
            EdgeType(edge.edge_type),
            NodeType(from_node.node_type),
            NodeType(to_node.node_type),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO edges VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                edge.edge_id, edge.from_id, edge.to_id, edge.edge_type,
                edge.source, edge.created_by, json.dumps(edge.metadata),
            ),
        )
        self.conn.commit()

    def get_node(self, node_id: str) -> GraphNode | None:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        return _node_row(row) if row else None

    def nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE node_type = ? ORDER BY node_id", (node_type.value,)
        ).fetchall()
        return [_node_row(r) for r in rows]

    def out_edges(self, node_id: str) -> list[GraphEdge]:
        rows = self.conn.execute(
            "SELECT * FROM edges WHERE from_id = ? ORDER BY edge_id", (node_id,)
        ).fetchall()
        return [_edge_row(r) for r in rows]

    def in_edges(self, node_id: str) -> list[GraphEdge]:
        rows = self.conn.execute(
            "SELECT * FROM edges WHERE to_id = ? ORDER BY edge_id", (node_id,)
        ).fetchall()
        return [_edge_row(r) for r in rows]

    def counts(self) -> tuple[int, int]:
        nodes = self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edges = self.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        return nodes, edges
