"""PostgreSQL + pgvector knowledge store.

Implements the same KnowledgeStore protocol as SqliteKnowledgeStore for
scaled deployments. Requires the optional `postgres` dependency group
(`pip install sdlc-factory[postgres]`) and a database with the pgvector
extension available.
"""

import json
from datetime import date
from typing import Any

from factory.knowledge.context.embedding import Embedder
from factory.models.context import ContextItem

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency
    psycopg = None

_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    section TEXT NOT NULL DEFAULT '',
    authority TEXT NOT NULL DEFAULT 'informative',
    version TEXT NOT NULL DEFAULT 'v1',
    effective_from DATE,
    supersedes TEXT,
    superseded_by TEXT,
    repo_commit TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    embedding vector(%(dimension)s)
);
CREATE INDEX IF NOT EXISTS items_subject_idx ON items (subject);
"""


def _row_to_item(row: dict[str, Any]) -> ContextItem:
    return ContextItem(
        item_id=row["item_id"],
        kind=row["kind"],
        content=row["content"],
        source=row["source"],
        section=row["section"],
        authority=row["authority"],
        version=row["version"],
        effective_from=row["effective_from"]
        if isinstance(row["effective_from"], (date, type(None)))
        else date.fromisoformat(row["effective_from"]),
        supersedes=row["supersedes"],
        superseded_by=row["superseded_by"],
        repo_commit=row["repo_commit"],
        subject=row["subject"],
        metadata=row["metadata"] or {},
    )


class PgVectorKnowledgeStore:
    """KnowledgeStore backed by PostgreSQL with pgvector similarity search."""

    def __init__(self, dsn: str, embedder: Embedder) -> None:
        if psycopg is None:
            raise RuntimeError(
                "PgVectorKnowledgeStore requires the optional 'postgres' extra: "
                "pip install sdlc-factory[postgres]"
            )
        self.embedder = embedder
        self._conn = psycopg.connect(dsn, row_factory=psycopg.rows.dict_row)
        with self._conn.cursor() as cur:
            cur.execute(_SCHEMA % {"dimension": embedder.dimension})
        self._conn.commit()

    def upsert(self, items: list[ContextItem]) -> None:
        with self._conn.cursor() as cur:
            for item in items:
                cur.execute(
                    """
                    INSERT INTO items VALUES
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (item_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        version = EXCLUDED.version,
                        superseded_by = EXCLUDED.superseded_by,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        item.item_id, item.kind, item.content, item.source,
                        item.section, item.authority, item.version,
                        item.effective_from, item.supersedes, item.superseded_by,
                        item.repo_commit, item.subject, json.dumps(item.metadata),
                        str(self.embedder.embed(item.content)),
                    ),
                )
            cur.execute(
                """
                UPDATE items SET superseded_by = n.item_id
                FROM items n WHERE n.supersedes = items.item_id
                """
            )
        self._conn.commit()

    def exact_search(self, term: str, *, limit: int = 20) -> list[ContextItem]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM items
                WHERE content ILIKE %s OR subject = %s OR source ILIKE %s
                ORDER BY item_id LIMIT %s
                """,
                (f"%{term}%", term, f"%{term}%", limit),
            )
            return [_row_to_item(r) for r in cur.fetchall()]

    def vector_search(
        self, query: str, *, limit: int = 20
    ) -> list[tuple[ContextItem, float]]:
        query_vector = str(self.embedder.embed(query))
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT *, 1 - (embedding <=> %s::vector) AS score
                FROM items WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector, item_id LIMIT %s
                """,
                (query_vector, query_vector, limit),
            )
            return [(_row_to_item(r), float(r["score"])) for r in cur.fetchall()]

    def by_subject(self, subject: str) -> list[ContextItem]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM items WHERE subject = %s ORDER BY item_id", (subject,)
            )
            return [_row_to_item(r) for r in cur.fetchall()]

    def all_items(self) -> list[ContextItem]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM items ORDER BY item_id")
            return [_row_to_item(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
