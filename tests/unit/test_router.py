from factory.models.enums import FailureClass
from factory.orchestrator.router import (
    FAILURE_ROUTES,
    requires_human_when_blocking,
    route_failure,
)


def test_every_failure_class_routes():
    for failure_class in FailureClass:
        assert failure_class in FAILURE_ROUTES


def test_code_defect_routes_to_implementation():
    assert route_failure(FailureClass.CODE_DEFECT) == "implementation-agent"


def test_spec_ambiguity_may_require_human():
    assert requires_human_when_blocking(FailureClass.SPEC_AMBIGUITY)
    assert not requires_human_when_blocking(FailureClass.CODE_DEFECT)
