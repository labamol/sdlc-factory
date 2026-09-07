"""Deterministic Git tool wrapping the git CLI for a single repository."""

import subprocess
from pathlib import Path

CREDENTIAL_PREFIXES = ("http.extraheader=",)


class GitError(Exception):
    pass


def _redact(args: tuple[str, ...]) -> str:
    """Never echo an authorization header back into an exception or a log."""
    return " ".join(
        "[REDACTED]" if arg.startswith(CREDENTIAL_PREFIXES) else arg for arg in args
    )


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
            raise GitError(f"git {_redact(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def run_raw(self, *args: str) -> str:
        """Escape hatch for adapters needing git flags this tool does not model."""
        return self._run(*args)

    def has_commits(self) -> bool:
        try:
            self._run("rev-parse", "--verify", "HEAD")
        except GitError:
            return False
        return True

    def init(self, default_branch: str = "main") -> None:
        self._run("init", "-b", default_branch)

    def is_repo(self) -> bool:
        return (self.repo_dir / ".git").exists()

    def configure_identity(self, name: str, email: str) -> None:
        """Set a repository-local committer identity for factory-owned repos."""
        self._run("config", "user.name", name)
        self._run("config", "user.email", email)

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
