"""Failure classification routing: which agent owns each failure class."""

from factory.models.enums import FailureClass

FAILURE_ROUTES: dict[FailureClass, str] = {
    FailureClass.CODE_DEFECT: "implementation-agent",
    FailureClass.TEST_DEFECT: "test-agent",
    FailureClass.SPEC_DEFECT: "specification-agent",
    FailureClass.SPEC_AMBIGUITY: "requirements-agent",
    FailureClass.DATA_DEFECT: "requirements-agent",
    FailureClass.ENVIRONMENT_DEFECT: "release-agent",
    FailureClass.DEPENDENCY_DEFECT: "implementation-agent",
    FailureClass.CONFIGURATION_DEFECT: "release-agent",
    FailureClass.FACTORY_TEMPLATE_DEFECT: "learning-backlog",
}

HUMAN_IF_BLOCKING: set[FailureClass] = {FailureClass.SPEC_AMBIGUITY}


def route_failure(failure_class: FailureClass) -> str:
    return FAILURE_ROUTES[failure_class]


def requires_human_when_blocking(failure_class: FailureClass) -> bool:
    return failure_class in HUMAN_IF_BLOCKING
