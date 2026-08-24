from factory.agents.ambiguity import analyze_requirements, classify, has_blocking
from factory.models.enums import AmbiguityClass
from factory.models.requirement import Requirement


def _req(req_id: str, statement: str) -> Requirement:
    return Requirement(req_id=req_id, statement=statement, source="test")


def test_blocking_markers_detected():
    cls, trigger = classify("Retention period is TBD pending compliance.")
    assert cls == AmbiguityClass.BLOCKING
    assert trigger == "TBD"
    cls, _ = classify("The channel is a pending decision.")
    assert cls == AmbiguityClass.BLOCKING


def test_vague_markers_are_material_assumable():
    cls, trigger = classify("The dashboard should feel fast and user-friendly.")
    assert cls == AmbiguityClass.MATERIAL_ASSUMABLE
    assert trigger == "fast"


def test_detail_markers_are_implementation_detail():
    cls, _ = classify("Use consistent logging across services.")
    assert cls == AmbiguityClass.IMPLEMENTATION_DETAIL


def test_unambiguous_statement_returns_none():
    cls, trigger = classify("The system stores submissions in the database.")
    assert cls is None
    assert trigger == ""


def test_analyze_creates_assumptions_only_for_material_class():
    clarifications, assumptions = analyze_requirements(
        [
            _req("BR-01", "Retention is TBD."),
            _req("BR-02", "The UI should be intuitive."),
            _req("BR-03", "Apply the standard log format."),
            _req("BR-04", "Store submissions durably."),
        ]
    )
    by_req = {c.req_id: c for c in clarifications}
    assert by_req["BR-01"].status == "OPEN"
    assert by_req["BR-02"].status == "ASSUMED"
    assert by_req["BR-03"].status == "ASSUMED"
    assert "BR-04" not in by_req
    assert [a.req_id for a in assumptions] == ["BR-02"]


def test_has_blocking_only_counts_open_blocking():
    clarifications, _ = analyze_requirements([_req("BR-01", "Retention is TBD.")])
    assert has_blocking(clarifications)
    clarifications[0].status = "ANSWERED"
    assert not has_blocking(clarifications)
