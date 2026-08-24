from datetime import datetime, timezone

from pydantic import BaseModel, Field

from factory.models.enums import FactoryState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StateTransition(BaseModel):
    """Immutable record of one state-machine transition."""

    transition_id: str
    feature_id: str
    project_id: str
    from_state: FactoryState
    to_state: FactoryState
    agent: str
    reason: str = ""
    retry_number: int = 0
    human_intervention: bool = False
    timestamp: datetime = Field(default_factory=_utcnow)
    evidence_refs: list[str] = Field(default_factory=list)


class AgentExecution(BaseModel):
    """Auditable record of one agent invocation."""

    execution_id: str
    feature_id: str
    project_id: str
    stage: FactoryState
    agent: str
    skill: str | None = None
    runtime: str = "in-process"
    context_pack_id: str | None = None
    spec_version: str | None = None
    repo_commit: str | None = None
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    status: str = "RUNNING"  # RUNNING | SUCCESS | FAILURE
    retry_number: int = 0
    human_intervention: bool = False
    result_summary: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
