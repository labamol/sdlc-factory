"""Token budgeting: fit ranked context into a fixed budget, never truncate
mid-item, and always leave room for binding decisions."""

from factory.models.context import ScoredItem


def estimate_tokens(text: str) -> int:
    """Deterministic offline token estimate (~4 chars per token)."""
    return max(1, len(text) // 4)


def fit_to_budget(
    ranked: list[ScoredItem], budget_tokens: int
) -> tuple[list[ScoredItem], int]:
    """Greedy pack by rank; binding-authority items are admitted first."""
    binding = [s for s in ranked if s.item.authority == "binding"]
    rest = [s for s in ranked if s.item.authority != "binding"]

    selected: list[ScoredItem] = []
    used = 0
    for scored in binding + rest:
        cost = estimate_tokens(scored.item.content)
        if used + cost > budget_tokens:
            continue
        selected.append(scored)
        used += cost
    selected.sort(key=lambda s: -s.score)
    return selected, used
