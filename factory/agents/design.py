"""Design agent.

Owns DESIGNED: derives a technical design from the specified backlog and the
context pack, selecting an implementation worker per feature and recording
module/test layout decisions.
"""

from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.agents.workers import select_worker
from factory.implementation.codegen import feature_module_name
from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.models.requirement import Feature
from factory.orchestrator.events import new_id
from factory.tools.filesystem import FilesystemTool


class DesignAgent:
    name = "design-agent"

    def __init__(self, project_dir: Path) -> None:
        self.fs = FilesystemTool(project_dir)

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage != FactoryState.DESIGNED:
            return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

        raw = yaml.safe_load(self.fs.read_text("backlog/features.yaml")) or []
        features = [Feature.model_validate(f) for f in raw]
        if not features:
            return AgentResult(status="FAILURE", summary="No features to design")

        lines = ["# Technical Design", ""]
        assignments = []
        for feat in features:
            worker = select_worker(f"{feat.title} {feat.description}")
            module = feature_module_name(feat.feature_id)
            assignments.append(
                {
                    "feature_id": feat.feature_id,
                    "worker_id": worker.worker_id,
                    "module": f"src/{module}.py",
                    "tests": f"tests/test_{module}.py",
                    "skills": worker.skills,
                }
            )
            lines += [
                f"## {feat.feature_id}: {feat.title}",
                "",
                f"- worker: {worker.worker_id} ({worker.title})",
                f"- skills: {', '.join(worker.skills)}",
                f"- module: `src/{module}.py` (one entry function per story)",
                f"- tests: `tests/test_{module}.py` (one test per acceptance criterion)",
                "- data: deterministic synthetic records seeded from story IDs",
                "",
            ]
        design_path = self.fs.write_text("design/design.md", "\n".join(lines))
        plan_path = self.fs.write_text(
            "design/worker-assignments.yaml", yaml.safe_dump(assignments, sort_keys=False)
        )

        return AgentResult(
            summary=f"Designed {len(features)} feature(s), workers assigned",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="design",
                    ref=str(design_path), summary="Technical design",
                ),
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="worker-assignments",
                    ref=str(plan_path), summary="Worker assignments per feature",
                ),
            ],
            skill="design/module-decomposition",
        )
