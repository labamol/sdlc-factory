import pytest

from factory.healing.memory import Episode
from factory.learning.feedback import FeedbackStore, HumanFeedback
from factory.learning.promotion import LearningPolicy, PromotionStore


def _episode(episode_id: str, signature: str, outcome: str = "REPAIRED") -> Episode:
    return Episode(
        episode_id=episode_id, feature_id="FEAT-01", stage="RETEST",
        failure_class="CODE_DEFECT", signature=signature,
        repair_action="regenerate-implementation",
        repair_owner="implementation-agent", outcome=outcome,
    )


def test_feedback_requires_author_and_persists(tmp_path):
    store = FeedbackStore(tmp_path)
    with pytest.raises(ValueError):
        store.record(
            HumanFeedback(
                feedback_id="FB-1", target_kind="skill", target="testing/pytest-unit",
                rating="positive", author="",
            )
        )
    store.record(
        HumanFeedback(
            feedback_id="FB-1", target_kind="skill", target="testing/pytest-unit",
            rating="positive", comment="good coverage", author="amol",
        )
    )
    assert [f.feedback_id for f in store.all()] == ["FB-1"]


def test_promotion_requires_min_repeated_successful_repairs(tmp_path):
    store = PromotionStore(tmp_path)
    policy = LearningPolicy(min_successful_repairs=2, require_human_approval=True)

    assert store.propose([_episode("EPI-1", "sig-a")], policy) == []
    candidates = store.propose(
        [_episode("EPI-1", "sig-a"), _episode("EPI-2", "sig-a"),
         _episode("EPI-3", "sig-b", outcome="ESCALATED")],
        policy,
    )
    assert len(candidates) == 1
    assert candidates[0].signature == "sig-a"
    assert candidates[0].status == "PROPOSED"
    assert candidates[0].evidence_episodes == ["EPI-1", "EPI-2"]
    # idempotent: same signature is not proposed twice
    assert store.propose([_episode("EPI-1", "sig-a"), _episode("EPI-2", "sig-a")], policy) == []


def test_promotion_approval_is_governed(tmp_path):
    store = PromotionStore(tmp_path)
    policy = LearningPolicy(min_successful_repairs=1, require_human_approval=True)
    [candidate] = store.propose([_episode("EPI-1", "sig-a")], policy)
    assert candidate.status == "PROPOSED"

    with pytest.raises(ValueError):
        store.approve(candidate.candidate_id, "")
    approved = store.approve(candidate.candidate_id, "amol")
    assert approved.status == "APPROVED" and approved.approved_by == "amol"

    with pytest.raises(KeyError):
        store.approve("PROMO-unknown", "amol")


def test_autonomous_promotion_only_when_policy_allows(tmp_path):
    store = PromotionStore(tmp_path)
    policy = LearningPolicy(min_successful_repairs=1, require_human_approval=False)
    [candidate] = store.propose([_episode("EPI-1", "sig-c")], policy)
    assert candidate.status == "APPROVED"
