"""Exact/code search over a repository tree.

Deterministic grep-style search plus Python symbol indexing (functions and
classes) so implementation agents can locate existing code precisely rather
than relying on semantic similarity alone.
"""

import re
from pathlib import Path

from pydantic import BaseModel

DEFAULT_EXTENSIONS = (".py", ".md", ".yaml", ".yml", ".toml", ".json", ".txt")
PY_SYMBOL = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)")
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}


class SearchHit(BaseModel):
    path: str
    line_number: int
    line: str
    symbol: str = ""


class CodeSearch:
    def __init__(self, root: Path, extensions: tuple[str, ...] = DEFAULT_EXTENSIONS) -> None:
        self.root = root.resolve()
        self.extensions = extensions

    def _files(self) -> list[Path]:
        files = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix not in self.extensions:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            files.append(path)
        return files

    def grep(self, pattern: str, *, limit: int = 50) -> list[SearchHit]:
        regex = re.compile(pattern)
        hits: list[SearchHit] = []
        for path in self._files():
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
            ):
                if regex.search(line):
                    hits.append(
                        SearchHit(
                            path=str(path.relative_to(self.root)),
                            line_number=line_number,
                            line=line.strip(),
                        )
                    )
                    if len(hits) >= limit:
                        return hits
        return hits

    def symbols(self, name_pattern: str = ".*") -> list[SearchHit]:
        """Index Python function/class definitions matching a name pattern."""
        regex = re.compile(name_pattern)
        hits: list[SearchHit] = []
        for path in self._files():
            if path.suffix != ".py":
                continue
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
            ):
                match = PY_SYMBOL.match(line)
                if match and regex.search(match.group(1)):
                    hits.append(
                        SearchHit(
                            path=str(path.relative_to(self.root)),
                            line_number=line_number,
                            line=line.strip(),
                            symbol=match.group(1),
                        )
                    )
        return hits
