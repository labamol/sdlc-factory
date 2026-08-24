"""Typed context-intelligence models.

Context packs are versioned, auditable artifacts: every item carries
provenance (source, version, authority, effective date, repo commit) so an
agent's inputs can be reconstructed exactly.
"""

from datetime import date, datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContextItem(BaseModel):
    """One retrievable unit of knowledge (document chunk, decision, code)."""

    item_id: str
    kind: str  # requirement | decision | assumption | spec | code | doc | meeting
    content: str
    source: str  # file path, document id or URL
    section: str = ""
    authority: str = "informative"  # binding | authoritative | informative
    version: str = "v1"
    effective_from: date | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    repo_commit: str = ""
    subject: str = ""  # traceability subject, e.g. BR-06 / FEAT-01
    metadata: dict = Field(default_factory=dict)


class ContextConflict(BaseModel):
    """Two items making incompatible claims about the same subject."""

    subject: str
    item_ids: list[str]
    reason: str
    resolution: str = ""  # e.g. "kept latest binding decision" or "" if unresolved


class ScoredItem(BaseModel):
    item: ContextItem
    score: float
    reasons: list[str] = Field(default_factory=list)


class ContextPack(BaseModel):
    """Versioned, budgeted context assembled for one task."""

    pack_id: str
    feature_id: str
    query: str
    spec_version: str | None = None
    repo_commit: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    budget_tokens: int = 4000
    used_tokens: int = 0
    items: list[ScoredItem] = Field(default_factory=list)
    conflicts: list[ContextConflict] = Field(default_factory=list)
    excluded_superseded: list[str] = Field(default_factory=list)
    filters: dict = Field(default_factory=dict)
