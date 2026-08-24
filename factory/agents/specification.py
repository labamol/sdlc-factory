"""Specification agent.

Owns SPECIFIED: runs the Spec Kit lifecycle (specify -> clarify -> plan ->
tasks -> analyze) for every decomposed feature and versions the resulting
spec artifacts in Git.
"""

from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.models.requirement import Assumption, Decision, Feature, Requirement
from factory.models.story import Story
from factory.orchestrator.events import new_id
from factory.speckit.adapter import SpecAnalysisError, SpecKitAdapter
from factory.tools.filesystem import FilesystemTool


class SpecificationAgent:
    name = "specification-agent"

    def __init__(self, project_dir: Path) -> None:
        self.fs = FilesystemTool(project_dir)
        self.speckit = SpecKitAdapter(project_dir)

    def _load(self, relative: str) -> list[dict]:
        if not self.fs.exists(relative):
            return []
        return yaml.safe_load(self.fs.read_text(relative)) or []

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage != FactoryState.SPECIFIED:
            return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

        requirements = [
            Requirement.model_validate(r) for r in self._load("requirements/requirements.yaml")
        ]
        features = [Feature.model_validate(f) for f in self._load("backlog/features.yaml")]
        stories = [Story.model_validate(s) for s in self._load("backlog/stories.yaml")]
        decisions = [Decision.model_validate(d) for d in self._load("decisions/decisions.yaml")]
        assumptions = [
            Assumption.model_validate(a) for a in self._load("requirements/assumptions.yaml")
        ]
        if not features:
            return AgentResult(status="FAILURE", summary="No decomposed features to specify")

        spec_version = "v1"
        evidence: list[Evidence] = []
        for feat in features:
            feature_stories = [s for s in stories if s.feature_id == feat.feature_id]
            try:
                artifacts = self.speckit.run_lifecycle(
                    feat, requirements, feature_stories, decisions, assumptions
                )
            except SpecAnalysisError as exc:
                return AgentResult(
                    status="FAILURE",
                    summary=f"Spec analysis failed for {feat.feature_id}: {exc}",
                )
            commit = self.speckit.commit_spec(feat, spec_version)
            for phase, path in artifacts.items():
                evidence.append(
                    Evidence(
                        evidence_id=new_id("EVD"),
                        stage=stage.value,
                        kind=f"spec-{phase}",
                        ref=str(path),
                        summary=f"Spec Kit {phase} for {feat.feature_id}",
                        metadata={"commit": commit or ""},
                    )
                )

        return AgentResult(
            summary=f"Specified {len(features)} feature(s) at {spec_version}",
            evidence=evidence,
            state_updates={"spec_version": spec_version},
            skill="specification/spec-kit-lifecycle",
        )
