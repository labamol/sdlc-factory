"""Deterministic pull-request tool.

Maintains a project-local PR registry (`prs/PR-<n>.yaml`) and performs the
branch/commit/merge mechanics inside the project's own Git repository. It
implements the same `Forge` contract as the GitHub adapter, so a factory with
no remote configured still traverses PR_CREATED -> MERGED with real commits.
"""

from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from factory.tools.git import GitError, GitTool

COMMIT_PATHS = ("workspace", "design", "testing", "quality")


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
    url: str = ""  # populated by remote forges


class PrTool:
    name = "github"

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.prs_dir = project_dir / "prs"

    def publish(self, branch: str, source_dir: Path, *, base: str, message: str) -> str:
        """Commit the generated artifacts in the project's own repository."""
        git = GitTool(self.project_dir)
        if not git.is_repo():
            return ""
        existing = [p for p in COMMIT_PATHS if (self.project_dir / p).exists()]
        if existing:
            git.add(*existing)
        if not git.status_porcelain():
            return git.current_commit()
        try:
            return git.commit(message)
        except GitError:
            return git.current_commit()

    def _path(self, number: int) -> Path:
        return self.prs_dir / f"PR-{number}.yaml"

    def next_number(self) -> int:
        if not self.prs_dir.exists():
            return 1
        return len(list(self.prs_dir.glob("PR-*.yaml"))) + 1

    def create(
        self, title: str, branch: str, *, base: str = "main",
        commit: str = "", files: list[str] | None = None, body: str = "",
    ) -> PullRequestRecord:
        record = PullRequestRecord(
            number=self.next_number(), title=title, branch=branch,
            base=base, commit=commit, files=files or [],
        )
        self._save(record)
        return record

    def merge(self, record: PullRequestRecord, *, message: str) -> PullRequestRecord:
        git = GitTool(self.project_dir)
        if git.is_repo() and record.branch:
            git.checkout(record.base)
            record.merged_commit = git.merge(record.branch, message)
        record.status = "MERGED"
        return self.update(record)

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
