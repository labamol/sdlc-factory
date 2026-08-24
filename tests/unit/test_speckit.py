import pytest

from factory.models.requirement import Assumption, Decision, Feature, Requirement
from factory.models.story import AcceptanceCriterion, Story
from factory.speckit.adapter import SpecAnalysisError, SpecKitAdapter
from factory.speckit.lifecycle import SPEC_LIFECYCLE
from factory.tools.git import GitTool


@pytest.fixture
def feature() -> Feature:
    return Feature(feature_id="FEAT-01", title="Submission", requirements=["BR-01"])


@pytest.fixture
def requirements() -> list[Requirement]:
    return [Requirement(req_id="BR-01", statement="Submit feedback.", source="brd")]


@pytest.fixture
def stories() -> list[Story]:
    return [
        Story(
            story_id="STORY-01.01",
            feature_id="FEAT-01",
            title="Submit feedback",
            description="Submit feedback.",
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="AC-01.01.01", description="Positive case."),
                AcceptanceCriterion(ac_id="AC-01.01.02", description="Negative case."),
            ],
        )
    ]


def test_lifecycle_produces_all_artifacts(tmp_path, feature, requirements, stories):
    adapter = SpecKitAdapter(tmp_path)
    artifacts = adapter.run_lifecycle(feature, requirements, stories, [], [])
    assert set(artifacts) == set(SPEC_LIFECYCLE)
    spec_dir = tmp_path / "specs" / "FEAT-01"
    for name in ("spec.md", "clarifications.md", "plan.md", "tasks.md", "analysis.md"):
        assert (spec_dir / name).exists()
    assert "PASS" in (spec_dir / "analysis.md").read_text()


def test_clarify_folds_decisions_and_assumptions(tmp_path, feature, requirements, stories):
    adapter = SpecKitAdapter(tmp_path)
    decisions = [
        Decision(decision_id="DEC-001", source="meeting", requirement="BR-01",
                 decision="Retain 24 months."),
        Decision(decision_id="DEC-002", source="meeting", requirement="BR-99",
                 feature="FEAT-99", decision="Unrelated."),
    ]
    assumptions = [
        Assumption(asm_id="ASM-001", req_id="BR-01", statement="Default page size 50."),
    ]
    adapter.run_lifecycle(feature, requirements, stories, decisions, assumptions)
    text = (tmp_path / "specs" / "FEAT-01" / "clarifications.md").read_text()
    assert "DEC-001" in text
    assert "DEC-002" not in text
    assert "ASM-001" in text


def test_analyze_fails_closed_on_missing_task_coverage(tmp_path, feature, requirements, stories):
    adapter = SpecKitAdapter(tmp_path)
    adapter.specify(feature, requirements, stories)
    adapter.clarify(feature, [], [])
    adapter.plan(feature)
    adapter.tasks(feature, [])  # no stories -> no task coverage
    with pytest.raises(SpecAnalysisError):
        adapter.analyze(feature, stories)
    assert "FAIL" in (tmp_path / "specs" / "FEAT-01" / "analysis.md").read_text()


def test_spec_commit_versions_artifacts_in_git(tmp_path, feature, requirements, stories):
    git = GitTool(tmp_path)
    git.init()
    git.configure_identity("test", "test@localhost")
    adapter = SpecKitAdapter(tmp_path)
    adapter.run_lifecycle(feature, requirements, stories, [], [])
    commit = adapter.commit_spec(feature, "v1")
    assert commit
    assert adapter.commit_spec(feature, "v1") is None  # nothing new to commit
