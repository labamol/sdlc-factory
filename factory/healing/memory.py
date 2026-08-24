"""Episodic memory.

Durable record of every failure episode: what failed, how it was classified,
what repair was applied and whether it worked. Signatures let the factory
recognize recurring failures and feed governed promotion of fixes into
skills and templates.
"""

from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

EPISODES_FILE = "learning/episodes.yaml"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Episode(BaseModel):
    episode_id: str
    feature_id: str
    stage: str
    failure_class: str
    signature: str
    diagnosis_summary: str = ""
    repair_action: str = ""
    repair_owner: str = ""
    outcome: str = "PENDING"  # PENDING | REPAIRED | ESCALATED
    attempt: int = 1
    created_at: str = Field(default_factory=_utcnow_iso)


class EpisodicMemory:
    def __init__(self, project_dir: Path) -> None:
        self.path = project_dir / EPISODES_FILE

    def all(self) -> list[Episode]:
        if not self.path.exists():
            return []
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or []
        return [Episode.model_validate(e) for e in raw]

    def _save(self, episodes: list[Episode]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                [e.model_dump(mode="json") for e in episodes], sort_keys=False
            ),
            encoding="utf-8",
        )

    def record(self, episode: Episode) -> None:
        episodes = self.all()
        episodes.append(episode)
        self._save(episodes)

    def update(self, episode: Episode) -> None:
        episodes = [
            episode if e.episode_id == episode.episode_id else e for e in self.all()
        ]
        self._save(episodes)

    def find_by_signature(self, signature: str) -> list[Episode]:
        return [e for e in self.all() if e.signature == signature]

    def attempts_for(self, feature_id: str) -> int:
        return len([e for e in self.all() if e.feature_id == feature_id])
