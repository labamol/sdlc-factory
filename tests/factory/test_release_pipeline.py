"""Factory tests: merged feature through packaging, deploy, validation, closure."""

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
async def test_release_reaches_story_completed_with_evidence(tmp_path):
    feature = await run_intake(
        tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-R1", release=True
    )
    assert feature.current_state == FactoryState.STORY_COMPLETED
    assert feature.deployment_environment == "local"
    assert feature.functional_test_status == enums.TestStatus.PASSED

    project_dir = tmp_path / "projects" / "PRJ-R1"

    release = yaml.safe_load((project_dir / "release" / "release.yaml").read_text())
    assert release["artifact"].endswith(".tar.gz")
    assert release["artifact_uri"] == f"artifact://PRJ-R1/{release['artifact']}"
    assert release["smoke_passed"] is True
    assert (project_dir / "dist" / release["artifact"]).exists()
    assert (
        project_dir / "artifacts" / "PRJ-R1" / release["artifact"]
    ).exists()

    smoke = yaml.safe_load((project_dir / "release" / "smoke-report.yaml").read_text())
    assert smoke["passed"] and all(c["passed"] for c in smoke["checks"])

    deployment = yaml.safe_load(
        (project_dir / "deployments" / "local" / "deployment.yaml").read_text()
    )
    assert deployment["sha256"] == release["sha256"]
    assert deployment["modules"]

    validation = yaml.safe_load(
        (project_dir / "validation" / "validation-report.yaml").read_text()
    )
    assert validation["decision"] == "PASS"
    assert validation["mandatory_ac_pass_percentage"] == 100.0
    assert len(validation["results"]) == len(feature.acceptance_criteria)
    assert all(r["test_outcome"] == "PASSED" for r in validation["results"])

    completion = yaml.safe_load(
        (project_dir / "tracker" / "completion.yaml").read_text()
    )
    assert {s["status"] for s in completion["stories"]} == {"DONE"}
    assert completion["requirements_closed"] == sorted(feature.requirements)

    kinds = {e.kind for e in feature.evidence}
    assert {
        "artifact", "artifact-uri", "deployment", "smoke-evidence",
        "functional-report", "validation-report", "tracker-completion",
    } <= kinds
