"""Structured audit event emission.

Events are immutable JSON records carrying stable correlation identifiers so
metrics and history can be reconstructed without agent-generated summaries.
"""

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class FactoryEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("EVT"))
    event_type: str
    timestamp: datetime = Field(default_factory=_utcnow)
    project_id: str | None = None
    feature_id: str | None = None
    story_id: str | None = None
    execution_id: str | None = None
    trace_id: str | None = None
    stage: str | None = None
    agent: str | None = None
    skill: str | None = None
    runtime: str | None = None
    context_pack_id: str | None = None
    status: str | None = None
    retry_number: int | None = None
    human_intervention: bool | None = None
    payload: dict = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)


EventSink = Callable[[FactoryEvent], None]


class JsonlEventSink:
    """Appends events to a JSONL audit log."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, event: FactoryEvent) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[FactoryEvent] = []

    def __call__(self, event: FactoryEvent) -> None:
        self.events.append(event)


class EventBus:
    """Fans one event out to all registered sinks."""

    def __init__(self, sinks: list[EventSink] | None = None) -> None:
        self._sinks: list[EventSink] = sinks or []

    def add_sink(self, sink: EventSink) -> None:
        self._sinks.append(sink)

    def emit(self, event: FactoryEvent) -> FactoryEvent:
        for sink in self._sinks:
            sink(event)
        return event


def read_events(path: Path) -> list[FactoryEvent]:
    if not path.exists():
        return []
    events = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(FactoryEvent.model_validate(json.loads(line)))
    return events
