"""Mocked stage agents for Increment 1.

Each mocked agent produces the stage's expected artifacts as real files under
the project directory and returns evidence references, so the control plane
can be exercised end-to-end before real reasoning agents exist.
"""

from pathlib import Path

from factory.agents.base import AgentResult
from factory.models.enums import FactoryState, TestStatus
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.orchestrator.events import new_id
from factory.tools.filesystem import FilesystemTool

STAGE_ARTIFACTS: dict[FactoryState, list[str]] = {
    FactoryState.INTAKE: ["intake/requirements.md"],
    FactoryState.CLARIFICATION: ["intake/clarifications.md", "intake/assumptions.md"],
    FactoryState.REQUIREMENTS_READY: [],
    FactoryState.DECOMPOSED: [
        "decisions/features.yaml",
        "decisions/stories.yaml",
        "decisions/traceability.yaml",
    ],
    FactoryState.SPECIFIED: [
        "specs/spec.md",
        "specs/acceptance-criteria.md",
        "specs/tasks.md",
    ],
    FactoryState.KNOWLEDGE_MINED: ["specs/context-pack.md"],
    FactoryState.DESIGNED: ["specs/design.md"],
    FactoryState.TASKS_READY: [],
    FactoryState.TEST_DESIGNED: ["specs/test-plan.yaml"],
    FactoryState.IMPLEMENTING: [],
    FactoryState.BUILT: ["evidence/build.json"],
    FactoryState.UNIT_TESTED: ["evidence/unit-test-report.json"],
    FactoryState.PR_CREATED: ["evidence/pr.json"],
    FactoryState.REVIEWED: ["evidence/review-report.md"],
    FactoryState.MERGE_READY: [],
    FactoryState.POLICY_GATE: ["evidence/quality-gate.json"],
    FactoryState.MERGED: ["evidence/merge.json"],
    FactoryState.PACKAGED: ["evidence/artifact.json"],
    FactoryState.PUBLISHED: ["evidence/artifact-uri.txt"],
    FactoryState.DEPLOYED: ["evidence/deployment.json", "evidence/smoke-report.json"],
    FactoryState.FUNCTIONAL_TESTED: ["evidence/functional-report.json"],
    FactoryState.AC_VALIDATED: ["evidence/validation-report.json"],
    FactoryState.STORY_COMPLETED: ["evidence/tracker-completion.json"],
    FactoryState.LEARNED: ["evidence/learning-record.yaml"],
}

STAGE_STATE_UPDATES: dict[FactoryState, dict] = {
    FactoryState.SPECIFIED: {"spec_version": "v1"},
    FactoryState.IMPLEMENTING: {"branch": "feature/demo"},
    FactoryState.UNIT_TESTED: {"unit_test_status": TestStatus.PASSED, "coverage": 86.4},
    FactoryState.PR_CREATED: {"pull_request": 1},
    FactoryState.DEPLOYED: {"deployment_environment": "local"},
    FactoryState.FUNCTIONAL_TESTED: {"functional_test_status": TestStatus.PASSED},
}


class MockedStageAgent:
    """Stands in for any factory agent; writes stage artifacts and evidence."""

    def __init__(self, name: str, project_dir: Path) -> None:
        self.name = name
        self.fs = FilesystemTool(project_dir)

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        evidence: list[Evidence] = []
        for artifact in STAGE_ARTIFACTS.get(stage, []):
            path = self.fs.write_text(
                artifact,
                f"# {artifact}\nfeature: {feature.feature_id}\nstage: {stage.value}\n"
                f"agent: {self.name}\n(mocked artifact)\n",
            )
            evidence.append(
                Evidence(
                    evidence_id=new_id("EVD"),
                    stage=stage.value,
                    kind=Path(artifact).stem,
                    ref=str(path),
                    summary=f"Mocked {artifact} produced by {self.name}",
                )
            )
        return AgentResult(
            status="SUCCESS",
            summary=f"{self.name} completed {stage.value}",
            evidence=evidence,
            state_updates=dict(STAGE_STATE_UPDATES.get(stage, {})),
            skill=f"{self.name}/mocked",
        )


AGENT_NAMES = [
    "orchestrator",
    "requirements-agent",
    "product-agent",
    "specification-agent",
    "knowledge-agent",
    "design-agent",
    "implementation-agent",
    "test-agent",
    "review-agent",
    "release-agent",
    "validation-agent",
    "learning-agent",
]


def build_mocked_agents(project_dir: Path) -> dict[str, MockedStageAgent]:
    return {name: MockedStageAgent(name, project_dir) for name in AGENT_NAMES}
