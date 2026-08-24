"""Governed skill/template promotion.

Recurring successful repairs become promotion candidates for the skill and
template catalogue. Promotion is governed: candidates are only proposed when
a signature has been repaired at least the policy minimum number of times,
and they stay PROPOSED until a named human approves them (unless the policy
explicitly allows autonomous promotion).
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from factory.healing.memory import Episode

PROMOTIONS_FILE = "learning/promotions.yaml"
DEFAULT_MIN_REPAIRS = 2


class LearningPolicy(BaseModel):
    min_successful_repairs: int = DEFAULT_MIN_REPAIRS
    require_human_approval: bool = True


def load_learning_policy(policies_dir: Path) -> LearningPolicy:
    path = policies_dir / "learning.yaml"
    if not path.exists():
        return LearningPolicy()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    promotion = raw.get("learning_policy", {}).get("promotion", {})
    return LearningPolicy.model_validate(promotion)


class PromotionCandidate(BaseModel):
    candidate_id: str
    kind: str = "skill-update"
    signature: str
    failure_class: str
    repair_action: str
    occurrences: int
    proposal: str
    status: str = "PROPOSED"  # PROPOSED | APPROVED | REJECTED
    approved_by: str = ""
    evidence_episodes: list[str] = Field(default_factory=list)


class PromotionStore:
    def __init__(self, project_dir: Path) -> None:
        self.path = project_dir / PROMOTIONS_FILE

    def all(self) -> list[PromotionCandidate]:
        if not self.path.exists():
            return []
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or []
        return [PromotionCandidate.model_validate(c) for c in raw]

    def _save(self, candidates: list[PromotionCandidate]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                [c.model_dump(mode="json") for c in candidates], sort_keys=False
            ),
            encoding="utf-8",
        )

    def propose(
        self, episodes: list[Episode], policy: LearningPolicy
    ) -> list[PromotionCandidate]:
        """Derive candidates from repaired episodes; idempotent per signature."""
        existing = self.all()
        known_signatures = {c.signature for c in existing}
        groups: dict[str, list[Episode]] = {}
        for episode in episodes:
            if episode.outcome == "REPAIRED":
                groups.setdefault(episode.signature, []).append(episode)

        new_candidates = []
        for signature, group in sorted(groups.items()):
            if len(group) < policy.min_successful_repairs:
                continue
            if signature in known_signatures:
                continue
            sample = group[0]
            candidate = PromotionCandidate(
                candidate_id=f"PROMO-{signature[:8]}",
                signature=signature,
                failure_class=sample.failure_class,
                repair_action=sample.repair_action,
                occurrences=len(group),
                proposal=(
                    f"Promote '{sample.repair_action}' as the standard repair for "
                    f"{sample.failure_class} failures with signature {signature}"
                ),
                status="PROPOSED" if policy.require_human_approval else "APPROVED",
                evidence_episodes=[e.episode_id for e in group],
            )
            new_candidates.append(candidate)
        if new_candidates:
            self._save(existing + new_candidates)
        return new_candidates

    def approve(self, candidate_id: str, approved_by: str) -> PromotionCandidate:
        if not approved_by:
            raise ValueError("Promotion approval requires a named approver")
        candidates = self.all()
        for candidate in candidates:
            if candidate.candidate_id == candidate_id:
                candidate.status = "APPROVED"
                candidate.approved_by = approved_by
                self._save(candidates)
                return candidate
        raise KeyError(f"Unknown promotion candidate: {candidate_id}")

    def reject(self, candidate_id: str, rejected_by: str) -> PromotionCandidate:
        if not rejected_by:
            raise ValueError("Promotion rejection requires a named reviewer")
        candidates = self.all()
        for candidate in candidates:
            if candidate.candidate_id == candidate_id:
                candidate.status = "REJECTED"
                candidate.approved_by = rejected_by
                self._save(candidates)
                return candidate
        raise KeyError(f"Unknown promotion candidate: {candidate_id}")
