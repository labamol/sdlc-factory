"""Deterministic Git tool wrapping the git CLI for a single repository."""

import subprocess
from pathlib import Path


class GitError(Exception):
    pass


class GitTool:
    name = "git"

    def __init__(self, repo_dir: Path) -> None:
        self.repo_dir = repo_dir

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def init(self, default_branch: str = "main") -> None:
        self._run("init", "-b", default_branch)

    def current_commit(self) -> str:
        return self._run("rev-parse", "HEAD")

    def current_branch(self) -> str:
        return self._run("rev-parse", "--abbrev-ref", "HEAD")

    def create_branch(self, name: str) -> None:
        self._run("checkout", "-b", name)

    def checkout(self, ref: str) -> None:
        self._run("checkout", ref)

    def add(self, *paths: str) -> None:
        self._run("add", *paths)

    def commit(self, message: str) -> str:
        self._run("commit", "-m", message)
        return self.current_commit()

    def merge(self, branch: str, message: str | None = None) -> str:
        args = ["merge", "--no-ff", branch]
        if message:
            args += ["-m", message]
        self._run(*args)
        return self.current_commit()

    def status_porcelain(self) -> str:
        return self._run("status", "--porcelain")
