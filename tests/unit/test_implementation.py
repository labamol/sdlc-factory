from factory.agents.workers import WORKER_PROFILES, select_worker
from factory.implementation.codegen import (
    feature_module_name,
    generate_feature_module,
    story_function_name,
)
from factory.implementation.synthdata import generate_synthetic_records
from factory.implementation.testgen import generate_feature_tests
from factory.models.requirement import Feature
from factory.models.story import AcceptanceCriterion, Story


def _fixture() -> tuple[Feature, list[Story]]:
    feature = Feature(feature_id="FEAT-01", title="Feedback Capture")
    story = Story(
        story_id="STORY-01.01",
        feature_id="FEAT-01",
        title="Submit feedback",
        description="Users can submit feedback",
        acceptance_criteria=[
            AcceptanceCriterion(ac_id="AC-01.01.01", description="submission stored"),
            AcceptanceCriterion(ac_id="AC-01.01.02", description="empty input rejected"),
        ],
    )
    return feature, [story]


def test_worker_selection_by_tech_hints():
    assert select_worker("React form for feedback UI").worker_id == "react-frontend-worker"
    assert select_worker("Weekly summary report with SQL").worker_id == "data-worker"
    assert select_worker("Miscellaneous").worker_id == WORKER_PROFILES[0].worker_id


def test_synthetic_data_is_deterministic_and_safe():
    a = generate_synthetic_records("STORY-01.01", count=3)
    b = generate_synthetic_records("STORY-01.01", count=3)
    assert a == b
    assert len(a) == 3
    assert all("@" in r["email"] and "example" in r["email"] or "." in r["email"] for r in a)
    assert generate_synthetic_records("STORY-02.01") != a


def test_generated_module_executes_story_contract(tmp_path):
    feature, stories = _fixture()
    source = generate_feature_module(feature, stories)
    namespace: dict = {}
    exec(compile(source, "feat_01.py", "exec"), namespace)  # noqa: S102
    func = namespace[story_function_name("STORY-01.01")]
    stored = func({"name": "Ava", "email": "ava@example.com"})
    assert stored["story_id"] == "STORY-01.01"
    assert stored["record_id"] == 1
    error = namespace["ServiceError"]
    try:
        func({})
        raise AssertionError("expected ServiceError")
    except error:
        pass
    assert "AC-01.01.01" in source and "AC-01.01.02" in source


def test_generated_tests_cover_every_ac():
    feature, stories = _fixture()
    tests = generate_feature_tests(feature, stories)
    assert "def test_ac_01_01_01" in tests
    assert "def test_ac_01_01_02" in tests
    assert f"import {feature_module_name('FEAT-01')}" in tests
    assert "pytest.raises" in tests
