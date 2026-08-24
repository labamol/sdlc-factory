"""Knowledge store: SQL catalog + exact search + vector search.

The portable default is SQLite (stdlib) with embeddings stored inline and
cosine similarity computed in-process. A PostgreSQL + pgvector store
implements the same protocol for scaled deployments
(:mod:`factory.knowledge.context.pgvector`).
"""

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Protocol

from factory.knowledge.context.embedding import Embedder, cosine
from factory.models.context import ContextItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    section TEXT NOT NULL DEFAULT '',
    authority TEXT NOT NULL DEFAULT 'informative',
    version TEXT NOT NULL DEFAULT 'v1',
    effective_from TEXT,
    supersedes TEXT,
    superseded_by TEXT,
    repo_commit TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',
    embedding TEXT NOT NULL DEFAULT '[]'
);
"""


class KnowledgeStore(Protocol):
    def upsert(self, items: list[ContextItem]) -> None: ...

    def exact_search(self, term: str, *, limit: int = 20) -> list[ContextItem]: ...

    def vector_search(
        self, query: str, *, limit: int = 20
    ) -> list[tuple[ContextItem, float]]: ...

    def by_subject(self, subject: str) -> list[ContextItem]: ...

    def all_items(self) -> list[ContextItem]: ...


def _row_to_item(row: sqlite3.Row) -> ContextItem:
    return ContextItem(
        item_id=row["item_id"],
        kind=row["kind"],
        content=row["content"],
        source=row["source"],
        section=row["section"],
        authority=row["authority"],
        version=row["version"],
        effective_from=date.fromisoformat(row["effective_from"])
        if row["effective_from"]
        else None,
        supersedes=row["supersedes"],
        superseded_by=row["superseded_by"],
        repo_commit=row["repo_commit"],
        subject=row["subject"],
        metadata=json.loads(row["metadata"]),
    )


class SqliteKnowledgeStore:
    """SQL + exact + vector search over one SQLite database file."""

    def __init__(self, db_path: Path | str, embedder: Embedder) -> None:
        self.embedder = embedder
        if isinstance(db_path, Path):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def upsert(self, items: list[ContextItem]) -> None:
        rows = []
        for item in items:
            rows.append(
                (
                    item.item_id, item.kind, item.content, item.source, item.section,
                    item.authority, item.version,
                    item.effective_from.isoformat() if item.effective_from else None,
                    item.supersedes, item.superseded_by, item.repo_commit, item.subject,
                    json.dumps(item.metadata),
                    json.dumps(self.embedder.embed(item.content)),
                )
            )
        self._conn.executemany(
            "INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
        )
        # Mark superseded items so version filtering can exclude them.
        self._conn.execute(
            """
            UPDATE items SET superseded_by = (
                SELECT n.item_id FROM items n WHERE n.supersedes = items.item_id
            )
            WHERE EXISTS (SELECT 1 FROM items n WHERE n.supersedes = items.item_id)
            """
        )
        self._conn.commit()

    def exact_search(self, term: str, *, limit: int = 20) -> list[ContextItem]:
        rows = self._conn.execute(
            """
            SELECT * FROM items
            WHERE content LIKE ? OR subject = ? OR source LIKE ?
            ORDER BY item_id LIMIT ?
            """,
            (f"%{term}%", term, f"%{term}%", limit),
        ).fetchall()
        return [_row_to_item(r) for r in rows]

    def vector_search(
        self, query: str, *, limit: int = 20
    ) -> list[tuple[ContextItem, float]]:
        query_vector = self.embedder.embed(query)
        scored: list[tuple[ContextItem, float]] = []
        for row in self._conn.execute("SELECT * FROM items").fetchall():
            embedding = json.loads(row["embedding"])
            if not embedding:
                continue
            scored.append((_row_to_item(row), cosine(query_vector, embedding)))
        scored.sort(key=lambda pair: (-pair[1], pair[0].item_id))
        return scored[:limit]

    def by_subject(self, subject: str) -> list[ContextItem]:
        rows = self._conn.execute(
            "SELECT * FROM items WHERE subject = ? ORDER BY item_id", (subject,)
        ).fetchall()
        return [_row_to_item(r) for r in rows]

    def all_items(self) -> list[ContextItem]:
        rows = self._conn.execute("SELECT * FROM items ORDER BY item_id").fetchall()
        return [_row_to_item(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
