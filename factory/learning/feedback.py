"""Human feedback records.

Structured feedback on factory output (a stage, a skill, a generated
artifact) with provenance. Feedback is durable input to learning: it never
mutates skills directly — promotion is governed separately.
"""

from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

FEEDBACK_FILE = "learning/feedback.yaml"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class HumanFeedback(BaseModel):
    feedback_id: str
    target_kind: str  # stage | skill | artifact
    target: str
    rating: str  # positive | negative | neutral
    comment: str = ""
    author: str
    created_at: str = Field(default_factory=_utcnow_iso)


class FeedbackStore:
    def __init__(self, project_dir: Path) -> None:
        self.path = project_dir / FEEDBACK_FILE

    def all(self) -> list[HumanFeedback]:
        if not self.path.exists():
            return []
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or []
        return [HumanFeedback.model_validate(f) for f in raw]

    def record(self, feedback: HumanFeedback) -> None:
        if not feedback.author:
            raise ValueError("Feedback requires an author")
        entries = self.all()
        entries.append(feedback)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                [f.model_dump(mode="json") for f in entries], sort_keys=False
            ),
            encoding="utf-8",
        )
