"""Implementation agent (worker pool).

Owns IMPLEMENTING (feature branch + module skeletons in the workspace) and
BUILT (generated story implementations plus the full pre-PR quality
pipeline: formatting, build, security scan, unit tests, spec compliance and
coverage — all recorded as explainable evidence).
"""

from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.agents.workers import select_worker
from factory.implementation.codegen import feature_module_name, generate_feature_module
from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.models.requirement import Feature
from factory.models.story import Story
from factory.orchestrator.events import new_id
from factory.quality.prepr import run_pre_pr_checks
from factory.tools.filesystem import FilesystemTool
from factory.tools.git import GitTool


class ImplementationAgent:
    name = "implementation-agent"

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.fs = FilesystemTool(project_dir)

    def _load(self, relative: str) -> list[dict]:
        if not self.fs.exists(relative):
            return []
        return yaml.safe_load(self.fs.read_text(relative)) or []

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage == FactoryState.IMPLEMENTING:
            return self._start_implementation(feature, stage)
        if stage in (FactoryState.BUILT, FactoryState.RETEST, FactoryState.DIAGNOSE):
            return self._build(stage)
        return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

    def _start_implementation(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        branch = f"feature/{feature.feature_id.lower()}"
        git = GitTool(self.project_dir)
        if git.is_repo():
            git.create_branch(branch)
        note_path = self.fs.write_text(
            "workspace/BRANCH", f"{branch}\n"
        )
        return AgentResult(
            summary=f"Implementation started on {branch}",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="feature-branch",
                    ref=str(note_path), summary=f"Branch {branch}",
                )
            ],
            state_updates={"branch": branch},
            skill="implementation/python-fastapi",
        )

    def _build(self, stage: FactoryState) -> AgentResult:
        features = [Feature.model_validate(f) for f in self._load("backlog/features.yaml")]
        stories = [Story.model_validate(s) for s in self._load("backlog/stories.yaml")]
        if not features:
            return AgentResult(status="FAILURE", summary="No features to implement")

        evidence: list[Evidence] = []
        for feat in features:
            feature_stories = [s for s in stories if s.feature_id == feat.feature_id]
            worker = select_worker(f"{feat.title} {feat.description}")
            module = feature_module_name(feat.feature_id)
            path = self.fs.write_text(
                f"workspace/src/{module}.py",
                generate_feature_module(feat, feature_stories),
            )
            evidence.append(
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="source",
                    ref=str(path),
                    summary=f"{feat.feature_id} implemented by {worker.worker_id}",
                    metadata={"worker": worker.worker_id, "skills": worker.skills},
                )
            )

        report = run_pre_pr_checks(self.project_dir / "workspace", stories)
        report_path = self.fs.write_text(
            "quality/pre-pr-report.yaml",
            yaml.safe_dump(report.model_dump(mode="json"), sort_keys=False),
        )
        evidence.append(
            Evidence(
                evidence_id=new_id("EVD"), stage=stage.value, kind="pre-pr-checks",
                ref=str(report_path),
                summary="; ".join(
                    f"{c.name}={'PASS' if c.passed else 'FAIL'}" for c in report.checks
                ),
            )
        )
        if not report.passed:
            failed = [c.name for c in report.checks if not c.passed]
            return AgentResult(
                status="FAILURE",
                summary=f"Pre-PR checks failed: {', '.join(failed)}",
                evidence=evidence,
                skill="implementation/python-fastapi",
            )
        return AgentResult(
            summary=f"Built {len(features)} feature module(s); all pre-PR checks passed",
            evidence=evidence,
            skill="implementation/python-fastapi",
        )
