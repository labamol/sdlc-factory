"""Scoped shell tool.

Deterministic command execution inside a workspace: only allowlisted
executables, bounded runtime, captured output. Agents never shell out
directly; they request execution through this tool.
"""

import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel

DEFAULT_ALLOWED = ("python", sys.executable)


class ShellResult(BaseModel):
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class ShellTool:
    def __init__(
        self,
        workdir: Path,
        *,
        allowed: tuple[str, ...] = DEFAULT_ALLOWED,
        timeout: int = 120,
    ) -> None:
        self.workdir = workdir.resolve()
        self.allowed = allowed
        self.timeout = timeout

    def run(self, command: list[str]) -> ShellResult:
        if not command:
            raise ValueError("Empty command")
        if command[0] not in self.allowed:
            raise PermissionError(f"Executable not allowlisted: {command[0]}")
        completed = subprocess.run(
            command,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        return ShellResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
