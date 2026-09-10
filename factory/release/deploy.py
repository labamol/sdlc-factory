"""Deterministic deployment and smoke testing.

Deploys a published artifact into an environment directory (the local
environment is a scoped filesystem deployment; container/VM adapters satisfy
the same contract), writes a deployment descriptor, and runs smoke tests:
every deployed module must import cleanly in a fresh interpreter.
"""

import gzip
import io
import sys
import tarfile
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from factory.tools.shell import ShellTool


class DeploymentDescriptor(BaseModel):
    environment: str
    artifact_uri: str
    sha256: str
    target: str
    modules: list[str] = Field(default_factory=list)


class SmokeReport(BaseModel):
    passed: bool
    checks: list[dict] = Field(default_factory=list)


def deploy_artifact(
    artifact_path: Path, target_dir: Path, *, environment: str,
    artifact_uri: str, sha256: str,
) -> DeploymentDescriptor:
    target_dir.mkdir(parents=True, exist_ok=True)
    data = gzip.decompress(artifact_path.read_bytes())
    with tarfile.open(fileobj=io.BytesIO(data), mode="r") as tar:
        for member in tar.getmembers():
            resolved = (target_dir / member.name).resolve()
            if not resolved.is_relative_to(target_dir.resolve()):
                raise PermissionError(f"Archive member escapes target: {member.name}")
        tar.extractall(target_dir)
    modules = sorted(p.stem for p in (target_dir / "src").glob("*.py"))
    descriptor = DeploymentDescriptor(
        environment=environment, artifact_uri=artifact_uri, sha256=sha256,
        target=str(target_dir), modules=modules,
    )
    (target_dir / "deployment.yaml").write_text(
        yaml.safe_dump(descriptor.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    return descriptor


def run_smoke_tests(target_dir: Path, descriptor: DeploymentDescriptor) -> SmokeReport:
    shell = ShellTool(target_dir)
    checks: list[dict] = []
    for module in descriptor.modules:
        script = (
            "import sys; sys.path.insert(0, 'src'); "
            f"import {module}; {module}.reset()"
        )
        result = shell.run([sys.executable, "-c", script])
        checks.append(
            {
                "check": f"import+reset {module}",
                "passed": result.ok,
                "detail": result.stderr.strip()[-200:] if not result.ok else "",
            }
        )
    checks.append(
        {
            "check": "deployment descriptor present",
            "passed": (target_dir / "deployment.yaml").exists(),
            "detail": "",
        }
    )
    return SmokeReport(passed=all(c["passed"] for c in checks), checks=checks)
