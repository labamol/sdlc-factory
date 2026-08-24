from pathlib import Path

import pytest

from factory.agents.selfheal import SelfHealAgent
from factory.healing.memory import Episode, EpisodicMemory
from factory.healing.repair import REPAIR_ROUTES
from factory.healing.taxonomy import classify_failure
from factory.models import enums
from factory.models.enums import FactoryState, FailureClass
from factory.models.feature import FeatureState

POLICIES_DIR = Path(__file__).resolve().parents[2] / "policies"


def test_classify_assertion_failure_as_code_defect():
    report = "FAILED tests/test_x.py::test_ac - AssertionError: assert 1 == 2"
    diagnosis = classify_failure(report)
    assert diagnosis.failure_class == FailureClass.CODE_DEFECT
    assert diagnosis.signature


def test_classify_missing_module_as_dependency_defect():
    report = "E   ModuleNotFoundError: No module named 'requests'"
    assert classify_failure(report).failure_class == FailureClass.DEPENDENCY_DEFECT


def test_classify_template_regression():
    report = 'E   RuntimeError: injected template regression'
    assert (
        classify_failure(report).failure_class == FailureClass.FACTORY_TEMPLATE_DEFECT
    )


def test_classify_environment_defect():
    report = "E   PermissionError: [Errno 13] Permission denied: '/etc/hosts'"
    assert classify_failure(report).failure_class == FailureClass.ENVIRONMENT_DEFECT


def test_signature_is_stable_and_normalized():
    a = classify_failure("E   AssertionError: assert 12 == 34 at /home/a/x.py:12")
    b = classify_failure("E   AssertionError: assert 56 == 78 at /home/b/y.py:99")
    assert a.signature == b.signature


def test_every_failure_class_has_a_repair_route():
    assert set(REPAIR_ROUTES) == set(FailureClass)
    for route in REPAIR_ROUTES.values():
        assert route.owner_agent and route.action


def test_non_autonomous_routes_require_humans():
    assert not REPAIR_ROUTES[FailureClass.SPEC_DEFECT].autonomous
    assert not REPAIR_ROUTES[FailureClass.ENVIRONMENT_DEFECT].autonomous
    assert REPAIR_ROUTES[FailureClass.CODE_DEFECT].autonomous


@pytest.fixture
def episode() -> Episode:
    return Episode(
        episode_id="EPI-1", feature_id="FEAT-01", stage="RETEST",
        failure_class="CODE_DEFECT", signature="abc123",
        repair_action="regenerate-implementation", repair_owner="implementation-agent",
    )


def test_episodic_memory_record_find_update(tmp_path, episode):
    memory = EpisodicMemory(tmp_path)
    memory.record(episode)
    assert memory.attempts_for("FEAT-01") == 1
    found = memory.find_by_signature("abc123")
    assert len(found) == 1 and found[0].outcome == "PENDING"

    episode.outcome = "REPAIRED"
    memory.update(episode)
    assert memory.find_by_signature("abc123")[0].outcome == "REPAIRED"
    assert enums.FailureClass(found[0].failure_class) == FailureClass.CODE_DEFECT


def _feature() -> FeatureState:
    return FeatureState(
        feature_id="FEAT-01", project_id="PRJ-T", title="test feature"
    )


@pytest.mark.asyncio
async def test_selfheal_escalates_non_autonomous_failure(tmp_path):
    (tmp_path / "testing").mkdir()
    (tmp_path / "testing" / "unit_tested-report.txt").write_text(
        "FAILED tests/test_x.py::test_ac - acceptance criteria not met\n"
    )
    agent = SelfHealAgent(tmp_path, POLICIES_DIR)
    result = await agent.execute(_feature(), FactoryState.RETEST)
    assert result.status == "FAILURE"
    assert "SPEC_DEFECT" in result.summary

    episodes = EpisodicMemory(tmp_path).all()
    assert len(episodes) == 1 and episodes[0].outcome == "ESCALATED"


@pytest.mark.asyncio
async def test_selfheal_respects_attempt_budget(tmp_path):
    (tmp_path / "testing").mkdir()
    (tmp_path / "testing" / "unit_tested-report.txt").write_text(
        "E   AssertionError: assert 1 == 2\n"
    )
    memory = EpisodicMemory(tmp_path)
    for i in range(3):
        memory.record(
            Episode(
                episode_id=f"EPI-{i}", feature_id="FEAT-01", stage="RETEST",
                failure_class="CODE_DEFECT", signature="sig", attempt=i + 1,
            )
        )
    agent = SelfHealAgent(tmp_path, POLICIES_DIR)
    result = await agent.execute(_feature(), FactoryState.RETEST)
    assert result.status == "FAILURE"
    assert "budget exhausted" in result.summary
