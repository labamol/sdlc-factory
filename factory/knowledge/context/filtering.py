"""Authority and version filtering plus conflict detection.

Superseded items never enter a context pack. When two current items make
claims about the same subject at different authority levels, the higher
authority wins; equal-authority disagreements are surfaced as conflicts for
human or policy resolution instead of being silently mixed into context.
"""

from factory.models.context import ContextConflict, ContextItem

AUTHORITY_RANK = {"binding": 3, "authoritative": 2, "informative": 1}


def authority_rank(item: ContextItem) -> int:
    return AUTHORITY_RANK.get(item.authority, 0)


def filter_superseded(items: list[ContextItem]) -> tuple[list[ContextItem], list[str]]:
    """Drop superseded items; return (current, excluded ids)."""
    superseded = {i.supersedes for i in items if i.supersedes}
    current: list[ContextItem] = []
    excluded: list[str] = []
    for item in items:
        if item.superseded_by or item.item_id in superseded:
            excluded.append(item.item_id)
        else:
            current.append(item)
    return current, excluded


def detect_conflicts(items: list[ContextItem]) -> list[ContextConflict]:
    """Flag same-subject decision-grade items with differing content."""
    by_subject: dict[str, list[ContextItem]] = {}
    for item in items:
        if item.subject and item.kind in ("decision", "assumption"):
            by_subject.setdefault(item.subject, []).append(item)

    conflicts: list[ContextConflict] = []
    for subject, group in sorted(by_subject.items()):
        if len(group) < 2:
            continue
        contents = {i.content for i in group}
        if len(contents) < 2:
            continue
        top = max(authority_rank(i) for i in group)
        leaders = [i for i in group if authority_rank(i) == top]
        if len(leaders) == 1:
            resolution = f"kept highest authority item {leaders[0].item_id}"
        else:
            resolution = ""  # unresolved: equal authority, different claims
        conflicts.append(
            ContextConflict(
                subject=subject,
                item_ids=sorted(i.item_id for i in group),
                reason="multiple current decision-grade items disagree",
                resolution=resolution,
            )
        )
    return conflicts


def resolve_conflicts(
    items: list[ContextItem], conflicts: list[ContextConflict]
) -> list[ContextItem]:
    """Drop lower-authority sides of resolved conflicts from the candidate set."""
    dropped: set[str] = set()
    for conflict in conflicts:
        if not conflict.resolution:
            continue
        keep = conflict.resolution.rsplit(" ", 1)[-1]
        dropped.update(i for i in conflict.item_ids if i != keep)
    return [i for i in items if i.item_id not in dropped]
