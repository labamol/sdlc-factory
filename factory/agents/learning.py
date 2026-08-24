"""Learning agent.

Owns LEARNED: aggregates episodic memory, human feedback and governed
promotion candidates into a durable learning record for the feature. It
proposes promotions from recurring successful repairs but never applies
them — promotion requires human approval per `policies/learning.yaml`.
"""

from collections.abc import Iterable
from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.healing.memory import EpisodicMemory
from factory.learning.feedback import FeedbackStore
from factory.learning.promotion import PromotionStore, load_learning_policy
from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.orchestrator.events import new_id
from factory.tools.filesystem import FilesystemTool


class LearningAgent:
    name = "learning-agent"

    def __init__(self, project_dir: Path, policies_dir: Path) -> None:
        self.project_dir = project_dir
        self.policies_dir = policies_dir
        self.fs = FilesystemTool(project_dir)

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage != FactoryState.LEARNED:
            return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

        memory = EpisodicMemory(self.project_dir)
        episodes = memory.all()
        feedback = FeedbackStore(self.project_dir).all()
        promotions = PromotionStore(self.project_dir)
        policy = load_learning_policy(self.policies_dir)
        proposed = promotions.propose(episodes, policy)

        record = {
            "feature_id": feature.feature_id,
            "episodes": {
                "total": len(episodes),
                "repaired": len([e for e in episodes if e.outcome == "REPAIRED"]),
                "escalated": len([e for e in episodes if e.outcome == "ESCALATED"]),
                "by_failure_class": _count_by(e.failure_class for e in episodes),
            },
            "feedback": {
                "total": len(feedback),
                "by_rating": _count_by(f.rating for f in feedback),
            },
            "promotions": {
                "proposed_now": [c.candidate_id for c in proposed],
                "total": len(promotions.all()),
                "approved": len([c for c in promotions.all() if c.status == "APPROVED"]),
                "policy": policy.model_dump(mode="json"),
            },
        }
        path = self.fs.write_text(
            "learning/learning-record.yaml", yaml.safe_dump(record, sort_keys=False)
        )
        return AgentResult(
            summary=f"Learning record: {len(episodes)} episode(s), "
                    f"{len(feedback)} feedback item(s), "
                    f"{len(proposed)} new promotion candidate(s)",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="learning-record",
                    ref=str(path),
                    summary=f"{len(episodes)} episodes; {len(proposed)} promotions proposed",
                )
            ],
            skill="learning/episodic-memory",
        )


def _count_by(keys: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in keys:
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
