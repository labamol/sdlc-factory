"""Test engineering agent.

Owns TEST_DESIGNED (test plan, generated acceptance-criteria tests and
synthetic data, before implementation) and UNIT_TESTED / RETEST (executing
the workspace test suite through the scoped shell tool and recording the
report as evidence).
"""

import json
import sys
from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.implementation.codegen import feature_module_name
from factory.implementation.synthdata import generate_synthetic_records
from factory.implementation.testgen import generate_feature_tests
from factory.models.enums import FactoryState, TestStatus
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.models.requirement import Feature
from factory.models.story import Story
from factory.orchestrator.events import new_id
from factory.tools.filesystem import FilesystemTool
from factory.tools.shell import ShellTool


class TestEngineeringAgent:
    name = "test-agent"

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.fs = FilesystemTool(project_dir)

    def _load(self, relative: str) -> list[dict]:
        if not self.fs.exists(relative):
            return []
        return yaml.safe_load(self.fs.read_text(relative)) or []

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage == FactoryState.TEST_DESIGNED:
            return self._design_tests(stage)
        if stage in (FactoryState.UNIT_TESTED, FactoryState.RETEST):
            return self._run_tests(stage)
        return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

    def _design_tests(self, stage: FactoryState) -> AgentResult:
        features = [Feature.model_validate(f) for f in self._load("backlog/features.yaml")]
        stories = [Story.model_validate(s) for s in self._load("backlog/stories.yaml")]
        if not features:
            return AgentResult(status="FAILURE", summary="No features for test design")

        plan = []
        for feat in features:
            feature_stories = [s for s in stories if s.feature_id == feat.feature_id]
            module = feature_module_name(feat.feature_id)
            self.fs.write_text(
                f"workspace/tests/test_{module}.py",
                generate_feature_tests(feat, feature_stories),
            )
            plan.append(
                {
                    "feature_id": feat.feature_id,
                    "test_file": f"workspace/tests/test_{module}.py",
                    "levels": ["unit", "acceptance"],
                    "acceptance_criteria": [
                        ac.ac_id for s in feature_stories for ac in s.acceptance_criteria
                    ],
                }
            )
        self.fs.write_text(
            "workspace/conftest.py",
            "import sys\n"
            "from pathlib import Path\n"
            "\n"
            'sys.path.insert(0, str(Path(__file__).parent / "src"))\n',
        )
        data = {
            s.story_id: generate_synthetic_records(s.story_id, count=3) for s in stories
        }
        data_path = self.fs.write_text(
            "workspace/data/synthetic.json", json.dumps(data, indent=2)
        )
        plan_path = self.fs.write_text(
            "testing/test-plan.yaml", yaml.safe_dump(plan, sort_keys=False)
        )
        total_acs = sum(len(p["acceptance_criteria"]) for p in plan)
        return AgentResult(
            summary=f"Test plan for {len(plan)} feature(s), {total_acs} AC tests generated",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="test-plan",
                    ref=str(plan_path), summary="Test plan with AC traceability",
                ),
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="synthetic-data",
                    ref=str(data_path), summary="Deterministic synthetic fixtures",
                ),
            ],
            skill="testing/pytest-unit",
        )

    def _run_tests(self, stage: FactoryState) -> AgentResult:
        workspace = self.project_dir / "workspace"
        shell = ShellTool(workspace)
        result = shell.run(
            [sys.executable, "-m", "pytest", "tests", "-q", "--rootdir", "."]
        )
        report_path = self.fs.write_text(
            f"testing/{stage.value.lower()}-report.txt",
            f"$ pytest tests -q\nexit={result.exit_code}\n\n{result.stdout}{result.stderr}",
        )
        status = TestStatus.PASSED if result.ok else TestStatus.FAILED
        return AgentResult(
            status="SUCCESS" if result.ok else "FAILURE",
            summary=f"Unit tests {'passed' if result.ok else 'failed'}",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="test-report",
                    ref=str(report_path), summary=result.stdout.strip().splitlines()[-1]
                    if result.stdout.strip() else "no output",
                )
            ],
            state_updates={"unit_test_status": status},
            skill="testing/pytest-unit",
        )
