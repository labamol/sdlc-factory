from factory.agents.product import build_traceability, decompose
from factory.models.requirement import Requirement


def _reqs() -> list[Requirement]:
    return [
        Requirement(req_id="BR-01", statement="Submit feedback.", source="brd", section="Submit"),
        Requirement(req_id="BR-02", statement="Acknowledge it.", source="brd", section="Submit"),
        Requirement(req_id="BR-03", statement="Weekly report.", source="brd", section="Reporting"),
    ]


def test_features_grouped_by_section():
    features, stories = decompose(_reqs())
    assert [f.title for f in features] == ["Submit", "Reporting"]
    assert features[0].requirements == ["BR-01", "BR-02"]
    assert features[1].requirements == ["BR-03"]
    assert len(stories) == 3


def test_every_story_has_positive_and_negative_criteria():
    _, stories = decompose(_reqs())
    for story in stories:
        assert len(story.acceptance_criteria) == 2
        assert all(ac.ac_id.startswith("AC-") for ac in story.acceptance_criteria)


def test_traceability_covers_all_requirements_and_acs():
    features, stories = decompose(_reqs())
    trace = build_traceability(features, stories)
    traced_reqs = [r for f in trace["features"] for r in f["requirements"]]
    assert traced_reqs == ["BR-01", "BR-02", "BR-03"]
    traced_acs = [
        ac
        for f in trace["features"]
        for s in f["stories"]
        for ac in s["acceptance_criteria"]
    ]
    assert len(traced_acs) == 6
    assert len(set(traced_acs)) == 6


def test_requirement_without_section_falls_back_to_general():
    features, _ = decompose(
        [Requirement(req_id="BR-01", statement="Do a thing.", source="brd")]
    )
    assert features[0].title == "General"
