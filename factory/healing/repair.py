"""Repair routing.

Every failure class routes to exactly one repair owner and action. Classes
the factory can repair autonomously regenerate artifacts from their
deterministic templates; the rest require human input and route to
escalation instead of guessing.
"""

from pydantic import BaseModel

from factory.models.enums import FailureClass


class RepairRoute(BaseModel):
    failure_class: FailureClass
    owner_agent: str
    action: str
    autonomous: bool


REPAIR_ROUTES: dict[FailureClass, RepairRoute] = {
    route.failure_class: route
    for route in (
        RepairRoute(
            failure_class=FailureClass.CODE_DEFECT,
            owner_agent="implementation-agent",
            action="regenerate-implementation", autonomous=True,
        ),
        RepairRoute(
            failure_class=FailureClass.TEST_DEFECT,
            owner_agent="test-agent",
            action="regenerate-tests", autonomous=True,
        ),
        RepairRoute(
            failure_class=FailureClass.DATA_DEFECT,
            owner_agent="test-agent",
            action="regenerate-synthetic-data", autonomous=True,
        ),
        RepairRoute(
            failure_class=FailureClass.FACTORY_TEMPLATE_DEFECT,
            owner_agent="implementation-agent",
            action="regenerate-implementation", autonomous=True,
        ),
        RepairRoute(
            failure_class=FailureClass.SPEC_DEFECT,
            owner_agent="specification-agent",
            action="respecify-with-human-review", autonomous=False,
        ),
        RepairRoute(
            failure_class=FailureClass.SPEC_AMBIGUITY,
            owner_agent="requirements-agent",
            action="raise-clarification", autonomous=False,
        ),
        RepairRoute(
            failure_class=FailureClass.ENVIRONMENT_DEFECT,
            owner_agent="orchestrator",
            action="repair-environment", autonomous=False,
        ),
        RepairRoute(
            failure_class=FailureClass.DEPENDENCY_DEFECT,
            owner_agent="orchestrator",
            action="repair-dependencies", autonomous=False,
        ),
        RepairRoute(
            failure_class=FailureClass.CONFIGURATION_DEFECT,
            owner_agent="orchestrator",
            action="repair-configuration", autonomous=False,
        ),
    )
}
