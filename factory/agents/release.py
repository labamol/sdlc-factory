"""Release agent.

Owns PACKAGED (deterministic artifact build from the merged workspace),
PUBLISHED (checksum-verified publish to the artifact repository) and
DEPLOYED (deploy the published artifact to the target environment and run
smoke tests). Every stage leaves a durable release record.
"""

from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.orchestrator.events import new_id
from factory.release.deploy import deploy_artifact, run_smoke_tests
from factory.release.packaging import artifact_sha256, build_artifact
from factory.tools.artifacts import ArtifactRepoTool
from factory.tools.filesystem import FilesystemTool
from factory.tools.git import GitTool

RELEASE_RECORD = "release/release.yaml"


class ReleaseAgent:
    name = "release-agent"

    def __init__(
        self, project_dir: Path, *, environment: str = "local",
        artifact_repo_dir: Path | None = None,
    ) -> None:
        self.project_dir = project_dir
        self.fs = FilesystemTool(project_dir)
        self.environment = environment
        self.repo = ArtifactRepoTool(artifact_repo_dir or project_dir / "artifacts")

    def _record(self) -> dict:
        if not self.fs.exists(RELEASE_RECORD):
            return {}
        return yaml.safe_load(self.fs.read_text(RELEASE_RECORD)) or {}

    def _save_record(self, record: dict) -> Path:
        return self.fs.write_text(
            RELEASE_RECORD, yaml.safe_dump(record, sort_keys=False)
        )

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage == FactoryState.PACKAGED:
            return self._package(feature, stage)
        if stage == FactoryState.PUBLISHED:
            return self._publish(feature, stage)
        if stage == FactoryState.DEPLOYED:
            return self._deploy(feature, stage)
        return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

    def _package(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        git = GitTool(self.project_dir)
        commit = git.current_commit() if git.is_repo() else ""
        version = f"{feature.spec_version or 'v1'}.0"
        artifact_path, manifest = build_artifact(
            self.project_dir / "workspace",
            self.project_dir / "dist",
            name=feature.feature_id.lower(),
            version=version,
            commit=commit,
        )
        record = self._record()
        record.update(
            {
                "feature_id": feature.feature_id,
                "version": version,
                "artifact": artifact_path.name,
                "sha256": artifact_sha256(artifact_path),
                "commit": commit,
                "packaged_files": len(manifest.files),
            }
        )
        record_path = self._save_record(record)
        return AgentResult(
            summary=f"Packaged {artifact_path.name} ({len(manifest.files)} files)",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="artifact",
                    ref=str(artifact_path),
                    summary=f"{artifact_path.name} sha256={record['sha256'][:12]}",
                    metadata={"version": version, "commit": commit},
                ),
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="release-record",
                    ref=str(record_path), summary="Release record",
                ),
            ],
            skill="release/package",
        )

    def _publish(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        record = self._record()
        if not record.get("artifact"):
            return AgentResult(status="FAILURE", summary="No packaged artifact to publish")
        artifact_path = self.project_dir / "dist" / record["artifact"]
        published = self.repo.publish(artifact_path, project_id=feature.project_id)
        if published.sha256 != record["sha256"]:
            return AgentResult(
                status="FAILURE", summary="Published checksum differs from packaged"
            )
        record["artifact_uri"] = published.uri
        record_path = self._save_record(record)
        return AgentResult(
            summary=f"Published {published.uri}",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="artifact-uri",
                    ref=str(record_path), summary=published.uri,
                    metadata={"sha256": published.sha256},
                )
            ],
            skill="release/publish",
        )

    def _deploy(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        record = self._record()
        uri = record.get("artifact_uri", "")
        if not uri:
            return AgentResult(status="FAILURE", summary="No published artifact to deploy")
        artifact_path = self.repo.resolve(uri)
        target = self.project_dir / "deployments" / self.environment
        descriptor = deploy_artifact(
            artifact_path, target, environment=self.environment,
            artifact_uri=uri, sha256=record["sha256"],
        )
        smoke = run_smoke_tests(target, descriptor)
        smoke_path = self.fs.write_text(
            "release/smoke-report.yaml",
            yaml.safe_dump(smoke.model_dump(mode="json"), sort_keys=False),
        )
        record["environment"] = self.environment
        record["smoke_passed"] = smoke.passed
        self._save_record(record)
        return AgentResult(
            status="SUCCESS" if smoke.passed else "FAILURE",
            summary=f"Deployed to {self.environment}; smoke "
                    f"{'passed' if smoke.passed else 'FAILED'}",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="deployment",
                    ref=str(target / "deployment.yaml"),
                    summary=f"{uri} -> {self.environment}",
                ),
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="smoke-evidence",
                    ref=str(smoke_path),
                    summary=f"{sum(c['passed'] for c in smoke.checks)}/"
                            f"{len(smoke.checks)} smoke checks passed",
                ),
            ],
            state_updates={"deployment_environment": self.environment},
            skill="release/deploy",
        )
