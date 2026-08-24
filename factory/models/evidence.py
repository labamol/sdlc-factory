from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Evidence(BaseModel):
    """Reference to a durable artifact proving a stage outcome."""

    evidence_id: str
    stage: str
    kind: str  # e.g. "requirements", "spec", "test-report", "coverage", "pr", "artifact"
    ref: str  # path, URL or artifact URI
    summary: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict = Field(default_factory=dict)
