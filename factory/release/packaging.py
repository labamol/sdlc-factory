"""Deterministic packaging.

Builds a reproducible source artifact from the merged workspace: a tar.gz
with fixed metadata (mtime/uid/gid zeroed) plus a MANIFEST recording the
sha256 of every packaged file, the version and the source commit, so the
same inputs always produce byte-identical artifacts.
"""

import gzip
import hashlib
import io
import tarfile
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

PACKAGED_DIRS = ("src", "tests", "data")
PACKAGED_ROOT_FILES = ("conftest.py",)


class ArtifactManifest(BaseModel):
    name: str
    version: str
    commit: str = ""
    files: dict[str, str] = Field(default_factory=dict)  # relative path -> sha256

    @property
    def filename(self) -> str:
        return f"{self.name}-{self.version}.tar.gz"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _add_bytes(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    tar.addfile(info, io.BytesIO(data))


def build_artifact(
    workspace: Path, dist_dir: Path, *, name: str, version: str, commit: str = ""
) -> tuple[Path, ArtifactManifest]:
    """Package the workspace into dist_dir; returns (artifact path, manifest)."""
    manifest = ArtifactManifest(name=name, version=version, commit=commit)
    members: list[tuple[str, bytes]] = []
    for filename in PACKAGED_ROOT_FILES:
        path = workspace / filename
        if path.is_file():
            data = path.read_bytes()
            manifest.files[filename] = _sha256(data)
            members.append((filename, data))
    for directory in PACKAGED_DIRS:
        root = workspace / directory
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                data = path.read_bytes()
                relative = str(path.relative_to(workspace))
                manifest.files[relative] = _sha256(data)
                members.append((relative, data))
    if not members:
        raise FileNotFoundError(f"Nothing to package under {workspace}")

    manifest_bytes = yaml.safe_dump(
        manifest.model_dump(mode="json"), sort_keys=True
    ).encode("utf-8")

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        _add_bytes(tar, "MANIFEST.yaml", manifest_bytes)
        for relative, data in members:
            _add_bytes(tar, relative, data)

    dist_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = dist_dir / manifest.filename
    artifact_path.write_bytes(gzip.compress(buffer.getvalue(), 9, mtime=0))
    return artifact_path, manifest


def artifact_sha256(artifact_path: Path) -> str:
    return _sha256(artifact_path.read_bytes())
