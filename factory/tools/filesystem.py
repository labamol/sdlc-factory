"""Deterministic filesystem tool scoped to a root directory."""

from pathlib import Path


class FilesystemTool:
    name = "filesystem"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _resolve(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise PermissionError(f"Path escapes tool root: {relative}")
        return path

    def write_text(self, relative: str, content: str) -> Path:
        path = self._resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_text(self, relative: str) -> str:
        return self._resolve(relative).read_text(encoding="utf-8")

    def exists(self, relative: str) -> bool:
        return self._resolve(relative).exists()

    def list_dir(self, relative: str = ".") -> list[str]:
        return sorted(p.name for p in self._resolve(relative).iterdir())
