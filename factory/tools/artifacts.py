"""Deterministic artifact repository tool.

A local artifact repository under `artifacts/`: publishing verifies the
checksum, stores the artifact immutably and returns a stable
`artifact://<project>/<filename>` URI with a registry entry. A remote
repository (PyPI, OCI registry, S3) swaps in behind the same contract.
"""

import shutil
from pathlib import Path

import yaml
from pydantic import BaseModel

from factory.release.packaging import artifact_sha256


class PublishedArtifact(BaseModel):
    uri: str
    filename: str
    sha256: str
    project_id: str


class ArtifactRepoTool:
    name = "artifact-repo"

    def __init__(self, repo_dir: Path) -> None:
        self.repo_dir = repo_dir

    def _registry_path(self) -> Path:
        return self.repo_dir / "registry.yaml"

    def _registry(self) -> list[dict]:
        if not self._registry_path().exists():
            return []
        return yaml.safe_load(self._registry_path().read_text(encoding="utf-8")) or []

    def publish(self, artifact_path: Path, *, project_id: str) -> PublishedArtifact:
        digest = artifact_sha256(artifact_path)
        target = self.repo_dir / project_id / artifact_path.name
        if target.exists():
            if artifact_sha256(target) != digest:
                raise ValueError(
                    f"Immutable artifact conflict: {target.name} already "
                    "published with a different checksum"
                )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(artifact_path, target)
        record = PublishedArtifact(
            uri=f"artifact://{project_id}/{artifact_path.name}",
            filename=artifact_path.name, sha256=digest, project_id=project_id,
        )
        registry = [e for e in self._registry() if e["uri"] != record.uri]
        registry.append(record.model_dump(mode="json"))
        self._registry_path().parent.mkdir(parents=True, exist_ok=True)
        self._registry_path().write_text(
            yaml.safe_dump(sorted(registry, key=lambda e: e["uri"]), sort_keys=False),
            encoding="utf-8",
        )
        return record

    def resolve(self, uri: str) -> Path:
        if not uri.startswith("artifact://"):
            raise ValueError(f"Not an artifact URI: {uri}")
        project_id, _, filename = uri.removeprefix("artifact://").partition("/")
        path = self.repo_dir / project_id / filename
        if not path.exists():
            raise FileNotFoundError(f"Artifact not published: {uri}")
        entry = next((e for e in self._registry() if e["uri"] == uri), None)
        if entry and artifact_sha256(path) != entry["sha256"]:
            raise ValueError(f"Checksum mismatch for {uri}")
        return path
