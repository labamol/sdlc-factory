from pydantic import BaseModel, Field

from factory.models.enums import FactoryState, TestStatus
from factory.models.evidence import Evidence


class FeatureState(BaseModel):
    """Typed durable state for one feature traversing the factory lifecycle."""

    feature_id: str
    project_id: str
    title: str = ""
    requirements: list[str] = Field(default_factory=list)
    stories: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    spec_version: str | None = None
    branch: str | None = None
    pull_request: int | None = None
    unit_test_status: TestStatus = TestStatus.NOT_RUN
    integration_test_status: TestStatus = TestStatus.NOT_RUN
    functional_test_status: TestStatus = TestStatus.NOT_RUN
    coverage: float | None = None
    deployment_environment: str | None = None
    current_state: FactoryState = FactoryState.BRD_RECEIVED
    retry_count: int = 0
    evidence: list[Evidence] = Field(default_factory=list)

    def add_evidence(self, evidence: Evidence) -> None:
        self.evidence.append(evidence)

    def evidence_for_stage(self, stage: str) -> list[Evidence]:
        return [e for e in self.evidence if e.stage == stage]
