"""Declarative end-to-end state machine.

Every transition defines entry criteria, responsible agent, allowed tools,
expected artifacts, validation rule, retry route, maximum autonomous attempts
and human escalation condition.
"""

from collections.abc import Callable

from pydantic import BaseModel, Field

from factory.models.enums import FactoryState
from factory.models.feature import FeatureState

S = FactoryState

ValidationRule = Callable[[FeatureState], bool]


def _has_stage_evidence(stage: str) -> ValidationRule:
    def rule(feature: FeatureState) -> bool:
        return len(feature.evidence_for_stage(stage)) > 0

    return rule


class TransitionSpec(BaseModel):
    """Contract for one allowed transition in the factory lifecycle."""

    model_config = {"arbitrary_types_allowed": True}

    from_state: FactoryState
    to_state: FactoryState
    agent: str
    allowed_tools: list[str] = Field(default_factory=list)
    expected_artifacts: list[str] = Field(default_factory=list)
    max_attempts: int = 3
    retry_route: FactoryState | None = None
    escalation_state: FactoryState = FactoryState.HUMAN_ESCALATION
    validation: ValidationRule | None = None

    def validate_outcome(self, feature: FeatureState) -> bool:
        if self.validation is None:
            return True
        return self.validation(feature)


_TRANSITIONS: list[TransitionSpec] = [
    TransitionSpec(
        from_state=S.BRD_RECEIVED, to_state=S.INTAKE, agent="requirements-agent",
        allowed_tools=["filesystem", "documents"], expected_artifacts=["requirements.md"],
        validation=_has_stage_evidence("INTAKE"),
    ),
    TransitionSpec(
        from_state=S.INTAKE, to_state=S.CLARIFICATION, agent="requirements-agent",
        allowed_tools=["filesystem", "context"],
        expected_artifacts=["clarifications.md", "assumptions.md"],
    ),
    TransitionSpec(
        from_state=S.CLARIFICATION, to_state=S.HUMAN_INPUT, agent="orchestrator",
        expected_artifacts=["hitl-request"],
    ),
    TransitionSpec(
        from_state=S.HUMAN_INPUT, to_state=S.CLARIFICATION, agent="requirements-agent",
        expected_artifacts=["decisions.yaml"],
    ),
    TransitionSpec(
        from_state=S.CLARIFICATION, to_state=S.REQUIREMENTS_READY, agent="requirements-agent",
        validation=_has_stage_evidence("CLARIFICATION"),
    ),
    TransitionSpec(
        from_state=S.REQUIREMENTS_READY, to_state=S.DECOMPOSED, agent="product-agent",
        allowed_tools=["jira", "filesystem"],
        expected_artifacts=["features.yaml", "stories.yaml", "traceability.yaml"],
        validation=_has_stage_evidence("DECOMPOSED"),
    ),
    TransitionSpec(
        from_state=S.DECOMPOSED, to_state=S.SPECIFIED, agent="specification-agent",
        allowed_tools=["filesystem", "speckit", "git"],
        expected_artifacts=["spec.md", "acceptance-criteria.md", "tasks.md"],
        validation=_has_stage_evidence("SPECIFIED"),
    ),
    TransitionSpec(
        from_state=S.SPECIFIED, to_state=S.KNOWLEDGE_MINED, agent="knowledge-agent",
        allowed_tools=["git", "context", "knowledge-graph"],
        expected_artifacts=["context-pack.md"],
    ),
    TransitionSpec(
        from_state=S.KNOWLEDGE_MINED, to_state=S.DESIGNED, agent="design-agent",
        allowed_tools=["git", "filesystem"], expected_artifacts=["design.md"],
    ),
    TransitionSpec(
        from_state=S.DESIGNED, to_state=S.TASKS_READY, agent="specification-agent",
        expected_artifacts=["tasks.md"],
    ),
    TransitionSpec(
        from_state=S.TASKS_READY, to_state=S.TEST_DESIGNED, agent="test-agent",
        allowed_tools=["filesystem"], expected_artifacts=["test-plan.yaml"],
    ),
    TransitionSpec(
        from_state=S.TEST_DESIGNED, to_state=S.IMPLEMENTING, agent="implementation-agent",
        allowed_tools=["git", "filesystem", "terminal"],
    ),
    TransitionSpec(
        from_state=S.IMPLEMENTING, to_state=S.BUILT, agent="implementation-agent",
        allowed_tools=["git", "filesystem", "terminal"],
        expected_artifacts=["source", "feature-branch"],
    ),
    TransitionSpec(
        from_state=S.BUILT, to_state=S.UNIT_TESTED, agent="test-agent",
        allowed_tools=["pytest", "terminal"], expected_artifacts=["test-report"],
        retry_route=S.DIAGNOSE,
    ),
    TransitionSpec(
        from_state=S.UNIT_TESTED, to_state=S.DIAGNOSE, agent="orchestrator",
        expected_artifacts=["failure-classification"],
    ),
    TransitionSpec(
        from_state=S.DIAGNOSE, to_state=S.RETEST, agent="implementation-agent",
        allowed_tools=["git", "filesystem", "terminal", "pytest"],
        retry_route=S.DIAGNOSE,
    ),
    TransitionSpec(
        from_state=S.RETEST, to_state=S.UNIT_TESTED, agent="test-agent",
        allowed_tools=["pytest", "terminal"],
    ),
    TransitionSpec(
        from_state=S.UNIT_TESTED, to_state=S.PR_CREATED, agent="review-agent",
        allowed_tools=["github"], expected_artifacts=["pr"],
        validation=_has_stage_evidence("PR_CREATED"),
    ),
    TransitionSpec(
        from_state=S.PR_CREATED, to_state=S.REVIEWED, agent="review-agent",
        allowed_tools=["github", "scanners"], expected_artifacts=["review-report.md"],
    ),
    TransitionSpec(
        from_state=S.REVIEWED, to_state=S.IMPLEMENTING, agent="implementation-agent",
        allowed_tools=["git", "filesystem", "terminal"],
    ),
    TransitionSpec(
        from_state=S.REVIEWED, to_state=S.MERGE_READY, agent="review-agent",
        validation=_has_stage_evidence("REVIEWED"),
    ),
    TransitionSpec(
        from_state=S.MERGE_READY, to_state=S.POLICY_GATE, agent="orchestrator",
        allowed_tools=["policy"],
    ),
    TransitionSpec(
        from_state=S.POLICY_GATE, to_state=S.MERGED, agent="orchestrator",
        allowed_tools=["git", "policy"], expected_artifacts=["merge-decision"],
        validation=_has_stage_evidence("POLICY_GATE"),
    ),
    TransitionSpec(
        from_state=S.MERGED, to_state=S.PACKAGED, agent="release-agent",
        allowed_tools=["docker", "terminal"], expected_artifacts=["artifact"],
    ),
    TransitionSpec(
        from_state=S.PACKAGED, to_state=S.PUBLISHED, agent="release-agent",
        allowed_tools=["artifact-repo"], expected_artifacts=["artifact-uri"],
    ),
    TransitionSpec(
        from_state=S.PUBLISHED, to_state=S.DEPLOYED, agent="release-agent",
        allowed_tools=["docker", "terminal"],
        expected_artifacts=["deployment", "smoke-evidence"],
    ),
    TransitionSpec(
        from_state=S.DEPLOYED, to_state=S.FUNCTIONAL_TESTED, agent="validation-agent",
        allowed_tools=["pytest", "playwright"], expected_artifacts=["functional-report"],
    ),
    TransitionSpec(
        from_state=S.FUNCTIONAL_TESTED, to_state=S.AC_VALIDATED, agent="validation-agent",
        expected_artifacts=["validation-report"],
        validation=_has_stage_evidence("AC_VALIDATED"),
    ),
    TransitionSpec(
        from_state=S.AC_VALIDATED, to_state=S.STORY_COMPLETED, agent="validation-agent",
        allowed_tools=["jira"], expected_artifacts=["tracker-completion"],
    ),
    TransitionSpec(
        from_state=S.STORY_COMPLETED, to_state=S.LEARNED, agent="learning-agent",
        expected_artifacts=["learning-record.yaml"],
    ),
]


class StateMachine:
    """Lookup and validation over the declarative transition table."""

    def __init__(self, transitions: list[TransitionSpec] | None = None) -> None:
        self._transitions = transitions if transitions is not None else list(_TRANSITIONS)

    @property
    def transitions(self) -> list[TransitionSpec]:
        return list(self._transitions)

    def transitions_from(self, state: FactoryState) -> list[TransitionSpec]:
        return [t for t in self._transitions if t.from_state == state]

    def find(self, from_state: FactoryState, to_state: FactoryState) -> TransitionSpec | None:
        for t in self._transitions:
            if t.from_state == from_state and t.to_state == to_state:
                return t
        return None

    def is_allowed(self, from_state: FactoryState, to_state: FactoryState) -> bool:
        return self.find(from_state, to_state) is not None

    def is_terminal(self, state: FactoryState) -> bool:
        return state in (FactoryState.LEARNED, FactoryState.HUMAN_ESCALATION) or not (
            self.transitions_from(state)
        )


STATE_MACHINE = StateMachine()
