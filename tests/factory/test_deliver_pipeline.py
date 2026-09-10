"""Factory tests: full delivery from BRD to executed unit tests."""

from pathlib import Path

import pytest
import yaml

from factory.cli import run_intake
from factory.models import enums
from factory.models.enums import FactoryState

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
BRD = EXAMPLES / "brd" / "sample-brd.md"
TRANSCRIPT = EXAMPLES / "meetings" / "kickoff-transcript.md"


@pytest.mark.asyncio
async def test_deliver_reaches_unit_tested_with_passing_tests(tmp_path):
    feature = await run_intake(
        tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-D1", deliver=True
    )
    assert feature.current_state == FactoryState.UNIT_TESTED
    assert feature.unit_test_status == enums.TestStatus.PASSED
    assert feature.branch == "feature/feat-000"

    project_dir = tmp_path / "projects" / "PRJ-D1"

    # design + tasks + test plan artifacts
    assert (project_dir / "design" / "design.md").exists()
    assignments = yaml.safe_load(
        (project_dir / "design" / "worker-assignments.yaml").read_text()
    )
    assert len(assignments) == 3 and all(a["worker_id"] for a in assignments)
    tasks = yaml.safe_load((project_dir / "design" / "tasks.yaml").read_text())
    assert len(tasks) == 8
    plan = yaml.safe_load((project_dir / "testing" / "test-plan.yaml").read_text())
    assert sum(len(p["acceptance_criteria"]) for p in plan) == 16

    # generated workspace: one module and one test file per feature
    src_files = sorted((project_dir / "workspace" / "src").glob("*.py"))
    test_files = sorted((project_dir / "workspace" / "tests").glob("test_*.py"))
    assert len(src_files) == 3 and len(test_files) == 3
    assert (project_dir / "workspace" / "data" / "synthetic.json").exists()

    # pre-PR quality report: every check passed with threshold/actual/evidence
    report = yaml.safe_load((project_dir / "quality" / "pre-pr-report.yaml").read_text())
    names = {c["name"] for c in report["checks"]}
    assert {
        "formatting", "build", "security_critical_findings",
        "unit_tests", "spec_compliance", "coverage",
    } <= names
    assert all(c["passed"] for c in report["checks"])
    assert all(c["threshold"] and c["actual"] for c in report["checks"])

    # executed test report evidence
    report_txt = (project_dir / "testing" / "unit_tested-report.txt").read_text()
    assert "exit=0" in report_txt
