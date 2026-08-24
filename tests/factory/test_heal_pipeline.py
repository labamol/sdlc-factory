"""Factory tests: bounded self-healing and episodic learning pipelines."""

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
async def test_heal_recovers_from_injected_defect(tmp_path):
    feature = await run_intake(
        tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-H1", heal_demo=True
    )
    assert feature.current_state == FactoryState.UNIT_TESTED
    assert feature.unit_test_status == enums.TestStatus.PASSED

    project_dir = tmp_path / "projects" / "PRJ-H1"

    episodes = yaml.safe_load(
        (project_dir / "learning" / "episodes.yaml").read_text()
    )
    assert len(episodes) == 1
    episode = episodes[0]
    assert episode["failure_class"] == "FACTORY_TEMPLATE_DEFECT"
    assert episode["repair_action"] == "regenerate-implementation"
    assert episode["outcome"] == "REPAIRED"
    assert episode["attempt"] == 1
    assert episode["signature"]

    diagnosis = yaml.safe_load(
        (project_dir / "healing" / "diagnosis-1.yaml").read_text()
    )
    assert diagnosis["diagnosis"]["failure_class"] == "FACTORY_TEMPLATE_DEFECT"
    assert diagnosis["repair_route"]["autonomous"] is True
    assert diagnosis["max_attempts"] == 3

    kinds = {e.kind for e in feature.evidence}
    assert {"diagnosis", "repair"} <= kinds


@pytest.mark.asyncio
async def test_learn_reaches_learned_with_learning_record(tmp_path):
    feature = await run_intake(
        tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-L1", learn=True
    )
    assert feature.current_state == FactoryState.LEARNED

    project_dir = tmp_path / "projects" / "PRJ-L1"
    record = yaml.safe_load(
        (project_dir / "learning" / "learning-record.yaml").read_text()
    )
    assert record["feature_id"] == feature.feature_id
    assert record["episodes"]["total"] == 0
    assert record["promotions"]["policy"]["require_human_approval"] is True

    kinds = {e.kind for e in feature.evidence}
    assert "learning-record" in kinds
