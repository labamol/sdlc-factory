"""Deterministic pull-request tool.

Maintains a project-local PR registry (`prs/PR-<n>.yaml`) with the same
contract a GitHub adapter would satisfy: create, read, update status. When a
remote forge is configured, this tool is swapped for a remote adapter; the
agents and policies are unchanged.
"""

from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PullRequestRecord(BaseModel):
    number: int
    title: str
    branch: str
    base: str = "main"
    status: str = "OPEN"  # OPEN | APPROVED | CHANGES_REQUESTED | MERGED
    commit: str = ""
    files: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utcnow_iso)
    merged_commit: str = ""


class PrTool:
    name = "github"

    def __init__(self, project_dir: Path) -> None:
        self.prs_dir = project_dir / "prs"

    def _path(self, number: int) -> Path:
        return self.prs_dir / f"PR-{number}.yaml"

    def next_number(self) -> int:
        if not self.prs_dir.exists():
            return 1
        return len(list(self.prs_dir.glob("PR-*.yaml"))) + 1

    def create(
        self, title: str, branch: str, *, base: str = "main",
        commit: str = "", files: list[str] | None = None,
    ) -> PullRequestRecord:
        record = PullRequestRecord(
            number=self.next_number(), title=title, branch=branch,
            base=base, commit=commit, files=files or [],
        )
        self._save(record)
        return record

    def get(self, number: int) -> PullRequestRecord:
        return PullRequestRecord.model_validate(
            yaml.safe_load(self._path(number).read_text(encoding="utf-8"))
        )

    def update(self, record: PullRequestRecord) -> PullRequestRecord:
        self._save(record)
        return record

    def _save(self, record: PullRequestRecord) -> None:
        self.prs_dir.mkdir(parents=True, exist_ok=True)
        self._path(record.number).write_text(
            yaml.safe_dump(record.model_dump(mode="json"), sort_keys=False),
            encoding="utf-8",
        )
