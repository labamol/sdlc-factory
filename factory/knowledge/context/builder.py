"""Context builder: assemble a versioned, budgeted context pack for a task.

Pipeline: retrieve (vector + exact) -> filter superseded versions -> detect
and resolve authority conflicts -> rerank (similarity + exact-match bonus +
authority weight) -> fit to token budget -> persist versioned pack with full
provenance.
"""

from pathlib import Path

import yaml

from factory.knowledge.context.budget import fit_to_budget
from factory.knowledge.context.filtering import (
    authority_rank,
    detect_conflicts,
    filter_superseded,
    resolve_conflicts,
)
from factory.knowledge.context.store import KnowledgeStore
from factory.models.context import ContextItem, ContextPack, ScoredItem
from factory.orchestrator.events import new_id

AUTHORITY_WEIGHT = 0.15
EXACT_MATCH_BONUS = 0.25


class ContextBuilder:
    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    def build(
        self,
        query: str,
        *,
        feature_id: str,
        spec_version: str | None = None,
        repo_commit: str = "",
        budget_tokens: int = 4000,
        limit: int = 40,
    ) -> ContextPack:
        vector_hits = self.store.vector_search(query, limit=limit)
        exact_ids = {i.item_id for i in self.store.exact_search(query, limit=limit)}
        for term in query.split():
            if term.isupper() or "-" in term:  # likely an ID like BR-06 / FEAT-01
                exact_ids.update(
                    i.item_id for i in self.store.exact_search(term, limit=limit)
                )

        candidates: dict[str, tuple[ContextItem, float]] = {
            item.item_id: (item, score) for item, score in vector_hits
        }
        for item in self.store.all_items():
            if item.item_id in exact_ids and item.item_id not in candidates:
                candidates[item.item_id] = (item, 0.0)

        items = [item for item, _ in candidates.values()]
        current, excluded = filter_superseded(items)
        conflicts = detect_conflicts(current)
        current = resolve_conflicts(current, conflicts)

        ranked: list[ScoredItem] = []
        for item in current:
            base = candidates[item.item_id][1]
            reasons = [f"similarity={base:.3f}"]
            score = base + AUTHORITY_WEIGHT * authority_rank(item)
            reasons.append(f"authority={item.authority}")
            if item.item_id in exact_ids:
                score += EXACT_MATCH_BONUS
                reasons.append("exact-match")
            ranked.append(ScoredItem(item=item, score=round(score, 4), reasons=reasons))
        ranked.sort(key=lambda s: (-s.score, s.item.item_id))

        selected, used = fit_to_budget(ranked, budget_tokens)
        return ContextPack(
            pack_id=new_id("PACK"),
            feature_id=feature_id,
            query=query,
            spec_version=spec_version,
            repo_commit=repo_commit,
            budget_tokens=budget_tokens,
            used_tokens=used,
            items=selected,
            conflicts=conflicts,
            excluded_superseded=sorted(excluded),
        )


def save_pack(pack: ContextPack, directory: Path) -> Path:
    """Persist the pack as a versioned YAML artifact."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{pack.pack_id}.yaml"
    path.write_text(yaml.safe_dump(pack.model_dump(mode="json"), sort_keys=False))
    return path


def render_pack_md(pack: ContextPack) -> str:
    lines = [
        f"# Context Pack {pack.pack_id}",
        "",
        f"- feature: {pack.feature_id}",
        f"- query: {pack.query}",
        f"- spec version: {pack.spec_version or 'n/a'}",
        f"- repo commit: {pack.repo_commit or 'n/a'}",
        f"- tokens: {pack.used_tokens}/{pack.budget_tokens}",
        f"- superseded excluded: {len(pack.excluded_superseded)}",
        "",
        "## Items",
        "",
    ]
    for scored in pack.items:
        item = scored.item
        lines.append(
            f"### {item.item_id} ({item.kind}, {item.authority}, {item.version}) "
            f"score={scored.score}"
        )
        lines.append(f"source: {item.source}" + (f" [{item.subject}]" if item.subject else ""))
        lines.append("")
        lines.append(item.content)
        lines.append("")
    if pack.conflicts:
        lines += ["## Conflicts", ""]
        for conflict in pack.conflicts:
            state = conflict.resolution or "UNRESOLVED"
            lines.append(f"- {conflict.subject}: {conflict.reason} -> {state}")
        lines.append("")
    return "\n".join(lines)
