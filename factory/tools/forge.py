"""Forge contract: the tool-plane interface for branches, PRs and merges.

Two implementations satisfy it — the project-local registry (`PrTool`) that
keeps the factory self-contained, and the GitHub adapter that publishes the
generated workspace to a real repository. Agents and policies depend on this
protocol only, so switching forges never changes WHEN or WHAT is decided.
"""

from pathlib import Path
from typing import Protocol

from factory.tools.pr import PullRequestRecord


class ForgeError(Exception):
    """Raised when a forge operation cannot be completed."""


class Forge(Protocol):
    name: str

    def publish(self, branch: str, source_dir: Path, *, base: str, message: str) -> str:
        """Place the generated code on `branch` and return the commit sha."""
        ...

    def create(
        self,
        title: str,
        branch: str,
        *,
        base: str = "main",
        commit: str = "",
        files: list[str] | None = None,
        body: str = "",
    ) -> PullRequestRecord: ...

    def get(self, number: int) -> PullRequestRecord: ...

    def update(self, record: PullRequestRecord) -> PullRequestRecord: ...

    def merge(self, record: PullRequestRecord, *, message: str) -> PullRequestRecord:
        """Merge the pull request and return the record with `merged_commit` set."""
        ...
