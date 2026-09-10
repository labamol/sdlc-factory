from factory.models.enums import FactoryState as S
from factory.orchestrator.state_machine import STATE_MACHINE


def test_happy_path_transitions_exist():
    path = [
        S.BRD_RECEIVED, S.INTAKE, S.CLARIFICATION, S.REQUIREMENTS_READY, S.DECOMPOSED,
        S.SPECIFIED, S.KNOWLEDGE_MINED, S.DESIGNED, S.TASKS_READY, S.TEST_DESIGNED,
        S.IMPLEMENTING, S.BUILT, S.UNIT_TESTED, S.PR_CREATED, S.REVIEWED, S.MERGE_READY,
        S.POLICY_GATE, S.MERGED, S.PACKAGED, S.PUBLISHED, S.DEPLOYED, S.FUNCTIONAL_TESTED,
        S.AC_VALIDATED, S.STORY_COMPLETED, S.LEARNED,
    ]
    for from_state, to_state in zip(path, path[1:], strict=False):
        assert STATE_MACHINE.is_allowed(from_state, to_state), (
            f"missing transition {from_state} -> {to_state}"
        )


def test_disallowed_transition():
    assert not STATE_MACHINE.is_allowed(S.BRD_RECEIVED, S.MERGED)


def test_self_heal_loop_transitions():
    assert STATE_MACHINE.is_allowed(S.UNIT_TESTED, S.DIAGNOSE)
    assert STATE_MACHINE.is_allowed(S.DIAGNOSE, S.RETEST)
    assert STATE_MACHINE.is_allowed(S.RETEST, S.UNIT_TESTED)


def test_clarification_human_loop():
    assert STATE_MACHINE.is_allowed(S.CLARIFICATION, S.HUMAN_INPUT)
    assert STATE_MACHINE.is_allowed(S.HUMAN_INPUT, S.CLARIFICATION)


def test_review_rework_loop():
    assert STATE_MACHINE.is_allowed(S.REVIEWED, S.IMPLEMENTING)


def test_every_transition_bounded():
    for t in STATE_MACHINE.transitions:
        assert t.max_attempts >= 1
        assert t.escalation_state == S.HUMAN_ESCALATION
        assert t.agent


def test_terminal_states():
    assert STATE_MACHINE.is_terminal(S.LEARNED)
    assert STATE_MACHINE.is_terminal(S.HUMAN_ESCALATION)
    assert not STATE_MACHINE.is_terminal(S.IMPLEMENTING)
