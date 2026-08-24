"""Graph traversal, lineage and impact analysis.

Edges point downstream in the delivery flow, so:
- impact(node): everything downstream that a change to the node can affect.
- lineage(node): everything upstream that justifies the node's existence.
"""

from collections import deque

from factory.knowledge.graph.store import SqliteGraphStore
from factory.models.graph import GraphEdge


def traverse(
    store: SqliteGraphStore,
    start: str,
    *,
    direction: str = "out",
    max_depth: int = 10,
) -> list[GraphEdge]:
    """Deterministic BFS returning the edges reached from `start`."""
    if store.get_node(start) is None:
        raise ValueError(f"Unknown node: {start}")
    edges_fn = store.out_edges if direction == "out" else store.in_edges
    seen: set[str] = {start}
    result: list[GraphEdge] = []
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    while queue:
        node_id, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in edges_fn(node_id):
            result.append(edge)
            nxt = edge.to_id if direction == "out" else edge.from_id
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, depth + 1))
    return result


def impact(store: SqliteGraphStore, node_id: str, *, max_depth: int = 10) -> list[str]:
    """Downstream node IDs affected by a change to `node_id`."""
    edges = traverse(store, node_id, direction="out", max_depth=max_depth)
    ordered: list[str] = []
    for edge in edges:
        if edge.to_id != node_id and edge.to_id not in ordered:
            ordered.append(edge.to_id)
    return ordered


def lineage(store: SqliteGraphStore, node_id: str, *, max_depth: int = 10) -> list[str]:
    """Upstream node IDs that `node_id` derives from (its provenance chain)."""
    edges = traverse(store, node_id, direction="in", max_depth=max_depth)
    ordered: list[str] = []
    for edge in edges:
        if edge.from_id != node_id and edge.from_id not in ordered:
            ordered.append(edge.from_id)
    return ordered
